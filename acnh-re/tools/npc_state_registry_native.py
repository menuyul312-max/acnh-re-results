"""Run the original NPC state registration and resolve its member callbacks.

The owning NPC, name strings and descriptor buffers are explicitly prepared.
The original registration block, extension, getters and member dispatchers run.
Dispatch checks stop before the AI callback executes; this is not a live NPC.
"""
from collections import Counter
from pathlib import Path
import hashlib
import json
import struct

from native_emulator import Sandbox, regs
from unicorn import UC_HOOK_CODE

ROOT = Path(__file__).resolve().parent.parent


def main():
    s = Sandbox(); u = s.uc; im = s.image
    npc, records, names = 0x500a0000, 0x500c0000, 0x500d0000
    manager = npc+0x7760
    owner_vt = 0x30d5f28
    def q(p, v): u.mem_write(p, struct.pack('<Q', v))
    def d(p, v): u.mem_write(p, struct.pack('<I', v & 0xffffffff))
    def readq(p): return struct.unpack('<Q', u.mem_read(p, 8))[0]
    def readd(p): return struct.unpack('<I', u.mem_read(p, 4))[0]
    def cstring(p): return bytes(u.mem_read(p, 256)).split(b'\0', 1)[0].decode()
    u.mem_write(npc, bytes(0xb000)); q(npc, owner_vt)
    state_count = s.call(im.ptr(owner_vt+0x220), (npc,))
    initial_state = s.call(im.ptr(owner_vt+0x218), (npc,))
    assert state_count == 67 and initial_state == 0
    assert im.ptr(owner_vt+0x228) == 0xbfee00
    d(manager+0x28, state_count); q(manager+0x30, records)
    d(manager+0x38, state_count); q(manager+0x40, names)
    string_vt = im.ptr(0x32d0668)+16
    for i in range(state_count): q(names+16*i, string_vt)
    registered = {}
    def observe_name(uc, pc, size, data):
        index = uc.reg_read(regs.UC_ARM64_REG_W1)
        source = readq(uc.reg_read(regs.UC_ARM64_REG_X2)+8)
        assert index not in registered
        registered[index] = {'label': cstring(source), 'string_va': hex(source)}
    hook = u.hook_add(UC_HOOK_CODE, observe_name, begin=0x1f064b0, end=0x1f064b0)
    stack = s.STACK+0x1ff000
    u.reg_write(regs.UC_ARM64_REG_SP, stack)
    u.reg_write(regs.UC_ARM64_REG_X20, npc)
    u.reg_write(regs.UC_ARM64_REG_X21, manager)
    u.reg_write(regs.UC_ARM64_REG_LR, s.STOP)
    u.emu_start(0xc1acb8, 0xc1bb08, timeout=5_000_000, count=200000)
    assert u.reg_read(regs.UC_ARM64_REG_PC) == 0xc1bb08
    u.hook_del(hook)
    assert set(registered) == set(range(state_count))
    assert readd(manager+0x48) == initial_state
    prior = json.loads((ROOT/'output/mechanics/focus7/npc_native_state_labels.json').read_text())['states']
    assert {x['label'] for x in prior} == {x['label'] for x in registered.values()}
    assert {x['string_va'] for x in prior} == {x['string_va'] for x in registered.values()}
    groups = {'original_state_getters': 2, 'registered_source_states': 0,
              'member_callback_target_dispatch': 0}
    states, dispatch_modes = [], Counter()
    for i in range(state_count):
        address = records+64*i
        words = list(struct.unpack('<8Q', u.mem_read(address, 64)))
        expected_vt = im.ptr(0x32f8230 if i < 43 else 0x32f7e78)+16
        assert words[:2] == [expected_vt, npc]
        label = registered[i]['label']; short = label.rsplit('::', 1)[-1]
        assert readq(names+16*i) == string_vt and cstring(readq(names+16*i+8)) == short
        groups['registered_source_states'] += 1
        state = {'index': i, **registered[i], 'registered_name': short,
                 'registration_owner_va': hex(0xc1ac50 if i < 43 else 0xbfee00),
                 'descriptor_vtable': hex(words[0]), 'callbacks': {}}
        for slot, role in enumerate(['entry', 'update', 'exit']):
            function_or_offset, adjustment = words[2+2*slot:4+2*slot]
            signed_adjustment = struct.unpack('<q', struct.pack('<Q', adjustment))[0]
            receiver = npc+(signed_adjustment >> 1)
            virtual = bool(adjustment & 1)
            target = readq(readq(receiver)+function_or_offset) if virtual else function_or_offset
            dispatcher = im.ptr(words[0]+8*slot)
            u.reg_write(regs.UC_ARM64_REG_SP, stack)
            u.reg_write(regs.UC_ARM64_REG_X0, address)
            u.reg_write(regs.UC_ARM64_REG_X1, 42)
            u.reg_write(regs.UC_ARM64_REG_LR, s.STOP)
            stop = target or s.STOP
            u.emu_start(dispatcher, stop, timeout=5_000_000, count=32)
            assert u.reg_read(regs.UC_ARM64_REG_PC) == stop, (i, role, hex(target))
            assert u.reg_read(regs.UC_ARM64_REG_X0) == (receiver if target else address)
            if slot == 2: assert u.reg_read(regs.UC_ARM64_REG_X1) == 42
            mode = 'virtual' if virtual else 'direct' if target else 'null_member_noop'
            dispatch_modes[mode] += 1
            state['callbacks'][role] = {'dispatcher_va': hex(dispatcher),
                                       'member_function_or_vtable_offset': hex(function_or_offset),
                                       'raw_adjustment_flag': hex(adjustment),
                                       'receiver_byte_adjustment': signed_adjustment >> 1,
                                       'dispatch_mode': mode, 'target_va': hex(target) if target else None,
                                       'validation': 'Original dispatcher reached handler entry; handler not executed.' if target else 'Original null-member dispatcher returned.'}
            groups['member_callback_target_dispatch'] += 1
        states.append(state)
    result = {'cases': sum(groups.values()), 'groups': groups, 'mismatches': [],
              'states': states, 'dispatch_modes': dict(dispatch_modes),
              'registration_block': {'entry_va': '0xc1acb8', 'stop_before_va': '0xc1bb08',
                                     'common_registration_function': '0xc1ac50',
                                     'extension_registration_function': '0xbfee00',
                                     'owner_vtable': hex(owner_vt), 'state_manager_offset': '0x7760',
                                     'record_size': 64, 'name_record_size': 16,
                                     'common_states': 43, 'activity_states': 24, 'initial_state': initial_state},
              'role_evidence': {'entry': {'native_consumer_va': '0x1f06750', 'descriptor_virtual_slot': '0x0'},
                                'update': {'native_consumer_va': '0x1f06900', 'descriptor_virtual_slot': '0x8'},
                                'exit': {'native_consumer_va': '0x1f067b0', 'descriptor_virtual_slot': '0x10',
                                         'argument_W1': 'new state index'}},
              'member_pointer_rule': 'Receiver=owner+(signed adjustment_flag>>1); low bit chooses owner vtable lookup by offset versus direct function. Null direct members return.',
              'source_reference': 'mechanics/focus7/npc_native_state_labels.json',
              'dependencies_stubbed': [],
              'scope': 'Original registration and callback dispatch targets for all67 states of this activity-NPC owner vtable.',
              'limits': ['Owner and preallocated descriptor/string buffers are reconstructed; allocator prefix and full NPC constructor do not execute.',
                         'Callback dispatch checks stop BEFORE the actual handler executes. State-role consumers are statically verified, not a complete FSM simulation.',
                         'This does not execute state decisions, movement, path searches, collision avoidance, world schedules or all NPC subclasses.',
                         'State names such as EscapeHighCostArea are native labels, not proof of a particular pathfinding algorithm.'],
              'elf_sha256': hashlib.sha256(im.data).hexdigest()}
    (ROOT/'output/mechanics/npc_state_registry_native.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({'cases': result['cases'], 'groups': groups, 'dispatch_modes': dict(dispatch_modes), 'mismatches': 0}), flush=True)


if __name__ == '__main__': main()
