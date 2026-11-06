"""Run the original friendship delta calculation to its save-writer boundary.

The getter is supplied with a controlled per-villager friendship value. The
original 0xd34f80 code computes the candidate and calls 0xef2c70 with the
"Friendship" save key; the harness stops at that call before mutating a save.
"""
from collections import Counter
from pathlib import Path
import hashlib
import json
import struct

from nso_sandbox import DEFAULT_NSO, Sandbox
from unicorn import UC_HOOK_CODE, arm64_const as regs


ROOT = Path(__file__).resolve().parent.parent
ELF_SHA256 = '5bf707c3dc5dac0ad9635af7d336ec580f81c3f7876d0f55400d1900e3415d74'
NSO_SHA256 = 'f8d248109ff72999b4600ae3749f8c7397fb960f7ad3ab8dee3018ae9e14e900'
FRIENDSHIP_DELTA = 0xd34f80
FRIENDSHIP_LEVEL = 0xd34a20
SAVE_WRITER = 0xef2c70
FRIENDSHIP_KEY_VA = 0x29a5d44
LEVEL_FLOORS = (0, 30, 60, 100, 150, 200)


def level(points):
    if points < 30:
        return 1
    if points < 60:
        return 2
    if points < 100:
        return 3
    if points < 150:
        return 4
    if points < 200:
        return 5
    return 6


def expected_candidate(old, delta):
    candidate = (old + delta) & 0xffffffff
    old_level = level(old)
    if level(candidate) < old_level:
        candidate = LEVEL_FLOORS[old_level - 1]
    return candidate


class Harness:
    def __init__(self):
        self.s = Sandbox()
        self.u = self.s.uc
        self.row = self.s.HEAP + 0x10000
        self.wrapper = self.s.HEAP + 0x20000
        self.current = 0
        self.writer_args = None

        # Controlled save read: ef2320 returns a synthetic row, ee9350 exposes
        # that row to f486c0, and f486c0 reads the prepared Friendship value.
        self.s.stub(0xef2320, lambda _sb: self.row)

        def make_member_wrapper(sb):
            destination = sb.reg('x0')
            source = sb.reg('x1')
            sb.uc.mem_write(self.wrapper, struct.pack('<QQQ', 0, 0, source))
            sb.uc.mem_write(destination, struct.pack('<QQQ', 0, self.wrapper, 0))
            return None

        self.s.stub(0xee9350, make_member_wrapper)
        self.s.stub(0xf486c0, lambda sb: sb.u32(sb.reg('x0')))
        self.s.stub(0xee93d0, lambda _sb: 0)

        def stop_before_save_write(uc, pc, _size, _data):
            assert pc == SAVE_WRITER
            x2 = uc.reg_read(regs.UC_ARM64_REG_X2)
            key_ptr = struct.unpack('<Q', bytes(uc.mem_read(x2 + 8, 8)))[0]
            key = bytes(uc.mem_read(key_ptr, 64)).split(b'\0', 1)[0].decode()
            self.writer_args = {
                'resident_slot': uc.reg_read(regs.UC_ARM64_REG_W0),
                'player_slot': uc.reg_read(regs.UC_ARM64_REG_W1),
                'key': key,
                'candidate_points': uc.reg_read(regs.UC_ARM64_REG_W3),
                'network_mode': uc.reg_read(regs.UC_ARM64_REG_W4),
            }
            uc.emu_stop()

        self.stop_hook = self.u.hook_add(
            UC_HOOK_CODE, stop_before_save_write,
            begin=SAVE_WRITER, end=SAVE_WRITER)

    def run(self, resident_slot, player_slot, old, delta):
        self.current = old
        self.writer_args = None
        self.u.mem_write(self.row + 0x38, struct.pack('<I', old))
        for index, value in enumerate((resident_slot, player_slot, delta, 0)):
            self.u.reg_write(getattr(regs, f'UC_ARM64_REG_X{index}'), value & 0xffffffff)
        self.u.reg_write(regs.UC_ARM64_REG_SP, self.s.STACK + 0x1ff000)
        self.u.reg_write(regs.UC_ARM64_REG_X30, self.s.STOP)
        self.u.emu_start(FRIENDSHIP_DELTA, self.s.STOP,
                         timeout=5_000_000, count=100_000)
        pc = self.u.reg_read(regs.UC_ARM64_REG_PC)
        assert pc == SAVE_WRITER, hex(pc)
        assert self.writer_args is not None
        return self.writer_args

    def close(self):
        self.u.hook_del(self.stop_hook)


