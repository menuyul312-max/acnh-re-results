"""Bounded native checks for selected paths in FUN_00eac780 / ELF VA 0xdac780."""
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


def bits(value):
    return struct.unpack('<I', struct.pack('<f', f32(value)))[0]


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
    assert s.image.ptr(vtable + 0xf8) == 0xdb4fb0

    # Full function early return: original predicate dc80b0 says player+178 != 1,
    # then the absent collider at player+0xa0 skips the remaining work.
    early_cases = [0, 2, 0xffffffff]
    for gate_word in early_cases:
        u.mem_write(player - 16, b'\xa5' * (0x1820 + 32))
        u.mem_write(actor - 16, b'\x5a' * (0x300 + 32))
        q(u, player + 0x68, actor)
        q(u, player + 0xa0, 0)
        u.mem_write(player + 0x178, struct.pack('<I', gate_word))
        before_player = bytes(u.mem_read(player - 16, 0x1820 + 32))
        before_actor = bytes(u.mem_read(actor - 16, 0x300 + 32))
        s.call(0xdac780, (player,), limit=1000)
        assert bytes(u.mem_read(player - 16, 0x1820 + 32)) == before_player
        assert bytes(u.mem_read(actor - 16, 0x300 + 32)) == before_actor

    # Branch edge after the caller's dacc40 result has been produced. One-hot
    # state results 1/2/5/6 intersect mask 0x66 and arrive at the da86b0 call.
    state_results = [1, 2, 5, 6]
    state_edges = []
    for state_result in state_results:
        u.mem_write(player - 16, b'\xa5' * (0x1820 + 32))
        u.mem_write(actor - 16, b'\x5a' * (0x300 + 32))
        before_player = bytes(u.mem_read(player - 16, 0x1820 + 32))
        before_actor = bytes(u.mem_read(actor - 16, 0x300 + 32))
        u.reg_write(regs.UC_ARM64_REG_SP, sp)
        u.reg_write(regs.UC_ARM64_REG_X19, player)
        u.reg_write(regs.UC_ARM64_REG_X0, state_result)
        u.emu_start(0xdac7bc, 0xdac9e0, timeout=5_000_000, count=100)
        assert u.reg_read(regs.UC_ARM64_REG_PC) == 0xdac9e0
        assert bytes(u.mem_read(player - 16, 0x1820 + 32)) == before_player
        assert bytes(u.mem_read(actor - 16, 0x300 + 32)) == before_actor
        state_edges.append({'dacc40_result_u32': state_result,
                            'stopped_before_call_at': '0xdac9e0'})

    # Exercise the common actor-Y sink at the end of the correction branches.
    # S8 is the upstream selected value; query/math producers remain out of scope.
    sink_values = [-2.0, -0.0, 0.25, 1.5, 10.0]
    sink_samples = []
    for target_y in sink_values:
        u.mem_write(player - 16, b'\xa5' * (0x1820 + 32))
        u.mem_write(actor - 16, b'\x5a' * (0x300 + 32))
        q(u, player + 0x68, actor)
        q(u, actor, vtable)
        u.mem_write(actor + 0x278, struct.pack('<3f', 13.0, -7.0, 29.0))
        before_player = bytes(u.mem_read(player - 16, 0x1820 + 32))
        before_actor = bytes(u.mem_read(actor - 16, 0x300 + 32))
        u.reg_write(regs.UC_ARM64_REG_SP, sp)
        u.reg_write(regs.UC_ARM64_REG_X19, player)
        u.reg_write(regs.UC_ARM64_REG_X0, actor)
        u.reg_write(regs.UC_ARM64_REG_S8, bits(target_y))
        u.emu_start(0xdac9d0, 0xdac9e0, timeout=5_000_000, count=50)
        assert u.reg_read(regs.UC_ARM64_REG_PC) == 0xdac9e0
        actual = struct.unpack('<3f', u.mem_read(actor + 0x278, 12))
        assert struct.pack('<f', actual[1]) == struct.pack('<f', f32(target_y))
        assert struct.pack('<f', actual[0]) == struct.pack('<f', 13.0)
        assert struct.pack('<f', actual[2]) == struct.pack('<f', 29.0)
        expected_actor = bytearray(before_actor)
        expected_actor[16 + 0x27c:16 + 0x280] = struct.pack('<f', f32(target_y))
        assert bytes(u.mem_read(actor - 16, 0x300 + 32)) == expected_actor
        assert bytes(u.mem_read(player - 16, 0x1820 + 32)) == before_player
        sink_samples.append({'selected_s8': f32(target_y),
                             'actor_position_after': actual,
                             'stopped_before_da86b0_call_at': '0xdac9e0'})

    spans = [(0xdac780, 0x27c), (0xdac7bc, 0x224), (0xdac9d0, 0x10),
             (0xdc80b0, 0x0c), (0xdb4fb0, 8)]
    evidence = [{'va': hex(begin), 'bytes': size,
                 'sha256': hashlib.sha256(s.image.read(begin, size)).hexdigest()}
                for begin, size in spans]
    result = {
        'native_function': '0xdac780',
        'incoming_callers': {
            'status': 'No direct B/BL reference or relocation/code-pointer-array entry was found in the inspected main ELF evidence; incoming caller/frame schedule remains unresolved.',
            'scope': 'The outgoing path inside this function is mapped below.'
        },
        'outgoing_call_path': {
            'early_state_mask_edge': 'At 0xdac7bc, dacc40 result W0 is tested as 1<<state against 0x66; results 1,2,5,6 branch to 0xdac9e0, immediately before BL 0xda86b0.',
            'actor_y_correction_edge': 'Selected S8 reaches the virtual getter slot actor_vtable+0xf8 at 0xdac9d0; original getter 0xdb4fb0 returns actor+0x278; str s8,[x0,#4] writes actor+0x27c; BL 0xda86b0 follows at 0xdac9e4.',
            'tail_edge': 'A second branch at 0xdac9a4 restores the frame then branches to 0xda86b0.'
        },
        'static_branch_map': {
            'gate': 'Original 0xdc80b0 returns 1 iff u32(player+0x178)==1.',
            'gate_false': 'player+0xa0 == null returns without writes; otherwise a separate collider-property/scalar-smoothing path runs before state-dependent routing.',
            'gate_true': 'Copies actor+0x27c into player+0x1304, then player+0xefd bit0 selects query path versus dacc40 state routing.',
            'state_path': 'If (1<<W0)&0x66 is nonzero, skip the floor-query branch and call 0xda86b0. State 0 uses packed input player+0x1001 and 0x7c5570; other unmatched states call 0x7bccf0.',
            'query_result_consumer': '0x7bccf0 result is compared with actor+0x27c; unless player+0xf40==1, the selected S8 is max(query_result, actor_y). The selected scalar is written through the common actor-Y sink.'
        },
        'native_fixtures': {
            'full_function_early_return': {'cases': len(early_cases), 'gate_words': early_cases,
                                           'collider_pointer': 'null', 'writes': 0,
                                           'callee_executed': '0xdc80b0'},
            'state_to_da86b0_edge': {'cases': len(state_edges), 'mismatches': [],
                                     'state_results': state_edges,
                                     'injected_input': 'W0 at 0xdac7bc is supplied as the earlier 0xdacc40 result.'},
            'common_actor_y_sink': {'cases': len(sink_values), 'mismatches': [],
                                    'samples': sink_samples,
                                    'injected_input': 'S8 is the selected upstream query/floor scalar; query producer is not executed.'},
            'dependencies_stubbed': [],
            'native_callees_executed': ['0xdc80b0', '0xdb4fb0']
        },
        'evidence': evidence,
        'source_identity': {
            'elf_sha256': elf_hash,
            'additional_exefs_main': str(NSO),
            'additional_exefs_main_sha256': nso_hash,
            'relation': 'The existing ADDITIONAL_EXEFS.md audit records identical main-code segments for this ELF and NSO build.'
        },
        'limits': [
            'The 0x7bccf0 and 0x7c5570 query producers are not executed; the Y-sink fixture supplies S8.',
            'The collider-present scalar-smoothing branch and its e254a0/e6fb50/dd7040/dacc40 path are not executed.',
            'The state producer 0xdacc40 and actual state/frame caller of 0xdac780 remain unresolved.',
            'Calls to 0xda86b0 are established as static outgoing edges; this fixture stops before executing that callee.',
            'No complete player frame, collision geometry, penetration solver, or live game integration is proven.'
        ]
    }
    (OUT / 'dac780_postmotion_native.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'early_return_cases': len(early_cases),
                      'state_edges': len(state_edges), 'y_sink_cases': len(sink_values),
                      'mismatches': 0,
                      'output': str(OUT / 'dac780_postmotion_native.json')}), flush=True)


if __name__ == '__main__':
    main()
