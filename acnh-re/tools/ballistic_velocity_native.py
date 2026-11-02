"""Verify the three-register ballistic solver and its bounded player consumer.

The complete player state is not executed. The consumer block begins after
state setup and ends immediately after the motion-triplet builder call.
"""
from pathlib import Path
import hashlib
import itertools
import json
import math
import struct
from native_emulator import Sandbox, regs

ROOT = Path(__file__).resolve().parent.parent
def f32(value): return struct.unpack('<f', struct.pack('<f', value))[0]
def packed(values): return struct.pack('<3f', *values)


def reference(start, end, duration, gravity, cap):
    n = duration & 0xffffffff
    assert n
    gravity, cap = f32(abs(f32(gravity))), f32(cap)
    velocity = 0.; total = 0.
    for _ in range(n):
        velocity = f32(velocity-gravity)
        if cap < 0: velocity = max(cap, velocity)
        total = f32(total+velocity)
    divisor = f32(n)
    delta = [f32(b-a) for a, b in zip(start, end)]
    return (f32(delta[0]/divisor), f32(f32(delta[1]-total)/divisor),
            f32(delta[2]/divisor)), total


def main():
    s = Sandbox(); u = s.uc
    start_ptr, end_ptr, player, actor = [s.HEAP+n for n in (0x10000, 0x20000, 0x30000, 0x40000)]
    pairs = [((0., 0., 0.), (10., 5., -5.)),
             ((13.5, -5., 99.25), (-12.25, 8., 3.)),
             ((1., 2., 3.), (1., 2., 3.)),
             ((-2., 7., .5), (0., -20., -1.)),
             ((.1, -.2, .3), (.4, .5, -.6))]
    pairs = [(tuple(map(f32, a)), tuple(map(f32, b))) for a, b in pairs]
    groups = {'three_register_solver': 0, 'zero_duration': 0,
              'duration_low32_alias': 0, 'bounded_player_consumer': 0}
    samples = []
    def read_result():
        return tuple(struct.unpack('<f', struct.pack('<I', u.reg_read(getattr(regs, f'UC_ARM64_REG_S{i}'))))[0] for i in range(3))
    guard = b'\xa5'*16
    for (start, end), n, gravity, cap in itertools.product(
            pairs, [1, 2, 3, 4, 5, 8, 9, 16, 60, 120],
            [-.25, .25, -.2, 0., 1., -2.1], [0., -.0, .5, -1.5, -2.1]):
        u.mem_write(start_ptr-16, guard+packed(start)+guard)
        u.mem_write(end_ptr-16, guard+packed(end)+guard)
        s.call(0x1d280, (start_ptr, end_ptr, n), (gravity, cap), limit=5000)
        actual = read_result(); expected, offset = reference(start, end, n, gravity, cap)
        assert packed(actual) == packed(expected), (start, end, n, gravity, cap, actual, expected)
        assert bytes(u.mem_read(start_ptr-16, 44)) == guard+packed(start)+guard
        assert bytes(u.mem_read(end_ptr-16, 44)) == guard+packed(end)+guard
        groups['three_register_solver'] += 1
        if len(samples) < 5 and n in [1, 2, 60] and gravity == -.25 and cap == 0:
            samples.append({'start': start, 'target': end, 'duration': n, 'gravity': gravity,
                            'cap': cap, 'gravity_displacement_sum': offset, 'velocity_xyz': actual})
    for dy, cap in itertools.product([-2., 0., 2.], [0., -2.1]):
        u.mem_write(start_ptr, packed([1., 0., 2.])); u.mem_write(end_ptr, packed([5., dy, 6.]))
        s.call(0x1d280, (start_ptr, end_ptr, 0), (-.25, cap), limit=100)
        result = read_result()
        assert result[0] == 0. and result[2] == 0.
        assert math.isnan(result[1]) if dy == 0 else result[1] == math.copysign(math.inf, dy)
        groups['zero_duration'] += 1
    for n in [0x100000001, 0x100000005, 0xffffffff0000003c]:
        start, end = pairs[0]; u.mem_write(start_ptr, packed(start)); u.mem_write(end_ptr, packed(end))
        s.call(0x1d280, (start_ptr, end_ptr, n), (-.25, -2.1), limit=5000)
        expected, _ = reference(start, end, n, -.25, -2.1)
        assert packed(read_result()) == packed(expected)
        groups['duration_low32_alias'] += 1
    def q(p, v): u.mem_write(p, struct.pack('<Q', v))
    def d(p, v): u.mem_write(p, struct.pack('<I', v))
    registry = s.HEAP+0x50000
    q(s.image.ptr(0x32d16a8), registry); u.mem_write(registry, bytes(158*16))
    d(s.image.ptr(0x32d8b28), 0)
    u.mem_write(s.image.ptr(0x32fd7e8), b'\x01')
    parameter = s.image.ptr(0x32fd7f0)
    q(parameter+0x780, s.image.ptr(0x32d1bf0)+16)
    sp = s.STACK+0x1ff000
    terminal = struct.unpack('<f', s.image.read(0x29d5c8c, 4))[0]
    for (start, end), n, gravity in itertools.product(pairs, [1, 2, 5, 60], [-.25, -.2, 0.]):
        gravity = f32(gravity)
        u.mem_write(player-16, b'\xa5'*0x1820); q(player+0x68, actor)
        u.mem_write(actor+0x278, packed(start)); u.mem_write(sp+0x40, packed(end))
        u.mem_write(parameter+0x7a4, struct.pack('<f', gravity))
        before = bytes(u.mem_read(player-16, 0x1820))
        u.reg_write(regs.UC_ARM64_REG_X19, player); u.reg_write(regs.UC_ARM64_REG_X22, n)
        u.reg_write(regs.UC_ARM64_REG_SP, sp)
        u.emu_start(0xe17e54, 0xe17e94, timeout=5_000_000, count=10000)
        assert u.reg_read(regs.UC_ARM64_REG_PC) == 0xe17e94
        velocity, _ = reference(start, end, n, gravity, 0.)
        expected = bytearray(before)
        expected[16+0x574:16+0x580] = packed(velocity)
        expected[16+0xf58:16+0xf64] = packed([velocity[1], terminal, gravity])
        assert bytes(u.mem_read(player-16, 0x1820)) == expected
        assert bytes(u.mem_read(actor+0x278, 12)) == packed(start)
        assert bytes(u.mem_read(sp+0x40, 12)) == packed(end)
        groups['bounded_player_consumer'] += 1
    source = json.loads((ROOT/'output/byml_resolved/01079.json').read_text())
    result = {
        'groups': groups, 'cases': sum(groups.values()), 'mismatches': [],
        'solver': '0x1d280', 'return_abi': 'Homogeneous float3 returned in S0/S1/S2, not a single float.',
        'rules': ['Input X0=start vec3, X1=target vec3, W2=duration, S0=gravity, S1=negative cap or nonnegative disabled cap.',
                  'Build a zero-initialized gravity velocity sequence: subtract magnitude gravity each step; apply lower cap only if cap<0; sum f32 displacements.',
                  'Return[(targetX-startX)/N, (targetY-startY-gravity_sum)/N, (targetZ-startZ)/N], with native f32 operation order.',
                  'Duration0 uses native default X/Z but still divides the vertical difference by0: nonzero deltaY gives signed infinity, zero gives NaN.',
                  'Duration uses low32 bits. Tested positive durations1..120; very large durations are not executed.'],
        'samples': samples,
        'player_consumer': {'begin': '0xe17e54', 'stop_before': '0xe17e94', 'enclosing_function': '0xe17cb0',
                            'reconstructed_registers': ['X19=player', 'W22=positive duration', 'SP+0x40=target vec3'],
                            'callees_executed': ['0xdb17b0', '0x1d280', '0xdb17f0', 'native parameter resolver/typed getter'],
                            'stores': {'player+0x574': 'velocity XYZ', 'player+0xf58': '[velocityY, native terminal fallback -0.0, configured gravity]'},
                            'scope': 'Bounded original instruction block only. State prefix and continuation after0xe17e94 are not executed.'},
        'source_parameter': {'json': 'byml_resolved/01079.json', 'source': source['source'],
                             'source_sha256': source['source_sha256'],
                             'descriptor': 'mDefaultGravity.f32', 'source_value': source['root']['@PlayerActor']['@mDefaultGravity.f32']},
        'dependencies_stubbed': [],
        'limits': ['Selected finite inputs plus documented duration0 behavior; arbitrary NaN/infinite inputs are not covered.',
                   'The gravity sum begins at zero velocity. It is not proof that every runtime motion integrator uses the same cap semantics.',
                   'No full jump/vault state, collision response, landing or animation timing is executed.',
                   'Positive duration units are not proven seconds or a fixed frame rate.'],
        'elf_sha256': hashlib.sha256(s.image.data).hexdigest()
    }
    (ROOT/'output/mechanics/ballistic_velocity_native.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({'groups': groups, 'cases': result['cases'], 'mismatches': 0}), flush=True)


if __name__ == '__main__': main()
