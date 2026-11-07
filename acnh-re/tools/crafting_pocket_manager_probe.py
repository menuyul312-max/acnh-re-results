"""Run the original craft pocket wrapper with a bounded player-manager fixture.

This fixture reconstructs only the fields read by the player resolver and the
0x17c pocket-member accessor. Two view-service virtual calls are synthetic
success stubs; item records and ItemParam/ItemKind tables come from the dump.
It is not a full island/player/save runtime.
"""
from pathlib import Path
import hashlib
import json
import struct
import sys

TOOLS = Path(__file__).resolve().parent
REPO = TOOLS.parent
SHARED = Path('/workspace/acnh-re')
OUT = REPO / 'output' / 'gameplay' / 'crafting_transaction_followup'
sys.path.insert(0, str(SHARED / '.deps'))
sys.path.insert(0, str(TOOLS))

from unicorn import (UC_HOOK_CODE, UC_HOOK_MEM_READ_UNMAPPED,
                     UC_HOOK_MEM_WRITE, UC_HOOK_MEM_WRITE_UNMAPPED)  # noqa: E402
from native_emulator import Sandbox, regs  # noqa: E402
import inventory_requirements_native as item_tables  # noqa: E402
import crafting_transaction_fixture_attempt as prior_fixture  # noqa: E402

item_tables.ROOT = SHARED


def sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def load_recipe_56():
    table_path = SHARED / 'output' / 'tables_resolved' / 'RecipeCraftParam.json'
    table = json.loads(table_path.read_text())
    columns = {col['name']: index for index, col in enumerate(table['columns'])}
    row = next(row for row in table['rows']
               if row[columns['UniqueID']] == 56)
    materials = [row[columns[f'Material{i}']] for i in range(1, 7)]
    amounts = [row[columns[f'Amount{i}']] for i in range(1, 7)]
    return {
        'recipe_id': 56,
        'result_item_id': row[columns['Item']],
        'material_item_ids': [item for item in materials if item != 0xfffe],
        'material_slots': [
            {'slot': index, 'item_id': materials[index], 'amount': amounts[index]}
            for index in range(6)
        ],
        'table': table,
    }


