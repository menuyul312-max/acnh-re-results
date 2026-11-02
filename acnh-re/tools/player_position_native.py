"""Run the complete position updater on its non-animation branch.

The actor vtable is taken from its native constructor, not a synthetic callback.
The independent geometric oracle uses mathematical sine/cosine; native lookup
interpolation has a small, explicitly measured approximation error.
"""
from pathlib import Path
import hashlib
import itertools
import json
import math
import struct
from native_emulator import Sandbox

ROOT = Path(__file__).resolve().parent.parent


def f32(value):
    return struct.unpack('<f', struct.pack('<f', value))[0]


def main():
    s = Sandbox(); u = s.uc
    player, actor, context = [s.HEAP + n for n in (0x10000, 0x20000, 0x30000)]
    vtable = s.image.ptr(0x32fbc00) + 16
    assert vtable == 0x30e38f8 and s.image.ptr(vtable + 0xf8) == 0xdb4fb0
    groups = {'position_update_non_animation': 0, 'absent_actor': 0}
    max_delta_error = 0.0; max_table_error = 0.0; samples = []

    def q(address, value): u.mem_write(address, struct.pack('<Q', value))
    def d(address, value): u.mem_write(address, struct.pack('<I', value))
    def f(address, value): u.mem_write(address, struct.pack('<f', value))

    angles = [0, 1, 0x12345678, 0x20000000, 0x40000000, 0x6bdac135,
              0x80000000, 0x9abcdef0, 0xc0000000, 0xffffffff]
    vectors = [(0., 0.), (1.8, -.25), (-2., 3.5), (5., -2.1)]
    scales = [0., .5, 1., 2.]
    history_indices = [0, 29, 30, 31, 0xffffffff]
    for angle, (forward, vertical), scale, index, flags in itertools.product(
            angles, vectors, scales, history_indices, [0, 1, 8, 32]):
        u.mem_write(player - 16, b'\xa5' * (0x1800 + 32))
        u.mem_write(actor - 16, b'\x5a' * (0x400 + 32))
        u.mem_write(context, b'\x33' * 0x1000)
        q(player + 0x60, context); q(player + 0x68, actor); q(actor, vtable)
        d(player + 0xefc, flags); d(player + 0xf48, angle)
        f(player + 0xf50, forward); f(player + 0xf58, vertical)
        f(context + 0xd30, scale); d(player + 0x1740, index)
        initial = (13.25, -4., 100.5)
        u.mem_write(actor + 0x278, struct.pack('<3f', *initial))
        f(actor + 0x2dc, 7.25)
        before_player = bytes(u.mem_read(player - 16, 0x1820))
        before_actor = bytes(u.mem_read(actor - 16, 0x420))
        before_context = bytes(u.mem_read(context, 0x1000))
        # S0 is deliberately unrelated to the context scale. The true ABI uses
        # X0 for the player and obtains the scale via 0x7d1f00.
        s.call(0xdac550, (player,), (123.5,), limit=3000)
        delta_bytes = bytes(u.mem_read(actor + 0x294, 12))
        delta = struct.unpack('<3f', delta_bytes)
        theta = angle * (2 * math.pi / 2**32)
        expected_delta = (math.sin(theta) * f32(forward) * scale,
                          f32(vertical) * scale,
                          math.cos(theta) * f32(forward) * scale)
        error = max(abs(a-b) for a, b in zip(delta, expected_delta))
        max_delta_error = max(max_delta_error, error)
        # Half-angle quaternion interpolation is not exactly unit length. Its
        # yaw matrix therefore differs from exact mathematical sine/cosine.
        assert error <= 0.0004 * max(1., abs(forward * scale)), (angle, delta, expected_delta)
        half = angle >> 1
        table = s.image.ptr(0x32d1428)
        a, b, c, e = struct.unpack('<4f', s.image.read(table+(half>>24)*16, 16))
        fraction = f32((half & 0xffffff)*struct.unpack('<f', s.image.read(0x29d5c7c, 4))[0])
        qs, qc = f32(a+f32(b*fraction)), f32(c+f32(e*fraction))
        qx, qz = f32(qs*f32(2*qc)), f32(1-f32(qs*f32(2*qs)))
        table_reference = (f32(f32(f32(forward)*qx)*scale), f32(f32(vertical)*scale),
                           f32(f32(f32(forward)*qz)*scale))
        table_error = max(abs(a-b) for a, b in zip(delta, table_reference))
        max_table_error = max(max_table_error, table_error)
        assert table_error <= 0.000001 * max(1., abs(forward*scale)), (angle, delta, table_reference)
        pos = struct.unpack('<3f', u.mem_read(actor + 0x278, 12))
        assert pos == tuple(f32(a+b) for a, b in zip(initial, delta))
        expected_actor = bytearray(before_actor)
        expected_actor[16+0x278:16+0x284] = struct.pack('<3f', *pos)
        expected_actor[16+0x294:16+0x2a0] = delta_bytes
        expected_actor[16+0x2c8] = 0
        assert bytes(u.mem_read(actor-16, 0x420)) == expected_actor
        expected_player = bytearray(before_player)
        expected_player[16+0x12dc:16+0x12e8] = delta_bytes[:4] + b'\0'*4 + delta_bytes[8:]
        history = index if index < 30 else 0
        struct.pack_into('<f', expected_player, 16+0x16c8+4*history, 7.25)
        struct.pack_into('<I', expected_player, 16+0x1740, history+1)
        assert bytes(u.mem_read(player-16, 0x1820)) == expected_player
        assert bytes(u.mem_read(context, 0x1000)) == before_context
        groups['position_update_non_animation'] += 1
        if angle in (0, 0x40000000, 0x80000000) and forward == 1.8 and scale == 1 and index == 29 and flags == 0:
            samples.append({'angle32': hex(angle), 'delta': delta, 'position': pos,
                            'history_index_after': 30, 'max_math_oracle_error': error})
    for flags in [0, 2, 4, 6, 0xffffffff]:
        q(player + 0x68, 0); d(player+0xefc, flags)
        before = bytes(u.mem_read(player-16, 0x1820))
        s.call(0xdac550, (player,), limit=1000)
        assert bytes(u.mem_read(player-16, 0x1820)) == before
        groups['absent_actor'] += 1
    result = {
        'helper': '0xdac550', 'groups': groups, 'cases': sum(groups.values()), 'mismatches': [],
        'callees_executed': ['0x7bc0b0', '0x1cbd0', '0x7d1f00', '0xdb4fb0'],
        'actor_vtable': hex(vtable), 'actor_vtable_evidence': '0xdb4e70 stores *(0x32fbc00)+16 at actor+0',
        'actor_position_offset': '0x278', 'actor_delta_offset': '0x294',
        'scale': 'Float context+0xd30, obtained through actual 0x7d1f00; units and update frequency unproven.',
        'branch': 'Player flags at +0xefc have bits1/2 clear; player+0x60 is an existing context pointer.',
        'rules': [
            'Local input [0, player.f58, player.f50] is yaw-rotated and multiplied by the context scale.',
            'The full XYZ delta is added to actor position and copied to actor+0x294.',
            'Player+0x12dc receives X/Z delta with its middle Y field explicitly zero.',
            'Actor+0x2dc is sampled into a 30-entry player history at +0x16c8.',
            'Unsigned history index >=30 resets to0 before the write; the stored next index is1..30.',
            'No actor means the updater returns without changing player fields.'
        ],
        'oracle': 'Independent mathematical yaw rotation, absolute bound 0.0004*max(1,abs(forward*scale)); separate native-table quaternion reference bound0.000001*max(1,abs(forward*scale)). Position integration and memory effects checked exactly.',
        'trig_contract': 'Linear interpolation at half angle yields qs/qc; X coefficient is2*qs*qc, Z coefficient is1-2*qs*qs. Quaternion is not renormalized, so exact mathematical yaw is only an approximation.',
        'max_delta_error_against_math': max_delta_error, 'max_delta_error_against_table_quaternion': max_table_error,
        'samples': samples,
        'dependencies_stubbed': [],
        'reconstructed_state': ['Player/context/actor memory', 'Original actor vtable from constructor; constructor itself not executed'],
        'limits': ['Animation/root-motion branches are not executed.',
                   'Input acquisition, gravity/velocity updates, collision resolution and full frame scheduling remain unverified.',
                   'Finite inputs only; this is an isolated native updater, not a running game.'],
        'elf_sha256': hashlib.sha256(s.image.data).hexdigest()
    }
    (ROOT/'output/mechanics/player_position_native.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({'groups': groups, 'cases': result['cases'], 'max_delta_error': max_delta_error, 'mismatches': 0}), flush=True)


if __name__ == '__main__': main()
