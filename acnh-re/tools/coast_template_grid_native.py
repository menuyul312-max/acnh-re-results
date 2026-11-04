#!/usr/bin/env python3
"""Run native coast-slot and sea-ring assembly for every source template.

The original selector, slot accessors, sea-ring assembler, interior clear, and
grid serializer execute unmodified. Decoded table rows are placed in reconstructed
resource wrappers and warmed typed caches; only the missing nn::os system-tick
import receives deterministic test ticks.
"""
from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import struct
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

SLOT_NAMES = [
    "NWParts", "N0Parts", "N1Parts", "N2Parts", "N3Parts", "N4Parts", "NEParts",
    "W0Parts", "W1Parts", "W2Parts", "W3Parts", "E0Parts", "E1Parts", "E2Parts",
    "E3Parts", "SWParts", "S0Parts", "S1Parts", "S2Parts", "S3Parts", "S4Parts", "SEParts",
]
SLOT_COORDS = [
    (1, 1), (2, 1), (3, 1), (4, 1), (5, 1), (6, 1), (7, 1),
    (1, 2), (1, 3), (1, 4), (1, 5), (7, 2), (7, 3), (7, 4), (7, 5),
    (1, 6), (2, 6), (3, 6), (4, 6), (5, 6), (6, 6), (7, 6),
]
# The generated W3Parts accessor and SEParts accessor reference discontiguous
# typed-cache globals; all other slots follow the accessor order consecutively.
SLOT_CACHE_ORDER = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 21, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 10]


def make_row_table(uc, *, base: int, pointers: int, rows: list, uid_index: int, value_builder):
    """Create row objects compatible with native 0x1665ea0 row-index helper."""
    count = len(rows)
    stride = 8
    rows_offset = 0x1C + 8
    uc.mem_write(base, struct.pack("<IIHBB", count, stride, 1, 1, 0) + bytes(rows_offset - 12))
    by_uid = {}
    for row_index, row in enumerate(rows):
        row_ptr = base + rows_offset + row_index * stride
        uid = row[uid_index]
        uc.mem_write(row_ptr, struct.pack("<IHH", rows_offset + row_index * stride, uid, 0))
        uc.mem_write(pointers + row_index * 8, struct.pack("<Q", row_ptr))
        value_builder(row_index, row)
        by_uid[uid] = row_ptr
    return rows_offset, by_uid


def run_native(harness, va: int, args: tuple[int, ...], *, limit: int = 2_000_000) -> int:
    return harness.call(va, args, limit=limit)


