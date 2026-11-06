#!/usr/bin/env python3
"""Cross-check the static nested-scissor path to the dynamically resolved NVN API."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sqlite3
import struct

from capstone import Cs, CS_ARCH_ARM64, CS_MODE_ARM
import re_helpers

ROOT = Path(__file__).resolve().parent.parent
NSO = ROOT / "inputs/additional_exefs/main"
DEFAULT_OUTPUT = Path("/workspace/acnh-re/output")
RESOLVER = 0x18FB3F0
SCISSOR_SETUP = 0x14C8FE0
SCISSOR_RESTORE = 0x14C9250
SCISSOR_APPLY = 0x14C90E0
VIEWPORT_RECT_APPLY = 0x19A9960
API_NAME = "nvnCommandBufferSetScissor"


def function_size(db: sqlite3.Connection, va: int) -> int:
    row = db.execute("select size from functions where va=?", (va,)).fetchone()
    if not row:
        raise ValueError(f"missing function size for {va:#x}")
    return row[0]


def decode(md: Cs, segments, db: sqlite3.Connection, va: int):
    code = re_helpers._read(segments, va, function_size(db, va))
    return list(md.disasm(code, va))


def reg(md: Cs, ins, operand: int) -> str:
    return md.reg_name(ins.operands[operand].reg)


def memory_disp(ins, operand: int) -> int:
    return ins.operands[operand].mem.disp


def find_resolver_cell(md: Cs, instructions, string_va: int) -> tuple[int, int]:
    x1_value = None
    for i, ins in enumerate(instructions):
        ops = ins.operands
        if ins.mnemonic == "adrp" and reg(md, ins, 0) == "x1":
            x1_value = ops[1].imm
        elif (ins.mnemonic == "add" and len(ops) == 3 and reg(md, ins, 0) == "x1"
              and reg(md, ins, 1) == "x1"):
            x1_value = (x1_value or 0) + ops[2].imm
        elif ins.mnemonic == "blr" and reg(md, ins, 0) == "x19" and x1_value == string_va:
            # Resolver returns the function pointer in x0. Its next instructions
            # load the GOT cell address and store that pointer into the cell.
            for j in range(i + 1, min(i + 5, len(instructions) - 1)):
                a, b = instructions[j], instructions[j + 1]
                if a.mnemonic == "adrp" and reg(md, a, 0) == "x8" and b.mnemonic == "ldr" and reg(md, b, 0) == "x8" and reg(md, b, 1) == "x8":
                    return ins.address, a.operands[1].imm + memory_disp(b, 1)
    raise ValueError(f"could not find API resolver sequence for {API_NAME}")


def find_indirect_call_cell(md: Cs, instructions, wanted_cell: int) -> tuple[int, int]:
    x8_page = None
    loaded_cell = None
    for ins in instructions:
        ops = ins.operands
        if ins.mnemonic == "adrp" and reg(md, ins, 0) == "x8":
            x8_page = ops[1].imm
            loaded_cell = None
        elif (ins.mnemonic == "ldr" and len(ops) >= 2 and reg(md, ins, 0) == "x8"
              and reg(md, ins, 1) == "x8" and x8_page is not None and loaded_cell is None):
            loaded_cell = x8_page + memory_disp(ins, 1)
        elif ins.mnemonic == "blr" and reg(md, ins, 0) == "x8" and loaded_cell == wanted_cell:
            return ins.address, loaded_cell
    raise ValueError(f"{VIEWPORT_RECT_APPLY:#x} does not indirect-call resolved scissor cell {wanted_cell:#x}")


def direct_calls(db: sqlite3.Connection, caller: int) -> set[int]:
    return {row[0] for row in db.execute("select target_va from direct_calls where owner_va=?", (caller,))}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT,
                        help="shared analysis output containing index.sqlite")
    args = parser.parse_args()
    db = sqlite3.connect(args.output_root / "index.sqlite")
    string_rows = list(db.execute("select string_va from string_refs where function_va=? and text=?",
                                  (RESOLVER, API_NAME)))
    if len(string_rows) != 1:
        raise ValueError(f"expected one {API_NAME} reference in resolver, got {len(string_rows)}")
    string_va = string_rows[0][0]
    segments = re_helpers.nso_segments(NSO)
    md = Cs(CS_ARCH_ARM64, CS_MODE_ARM)
    md.detail = True
    resolver_instructions = decode(md, segments, db, RESOLVER)
    resolver_callsite, resolver_cell = find_resolver_cell(md, resolver_instructions, string_va)
    renderer_instructions = decode(md, segments, db, VIEWPORT_RECT_APPLY)
    renderer_callsite, renderer_cell = find_indirect_call_cell(md, renderer_instructions, resolver_cell)

    required_edges = {
        SCISSOR_SETUP: {SCISSOR_APPLY},
        SCISSOR_RESTORE: {SCISSOR_APPLY},
        SCISSOR_APPLY: {VIEWPORT_RECT_APPLY, 0x19A9C60, 0x19A9D50},
    }
    for caller, targets in required_edges.items():
        missing = targets - direct_calls(db, caller)
        if missing:
            raise ValueError(f"missing call edges from {caller:#x}: {[hex(x) for x in sorted(missing)]}")

    result = {
        "schema": "acnh.ui_hud_runtime_followup.scissor_static_path.v1",
        "source": {"game_build": "ACNH 1.0.0", "module": "ExeFS main",
                   "main_sha256": __import__("hashlib").sha256(NSO.read_bytes()).hexdigest(),
                   "evidence_kind": "Native disassembly, direct call index, and imported API string/global-cell cross-check; no game capture."},
        "scissor_context": {
            "push_candidate": hex(SCISSOR_SETUP),
            "restore_candidate": hex(SCISSOR_RESTORE),
            "apply": hex(SCISSOR_APPLY),
            "observed": ["0x14c8fe0 intersects an incoming rectangle with the top saved rectangle when the context count is nonzero, applies it through 0x14c90e0, and stores up to six rectangle entries.",
                         "0x14c9250 decrements the context count and reapplies the previous saved rectangle through 0x14c90e0; its empty-stack branch passes a zero rectangle and mode 0.",
                         "0x14c90e0 dispatches to 0x19a9960, 0x19a9c60, and 0x19a9d50 for viewport/scissor state updates."],
            "limits": ["No direct caller or vtable identity was recovered for 0x14c8fe0/0x14c9250.",
                       "This nested-scissor context is not yet tied to the ScissorPane object created by the viewport adjustment path."]},
        "nvn_scissor_api": {"api_name": API_NAME, "string_va": hex(string_va),
                            "resolver": hex(RESOLVER), "resolver_callsite": hex(resolver_callsite),
                            "resolver_got_cell": hex(resolver_cell),
                            "indirect_caller": hex(VIEWPORT_RECT_APPLY),
                            "indirect_callsite": hex(renderer_callsite),
                            "matching_cell": hex(renderer_cell),
                            "finding": "The original resolver looks up nvnCommandBufferSetScissor and stores the returned pointer through the same GOT cell that 0x19a9960 later loads and calls with the computed rectangle."},
        "call_edges": {hex(caller): [hex(target) for target in sorted(targets)]
                       for caller, targets in required_edges.items()},
        "open": ["Connect the nested-scissor context to the specific ScissorPane viewport object and its four stored values.",
                 "Determine exact viewport coordinate conversion and empty-stack scissor semantics from runtime or constructor/caller data.",
                 "Verify rendered clipping and nested pane behavior against a synchronized game capture."]
    }
    destination = ROOT / "output/ui_hud/runtime_followup/scissor_static_path.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"artifact": str(destination), "resolver_callsite": hex(resolver_callsite),
                      "resolver_cell": hex(resolver_cell), "renderer_callsite": hex(renderer_callsite),
                      "call_edges_verified": len(required_edges), "open": result["open"]}, indent=2))


if __name__ == "__main__":
    main()
