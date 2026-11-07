"""Run cConversationHost's early-return entry path from the pinned ACNH NSO.

The fixture supplies the owner/context pointers, an empty native callback
registry, and the nested runtime-context vtable data needed by the body. The
host callback and called NSO helpers run as original code; no function VAs are
stubbed.
"""
from pathlib import Path
import hashlib
import json
import struct
import sys


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))
from nso_sandbox import DEFAULT_NSO, Sandbox  # noqa: E402


NSO_SHA256 = "f8d248109ff72999b4600ae3749f8c7397fb960f7ad3ab8dee3018ae9e14e900"
ELF_SHA256 = "5bf707c3dc5dac0ad9635af7d336ec580f81c3f7876d0f55400d1900e3415d74"
HOST_ENTRY = 0xC0B510
CALLBACK_REGISTRY_CELL = 0x32D3E18
VIEW_GLOBAL_CELL = 0x32D0DE0


def read_u32(sb, address):
    return struct.unpack("<I", sb.read(address, 4))[0]


def read_i32(sb, address):
    return struct.unpack("<i", sb.read(address, 4))[0]


def read_u64(sb, address):
    return struct.unpack("<Q", sb.read(address, 8))[0]


def write_u32(sb, address, value):
    sb.uc.mem_write(address, struct.pack("<I", value & 0xFFFFFFFF))


def write_u64(sb, address, value):
    sb.uc.mem_write(address, struct.pack("<Q", value & 0xFFFFFFFFFFFFFFFF))


def changed_ranges(before, after, base):
    result = []
    i = 0
    while i < len(before):
        if before[i] == after[i]:
            i += 1
            continue
        start = i
        while i < len(before) and before[i] != after[i]:
            i += 1
        result.append({
            "address": hex(base + start),
            "offset": hex(start),
            "before_hex": before[start:i].hex(),
            "after_hex": after[start:i].hex(),
        })
    return result


def make_base_objects(sb):
    owner = sb.alloc(0x11000)
    owner_context = sb.alloc(0x800)
    actor = sb.alloc(0x400)
    runtime_context = sb.alloc(0x800)
    write_u64(sb, owner + 8, owner_context)
    write_u64(sb, owner + 0x10, runtime_context)
    write_u64(sb, owner_context + 0x68, actor)
    write_u32(sb, owner_context + 0x230, 0x77)
    sb.uc.mem_write(actor + 0x278, struct.pack("<f", 1.25))
    sb.uc.mem_write(actor + 0x280, struct.pack("<f", -2.5))
    return owner, owner_context, actor, runtime_context


def reproduce_initial_dispatch_fault():
    """Show the zero-singleton dereference that motivated the empty fixture."""
    from unicorn import UC_HOOK_CODE

    sb = Sandbox()
    owner, _context, _actor, _runtime = make_base_objects(sb)
    singleton_cell = read_u64(sb, CALLBACK_REGISTRY_CELL)
    singleton_before = read_u64(sb, singleton_cell)
    assert singleton_before == 0, hex(singleton_before)
    trace = {}

    def record(uc, address, size, data):
        if address == 0xCA4380:
            x0 = sb.reg("x0")
            trace["dispatcher_x0"] = hex(x0)
            trace["raw_i32_callback_count"] = hex(read_u32(sb, x0 + 0xB70))
            trace["signed_i32_callback_count"] = read_i32(sb, x0 + 0xB70)
        elif address == 0xCA4394:
            trace["faulting_load_base_x20"] = hex(sb.reg("x20"))

    sb.uc.hook_add(UC_HOOK_CODE, record)
    try:
        sb.call(HOST_ENTRY, (owner,), limit=100_000)
    except Exception as exc:  # Unicorn reports the invalid access at the load.
        fault_pc = sb.reg("pc")
        assert fault_pc == 0xCA4394, hex(fault_pc)
        trace.update({
            "error_type": type(exc).__name__,
            "error": str(exc),
            "pc": hex(fault_pc),
            "instruction": "ldr x1, [x20], #8",
            "singleton_cell": hex(singleton_cell),
            "singleton_value_before": hex(singleton_before),
        })
    else:
        raise AssertionError("unprepared singleton unexpectedly completed")
    return trace


