#!/usr/bin/env python3
"""Record native def-use from a controller Hit lookup into hit-node pane geometry."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sqlite3

from capstone import Cs, CS_ARCH_ARM64, CS_MODE_ARM
import re_helpers

ROOT = Path(__file__).resolve().parent.parent
NSO = ROOT / "inputs/additional_exefs/main"
INDEX = ROOT / "output/index.sqlite"
ASSET_TRACE = ROOT / "output/ui_hud/runtime_followup/bnd1_hit_test_trace.json"
OUTPUT = ROOT / "output/ui_hud/runtime_followup/hit_node_link_static.json"

CONTROL_CTOR = 0x14821D0
PANE_LOOKUP = 0x1485AB0
CONTROL_PANE_BIND = 0x14885B0
NODE_ATTACH = 0x14B87B0
NODE_HIT_TEST = 0x14B7820
CONTROL_PANE_BIND_CALLSITE = 0x14827C4
CONTROL_NODE_OFFSET = 0x200
NODE_PANE_FIELD_OFFSET = 0x20
NODE_PARENT_BOUND_OFFSET = 0x28
HIT_TOKEN = 0x294751B


def instruction_map(md: Cs, segments, db: sqlite3.Connection, va: int):
    row = db.execute("select size from functions where va=?", (va,)).fetchone()
    if row is None:
        raise ValueError(f"missing function size for {va:#x}")
    return {ins.address: ins for ins in md.disasm(re_helpers._read(segments, va, row[0]), va)}


def show(insts, addresses):
    result = []
    for address in addresses:
        ins = insts.get(address)
        if ins is None:
            raise AssertionError(f"instruction missing at {address:#x}")
        result.append({"address": hex(address), "mnemonic": ins.mnemonic,
                       "operands": ins.op_str})
    return result


def require(insts, address, mnemonic, operands_prefix):
    ins = insts.get(address)
    if ins is None or ins.mnemonic != mnemonic or not ins.op_str.startswith(operands_prefix):
        raise AssertionError({"address": hex(address),
                              "actual": None if ins is None else (ins.mnemonic, ins.op_str),
                              "expected": (mnemonic, operands_prefix)})


def main() -> None:
    db = sqlite3.connect(INDEX)
    segments = re_helpers.nso_segments(NSO)
    md = Cs(CS_ARCH_ARM64, CS_MODE_ARM)
    md.detail = True

    ctor = instruction_map(md, segments, db, CONTROL_CTOR)
    attach = instruction_map(md, segments, db, NODE_ATTACH)
    hit = instruction_map(md, segments, db, NODE_HIT_TEST)
    binder = instruction_map(md, segments, db, CONTROL_PANE_BIND)

    # The controller's inline node begins at control+0x200. The pane-lookup
    # helper's return is stored at control+0x220, which is exactly node+0x20.
    require(ctor, 0x1482258, "add", "x21, x19, #0x200")
    require(ctor, 0x148227C, "adrp", "x8, #0x2947000")
    require(ctor, 0x1482280, "add", "x8, x8, #0x51b")
    require(ctor, 0x1482298, "bl", "#0x1485ab0")
    require(ctor, 0x14822A4, "str", "x0, [x19, #0x220]")
    require(ctor, 0x1482204, "mov", "x20, x1")
    require(ctor, 0x1482268, "ldp", "x8, x1, [x20, #8]")
    require(ctor, 0x148226C, "ldr", "x8, [x8, #0x18]")
    require(ctor, 0x1482278, "ldr", "x23, [x23, #0xe88]")
    require(ctor, 0x148228C, "add", "x9, x23, #0x10")
    require(ctor, CONTROL_PANE_BIND_CALLSITE - 4, "ldp", "x1, x2, [x20, #8]")
    require(ctor, CONTROL_PANE_BIND_CALLSITE, "bl", "#0x14885b0")
    require(ctor, 0x14824D0, "mov", "x0, x21")
    require(ctor, 0x14824D4, "bl", "#0x14b87b0")
    require(binder, 0x14885C4, "ldr", "x8, [x1, #0x18]")
    require(binder, 0x14885D0, "ldr", "x22, [x22, #0xe88]")
    require(binder, 0x14885D4, "mov", "x20, x2")
    require(binder, 0x14885F0, "add", "x21, x22, #0x10")
    require(binder, 0x14885FC, "adrp", "x8, #0x2947000")
    require(binder, 0x1488600, "add", "x8, x8, #0x51b")
    require(binder, 0x1488610, "mov", "x1, x20")
    require(binder, 0x1488614, "stp", "x21, x8, [sp, #0x10]")
    require(binder, 0x1488618, "bl", "#0x1485ab0")
    require(binder, 0x1488620, "str", "x0, [x19, #0x70]")
    require(attach, 0x14B87FC, "ldr", "x8, [x20, #0x28]")
    require(attach, 0x14B8800, "str", "x8, [x19, #0x28]")
    require(hit, 0x14B78A0, "ldr", "x8, [x20, #0x20]")
    require(hit, 0x14B78BC, "ldp", "s0, s4, [x20, #0x30]")
    require(hit, 0x14B78C0, "ldr", "x8, [x20, #0x28]")

    asset = json.loads(ASSET_TRACE.read_text())
    same_layout_matches = asset["asset_crosswalk"]["same_layout_matches"]
    hit_asset_matches = [row for row in same_layout_matches
                         if row["pane_action"] == "B_Hit:Hit"]
    if len(hit_asset_matches) != 18:
        raise AssertionError(f"expected 18 B_Hit:Hit records, got {len(hit_asset_matches)}")

    source_token = re_helpers._read(segments, HIT_TOKEN, 64).split(b"\0", 1)[0].decode()
    if source_token != "Hit":
        raise AssertionError({"hit_token": source_token})

    binder_strings = [row["text"] for row in asset["native_functions"].get(
        "string_references_in_0x14885b0", [])]
    if "B_Hit" not in binder_strings:
        raise AssertionError({"control_fallback_names": binder_strings})

    result = {
        "schema": "acnh.ui_hud_runtime_followup.hit_node_link_static.v1",
        "source": {
            "game_build": "ACNH 1.0.0",
            "module": "ExeFS main",
            "main_sha256": hashlib.sha256(NSO.read_bytes()).hexdigest(),
            "evidence_kind": "Raw AArch64 instruction/data-flow checks plus same-layout BFLYT/CNT1 catalogue crosswalk; no runtime instance trace."
        },
        "native_constructor_dataflow": {
            "function": hex(CONTROL_CTOR),
            "control_object": "x19",
            "inline_hit_node": {
                "base_expression": "control+0x200",
                "pane_pointer_field": "control+0x220 = node+0x20",
                "allocation_address_instruction": "0x1482258",
                "pointer_store_instruction": "0x14822a4"
            },
            "pane_lookup": {
                "helper": hex(PANE_LOOKUP),
                "dynamic_key_source": "[controller_params+8]+0x18",
                "literal_action_token": {"address": hex(HIT_TOKEN), "text": source_token},
                "result_flow": "lookup return x0 is stored at control+0x220, exactly the inline hit node's +0x20 Pane pointer field",
                "callsite": "0x1482298"
            },
            "parent_attach": {
                "helper": hex(NODE_ATTACH),
                "callsite": "0x14824d4",
                "node_argument": "x21 = control+0x200",
                "parent_argument": "[controller_params+0x20]"
            },
            "instructions": {
                "node_and_lookup": show(ctor, [0x1482258, 0x1482264, 0x1482268,
                                                0x148226C, 0x1482270, 0x148227C,
                                                0x1482280, 0x1482298, 0x14822A4]),
                "attach": show(ctor, [0x14824CC, 0x14824D0, 0x14824D4]),
                "parallel_control_pane_lookup_callsite": show(
                    ctor, [0x14827C0, 0x14827C4])
            }
        },
        "same_key_lookup_inputs": {
            "node_pane_lookup": {
                "callsite": "0x1482298",
                "helper": hex(PANE_LOOKUP),
                "dynamic_name_source": "[controller_params+8]+0x18",
                "lookup_context": "[controller_params+0x10]",
                "descriptor_base": "global cell [0x330de88] + 0x10",
                "token": "Hit",
                "result_field": "control+0x220"
            },
            "control_visibility_lookup": {
                "constructor_callsite": "0x14827c4",
                "helper_callsite": "0x1488618",
                "helper": hex(PANE_LOOKUP),
                "dynamic_name_source": "[controller_params+8]+0x18",
                "lookup_context": "[controller_params+0x10]",
                "descriptor_base": "global cell [0x330de88] + 0x10",
                "token": "Hit",
                "result_field": "control+0x420+0x70"
            },
            "interpretation": "The constructor builds the node+0x20 lookup and the control-side Hit lookup from the same controller parameter fields, descriptor base, helper, and token. Their calls are separate and native code does not compare the returned pointers; this is same-key input evidence, not a direct pointer-equality assertion.",
            "instructions": {
                "constructor_sources": show(ctor, [0x1482204, 0x1482268, 0x148226C,
                                                     0x1482278, 0x148228C, 0x1482298,
                                                     0x14822A4, 0x14827C0, 0x14827C4]),
                "control_lookup_sources": show(binder, [0x14885C4, 0x14885D0,
                                                         0x14885D4, 0x14885F0,
                                                         0x14885FC, 0x1488600,
                                                         0x1488610, 0x1488614,
                                                         0x1488618, 0x1488620])
            }
        },
        "hit_node_consumer": {
            "geometry_helper": hex(NODE_HIT_TEST),
            "pane_pointer_read": "node+0x20; passed to pane visibility test before rectangle evaluation",
            "primary_rect": "node+0x30..+0x3c",
            "secondary_pane_pointer_read": "node+0x28",
            "secondary_rect": "node+0x40..+0x4c; intersected with the first rectangle when the pointer is non-null",
            "parent_bound_inheritance": {
                "helper": hex(NODE_ATTACH),
                "condition": "child node flags at +0x50 include bit 0x40",
                "dataflow": "parent+0x28 Pane pointer is copied into child+0x28",
                "instructions": show(attach, [0x14B87DC, 0x14B87F0, 0x14B87FC, 0x14B8800])
            },
            "instructions": show(hit, [0x14B78A0, 0x14B78B4, 0x14B78BC,
                                        0x14B78C0, 0x14B79B0])
        },
        "asset_crosswalk": {
            "records_named_B_Hit_and_bound_as_Hit": len(hit_asset_matches),
            "same_layout_matches": hit_asset_matches
        },
        "separate_control_visibility_binding": {
            "helper": hex(CONTROL_PANE_BIND),
            "callsite_in_same_constructor": "0x14827c4",
            "writes_control_offsets": ["+0x68", "+0x70"],
            "fallback_name_observed": "B_Hit",
            "interpretation": "The controller visibility helper stores its Hit lookup at +0x70. Its lookup uses the same key sources as the constructor lookup feeding node+0x20, but the return values are not compared in native code."
        },
        "limits": [
            "Native code proves a controller Hit lookup result flows into node+0x20 and that node+0x20 is consumed by hit testing. The separate control-side Hit lookup at +0x70 is constructed with the same dynamic name source, lookup context, descriptor base, helper, and token. The asset catalogue's 18 same-layout B_Hit:Hit pairs are a strong name crosswalk, but the dynamic prefix value for a live instance was not captured and the two return values are not explicitly compared.",
            "The node+0x28 pointer is populated from a parent's +0x28 under child flag 0x40; native code does not identify its section type or label it as render clipping.",
            "The control-side +0x70 Hit result and node+0x20 Pane pointer use the same key inputs, but the native constructor does not compare the returned pointers. A synchronized layout/control instance trace or the corresponding raw BFLYT/controller data is needed to close direct instance identity.",
            "Hit-test coordinates have not been compared with a known-resolution/orientation game capture, so screen origin and pixel parity remain open."
        ]
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"artifact": str(OUTPUT), "node_hit_pointer": "control+0x220 = node+0x20",
                      "B_Hit_Hit_asset_matches": len(hit_asset_matches),
                      "limits": len(result["limits"])}, indent=2))


if __name__ == "__main__":
    main()
