#!/usr/bin/env python3
"""Collect bounded static evidence for UI page routing and renderer flags.

Reads the local ExeFS main NSO, the read-only evidence index, and committed UI
catalogues. It does not emulate a live session or issue GPU commands.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
import sys

from capstone import Cs, CS_ARCH_ARM64, CS_MODE_ARM

ROOT = Path(__file__).resolve().parent.parent
NSO = ROOT / "inputs/additional_exefs/main"
DEFAULT_OUTPUT_ROOT = Path("/workspace/acnh-re/output")
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
ROOT_PAGE_FACTORY_METHOD = 0x1DD4090
ROOT_PAGE_CONSTRUCTOR = 0x1DA5B50
ROOT_PAGE_EVENT_METHOD = 0x1DD4560
ROOT_PAGE_EVENT_METHOD_ALT = 0x1DD44C0
ROOT_PAGE_TEARDOWN_METHOD = 0x1DD4390
ROOT_PAGE_TRANSITION_METHOD = 0x1DD43A0
PAGE_TREE_PROCESS_METHOD = 0x1DD43B0
PAGE_STATE_SET_ONE = 0x1DA40A0
PAGE_STATE_SET_TWO = 0x1DA40B0
ROOT_PAGE_STATE_SET_THREE = 0x1DA5C60
PAGE_STATE_PRECALC_TRANSITION = 0x1DA4790
UIMGR_CONSTRUCTOR = 0x1DD3BD0
UIMGR_PRECALC_CALLBACK = 0x1DD3E70
DRAW_EVENT_CONSTRUCTOR = 0x1C80330
DRAW_EVENT_CALLBACK = 0x1C805D0
DRAW_PARTICLE_PRE_CALLBACK = 0x1C806B0
DRAW_PARTICLE_POST_CALLBACK = 0x1C806C0
DRAW_USER_CALLBACK = 0x1C806D0
DRAW_PARTICLE_RENDER = 0x1C80850
PANE_TYPE_DISPATCHER = 0x19212E0
SCR1_PANE_CONSTRUCTOR = 0x1937280
SCR1_PANE_RENDER = 0x19372B0
PANE_LAYOUT_FLAG_WRAPPER = 0x192D450
PANE_LAYOUT_FLAG_PARSER = 0x192D490
SCISSOR_CONTEXT_DISPATCH = 0x18FAF70
SWKBD_PADDING_FLAG_WRITER = 0x14C81B0
SHARED_UI_BIT4_HELPER = 0x14C8490
SHARED_UI_BIT4_CALLERS = {0x1496B60, 0x1496CA0, 0x1497060, 0x1497320, 0x1497C10}
PANE_COPY_CONSTRUCTOR = 0x192E290
PANE_RENDER_STATE_UPDATE = 0x192EDC0
PANE_USER_DATA_UPDATE = 0x192F4C0
PANE_CHILD_FLAG_PROPAGATOR = 0x192FE30


def pane_field_store_inventory(md: Cs, segments, db: sqlite3.Connection) -> dict:
    """Bound fixed-offset stores to the generic Pane method address family."""
    rows = []
    adjacent_overlap_stores = []
    for owner, size in db.execute(
        "select va,size from native_functions where va>=? and va<? order by va",
        (0x192D000, 0x1930000),
    ):
        for instruction in md.disasm(re_helpers._read(segments, int(owner), int(size)), int(owner)):
            if not instruction.mnemonic.startswith("st"):
                continue
            for operand in instruction.operands:
                if operand.type != 3 or instruction.reg_name(operand.mem.base) == "sp":
                    continue
                # Fixed-offset stores starting at +0x58/+0x5c are the direct
                # flag writes. Also detect neighboring wide stores whose byte
                # ranges could overlap either flag, so the inventory does not
                # silently miss a pair/store beginning at +0x50 or +0x54.
                start = int(operand.mem.disp)
                if start in (0x58, 0x5C):
                    rows.append({
                        "owner": hex(int(owner)),
                        "pc": hex(instruction.address),
                        "mnemonic": instruction.mnemonic,
                        "operands": instruction.op_str,
                        "field_offset_bytes": hex(start),
                        "base_register": instruction.reg_name(operand.mem.base),
                    })
                if not 0x50 <= start < 0x5D:
                    continue
                store_registers = []
                for candidate in instruction.operands:
                    if candidate.type == 3:
                        break
                    if candidate.type == 1:
                        store_registers.append(instruction.reg_name(candidate.reg))
                widths = [
                    16 if register.startswith("q") else
                    8 if register.startswith(("x", "d")) else
                    4 if register.startswith(("w", "s")) else
                    2 if register.startswith("h") else
                    1 if register.startswith("b") else 0
                    for register in store_registers
                ]
                width = max(widths, default=0)
                if instruction.mnemonic in ("stp", "stnp"):
                    width *= 2
                elif instruction.mnemonic.endswith("b"):
                    width = 1
                elif instruction.mnemonic.endswith("h"):
                    width = 2
                if (
                    start not in (0x58, 0x5C)
                    and width
                    and any(start < flag + 1 and start + width > flag for flag in (0x58, 0x5C))
                ):
                    adjacent_overlap_stores.append({
                        "owner": hex(int(owner)),
                        "pc": hex(instruction.address),
                        "mnemonic": instruction.mnemonic,
                        "operands": instruction.op_str,
                        "store_range_bytes": [hex(start), hex(start + width)],
                    })
    owners = sorted({int(row["owner"], 16) for row in rows})
    expected_owners = {0x192D3D0, 0x192D490, 0x192E290, 0x192EDC0, 0x192F4C0, 0x192FE30}
    if set(owners) != expected_owners or len(rows) != 19:
        raise AssertionError("generic Pane +0x58/+0x5c store inventory changed")
    expected_overlap = [("0x192d3d0", "0x192d3f8", "sturh", "0x5b", "0x5d")]
    actual_overlap = [
        (row["owner"], row["pc"], row["mnemonic"], *row["store_range_bytes"])
        for row in adjacent_overlap_stores
    ]
    if actual_overlap != expected_overlap:
        raise AssertionError("generic Pane adjacent-store overlap inventory changed")
    return {
        "search_scope": "Indexed native functions at 0x192d000 <= entry < 0x1930000; stores through a non-SP base with fixed displacement +0x58 or +0x5c.",
        "function_count": len(owners),
        "store_count": len(rows),
        "adjacent_overlap_store_count": len(adjacent_overlap_stores),
        "adjacent_overlap_stores": adjacent_overlap_stores,
        "functions": [hex(owner) for owner in owners],
        "stores": rows,
        "completeness_limit": "This exhausts fixed-displacement writes starting at the flag bytes and adjacent wide stores that overlap them within the generic Pane method family selected by the parser/render implementation. The sole adjacent overlap is the base constructor's halfword zero at +0x5b..+0x5c. The same numeric offsets occur in unrelated object layouts elsewhere in main; a whole-image offset-only scan cannot identify object type, and register-computed stores are outside this inventory.",
    }


def bounded_ui_offset_store_inventory(md: Cs, segments, db: sqlite3.Connection) -> dict:
    """Inventory possible +0x58/+0x5c store sites in the adjacent UI method range."""
    rows = []
    for owner, size in db.execute(
        "select va,size from native_functions where va>=? and va<? order by va",
        (0x14C8000, 0x14CA000),
    ):
        for instruction in md.disasm(re_helpers._read(segments, int(owner), int(size)), int(owner)):
            if not instruction.mnemonic.startswith("st"):
                continue
            for operand in instruction.operands:
                if operand.type != 3 or instruction.reg_name(operand.mem.base) == "sp":
                    continue
                if operand.mem.disp not in (0x58, 0x5C):
                    continue
                rows.append({
                    "owner": hex(int(owner)),
                    "pc": hex(instruction.address),
                    "mnemonic": instruction.mnemonic,
                    "operands": instruction.op_str,
                    "field_offset_bytes": hex(operand.mem.disp),
                })
    owners = sorted({row["owner"] for row in rows})
    if len(owners) != 9 or len(rows) != 12:
        raise AssertionError("bounded UI +0x58/+0x5c candidate store inventory changed")
    return {
        "search_scope": "Indexed native functions at 0x14c8000 <= entry < 0x14ca000; non-SP fixed-displacement stores to +0x58/+0x5c.",
        "function_count": len(owners),
        "store_count": len(rows),
        "functions": owners,
        "stores": rows,
        "classification_limit": "This includes UI-pane candidates plus static configuration and derived-layout payload stores. Numeric offsets alone do not establish that every listed base is a Pane flag byte.",
    }


def read_function_size(db: sqlite3.Connection, address: int) -> int:
    row = db.execute("select size from native_functions where va=?", (address,)).fetchone()
    if row is None:
        raise ValueError(f"function size missing for {address:#x}")
    return int(row[0])


def disassemble_function(md: Cs, segments, db: sqlite3.Connection, address: int):
    size = read_function_size(db, address)
    return list(md.disasm(re_helpers._read(segments, address, size), address))


def read_c_string(segments, address: int, maximum: int = 96) -> str:
    raw = re_helpers._read(segments, address, maximum)
    return raw.split(b"\0", 1)[0].decode("utf-8", "replace")


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


def owner_callsite_map(db: sqlite3.Connection, target: int) -> dict[int, int]:
    rows = list(db.execute(
        "select owner_va,pc from direct_calls where target_va=? and owner_va is not null",
        (target,),
    ))
    result = {int(owner): int(pc) for owner, pc in rows}
    if len(result) != len(rows):
        raise AssertionError(f"multiple indexed direct calls per owner to {target:#x}")
    return result


def pointer_sequence_inventory(path: Path, targets: set[int]):
    """Summarize exact memberships in the relocated code-pointer inventory.

    The inventory deliberately does not call every sequence a C++ vtable; this
    function preserves that source label so an observed slot is not mistaken
    for a proven dynamic call edge.
    """
    rows = json.loads(path.read_text())
    memberships = {target: [] for target in targets}
    entry_count = 0
    for row in rows:
        entries = row.get("entries", [])
        entry_count += len(entries)
        for slot, entry in enumerate(entries):
            target = int(entry["target_va"], 16)
            if target in memberships:
                memberships[target].append({
                    "sequence_start": row["start_va"],
                    "slot_index": slot,
                    "pointer_va": entry["pointer_va"],
                    "sequence_length": len(entries),
                    "source_status": row["status"],
                })
    return {
        "sequence_count": len(rows),
        "entry_count": entry_count,
        "memberships": {hex(target): found for target, found in memberships.items()},
    }


def callsite_context(db: sqlite3.Connection, target: int) -> list[dict[str, str | None]]:
    """Recover the smallest indexed function range when direct-call owner is null."""
    result = []
    for pc, owner, instruction in db.execute(
        "select pc,owner_va,instruction from direct_calls where target_va=? order by pc",
        (target,),
    ):
        range_evidence = "indexed_owner"
        if owner is None:
            candidates = db.execute(
                """select va,name,span_end_va from native_functions
                   where va<=? and span_end_va>? order by (span_end_va-va),va""",
                (pc, pc),
            ).fetchall()
            if candidates:
                owner, _name, _end = candidates[0]
                range_evidence = "smallest_enclosing_native_function_range"
        result.append({
            "callsite": hex(pc),
            "owner": None if owner is None else hex(owner),
            "owner_evidence": range_evidence if owner is not None else None,
            "instruction": instruction,
        })
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT,
                        help="shared analysis output containing the read-only index.sqlite")
    args = parser.parse_args()
    index_path = args.output_root / "index.sqlite"
    db = sqlite3.connect(f"file:{index_path}?mode=ro", uri=True)
    segments = re_helpers.nso_segments(NSO)
    md = Cs(CS_ARCH_ARM64, CS_MODE_ARM)
    md.detail = True
    pointer_inventory = pointer_sequence_inventory(
        args.output_root / "binary/code_pointer_arrays.json",
        {
            ROOT_PAGE_FACTORY_METHOD,
            ROOT_PAGE_TEARDOWN_METHOD,
            ROOT_PAGE_TRANSITION_METHOD,
            PAGE_TREE_PROCESS_METHOD,
            PANE_LAYOUT_FLAG_PARSER,
            ROOT_PAGE_STATE_SET_THREE,
            UIMGR_CONSTRUCTOR,
            UIMGR_PRECALC_CALLBACK,
            DRAW_EVENT_CALLBACK,
            SCR1_PANE_RENDER,
            0x192FC90,
            SCISSOR_RENDER_CALLBACK,
            GENERIC_PANE_RENDER,
            PANE_COPY_CONSTRUCTOR,
            PANE_RENDER_STATE_UPDATE,
            PANE_USER_DATA_UPDATE,
            PANE_CHILD_FLAG_PROPAGATOR,
            SHARED_UI_BIT4_HELPER,
            *SHARED_UI_BIT4_CALLERS,
        },
    )

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
    scissor_native_path = json.loads((ROOT / "output/ui_hud/runtime_followup/scissor_static_path.json").read_text())
    sections = json.loads((ROOT / "output/ui_hud/section_semantics.json").read_text())

    page_method_summary = page_methods["summary"]
    page_registration = page_factories["shared_handoff_slot_observation"]
    page_factory_rows = page_factories["pages"]
    page_factory_owners = {int(row["factory_va"], 16) for row in page_factory_rows}
    init_calls = owner_callsite_map(db, 0x1DA8210)
    common_init_calls = owner_callsite_map(db, 0x1144600)
    register_calls = owner_callsite_map(db, PAGE_REGISTER)
    state_sequence_rows = []
    state_sequence_branch_count = 0
    for owner in sorted(page_factory_owners):
        if owner not in init_calls or owner not in common_init_calls or owner not in register_calls:
            raise AssertionError(f"page factory {owner:#x} lacks the indexed state/init/register sequence")
        init_pc, common_pc, register_pc = (
            init_calls[owner], common_init_calls[owner], register_calls[owner]
        )
        if not init_pc < common_pc < register_pc:
            raise AssertionError(f"page factory {owner:#x} call order changed")
        factory_body = disassemble_function(md, segments, db, owner)
        intervening_branches = [
            instruction for instruction in factory_body
            if init_pc < instruction.address < register_pc
            and (
                instruction.mnemonic == "b"
                or instruction.mnemonic.startswith("b.")
                or instruction.mnemonic in {"cbz", "cbnz", "tbz", "tbnz"}
            )
        ]
        state_sequence_branch_count += len(intervening_branches)
        if intervening_branches:
            raise AssertionError(
                f"page factory {owner:#x} has a branch in its state/init/register interval"
            )
        state_sequence_rows.append({
            "factory": hex(owner),
            "state_one_callsite": hex(init_pc),
            "common_page_init_callsite": hex(common_pc),
            "registration_callsite": hex(register_pc),
        })
    if len(page_factory_owners) != page_factories["summary"]["factory_count"]:
        raise AssertionError("page factory address count disagrees with catalogue summary")

    base_pane_constructor = disassemble_function(md, segments, db, 0x192D3D0)
    scissor_factory = disassemble_function(md, segments, db, 0x14C89C0)
    scissor_aux_constructor = disassemble_function(md, segments, db, 0x14C8A90)
    swkbd_padding_flag_writer = disassemble_function(md, segments, db, SWKBD_PADDING_FLAG_WRITER)
    shared_ui_bit4_helper = disassemble_function(md, segments, db, SHARED_UI_BIT4_HELPER)
    pane_copy_constructor = disassemble_function(md, segments, db, PANE_COPY_CONSTRUCTOR)
    pane_render_state_update = disassemble_function(md, segments, db, PANE_RENDER_STATE_UPDATE)
    pane_user_data_update = disassemble_function(md, segments, db, PANE_USER_DATA_UPDATE)
    pane_child_flag_propagator = disassemble_function(md, segments, db, PANE_CHILD_FLAG_PROPAGATOR)
    raw_pane_flag_copy_candidate = disassemble_function(md, segments, db, PANE_LAYOUT_FLAG_PARSER)
    pane_layout_flag_wrapper = disassemble_function(md, segments, db, PANE_LAYOUT_FLAG_WRAPPER)
    pane_type_dispatcher = disassemble_function(md, segments, db, PANE_TYPE_DISPATCHER)
    scr1_pane_constructor = disassemble_function(md, segments, db, SCR1_PANE_CONSTRUCTOR)
    scr1_pane_render = disassemble_function(md, segments, db, SCR1_PANE_RENDER)
    scissor_context_dispatch = disassemble_function(md, segments, db, SCISSOR_CONTEXT_DISPATCH)
    uimgr_constructor = disassemble_function(md, segments, db, UIMGR_CONSTRUCTOR)
    uimgr_precalc_callback = disassemble_function(md, segments, db, UIMGR_PRECALC_CALLBACK)
    draw_event_constructor = disassemble_function(md, segments, db, DRAW_EVENT_CONSTRUCTOR)
    draw_event_callback = disassemble_function(md, segments, db, DRAW_EVENT_CALLBACK)
    draw_particle_pre_callback = disassemble_function(md, segments, db, DRAW_PARTICLE_PRE_CALLBACK)
    draw_particle_post_callback = disassemble_function(md, segments, db, DRAW_PARTICLE_POST_CALLBACK)
    draw_user_callback = disassemble_function(md, segments, db, DRAW_USER_CALLBACK)
    draw_particle_render = disassemble_function(md, segments, db, DRAW_PARTICLE_RENDER)
    base_flag_rows = instruction_rows(base_pane_constructor, [0x192D3F8, 0x192D43C, 0x192D440])
    scissor_base_call_rows = instruction_rows(scissor_factory, [0x14C89F0, 0x14C8A34])
    scissor_factory_dispatch_rows = instruction_rows(scissor_factory, [
        0x14C89F8, 0x14C89FC, 0x14C8A08, 0x14C8A10, 0x14C8A14,
        0x14C8A18, 0x14C8A20, 0x14C8A3C, 0x14C8A40, 0x14C8A4C,
        0x14C8A50, 0x14C8A54, 0x14C8A58, 0x14C8A78,
    ])
    scissor_aux_constructor_rows = instruction_rows(scissor_aux_constructor, [
        0x14C8B00, 0x14C8B04, 0x14C8B08, 0x14C8B0C, 0x14C8B10,
        0x14C8B34, 0x14C8B38, 0x14C8B3C, 0x14C8B40, 0x14C8B44,
        0x14C8B50, 0x14C8B58,
    ])
    swkbd_padding_flag_rows = instruction_rows(swkbd_padding_flag_writer, [
        0x14C81D0, 0x14C81F0, 0x14C81F8, 0x14C8200,
        0x14C82F0, 0x14C82F8, 0x14C82FC,
        0x14C833C, 0x14C8340, 0x14C834C,
        0x14C8378, 0x14C837C, 0x14C8388,
    ])
    shared_ui_bit4_rows = instruction_rows(shared_ui_bit4_helper, [
        0x14C8490, 0x14C8494, 0x14C8498, 0x14C849C, 0x14C84A0, 0x14C84A4,
    ])
    pane_copy_flag_rows = instruction_rows(pane_copy_constructor, [
        0x192E2D4, 0x192E2D8, 0x192E2DC, 0x192E2E0, 0x192E2FC,
        0x192E300, 0x192E364, 0x192E368, 0x192E36C, 0x192E370,
    ])
    pane_render_state_rows = instruction_rows(pane_render_state_update, [
        0x192EDDC, 0x192EDEC, 0x192EE1C, 0x192EE34, 0x192EE38,
        0x192EE3C, 0x192EE40, 0x192EE58, 0x192EE60, 0x192EE64,
        0x192EE68, 0x192EE6C, 0x192EE78, 0x192F018, 0x192F01C,
        0x192F024, 0x192F028, 0x192F02C,
    ])
    pane_user_data_rows = instruction_rows(pane_user_data_update, [
        0x192F4E0, 0x192F4E4, 0x192F588, 0x192F594,
        0x192F5D0, 0x192F5D4, 0x192F5D8,
    ])
    pane_child_flag_rows = instruction_rows(pane_child_flag_propagator, [
        0x192FE40, 0x192FE44, 0x192FE48, 0x192FE54, 0x192FE58,
        0x192FE5C, 0x192FE68, 0x192FE74, 0x192FE84, 0x192FE8C,
    ])
    raw_flag_copy_rows = instruction_rows(raw_pane_flag_copy_candidate, [
        0x192D648, 0x192D64C, 0x192D8B0, 0x192D8B4,
    ])
    raw_flag_copy_direct_callers = db.execute(
        "select count(*) from direct_calls where target_va=?", (PANE_LAYOUT_FLAG_PARSER,)
    ).fetchone()[0]
    pane_layout_wrapper_callers = callsite_context(db, PANE_LAYOUT_FLAG_WRAPPER)
    pane_layout_wrapper_to_parser = instruction_rows(pane_layout_flag_wrapper, [0x192D460, 0x192D480])
    pane_type_case_rows = instruction_rows(pane_type_dispatcher, [
        0x1921424, 0x1921428, 0x192142C, 0x1921430,
        0x1921434, 0x192143C, 0x1921448, 0x1921454,
    ])
    scr1_constructor_rows = instruction_rows(scr1_pane_constructor, [0x1937290, 0x1937298, 0x193729C, 0x19372A0])
    scr1_render_rows = instruction_rows(scr1_pane_render, [
        0x19372C4, 0x19372D4, 0x19372D8, 0x1937494, 0x19374B4, 0x19374C8,
        0x193750C,
    ])
    scissor_context_dispatch_rows = instruction_rows(scissor_context_dispatch, [
        0x18FAF80, 0x18FAFC4, 0x18FAFC8, 0x18FAFD0, 0x18FAFD4,
    ])
    uimgr_constructor_rows = instruction_rows(uimgr_constructor, [
        0x1DD3BF8, 0x1DD3C08, 0x1DD3C54, 0x1DD3C5C,
        0x1DD3D08, 0x1DD3D10, 0x1DD3D14, 0x1DD3D18,
        0x1DD3D30, 0x1DD3D34,
    ])
    uimgr_precalc_rows = instruction_rows(uimgr_precalc_callback, [
        0x1DD3E7C, 0x1DD3E80, 0x1DD3E84, 0x1DD3E88,
        0x1DD3E8C, 0x1DD3E90, 0x1DD3E94, 0x1DD3E98,
        0x1DD3E9C, 0x1DD3EA0, 0x1DD3EA4, 0x1DD3EA8,
        0x1DD3EAC, 0x1DD3EB0, 0x1DD3EB4, 0x1DD3EB8,
        0x1DD3EBC, 0x1DD3EC0, 0x1DD3EC4, 0x1DD3EC8,
        0x1DD3ECC, 0x1DD3ED0, 0x1DD3EDC,
    ])
    draw_event_constructor_rows = instruction_rows(draw_event_constructor, [
        0x1C80364, 0x1C80368, 0x1C803C4, 0x1C803D0, 0x1C803D4,
        0x1C80410, 0x1C80420, 0x1C80424, 0x1C80460, 0x1C80470, 0x1C80474, 0x1C804B0,
        0x1C804B8, 0x1C804C0, 0x1C804C4, 0x1C804CC,
        0x1C804D4, 0x1C804DC, 0x1C804E4, 0x1C804EC,
        0x1C804F4,
    ])
    draw_event_callback_rows = instruction_rows(draw_event_callback, [
        0x1C805E4, 0x1C805F4, 0x1C80604, 0x1C80670,
        0x1C80688, 0x1C806A4, 0x1C806AC,
    ])
    draw_particle_callback_rows = {
        hex(DRAW_PARTICLE_PRE_CALLBACK): instruction_rows(draw_particle_pre_callback, [
            0x1C806B0, 0x1C806B4, 0x1C806B8,
        ]),
        hex(DRAW_PARTICLE_POST_CALLBACK): instruction_rows(draw_particle_post_callback, [
            0x1C806C0, 0x1C806C4, 0x1C806C8,
        ]),
        hex(DRAW_USER_CALLBACK): instruction_rows(draw_user_callback, [
            0x1C806E4, 0x1C806F4, 0x1C8076C, 0x1C80778,
            0x1C8077C, 0x1C80784,
        ]),
    }
    draw_particle_render_rows = instruction_rows(draw_particle_render, [
        0x1C80874, 0x1C8087C, 0x1C80A3C, 0x1C80A50,
        0x1C80DD0, 0x1C80DE4,
    ])
    visibility_label_refs = {}
    for label in ("VisibleOn", "VisibleOff"):
        visibility_label_refs[label] = [
            hex(row[0]) for row in db.execute(
                "select distinct function_va from string_refs where text=? order by function_va",
                (label,),
            )
        ]
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
    pane_store_inventory = pane_field_store_inventory(md, segments, db)
    bounded_ui_store_inventory = bounded_ui_offset_store_inventory(md, segments, db)
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
    root_page_factory_method = disassemble_function(md, segments, db, ROOT_PAGE_FACTORY_METHOD)
    root_page_constructor = disassemble_function(md, segments, db, ROOT_PAGE_CONSTRUCTOR)
    root_page_teardown_method = disassemble_function(md, segments, db, ROOT_PAGE_TEARDOWN_METHOD)
    root_page_transition_method = disassemble_function(md, segments, db, ROOT_PAGE_TRANSITION_METHOD)
    page_tree_process_method = disassemble_function(md, segments, db, PAGE_TREE_PROCESS_METHOD)
    page_state_set_one = disassemble_function(md, segments, db, PAGE_STATE_SET_ONE)
    page_state_set_two = disassemble_function(md, segments, db, PAGE_STATE_SET_TWO)
    page_state_set_three = disassemble_function(md, segments, db, ROOT_PAGE_STATE_SET_THREE)
    page_state_precalc_transition = disassemble_function(md, segments, db, PAGE_STATE_PRECALC_TRANSITION)
    page_state_precalc_cleanup = disassemble_function(md, segments, db, 0x1DA4960)
    page_state_precalc_callback_48 = disassemble_function(md, segments, db, 0x1DA4A20)
    page_state_precalc_callback_50 = disassemble_function(md, segments, db, 0x1DA4B20)
    page_state_precalc_callback_update = disassemble_function(md, segments, db, 0x1DA4C20)
    page_start = disassemble_function(md, segments, db, 0x1DA7030)
    page_start_wait = disassemble_function(md, segments, db, 0x1DA7150)
    page_stop = disassemble_function(md, segments, db, 0x1DA4890)
    page_finish = disassemble_function(md, segments, db, 0x1DA43D0)
    page_close_request = disassemble_function(md, segments, db, 0x1DA4210)
    root_page_dispatch = disassemble_function(md, segments, db, ROOT_PAGE_EVENT_METHOD)
    root_page_dispatch_alt = disassemble_function(md, segments, db, ROOT_PAGE_EVENT_METHOD_ALT)

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
    root_page_factory_rows = instruction_rows(root_page_factory_method, [
        0x1DD42F4, 0x1DD42F8, 0x1DD4300, 0x1DD4308, 0x1DD430C, 0x1DD4314,
    ])
    root_page_constructor_rows = instruction_rows(root_page_constructor, [0x1DA5BBC])
    root_page_state_helper_rows = instruction_rows(page_state_set_one, [0x1DA40A0, 0x1DA40A4])
    root_page_state_helper_rows.extend(instruction_rows(page_state_set_two, [0x1DA40B0, 0x1DA40B4]))
    root_page_state_helper_rows.extend(instruction_rows(page_state_set_three, [0x1DA5C60, 0x1DA5C64]))
    root_page_state_helper_rows.extend(instruction_rows(page_state_precalc_transition, [
        0x1DA47A4, 0x1DA47B0, 0x1DA47B4, 0x1DA47B8, 0x1DA47BC,
    ]))
    root_page_teardown_rows = instruction_rows(root_page_teardown_method, [0x1DD4394])
    root_page_transition_rows = instruction_rows(root_page_transition_method, [0x1DD43A4])
    page_tree_process_rows = instruction_rows(page_tree_process_method, [
        0x1DD4420, 0x1DD4428, 0x1DD4430, 0x1DD4438,
    ])
    root_page_dispatch_rows = instruction_rows(root_page_dispatch, [0x1DD4578])
    root_page_dispatch_alt_rows = instruction_rows(root_page_dispatch_alt, [0x1DD4540])
    page_state_instruction_rows = {
        "start_if_state_one_then_store_two": instruction_rows(page_start, [0x1DA703C, 0x1DA704C]),
        "start_wait_may_store_one": instruction_rows(page_start_wait, [0x1DA7168, 0x1DA7348]),
        "stop_store_four": instruction_rows(page_stop, [0x1DA48AC]),
        "finish_store_site": instruction_rows(page_finish, [0x1DA453C]),
        "close_request_store_sites": instruction_rows(page_close_request, [
            0x1DA42BC, 0x1DA42F0, 0x1DA436C, 0x1DA43B4,
        ]),
    }
    page_state_instruction_rows["root_page_virtual_slot_five_stores_three"] = instruction_rows(
        page_state_set_three, [0x1DA5C60, 0x1DA5C64]
    )
    page_state_instruction_rows["precalc_transition_state_three_to_four"] = instruction_rows(
        page_state_precalc_transition, [0x1DA47A4, 0x1DA47B0, 0x1DA47B4, 0x1DA47B8, 0x1DA47BC]
    )
    page_state_instruction_rows["precalc_recursive_state_work"] = instruction_rows(
        page_state_precalc_transition, [
            0x1DA47C0, 0x1DA47D4, 0x1DA47DC, 0x1DA47E0, 0x1DA47E4,
            0x1DA47E8, 0x1DA47EC, 0x1DA481C, 0x1DA4820, 0x1DA4828,
            0x1DA4864, 0x1DA486C, 0x1DA4874, 0x1DA4878, 0x1DA487C,
            0x1DA4888,
        ]
    )
    page_state_instruction_rows["precalc_child_callback_slots"] = {
        "cleanup_recursion": instruction_rows(page_state_precalc_cleanup, [
            0x1DA49DC, 0x1DA49E0, 0x1DA49E4, 0x1DA49E8, 0x1DA4A04,
        ]),
        "slot_plus_0x48": instruction_rows(page_state_precalc_callback_48, [
            0x1DA4A20, 0x1DA4A24, 0x1DA4A28, 0x1DA4AC0,
            0x1DA4AE4, 0x1DA4AE8, 0x1DA4B10,
        ]),
        "slot_plus_0x50": instruction_rows(page_state_precalc_callback_50, [
            0x1DA4B20, 0x1DA4B24, 0x1DA4B28, 0x1DA4BC0,
            0x1DA4BE4, 0x1DA4BE8, 0x1DA4C10,
        ]),
        "slot_plus_0xa0_and_plus_0x58": instruction_rows(page_state_precalc_callback_update, [
            0x1DA4C34, 0x1DA4C38, 0x1DA4C3C, 0x1DA4C40, 0x1DA4C44,
            0x1DA4C48, 0x1DA4C4C, 0x1DA4C50, 0x1DA4C54, 0x1DA4C58,
        ]),
    }
    root_page_constructor_strings = [row[0] for row in db.execute(
        "select text from string_refs where function_va=? order by text",
        (ROOT_PAGE_CONSTRUCTOR,),
    )]
    uimgr_constructor_strings = [row[0] for row in db.execute(
        "select text from string_refs where function_va=? order by text",
        (UIMGR_CONSTRUCTOR,),
    )]
    draw_event_strings = [row[0] for row in db.execute(
        "select text from string_refs where function_va=? order by text",
        (DRAW_EVENT_CONSTRUCTOR,),
    )]
    draw_event_string_addresses = {
        "drawLayout": "0x29b87db",
        "drawParticlePreLayout": "0x2995a7f",
        "drawParticlePostLayout": "0x2949843",
        "drawUser": "0x29b87e6",
    }
    draw_event_literals = {
        label: read_c_string(segments, int(address, 16))
        for label, address in draw_event_string_addresses.items()
    }
    root_page_direct_call_count = db.execute(
        "select count(*) from direct_calls where target_va=?",
        (ROOT_PAGE_FACTORY_METHOD,),
    ).fetchone()[0]
    root_page_event_callers = {
        hex(target): callsite_context(db, target)
        for target in (ROOT_PAGE_EVENT_METHOD, ROOT_PAGE_EVENT_METHOD_ALT)
    }
    wrapper_callsite_count = len(pane_layout_wrapper_callers)
    if wrapper_callsite_count != 8:
        raise AssertionError("generic Pane layout parser wrapper caller count changed")
    expected_draw_labels = {
        "drawLayout", "drawParticlePreLayout", "drawParticlePostLayout", "drawUser"
    }
    if not expected_draw_labels.issubset(set(draw_event_literals.values())):
        raise AssertionError("UIMgr draw event label crosswalk changed")
    if not {"UIMgr", "UIMgr::PreCalc"}.issubset(set(uimgr_constructor_strings)):
        raise AssertionError("UIMgr constructor/precalc string references changed")
    flag_copy_pointer_membership = pointer_inventory["memberships"][hex(PANE_LAYOUT_FLAG_PARSER)]
    root_method_pointer_membership = pointer_inventory["memberships"][hex(ROOT_PAGE_FACTORY_METHOD)]
    root_state_three_pointer_membership = pointer_inventory["memberships"][hex(ROOT_PAGE_STATE_SET_THREE)]
    scr1_render_pointer_membership = pointer_inventory["memberships"][hex(SCR1_PANE_RENDER)]
    pane_render_state_membership = pointer_inventory["memberships"][hex(PANE_RENDER_STATE_UPDATE)]
    shared_ui_bit4_callers = callsite_context(db, SHARED_UI_BIT4_HELPER)
    shared_ui_bit4_caller_memberships = {
        caller["owner"]: pointer_inventory["memberships"][caller["owner"]]
        for caller in shared_ui_bit4_callers
        if caller["owner"] is not None
    }
    if root_page_direct_call_count != 0 or len(root_method_pointer_membership) != 1:
        raise AssertionError("RootPage creator method direct-call/pointer-sequence evidence changed")
    if "RootPage" not in root_page_constructor_strings:
        raise AssertionError("RootPage constructor token string reference missing")
    if flag_copy_pointer_membership:
        raise AssertionError("Generic Pane layout parser unexpectedly appears in pointer inventory")
    if len(root_state_three_pointer_membership) != 1 or root_state_three_pointer_membership[0]["slot_index"] != 5:
        raise AssertionError("RootPage slot-five state helper membership changed")
    if len(scr1_render_pointer_membership) != 1 or scr1_render_pointer_membership[0]["slot_index"] != 20:
        raise AssertionError("BFLYT SCR1 renderer vtable membership changed")
    pane_update_slots = {
        row["sequence_start"]: row["slot_index"]
        for row in pane_render_state_membership
        if row["sequence_start"] in ("0x313a398", "0x31a2ff8")
    }
    if pane_update_slots != {"0x313a398": 19, "0x31a2ff8": 19}:
        raise AssertionError("ScissorPane/SCR1 Pane state-update slot membership changed")
    if len(shared_ui_bit4_callers) != 5 or set(shared_ui_bit4_caller_memberships) != {
        hex(owner) for owner in SHARED_UI_BIT4_CALLERS
    }:
        raise AssertionError("shared UI bit-4 helper callsite set changed")
    if any(
        not memberships or any(row["slot_index"] != 7 for row in memberships)
        for memberships in shared_ui_bit4_caller_memberships.values()
    ):
        raise AssertionError("shared UI bit-4 helper caller slot membership changed")

    source_hash = hashlib.sha256(NSO.read_bytes()).hexdigest()
    result = {
        "schema": "acnh.ui_hud_runtime_followup.page_input_renderer_static.v3",
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
            "factory_state_sequence": {
                "field_offset_bytes": "0x48",
                "state_one_helper": hex(0x1DA8210),
                "state_one_store_helper": hex(0x1DA40A0),
                "state_one_value": 1,
                "common_page_initializer": hex(0x1144600),
                "registration_helper": hex(PAGE_REGISTER),
                "registration_store_helper": hex(0x1DA40B0),
                "registration_value": 2,
                "factory_count_checked": len(state_sequence_rows),
                "all_factories_call_same_helpers_in_order": True,
                "branch_instruction_count_between_first_and_last_helper_calls": state_sequence_branch_count,
                "helper_callsites_share_a_straight_line_region": state_sequence_branch_count == 0,
                "callsite_samples": state_sequence_rows[:3],
                "observation": "All 135 catalogued factory functions have indexed direct calls ordered state-one helper -> common page initializer -> registration helper, with no conditional or unconditional branch between those callsites. This is the construction/registration region only; the field has no recovered open/active/visible name or scheduler edge.",
            },
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
            "root_page_creation_and_state": {
                "creator_method": hex(ROOT_PAGE_FACTORY_METHOD),
                "creator_method_direct_callers": root_page_direct_call_count,
                "relocated_pointer_sequence_membership": root_method_pointer_membership,
                "pointer_sequence_classification_limit": "The shared inventory labels this as a relocated code-pointer sequence, not automatically a C++ vtable; the slot membership is proven, the virtual dispatch interpretation is not.",
                "root_page_constructor": {
                    "function": hex(ROOT_PAGE_CONSTRUCTOR),
                    "string_refs": root_page_constructor_strings,
                    "allocation_size_bytes": "0x1c8",
                    "owner_object_member_offset": "0x448",
                    "vptr_cell": "0x3321ed0",
                    "vptr_relocation_target": "0x31dcbf0",
                    "vptr_address_point": "0x31dcc00",
                    "slot_five_target_membership": root_state_three_pointer_membership,
                    "constructor_state_initialization": {
                        "field_offset_bytes": "0x48",
                        "instruction": root_page_constructor_rows[0],
                        "observed_value": 0,
                    },
                },
                "creator_instructions": root_page_factory_rows,
                "state_helper_instructions": root_page_state_helper_rows,
                "observed_state_sequence": [0, 1, 2, 3],
                "slot_five_state_three_helper": {
                    "function": hex(ROOT_PAGE_STATE_SET_THREE),
                    "sequence_membership": root_state_three_pointer_membership,
                    "instructions": page_state_instruction_rows["root_page_virtual_slot_five_stores_three"],
                    "observation": "The RootPage constructor installs the relocated sequence at 0x31dcc00; its slot 5 (+0x28) target is this two-instruction helper, which stores 3 at +0x48. The existing state-2 helper branches through the same slot, completing 0→1→2→3.",
                },
                "observation": "The method allocates 0x1c8 bytes, calls the constructor whose native string reference is RootPage, stores that object at +0x448, then calls helpers which write +0x48 values 1 and 2 in order. The state-2 helper dispatches through vtable slot +0x28 to the RootPage slot-5 helper, which stores 3. This is a concrete construction transition; the integers remain unnamed states.",
                "registration_limit": "This method calls the state-2 helper 0x1da40b0, but not the collection-inserting wrapper 0x1da8220. The available instructions do not show whether another path attaches this RootPage elsewhere.",
            },
            "uimgr_precalc_callback": {
                "manager_constructor": hex(UIMGR_CONSTRUCTOR),
                "constructor_string_refs": uimgr_constructor_strings,
                "manager_vptr_cell": "0x3322938",
                "manager_vptr_relocation_target": "0x31e0b90",
                "manager_vptr_address_point": "0x31e0ba0",
                "manager_slot_10_root_page_creator": {
                    "target": hex(ROOT_PAGE_FACTORY_METHOD),
                    "membership": root_method_pointer_membership,
                    "observation": "The relocated UIMgr address point places 0x1dd4090 in slot 10; this method constructs and stores RootPage. UIMgr::PreCalc is a separately stored callback member, not the slot-10 method.",
                },
                "callback_global_cell": "0x3322948",
                "callback_relocation_target": hex(UIMGR_PRECALC_CALLBACK),
                "callback_pointer_stored_at_manager_offset": "0x390",
                "callback_object_self_offset": "0x388",
                "callback_label_field_offset": "0x378",
                "constructor_instructions": uimgr_constructor_rows,
                "callback_instructions": uimgr_precalc_rows,
                "callback_direct_call_count": db.execute(
                    "select count(*) from direct_calls where target_va=?", (UIMGR_PRECALC_CALLBACK,)
                ).fetchone()[0],
                "observed_behavior": "The UIMgr constructor builds a descriptor bearing the indexed string UIMgr::PreCalc, stores the relocated callback pointer at manager +0x390 and self at +0x388 under its callback lock. The callback increments manager +0x500, calls 0x1da4960 on RootPage +0x448, calls 0x1da4790(root, 1), then dispatches additional helpers over RootPage and tail-calls 0x1da4c20. In 0x1da4790, state 3 calls 0x1da4890, which stores state 4; the helper then performs its mask-gated +0x50/+0x54 work and recurses over child pages.",
                "precalc_child_tree_callback_family": {
                    "callback_call_instructions": uimgr_precalc_rows,
                    "helper_facts": [
                        "0x1da4960 recursively visits children and sends states 5 through 7 to finish helper 0x1da43d0.",
                        "0x1da4790 changes state 3 through 0x1da4890 to 4, then uses the callback's input flag and a global mask against page +0x4c to update +0x50/+0x54 and recursively visit children.",
                        "0x1da4a20 returns at state 3; otherwise it recurses and invokes each page's vtable slot +0x48.",
                        "0x1da4b20 returns at state 3; otherwise it recurses and invokes each page's vtable slot +0x50.",
                        "0x1da4c20 checks byte +0x50; when set, it invokes vtable slots +0xa0 and +0x58, then recursively visits children.",
                    ],
                    "instruction_rows": page_state_instruction_rows["precalc_child_callback_slots"],
                    "observation": "These calls prove the work performed by the registered PreCalc callback and its state/child callback fanout. They do not identify which external system invokes the callback or its cadence.",
                },
                "limit": "The named UIMgr::PreCalc callback is the static producer path that can advance RootPage +0x48 from 3 to 4. Its callback has no indexed direct caller; the relocation cell and descriptor establish registration, not the external dispatcher, actual tick cadence, or ordering relative to draw events.",
            },
            "draw_event_child_tree_lifecycle": {
                "registration_constructor": hex(DRAW_EVENT_CONSTRUCTOR),
                "shared_registration_target": "0x1a24ef0",
                "direct_indexed_string_refs": draw_event_strings,
                "constructor_string_literals": draw_event_literals,
                "constructor_string_addresses": draw_event_string_addresses,
                "constructor_instructions": draw_event_constructor_rows,
                "registrations": [
                    {
                        "event_index": 0, "member_offset": "0x1040", "label": "drawParticlePreLayout",
                        "callback_cell": "0x331d448", "callback_relocation_target": hex(DRAW_PARTICLE_PRE_CALLBACK),
                    },
                    {
                        "event_index": 1, "member_offset": "0x10a0", "label": "drawLayout",
                        "callback_cell": "0x331d438", "callback_relocation_target": hex(DRAW_EVENT_CALLBACK),
                    },
                    {
                        "event_index": 2, "member_offset": "0x1100", "label": "drawParticlePostLayout",
                        "callback_cell": "0x331d450", "callback_relocation_target": hex(DRAW_PARTICLE_POST_CALLBACK),
                    },
                    {
                        "event_index": 3, "member_offset": "0x1160", "label": "drawUser",
                        "callback_cell": "0x331d458", "callback_relocation_target": hex(DRAW_USER_CALLBACK),
                    },
                ],
                "registration_call_order": [1, 0, 2, 3],
                "callback_instructions": {
                    hex(DRAW_EVENT_CALLBACK): draw_event_callback_rows,
                    "particle_event_thunks": draw_particle_callback_rows,
                },
                "particle_draw_helper": {
                    "function": hex(DRAW_PARTICLE_RENDER),
                    "instructions": draw_particle_render_rows,
                    "observation": "The pre/post thunks set event IDs 10 and 11 and tail-branch here. This helper performs the particle draw/context path; it does not direct-call the RootPage event wrappers.",
                },
                "user_draw_callback_observation": "The drawUser callback follows a distinct gated path and invokes a vtable slot +0xb8 on the global user-draw manager. Its dynamic target is not resolved to RootPage.",
                "layout_draw_callback_observation": "Only drawLayout uses 0x1c805d0: it checks a global gate and input byte +0x202; values 1 and 2 build an event context and call 0x1dd4560, while other values tail-call 0x1dd44c0 with a null second context. Both manager methods reach 0x1da4db0 on RootPage +0x448.",
                "child_tree_observation": "0x1da4db0 returns immediately for RootPage state 3; otherwise it recursively visits the child list and calls each page child's virtual slot +0x78 with the event context.",
                "limit": "All four registration labels, relocation cells, and callback targets are mapped. Only drawLayout is statically connected to the RootPage child tree; draw-particle events use 0x1c80850, and drawUser calls an unresolved manager slot. The meaning of drawLayout input values 1/2 and the scheduler ordering/cadence are not established.",
            },
            "root_page_dispatch_and_stop_methods": {
                "event_method_callers": root_page_event_callers,
                "event_method_instructions": {
                    hex(ROOT_PAGE_EVENT_METHOD): root_page_dispatch_rows,
                    hex(ROOT_PAGE_EVENT_METHOD_ALT): root_page_dispatch_alt_rows,
                },
                "event_helper": {
                    "function": hex(0x1DA4DB0),
                    "observed": "Returns immediately for numeric state 3; otherwise walks the child list recursively and calls each page object's virtual slot +0x78 with the supplied context.",
                },
                "teardown_method": {
                    "function": hex(ROOT_PAGE_TEARDOWN_METHOD),
                "sequence_membership": pointer_inventory["memberships"][hex(ROOT_PAGE_TEARDOWN_METHOD)],
                    "tail_call_instruction": root_page_teardown_rows[0],
                    "target": hex(0x1DA4890),
                },
                "transition_method": {
                    "function": hex(ROOT_PAGE_TRANSITION_METHOD),
                    "sequence_membership": pointer_inventory["memberships"][hex(ROOT_PAGE_TRANSITION_METHOD)],
                    "tail_call_instruction": root_page_transition_rows[0],
                    "target": hex(0x1DA43D0),
                },
                "limit": "The event callbacks are directly connected into the RootPage child tree, and the manager methods have exact sequence-slot membership. The named UIMgr::PreCalc callback advances RootPage state 3→4, but external scheduler cadence/order, open-close call routes, and semantic labels for numeric states remain unresolved.",
            },
            "numeric_page_state_handlers": {
                "field_offset_bytes": "0x48",
                "instruction_rows": page_state_instruction_rows,
                "handlers": [
                    {
                        "function": "0x1da7030",
                        "observed": "Only proceeds when +0x48 is 1, stores 2, constructs a pending-work mask at +0x854, and signals selected child resources.",
                    },
                    {
                        "function": "0x1da7150",
                        "observed": "Reads states 0, 2, and 5; state 2 checks pending child-resource conditions and can store state 1 at 0x1da7348. Other branches wait or return according to these numeric values.",
                    },
                    {
                        "function": "0x1da4890",
                        "observed": "Stores state 4, resets +0x54 to -1, calls virtual slots +0x80 and +0x38, recursively processes children, then calls slot +0x88.",
                    },
                    {
                        "function": "0x1da4210",
                        "observed": "Close-request path moves child/self states through numeric 4/6 to 5, state 3 to 2 after list removal, 5 to 7, and state 2 to 8 after virtual slot +0x30; it then invokes 0x1da43d0.",
                    },
                    {
                        "function": "0x1da43d0",
                        "observed": "Finishes states 3 through 7 recursively: state 3 returns; 4/6 become 3; 5 is unlinked and becomes 2; 7 is unlinked, calls slot +0x30, and becomes 8. It clears +0x50 and resets +0x54 to -1 on processed nodes.",
                    },
                ],
                "manager_process_method": {
                    "function": hex(PAGE_TREE_PROCESS_METHOD),
                    "sequence_membership": pointer_inventory["memberships"][hex(PAGE_TREE_PROCESS_METHOD)],
                    "observed_instructions": page_tree_process_rows,
                    "observation": "This method calls 0x1da4cd0 on the RootPage at owner +0x448, then calls 0x1da7030 and 0x1da7150 on a separate page object at owner +0x420. The former recursively dispatches child callbacks through slot +0x70; the latter two perform the numeric state/resource processing described above.",
                    "limit": "No indexed direct call reaches this method; its slot membership is an indirect-call candidate, not proof of scheduler cadence.",
                },
                "semantic_limit": "These are observed numeric transitions and callback effects only. No recovered string or runtime capture names the states as open, active, closing, or visible.",
            },
            "status": "Factory construction/insertion, the RootPage 0→1→2→3 construction route, the UIMgr::PreCalc 3→4 transition, its draw-event child callback path, and several further numeric page-state transitions are statically mapped. Getter-to-layout-loader handoff, numeric state names, external scheduler cadence/order, modal order, focus restoration, and live instance behavior remain unresolved.",
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
            "constructor_defaults_and_source_candidates": {
                "scissor_factory": hex(0x14C89C0),
                "auxiliary_scissor_constructor": hex(0x14C8A90),
                "base_pane_constructor": hex(0x192D3D0),
                "factory_to_base_call_instructions": scissor_base_call_rows,
                "factory_to_base_call_observation": "Both allocation branches in the ScissorPane factory call the base Pane constructor. The subsequent auxiliary constructor at 0x14c8a90 initializes the auxiliary object; it is not the factory-to-base callsite.",
                "factory_vptr_and_flag_writes": {
                    "global_cell": "0x330ee30",
                    "relocated_target": "0x313a388",
                    "address_point": "0x313a398",
                    "slot_20_target": hex(GENERIC_PANE_RENDER),
                    "slot_21_target": hex(SCISSOR_RENDER_CALLBACK),
                    "instruction_rows": scissor_factory_dispatch_rows,
                    "branch_observation": "Both allocation branches install the same address point and initialize the +0xe0 bounds-enable byte and +0xf0..+0xfc bounds. The non-null-input branch ORs bit 3 into pane +0x58; the null-input branch does not. Base +0x58 begins at 0x11, so this bit-3 write alone does not meet the generic renderer's 0x81 mask gate.",
                },
                "auxiliary_restore_object": {
                    "constructor": "0x14c8a90",
                    "vptr_cell": "0x330ee38",
                    "relocated_target": "0x313a478",
                    "address_point": "0x313a488",
                    "owner_member_offset": "0xd8",
                    "instruction_rows": scissor_aux_constructor_rows,
                    "observation": "The constructor creates the auxiliary object attached at parent +0xd8 with a distinct dispatch sequence; this is the restore child path, separate from the ScissorPane object's own slot-21 push callback.",
                },
                "additional_ui_flag_producers": {
                    "swkbd_padding_nodes": {
                        "function": hex(SWKBD_PADDING_FLAG_WRITER),
                        "direct_callers": callsite_context(db, SWKBD_PADDING_FLAG_WRITER),
                        "indexed_string_refs": [row[0] for row in db.execute(
                            "select text from string_refs where function_va=? order by text",
                            (SWKBD_PADDING_FLAG_WRITER,),
                        )],
                        "instructions": swkbd_padding_flag_rows,
                        "observed_write": "The Swkbd page's N_Padding lookup walks three returned child nodes and ORs bit 4 into each node's +0x58 byte while also updating +0x30 position data. It does not write +0x5c or set bits 0/7 required by the generic renderer's 0x81 gate.",
                        "scissor_link": "This helper's only indexed direct caller is 0x1508390 in the Swkbd page path. No static call or pointer-sequence edge ties its N_Padding targets to either BFLYT SCR1 or the 0x14c89c0 ScissorPane factory.",
                    },
                    "shared_ui_bit4_helper": {
                        "function": hex(SHARED_UI_BIT4_HELPER),
                        "direct_callers": shared_ui_bit4_callers,
                        "helper_pointer_sequence_membership": pointer_inventory["memberships"][hex(SHARED_UI_BIT4_HELPER)],
                        "caller_pointer_sequence_memberships": shared_ui_bit4_caller_memberships,
                        "instructions": shared_ui_bit4_rows,
                        "observed_write": "Copies the low 32 bits of a source vtable slot at +0x50 into destination +0x50, then ORs bit 4 into destination +0x58.",
                        "limit": "Five direct callsites come from functions occupying slot 7 in relocated UI pointer sequences, but those sequence owners are unnamed. This helper only sets +0x58 bit 4, not the generic renderer's required bits 0/7, and no callsite is tied to the ScissorPane or SCR1 instance path.",
                    },
                    "bounded_ui_method_store_scan": {
                        **bounded_ui_store_inventory,
                        "pane_flag_candidate_functions": [
                            hex(SWKBD_PADDING_FLAG_WRITER),
                            hex(SHARED_UI_BIT4_HELPER),
                            "0x14c89c0",
                            "0x14c8a90",
                        ],
                        "static_configuration_candidates": [
                            {"function": "0x14c8760", "base": "global 0x370f000"},
                            {"function": "0x14c8890", "base": "global 0x370f000"},
                            {"function": "0x14c8eb0", "base": "global 0x370f000"},
                            {"function": "0x14c93b0", "base": "global 0x370f000"},
                        ],
                        "derived_payload_candidate": {
                            "function": "0x14c9ac0",
                            "string_refs": [row[0] for row in db.execute(
                                "select distinct text from string_refs where function_va=? order by text",
                                (0x14C9AC0,),
                            )],
                            "observation": "The matching +0x58 stores are paired float payload writes in the Gradation parameter loader; no evidence treats them as the base Pane flag byte.",
                        },
                    },
                    "scope_limit": "The generic Pane family and these identified UI-range writers are classifiable. A whole-image exact-offset scan yields thousands of +0x58/+0x5c stores across unrelated structures; offsets alone cannot prove additional Pane/ScissorPane producers.",
                },
                "base_flag_initialization_instructions": base_flag_rows,
                "observed_base_values": {
                    "+0x58": "0x11",
                    "+0x5b..+0x5c": 0,
                },
                "gate_comparison": "The base defaults alone fail the generic renderer callback gate: +0x58 lacks bit 7 and +0x5c lacks bit 4. The BFLYT pane parser writes these fields from layout bytes, and the SCR1 render method has its own +0x58 bit-0 and +0x5a gates before clipping.",
                "pane_layout_flag_conversion": {
                    "type_dispatcher": hex(PANE_TYPE_DISPATCHER),
                    "type_dispatcher_direct_callers": db.execute(
                        "select count(*) from direct_calls where target_va=?", (PANE_TYPE_DISPATCHER,)
                    ).fetchone()[0],
                    "scr1_case_instructions": pane_type_case_rows,
                    "scr1_tag_ascii": "scr1",
                    "scr1_allocation_size_bytes": "0xe0",
                    "scr1_factory_callsite": "0x1921454",
                    "scr1_factory_target": hex(SCR1_PANE_CONSTRUCTOR),
                    "scr1_constructor_instructions": scr1_constructor_rows,
                    "layout_flag_wrapper": {
                        "function": hex(PANE_LAYOUT_FLAG_WRAPPER),
                        "direct_callers": pane_layout_wrapper_callers,
                        "direct_call_count": wrapper_callsite_count,
                        "instructions": pane_layout_wrapper_to_parser,
                        "observation": "This wrapper sets x3=x1 and tail-branches to the parser. The SCR1 constructor calls it directly, so its input layout record reaches the parser even though the parser itself is a tail target rather than a direct-call target.",
                    },
                    "layout_flag_parser": {
                        "function": hex(PANE_LAYOUT_FLAG_PARSER),
                        "instructions": raw_flag_copy_rows,
                        "input_byte_+0x08_to_object_+0x58": True,
                        "input_byte_+0x0b_to_object_+0x5c": True,
                        "conditional_edits": [
                            "The parser may replace +0x58 bit 1 from the layout/runtime halfword at context +0x42 when the context predicate passes.",
                            "The +0x5c bit-2 path can clear bit 2 while preserving other source bits.",
                            "Later in the same parser, bit 4 is ORed into +0x58.",
                        ],
                        "indexed_direct_caller_count": raw_flag_copy_direct_callers,
                        "relocated_pointer_sequence_membership": flag_copy_pointer_membership,
                        "observation": "This is a layout parser reached through the indexed wrapper's tail branch, not an unlinked copy candidate. The SCR1 type case calls the wrapper through constructor 0x1937280.",
                    },
                    "runtime_pane_state_update_method": {
                        "function": hex(PANE_RENDER_STATE_UPDATE),
                        "direct_callers": callsite_context(db, PANE_RENDER_STATE_UPDATE),
                        "vtable_memberships": pane_render_state_membership,
                        "scissor_factory_slot_index": pane_update_slots["0x313a398"],
                        "scr1_slot_index": pane_update_slots["0x31a2ff8"],
                        "instructions": pane_render_state_rows,
                        "observation": "The typed ScissorPane and BFLYT SCR1 pointer sequences both place 0x192edc0 at slot 19 (+0x98). On its ordinary path it updates alpha +0x5a, recursively invokes child slot +0x98, then sets +0x58 bit 7 and +0x5c bit 4; an early branch can clear +0x58 bit 7 and return. The SCR1 renderer later tests +0x58 bit 0 and +0x5a; generic Pane rendering tests +0x58 mask 0x81 and +0x5c bit 4.",
                        "limit": "The type-specific constructor installs slot 19 and this function has indexed direct callers, but no recovered static edge establishes when slot 19 runs on an SCR1/ScissorPane instance or with which live inputs.",
                    },
                    "other_generic_pane_writers": {
                        "clone_function": hex(PANE_COPY_CONSTRUCTOR),
                        "clone_instructions": pane_copy_flag_rows,
                        "clone_observation": "The clone copies source +0x58/+0x5c bytes, then clears source-derived +0x58 bit 5 and ORs bit 4 into the new Pane.",
                        "user_data_function": hex(PANE_USER_DATA_UPDATE),
                        "user_data_instructions": pane_user_data_rows,
                        "user_data_observation": "This helper sets +0x5c bit 6 on its runtime attribute-data path; it does not set the generic callback gate's bit 4.",
                        "child_flag_function": hex(PANE_CHILD_FLAG_PROPAGATOR),
                        "child_flag_instructions": pane_child_flag_rows,
                        "child_flag_observation": "This recursive child helper may clear +0x58 bit 4 before recomputing child state; bit 4 is separate from generic callback gate mask 0x81.",
                    },
                    "generic_pane_fixed_offset_store_inventory": pane_store_inventory,
                    "pointer_inventory_coverage": {
                        "sequence_count": pointer_inventory["sequence_count"],
                        "entry_count": pointer_inventory["entry_count"],
                    },
                    "limit": "The native SCR1 type switch is identified and its constructor-to-parser flag conversion is direct. The switch itself has no indexed direct caller, so the outer resource-loader dispatch to this switch is not recovered. The family inventory exhausts fixed-displacement stores starting at +0x58/+0x5c and checks adjacent wide-store overlap in the generic Pane code range; whole-image offset-only matches include unrelated objects and cannot safely be treated as Pane writes.",
                },
                "visible_label_strings": visibility_label_refs,
                "visible_label_limit": "VisibleOn/VisibleOff string references are present in page functions, but the available evidence does not connect those labels to writes of these renderer flag bytes or to current callback state.",
            },
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
            "bflty_scr1_scissor_render_path": {
                "bflly_type_dispatcher": hex(PANE_TYPE_DISPATCHER),
                "scr1_constructor": hex(SCR1_PANE_CONSTRUCTOR),
                "scr1_render_method": hex(SCR1_PANE_RENDER),
            "scr1_slot_19_state_update": {
                "target": hex(PANE_RENDER_STATE_UPDATE),
                "membership": [row for row in pane_render_state_membership if row["sequence_start"] == "0x31a2ff8"],
                "observation": "The SCR1 address point places shared Pane state/alpha update 0x192edc0 in slot 19 (+0x98), before its custom renderer at slot 20.",
            },
                "scr1_render_vtable_membership": scr1_render_pointer_membership,
                "scr1_vtable_address_point": "0x31a2ff8",
                "scr1_vtable_relocation_source": {
                    "cell": "0x3318e10",
                    "relocated_value": "0x31a2fe8",
                    "address_point_adjustment": "+0x10",
                    "source": "R_AARCH64_RELATIVE resolution from additional ExeFS main.elf; the NSO file contains an unresolved relocation placeholder.",
                },
                "scr1_slot_20_target": hex(SCR1_PANE_RENDER),
                "scr1_slot_21_target": hex(0x192FC90),
                "render_instructions": scr1_render_rows,
                "generic_child_traversal": {
                    "function": hex(GENERIC_PANE_RENDER),
                    "child_slot_call_instructions": renderer_rows[-4:],
                    "observation": "The generic Pane traversal calls each child object's vtable slot +0xa0; for the SCR1 address point this is slot 20, target 0x19372b0.",
                },
                "scissor_context_dispatch": {
                    "function": hex(SCISSOR_CONTEXT_DISPATCH),
                    "instructions": scissor_context_dispatch_rows,
                    "indexed_direct_callers": callsite_context(db, SCISSOR_CONTEXT_DISPATCH),
                    "observation": "The SCR1 render method calls this helper with one four-integer rectangle before invoking generic Pane rendering, then calls it again with saved context to restore. The helper forwards through a global context object at 0x3317bf8 to an indirect first-slot call; it does not itself contain direct NVN API calls.",
                },
                "flag_to_render_observation": "For a parsed SCR1 pane, slot 20 checks pane +0x58 bit 0 and +0x5a nonzero before computing and submitting a clipped rectangle around the generic Pane render. If either test fails, it calls the generic Pane renderer without this wrapper's clip dispatch. The generic renderer separately tests +0x58 mask 0x81, +0x5c bit 4, +0x5a, and +0x62 bit 1 before its slot +0xa8 callback; the SCR1 slot 21 is a return-only thunk.",
                "separate_scissor_factory_path": {
                    "factory": hex(0x14C89C0),
                    "factory_address_point": "0x313a398",
                    "factory_vptr_and_flag_write_instructions": scissor_factory_dispatch_rows,
                    "auxiliary_constructor_instructions": scissor_aux_constructor_rows,
                    "slot_19_state_update": {
                        "target": hex(PANE_RENDER_STATE_UPDATE),
                        "membership": [row for row in pane_render_state_membership if row["sequence_start"] == "0x313a398"],
                    },
                    "vtable_callback_membership": pointer_inventory["memberships"][hex(SCISSOR_RENDER_CALLBACK)],
                    "generic_renderer_membership": pointer_inventory["memberships"][hex(GENERIC_PANE_RENDER)],
                    "observation": "The separately string-referenced 0x14c89c0 factory installs address point 0x313a398 whose slot 20 is generic renderer 0x192fb20 and slot 21 is callback 0x14c8d30. The BFLYT SCR1 address point instead uses slot 20 0x19372b0 and slot 21 0x192fc90; the static files do not establish that every SCR1 pane is instantiated through 0x14c89c0.",
                },
                "limits": [
                    "The layout-type switch has no indexed direct caller, so the outer archive/resource-loader edge is unresolved.",
                    "The indirect context callback in 0x18faf70 is not statically resolved to the separately mapped NVN setter path; the render wrapper and flag gates are proven, but exact GPU submission and pixel coverage for SCR1 are not.",
                    "The runtime values of source flags, pane transforms, parent clip state, display dimensions, and framebuffer origin were not captured.",
                ],
            },
            "scissor_bounds_selector": {
                "setter_function": hex(SCISSOR_SET_BOUNDS),
                "callback_function": hex(SCISSOR_RENDER_CALLBACK),
                "instructions": {"setter": setter_rows, "callback": callback_rows},
                "observation": "The setter writes 1 to object byte +0xe0 and copies four 32-bit bounds to +0xf0..+0xfc. The callback uses those stored bounds when +0xe0 is nonzero; when zero it computes bounds from the pane transform. Both branches converge on the stack-push call at 0x14c8e44, so +0xe0 selects the bounds source, not whether clipping is applied.",
            },
            "nested_scissor_submission": {
                "trace_artifact": "scissor_static_path.json",
                "coordinate_conversion": scissor_native_path["nvn_state_apis"]["coordinate_conversion"],
                "resolved_nvn_state_apis": scissor_native_path["nvn_state_apis"]["apis"],
                "native_observations": [
                    "0x14c8fe0 intersects incoming left/top/right/bottom bounds with the current top entry; an inverted result becomes a four-zero rectangle. It applies in mode 1, then saves the rectangle if the prior count is at most five (six saved entries). At count six, a further push applies its intersection but exits without saving or incrementing.",
                    "0x14c9250 decrements and reapplies the previous entry in mode 1. On an empty stack it applies a zero rectangle in mode 0.",
                    "0x14c90e0 mode 1 calls 0x19a9c60 for viewport/depth and 0x19a9d50 for scissor; mode 0 calls the combined 0x19a9960 path. Resolved GOT cells match the nvnCommandBufferSetViewport and nvnCommandBufferSetScissor API strings.",
                ],
                "limits": [
                    "The stack fixture uses synthetic memory and stubs rectangle application; it does not execute NVN or compare pixels.",
                    "The native math maps logical bounds into target-pixel bounds only after runtime viewport dimensions and pixel bounds are supplied; framebuffer origin and GPU coverage for the resulting rectangle are unknown.",
                    "The existing fixture does not exercise balanced traversal beyond six saved entries.",
                ],
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
            "RootPage creation and numeric +0x48 transitions are statically mapped, but state names and the outer scheduler dispatch route/cadence are not.",
            "The parent-bound pointer used by hit testing is not named a render clip by native code; its geometric intersection is established, but visual clipping from that field is not.",
            "BFLYT SCR1 flag conversion and its custom clipping render wrapper are statically connected. The external call that enters the pane type switch, the indirect context handler target, live flags/transforms, and SCR1 pixel coverage remain unresolved; the separate 0x14c89c0 ScissorPane callback path is mapped independently.",
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
        "root_page_state_sequence": result["page_loader_and_lifecycle"]["root_page_creation_and_state"]["observed_state_sequence"],
        "root_page_direct_callers": result["page_loader_and_lifecycle"]["root_page_creation_and_state"]["creator_method_direct_callers"],
        "pane_flag_conversion_writer_count": result["static_pane_and_scissor_flags"]["constructor_defaults_and_source_candidates"]["pane_layout_flag_conversion"]["generic_pane_fixed_offset_store_inventory"]["store_count"],
        "scr1_renderer_memberships": len(result["static_pane_and_scissor_flags"]["bflty_scr1_scissor_render_path"]["scr1_render_vtable_membership"]),
        "limits": len(result["limits"]),
    }, indent=2))


if __name__ == "__main__":
    main()