def run_controlled_case():
    from unicorn import UC_HOOK_CODE

    sb = Sandbox()
    owner, owner_context, actor, runtime_context = make_base_objects(sb)
    manager = sb.alloc(0x1000)
    nested_context = sb.alloc(0x800)
    vtable = sb.alloc(0x100)

    # The original 0xca4370 dispatcher follows this singleton indirection.
    # Supply a valid manager object with zero callbacks so its native body can
    # return without dispatching unrelated callback entries.
    singleton_cell = read_u64(sb, CALLBACK_REGISTRY_CELL)
    singleton_value_before = read_u64(sb, singleton_cell)
    write_u64(sb, singleton_cell, manager)
    write_u32(sb, manager + 0xB70, 0)

    # cConversationHost's 0xbf7850 helper reads this nested runtime object.
    # The method slot uses the existing one-instruction native RET at 0x3fcc0.
    write_u64(sb, runtime_context + 0x350, nested_context)
    write_u64(sb, nested_context + 0x320, vtable)
    write_u64(sb, vtable + 0x18, 0x3FCC0)

    # Keep the original 0xbf7670 body on its equal-sentinel branch.
    write_u64(sb, runtime_context + 0x3B0, 0x29D4E28)

    before = {
        "owner": sb.read(owner, 0x11000),
        "owner_context": sb.read(owner_context, 0x800),
        "actor": sb.read(actor, 0x400),
        "runtime_context": sb.read(runtime_context, 0x800),
        "nested_context": sb.read(nested_context, 0x800),
    }
    observations = []
    code_entries = set()
    watched_entries = {
        0xC0B510, 0xD355F0, 0xCA4370, 0x3FA40, 0xBF7850, 0xBF7670,
        0xF58890, 0xF5AE70, 0xF57780, 0xF57E10, 0x1990780, 0x1990820,
        0x3FCC0,
    }

    def record(uc, address, size, data):
        if address in watched_entries:
            code_entries.add(address)
        if address == 0xC0B550:
            observations.append({
                "callsite": hex(address),
                "target": "0xd355f0",
                "actor_vector": hex(sb.reg("x0")),
                "actor_vector_offset": hex(sb.reg("x0") - actor),
                "scalar_out": hex(sb.reg("x1")),
                "mode": sb.reg("w2"),
                "context_scalar_source": hex(owner_context + 0x230),
                "context_scalar": hex(read_u32(sb, owner_context + 0x230)),
            })
        elif address == 0xC0B56C:
            observations.append({
                "callsite": hex(address),
                "branch": "null output from original 0x3fa40 view initializer",
                "view_object": hex(sb.reg("x0")),
                "view_bytes": sb.read(sb.reg("x0"), 16).hex(),
                "conversion_scalar": hex(read_u32(sb, sb.reg("x1"))),
            })
        elif address == 0xBF7850:
            observations.append({
                "entry": hex(address),
                "x0_runtime_context": hex(sb.reg("x0")),
                "x1_global_value": hex(sb.reg("x1")),
            })
        elif address == 0xBF7670:
            observations.append({
                "entry": hex(address),
                "x0_runtime_context": hex(sb.reg("x0")),
                "x1": hex(sb.reg("x1")),
                "x2_static_record": hex(sb.reg("x2")),
                "x3_stack_record": hex(sb.reg("x3")),
                "x4_stack_record": hex(sb.reg("x4")),
                "x5_static_record": hex(sb.reg("x5")),
                "x6_mode": sb.reg("w6"),
            })

    sb.uc.hook_add(UC_HOOK_CODE, record)
    returned_x0 = sb.call(HOST_ENTRY, (owner,), limit=100_000)
    after = {
        "owner": sb.read(owner, 0x11000),
        "owner_context": sb.read(owner_context, 0x800),
        "actor": sb.read(actor, 0x400),
        "runtime_context": sb.read(runtime_context, 0x800),
        "nested_context": sb.read(nested_context, 0x800),
    }

    diffs = {
        name: changed_ranges(before[name], after[name], base)
        for name, base in (
            ("owner", owner),
            ("owner_context", owner_context),
            ("actor", actor),
            ("runtime_context", runtime_context),
            ("nested_context", nested_context),
        )
    }
    runtime_fields = [
        {"offset": "+0x380", "type": "u32", "before_hex": before["runtime_context"][0x380:0x384].hex(),
         "after_hex": after["runtime_context"][0x380:0x384].hex(),
         "before_u32": struct.unpack("<I", before["runtime_context"][0x380:0x384])[0],
         "after_u32_hex": hex(read_u32(sb, runtime_context + 0x380))},
        {"offset": "+0x384", "type": "u32", "before_hex": before["runtime_context"][0x384:0x388].hex(),
         "after_hex": after["runtime_context"][0x384:0x388].hex(),
         "after_float": struct.unpack("<f", after["runtime_context"][0x384:0x388])[0]},
        {"offset": "+0x394", "type": "u32", "before_hex": before["runtime_context"][0x394:0x398].hex(),
         "after_hex": after["runtime_context"][0x394:0x398].hex(),
         "after_u32": struct.unpack("<I", after["runtime_context"][0x394:0x398])[0]},
        {"offset": "+0x400", "type": "u64", "before_hex": before["runtime_context"][0x400:0x408].hex(),
         "after_hex": after["runtime_context"][0x400:0x408].hex(),
         "after_u64": hex(struct.unpack("<Q", after["runtime_context"][0x400:0x408])[0])},
    ]

    expected_entries = {
        0xC0B510, 0xD355F0, 0xCA4370, 0x3FA40, 0xBF7850, 0xBF7670,
        0xF58890, 0xF5AE70, 0xF57780, 0xF57E10, 0x1990780, 0x1990820,
        0x3FCC0,
    }
    assert code_entries == expected_entries, sorted(hex(x) for x in code_entries)
    non_runtime_diffs = {name: diffs[name] for name in
                         ("owner", "owner_context", "actor", "nested_context")
                         if diffs[name]}
    assert not non_runtime_diffs, non_runtime_diffs

    runtime_diffs = diffs["runtime_context"]
    assert [(int(row["offset"], 16), row["before_hex"], row["after_hex"]) for row in runtime_diffs] == [
        (0x382, "0000", "80bf"),
        (0x387, "00", "40"),
        (0x394, "00", "06"),
        (0x400, "0000", "feff"),
    ], runtime_diffs

    assert singleton_value_before == 0
    assert read_u64(sb, singleton_cell) == manager
    assert read_u32(sb, manager + 0xB70) == 0
    assert not sb.unknown_imports, sb.unknown_imports
    assert [row for row in observations if row.get("entry") == "0xbf7850"][0]["x1_global_value"] == "0x6"

    return {
        "registered_state": "NpcAIActivityState::cConversationHost",
        "registered_state_index": 60,
        "callback_entry": hex(HOST_ENTRY),
        "execution": "original NSO code; no function VAs stubbed",
        "fixture": {
            "owner": hex(owner),
            "owner_context": hex(owner_context),
            "actor": hex(actor),
            "actor_vector": hex(actor + 0x278),
            "actor_vector_x_f32": 1.25,
            "actor_vector_z_f32": -2.5,
            "context_scalar_u32": {"address": hex(owner_context + 0x230), "value": "0x77"},
            "runtime_context": hex(runtime_context),
            "nested_context": hex(nested_context),
            "vtable_slot": {"address": hex(vtable + 0x18), "target": "0x3fcc0"},
            "runtime_context_equal_sentinel": "0x29d4e28 at +0x3b0",
            "callback_registry": {
                "global_cell": hex(CALLBACK_REGISTRY_CELL),
                "singleton_pointer_cell": hex(singleton_cell),
                "singleton_value_before": hex(singleton_value_before),
                "singleton_value_after": hex(read_u64(sb, singleton_cell)),
                "synthetic_manager": hex(manager),
                "manager_callback_count_offset": "+0xb70",
                "manager_callback_count": 0,
            },
            "view_initializer_global_cell": hex(VIEW_GLOBAL_CELL),
            "view_initializer_inner_pointer": hex(read_u64(sb, read_u64(sb, VIEW_GLOBAL_CELL))),
        },
        "native_observations": observations,
        "owner_changed_ranges": diffs["owner"],
        "owner_context_changed_ranges": diffs["owner_context"],
        "actor_changed_ranges": diffs["actor"],
        "runtime_context_changed_ranges": runtime_diffs,
        "runtime_context_field_before_after": runtime_fields,
        "nested_context_changed_ranges": diffs["nested_context"],
        "native_function_entries_seen": [hex(x) for x in sorted(code_entries)],
        "unknown_imports": sb.unknown_imports,
        "raw_x0_after_callback_return": hex(returned_x0),
    }


