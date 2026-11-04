#!/usr/bin/env python3
"""Map FieldOutsideTemplate slot selection and 9x8 coast/sea part assembly."""
from collections import Counter, defaultdict
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = Path(os.environ.get("ACNH_RESEARCH_ROOT", ROOT))
sys.path.insert(0, str(ROOT / "tools"))
from native_image import Image  # noqa: E402


SLOT_LAYOUT = [
    ("NWParts", 1, 1),
    ("N0Parts", 2, 1),
    ("N1Parts", 3, 1),
    ("N2Parts", 4, 1),
    ("N3Parts", 5, 1),
    ("N4Parts", 6, 1),
    ("NEParts", 7, 1),
    ("W0Parts", 1, 2),
    ("W1Parts", 1, 3),
    ("W2Parts", 1, 4),
    ("W3Parts", 1, 5),
    ("E0Parts", 7, 2),
    ("E1Parts", 7, 3),
    ("E2Parts", 7, 4),
    ("E3Parts", 7, 5),
    ("SWParts", 1, 6),
    ("S0Parts", 2, 6),
    ("S1Parts", 3, 6),
    ("S2Parts", 4, 6),
    ("S3Parts", 5, 6),
    ("S4Parts", 6, 6),
    ("SEParts", 7, 6),
]


def coords(xs, target_z, source_z):
    return [
        {"target": [x, target_z], "reef_source": [x, source_z]}
        for x in xs
    ]


def build_ring_rules():
    direct = []
    # Keep target/source ordering explicit: the source is the inner coast cell.
    direct += [
        {"edge": "east", "target": [8, z], "reef_source": [7, z]}
        for z in range(1, 7)
    ]
    direct += [
        {"edge": "west", "target": [0, z], "reef_source": [1, z]}
        for z in range(1, 7)
    ]
    direct += [
        {"edge": "south", "target": [x, 7], "reef_source": [x, 6]}
        for x in range(1, 8)
    ]
    direct += [
        {"edge": "north", "target": [x, 0], "reef_source": [x, 1]}
        for x in range(1, 9)
    ]

    corners = [
        {
            "name": "NE",
            "coast_source": [7, 1],
            "diagonal_target": [8, 0],
            "side_targets": {"north": [7, 0], "east": [8, 1]},
        },
        {
            "name": "NW",
            "coast_source": [1, 1],
            "diagonal_target": [0, 0],
            "side_targets": {"north": [1, 0], "west": [0, 1]},
        },
        {
            "name": "SE",
            "coast_source": [7, 6],
            "diagonal_target": [8, 7],
            "side_targets": {"south": [7, 7], "east": [8, 6]},
        },
        {
            "name": "SW",
            "coast_source": [1, 6],
            "diagonal_target": [0, 7],
            "side_targets": {"south": [1, 7], "west": [0, 6]},
        },
    ]
    for corner in corners:
        corner["diagonal_rule"] = "OutsideSea with ReefType equal to coast_source ReefType"
        corner["side_rule"] = (
            "OutsideSea with orientation-specific ReefType; map the coast source's "
            "convexity/flat/concavity class onto that side"
        )
    return direct, corners


def enum_hashes(column):
    # The resolved enum map preserves the generated schema's ordinal order.
    return list(column["enum_values"].items())


