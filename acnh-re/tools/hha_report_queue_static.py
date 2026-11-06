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
