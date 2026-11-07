"""Bounded probes of the original craft/pocket helpers with a partial fixture.

This is an execution attempt, not a transaction emulator. It records whether
the supplied synthetic Player/session fields reach the pocket-slot insertion
helper. It intentionally does not patch missing game managers or callbacks.
"""
from pathlib import Path
import hashlib
import json
import struct
import sys

SHARED = Path('/workspace/acnh-re')
TOOLS = Path(__file__).resolve().parent
REPO = TOOLS.parent
OUT = REPO / 'output' / 'gameplay' / 'crafting_transaction_followup'
MANIFEST = json.loads((SHARED / 'output' / 'manifest.json').read_text())
ANALYSIS_ELF = Path(MANIFEST['source_root']) / 'A_logic' / 'main.elf'
if (SHARED / '.deps').is_dir():
    sys.path.insert(0, str(SHARED / '.deps'))
sys.path.insert(0, str(TOOLS))

from native_emulator import Sandbox, regs  # noqa: E402
from unicorn import UC_HOOK_CODE, UC_HOOK_MEM_READ_UNMAPPED, UC_HOOK_MEM_WRITE_UNMAPPED  # noqa: E402


def sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def put_u64(uc, address, value):
    uc.mem_write(address, struct.pack('<Q', value))


def set_global(s, got, value):
    cell = struct.unpack('<Q', s.uc.mem_read(got, 8))[0]
    put_u64(s.uc, cell, value)
    return {'got_va': f'0x{got:x}', 'cell_va': f'0x{cell:x}',
            'fixture_value': f'0x{value:x}'}


def partial_player_fixture(s):
    u = s.uc
    manager = 0x70000000
    u.mem_map(manager, 0x500000)
    records = s.HEAP + 0x120000
    session = s.HEAP + 0x130000
    session_state = s.HEAP + 0x131000
    globals_written = [
        set_global(s, 0x32d4f90, manager),
        set_global(s, 0x32d4ff0, records),
        set_global(s, 0x32d0df0, session),
    ]
    u.mem_write(manager + 0x3cdd20, struct.pack('<I', 1))
    put_u64(u, session, session_state)
    u.mem_write(session_state + 0x476, b'\x00')
    for index in range(8):
        record = records + index * 0xb28
        u.mem_write(record + 0xb08, struct.pack('<I', 1))
        u.mem_write(record + 0xb0c, b'\x01')
        u.mem_write(record + 0xb0e, b'\x01')
    player_save = manager + 0x1e6aa0
    u.mem_write(player_save + 0x173e0 + 8, struct.pack('<Q', 1))
    return manager, records, globals_written


def run_probe(va, args, watch, expected_target, setup):
    s = Sandbox()
    u = s.uc
    setup_state = setup(s)
    executed = []
    watch_entries = []
    last_pcs = []
    fault = None

    def code_hook(uc, address, size, user_data):
        last_pcs.append(f'0x{address:x}')
        if len(last_pcs) > 32:
            del last_pcs[0]
        if address in watch:
            executed.append(f'0x{address:x}')
            registers = [uc.reg_read(getattr(regs, f'UC_ARM64_REG_X{i}')) for i in range(4)]
            entry = {'va': f'0x{address:x}',
                     'x0_x3': [f'0x{value:x}' for value in registers]}
            if address == 0xa774c0:
                manager_ptr = registers[0]
                if manager_ptr == 0:
                    entry['manager_pointer_is_null'] = True
                else:
                    try:
                        entry['manager_fields'] = {
                            'count_1c0': struct.unpack('<I', uc.mem_read(manager_ptr + 0x1c0, 4))[0],
                            'count_1b0': struct.unpack('<I', uc.mem_read(manager_ptr + 0x1b0, 4))[0],
                            'array_1b8': f'0x{struct.unpack("<Q", uc.mem_read(manager_ptr + 0x1b8, 8))[0]:x}',
                        }
                    except Exception as error:
                        entry['manager_fields_read_error'] = f'{type(error).__name__}: {error}'
            watch_entries.append(entry)

    def mem_fault(uc, access, address, size, value, user_data):
        nonlocal fault
        fault = {'address': f'0x{address:x}', 'pc': f'0x{uc.reg_read(regs.UC_ARM64_REG_PC):x}',
                 'size': size,
                 'x0_x3': [f'0x{uc.reg_read(getattr(regs, f"UC_ARM64_REG_X{i}")):x}'
                           for i in range(4)],
                 'last_pcs': last_pcs[-20:]}
        return False

    u.hook_add(UC_HOOK_CODE, code_hook)
    u.hook_add(UC_HOOK_MEM_READ_UNMAPPED, mem_fault)
    u.hook_add(UC_HOOK_MEM_WRITE_UNMAPPED, mem_fault)
    try:
        result = s.call(va, args, limit=1_000_000)
        return_value = f'0x{result:x}'
        exception = None
    except Exception as error:  # record first unhandled boundary, do not mask it
        return_value = None
        exception = f'{type(error).__name__}: {error}'
    return {
        'entry_va': f'0x{va:x}',
        'fixture': setup_state,
        'executed_watchpoints': executed,
        'watch_entries': watch_entries,
        'target_helper_reached': expected_target in executed,
        'return_value': return_value,
        'exception': exception,
        'first_unmapped_access': fault,
    }


