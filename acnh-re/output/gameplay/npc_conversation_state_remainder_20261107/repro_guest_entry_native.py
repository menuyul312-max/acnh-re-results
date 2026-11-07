"""Execute the registered cConversationGuest entry body with a controlled pair.

The original callback body runs from the pinned ACNH 1.0.0 NSO. The context
adapter and actor/global helpers are controlled so the test can observe the
callback's own state writes without creating a live NPC or scheduler.
"""
from pathlib import Path
import hashlib
import json
import struct
import sys


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tools'))
from nso_sandbox import DEFAULT_NSO, Sandbox  # noqa: E402


ELF_SHA256 = '5bf707c3dc5dac0ad9635af7d336ec580f81c3f7876d0f55400d1900e3415d74'
NSO_SHA256 = 'f8d248109ff72999b4600ae3749f8c7397fb960f7ad3ab8dee3018ae9e14e900'
GUEST_ENTRY = 0xc0c9e0


def read_u32(sb, address):
    return struct.unpack('<I', sb.read(address, 4))[0]


def read_u64(sb, address):
    return struct.unpack('<Q', sb.read(address, 8))[0]


def write_u32(sb, address, value):
    sb.uc.mem_write(address, struct.pack('<I', value & 0xffffffff))


def write_u64(sb, address, value):
    sb.uc.mem_write(address, struct.pack('<Q', value & 0xffffffffffffffff))


def changed_ranges(before, after, base):
    changes = []
    i = 0
    while i < len(before):
        if before[i] == after[i]:
            i += 1
            continue
        start = i
        while i < len(before) and before[i] != after[i]:
            i += 1
        changes.append({
            'address': hex(base + start),
            'offset_from_owner': hex(start),
            'before_hex': before[start:i].hex(),
            'after_hex': after[start:i].hex(),
        })
    return changes


