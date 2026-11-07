#!/usr/bin/env python3
"""Audit catalog variant selection, table candidates, and mail insertion boundaries.

The native index and resolved table JSON are read-only inputs.  The report is
written only to the requested output path.
"""

from __future__ import annotations

import argparse
import collections
import json
import sqlite3
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def hx(value: int | None) -> str | None:
    return None if value is None else f"0x{value:x}"


def label(value: Any) -> Any:
    if isinstance(value, dict):
        labels = value.get("labels")
        return labels[0] if labels else None
    return value


def load_table(root: Path, name: str) -> tuple[dict[str, Any], dict[str, int]]:
    data = json.loads((root / f"{name}.json").read_text(encoding="utf-8"))
    columns = {column["name"]: i for i, column in enumerate(data["columns"])
               if column.get("name")}
    return data, columns


def function_record(db: sqlite3.Connection, va: int) -> dict[str, Any]:
    row = db.execute(
        "select path,sha256 from decomp_new where va=?", (va,)
    ).fetchone()
    func = db.execute(
        "select ghidra_name,size from functions where va=?", (va,)
    ).fetchone()
    return {
        "va": hx(va),
        "name": func[0] if func else None,
        "size": func[1] if func else None,
        "decomp_path": row[0] if row else None,
        "decomp_sha256": row[1] if row else None,
    }


def direct_callers(db: sqlite3.Connection, target: int) -> list[dict[str, Any]]:
    rows = db.execute(
        "select owner_va,pc from direct_calls where target_va=? order by owner_va,pc",
        (target,),
    ).fetchall()
    result = []
    for owner, pc in rows:
        name = None
        if owner is not None:
            row = db.execute("select ghidra_name from functions where va=?", (owner,)).fetchone()
            name = row[0] if row else None
        result.append({"owner_va": hx(owner), "owner_name": name, "call_pc": hx(pc)})
    return result


def hash_references(db: sqlite3.Connection, hash_value: int) -> list[dict[str, Any]]:
    rows = db.execute(
        "select owner_va,pc from hash_refs where hash=? order by owner_va,pc",
        (hash_value,),
    ).fetchall()
    result = []
    for owner, pc in rows:
        row = db.execute("select ghidra_name from functions where va=?", (owner,)).fetchone()
        result.append({"owner_va": hx(owner), "owner_name": row[0] if row else None,
                       "pc": hx(pc)})
    return result


def source_record(db: sqlite3.Connection, source: str) -> dict[str, Any]:
    row = db.execute("select sha256,size from files where source=?", (source,)).fetchone()
    return {"source": source, "sha256": row[0] if row else None,
            "size": row[1] if row else None}


