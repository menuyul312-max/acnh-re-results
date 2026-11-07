#!/usr/bin/env python3
"""Bound the remaining native tool-wear, break, ring, and save paths."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sqlite3

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INDEX = Path("/workspace/acnh-re/output/index.sqlite")
DEFAULT_RESEARCH = Path("/workspace/acnh-re/output")
DEFAULT_OUTPUT = ROOT / "output/gameplay/tool_mechanics_followup/tool_durability_residual_static.json"

BREAK_DISPATCH_TARGETS = (0xE37830, 0xE37A50, 0xE37ED0)
WEAR_TARGETS = (0xE893C0, 0xE895A0, 0xDB00F0)
RING_CALLBACK = 0x1417F70
RING_ITEM_READ = 0x11B7210
REMAINING_DAMAGE = 0xAA7CE0
REMAINING_DAMAGE_CONSUMER = 0xEE1060
PLAYER_ITEM_CONTEXT_GLOBAL = "33d3e00"
PLAYER_SLOT_BASE = "0x204"
SLOT_DIRTY_SET = re.compile(r"0x0*4000(?![0-9a-f])", re.IGNORECASE)
SLOT_DIRTY_CLEAR = re.compile(r"0x0*ffffbfff(?![0-9a-f])", re.IGNORECASE)
SAVEPROC_NODES = (0x337F00, 0x338080, 0xFB3160, 0xFAF180, 0xF1DA80)


def edge_rows(conn: sqlite3.Connection, *, target: int | None = None,
              owner: int | None = None) -> list[dict]:
    clauses, values = [], []
    if target is not None:
        clauses.append("target_va=?")
        values.append(target)
    if owner is not None:
        clauses.append("owner_va=?")
        values.append(owner)
    query = "SELECT pc, owner_va, target_va FROM direct_calls"
    if clauses:
        query += " WHERE " + " AND ".join(clauses)
    query += " ORDER BY pc"
    return [{"pc": hex(pc),
             "owner_va": hex(owner_va) if owner_va is not None else None,
             "target_va": hex(target_va)}
            for pc, owner_va, target_va in conn.execute(query, values)]


def function_info(conn: sqlite3.Connection, va: int) -> dict:
    row = conn.execute(
        "SELECT name, size, span_end_va FROM native_functions WHERE va=?", (va,)
    ).fetchone()
    if row is None:
        raise ValueError(f"native function {va:#x} missing from index")
    name, size, end = row
    calls = conn.execute(
        "SELECT pc, target_va FROM direct_calls WHERE owner_va=? ORDER BY pc", (va,)
    ).fetchall()
    strings = [text for (text,) in conn.execute(
        "SELECT text FROM string_refs WHERE function_va=? ORDER BY text", (va,)
    )]
    return {
        "function_va": hex(va),
        "name": name,
        "size_bytes": size,
        "span_end_va": hex(end),
        "string_refs": strings,
        "direct_calls": [{"pc": hex(pc), "target_va": hex(target)}
                         for pc, target in calls],
        "direct_callers": edge_rows(conn, target=va),
    }


def eventflow_rows(conn: sqlite3.Connection, flow: str) -> list[dict]:
    return [{"index": index, "actor": actor, "kind": kind, "name": name,
             "params": json.loads(params) if params else None}
            for index, actor, kind, name, params in conn.execute(
                "SELECT event_index,actor,kind,name,params_json FROM event_calls "
                "WHERE flow=? ORDER BY event_index", (flow,))]


def saveproc_summary(research_root: Path) -> dict | None:
    candidates = [
        research_root / "gameplay/crafting_transaction_followup/crafting_transaction_followup_static.json",
        ROOT / "output/gameplay/crafting_transaction_followup/crafting_transaction_followup_static.json",
    ]
    path = next((candidate for candidate in candidates if candidate.is_file()), None)
    if path is None:
        return None
    boundary = json.loads(path.read_text()).get("save_flush_boundary", {})
    return {
        "source_artifact": str(path),
        "explicit_save_event_action_count": boundary.get("explicit_save_event_action_count"),
        "system_save_close_event": boundary.get("system_save_close_event"),
        "native_request_path": boundary.get("native_request_path"),
        "durable_flush_status": boundary.get("durable_flush_status",
            "Serializer/file write after SaveProc remains outside the recorded trace."),
        "scope_limit": (
            "This is the generic SaveSimpleSave -> SaveProc request/completion trace. "
            "It does not connect the tool-slot dirty bit to a serialized field or prove a disk flush."
        ),
    }


def dirty_slot_decomp_scan(conn: sqlite3.Connection, research_root: Path) -> dict:
    """Search every indexed decomp snapshot for the exact player-slot dirty-bit access."""
    rows = conn.execute("SELECT va,path FROM decomp_new ORDER BY va").fetchall()
    scanned = 0
    context_slot_functions = 0
    marker_accesses = []
    paths_by_va = {va: path for va, path in rows}
    for va, relative in rows:
        if not relative:
            continue
        path = research_root / relative
        if not path.is_file():
            continue
        source = path.read_text(errors="ignore")
        scanned += 1
        has_context = PLAYER_ITEM_CONTEXT_GLOBAL in source.lower()
        has_slot_base = PLAYER_SLOT_BASE in source.lower()
        if has_context and has_slot_base:
            context_slot_functions += 1
        if not (has_context and has_slot_base):
            continue
        for match in SLOT_DIRTY_SET.finditer(source):
            line = source.count("\n", 0, match.start()) + 1
            text = source.splitlines()[line - 1].strip()
            marker_accesses.append({"function_va": hex(va), "operation": "set_0x4000",
                                    "decomp_path": relative, "line": line,
                                    "source": text})
        for match in SLOT_DIRTY_CLEAR.finditer(source):
            line = source.count("\n", 0, match.start()) + 1
            text = source.splitlines()[line - 1].strip()
            marker_accesses.append({"function_va": hex(va), "operation": "clear_0x4000",
                                    "decomp_path": relative, "line": line,
                                    "source": text})

    save_nodes = []
    for va in SAVEPROC_NODES:
        relative = paths_by_va.get(va)
        source_path = research_root / relative if relative else None
        source = source_path.read_text(errors="ignore") if source_path and source_path.is_file() else ""
        save_nodes.append({
            "function_va": hex(va),
            "decomp_path": relative,
            "decomp_available": bool(source),
            "references_player_item_context_global": PLAYER_ITEM_CONTEXT_GLOBAL in source.lower(),
            "references_player_slot_base_0x204": PLAYER_SLOT_BASE in source.lower(),
            "references_exact_slot_dirty_set_or_clear": bool(
                SLOT_DIRTY_SET.search(source) or SLOT_DIRTY_CLEAR.search(source)
            ),
        })

    return {
        "evidence_level": "EXHAUSTIVE_TEXT_SCAN_OF_INDEXED_DECOMP_NEW_SNAPSHOT",
        "decomp_root": str(research_root / "binary/analysis_decomp"),
        "indexed_snapshot_rows": len(rows),
        "decomp_files_scanned": scanned,
        "functions_referencing_player_context_and_slot_base": context_slot_functions,
        "exact_marker_accesses": marker_accesses,
        "saveproc_chain_nodes": save_nodes,
        "finding": (
            "Across the available indexed decompilation snapshot, the only exact access to "
            "the per-player slot-state word at context+0x204+slot*8 using marker 0x4000 is "
            "the e895a0 setter and e767b0 clear-mask. The SaveSimpleSave/SaveProc nodes with "
            "available decompilation do not reference that player-slot context or marker; "
            "the process-dispatch node 0x338080 has no indexed decomp snapshot."
        ),
        "bound": (
            "This is a static scan of indexed decomp source, not proof that no indirect or "
            "omitted serializer callback reads the slot marker. SaveProc request/completion "
            "is mapped separately; the serializer and durable file write/flush remain unknown."
        ),
    }


def run(index_db: Path, research_root: Path, output: Path) -> dict:
    conn = sqlite3.connect(f"file:{index_db.resolve()}?mode=ro", uri=True)
    remaining_callers = edge_rows(conn, target=REMAINING_DAMAGE)
    break_dispatch = [edge for target in BREAK_DISPATCH_TARGETS
                      for edge in edge_rows(conn, target=target)]
    ring_calls = edge_rows(conn, owner=RING_CALLBACK)
    relevant_ring_calls = [edge for edge in ring_calls if int(edge["target_va"], 16) in {
        RING_ITEM_READ, 0x157E140, 0x1591C00, 0xF589E0, 0xE893C0, 0xE895A0, 0xDB00F0
    }]
    ring_wear_edges = [edge for edge in ring_calls
                       if int(edge["target_va"], 16) in WEAR_TARGETS]
    consumer_strings = [text for (text,) in conn.execute(
        "SELECT text FROM string_refs WHERE function_va=? ORDER BY text",
        (REMAINING_DAMAGE_CONSUMER,))]
    flow = eventflow_rows(conn, "Player_ToolBreak")
    save_event = [{"flow": row[0], "event_index": row[1], "actor": row[2],
                   "kind": row[3], "name": row[4], "params": json.loads(row[5]) if row[5] else None}
                  for row in conn.execute(
                      "SELECT flow,event_index,actor,kind,name,params_json FROM event_calls "
                      "WHERE flow='System_SaveGameClose' AND name='EventFlowActionSaveSimpleSave' "
                      "ORDER BY event_index")]

    result = {
        "schema": "acnh-re/tool-durability-residual-static/1",
        "evidence_level": "INDEXED_NATIVE_CALLS_EVENTFLOW_AND_EXISTING_BOUNDED_PROBES",
        "game_version": "1.0.0",
        "zero_remaining_to_break_state": {
            "remaining_damage_helper": function_info(conn, REMAINING_DAMAGE),
            "remaining_helper_direct_callers": remaining_callers,
            "only_indexed_consumer": {
                **function_info(conn, REMAINING_DAMAGE_CONSUMER),
                "parent_string_refs": consumer_strings,
            },
            "break_state_lifecycle_edges": break_dispatch,
            "break_state_handlers": {
                hex(va): function_info(conn, va) for va in BREAK_DISPATCH_TARGETS
            },
            "break_state_wear_edges": [
                edge for va in BREAK_DISPATCH_TARGETS
                for edge in edge_rows(conn, owner=va)
                if int(edge["target_va"], 16) in {
                    0xAA7700, 0xAA77D0, 0xAA79A0, REMAINING_DAMAGE,
                    0xE895A0, 0xE893C0, 0xDB00F0,
                }
            ],
            "handler_notes": {
                "0xe37830": (
                    "Branches on state byte +0x1024: zero requests the BreakTool event flag; "
                    "nonzero enters e37950. Clears state-local +0x898 and +0x89c."
                ),
                "0xe37a50": (
                    "Updates PlayerToolBreak animation/timing fields, increments state-local "
                    "+0x898 on progression branches, and can enter e37950; no ToolDamage or "
                    "BreakDamage helper call is indexed."
                ),
                "0xe37ed0": (
                    "Clears ForceToolBreakDemo through f4e990 and can enter e37950 on its "
                    "state gate; no ToolDamage or BreakDamage helper call is indexed."
                ),
            },
            "player_tool_break_eventflow": flow,
            "finding": (
                "The only indexed direct call to 0xaa7ce0 is 0xee1198 from 0xee1060. "
                "That consumer is called six times by 0xee1420, whose string refs are "
                "DiyCount/DIYFurniture/DIYItem/DIYTool, so the remaining-value helper is "
                "currently evidenced as a workbench/list display input. Indexed code also "
                "shows state lifecycle edges at 0xdf6584->0xe37830, 0xdf65d8->0xe37a50, "
                "and 0xdf6654->0xe37ed0. These show BreakTool/PlayerToolBreak/force-break "
                "handlers are dispatched, but no threshold comparison or call edge from "
                "the remaining-value consumer into that lifecycle is present in the index."
            ),
            "bound": (
                "The packed damage arithmetic and BreakDamage threshold are executed in the "
                "existing bounded helper probe; end-to-end action-state selection at zero "
                "remaining requires a live game state or the omitted indirect transition producer."
            ),
        },
        "action_cadence_and_wear_commit": {
            "wear_chain_functions": {
                hex(va): function_info(conn, va) for va in WEAR_TARGETS
            },
            "known_shovel_action_sites": [
                edge for edge in edge_rows(conn, target=0xDB0140)
                if edge["owner_va"] in {"0xe52390", "0xe52ee0", "0xe541a0"}
            ],
            "wrapper_status_contract": {
                "0xe895a0": (
                    "Returns 0 when its item-use gate or native wear increment fails; returns "
                    "1 after the packed word is copied back and the selected slot flag is set. "
                    "The status does not encode remaining damage or break state."
                ),
                "0xe893c0": (
                    "Has no scalar return status; it checks e895a0's low-bit success before "
                    "producing the action result descriptor. The db0140 consumer tests that "
                    "descriptor's ItemUniqueID against the empty sentinel -2."
                ),
                "0xdb00f0": (
                    "Returns 1 only when e895a0 succeeds (and then requests the action telemetry "
                    "update through dafee0); otherwise returns 0. Its indexed net, rod, and "
                    "generic callers do not branch on this scalar result."
                ),
            },
            "wrapper_action_callsites": {
                "0xe893c0": [
                    {"caller": "0x4c0190", "pc": "0x4c0258", "wear_amount": 1,
                     "result_use": "writes local output descriptor; caller ignores it"},
                    {"caller": "0xda4560", "pc": "0xda4598", "wear_amount": 1,
                     "result_use": "writes local output descriptor; caller ignores it"},
                    {"caller": "0xdb0140", "pc": "0xdb0168", "wear_amount": 1,
                     "result_use": "checks ItemUniqueID != -2, then enters item-result insertion"},
                ],
                "0xdb00f0": [
                    {"caller": "0xe45b80", "pc": "0xe45cbc", "action": "NetGetDemo",
                     "wear_amount": 1},
                    {"caller": "0xe4e730", "pc": "0xe4ea70", "action": "RodGetDemo",
                     "wear_amount": "1 or 2 from rod-state/item predicate"},
                    {"caller": "0xe899b0", "pc": "0xe89ac0", "action": "generic result path",
                     "wear_amount": "forwarded caller argument"},
                ],
            },
            "exhaustion_status_probe": {
                "artifact": "output/gameplay/tool_mechanics_followup/tool_durability_native.json",
                "item_unique_id": 2100,
                "break_damage": 100,
                "first_apply": {"start_damage": 99, "result_status": 1,
                                 "remaining_after": 0, "slot_marker": "0x4000"},
                "second_apply": {"start_damage": 100, "result_status": 1,
                                  "damage_after": 101,
                                  "remaining_unsigned": 4294967295,
                                  "remaining_signed": -1},
                "interpretation": (
                    "In this bounded native probe, e895a0's status is update success, not a "
                    "break notification; the wrapper permits another wear increment at zero remaining."
                ),
            },
            "finding": (
                "e895a0 is reached through e893c0 (which passes wear amount 1) and db00f0 "
                "(used by the net/rod result states and a generic indirect caller). The "
                "indexed call graph identifies shovel action sites through db0140. The "
                "remaining tools/families do not all converge on one statically indexed "
                "wear wrapper; no complete per-family use cadence is claimed."
            ),
        },
        "ring_selection_and_held_item_boundary": {
            "callback_va": hex(RING_CALLBACK),
            "relevant_direct_calls": relevant_ring_calls,
            "callback_direct_wear_edges": ring_wear_edges,
            "selected_item_reader": function_info(conn, RING_ITEM_READ),
            "finding": (
                "The ring callback reads an indexed pocket item descriptor and then invokes "
                "the UI item-pool manager and selection-state updater. No direct callback "
                "edge reaches e893c0/e895a0/db00f0 or a known held-hand writer. The existing "
                "bounded ring probe now tests distinct nonzero ToolDamage values 1..8 and "
                "preserves both the low 10 wear bits and upper reserved bits in the copied word."
            ),
            "held_item_transfer_status": "OPEN; ring-to-held-hand transition is not established",
        },
        "dirty_slot_and_saveproc_boundary": {
            "wear_writer": function_info(conn, 0xE895A0),
            "slot_flag_clearer": function_info(conn, 0xE767B0),
            "slot_flag_clearer_callers": edge_rows(conn, target=0xE767B0),
            "available_decomp_slot_marker_scan": dirty_slot_decomp_scan(conn, research_root),
            "tool_break_save_eventflow": save_event,
            "generic_saveproc_trace": saveproc_summary(research_root),
            "finding": (
                "The bounded e895a0 probe confirms in-memory packed-word copy-back and bit "
                "0x4000 on the selected player-item slot. e767b0 contains a matching clear "
                "for that bit as part of broader slot-state cleanup. An exhaustive scan of "
                "indexed decomp files finds no additional exact setter/clearer or reference "
                "from the SaveProc nodes to this slot-state array. EventFlow has an explicit "
                "SaveSimpleSave request at System_SaveGameClose, and the separate indexed "
                "SaveProc trace reaches its request/completion boundary. No indexed edge ties "
                "this tool dirty bit to a particular serialized save member or durable file flush."
            ),
        },
        "remaining_blockers": [
            "The indirect producer that selects PlayerToolBreak when an item's remaining value reaches zero is not identified.",
            "The ring callback's eventual transfer to the held-hand object and resulting ToolChange/ToolPullout action are not identified.",
            "ToolDamage's slot dirty-bit clear is visible, but the exact serializer mapping and durable write/flush remain open.",
            "Per-family cadence is only bounded at the indexed caller sites; a live player action sequence is unavailable.",
        ],
    }
    conn.close()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"schema": result["schema"],
                      "remaining_helper_callers": remaining_callers,
                      "break_lifecycle_edge_count": len(break_dispatch),
                      "ring_direct_wear_edge_count": len(ring_wear_edges),
                      "saveproc_trace_found": result["dirty_slot_and_saveproc_boundary"]["generic_saveproc_trace"] is not None,
                      "output": str(output)}, indent=2))
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
