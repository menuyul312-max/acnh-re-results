"""Verify EventFlow friendship action inputs reach the friendship wrapper.

The original EventFlow action callback runs through its native validation
dispatch and stops at the original 0xd34cb0 call. The actor/action objects and
the static validation guard are controlled test inputs; no save mutation runs.
"""
from pathlib import Path
import hashlib
import json
import struct

from nso_sandbox import DEFAULT_NSO, Sandbox
from unicorn import UC_HOOK_CODE, arm64_const as regs


ROOT = Path(__file__).resolve().parent.parent
ELF_SHA256 = '5bf707c3dc5dac0ad9635af7d336ec580f81c3f7876d0f55400d1900e3415d74'
NSO_SHA256 = 'f8d248109ff72999b4600ae3749f8c7397fb960f7ad3ab8dee3018ae9e14e900'
ACTION_EXECUTE = 0x27a220
ACTION_VTABLE = 0x3040940
VALIDATION_METHOD = 0x27a210
FRIENDSHIP_WRAPPER = 0xd34cb0
ADD_VALUE_OFFSET = 0xd8
RESIDENT_SLOT_OFFSET = 0x448

# Every registered use comes from the locally extracted BFEVFL set. Keep only
# flow/event IDs and AddValue; dialog strings and unrelated payloads are omitted.
EVENTFLOW_CASES = [
    ('NNPC_FreeA', 70, 1), ('NNPC_FreeA', 78, 1),
    ('NNPC_GEvent_BirthdayN_H', 92, -5),
    ('NNPC_GEvent_BirthdayN_H', 102, 6),
    ('NNPC_GEvent_BirthdayN_H', 103, 4),
    ('NNPC_GEvent_BirthdayN_H', 104, 8),
    ('NNPC_GEvent_BirthdayN_H', 105, 4),
    ('NNPC_GEvent_BirthdayN_H', 106, 3),
    ('NNPC_GEvent_BirthdayN_H', 107, 5),
    ('NNPC_Quest_AllReward', 4, 2),
    ('NNPC_Quest_AllReward', 5, 3),
    ('NNPC_Quest_AllReward', 6, 1),
    ('NNPC_Quest_AllReward', 27, 1),
    ('NNPC_Quest_AllReward', 31, 3),
    ('NNPC_Quest_Delivery_Give', 93, 3),
    ('NNPC_Quest_Delivery_Give', 94, 1),
    ('NNPC_Quest_Delivery_Report', 115, 3),
    ('NNPC_Quest_Delivery_TimeOver', 34, -1),
    ('NNPC_Quest_Delivery_TimeOver', 35, -2),
    ('NNPC_Quest_Delivery_TimeOver', 36, -3),
    ('NNPC_Quest_LostProperty_End', 95, 2),
    ('NNPC_Quest_Sick_End', 77, -1),
    ('NNPC_Quest_TreasureHunt_End', 48, -1),
    ('NNPC_Quest_TreasureHunt_End', 82, 1),
    ('NNPC_Quest_VisitN_Begin', 76, 1),
    ('NNPC_Quest_VisitN_Begin', 77, 1),
    ('NNPC_Quest_VisitP_Begin', 75, 1),
    ('NNPC_Quest_VisitP_Begin', 76, 1),
    ('NNPC_Reaction_Mood', 31, 3),
    ('NNPC_Reaction_Mood', 42, 3),
    ('NNPC_Reaction_Mood', 47, 3),
    ('NNPC_Reaction_Mood', 62, 3),
    ('NNPC_Reaction_Mood', 83, 3),
    ('NNPC_Reaction_Quest', 37, -5),
    ('NNPC_Reaction_Quest', 38, -5),
    ('NNPC_Reaction_Quest', 40, 1),
    ('NNPC_Select_Creature', 16, 2),
    ('NNPC_Select_Creature', 17, 1),
    ('NNPC_Select_Creature', 34, 2),
    ('NNPC_Select_Equipment', 17, 2),
    ('NNPC_Select_Equipment', 18, 1),
    ('NNPC_Select_Equipment', 21, 1),
    ('NNPC_Select_Etc', 11, -2),
    ('NNPC_Select_Etc', 12, 1),
    ('NNPC_Select_Etc', 16, 2),
    ('NNPC_Select_Etc', 17, 1),
    ('NNPC_Select_Etc', 25, 1),
    ('NNPC_Select_Furniture', 11, 3),
    ('NNPC_Select_Furniture', 13, 1),
    ('NNPC_Select_Furniture', 19, 1),
    ('NNPC_Select_Furniture', 25, 1),
    ('NNPC_Select_Present', 10, 1),
    ('NNPC_Select_Sell_Gift', 23, 1),
    ('NNPC_Select_Sell_Gift', 24, 3),
    ('NNPC_Select_Sell_Gift', 25, 2),
    ('NNPC_Select_Sell_Gift', 35, 1),
    ('NNPC_Select_Sell_Gift', 36, 3),
    ('NNPC_Select_Sell_Gift', 37, 2),
    ('NNPC_Select_Tool', 6, 1),
    ('NNPC_Select_Tool', 7, 2),
    ('NNPC_Select_Tool', 13, 1),
    ('NNPC_Select_Tool', 18, 2),
    ('NNPC_Select_Tool', 19, 1),
    ('NNPC_Select_Tool', 26, 1),
    ('NNPC_Talk_Force', 21, -3),
    ('NNPC_Talk_Force', 31, 5),
    ('NNPC_Talk_Force', 32, -3),
    ('NNPC_Talk_Force', 33, -3),
    ('NNPC_Talk_Force', 34, -3),
    ('NNPC_Talk_Force', 36, -3),
    ('NNPC_Talk_Force', 38, -3),
    ('NNPC_Talk_Force', 64, -3),
]


