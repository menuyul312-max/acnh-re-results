"""Extend the bounded player velocity proof to the state timing consumer.

The state prefix that produces the timing-record pair is not run. The block
from 0xe17e0c through (but not including) 0xe17e94 is original ARM64 code; its
parameter resolver, gravity getter, ballistic solver, and motion-triplet
builder execute natively without stubs.
"""
from pathlib import Path
import hashlib
import json
import struct
import sys

from native_emulator import Sandbox, regs

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'output/mechanics/player_physics_followup'
NSO = Path('/workspace/acnh-re/inputs/additional_exefs/main')


def f32(value):
    return struct.unpack('<f', struct.pack('<f', value))[0]


def pack3(values):
    return struct.pack('<3f', *values)


def read3(data):
    return struct.unpack('<3f', data)


def reference(start, target, duration, gravity):
    velocity = 0.0
    gravity_sum = 0.0
    magnitude = f32(abs(f32(gravity)))
    for _ in range(duration):
        velocity = f32(velocity - magnitude)
        gravity_sum = f32(gravity_sum + velocity)
    divisor = f32(duration)
    delta = [f32(b - a) for a, b in zip(start, target)]
    return (
        f32(delta[0] / divisor),
        f32(f32(delta[1] - gravity_sum) / divisor),
        f32(delta[2] / divisor),
    ), gravity_sum


def expected_duration(case):
    if case.get('pair_absent') or case.get('primary_absent'):
        return 1
    primary = f32(case['primary_end'])
    if primary < 0.0:
        assert case['fallback_end'] is not None
        endpoint = f32(case['fallback_end'])
    else:
        endpoint = primary
    difference = f32(endpoint - f32(case['start_time']))
    # ARM64 FCVTZU maps finite negative inputs to zero; zero is promoted to 1
    # by the following CSINC in the native block.
    candidate = max(0, min(0xffffffff, int(difference)))
    return candidate or 1