def initialize_manager_fixture(s, pocket_item_id, descriptor_item_id):
    u = s.uc
    _, save_records, globals_written = prior_fixture.partial_player_fixture(s)

    # 0xe670b0 -> 0xf2d640 reads count +0xe8 and member-array pointer +0xf0;
    # the array entry stride is 0x3ce50. 0xf8f400 falls back through +0x118.
    member_array = s.HEAP + 0x140000
    world_player_manager = s.HEAP + 0x180000
    active_player_view = s.HEAP + 0x190000
    pocket_record = s.HEAP + 0x1a0000
    u.mem_write(world_player_manager, bytes(0x300))
    u.mem_write(world_player_manager + 0xe8, struct.pack('<I', 1))
    prior_fixture.put_u64(u, world_player_manager + 0xf0, member_array)
    u.mem_write(member_array, bytes(0x3ce50))
    prior_fixture.put_u64(u, world_player_manager + 0x118, active_player_view)
    manager_global = prior_fixture.set_global(s, 0x32d3d78, world_player_manager)

    # The active view exposes the 0x17c pocket member as base + offset and a
    # service object at +0x28. Its two virtual calls are deliberately bounded.
    u.mem_write(pocket_record, bytes(0x17c))
    u.mem_write(pocket_record + 0x158, struct.pack('<I', 1))
    u.mem_write(pocket_record + 0xa0, struct.pack('<I', 0))
    u.mem_write(pocket_record + 0x178, b'\0')
    empty_word = struct.pack('<HHI', 0xfffe, 0, 0)
    for slot in range(20):
        u.mem_write(pocket_record + 0xb8 + slot * 8, empty_word)
    if pocket_item_id is not None:
        u.mem_write(pocket_record + 0xb8,
                    struct.pack('<HHI', pocket_item_id, 0, 0))
    prior_fixture.put_u64(u, active_player_view + 0x78, pocket_record)
    prior_fixture.put_u64(u, active_player_view + 0x80, 0)

    proxy = s.HEAP + 0x1b0000
    validity_object = s.HEAP + 0x1b1000
    validity_vtable = s.HEAP + 0x1b2000
    provider = s.HEAP + 0x1b3000
    provider_vtable = s.HEAP + 0x1b4000
    validity_stub = s.HEAP + 0x1b5000
    provider_stub = s.HEAP + 0x1b5010
    for address in (proxy, validity_object, validity_vtable, provider,
                    provider_vtable):
        u.mem_write(address, bytes(0x100))
    prior_fixture.put_u64(u, active_player_view + 0x98, proxy)
    prior_fixture.put_u64(u, proxy + 0x10, validity_object)
    prior_fixture.put_u64(u, validity_object, validity_vtable)
    prior_fixture.put_u64(u, validity_vtable, validity_stub)
    prior_fixture.put_u64(u, proxy + 0x20, provider)
    prior_fixture.put_u64(u, provider, provider_vtable)
    prior_fixture.put_u64(u, provider_vtable + 0x20, provider_stub)
    # mov w0, #1 ; ret — validity and access-projection methods only.
    u.mem_write(validity_stub, bytes.fromhex('20008052c0035fd6'))
    u.mem_write(provider_stub, bytes.fromhex('20008052c0035fd6'))

    empty_singleton = s.HEAP + 0x1b6000
    u.mem_write(empty_singleton, empty_word)
    u.mem_write(0x32d25e0, struct.pack('<Q', empty_singleton))

    mode_context = s.HEAP + 0x10000
    item_descriptor = s.HEAP + 0x20000
    u.mem_write(mode_context, bytes(0x40))
    u.mem_write(item_descriptor,
                struct.pack('<HBBI', descriptor_item_id, 0, 0, 0))
    return {
        'save_records_va': f'0x{save_records:x}',
        'save_player_record_state': {
            'slot_index': 0,
            'state_u32_at_plus_0xb08': 1,
            'active_flag_at_plus_0xb0c': 1,
            'resolver_subindex_at_plus_0xb0d': 0,
        },
        'manager_global': manager_global,
        'world_player_manager_va': f'0x{world_player_manager:x}',
        'manager_count_member': {'offset': '0xe8', 'value': 1},
        'manager_array_member': {
            'offset': '0xf0', 'value_va': f'0x{member_array:x}',
            'element_stride': '0x3ce50',
        },
        'active_view_member': {
            'manager_offset': '0x118', 'value_va': f'0x{active_player_view:x}'},
        'pocket_record_va': f'0x{pocket_record:x}',
        'pocket_record_size': '0x17c',
        'pocket_layout': {
            'active_slot_count_offset': '0x158',
            'secondary_slot_count_offset': '0xa0',
            'slot_records_offset': '0xb8',
            'slot_record_stride': 8,
            'dirty_slot_markers_offset': '0x15c',
            'category_byte_offset': '0x178',
        },
        'pocket_slot0_before': (
            None if pocket_item_id is None else
            list(struct.unpack('<HHI', u.mem_read(pocket_record + 0xb8, 8)))
        ),
        'pocket_slot0_fixture_item_id': pocket_item_id,
        'item_descriptor_va': f'0x{item_descriptor:x}',
        'item_descriptor_bytes': bytes(u.mem_read(item_descriptor, 8)).hex(),
        'view_proxy_fields': {
            'player_plus_0x70_plus_8_base_pointer': f'0x{pocket_record:x}',
            'player_plus_0x70_plus_0x10_offset': 0,
            'player_plus_0x70_plus_0x28_proxy': f'0x{proxy:x}',
            'validity_virtual_method_stub_va': f'0x{validity_stub:x}',
            'access_virtual_method_stub_va': f'0x{provider_stub:x}',
            'stub_instruction_bytes': '20008052c0035fd6',
        },
        'limits': [
            'The 0x33d3d78 member array and +0x118 active view are synthetic records sized to fields read by this path.',
            'The two view-service virtual methods return success from synthetic code; their actual runtime implementations remain unknown.',
            'The full 0x3ce50-byte player member and unrelated runtime managers are not reconstructed.',
        ],
        '_addresses': {
            'pocket_record': pocket_record,
            'mode_context': mode_context,
            'item_descriptor': item_descriptor,
            'validity_stub': validity_stub,
            'provider_stub': provider_stub,
        },
    }


