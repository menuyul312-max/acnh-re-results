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
    item_kind_table = json.loads((args.output_root / "tables_resolved/ItemKind.json").read_text())
    item_remake_table = json.loads((args.output_root / "tables_resolved/ItemRemake.json").read_text())
    columns = {column["name"]: index for index, column in enumerate(table["columns"])}
    kind_columns = {column["name"]: index for index, column in enumerate(item_kind_table["columns"])}
    remake_columns = {column["name"]: index for index, column in enumerate(item_remake_table["columns"])}
    catalog_type = columns["ItemCatalogType"]
    item_kind = columns["ItemKind"]
    remake_id = columns["RemakeID"]
    counts = Counter()
    by_kind = defaultdict(Counter)
    remake_ids_by_type = defaultdict(set)
    nonnegative_by_type = Counter()
    item_remake_type_by_kind = {
        row[kind_columns["Label"]]: label(row[kind_columns["ItemRemakeType"]])
        for row in item_kind_table["rows"]
    }
    remake_by_id = {
        row[remake_columns["UniqueID"]]: row
        for row in item_remake_table["rows"]
    }
    remake_fanout = Counter()
    rows_by_remake_type = Counter()
    rows_by_remake_and_catalog_type = defaultdict(Counter)
    fabric_type_counts = Counter()
    item_unique_matches = 0
    item_unique_mismatches = Counter()
    missing_remake_rows = Counter()
    kind_join_misses = Counter()
    for row in table["rows"]:
        category = label(row[catalog_type])
        kind = label(row[item_kind])
        counts[category] += 1
        by_kind[category][kind] += 1
        remake = row[remake_id]
        if isinstance(remake, int) and remake >= 0:
            nonnegative_by_type[category] += 1
            remake_ids_by_type[category].add(remake)
            remake_fanout[remake] += 1
            remake_row = remake_by_id.get(remake)
            remake_type = item_remake_type_by_kind.get(label(row[item_kind]))
            if remake_type is None:
                kind_join_misses[kind] += 1
                remake_type = "<no ItemKind.Label join>"
            rows_by_remake_type[remake_type] += 1
            rows_by_remake_and_catalog_type[remake_type][category] += 1
            if remake_row is None:
                missing_remake_rows[remake] += 1
            else:
                fabric_type_counts[label(remake_row[remake_columns["ItemReFabricType"]])] += 1
                if remake_row[remake_columns["ItemUniqueID"]] == row[columns["UniqueID"]]:
                    item_unique_matches += 1
                else:
                    item_unique_mismatches[remake] += 1
    fanout_histogram = Counter(remake_fanout.values())
    mismatch_groups = []
    for rid, count in sorted(item_unique_mismatches.items()):
        rows = [row for row in table["rows"] if row[remake_id] == rid]
        remake_row = remake_by_id[rid]
        mismatch_groups.append({
            "remake_id": rid,
            "item_remake_item_unique_id": remake_row[remake_columns["ItemUniqueID"]],
            "mismatch_rows": count,
            "item_param_rows_for_remake_id": len(rows),
            "item_kinds": sorted({label(row[item_kind]) for row in rows}),
            "catalog_types": sorted({label(row[catalog_type]) for row in rows}),
            "interpretation": "shared RemakeID group; table join does not imply each row has a distinct ItemRemake record",
        })
    item_remake_crosswalk = {
        "evidence_level": "TABLE_JOIN_ONLY",
        "remake_id_join": "ItemParam.RemakeID == ItemRemake.UniqueID",
        "item_kind_join": "ItemParam.ItemKind label == ItemKind.Label; read ItemKind.ItemRemakeType",
        "item_param_rows_with_nonnegative_remake_id": sum(nonnegative_by_type.values()),
        "distinct_remake_ids": len(remake_fanout),
        "item_remake_rows": len(item_remake_table["rows"]),
        "item_param_rows_without_item_remake_row": sum(missing_remake_rows.values()),
        "item_kind_label_join_misses": dict(sorted(kind_join_misses.items())),
        "item_remake_type_counts": dict(sorted(rows_by_remake_type.items())),
        "item_catalog_type_by_item_remake_type": {
            key: dict(sorted(value.items()))
            for key, value in sorted(rows_by_remake_and_catalog_type.items())
        },
        "item_re_fabric_type_counts_across_joined_rows": dict(sorted(fabric_type_counts.items())),
        "item_unique_id_matches_to_item_remake": item_unique_matches,
        "item_unique_id_mismatch_rows": sum(item_unique_mismatches.values()),
        "item_unique_id_mismatch_groups": mismatch_groups,
        "remake_id_fanout_histogram": {str(key): value for key, value in sorted(fanout_histogram.items())},
        "interpretation_limit": "The tables show join structure and supported remake categories. They do not reveal which packed-item payload values are produced for each visible design/color or how registration is gated at runtime.",
    }
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
        "item_remake_crosswalk": item_remake_crosswalk,
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