def main():
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--research-root", type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / "output/ui_island/coast_template_grid_native.json")
    args = parser.parse_args()

    manifest = json.loads((ROOT / "output/manifest.json").read_text())
    source_root = (args.research_root or Path(manifest["source_root"])).resolve()
    sys.path.insert(0, str(source_root / "tools"))
    from native_emulator import Sandbox  # noqa: E402
    from native_image import Image  # noqa: E402
    from unicorn import UC_HOOK_CODE  # noqa: E402
    from unicorn import arm64_const as regs  # noqa: E402

    parts = json.loads((source_root / "output/tables_resolved/FieldOutsideParts.json").read_text())
    templates = json.loads((source_root / "output/tables_resolved/FieldOutsideTemplate.json").read_text())
    pcols = {column["name"]: i for i, column in enumerate(parts["columns"]) if column.get("name")}
    tcols = {column["name"]: i for i, column in enumerate(templates["columns"]) if column.get("name")}
    part_kind_hashes = list(parts["columns"][pcols["PartsKind"]]["enum_values"])
    part_kind_ord = {key: i for i, key in enumerate(part_kind_hashes)}
    reef_hashes = list(parts["columns"][pcols["ReefType"]]["enum_values"])
    reef_ord = {key: i for i, key in enumerate(reef_hashes)}
    reef_labels_by_ordinal = [parts["columns"][pcols["ReefType"]]["enum_values"][key][0] for key in reef_hashes]
    slot_enum_hashes = list(templates["columns"][tcols[SLOT_NAMES[0]]]["enum_values"])
    slot_enum_ord = {key: i for i, key in enumerate(slot_enum_hashes)}
    for name in SLOT_NAMES:
        if list(templates["columns"][tcols[name]]["enum_values"]) != slot_enum_hashes:
            raise AssertionError((name, "slot enum order differs"))
    part_rows = parts["rows"]
    template_rows = templates["rows"]
    if len(part_rows) != 136 or len(template_rows) != 36:
        raise AssertionError((len(part_rows), len(template_rows)))
    template_ids = [row[tcols["UniqueID"]] for row in template_rows]
    template_min_uid, template_max_uid = min(template_ids), max(template_ids)
    if sorted(template_ids) != list(range(template_min_uid, template_max_uid + 1)):
        raise AssertionError("template UniqueIDs are not contiguous")

    part_uid_index = pcols["UniqueID"]
    part_pools = {}
    parts_by_uid = {}
    for row in part_rows:
        uid = row[part_uid_index]
        parts_by_uid[uid] = {
            "kind_hash": row[pcols["PartsKind"]]["hash"],
            "reef_hash": row[pcols["ReefType"]]["hash"],
        }
        part_pools.setdefault(row[pcols["PartsKind"]]["hash"], []).append(uid)
    reef_pools = {}
    outside_sea_hash = next(key for key, labels in parts["columns"][pcols["PartsKind"]]["enum_values"].items() if "OutsideSea" in labels)
    for row in part_rows:
        if row[pcols["PartsKind"]]["hash"] == outside_sea_hash:
            reef_pools.setdefault(row[pcols["ReefType"]]["hash"], []).append(row[part_uid_index])

    harness = Sandbox()
    image = Image()
    elf_sha = hashlib.sha256(image.data).hexdigest()
    if elf_sha != "5bf707c3dc5dac0ad9635af7d336ec580f81c3f7876d0f55400d1900e3415d74":
        raise AssertionError(f"unexpected ELF digest {elf_sha}")
    uc = harness.uc
    heap = harness.HEAP
    owner = heap + 0x10000
    part_ptrs, part_base = heap + 0x20000, heap + 0x30000
    part_kind_data, part_kind_header = heap + 0x40000, heap + 0x41000
    part_reef_data, part_reef_header = heap + 0x42000, heap + 0x43000
    cache_flag, uid_offset_cache = heap + 0x44000, heap + 0x45000
    template_ptrs, template_base = heap + 0x50000, heap + 0x60000
    uid_input, grid, serialized = heap + 0x70000, heap + 0x80000, heap + 0x90000
    slot_values_base, slot_headers_base = heap + 0xA0000, heap + 0xB0000

    part_rows_offset, part_row_by_uid = make_row_table(
        uc,
        base=part_base,
        pointers=part_ptrs,
        rows=part_rows,
        uid_index=part_uid_index,
        value_builder=lambda i, row: (
            uc.mem_write(part_kind_data + 2 * i, struct.pack("<H", part_kind_ord[row[pcols["PartsKind"]]["hash"]])),
            uc.mem_write(part_reef_data + 2 * i, struct.pack("<H", reef_ord[row[pcols["ReefType"]]["hash"]])),
        ),
    )
    template_rows_offset, template_by_uid = make_row_table(
        uc,
        base=template_base,
        pointers=template_ptrs,
        rows=template_rows,
        uid_index=tcols["UniqueID"],
        value_builder=lambda _i, _row: None,
    )
    if part_rows_offset != template_rows_offset:
        raise AssertionError("row fixture offsets diverged")

    for index, row in enumerate(template_rows):
        uid = row[tcols["UniqueID"]]
        row_ptr = template_by_uid[uid]
        uc.mem_write(template_ptrs + (uid - template_min_uid) * 8, struct.pack("<Q", row_ptr))
        for slot_index, name in enumerate(SLOT_NAMES):
            ordinal = slot_enum_ord[row[tcols[name]]["hash"]]
            uc.mem_write(slot_values_base + slot_index * 0x100 + index * 2, struct.pack("<H", ordinal))

    part_count = len(part_rows)
    uc.mem_write(owner + 0xB30, struct.pack("<I", part_count))
    uc.mem_write(owner + 0xB38, struct.pack("<Q", part_ptrs))
    uc.mem_write(owner + 0xB50, struct.pack("<H", 0))
    uc.mem_write(owner + 0xB52, struct.pack("<H", part_count - 1))
    template_range_count = template_max_uid - template_min_uid + 1
    uc.mem_write(owner + 0xD30, struct.pack("<I", template_range_count))
    uc.mem_write(owner + 0xD38, struct.pack("<Q", template_ptrs))
    uc.mem_write(owner + 0xD50, struct.pack("<H", template_min_uid))
    uc.mem_write(image.ptr(0x32D1BA8), struct.pack("<Q", owner))

    uc.mem_write(0x32E2980, struct.pack("<Q", part_kind_header))
    uc.mem_write(part_kind_header, struct.pack("<I", part_count) + bytes(4) + struct.pack("<Q", part_kind_data))
    uc.mem_write(0x32E2998, struct.pack("<Q", part_reef_header))
    uc.mem_write(part_reef_header, struct.pack("<I", part_count) + bytes(4) + struct.pack("<Q", part_reef_data))
    uc.mem_write(0x32E2988, struct.pack("<Q", cache_flag))
    uc.mem_write(0x32E2990, struct.pack("<Q", uid_offset_cache))
    uc.mem_write(0x32D6FA0, struct.pack("<Q", cache_flag))
    uc.mem_write(cache_flag, b"\x01")
    uc.mem_write(0x32D6FA8, struct.pack("<Q", uid_offset_cache))
    uc.mem_write(uid_offset_cache + 8, struct.pack("<i", 4))

    # _INIT_1975 (Ghidra VA 0x551f70) assigns packed ReefType ordinals used by
    # 0x551d70/0x551e70. Reproduce only these literal post-constructor values;
    # the constructor's unrelated SDK/network setup is outside this harness.
    reef_side_class_literals = [
        (0x345DDAC, 0x300000000), (0x345DDB4, 0x900000006),
        (0x345DDBC, 0xF0000000C), (0x345DDC4, 0x1500000012),
        (0x345DDCC, 0x400000001), (0x345DDD4, 0xA00000007),
        (0x345DDDC, 0x100000000D), (0x345DDE4, 0x1600000013),
    ]
    for address, packed_ordinals in reef_side_class_literals:
        uc.mem_write(address, struct.pack("<Q", packed_ordinals))

    reef_predicate_handle = heap + 0xC0000
    classifier_results = {}
    for row in part_rows:
        reef_hash = row[pcols["ReefType"]]["hash"]
        ordinal = reef_ord[reef_hash]
        if ordinal in classifier_results:
            continue
        uid = row[part_uid_index]
        uc.mem_write(reef_predicate_handle + 8, struct.pack("<Q", part_row_by_uid[uid]))
        convexity = run_native(harness, 0x551D70, (reef_predicate_handle,)) & 1
        flat = run_native(harness, 0x551E70, (reef_predicate_handle,)) & 1
        expected = (int(ordinal in {0, 3, 6, 9, 12, 15, 18, 21}), int(ordinal in {1, 4, 7, 10, 13, 16, 19, 22}))
        if (convexity, flat) != expected:
            raise AssertionError(("reef side class predicate", ordinal, convexity, flat, expected))
        classifier_results[ordinal] = {"convexity": convexity, "flat": flat}

    for slot_index in range(len(SLOT_NAMES)):
        values = slot_values_base + slot_index * 0x100
        header = slot_headers_base + slot_index * 0x40
        uc.mem_write(header, struct.pack("<I", len(template_rows)) + bytes(4) + struct.pack("<Q", values))
        uc.mem_write(0x32E3A80 + SLOT_CACHE_ORDER[slot_index] * 8, struct.pack("<Q", header))

    tick_state = {"value": 0xAC110000, "calls": 0}
    active_template = {"uid": None}
    outside_sea_trace = []
    pending_sea_selector = {"call": None}

    def deterministic_system_tick(machine, address, _size, _user_data):
        if address == 0x220E420:
            machine.reg_write(regs.UC_ARM64_REG_X0, tick_state["value"])
            machine.reg_write(regs.UC_ARM64_REG_PC, machine.reg_read(regs.UC_ARM64_REG_X30))
            tick_state["value"] = (tick_state["value"] + 0x9E3779B9) & 0xFFFFFFFF
            tick_state["calls"] += 1
        elif address == 0x4E01D0:
            wanted_ptr = machine.reg_read(regs.UC_ARM64_REG_X1)
            caller = (machine.reg_read(regs.UC_ARM64_REG_X30) - 4) & 0xFFFFFFFF
            pending_sea_selector["call"] = {
                "template_unique_id": active_template["uid"],
                "caller_va": hex(caller),
                "reef_type_ordinal": struct.unpack("<I", bytes(machine.mem_read(wanted_ptr, 4)))[0],
            }
        elif address == 0x4E0500 and pending_sea_selector["call"] is not None:
            outside_sea_trace.append({**pending_sea_selector["call"], "selected_unique_id": 0})
            pending_sea_selector["call"] = None
        elif address == 0x4E0504 and pending_sea_selector["call"] is not None:
            selected = machine.reg_read(regs.UC_ARM64_REG_X0) & 0xFFFF
            outside_sea_trace.append({**pending_sea_selector["call"], "selected_unique_id": selected})
            pending_sea_selector["call"] = None

    uc.hook_add(UC_HOOK_CODE, deterministic_system_tick)
    template_results = []
    total_selector_tick_calls = 0
    for template in template_rows:
        template_uid = template[tcols["UniqueID"]]
        active_template["uid"] = template_uid
        uc.mem_write(uid_input, struct.pack("<H", template_uid))
        before_ticks = tick_state["calls"]
        before_sea_calls = len(outside_sea_trace)
        run_native(harness, 0x4DE810, (grid,))
        success = run_native(harness, 0x4DEA40, (uid_input, grid), limit=10_000_000)
        if (success & 0xFFFFFFFF) != 1:
            raise AssertionError((template_uid, "native slot assembly returned failure", success))
        slot_grid = list(struct.unpack("<72H", bytes(uc.mem_read(grid, 144))))

        expected_slot_positions = set()
        for slot_name, (x, z) in zip(SLOT_NAMES, SLOT_COORDS):
            index = z * 9 + x
            expected_slot_positions.add(index)
            kind_hash = template[tcols[slot_name]]["hash"]
            uid = slot_grid[index]
            if uid not in part_pools.get(kind_hash, []):
                raise AssertionError((template_uid, slot_name, uid, part_pools.get(kind_hash)))
        if sum(uid != 0 for uid in slot_grid) != 22:
            raise AssertionError((template_uid, "slot grid nonzero count", sum(uid != 0 for uid in slot_grid)))

        run_native(harness, 0x4DEEB0, (0, grid), limit=20_000_000)
        template_sea_trace = outside_sea_trace[before_sea_calls:]
        run_native(harness, 0x4DFCB0, (0, grid), limit=2_000_000)
        full_grid = list(struct.unpack("<72H", bytes(uc.mem_read(grid, 144))))
        interior = [full_grid[z * 9 + x] for z in range(2, 6) for x in range(2, 7)]
        if any(interior):
            raise AssertionError((template_uid, "interior is not zero", interior))
        border_uids = [
            full_grid[z * 9 + x]
            for z in range(8)
            for x in range(9)
            if x in (0, 8) or z in (0, 7)
        ]
        if len(border_uids) != 30:
            raise AssertionError((template_uid, "perimeter cell count", len(border_uids)))
        if any(uid != 0 and parts_by_uid.get(uid, {}).get("kind_hash") != outside_sea_hash for uid in border_uids):
            raise AssertionError((template_uid, "nonzero perimeter cell is not OutsideSea", border_uids))

        run_native(harness, 0x4E0C90, (serialized, grid), limit=2_000_000)
        dims = struct.unpack("<II", bytes(uc.mem_read(serialized + 8, 8)))
        if dims != (9, 8):
            raise AssertionError((template_uid, "serialized dimensions", dims))
        for index, expected_uid in enumerate(full_grid):
            address = serialized + 16 + index * 24
            uid = struct.unpack("<H", bytes(uc.mem_read(address + 8, 2)))[0]
            x, z = struct.unpack("<II", bytes(uc.mem_read(address + 12, 8)))
            if (uid, x, z) != (expected_uid, index % 9, index // 9):
                raise AssertionError((template_uid, index, (uid, x, z), expected_uid))

        elapsed_ticks = tick_state["calls"] - before_ticks
        total_selector_tick_calls += elapsed_ticks
        if elapsed_ticks <= 22:
            raise AssertionError((template_uid, "expected coast plus sea selector calls", elapsed_ticks))
        template_results.append({
            "template_unique_id": template_uid,
            "template_name": template[tcols["EnglishName"]],
            "selector_tick_calls": elapsed_ticks,
            "coast_slot_cells": 22,
            "outside_sea_perimeter_cells": 30,
            "outside_sea_filled_cells": sum(uid != 0 for uid in border_uids),
            "outside_sea_empty_cells": sum(uid == 0 for uid in border_uids),
            "outside_sea_empty_positions": [
                [index % 9, index // 9]
                for index, uid in enumerate(full_grid)
                if uid == 0 and (index % 9 in (0, 8) or index // 9 in (0, 7))
            ],
            "outside_sea_selector_calls": len(template_sea_trace),
            "outside_sea_selector_empty_results": [call for call in template_sea_trace if call["selected_unique_id"] == 0],
            "empty_interior_cells": 20,
            "serialized_record_count": 72,
            "grid_unique_ids": full_grid,
        })

    empty_position_counts = Counter(
        tuple(position)
        for template in template_results
        for position in template["outside_sea_empty_positions"]
    )
    result = {
        "scope": "Original 0x4de810 -> 0x4dea40 -> 0x4deeb0 -> 0x4dfcb0 -> 0x4e0c90 executed for all 36 FieldOutsideTemplate rows. The 24 coast selector kinds, reef-filtered OutsideSea selectors, and serializer all run as original code. Row wrappers and warmed typed caches are reconstructed from decoded source tables; the nn::os::GetSystemTick PLT import returns a deterministic incrementing tick fixture.",
        "source_elf_sha256": elf_sha,
        "source_table_sha256": {
            "FieldOutsideParts": parts["raw"]["sha256"],
            "FieldOutsideTemplate": templates["raw"]["sha256"],
        },
        "native_functions": ["0x4de810", "0x4dea40", "0x4dfeb0", "0x4deeb0", "0x4e01d0", "0x4dfcb0", "0x4e0c90", "0x1665ea0"],
        "input_contract": {
            "decoded_template_rows": len(template_rows),
            "decoded_part_rows": len(part_rows),
            "template_slot_cache_columns": len(SLOT_NAMES),
            "parts_kind_cache_from_source_enum_order": True,
            "reef_type_cache_from_source_enum_order": True,
            "unique_id_warmed_cache_offset": 4,
            "row_wrappers_reconstructed": True,
            "resource_loader_executed": False,
            "reef_side_predicate_constants": "Literal packed ordinals from native _INIT_1975 (Ghidra 0x551f70) restored for 0x551d70/0x551e70; unrelated constructor body not run.",
            "reef_side_predicates_checked": len(classifier_results),
            "system_tick_import_shim": "0x220e420 returns deterministic u32 values; all caller selector and RNG seed/draw instructions execute natively.",
            "other_dependencies_stubbed": [],
        },
        "validation": {
            "templates": len(template_results),
            "coast_slot_ids_checked_against_source_pools": len(template_results) * 22,
            "sea_perimeter_cells_checked": len(template_results) * 30,
            "sea_perimeter_nonzero_ids_checked_as_OutsideSea": sum(item["outside_sea_filled_cells"] for item in template_results),
            "sea_perimeter_empty_cells_observed": sum(item["outside_sea_empty_cells"] for item in template_results),
            "interior_zero_cells_checked": len(template_results) * 20,
            "serialized_records_checked": len(template_results) * 72,
            "selector_tick_calls": total_selector_tick_calls,
            "outside_sea_selector_calls": len(outside_sea_trace),
            "outside_sea_selector_empty_returns": sum(call["selected_unique_id"] == 0 for call in outside_sea_trace),
            "outside_sea_empty_position_counts": [
                {"xy": list(position), "templates_with_empty_cell": count}
                for position, count in sorted(empty_position_counts.items())
            ],
            "native_mismatches": 0,
        },
        "outside_sea_selector_empty_return_targets": [
            {
                "template_unique_id": call["template_unique_id"],
                "caller_va": call["caller_va"],
                "reef_type_ordinal": call["reef_type_ordinal"],
                "reef_type": reef_labels_by_ordinal[call["reef_type_ordinal"]],
            }
            for call in outside_sea_trace
            if call["selected_unique_id"] == 0
        ],
        "outside_sea_types_without_source_candidates": [
            {"reef_type_ordinal": ordinal, "reef_type": reef_labels_by_ordinal[ordinal]}
            for ordinal, reef_hash in enumerate(reef_hashes)
            if reef_hash not in reef_pools
        ],
        "templates": template_results,
        "limits": [
            "BCSV resource loading and live typed-cache bootstrap are represented by reconstructed row wrappers and cache arrays populated from the decoded tables.",
            "System tick values are deterministic fixtures; actual console tick timing and the parent island-generation call schedule are not reproduced.",
            "The full grid assembly is native, but model/PBC loading, render/collision success, parent/world transform, and physical seam behavior remain untested.",
        ],
    }
    output_path = args.output if args.output.is_absolute() else ROOT / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"output": str(output_path), **result["validation"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