def run_case(name, pocket_item_id, descriptor_item_id):
    s = Sandbox()
    item_table_info = item_tables.install_item_tables(s)
    fixture = initialize_manager_fixture(s, pocket_item_id, descriptor_item_id)
    addresses = fixture.pop('_addresses')
    executed = []
    slot_mutator_calls = []
    writes = []
    fault = None
    watched = {
        0xefbd30, 0xef6700, 0xeab1f0, 0xe670b0, 0xf2d640,
        0xf8f400, 0xee9350, 0xee94f0, 0xf99270, 0xf98650,
        0xefb090, addresses['validity_stub'], addresses['provider_stub'],
    }
    pocket = addresses['pocket_record']

    def code_hook(uc, address, _size, _user_data):
        if address not in watched:
            return
        entry = {
            'va': f'0x{address:x}',
            'x0_x3': [f'0x{uc.reg_read(getattr(regs, f"UC_ARM64_REG_X{i}")):x}'
                      for i in range(4)],
        }
        executed.append(entry)
        if address == 0xf98650:
            slot_mutator_calls.append({
                'slot_index': uc.reg_read(regs.UC_ARM64_REG_X1),
                'source_descriptor_va': f'0x{uc.reg_read(regs.UC_ARM64_REG_X2):x}',
                'source_descriptor_bytes': bytes(uc.mem_read(
                    uc.reg_read(regs.UC_ARM64_REG_X2), 8)).hex(),
            })

    def write_hook(uc, _access, address, size, value, _user_data):
        if pocket <= address < pocket + 0x17c:
            writes.append({
                'pc': f'0x{uc.reg_read(regs.UC_ARM64_REG_PC):x}',
                'offset': f'0x{address - pocket:x}',
                'size': size,
                'value': f'0x{value:x}',
            })

    def unmapped_hook(uc, _access, address, size, _value, _user_data):
        nonlocal fault
        fault = {
            'pc': f'0x{uc.reg_read(regs.UC_ARM64_REG_PC):x}',
            'address': f'0x{address:x}',
            'size': size,
        }
        return False

    s.uc.hook_add(UC_HOOK_CODE, code_hook)
    s.uc.hook_add(UC_HOOK_MEM_WRITE, write_hook)
    s.uc.hook_add(UC_HOOK_MEM_READ_UNMAPPED, unmapped_hook)
    s.uc.hook_add(UC_HOOK_MEM_WRITE_UNMAPPED, unmapped_hook)
    before = bytes(s.uc.mem_read(pocket, 0x17c))
    try:
        s.call(0xefbd30,
               (addresses['mode_context'], addresses['item_descriptor']),
               limit=1_000_000)
        error = None
    except Exception as exc:  # preserve the native fault as an explicit result
        error = f'{type(exc).__name__}: {exc}'
    after = bytes(s.uc.mem_read(pocket, 0x17c))
    changed_offsets = [index for index, (old, new) in enumerate(zip(before, after))
                       if old != new]
    return {
        'case': name,
        'entry_va': '0xefbd30',
        'descriptor_item_id': descriptor_item_id,
        'fixture': {key: value for key, value in fixture.items()
                    if not key.startswith('_')},
        'executed_native_vas': [entry['va'] for entry in executed],
        'native_entries': executed,
        'slot_mutator_calls': slot_mutator_calls,
        'pocket_write_events': writes,
        'pocket_changed_offsets': [f'0x{index:x}' for index in changed_offsets],
        'slot0_before': list(struct.unpack('<HHI', before[0xb8:0xc0])),
        'slot0_after': list(struct.unpack('<HHI', after[0xb8:0xc0])),
        'dirty_slot0_before': before[0x15c],
        'dirty_slot0_after': after[0x15c],
        'active_slot_count_before_after': [
            struct.unpack('<I', before[0x158:0x15c])[0],
            struct.unpack('<I', after[0x158:0x15c])[0],
        ],
        'native_error': error,
        'first_unmapped_access': fault,
        'item_table_sources': {
            'ItemParam_raw_sha256': item_table_info['item_raw_sha256'],
            'ItemKind_raw_sha256': item_table_info['kind_raw_sha256'],
        },
    }


