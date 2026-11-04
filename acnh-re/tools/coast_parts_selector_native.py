#!/usr/bin/env python3
"""Exercise native coast-part candidate gathering before its global RNG call.

Uses source-row UIDs and PartsKind ordinals in reconstructed row/typed-cache
objects. The original 0x4dfeb0 runs unmodified and is stopped at the first
instruction of its nonempty-selection/RNG block so candidate collection can be
checked independently of global RNG initialization.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import struct
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
MASK32 = 0xFFFFFFFF


def state_from_tick(tick: int) -> list[int]:
    state = []
    value = tick & MASK32
    for increment in range(1, 5):
        value = ((value ^ (value >> 30)) * 0x6C078965 + increment) & MASK32
        state.append(value)
    return state


def draw_u32(state: list[int]) -> int:
    a, b, c, d = state
    n = (a ^ (a << 11)) & MASK32
    return (n ^ (n >> 8) ^ d ^ (d >> 19)) & MASK32


def main():
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--research-root", type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / "output/ui_island/coast_parts_selector_native.json")
    args = parser.parse_args()

    manifest = json.loads((ROOT / "output/manifest.json").read_text())
    source_root = (args.research_root or Path(manifest["source_root"])).resolve()
    sys.path.insert(0, str(source_root / "tools"))
    from native_emulator import Sandbox  # noqa: E402
    from unicorn import UC_HOOK_CODE  # noqa: E402
    from unicorn import arm64_const as regs  # noqa: E402
    from native_image import Image  # noqa: E402

    parts = json.loads((source_root / "output/tables_resolved/FieldOutsideParts.json").read_text())
    assembly = json.loads((ROOT / "output/ui_island/coast_part_assembly_native.json").read_text())
    columns = {column["name"]: i for i, column in enumerate(parts["columns"]) if column.get("name")}
    kind_column = parts["columns"][columns["PartsKind"]]
    enum_hashes = list(kind_column["enum_values"])
    enum_index = {key: index for index, key in enumerate(enum_hashes)}
    reef_column = parts["columns"][columns["ReefType"]]
    reef_hashes = list(reef_column["enum_values"])
    reef_index = {key: index for index, key in enumerate(reef_hashes)}
    outside_sea_hash = next(key for key, labels in kind_column["enum_values"].items() if "OutsideSea" in labels)
    used_kinds = {}
    for template in assembly["grid"]["templates"]:
        for slot in template["slots"]:
            item = slot["parts_kind"]
            used_kinds[item["hash"]] = item["labels"][0]
    if len(used_kinds) != 24:
        raise AssertionError(f"expected 24 used coast slot kinds, got {len(used_kinds)}")

    rows = parts["rows"]
    count = len(rows)
    if count != 136 or count > 0xFFFF:
        raise AssertionError(f"unexpected source row count {count}")
    candidate_pools = {}
    for kind_hash, label in used_kinds.items():
        pool = [row[columns["UniqueID"]] for row in rows if row[columns["PartsKind"]]["hash"] == kind_hash]
        if not pool or len(pool) > 32:
            raise AssertionError((label, len(pool), "pool must fit the native 32-entry stack buffer"))
        candidate_pools[kind_hash] = pool
    reef_pools = {}
    for reef_hash, labels in reef_column["enum_values"].items():
        if not any(row[columns["PartsKind"]]["hash"] == outside_sea_hash and row[columns["ReefType"]]["hash"] == reef_hash for row in rows):
            continue
        pool = [
            row[columns["UniqueID"]]
            for row in rows
            if row[columns["PartsKind"]]["hash"] == outside_sea_hash
            and row[columns["ReefType"]]["hash"] == reef_hash
        ]
        if not pool or len(pool) > 32:
            raise AssertionError((labels[0], len(pool), "reef-filtered pool must fit native stack buffer"))
        reef_pools[reef_hash] = pool

    harness = Sandbox()
    image = Image()
    elf_sha = hashlib.sha256(image.data).hexdigest()
    if elf_sha != "5bf707c3dc5dac0ad9635af7d336ec580f81c3f7876d0f55400d1900e3415d74":
        raise AssertionError(f"unexpected ELF digest {elf_sha}")
    uc = harness.uc
    heap = harness.HEAP
    owner = heap + 0x10000
    row_ptrs = heap + 0x20000
    row_base = heap + 0x30000
    kind_cache = heap + 0x40000
    cache_header = heap + 0x41000
    reef_cache = heap + 0x40800
    reef_header = heap + 0x41800
    cache_flag = heap + 0x42000
    field_cache = heap + 0x43000
    requested_kind = heap + 0x44000

    # This is a small reconstructed resource-row layout accepted by native
    # 0x1665ea0: count, stride, field-count/flags, then row records.
    field_count = 1
    row_stride = 8
    rows_offset = 0x1C + field_count * 8
    uc.mem_write(row_base, struct.pack("<IIHBB", count, row_stride, field_count, 1, 0) + bytes(rows_offset - 12))
    for row_index, row in enumerate(rows):
        row_ptr = row_base + rows_offset + row_index * row_stride
        unique_id = row[columns["UniqueID"]]
        kind_hash = row[columns["PartsKind"]]["hash"]
        enum_ordinal = enum_index[kind_hash]
        reef_ordinal = reef_index[row[columns["ReefType"]]["hash"]]
        # The first u32 is the original helper's relative row-to-header offset;
        # the warmed UID cache points to the following u16 field at +4.
        uc.mem_write(row_ptr, struct.pack("<IHH", rows_offset + row_index * row_stride, unique_id, 0))
        uc.mem_write(row_ptrs + row_index * 8, struct.pack("<Q", row_ptr))
        uc.mem_write(kind_cache + row_index * 2, struct.pack("<H", enum_ordinal))
        uc.mem_write(reef_cache + row_index * 2, struct.pack("<H", reef_ordinal))

    uc.mem_write(owner + 0xB30, struct.pack("<I", count))
    uc.mem_write(owner + 0xB38, struct.pack("<Q", row_ptrs))
    uc.mem_write(owner + 0xB50, struct.pack("<H", 0))
    uc.mem_write(owner + 0xB52, struct.pack("<H", count - 1))
    # The indirect table-owner global matches the native double load.
    uc.mem_write(image.ptr(0x32D1BA8), struct.pack("<Q", owner))
    uc.mem_write(0x32E2980, struct.pack("<Q", cache_header))
    uc.mem_write(cache_header, struct.pack("<I", count) + bytes(4) + struct.pack("<Q", kind_cache))
    uc.mem_write(0x32E2998, struct.pack("<Q", reef_header))
    uc.mem_write(reef_header, struct.pack("<I", count) + bytes(4) + struct.pack("<Q", reef_cache))
    uc.mem_write(0x32E2988, struct.pack("<Q", cache_flag))
    uc.mem_write(0x32E2990, struct.pack("<Q", field_cache))
    uc.mem_write(0x32D6FA0, struct.pack("<Q", cache_flag))
    uc.mem_write(cache_flag, b"\x01")
    uc.mem_write(0x32D6FA8, struct.pack("<Q", field_cache))
    uc.mem_write(field_cache + 8, struct.pack("<i", 4))

    captures = []
    current = {}
    control = {"capture_boundary": True, "tick": 0, "tick_calls": 0}

    def stop_before_rng(machine, address, _size, _user_data):
        if address == 0x220E420:
            control["tick_calls"] += 1
            machine.reg_write(regs.UC_ARM64_REG_X0, control["tick"])
            machine.reg_write(regs.UC_ARM64_REG_PC, machine.reg_read(regs.UC_ARM64_REG_X30))
        elif control["capture_boundary"] and address == 0x4E0184:
            sp = machine.reg_read(regs.UC_ARM64_REG_SP)
            found = machine.reg_read(regs.UC_ARM64_REG_X24)
            ids = list(struct.unpack("<" + "H" * found, bytes(machine.mem_read(sp + 0x20, found * 2))))
            current.update({"count": found, "ids": ids, "stop": "before_rng"})
            machine.emu_stop()
        elif control["capture_boundary"] and address == 0x4E04D0:
            sp = machine.reg_read(regs.UC_ARM64_REG_SP)
            found = machine.reg_read(regs.UC_ARM64_REG_X24)
            ids = list(struct.unpack("<" + "H" * found, bytes(machine.mem_read(sp + 0x10, found * 2))))
            current.update({"count": found, "ids": ids, "stop": "before_rng"})
            machine.emu_stop()
        elif control["capture_boundary"] and address == 0x4E01B0:
            current.update({"count": 0, "ids": [], "stop": "empty_return"})
            machine.emu_stop()
        elif control["capture_boundary"] and address == 0x4E0500:
            current.update({"count": 0, "ids": [], "stop": "empty_return"})
            machine.emu_stop()

    uc.hook_add(UC_HOOK_CODE, stop_before_rng)
    for kind_hash, label in sorted(used_kinds.items(), key=lambda item: enum_index[item[0]]):
        requested = enum_index[kind_hash]
        uc.mem_write(requested_kind, struct.pack("<I", requested))
        current.clear()
        for i in range(8):
            uc.reg_write(getattr(regs, f"UC_ARM64_REG_X{i}"), 0)
        uc.reg_write(regs.UC_ARM64_REG_X1, requested_kind)
        uc.reg_write(regs.UC_ARM64_REG_SP, harness.STACK + 0x1FF000)
        uc.reg_write(regs.UC_ARM64_REG_X30, harness.STOP)
        uc.emu_start(0x4DFEB0, harness.STOP, timeout=5_000_000, count=1_000_000)
        if "ids" not in current:
            raise AssertionError((label, "selector did not reach candidate boundary", hex(uc.reg_read(regs.UC_ARM64_REG_PC))))
        expected = candidate_pools[kind_hash]
        if current["ids"] != expected:
            raise AssertionError((label, current["ids"], expected))
        captures.append({
            "parts_kind": label,
            "enum_ordinal": requested,
            "candidate_count": current["count"],
            "candidate_unique_ids_in_native_order": current["ids"],
            "native_stop": current["stop"],
        })

    sea_captures = []
    for reef_hash, expected in sorted(reef_pools.items(), key=lambda item: reef_index[item[0]]):
        requested = reef_index[reef_hash]
        labels = reef_column["enum_values"][reef_hash]
        uc.mem_write(requested_kind, struct.pack("<I", requested))
        current.clear()
        for i in range(8):
            uc.reg_write(getattr(regs, f"UC_ARM64_REG_X{i}"), 0)
        uc.reg_write(regs.UC_ARM64_REG_X1, requested_kind)
        uc.reg_write(regs.UC_ARM64_REG_SP, harness.STACK + 0x1FF000)
        uc.reg_write(regs.UC_ARM64_REG_X30, harness.STOP)
        uc.emu_start(0x4E01D0, harness.STOP, timeout=5_000_000, count=1_000_000)
        if "ids" not in current:
            raise AssertionError((labels[0], "outside-sea selector did not reach candidate boundary", hex(uc.reg_read(regs.UC_ARM64_REG_PC))))
        if current["ids"] != expected:
            raise AssertionError((labels[0], current["ids"], expected))
        sea_captures.append({
            "reef_type": labels[0],
            "enum_ordinal": requested,
            "candidate_count": current["count"],
            "candidate_unique_ids_in_native_order": current["ids"],
            "native_stop": current["stop"],
        })

    control["capture_boundary"] = False
    tick_values = [0, 1, 2, 0xFFFFFFFF, 0x12345678, 0xDEADBEEF, 0x80000000, 0xCAFEBABE]
    full_selection_cases = []
    for selector_name, selector_va, pools in (
        ("parts_kind", 0x4DFEB0, [(used_kinds[key], key, candidate_pools[key], enum_index[key]) for key in used_kinds]),
        ("outside_sea_reef", 0x4E01D0, [(reef_column["enum_values"][key][0], key, reef_pools[key], reef_index[key]) for key in reef_pools]),
    ):
        for label, _key, pool, ordinal in pools:
            uc.mem_write(requested_kind, struct.pack("<I", ordinal))
            for tick in tick_values:
                control["tick"] = tick
                before_calls = control["tick_calls"]
                got = harness.call(selector_va, (0, requested_kind), limit=1_000_000) & 0xFFFF
                draw = draw_u32(state_from_tick(tick))
                rank = (draw * len(pool)) >> 32
                expected = pool[rank]
                if got != expected:
                    raise AssertionError((selector_name, label, tick, got, expected, rank))
                if control["tick_calls"] != before_calls + 1:
                    raise AssertionError((selector_name, label, tick, "expected exactly one system-tick read", control["tick_calls"] - before_calls))
                full_selection_cases.append({
                    "selector": selector_name,
                    "category": label,
                    "tick_fixture": hex(tick),
                    "native_rng_u32": hex(draw),
                    "candidate_count": len(pool),
                    "selected_rank": rank,
                    "native_unique_id": got,
                    "expected_unique_id": expected,
                })

    result = {
        "scope": "Original 0x4dfeb0 candidate filtering and 0x4e01d0 reef-filtered OutsideSea selection ran for all 24 PartsKind values used by the 36 coast templates and all 22 reef types with sea parts. Candidate collection was checked at the pre-RNG boundary, then both native selectors completed full selections for eight deterministic system-tick fixtures per pool.",
        "source_elf_sha256": elf_sha,
        "source_table_sha256": parts["raw"]["sha256"],
        "native_functions": {
            "parts_kind_selector": "0x4dfeb0",
            "outside_sea_reef_selector": "0x4e01d0",
            "tick_seed_expander": "0x19a9fe0",
            "next_u32": "0x19aa0e0",
        },
        "row_index_helper": "0x1665ea0",
        "native_call_contract": {
            "source_rows": count,
            "row_order_preserved": True,
            "typed_cache_values_from_source_enum_order": True,
            "unique_id_cache_offset": 4,
            "candidate_stack_capacity": 32,
            "candidate_counts_max": max(len(pool) for pool in candidate_pools.values()),
            "outside_sea_reef_pool_count": len(reef_pools),
            "outside_sea_candidate_counts_max": max(len(pool) for pool in reef_pools.values()),
            "unmodified_native_instructions": True,
            "pre_rng_dependencies_stubbed": [],
            "full_selection_platform_shim": "nn::os::GetSystemTick import at PLT 0x220e420 returns the deterministic test tick; seed expander, native RNG step, native candidate rank selection, and return path execute unmodified.",
            "rng_block_executed_for_full_selection_cases": True,
        },
        "fixtures": {
            "row_wrappers_reconstructed": True,
            "warmed_parts_kind_cache_reconstructed": True,
            "warmed_unique_id_cache_reconstructed": True,
            "source_field_values_from_decoded_table": True,
        },
        "cases": captures,
        "outside_sea_reef_cases": sea_captures,
        "full_selection_cases": full_selection_cases,
        "totals": {
            "used_parts_kinds": len(captures),
            "candidate_ids_compared": sum(case["candidate_count"] for case in captures),
            "outside_sea_reef_types": len(sea_captures),
            "outside_sea_candidate_ids_compared": sum(case["candidate_count"] for case in sea_captures),
            "full_selection_cases": len(full_selection_cases),
            "tick_fixtures_per_pool": len(tick_values),
            "system_tick_calls": control["tick_calls"],
            "mismatches": 0,
        },
        "limits": [
            "The original BCSV/resource loader and live table cache initialization did not run; row wrappers and warmed cache values were reconstructed from exact decoded source rows.",
            "The platform system-tick source is unavailable in the isolated harness; full-selection tests substitute eight explicit tick values at the import PLT. Actual gameplay timing and parent call ordering are not inferred.",
            "The complete 0x4dea40/0x4deeb0 grid assembly wrapper was not executed; selection predicates and candidate pools are tested separately.",
        ],
    }
    output_path = args.output if args.output.is_absolute() else ROOT / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"output": str(output_path), **result["totals"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
