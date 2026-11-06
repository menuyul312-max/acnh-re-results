#!/usr/bin/env python3
"""Join the mailbox catalog BYML IDs to the local resolved ItemParam table."""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT_ROOT = Path("/workspace/acnh-re/output")
BYML_ID = 2281


def label(value):
    if isinstance(value, dict):
        values = value.get("labels")
        if values and values[0]:
            return values[0]
    return value


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    args = parser.parse_args()
    root = args.output_root
    byml = json.loads((root / "byml_resolved/02281.json").read_text())
    table = json.loads((root / "tables_resolved/ItemParam.json").read_text())
    columns = {column["name"]: index for index, column in enumerate(table["columns"])}
    unique_id_col = columns["UniqueID"]
    item_rows = {}
    for row_index, row in enumerate(table["rows"]):
        unique_id = row[unique_id_col]
        if isinstance(unique_id, int):
            item_rows.setdefault(unique_id, []).append((row_index, row))

    entries = byml["root"]["@MailboxCatalog[]"]
    joined = []
    missing = []
    for position, entry in enumerate(entries):
        unique_id = entry["@mUniqueID.u16"]
        matches = item_rows.get(unique_id, [])
        if len(matches) != 1:
            missing.append({"unique_id": unique_id, "matches": len(matches)})
            continue
        row_index, row = matches[0]
        joined.append({
            "position": position,
            "unique_id": unique_id,
            "item_param_row": row_index,
            "item_name_jp": row[columns["ItemName"]],
            "item_kind": label(row[columns["ItemKind"]]),
            "catalog_type": label(row[columns["ItemCatalogType"]]),
            "remake_id": row[columns["RemakeID"]],
        })
    if missing or len(joined) != len(entries) or len({x["unique_id"] for x in joined}) != len(joined):
        raise ValueError({"missing_or_ambiguous_unique_ids": missing})
    kind_counts = {}
    catalog_counts = {}
    for item in joined:
        kind_counts[item["item_kind"]] = kind_counts.get(item["item_kind"], 0) + 1
        catalog_counts[item["catalog_type"]] = catalog_counts.get(item["catalog_type"], 0) + 1
    result = {
        "schema": "acnh-re/catalog-mailbox-table-audit/1",
        "evidence_level": "TABLE_JOIN_ONLY",
        "byml_source": byml["source"],
        "byml_sha256": byml["source_sha256"],
        "item_param_source": table["source"],
        "item_param_sha256": table["raw"]["sha256"],
        "item_param_rows": table["row_count"],
        "catalog_entries": len(joined),
        "kind_counts": kind_counts,
        "item_catalog_type_counts": catalog_counts,
        "items": joined,
        "remaining": ["This list does not prove purchase eligibility, order placement, mail delivery, or save-state transitions."],
    }
    output = ROOT / "output/gameplay/mailbox_catalog_table_audit.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({key: value for key, value in result.items() if key != "items"}, indent=2))


if __name__ == "__main__":
    main()