def build_report():
    recipe = load_recipe_56()
    material_item = recipe['material_item_ids'][0]
    result_item = recipe['result_item_id']
    analysis_elf = Path(json.loads(
        (SHARED / 'output' / 'manifest.json').read_text())['source_root']) / 'A_logic' / 'main.elf'
    nso = REPO / 'inputs' / 'additional_exefs' / 'main'
    material = run_case('recipe_56_material_descriptor_existing_stack',
                        material_item, material_item)
    result = run_case('recipe_56_result_descriptor_control',
                      result_item, result_item)
    native_chain = [
        0xefbd30, 0xeab1f0, 0xe670b0, 0xf2d640, 0xf8f400,
        0xee9350, 0xee94f0, 0xf99270,
    ]
    return {
        'schema': 'acnh.crafting.pocket_manager_probe.v1',
        'scope': 'Original 0xefbd30 and 0xf99270 execute against a partial manager/view fixture. The target item insertion/content outcome remains a bounded leaf result, not a full craft transaction.',
        'provenance': {
            'analysis_elf_sha256': sha256(analysis_elf),
            'main_nso_sha256': sha256(nso),
            'recipe_craft_param_path': 'output/tables_resolved/RecipeCraftParam.json',
            'recipe_id': recipe['recipe_id'],
            'result_item_id': result_item,
            'material_slots': recipe['material_slots'],
        },
        'fixture_contract': {
            'world_player_manager_global': '0x33d3d78 (GOT 0x32d3d78)',
            'world_player_manager_contract': {
                'count_member_offset': '0xe8',
                'member_array_pointer_offset': '0xf0',
                'member_stride': '0x3ce50',
                'active_view_pointer_offset': '0x118',
            },
            'pocket_member_view_contract': {
                'member_offset': '+0x70',
                'base_pointer_offset': '+0x8',
                'view_offset': '+0x10',
                'service_proxy_offset': '+0x28',
                'pocket_record_size': '0x17c',
                'item_records_offset': '0xb8',
                'active_slot_count_offset': '0x158',
                'dirty_slot_markers_offset': '0x15c',
            },
            'virtual_methods_stubbed': [
                {'edge': '0xee9350 validity query via member+0x28/+0x10',
                 'return_value': 1},
                {'edge': '0xee94f0 view access via member+0x28/+0x20',
                 'return_value': 1},
            ],
            'native_functions_not_stubbed': [f'0x{va:x}' for va in native_chain],
        },
        'probes': {'material': material, 'result_descriptor_control': result},
        'claims': {
            'material_descriptor_reaches_native_slot_helper':
                'PROVEN ON PARTIAL MANAGER/VIEW FIXTURE'
                if '0xf99270' in material['executed_native_vas'] else 'NOT REACHED',
            'material_helper_calls_and_dirty_marker':
                'PROVEN ON PARTIAL FIXTURE' if material['slot_mutator_calls']
                and material['dirty_slot0_after'] == 0xff else 'NOT OBSERVED',
            'result_descriptor_effect_in_f99270':
                ('NATIVE HELPER REACHED; no f98650 call, slot write, or dirty-byte write'
                 if '0xf99270' in result['executed_native_vas']
                 and not result['slot_mutator_calls'] and not result['pocket_write_events']
                 else 'NOT ESTABLISHED'),
            'full_save_member_dirty_state_and_durable_flush': 'OPEN',
            'full_player_manager_runtime_layout': 'OPEN; only fields read by this path are reconstructed',
        },
    }


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    report = build_report()
    path = OUT / 'crafting_pocket_manager_probe.json'
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n')
    print(path)


if __name__ == '__main__':
    main()
