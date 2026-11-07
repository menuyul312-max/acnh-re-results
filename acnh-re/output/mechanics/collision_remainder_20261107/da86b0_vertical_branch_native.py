"""Exercise selected original state branches in FUN_00ea86b0.

W0 at 0xda86e4 is an externally supplied result of the earlier state helper
0xdacc40. Branches that require 0x7bccf0 stop before that helper is called.
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


def f(u, address, value):
    u.mem_write(address, struct.pack('<f', f32(value)))


def q(u, address, value):
    u.mem_write(address, struct.pack('<Q', value))


def main():
    s = Sandbox()
    u = s.uc
    elf_hash = hashlib.sha256(s.image.data).hexdigest()
    nso_hash = hashlib.sha256(NSO.read_bytes()).hexdigest()
    assert elf_hash == '5bf707c3dc5dac0ad9635af7d336ec580f81c3f7876d0f55400d1900e3415d74'
    assert nso_hash == 'f8d248109ff72999b4600ae3749f8c7397fb960f7ad3ab8dee3018ae9e14e900'

    player, actor = s.HEAP + 0x10000, s.HEAP + 0x20000
    sp = s.STACK + 0x1ff000
    vtable = s.image.ptr(0x32fbc00) + 16
    assert vtable == 0x30e38f8
    assert s.image.ptr(vtable + 0x110) == 0xdb4f90
    # The native vtable slot is a branch stub into this original float setter.
    assert s.image.read(0x2eac0, 8) == bytes.fromhex('007c02bdc0035fd6')

    cases = [
        {'name': 'state_1_uses_player_1304', 'state_result': 1, 'lane': 'set_target',
         'player_target': 4.25, 'position_y': -2.0},
        {'name': 'state_5_uses_player_1304', 'state_result': 5, 'lane': 'set_target',
         'player_target': -1.5, 'position_y': 9.0},
        {'name': 'state_6_uses_player_1304', 'state_result': 6, 'lane': 'set_target',
         'player_target': 0.75, 'position_y': -4.0},
        {'name': 'state_2_positive_adds_actor_288', 'state_result': 2,
         'motion_y': 1.25, 'actor_288': 0.5, 'position_y': -3.0,
         'lane': 'set_sum'},
        {'name': 'state_2_zero_does_not_store', 'state_result': 2,
         'motion_y': 0.0, 'actor_288': 0.5, 'position_y': 2.0,
         'lane': 'no_store'},
        {'name': 'state_2_negative_does_not_store', 'state_result': 2,
         'motion_y': -0.25, 'actor_288': 0.5, 'position_y': 2.0,
         'lane': 'no_store'},
        {'name': 'state_0_routes_to_query_lane', 'state_result': 0,
         'lane': 'query_lane'},
        {'name': 'state_3_routes_to_query_lane', 'state_result': 3,
         'lane': 'query_lane'},
        {'name': 'state_4_routes_to_query_lane', 'state_result': 4,
         'lane': 'query_lane'},
        {'name': 'state_7_routes_to_query_lane', 'state_result': 7,
         'lane': 'query_lane'},
        {'name': 'state_u32_max_routes_to_query_lane',
         'state_result': 0xffffffff, 'lane': 'query_lane'},
    ]

    counts = {'set_target': 0, 'set_sum': 0, 'no_store': 0, 'query_lane': 0}
    samples = []
    for case in cases:
        u.mem_write(player - 16, b'\xa5' * (0x1820 + 32))
        u.mem_write(actor - 16, b'\x5a' * (0x300 + 32))
        q(u, player + 0x68, actor)
        q(u, actor, vtable)
        f(u, actor + 0x278, 10.0)
        f(u, actor + 0x27c, case.get('position_y', 3.0))
        f(u, actor + 0x280, -7.0)
        if 'actor_288' in case:
            f(u, actor + 0x288, case['actor_288'])
        if 'player_target' in case:
            f(u, player + 0x1304, case['player_target'])
        if 'motion_y' in case:
            f(u, player + 0xf58, case['motion_y'])

        player_before = bytes(u.mem_read(player - 16, 0x1820 + 32))
        actor_before = bytes(u.mem_read(actor - 16, 0x300 + 32))
        stop = 0xda8734 if case['lane'] == 'query_lane' else 0xda8774
        u.reg_write(regs.UC_ARM64_REG_SP, sp)
        u.reg_write(regs.UC_ARM64_REG_X19, player)
        u.reg_write(regs.UC_ARM64_REG_W0, case['state_result'])
        u.emu_start(0xda86e4, stop, timeout=5_000_000, count=100)
        assert u.reg_read(regs.UC_ARM64_REG_PC) == stop, (
            case['name'], hex(u.reg_read(regs.UC_ARM64_REG_PC)), hex(stop))

        if case['lane'] == 'set_target':
            expected_y = f32(case['player_target'])
        elif case['lane'] == 'set_sum':
            expected_y = f32(f32(case['motion_y']) + f32(case['actor_288']))
        else:
            expected_y = f32(case.get('position_y', 3.0))

        actual_y = struct.unpack('<f', u.mem_read(actor + 0x27c, 4))[0]
        assert struct.pack('<f', actual_y) == struct.pack('<f', expected_y), (
            case, actual_y, expected_y)
        expected_actor = bytearray(actor_before)
        if case['lane'] in ('set_target', 'set_sum'):
            expected_actor[16 + 0x27c:16 + 0x280] = struct.pack('<f', expected_y)
        assert bytes(u.mem_read(actor - 16, 0x300 + 32)) == expected_actor
        assert bytes(u.mem_read(player - 16, 0x1820 + 32)) == player_before

        counts[case['lane']] += 1
        samples.append({
            'name': case['name'], 'state_helper_result_w0': case['state_result'],
            'stopped_at': hex(stop), 'lane': case['lane'],
            'position_y_before': case.get('position_y', 3.0),
            'position_y_after': actual_y,
        })

    spans = [(0xda86e4, 0x90), (0xdb4f90, 4), (0x2eac0, 8)]
    evidence = [{'va': hex(begin), 'bytes': size,
                 'sha256': hashlib.sha256(s.image.read(begin, size)).hexdigest()}
                for begin, size in spans]
    result = {
        'native_function': '0xda86b0',
        'executed_fragment': {'begin': '0xda86e4', 'stop_before_by_lane': {
            'direct_set_or_no_store': '0xda8774',
            'query_path': '0xda8734'},
            'note': 'The earlier collider tests and BL to 0xdacc40 are outside this fragment.'},
        'state_branch_map': {
            'state_w0_in_1_5_6': 'The one-hot bit intersects 0x62; store player+0x1304 through the actor vtable +0x110 setter.',
            'state_w0_2': 'If player+0xf58 > 0, store f32(player+0xf58 + actor+0x288); otherwise bypass the Y store.',
            'other_tested_values': 'Branch to 0xda8734, whose next operation calls 0x7bccf0; fixture stops before that call.'
        },
        'actor_vtable': {
            'address': hex(vtable), 'slot_0x110': '0xdb4f90',
            'slot_target': '0x2eac0', 'target_rule': 'str s0, [x0, #0x27c]; ret'
        },
        'groups': counts, 'cases': len(cases), 'mismatches': [], 'samples': samples,
        'harness': {
            'engine': 'Unicorn AArch64 over the supplied ELF image; no game or console OS.',
            'injected_input': 'W0 at 0xda86e4 is the u32 return value supplied for the earlier native 0xdacc40 call.',
            'reconstructed': [
                'Player+0x68 actor pointer and original actor vtable from 0x32fbc00 + 16.',
                'Player+0x1304 and player+0xf58 scalar values where the selected branch reads them.',
                'Actor position vector at +0x278 and adjustment float at +0x288.'
            ],
            'dependencies_stubbed': [],
            'executed_native_vtable_path': ['0xdb4f90', '0x2eac0'],
            'not_executed': ['Earlier collider gate and 0xdacc40 state producer.',
                             'Query helper 0x7bccf0 and remainder of 0xda86b0.']
        },
        'evidence': evidence,
        'source_identity': {
            'elf_sha256': elf_hash,
            'additional_exefs_main': str(NSO),
            'additional_exefs_main_sha256': nso_hash,
            'relation': 'The existing ADDITIONAL_EXEFS.md audit records identical main-code segments for this ELF and NSO build.'
        },
        'limits': [
            'State index/result is supplied at W0; this test does not prove which gameplay state names produce these values.',
            'Collider gates before 0xda86e8 are not executed, so no collision-mask meaning is assigned.',
            'The query path at 0xda8734/0x7bccf0, geometric penetration response, friction, and complete update remain open.',
            'This is a selected native branch proof, not a full landing or physics simulation.'
        ]
    }
    (OUT / 'da86b0_vertical_branch_native.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'cases': len(cases), 'groups': counts, 'mismatches': 0,
                      'output': str(OUT / 'da86b0_vertical_branch_native.json')}), flush=True)


if __name__ == '__main__':
    main()
