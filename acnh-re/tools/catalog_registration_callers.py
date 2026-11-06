#!/usr/bin/env python3
"""Inventory native direct-call sites of the unique-item catalog registrar."""
import argparse
import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INDEX = Path("/workspace/acnh-re/output/index.sqlite")
DEFAULT_OUTPUT = ROOT / "output/gameplay/catalog_registration_callers.json"
TARGET = 0xEEBE80


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--index-db", type=Path, default=DEFAULT_INDEX)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    db_uri = f"file:{args.index_db.resolve()}?mode=ro"
    conn = sqlite3.connect(db_uri, uri=True)
    calls = conn.execute(
        "SELECT pc, instruction FROM direct_calls WHERE target_va=? ORDER BY pc",
        (TARGET,),
    ).fetchall()
    if not calls:
        raise SystemExit(f"no direct-call records for {TARGET:#x} in {args.index_db}")

    callers = {}
    unresolved = []
    for pc, instruction in calls:
        ranges = conn.execute(
            """SELECT va, name, span_end_va, evidence FROM native_functions
               WHERE va<=? AND span_end_va>? ORDER BY (span_end_va-va), va""",
            (pc, pc),
        ).fetchall()
        if not ranges:
            ranges = conn.execute(
                """SELECT va, ghidra_name, va+size, 'function_snapshot' FROM functions
                   WHERE va<=? AND va+size>? ORDER BY size, va""",
                (pc, pc),
            ).fetchall()
        if not ranges:
            unresolved.append({"pc": hex(pc), "instruction": instruction})
            continue

        va, name, _end, evidence = ranges[0]
        rec = callers.setdefault(va, {
            "function_va": hex(va), "name": name, "range_evidence": evidence,
            "call_sites": [],
        })
        rec["call_sites"].append({"pc": hex(pc), "instruction": instruction})

    for va, rec in callers.items():
        path = conn.execute("SELECT path FROM decomp_new WHERE va=?", (va,)).fetchone()
        if path:
            rec["pseudocode"] = path[0]
        else:
            old = conn.execute("SELECT decomp_path FROM functions WHERE va=?", (va,)).fetchone()
            rec["pseudocode"] = old[0] if old else None
        rec["string_refs"] = [row[0] for row in conn.execute(
            "SELECT text FROM string_refs WHERE function_va=? ORDER BY text", (va,)
        )]
        rec["direct_call_count"] = len(rec["call_sites"])

    result = {
        "schema": "acnh-re/catalog-registration-callers/1",
        "evidence_level": "STATIC_DIRECT_CALL_XREF_INDEX",
        "target_va": hex(TARGET),
        "direct_call_records": len(calls),
        "resolved_caller_functions": len(callers),
        "unresolved_call_sites": unresolved,
        "callers": sorted(callers.values(), key=lambda item: int(item["function_va"], 16)),
        "limitation": (
            "Direct call references identify call sites, not the runtime condition that reaches them. "
            "String references can label a caller but absence of strings does not identify its gameplay source."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    conn.close()
    print(json.dumps({key: value for key, value in result.items() if key != "callers"}, indent=2))


if __name__ == "__main__":
    main()