def item_fixtures(tables_root: Path) -> dict[str, Any]:
    item_param, pi = load_table(tables_root, "ItemParam")
    item_remake, ri = load_table(tables_root, "ItemRemake")
    item_kind, ki = load_table(tables_root, "ItemKind")

    remake_by_id = {int(row[ri["UniqueID"]]): row for row in item_remake["rows"]}
    kind_by_label = {label(row[ki["Label"]]): row for row in item_kind["rows"]}

    catalog_counts = collections.Counter()
    row_counts_by_type = collections.Counter()
    group_by_remake: dict[int, dict[str, Any]] = {}
    examples: list[dict[str, Any]] = []
    wanted_examples = [
        ("Sale", "Ftr"),
        ("NotForSale", "Ftr"),
        ("NotSee", "Bromide"),
        ("NotSee", "SmartPhone"),
    ]
    selected: set[tuple[str, str]] = set()

    for row in item_param["rows"]:
        catalog_type = label(row[pi["ItemCatalogType"]])
        item_kind_label = label(row[pi["ItemKind"]])
        catalog_counts[catalog_type] += 1
        remake_id = int(row[pi["RemakeID"]])
        if remake_id < 0:
            continue
        remake = remake_by_id.get(remake_id)
        if remake is None:
            continue
        remake_row = group_by_remake.setdefault(remake_id, {
            "item_catalog_type": catalog_type,
            "itemparam_rows": 0,
            "body_pattern_count": int(remake[ri["ReBodyPatternNum"]]),
            "fabric_pattern_count": int(remake[ri["ReFabricPatternNum"]]),
            "item_remake_item_unique_id": int(remake[ri["ItemUniqueID"]]),
        })
        remake_row["itemparam_rows"] += 1
        row_counts_by_type[catalog_type] += 1

        key = (catalog_type, item_kind_label)
        if key in wanted_examples and key not in selected:
            selected.add(key)
            kind_row = kind_by_label.get(item_kind_label)
            remake_type = label(kind_row[ki["ItemRemakeType"]]) if kind_row else None
            can_ftr = int(kind_row[ki["CanFtr"]]) if kind_row else None
            body_count = int(remake[ri["ReBodyPatternNum"]])
            ordinals = list(range(max(0, body_count)))
            bit_indices = None
            if remake_type == "Ftr" and can_ftr == 1:
                bit_indices = [remake_id * 8 + ordinal for ordinal in ordinals]
            examples.append({
                "item_catalog_type": catalog_type,
                "item_kind": item_kind_label,
                "item_remake_type": remake_type,
                "itemkind_can_ftr": can_ftr,
                "item_unique_id": int(row[pi["UniqueID"]]),
                "remake_id": remake_id,
                "item_remake_item_unique_id": int(remake[ri["ItemUniqueID"]]),
                "res_name": row[pi["ResName"]],
                "item_name": row[pi["ItemName"]],
                "body_pattern_count": body_count,
                "fabric_pattern_count": int(remake[ri["ReFabricPatternNum"]]),
                "candidate_ordinals": ordinals,
                "candidate_bit_indices_when_ftr_mapper_applies": bit_indices,
            })

    pattern_by_catalog_type: dict[str, collections.Counter[int]] = collections.defaultdict(collections.Counter)
    group_rows_by_type = collections.Counter()
    itemparam_rows_by_type = collections.Counter()
    for remake_id, values in group_by_remake.items():
        catalog_type = values["item_catalog_type"]
        pattern_by_catalog_type[catalog_type][values["body_pattern_count"]] += 1
        group_rows_by_type[catalog_type] += 1
        itemparam_rows_by_type[catalog_type] += values["itemparam_rows"]

    duplicate_remakes = []
    for remake_id, values in sorted(group_by_remake.items()):
        if values["itemparam_rows"] > 1:
            duplicate_remakes.append({"remake_id": remake_id, **values})

    all_body_counts = collections.Counter(
        int(row[ri["ReBodyPatternNum"]]) for row in item_remake["rows"]
    )
    body_minus_one_fabric_positive = sum(
        1 for row in item_remake["rows"]
        if int(row[ri["ReBodyPatternNum"]]) < 0 and int(row[ri["ReFabricPatternNum"]]) > 0
    )

    return {
        "source_tables": {
            "ItemParam": {"rows": item_param["row_count"], "source": item_param["source"],
                          "sha256": item_param["raw"].get("sha256")},
            "ItemRemake": {"rows": item_remake["row_count"], "source": item_remake["source"],
                           "sha256": item_remake["raw"].get("sha256")},
            "ItemKind": {"rows": item_kind["row_count"], "source": item_kind["source"],
                         "sha256": item_kind["raw"].get("sha256")},
        },
        "item_catalog_type_counts_all_itemparam_rows": dict(sorted(catalog_counts.items())),
        "itemparam_rows_with_nonnegative_remake_id_by_catalog_type": dict(sorted(row_counts_by_type.items())),
        "distinct_remake_ids_by_catalog_type": dict(sorted(group_rows_by_type.items())),
        "body_pattern_count_distribution_by_itemremake_row": {
            str(k): v for k, v in sorted(all_body_counts.items())
        },
        "body_pattern_count_distribution_by_catalog_type_distinct_remake_id": {
            catalog_type: {str(k): v for k, v in sorted(counter.items())}
            for catalog_type, counter in sorted(pattern_by_catalog_type.items())
        },
        "distinct_body_candidate_slots_by_catalog_type": {
            catalog_type: sum(max(0, count) * amount for count, amount in counter.items())
            for catalog_type, counter in sorted(pattern_by_catalog_type.items())
        },
        "distinct_body_candidate_slots_total": sum(
            max(0, values["body_pattern_count"]) for values in group_by_remake.values()
        ),
        "body_pattern_minus_one_rows_with_positive_fabric_pattern_count": body_minus_one_fabric_positive,
        "duplicate_remake_id_groups": duplicate_remakes,
        "fixtures": examples,
    }


