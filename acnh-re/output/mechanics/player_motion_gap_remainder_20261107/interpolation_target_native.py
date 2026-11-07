"""Test the distance-ratio Y-scalar path inside FUN_00f17cb0.

The complete gap is mapped from original instructions. This fixture executes
only 0xe17f58..0xe17ff8, with the earlier packed-position conversions supplied
by running the original 0xe99510 helper on the fields read in the gap prefix.
"""
from pathlib import Path
import hashlib
import json
import math
import struct
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tools'))
from native_emulator import Sandbox, regs

OUT = Path(__file__).resolve().parent
NSO = ROOT / 'inputs/additional_exefs/main'


def f32(value):
    return struct.unpack('<f', struct.pack('<f', value))[0]


def read_s(u, index):
    return struct.unpack('<f', struct.pack('<I', u.reg_read(getattr(regs, f'UC_ARM64_REG_S{index}'))))[0]


def f(u, address, value):
    u.mem_write(address, struct.pack('<f', f32(value)))


def q(u, address, value):
    u.mem_write(address, struct.pack('<Q', value))


def packed_point(x_mm, y_quarters, z_mm):
    return struct.pack('<ihi', x_mm, y_quarters, z_mm)


def native_point(s, address):
    s.call(0xe99510, (address,))
    return tuple(read_s(s.uc, i) for i in range(3))


def f32_distance(ax, az, bx, bz):
    dx = f32(ax - bx)
    dz = f32(az - bz)
    squared = f32(f32(dx * dx) + f32(dz * dz))
    return f32(math.sqrt(squared))


def expected_target(anchor, target, actor_xz):
    actor_distance = f32_distance(anchor[0], anchor[2], actor_xz[0], actor_xz[1])
    target_distance = f32_distance(anchor[0], anchor[2], target[0], target[2])
    if target_distance == 0.0:
        ratio = float('inf') if actor_distance > 0.0 else float('nan')
    else:
        ratio = f32(actor_distance / target_distance)
    t = f32(min(ratio, 1.0))
    if ratio < 0.0:
        t = 0.0
    delta_y = f32(target[1] - anchor[1])
    return f32(anchor[1] + f32(delta_y * t)), actor_distance, target_distance, t


