#!/usr/bin/env python3
"""Summarize ItemCatalogType and RemakeID metadata without inferring runtime behavior."""
import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT_ROOT = Path("/workspace/acnh-re/output")


def label(value):
    if isinstance(value, dict):
        values = value.get("labels")
        if values and values[0]:
            return values[0]
    return str(value)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    args = parser.parse_args()
    table = json.loads((args.output_root / "tables_resolved/ItemParam.json").read_text())
    columns = {column["name"]: index for index, column in enumerate(table["columns"])}
    catalog_type = columns["ItemCatalogType"]
    item_kind = columns["ItemKind"]
    remake_id = columns["RemakeID"]
    counts = Counter()
    by_kind = defaultdict(Counter)
    remake_ids_by_type = defaultdict(set)
    nonnegative_by_type = Counter()
    for row in table["rows"]:
        category = label(row[catalog_type])
        kind = label(row[item_kind])
        counts[category] += 1
        by_kind[category][kind] += 1
        remake = row[remake_id]
        if isinstance(remake, int) and remake >= 0:
            nonnegative_by_type[category] += 1
            remake_ids_by_type[category].add(remake)
    result = {
        "schema": "acnh-re/catalog-itemparam-table-audit/1",
        "evidence_level": "TABLE_METADATA_ONLY",
        "source": table["source"],
        "source_sha256": table["raw"]["sha256"],
        "rows": table["row_count"],
        "item_catalog_type_counts": dict(sorted(counts.items())),
        "rows_by_item_kind_and_catalog_type": {category: dict(sorted(values.items()))
                                              for category, values in sorted(by_kind.items())},
        "nonnegative_remake_id_rows_by_catalog_type": dict(sorted(nonnegative_by_type.items())),
        "unique_nonnegative_remake_ids_by_catalog_type": {
            category: len(values) for category, values in sorted(remake_ids_by_type.items())},
        "max_nonnegative_remake_id": max(
            (row[remake_id] for row in table["rows"]
             if isinstance(row[remake_id], int) and row[remake_id] >= 0), default=None),
        "interpretation_limit": "ItemCatalogType and RemakeID are table fields. Their values do not alone prove runtime registration, order availability, save bits, or UI visibility.",
    }
    output = ROOT / "output/gameplay/catalog_itemparam_table_audit.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({key: value for key, value in result.items()
                      if key != "rows_by_item_kind_and_catalog_type"}, indent=2))


if __name__ == "__main__":
    main()
