"""Reproduce the uninitialized world-query context boundary at 0x7bccf0."""
from pathlib import Path
import hashlib
import json
import struct
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tools'))
from native_emulator import Sandbox, regs
from unicorn import UC_HOOK_MEM_INVALID, UcError

OUT = Path(__file__).resolve().parent
NSO = ROOT / 'inputs/additional_exefs/main'


def main():
    s = Sandbox()
    u = s.uc
    elf_hash = hashlib.sha256(s.image.data).hexdigest()
    nso_hash = hashlib.sha256(NSO.read_bytes()).hexdigest()
    assert elf_hash == '5bf707c3dc5dac0ad9635af7d336ec580f81c3f7876d0f55400d1900e3415d74'
    assert nso_hash == 'f8d248109ff72999b4600ae3749f8c7397fb960f7ad3ab8dee3018ae9e14e900'

    # Same register-level query form used by dac780/da86b0: position pointer,
    # null optional output, zero flags, and S0=0. The singleton below is not
    # initialized by Sandbox because it does not run the game's world startup.
    position = s.HEAP + 0x10000
    u.mem_write(position, struct.pack('<3f', 13.0, -7.0, 29.0))
    position_before = bytes(u.mem_read(position, 12))
    root_global = 0x32d0de8
    root_slot = int.from_bytes(u.mem_read(root_global, 8), 'little')
    assert root_slot == 0x33728b0
    root_before = int.from_bytes(u.mem_read(root_slot, 8), 'little')
    assert root_before == 0

    invalid = []

    def on_invalid(uc, access, address, size, value, user_data):
        invalid.append({
            'access': access,
            'address': hex(address),
            'size': size,
            'pc': hex(uc.reg_read(regs.UC_ARM64_REG_PC)),
        })
        return False

    u.hook_add(UC_HOOK_MEM_INVALID, on_invalid)
    error = None
    try:
        s.call(0x7bccf0, (position, 0, 0), (0.0,), limit=1000)
    except UcError as exc:
        error = f'{type(exc).__name__}: {exc}'

    assert error is not None
    assert len(invalid) == 1
    fault = invalid[0]
    assert fault == {
        'access': 19,
        'address': '0xf90033e8f9419e40',
        'size': 4,
        'pc': '0x172780',
    }
    position_after = bytes(u.mem_read(position, 12))
    assert position_after == position_before
    context_word = int.from_bytes(u.mem_read(0xa0, 8), 'little')
    assert context_word == 0xf90033e8f9419e10
    assert fault['address'] == hex(context_word + 0x30)

    result = {
        'native_function': '0x7bccf0',
        'source_identity': {
            'elf_sha256': elf_hash,
            'additional_exefs_main_sha256': nso_hash,
        },
        'input': {
            'x0_position_pointer': hex(position),
            'position_xyz': [13.0, -7.0, 29.0],
            'x1_optional_output': 'null',
            'w2_flags': 0,
            's0_query_y': 0.0,
        },
        'sandbox_state': {
            'root_global': hex(root_global),
            'root_global_points_to_slot': hex(root_slot),
            'root_pointer_in_fresh_sandbox': hex(root_before),
            'assumption': 'No game startup or world/context constructor ran; Sandbox maps original ELF segments and relocations only, then synthetic stack/heap/stop regions.',
        },
        'observed_chain': [
            {'va': '0x7bcd28', 'operation': 'load world-root slot through 0x32d0de8', 'value': hex(root_slot)},
            {'va': '0x7bcd2c', 'operation': 'load *root_slot', 'value': hex(root_before)},
            {'va': '0x7bcd30', 'operation': 'form context = root + 0x28', 'value': '0x28'},
            {'va': '0x1577b8', 'operation': 'read *(context + 0x78) from low mapped ELF bytes', 'value': hex(context_word)},
            {'va': '0x172780', 'operation': 'load word at candidate_grid + 0x30', 'effective_address': fault['address']},
        ],
        'native_result': {
            'completed': False,
            'exception': error,
            'fault': fault,
            'position_unchanged': position_after == position_before,
            'dependencies_stubbed': [],
            'callees_reached_before_fault': ['0x71cfa0', '0x1577a0', '0x18ba40', '0x172740'],
        },
        'evidence': {
            'query_bytes': 0x1c8,
            'query_sha256': hashlib.sha256(s.image.read(0x7bccf0, 0x1c8)).hexdigest(),
            'fault_instruction': 'ldr w10, [x20, #0x30]',
            'caller_registers': 'The 0xdac780 and 0xda86b0 query sites set X0=actor+0x278, X1=0, W2=0, S0=0 before BL 0x7bccf0.',
        },
        'limits': [
            'This is a reproducible harness-context fault, not a completed query result.',
            'The world singleton, broad-phase grid, candidate list, collision candidates, and any live query result are unavailable in the fresh Sandbox.',
            'No collider candidate selection, floor/landing scalar, or movement integration is proven.',
        ],
    }
    (OUT / 'player_7bccf0_boundary_native.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'query': '0x7bccf0', 'completed': False,
                      'fault_pc': fault['pc'], 'fault_address': fault['address'],
                      'root_pointer': hex(root_before),
                      'output': str(OUT / 'player_7bccf0_boundary_native.json')}), flush=True)


if __name__ == '__main__':
    main()
