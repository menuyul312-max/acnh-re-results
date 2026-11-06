#!/usr/bin/env python3
"""Trace selected tool-ring pocket indices into their native item-word records."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
import struct
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from nso_sandbox import NSO_SHA256, Sandbox  # noqa: E402

DEFAULT_RESEARCH_OUTPUT = Path("/workspace/acnh-re/output")
DEFAULT_NSO = ROOT / "inputs/additional_exefs/main"
DEFAULT_OUTPUT = ROOT / "output/gameplay/tool_mechanics_followup/tool_ring_inventory_native.json"
SELECTED_ITEM_COPY = 0x11B7210
POCKET_SLOT_ADDRESS = 0xEF7260
RING_SELECTION_CALLBACK = 0x1417F70
SLOT_CALL_PC = 0x1418008
ITEM_COPY_CALL_PC = 0x11B7264
ITEMPARAM_SOURCE_ID = 72
SAMPLE_TOOL_LABELS = (
    "ToolAxe", "ToolScoop", "ToolNet", "ToolAngling",
    "ToolSlingshot", "ToolWatering", "ToolAxeGold", "ToolNetGold",
)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_tool_samples(research_output: Path) -> tuple[dict, list[dict]]:
    table = json.loads((research_output / "tables_resolved/ItemParam.json").read_text())
    if table["source_id"] != ITEMPARAM_SOURCE_ID:
        raise ValueError(f"unexpected ItemParam source id {table['source_id']}")
    col = {column["name"]: index for index, column in enumerate(table["columns"])}
    by_label = {}
    for row in table["rows"]:
        if row[col["Label"]] in SAMPLE_TOOL_LABELS:
            kind = row[col["ItemKind"]]
            labels = kind.get("labels") if isinstance(kind, dict) else None
            by_label[row[col["Label"]]] = {
                "unique_id": row[col["UniqueID"]],
                "label": row[col["Label"]],
                "item_kind": labels[0] if labels else None,
            }
    missing = set(SAMPLE_TOOL_LABELS) - set(by_label)
    if missing:
        raise ValueError(f"expected sample tool rows are missing: {sorted(missing)}")
    return table, [by_label[label] for label in SAMPLE_TOOL_LABELS]


def static_calls(research_output: Path) -> list[dict]:
    with sqlite3.connect(research_output / "index.sqlite") as db:
        rows = db.execute(
            "SELECT owner_va, pc, target_va FROM direct_calls "
            "WHERE (owner_va=? AND target_va=? AND pc=?) "
            "OR (owner_va=? AND target_va=? AND pc=?) ORDER BY owner_va,pc",
            (RING_SELECTION_CALLBACK, SELECTED_ITEM_COPY, SLOT_CALL_PC,
             SELECTED_ITEM_COPY, POCKET_SLOT_ADDRESS, ITEM_COPY_CALL_PC),
        ).fetchall()
    expected = {
        (RING_SELECTION_CALLBACK, SLOT_CALL_PC, SELECTED_ITEM_COPY),
        (SELECTED_ITEM_COPY, ITEM_COPY_CALL_PC, POCKET_SLOT_ADDRESS),
    }
    if set(rows) != expected:
        raise AssertionError(f"selected-tool item-word call chain changed: {rows}")
    return [{"owner_va": hex(owner), "call_pc": hex(pc),
             "target_va": hex(target)} for owner, pc, target in rows]


def callback_index_evidence(sandbox: Sandbox) -> dict:
    """Check the callback's stored-index load and pass-through to the item reader."""
    instructions = [
        (0x1417F8C, "083f9752", "mov w8, #0xb9f8"),
        (0x1417F90, "2800a072", "movk w8, #1, lsl #16"),
        (0x1417F94, "1700088b", "add x23, x0, x8"),
        (0x1417FFC, "e20240b9", "ldr w2, [x23]"),
        (SLOT_CALL_PC, "827cf697", "bl #0x11b7210"),
    ]
    observed = []
    for pc, expected_hex, instruction in instructions:
        actual_hex = sandbox.read(pc, 4).hex()
        if actual_hex != expected_hex:
            raise AssertionError(
                f"ring callback instruction changed at {pc:#x}: "
                f"{actual_hex} != {expected_hex}"
            )
        observed.append({"va": hex(pc), "instruction": instruction,
                         "bytes_le_hex": actual_hex})
    return {
        "callback_va": hex(RING_SELECTION_CALLBACK),
        "stored_index_field_offset_from_page": hex(0x1B9F8),
        "reader_argument_register": "w2",
        "reader_call_pc": hex(SLOT_CALL_PC),
        "reader_va": hex(SELECTED_ITEM_COPY),
        "instructions": observed,
    }