def main():
    sb = Sandbox()
    owner = sb.alloc(0x11000)
    owner_context = sb.alloc(0x800)
    paired_context = sb.alloc(0x800)
    actor_a = sb.alloc(0x400)
    actor_b = sb.alloc(0x400)
    runtime_context = sb.alloc(0x800)
    owner_demo_context = sb.alloc(0x400)
    resident_slot = 4
    copied_activity_value = 0x1357
    initial_activity_flags = 0x0000000000000041
    context_source_word = 0x2468

    # The state object and the conversation/event contexts are prepared input.
    write_u64(sb, owner + 8, owner_context)
    write_u64(sb, owner + 0x10, runtime_context)
    write_u64(sb, owner + 0x18, owner_demo_context)
    write_u32(sb, owner + 0x7d1c, context_source_word)
    write_u32(sb, owner_context + 0x448, resident_slot)
    write_u64(sb, owner_context + 0x68, actor_a)
    write_u64(sb, paired_context + 0x68, actor_b)
    write_u32(sb, owner + 0x7834, copied_activity_value)
    write_u64(sb, owner + 0xab40, initial_activity_flags)
    for actor, x, z in ((actor_a, 1.25, -2.5), (actor_b, 5.0, 7.5)):
        sb.uc.mem_write(actor + 0x278, struct.pack('<f', x))
        sb.uc.mem_write(actor + 0x280, struct.pack('<f', z))

    call_records = []

    def context_resolver(sandbox):
        output = sandbox.reg('x0')
        source = sandbox.reg('x1')
        mode = sandbox.reg('w2')
        # c0c9e0 expects a pointer at temporary +0 and two true state bytes at
        # +8 and +0xa before entering its paired-context path.
        sandbox.uc.mem_write(output,
                             struct.pack('<Q', paired_context) +
                             b'\x01\x00\x01' + bytes(5))
        call_records.append({
            'helper': '0x3fe00',
            'source': hex(source),
            'source_offset_from_owner': hex(source - owner),
            'source_u32': hex(read_u32(sandbox, source)),
            'mode': mode,
            'returned_paired_context': hex(paired_context),
            'returned_state_bytes': {'temporary_plus_8': 1,
                                     'temporary_plus_10': 1},
        })

    def capture_helper(name, return_value=0):
        def callback(sandbox):
            args = [sandbox.reg(f'x{i}') for i in range(5)]
            call_records.append({
                'helper': name,
                'args_x0_to_x4': [hex(arg) for arg in args],
            })
            return return_value
        return callback

    def capture_position_compare(sandbox):
        call_records.append({
            'helper': '0x1c780',
            'position_a': hex(sandbox.reg('x0')),
            'position_b': hex(sandbox.reg('x1')),
            'hidden_output_x8': hex(sandbox.reg('x8')),
            'position_a_values': [
                struct.unpack('<f', sandbox.read(sandbox.reg('x0'), 4))[0],
                struct.unpack('<f', sandbox.read(sandbox.reg('x0') + 8, 4))[0],
            ],
            'position_b_values': [
                struct.unpack('<f', sandbox.read(sandbox.reg('x1'), 4))[0],
                struct.unpack('<f', sandbox.read(sandbox.reg('x1') + 8, 4))[0],
            ],
        })
        return 0

    def capture_owner_flag_helper(sandbox):
        call_records.append({
            'helper': '0xceb7d0',
            'object': hex(sandbox.reg('x0')),
            'object_offset_from_owner': hex(sandbox.reg('x0') - owner),
            'value': sandbox.reg('w1'),
        })
        return 0

    # These replace context resolution, actor lookup/position comparison, and
    # unrelated engine services. State writes in c0c9e0 itself remain native.
    sb.stub(0x3fe00, context_resolver)
    sb.stub(0xd1cb80, capture_helper('0xd1cb80', 0))
    sb.stub(0xd1eaf0, capture_helper('0xd1eaf0', 0))
    sb.stub(0x1c780, capture_position_compare)
    sb.stub(0xbf78f0, capture_helper('0xbf78f0', 0))
    sb.stub(0xc8c920, capture_helper('0xc8c920', 0))
    sb.stub(0xceb7d0, capture_owner_flag_helper)
    sb.stub(0x40040, capture_helper('0x40040', 0))

    before = sb.read(owner, 0x11000)
    sb.call(GUEST_ENTRY, (owner,), limit=100_000)
    after = sb.read(owner, 0x11000)

    flags_after = read_u64(sb, owner + 0xab40)
    copied_value_after = read_u32(sb, owner + 0x103dc)
    assert flags_after == (initial_activity_flags | 0x1000), hex(flags_after)
    assert copied_value_after == copied_activity_value, hex(copied_value_after)
    assert [row['helper'] for row in call_records].count('0x3fe00') == 1
    assert [row['helper'] for row in call_records].count('0x1c780') == 1
    assert [row['helper'] for row in call_records].count('0xc8c920') == 1
    assert [row['helper'] for row in call_records].count('0xceb7d0') == 1

    nso_hash = hashlib.sha256(Path(DEFAULT_NSO).read_bytes()).hexdigest()
    assert nso_hash == NSO_SHA256, nso_hash
    result = {
        'cases': 1,
        'mismatches': [],
        'build': {
            'main_nso_sha256': nso_hash,
            'main_elf_sha256': ELF_SHA256,
        },
        'callback': {
            'registered_state': 'NpcAIActivityState::cConversationGuest',
            'registered_state_index': 61,
            'role': 'entry',
            'va': hex(GUEST_ENTRY),
        },
        'prepared_pair': {
            'owner': hex(owner),
            'owner_event_context': hex(owner_context),
            'paired_context': hex(paired_context),
            'resident_slot_input': resident_slot,
            'actor_position_inputs': {
                'owner_context_actor': {'address': hex(actor_a + 0x278),
                                        'xz': [1.25, -2.5]},
                'paired_context_actor': {'address': hex(actor_b + 0x278),
                                         'xz': [5.0, 7.5]},
            },
        },
        'callback_owner_writes': changed_ranges(before, after, owner),
        'asserted_fields': {
            'owner_plus_0xab40_u64_before': hex(initial_activity_flags),
            'owner_plus_0xab40_u64_after': hex(flags_after),
            'owner_plus_0x7834_u32_input': hex(copied_activity_value),
            'owner_plus_0x7d1c_u32_input': hex(context_source_word),
            'owner_plus_0x103dc_u32_after': hex(copied_value_after),
        },
        'captured_calls': call_records,
        'execution_boundary': (
            'Original 0xc0c9e0 body executed to return. The paired-context '
            'resolver, actor/user lookup, position comparison, unrelated '
            'engine requests, and temporary-object destructor were replaced '
            'with controlled adapters.'),
        'dependencies_controlled': [
            {'va': '0x3fe00', 'purpose': 'supplies a paired-context pointer and two positive context-state bytes'},
            {'va': '0xd1cb80', 'purpose': 'controls the helper called with raw resident slot 4 and mode 1; returns null'},
            {'va': '0xd1eaf0', 'purpose': 'is skipped by the controlled null result from 0xd1cb80'},
            {'va': '0x1c780', 'purpose': 'captures the two actor position addresses and skips the engine position comparison'},
            {'va': '0xbf78f0', 'purpose': 'captures arguments for an additional context helper without running its body'},
            {'va': '0xc8c920', 'purpose': 'captures callback arguments without running the native service body'},
            {'va': '0xceb7d0', 'purpose': "captures a related helper request; the callback's direct owner bitfield write remains native"},
            {'va': '0x40040', 'purpose': 'skips destruction of the synthetic temporary context wrapper'},
        ],
        'limits': [
            'The owner, pair, actor contexts, positions, resident slot, and source value are synthetic; no live NPC pair or save was loaded.',
            'This tests one positive cConversationGuest entry branch only; it does not execute the host callback, update/exit bodies, state manager transition, network synchronization, or scheduler.',
            'The meanings of owner offsets +0xab40, +0x7834, +0x7d1c, and +0x103dc are not recovered from this fixture; only the byte-level operations are proven.',
            'The 0xc8c920 service and helper called by 0xd1cb80 are controlled, so their downstream effects remain open.',
        ],
    }
    out = ROOT / 'output/gameplay/npc_conversation_state_remainder_20261107/guest_entry_native.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps({'cases': 1, 'mismatches': 0,
                      'owner_writes': len(result['callback_owner_writes']),
                      'artifact': str(out.relative_to(ROOT))},
                     ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
