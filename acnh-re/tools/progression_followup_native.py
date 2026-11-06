"""Run one recipe's material list and availability helper over native code.

The test deliberately stops before material removal/result delivery.  The raw
game tables and source binary are read from the shared evidence tree; only the
new JSON under output/gameplay/progression_followup is written here.
"""
from pathlib import Path
import hashlib
import json
import re
import sqlite3
import struct
import sys

TOOLS = Path(__file__).resolve().parent
REPO = TOOLS.parent
DATA = Path('/workspace/acnh-re')
OUT = REPO / 'output' / 'gameplay' / 'progression_followup'
NSO = DATA / 'inputs' / 'additional_exefs' / 'main'
ROMFS = Path('/workspace/downloads/acnh_additional_romfs_2026-11-02/romfs')
DB = DATA / 'output' / 'index.sqlite'
MAIN_NSO_SHA256 = 'f8d248109ff72999b4600ae3749f8c7397fb960f7ad3ab8dee3018ae9e14e900'

# The worktree contains the code but not the dependency cache.  Use the shared
# read-only cache when it is present; users with a normal local install can use
# their regular Python environment instead.
SHARED_DEPS = DATA / '.deps'
if SHARED_DEPS.is_dir():
    sys.path.insert(0, str(SHARED_DEPS))
sys.path.insert(0, str(TOOLS))

from native_emulator import Sandbox  # noqa: E402
import inventory_requirements_native as inventory_requirements  # noqa: E402

inventory_requirements.ROOT = DATA


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_resolved(name):
    out = DATA / 'output'
    table = json.loads((out / 'tables_resolved' / f'{name}.json').read_text())
    manifest = json.loads((out / 'manifest.json').read_text())
    entries = manifest['entries']
    entry = entries[table['source_id']] if isinstance(entries, list) else entries[str(table['source_id'])]
    decoded = json.loads((out / entry['decoded']).read_text())['data']
    raw = (out / table['raw']['$blob']).read_bytes()
    return table, decoded, raw


def prepare_recipe_table(s, table, decoded, raw):
    u = s.uc
    manager = s.HEAP + 0x80000
    data_base = s.HEAP + 0x10000
    array = s.HEAP + 0x30000
    unique_col = next(i for i, col in enumerate(table['columns']) if col['name'] == 'UniqueID')
    minimum = min(row[unique_col] for row in table['rows'])
    maximum = max(row[unique_col] for row in table['rows'])
    span = maximum - minimum + 1
    u.mem_write(data_base, raw)
    u.mem_write(array, bytes(span * 8))
    u.mem_write(manager + 0x8f320, struct.pack('<H', minimum))
    u.mem_write(manager + 0x8f300, struct.pack('<I', span))
    u.mem_write(manager + 0x8f308, struct.pack('<Q', array))
    for row_index, row in enumerate(table['rows']):
        row_address = data_base + decoded['data_start'] + row_index * table['row_size']
        slot = row[unique_col] - minimum
        u.mem_write(array + slot * 8, struct.pack('<Q', row_address))

    # Original RecipeCraftParam column-offset cache read by the native getter.
    u.mem_write(s.image.ptr(0x32fe548), b'\x01')
    offsets = s.image.ptr(0x32fe550)
    for i, column in enumerate(table['columns']):
        u.mem_write(offsets + 4 * i, struct.pack('<I', column['offset']))
    return manager, data_base, unique_col


def get_six_materials(s, manager, table, row, unique_col):
    u = s.uc
    cols = {column['name']: i for i, column in enumerate(table['columns'])}
    item_out = s.HEAP + 0x50000
    quantity_out = item_out + 0x100
    extracted = []
    for slot in range(6):
        u.mem_write(item_out, b'\xa5' * 40)
        u.mem_write(quantity_out, b'\x5a' * 24)
        status = s.call(0xedac50, (manager, item_out + 16, quantity_out + 8,
                                   row[unique_col], slot), limit=2000)
        material = row[cols[f'Material{slot + 1}']]
        amount = row[cols[f'Amount{slot + 1}']] & 0xff
        writes = material != 0xfffe and amount != 0
        assert status == int(writes), (slot, status, material, amount)
        if writes:
            actual_item = struct.unpack('<Q', u.mem_read(item_out + 16, 8))[0]
            actual_amount = u.mem_read(quantity_out + 8, 1)[0]
            assert actual_item == material, (slot, actual_item, material)
            assert actual_amount == amount, (slot, actual_amount, amount)
            extracted.append({'slot': slot, 'item_id': actual_item, 'quantity': actual_amount})
        else:
            assert bytes(u.mem_read(item_out, 40)) == b'\xa5' * 40
            assert bytes(u.mem_read(quantity_out, 24)) == b'\x5a' * 24
            extracted.append({'slot': slot, 'item_id': 0xfffe, 'quantity': 0})
    return extracted


