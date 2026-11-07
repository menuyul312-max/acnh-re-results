"""Execute the cConversationHost exit body on its bit-5 cleanup branch."""
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
HOST_EXIT = 0xC0C280
SINGLETON_GLOBAL = 0x32D3E18
VIEW_GLOBAL = 0x32D0DE0
COUNTER_GLOBAL = 0x32D1C88


def read_u16(sb, address):
    return struct.unpack("<H", sb.read(address, 2))[0]


def read_u32(sb, address):
    return struct.unpack("<I", sb.read(address, 4))[0]


def read_u64(sb, address):
    return struct.unpack("<Q", sb.read(address, 8))[0]


def write_u16(sb, address, value):
    sb.uc.mem_write(address, struct.pack("<H", value & 0xFFFF))


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


def main():
    nso_hash = hashlib.sha256(Path(DEFAULT_NSO).read_bytes()).hexdigest()
    assert nso_hash == NSO_SHA256, nso_hash

    sb = Sandbox()
    owner = sb.alloc(0x11000)
    owner_context = sb.alloc(0x800)
    manager = sb.alloc(0x3000)

    # The exit body reads owner_context+0x230 and uses the global singleton
    # object in ca52a0. A circular-list sentinel makes ca52a0's native empty
    # path return without dispatching list items.
    write_u64(sb, owner + 8, owner_context)
    write_u32(sb, owner_context + 0x230, 0x77)
    singleton_cell = read_u64(sb, SINGLETON_GLOBAL)
    singleton_value_before = read_u64(sb, singleton_cell)
    assert singleton_value_before == 0, hex(singleton_value_before)
    write_u64(sb, singleton_cell, manager)
    write_u64(sb, manager + 0x2488, manager + 0x2480)

    initial_flags = 0x1020  # bit 5 selects c0c420; bit 12 is cleared there.
    initial_mask = 0xFFFF
    initial_view_a = 0x55
    initial_view_b = 0x66
    initial_activity_word = 0x99
    write_u64(sb, owner + 0xAB40, initial_flags)
    write_u16(sb, owner + 0xAB10, initial_mask)
    write_u32(sb, owner + 0x7D14, initial_view_a)
    write_u32(sb, owner + 0x7D1C, initial_view_b)
    write_u32(sb, owner + 0x103DC, initial_activity_word)

    before_owner = sb.read(owner, 0x11000)
    before_context = sb.read(owner_context, 0x800)
    before_manager = sb.read(manager, 0x3000)
    observations = []
    code_entries = set()
    native_entries = {HOST_EXIT, 0x3FA40, 0x3FCC0, 0xCEB7D0, 0xCA52A0}

    from unicorn import UC_HOOK_CODE

    def record(uc, address, size, data):
        if address in native_entries:
            code_entries.add(address)
        if address == 0xC0C2A8:
            observations.append({
                "pc": hex(address),
                "activity_flags_before_branch": hex(read_u64(sb, owner + 0xAB40)),
                "branch_bit_5": 1,
            })
        elif address == 0xC0C420:
            observations.append({
                "pc": hex(address),
                "activity_flags_before_clear_bit_12": hex(read_u64(sb, owner + 0xAB40)),
            })
        elif address == 0xCEB7D0:
            observations.append({
                "entry": hex(address),
                "x0": hex(sb.reg("x0")),
                "x0_offset_from_owner": hex(sb.reg("x0") - owner),
                "x1": sb.reg("w1"),
                "halfword_before": hex(read_u16(sb, owner + 0xAB10)),
            })
        elif address == 0xCA52A0:
            x0 = sb.reg("x0")
            observations.append({
                "entry": hex(address),
                "manager": hex(x0),
                "list_end_pointer": hex(read_u64(sb, x0 + 0x2488)),
                "empty_list_sentinel": hex(x0 + 0x2480),
                "condition_is_equal": read_u64(sb, x0 + 0x2488) == x0 + 0x2480,
                "scalar_input": hex(read_u32(sb, sb.reg("x1"))),
            })
        elif address in (0xC0C6E4, 0xC0C390):
            observations.append({
                "pc": hex(address),
                "view_pointer": hex(sb.reg("x20")),
                "view_wrapper_bytes": sb.read(sb.reg("sp") + 8, 16).hex(),
            })
        elif address == 0xC0C3F4:
            counter_pointer = read_u64(sb, COUNTER_GLOBAL)
            observations.append({
                "pc": hex(address),
                "counter_pointer": hex(counter_pointer),
                "counter_value": hex(read_u32(sb, counter_pointer)),
                "target_owner_offset": "+0x7d14",
            })
        elif address == 0xC0C408:
            observations.append({
                "pc": hex(address),
                "activity_flags_before_clear_bit_5": hex(read_u64(sb, owner + 0xAB40)),
            })
        elif address == 0xC0C890:
            counter_pointer = read_u64(sb, COUNTER_GLOBAL)
            observations.append({
                "pc": hex(address),
                "counter_pointer": hex(counter_pointer),
                "counter_value": hex(read_u32(sb, counter_pointer)),
                "target_owner_offset": "+0x7d1c",
            })

    sb.uc.hook_add(UC_HOOK_CODE, record)
    returned_x0 = sb.call(HOST_EXIT, (owner, 0), limit=100_000)

    after_owner = sb.read(owner, 0x11000)
    after_context = sb.read(owner_context, 0x800)
    after_manager = sb.read(manager, 0x3000)
    owner_changes = changed_ranges(before_owner, after_owner, owner)
    context_changes = changed_ranges(before_context, after_context, owner_context)
    manager_changes = changed_ranges(before_manager, after_manager, manager)

    expected_changes = [
        {"offset": "0x7d14", "before_hex": "55", "after_hex": "00"},
        {"offset": "0x7d1c", "before_hex": "66", "after_hex": "00"},
        {"offset": "0xab10", "before_hex": "ffff", "after_hex": "00fc"},
        {"offset": "0xab40", "before_hex": "2010", "after_hex": "0000"},
        {"offset": "0x103dc", "before_hex": "99", "after_hex": "00"},
    ]
    normalized_changes = [{k: row[k] for k in ("offset", "before_hex", "after_hex")}
                          for row in owner_changes]
    assert normalized_changes == expected_changes, owner_changes
    assert not context_changes, context_changes
    assert not manager_changes, manager_changes
    assert read_u64(sb, owner + 0xAB40) == 0
    assert read_u16(sb, owner + 0xAB10) == 0xFC00
    assert read_u32(sb, owner + 0x7D14) == 0
    assert read_u32(sb, owner + 0x7D1C) == 0
    assert read_u32(sb, owner + 0x103DC) == 0
    assert read_u64(sb, singleton_cell) == manager
    assert read_u64(sb, manager + 0x2488) == manager + 0x2480
    assert code_entries == native_entries, sorted(hex(x) for x in code_entries)
    assert not sb.unknown_imports, sb.unknown_imports

    counter_pointer = read_u64(sb, COUNTER_GLOBAL)
    result = {
        "build": {"main_nso_sha256": nso_hash, "main_elf_sha256": ELF_SHA256},
        "callback": {
            "registered_state": "NpcAIActivityState::cConversationHost",
            "registered_state_index": 60,
            "callback_kind": "exit",
            "entry": hex(HOST_EXIT),
            "direct_call_args": {"x0_owner": hex(owner), "x1": 0},
            "execution": "original NSO code; no function VAs stubbed",
        },
        "fixture": {
            "owner": hex(owner),
            "owner_context": hex(owner_context),
            "owner_context_scalar": {"offset": "+0x230", "value": "0x77"},
            "owner_activity_flags_before": hex(initial_flags),
            "owner_activity_mask_before": hex(initial_mask),
            "owner_7d14_before": hex(initial_view_a),
            "owner_7d1c_before": hex(initial_view_b),
            "owner_103dc_before": hex(initial_activity_word),
            "singleton_global": hex(SINGLETON_GLOBAL),
            "singleton_pointer_cell": hex(singleton_cell),
            "singleton_pointer_before": hex(singleton_value_before),
            "synthetic_empty_manager": hex(manager),
            "manager_list_end": hex(manager + 0x2488),
            "manager_empty_sentinel": hex(manager + 0x2480),
            "view_global": hex(VIEW_GLOBAL),
            "view_global_inner_pointer": hex(read_u64(sb, read_u64(sb, VIEW_GLOBAL))),
            "counter_global": hex(COUNTER_GLOBAL),
            "counter_pointer": hex(counter_pointer),
            "counter_value": hex(read_u32(sb, counter_pointer)),
        },
        "native_observations": observations,
        "owner_changed_ranges": owner_changes,
        "owner_context_changed_ranges": context_changes,
        "manager_changed_ranges": manager_changes,
        "final_owner_fields": {
            "+0xab40_u64": hex(read_u64(sb, owner + 0xAB40)),
            "+0xab10_u16": hex(read_u16(sb, owner + 0xAB10)),
            "+0x7d14_u32": hex(read_u32(sb, owner + 0x7D14)),
            "+0x7d1c_u32": hex(read_u32(sb, owner + 0x7D1C)),
            "+0x103dc_u32": hex(read_u32(sb, owner + 0x103DC)),
        },
        "native_function_entries_seen": [hex(x) for x in sorted(code_entries)],
        "unknown_imports": sb.unknown_imports,
        "raw_x0_after_callback_return": hex(returned_x0),
        "limits": [
            "The host exit callback was called directly; no state manager or scheduler ran.",
            "The singleton manager and its empty-list sentinel are synthetic fixture data.",
            "The original view initializer returned null on both +0x7d14 paths; no live view was exercised.",
            "No host/guest pair selection, dialogue topic/message, EventFlow, or network behavior was exercised.",
        ],
    }
    output = Path(__file__).with_name("host_exit_native.json")
    output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({
        "result": str(output),
        "owner_changed_ranges": len(owner_changes),
        "final_flags": result["final_owner_fields"]["+0xab40_u64"],
        "final_mask": result["final_owner_fields"]["+0xab10_u16"],
        "native_function_entries": len(code_entries),
    }, indent=2))


if __name__ == "__main__":
    main()
