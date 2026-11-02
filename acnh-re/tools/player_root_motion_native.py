"""Verify animation-result consumption by the complete position updater.

Animation sample buffers are reconstructed; sampling/playback is not emulated.
All eligibility checks, vector readers, angle conversion and the updater itself
execute original instructions without replacement callbacks.
"""
from pathlib import Path
import hashlib
import itertools
import json
import math
import struct
from native_emulator import Sandbox
from player_position_native import f32

ROOT = Path(__file__).resolve().parent.parent


def main():
    s = Sandbox(); u = s.uc
    player, actor, context, model, controller, array, entry, motion = [
        s.HEAP+n for n in (0x10000, 0x20000, 0x30000, 0x40000,
                          0x50000, 0x60000, 0x61000, 0x62000)]
    vt = s.image.ptr(0x32fbc00)+16
    assert s.image.ptr(vt+0x140) == 0x26250
    angle_scale = struct.unpack('<f', s.image.read(0x29d6184, 4))[0]
    def q(p, v): u.mem_write(p, struct.pack('<Q', v))
    def d(p, v): u.mem_write(p, struct.pack('<I', v & 0xffffffff))
    def f(p, v): u.mem_write(p, struct.pack('<f', v))
    modes = ['valid', 'missing_model', 'disabled_model', 'blocked_model',
             'missing_controller', 'missing_data', 'controller_masked']
    groups = {mode: 0 for mode in modes}; samples = []; max_error = 0.
    for mode, flags, local_forward, yaw, scale, root_scale, root_vector, root_angles in itertools.product(
            modes, [2, 4, 6, 34, 36, 38], [0., 1.8], [0, 0x12345678],
            [.5, 1.], [0., 1.25], [(.75, .5, -1.25)], [(0., 0., 0.), (.125, -.25, .5)]):
        u.mem_write(player-16, b'\xa5' * 0x1820)
        u.mem_write(actor-16, b'\x5a' * 0x420)
        u.mem_write(context, bytes(0x1000)); u.mem_write(model, bytes(0x200))
        u.mem_write(controller, bytes(0x2000))
        q(player+0x60, context); q(player+0x68, actor); q(actor, vt)
        q(context+0x890, 0 if mode == 'missing_model' else model)
        q(model+0x70, 0 if mode == 'missing_controller' else controller)
        u.mem_write(model+0xa6, bytes([mode != 'disabled_model']))
        u.mem_write(model+0xac, bytes([mode == 'blocked_model']))
        d(controller+0x18, 1); q(controller+0x20, array); q(array, entry)
        q(entry+0x28, 0 if mode == 'missing_data' else motion)
        u.mem_write(controller+0x1d09, bytes([4 if mode == 'controller_masked' else 0]))
        u.mem_write(motion+12, struct.pack('<3f', *root_vector))
        u.mem_write(motion+24, struct.pack('<3f', *root_angles))
        d(player+0xefc, flags); f(player+0xf50, local_forward); f(player+0xf58, -.25)
        f(player+0x12d8, root_scale); f(context+0xd30, scale)
        initial_angles = (0xfffffff0, yaw, 0x80000000)
        u.mem_write(player+0xf44, struct.pack('<3I', *initial_angles))
        d(player+0x1308, 0x40000000)
        actor_angles = (0xfffffff0, 0x80000000, 0x10)
        u.mem_write(actor+0x2b0, struct.pack('<3I', *actor_angles))
        initial_pos = (10., 2., -30.)
        u.mem_write(actor+0x278, struct.pack('<3f', *initial_pos))
        d(player+0x1740, 30); f(actor+0x2dc, 7.25)
        before_player = bytes(u.mem_read(player-16, 0x1820))
        before_actor = bytes(u.mem_read(actor-16, 0x420))
        preserved = {p: bytes(u.mem_read(p, size)) for p, size in
                     [(context, 0x1000), (model, 0x200), (controller, 0x2000), (motion, 0x30)]}
        valid = mode == 'valid'
        angle_delta = tuple(int(f32(a*angle_scale)) & 0xffffffff if valid else 0 for a in root_angles)
        expected_angles = list(initial_angles)
        expected_actor_angles = list(actor_angles)
        if flags & 4:
            if flags & 32: expected_angles[1] = 0x40000000
            else: expected_angles = [(a+b)&0xffffffff for a, b in zip(initial_angles, angle_delta)]
            expected_actor_angles = [(a+b)&0xffffffff for a, b in zip(actor_angles, angle_delta)]
        local = [0., -.25, f32(local_forward)]
        if flags & 2 and valid:
            if flags & 32:
                magnitude = f32(math.sqrt(f32(f32(root_vector[0]**2)+f32(root_vector[2]**2))))
                local[2] = f32(local[2]+f32(root_scale*magnitude))
            else:
                local = [f32(a+f32(root_scale*b)) for a, b in zip(local, root_vector)]
        theta = expected_angles[1] * (2*math.pi/2**32)
        oracle = ((math.cos(theta)*local[0]+math.sin(theta)*local[2])*scale,
                  local[1]*scale,
                  (-math.sin(theta)*local[0]+math.cos(theta)*local[2])*scale)
        try: s.call(0xdac550, (player,), (123.5,), limit=15000)
        except Exception as error:
            from native_emulator import regs
            raise RuntimeError(f'{mode=} {flags=} PC={u.reg_read(regs.UC_ARM64_REG_PC):#x}: {error}') from error
        delta_bytes = bytes(u.mem_read(actor+0x294, 12)); delta = struct.unpack('<3f', delta_bytes)
        error = max(abs(a-b) for a, b in zip(delta, oracle)); max_error = max(max_error, error)
        assert error <= .0003 * max(1., *(abs(a) for a in local)), (mode, flags, delta, oracle)
        position = tuple(f32(a+b) for a, b in zip(initial_pos, delta))
        expected_actor = bytearray(before_actor)
        expected_actor[16+0x278:16+0x284] = struct.pack('<3f', *position)
        expected_actor[16+0x294:16+0x2a0] = delta_bytes
        expected_actor[16+0x2b0:16+0x2bc] = struct.pack('<3I', *expected_actor_angles)
        expected_actor[16+0x2c8] = 0
        assert bytes(u.mem_read(actor-16, 0x420)) == expected_actor, (mode, flags, 'actor')
        expected_player = bytearray(before_player)
        expected_player[16+0xf44:16+0xf50] = struct.pack('<3I', *expected_angles)
        expected_player[16+0x12dc:16+0x12e8] = delta_bytes[:4]+bytes(4)+delta_bytes[8:]
        struct.pack_into('<f', expected_player, 16+0x16c8, 7.25)
        struct.pack_into('<I', expected_player, 16+0x1740, 1)
        assert bytes(u.mem_read(player-16, 0x1820)) == expected_player, (mode, flags, 'player')
        for p, before in preserved.items(): assert bytes(u.mem_read(p, len(before))) == before
        groups[mode] += 1
        if mode == 'valid' and yaw == 0 and local_forward == 1.8 and scale == 1 and root_scale == 1.25 and root_angles[1] == -.25:
            samples.append({'flags': flags, 'local_delta': local, 'angle32_after': hex(expected_angles[1]), 'world_delta': delta})
    result = {
        'helper': '0xdac550', 'groups': groups, 'cases': sum(groups.values()), 'mismatches': [],
        'callees_executed': ['0x7bc0b0', '0x46f70', '0x46fa0', '0x1662fa0', '0x1662ff0',
                             '0x1f280c0', '0x1f27e80', '0x1f27fa0', '0x1ce20',
                             '0x26250', '0x1cbd0', '0x7d1f00', '0xdb4fb0'],
        'angle_conversion_scale_f32': angle_scale,
        'rules': ['Flags bit1 adds the sampled root translation times player+0x12d8 before yaw/scale.',
                  'With bit5 also set, it uses the XZ length along local Z; sampled root Y is ignored.',
                  'Flags bit2 converts the sampled float rotation to packed u32 and accumulates actor rotation.',
                  'With bit2 set and bit5 clear, all three player angles also accumulate with u32 wrap.',
                  'With bits2/5 set, player yaw is replaced by player+0x1308; player X/Z angles remain unchanged.',
                  'Model absent/disabled/blocked, controller absent, data absent or controller mask bit2 suppresses sampled contributions.'],
        'actor_rotation_offset': '0x2b0', 'samples': samples,
        'max_delta_error_against_math': max_error,
        'oracle': 'Independent mathematical yaw rotation with f32 additions/scaling, bounded error .0003*max(1,abs(local components)); angle wrap and memory effects checked exactly.',
        'dependencies_stubbed': [],
        'reconstructed_state': ['Original actor vtable', 'Existing animation model/controller, channel0 descriptor and sampled translation/rotation buffers'],
        'limits': ['Animation samples are supplied data. Playback, animation blending, resource loading and sample generation not executed.',
                   'Input/velocity/gravity/collision updates and full player-frame scheduling not executed.',
                   'Only finite samples and valid channel0 are exercised. Invalid controller-index logging paths not executed.'],
        'elf_sha256': hashlib.sha256(s.image.data).hexdigest()
    }
    (ROOT/'output/mechanics/player_root_motion_native.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({'groups': groups, 'cases': result['cases'], 'max_delta_error': max_error, 'mismatches': 0}), flush=True)


if __name__ == '__main__': main()
