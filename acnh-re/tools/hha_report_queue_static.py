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


def hsha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


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

    decomp_hashes = {}
    for name in ("7b1dd0", "7b1fe0", "7b29d0", "7b4fc0", "7b6470",
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
        "mail_lookup": {
            "indexed_hha_mail_actions": hha_mail_rows,
            "indexed_grade_flag_eventflow_accesses": grade_flag_eventflow_rows,
            "native_flag_references": flag["referencing_functions"],
            "native_flag_name_ja": flag["name_ja"],
        },
        "decomp_sha256": decomp_hashes,
        "scope": (
            "Static call references establish that the score-bucket path and "
            "several HHA branches build report records and call a shared queue "
            "helper. The queue consumer, localization mapping, and any later "
            "conversion to a grade mail are not established by this evidence."
        ),
    }
    db.close()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"output": str(OUT),
                      "core_edges": len(core_chain),
                      "report_branches": len(report_branches),
                      "indexed_hha_mail_actions": len(hha_mail_rows),
                      "indexed_grade_flag_eventflow_accesses": len(grade_flag_eventflow_rows)},
                     indent=2))


if __name__ == "__main__":
    main()
