#!/usr/bin/env python3
"""Feed extracted terrain PBC records to original native height consumers.

PBC JSON is reserialized as the externally cross-checked 52-byte record, then
the unchanged native height writer runs over a reconstructed, tiled 8x8 world.
This tests consumption of payload values, not the original PBC loader or island
world construction.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import struct
import sys
import zipfile


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from audit_manifest_pbc import pbc_path_info, rotate_n  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest_zip", type=Path)
    parser.add_argument("--research-root", type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / "output/mechanics/terrain_pbc_native_consumers.json")
    args = parser.parse_args()

    manifest = json.loads((ROOT / "output/manifest.json").read_text())
    source_root = (args.research_root or Path(manifest["source_root"])).resolve()
    source_tools = source_root / "tools"
    if not source_tools.is_dir():
        raise FileNotFoundError(f"research tools directory not found: {source_tools}")
    # RouteHarness/Sandbox must import against the research checkout's pinned
    # ELF and local Unicorn/Capstone dependencies.
    sys.path.insert(0, str(source_tools))
    from terrain_nav_flags_native import WorldHarness  # noqa: E402

    archive_path = args.manifest_zip.resolve()
    digest = hashlib.sha256(archive_path.read_bytes()).hexdigest()
    table = json.loads((source_root / "output/tables_resolved/FieldLandMakingUnitModelParam.json").read_text())
    columns = {column["name"]: index for index, column in enumerate(table["columns"]) if column.get("name")}
    model_by_id = {row[columns["UniqueID"]]: row[columns["ModelName"]] for row in table["rows"]}
    preset_paths = sorted((source_root / "output/world").glob("FieldPreset*_LandMaking.json"))
    if len(preset_paths) != 96:
        raise AssertionError(f"expected 96 decoded presets, found {len(preset_paths)}")
    used_ids = {
        cell[0]
        for path in preset_paths
        for cell in json.loads(path.read_text())["cells"]
    }

    with zipfile.ZipFile(archive_path) as archive:
        bad_member = archive.testzip()
        if bad_member:
            raise AssertionError(f"ZIP CRC failed at {bad_member}")
        pbc_by_model = {}
        for member in archive.namelist():
            if not member.endswith(".pbc.json"):
                continue
            data = json.loads(archive.read(member))
            group, model_name = pbc_path_info(member, data)
            if group.startswith("FldUnit"):
                pbc_by_model[model_name] = data

        missing = sorted({model_by_id[uid] for uid in used_ids} - set(pbc_by_model))
        if missing:
            raise AssertionError(f"used terrain models lack PBC: {missing}")
        if len(used_ids) != 13:
            raise AssertionError(f"expected 13 used terrain IDs, got {len(used_ids)}")

        harness = WorldHarness()
        cases = []
        per_model = defaultdict(Counter)
        for unit_id in sorted(used_ids):
            model_name = model_by_id[unit_id]
            original = pbc_by_model[model_name]
            if (original["w"], original["h"], original["cell_size"]) != (2, 2, 5.0):
                raise AssertionError((model_name, original["w"], original["h"], original["cell_size"]))
            for rotation in range(4):
                pbc = rotate_n(original, rotation)
                records = [
                    struct.pack("<12f4B", *heights, *attributes)
                    for heights, attributes in zip(pbc["heights"], pbc["attributes"])
                ]
                for cell_index in range(4):
                    harness.reset()
                    # Repeat the asset's 2x2 local record pattern throughout
                    # the test world so all native neighbor reads are in-bounds.
                    for z in range(8):
                        for x in range(8):
                            harness.u.mem_write(harness.tile((x, z)), records[(z % 2) * 2 + (x % 2)])
                    point = (3 + cell_index % 2, 3 + cell_index // 2)
                    word_address = harness.word_address(point)
                    harness.set_coord(point)
                    harness.d(word_address, 0x80008080)
                    before = bytes(harness.u.mem_read(harness.base, 52 * 64))
                    harness.s.call(
                        0x180D20,
                        (harness.world, harness.coord, word_address, harness.tile(point)),
                        limit=300_000,
                    )
                    if bytes(harness.u.mem_read(harness.base, 52 * 64)) != before:
                        raise AssertionError((model_name, rotation, cell_index, "native writer modified source records"))
                    word = harness.rd(word_address)
                    per_model[model_name][hex(word)] += 1
                    cases.append({
                        "unit_id": unit_id,
                        "model_name": model_name,
                        "candidate_ccw_rotation": rotation,
                        "pbc_cell_index": cell_index,
                        "height_min_max": [min(pbc["heights"][cell_index]), max(pbc["heights"][cell_index])],
                        "material_row_indices": pbc["attributes"][cell_index],
                        "incoming_word": "0x80008080",
                        "native_output_word": hex(word),
                    })

    if len(cases) != 208:
        raise AssertionError(f"expected 208 native PBC cases, got {len(cases)}")
    image_sha = hashlib.sha256(harness.im.data).hexdigest()
    if image_sha != "5bf707c3dc5dac0ad9635af7d336ec580f81c3f7876d0f55400d1900e3415d74":
        raise AssertionError(f"unexpected ELF digest {image_sha}")
    result = {
        "scope": "Original native height writer 0x180d20 consumed the 12-float height prefix from 208 reconstructed 52-byte records drawn from the 13 terrain PBC models used in the 96 presets, across four candidate rotations and four PBC cells. Each PBC JSON cell was serialized as 12 float32 heights plus four material bytes. A reconstructed 8x8 world repeats the 2x2 PBC pattern to supply bounded neighbor records; this is a consumer test, not proof of original loader, transform, or full-island layout.",
        "archive": {"filename": archive_path.name, "sha256": digest},
        "source_elf_sha256": image_sha,
        "source_grid": {"decoded_preset_count": len(preset_paths), "dimensions": [112, 96], "used_unit_ids": sorted(used_ids)},
        "pbc_record_serialization": {"header_bytes": 0, "record_stride_bytes": 52, "height_float32_byte_range_exclusive": [0, 48], "material_byte_range_exclusive": [48, 52]},
        "native_consumer": {
            "height_writer": "0x180d20",
            "runtime_neighbor_lookup": "0x174070",
            "cases": len(cases),
            "world_grid": [8, 8],
            "neighbor_context": "periodic repetition of each individual PBC asset's 2x2 record pattern",
            "consumed_record_bytes": [0, 48],
            "material_attribute_bytes_separately_verified_by_this_writer": False,
            "source_records_unchanged": True,
            "dependencies_stubbed": [],
        },
        "per_model_native_output_words": {
            name: {word: counts[word] for word in sorted(counts)}
            for name, counts in sorted(per_model.items())
        },
        "cases": cases,
        "limits": [
            "PBC payload values were reserialized from JSON; original PBC container bytes and resource loading were not executed.",
            "The repeating neighbor context is synthetic and cannot establish island-scale seams or the elevation-byte transform.",
            "This writer's output is a terrain/navigation flag word, not a rendered mesh, collision response, water-flow, or actor-movement proof.",
            "The four material bytes are serialized into each record but this specific height-writer test does not claim their reader behavior.",
        ],
    }
    output = args.output if args.output.is_absolute() else ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({
        "output": str(output),
        "archive_sha256": digest,
        "native_cases": len(cases),
        "used_models": len(per_model),
        "native_words": {name: result["per_model_native_output_words"][name] for name in ("Base", "River3B", "Cliff3B", "Fall300")},
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
