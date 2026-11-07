#!/usr/bin/env python3
"""Resolve tool-family event selectors and bound the SaveProc callback route."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sqlite3
import struct
import sys

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INDEX = Path("/workspace/acnh-re/output/index.sqlite")
DEFAULT_RESEARCH = Path("/workspace/acnh-re/output")
DEFAULT_OUTPUT = ROOT / "output/gameplay/tool_mechanics_followup/tool_durability_producer_dispatch_static.json"

A9D0B0 = 0xA9D0B0
AA7CE0 = 0xAA7CE0
DB1070 = 0xDB1070
FAFEC0 = 0xFAFEC0
SAVEPROC_ARRAY = 0x32FF8D8
SAVEPROC_TASKS = (0xFB1E10, 0xFB1FF0, 0xFB2200, 0xFB23E0, 0xFB25E0)
WRITE_FLUSH = {"WriteFile": 0x22103C0, "FlushFile": 0x22103A0}
PLAYER_ITEM_KINDS = {
    "Axe": "Axe", "Shovel": "Scoop", "Watering": "Watering",
    "Net": "Net", "Slingshot": "Slingshot", "FishingRod": "FishingRod",
}
BREAK_ENTRYPOINTS = {
    "Axe": "ToolBreak_Axe", "Scoop": "ToolBreak_Scoop",
    "Watering": "ToolBreak_Watering", "Net": "ToolBreak_Net",
    "Slingshot": "ToolBreak_Slingshot", "FishingRod": "ToolBreak_FishingRod",
}


def read_table(research_root: Path, name: str) -> dict:
    path = research_root / "tables_resolved" / f"{name}.json"
    return json.loads(path.read_text())


def column_index(table: dict, name: str) -> int:
    for index, column in enumerate(table["columns"]):
        if column.get("name") == name:
            return index
    raise KeyError(f"{table.get('source')}: missing column {name}")


def enum_label(value) -> str | None:
    if isinstance(value, dict):
        labels = value.get("labels", [])
        return labels[0] if labels else None
    return value if isinstance(value, str) else None


def tool_family_rows(research_root: Path) -> dict:
    item_param = read_table(research_root, "ItemParam")
    outfit_info = read_table(research_root, "ItemOutfitInfo")
    outfit_categories = read_table(research_root, "ItemOutfitCategory")
    if len(outfit_categories["rows"]) != 0x41:
        raise ValueError("ItemOutfitCategory must contain the 65 entries used by 7e30f0")

    ip_ui = column_index(item_param, "ItemUICategory")
    ip_kind = column_index(item_param, "ItemKind")
    ip_outfit = column_index(item_param, "ItemOutfitInfo")
    ip_uid = column_index(item_param, "UniqueID")
    oi_category = column_index(outfit_info, "Category")
    oi_label = column_index(outfit_info, "Label")
    oi_break = column_index(outfit_info, "BreakDamage")
    oc_label = column_index(outfit_categories, "Label")
    oc_uid = column_index(outfit_categories, "UniqueID")

    outfit_by_label = {row[oi_label]: (index, row)
                       for index, row in enumerate(outfit_info["rows"])}
    category_row_by_label = {row[oc_label]: index
                             for index, row in enumerate(outfit_categories["rows"])}
    result_rows = []
    for row_index, row in enumerate(item_param["rows"]):
        kind = enum_label(row[ip_kind])
        outfit_label = enum_label(row[ip_outfit])
        if enum_label(row[ip_ui]) != "Tool" or kind not in PLAYER_ITEM_KINDS:
            continue
        outfit = outfit_by_label.get(outfit_label)
        if outfit is None:
            raise ValueError(f"ItemParam row {row_index} has unresolved ItemOutfitInfo {outfit_label}")
        outfit_index, outfit_row = outfit
        family = enum_label(outfit_row[oi_category])
        expected_family = PLAYER_ITEM_KINDS[kind]
        if family != expected_family:
            raise ValueError(f"ItemParam row {row_index}: {kind} maps to {family}, expected {expected_family}")
        selector = category_row_by_label[family]
        result_rows.append({
            "itemparam_row": row_index,
            "item_unique_id": row[ip_uid],
            "item_kind": kind,
            "item_outfit_info_label": outfit_label,
            "item_outfit_info_row": outfit_index,
            "outfit_category_label": family,
            "a9d0b0_expected_selector_row_ordinal": selector,
            "itemoutfitcategory_unique_id_field": outfit_categories["rows"][selector][oc_uid],
            "break_damage": outfit_row[oi_break],
        })

    selector_by_family = {}
    for row in result_rows:
        selector_by_family.setdefault(row["outfit_category_label"],
                                      row["a9d0b0_expected_selector_row_ordinal"])
        if selector_by_family[row["outfit_category_label"]] != row["a9d0b0_expected_selector_row_ordinal"]:
            raise ValueError("one family mapped to multiple ItemOutfitCategory rows")
    expected = {"Axe": 8, "Scoop": 7, "Watering": 13,
                "Net": 10, "Slingshot": 19, "FishingRod": 9}
    if selector_by_family != expected or len(result_rows) != 32:
        raise ValueError({"selector_by_family": selector_by_family, "player_tool_rows": len(result_rows)})

    return {
        "evidence_level": "STATIC_BCSV_JOIN",
        "source_hashes": {name: read_table(research_root, name)["raw"]["sha256"]
                          for name in ("ItemParam", "ItemOutfitInfo", "ItemOutfitCategory")},
        "player_tool_row_count": len(result_rows),
        "selector_by_family": selector_by_family,
        "selector_semantics": (
            "The A9D0B0 result is consumed as an index into the 65-entry array returned by 7e30f0. "
            "The selectors here are zero-based ItemOutfitCategory row ordinals; they are not that "
            "table's separate UniqueID field."
        ),
        "rows": sorted(result_rows, key=lambda row: (row["a9d0b0_expected_selector_row_ordinal"],
                                                     row["item_unique_id"])),
    }


def resolve_owner(conn: sqlite3.Connection, pc: int) -> int | None:
    row = conn.execute(
        "SELECT va FROM native_functions WHERE va<=? AND span_end_va>? ORDER BY size LIMIT 1",
        (pc, pc),
    ).fetchone()
    return row[0] if row else None


def function_label(conn: sqlite3.Connection, va: int | None) -> dict | None:
    if va is None:
        return None
    row = conn.execute("SELECT name,size FROM native_functions WHERE va=?", (va,)).fetchone()
    strings = [text for (text,) in conn.execute(
        "SELECT text FROM string_refs WHERE function_va=? ORDER BY text", (va,))]
    return {"va": hex(va), "name": row[0] if row else None,
            "size": row[1] if row else None, "strings": strings}


def calls_by_owner(conn: sqlite3.Connection, owner: int) -> list[int]:
    return [target for (target,) in conn.execute(
        "SELECT target_va FROM direct_calls WHERE owner_va=? ORDER BY pc", (owner,))]


def event_dispatch_callers(conn: sqlite3.Connection) -> dict:
    rows = []
    for pc, direct_owner in conn.execute(
            "SELECT pc,owner_va FROM direct_calls WHERE target_va=? ORDER BY pc", (DB1070,)):
        owner = direct_owner if direct_owner is not None else resolve_owner(conn, pc)
        direct_targets = calls_by_owner(conn, owner) if owner is not None else []
        rows.append({
            "callsite": hex(pc),
            "owner": function_label(conn, owner),
            "directly_calls_wear_or_remaining_helper": any(
                target in {0xAA7700, 0xAA77D0, 0xAA79A0, AA7CE0, 0xE895A0, 0xE893C0, 0xDB00F0}
                for target in direct_targets),
        })
    return {
        "target": hex(DB1070),
        "indexed_direct_callsite_count": len(rows),
        "callers": rows,
        "player_tool_break_dispatch_status": {
            "e37a50_callsite": "0xe37e4c",
            "event_call_success": "DB1070 returns a low-bit success result after its gated dispatch path.",
            "caller_latch": (
                "e37a50 sets state+0xf00 bit 0x40 before dispatch and clears it only when DB1070 "
                "returns success; this is event-dispatch bookkeeping, not a durability status."
            ),
        },
        "finding": (
            "The indexed DB1070 caller set contains the PlayerToolBreak formatter and other player "
            "event/action flows. No caller has a direct edge to the remaining-damage helper or wear "
            "commit wrapper, and the successful return is used by e37a50 only to clear its event latch."
        ),
    }


def a9d0b0_callers(conn: sqlite3.Connection) -> dict:
    callers = []
    for pc, direct_owner in conn.execute(
            "SELECT pc,owner_va FROM direct_calls WHERE target_va=? ORDER BY pc", (A9D0B0,)):
        owner = direct_owner if direct_owner is not None else resolve_owner(conn, pc)
        callers.append({"callsite": hex(pc), "owner": function_label(conn, owner)})
    return {
        "target": hex(A9D0B0),
        "indexed_direct_callsite_count": len(callers),
        "callers": callers,
        "relevant_producers": {
            "e37a50": {
                "callsite": "0xe37d4c",
                "result_use": (
                    "stores A9D0B0's row ordinal, clamps out-of-range to a fallback, reads "
                    "7e30f0[selector], formats ToolBreak_%s, and dispatches through DB1070."
                ),
                "selector_table_crosscheck": (
                    "db01e0 compares the same helper result to 10/9/8, matching ItemOutfitCategory "
                    "row ordinals Net/FishingRod/Axe; this separates row ordinal from UniqueID."
                ),
            },
            "aa7ce0": {
                "only_direct_caller": "0xee1060",
                "consumer_context": "0xee1420 DIY list rows (DiyCount/DIYFurniture/DIYItem/DIYTool)",
                "relationship": (
                    "A9D0B0 resolves an outfit category for break-message naming; AA7CE0 reads "
                    "BreakDamage-current ToolDamage for a workbench/list consumer. There is no "
                    "indexed call edge between these functions or from AA7CE0 into the break-state callbacks."
                ),
            },
        },
    }


def code_pointer_array(research_root: Path, start: int) -> dict | None:
    path = research_root / "binary/code_pointer_arrays.json"
    if not path.is_file():
        return None
    rows = json.loads(path.read_text())
    return next((row for row in rows if int(row["start_va"], 16) == start), None)


def relocation_page_audit() -> dict:
    """Check direct page/literal relocation references to the candidate table base."""
    try:
        sys.path.insert(0, str(ROOT / "tools"))
        from native_image import Image
        image = Image()
        target_page = SAVEPROC_ARRAY & ~0xFFF
        adrp_hits = []
        for segment in image.segments:
            if not segment["p_flags"] & 1:
                continue
            data = image.read(segment["p_vaddr"], segment["p_filesz"])
            base = segment["p_vaddr"]
            for offset in range(0, len(data), 4):
                word = struct.unpack_from("<I", data, offset)[0]
                if word & 0x9F000000 != 0x90000000:
                    continue
                pc = base + offset
                imm = (((word >> 5) & 0x7FFFF) << 2) | ((word >> 29) & 3)
                if imm & (1 << 20):
                    imm -= 1 << 21
                if ((pc & ~0xFFF) + (imm << 12)) & 0xFFFFFFFFFFFFFFFF == target_page:
                    adrp_hits.append(hex(pc))
        table_relocation_refs = [hex(va) for va, target in image.relocations.items()
                                 if target == SAVEPROC_ARRAY]
        return {
            "executable_adrp_page_refs_to_array_page": adrp_hits,
            "relative_relocation_targets_equal_array_base": table_relocation_refs,
            "scope": "Main ELF direct ADRP-page and RELATIVE-relocation checks; computed/runtime references can remain.",
        }
    except (ImportError, OSError, ValueError) as exc:
        return {"status": "UNAVAILABLE", "error": str(exc)}


def saveproc_route(conn: sqlite3.Connection, research_root: Path) -> dict:
    array = code_pointer_array(research_root, SAVEPROC_ARRAY)
    entries = array.get("entries", []) if array else []
    candidate_entries = [entry for entry in entries
                         if int(entry["target_va"], 16) == FAFEC0]
    callback_edges = []
    for owner in (FAFEC0, *SAVEPROC_TASKS):
        end = conn.execute("SELECT span_end_va FROM native_functions WHERE va=?", (owner,)).fetchone()
        if not end:
            continue
        for pc, target in conn.execute(
                "SELECT pc,target_va FROM direct_calls WHERE pc>=? AND pc<? ORDER BY pc",
                (owner, end[0])):
            callback_edges.append({"owner": hex(owner), "callsite": hex(pc), "target": hex(target)})

    write_flush = {}
    for label, target in WRITE_FLUSH.items():
        found = []
        for pc, direct_owner in conn.execute(
                "SELECT pc,owner_va FROM direct_calls WHERE target_va=? ORDER BY pc", (target,)):
            owner = direct_owner if direct_owner is not None else resolve_owner(conn, pc)
            found.append({"callsite": hex(pc), "owner": function_label(conn, owner)})
        write_flush[label] = found

    return {
        "save_request_registration": {
            "request_dispatch": "0x338080 -> 0xfb3160",
            "worker_registration": "0xfb4150 -> 0xd4240",
            "worker_name": "SaveProc",
            "queue_copy": "0xfb3160 builds a 0x38-byte request descriptor and passes it to 0xfaf180.",
            "generic_dispatch": "0xd45c0 -> 0x2201820; the generic executor invokes a callback through the queued object's first vtable slot.",
        },
        "candidate_relocated_callback_sequence": {
            "array_start_va": hex(SAVEPROC_ARRAY),
            "status": array.get("status") if array else None,
            "entry_count": len(entries),
            "fafec0_entries": candidate_entries,
            "direct_task_and_file_edges": callback_edges,
            "binding_limit": (
                "The table sequence contains FAFEC0, whose body dispatches the five FB1E10/FB1FF0/FB2200/FB23E0/FB25E0 "
                "task helpers. The queue object's vptr/slot has not been statically tied to this sequence; "
                "treat it as a candidate, not a proven SaveProc vtable."
            ),
        },
        "candidate_file_path_boundary": {
            "helper_chain": "candidate task helpers reach 0xf214a0/0xf21350; native fixture reaches mount, open, set-size(0x4000), close.",
            "write_flush_direct_callers_elsewhere": write_flush,
            "write_flush_reached_from_request_or_candidate_helpers": False,
            "serialized_player_slot_bytes_proven": False,
        },
        "direct_table_reference_scan": relocation_page_audit(),
        "runtime_capture_required": [
            "Capture the complete 0xfb3160 descriptor at enqueue and the matching 0xfaf180 queue slot, including pointer values and worker name.",
            "At 0xd45c0/0x2201820, record the actual queued callback object address, vptr, selected function slot, and indirect target; compare it with the 0x32ff8d8 candidate sequence.",
            "Record the same player's ItemParam slot bytes before/after last-use and SaveProc, then capture buffer pointer, length, offset, and bytes at WriteFile/FlushFile/Commit plus reload result.",
        ],
        "static_boundary": (
            "Available code proves request/queue and generic callback dispatch, plus a candidate helper path to file open/size/close. "
            "It does not identify the callback target selected for SaveProc or connect the dirty slot to a serialized range or durable flush."
        ),
    }


def run(index_db: Path, research_root: Path, output: Path) -> dict:
    conn = sqlite3.connect(f"file:{index_db.resolve()}?mode=ro", uri=True)
    result = {
        "schema": "acnh-re/tool-durability-producer-dispatch-static/1",
        "game_version": "1.0.0",
        "evidence_level": "INDEXED_NATIVE_CALLS_BCSV_JOIN_AND_RELOCATED_CODE_POINTERS",
        "item_category_selector_join": tool_family_rows(research_root),
        "a9d0b0_family_index_callers": a9d0b0_callers(conn),
        "db1070_event_dispatch_callers": event_dispatch_callers(conn),
        "saveproc_callback_to_serializer": saveproc_route(conn, research_root),
        "conclusion": (
            "Tool-family selection for the break message is statically explained by ItemParam.ItemOutfitInfo -> "
            "ItemOutfitInfo.Category -> ItemOutfitCategory row ordinal and does not consume remaining durability. "
            "AA7CE0 remains only a DIY-list consumer. The zero-remaining state transition and durable slot serializer "
            "remain unproven at the stated native/runtime boundaries."
        ),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({
        "schema": result["schema"],
        "player_tool_rows": result["item_category_selector_join"]["player_tool_row_count"],
        "selectors": result["item_category_selector_join"]["selector_by_family"],
        "a9d0b0_callers": result["a9d0b0_family_index_callers"]["indexed_direct_callsite_count"],
        "db1070_callers": result["db1070_event_dispatch_callers"]["indexed_direct_callsite_count"],
        "saveproc_candidate_entries": result["saveproc_callback_to_serializer"]["candidate_relocated_callback_sequence"]["fafec0_entries"],
        "output": str(output),
    }, indent=2))
    conn.close()
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--index-db", type=Path, default=DEFAULT_INDEX)
    parser.add_argument("--research-root", type=Path, default=DEFAULT_RESEARCH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    run(args.index_db, args.research_root, args.output)


if __name__ == "__main__":
    main()
