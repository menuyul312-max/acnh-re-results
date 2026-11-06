"""Exercise native TalkCountToday / ContinuousTalkDays reset branches.

The original reset helpers execute through their field-writer calls. A
controlled getter supplies TalkCountToday, while the writer records the reset
keys and values instead of mutating save memory.
"""
from pathlib import Path
import hashlib
import json
import struct

from nso_sandbox import DEFAULT_NSO, Sandbox


ROOT = Path(__file__).resolve().parent.parent
ELF_SHA256 = '5bf707c3dc5dac0ad9635af7d336ec580f81c3f7876d0f55400d1900e3415d74'
NSO_SHA256 = 'f8d248109ff72999b4600ae3749f8c7397fb960f7ad3ab8dee3018ae9e14e900'
TALK_MEMORY_RESET = 0xf76010
TALK_STREAK_RESET = 0xf696c0
FLAG_GETTER = 0xf486c0
FLAG_SETTER = 0xf48840
NON_TALK_RESET_HELPER = 0xf6ec10


def signed_u32(value):
    value &= 0xffffffff
    return value - 0x100000000 if value & 0x80000000 else value


class Harness:
    def __init__(self):
        self.s = Sandbox()
        self.record = self.s.alloc(0x800)
        self.context = self.s.alloc(0x40)
        self.talk_count = 0
        self.writer_calls = []

        self.s.stub(NON_TALK_RESET_HELPER, lambda _sb: None)
        self.s.stub(FLAG_GETTER, lambda _sb: self.talk_count)

        def capture_flag_reset(sb):
            string_object = sb.reg('x1')
            string_data = sb.u64(string_object + 8)
            key = sb.read(string_data, 96).split(b'\0', 1)[0].decode('ascii')
            self.writer_calls.append({
                'key': key,
                'reset_value': signed_u32(sb.reg('w2')),
            })

        self.s.stub(FLAG_SETTER, capture_flag_reset)

    def set_context(self, mode):
        # The nonzero byte at +24 exits after the talk-counter reset logic and
        # before unrelated calendar greeting flags are processed.
        context = bytearray(0x40)
        struct.pack_into('<Q', context, 0, mode)
        context[24] = 1
        self.s.uc.mem_write(self.context, bytes(context))

    def run(self, helper, mode, prior_talk_count, expected_keys):
        self.talk_count = prior_talk_count
        self.writer_calls.clear()
        self.set_context(mode)
        record_ptr = self.record + (8 if helper == TALK_STREAK_RESET else 0)
        self.s.call(helper, (record_ptr, self.context))
        observed_keys = [call['key'] for call in self.writer_calls]
        expected_calls = [{'key': key, 'reset_value': 0} for key in expected_keys]
        assert self.writer_calls == expected_calls, (hex(helper), mode,
                                                       prior_talk_count,
                                                       self.writer_calls,
                                                       expected_calls)
        return {
            'helper_va': hex(helper),
            'mode_input': mode,
            'prior_TalkCountToday': prior_talk_count,
            'field_reset_calls': list(self.writer_calls),
        }


def main():
    harness = Harness()
    cases = [
        harness.run(TALK_MEMORY_RESET, 0, 0,
                    ['ContinuousTalkDays']),
        harness.run(TALK_MEMORY_RESET, 0, 1, []),
        harness.run(TALK_MEMORY_RESET, 1, 0,
                    ['ContinuousTalkDays', 'TalkCountToday']),
        harness.run(TALK_MEMORY_RESET, 1, 1, ['TalkCountToday']),
        harness.run(TALK_MEMORY_RESET, 2, 1,
                    ['ContinuousTalkDays', 'TalkCountToday']),
        harness.run(TALK_STREAK_RESET, 0, 0,
                    ['ContinuousTalkDays', 'TalkCountToday']),
        harness.run(TALK_STREAK_RESET, 0, 1, ['TalkCountToday']),
        harness.run(TALK_STREAK_RESET, 2, 1,
                    ['ContinuousTalkDays', 'TalkCountToday']),
    ]

    nso_hash = hashlib.sha256(Path(DEFAULT_NSO).read_bytes()).hexdigest()
    assert nso_hash == NSO_SHA256, nso_hash
    result = {
        'cases': len(cases),
        'mismatches': [],
        'native_functions': {
            'main_villager_memory_reset': hex(TALK_MEMORY_RESET),
            'alternate_talk_streak_reset': hex(TALK_STREAK_RESET),
            'flag_getter_boundary': hex(FLAG_GETTER),
            'flag_setter_boundary': hex(FLAG_SETTER),
            'non_talk_reset_helper': hex(NON_TALK_RESET_HELPER),
        },
        'call_chain_from_day_change': [
            '0xf53a70', '0xf545f0', '0xf84320', '0xf12aa0', '0xf76010',
        ],
        'cases_data': cases,
        'scope': ('Original 0xf76010 and 0xf696c0 instructions run through the '
                  'TalkCountToday / ContinuousTalkDays branch. The test stops '
                  'each field reset at entry to original 0xf48840.'),
        'dependencies_stubbed': [
            {'va': hex(FLAG_GETTER),
             'purpose': 'returns the controlled prior TalkCountToday value'},
            {'va': hex(FLAG_SETTER),
             'purpose': 'captures a reset key/value without changing save memory'},
            {'va': hex(NON_TALK_RESET_HELPER),
             'purpose': 'skips unrelated talk-memory helper work before the tested branch'},
        ],
        'prepared_context': {
            'mode': 'controlled integer at reset context +0',
            'early_return_byte': 'context +0x18 set to 1 so unrelated greeting/calendar resets do not run',
            'prior_TalkCountToday': 'controlled getter result',
        },
        'limits': [
            'The helpers and getter/writer arguments are synthetic; no live save or actual day-change event was loaded.',
            'The setter is captured at entry to 0xf48840, before a save field changes.',
            'The day-change caller chain and meanings of its mode values are pseudocode evidence; this test exercises controlled mode numbers only.',
            'This verifies reset branches for TalkCountToday and ContinuousTalkDays, not the daily Friendship delta source, reset of TalkNpc%dCount, or friendship decay.',
        ],
        'elf_sha256': ELF_SHA256,
        'nso_sha256': nso_hash,
    }
    out = ROOT / 'output/gameplay/villager_social_followup/talk_streak_reset_native.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps({'cases': len(cases), 'mismatches': 0,
                      'field_reset_calls': sum(len(case['field_reset_calls']) for case in cases),
                      'artifact': str(out.relative_to(ROOT))}, ensure_ascii=False),
          flush=True)


if __name__ == '__main__':
    main()