def main():
    cases = [
        ('zero_to_one', 0, 1),
        ('cross_30', 29, 1),
        ('cross_60', 59, 1),
        ('cross_100', 99, 1),
        ('cross_150', 149, 1),
        ('cross_200', 199, 1),
        ('within_band', 100, 3),
        ('floor_at_30', 30, -1),
        ('floor_at_60', 60, -1),
        ('floor_at_100', 100, -1),
        ('floor_at_150', 150, -1),
        ('floor_at_200', 200, -1),
        ('loss_inside_band', 99, -1),
    ]
    harness = Harness()
    samples = []
    groups = Counter()
    level_samples = []
    for points in (0, 29, 30, 59, 60, 99, 100, 149, 150, 199, 200, 255):
        observed_level = harness.s.call(FRIENDSHIP_LEVEL, (points,))
        assert observed_level == level(points), (points, observed_level, level(points))
        level_samples.append({'points': points, 'observed_level': observed_level})
    for name, old, delta in cases:
        observed = harness.run(1, 2, old, delta)
        expected = expected_candidate(old, delta)
        assert observed == {
            'resident_slot': 1,
            'player_slot': 2,
            'key': 'Friendship',
            'candidate_points': expected,
            'network_mode': 0,
        }, (name, observed, expected)
        groups['boundary_loss' if delta < 0 and level(old + delta) < level(old)
               else 'ordinary_delta'] += 1
        samples.append({'name': name, 'starting_points': old, 'delta': delta,
                        'starting_level': level(old),
                        'candidate_at_save_writer': observed['candidate_points'],
                        'candidate_level': level(observed['candidate_points']),
                        'save_writer_args': observed})
    harness.close()

    nso_hash = hashlib.sha256(Path(DEFAULT_NSO).read_bytes()).hexdigest()
    assert nso_hash == NSO_SHA256, nso_hash
    result = {
        'cases': len(cases) + len(level_samples),
        'groups': {**dict(groups), 'level_thresholds': len(level_samples)},
        'mismatches': [],
        'native_functions': {
            'conversation_side_effect_caller': '0xc84240',
            'friendship_delta_wrapper': '0xd34cb0',
            'delta_and_floor_calculation': '0xd34f80',
            'save_field_writer': '0xef2c70',
            'friendship_level_converter': '0xd34a20',
        },
        'save_binding': {
            'key': 'Friendship',
            'key_va': hex(FRIENDSHIP_KEY_VA),
            'local_record_base_formula_in_0xef2c70':
                'save_base + resident_slot*0x10798 + player_slot*0xa8 + 0x39f8',
            'network_record_base_formula_in_0xef2c70':
                'save_base + resident_slot*0x10798 + player_slot*0x700 + 0x1c0',
            'field_selector': '0xef2c70 forwards the Friendship key to 0xf48840 on the selected record; this harness stops at 0xef2c70 entry.',
        },
        'samples': samples,
        'level_threshold_samples': level_samples,
        'prepared_context': {
            'resident_slot': 1,
            'player_slot': 2,
            'starting_friendship': 'Synthetic u32 read from row+0x38 by a controlled getter stub.',
            'network_mode': 0,
        },
        'scope': 'Original 0xd34f80 instructions execute through candidate calculation and branch to the original 0xef2c70 save-writer entry. The setter body is not entered.',
        'dependencies_stubbed': [
            {'va': '0xef2320', 'purpose': 'returns a synthetic resident save-row address'},
            {'va': '0xee9350', 'purpose': 'constructs a minimal member wrapper around the prepared synthetic row'},
            {'va': '0xf486c0', 'purpose': 'reads the controlled starting Friendship u32'},
            {'va': '0xee93d0', 'purpose': 'releases the synthetic wrapper without side effects'},
        ],
        'limits': [
            'Execution stops on entry to 0xef2c70, before its save mutation and field-selector call 0xf48840.',
            'The starting points are controlled; no live villager/player save was loaded.',
            'The tested negative deltas show 0xd34f80 floors a cross-level decrease at the starting level threshold. This does not identify a daily decay source or prove that negative deltas occur in normal gameplay.',
            'The talk caller and ConversationHost/ConversationGuest state handlers are not executed by this test.',
        ],
        'elf_sha256': ELF_SHA256,
        'nso_sha256': nso_hash,
    }
    out = ROOT / 'output/gameplay/villager_social_followup/friendship_delta_native.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps({'cases': len(cases) + len(level_samples),
                      'delta_cases': len(cases),
                      'level_cases': len(level_samples),
                      'groups': {**dict(groups), 'level_thresholds': len(level_samples)},
                      'mismatches': 0,
                      'artifact': str(out.relative_to(ROOT))}, ensure_ascii=False),
          flush=True)


if __name__ == '__main__':
    main()
