#!/usr/bin/env python3
"""Trace the statically visible SCR1 type switch, vtable, and loader boundary."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
import struct

from capstone import Cs, CS_ARCH_ARM64, CS_MODE_ARM

ROOT = Path(__file__).resolve().parent.parent
NSO = ROOT / "inputs/additional_exefs/main"
DEFAULT_OUTPUT_ROOT = Path("/workspace/acnh-re/output")
DEFAULT_ROMFS_ROOT = Path("/workspace/downloads/acnh_additional_romfs_2026-11-02/romfs")
DISPATCHER = 0x19212E0
SCR1_CTOR = 0x1937280
SCR1_RENDER = 0x19372B0
PANE_FLAG_PARSER = 0x192D490
PANE_FLAG_WRAPPER = 0x192D450
PANE_STATE_SLOT19 = 0x192EDC0
LAYOUT_FACTORY_ADDRESS_POINT = 0x31A2690
LAYOUT_FACTORY_CELL = 0x31A2208
SCR1_ADDRESS_POINT = 0x31A2FF8
SCR1_VPTR_CELL = 0x3318E10


def function_instructions(md: Cs, segments, db: sqlite3.Connection, address: int):
    row = db.execute("select size from native_functions where va=?", (address,)).fetchone()
    if not row:
        raise ValueError(f"missing native function {address:#x}")
    return list(md.disasm(_read(segments, address, row[0]), address))


def _read(segments, address: int, size: int) -> bytes:
    for base, data in segments:
        if base <= address < base + len(data):
            return data[address - base:address - base + size]
    raise ValueError(f"address outside NSO segments: {address:#x}")


def ins_row(instructions, address: int) -> dict[str, str]:
    for ins in instructions:
        if ins.address == address:
            return {"address": hex(address), "mnemonic": ins.mnemonic, "operands": ins.op_str}
    raise ValueError(f"instruction missing at {address:#x}")


def read_c_string(segments, address: int, size: int = 96) -> str:
    return _read(segments, address, size).split(b"\0", 1)[0].decode("utf-8", "replace")


def adrp_pair_refs(segments, targets: set[int]) -> dict[int, list[int]]:
    """Find executable ADRP+ADD/LDR materializations within the next three words."""
    base, blob = segments[0]
    count = len(blob) // 4
    words = struct.unpack(f"<{count}I", blob[:count * 4])

    def signed(value: int, width: int) -> int:
        return value - (1 << width) if value & (1 << (width - 1)) else value

    refs = {target: [] for target in targets}
    for i, word in enumerate(words):
        if word & 0x9F000000 != 0x90000000:
            continue
        destination = word & 31
        immediate = signed((((word >> 5) & 0x7FFFF) << 2) | ((word >> 29) & 3), 21)
        page = ((base + i * 4) & ~0xFFF) + (immediate << 12)
        for j in range(i + 1, min(count, i + 4)):
            candidate = words[j]
            base_register = (candidate >> 5) & 31
            target = None
            if candidate & 0x7F800000 == 0x11000000 and base_register == destination:
                shift = 12 if candidate & (1 << 22) else 0
                target = page + (((candidate >> 10) & 0xFFF) << shift)
            elif candidate & 0xFFC00000 == 0xF9400000 and base_register == destination:
                target = page + (((candidate >> 10) & 0xFFF) * 8)
            if target in refs:
                refs[target].append(base + j * 4)
    return refs


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT,
                        help="shared read-only index and pointer inventory")
    parser.add_argument("--romfs-root", type=Path, default=DEFAULT_ROMFS_ROOT,
                        help="additional RomFS tree containing the catalogued raw layout resource")
    args = parser.parse_args()

    db_path = args.output_root / "index.sqlite"
    db = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    segments = __import__("re_helpers").nso_segments(NSO)
    md = Cs(CS_ARCH_ARM64, CS_MODE_ARM)
    md.detail = True

    from ui_hud_page_layout_bindings import relative_relocations
    relocations = relative_relocations(segments)
    pointer_arrays = json.loads((args.output_root / "binary/code_pointer_arrays.json").read_text())
    layout_factory_array = next(
        row for row in pointer_arrays if int(row["start_va"], 16) == LAYOUT_FACTORY_ADDRESS_POINT
    )
    layout_slots = [entry["target_va"] for entry in layout_factory_array["entries"]]
    expected_layout_slots = ["0x19194f0", "0x1922280", "0x19212e0", "0x1921e30", "0x1921ed0", "0x19215b0"]
    if layout_slots != expected_layout_slots:
        raise AssertionError("LayoutPaneFactory address point slots changed")

    dispatcher = function_instructions(md, segments, db, DISPATCHER)
    constructor = function_instructions(md, segments, db, SCR1_CTOR)
    factory_group_method = function_instructions(md, segments, db, 0x1921ED0)
    parser_wrapper = function_instructions(md, segments, db, PANE_FLAG_WRAPPER)
    state_update = function_instructions(md, segments, db, PANE_STATE_SLOT19)

    direct_call_count = db.execute(
        "select count(*) from direct_calls where target_va=? and instruction in ('B','BL')",
        (DISPATCHER,),
    ).fetchone()[0]
    if direct_call_count != 0:
        raise AssertionError("SCR1 dispatcher unexpectedly gained indexed direct callers")

    rel_target = relocations.get(LAYOUT_FACTORY_CELL)
    scr1_vtable_target = relocations.get(SCR1_VPTR_CELL)
    if rel_target != LAYOUT_FACTORY_ADDRESS_POINT:
        raise AssertionError("LayoutPaneFactory cell no longer resolves to the recorded address point")
    if scr1_vtable_target != SCR1_ADDRESS_POINT - 0x10:
        raise AssertionError("SCR1 constructor vtable cell changed")

    scissor_records = json.loads(
        (ROOT / "output/ui_hud/section_semantics.json").read_text()
    )["bounding_scissor_sections"]
    scr1_assets = [row for row in scissor_records if row["pane"]["type"] == "scr1"]
    if len(scr1_assets) != 2 or {row["source"] for row in scr1_assets} != {
        "LMyDesignEditCanvas.Nin_NX_NVN.zs"
    }:
        raise AssertionError("catalogued SCR1 asset records changed")
    raw_layout_path = args.romfs_root / "Layout/LMyDesignEditCanvas.Nin_NX_NVN.zs"
    raw_layout = None
    if raw_layout_path.is_file():
        raw_layout_bytes = raw_layout_path.read_bytes()
        raw_layout = {
            "relative_path": "Layout/LMyDesignEditCanvas.Nin_NX_NVN.zs",
            "sha256": hashlib.sha256(raw_layout_bytes).hexdigest(),
            "bytes": len(raw_layout_bytes),
            "container_signature": raw_layout_bytes[:4].hex(),
            "compression": "Zstandard .zs resource; decoded BFLYT records are represented in the asset catalogue.",
        }

    code_refs = adrp_pair_refs(segments, {LAYOUT_FACTORY_CELL, LAYOUT_FACTORY_ADDRESS_POINT,
                                          SCR1_VPTR_CELL})
    if len(code_refs[SCR1_VPTR_CELL]) != 2:
        raise AssertionError("expected two known SCR1 vptr-cell references as scanner control")

    state_slot19_memberships = []
    for array in pointer_arrays:
        address_point = int(array["start_va"], 16)
        slot19 = array["entries"][19]["target_va"] if len(array["entries"]) > 19 else None
        if slot19 != hex(PANE_STATE_SLOT19):
            continue
        typeinfo = relocations.get(address_point - 8)
        name_va = relocations.get(typeinfo + 8) if typeinfo is not None else None
        state_slot19_memberships.append({
            "address_point": hex(address_point),
            "typeinfo_name": read_c_string(segments, name_va) if name_va is not None else None,
        })

    resolver_string = db.execute(
        "select string_va from string_refs where function_va=? and text=?",
        (0x18FB3F0, "nvnCommandBufferSetScissors"),
    ).fetchone()
    if not resolver_string:
        raise AssertionError("SetScissors resolver name missing")

    result = {
        "schema": "acnh.ui_hud_runtime_followup.scr1_loader_static.v1",
        "source": {
            "game_build": "ACNH 1.0.0",
            "module": "ExeFS main",
            "main_sha256": hashlib.sha256(NSO.read_bytes()).hexdigest(),
            "evidence_kind": "AArch64 disassembly, relative relocations, read-only function/call index, code-pointer inventory, and committed BFLYT catalogue. No synchronized live capture.",
        },
        "layout_pane_factory": {
            "type_name": read_c_string(segments, 0x2A3BA52),
            "vtable_cell": hex(LAYOUT_FACTORY_CELL),
            "resolved_address_point": hex(rel_target),
            "address_point_slots": [
                {"index": index, "target": target}
                for index, target in enumerate(layout_slots)
            ],
            "observations": [
                "The typeinfo string identifies the six-entry relocated code-pointer sequence as nn::ui2d::LayoutPaneFactory.",
                "Slot 2 is the BFLYT pane-type dispatcher 0x19212e0; slot 4 is 0x1921ed0; slot 5 is 0x19215b0.",
                "No indexed direct B/BL caller reaches 0x19212e0. The address point occurs in the pointer inventory, but this main image has no ADRP+ADD/LDR code reference to its vtable cell or address point. The scan is limited to direct page-relative address materialization patterns; it cannot exclude runtime-filled references or use by another module.",
            ],
            "slot4_indirect_candidate": {
                "method": "0x1921ed0",
                "callsite": ins_row(factory_group_method, 0x1921F20),
                "receiver_register": "x22, copied from incoming argument x1",
                "dispatch_offset_bytes": "0x10",
                "receiver_note": "The method also traverses the x22 list at +0x20/+0x28 after this call. Static input flow does not establish that x22 has LayoutPaneFactory type or that this slot-2 call resolves to 0x19212e0.",
            },
        },
        "scr1_type_switch": {
            "dispatcher": hex(DISPATCHER),
            "tag_bytes": "scr1",
            "allocation_size_bytes": "0xe0",
            "constructor": hex(SCR1_CTOR),
            "constructor_callsite": "0x1921454",
            "constructor_calls": [
                ins_row(dispatcher, 0x1921454),
                ins_row(constructor, 0x1937290),
            ],
            "pane_parser": {
                "wrapper": hex(PANE_FLAG_WRAPPER),
                "parser": hex(PANE_FLAG_PARSER),
                "wrapper_tail_branch": ins_row(parser_wrapper, 0x192D480),
            },
            "vptr": {
                "global_cell": hex(SCR1_VPTR_CELL),
                "relocated_vtable_start": hex(scr1_vtable_target),
                "address_point": hex(SCR1_ADDRESS_POINT),
                "slots": {
                    "19_update": hex(relocations[SCR1_ADDRESS_POINT + 19 * 8]),
                    "20_render": hex(relocations[SCR1_ADDRESS_POINT + 20 * 8]),
                    "21": hex(relocations[SCR1_ADDRESS_POINT + 21 * 8]),
                },
                "slot19_target": hex(PANE_STATE_SLOT19),
                "slot19_context_flow": {
                    "function_argument_x1": "Copied unchanged to x20 and forwarded to child slot-19 calls; the function does not dereference/name this argument.",
                    "function_argument_x2": "Copied to x21 and read at byte offsets +0x1d, +0x1f and float offset +0x18; native field semantics remain unnamed.",
                    "recursive_virtual_calls": [
                        ins_row(state_update, 0x192EED8),
                        ins_row(state_update, 0x192EEEC),
                        ins_row(state_update, 0x192EFB0),
                        ins_row(state_update, 0x192EFC4),
                    ],
                    "recursive_observation": "Slot 19 walks pane child links and dispatches child vtable +0x98, preserving x1/x2 and forwarding the normalized update flag. No separate context callback target is resolved inside this method.",
                },
            },
            "slot19_pointer_inventory": {
                "sequence_count": len(state_slot19_memberships),
                "memberships": state_slot19_memberships,
                "observation": "The common update target occurs in slot 19 in multiple relocated code-pointer sequences. Four sequences carry recoverable RTTI names; unnamed sequences remain classified only by pointer membership.",
            },
            "catalogued_instances": [
                {
                    "archive": row["source"],
                    "layout_member": row["layout_member"],
                    "layout": row["layout"],
                    "pane_name": row["pane"]["name"],
                    "section_offset": row["section_offset"],
                    "serialized_visible": row["pane"]["visible"],
                    "serialized_translate": row["pane"]["translate"],
                    "serialized_size": row["pane"]["size"],
                }
                for row in scr1_assets
            ],
            "raw_resource": raw_layout,
        },
        "resolved_scissor_submission": {
            "wrapper": "0x18faf70",
            "resolver": "0x18fb3f0",
            "exact_api_name": "nvnCommandBufferSetScissors",
            "api_name_string_va": hex(resolver_string[0]),
            "resolver_callsite": "0x18fe1e0",
            "got_cell": "0x3317bf8",
            "wrapper_indirect_callsite": "0x18fafd8",
            "scr1_renderer_calls": ["0x1937494", "0x19374c8"],
            "observation": "The SCR1 renderer submits/restores scissor rectangles through NVN SetScissors around generic Pane rendering. Static submission is proven; live context pointer, first index, rectangle count/data, viewport origin, and pixel coverage are not.",
        },
        "remaining_static_boundary": {
            "outer_resource_loader": "The main-image evidence proves the scr1 type-switch arm, constructor, parser, installed slot-19 method, and catalogued LMyDesignEditCanvas records. It does not identify the resource-loader callsite/object that invokes the LayoutPaneFactory virtual dispatcher or prove which archive instance is active.",
            "precalc_scheduler": "UIMgr::PreCalc callback 0x1dd3e70 is registered by 0x1dd3bd0 and calls RootPage processing, but it has no indexed direct caller; external cadence and order relative to draw events are unresolved.",
            "runtime_blocker": ("The raw layout resource and both SCR1 records are present and catalogued. The static evidence does not identify which resource-loader object invokes LayoutPaneFactory at runtime or capture a live rendered frame."
                                if raw_layout else "The selected RomFS root has no raw layout resource; the local catalogue still contains two decoded SCR1 records, but neither an active loader instance nor a live rendered frame is captured."),
            "capture_needed": [
                "On ACNH 1.0.0, load LMyDesignEditCanvas and capture the archive/layout key, loader call stack, LayoutPaneFactory object address/vptr, and the actual indirect target at 0x1921f20 or equivalent callsite.",
                "At 0x19212e0 record w3 tag and x0-x6; on the scr1 branch record allocated object, source bytes, and returned object pointer; then record the same instance at slot 19 (x0-x3), including children and parent pointers.",
                "For the frame that renders S_Scissor_00/01, capture PreCalc and draw callback timestamps/order, pane flags/transforms, 0x18faf70 x0-x3 arguments, resolved NVN SetScissors rectangle array, logical viewport dimensions, target pixel bounds, framebuffer origin, and a matching GPU/frame capture.",
            ],
        },
        "scanner_control": {
            "known_scr1_vptr_cell_code_refs": [hex(x) for x in code_refs[SCR1_VPTR_CELL]],
            "layout_factory_cell_code_refs": [hex(x) for x in code_refs[LAYOUT_FACTORY_CELL]],
            "layout_factory_address_point_code_refs": [hex(x) for x in code_refs[LAYOUT_FACTORY_ADDRESS_POINT]],
            "scope": "ADRP followed within three instructions by ADD or 64-bit LDR in the executable main segment.",
        },
    }
    destination = ROOT / "output/ui_hud/runtime_followup/scr1_loader_static.json"
    destination.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"artifact": str(destination),
                      "layout_factory_slot2": layout_slots[2],
                      "scr1_slot19": result["scr1_type_switch"]["vptr"]["slots"]["19_update"],
                      "catalogued_scr1_instances": len(scr1_assets),
                      "set_scissors_resolved": result["resolved_scissor_submission"]["got_cell"],
                      "outer_loader": "runtime-only gap"}, indent=2))


if __name__ == "__main__":
    main()
