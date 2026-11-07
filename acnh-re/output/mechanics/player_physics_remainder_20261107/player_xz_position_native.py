"""Bounded native proof of the X/Z velocity consumer in FUN_00f17cb0.

The timing/ballistic block and a later position-add block both execute original
ELF instructions. The intervening destination/ground-query path is not run.
"""
from pathlib import Path
import hashlib
import json
import struct
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tools'))
from native_emulator import Sandbox, regs

OUT = Path(__file__).resolve().parent
NSO = ROOT / 'inputs/additional_exefs/main'


def f32(value):
    return struct.unpack('<f', struct.pack('<f', value))[0]


def pack3(values):
    return struct.pack('<3f', *values)


def read3(data):
    return struct.unpack('<3f', data)


def q(u, address, value):
    u.mem_write(address, struct.pack('<Q', value))


def f(u, address, value):
    u.mem_write(address, struct.pack('<f', f32(value)))


def duration_for(case):
    if case.get('pair_absent') or case.get('primary_absent'):
        return 1
    primary_end = f32(case['primary_end'])
    endpoint = f32(case['fallback_end']) if primary_end < 0.0 else primary_end
    difference = f32(endpoint - f32(case['start_time']))
    count = max(0, min(0xffffffff, int(difference)))
    return count or 1


def velocity_reference(start, target, duration, gravity):
    velocity = 0.0
    gravity_sum = 0.0
    magnitude = f32(abs(f32(gravity)))
    for _ in range(duration):
        velocity = f32(velocity - magnitude)
        gravity_sum = f32(gravity_sum + velocity)
    n = f32(duration)
    delta = tuple(f32(b - a) for a, b in zip(start, target))
    return (f32(delta[0] / n), f32(f32(delta[1] - gravity_sum) / n),
            f32(delta[2] / n))