def mail_evidence(db: sqlite3.Connection, catalog_audit_path: Path) -> dict[str, Any]:
    event_counts: dict[str, Any] = {}
    for action in ("EventFlowActionCatalogMailSend", "EventFlowActionSystemMailSend"):
        rows = db.execute(
            "select flow,event_index,params_json from event_calls where name=? order by flow,event_index",
            (action,),
        ).fetchall()
        route_counts: collections.Counter[str] = collections.Counter()
        for _flow, _index, params_json in rows:
            params = (json.loads(params_json) if params_json else None) or {}
            route_counts[params.get("Route", "<none>")] += 1
        event_counts[action] = {
            "uses": len(rows),
            "distinct_flows": len({row[0] for row in rows}),
            "routes": dict(sorted(route_counts.items())),
            "flow_event_pairs": [{"flow": row[0], "event_index": row[1]} for row in rows],
        }

    catalog_audit = {}
    if catalog_audit_path.is_file():
        catalog_audit = json.loads(catalog_audit_path.read_text(encoding="utf-8"))
    handler = catalog_audit.get("catalog_mail_send_handler", {})
    method_trace = catalog_audit.get("catalog_mail_send_static_method_trace", {})
    return {
        "event_action_inventory": event_counts,
        "catalog_mail_send_handler_audit": handler,
        "catalog_mail_send_static_method_audit": method_trace,
        "catalog_mail_send_insertion_boundary": {
            "function": "0xf62e90",
            "player_view_offset": "0x169d0",
            "view_size": "0x54a8",
            "next_helper": "0xf62c00",
            "count_member_offset_within_view": "0xe98",
            "record_array_offset_within_view": "0x2298",
            "record_stride": "0x18",
            "other_copy_helper": "0xf73ea0",
            "destination_view_size": "0x13418",
            "copy_note": "0xf73ea0 copies selected fields into the destination view; the 0x13418 value is the view size passed to its accessor, not bytes copied by that helper.",
            "evidence_limit": "Native mutation/copy boundary only; no proof of recipient inbox arrival or delivery time.",
        },
        "system_mail_send_static_insertion_trace": {
            "method": "0x345890",
            "record_builder": "0xac77a0",
            "route_mapper": "0x27ccd0",
            "dispatcher": "0x346a50",
            "routes": {
                "cFastToday": {"branch": "0xabf6a0 -> 0xac1eb0 -> virtual +0x30 / 0xac7070",
                               "mode": 1, "slot_writer": "0xfaabf0"},
                "cFastTomorrow": {"branch": "0xabf730 -> 0xac1eb0 -> virtual +0x30 / 0xac7070",
                                  "mode": 2, "slot_writer": "0xfaa3f0"},
                "cSlowRetry": {"branch": "0xabf740 -> 0xac1eb0 -> virtual +0x30 / 0xac7070",
                               "mode": 3, "fallback_writer": "0xfaaeb0",
                               "note": "The cNone path first tries the shared 0xac1ff0 handler."},
            },
            "evidence_limit": "Route handlers reach save-backed record collections; this does not prove mailbox visibility, receipt, or delivery timing.",
            "cross_reference": "acnh-re/docs/HOUSE_HHA_FOLLOWUP.md, SystemMailSend section",
        },
    }


