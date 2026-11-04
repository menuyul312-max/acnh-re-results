#!/usr/bin/env python3
"""Run the original coast-grid clear and record serializer on all 36 templates.

The template slot IDs come from the decoded source table's first candidate per
PartsKind; the perimeter uses a valid OutsideSea UID as a stable fixture. This
isolates the original grid writer without claiming to execute selection, RNG,
or the complete sea-ring assembler.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import struct
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))


def main():
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--research-root", type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / "output/ui_island/coast_grid_serializer_native.json")
    args = parser.parse_args()

    manifest = json.loads((ROOT / "output/manifest.json").read_text())
    source_root = (args.research_root or Path(manifest["source_root"])).resolve()
    sys.path.insert(0, str(source_root / "tools"))
    from native_emulator import Sandbox  # noqa: E402

    assembly_path = ROOT / "output/ui_island/coast_part_assembly_native.json"
    assembly = json.loads(assembly_path.read_text())
    parts_table = json.loads((source_root / "output/tables_resolved/FieldOutsideParts.json").read_text())
    pcols = {column["name"]: i for i, column in enumerate(parts_table["columns"]) if column.get("name")}
    sea_ids = []
    for row in parts_table["rows"]:
        kind = row[pcols["PartsKind"]]
        if "OutsideSea" in kind.get("labels", []):
            sea_ids.append(row[pcols["UniqueID"]])
    if not sea_ids:
        raise AssertionError("source table has no OutsideSea parts")

    templates = assembly["grid"]["templates"]
    if len(templates) != 36:
        raise AssertionError(f"expected 36 templates, got {len(templates)}")
    if len(assembly["grid"]["coast_slots"]) != 22:
        raise AssertionError("expected 22 coast slots")

    harness = Sandbox()
    image = harness.image
    image_sha = hashlib.sha256(image.data).hexdigest()
    if image_sha != "5bf707c3dc5dac0ad9635af7d336ec580f81c3f7876d0f55400d1900e3415d74":
        raise AssertionError(f"unexpected ELF digest {image_sha}")

    grid = harness.HEAP + 0x10000
    output = harness.HEAP + 0x20000
    sea_uid = sea_ids[0]
    case_results = []
    for template in templates:
        harness.uc.mem_write(grid, b"\xA5" * 144)
        harness.call(0x4DE810, (grid,))
        if bytes(harness.uc.mem_read(grid, 144)) != bytes(144):
            raise AssertionError((template["unique_id"], "native grid clear mismatch"))

        expected = [0] * 72
        for slot in template["slots"]:
            x, z = slot["grid_xy"]
            uid = slot["candidate_unique_ids_in_source_row_order"][0]
            expected[z * 9 + x] = uid
        for z in range(8):
            for x in range(9):
                if x in (0, 8) or z in (0, 7):
                    expected[z * 9 + x] = sea_uid
        for i, uid in enumerate(expected):
            harness.uc.mem_write(grid + 2 * i, struct.pack("<H", uid))

        harness.uc.mem_write(output, b"\xCC" * 1748)
        harness.call(0x4E0C90, (output, grid))
        dims = struct.unpack("<II", bytes(harness.uc.mem_read(output + 8, 8)))
        if dims != (9, 8):
            raise AssertionError((template["unique_id"], "dimensions", dims))

        records = []
        for index, expected_uid in enumerate(expected):
            address = output + 16 + index * 24
            uid = struct.unpack("<H", bytes(harness.uc.mem_read(address + 8, 2)))[0]
            x, z = struct.unpack("<II", bytes(harness.uc.mem_read(address + 12, 8)))
            expected_x, expected_z = index % 9, index // 9
            if (uid, x, z) != (expected_uid, expected_x, expected_z):
                raise AssertionError((template["unique_id"], index, (uid, x, z), (expected_uid, expected_x, expected_z)))
            records.append({"index": index, "xy": [x, z], "unique_id": uid})
        case_results.append({
            "template_unique_id": template["unique_id"],
            "template_name": template["english_name"],
            "grid_cells": len(records),
            "coast_slots": 22,
            "outside_sea_fixture_cells": 30,
            "empty_interior_cells": sum(uid == 0 for uid in expected),
            "records": records,
        })

    result = {
        "scope": "Original native 0x4de810 grid clear and 0x4e0c90 serializer executed for all 36 decoded FieldOutsideTemplate rows. Slot fixtures use the first source-row candidate UID for each PartsKind; all 30 perimeter cells use one valid OutsideSea UID. This does not execute 0x4dea40/0x4dfeb0 selection or 0x4deeb0 reef-aware ring assembly.",
        "source_elf_sha256": image_sha,
        "source_table_sha256": {
            "FieldOutsideParts": parts_table["raw"]["sha256"],
            "coast_part_assembly_native": hashlib.sha256(assembly_path.read_bytes()).hexdigest(),
        },
        "native_functions": {
            "grid_clear": "0x4de810",
            "serializer": "0x4e0c90",
            "serializer_record_bytes": 24,
            "serialized_records_per_template": 72,
            "dependencies_stubbed": [],
        },
        "fixture_contract": {
            "template_rows": 36,
            "coast_part_policy": "first candidate UniqueID in FieldOutsideParts source-row order for each slot PartsKind",
            "sea_ring_policy": "first source-row UniqueID labeled OutsideSea repeated over the 30 perimeter cells",
            "selection_rng_executed": False,
            "reef_compatibility_executed": False,
        },
        "cases": case_results,
        "totals": {
            "templates": len(case_results),
            "grid_records": sum(case["grid_cells"] for case in case_results),
            "serialized_unique_ids": sum(len(case["records"]) for case in case_results),
            "native_mismatches": 0,
        },
        "limits": [
            "Only original grid clearing and grid-to-record serialization ran natively; slot selection and sea-ring rules are controlled fixtures.",
            "Integer grid coordinates are verified; model instance transforms, PBC resource loading, render/collision, seam behavior, and world origin remain untested.",
        ],
    }
    output_path = args.output if args.output.is_absolute() else ROOT / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"output": str(output_path), **result["totals"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
