"""Run the native TalkNpc counter-index selector with controlled save reads.

0xf4dbd0 executes natively, including its key formatting and first-match loop.
The lower-level record lookup is supplied with a short sequence of values, so
the test checks the selector without claiming to execute real save reads.
"""
from pathlib import Path
import hashlib
import json
import struct

from nso_sandbox import DEFAULT_NSO, Sandbox


ROOT = Path(__file__).resolve().parent.parent
ELF_SHA256 = '5bf707c3dc5dac0ad9635af7d336ec580f81c3f7876d0f55400d1900e3415d74'
NSO_SHA256 = 'f8d248109ff72999b4600ae3749f8c7397fb960f7ad3ab8dee3018ae9e14e900'
TALK_INDEX_SELECTOR = 0xf4dbd0
COUNTER_LOOKUP = 0xf4d560
COUNTER_QUERY_CONTEXT = 0xf4da70
KEY_FORMATTER = 0x47360
COUNTER_CONTEXT_GLOBAL = 0x32d0790


class CaseHarness:
    def __init__(self, reads):
        self.s = Sandbox()
        self.root = self.s.alloc(0x20)
        self.fake_save = self.s.alloc(0x2000)
        self.reads = list(reads)
        self.key_reads = []
        self.s.uc.mem_write(COUNTER_CONTEXT_GLOBAL,
                            struct.pack('<Q', self.root))
        self.s.uc.mem_write(self.root, struct.pack('<Q', self.fake_save))

        def controlled_counter_read(sb):
            string_object = sb.reg('x1')
            string_data = sb.u64(string_object + 8)
            key = sb.read(string_data, 64).split(b'\0', 1)[0].decode('ascii')
            self.key_reads.append(key)
            assert self.reads, f'unexpected extra read of {key}'
            return self.reads.pop(0)

        # The record lookup and its contextual setup are controlled. Native
        # selector code and original 0x47360 key formatting remain active.
        self.s.stub(COUNTER_LOOKUP, controlled_counter_read)
        self.s.stub(COUNTER_QUERY_CONTEXT, lambda _sb: None)

    def run(self, argument, expected, expected_keys):
        result = self.s.call(TALK_INDEX_SELECTOR, (argument,), limit=100_000)
        result = result & 0xffffffff
        if result == 0xffffffff:
            result = -1
        assert result == expected, (result, expected)
        assert self.key_reads == expected_keys, (self.key_reads, expected_keys)
        assert not self.reads, self.reads
        return {'argument': argument, 'selected_index': result,
                'controlled_counter_reads': list(zip(expected_keys, self._read_values))}

    @property
    def _read_values(self):
        # Filled by the caller before run; retained for artifact clarity.
        return getattr(self, 'initial_reads', [])


def run_case(name, argument, read_values, expected, expected_keys):
    harness = CaseHarness(read_values)
    harness.initial_reads = list(read_values)
    observed = harness.run(argument, expected, expected_keys)
    observed['name'] = name
    return observed


def main():
    cases = [
        run_case('initial_gate_mismatch', 4, [3], -1,
                 ['TalkNpc0Count']),
        run_case('first_match_at_index_2', 4, [4, 3, 3, 4], 2,
                 ['TalkNpc0Count', 'TalkNpc0Count',
                  'TalkNpc1Count', 'TalkNpc2Count']),
    ]
    nso_hash = hashlib.sha256(Path(DEFAULT_NSO).read_bytes()).hexdigest()
    assert nso_hash == NSO_SHA256, nso_hash
    result = {
        'cases': len(cases),
        'mismatches': [],
        'native_functions': {
            'talk_counter_index_selector': hex(TALK_INDEX_SELECTOR),
            'counter_lookup_boundary': hex(COUNTER_LOOKUP),
            'counter_query_context': hex(COUNTER_QUERY_CONTEXT),
            'native_key_formatter': hex(KEY_FORMATTER),
        },
        'cases_data': cases,
        'scope': ('Original 0xf4dbd0 instructions and 0x47360 key formatting '
                  'execute. The test stops each persisted counter lookup at '
                  '0xf4d560 and supplies controlled read results.'),
        'dependencies_stubbed': [
            {'va': hex(COUNTER_LOOKUP),
             'purpose': 'supplies a controlled sequence of per-key saved counter values'},
            {'va': hex(COUNTER_QUERY_CONTEXT),
             'purpose': 'skips unrelated query-context iteration setup'},
        ],
        'limits': [
            'No real save record or underlying f4d560/f4da70 lookup state was executed.',
            'This proves the selector returns the first index whose controlled TalkNpc%dCount read equals its argument, after an initial TalkNpc0Count gate.',
            'The callers 0x395bc0, 0x395e50, and 0x3960d0 are not executed; the result is not proven to be a conversation topic or message ID.',
        ],
        'elf_sha256': ELF_SHA256,
        'nso_sha256': nso_hash,
    }
    out = ROOT / 'output/gameplay/villager_social_followup/talk_index_selection_native.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps({'cases': len(cases), 'mismatches': 0,
                      'artifact': str(out.relative_to(ROOT))}, ensure_ascii=False),
          flush=True)


if __name__ == '__main__':
    main()