def main():
    image = Image()
    template = json.loads(
        (SOURCE_ROOT / "output/tables_resolved/FieldOutsideTemplate.json").read_text()
    )
    parts = json.loads(
        (SOURCE_ROOT / "output/tables_resolved/FieldOutsideParts.json").read_text()
    )
    assert hashlib.sha256(image.data).hexdigest() == (
        "5bf707c3dc5dac0ad9635af7d336ec580f81c3f7876d0f55400d1900e3415d74"
    )
    assert template["row_count"] == 36 and parts["row_count"] == 136
    tcols = {c["name"]: i for i, c in enumerate(template["columns"])}
    pcols = {c["name"]: i for i, c in enumerate(parts["columns"])}
    assert len(SLOT_LAYOUT) == 22
    assert all(name in tcols for name, _, _ in SLOT_LAYOUT)
    assert {"PartsKind", "ReefType", "UniqueID", "ModelName"} <= pcols.keys()

    parts_kind_enum = next(c for c in parts["columns"] if c["name"] == "PartsKind")
    reef_enum = next(c for c in parts["columns"] if c["name"] == "ReefType")
    kind_order = enum_hashes(parts_kind_enum)
    reef_order = enum_hashes(reef_enum)
    kind_index = {h: i for i, (h, _) in enumerate(kind_order)}
    reef_index = {h: i for i, (h, _) in enumerate(reef_order)}
    assert kind_order[24][1][0] == "OutsideSea", kind_order[24]

    candidate_by_kind = defaultdict(list)
    sea_by_reef = defaultdict(list)
    category_counts = Counter()
    reef_hashes = {}
    for row_index, row in enumerate(parts["rows"]):
        reef = row[pcols["ReefType"]]
        kind = row[pcols["PartsKind"]]
        uid = row[pcols["UniqueID"]]
        name = row[pcols["ModelName"]]
        assert isinstance(uid, int) and isinstance(name, str)
        reef_hashes[reef["hash"]] = reef["labels"]
        part = {
            "row_index": row_index,
            "unique_id": uid,
            "model_name": name,
            "reef_type": {"hash": reef["hash"], "labels": reef["labels"]},
        }
        candidate_by_kind[kind["hash"]].append(part)
        category_counts[kind["hash"]] += 1
        if kind_index[kind["hash"]] == 24:
            sea_by_reef[reef["hash"]].append(part)

    template_rows = []
    max_slot_pool = 0
    slot_kind_hashes = set()
    for row in template["rows"]:
        uid = row[tcols["UniqueID"]]
        slots = []
        for column, x, z in SLOT_LAYOUT:
            value = row[tcols[column]]
            if not isinstance(value, dict):
                raise AssertionError((uid, column, value))
            kind_hash = value["hash"]
            options = candidate_by_kind[kind_hash]
            assert options, (uid, column, kind_hash)
            assert len(options) <= 32, (column, len(options))
            slot_kind_hashes.add(kind_hash)
            max_slot_pool = max(max_slot_pool, len(options))
            slots.append({
                "column": column,
                "grid_xy": [x, z],
                "parts_kind": {"hash": kind_hash, "labels": value["labels"]},
                "candidate_count": len(options),
                "candidate_unique_ids_in_source_row_order": [p["unique_id"] for p in options],
                "candidates": options,
                "selection": "native 0x4dfeb0 filters PartsKind and selects floor(draw_u32*N/2^32)",
            })
        assert len(slots) == 22
        template_rows.append({
            "unique_id": uid,
            "english_name": row[tcols["EnglishName"]],
            "template_kind": row[tcols["TemplateKind"]],
            "slots": slots,
        })

    river_slots_by_kind = defaultdict(lambda: {
        "template_count": 0,
        "slot_patterns": Counter(),
        "candidate_model_names_by_slot": {},
    })
    for template_row in template_rows:
        kind_name = template_row["template_kind"]["labels"][0]
        river_slots = [
            slot for slot in template_row["slots"]
            if "River" in slot["parts_kind"]["labels"][0]
        ]
        assert len(river_slots) == 2, (template_row["english_name"], river_slots)
        group = river_slots_by_kind[kind_name]
        group["template_count"] += 1
        pattern = tuple((slot["column"], tuple(slot["grid_xy"])) for slot in river_slots)
        group["slot_patterns"][pattern] += 1
        for slot in river_slots:
            names = sorted({candidate["model_name"] for candidate in slot["candidates"]})
            previous = group["candidate_model_names_by_slot"].setdefault(slot["column"], names)
            assert previous == names
    river_coast_summary = {}
    for kind_name, group in sorted(river_slots_by_kind.items()):
        patterns = [
            {
                "slots": [
                    {"column": column, "grid_xy": list(xz)}
                    for column, xz in pattern
                ],
                "template_count": count,
            }
            for pattern, count in sorted(group["slot_patterns"].items())
        ]
        river_coast_summary[kind_name] = {
            "template_count": group["template_count"],
            "river_slot_patterns": patterns,
            "candidate_model_names_by_slot": group["candidate_model_names_by_slot"],
        }
    assert sum(g["template_count"] for g in river_slots_by_kind.values()) == 36

    direct_edges, corners = build_ring_rules()
    assert len(direct_edges) == 27
    assert len(corners) == 4
    outside_sea_rows = [p for pool in sea_by_reef.values() for p in pool]
    assert len(outside_sea_rows) == 52
    assert max(map(len, sea_by_reef.values())) <= 32
    # Every part reef type which occurs in the table has a matching sea row.
    assert set(reef_hashes) == set(sea_by_reef)
    assert len(sea_by_reef) == 22

    interior = [[x, z] for z in range(2, 6) for x in range(2, 7)]
    assert len(interior) == 20
    occupied_coast = {(x, z) for _, x, z in SLOT_LAYOUT}
    water_border = {
        (x, z)
        for z in range(8)
        for x in range(9)
        if x in (0, 8) or z in (0, 7)
    }
    assert len(occupied_coast) == 22 and len(water_border) == 30
    assert occupied_coast.isdisjoint(water_border)
    assert occupied_coast | water_border | {(x, z) for x, z in interior} == {
        (x, z) for z in range(8) for x in range(9)
    }

    regions = {
        "coast_grid_zero_init": (0x4DE810, 80),
        "setup_enable_flag_copy": (0x4DE9A0, 8),
        "template_slot_selection": (0x4DEA40, 1136),
        "outside_sea_edge_assembly": (0x4DEEB0, 3576),
        "interior_clear": (0x4DFCB0, 512),
        "coast_grid_wrapper": (0x4DE9B0, 136),
        "parts_kind_selector": (0x4DFEB0, 800),
        "outside_sea_selector": (0x4E01D0, 852),
        "coast_grid_to_cell_records": (0x4E0C90, 204),
        "coast_cell_coordinate_write": (0x4DE610, 8),
        "coast_grid_accessor": (0x4DE8C0, 48),
        "selected_template_setup": (0x528BF0, 476),
    }
    instruction_evidence = {}
    asm = []
    for name, (va, size) in regions.items():
        code = image.read(va, size)
        listing = image.disasm(va, size)
        instruction_evidence[name] = {
            "elf_va": hex(va),
            "size": size,
            "sha256": hashlib.sha256(code).hexdigest(),
        }
        asm.extend([
            f"; {name} ELF {va:#x} size={size} sha256={instruction_evidence[name]['sha256']}",
            *[
                f"{i.address:08x} {i.bytes.hex():8s} {i.mnemonic:8s} {i.op_str}".rstrip()
                for i in listing
            ],
            "",
        ])

    result = {
        "scope": (
            "Static native dataflow for the FieldOutsideTemplate -> FieldOutsideParts "
            "9x8 selection and perimeter fill, joined with all source table rows. "
            "It does not establish PBC geometry, world-space transforms, collision, or runtime load success."
        ),
        "source_elf_sha256": hashlib.sha256(image.data).hexdigest(),
        "tables": {
            "FieldOutsideTemplate": {
                "source": template["source"],
                "source_id": template["source_id"],
                "rows": template["row_count"],
                "source_sha256": template["raw"]["sha256"],
            },
            "FieldOutsideParts": {
                "source": parts["source"],
                "source_id": parts["source_id"],
                "rows": parts["row_count"],
                "source_sha256": parts["raw"]["sha256"],
                "parts_kind_enum_index_0x18": kind_order[24],
                "reef_type_cache_enum_order": [
                    {"index": i, "hash": h, "labels": labels}
                    for i, (h, labels) in enumerate(reef_order)
                ],
            },
        },
        "native_pipeline": [
            {
                "function": "0x4de810",
                "operation": "zero a 9x8 u16 grid (0x90 bytes)",
            },
            {
                "function": "0x4dea40",
                "operation": "read the 22 FieldOutsideTemplate part-kind columns and place one selected FieldOutsideParts UniqueID at each fixed coast coordinate",
            },
            {
                "function": "0x4dfeb0",
                "operation": "filter FieldOutsideParts by PartsKind; collect UniqueID values in source row order; choose floor(draw_u32*N/2^32); zero candidates return 0 without selection",
                "candidate_buffer_capacity": 32,
                "max_candidate_pool_in_the_22_coast_slot_kinds": max_slot_pool,
                "all_source_pools_fit_without_truncation": max_slot_pool <= 32,
            },
            {
                "function": "0x4deeb0",
                "operation": "fill perimeter cells with OutsideSea parts chosen by ReefType compatibility, including four corner transitions",
                "direct_edge_rules": len(direct_edges),
                "corner_groups": len(corners),
                "sea_unique_ids_by_reef_type_max_candidates": max(map(len, sea_by_reef.values())),
            },
            {
                "function": "0x4dfcb0",
                "operation": "clear the 5x4 interior coordinates after perimeter assembly",
            },
            {
                "function": "0x4de9b0",
                "operation": "orchestrate zero -> slots; when temporary header bit 0 is set, fill sea ring -> clear interior -> copy 0x90-byte grid",
                "enable_flag_source": "selected-template setup object +0xe, copied by 0x4de9a0",
            },
            {
                "function": "0x528bf0",
                "operation": "selected template setup copies an enable field, builds the coast grid, then writes it to the resource object",
                "static_call_sites": [
                    "0x528cbc -> 0x4de9a0",
                    "0x528ccc -> 0x4de9b0",
                    "0x528cdc -> 0x4e0c90",
                ],
            },
            {
                "function": "0x4e0c90",
                "operation": "convert 72 u16 grid entries into 72 0x18-byte records",
                "record_layout": [
                    {"record_offset": 0, "size": 8, "field": "unresolved/padding"},
                    {"record_offset": 8, "size": 2, "field": "selected FieldOutsideParts UniqueID"},
                    {"record_offset": 10, "size": 2, "field": "unresolved/padding"},
                    {"record_offset": 12, "size": 4, "field": "grid_x"},
                    {"record_offset": 16, "size": 4, "field": "grid_z"},
                    {"record_offset": 20, "size": 4, "field": "unresolved/padding"},
                ],
                "grid_dimensions": [9, 8],
                "record_count": 72,
                "record_array_bytes": 72 * 24,
                "destination_header": {
                    "dimensions_offset": 8,
                    "packed_u64": "0x0000000800000009",
                    "records_offset": 16,
                    "trailing_zero_u32_offset": 1744,
                },
                "spatial_units": "integer grid indices only; world scale/rotation/translation remain unresolved",
            },
        ],
        "grid": {
            "dimensions": [9, 8],
            "linear_index": "z*9+x",
            "coast_slots": [
                {"column": name, "grid_xy": [x, z]}
                for name, x, z in SLOT_LAYOUT
            ],
            "coast_slot_count": len(SLOT_LAYOUT),
            "outside_sea_unique_perimeter_cells": 30,
            "interior_zero_cells": interior,
            "interior_zero_cell_count": len(interior),
            "templates": template_rows,
        },
        "river_coast_slot_summary": {
            "templates": len(template_rows),
            "templates_with_exactly_two_river_labelled_coast_slots": 36,
            "templates_by_template_kind": river_coast_summary,
            "interpretation": "Source-table category and model-name mapping only; this does not prove the inland River grid connects geometrically to these coast pieces.",
        },
        "outside_sea_assembly": {
            "kind_index": 24,
            "kind_name": "OutsideSea",
            "direct_edge_transfer_rules": direct_edges,
            "corner_transitions": corners,
            "outside_sea_rows": len(outside_sea_rows),
            "outside_sea_candidate_count_by_reef_type": {
                reef: len(options) for reef, options in sorted(sea_by_reef.items())
            },
            "all_reef_types_actually_used_by_parts_have_an_outside_sea_candidate": True,
            "selection": "filter PartsKind=OutsideSea and ReefType=target; choose floor(draw_u32*N/2^32)",
            "corner_class_mapping": {
                "classification": "native predicates classify ReefType cache index modulo 3: 0 convexity, 1 flat, 2 concavity",
                "side_base_indices": {"north": 0, "east": 6, "south": 12, "west": 18},
                "index_expression": "side_base + class_index",
            },
            "final_nonzero_cell_count": 52,
            "validation": "22 coast slots + 30 perimeter sea cells + 20 cleared interior cells cover all 72 cells",
        },
        "instruction_evidence": instruction_evidence,
        "limits": [
            "Selection order and candidate row IDs are derived from the decoded source tables; the RNG parent state for a complete island generation is not reproduced here.",
            "The 9x8 record coordinates are discrete grid x/z only. This function does not reveal placement; the downstream instance pass resolves 160-unit local spacing, while parent/world origin, rotation, and seam geometry remain unresolved.",
            "A later user-supplied archive provides decoded PBC payloads for all 136 FieldOutsideParts names; a selected UniqueID still does not prove which model or collision resource loaded at runtime. See output/ui_island/manifests_pbc_audit.json.",
            "The output records contain a UniqueID and integer grid coordinates, but downstream model instantiation, PBC collision, water rendering, and runtime success are outside this proof.",
        ],
    }

    out = ROOT / "output/ui_island/coast_part_assembly_native.json"
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    (ROOT / "output/ui_island/coast_part_assembly_native.asm").write_text("\n".join(asm))
    print(json.dumps({
        "output": str(out.relative_to(ROOT)),
        "templates": len(template_rows),
        "coast_slots": len(SLOT_LAYOUT),
        "part_rows": parts["row_count"],
        "outside_sea_rows": len(outside_sea_rows),
        "direct_edge_rules": len(direct_edges),
        "corner_groups": len(corners),
        "grid_records": 72,
    }, indent=2))


if __name__ == "__main__":
    main()
