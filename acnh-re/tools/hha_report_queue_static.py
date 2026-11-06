#!/usr/bin/env python3
"""Export static call-chain and EventFlow evidence for HHA report/mail follow-up."""
import hashlib
import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = Path("/workspace/acnh-re")
DB = DATA / "output/index.sqlite"
FLAG_REFS = DATA / "output/gameplay/native_flag_refs.json"
DECOMP = DATA / "output/binary/analysis_decomp"
NSO = DATA / "inputs/additional_exefs/main"
POINTER_ARRAYS = DATA / "output/binary/code_pointer_arrays.json"
USEN_MESSAGES = DATA / "output/additional_romfs/messages/USen"
OUT = ROOT / "output/gameplay/house_hha_followup/hha_report_queue_static.json"

BUCKET = 0x7B4FC0
BUCKET_RECEIVER = 0x7B6470
REPORT_RECORD_BUILDER = 0xAC77A0
REPORT_QUEUE_APPEND = 0xABF610
REPORT_BUILDERS = [0x7B6470, 0x7B53B0, 0x7B55E0, 0x7B5E60, 0x7B61E0]
SCORE_TOTAL_EVALUATOR = 0x7B1FE0
ITEM_SCORE_ACCUMULATOR = 0x7B36B0
SCORE_BUCKET = 0x7B4FC0
SCORE_BUCKET_RECEIVER = 0x7B6470
ITEM_SCORE_ACCUMULATOR_CALL_PC = 0x7B265C
ITEM_SCORE_HELPER_CALL_PC = 0x7B37B8

QUEUE_LIFECYCLE = {
    "append": 0xABF610,
    "flush": 0xABF910,
    "nonempty": 0xABF960,
    "filter_dispatch_remove": 0xABFA00,
    "consume_type_3": 0xABFB40,
    "pump": 0xAC0A60,
    "event_handoff": 0xAC13F0,
}
HHA_UI_FUNCTIONS = {0xAC2E30, 0xAC3360}
HHA_UI_TRAMPOLINES = {0x7B8420, 0x7B8270}
HHA_MESSAGE_MEMBERS = (
    "Sp/HHA/STR_HHA_Rank.msbt",
    "Sp/HHA/STR_HHA_RoomLocation.msbt",
    "Sp/HHA/STR_HHA_Set.msbt",
    "Sp/HHA/STR_HHA_Situation.msbt",
    "Sp/HHA/STR_HHA_Theme.msbt",
    "Sp/HHA/MAIL_SP_HHA_Grade.msbt",
    "Sp/HHA/MAIL_SP_HHA_GradeFixedPoints.msbt",
    "Sp/HHA/MAIL_SP_HHA_GradeMission.msbt",
    "Sp/HHA/MAIL_SP_HHA_Mission.msbt",
    "Sp/HHA/MAIL_SP_HHA_BuildCelebration.msbt",
)


def hsha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def hex_addr(value):
    return f"0x{value:x}"


def localized_inventory():
    """Return HHA message IDs and counts only; never copy localized bodies."""
    inventory = {}
    for archive in ("String", "Mail"):
        path = USEN_MESSAGES / f"{archive}.json"
        if not path.is_file():
            continue
        payload = json.loads(path.read_text())
        for member in HHA_MESSAGE_MEMBERS:
            if member not in payload["members"]:
                continue
            entry = payload["members"][member]
            messages = entry.get("messages", [])
            inventory[member] = {
                "entry_count": len(messages),
                "labels": [label for row in messages for label in row.get("labels", [])],
            }
    return inventory


