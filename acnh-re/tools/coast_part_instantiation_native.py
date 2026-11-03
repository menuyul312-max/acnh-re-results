#!/usr/bin/env python3
"""Map the native coast-part record consumer and instance placement path."""
import hashlib
import json
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from native_image import Image  # noqa: E402


ELF_SHA256 = "5bf707c3dc5dac0ad9635af7d336ec580f81c3f7876d0f55400d1900e3415d74"
REGIONS = {
    "template_setup": (0x528BF0, 476),
    "template_update_dispatch": (0x529DE0, 104),
    "coast_instance_update": (0x528E60, 528),
    "template_grid_enable_flag": (0x4DE9A0, 8),
    "coast_grid_assembly_wrapper": (0x4DE9B0, 136),
    "coast_grid_to_part_records": (0x4E0C90, 204),
    "part_record_getter": (0x4E0D60, 32),
    "part_grid_bounds_check": (0x4E0D80, 40),
    "coast_part_instance_loop": (0x4DD4D0, 428),
    "part_unique_id_lookup": (0x551BF0, 72),
    "outside_sea_kind_check": (0x551D20, 76),
}


def main():
    image = Image()
    elf_sha256 = hashlib.sha256(image.data).hexdigest()
    assert elf_sha256 == ELF_SHA256, elf_sha256
    assembly = json.loads(
        (ROOT / "output/ui_island/coast_part_assembly_native.json").read_text()
    )
    terrain_loader = json.loads(
        (ROOT / "output/ui_island/island_terrain_loader_native.json").read_text()
    )
    part_counts = {
        "coast_parts": assembly["grid"]["coast_slot_count"],
        "outside_sea_parts": assembly["grid"]["outside_sea_unique_perimeter_cells"],
        "expected_nonzero_cells": assembly["outside_sea_assembly"]["final_nonzero_cell_count"],
    }
    assert part_counts == {
        "coast_parts": 22,
        "outside_sea_parts": 30,
        "expected_nonzero_cells": 52,
    }, part_counts
    coast_x = [slot["grid_xy"][0] for slot in assembly["grid"]["coast_slots"]]
    coast_z = [slot["grid_xy"][1] for slot in assembly["grid"]["coast_slots"]]
    coast_land_segments = [max(coast_x) - min(coast_x) + 1, max(coast_z) - min(coast_z) + 1]
    terrain_dimensions = terrain_loader["preset_collection"]["dimensions_cells"]
    assert coast_land_segments == [7, 6]
    assert terrain_dimensions == [112, 96]
    cells_per_coast_segment = [
        terrain_dimensions[0] // coast_land_segments[0],
        terrain_dimensions[1] // coast_land_segments[1],
    ]
    assert cells_per_coast_segment == [16, 16]

    scale_x_ptr = image.ptr(0x32E2950)
    scale_z_ptr = image.ptr(0x32E2958)
    base_position_ptr = image.ptr(0x32D06B0)
    scale_x = struct.unpack("<f", image.read(scale_x_ptr, 4))[0]
    scale_z = struct.unpack("<f", image.read(scale_z_ptr, 4))[0]
    base_position = struct.unpack("<3f", image.read(base_position_ptr, 12))
    assert scale_x == 160.0 and scale_z == 160.0, (scale_x, scale_z)
    assert base_position == (0.0, 0.0, 0.0), base_position
    data_evidence = {
        "scale_x": {
            "global_elf_va": "0x32e2950",
            "relocated_pointer_target": hex(scale_x_ptr),
            "value_f32": scale_x,
            "bytes": image.read(scale_x_ptr, 4).hex(),
        },
        "scale_z": {
            "global_elf_va": "0x32e2958",
            "relocated_pointer_target": hex(scale_z_ptr),
            "value_f32": scale_z,
            "bytes": image.read(scale_z_ptr, 4).hex(),
        },
        "base_position": {
            "global_elf_va": "0x32d06b0",
            "relocated_pointer_target": hex(base_position_ptr),
            "xyz_f32": list(base_position),
            "bytes": image.read(base_position_ptr, 12).hex(),
        },
    }

    evidence = {}
    asm = []
    for name, (va, size) in REGIONS.items():
        code = image.read(va, size)
        digest = hashlib.sha256(code).hexdigest()
        evidence[name] = {"elf_va": hex(va), "size": size, "sha256": digest}
        asm.extend([
            f"; {name} ELF {va:#x} size={size} sha256={digest}",
            *[
                f"{ins.address:08x} {ins.bytes.hex():8s} {ins.mnemonic:8s} {ins.op_str}".rstrip()
                for ins in image.disasm(va, size)
            ],
            "",
        ])

    result = {
        "scope": (
            "Static instruction/dataflow map from the selected FieldOutsideTemplate grid "
            "to the guarded coast-part instance loop. Local cell spacing is resolved; "
            "parent/world transform composition and runtime resource success are unresolved."
        ),
        "source_elf_sha256": elf_sha256,
        "resolved_rodata_constants": data_evidence,
        "terrain_grid_relation": {
            "landmaking_source_dimensions_cells": terrain_dimensions,
            "coastline_segment_dimensions": coast_land_segments,
            "source_cells_per_coast_segment": cells_per_coast_segment,
            "coast_segment_spacing_local_units": [scale_x, scale_z],
            "implied_landmaking_cell_spacing_if_same_axes_and_transform": [
                scale_x / cells_per_coast_segment[0],
                scale_z / cells_per_coast_segment[1],
            ],
            "implied_cell_spacing": [10.0, 10.0],
            "status": "exact dimension ratio across source grids; 10-unit terrain-cell spacing is a cross-grid inference, not a proven native transform or origin alignment",
        },
        "call_chain": [
            {
                "caller": "0x528bf0",
                "callee": "0x4de9a0",
                "call_site": "0x528cbc",
                "operation": "copy the 16-bit setup value at object +0xe into a temporary grid header field",
            },
            {
                "caller": "0x528bf0",
                "callee": "0x4de9b0",
                "call_site": "0x528ccc",
                "operation": "build the 9x8 UID grid; the wrapper runs the sea fill, interior clear, and copy only when the temporary header low bit is set",
            },
            {
                "caller": "0x528bf0",
                "callee": "0x4e0c90",
                "call_site": "0x528cdc",
                "operation": "write dimensions and 72 UID/x/z records into the selected template resource object",
            },
            {
                "caller": "0x529de0",
                "callee": "0x528e60",
                "call_site": "0x529e44",
                "operation": "guarded update dispatch for the selected template object",
            },
            {
                "caller": "0x528e60",
                "callee": "0x4dd4d0",
                "call_site": "0x528ed4",
                "operation": "when the object state permits, iterate the template resource's part grid using descriptor type 0x6622bd46",
            },
        ],
        "resource_grid_layout": {
            "header_dimensions_offset": 8,
            "header_dimensions_u64": "0x0000000800000009",
            "dimensions_xz": [9, 8],
            "records_offset": 16,
            "record_count": 72,
            "record_stride": 24,
            "record_bytes": 1728,
            "record_fields": [
                {"offset": 8, "size": 2, "field": "FieldOutsideParts UniqueID"},
                {"offset": 12, "size": 4, "field": "grid_x"},
                {"offset": 16, "size": 4, "field": "grid_z"},
            ],
            "trailing_zero_u32_offset": 1744,
            "bounds_helper": "0x4e0d80 accepts x<=width and z<=height; caller loops x=0..8 and z=0..7",
            "record_getter": "0x4e0d60 returns records_offset + (z*9+x)*24; out-of-range linear indices fall back to first record",
        },
        "part_instantiation": {
            "function": "0x4dd4d0",
            "iteration": "8 rows x 9 columns; skip cells whose UniqueID is zero",
            "source_count": part_counts,
            "lookup": {
                "function": "0x551bf0",
                "operation": "resolve a 16-bit UniqueID against the registered part table's base ID, count, and row-pointer array",
            },
            "position_descriptor": {
                "x": "160 * grid_x + 80",
                "y": 0.0,
                "z": "160 * grid_z + 80",
                "cell_spacing": {"x": 160.0, "z": 160.0},
                "sample_ranges_for_full_grid": {"x": [80.0, 1360.0], "z": [80.0, 1200.0]},
                "status": "native factory descriptor receives exact center-of-cell coordinates; parent/world transform composition remains unresolved",
            },
            "outside_sea_condition": {
                "function": "0x551d20",
                "operation": "test the resolved row's PartsKind cache index against 0x18 (OutsideSea)",
                "effect": "the result selects descriptor option 0 or 2 before the object factory call; the option's engine meaning is unresolved",
            },
            "factory": {
                "call_site": "0x4dd61c",
                "target": "0x1490f0",
                "operation": "dispatch one object-construction call for each valid nonzero cell",
                "success": "static dispatch is proven; model load, collision creation, and runtime object success are not",
            },
        },
        "instruction_evidence": evidence,
        "limits": [
            "The position constants are resolved to 160.0 units per coast cell and a zero base XYZ vector. The object's parent/world transform composition remains unresolved.",
            "No coast-part rotation, terrain-height snapping, seam construction, or collision generation is proven by this path.",
            "The 52 nonzero records imply 52 guarded factory dispatches when this update branch runs, not 52 confirmed loaded/rendered objects.",
            "The setup flag copied from object +0xe controls whether the wrapper copies a populated grid; the source field's higher-level meaning is unresolved.",
        ],
    }

    out = ROOT / "output/ui_island/coast_part_instantiation_native.json"
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    (ROOT / "output/ui_island/coast_part_instantiation_native.asm").write_text("\n".join(asm))
    print(json.dumps({
        "output": str(out.relative_to(ROOT)),
        "regions": len(REGIONS),
        "expected_nonzero_cells": 52,
        "record_stride": 24,
        "elf_sha256": elf_sha256,
    }, indent=2))


if __name__ == "__main__":
    main()