def check_materials(s, materials, available):
    u = s.uc
    cache = s.HEAP + 0x40000
    requirement = s.HEAP + 0xd0000
    handle = s.HEAP + 0xe0000
    u.mem_write(handle, b'\xff' + bytes(7))
    # Warm-cache counters are controlled inputs for this isolated rule test.
    u.mem_write(cache, bytes(0x2a550))
    u.mem_write(cache + 8, b'\x01')
    for item_id, amount in available.items():
        u.mem_write(cache + 0x308 + item_id * 2, struct.pack('<H', amount))
    cache_before = bytes(u.mem_read(cache, 0x2a550))

    u.mem_write(requirement, bytes(0xb0))
    u.mem_write(requirement + 0x25, b'\x01')
    for material in materials:
        offset = requirement + 0x2c + 20 * material['slot']
        u.mem_write(offset, struct.pack('<Q', material['item_id']))
        u.mem_write(offset + 8, struct.pack('<H', material['quantity']))

    slots = []
    flag = 1
    for material in materials:
        slot = material['slot']
        s.call(0xee0be0, (cache, requirement, handle, slot, 0), limit=30000)
        flag = u.mem_read(requirement + 0x25, 1)[0]
        entry = requirement + 0x2c + 20 * slot
        observed = struct.unpack('<HHH', u.mem_read(entry + 10, 6))
        needed = material['quantity']
        if needed:
            expected_count = (0, available.get(material['item_id'], 0), 0)
            assert observed == expected_count, (slot, observed, expected_count)
            should_fail = available.get(material['item_id'], 0) < needed
            assert flag == int(not should_fail and all(x['flag_after'] for x in slots)), (slot, flag)
        else:
            assert flag == (slots[-1]['flag_after'] if slots else 1), (slot, flag)
        slots.append({'slot': slot, 'item_id': material['item_id'], 'required': needed,
                      'available_in_A': available.get(material['item_id'], 0),
                      'counter_parts_C_A_B': list(observed), 'flag_after': flag})

    assert bytes(u.mem_read(cache, 0x2a550)) == cache_before, 'availability check changed counters'
    return {'slots': slots, 'final_sufficient_flag': flag, 'counters_unchanged': True}