def build_report(index_path: Path, tables_root: Path, catalog_audit_path: Path) -> dict[str, Any]:
    db = sqlite3.connect(f"file:{index_path}?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    try:
        targets = [0x11829D0, 0x118A3D0, 0x118A740, 0xEECC70,
                   0xA9C290, 0xAB2A50, 0xAAC250, 0xAABF10,
                   0xAB2940, 0xAB0F50, 0xAA84F0]
        app_path_owners = [0x11829D0, 0x118A3D0, 0x118A740, 0xEECC70,
                           0xA9C290, 0xAB2A50, 0xAAC250, 0xAABF10,
                           0xAB2940, 0xAB0F50, 0xAA84F0]
        item_catalog_type_hash = 0xDAF0238C
        expected_callers = {
            0x118A3D0: {0x11829D0},
            0x118A740: {0x118A3D0},
            0xEECC70: {0x1179DD0, 0x118A740, 0x1355440},
        }
        call_boundary = {}
        for target, expected in expected_callers.items():
            callers = direct_callers(db, target)
            actual = {int(row["owner_va"], 16) for row in callers if row["owner_va"]}
            call_boundary[hx(target)] = {
                "actual_callers": callers,
                "expected_callers_for_this_index_snapshot": [hx(value) for value in sorted(expected)],
                "matches_expected": actual == expected,
            }

        item_catalog_refs = hash_references(db, item_catalog_type_hash)
        app_refs = [row for row in item_catalog_refs
                    if int(row["owner_va"], 16) in set(app_path_owners)]
        source_names = [
            "B_data/Bcsv/ItemParam.bcsv",
            "B_data/Bcsv/ItemRemake.bcsv",
            "B_data/Bcsv/ItemKind.bcsv",
            "B_data/EventFlow/Obj_RcoMachine.bfevfl",
        ]
        return {
            "schema": "acnh-re/catalog-order-remainder/1",
            "evidence_level": "STATIC_NATIVE_INDEX_AND_RESOLVED_TABLE_JOIN",
            "scope": "Catalog app body-variant representative selection, ItemCatalogType/NotSee binding, and mail record insertion boundary.",
            "inputs": [source_record(db, source) for source in source_names],
            "native_functions": [function_record(db, va) for va in targets + [
                0xA25760, 0xEEC760, 0x33A570, 0xF62E90, 0xF62C00, 0xF73EA0,
                0x345890, 0xAC77A0, 0x27CCD0, 0x346A50, 0xABF6A0, 0xABF730,
                0xABF740, 0xAC1EB0, 0xFAABF0, 0xFAA3F0, 0xFAAEB0,
            ]],
            "direct_call_boundary_checks": call_boundary,
            "app_chain": {
                "input_list_caller": "0x11829d0 passes its caller-supplied list to 0x118a3d0.",
                "variant_resolution": [
                    "0x118a3d0 skips sentinel item records (short ID -2), validates each remaining record, then invokes 0x118a740.",
                    "0x118a740 asks 0xeecc70 for body-pattern candidates, in ascending ordinal order.",
                    "For each candidate, 0x118a740 copies it to its output, maps it with 0xab2940, and checks the page-associated 0x7d0-byte bit view with a 16,000-bit bound.",
                    "The first candidate whose mapped bit is set is retained as the representative. If none is set, the original input record is copied to the output.",
                    "This is a representative-variant lookup over the incoming list; it does not build the upstream category list itself.",
                ],
                "candidate_builder": {
                    "function": "0xeecc70",
                    "itemparam_key": {"field": "RemakeID", "hash": "0xcb5eb33f"},
                    "itemremake_join": "ItemParam.RemakeID == ItemRemake.UniqueID",
                    "pattern_count": {"field": "ReBodyPatternNum", "hash": "0xb0304b0d"},
                    "ordinal_range": "0 through ReBodyPatternNum - 1 when count is positive; no candidates when count <= 0.",
                    "mutation": "0xaabf10 writes the ordinal into the low three bits while preserving the upper bits of the packed short.",
                    "not_read_here": ["ItemCatalogType", "ReFabricPatternNum"],
                },
                "bit_mapping": {
                    "function": "0xab2940",
                    "expression": "RemakeID * 8 + low_three_bits_of_remake_payload_when_ItemKind_gate_exposes_it",
                    "app_page_bit_view_size": "0x7d0 bytes / 16,000 bits",
                },
                "shared_eecc70_callers": direct_callers(db, 0xEECC70),
            },
            "item_catalog_type_binding": {
                "field": "ItemParam.ItemCatalogType",
                "hash": "0xdaf0238c",
                "enum_values": {"0": "Sale", "1": "NotForSale", "2": "NotSee"},
                "native_field_hash_references": item_catalog_refs,
                "references_from_catalog_app_variant_chain": app_refs,
                "conclusion": "No direct ItemCatalogType field read or enum comparison appears in the indexed 0x118a3d0 -> 0x118a740 -> 0xeecc70 candidate-selection chain or its listed helpers. The upstream list passed by 0x11829d0 remains a separate, unresolved source boundary; the generic integer value 2 passed to a caller helper is not enough to bind it to ItemCatalogType=NotSee.",
                "separate_count_path": "0xeec760 is the FillCatalog achievement count path. Its selectors 0 and 1 correspond to Sale and NotForSale; this does not bind the catalog app's incoming list to those categories.",
            },
            "table_candidate_census": item_fixtures(tables_root),
            "mail_insertion_boundaries": mail_evidence(db, catalog_audit_path),
            "open_questions": [
                "Which native producer/category query populates the list passed from 0x11829d0, and whether that query excludes ItemCatalogType=NotSee.",
                "Which items are actually orderable, price/quantity limits, and whether the representative variant selected here affects a purchase payload.",
                "Save serialization and mailbox consumer/arrival timing for both CatalogMailSend and SystemMailSend.",
            ],
        }
    finally:
        db.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", type=Path, required=True, help="Read-only native analysis index.sqlite")
    parser.add_argument("--tables-root", type=Path, required=True, help="Directory containing resolved ItemParam/ItemRemake/ItemKind JSON")
    parser.add_argument("--catalog-audit", type=Path,
                        default=ROOT / "output/gameplay/catalog_order_flow_audit.json")
    parser.add_argument("--output", type=Path,
                        default=ROOT / "output/gameplay/catalog_order_remainder/catalog_order_remainder_static.json")
    args = parser.parse_args()

    report = build_report(args.index.resolve(), args.tables_root.resolve(), args.catalog_audit.resolve())
    failed = [target for target, result in report["direct_call_boundary_checks"].items()
              if not result["matches_expected"]]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {args.output}")
    print(f"candidate slots: {report['table_candidate_census']['distinct_body_candidate_slots_total']}")
    if failed:
        print("direct-call boundary mismatch: " + ", ".join(failed))
        return 1
    print("direct-call boundary checks: all match this index snapshot")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
