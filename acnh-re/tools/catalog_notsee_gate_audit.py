#!/usr/bin/env python3
"""Verify the catalog's ItemCatalogType=NotSee bitset gate and its limits.

Inputs are read-only game analysis products. The report is written under the
repository's output tree and records the exact binary callback reached through
the relocated code-pointer sequence.
"""

from __future__ import annotations

import argparse
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


def build(index: Path, code_pointer_arrays: Path, decomp_root: Path, main_elf: Path) -> dict[str, Any]:
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
        }
        source_files = {}
        for va, fragments in source_requirements.items():
            _source, source_files[hx(va)] = verified_source(decomp_root, va, fragments)
        for va in (0xA105D0, 0xA9C290, 0x1189E80):
            source_files[hx(va)] = sha_source(decomp_root / f"{va:x}.c")

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
                    "0": "The indexed pseudocode has an unresolved jump-table branch; this audit does not claim its output behavior.",
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
                        "runtime_collection": "0x1189c70 adds entries from two runtime collections and a state-flag branch after the category-2 filter.",
                        "limitation": "The category of each post-filter addition and whether it survives later masks is unresolved.",
                    },
                    "common_tail": ["0x1189e80", "0x1adeb0", "0x11433d0", "0x118a3d0"],
                },
            },
            "conclusion": "The literal 2 in the catalog bitset filter is proven to mean ItemCatalogType=NotSee, resolving the previous ambiguity. For selectors 1–3, the later selector-specific helpers only clear additional bitmap entries, so those final lists retain the NotSee exclusion. Selector 4 receives post-filter item additions whose category/final mask behavior remains unresolved, and selector 0 follows an unresolved jump-table branch.",
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
    parser.add_argument("--output", type=Path,
                        default=ROOT / "output/gameplay/catalog_order_remainder/catalog_notsee_gate_static.json")
    args = parser.parse_args()
    result = build(args.index.resolve(), args.code_pointer_arrays.resolve(),
                   args.decomp_root.resolve(), args.main_elf.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {args.output}")
    print(result["conclusion"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