def main():
    assert DB.is_file() and NSO.is_file()
    assert sha256(NSO) == MAIN_NSO_SHA256
    s = Sandbox()
    tables = inventory_requirements.install_item_tables(s)
    recipe, decoded, recipe_raw = load_resolved('RecipeCraftParam')
    manager, _data_base, unique_col = prepare_recipe_table(s, recipe, decoded, recipe_raw)

    item = tables['item_table']
    item_cols = tables['item_cols']
    kind = tables['kind_table']
    kind_cols = tables['kind_cols']
    item_by_id = {row[item_cols['UniqueID']]: row for row in item['rows']}
    kind_by_label = {row[kind_cols['Label']]: row for row in kind['rows']}
    recipe_cols = {column['name']: i for i, column in enumerate(recipe['columns'])}
    recipe_row = next(row for row in recipe['rows']
                      if row[recipe_cols['UniqueID']] == 56 and row[recipe_cols['Item']] == 975)
    output_item = item_by_id[recipe_row[recipe_cols['Item']]]
    assert output_item[item_cols['Label']] == 'FtrFruitbasket'
    materials = get_six_materials(s, manager, recipe, recipe_row, unique_col)

    named_materials = []
    for material in materials:
        if material['quantity'] == 0:
            named_materials.append({**material, 'label': None, 'name': None})
            continue
        source_item = item_by_id[material['item_id']]
        named_materials.append({**material,
                                'label': source_item[item_cols['Label']],
                                'name': source_item[item_cols['ItemName']]})
    active = [m for m in named_materials if m['quantity']]
    assert len(active) == 5 and len({m['item_id'] for m in active}) == 5
    exact_counts = {m['item_id']: m['quantity'] for m in active}
    missing_counts = dict(exact_counts)
    missing_slot = active[1]
    missing_counts[missing_slot['item_id']] = missing_slot['quantity'] - 1

    exact = check_materials(s, named_materials, exact_counts)
    one_short = check_materials(s, named_materials, missing_counts)
    assert exact['final_sufficient_flag'] == 1
    assert one_short['final_sufficient_flag'] == 0
    assert one_short['slots'][missing_slot['slot']]['flag_after'] == 0

    db = sqlite3.connect(f'file:{DB}?mode=ro', uri=True)
    direct_calls = db.execute(
        'select pc from direct_calls where owner_va=? and target_va=? order by pc',
        (0xedc240, 0xee0be0)).fetchall()
    assert len(direct_calls) == 6
    workbench_events = db.execute(
        "select event_index,name,params_json from event_calls "
        "where flow='Ftr_Working' and (name like '%WorkingHandling%' "
        "or name like '%Workbench%' or name like '%CraftRecipe%') order by event_index").fetchall()
    db.close()
    caller_pseudocode = DATA / 'output' / 'binary' / 'analysis_decomp' / 'edc240.c'
    caller_text = caller_pseudocode.read_text()
    slot_args = [int(value) for value in re.findall(
        r'FUN_00fe0be0\(param_2,&uStack_130,param_4,(\d),param_5 & 1\);', caller_text)]
    assert slot_args == list(range(6)), slot_args

    romfs_recipe = ROMFS / 'Bcsv' / 'RecipeCraftParam.bcsv'
    romfs_working = ROMFS / 'EventFlow' / 'Ftr_Working.bfevfl'
    assert sha256(romfs_recipe) == hashlib.sha256(recipe_raw).hexdigest()
    result = {
        'scope': 'Single real RecipeCraftParam row: native material extraction followed by native warm-cache sufficiency checks. Inventory counters are controlled synthetic inputs; no item removal/result grant is tested.',
        'native_execution': {
            'harness': 'tools/native_emulator.py; original A_logic/main.elf image and function bytes, no function or dependency stubs',
            'elf_sha256': hashlib.sha256(s.image.data).hexdigest(),
            'main_nso_sha256': sha256(NSO),
            'function_calls': {'0xedac50': 6, '0xee0be0': 12},
            'mismatches': 0
        },
        'labels': {
            'RecipeCraftParam': '[TBL]',
            'Ftr_Working event calls': '[EF]',
            '0xedac50 and 0xee0be0 execution': '[NATIVE]',
            '0xedc240 argument mapping': '[PSEUDO]',
            'availability counters and player state': '[PSEUDO: controlled synthetic state]'
        },
        'provenance': {
            'main_nso_path': str(NSO), 'main_nso_sha256': sha256(NSO),
            'analysis_elf_sha256': hashlib.sha256(s.image.data).hexdigest(),
            'database_path': str(DB), 'database_sha256': sha256(DB),
            'romfs_recipe_path': str(romfs_recipe), 'romfs_recipe_sha256': sha256(romfs_recipe),
            'romfs_working_eventflow_path': str(romfs_working),
            'romfs_working_eventflow_sha256': sha256(romfs_working),
            'recipe_table_source_id': recipe['source_id'],
            'recipe_table_raw_sha256': hashlib.sha256(recipe_raw).hexdigest(),
            'itemparam_raw_sha256': tables['item_raw_sha256'],
            'itemkind_raw_sha256': tables['kind_raw_sha256'],
            'native_functions': ['0xedac50', '0xee0be0'],
            'requirement_check_native_call_sites_in_0xedc240': [hex(row[0]) for row in direct_calls],
            'requirement_check_slot_arguments_in_0xedc240_pseudocode': slot_args,
            'ftr_working_eventflow_calls': [
                {'event_index': index, 'name': name, 'params': json.loads(params) if params else None}
                for index, name, params in workbench_events
            ],
            'dependencies_stubbed': []
        },
        'recipe': {
            'recipe_unique_id': recipe_row[unique_col],
            'output_item_id': output_item[item_cols['UniqueID']],
            'output_label': output_item[item_cols['Label']],
            'output_name': output_item[item_cols['ItemName']],
            'materials': named_materials
        },
        'scenarios': {
            'exact_material_counts': exact,
            'one_required_material_missing': {
                'missing_material_slot': missing_slot['slot'],
                'missing_item_id': missing_slot['item_id'],
                'missing_label': missing_slot['label'],
                'missing_name': missing_slot['name'],
                'result': one_short
            }
        },
        'verified_rules': [
            'Native 0xedac50 writes the six actual recipe material slots and low quantity bytes from RecipeCraftParam.',
            'Native 0xee0be0 leaves the sufficient byte set for all five ingredients at exact inventory counts.',
            'One missing unit in the Pear slot clears the sufficient byte; subsequent checks preserve the failed state.',
            'The requirement helper writes observed cache counts into the recipe slot and does not mutate the cache counters.',
            'RecipeCraftParam BCSV in the provided additional RomFS is byte-identical to the table raw blob.'
        ],
        'gaps': [
            'The counter cache in this focused run is seeded directly; the player-save acquisition and A/B/C cache loaders are not repeated here.',
            'No material consumption, output item award, cancellation/rollback, learned-recipe gate, or full WorkCraftBgPage interaction is executed.',
            'Recipe selection/unlock source rules and Remake remain open; this is a material availability slice, not full crafting completion.'
        ]
    }
    OUT.mkdir(parents=True, exist_ok=True)
    target = OUT / 'crafting_material_availability_native.json'
    target.write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps({'result': str(target), 'recipe': recipe_row[unique_col],
                      'materials': len(active), 'exact_flag': exact['final_sufficient_flag'],
                      'one_short_flag': one_short['final_sufficient_flag'],
                      'native_call_sites': len(direct_calls), 'mismatches': 0}))


if __name__ == '__main__':
    main()
