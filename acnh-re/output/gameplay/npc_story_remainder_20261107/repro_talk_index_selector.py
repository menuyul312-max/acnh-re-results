"""Exhaust the native TalkNpc counter selector over all ten resident slots.

The original selector and key formatter run. The lower-level save reads and
query-context normalization are controlled so the first-match behavior can be
checked without claiming a live save, topic, or dialogue selection.
"""
from pathlib import Path
import hashlib
import json
import sys


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tools'))
from nso_sandbox import DEFAULT_NSO, Sandbox  # noqa: E402


ELF_SHA256 = '5bf707c3dc5dac0ad9635af7d336ec580f81c3f7876d0f55400d1900e3415d74'
NSO_SHA256 = 'f8d248109ff72999b4600ae3749f8c7397fb960f7ad3ab8dee3018ae9e14e900'
TALK_INDEX_SELECTOR = 0xf4dbd0
COUNTER_LOOKUP = 0xf4d560
COUNTER_QUERY_CONTEXT = 0xf4da70
COUNTER_CONTEXT_GLOBAL = 0x32d0790


class Harness:
    def __init__(self):
        self.s = Sandbox()
        self.root = self.s.alloc(0x20)
        self.fake_save = self.s.alloc(0x2000)
        self.values = []
        self.reads = []
        self.s.uc.mem_write(COUNTER_CONTEXT_GLOBAL,
                            self.pack_q(self.root))
        self.s.uc.mem_write(self.root, self.pack_q(self.fake_save))

        def read_counter(sb):
            string_object = sb.reg('x1')
            string_data = sb.u64(string_object + 8)
            key = sb.read(string_data, 64).split(b'\0', 1)[0].decode('ascii')
            assert self.values, f'unexpected extra read of {key}'
            value = self.values.pop(0)
            self.reads.append({'key': key, 'controlled_value': value})
            return value

        # Keep the native selector and formatter active while supplying the
        # values normally obtained from persisted counters/context accessors.
        self.s.stub(COUNTER_LOOKUP, read_counter)
        self.s.stub(COUNTER_QUERY_CONTEXT, lambda _sb: None)

    @staticmethod
    def pack_q(value):
        import struct
        return struct.pack('<Q', value)

    def run(self, argument, expected, values, expected_keys):
        self.values = list(values)
        self.reads.clear()
        raw = self.s.call(TALK_INDEX_SELECTOR, (argument,), limit=100_000)
        result = raw & 0xffffffff
        if result & 0x80000000:
            result -= 0x100000000
        assert result == expected, (result, expected)
        observed_keys = [read['key'] for read in self.reads]
        assert observed_keys == expected_keys, (observed_keys, expected_keys)
        observed_values = [read['controlled_value'] for read in self.reads]
        assert observed_values == values, (observed_values, values)
        assert not self.values, self.values
        return {
            'selector_argument': argument,
            'returned_resident_index': result,
            'controlled_reads': list(self.reads),
        }


def case(harness, name, argument, values, expected, keys):
    observed = harness.run(argument, expected, values, keys)
    observed['name'] = name
    return observed


def main():
    harness = Harness()
    cases = []
    for target in range(10):
        keys = ['TalkNpc0Count'] + [f'TalkNpc{i}Count'
                                    for i in range(target + 1)]
        # The first read is the native gate. Earlier resident slots then fail
        # the comparison; the target slot is the first match.
        values = [target] + [target + 100] * target + [target]
        cases.append(case(harness, f'first_match_at_resident_slot_{target}', target,
                          values, target, keys))

    cases.append(case(harness, 'initial_gate_mismatch', 4, [3], -1,
                      ['TalkNpc0Count']))
    cases.append(case(harness, 'all_ten_slots_miss', 5, [5] + [6] * 10, -1,
                      ['TalkNpc0Count'] + [f'TalkNpc{i}Count'
                                           for i in range(10)]))

    ns_hash = hashlib.sha256(Path(DEFAULT_NSO).read_bytes()).hexdigest()
    assert ns_hash == NSO_SHA256, ns_hash
    result = {
        'cases': len(cases),
        'mismatches': [],
        'build': {
            'main_nso_sha256': ns_hash,
            'main_elf_sha256': ELF_SHA256,
        },
        'native_functions': {
            'talk_counter_index_selector': hex(TALK_INDEX_SELECTOR),
            'controlled_counter_lookup': hex(COUNTER_LOOKUP),
            'controlled_query_context': hex(COUNTER_QUERY_CONTEXT),
            'native_key_formatter': '0x47360',
        },
        'cases_data': cases,
        'verified_boundary': (
            'Original 0xf4dbd0 instructions and 0x47360 key formatting ran. '
            'The initial TalkNpc0Count gate and first matching slot were '
            'checked for indices 0 through 9; the native function returned '
            'the matching resident index or -1.'),
        'dependencies_controlled': [
            {'va': hex(COUNTER_LOOKUP),
             'purpose': 'supplies explicit per-key saved counter values'},
            {'va': hex(COUNTER_QUERY_CONTEXT),
             'purpose': 'preserves the selector input while bypassing live query-context lookup'},
        ],
        'limits': [
            'No live save, resident record, or runtime query context was loaded.',
            'The test proves selector mechanics only; it does not show that the returned resident index is a topic, message, or EventFlow entry ID.',
            'Caller functions 0x395bc0, 0x395e50, and 0x3960d0 and the runtime scheduler were not executed.',
        ],
    }
    out = ROOT / 'output/gameplay/npc_story_remainder_20261107/talk_index_selector_native.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps({'cases': len(cases), 'mismatches': 0,
                      'artifact': str(out.relative_to(ROOT))},
                     ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
