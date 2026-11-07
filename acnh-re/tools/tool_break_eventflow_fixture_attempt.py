#!/usr/bin/env python3
"""Build static break-flow fixtures and record bounded native-runtime blockers."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = ROOT / "output/gameplay/tool_mechanics_followup/tool_break_eventflow_fixture_attempt.json"
NSO = ROOT / "inputs/additional_exefs/main"
NATIVE_REPORT = ROOT / "output/gameplay/tool_mechanics_followup/tool_mechanics_followup_native.json"
RESIDUAL_REPORT = ROOT / "output/gameplay/tool_mechanics_followup/tool_durability_residual_static.json"
NATIVE_FOLLOWUP = ROOT / "output/gameplay/tool_mechanics_followup/tool_state_callback_native.json"

DURABILITY_TERMS = re.compile(r"ToolDamage|BreakDamage|durability|remaining|use.?count|wear", re.I)
BREAK_ENTRIES = (
    "ToolBreak_Axe", "ToolBreak_Scoop", "ToolBreak_Watering",
    "ToolBreak_Net", "ToolBreak_Slingshot", "ToolBreak_FishingRod",
)


def runtime_probe() -> dict:
    """Try to construct the existing emulator, but do not call handlers with fake `this` objects."""
    sys.path.insert(0, str(ROOT / "tools"))
    try:
        from nso_sandbox import Sandbox
    except Exception as error:  # keep environment-specific blocker in the generated evidence
        return {"status": "BLOCKED_SANDBOX_IMPORT", "error_type": type(error).__name__,
                "error": str(error), "native_calls_attempted": []}

    try:
        Sandbox(NSO)
    except Exception as error:
        return {"status": "BLOCKED_SANDBOX_INITIALIZATION", "error_type": type(error).__name__,
                "error": str(error), "native_calls_attempted": []}

    return {
        "status": "SANDBOX_AVAILABLE_BUT_VALID_CONTEXT_REQUIRED",
        "native_calls_attempted": [],
        "reason": (
            "The state update handlers are member callbacks with a live player-state object graph, "
            "indirect vtable targets, actor/event context, and flag-store state. A zero-filled `this` "
            "pointer would be an invalid fixture and could not test tool-family selection."
        ),
    }


def build(output: Path) -> dict:
    native = json.loads(NATIVE_REPORT.read_text())
    residual = json.loads(RESIDUAL_REPORT.read_text())
    flow = native["player_tool_break_eventflow"]["entries"]
    if tuple(flow) != BREAK_ENTRIES:
        raise ValueError(f"unexpected Player_ToolBreak entries: {tuple(flow)}")

    fixtures = []
    for entry_name, events in flow.items():
        conditions = [event for event in events if event.get("op") == "IF"]
        matching_durability_inputs = []
        for event in events:
            if event.get("op") == "IF" and DURABILITY_TERMS.search(
                    json.dumps({"text": event.get("text"), "params": event.get("params")},
                               ensure_ascii=False)):
                matching_durability_inputs.append(event)
        fixtures.append({
            "entry_point": entry_name,
            "event_count": len(events),
            "operations": [event["op"] for event in events],
            "conditions": conditions,
            "durability_condition_count": len(matching_durability_inputs),
            "durability_conditions": matching_durability_inputs,
            "events": events,
        })

    if any(fixture["durability_condition_count"] for fixture in fixtures):
        raise AssertionError("a Player_ToolBreak condition now names a durability input; review manually")

    callback_audit = residual["zero_remaining_to_break_state"]["indirect_player_state_callback_audit"]
    save_audit = residual["dirty_slot_and_saveproc_boundary"]["saveproc_exefs_worker_audit"]
    entry_flags = callback_audit["player_tool_break_entry_flag_effects"]
    flag_writes = {
        entry: effect["flag_writes"] for entry, effect in entry_flags.items()
        if effect["flag_writes"]
    }
    if set(flag_writes) != {"ToolBreak_Axe"}:
        raise AssertionError(f"unexpected tool-break EventFlow flag writers: {flag_writes}")

    break_handler_info = residual["zero_remaining_to_break_state"]["break_state_handlers"]
    handlers = {}
    for address in ("0xe37a50", "0xe37ed0"):
        row = break_handler_info[address]
        handlers[address] = {
            "name": row["name"],
            "string_refs": row["string_refs"],
            "direct_call_targets": sorted({edge["target_va"] for edge in row["direct_calls"]}),
            "has_direct_wear_or_remaining_helper_edge": any(
                edge["target_va"] in {
                    "0xaa7ce0", "0xaa7700", "0xaa77d0", "0xe895a0", "0xe893c0", "0xdb00f0"
                } for edge in row["direct_calls"]
            ),
        }
    if any(row["has_direct_wear_or_remaining_helper_edge"] for row in handlers.values()):
        raise AssertionError("break handler now directly reaches a durability helper; review manually")

    candidate = save_audit["saveproc_callback_pointer_candidate"]
    file_audit = save_audit["filesystem_imports_resolved_to_sdk"]
    helper_edges = candidate["direct_task_and_filesystem_edges"]
    helper_targets = [row["function_va"] for row in candidate["task_callbacks"]]
    if "0xf214a0" not in {edge["target_va"] for edge in helper_edges}:
        raise AssertionError("SaveProc task path no longer reaches the bounded save-path helper")
    helper_operations = [
        edge for edge in helper_edges
        if edge["target_va"] in {"0x220ee60", "0x220ee80", "0x220ee90", "0x220eea0"}
    ]
    if {edge["target_va"] for edge in helper_operations} != {
            "0x220ee60", "0x220ee80", "0x220ee90", "0x220eea0"}:
        raise AssertionError("SaveProc mount/open/size/close helper edges are incomplete")

    runtime = runtime_probe()
    native_followup = json.loads(NATIVE_FOLLOWUP.read_text()) if NATIVE_FOLLOWUP.is_file() else None
    runtime["existing_harness_attempt"] = {
        "commands": [
            "PYTHONPATH=/workspace/acnh-re/.deps:/workspace/acnh-re-github/acnh-re/tools "
            "python3 acnh-re/tools/tool_break_action_native.py",
            "PYTHONPATH=/workspace/acnh-re/.deps:/workspace/acnh-re-github/acnh-re/tools "
            "python3 acnh-re/tools/tool_break_transition_native.py",
            "PYTHONPATH=/workspace/acnh-re/.deps:/workspace/acnh-re-github/acnh-re/tools "
            "python3 acnh-re/tools/tool_state_callback_native.py",
        ],
        "status": ("RERUN_PASSED_WITH_SHARED_DEPENDENCY_PATH" if native_followup is not None
                   else "INITIAL_DEFAULT_PATH_BLOCKED_BEFORE_ENTRYPOINT"),
        "initial_error": "ModuleNotFoundError: No module named 'unicorn'",
        "resolved_python_path": "/workspace/acnh-re/.deps",
        "native_followup_artifact": str(NATIVE_FOLLOWUP) if native_followup is not None else None,
        "note": (
            "The initial default-path attempt failed before execution. With the shared dependency "
            "directory on PYTHONPATH, the native callback and file-helper fixtures run with "
            "controlled object, actor, EventFlow, and filesystem boundaries."
        ),
    }
    native_followup_summary = None
    if native_followup is not None:
        native_followup_summary = {
            "artifact": str(NATIVE_FOLLOWUP),
            "schema": native_followup.get("schema"),
            "player_tool_break_entry_dispatch_count": native_followup[
                "player_tool_break_update"]["dispatch_count"],
            "force_break_case_count": native_followup["force_tool_break_demo"]["case_count"],
            "saveproc_native_entries": native_followup["saveproc_file_helpers"]["native_entries"],
            "saveproc_dirty_word_unchanged": native_followup["saveproc_file_helpers"][
                "synthetic_manager"]["slot_word_unchanged"],
        }

    result = {
        "schema": "acnh-re/tool-break-eventflow-fixture-attempt/1",
        "evidence_level": "STATIC_EVENTFLOW_FIXTURES_AND_NATIVE_SANDBOX_ATTEMPT",
        "native_main": {
            "path": str(NSO),
            "available": NSO.is_file(),
            "sha256": hashlib.sha256(NSO.read_bytes()).hexdigest() if NSO.is_file() else None,
        },
        "eventflow_fixture": {
            "source": native["player_tool_break_eventflow"]["source"],
            "entry_point_count": len(fixtures),
            "entry_points": fixtures,
            "entry_flag_writes": flag_writes,
            "durability_condition_total": sum(fixture["durability_condition_count"]
                                               for fixture in fixtures),
            "finding": (
                "The six entrypoints are tool-family message flows. Only ToolBreak_Axe contains "
                "conditions, and those query recipe ownership/MainmenuRecipe/"
                "GoldenAxeLearningCount (Border 99); its only EventFlow flag write adds one to "
                "GoldenAxeLearningCount. No entrypoint condition names ToolDamage, BreakDamage, "
                "remaining durability, or use count. This fixture cannot establish which native "
                "state selects an entrypoint."
            ),
        },
        "parameterized_native_state_handlers": {
            "0xe37a50": {
                **handlers["0xe37a50"],
                "observed_state_fields": [
                    "+0x226 progression counter", "+0x227 local gate", "+0x409 state byte",
                    "+0x1024 outer branch byte", "+0x898/+0x89c state bookkeeping",
                ],
                "fixture_requirements": [
                    "player-state `this` object and nested actor/context objects",
                    "valid vtables for several indirect calls at slot +0xf0",
                    "current item/name context and EventFlow/UI dispatcher state",
                    "animation/progression values needed to reach the branch under test",
                ],
                "static_result": (
                    "String references identify PlayerToolBreak/PlayerToolBreakKeep and "
                    "Player_ToolBreak flow dispatch. The indexed function has no direct edge to "
                    "ToolDamage, BreakDamage, remaining-value, or a wear writer."
                ),
            },
            "0xe37ed0": {
                **handlers["0xe37ed0"],
                "fixture_requirements": [
                    "player-state `this` object and valid state-manager/flag-store context",
                    "ForceToolBreakDemo flag state and its native clear operation",
                    "state context required by the optional 0xe37950 counter path",
                ],
                "static_result": (
                    "The handler is gated through native state/flag helpers, clears "
                    "ForceToolBreakDemo on the enabled path, and has no direct durability edge."
                ),
            },
            "runtime_attempt": runtime,
            "native_followup": native_followup_summary,
            "boundary": (
                "This static fixture does not execute callbacks. The related native artifact uses "
                "a controlled object graph and stubs actor/EventFlow boundaries; it is not a live "
                "player-state trace."
            ),
        },
        "saveproc_synthetic_dirty_slot_attempt": {
            "status": (
                "FILE_HELPERS_EXECUTED_WITH_SYNTHETIC_FILESYSTEM; SLOT_SERIALIZER_ROUTE_UNRESOLVED"
                if native_followup is not None else
                "BLOCKED_BEFORE_NATIVE_CALL; DIRTY_SLOT_SERIALIZER_ROUTE_UNRESOLVED"
            ),
            "runtime_attempt": runtime,
            "native_followup": native_followup_summary,
            "candidate_worker": {
                "pointer_array_candidate": candidate["entries_for_fafec0"],
                "task_helper_targets": helper_targets,
                "direct_task_filesystem_edges": candidate["direct_task_and_filesystem_edges"],
                "sdk_filesystem_imports": file_audit,
            },
            "static_file_helper_contract": {
                "0xf214a0": (
                    "Save-device/path helper: conditionally mounts save data, then calls 0xf21350; "
                    "the arguments are path/name objects and a requested size."
                ),
                "0xf21350": (
                    "Builds a save path, opens the file, sets its size, and closes it. It does not "
                    "read the player item-slot dirty marker or serialize a slot record."
                ),
                "candidate_helper_direct_operations": helper_operations,
                "generic_main_filesystem_imports": [row["api"] for row in file_audit],
                "write_flush_status": (
                    "The generic imports are present in main, but the saved static audit finds "
                    "no direct WriteFile/FlushFile call from the SaveProc request, queue, or "
                    "candidate task-helper spans; indirect reachability remains open."
                ),
            },
            "synthetic_manager_contract": {
                "candidate_slot_dirty_word": "player-context+0x204+slot*8 = 0x4000",
                "required_missing_edge": (
                    "No resolved callback/serializer connects this manager word to the SaveProc "
                    "task object or to 0xf214a0/0xf21350."
                ),
                "result": (
                    "The native successor executes f214a0/f21350 with synthetic mount/path state, "
                    "but the dirty marker remains an unrelated sentinel. File creation/resize "
                    "does not demonstrate that this slot word is serialized."
                ),
            },
        },
        "conclusion": (
            "The static EventFlow fixtures rule out durability-named conditions inside the six "
            "break presentation entries, but they do not reveal the durability-based selector. "
            "The Unicorn path issue is resolved for bounded fixtures; their actor and filesystem "
            "boundaries remain controlled. SaveProc file helpers execute mount/open/size/close "
            "operations, but the dirty-word-to-task/serializer edge remains absent."
        ),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    result = build(args.output)
    print(json.dumps({
        "schema": result["schema"],
        "eventflow_entry_count": result["eventflow_fixture"]["entry_point_count"],
        "durability_condition_total": result["eventflow_fixture"]["durability_condition_total"],
        "native_runtime_status": result["parameterized_native_state_handlers"]["runtime_attempt"]["status"],
        "saveproc_status": result["saveproc_synthetic_dirty_slot_attempt"]["status"],
        "output": str(args.output),
    }, indent=2))


if __name__ == "__main__":
    main()