def main():
    nso_hash = hashlib.sha256(Path(DEFAULT_NSO).read_bytes()).hexdigest()
    assert nso_hash == NSO_SHA256, nso_hash
    result = {
        "build": {"main_nso_sha256": nso_hash, "main_elf_sha256": ELF_SHA256},
        "initial_unprepared_access": reproduce_initial_dispatch_fault(),
        "controlled_host_entry": run_controlled_case(),
        "limits": [
            "The host entry was called directly; this does not run the NPC state manager or scheduler.",
            "The callback registry was supplied as an empty synthetic object, so no registry callbacks ran.",
            "The nested runtime vtable points to the existing native RET at 0x3fcc0; it is not an ACNH runtime implementation.",
            "The original 0x3fa40 initializer returned a null view, so the host took its early-return branch.",
            "No dialogue topic, message, EventFlow selection, host/guest admission, or network synchronization was exercised.",
        ],
    }
    out = Path(__file__).with_name("host_entry_native.json")
    out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({
        "result": str(out),
        "initial_fault_pc": result["initial_unprepared_access"]["pc"],
        "owner_changes": len(result["controlled_host_entry"]["owner_changed_ranges"]),
        "runtime_context_changes": result["controlled_host_entry"]["runtime_context_changed_ranges"],
        "native_function_entries": len(result["controlled_host_entry"]["native_function_entries_seen"]),
    }, indent=2))


if __name__ == "__main__":
    main()
