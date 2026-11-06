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
SCISSOR_ONLY_APPLY = 0x19A9D50
VIEWPORT_ONLY_APPLY = 0x19A9C60
API_NAMES = ("nvnCommandBufferSetScissor", "nvnCommandBufferSetViewport")


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
    segments = re_helpers.nso_segments(NSO)
    md = Cs(CS_ARCH_ARM64, CS_MODE_ARM)
    md.detail = True
    resolver_instructions = decode(md, segments, db, RESOLVER)
    api_paths = {}
    for api_name in API_NAMES:
        string_rows = list(db.execute("select string_va from string_refs where function_va=? and text=?",
                                      (RESOLVER, api_name)))
        if len(string_rows) != 1:
            raise ValueError(f"expected one {api_name} reference in resolver, got {len(string_rows)}")
        string_va = string_rows[0][0]
        resolver_callsite, resolver_cell = find_resolver_cell(md, resolver_instructions, string_va)
        target_functions = ({"nvnCommandBufferSetScissor": (VIEWPORT_RECT_APPLY, SCISSOR_ONLY_APPLY),
                             "nvnCommandBufferSetViewport": (VIEWPORT_RECT_APPLY, VIEWPORT_ONLY_APPLY)}[api_name])
        calls = []
        for target_function in target_functions:
            instructions = decode(md, segments, db, target_function)
            callsite, loaded_cell = find_indirect_call_cell(md, instructions, resolver_cell)
            calls.append({"function": hex(target_function), "callsite": hex(callsite),
                          "loaded_got_cell": hex(loaded_cell)})
        api_paths[api_name] = {"string_va": hex(string_va), "resolver": hex(RESOLVER),
                               "resolver_callsite": hex(resolver_callsite),
                               "resolver_got_cell": hex(resolver_cell), "indirect_calls": calls}

    required_edges = {
        SCISSOR_SETUP: {SCISSOR_APPLY},
        SCISSOR_RESTORE: {SCISSOR_APPLY},
        SCISSOR_APPLY: {VIEWPORT_RECT_APPLY, 0x19A9C60, 0x19A9D50},
        VIEWPORT_RECT_APPLY: {0x19A9A80},
        VIEWPORT_ONLY_APPLY: {0x19A9A80},
        SCISSOR_ONLY_APPLY: {0x19A9A80},
    }
    for caller, targets in required_edges.items():
        missing = targets - direct_calls(db, caller)
        if missing:
            raise ValueError(f"missing call edges from {caller:#x}: {[hex(x) for x in sorted(missing)]}")

    result = {
        "schema": "acnh.ui_hud_runtime_followup.scissor_static_path.v2",
        "source": {"game_build": "ACNH 1.0.0", "module": "ExeFS main",
                   "main_sha256": __import__("hashlib").sha256(NSO.read_bytes()).hexdigest(),
                   "evidence_kind": "Native disassembly, direct call index, and imported API string/global-cell cross-check; no game capture."},
        "scissor_context": {
            "push_candidate": hex(SCISSOR_SETUP),
            "restore_candidate": hex(SCISSOR_RESTORE),
            "apply": hex(SCISSOR_APPLY),
            "observed": ["0x14c8fe0 intersects incoming left/top/right/bottom bounds with the top saved rectangle when the context count is nonzero; if the intersection is inverted on either axis, it applies a four-zero rectangle through 0x14c90e0. It stores up to six entries; at count six an extra push still applies its intersection but does not save or increment.",
                         "0x14c9250 decrements the context count and reapplies the previous saved rectangle through 0x14c90e0; its empty-stack branch passes a zero rectangle and mode 0.",
                         "0x14c90e0 dispatches to 0x19a9960, 0x19a9c60, and 0x19a9d50 for viewport/scissor state updates."],
            "mode_dispatch": {"mode_bit": "When bit 0 is set, 0x14c90e0 calls 0x19a9c60 for viewport/depth and 0x19a9d50 for scissor; when clear, it calls the combined 0x19a9960 update.",
                              "renderer_roles": {"0x19a9960": "sets NVN scissor, viewport, and depth range",
                                                 "0x19a9c60": "sets NVN viewport and depth range",
                                                 "0x19a9d50": "sets NVN scissor"}},
            "limits": ["The ScissorPane render callback 0x14c8d30 calls 0x14c8fe0, and its auxiliary object's vtable hook reaches 0x14c9250; see scissorpane_restore_native.json for the native instance-path trace.",
                       "The synthetic stack fixture does not exercise balanced traversal beyond six saved entries.",
                       "This artifact follows static helper/API calls and does not establish active flags on a live BFLYT instance or rendered pixel coverage."]},
        "nvn_state_apis": {
            "apis": api_paths,
            "coordinate_conversion": {
                "rect_transform": "0x19a9a80 applies coordinate-mode cases 1–5 from param1+0x18 to source bounds at param1+0x8..+0x14. It reads logical viewport dimensions from param3+0x8/+0xc and target pixel bounds from param3+0x10..+0x1c; the enum's native label is unknown.",
                "pixel_mapping": "0x19a9960/0x19a9c60/0x19a9d50 scale the transformed origin and extent by logical viewport dimensions, map them into the target pixel bounds, then convert origin and size to integers by truncation.",
                "limits": "Static native math only; framebuffer origin convention, GPU pixel coverage, and parity against a capture remain unverified."
            }
        },
        "call_edges": {hex(caller): [hex(target) for target in sorted(targets)]
                       for caller, targets in required_edges.items()},
        "open": ["Determine framebuffer origin and GPU coverage semantics for the statically observed empty-stack zero rectangle.",
                 "Verify rendered clipping and nested pane behavior against a synchronized game capture."]
    }
    destination = ROOT / "output/ui_hud/runtime_followup/scissor_static_path.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"artifact": str(destination), "apis_traced": list(api_paths),
                      "renderer_calls_verified": sum(len(x["indirect_calls"]) for x in api_paths.values()),
                      "call_edges_verified": len(required_edges), "open": result["open"]}, indent=2))


if __name__ == "__main__":
    main()