def run(research_output: Path, nso_path: Path, output: Path) -> dict:
    if sha256(nso_path.read_bytes()) != NSO_SHA256:
        raise ValueError("main NSO does not match the indexed 1.0.0 image")
    table, samples = load_tool_samples(research_output)
    calls = static_calls(research_output)

    sandbox = Sandbox(nso_path)
    callback_operand = callback_index_evidence(sandbox)
    context = sandbox.alloc(0x100)
    pocket_storage = sandbox.alloc(0x17000)
    out = sandbox.alloc(8)
    sandbox.stub(0xDA4020, lambda _sb: 1)  # selected pocket context is present
    sandbox.stub(0xDA3FC0, lambda _sb: 0)  # construct context wrapper
    sandbox.stub(0xEAB1F0, lambda _sb: pocket_storage)  # wrapper's pocket base

    def make_item_reference(sb):
        descriptor = sb.reg("x0")
        item_address = sb.reg("x1")
        handle = sb.alloc(0x20)
        # EE9350 creates a small reference wrapper.  Preserve the native
        # consumer's {base + offset} access while replacing only its owner.
        sb.uc.mem_write(handle + 8, struct.pack("<Q", item_address))
        sb.uc.mem_write(handle + 16, struct.pack("<Q", 0))
        sb.uc.mem_write(descriptor + 8, struct.pack("<Q", handle))
        return 1

    sandbox.stub(0xEE9350, make_item_reference)
    sandbox.stub(0xEE93D0, lambda _sb: 0)

    cases = []
    for slot, item in enumerate(samples):
        source = struct.pack("<HBBI", item["unique_id"], slot, 0,
                             0xA5000000 | slot)
        source_address = pocket_storage + 0x3F00 + slot * 0x2450 + 0x2418
        sandbox.uc.mem_write(source_address, source)
        sandbox.uc.mem_write(out, bytes(8))
        sandbox.call(SELECTED_ITEM_COPY, (out, context, slot))
        copied = sandbox.read(out, 8)
        if copied != source:
            raise AssertionError({"slot": slot, "item": item,
                                  "source": source.hex(), "copied": copied.hex()})
        cases.append({
            "ring_selection_index": slot,
            "pocket_inventory_slot": slot,
            "item_unique_id": item["unique_id"],
            "item_label": item["label"],
            "item_kind": item["item_kind"],
            "source_record_offset_from_pocket_base": hex(0x3F00 + slot * 0x2450 + 0x2418),
            "packed_word_hex": copied.hex(),
            "exact_word_copied": True,
        })

    if sandbox.unknown_imports:
        raise AssertionError(f"unexpected native imports: {sandbox.unknown_imports}")
    result = {
        "schema": "acnh-re/tool-ring-inventory-native/1",
        "native_elf_sha256": sha256(nso_path.read_bytes()),
        "itemparam_source_id": table["source_id"],
        "itemparam_raw_sha256": table["raw"]["sha256"],
        "ring_selection_callback_va": hex(RING_SELECTION_CALLBACK),
        "ring_callback_item_lookup_call": {
            "call_pc": hex(SLOT_CALL_PC),
            "helper_va": hex(SELECTED_ITEM_COPY),
            "selected_index_source": "*(uint32_t *)(page + 0x1b9f8)",
            "pocket_context_source": "page + 0x1f8",
        },
        "item_word_helper": {
            "function_va": hex(SELECTED_ITEM_COPY),
            "pocket_slot_accessor_va": hex(POCKET_SLOT_ADDRESS),
            "pocket_slot_accessor_call_pc": hex(ITEM_COPY_CALL_PC),
            "slot_count_bound": 8,
            "record_stride_bytes": hex(0x2450),
            "item_word_offset_in_record": hex(0x2418),
            "copy_operation_va": "0xf589e0",
        },
        "callback_index_argument": callback_operand,
        "native_functions_executed": [
            "0x11b7210 original item-word reader invoked directly by the harness",
            "0xef7260 original selected-pocket pointer arithmetic",
            "0xf589e0 original 8-byte packed-item copy",
        ],
        "native_functions_stubbed": [
            "0xda4020 indicates the controlled pocket context is present",
            "0xda3fc0/0xeab1f0 provide a synthetic pocket-storage base",
            "0xee9350/0xee93d0 create and release the result reference wrapper",
        ],
        "static_call_chain": calls,
        "cases": cases,
        "case_count": len(cases),
        "mismatches": 0,
        "unresolved_imports": sandbox.unknown_imports,
        "proven": [
            "The RingMenuTools selection callback passes its stored index directly as the selected pocket-slot argument to 0x11b7210.",
            "The original 0x11b7210 and 0xef7260 use that index to read pocket storage at base+0x3f00+index*0x2450+0x2418, then the original 0xf589e0 copies the packed word to the callback's output.",
            "Native reproduction confirms exact selection-index-to-record mapping for indices 0 through 7 using eight valid source ItemParam tool variants from all six tool families.",
        ],
        "limits": [
            "The synthetic item reader runs the helper, not the full ring menu, controller input, UI animation, or save-backed pocket object.",
            "The helper proves which pocket item word the selection index reads; transfer into the player's held-hand object and transition into ToolChange/ToolPullout or a tool-use action remain unproven.",
            "The widget binder separately maps button suffixes to indices 0 through 7; the full runtime callback-to-layout animation timing is not emulated.",
        ],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({key: value for key, value in result.items()
                      if key != "cases"}, indent=2, ensure_ascii=False))
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--research-output", type=Path, default=DEFAULT_RESEARCH_OUTPUT)
    parser.add_argument("--nso", type=Path, default=DEFAULT_NSO)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    run(args.research_output, args.nso, args.output)


if __name__ == "__main__":
    main()
