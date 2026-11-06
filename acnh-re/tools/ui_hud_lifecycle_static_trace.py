#!/usr/bin/env python3
"""Collect bounded static evidence for UI page routing and renderer flags.

Reads the local ExeFS main NSO, the read-only evidence index, and committed UI
catalogues. It does not emulate a live session or issue GPU commands.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sqlite3
import sys

from capstone import Cs, CS_ARCH_ARM64, CS_MODE_ARM

ROOT = Path(__file__).resolve().parent.parent
NSO = ROOT / "inputs/additional_exefs/main"
INDEX = ROOT / "output/index.sqlite"
OUTPUT = ROOT / "output/ui_hud/runtime_followup/page_input_renderer_static.json"
sys.path.insert(0, str(ROOT / "tools"))
import re_helpers  # noqa: E402

NPAD_UPDATE = 0x1968B80
ACTION_DISPATCH = 0x14845A0
PAGE_REGISTER = 0x1DA8220
PAGE_SELECTOR = 0x1DA8270
GENERIC_PANE_RENDER = 0x192FB20
PANE_HIT_VISIBILITY = 0x14C80D0
SCISSOR_SET_BOUNDS = 0x14C8D00
SCISSOR_RENDER_CALLBACK = 0x14C8D30


def read_function_size(db: sqlite3.Connection, address: int) -> int:
    row = db.execute("select size from native_functions where va=?", (address,)).fetchone()
    if row is None:
        raise ValueError(f"function size missing for {address:#x}")
    return int(row[0])


def disassemble_function(md: Cs, segments, db: sqlite3.Connection, address: int):
    size = read_function_size(db, address)
    return list(md.disasm(re_helpers._read(segments, address, size), address))


def instruction_rows(instructions, addresses: list[int]) -> list[dict[str, str]]:
    by_address = {instruction.address: instruction for instruction in instructions}
    rows = []
    for address in addresses:
        instruction = by_address.get(address)
        if instruction is None:
            raise AssertionError(f"instruction missing at {address:#x}")
        rows.append({
            "address": hex(address),
            "mnemonic": instruction.mnemonic,
            "operands": instruction.op_str,
        })
    return rows


def main() -> None:
    db = sqlite3.connect(f"file:{INDEX}?mode=ro", uri=True)
    segments = re_helpers.nso_segments(NSO)
    md = Cs(CS_ARCH_ARM64, CS_MODE_ARM)
    md.detail = True

    npad = disassemble_function(md, segments, db, NPAD_UPDATE)
    npad_calls = []
    for instruction in npad:
        if instruction.mnemonic != "bl" or not instruction.operands:
            continue
        operand = instruction.operands[0]
        if operand.type == 2:
            npad_calls.append({
                "callsite": hex(instruction.address),
                "target": hex(operand.imm),
            })
    if any(int(row["target"], 16) == ACTION_DISPATCH for row in npad_calls):
        raise AssertionError("Npad update unexpectedly has a direct action-dispatch call")

    dispatcher_callers = [
        {"callsite": hex(pc), "owner": None if owner is None else hex(owner)}
        for pc, owner in db.execute(
            "select pc,owner_va from direct_calls where target_va=? order by pc",
            (ACTION_DISPATCH,),
        )
    ]
    npad_direct_edge_count = db.execute(
        "select count(*) from direct_calls where owner_va=? and target_va=?",
        (NPAD_UPDATE, ACTION_DISPATCH),
    ).fetchone()[0]

    page_methods = json.loads((ROOT / "output/ui_hud/page_layout_method_bindings.json").read_text())
    page_factories = json.loads((ROOT / "output/ui_hud/page_factory_catalog.json").read_text())
    native_traces = json.loads((ROOT / "output/ui_hud/native_ui_traces.json").read_text())
    hit_proof = json.loads((ROOT / "output/ui_hud/runtime_followup/hit_node_link_static.json").read_text())
    hit_assets = json.loads((ROOT / "output/ui_hud/runtime_followup/bnd1_hit_test_trace.json").read_text())
    scissor_fixture = json.loads((ROOT / "output/ui_hud/runtime_followup/scissorpane_restore_native.json").read_text())
    sections = json.loads((ROOT / "output/ui_hud/section_semantics.json").read_text())

    page_method_summary = page_methods["summary"]
    page_registration = page_factories["shared_handoff_slot_observation"]
    page_selector = native_traces["page_factory_registry"][
        "shared_registration_and_selection_helpers"
    ]["candidate_selection_helper"]
    scissor_check_count = sum(scissor_fixture[key][case_key] for key, case_key in [
        ("native_rect_setter", "synthetic_cases"),
        ("scissorpane_render_to_push", "native_probe_cases"),
        ("native_scissor_stack", "push_cases"),
        ("native_scissor_stack", "restore_cases"),
        ("restore_thunk", "native_probe_cases"),
    ])
    hit_matches = hit_assets["asset_crosswalk"]["same_layout_matches"]
    hit_pane_rows = [
        row for row in sections["bounding_scissor_sections"]
        if row["pane"]["type"] == "bnd1" and row["pane"]["name"] == "B_Hit"
    ]
    scissor_rows = [
        row for row in sections["bounding_scissor_sections"]
        if row["pane"]["type"] == "scr1"
    ]
    if len(hit_matches) != 18 or len(hit_pane_rows) != 18 or len(scissor_rows) != 2:
        raise AssertionError("catalogue crosswalk/count changed")

    renderer = disassemble_function(md, segments, db, GENERIC_PANE_RENDER)
    visibility = disassemble_function(md, segments, db, PANE_HIT_VISIBILITY)
    setter = disassemble_function(md, segments, db, SCISSOR_SET_BOUNDS)
    scissor_callback = disassemble_function(md, segments, db, SCISSOR_RENDER_CALLBACK)

    renderer_rows = instruction_rows(renderer, [
        0x192FB30, 0x192FB34, 0x192FB38, 0x192FB3C,
        0x192FB50, 0x192FB54, 0x192FB5C, 0x192FB60,
        0x192FB64, 0x192FB68, 0x192FB78,
        0x192FBE8, 0x192FBEC, 0x192FBFC,
    ])
    visibility_rows = instruction_rows(visibility, [
        0x14C80D0, 0x14C80D4, 0x14C80D8, 0x14C80DC,
        0x14C80E4, 0x14C80E8, 0x14C80EC,
        0x14C80FC, 0x14C8100, 0x14C8104,
    ])
    setter_rows = instruction_rows(setter, [
        0x14C8D00, 0x14C8D04, 0x14C8D08, 0x14C8D0C,
        0x14C8D10, 0x14C8D14, 0x14C8D18, 0x14C8D1C,
        0x14C8D20, 0x14C8D24,
    ])
    callback_rows = instruction_rows(scissor_callback, [
        0x14C8D44, 0x14C8D4C, 0x14C8D50, 0x14C8D54,
        0x14C8D7C, 0x14C8E40, 0x14C8E44,
    ])

    source_hash = hashlib.sha256(NSO.read_bytes()).hexdigest()
    result = {
        "schema": "acnh.ui_hud_runtime_followup.page_input_renderer_static.v1",
        "source": {
            "game_build": "ACNH 1.0.0",
            "module": "ExeFS main",
            "main_sha256": source_hash,
            "evidence_kind": "Raw AArch64 static inspection, indexed direct-call rows, and committed BFLYT audit outputs.",
            "capture_status": "No synchronized live game capture or runtime pointer trace is present in the available evidence.",
            "local_input_scope": "This worktree has the ExeFS main image; RomFS-derived UI evidence is available only as committed catalogues, not as raw archives under inputs/.",
        },
        "page_loader_and_lifecycle": {
            "factory_count": page_factories["summary"]["factory_count"],
            "registration": {
                "helper": hex(PAGE_REGISTER),
                "shared_virtual_slot_index": page_registration["shared_virtual_slot_index"],
                "shared_virtual_slot_offset_bytes": page_registration["shared_virtual_slot_offset_bytes"],
                "target": page_registration["target_raw_va"],
                "observation": page_registration["observed_call_path"],
            },
            "slot46_layout_getters": {
                "summary": page_method_summary,
                "method": "One relocated three-instruction string getter at slot 46 (+0x170) in each of 135 observed factory page pointer sequences.",
                "direct_getter_calls": "The static page audit records zero direct B/BL references to the getter targets.",
            },
            "candidate_selector": {
                "helper": hex(PAGE_SELECTOR),
                "direct_callsite_count": page_selector["direct_callsite_count"],
                "direct_callsite_va": page_selector["direct_callsite_va"],
                "observed": page_selector["observed_operations"],
                "limit": page_selector["limit"],
            },
            "status": "Factory construction and collection insertion are statically mapped; getter-to-layout-loader handoff, page open/update/close/back scheduling, modal ordering, focus restoration, and page teardown remain unresolved.",
        },
        "npad_to_action_route": {
            "npad_update_function": hex(NPAD_UPDATE),
            "direct_call_count_inside_update": len(npad_calls),
            "direct_call_targets_inside_update": npad_calls,
            "action_dispatcher": hex(ACTION_DISPATCH),
            "direct_calls_into_action_dispatcher": len(dispatcher_callers),
            "action_dispatcher_direct_call_sites": dispatcher_callers,
            "direct_edge_from_npad_update_to_action_dispatcher": npad_direct_edge_count != 0,
            "interpretation": "The indexed updater's direct calls go to its recorded HID/runtime call targets, but none lead directly to the generic UI action dispatcher. This does not exclude a virtual callback, another scheduler function, or state translated between the two subsystems.",
        },
        "hit_pane_identity": {
            "native_inputs": hit_proof["same_key_lookup_inputs"],
            "asset_pair_count": len(hit_matches),
            "asset_pairs": hit_matches,
            "b_hit_declared_visible_counts": {
                "true": sum(1 for row in hit_pane_rows if row["pane"]["visible"]),
                "false": sum(1 for row in hit_pane_rows if not row["pane"]["visible"]),
            },
            "return_pointer_comparison_present": False,
            "status": "Both native lookups use the same dynamic name source, context, descriptor base, helper, and Hit token. Their returns are stored separately and are not compared. The 18 same-layout B_Hit:Hit records support the asset name crosswalk; no live dynamic prefix or pane pointer was captured.",
        },
        "static_pane_and_scissor_flags": {
            "hit_visibility_helper": {
                "function": hex(PANE_HIT_VISIBILITY),
                "instructions": visibility_rows,
                "observation": "The helper tests bit 0 of the pane byte at +0x58 and then walks the parent chain under its input options. The byte is consulted as visibility state in the hit-test path; live instance values are unavailable.",
            },
            "generic_renderer_callback_gate": {
                "function": hex(GENERIC_PANE_RENDER),
                "instructions": renderer_rows,
                "raw_conditions": [
                    "Pane byte +0x58 has both mask bits 0 and 7 set (mask 0x81).",
                    "Pane byte +0x5c has bit 4 set.",
                    "Pane byte +0x5a is nonzero.",
                    "Pane byte +0x62 has bit 1 clear.",
                ],
                "callback": "The pane vtable slot +0xa8 (byte offset 168) is called after those raw gates; the child traversal later calls slot +0xa0 (offset 160). These raw object fields are not named active/visible flags by the disassembly.",
            },
            "scissor_bounds_selector": {
                "setter_function": hex(SCISSOR_SET_BOUNDS),
                "callback_function": hex(SCISSOR_RENDER_CALLBACK),
                "instructions": {"setter": setter_rows, "callback": callback_rows},
                "observation": "The setter writes 1 to object byte +0xe0 and copies four 32-bit bounds to +0xf0..+0xfc. The callback uses those stored bounds when +0xe0 is nonzero; when zero it computes bounds from the pane transform. Both branches converge on the stack-push call at 0x14c8e44, so +0xe0 selects the bounds source, not whether clipping is applied.",
            },
            "catalogued_scissor_panes": [
                {"layout": row["layout"], "pane": row["pane"]}
                for row in scissor_rows
            ],
            "synthetic_fixture": {
                "artifact": "scissorpane_restore_native.json",
                "checks_without_mismatch": scissor_check_count,
                "pixel_or_nvn_capture": False,
            },
        },
        "limits": [
            "No synchronized live capture aligns page scheduler events, Npad samples, BFLYT instance pointers, renderer flags, and GPU output.",
            "The current worktree does not contain raw RomFS archives under inputs/; BFLYT claims here use the committed parser/catalogue outputs.",
            "The static Npad call graph does not establish indirect routes from HID state to the 13 UI action IDs.",
            "The parent-bound pointer used by hit testing is not named a render clip by native code; its geometric intersection is established, but visual clipping from that field is not.",
            "The renderer's pane flag bytes and ScissorPane bounds-source byte have no recovered runtime active-state names beyond the code behavior recorded above.",
            "Scissor stack fixtures do not execute NVN or compare displayed pixels, so framebuffer origin and actual clip coverage remain unmeasured.",
        ],
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({
        "artifact": str(OUTPUT),
        "page_factories": result["page_loader_and_lifecycle"]["factory_count"],
        "npad_update_direct_action_edge": result["npad_to_action_route"]["direct_edge_from_npad_update_to_action_dispatcher"],
        "B_Hit_pairs": result["hit_pane_identity"]["asset_pair_count"],
        "scissor_fixture_checks": result["static_pane_and_scissor_flags"]["synthetic_fixture"]["checks_without_mismatch"],
        "limits": len(result["limits"]),
    }, indent=2))


if __name__ == "__main__":
    main()