def main():
    s = Sandbox()
    u = s.uc
    elf_hash = hashlib.sha256(s.image.data).hexdigest()
    nso_hash = hashlib.sha256(NSO.read_bytes()).hexdigest()
    assert elf_hash == '5bf707c3dc5dac0ad9635af7d336ec580f81c3f7876d0f55400d1900e3415d74'
    assert nso_hash == 'f8d248109ff72999b4600ae3749f8c7397fb960f7ad3ab8dee3018ae9e14e900'

    player, actor, pair, primary, fallback, registry = [
        s.HEAP + n for n in (0x10000, 0x20000, 0x30000, 0x31000, 0x32000, 0x50000)
    ]
    sp = s.STACK + 0x1ff000
    vtable = s.image.ptr(0x32fbc00) + 16
    assert vtable == 0x30e38f8
    assert s.image.ptr(vtable + 0xf8) == 0xdb4fb0

    # Reconstruct the initialized PlayerActor parameter resolver path used by
    # the earlier native ballistic fixtures; all resolver/getter code remains
    # original. The source-bound default gravity is -0.25.
    q(u, s.image.ptr(0x32d16a8), registry)
    u.mem_write(registry, bytes(158 * 16))
    u.mem_write(s.image.ptr(0x32d8b28), struct.pack('<I', 0))
    u.mem_write(s.image.ptr(0x32fd7e8), b'\x01')
    parameter = s.image.ptr(0x32fd7f0)
    q(u, parameter + 0x780, s.image.ptr(0x32d1bf0) + 16)
    prior = json.loads((ROOT / 'output/mechanics/ballistic_velocity_native.json').read_text())
    gravity = f32(prior['source_parameter']['source_value'])
    assert gravity == f32(-0.25)
    f(u, parameter + 0x7a4, gravity)
    terminal = struct.unpack('<f', s.image.read(0x29d5c8c, 4))[0]

    cases = [
        {
            'name': 'three_step_primary_interval', 'start_time': 1.0,
            'primary_end': 4.0, 'fallback_end': 9.0,
            'start': (0.0, 0.0, 0.0), 'target': (10.0, 5.0, -5.0),
        },
        {
            'name': 'five_step_negative_axes', 'start_time': 0.5,
            'primary_end': 5.5, 'fallback_end': 12.0,
            'start': (3.5, 1.0, -8.0), 'target': (-2.5, -5.0, 6.0),
        },
        {
            'name': 'negative_primary_uses_fallback', 'start_time': 2.0,
            'primary_end': -1.0, 'fallback_end': 7.5,
            'start': (-4.0, 2.0, 10.0), 'target': (6.0, 12.0, -2.0),
        },
        {
            'name': 'minimum_one_step', 'start_time': 2.0,
            'primary_end': 2.0, 'fallback_end': 8.0,
            'start': (-1.0, 4.0, 3.0), 'target': (5.0, 6.0, -3.0),
        },
        {
            'name': 'vertical_only_leaves_xz', 'start_time': 0.0,
            'primary_end': 4.0, 'fallback_end': 8.0,
            'start': (2.0, -3.0, 5.0), 'target': (2.0, 9.0, 5.0),
        },
        {
            'name': 'negative_zero_primary_uses_primary', 'start_time': 4.0,
            'primary_end': -0.0, 'fallback_end': 12.0,
            'start': (7.0, 1.0, -2.0), 'target': (3.0, 2.0, 1.0),
        },
        {
            'name': 'fractional_interval_truncates', 'start_time': 0.25,
            'primary_end': 3.95, 'fallback_end': 12.0,
            'start': (-7.0, 0.5, 4.0), 'target': (1.0, -2.5, -3.0),
        },
        {
            'name': 'reverse_displacement', 'start_time': 1.0,
            'primary_end': 6.0, 'fallback_end': 10.0,
            'start': (11.0, -3.0, 8.0), 'target': (-1.0, -3.0, -4.0),
        },
    ]

    samples = []
    guard = b'\xa5' * 16
    for case in cases:
        start, target = tuple(map(f32, case['start'])), tuple(map(f32, case['target']))
        u.mem_write(player - 16, b'\xa5' * (0x1820 + 32))
        u.mem_write(actor - 16, b'\x5a' * (0x300 + 32))
        u.mem_write(pair - 16, guard + bytes(16) + guard)
        u.mem_write(primary - 16, guard + bytes(0x30) + guard)
        u.mem_write(fallback - 16, guard + bytes(0x20) + guard)
        q(u, player + 0x68, actor)
        q(u, actor, vtable)
        u.mem_write(actor + 0x278, pack3(start))
        u.mem_write(primary, bytes(0x30))
        u.mem_write(fallback, bytes(0x20))
        f(u, primary + 0x14, case['start_time'])
        f(u, primary + 0x18, case['primary_end'])
        f(u, fallback + 0x0c, case['fallback_end'])
        q(u, pair, primary)
        q(u, pair + 8, fallback)
        q(u, sp + 0x38, pair)
        u.mem_write(sp + 0x40, pack3(target))

        before_actor = bytes(u.mem_read(actor - 16, 0x300 + 32))
        before_pair = bytes(u.mem_read(pair - 16, 48))
        before_primary = bytes(u.mem_read(primary - 16, 16 + 0x30 + 16))
        before_fallback = bytes(u.mem_read(fallback - 16, 16 + 0x20 + 16))
        target_before = bytes(u.mem_read(sp + 0x40, 12))

        u.reg_write(regs.UC_ARM64_REG_SP, sp)
        u.reg_write(regs.UC_ARM64_REG_X19, player)
        u.reg_write(regs.UC_ARM64_REG_X22, 0xdeadbeef)
        u.emu_start(0xe17e0c, 0xe17e94, timeout=5_000_000, count=2000)
        assert u.reg_read(regs.UC_ARM64_REG_PC) == 0xe17e94

        duration = u.reg_read(regs.UC_ARM64_REG_X22) & 0xffffffff
        assert duration == duration_for(case), (case, duration)
        velocity = read3(u.mem_read(player + 0x574, 12))
        expected_velocity = velocity_reference(start, target, duration, gravity)
        assert pack3(velocity) == pack3(expected_velocity), (case, velocity, expected_velocity)
        triplet = read3(u.mem_read(player + 0xf58, 12))
        assert pack3(triplet) == pack3((velocity[1], terminal, gravity))
        assert bytes(u.mem_read(actor - 16, 0x300 + 32)) == before_actor

        before_consumer_player = bytes(u.mem_read(player - 16, 0x1820 + 32))
        before_consumer_actor = bytes(u.mem_read(actor - 16, 0x300 + 32))
        # This is the later original block in the same FUN_00f17cb0. The gap
        # from 0xe17e94 to 0xe17ff8 is intentionally supplied as context.
        u.reg_write(regs.UC_ARM64_REG_SP, sp)
        u.reg_write(regs.UC_ARM64_REG_X19, player)
        u.emu_start(0xe17ff8, 0xe18038, timeout=5_000_000, count=100)
        assert u.reg_read(regs.UC_ARM64_REG_PC) == 0xe18038

        actual_position = read3(u.mem_read(actor + 0x278, 12))
        expected_position = (f32(start[0] + velocity[0]), start[1],
                             f32(start[2] + velocity[2]))
        assert pack3(actual_position) == pack3(expected_position), (
            case, actual_position, expected_position)

        expected_actor = bytearray(before_consumer_actor)
        expected_actor[16 + 0x278:16 + 0x27c] = struct.pack('<f', expected_position[0])
        expected_actor[16 + 0x280:16 + 0x284] = struct.pack('<f', expected_position[2])
        assert bytes(u.mem_read(actor - 16, 0x300 + 32)) == expected_actor
        assert bytes(u.mem_read(player - 16, 0x1820 + 32)) == before_consumer_player
        assert bytes(u.mem_read(pair - 16, 48)) == before_pair
        assert bytes(u.mem_read(primary - 16, 16 + 0x30 + 16)) == before_primary
        assert bytes(u.mem_read(fallback - 16, 16 + 0x20 + 16)) == before_fallback
        assert bytes(u.mem_read(sp + 0x40, 12)) == target_before

        samples.append({
            'name': case['name'], 'duration_u32': duration,
            'start_xyz': start, 'target_xyz': target, 'velocity_xyz': velocity,
            'position_before_xyz': start, 'position_after_xyz': actual_position,
        })

    spans = [(0xe17e0c, 0x88), (0xe17ff8, 0x40), (0xdb4fb0, 8),
             (0xdb17b0, 0x2c), (0x1d280, 0x150), (0xdb17f0, 0x70)]
    evidence = [{'va': hex(begin), 'bytes': size,
                 'sha256': hashlib.sha256(s.image.read(begin, size)).hexdigest()}
                for begin, size in spans]
    result = {
        'native_function': '0xe17cb0',
        'executed_fragments': [
            {'begin': '0xe17e0c', 'stop_before': '0xe17e94',
             'purpose': 'Native record duration, gravity lookup, ballistic solve, and player velocity stores.'},
            {'begin': '0xe17ff8', 'stop_before': '0xe18038',
             'purpose': 'Native velocity X/Z additions through actor virtual position getter.'},
        ],
        'native_virtual_getter': {'va': '0xdb4fb0', 'bytes': 8,
                                  'rule': 'Return actor + 0x278.'},
        'rule': 'At 0xe18000 the native block adds player+0x574 to the returned vector X; at 0xe18018 it adds player+0x57c to vector Z. This fragment leaves vector Y unchanged.',
        'groups': {'composed_finite_cases': len(cases)},
        'cases': len(cases), 'mismatches': [], 'samples': samples,
        'harness': {
            'engine': 'Unicorn AArch64 over the supplied ELF image; no game or console OS.',
            'externally_reconstructed': [
                'Player and actor memory; player+0x68 points to actor.',
                'The original actor vtable pointer obtained from 0x32fbc00 plus 16.',
                'Stack+0x38 timing-record pair and record floats; Stack+0x40 target XYZ.',
                'Initialized parameter resolver tables and PlayerActor mDefaultGravity.f32 = -0.25.',
                'The destination/ground-query path between 0xe17e94 and 0xe18000 is skipped.'
            ],
            'dependencies_stubbed': [],
            'native_callees_executed': ['0xdb17b0', '0x1d280', '0xdb17f0', '0xdb4fb0',
                                        '0xe6fb50', '0xe70ea0', '0x5df70', '0x37a50'],
            'input_domain': 'Eight finite coordinate/timing cases; durations 1, 3, 4, and 5. No NaN, infinity, or long loop case.'
        },
        'evidence': evidence,
        'source_identity': {
            'elf_sha256': elf_hash,
            'additional_exefs_main': str(NSO),
            'additional_exefs_main_sha256': nso_hash,
            'relation': 'The existing ADDITIONAL_EXEFS.md audit records identical main-code segments for this ELF and NSO build.'
        },
        'limits': [
            'This composes two selected original instruction ranges with a reconstructed gap; it does not execute the whole 0xe17cb0 update.',
            'The proof shows the X/Z consumer and Y preservation in this block; landing, collision geometry, post-motion correction, and full traversal scheduling remain open.',
            'The supplied timing record and target are not identified as a specific gameplay timer or input producer; duration units are unknown.',
            'The finite test set is a bounded verification, not a proof for NaN, infinity, malformed pointers, or all runtime states.'
        ]
    }
    (OUT / 'player_xz_position_native.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'cases': len(cases), 'mismatches': 0,
                      'output': str(OUT / 'player_xz_position_native.json')}), flush=True)


if __name__ == '__main__':
    main()
