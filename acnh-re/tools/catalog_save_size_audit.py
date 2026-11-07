#!/usr/bin/env python3
"""Check whether catalog bitset view sizes identify a local save-layout node."""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_LAYOUT = ROOT / "output/gameplay/save_layout.json"
DEFAULT_CROSSWALK = ROOT / "output/gameplay/save_layout_external_crosswalk.json"
DEFAULT_KEYS = ROOT / "tools/external/CylindricalEarth/save_keys.json"
DEFAULT_ITEM_KIND = Path("/workspace/acnh-re/output/tables_resolved/ItemKind.json")
DEFAULT_OUTPUT = ROOT / "output/gameplay/catalog_save_size_audit.json"
REQUESTED_VIEW_BYTES = 2000
SHOP_SELECTOR_COUNTS = [(0, 2), (6, 2), (9, 1), (12, 1), (14, 1), (11, 1), (72, 1)]


def hex_int(value):
    return int(value, 16) if isinstance(value, str) else int(value)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--layout", type=Path, default=DEFAULT_LAYOUT)
    parser.add_argument("--crosswalk", type=Path, default=DEFAULT_CROSSWALK)
    parser.add_argument("--keys", type=Path, default=DEFAULT_KEYS)
    parser.add_argument("--item-kind", type=Path, default=DEFAULT_ITEM_KIND)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    layout = json.loads(args.layout.read_text())
    crosswalk = json.loads(args.crosswalk.read_text())
    keys = json.loads(args.keys.read_text())
    item_kind = json.loads(args.item_kind.read_text())
    item_kind_columns = {column["name"]: i for i, column in enumerate(item_kind["columns"])}
    members = layout.get("members", [])
    census = layout.get("type_census", [])
    exact_member_sizes = [
        {"node": row.get("node"), "data": row.get("data"), "size": row.get("size"),
         "name": row.get("name")}
        for row in members
        if hex_int(row.get("size", "0x0")) == REQUESTED_VIEW_BYTES
    ]
    exact_vtable_sizes = [
        {"vtable": row.get("vtable"), "size": row.get("size"),
         "sample_node": row.get("sample_node"), "sample_data": row.get("sample_data")}
        for row in census
        if hex_int(row.get("size", "0x0")) == REQUESTED_VIEW_BYTES
    ]

    named_type_matches = []
    for section in ("member_crosswalk", "vtable_crosswalk"):
        for row in crosswalk.get(section, []):
            if "SaveItemRemakeCollectBit" in json.dumps(row):
                named_type_matches.append({"section": section, **row})
    key_dictionary_hits = []
    for section, values in keys.items():
        if not isinstance(values, dict):
            continue
        for key_hash, name in values.items():
            if name in {"ItemRemakeCollectBit", "::Game::SaveItemRemakeCollectBit"}:
                key_dictionary_hits.append({"dictionary": section, "hash": key_hash, "name": name})

    shop_catalog_rows = []
    for section in ("member_crosswalk", "vtable_crosswalk"):
        for row in crosswalk.get(section, []):
            if "SaveShopCatalog" in json.dumps(row):
                shop_catalog_rows.append({"section": section, **row})

    shop_selector_crosswalk = []
    for row_index, count in SHOP_SELECTOR_COUNTS:
        row = item_kind["rows"][row_index]
        shop_selector_crosswalk.append({
            "selector_row_index": row_index,
            "count": count,
            "item_kind_label_candidate": row[item_kind_columns["Label"]],
            "item_kind_unique_id": row[item_kind_columns["UniqueID"]],
        })

    result = {
        "schema": "acnh-catalog-save-size-audit-v1",
        "evidence_level": "LAYOUT_SIZE_CROSSCHECK",
        "sources": {
            "native_save_layout": str(args.layout),
            "external_layout_crosswalk": str(args.crosswalk),
            "external_save_key_dictionary": str(args.keys),
            "catalog_setter_getter_view_length_bytes": REQUESTED_VIEW_BYTES,
            "catalog_setter_getter_view_length_hex": hex(REQUESTED_VIEW_BYTES),
        },
        "local_layout": {
            "selected_member_count": len(members),
            "unique_vtable_size_count": len(census),
            "exact_view_size_member_matches": exact_member_sizes,
            "exact_view_size_vtable_matches": exact_vtable_sizes,
        },
        "external_named_type_matches": named_type_matches,
        "external_save_key_dictionary_hits": key_dictionary_hits,
        "shop_catalog_crosswalk_rows": shop_catalog_rows,
        "shop_catalog_selector_crosswalk": {
            "evidence_level": "NATIVE_SELECTOR_VALUES_JOINED_TO_ITEMKIND_ROW_INDEX",
            "rows": shop_selector_crosswalk,
            "interpretation_limit": (
                "The native initializer passes these integer selector/count pairs to the "
                "shop-list builder. ItemKind row-index labels are candidate names; the "
                "builder's exact field binding and UI wording are not dynamically verified."
            ),
        },
        "interpretation": (
            "The native catalog accessor requests a 2,000-byte (0x7d0) view, but the "
            "selected local save members and complete local vtable-size census contain "
            "no exact 0x7d0-byte object. The external key dictionary names "
            "SaveItemRemakeCollectBit, but the available structural crosswalk does not "
            "bind that name to a local node. SaveShopCatalog candidates are retained "
            "separately and must not be conflated with this bitset view. This does not "
            "exclude a 0x7d0 slice within a larger serialized object or runtime manager."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({
        "output": str(args.output),
        "member_count": len(members),
        "unique_vtable_sizes": len(census),
        "exact_member_matches": len(exact_member_sizes),
        "exact_vtable_matches": len(exact_vtable_sizes),
        "save_item_remake_key_hits": len(key_dictionary_hits),
        "structural_name_matches": len(named_type_matches),
    }, indent=2))


if __name__ == "__main__":
    main()
