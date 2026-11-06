#!/usr/bin/env python3
"""Inventory native direct-call sites of the unique-item catalog registrar."""
import argparse
import json
import sqlite3
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INDEX = Path("/workspace/acnh-re/output/index.sqlite")
DEFAULT_TABLE_ROOT = Path("/workspace/acnh-re/output")
DEFAULT_POINTER_ARRAYS = Path("/workspace/acnh-re/output/binary/code_pointer_arrays.json")
DEFAULT_OUTPUT = ROOT / "output/gameplay/catalog_registration_callers.json"
TARGET = 0xEEBE80
REGISTRATION_WRAPPER = 0xEFE070
SPECIAL_ITEMKIND_INDICES = [0x4F, 0x50, 0x51, 0x52]


def table_crosswalk(table_root):
    kind_table = json.loads((table_root / "tables_resolved/ItemKind.json").read_text())
    item_table = json.loads((table_root / "tables_resolved/ItemParam.json").read_text())
    kind_columns = {column["name"]: i for i, column in enumerate(kind_table["columns"])}
    item_columns = {column["name"]: i for i, column in enumerate(item_table["columns"])}
    groups = []
    for row_index in SPECIAL_ITEMKIND_INDICES:
        kind_row = kind_table["rows"][row_index]
        label = kind_row[kind_columns["Label"]]
        crc = zlib.crc32(label.encode("utf-8"))
        rows = []
        for item_index, item_row in enumerate(item_table["rows"]):
            enum_value = item_row[item_columns["ItemKind"]]
            if isinstance(enum_value, dict) and int(enum_value["hash"], 16) == crc:
                rows.append({
                    "itemparam_row": item_index,
                    "unique_id": item_row[item_columns["UniqueID"]],
                    "item_catalog_type": item_row[item_columns["ItemCatalogType"]]["labels"][0],
                    "remake_id": item_row[item_columns["RemakeID"]],
                })
        groups.append({
            "itemkind_row_index": row_index,
            "itemkind_label": label,
            "itemkind_unique_id": kind_row[kind_columns["UniqueID"]],
            "itemparam_rows": rows,
            "itemparam_row_count": len(rows),
            "item_catalog_type_counts": dict(sorted({
                key: sum(item["item_catalog_type"] == key for item in rows)
                for key in {item["item_catalog_type"] for item in rows}
            }.items())),
            "remake_id_values": sorted({item["remake_id"] for item in rows}),
        })
    return {
        "evidence_level": "TABLE_JOIN_ONLY",
        "join": "CRC32(ItemKind.Label) == ItemParam.ItemKind enum hash; rows retain source order/index",
        "rows": groups,
        "interpretation_limit": "The caller compares the ItemKind lookup result to these row indices. The table join labels those values but does not supply the caller's runtime trigger.",
    }


def caller_groups(conn, target):
    grouped = {}
    unresolved = []
    call_rows = conn.execute(
        "SELECT pc, instruction FROM direct_calls WHERE target_va=? ORDER BY pc",
        (target,),
    ).fetchall()
    for pc, instruction in call_rows:
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
        rec = grouped.setdefault(va, {
            "function_va": hex(va), "name": name, "range_evidence": evidence,
            "call_sites": [],
        })
        rec["call_sites"].append({"pc": hex(pc), "instruction": instruction})

    for va, rec in grouped.items():
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
    return call_rows, grouped, unresolved


def pointer_array_matches(pointer_arrays_path, callers):
    """Attach exact pointer-sequence membership without labeling tables as vtables."""
    if not pointer_arrays_path.exists():
        return {
            "available": False,
            "source": str(pointer_arrays_path),
            "matched_caller_functions": 0,
            "interpretation_limit": "Code-pointer inventory is absent; no dispatch inference is available.",
        }

    pointer_arrays = json.loads(pointer_arrays_path.read_text())
    matched = set()
    for caller in callers:
        function_va = int(caller["function_va"], 16)
        memberships = []
        for pointer_array in pointer_arrays:
            entries = pointer_array.get("entries", [])
            for slot_index, entry in enumerate(entries):
                if int(entry["target_va"], 16) == function_va:
                    memberships.append({
                        "pointer_array_start_va": pointer_array.get("start_va"),
                        "slot_index": slot_index,
                        "entry_count": len(entries),
                        "status": pointer_array.get("status"),
                    })
        caller["code_pointer_array_memberships"] = memberships
        if memberships:
            matched.add(function_va)

    return {
        "available": True,
        "source": str(pointer_arrays_path),
        "matched_caller_functions": len(matched),
        "interpretation_limit": (
            "Membership proves only that a function address occurs in a relocated code-pointer sequence. "
            "The inventory does not classify the sequence as a C++ vtable or identify its runtime caller."
        ),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--index-db", type=Path, default=DEFAULT_INDEX)
    parser.add_argument("--table-root", type=Path, default=DEFAULT_TABLE_ROOT)
    parser.add_argument("--pointer-arrays", type=Path, default=DEFAULT_POINTER_ARRAYS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    db_uri = f"file:{args.index_db.resolve()}?mode=ro"
    conn = sqlite3.connect(db_uri, uri=True)
    calls, callers, unresolved = caller_groups(conn, TARGET)
    if not calls:
        raise SystemExit(f"no direct-call records for {TARGET:#x} in {args.index_db}")
    wrapper_calls, wrapper_callers, wrapper_unresolved = caller_groups(conn, REGISTRATION_WRAPPER)
    pointer_array_audit = pointer_array_matches(args.pointer_arrays, callers.values())

    result = {
        "schema": "acnh-re/catalog-registration-callers/1",
        "evidence_level": "STATIC_DIRECT_CALL_XREF_INDEX",
        "target_va": hex(TARGET),
        "direct_call_records": len(calls),
        "resolved_caller_functions": len(callers),
        "unresolved_call_sites": unresolved,
        "callers": sorted(callers.values(), key=lambda item: int(item["function_va"], 16)),
        "code_pointer_array_audit": pointer_array_audit,
        "registration_wrapper_trace": {
            "wrapper_va": hex(REGISTRATION_WRAPPER),
            "pseudocode": "binary/analysis_decomp/efe070.c",
            "wrapper_calls_registrar": True,
            "direct_call_records": len(wrapper_calls),
            "resolved_caller_functions": len(wrapper_callers),
            "unresolved_call_sites": wrapper_unresolved,
            "callers": sorted(wrapper_callers.values(), key=lambda item: int(item["function_va"], 16)),
            "interpretation_limit": "A purchase-counter string in a caller does not establish that this is specifically Nook Shopping or that it controls order eligibility/delivery.",
        },
        "itemkind_caller_crosswalk": table_crosswalk(args.table_root),
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
