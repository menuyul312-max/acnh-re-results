#!/usr/bin/env python3
"""Trace the ScissorPane render callback through native scissor push and restore."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from nso_sandbox import Sandbox  # noqa: E402

NSO = ROOT / "inputs/additional_exefs/main"
OUTPUT = ROOT / "output/ui_hud/runtime_followup/scissorpane_restore_native.json"
SCISSORPANE_VTABLE_GLOBAL = 0x330EE38
SCISSORPANE_RENDER_VTABLE_GLOBAL = 0x330EE30
SCISSOR_CONTEXT_GLOBAL = 0x330ED18
SCISSORPANE_SET_RECT = 0x14C8D00
SCISSORPANE_RENDER_CALLBACK = 0x14C8D30
SCISSORPANE_RESTORE_THUNK = 0x14C8E90
SCISSOR_STACK_PUSH = 0x14C8FE0
SCISSOR_STACK_RESTORE = 0x14C9250
SCISSOR_STATE_APPLY = 0x14C90E0
SCISSORPANE_METHOD_SLOT = 0xA8
GENERIC_PANE_RENDER = 0x192FB20


def relocated_vtable_slot(sb: Sandbox, global_cell: int, slot: int) -> tuple[int, int, int]:
    table_start = sb.u64(global_cell)
    address_point = table_start + 0x10
    return table_start, address_point, sb.u64(address_point + slot)


def set_context_singleton(sb: Sandbox, context: int) -> int:
    holder = sb.alloc(8)
    sb.uc.mem_write(holder, struct.pack("<Q", context))
    sb.uc.mem_write(SCISSOR_CONTEXT_GLOBAL, struct.pack("<Q", holder))
    return holder


def rect_at(sb: Sandbox, address: int) -> tuple[float, float, float, float]:
    return struct.unpack("<4f", sb.read(address, 0x10))


def main() -> None:
    sb = Sandbox(NSO)
    pane_table, pane_vtable, pane_render_entry = relocated_vtable_slot(
        sb, SCISSORPANE_RENDER_VTABLE_GLOBAL, SCISSORPANE_METHOD_SLOT)
    child_table, child_vtable, restore_entry = relocated_vtable_slot(
        sb, SCISSORPANE_VTABLE_GLOBAL, SCISSORPANE_METHOD_SLOT)
    if pane_render_entry != SCISSORPANE_RENDER_CALLBACK:
        raise AssertionError({"pane_vtable": hex(pane_vtable),
                              "render_entry": hex(pane_render_entry)})
    if restore_entry != SCISSORPANE_RESTORE_THUNK:
        raise AssertionError({"child_vtable": hex(child_vtable),
                              "restore_entry": hex(restore_entry)})

    pane = sb.alloc(0x110)
    rect = sb.alloc(0x10)
    sb.uc.mem_write(pane, struct.pack("<Q", pane_vtable))
    setter_cases = [
        (0, (0.0, -10.0, 650.0, 650.0)),
        (0x7F, (-32.5, 17.25, 512.0, 384.0)),
    ]
    for sentinel, values in setter_cases:
        sb.uc.mem_write(pane + 0xE0, bytes([sentinel & 0xFF]))
        sb.uc.mem_write(pane + 0xF0, b"\xA5" * 0x10)
        sb.uc.mem_write(rect, struct.pack("<4f", *values))
        sb.call(SCISSORPANE_SET_RECT, (pane, rect))
        enabled = sb.read(pane + 0xE0, 1)[0]
        actual_rect = sb.read(pane + 0xF0, 0x10)
        expected_rect = struct.pack("<4f", *values)
        if enabled != 1 or actual_rect != expected_rect:
            raise AssertionError({"input_rect": values, "enabled": enabled,
                                  "actual_rect": actual_rect.hex(),
                                  "expected_rect": expected_rect.hex()})

    # Exercise both the pane callback directly and through the generic pane
    # renderer's relocated vtable dispatch at slot +0xa8.
    render_context = sb.alloc(0x80)
    set_context_singleton(sb, render_context)
    render_rect = (10.0, 20.0, 100.0, 120.0)
    sb.uc.mem_write(rect, struct.pack("<4f", *render_rect))
    sb.call(SCISSORPANE_SET_RECT, (pane, rect))
    push_seen = []

    def record_push_call(sandbox):
        push_seen.append({"context": sandbox.reg("x0"),
                          "render_argument": sandbox.reg("x1"),
                          "rectangle": rect_at(sandbox, sandbox.reg("x2"))})
        return 0

    sb.stub(SCISSOR_STACK_PUSH, record_push_call)
    direct_render_argument = 0x1234
    sb.call(SCISSORPANE_RENDER_CALLBACK, (pane, 0x5678, direct_render_argument))
    direct_push = push_seen[-1]
    expected_direct_push = {"context": render_context,
                            "render_argument": direct_render_argument,
                            "rectangle": render_rect}
    if direct_push != expected_direct_push:
        raise AssertionError({"direct_render_push": direct_push,
                              "expected": expected_direct_push})

    # These flags select the ordinary visible-pane branch, which invokes the
    # callback before reaching the empty child-list sentinel.
    sb.uc.mem_write(pane + 0x58, b"\x81")
    sb.uc.mem_write(pane + 0x5A, b"\x01")
    sb.uc.mem_write(pane + 0x5C, b"\x10")
    sb.uc.mem_write(pane + 0x62, b"\x00")
    sb.uc.mem_write(pane + 0x28, struct.pack("<Q", pane + 0x20))
    generic_render_argument = 0x5678
    sb.call(GENERIC_PANE_RENDER, (pane, 0x9ABC, generic_render_argument))
    generic_push = push_seen[-1]
    expected_generic_push = {"context": render_context,
                             "render_argument": generic_render_argument,
                             "rectangle": render_rect}
    if generic_push != expected_generic_push or len(push_seen) != 2:
        raise AssertionError({"generic_render_push": generic_push,
                              "expected": expected_generic_push,
                              "push_callback_cases": len(push_seen)})
    sb.stubs.pop(SCISSOR_STACK_PUSH)

    # Run original stack push/restore instructions. Only the function that
    # applies computed rectangles to renderer state is replaced with a recorder.
    stack_context = sb.alloc(0x80)
    apply_seen = []

    def record_apply_call(sandbox):
        apply_seen.append({"context": sandbox.reg("x0"),
                           "mode_argument": sandbox.reg("x1"),
                           "apply_mode": sandbox.reg("x2"),
                           "rectangle": rect_at(sandbox, sandbox.reg("x3"))})
        return 0

    sb.stub(SCISSOR_STATE_APPLY, record_apply_call)
    first_rect = (0.0, 0.0, 100.0, 100.0)
    first_rect_ptr = sb.alloc(0x10)
    sb.uc.mem_write(first_rect_ptr, struct.pack("<4f", *first_rect))
    sb.call(SCISSOR_STACK_PUSH, (stack_context, 0x31, first_rect_ptr))
    if sb.u32(stack_context + 0x60) != 1 or rect_at(sb, stack_context) != first_rect:
        raise AssertionError({"first_push_depth": sb.u32(stack_context + 0x60),
                              "first_saved_rect": rect_at(sb, stack_context)})

    second_rect = (10.0, 20.0, 90.0, 80.0)
    second_rect_ptr = sb.alloc(0x10)
    sb.uc.mem_write(second_rect_ptr, struct.pack("<4f", *second_rect))
    sb.call(SCISSOR_STACK_PUSH, (stack_context, 0x32, second_rect_ptr))
    if sb.u32(stack_context + 0x60) != 2 or rect_at(sb, stack_context + 0x10) != second_rect:
        raise AssertionError({"nested_push_depth": sb.u32(stack_context + 0x60),
                              "nested_saved_rect": rect_at(sb, stack_context + 0x10)})

    sb.call(SCISSOR_STACK_RESTORE, (stack_context, 0x41))
    if sb.u32(stack_context + 0x60) != 1:
        raise AssertionError({"restore_depth": sb.u32(stack_context + 0x60)})
    restored_previous = apply_seen[-1]
    if (restored_previous["context"] != stack_context
            or restored_previous["mode_argument"] != 0x41
            or restored_previous["apply_mode"] != 1
            or restored_previous["rectangle"] != first_rect):
        raise AssertionError({"restored_previous": restored_previous})

    sb.call(SCISSOR_STACK_RESTORE, (stack_context, 0x42))
    if sb.u32(stack_context + 0x60) != 0:
        raise AssertionError({"empty_restore_depth": sb.u32(stack_context + 0x60)})
    empty_restore = apply_seen[-1]
    if (empty_restore["context"] != stack_context
            or empty_restore["mode_argument"] != 0x42
            or empty_restore["apply_mode"] != 0
            or empty_restore["rectangle"] != (0.0, 0.0, 0.0, 0.0)):
        raise AssertionError({"empty_restore": empty_restore})

    # The second vtable's hook is a thunk into the same restore implementation.
    context_slot = sb.alloc(8)
    captured = []

    def record_restore_call(sandbox):
        captured.append({"context": sandbox.reg("x0"),
                         "forwarded_second_argument": sandbox.reg("x1")})
        return 0

    sb.stub(SCISSOR_STACK_RESTORE, record_restore_call)
    cases = [
        (0x71001000, 0),
        (0x71002000, 0x1234),
        (0x71001000, 0xFFFFFFFF),
    ]
    for context, argument in cases:
        sb.uc.mem_write(SCISSOR_CONTEXT_GLOBAL, struct.pack("<Q", context_slot))
        sb.uc.mem_write(context_slot, struct.pack("<Q", context))
        before = len(captured)
        sb.call(SCISSORPANE_RESTORE_THUNK, (0x71003000, 0xABC, argument))
        observed = captured[before:]
        expected = [{"context": context, "forwarded_second_argument": argument}]
        if observed != expected:
            raise AssertionError({"context": hex(context), "argument": hex(argument),
                                  "observed": observed, "expected": expected})

    if sb.unknown_imports:
        raise AssertionError({"unexpected_imports": sb.unknown_imports})

    result = {
        "schema": "acnh.ui_hud_runtime_followup.scissorpane_restore_native.v2",
        "native_elf_sha256": hashlib.sha256(NSO.read_bytes()).hexdigest(),
        "scissorpane_factory_and_vtable": {
            "factory": "0x14c89c0",
            "factory_label": "ScissorPane",
            "constructor": "0x14c8a90",
            "constructor_allocation_size": "0x110",
            "pane_vtable": {
                "relocation_slot": hex(SCISSORPANE_RENDER_VTABLE_GLOBAL),
                "vtable_start": hex(pane_table),
                "address_point": hex(pane_vtable),
                "render_hook_slot_offset": hex(SCISSORPANE_METHOD_SLOT),
                "slot_target": hex(pane_render_entry),
                "evidence": "The factory stores this relocated address point in the allocated ScissorPane; slot +0xa8 is its native rectangle-to-stack callback at 0x14c8d30."
            },
            "auxiliary_object_vtable": {
                "relocation_slot": hex(SCISSORPANE_VTABLE_GLOBAL),
                "vtable_start": hex(child_table),
                "address_point": hex(child_vtable),
                "restore_hook_slot_offset": hex(SCISSORPANE_METHOD_SLOT),
                "slot_target": hex(restore_entry),
                "evidence": "The constructor installs this second address point on its child/context object; slot +0xa8 is the restore thunk at 0x14c8e90."
            },
            "generic_renderer_dispatch": {
                "entry": hex(GENERIC_PANE_RENDER),
                "observed": "loads object vtable slot +0xa8 and calls it on the visible-pane branch, then visits child panes through slot +0xa0",
                "native_probe_cases": 1,
                "mismatches": 0
            }
        },
        "native_rect_setter": {
            "entry": hex(SCISSORPANE_SET_RECT),
            "enable_byte_offset": "0xe0",
            "rectangle_offsets": ["0xf0", "0xf4", "0xf8", "0xfc"],
            "synthetic_cases": len(setter_cases),
            "mismatches": 0,
            "scope": "The original setter copies the enable byte and four input floats into the synthetic ScissorPane object."
        },
        "scissorpane_render_to_push": {
            "render_callback": hex(SCISSORPANE_RENDER_CALLBACK),
            "push_helper": hex(SCISSOR_STACK_PUSH),
            "native_probe_cases": len(push_seen),
            "mismatches": 0,
            "results": [
                {"path": "direct virtual target", **push_seen[0]},
                {"path": "generic pane renderer through relocated vtable slot +0xa8", **push_seen[1]}
            ],
            "scope": "Original render-callback instructions run with a synthetic pane and context; only the scissor-stack push boundary is stubbed."
        },
        "native_scissor_stack": {
            "push_helper": hex(SCISSOR_STACK_PUSH),
            "restore_helper": hex(SCISSOR_STACK_RESTORE),
            "apply_boundary": hex(SCISSOR_STATE_APPLY),
            "push_cases": 2,
            "restore_cases": 2,
            "apply_boundary_calls": len(apply_seen),
            "mismatches": 0,
            "results": apply_seen,
            "scope": "Original stack push/restore instructions run with synthetic memory; only rectangle application is stubbed, so no NVN/GPU state is executed."
        },
        "restore_thunk": {
            "entry": hex(SCISSORPANE_RESTORE_THUNK),
            "native_instructions": [
                "load context-holder pointer from global cell 0x330ed18",
                "load scissor-context pointer from the holder",
                "forward incoming x2 as x1",
                "tail-branch to 0x14c9250"
            ],
            "stack_restore": hex(SCISSOR_STACK_RESTORE),
            "native_probe_cases": len(cases),
            "mismatches": 0,
            "results": [{"context": hex(ctx), "forwarded_second_argument": hex(arg),
                         "restore_target": hex(SCISSOR_STACK_RESTORE)} for ctx, arg in cases]
        },
        "scope_and_limits": [
            "The ScissorPane setter, render callback, generic renderer dispatch, nested-stack push/restore helpers, and child restore thunk run as original native instructions against synthetic objects/context memory.",
            "The renderer-to-push callback and push/restore-to-apply boundaries are stubbed at function boundaries; no BFLYT archive instance or NVN command is run.",
            "This proves the static ScissorPane instance-to-generic-scissor-context path and stack bookkeeping, but not live pane visibility conditions, shader coverage, framebuffer origin, or pixel parity against a game capture."
        ]
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"artifact": str(OUTPUT),
                      "pane_render_vtable_entry": hex(pane_render_entry),
                      "restore_vtable_entry": hex(restore_entry),
                      "native_checks": len(setter_cases) + len(push_seen) + len(apply_seen) + len(cases),
                      "mismatches": 0}, indent=2))


if __name__ == "__main__":
    main()