def main():
    s = Sandbox()
    u = s.uc
    elf_hash = hashlib.sha256(s.image.data).hexdigest()
    nso_hash = hashlib.sha256(NSO.read_bytes()).hexdigest()
    assert elf_hash == '5bf707c3dc5dac0ad9635af7d336ec580f81c3f7876d0f55400d1900e3415d74'
    assert nso_hash == 'f8d248109ff72999b4600ae3749f8c7397fb960f7ad3ab8dee3018ae9e14e900'

    player, actor = s.HEAP + 0x10000, s.HEAP + 0x20000
    prop = s.HEAP + 0x40000
    sp = s.STACK + 0x1ff000
    scale = struct.unpack('<f', s.image.read(0x29d6404, 4))[0]
    assert scale == f32(0.001)

    cases = [
        {'name': 'actor_at_anchor', 'gate_word': 0,
         'first': (0, 4, 0), 'target': (100, 12, 0), 'actor_xz': (0.0, 0.0)},
        {'name': 'halfway_axis', 'gate_word': 0,
         'first': (0, 4, 0), 'target': (100, 12, 0), 'actor_xz': (0.05, 0.0)},
        {'name': 'past_target_clamps_to_one', 'gate_word': 0,
         'first': (0, 4, 0), 'target': (100, 12, 0), 'actor_xz': (0.25, 0.0)},
        {'name': 'halfway_diagonal', 'gate_word': 0,
         'first': (0, 4, 0), 'target': (300, 10, 400), 'actor_xz': (0.15, 0.20)},
        {'name': 'zero_target_distance_with_nonzero_actor_distance', 'gate_word': 0,
         'first': (0, 4, 0), 'target': (0, 10, 0), 'actor_xz': (0.05, 0.0)},
        {'name': 'predicate_false_skips_scalar_store', 'gate_word': 1,
         'first': (0, 4, 0), 'target': (100, 12, 0), 'actor_xz': (0.05, 0.0)},
        {'name': 'predicate_false_all_bits_skips_scalar_store', 'gate_word': 0xffffffff,
         'first': (300, -8, -400), 'target': (-100, 20, 0), 'actor_xz': (0.0, 0.0)},
    ]

    counts = {'predicate_true_interpolation': 0, 'predicate_false_skip': 0}
    samples = []
    for case in cases:
        u.mem_write(player - 16, b'\xa5' * (0x1820 + 32))
        u.mem_write(actor - 16, b'\x5a' * (0x300 + 32))
        u.mem_write(prop - 16, b'\x6b' * (0x320 + 32))
        q(u, player + 0x68, actor)
        q(u, player + 0x3f8, prop)
        # The gap reads two packed 10-byte positions and converts both through
        # original 0xe99510. Fixed-point X/Z are millimetres; Y is signed i16*0.25.
        u.mem_write(player + 0x1018, packed_point(*case['first']))
        u.mem_write(player + 0x1022, packed_point(*case['target']))
        anchor = native_point(s, player + 0x1018)
        target = native_point(s, player + 0x1022)
        assert len(anchor) == len(target) == 3

        f(u, actor + 0x278, case['actor_xz'][0])
        f(u, actor + 0x27c, 77.0)
        f(u, actor + 0x280, case['actor_xz'][1])
        u.mem_write(player + 0x178, struct.pack('<I', case['gate_word']))
        f(u, prop + 0x2ec, -99.0)
        u.mem_write(prop + 0x2e5, b'\x00')
        f(u, sp + 0x40, target[0])
        f(u, sp + 0x44, target[1])
        f(u, sp + 0x48, target[2])

        expected_y, actor_distance, target_distance, t = expected_target(
            anchor, target, case['actor_xz'])
        assert math.isfinite(expected_y)
        player_before = bytes(u.mem_read(player - 16, 0x1820 + 32))
        actor_before = bytes(u.mem_read(actor - 16, 0x300 + 32))
        prop_before = bytes(u.mem_read(prop - 16, 0x320 + 32))
        target_before = bytes(u.mem_read(sp + 0x40, 12))

        u.reg_write(regs.UC_ARM64_REG_SP, sp)
        u.reg_write(regs.UC_ARM64_REG_X19, player)
        u.reg_write(regs.UC_ARM64_REG_S8, struct.unpack('<I', struct.pack('<f', anchor[1]))[0])
        u.reg_write(regs.UC_ARM64_REG_S9, struct.unpack('<I', struct.pack('<f', anchor[0]))[0])
        u.reg_write(regs.UC_ARM64_REG_S10, struct.unpack('<I', struct.pack('<f', anchor[2]))[0])
        # The gap prefix sets S12 to the upper clamp value 1.0.
        u.reg_write(regs.UC_ARM64_REG_S12, struct.unpack('<I', struct.pack('<f', 1.0))[0])
        u.emu_start(0xe17f58, 0xe17ff8, timeout=5_000_000, count=300)
        assert u.reg_read(regs.UC_ARM64_REG_PC) == 0xe17ff8

        actual_y = struct.unpack('<f', u.mem_read(prop + 0x2ec, 4))[0]
        flag_after = u.mem_read(prop + 0x2e5, 1)[0]
        expected_written = case['gate_word'] == 0
        counts['predicate_true_interpolation' if expected_written else 'predicate_false_skip'] += 1
        if expected_written:
            assert struct.pack('<f', actual_y) == struct.pack('<f', expected_y), (
                case, anchor, target, actual_y, expected_y)
            assert flag_after == 1
            expected_prop = bytearray(prop_before)
            expected_prop[16 + 0x2ec:16 + 0x2f0] = struct.pack('<f', expected_y)
            expected_prop[16 + 0x2e5] = 1
        else:
            assert prop_before == bytes(u.mem_read(prop - 16, 0x320 + 32))
            expected_prop = bytearray(prop_before)
            assert actual_y == -99.0 and flag_after == 0
        assert bytes(u.mem_read(prop - 16, 0x320 + 32)) == expected_prop
        assert bytes(u.mem_read(player - 16, 0x1820 + 32)) == player_before
        assert bytes(u.mem_read(actor - 16, 0x300 + 32)) == actor_before
        assert bytes(u.mem_read(sp + 0x40, 12)) == target_before

        samples.append({
            'name': case['name'], 'predicate_field_player_178': case['gate_word'],
            'first_packed_xyz': case['first'], 'target_packed_xyz': case['target'],
            'first_world_xyz': anchor, 'target_world_xyz': target,
            'actor_xz_world': case['actor_xz'],
            'actor_distance_xz': actor_distance, 'target_distance_xz': target_distance,
            'clamped_ratio': t, 'written_target_y': actual_y if expected_written else None,
            'property_flag_after': flag_after,
        })

    spans = [
        (0xe17e94, 0x164), (0xe17f58, 0xa0), (0xe99510, 0x38),
        (0x1d5e0, 0x124), (0xdaa4a0, 0x5c), (0xdc80a0, 0x10),
        (0xe5a6a0, 0x18), (0xdb5050, 0x10),
    ]
    evidence = [{'va': hex(begin), 'bytes': size,
                 'sha256': hashlib.sha256(s.image.read(begin, size)).hexdigest()}
                for begin, size in spans]
    result = {
        'native_function': '0xe17cb0',
        'static_gap': {
            'begin': '0xe17e94', 'end_exclusive': '0xe17ff8',
            'prefix': [
                '0xe17e94 reads packed positions at player+0x1018 and player+0x1022 through 0xe99510; the converted values are held in S8/S9/S10 and SP+0x40..0x48.',
                '0x1d5e0 computes an X/Z direction value into SP+0x18 from the two converted point records; 0xdaa4a0 consumes it with stack constants and an actor virtual call.',
                '0xe17ef4..0xe17f20 builds a query key and calls 0x7d1e60. A zero W0 branches to 0xe17f58. A nonzero result calls 0x7d6970; a zero there jumps to the epilogue at 0xe18084. A nonzero result calls 0xdc80a0, then selects 0xdd6b40(player,6,1) or 0xdaaa50(player,6), and also reaches that epilogue.'
            ],
            'no_hit_path': 'At 0xe17f58, 0xdc80a0 returns 1 iff u32(player+0x178)==0. A zero return skips the scalar interpolation to 0xe17ff8; a nonzero return enters the distance-ratio block.',
            'interpolation_formula_finite_non_nan': 'dActor = hypot(anchorX-actorX, anchorZ-actorZ); dTarget = hypot(anchorX-targetX, anchorZ-targetZ); t = clamp(dActor/dTarget, 0, 1); targetScalar = anchorY + (targetY-anchorY)*t.',
            'output': '0xe5a6a0 selects player+0x3f8 when nonnull (otherwise a global default object); 0xdb5050 stores the scalar at selected_object+0x2ec and sets byte selected_object+0x2e5 to 1. This gap does not directly store actor+0x27c.'
        },
        'native_fixture': {
            'begin': '0xe17f58', 'stop_before': '0xe17ff8',
            'cases': len(cases), 'groups': counts, 'mismatches': [],
            'native_callees_executed': ['0xe99510', '0xdc80a0', '0xe5a6a0', '0xdb5050'],
            'dependencies_stubbed': [],
            'externally_reconstructed': [
                'Packed points at player+0x1018 and player+0x1022; their world triples are produced by original 0xe99510.',
                'Actor pointer at player+0x68 and actor X/Z position at +0x278/+0x280.',
                'Property object at player+0x3f8, plus target position XYZ at SP+0x40..0x48.',
                'S8/S9/S10 are seeded with the original conversion output for player+0x1018, matching the earlier gap prefix.'
            ],
            'skipped_context': [
                'The 0x7d1e60 lookup earlier in the gap; fixture represents its no-hit branch.',
                'The 0x1d5e0 and 0xdaa4a0 prefix calls; they do not supply the lower interpolation operands exercised here.',
                'The 0xe17ff8 X/Z position writes and function epilogue.'
            ],
            'domain': 'Finite packed points and actor positions; one dTarget=0 case uses nonzero dActor, yielding an infinite ratio that clamps to 1. No NaN distances.'
        },
        'samples': samples,
        'evidence': evidence,
        'source_identity': {
            'elf_sha256': elf_hash,
            'additional_exefs_main': str(NSO),
            'additional_exefs_main_sha256': nso_hash,
            'conversion_scale_float_at_0x29d6404': scale,
            'relation': 'The existing ADDITIONAL_EXEFS.md audit records identical main-code segments for this ELF and NSO build.'
        },
        'limits': [
            'The full gap was statically mapped, but only the 0xe17f58..0xe17ff8 predicate/interpolation path was executed natively.',
            'The 0x7d1e60 lookup hit branch and its 0x7d6970/0xdd6b40/0xdaaa50 behavior were not executed.',
            'The stored scalar is a selected property-object field, not a direct actor Y write; no claim assigns its gameplay name or proves subsequent application.',
            'Landing resolution, geometric penetration response, collision masks, complete update scheduling, and duration units remain open.'
        ]
    }
    (OUT / 'interpolation_target_native.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'cases': len(cases), 'groups': counts, 'mismatches': 0,
                      'output': str(OUT / 'interpolation_target_native.json')}), flush=True)


if __name__ == '__main__':
    main()