def main():
    db = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    db.row_factory = sqlite3.Row

    def xrefs(target, owner=None):
        if owner is None:
            rows = db.execute(
                "SELECT pc,owner_va,instruction FROM direct_calls WHERE target_va=? ORDER BY pc",
                (target,))
        else:
            rows = db.execute(
                "SELECT pc,owner_va,instruction FROM direct_calls "
                "WHERE target_va=? AND owner_va=? ORDER BY pc", (target, owner))
        return [{"pc": f"0x{r['pc']:x}",
                 "owner": f"0x{r['owner_va']:x}" if r["owner_va"] is not None else None,
                 "instruction": r["instruction"]} for r in rows]

    def xrefs_in_function(target, function):
        row = db.execute("SELECT va,span_end_va FROM native_functions WHERE va=?",
                         (function,)).fetchone()
        if not row:
            raise AssertionError({"missing_function": hex(function)})
        rows = db.execute(
            "SELECT pc,owner_va,instruction FROM direct_calls "
            "WHERE target_va=? AND pc>=? AND pc<=? ORDER BY pc",
            (target, row["va"], row["span_end_va"]))
        return [{"pc": f"0x{r['pc']:x}",
                 "owner": f"0x{r['owner_va']:x}" if r["owner_va"] is not None else None,
                 "instruction": r["instruction"]} for r in rows]

    core_chain = [
        {"caller": 0x7B29D0, "target": BUCKET, "call_pc": 0x7B2BEC},
        {"caller": BUCKET, "target": BUCKET_RECEIVER, "call_pc": 0x7B52B0},
        {"caller": BUCKET_RECEIVER, "target": REPORT_RECORD_BUILDER, "call_pc": 0x7B66F0},
        {"caller": BUCKET_RECEIVER, "target": REPORT_QUEUE_APPEND, "call_pc": 0x7B6724},
    ]
    for edge in core_chain:
        actual = xrefs_in_function(edge["target"], edge["caller"])
        if not any(int(row["pc"], 16) == edge["call_pc"] for row in actual):
            raise AssertionError({"missing_call_edge": edge, "actual": actual})
        edge["caller"] = f"0x{edge['caller']:x}"
        edge["target"] = f"0x{edge['target']:x}"
        edge["call_pc"] = f"0x{edge['call_pc']:x}"

    report_branches = []
    for function in REPORT_BUILDERS:
        report_branches.append({
            "function": f"0x{function:x}",
            "record_builder_calls": xrefs_in_function(REPORT_RECORD_BUILDER, function),
            "queue_append_calls": xrefs_in_function(REPORT_QUEUE_APPEND, function),
        })

    score_decomp = {
        name: DECOMP / f"{name}.c"
        for name in ("7b1fe0", "7b4fc0", "7b6470", "ab9050")
    }
    for path in score_decomp.values():
        if not path.is_file():
            raise AssertionError({"missing_score_bridge_decomp": str(path)})
    item_accumulator_calls = xrefs_in_function(ITEM_SCORE_ACCUMULATOR, SCORE_TOTAL_EVALUATOR)
    if not any(int(row["pc"], 16) == ITEM_SCORE_ACCUMULATOR_CALL_PC
               for row in item_accumulator_calls):
        raise AssertionError({"missing_item_accumulator_call": item_accumulator_calls})
    item_helper_call = db.execute(
        "SELECT pc,target_va,instruction FROM direct_calls WHERE pc=? AND target_va=?",
        (ITEM_SCORE_HELPER_CALL_PC, 0xAB9050)).fetchone()
    if not item_helper_call:
        raise AssertionError({"missing_item_score_helper_call": hex(ITEM_SCORE_HELPER_CALL_PC)})
    score_total_bridge = {
        "evaluator_va": f"0x{SCORE_TOTAL_EVALUATOR:x}",
        "item_score_accumulator_va": f"0x{ITEM_SCORE_ACCUMULATOR:x}",
        "item_score_accumulator_call_pc": f"0x{ITEM_SCORE_ACCUMULATOR_CALL_PC:x}",
        "item_score_helper_va": "0xab9050",
        "item_score_helper_call_pc": f"0x{ITEM_SCORE_HELPER_CALL_PC:x}",
        "category_accumulator_offsets": [f"0x{x:x}" for x in range(0x24, 0x51, 4)],
        "temporary_total_offset": "0x136c",
        "per_area_delta_offset": "0xd8",
        "bucket_va": f"0x{SCORE_BUCKET:x}",
        "bucket_receiver_va": f"0x{SCORE_BUCKET_RECEIVER:x}",
        "bucket_area_count_offset": "0x154",
        "bucket_max_area_index_offset": "0x155",
        "bucket_min_area_index_offset": "0x156",
        "bucket_report_index_codes": {
            "mask_bit_8": {"mask": "0x100", "record_code": "0x33", "index_offset": "0x155"},
            "mask_bit_9": {"mask": "0x200", "record_code": "0x34", "index_offset": "0x156"},
        },
        "decomp_sha256": {f"{name}.c": hsha(path)
                           for name, path in score_decomp.items()},
        "static_trace": (
            "0x7b1fe0 calls item accumulator 0x7b36b0, which calls 0xab9050 for the item score; "
            "the native item accumulator adds the returned score to the current category field, "
            "then the evaluator recomputes +0x136c as the sum of twelve fields +0x24..+0x50, "
            "and stores the change from the previous total at +0xd8 + 4*min(area_index,5). "
            "0x7b4fc0 scans that +0xd8 array up to +0x154, records maximum/minimum indices "
            "at +0x155/+0x156, and sets mask bits 0x100/0x200; 0x7b6470 maps those bits "
            "to queued record codes 0x33/0x34."
        ),
        "limits": [
            "This is a static cross-reference of separate native functions, not an end-to-end native execution.",
            "The aggregate +0x136c is not itself mapped to a displayed HHA rank or threshold; the proven downstream values are per-area deltas and report-mask details.",
            "Queued record codes 0x33/0x34 have no proven localization, UI, or mail consumer in the indexed evidence.",
        ],
    }

    hha_mail_rows = [dict(r) for r in db.execute(
        "SELECT flow,event_index,actor,kind,name,params_json FROM event_calls "
        "WHERE params_json LIKE '%MAIL_SP_HHA%' OR params_json LIKE '%cHHA%' "
        "ORDER BY flow,event_index")]
    grade_flag_eventflow_rows = [dict(r) for r in db.execute(
        "SELECT flow,event_index,actor,kind,name,params_json FROM event_calls "
        "WHERE params_json LIKE '%HHAGradeMailFlag%' OR name LIKE '%HHAGradeMailFlag%' "
        "ORDER BY flow,event_index")]
    flag = json.loads(FLAG_REFS.read_text())["data"]["flags"]["cPlayer:HHAGradeMailFlag"]

    queue_lifecycle = {
        "shared_queue_global_va": "0x33d4ff8",
        "helpers": {
            name: {"function_va": hex_addr(va), "direct_callers": xrefs(va)}
            for name, va in QUEUE_LIFECYCLE.items()
        },
        "static_behavior": {
            "append": "0xabf610 appends a record object to the shared queue when its virtual eligibility method succeeds.",
            "pump": "0xac0a60 dispatches the generic queue, handles type-3 entries, then checks and flushes the queue.",
            "type_3": "0xabfb40 selects entries whose virtual type at +0x14 equals 3 and invokes the generic record handler.",
            "event_handoff": "0xac13f0 routes a generic event record through 0xabfa00 filter/dispatch/remove.",
        },
        "hha_specific_consumer_found": False,
        "limits": [
            "HHA evaluator callsites prove records enter the shared queue, but no direct or resolved virtual edge from those records to the generic consumer is identified.",
            "The pump, type-3 handler, and event handoff are generic queue lifecycle code; they do not prove a grade-mail or HHA UI consumer.",
        ],
    }

    ui_localization_refs = {}
    for function in HHA_UI_FUNCTIONS:
        rows = db.execute(
            "SELECT string_va,text FROM string_refs WHERE function_va=? ORDER BY string_va",
            (function,))
        ui_localization_refs[hex_addr(function)] = [
            {"string_va": hex_addr(row["string_va"]), "message_id": row["text"]}
            for row in rows if row["text"].startswith("STR_HHA_")
        ]

    ui_pointer_arrays = []
    if POINTER_ARRAYS.is_file():
        for array in json.loads(POINTER_ARRAYS.read_text()):
            entries = array.get("entries", [])
            targets = {row.get("target_va") for row in entries}
            if targets & {hex_addr(x) for x in HHA_UI_TRAMPOLINES}:
                ui_pointer_arrays.append({
                    "start_va": array["start_va"],
                    "hha_trampoline_targets": sorted(targets & {hex_addr(x) for x in HHA_UI_TRAMPOLINES}),
                    "targets": [row.get("target_va") for row in entries],
                })

    crosswalk_path = ROOT / "output/gameplay/save_layout_external_crosswalk.json"
    selector_candidate = {}
    saved_byte_candidate = {}
    if crosswalk_path.is_file():
        crosswalk = json.loads(crosswalk_path.read_text())
        for row in crosswalk.get("vtable_crosswalk", []):
            if row.get("sample_node") == "0x17cd80":
                selector_candidate = {
                    "local_sample_node": row.get("sample_node"),
                    "local_vtable": row.get("vtable"),
                    "sample_data": row.get("sample_data"),
                    "size": row.get("size"),
                    "instances": row.get("instances"),
                    "external_matches": row.get("matches", []),
                    "confidence_note": "The local descriptor is unnamed; HouseLevel is an offset/size cross-version candidate, not local RTTI proof.",
                }
            if row.get("sample_node") == "0x18b058":
                saved_byte_candidate = {
                    "local_sample_node": row.get("sample_node"),
                    "local_vtable": row.get("vtable"),
                    "sample_data": row.get("sample_data"),
                    "size": row.get("size"),
                    "instances": row.get("instances"),
                    "external_matches": row.get("matches", []),
                    "confidence_note": "The one-byte local sample has no exact external path and no local semantic name.",
                }

    selector_and_saved_flag = {
        "selector": {
            "evaluator_va": "0x7b1fe0",
            "node_accessor_global_va": "0x33dc730",
            "read_type": "u32",
            "invalid_value_behavior": "values > 8 are clamped to 0",
            "switch_values": {
                "2": {"area_denominator": 36, "area_count": 1},
                "3": {"area_denominator": 64, "area_count": 1},
                "4": {"area_denominator": 100, "area_count": 2},
                "5": {"area_denominator": 136, "area_count": 3},
                "6": {"area_denominator": 172, "area_count": 4},
                "7": {"area_denominator": 232, "area_count": 5},
                "8": {"area_denominator": 292, "area_count": 6},
            },
            "save_layout_candidate": selector_candidate,
        },
        "saved_grade_mail_flag_source": {
            "evaluator_va": "0x7b1fe0",
            "helper_va": "0xf95610",
            "helper_read": "signed byte at SavePlayerHouse + 0x263d0",
            "stored_evaluator_offset": "0x158",
            "setter_flag": "cPlayer:HHAGradeMailFlag",
            "setter_conditions": ["player index is nonzero", "selector > 1", "saved byte != -1"],
            "related_house_updater_va": "0xf949c0",
            "related_record_builder_va": "0xf95620",
            "related_house_updater_behavior": "For house levels 4-6 and a non--1 byte, 0xf95620 queues record code 0x19 and sets RcoWallFtrRemoveHouseRemodel from the byte.",
            "adjacent_byte_use": "0xf95ba0 compares a candidate against signed bytes +0x263d0 and +0x263d1; 0xf95ca0 serializes both when non--1.",
            "save_layout_candidate": saved_byte_candidate,
            "semantic_name": None,
            "confidence_note": "Native reads and consumers are identified, but the byte's local field name and its relationship to grade-mail delivery are unresolved.",
        },
    }

    fixed_points = {
        "function_va": "0x7b4720",
        "input_record_offset": "0x110",
        "input_value_type": "signed i32",
        "milestone_thresholds": [10000, 20000, 30000, 50000, 70000, 100000, 150000],
        "progress_member_size_bytes": "0x23c",
        "progress_update": "When the +0x110 value reaches the next band and its saved milestone index is behind, the function increments that index and calls 0x7b52d0.",
        "limit": "These are fixed-point progression cutoffs; no mapping from them or from +0x136c to the displayed S/A/B rank thresholds is proven.",
    }

    decomp_hashes = {}
    for name in ("7b1dd0", "7b1fe0", "7b29d0", "7b4720", "7b4fc0", "7b6470",
                 "ac77a0", "abf610", "7b53b0", "7b55e0", "7b5e60", "7b61e0"):
        path = DECOMP / f"{name}.c"
        if path.exists():
            decomp_hashes[f"{name}.c"] = hsha(path)

    result = {
        "schema": "acnh-re/hha-report-queue-static/1",
        "native_elf_sha256": hsha(NSO),
        "core_bucket_report_call_chain": core_chain,
        "report_record_builder_nso_va": "0xac77a0",
        "report_queue_append_nso_va": "0xabf610",
        "report_branches": report_branches,
        "score_total_to_report_bridge": score_total_bridge,
        "shared_queue_lifecycle": queue_lifecycle,
        "selector_and_saved_flag_source": selector_and_saved_flag,
        "fixed_point_progression_thresholds": fixed_points,
        "ui_localization": {
            "native_functions": ui_localization_refs,
            "trampoline_pointer_arrays": ui_pointer_arrays,
            "us_en_resource_inventory": localized_inventory(),
            "limits": [
                "0xac2e30 and 0xac3360 reference localized HHA UI message IDs, but no direct call from the shared queue consumer to these builders is established.",
                "Only message IDs, labels, and counts are exported; localized message bodies are deliberately omitted.",
            ],
        },
        "mail_lookup": {
            "indexed_hha_mail_actions": hha_mail_rows,
            "indexed_grade_flag_eventflow_accesses": grade_flag_eventflow_rows,
            "native_flag_references": flag["referencing_functions"],
            "native_flag_name_ja": flag["name_ja"],
        },
        "decomp_sha256": decomp_hashes,
        "scope": (
            "Static references establish HHA score/report record creation, a shared queue lifecycle, "
            "localized HHA UI resources, and fixed-point progression cutoffs. They do not establish "
            "the HHA-specific queue consumer, displayed rank point cutoffs, or conversion to grade mail."
        ),
    }
    db.close()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"output": str(OUT),
                      "core_edges": len(core_chain),
                      "report_branches": len(report_branches),
                      "queue_lifecycle_helpers": len(queue_lifecycle["helpers"]),
                      "localized_hha_resources": len(result["ui_localization"]["us_en_resource_inventory"]),
                      "indexed_hha_mail_actions": len(hha_mail_rows),
                      "indexed_grade_flag_eventflow_accesses": len(grade_flag_eventflow_rows)},
                     indent=2))


if __name__ == "__main__":
    main()