class Harness:
    def __init__(self):
        self.s = Sandbox()
        self.u = self.s.uc
        self.action = self.s.HEAP + 0x10000
        self.context = self.s.HEAP + 0x20000
        self.actor = self.s.HEAP + 0x30000
        self.guard = self.s.HEAP + 0x40000
        self.descriptor = self.s.HEAP + 0x50000
        self.resident_slot = 4
        self.observed = None

        self.u.mem_write(self.action, bytes(0x500))
        self.u.mem_write(self.context, bytes(0x400))
        self.u.mem_write(self.actor, bytes(0x500))

        # The action instance uses the original registered vtable. Its native
        # validation slot at +0x20 also runs on a synthetic context receiver.
        self.q(self.action, ACTION_VTABLE)
        self.q(self.action + 8, self.context)
        self.q(self.context + 0x48, self.actor)
        self.q(self.actor, ACTION_VTABLE)
        self.d(self.actor + RESIDENT_SLOT_OFFSET, self.resident_slot)

        # 0x27a220 reads this already-constructed static validation descriptor.
        # The method itself remains the original 0x27a210 code.
        self.q(0x32d2630, self.guard)
        self.u.mem_write(self.guard, b'\x01')
        self.q(0x32d2638, self.descriptor)

        def stop_before_friendship_wrapper(uc, pc, _size, _data):
            assert pc == FRIENDSHIP_WRAPPER
            actor_context = uc.reg_read(regs.UC_ARM64_REG_X1)
            self.observed = {
                'resident_slot': uc.reg_read(regs.UC_ARM64_REG_W0),
                'actor_context_offset_from_prepared_context': actor_context - self.context,
                'add_value': struct.unpack('<i', bytes(
                    uc.mem_read(self.action + ADD_VALUE_OFFSET, 4)))[0],
                'forwarded_add_value': uc.reg_read(regs.UC_ARM64_REG_W2),
            }
            uc.emu_stop()

        self.stop_hook = self.u.hook_add(
            UC_HOOK_CODE, stop_before_friendship_wrapper,
            begin=FRIENDSHIP_WRAPPER, end=FRIENDSHIP_WRAPPER)

    def q(self, address, value):
        self.u.mem_write(address, struct.pack('<Q', value))

    def d(self, address, value):
        self.u.mem_write(address, struct.pack('<I', value & 0xffffffff))

    def run(self, delta):
        self.observed = None
        self.d(self.action + ADD_VALUE_OFFSET, delta)
        self.u.reg_write(regs.UC_ARM64_REG_SP, self.s.STACK + 0x1ff000)
        self.u.reg_write(regs.UC_ARM64_REG_X0, self.action)
        self.u.reg_write(regs.UC_ARM64_REG_X30, self.s.STOP)
        self.u.emu_start(ACTION_EXECUTE, self.s.STOP,
                         timeout=5_000_000, count=100_000)
        pc = self.u.reg_read(regs.UC_ARM64_REG_PC)
        assert pc == FRIENDSHIP_WRAPPER, hex(pc)
        assert self.observed is not None
        return self.observed

    def close(self):
        self.u.hook_del(self.stop_hook)


