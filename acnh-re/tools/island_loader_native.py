#!/usr/bin/env python3
"""Record the statically proven LandMaking preset-to-cell transfer contract."""
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = Path(os.environ.get("ACNH_RESEARCH_ROOT", ROOT))
sys.path.insert(0, str(ROOT / "tools"))
from native_image import Image  # noqa: E402


def main():
    image = Image()
    files = sorted((SOURCE_ROOT / "output/world").glob("FieldPreset*_LandMaking.json"))
    assert len(files) == 96, len(files)
    height_counts = Counter()
    preset_rows = []
    for path in files:
        data = json.loads(path.read_text())
        assert data["grid"] == [112, 96], (path.name, data["grid"])
        assert data["order"] == "row_major"
        assert data["cell_fields"] == [
            "unit0", "variation0", "rotation0", "unit1", "variation1",
            "rotation1", "height",
        ]
        assert len(data["cells"]) == 112 * 96
        assert data["raw"]["size"] == 112 * 96 * 14
        for cell in data["cells"]:
            assert len(cell) == 7
            height_counts[cell[6]] += 1
        preset_rows.append({
            "source_id": data["source_id"],
            "file": str(path.relative_to(SOURCE_ROOT / "output")),
            "raw_sha256": data["raw"]["sha256"],
            "cells": len(data["cells"]),
        })

    regions = {
        "preset_cell_loader": (0x558F40, 0x748),
        "preset_grid_wrapper_buffer_init": (0x559690, 0x1A8),
        "preset_grid_wrapper_payload_accessor": (0x55AC40, 8),
        "preset_object_setup": (0x528BF0, 0x130),
        "outside_template_generation_prefix": (0x529910, 0x1B0),
        "variation_max_reader": (0x547520, 0x154),
    }
    evidence = {}
    for name, (va, size) in regions.items():
        raw = image.read(va, size)
        evidence[name] = {
            "elf_va": hex(va),
            "bytes": size,
            "sha256": hashlib.sha256(raw).hexdigest(),
        }

    wrapper_vtable = image.ptr(0x32E4838) + 0x10
    wrapper_payload_accessor = image.ptr(wrapper_vtable + 0xF0)
    assert wrapper_payload_accessor == 0x55AC40

    result = {
        "scope": "Static main.elf dataflow plus validation of every decoded LandMaking preset. The full loader and its runtime dependencies were not emulated.",
        "source_elf_sha256": hashlib.sha256(image.data).hexdigest(),
        "preset_collection": {
            "count": len(preset_rows),
            "dimensions_cells": [112, 96],
            "row_major_cell_count_each": 112 * 96,
            "source_record_size_bytes": 14,
            "source_total_records": len(preset_rows) * 112 * 96,
            "decoded_height_histogram": {str(k): height_counts[k] for k in sorted(height_counts)},
            "presets": preset_rows,
        },
        "source_record_layout": [
            {"offset": 0, "size": 2, "field": "layer0.unit_id"},
            {"offset": 2, "size": 2, "field": "layer0.variation_index"},
            {"offset": 4, "size": 1, "field": "layer0.rotation"},
            {"offset": 5, "size": 1, "field": "padding"},
            {"offset": 6, "size": 2, "field": "layer1.unit_id"},
            {"offset": 8, "size": 2, "field": "layer1.variation_index"},
            {"offset": 10, "size": 1, "field": "layer1.rotation"},
            {"offset": 11, "size": 1, "field": "padding"},
            {"offset": 12, "size": 1, "field": "height"},
            {"offset": 13, "size": 1, "field": "padding"},
        ],
        "native_transfer": {
            "call_chain": [
                {"caller": "0x529910", "callee": "0x528bf0", "evidence": "four repeated generation slots call the preset setup function"},
                {"caller": "0x528bf0", "callee": "0x558f40", "condition": "preset resource and destination grid pointers are non-null"},
            ],
            "grid_iteration": {
                "width": 112,
                "height": 96,
                "source_cell_index": "x + 112*z",
                "source_cell_byte_offset": "14 * (x + 112*z)",
                "layer_loop": "0, 1",
                "source_layer_byte_offsets": [0, 6],
                "source_height_byte_offset": 12,
                "coordinates": "passed to destination grid accessors; out-of-range coordinates are skipped",
            },
            "wrapper_backing_store": {
                "constructor_elf_va": "0x559690",
                "nested_vtable_global_elf_va": "0x32e4838",
                "nested_vtable_address_point": hex(wrapper_vtable),
                "payload_accessor_vtable_offset": "0xf0",
                "payload_accessor_elf_va": hex(wrapper_payload_accessor),
                "payload_accessor_rule": "0x55ac40 returns this+0x28; constructor copies at returned_pointer+8, i.e. constructor_object+0xf0.",
                "zeroed_bytes": 0x24C00,
                "copy_bytes": 0x24C00,
                "size_equation": "0x24c00 = 112 * 96 * 14",
                "interpretation": "The wrapper's inline backing buffer begins at constructor_object+0xf0 and has the same total size as the decoded 14-byte preset grid.",
                "does_not_prove": "This size match does not establish that the wrapper buffer is the destination accessor's cell storage or the separate 52-byte ground/collision grid.",
            },
            "destination_cell_writes": [
                {"offset": 0, "size": 2, "field": "layer0.unit_id"},
                {"offset": 2, "size": 2, "field": "layer0.variation_index"},
                {"offset": 4, "size": 1, "field": "layer0.rotation"},
                {"offset": 6, "size": 2, "field": "layer1.unit_id"},
                {"offset": 8, "size": 2, "field": "layer1.variation_index"},
                {"offset": 10, "size": 1, "field": "layer1.rotation"},
                {"offset": 12, "size": 1, "field": "height"},
            ],
            "write_offsets_note": "Offsets are relative to the cell pointer returned by the destination grid accessor. The accessor's internal allocation/chunk stride is not established here.",
            "unit_id_rule": "Source ID is copied unless it equals the native empty-unit sentinel; that value is replaced by the native default-unit ID. Sentinel/default runtime values were not resolved.",
            "variation_rule": "The loader looks up the destination unit's FieldUnitParam Variation u16 limit (CRC32 0xc733aa77); a source variation index greater than the limit is reset to 0, otherwise it is copied.",
            "height_rule": "The source height byte is copied to cell offset 12. Downstream height accessor 0xf52860 clamps values above 5 to 4; all decoded presets in this corpus contain heights 0–3.",
        },
        "separation_from_collision_grid": "This 14-byte preset cell transfer does not establish conversion into the separate 52-byte runtime ground/collision records documented in mechanics/terrain_native.json.",
        "limits": [
            "The loader's virtual accessors and resource callback were not executed with original game objects.",
            "The destination grid's allocation stride/chunk mapping and lifetime are unresolved.",
            "No derivation from these cells to collision mesh, cliff geometry, water mesh, or shore seams is proven.",
            "This is static field-transfer evidence, not a complete native world-generation run.",
        ],
        "instruction_evidence": evidence,
    }
    out = ROOT / "output/ui_island/island_terrain_loader_native.json"
    out.write_text(json.dumps(result, indent=2) + "\n")
    asm = image.disasm(0x558F40, 0x748)
    (ROOT / "output/ui_island/island_terrain_loader.asm").write_text(
        "\n".join(
            f"{i.address:08x} {i.bytes.hex():8s} {i.mnemonic:8s} {i.op_str}".rstrip()
            for i in asm
        ) + "\n"
    )
    wrapper_asm = image.disasm(0x559690, 0x1A8)
    (ROOT / "output/ui_island/island_terrain_wrapper_buffer.asm").write_text(
        "\n".join(
            f"{i.address:08x} {i.bytes.hex():8s} {i.mnemonic:8s} {i.op_str}".rstrip()
            for i in wrapper_asm
        ) + "\n"
    )
    accessor_asm = image.disasm(0x55AC40, 8)
    (ROOT / "output/ui_island/island_terrain_wrapper_accessor.asm").write_text(
        "\n".join(
            f"{i.address:08x} {i.bytes.hex():8s} {i.mnemonic:8s} {i.op_str}".rstrip()
            for i in accessor_asm
        ) + "\n"
    )
    print(json.dumps({
        "output": str(out.relative_to(ROOT)),
        "presets": len(preset_rows),
        "source_cells": len(preset_rows) * 112 * 96,
        "height_histogram": result["preset_collection"]["decoded_height_histogram"],
        "elf_sha256": result["source_elf_sha256"],
    }, indent=2))


if __name__ == "__main__":
    main()
