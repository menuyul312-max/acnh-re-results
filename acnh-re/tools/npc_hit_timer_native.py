#!/usr/bin/env python3
"""Run the original net-hit timer setter with a controlled NPC context.

The native EventFlow action at 0x25c650 is executed. Only the current-context
lookup and the two virtual object lookups are controlled; the native handler
performs the Timer * 30 multiplication and writes the NPC timer field. This
does not establish how often the NPC update method is dispatched in gameplay.
"""
from pathlib import Path
import hashlib
import json
import struct

from nso_sandbox import DEFAULT_NSO, Sandbox


ROOT = Path(__file__).resolve().parent.parent
NSO_SHA256 = 'f8d248109ff72999b4600ae3749f8c7397fb960f7ad3ab8dee3018ae9e14e900'
NPC_SET_HIT_TIMER = 0x25c650
CURRENT_EVENT_CONTEXT = 0x455d20
CONTEXT_QUERY_STUB = 0x1000
NPC_QUERY_STUB = 0x1010
TIMER_PARAMETER_OFFSET = 0xd8
NPC_POINTER_OFFSET = 0x2f8
NPC_TIMER_OFFSET = 0xacac


class Harness:
    def __init__(self):
        self.s = Sandbox()
        self.action = self.s.alloc(0x200)
        self.context = self.s.alloc(0x400)
        self.npc = self.s.alloc(NPC_TIMER_OFFSET + 0x10)
        self.context_vtable = self.s.alloc(0x40)
        self.npc_vtable = self.s.alloc(0x40)

        # The action handler retrieves the active context through this boundary.
        # The context's virtual lookup yields the synthetic NPC actor.
        self.s.uc.mem_write(self.context, struct.pack('<Q', self.context_vtable))
        self.s.uc.mem_write(self.context + NPC_POINTER_OFFSET,
                            struct.pack('<Q', self.npc))
        self.s.uc.mem_write(self.context_vtable + 0x20,
                            struct.pack('<Q', CONTEXT_QUERY_STUB))
        self.s.uc.mem_write(self.npc, struct.pack('<Q', self.npc_vtable))
        self.s.uc.mem_write(self.npc_vtable,
                            struct.pack('<Q', NPC_QUERY_STUB))

        self.s.stub(CURRENT_EVENT_CONTEXT, lambda _sb: self.context)
        self.s.stub(CONTEXT_QUERY_STUB, lambda _sb: 1)
        self.s.stub(NPC_QUERY_STUB, lambda _sb: 1)

    def run(self, timer):
        self.s.uc.mem_write(self.action + TIMER_PARAMETER_OFFSET,
                            struct.pack('<I', timer))
        self.s.uc.mem_write(self.npc + NPC_TIMER_OFFSET,
                            struct.pack('<I', 0xdeadbeef))
        self.s.call(NPC_SET_HIT_TIMER, (self.action,), limit=100_000)
        return self.s.u32(self.npc + NPC_TIMER_OFFSET)


def main():
    cases = [0, 1, 30, 60, 90]
    harness = Harness()
    samples = []
    for timer in cases:
        observed = harness.run(timer)
        expected = timer * 30
        assert observed == expected, (timer, observed, expected)
        samples.append({
            'eventflow_timer': timer,
            'stored_actor_timer': observed,
            'expected_timer_x30': expected,
        })

    nso_hash = hashlib.sha256(Path(DEFAULT_NSO).read_bytes()).hexdigest()
    assert nso_hash == NSO_SHA256, nso_hash
    result = {
        'evidence_status': 'native_controlled',
        'nso_sha256': nso_hash,
        'native_handler': hex(NPC_SET_HIT_TIMER),
        'field_offset': hex(NPC_TIMER_OFFSET),
        'parameter_offset': hex(TIMER_PARAMETER_OFFSET),
        'controlled_boundaries': [
            hex(CURRENT_EVENT_CONTEXT),
            hex(CONTEXT_QUERY_STUB),
            hex(NPC_QUERY_STUB),
        ],
        'case_count': len(samples),
        'mismatches': [],
        'samples': samples,
        'finding': 'The original handler writes Timer * 30 to NPC actor+0xacac.',
        'limit': (
            'The context and NPC are synthetic; this proves native scaling only. '
            'The update-dispatch interval, per-second cadence, and net-hit counter '
            'incrementer are not established.'
        ),
    }
    (ROOT / 'output/gameplay/villager_social_followup/hit_timer_native.json').write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