def build_report():
    probes = {}

    def setup_craft(s):
        manager, _, globals_written = partial_player_fixture(s)
        cache_cell = struct.unpack('<Q', s.uc.mem_read(0x32f3f78, 8))[0]
        cache_value = struct.unpack('<Q', s.uc.mem_read(cache_cell, 8))[0]
        requirement = s.HEAP + 0xd0000
        context = s.HEAP + 0xe0000
        # RecipeCraftParam.UniqueID=56, output item 975, and the five actual
        # material IDs/amounts from the resolved table. Availability fields
        # and live ItemParam manager views are deliberately not fabricated.
        u = s.uc
        u.mem_write(requirement, bytes(0xb0))
        u.mem_write(requirement, struct.pack('<H', 0x4c7b))
        u.mem_write(requirement + 8, struct.pack('<HHI', 975, 0, 0))
        u.mem_write(requirement + 0x25, b'\x01')
        materials = [(2213, 1), (2285, 1), (2287, 1), (2214, 1), (2286, 1), (0xfffe, 0)]
        for index, (item_id, count) in enumerate(materials):
            offset = requirement + 0x2c + index * 0x14
            u.mem_write(offset, struct.pack('<HHI', item_id, 0, 0))
            u.mem_write(offset + 8, struct.pack('<H', count))
        # Set the consume-path discriminator once to test whether the native
        # gates can advance; native precheck may overwrite it.
        u.mem_write(requirement + 0x3c, struct.pack('<H', 1))
        u.mem_write(context, bytes(0x200))
        return {'manager_va': f'0x{manager:x}', 'requirement_va': f'0x{requirement:x}',
                'context_va': f'0x{context:x}', 'recipe_id': 56, 'output_item_id': 975,
                'material_slots': materials, 'global_setup': globals_written,
                'item_cache_global': {'got_va': '0x32f3f78', 'cell_va': f'0x{cache_cell:x}',
                                      'value_before_call': f'0x{cache_value:x}'},
                'limit': 'partial synthetic Player/session state; no live item-table/cache/UI objects'}

    craft = run_probe(
        0xee1420,
        (0x70000000, 0x500d0000, 0x500e0000),
        {0xee1420, 0xee0ed0, 0xeff060, 0xa9e440, 0xa774c0, 0xab9400,
         0xefbd30, 0xf99270},
        '0xefbd30', setup_craft)
    craft['fixture']['requirement_va'] = '0x500d0000'
    craft['fixture']['context_va'] = '0x500e0000'
    probes['ee1420'] = craft

    def setup_insert(s):
        manager, records, globals_written = partial_player_fixture(s)
        mode = s.HEAP + 0x10000
        descriptor = s.HEAP + 0x20000
        s.uc.mem_write(mode, bytes(0x40))
        s.uc.mem_write(descriptor, struct.pack('<HHI', 2213, 0, 0))
        service_cell = struct.unpack('<Q', s.uc.mem_read(0x32d3d78, 8))[0]
        service_value = struct.unpack('<Q', s.uc.mem_read(service_cell, 8))[0]
        return {'manager_va': f'0x{manager:x}', 'player_records_va': f'0x{records:x}',
                'mode_context_va': f'0x{mode:x}', 'descriptor_va': f'0x{descriptor:x}',
                'descriptor_item_id': 2213, 'global_setup': globals_written,
                'world_service_global': {'got_va': '0x32d3d78', 'cell_va': f'0x{service_cell:x}',
                                         'value_before_call': f'0x{service_value:x}'},
                'limit': '0x33d3d78 world/player service object was not reconstructed'}

    insertion = run_probe(
        0xefbd30,
        (0x50010000, 0x50020000),
        {0xefbd30, 0xeab1f0, 0xeab210, 0xe670b0, 0xf99270, 0xefb090},
        '0xf99270', setup_insert)
    insertion['fixture']['mode_context_va'] = '0x50010000'
    insertion['fixture']['descriptor_va'] = '0x50020000'
    probes['efbd30'] = insertion

    return {
        'schema': 'acnh.crafting.transaction_fixture_attempt.v1',
        'scope': 'Bounded execution of original main.elf instructions using partial synthetic manager/player records. Neither probe reaches the intended pocket insertion call; this is a blocker report, not a completed craft runtime test.',
        'provenance': {
            'analysis_elf_sha256': sha256(ANALYSIS_ELF),
            'main_nso_sha256': sha256(REPO / 'inputs' / 'additional_exefs' / 'main'),
        },
        'probes': probes,
        'blockers': {
            'ee1420': {
                'first_unmapped_access': probes['ee1420']['first_unmapped_access'],
                'path': '0xee1420 -> 0xee0ed0 -> 0xeff060 -> 0xa9e440 -> 0xa774c0 -> 0xab9400',
                'dependency_global': '0x32f3f78 (cell 0x354ce00)',
                'behavior': 'The partial fixture leaves the manager/table pointer at this GOT null. The original path passes null through 0xa774c0, then 0xab9400 dereferences the invalid returned pointer at 0xab941c. The manager semantics are unnamed here; no material helper return, conditional insertion, or rollback result was observed.',
            },
            'efbd30': {
                'function': '0xe670b0',
                'dependency_global': '0x33d3d78 (GOT 0x32d3d78)',
                'behavior': 'The player-context resolver loads the world/player manager from this global and returns null when it is zero; the partial fixture reproduces the early return before 0xf99270.',
                'initializer_context': 'World initialization 0x96ef0 invokes 0xf30220 with the object behind this global after broader engine setup; constructing the service vtable/state is outside the partial fixture.',
            },
        },
        'status': 'ORIGINAL CODE PARTIALLY EXECUTED; target insertion path remains unexecuted; serializer/write-to-file remains static-only.',
    }


def main():
    report = build_report()
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / 'crafting_transaction_fixture_attempt.json'
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n')
    print(path)


if __name__ == '__main__':
    main()