def activity_registry_summary():
    source = ROOT / 'output/mechanics/npc_state_registry_native.json'
    data = json.loads(source.read_text())
    states = {state['registered_name']: state for state in data['states']}
    wanted = ('cConversationHost', 'cConversationGuest')
    result = {}
    for name in wanted:
        state = states[name]
        result[name] = {
            'index': state['index'],
            'registration_owner_va': state['registration_owner_va'],
            'callbacks': {role: callback['target_va']
                          for role, callback in state['callbacks'].items()},
        }
    return {'source': 'mechanics/npc_state_registry_native.json',
            'registered_state_count': data['registration_block']['common_states'] +
                                      data['registration_block']['activity_states'],
            'common_state_count': data['registration_block']['common_states'],
            'activity_state_count': data['registration_block']['activity_states'],
            'conversation_states': result}


def main():
    harness = Harness()
    samples = []
    for flow, event_index, delta in EVENTFLOW_CASES:
        observed = harness.run(delta)
        assert observed['resident_slot'] == harness.resident_slot
        assert observed['add_value'] == delta
        assert observed['forwarded_add_value'] == (delta & 0xffffffff)
        assert observed['actor_context_offset_from_prepared_context'] == 0x2a8
        samples.append({'flow': flow, 'event_index': event_index,
                        'AddValue': delta, 'callback_args': observed})
    harness.close()

    nso_hash = hashlib.sha256(Path(DEFAULT_NSO).read_bytes()).hexdigest()
    assert nso_hash == NSO_SHA256, nso_hash
    result = {
        'cases': len(samples),
        'mismatches': [],
        'eventflow_binding': {
            'action_name': 'EventFlowActionNpcAddFriendship',
            'parameter': 'AddValue:int',
            'native_forwarded_event_uses': len(samples),
            'registry_event_uses': 72,
            'registry_flow_count': 21,
            'factory_va': '0x4510b0',
            'constructor_va': '0x27a170',
            'vtable_va': hex(ACTION_VTABLE),
            'execute_slot_va': hex(ACTION_EXECUTE),
            'add_value_member_offset': hex(ADD_VALUE_OFFSET),
            'native_call_chain': ['0x27a220', '0xd34cb0', '0xd34f80', '0xef2c70'],
            'verified_boundary': '0x27a220 ran and forwarded AddValue to the 0xd34cb0 entry. Execution stopped before 0xd34cb0 body.',
        },
        'eventflow_samples': samples,
        'activity_registry': activity_registry_summary(),
        'prepared_context': {
            'action_object': 'Synthetic instance with original EventFlow action vtable and AddValue at +0xd8.',
            'actor_object': 'Synthetic receiver carrying resident slot 4 at +0x448; validation dispatch uses original vtable slot and original 0x27a210 code.',
            'context_to_actor_offset': 'context+0x48',
            'network_or_save_state': 'not entered',
        },
        'dependencies_stubbed': [],
        'scope': 'Original 0x27a220 action callback, 0x27a210 validation method, 0x455d20, and 0x455d00 execute. The harness stops at the original 0xd34cb0 call.',
        'limits': [
            'EventFlow action objects and actor context are prepared inputs; the EventFlow interpreter, action constructor, and live MainNpc object are not run.',
            'Execution stops before 0xd34cb0 reads or changes Friendship. The prior friendship delta artifact separately runs 0xd34f80 to the 0xef2c70 boundary.',
            'The host/guest state artifact proves registration and callback target dispatch only; host/guest callback bodies and conversation topic selection remain open.',
            'The registry event values prove configured AddValue inputs, not that every branch or event occurs in a given playthrough.',
        ],
        'elf_sha256': ELF_SHA256,
        'nso_sha256': nso_hash,
    }
    out = ROOT / 'output/gameplay/villager_social_followup/eventflow_friendship_action_native.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps({'cases': len(samples), 'mismatches': 0,
                      'event_flows': len({sample['flow'] for sample in samples}),
                      'artifact': str(out.relative_to(ROOT))}, ensure_ascii=False),
          flush=True)


if __name__ == '__main__':
    main()
