#!/usr/bin/env python3
"""Bounded native probes for the packed per-item ToolDamage helpers."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys

from nso_sandbox import NSO_SHA256, Sandbox

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RESEARCH = Path("/workspace/acnh-re/output")
DEFAULT_OUTPUT = ROOT / "output/gameplay/tool_mechanics_followup/tool_durability_native.json"
TOOL_KINDS = ("Axe", "Shovel", "Net", "FishingRod", "Slingshot", "Watering")


def load_joins(research_root: Path) -> list[dict]:
    item_table = json.loads((research_root / "tables_resolved/ItemParam.json").read_text())
    outfit_table = json.loads((research_root / "tables_resolved/ItemOutfitInfo.json").read_text())
    item_cols = {column["name"]: index for index, column in enumerate(item_table["columns"])}
    outfit_cols = {column["name"]: index for index, column in enumerate(outfit_table["columns"])}
    outfit_by_label = {
        row[outfit_cols["Label"]]: (row_index, row)
        for row_index, row in enumerate(outfit_table["rows"])
    }
    joined = []
    for row in item_table["rows"]:
        kind_value = row[item_cols["ItemKind"]]
        kind = (kind_value.get("labels") or [None])[0] if isinstance(kind_value, dict) else kind_value
        if kind not in TOOL_KINDS:
            continue
        reference = row[item_cols["ItemOutfitInfo"]]
        labels = reference.get("labels", []) if isinstance(reference, dict) else []
        matches = [outfit_by_label[label] for label in labels if label in outfit_by_label]
        if len(matches) != 1:
            raise ValueError(f"tool {row[item_cols['UniqueID']]} has {len(matches)} ItemOutfitInfo matches")
        outfit_row_index, outfit = matches[0]
        joined.append({
            "unique_id": row[item_cols["UniqueID"]],
            "label": row[item_cols["Label"]],
            "item_kind": kind,
            "item_outfit_info_unique_id": outfit[outfit_cols["UniqueID"]],
            "item_outfit_info_row_index": outfit_row_index,
            "item_outfit_info_label": outfit[outfit_cols["Label"]],
            "break_damage": outfit[outfit_cols["BreakDamage"]],
        })
    if len(joined) != 32:
        raise ValueError(f"expected 32 player tool rows, got {len(joined)}")
    return sorted(joined, key=lambda item: (TOOL_KINDS.index(item["item_kind"]), item["unique_id"]))


def run_case(sb: Sandbox, item: dict, cache_meta: int, cache_data: int,
             obj: int, item_row: int) -> dict:
    uid = int(item["unique_id"])
    outfit_index = int(item["item_outfit_info_row_index"])
    threshold = int(item["break_damage"])
    if threshold <= 0 or threshold > 999:
        raise ValueError(f"unexpected BreakDamage {threshold} for {uid}")
    sb.uc.mem_write(cache_data, struct.pack("<H", outfit_index))
    sb.uc.mem_write(cache_meta, struct.pack("<I4xQ", 1, cache_data))
    sb.uc.mem_write(obj + 16, struct.pack("<Q", item_row))

    reserved = 0xAC00  # high six bits must survive wear updates

    def set_damage(value: int):
        sb.uc.mem_write(obj + 14, struct.pack("<H", reserved | value))

    set_damage(threshold - 1)
    before = sb.call(0xAA7700, (obj,)) & 0xffff
    remaining_before = sb.call(0xAA7CE0, (obj,)) & 0xffffffff
    increment_result = sb.call(0xAA77D0, (obj, 1)) & 1
    after = sb.call(0xAA7700, (obj,)) & 0xffff
    remaining_after = sb.call(0xAA7CE0, (obj,)) & 0xffffffff
    packed_after = struct.unpack("<H", sb.read(obj + 14, 2))[0]
    if (before, remaining_before, increment_result, after, remaining_after) != (
        threshold - 1, 1, 1, threshold, 0
    ):
        raise AssertionError({"item": uid, "before": before, "remaining_before": remaining_before,
                              "increment_result": increment_result, "after": after,
                              "remaining_after": remaining_after, "threshold": threshold})
    if packed_after != (reserved | threshold):
        raise AssertionError({"item": uid, "reserved_bits_changed": hex(packed_after)})

    set_damage(998)
    sb.call(0xAA77D0, (obj, 1))
    clamped_999 = sb.call(0xAA7700, (obj,)) & 0xffff
    sb.call(0xAA77D0, (obj, 1))
    stayed_999 = sb.call(0xAA7700, (obj,)) & 0xffff
    clamped_word = struct.unpack("<H", sb.read(obj + 14, 2))[0]
    if (clamped_999, stayed_999, clamped_word) != (999, 999, reserved | 999):
        raise AssertionError({"item": uid, "clamp": [clamped_999, stayed_999, hex(clamped_word)]})

    reset_result = sb.call(0xAA79A0, (obj,)) & 1
    reset_value = sb.call(0xAA7700, (obj,)) & 0xffff
    reset_word = struct.unpack("<H", sb.read(obj + 14, 2))[0]
    if (reset_result, reset_value, reset_word) != (1, 0, reserved):
        raise AssertionError({"item": uid, "reset": [reset_result, reset_value, hex(reset_word)]})
    return {
        **item,
        "cases": {
            "threshold_minus_one_then_plus_one": {
                "start": before,
                "remaining_before": remaining_before,
                "increment_result": increment_result,
                "after": after,
                "remaining_after": remaining_after,
                "reserved_bits_preserved": True,
            },
            "saturation": {"998_plus_1": clamped_999, "999_plus_1": stayed_999},
            "reset": {"result": reset_result, "damage": reset_value, "reserved_bits_preserved": True},
        },
    }


def run_apply_wrapper_case(sb: Sandbox, item: dict, cache_data: int) -> dict:
    """Run e895a0 around the real incrementer with bounded inventory-context stubs."""
    slot_index = 3
    start_damage = int(item["break_damage"]) - 1
    reserved = 0xAC00
    packed_item = sb.alloc(8)
    pocket_index = sb.alloc(1)
    item_row = sb.alloc(8)
    dirty_slots = sb.alloc(0x300)
    dirty_slots_global = sb.alloc(8)

    sb.uc.mem_write(packed_item, struct.pack(
        "<HBB2xH", int(item["unique_id"]), 0, 0, reserved | start_damage
    ))
    sb.uc.mem_write(pocket_index, bytes([slot_index]))
    sb.uc.mem_write(cache_data, struct.pack(
        "<H", int(item["item_outfit_info_row_index"])
    ))

    # e895a0 reads a pointer-to-pointer global at ELF VA 0x32d3e00; its first
    # dereference points at the context whose dirty-bit array begins at +0x204.
    sb.uc.mem_write(dirty_slots_global, struct.pack("<Q", dirty_slots))
    sb.uc.mem_write(0x32D3E00, struct.pack("<Q", dirty_slots_global))

    def make_native_item_view(sandbox: Sandbox):
        # a9c290 normally constructs the game's item view/reference. Give the
        # original aa77d0 the packed word at view + 8 and a bounded row pointer.
        view = sandbox.reg("x0")
        source = sandbox.reg("x1")
        sandbox.uc.mem_write(view + 8, sandbox.read(source, 8))
        sandbox.uc.mem_write(view + 16, struct.pack("<Q", item_row))
        return 1

    # Only the view construction, class/context gates and table accessor are
    # controlled. e895a0's copy-back, aa77d0 wear arithmetic, and bit set run natively.
    sb.stub(0xF58D00, lambda _sandbox: 1)
    sb.stub(0xA9C290, make_native_item_view)
    sb.stub(0xDA4020, lambda _sandbox: 1)
    result = sb.call(0xE895A0, (packed_item, pocket_index, 1)) & 0xFFFFFFFF

    packed_after = sb.read(packed_item, 8)
    wear_after = struct.unpack_from("<H", packed_after, 6)[0]
    slot_markers = [sb.u32(dirty_slots + 0x204 + index * 8) for index in range(8)]
    expected_wear = start_damage + 1
    if result != 1 or wear_after != reserved | expected_wear:
        raise AssertionError({"apply_wrapper_result": result,
                              "wear_after": hex(wear_after),
                              "expected": hex(reserved | expected_wear)})
    if slot_markers != [0, 0, 0, 0x4000, 0, 0, 0, 0]:
        raise AssertionError({"slot_dirty_markers": [hex(value) for value in slot_markers]})
    if sb.unknown_imports:
        raise AssertionError({"unexpected_imports": sb.unknown_imports})

    return {
        "function": "0xe895a0",
        "item_unique_id": item["unique_id"],
        "pocket_slot_index": slot_index,
        "start_tool_damage": start_damage,
        "amount": 1,
        "result": result,
        "end_tool_damage": expected_wear,
        "reserved_bits_preserved": (wear_after & 0xFC00) == reserved,
        "dirty_slot_marker": hex(slot_markers[slot_index]),
        "other_slot_markers_zero": all(
            marker == 0 for index, marker in enumerate(slot_markers) if index != slot_index
        ),
        "bounded_stubs": ["0xf58d00 item-use gate", "0xa9c290 item-view construction",
                          "0x1665ea0 ItemParam row index", "0xaa7a30 table cache",
                          "0xda4020 pocket-context gate"],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--research-root", type=Path, default=DEFAULT_RESEARCH)
    parser.add_argument("--nso", type=Path, default=ROOT / "inputs/additional_exefs/main")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    native = args.nso.read_bytes()
    if hashlib.sha256(native).hexdigest() != NSO_SHA256:
        raise ValueError("main NSO does not match the indexed Animal Crossing 1.0.0 image")
    items = load_joins(args.research_root)
    sb = Sandbox(args.nso)

    # These stubs supply table/cache eligibility and the table's BreakDamage scalar only.
    # The getter, increment, reset, and remaining arithmetic execute from the original NSO.
    sb.stub(0xAA7880, lambda sandbox: sandbox.reg("x0") + 0xc)
    sb.stub(0x1665EA0, lambda sandbox: 0)
    sb.stub(0xAA7A30, lambda sandbox: 1)
    thresholds_by_index = {int(item["item_outfit_info_row_index"]): int(item["break_damage"])
                           for item in items}
    sb.stub(0xAA7B90, lambda sandbox: thresholds_by_index.get(sandbox.reg("x0"), 0))

    obj = sb.alloc(0x30)
    item_row = sb.alloc(0x100)
    cache_data = sb.alloc(2)
    cache_meta = sb.alloc(16)
    # Ghidra's decompiler labels this global 0x33f0a98; ELF VA is 0x32f0a98.
    sb.uc.mem_write(0x32F0A98, struct.pack("<Q", cache_meta))

    cases = [run_case(sb, item, cache_meta, cache_data, obj, item_row)
             for item in items]
    wrapper_case = run_apply_wrapper_case(
        sb, next(item for item in items if int(item["unique_id"]) == 2100), cache_data
    )
    if sb.unknown_imports:
        raise AssertionError({"unexpected_imports": sb.unknown_imports})

    result = {
        "schema": "acnh-re/tool-durability-native/1",
        "game_version": "1.0.0",
        "evidence_level": "NATIVE_HELPER_AND_APPLY_WRAPPER_EXECUTION_WITH_BOUNDED_STUBS",
        "native_elf_sha256": hashlib.sha256(native).hexdigest(),
        "functions_executed": {
            "current_damage_getter": "0xaa7700",
            "current_damage_incrementer": "0xaa77d0",
            "current_damage_reset": "0xaa79a0",
            "remaining_damage_calculator": "0xaa7ce0",
            "wear_apply_and_slot_dirty_marker": "0xe895a0",
        },
        "contract": {
            "packed_word_current_damage_offset": 6,
            "current_damage_width_bits": 10,
            "increment_adds_to_current_damage_and_clamps_at": 999,
            "remaining_damage_formula": "supplied ItemOutfitInfo.BreakDamage - current ToolDamage",
            "table_stub_limit": "ItemParam eligibility/cache and BreakDamage table getter are supplied by stubs; this does not execute a live save or prove the transition into PlayerToolBreak.",
        },
        "stubs": ["0xaa7880 item-class eligibility", "0x1665ea0 row index", "0xaa7a30 table cache", "0xaa7b90 BreakDamage table value"],
        "tool_count": len(cases),
        "case_count": len(cases) * 3,
        "apply_wrapper_case_count": 1,
        "apply_wrapper_case": wrapper_case,
        "mismatches": 0,
        "unknown_imports": sb.unknown_imports,
        "tools": cases,
        "remaining": [
            "Threshold-to-PlayerToolBreak dispatch is not exercised; the native tool state path is only statically tied to the wear helpers.",
            "The PlayerToolBreak path's durable save flush and a live action-to-break sequence are not available in this fixture.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({key: value for key, value in result.items() if key != "tools"}, indent=2))


if __name__ == "__main__":
    main()
