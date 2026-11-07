#!/usr/bin/env python3
"""Exercise break-state callbacks and SaveProc path helpers with bounded native stubs."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from nso_sandbox import NSO_SHA256, Sandbox  # noqa: E402

NSO = ROOT / "inputs/additional_exefs/main"
OUT = ROOT / "output/gameplay/tool_mechanics_followup/tool_state_callback_native.json"
EVENTFLOW_ENTRYPOINTS = {
    0: "ToolBreak_Axe",
    1: "ToolBreak_Scoop",
    2: "ToolBreak_Watering",
    3: "ToolBreak_Net",
    4: "ToolBreak_Slingshot",
    5: "ToolBreak_FishingRod",
}


def qword(sb: Sandbox, address: int, value: int) -> None:
    sb.uc.mem_write(address, struct.pack("<Q", value))


def make_handler_context(sb: Sandbox) -> dict:
    state = sb.alloc(0x3000)
    actor = sb.alloc(0x3000)
    vfloats = [sb.alloc(4), sb.alloc(4)]
    for ptr in vfloats:
        sb.uc.mem_write(ptr, struct.pack("<f", 1.0))
    vtables = [sb.alloc(0x200), sb.alloc(0x200)]
    methods = (0xF62E90, 0xF62E94)
    for subobject_offset, vtable, method in zip((0x12F0, 0x20B0), vtables, methods):
        qword(sb, actor + subobject_offset, vtable)
        qword(sb, vtable + 0xF0, method)

    labels = ("Axe", "Scoop", "Watering", "Net", "Slingshot", "FishingRod")
    label_ptrs = []
    for label in labels:
        ptr = sb.alloc(len(label) + 1)
        sb.uc.mem_write(ptr, label.encode("ascii") + b"\0")
        label_ptrs.append(ptr)
    label_table = sb.alloc(len(label_ptrs) * 8)
    sb.uc.mem_write(label_table, b"".join(struct.pack("<Q", ptr) for ptr in label_ptrs))
    return {
        "state": state,
        "actor": actor,
        "vfloats": vfloats,
        "labels": labels,
        "label_table": label_table,
    }


def run_player_tool_break_update(sb: Sandbox, context: dict) -> list[dict]:
    state, actor = context["state"], context["actor"]
    index = {"value": 0}
    dispatched = []

    for va, return_value in (
        (0xDC80B0, 0), (0xDA7B10, state), (0x15BBC00, 0), (0xDA7550, actor),
        (0x7BE330, 0), (0x7D57A0, 0), (0x7BC0B0, 0), (0x7D3F60, 0),
        (0xDC80A0, 1), (0x7D57C0, 1), (0xDA72E0, 0), (0x15BBBC0, 0),
        (0xF58D00, 1), (0xF589E0, 0), (0x7D6970, 0), (0xDAA280, 0),
        (0xDAA970, 0), (0x7D6C90, 0), (0x7CF9A0, 0), (0x7D6C60, 0),
        (0x7D5780, 0), (0xDD5F90, 0), (0xDD6B40, 0), (0xDB14D0, 0),
    ):
        sb.stub(va, lambda _sb, value=return_value: value)
    sb.stub(0xF62E90, lambda _sb: context["vfloats"][0])
    sb.stub(0xF62E94, lambda _sb: context["vfloats"][1])
    sb.stub(0x7E30F0, lambda _sb: context["label_table"])
    sb.stub(0xA9C290, lambda _sb: 1)
    sb.stub(0xA9D0B0, lambda _sb: index["value"])

    def format_toolbreak(sb_: Sandbox) -> int:
        dest, format_ptr, label_ptr = sb_.reg("x0"), sb_.reg("x1"), sb_.reg("x2")
        format_text = sb_.read(format_ptr, 128).split(b"\0")[0]
        label = sb_.read(label_ptr, 128).split(b"\0")[0]
        result = format_text.replace(b"%s", label)
        sb_.uc.mem_write(dest, result + b"\0")
        return dest

    sb.stub(0x1990820, format_toolbreak)
    # The game helper uses a large-count string copy convention here; the target
    # buffer is already assembled by the controlled formatter above.
    sb.stub(0x220E430, lambda sb_: sb_.reg("x0"))

    def event_dispatch(sb_: Sandbox) -> int:
        stack = sb_.reg("sp")
        event_name = sb_.read(stack + 0x78, 128).split(b"\0")[0].decode("ascii")
        descriptor = sb_.reg("x1")
        dispatched.append({
            "event_entrypoint": event_name,
            "event_descriptor_va": hex(descriptor),
            "event_descriptor_prefix_hex": sb_.read(descriptor, 24).hex(),
            "synthetic_item_family_index": index["value"],
        })
        return 1

    sb.stub(0xDB1070, event_dispatch)

    cases = []
    for family_index, entrypoint in EVENTFLOW_ENTRYPOINTS.items():
        index["value"] = family_index
        for offset, data in (
            (0x1024, b"\x01"), (0x89C, b"\0"),
            (0x898, struct.pack("<I", 0)), (0xF00, struct.pack("<I", 0)),
        ):
            sb.uc.mem_write(state + offset, data)
        before = len(dispatched)
        sb.call(0xE37A50, (state,))
        events = dispatched[before:]
        if len(events) != 1 or events[0]["event_entrypoint"] != entrypoint:
            raise AssertionError({"family_index": family_index, "expected": entrypoint,
                                  "events": events})
        cases.append({
            "entrypoint_expected": entrypoint,
            "item_family_index_supplied_at_A9D0B0_stub": family_index,
            "event_dispatch": events[0],
            "state_counter_0x898_after": sb.u32(state + 0x898),
            "durability_input_supplied": False,
        })

    return cases


def run_force_break_handler(sb: Sandbox) -> list[dict]:
    state_object = sb.alloc(0x1200)
    actor_context = sb.alloc(0x100)
    control = {"flag_gate": 0, "counter_gate": 0}
    flag_writes = []
    counter_calls = []
    sb.stub(0xDA7B10, lambda _sb: actor_context)
    sb.stub(0xDC80A0, lambda _sb: control["flag_gate"])
    sb.stub(0xDA8BA0, lambda _sb: control["counter_gate"])

    def write_flag(sb_: Sandbox) -> int:
        descriptor = sb_.reg("x1")
        flag_ptr = sb_.u64(descriptor + 8)
        flag_writes.append({
            "flag_name": sb_.read(flag_ptr, 128).split(b"\0")[0].decode("ascii"),
            "value": sb_.reg("x2"),
        })
        return 0

    sb.stub(0xF4E990, write_flag)
    sb.stub(0xE37950, lambda sb_: counter_calls.append({
        "descriptor_va": hex(sb_.reg("x0")), "context_va": hex(sb_.reg("x1"))
    }) or 0)
    for va in (0xDA3FC0, 0xDADFE0, 0xDB4470):
        sb.stub(va, lambda _sb: 0)

    cases = []
    for flag_gate, counter_gate in ((0, 0), (1, 0), (0, 1), (1, 1)):
        control.update(flag_gate=flag_gate, counter_gate=counter_gate)
        before_flags, before_counters = len(flag_writes), len(counter_calls)
        sb.call(0xE37ED0, (state_object,))
        flags = flag_writes[before_flags:]
        counters = counter_calls[before_counters:]
        expected_flags = ([{"flag_name": "ForceToolBreakDemo", "value": 0}]
                          if flag_gate else [])
        if flags != expected_flags or len(counters) != counter_gate:
            raise AssertionError({"flag_gate": flag_gate, "counter_gate": counter_gate,
                                  "flags": flags, "counters": counters})
        cases.append({
            "force_flag_gate": bool(flag_gate),
            "counter_gate": bool(counter_gate),
            "flag_write_boundary": flags,
            "counter_path_calls": counters,
        })
    return cases


def run_save_path_helper(sb: Sandbox) -> dict:
    """Run original f214a0/f21350 with synthetic global/path context and FS stubs."""
    manager = sb.alloc(0x300)
    slot = 3
    sb.uc.mem_write(manager, b"\0" + bytes(0x2FF))
    dirty_address = manager + 0x204 + slot * 8
    sb.uc.mem_write(dirty_address, struct.pack("<I", 0x4000))
    mount_name = sb.alloc(16)
    sb.uc.mem_write(mount_name, b"ACNH_SAVE\0")
    file_name = sb.alloc(32)
    sb.uc.mem_write(file_name, b"PlayerData.bin\0")

    file_path_object = sb.alloc(16)
    file_path_vtable = sb.alloc(0x40)
    qword(sb, file_path_object, file_path_vtable)
    qword(sb, file_path_object + 8, file_name)
    qword(sb, file_path_vtable + 0x18, 0xF62E90)

    lock_vtable = sb.alloc(0x40)
    qword(sb, 0x35E65E8, lock_vtable)
    qword(sb, 0x35E65F0, mount_name)
    qword(sb, lock_vtable + 0x18, 0xF62E94)

    root_path_vtable = sb.alloc(0x40)
    qword(sb, 0x32D0668, root_path_vtable - 0x10)
    qword(sb, root_path_vtable + 0x18, 0xF62E98)
    qword(sb, 0x32D0670, root_path_vtable - 0x10)
    string_path_vtable = sb.alloc(0x40)
    qword(sb, 0x32D1698, string_path_vtable - 0x10)
    qword(sb, string_path_vtable + 0x18, 0xF62E9C)
    prefix = sb.alloc(2)
    sb.uc.mem_write(prefix, b"/\0")
    qword(sb, 0x32D0660, prefix)

    fs_calls = []
    for va in (0xF62E90, 0xF62E94, 0xF62E98, 0xF62E9C, 0x1990780):
        sb.stub(va, lambda _sb: 0)

    def format_path(sb_: Sandbox) -> int:
        descriptor, format_ptr = sb_.reg("x0"), sb_.reg("x1")
        format_text = sb_.read(format_ptr, 128).split(b"\0")[0].decode("ascii")
        left = sb_.read(sb_.reg("x2"), 128).split(b"\0")[0].decode("ascii")
        right = sb_.read(sb_.reg("x3"), 128).split(b"\0")[0].decode("ascii")
        result = format_text.replace("%s", "\0", 1).replace("%s", "\1", 1)
        path = result.replace("\0", left, 1).replace("\1", right, 1)
        capacity = sb_.u32(descriptor + 0x10)
        buffer = sb_.u64(descriptor + 8)
        payload = path.encode("ascii")[:max(capacity - 1, 0)] + b"\0"
        sb_.uc.mem_write(buffer, payload)
        fs_calls.append({"api": "format_path", "format": format_text,
                         "segments": [left, right], "result": path})
        return descriptor

    sb.stub(0x1990820, format_path)

    def mount_save(sb_: Sandbox) -> int:
        name = sb_.read(sb_.reg("x0"), 128).split(b"\0")[0].decode("ascii")
        fs_calls.append({"api": "MountDeviceSaveData", "name": name})
        return 0

    def open_file(sb_: Sandbox) -> int:
        handle_ptr = sb_.reg("x0")
        path = sb_.read(sb_.reg("x1"), 256).split(b"\0")[0].decode("ascii")
        mode = sb_.reg("x2")
        sb_.uc.mem_write(handle_ptr, struct.pack("<Q", 0x12345678))
        fs_calls.append({"api": "OpenFile", "path": path, "mode": mode})
        return 0

    sb.stub(0x220EE60, mount_save)
    sb.stub(0x220EE80, open_file)
    sb.stub(0x220EE90, lambda sb_: fs_calls.append({
        "api": "SetFileSize", "handle": hex(sb_.reg("x0")), "size": sb_.reg("x1")
    }) or 0)
    sb.stub(0x220EEA0, lambda sb_: fs_calls.append({
        "api": "CloseFile", "handle": hex(sb_.reg("x0"))
    }) or 0)

    initial_marker = sb.u32(dirty_address)
    first_result = sb.call(0xF214A0, (manager, file_path_object, 0x4000))
    first_calls = list(fs_calls)
    first_marker = sb.u32(dirty_address)
    second_start = len(fs_calls)
    second_result = sb.call(0xF214A0, (manager, file_path_object, 0x4000))
    second_calls = fs_calls[second_start:]
    final_marker = sb.u32(dirty_address)

    expected_file_ops = ["format_path", "OpenFile", "SetFileSize", "CloseFile"]
    if [call["api"] for call in first_calls[1:]] != expected_file_ops:
        raise AssertionError({"first_calls": first_calls})
    if [call["api"] for call in second_calls] != expected_file_ops:
        raise AssertionError({"second_calls": second_calls})
    if (first_result, second_result, initial_marker, first_marker, final_marker) != (
            1, 1, 0x4000, 0x4000, 0x4000):
        raise AssertionError({"results": [first_result, second_result],
                              "dirty_markers": [initial_marker, first_marker, final_marker]})
    if len([call for call in first_calls if call["api"] == "MountDeviceSaveData"]) != 1:
        raise AssertionError({"mount_not_called_once": first_calls})
    if sb.unknown_imports:
        raise AssertionError({"unknown_imports": sb.unknown_imports})

    return {
        "native_entries": ["0xf214a0", "0xf21350"],
        "synthetic_manager": {
            "contract_note": (
                "The first argument is shaped for f214a0's one-byte mount-once flag. The 0x4000 "
                "word is only a sentinel placed at the known player-slot offset; this does not "
                "establish that the SaveProc object is a player-context/slot-manager object."
            ),
            "param1_first_byte_initial": 0,
            "param1_first_byte_after_first_call": sb.read(manager, 1)[0],
            "dirty_word_offset": hex(0x204 + slot * 8),
            "dirty_word_initial": hex(initial_marker),
            "dirty_word_after_calls": hex(final_marker),
            "slot_word_unchanged": initial_marker == final_marker,
        },
        "first_call_status": first_result,
        "second_call_status": second_result,
        "first_call_file_ops": first_calls,
        "second_call_file_ops": second_calls,
        "operations_not_observed": ["WriteFile", "FlushFile", "slot serialization"],
        "worker_queue_executed": False,
        "bounded_stubs": [
            "mutex/path string virtual methods",
            "0x1990780 string setup",
            "0x1990820 format helper (controlled path formatter)",
            "MountDeviceSaveData/OpenFile/SetFileSize/CloseFile SDK boundaries",
        ],
    }


def run() -> dict:
    if hashlib.sha256(NSO.read_bytes()).hexdigest() != NSO_SHA256:
        raise ValueError("main NSO checksum does not match the bounded helper map")
    sb = Sandbox(NSO)
    context = make_handler_context(sb)
    player_update_cases = run_player_tool_break_update(sb, context)
    force_break_cases = run_force_break_handler(sb)
    save_path = run_save_path_helper(sb)
    result = {
        "schema": "acnh-re/tool-state-callback-native/1",
        "native_main_sha256": NSO_SHA256,
        "evidence_level": "ORIGINAL_HANDLER_AND_FILE_HELPER_BODY_WITH_CONTROLLED_ENGINE_BOUNDARIES",
        "player_tool_break_update": {
            "entry": "0xe37a50",
            "cases": player_update_cases,
            "case_count": len(player_update_cases),
            "dispatch_count": len(player_update_cases),
            "proven": [
                "The original e37a50 body formats and dispatches the Player_ToolBreak entrypoint matching the supplied item-family lookup index for all six family labels.",
                "The exercised +0x1024=1, +0x89c=0 branch reaches the event-dispatch boundary without changing +0x898.",
                "No durability value is supplied to this fixture, and e37a50 has no direct ToolDamage/BreakDamage/remaining-helper call edge.",
            ],
            "limits": [
                "The A9D0B0 item-family index and 7E30F0 label table are controlled fixtures; actual inventory item-to-family lookup is not executed here.",
                "The database/EventFlow executor at DB1070 is stubbed at its dispatch boundary; entrypoint internal actions are covered by the separate static EventFlow fixture.",
                "Animation and actor/vtable context is synthetic; this is not a live player action trace.",
            ],
        },
        "force_tool_break_demo": {
            "entry": "0xe37ed0",
            "cases": force_break_cases,
            "case_count": len(force_break_cases),
            "proven": [
                "The original handler requests ForceToolBreakDemo=0 only when its controlled DC80A0 state gate is enabled.",
                "Its independent DA8BA0 gate controls whether it enters the E37950 counter path.",
                "No durability value or wear writer is used by these branches.",
            ],
            "limits": [
                "DC80A0/DA8BA0 flag and state predicates are controlled stubs, not a persisted flag manager.",
                "F4E990 and E37950 are captured at their mutation/request boundaries; backing flag/save storage is not executed.",
            ],
        },
        "saveproc_file_helpers": save_path,
        "unknown_imports": sb.unknown_imports,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({
        "schema": result["schema"],
        "tool_break_entries_dispatched": result["player_tool_break_update"]["dispatch_count"],
        "force_break_cases": result["force_tool_break_demo"]["case_count"],
        "save_file_ops": [row["api"] for row in save_path["first_call_file_ops"]],
        "dirty_word_unchanged": save_path["synthetic_manager"]["slot_word_unchanged"],
        "output": str(OUT),
    }, indent=2))
    return result


if __name__ == "__main__":
    run()
