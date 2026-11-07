#!/usr/bin/env python3
"""Verify the catalog's ItemCatalogType=NotSee bitset gate and its limits.

Inputs are read-only game analysis products. The report is written under the
repository's output tree and records the exact binary callback reached through
the relocated code-pointer sequence.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import sqlite3
import struct
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RESEARCH = Path("/workspace/acnh-re/output")
DEFAULT_MAIN = Path("/workspace/downloads/ACNH_island_RE/ACNH_island_RE/A_logic/main.elf")
CALLBACK_VA = 0xA105D0
CALLBACK_SIZE = 60
CALLBACK_SEQUENCE_VA = 0x30C6398
UI_CATEGORY_CALLBACK_VA = 0xA10F00
UI_CATEGORY_VTABLE_VA = 0x30C6640
UI_CATEGORY_ENUM_NAME = "enum_3b7b05ca4a0a_52b2ca6f0581"
UI_CATEGORY_FIELD_HASH = 0x28297660


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def hx(value: int | None) -> str | None:
    return None if value is None else f"0x{value:x}"


def native_function(db: sqlite3.Connection, va: int) -> dict[str, Any]:
    row = db.execute(
        "select size,span_end_va,name,evidence from native_functions where va=?", (va,)
    ).fetchone()
    if row is None:
        return {"va": hx(va), "found": False}
    return {"va": hx(va), "size": row[0], "span_end_va": hx(row[1]),
            "name": row[2], "evidence": row[3]}


def direct_calls(db: sqlite3.Connection, owner: int) -> list[dict[str, Any]]:
    return [{"pc": hx(pc), "target_va": hx(target)} for pc, target in db.execute(
        "select pc,target_va from direct_calls where owner_va=? order by pc", (owner,)
    )]


def callers(db: sqlite3.Connection, target: int) -> list[dict[str, Any]]:
    return [{"owner_va": hx(owner), "pc": hx(pc)} for owner, pc in db.execute(
        "select owner_va,pc from direct_calls where target_va=? order by pc", (target,)
    )]


def sha_source(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"path": str(path), "available": False}
    data = path.read_bytes()
    return {"path": str(path), "available": True, "sha256": sha256(data), "bytes": len(data)}


def table_display(value: Any) -> Any:
    if isinstance(value, dict):
        labels = value.get("labels") or []
        return labels[0] if labels else None
    return value


def poster_item_crosswalk(tables_root: Path) -> dict[str, Any]:
    def read_table(name: str) -> tuple[dict[str, Any], dict[str, int]]:
        data = json.loads((tables_root / f"{name}.json").read_text(encoding="utf-8"))
        columns = {column["name"]: index for index, column in enumerate(data["columns"])
                   if column.get("name")}
        return data, columns

    item_param, ip = read_table("ItemParam")
    by_id = {int(row[ip["UniqueID"]]): row for row in item_param["rows"]}
    source_tables: dict[str, Any] = {}
    poster_ids: dict[int, list[str]] = {}
    categories: dict[str, int] = {}
    item_kinds: dict[str, int] = {}
    ui_categories: dict[str, int] = {}
    for table_name in ("NmlNpcParam", "SpNpcParam"):
        data, columns = read_table(table_name)
        poster_column = columns["PosterItemID"]
        valid = 0
        invalid = 0
        for row in data["rows"]:
            item_id = int(row[poster_column])
            if item_id < 0:
                invalid += 1
                continue
            valid += 1
            poster_ids.setdefault(item_id, []).append(table_name)
            item = by_id.get(item_id)
            if item is None:
                raise ValueError(f"{table_name}.PosterItemID {item_id} does not join to ItemParam")
            kind = str(table_display(item[ip["ItemKind"]]))
            catalog_type = str(table_display(item[ip["ItemCatalogType"]]))
            ui_category = str(table_display(item[ip["ItemUICategory"]]))
            item_kinds[kind] = item_kinds.get(kind, 0) + 1
            categories[catalog_type] = categories.get(catalog_type, 0) + 1
            ui_categories[ui_category] = ui_categories.get(ui_category, 0) + 1
        source_tables[table_name] = {"rows": len(data["rows"]), "valid_poster_ids": valid,
                                     "negative_poster_id_rows": invalid}
    if any(len(tables) != 1 for tables in poster_ids.values()):
        raise ValueError("normal/special NPC tables unexpectedly share a PosterItemID")
    if set(item_kinds) != {"Poster"} or set(categories) != {"Sale"}:
        raise ValueError(f"unexpected poster ItemParam categories: {item_kinds}, {categories}")
    special = by_id.get(0x29F5)
    if special is None:
        raise ValueError("state-flag PosterItemID 0x29f5 is missing from ItemParam")
    special_kind = table_display(special[ip["ItemKind"]])
    special_catalog_type = table_display(special[ip["ItemCatalogType"]])
    special_ui_category = table_display(special[ip["ItemUICategory"]])
    if special_kind != "Poster" or special_catalog_type != "Sale" or special_ui_category != "Wall":
        raise ValueError(f"unexpected special poster category: {special_kind}, {special_catalog_type}")
    if set(ui_categories) != {"Wall"}:
        raise ValueError(f"unexpected poster ItemUICategory values: {ui_categories}")
    return {
        "source_tables": source_tables,
        "unique_poster_item_ids": len(poster_ids),
        "joined_item_kind_counts": item_kinds,
        "joined_item_catalog_type_counts": categories,
        "joined_item_ui_category_counts": ui_categories,
        "state_flag_addition": {"unique_id": "0x29f5", "item_kind": special_kind,
                                "item_catalog_type": special_catalog_type,
                                "item_ui_category": special_ui_category},
        "limitation": "This table join identifies eligible PosterItemID values. Runtime collection predicates determine which rows are added in a particular page state.",
    }


def item_ui_category_ordinal_map(tables_root: Path, specs_path: Path) -> dict[str, Any]:
    item_param = json.loads((tables_root / "ItemParam.json").read_text(encoding="utf-8"))
    column = next((column for column in item_param["columns"]
                   if column.get("name") == "ItemUICategory"), None)
    if column is None or int(column.get("hash", "0"), 16) != UI_CATEGORY_FIELD_HASH:
        raise ValueError("ItemParam.ItemUICategory schema/hash is missing or changed")
    source = specs_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(specs_path))
    enum_value = None
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
                isinstance(target, ast.Name) and target.id == UI_CATEGORY_ENUM_NAME
                for target in node.targets):
            enum_value = ast.literal_eval(node.value)
            break
    if enum_value is None:
        raise ValueError(f"schema enum {UI_CATEGORY_ENUM_NAME} is missing from reference specs")
    labels = [entry[0] for entry in enum_value]
    required = [(0, "None"), (13, "Unnecessary"), (10, "Tool")]
    if len(labels) != 15 or any(labels[ordinal] != label for ordinal, label in required):
        raise ValueError(f"unexpected ItemUICategory enum order: {labels}")
    enum_hashes = column.get("enum_values") or {}
    selectors = []
    for ordinal, label in required:
        matches = [(enum_hash, value[0] if value else None)
                   for enum_hash, value in enum_hashes.items()
                   if (value[0] if value else None) == label]
        if len(matches) != 1:
            raise ValueError(f"ItemUICategory label {label} is not unique in resolved schema")
        enum_hash, _ = matches[0]
        selectors.append({"ordinal": ordinal, "label": label,
                          "enum_hash": f"0x{enum_hash}"})
    return {
        "field": "ItemParam.ItemUICategory",
        "field_hash": hx(UI_CATEGORY_FIELD_HASH),
        "cache_writer": "0xa25010 reads hash 0x28297660 into cache 0x33f0a48; values above 14 normalize to 0.",
        "cache_predicate": "0xa10f00 resolves the item with 0xa9c290 and calls 0xaad2e0, which compares the cached ItemUICategory ordinal to the closure selector.",
        "enum_order": labels,
        "enum_order_source": {"path": str(specs_path), "sha256": sha256(source.encode("utf-8")),
                              "enum_name": UI_CATEGORY_ENUM_NAME},
        "excluded_ordinals": selectors,
    }


def item_kind_ordinal_crosswalk(tables_root: Path) -> dict[str, Any]:
    data = json.loads((tables_root / "ItemKind.json").read_text(encoding="utf-8"))
    columns = {column["name"]: index for index, column in enumerate(data["columns"])
               if column.get("name")}
    if "Label" not in columns or len(data["rows"]) <= 92:
        raise ValueError("resolved ItemKind table is missing the expected ordinal rows")
    labels = [table_display(row[columns["Label"]]) for row in data["rows"]]
    expected = {13: "Helmet", 65: "Fish", 66: "ShellDrift", 70: "Fossil",
                92: "BdayCupcake"}
    if any(labels[ordinal] != label for ordinal, label in expected.items()):
        raise ValueError(f"unexpected ItemKind ordinal labels: {expected}")
    return {
        "table": "ItemKind",
        "row_count": len(labels),
        "selector_0_values": [{"ordinal": ordinal, "label": labels[ordinal]}
                               for ordinal in (13, 92)],
        "crosscaller_checks": [
            {"function": "0x11fc680", "native_compare": "0x46", "ordinal": 70,
             "item_kind_label": labels[70]},
            {"function": "0x12efd60", "native_compares": ["0x41", "0x42"],
             "ordinals": [65, 66], "item_kind_labels": [labels[65], labels[66]]},
        ],
        "interpretation": "The 0x1345180 return value is consistent with an ItemKind ordinal: other callers compare 0x41/0x42/0x46, which join to Fish/ShellDrift/Fossil. The selector-0 values therefore map to Helmet (13) and BdayCupcake (92); the local class-field name for the +0x268 source is still unavailable.",
    }


def selector4_shop_catalog_source(save_layout_path: Path, save_keys_path: Path,
                                 tables_root: Path) -> dict[str, Any]:
    layout = json.loads(save_layout_path.read_text(encoding="utf-8"))
    members = layout.get("members", [])
    member = next((item for item in members if item.get("node") == "0x2092f8"), None)
    if member is None or member.get("data") != "0x4117fc" or member.get("size") != "0x200":
        raise ValueError("save-layout node 0x2092f8 no longer identifies the 64-entry shop list")
    parent = next((item for item in members if item.get("node") == member.get("parent")), None)
    if parent is None or parent.get("data") != "0x40ece8":
        raise ValueError("shop catalog node parent no longer matches the resolved shop block")
    save_keys = json.loads(save_keys_path.read_text(encoding="utf-8"))
    field_keys = [key for key, value in save_keys.get("f", {}).items()
                  if value == "ShopCatalog"]
    type_keys = [key for key, value in save_keys.get("t", {}).items()
                 if value == "::Game::SaveShopCatalog"]
    if field_keys != ["09ee4739"] or type_keys != ["bd29175c"]:
        raise ValueError(f"unexpected external SaveShopCatalog keys: {field_keys}, {type_keys}")
    if not str(member.get("name", "")).startswith("64-item list"):
        raise ValueError("shop catalog save-layout annotation is missing")
    item_param = json.loads((tables_root / "ItemParam.json").read_text(encoding="utf-8"))
    columns = {column["name"]: index for index, column in enumerate(item_param["columns"])
               if column.get("name")}
    for name in ("ItemKind", "ItemCatalogType", "ItemUICategory", "UniqueID", "Label"):
        if name not in columns:
            raise ValueError(f"ItemParam.{name} is missing from resolved schema")
    requested_kinds = [
        {"ordinal": 0, "label": "Ftr", "count": 2},
        {"ordinal": 6, "label": "Tops", "count": 2},
        {"ordinal": 9, "label": "Bottoms", "count": 1},
        {"ordinal": 12, "label": "Cap", "count": 1},
        {"ordinal": 14, "label": "Accessory", "count": 1},
        {"ordinal": 11, "label": "Shoes", "count": 1},
        {"ordinal": 72, "label": "Music", "count": 1},
    ]
    requested_labels = {row["label"] for row in requested_kinds}
    catalog_type_counts: dict[str, dict[str, int]] = {
        row["label"]: {} for row in requested_kinds
    }
    notsee_candidates = []
    for row in item_param["rows"]:
        item_kind = table_display(row[columns["ItemKind"]])
        if item_kind not in requested_labels:
            continue
        catalog_type = str(table_display(row[columns["ItemCatalogType"]]))
        counts = catalog_type_counts[item_kind]
        counts[catalog_type] = counts.get(catalog_type, 0) + 1
        if catalog_type == "NotSee":
            notsee_candidates.append({
                "unique_id": row[columns["UniqueID"]],
                "item_kind": item_kind,
                "label": table_display(row[columns["Label"]]),
                "item_ui_category": table_display(row[columns["ItemUICategory"]]),
            })
    if len(notsee_candidates) != 7:
        raise ValueError(f"expected seven NotSee rows in requested ItemKind domains, got {len(notsee_candidates)}")
    return {
        "native_source": {
            "function": "0x11829d0",
            "save_manager_accessor": "0xeecf00",
            "member_offset": "0x2092f8",
            "record_count": 64,
            "record_stride": 8,
            "record_item_id": "signed 16-bit ID at record offset 0; -2 records are skipped",
            "consumer": "The selector-4 loop validates each record with 0x1058d00 and appends valid IDs to its candidate bitmap.",
        },
        "local_save_layout": {
            "path": str(save_layout_path),
            "node": member["node"],
            "data_offset": member["data"],
            "size": member["size"],
            "parent_node": parent["node"],
            "parent_data_offset": parent["data"],
            "parent_size": parent.get("size"),
            "annotation": member["name"],
        },
        "external_schema_crosswalk": {
            "path": str(save_keys_path),
            "field_key": field_keys[0],
            "field_name": "ShopCatalog",
            "type_key": type_keys[0],
            "type_name": "::Game::SaveShopCatalog",
        },
        "population": {
            "builder": "0xfc6300 -> 0xfc5d60",
            "item_kind_ordinals_and_requested_counts": requested_kinds,
            "itemparam_catalog_type_counts_by_requested_kind": catalog_type_counts,
            "notsee_rows_in_requested_item_kind_domains": notsee_candidates,
            "shop_filter_chain": {
                "native_observation": "0xfc5d60 passes selector 1 to 0xfc5fd0, then applies additional selection helpers before adding records; the selector-1 predicate's ItemParam field binding and the extra helper semantics are unresolved.",
                "limitation": "The seven NotSee rows are table candidates in the requested ItemKind domains, not proof that any is selected into a daily shop list. These entries are appended after selector 4's explicit NotSee bitmap filter, so the saved records and their full NotSee exclusion must be established from the runtime selection predicates or controlled state.",
            },
        },
    }


def verified_source(decomp_root: Path, va: int, required: tuple[str, ...]) -> tuple[str, dict[str, Any]]:
    record = sha_source(decomp_root / f"{va:x}.c")
    if not record["available"]:
        raise FileNotFoundError(record["path"])
    source = Path(record["path"]).read_text(encoding="utf-8")
    missing = [fragment for fragment in required if fragment not in source]
    if missing:
        raise ValueError(f"source anchors missing for {va:#x}: {missing}")
    return source, record


def elf_function_bytes(elf_path: Path, va: int, size: int) -> tuple[bytes, str]:
    data = elf_path.read_bytes()
    if data[:4] != b"\x7fELF" or data[4] != 2 or data[5] != 1:
        raise ValueError(f"expected little-endian ELF64: {elf_path}")
    phoff = struct.unpack_from("<Q", data, 0x20)[0]
    phentsize = struct.unpack_from("<H", data, 0x36)[0]
    phnum = struct.unpack_from("<H", data, 0x38)[0]
    file_offset = None
    for index in range(phnum):
        p_type, _flags, p_offset, p_vaddr, _paddr, p_filesz, _memsz, _align = struct.unpack_from(
            "<IIQQQQQQ", data, phoff + index * phentsize
        )
        if p_type == 1 and p_vaddr <= va and va + size <= p_vaddr + p_filesz:
            file_offset = p_offset + va - p_vaddr
            break
    if file_offset is None:
        raise ValueError(f"function {va:#x} is not contained in a file-backed PT_LOAD segment")
    return data[file_offset:file_offset + size], sha256(data)


def disassemble_aarch64(code: bytes, va: int) -> list[dict[str, Any]]:
    try:
        from capstone import CS_ARCH_ARM64, CS_MODE_ARM, Cs
    except ImportError as error:
        raise RuntimeError("Capstone is required; add the research .deps directory to PYTHONPATH") from error
    decoder = Cs(CS_ARCH_ARM64, CS_MODE_ARM)
    return [{"va": hx(ins.address), "mnemonic": ins.mnemonic, "operands": ins.op_str}
            for ins in decoder.disasm(code, va)]


def build(index: Path, code_pointer_arrays: Path, decomp_root: Path, main_elf: Path,
          tables_root: Path, save_layout_path: Path, save_keys_path: Path) -> dict[str, Any]:
    db = sqlite3.connect(f"file:{index}?mode=ro", uri=True)
    try:
        pointer_arrays = json.loads(code_pointer_arrays.read_text(encoding="utf-8"))
        sequence = next((item for item in pointer_arrays
                         if int(item["start_va"], 16) == CALLBACK_SEQUENCE_VA), None)
        if sequence is None:
            raise ValueError(f"code pointer sequence {CALLBACK_SEQUENCE_VA:#x} missing")
        callback_entry = next((entry for entry in sequence["entries"]
                              if int(entry["pointer_va"], 16) == CALLBACK_SEQUENCE_VA), None)
        if callback_entry is None or int(callback_entry["target_va"], 16) != CALLBACK_VA:
            raise ValueError("callback sequence no longer maps its first entry to 0xa105d0")

        ui_category_sequence = next((item for item in pointer_arrays
                                     if int(item["start_va"], 16) == UI_CATEGORY_VTABLE_VA), None)
        if ui_category_sequence is None:
            raise ValueError(f"ItemUICategory callback sequence {UI_CATEGORY_VTABLE_VA:#x} missing")
        ui_category_entry = next((entry for entry in ui_category_sequence["entries"]
                                  if int(entry["pointer_va"], 16) == UI_CATEGORY_VTABLE_VA), None)
        if (ui_category_entry is None
                or int(ui_category_entry["target_va"], 16) != UI_CATEGORY_CALLBACK_VA):
            raise ValueError("ItemUICategory callback sequence no longer maps to 0xa10f00")

        dynamic_filter_vtable_va = 0x30CEFF8
        dynamic_filter_va = 0xB2EED0
        dynamic_filter_sequence = next((item for item in pointer_arrays
                                        if int(item["start_va"], 16) == dynamic_filter_vtable_va), None)
        if dynamic_filter_sequence is None:
            raise ValueError(f"selector-4 dynamic filter sequence {dynamic_filter_vtable_va:#x} missing")
        dynamic_filter_entry = next((entry for entry in dynamic_filter_sequence["entries"]
                                     if int(entry["pointer_va"], 16) == dynamic_filter_vtable_va), None)
        if (dynamic_filter_entry is None
                or int(dynamic_filter_entry["target_va"], 16) != dynamic_filter_va):
            raise ValueError("selector-4 dynamic filter sequence no longer maps to 0xb2eed0")

        callback_meta = native_function(db, CALLBACK_VA)
        if callback_meta.get("size") != CALLBACK_SIZE:
            raise ValueError(f"unexpected callback function size: {callback_meta}")
        callback_bytes, elf_sha = elf_function_bytes(main_elf, CALLBACK_VA, CALLBACK_SIZE)
        elf_manifest_path = index.parent / "binary/elf.json"
        elf_manifest = json.loads(elf_manifest_path.read_text(encoding="utf-8"))
        if elf_sha != elf_manifest["sha256"]:
            raise ValueError(f"main ELF does not match indexed binary manifest: {elf_sha}")
        instructions = disassemble_aarch64(callback_bytes, CALLBACK_VA)
        targets = [ins["operands"] for ins in instructions if ins["mnemonic"] == "bl"]
        if targets != ["#0xa9c290", "#0xab3160"]:
            raise ValueError(f"unexpected predicate call chain: {targets}")

        selector_helpers = {}
        for va in (0x1188CC0, 0x1188FE0, 0x11896D0):
            meta = native_function(db, va)
            code, helper_elf_sha = elf_function_bytes(main_elf, va, meta["size"])
            if helper_elf_sha != elf_sha:
                raise ValueError("selector helper was read from a different ELF build")
            helper_instructions = disassemble_aarch64(code, va)
            bit_clear = [ins for ins in helper_instructions
                         if ins["mnemonic"] == "bic" and ins["operands"] == "w9, w9, w23"]
            bit_store = [ins for ins in helper_instructions
                         if ins["mnemonic"] == "str" and ins["operands"] == "w9, [x0, x8]"]
            bitmap_stores = [ins for ins in helper_instructions
                             if ins["mnemonic"] in {"str", "stur"} and "[x0" in ins["operands"]]
            if (not bit_clear or len(bit_clear) != len(bit_store)
                    or len(bitmap_stores) != len(bit_store)
                    or not any(ins["mnemonic"] == "mov" and ins["operands"] == "w22, #0x3a98"
                               for ins in helper_instructions)):
                raise ValueError(f"selector helper {va:#x} no longer has matched clear-only bit stores")
            selector_helpers[hx(va)] = {
                "function": meta,
                "function_bytes_sha256": sha256(code),
                "bitmap_write_sites": [
                    {"clear_pc": clear["va"], "store_pc": store["va"],
                     "operation": "bitmap_word &= ~candidate_bit"}
                    for clear, store in zip(bit_clear, bit_store)
                ],
                "other_direct_calls": [ins["operands"] for ins in helper_instructions
                                       if ins["mnemonic"] == "bl"],
                "result": "The helper's explicit bitmap write sites clear matched bits; they do not set bitmap bits.",
            }

        ui_category_meta = native_function(db, UI_CATEGORY_CALLBACK_VA)
        if ui_category_meta.get("size") != CALLBACK_SIZE:
            raise ValueError(f"unexpected ItemUICategory callback function size: {ui_category_meta}")
        ui_category_bytes, ui_category_elf_sha = elf_function_bytes(
            main_elf, UI_CATEGORY_CALLBACK_VA, ui_category_meta["size"])
        if ui_category_elf_sha != elf_sha:
            raise ValueError("ItemUICategory callback was read from a different ELF build")
        ui_category_instructions = disassemble_aarch64(ui_category_bytes, UI_CATEGORY_CALLBACK_VA)
        ui_category_targets = [ins["operands"] for ins in ui_category_instructions
                               if ins["mnemonic"] == "bl"]
        if ui_category_targets != ["#0xa9c290", "#0xaad2e0"]:
            raise ValueError(f"unexpected ItemUICategory callback chain: {ui_category_targets}")

        selector4_filter_meta = native_function(db, 0xB2ECC0)
        selector4_filter_bytes, selector4_filter_elf_sha = elf_function_bytes(
            main_elf, 0xB2ECC0, selector4_filter_meta["size"])
        if selector4_filter_elf_sha != elf_sha:
            raise ValueError("selector-4 post-mask filter was read from a different ELF build")
        selector4_filter_instructions = disassemble_aarch64(selector4_filter_bytes, 0xB2ECC0)
        dynamic_filter_clear = [ins for ins in selector4_filter_instructions
                                if ins["mnemonic"] == "bic"
                                and ins["operands"] == "w9, w9, w23"]
        dynamic_filter_stores = [ins for ins in selector4_filter_instructions
                                 if ins["mnemonic"] == "str"
                                 and ins["operands"] == "w9, [x0, x8]"]
        if (len(dynamic_filter_clear) != 1 or len(dynamic_filter_stores) != 1
                or not any(ins["mnemonic"] == "blr" and ins["operands"] == "x8"
                           for ins in selector4_filter_instructions)):
            raise ValueError("selector-4 trailing filter no longer has its expected clear-only callback path")

        producer_meta = native_function(db, 0x11829D0)
        producer_bytes, producer_elf_sha = elf_function_bytes(
            main_elf, 0x11829D0, producer_meta["size"])
        if producer_elf_sha != elf_sha:
            raise ValueError("catalog producer was read from a different ELF build")
        producer_instructions = disassemble_aarch64(producer_bytes, 0x11829D0)
        notsee_call_pcs = [ins["va"] for ins in producer_instructions
                           if ins["mnemonic"] == "bl" and ins["operands"] == "#0x293cd0"]
        if notsee_call_pcs != ["0x1182a80", "0x1182b28"]:
            raise ValueError(f"unexpected catalog producer NotSee call sites: {notsee_call_pcs}")
        producer_by_va = {ins["va"]: (ins["mnemonic"], ins["operands"])
                          for ins in producer_instructions}
        shop_catalog_signature = {
            "0x1182b2c": ("bl", "#0xeecf00"),
            "0x1182b34": ("mov", "w8, #0x92f8"),
            "0x1182b38": ("movk", "w8, #0x20, lsl #16"),
            "0x1182b3c": ("add", "x1, x0, x8"),
            "0x1182b60": ("mov", "x22, xzr"),
            "0x1182ba0": ("cmp", "w8, #0x40"),
        }
        if any(producer_by_va.get(pc) != expected
               for pc, expected in shop_catalog_signature.items()):
            raise ValueError("selector-4 shop-catalog access signature changed")
        shop_catalog_source = selector4_shop_catalog_source(save_layout_path, save_keys_path,
                                                            tables_root)
        selector0_jump_table_va = 0x29FDC0D
        selector0_table_bytes, selector0_elf_sha = elf_function_bytes(
            main_elf, selector0_jump_table_va, 4)
        if selector0_elf_sha != elf_sha or list(selector0_table_bytes) != [0, 0xC7, 0xC9, 0xCB]:
            raise ValueError("selector-0 branch table bytes changed from the audited ELF")

        hash_refs = [{"pc": hx(pc), "owner_va": hx(owner)} for pc, owner in db.execute(
            "select pc,owner_va from hash_refs where hash=? order by pc", (0xDAF0238C,)
        )]
        type_refs = [reference for reference in hash_refs if reference["owner_va"] == hx(0xA25760)]
        if not type_refs:
            raise ValueError("ItemCatalogType field hash is no longer read in 0xa25760")

        source_requirements = {
            0x11829D0: ("if (uVar8 - 1 < 3)", "CONCAT44(uStack_1678._4_4_,2)",
                        "FUN_00393cd0", "if (uVar8 != 4)", "FUN_01289c70"),
            0x293CD0: ("FUN_00b0fdc0", "uVar6 == 15000", "apuStack_68[0]",
                       "uVar1 ^ 0xffffffff"),
            0xA0FDC0: ("*param_1 = 0x31c6398", "*(undefined4 *)(param_1 + 1) = uVar1"),
            0xAB3160: ("uVar3 = 2", "return uVar3 == param_2"),
            0xA25760: ("0xdaf0238c", "puRam00000000033f0a90"),
            0x118A2E0: ("FUN_01288cc0", "FUN_01288fe0", "FUN_012896d0"),
            0x1189C70: ("FUN_00b0f510", "0x35e04"),
            0xC90E90: ("0x2f1b930d",),
            0xC90D30: ("0x2f1b930d",),
            0xFD2D50: ("0x3ce2e8d8",),
            0xD40D20: ("0xf640691",),
            0xA25010: ("0x28297660", "puRam00000000033f0a48"),
            0xAAD2E0: ("puRam00000000033f0a48", "uVar3 == param_2"),
            0x1AF3A0: ("uVar6 == 15000", "1 << (ulong)(uVar6 & 0x1f)"),
            0xB2ECC0: ("0x31ceff8", "FUN_01058d00", "uVar6 == 15000"),
            0xB2EED0: ("FUN_00c31070", "FUN_00c2e810"),
            0x1345180: ("param_1 + 0x30", "lVar1 + 0x268"),
            0x11FC680: ("FUN_01445180", "iVar1 == 0x46"),
            0x12EFD60: ("FUN_01445180", "aiStack_60[0] == 0x42", "aiStack_60[0] == 0x41"),
        }
        source_files = {}
        for va, fragments in source_requirements.items():
            _source, source_files[hx(va)] = verified_source(decomp_root, va, fragments)
        for va in (0xA105D0, 0xA9C290, 0xA10F00, 0xAAD2E0,
                   0x1189E80, 0x11433D0):
            source_files[hx(va)] = sha_source(decomp_root / f"{va:x}.c")

        ui_category_ordinals = item_ui_category_ordinal_map(
            tables_root, ROOT / "tools/external/CylindricalEarth/specs_100.py")
        item_kind_ordinals = item_kind_ordinal_crosswalk(tables_root)
        hash_ui_category = [{"pc": hx(pc), "owner_va": hx(owner)} for pc, owner in db.execute(
            "select pc,owner_va from hash_refs where hash=? order by pc", (UI_CATEGORY_FIELD_HASH,)
        )]
        if not any(reference["owner_va"] == hx(0xA25010) for reference in hash_ui_category):
            raise ValueError("ItemUICategory field hash is no longer referenced in 0xa25010")

        return {
            "schema": "acnh-re/catalog-notsee-gate/1",
            "evidence_level": "NATIVE_INDEX_PLUS_RELOCATED_POINTER_AND_ELF_DISASSEMBLY",
            "input_build_sha256": elf_sha,
            "inputs": {
                "index": str(index),
                "code_pointer_arrays": str(code_pointer_arrays),
                "code_pointer_arrays_sha256": sha256(code_pointer_arrays.read_bytes()),
                "main_elf": str(main_elf),
                "elf_manifest": str(elf_manifest_path),
                "elf_manifest_sha256": elf_manifest["sha256"],
                "decomp_root": str(decomp_root),
                "tables_root": str(tables_root),
                "callback_bytes_sha256": sha256(callback_bytes),
            },
            "item_catalog_type": {
                "field_hash": "0xdaf0238c",
                "enum": {"0": "Sale", "1": "NotForSale", "2": "NotSee"},
                "field_read": "0xa25760 materializes the ItemCatalogType field into a cache; 0xab3160 reads the cached value.",
                "field_hash_references": hash_refs,
                "cache_writer": native_function(db, 0xA25760),
                "cache_reader": native_function(db, 0xAB3160),
                "cache_wrapper_resolver": native_function(db, 0xA9C290),
            },
            "item_ui_category": {
                **ui_category_ordinals,
                "field_hash_references": hash_ui_category,
                "cache_writer": native_function(db, 0xA25010),
                "cache_reader": native_function(db, 0xAAD2E0),
                "cache_wrapper_resolver": native_function(db, 0xA9C290),
                "callback_sequence": {
                    "start_va": hx(UI_CATEGORY_VTABLE_VA),
                    "status": ui_category_sequence.get("status"),
                    "entries": ui_category_sequence["entries"],
                    "callback_va": hx(UI_CATEGORY_CALLBACK_VA),
                    "callback_function": ui_category_meta,
                    "callback_bytes_sha256": sha256(ui_category_bytes),
                    "callback_disassembly": disassemble_aarch64(ui_category_bytes,
                                                                 UI_CATEGORY_CALLBACK_VA),
                },
            },
            "predicate": {
                "filter": "0x293cd0",
                "callback_constructor": "0xa0fdc0 stores code-pointer sequence 0x31c6398 and copies the requested selector into closure context.",
                "relocated_callback_sequence": {
                    "start_va": hx(CALLBACK_SEQUENCE_VA),
                    "status": sequence.get("status"),
                    "entries": sequence["entries"],
                    "callback_va": hx(CALLBACK_VA),
                },
                "callback_function": callback_meta,
                "callback_disassembly": instructions,
                "callback_semantics": "Resolves the candidate item with 0xa9c290, passes the candidate wrapper and closure selector to 0xab3160, and returns its boolean result.",
                "comparison_semantics": "0xab3160 compares the cached ItemCatalogType value with the closure selector. It normalizes cached values above 2 to 0; an unresolved wrapper defaults to value 2.",
            },
            "producer_gate": {
                "selector_field": "object + 0x568a4",
                "category_filter_value": 2,
                "selector_branches": {
                    "1_to_3": "0x11829d0 calls the 0x293cd0 filter with literal 2, then dispatches through 0x118a2e0 before building the final list.",
                    "4": "0x11829d0 also calls the same filter with literal 2; afterward it adds up to 64 stored entries and calls 0x1189c70 to collect additional runtime entries.",
                    "0": "The selector-0 branch does not call the 0x293cd0 NotSee gate or run selector-4's UI-category mask. Its separate branch probes a selected record, then conditionally adds the PosterItemID collection or up to 64 records; source values and final composition are still unresolved.",
                },
                "bitset_filter": {
                    "function": "0x293cd0",
                    "range": "indices 0..14999",
                    "behavior": "For each set bit, an invalid item handle is cleared. Otherwise the callback is evaluated and the bit is cleared when the candidate ItemCatalogType equals selector 2.",
                    "callers": callers(db, 0x293CD0),
                    "catalog_call_sites": ["0x1182a80", "0x1182b28"],
                    "constructor_call_site": "0x293cf4",
                },
                "post_filter_routes": {
                    "selectors_1_to_3": {
                        "dispatcher": "0x118a2e0",
                        "specialized_helpers": ["0x1188cc0", "0x1188fe0", "0x11896d0"],
                        "disassembly_audit": selector_helpers,
                        "result": "Each specialized helper scans the existing 15,000-bit set and its explicit bitmap writes only clear bits. The common tail enumerates that set into item records, then resolves variants; it does not add new base item IDs. Thus selectors 1–3 retain the NotSee exclusion through final list construction.",
                    },
                    "selector_4": {
                        "additional_item_scan": "0x40 records are checked and accepted entries are added to the bitset after the category-2 filter.",
                        "saved_shop_catalog_source": shop_catalog_source,
                        "runtime_collection": "0x1189c70 resolves Label keys against normal/special NPC parameter collections and reads PosterItemID (field hash 0xf640691); a state-flag branch adds UniqueID 0x29f5.",
                        "npc_parameter_field_hashes": {
                            "Label": {"hash": "0x2f1b930d", "tables": ["NmlNpcParam", "SpNpcParam"]},
                            "PacketId": {"hash": "0x3ce2e8d8", "table": "SpNpcParam"},
                            "PosterItemID": {"hash": "0x0f640691", "tables": ["NmlNpcParam", "SpNpcParam"]},
                        },
                        "poster_item_table_join": poster_item_crosswalk(tables_root),
                        "post_addition_mask": {
                            "construction": "0xa0ffa0 creates ItemUICategory predicates; 0x1af3a0 constructs the matching 15,000-item bitsets for ordinals 0, 13, and 10. The producer ORs those sets, complements the result, and intersects it with the accumulated list.",
                            "excluded_item_ui_categories": ui_category_ordinals["excluded_ordinals"],
                            "after_mask": "0xb2ecc0 scans 15,000 bits and only clears an item when its handle is invalid or its callback at 0x30ceff8→0xb2eed0 returns false.",
                            "clear_only_disassembly": {
                                "function": selector4_filter_meta,
                                "function_bytes_sha256": sha256(selector4_filter_bytes),
                                "clear_pc": dynamic_filter_clear[0]["va"],
                                "store_pc": dynamic_filter_stores[0]["va"],
                                "callback_sequence": {
                                    "start_va": hx(dynamic_filter_vtable_va),
                                    "status": dynamic_filter_sequence.get("status"),
                                    "entries": dynamic_filter_sequence["entries"],
                                    "callback_va": hx(dynamic_filter_va),
                                    "callback_function": native_function(db, dynamic_filter_va),
                                },
                            },
                            "runtime_predicate_semantics": "The callback builds a candidate-dependent runtime query, but its field/state meaning is not resolved here. It only removes entries in this caller.",
                        },
                        "limitation": "The 451 known NPC poster IDs and state-flag UniqueID 0x29f5 are Sale posters in ItemUICategory=Wall, so they pass the explicit UI-category mask; the later runtime callback may still remove them. The 64-record source is SaveLand.Shop.ShopCatalog, populated by the daily shop builder; its concrete runtime contents and complete NotSee exclusion remain unresolved.",
                    },
                    "common_tail": ["0x1189e80", "0x1adeb0", "0x11433d0", "0x118a3d0"],
                },
            },
            "selector_0_branch": {
                "all_explicit_notsee_filter_call_sites_in_producer": notsee_call_pcs,
                "calls_on_selector_0_branch": [],
                "call_site_roles": {"0x1182a80": "selectors 1–3", "0x1182b28": "selector 4"},
                "branch_table_va": hx(selector0_jump_table_va),
                "branch_table_bytes": selector0_table_bytes.hex(),
                "selector_0_target": "0x1182ac8 sets the selected-record offset to 0xb958; 0x1345180 reads the selected element's +0x268 code.",
                "record_code_crosswalk": item_kind_ordinals,
                "conditional_additions": {"item_kind_13_helmet": "calls 0x1189c70 to add the NPC PosterItemID collection",
                                           "item_kind_92_bday_cupcake": "scans up to 64 records and adds valid entries",
                                           "other_codes": "skip these additions"},
                "limitation": "This selector-0 branch bypasses the explicit ItemCatalogType=NotSee filter, the selector-4 ItemUICategory mask, and its trailing 0xb2ecc0 clear-only callback. The selected record's exact class-field descriptor and incoming base-list composition remain unresolved.",
            },
            "conclusion": "The literal 2 in the catalog bitset filter is proven to mean ItemCatalogType=NotSee. Selectors 1–3 use later clear-only bitmap helpers and retain the exclusion. Selector 4 adds daily shop entries from SaveLand.Shop.ShopCatalog and 451 known Sale posters in ItemUICategory=Wall, then removes ItemUICategory None, Tool, and Unnecessary plus entries rejected by a later clear-only runtime predicate. The concrete shop records and complete NotSee exclusion after those additions remain unresolved. Selector 0 bypasses these explicit filters and conditionally adds posters for ItemKind Helmet or up to 64 records for BdayCupcake, but its base-list composition remains unresolved.",
            "source_pseudocode": source_files,
        }
    finally:
        db.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", type=Path, default=DEFAULT_RESEARCH / "index.sqlite")
    parser.add_argument("--code-pointer-arrays", type=Path,
                        default=DEFAULT_RESEARCH / "binary/code_pointer_arrays.json")
    parser.add_argument("--decomp-root", type=Path,
                        default=DEFAULT_RESEARCH / "binary/analysis_decomp")
    parser.add_argument("--main-elf", type=Path, default=DEFAULT_MAIN)
    parser.add_argument("--tables-root", type=Path, default=DEFAULT_RESEARCH / "tables_resolved")
    parser.add_argument("--save-layout", type=Path,
                        default=DEFAULT_RESEARCH / "gameplay/save_layout.json")
    parser.add_argument("--save-keys", type=Path,
                        default=ROOT / "tools/external/CylindricalEarth/save_keys.json")
    parser.add_argument("--output", type=Path,
                        default=ROOT / "output/gameplay/catalog_order_remainder/catalog_notsee_gate_static.json")
    args = parser.parse_args()
    result = build(args.index.resolve(), args.code_pointer_arrays.resolve(),
                   args.decomp_root.resolve(), args.main_elf.resolve(), args.tables_root.resolve(),
                   args.save_layout.resolve(), args.save_keys.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {args.output}")
    print(result["conclusion"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
