"""Run the native per-talk counter wrapper to its save-field writer boundary.

The game code formats TalkNpc<resident>Count and TalkAllNpcCount, resolves a
per-player value, and forwards both to 0xce9390. The resolver and writer are
controlled boundaries; the formatter, index normalization, and wrapper body
execute as original AArch64 instructions.
"""
from pathlib import Path
import hashlib
import json
import struct

from nso_sandbox import DEFAULT_NSO, Sandbox


ROOT = Path(__file__).resolve().parent.parent
ELF_SHA256 = '5bf707c3dc5dac0ad9635af7d336ec580f81c3f7876d0f55400d1900e3415d74'
NSO_SHA256 = 'f8d248109ff72999b4600ae3749f8c7397fb960f7ad3ab8dee3018ae9e14e900'
TALK_COUNTER_WRAPPER = 0xce9af0
COUNTER_FORMATTER = 0x47360
PLAYER_INDEX_NORMALIZER = 0xda3fc0
PLAYER_COUNTER_RESOLVER = 0xeaa8c0
COUNTER_FIELD_WRITER = 0xce9390


class Harness:
    def __init__(self):
        self.s = Sandbox()
        self.u = self.s.uc
        self.resident_ptr = self.s.alloc(4)
        self.actor_context = self.s.alloc(0x20)
        self.resolver_calls = []
        self.writer_calls = []
        self.current_delta = 0

        def resolve_player_counter(sb):
            player_ptr = sb.reg('x0')
            player_index = sb.read(player_ptr, 1)[0]
            mode = sb.reg('w1')
            self.resolver_calls.append({'player_index_after_native_normalization': player_index,
                                        'resolver_mode': mode})
            return self.current_delta

        def capture_writer_boundary(sb):
            string_object = sb.reg('x0')
            string_data = sb.u64(string_object + 8)
            key = sb.read(string_data, 96).split(b'\0', 1)[0].decode('ascii')
            value_ptr = sb.reg('x2')
            value = struct.unpack('<I', sb.read(value_ptr, 4))[0]
            self.writer_calls.append({
                'key': key,
                'writer_operation': sb.reg('w1'),
                'value': value,
            })

        # The resolver depends on live save/runtime state. Return a controlled
        # value, while preserving the original wrapper's formatting and calls.
        self.s.stub(PLAYER_COUNTER_RESOLVER, resolve_player_counter)
        # Stop each native wrapper's writer call at entry and record its args.
        self.s.stub(COUNTER_FIELD_WRITER, capture_writer_boundary)

    def run(self, resident_slot, player_index, delta):
        self.current_delta = delta
        self.resolver_calls.clear()
        self.writer_calls.clear()
        self.u.mem_write(self.resident_ptr, struct.pack('<I', resident_slot))
        self.u.mem_write(self.actor_context, bytes([player_index]) + bytes(0x1f))
        self.s.call(TALK_COUNTER_WRAPPER, (self.resident_ptr, self.actor_context))
        normalized = player_index if player_index <= 7 else 0xff
        assert self.resolver_calls == [
            {'player_index_after_native_normalization': normalized, 'resolver_mode': 2},
            {'player_index_after_native_normalization': normalized, 'resolver_mode': 2},
        ], self.resolver_calls
        expected = [
            {'key': f'TalkNpc{resident_slot}Count', 'writer_operation': 1, 'value': delta},
            {'key': 'TalkAllNpcCount', 'writer_operation': 1, 'value': delta},
        ]
        assert self.writer_calls == expected, self.writer_calls
        return {'resident_slot': resident_slot, 'player_index_input': player_index,
                'resolver_value_input': delta, 'resolver_calls': list(self.resolver_calls),
                'writer_calls': list(self.writer_calls)}


def main():
    harness = Harness()
    inputs = [(0, 0, 1), (3, 5, 2), (9, 7, 6)]
    cases = [harness.run(*inputs_row) for inputs_row in inputs]
    nso_hash = hashlib.sha256(Path(DEFAULT_NSO).read_bytes()).hexdigest()
    assert nso_hash == NSO_SHA256, nso_hash

    result = {
        'cases': len(cases),
        'mismatches': [],
        'native_functions': {
            'talk_counter_wrapper': hex(TALK_COUNTER_WRAPPER),
            'format_key': hex(COUNTER_FORMATTER),
            'normalize_player_index': hex(PLAYER_INDEX_NORMALIZER),
            'resolve_player_counter': hex(PLAYER_COUNTER_RESOLVER),
            'save_field_writer_boundary': hex(COUNTER_FIELD_WRITER),
            'conversation_side_effect_caller': '0xc84240',
        },
        'cases_data': cases,
        'call_chain': ['0xc84240', '0xce9af0', '0x47360', '0xda3fc0',
                       '0xef62f0', '0xeaa8c0', '0xce9390'],
        'scope': ('Original 0xce9af0, 0x47360, 0xda3fc0 and 0xef62f0 execute. '
                  'Execution is intercepted at 0xce9390, where its key, operation '
                  'argument and value are captured.'),
        'dependencies_stubbed': [
            {'va': hex(PLAYER_COUNTER_RESOLVER),
             'purpose': 'supplies a controlled player-specific counter delta in place of live runtime/save lookup'},
            {'va': hex(COUNTER_FIELD_WRITER),
             'purpose': 'captures the original wrapper arguments without modifying save state'},
        ],
        'limits': [
            'The player-counter resolver result and actor context are prepared inputs; no live player or villager save was loaded.',
            'Execution stops before 0xce9390 performs its map/save lookup and update.',
            'The wrapper proves the two configured keys and forwarded controlled value; it does not establish the game-side semantic name or reset policy of TalkNpc%dCount / TalkAllNpcCount.',
            'The caller 0xc84240 is not executed in this test; its path to 0xce9af0 and its TalkCountToday gate are static call/pseudocode evidence.',
        ],
        'elf_sha256': ELF_SHA256,
        'nso_sha256': nso_hash,
    }
    out = ROOT / 'output/gameplay/villager_social_followup/talk_counter_native.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps({'cases': len(cases), 'mismatches': 0,
                      'writer_calls': sum(len(case['writer_calls']) for case in cases),
                      'artifact': str(out.relative_to(ROOT))}, ensure_ascii=False),
          flush=True)


if __name__ == '__main__':
    main()