def main():
    s = Sandbox()
    u = s.uc
    elf_hash = hashlib.sha256(s.image.data).hexdigest()
    assert elf_hash == '5bf707c3dc5dac0ad9635af7d336ec580f81c3f7876d0f55400d1900e3415d74'
    nso_hash = hashlib.sha256(NSO.read_bytes()).hexdigest()
    assert nso_hash == 'f8d248109ff72999b4600ae3749f8c7397fb960f7ad3ab8dee3018ae9e14e900'

    player = s.HEAP + 0x10000
    actor = s.HEAP + 0x20000
    pair = s.HEAP + 0x30000
    primary = s.HEAP + 0x31000
    fallback = s.HEAP + 0x32000
    registry = s.HEAP + 0x50000
    sp = s.STACK + 0x1ff000

    def q(address, value):
        u.mem_write(address, struct.pack('<Q', value))

    def f(address, value):
        u.mem_write(address, struct.pack('<f', f32(value)))

    def read_float(address):
        return struct.unpack('<f', u.mem_read(address, 4))[0]

    # Reconstruct the initialized PlayerActor parameter resolver path already
    # used by ballistic_velocity_native.py. The fallback parameter row itself
    # and its typed float getter remain original native code.
    q(s.image.ptr(0x32d16a8), registry)
    u.mem_write(registry, bytes(158 * 16))
    u.mem_write(s.image.ptr(0x32d8b28), struct.pack('<I', 0))
    u.mem_write(s.image.ptr(0x32fd7e8), b'\x01')
    parameter = s.image.ptr(0x32fd7f0)
    q(parameter + 0x780, s.image.ptr(0x32d1bf0) + 16)

    prior_velocity = json.loads((ROOT / 'output/mechanics/ballistic_velocity_native.json').read_text())
    source = prior_velocity['source_parameter']
    gravity = f32(source['source_value'])
    assert gravity == f32(-0.25)
    f(parameter + 0x7a4, gravity)
    terminal = struct.unpack('<f', s.image.read(0x29d5c8c, 4))[0]

    cases = [
        {
            'name': 'primary_integer_interval', 'start_time': 1.0,
            'primary_end': 4.0, 'fallback_end': 9.0,
            'start': (0.0, 0.0, 0.0), 'target': (10.0, 5.0, -5.0),
        },
        {
            'name': 'primary_fraction_truncates', 'start_time': 0.25,
            'primary_end': 3.95, 'fallback_end': 12.0,
            'start': (2.0, -3.0, 5.0), 'target': (8.0, 7.0, -1.0),
        },
        {
            'name': 'equal_primary_interval_defaults_to_one', 'start_time': 2.0,
            'primary_end': 2.0, 'fallback_end': 8.0,
            'start': (-1.0, 4.0, 3.0), 'target': (5.0, 6.0, -3.0),
        },
        {
            'name': 'negative_primary_difference_defaults_to_one', 'start_time': 5.0,
            'primary_end': 1.0, 'fallback_end': 12.0,
            'start': (1.0, 2.0, 3.0), 'target': (1.0, 2.0, 3.0),
        },
        {
            'name': 'negative_primary_sentinel_uses_fallback', 'start_time': 2.0,
            'primary_end': -1.0, 'fallback_end': 7.5,
            'start': (-4.0, 2.0, 10.0), 'target': (6.0, 12.0, -2.0),
        },
        {
            'name': 'fallback_equal_interval_defaults_to_one', 'start_time': 4.0,
            'primary_end': -1.0, 'fallback_end': 4.0,
            'start': (0.0, 0.0, 0.0), 'target': (0.0, 0.0, 0.0),
        },
        {
            'name': 'negative_zero_uses_primary_branch', 'start_time': 4.0,
            'primary_end': -0.0, 'fallback_end': 12.0,
            'start': (0.0, 0.0, 0.0), 'target': (3.0, 2.0, 1.0),
        },
        {
            'name': 'absent_pair_defaults_to_one', 'pair_absent': True,
            'start': (2.0, 1.0, -3.0), 'target': (3.0, 2.0, -1.0),
        },
        {
            'name': 'absent_primary_record_defaults_to_one', 'primary_absent': True,
            'start': (1.0, 4.0, 2.0), 'target': (-3.0, 0.0, 6.0),
        },
    ]

    groups = {'primary_interval': 0, 'fallback_interval': 0, 'default_one': 0}
    samples = []
    guard = b'\xa5' * 16
    for case in cases:
        start = tuple(map(f32, case['start']))
        target = tuple(map(f32, case['target']))

        # Keep independent guard bands around every supplied state/position
        # object so the bounded original block cannot silently overwrite input.
        u.mem_write(player - 16, b'\xa5' * (0x1820 + 32))
        u.mem_write(actor - 16, b'\x5a' * (0x300 + 32))
        u.mem_write(pair - 16, guard + bytes(16) + guard)
        u.mem_write(primary - 16, guard + bytes(0x30) + guard)
        u.mem_write(fallback - 16, guard + bytes(0x20) + guard)
        q(player + 0x68, actor)
        u.mem_write(actor + 0x278, pack3(start))
        u.mem_write(sp + 0x40, pack3(target))

        u.mem_write(primary, bytes(0x30))
        u.mem_write(fallback, bytes(0x20))
        if not case.get('primary_absent') and not case.get('pair_absent'):
            f(primary + 0x14, case['start_time'])
            f(primary + 0x18, case['primary_end'])
        if case.get('fallback_end') is not None:
            f(fallback + 0x0c, case['fallback_end'])
        q(pair, 0 if case.get('primary_absent') else primary)
        q(pair + 8, fallback)
        q(sp + 0x38, 0 if case.get('pair_absent') else pair)

        player_before = bytes(u.mem_read(player - 16, 0x1820 + 32))
        actor_before = bytes(u.mem_read(actor - 16, 0x300 + 32))
        pair_before = bytes(u.mem_read(pair - 16, 48))
        primary_before = bytes(u.mem_read(primary - 16, 16 + 0x30 + 16))
        fallback_before = bytes(u.mem_read(fallback - 16, 16 + 0x20 + 16))
        target_before = bytes(u.mem_read(sp + 0x40, 12))

        u.reg_write(regs.UC_ARM64_REG_X19, player)
        u.reg_write(regs.UC_ARM64_REG_X22, 0xdeadbeef)
        u.reg_write(regs.UC_ARM64_REG_SP, sp)
        u.emu_start(0xe17e0c, 0xe17e94, timeout=5_000_000, count=2000)
        assert u.reg_read(regs.UC_ARM64_REG_PC) == 0xe17e94

        duration = u.reg_read(regs.UC_ARM64_REG_X22) & 0xffffffff
        expected_n = expected_duration(case)
        assert duration == expected_n, (case, duration, expected_n)
        expected_velocity, gravity_sum = reference(start, target, duration, gravity)
        actual_velocity = read3(u.mem_read(player + 0x574, 12))
        assert pack3(actual_velocity) == pack3(expected_velocity), (case, actual_velocity, expected_velocity)
        actual_triplet = read3(u.mem_read(player + 0xf58, 12))
        expected_triplet = (expected_velocity[1], terminal, gravity)
        assert pack3(actual_triplet) == pack3(expected_triplet), (case, actual_triplet, expected_triplet)

        expected_player = bytearray(player_before)
        expected_player[16 + 0x574:16 + 0x580] = pack3(expected_velocity)
        expected_player[16 + 0xf58:16 + 0xf64] = pack3(expected_triplet)
        assert bytes(u.mem_read(player - 16, 0x1820 + 32)) == expected_player
        assert bytes(u.mem_read(actor - 16, 0x300 + 32)) == actor_before
        assert bytes(u.mem_read(pair - 16, 48)) == pair_before
        assert bytes(u.mem_read(primary - 16, 16 + 0x30 + 16)) == primary_before
        assert bytes(u.mem_read(fallback - 16, 16 + 0x20 + 16)) == fallback_before
        assert bytes(u.mem_read(sp + 0x40, 12)) == target_before

        if case.get('pair_absent') or case.get('primary_absent') or expected_n == 1:
            groups['default_one'] += 1
        elif case['primary_end'] < 0.0:
            groups['fallback_interval'] += 1
        else:
            groups['primary_interval'] += 1
        if len(samples) < 6:
            samples.append({
                'name': case['name'], 'native_duration': duration,
                'start_xyz': start, 'target_xyz': target,
                'velocity_xyz': actual_velocity,
                'gravity_displacement_sum': gravity_sum,
                'motion_triplet': actual_triplet,
            })

    spans = [(0xe17e0c, 0x88), (0x1d280, 0x150), (0xdb17b0, 0x2c), (0xdb17f0, 0x70)]
    evidence = []
    for begin, size in spans:
        evidence.append({
            'va': hex(begin), 'bytes': size,
            'sha256': hashlib.sha256(s.image.read(begin, size)).hexdigest(),
        })

    result = {
        'groups': groups,
        'cases': len(cases),
        'mismatches': [],
        'native_block': {
            'begin': '0xe17e0c',
            'stop_before': '0xe17e94',
            'enclosing_function': '0xe17cb0',
            'duration_source': 'Stack+0x38 -> pair of pointers; primary record +0x14/+0x18, fallback record +0x0c.',
            'duration_rule': 'Use primary end unless it is <0; otherwise use fallback end. FCVTZU(end-start) becomes u32; zero becomes1.',
            'stores': {
                'player+0x574': 'native ballistic velocity XYZ',
                'player+0xf58': '[velocityY, native terminal fallback -0.0, configured mDefaultGravity]',
            },
            'native_callees': ['0xdb17b0', '0x1d280', '0xdb17f0', '0xe6fb50', '0xe70ea0', '0x5df70', '0x37a50'],
            'dependencies_stubbed': [],
            'externally_supplied_fragment_inputs': [
                'Target XYZ at stack+0x40, representing the earlier state prefix output.',
                'Timing-record pair at stack+0x38 and its primary/fallback float fields.',
                'Starting actor XYZ at actor+0x278.',
                'Initialized actor-type registry and PlayerActor parameter fallback object.',
            ],
            'scope': 'Original block starts after the earlier state-prefix queries and stops before the later position/landing work. It does not run a full update or establish duration units.',
        },
        'source_parameter': {
            'prior_native_evidence': 'output/mechanics/ballistic_velocity_native.json',
            'source': source['source'],
            'source_sha256': source['source_sha256'],
            'descriptor': 'PlayerActor.mDefaultGravity.f32',
            'value': gravity,
        },
        'evidence': evidence,
        'samples': samples,
        'source_identity': {
            'additional_exefs_main': str(NSO),
            'nso_sha256': nso_hash,
            'elf_sha256': elf_hash,
            'relation': 'The existing ADDITIONAL_EXEFS.md audit records the main NSO code segments as identical to this ELF build; NSO and ELF are read-only inputs.',
        },
        'runtime_versions': {'unicorn': '2.1.4', 'capstone': '5.0.7', 'pyelftools': '0.33'},
        'limits': [
            'The state-record producer and target-point producer before 0xe17e0c are not executed.',
            'Only finite interval and coordinate values shown in the samples are covered; NaN, infinity, and huge linear durations are not covered.',
            'The evidence connects a reconstructed timing record to native velocity/gravity fields; it does not identify the record as a specific gameplay timer or prove seconds/frame units.',
            'Collision response, landing correction, position query, full traversal scheduling, and a running game remain outside this test.',
        ],
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'player_state_velocity_native.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'groups': groups, 'cases': len(cases), 'mismatches': 0, 'output': str(OUT / 'player_state_velocity_native.json')}), flush=True)


if __name__ == '__main__':
    main()
