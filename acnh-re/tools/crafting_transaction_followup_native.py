"""Run a cold-cache material check from reconstructed save-member records.

The original game cache acquisition path, A/B/C save loaders, cache producers,
recipe getter, and material sufficiency helper execute from the supplied ELF.
The save members and player context are reconstructed fixtures. Only the
unavailable SDK memset import is supplied by a byte-accurate memory callback.
"""
from pathlib import Path
import hashlib
import json
import sqlite3
import struct
import sys

TOOLS = Path(__file__).resolve().parent
REPO = TOOLS.parent
DATA = Path('/workspace/acnh-re')
OUT = REPO / 'output' / 'gameplay' / 'crafting_transaction_followup'
DB = DATA / 'output' / 'index.sqlite'
NSO = REPO / 'inputs' / 'additional_exefs' / 'main'
ROMFS = Path('/workspace/downloads/acnh_additional_romfs_2026-11-02/romfs')
SHARED_DEPS = DATA / '.deps'
if SHARED_DEPS.is_dir():
    sys.path.insert(0, str(SHARED_DEPS))
sys.path.insert(0, str(TOOLS))

from native_emulator import Sandbox, regs  # noqa: E402
import inventory_requirements_native as inventory_requirements  # noqa: E402
import inventory_cache_native as inventory_cache  # noqa: E402
from unicorn import UC_HOOK_CODE  # noqa: E402
from unicorn.arm64_const import (  # noqa: E402
    UC_ARM64_REG_X0,
    UC_ARM64_REG_X1,
    UC_ARM64_REG_X2,
    UC_ARM64_REG_X30,
    UC_ARM64_REG_PC,
)

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
        address = data_base + decoded['data_start'] + row_index * table['row_size']
        slot = row[unique_col] - minimum
        u.mem_write(array + slot * 8, struct.pack('<Q', address))

    # Native RecipeCraftParam column-offset cache used by 0xedac50.
    u.mem_write(s.image.ptr(0x32fe548), b'\x01')
    offsets = s.image.ptr(0x32fe550)
    for i, column in enumerate(table['columns']):
        u.mem_write(offsets + 4 * i, struct.pack('<I', column['offset']))
    return manager, unique_col


def get_six_materials(s, manager, table, row, unique_col):
    u = s.uc
    cols = {column['name']: i for i, column in enumerate(table['columns'])}
    item_out = s.HEAP + 0x50000
    quantity_out = item_out + 0x100
    materials = []
    for slot in range(6):
        u.mem_write(item_out, b'\xa5' * 40)
        u.mem_write(quantity_out, b'\x5a' * 24)
        status = s.call(0xedac50, (manager, item_out + 16, quantity_out + 8,
                                   row[unique_col], slot), limit=2000)
        item_id = row[cols[f'Material{slot + 1}']]
        quantity = row[cols[f'Amount{slot + 1}']] & 0xff
        writes = item_id != 0xfffe and quantity != 0
        assert status == int(writes), (slot, status, item_id, quantity)
        if writes:
            assert struct.unpack('<Q', u.mem_read(item_out + 16, 8))[0] == item_id
            assert u.mem_read(quantity_out + 8, 1)[0] == quantity
        else:
            assert bytes(u.mem_read(item_out, 40)) == b'\xa5' * 40
            assert bytes(u.mem_read(quantity_out, 24)) == b'\x5a' * 24
            item_id, quantity = 0xfffe, 0
        materials.append({'slot': slot, 'item_id': item_id, 'quantity': quantity})
    return materials


def install_memset_import(s):
    """Bind the missing SDK import to the standard byte-fill contract."""
    bindings_path = DATA / 'output' / 'native_modules' / 'import_resolution.json'
    bindings = json.loads(bindings_path.read_text())['main']['bindings']
    memset = next(x for x in bindings if x['symbol']['name'] == 'memset')
    assert len(memset['relocations']) == 1
    site = int(memset['relocations'][0]['site'], 16)
    sentinel = s.STOP + 0x100
    calls = []

    def execute(uc, address, size, user_data):
        destination = uc.reg_read(UC_ARM64_REG_X0)
        value = uc.reg_read(UC_ARM64_REG_X1) & 0xff
        count = uc.reg_read(UC_ARM64_REG_X2)
        uc.mem_write(destination, bytes([value]) * count)
        calls.append({'bytes': count, 'value': value})
        uc.reg_write(UC_ARM64_REG_X0, destination)
        uc.reg_write(UC_ARM64_REG_PC, uc.reg_read(UC_ARM64_REG_X30))

    s.uc.mem_write(site, struct.pack('<Q', sentinel))
    s.uc.hook_add(UC_HOOK_CODE, execute, begin=sentinel, end=sentinel)
    return {'name': 'memset', 'site': hex(site), 'sentinel': hex(sentinel), 'calls': calls}


def prepare_cold_cache(s, materials, missing_item=None):
    u = s.uc
    # The 0xee0be0 cold path selects this manager's player-0 record when the
    # native player-session bit is set and no live session object is selected.
    manager = 0x70000000
    u.mem_map(manager, 0x500000)
    inactive_players = s.HEAP + 0x120000
    session = s.HEAP + 0x130000
    for got, value in ((0x32d4f90, manager),
                       (0x32d4ff0, inactive_players),
                       (0x32d0df0, session)):
        global_cell = struct.unpack('<Q', u.mem_read(got, 8))[0]
        u.mem_write(global_cell, struct.pack('<Q', value))
    u.mem_write(manager, bytes(8))
    u.mem_write(manager + 0x3cdd20, struct.pack('<I', 1))
    u.mem_write(session + 0x50, bytes(8))

    player = manager + 0x1e6aa0
    context = player + 0x173e0
    # 0xf8f540 returns this context directly when +8 is populated.
    u.mem_write(context + 8, struct.pack('<Q', 1))

    words = [struct.pack('<HHI', item['item_id'], 0, 0)
             for item in materials if item['quantity'] and item['item_id'] != missing_item]
    source_base = s.HEAP + 0xa0000
    source_a, source_b, source_c = source_base, source_base + 0x1000, source_base + 0x2000
    empty = struct.pack('<Q', 0xfffe)
    grouped = (words[:2], words[2:4], words[4:5])
    sources = (source_a, source_b, source_c)
    source_counts = []
    for group, source, capacity in zip(grouped, sources, (20, 20, 5000)):
        count = len(group)
        source_counts.append(count)
        records = group + [empty] * (capacity - count)
        data = b''.join(records) + struct.pack('<I', count)
        if capacity == 20:
            data += bytes(20)
        u.mem_write(source, data)

    # The save accessors yield {offset,pointer} pairs; callbacks are null, so
    # the original loader receives the reconstructed member bytes directly.
    for offset, source in ((0xe0, source_a), (0xa8, source_b), (0x150, source_c)):
        descriptor = context + offset
        u.mem_write(descriptor + 8, bytes(8))
        u.mem_write(descriptor + 0x10, struct.pack('<Q', source))
        u.mem_write(descriptor + 0x28, bytes(8))

    cache = s.HEAP + 0x40000
    u.mem_write(cache, bytes(0x2a550))
    for name, spec in inventory_cache.COMPONENTS.items():
        obj = cache + spec['offset']
        vtable = s.image.ptr(spec['vtable_got']) + 16
        assert s.image.ptr(vtable + 0x40) == spec['producer']
        u.mem_write(obj, struct.pack('<Q', vtable))
        pointers = 0x51a00000 + 'ABC'.index(name) * 0x20000
        nodes = pointers + 0x4000
        list_base = obj + spec['list']
        u.mem_write(list_base, struct.pack('<IIQQ', 0, spec['limit'], pointers, nodes))
        for index in range(spec['limit']):
            nxt = nodes + 16 * (index + 1) if index + 1 < spec['limit'] else 0
            u.mem_write(nodes + 16 * index, struct.pack('<Q', nxt))
        u.mem_write(obj + spec['normal'], b'\xcc' * (spec['limit'] * 2))
    return cache, source_counts


def run_scenario(materials, include_c, missing_item=None):
    s = Sandbox()
    tables = inventory_requirements.install_item_tables(s)
    memset = install_memset_import(s)
    recipe, decoded, raw = load_resolved('RecipeCraftParam')
    manager, unique_col = prepare_recipe_table(s, recipe, decoded, raw)
    recipe_cols = {column['name']: i for i, column in enumerate(recipe['columns'])}
    row = next(r for r in recipe['rows']
               if r[recipe_cols['UniqueID']] == 56 and r[recipe_cols['Item']] == 975)
    assert materials == get_six_materials(s, manager, recipe, row, unique_col)

    cache, source_counts = prepare_cold_cache(s, materials, missing_item)
    requirement = s.HEAP + 0xd0000
    handle = s.HEAP + 0xe0000
    u = s.uc
    u.mem_write(requirement, bytes(0xb0))
    u.mem_write(requirement + 0x25, b'\x01')
    u.mem_write(handle, b'\x00' + bytes(7))
    for item in materials:
        offset = requirement + 0x2c + item['slot'] * 0x14
        u.mem_write(offset, struct.pack('<Q', item['item_id']))
        u.mem_write(offset + 8, struct.pack('<H', item['quantity']))

    observations = []
    counters_after_load = None
    for index, item in enumerate(materials):
        s.call(0xee0be0, (cache, requirement, handle, item['slot'], int(include_c)),
               limit=4_000_000)
        if index == 0:
            assert u.mem_read(cache + 8, 1) == b'\x01'
            counters_after_load = {
                name: {str(material['item_id']): struct.unpack(
                    '<H', u.mem_read(cache + spec['offset'] + spec['counters']
                                     + material['item_id'] * 2, 2))[0]
                       for material in materials if material['quantity']}
                for name, spec in inventory_cache.COMPONENTS.items()
            }
        entry = requirement + 0x2c + item['slot'] * 0x14
        available = struct.unpack('<HHH', u.mem_read(entry + 10, 6))
        flag = u.mem_read(requirement + 0x25, 1)[0]
        expected = ((1 if include_c and item['item_id'] == materials[4]['item_id']
                     and missing_item != materials[4]['item_id'] else 0),
                    (1 if item['item_id'] in {x['item_id'] for x in materials[:2]}
                     and item['quantity'] else 0),
                    (1 if item['item_id'] in {x['item_id'] for x in materials[2:4]}
                     and item['quantity'] else 0))
        if item['quantity']:
            if missing_item == item['item_id']:
                expected = (0, 0, 0)
            assert available == expected, (item, available, expected)
            assert flag == int(all(value >= 0 for value in available)
                               and (not item['quantity'] or sum(available) >= item['quantity']))
        observations.append({'slot': item['slot'], 'item_id': item['item_id'],
                             'required': item['quantity'], 'counter_C_A_B': list(available),
                             'sufficient_flag_after': flag})

    counters = {}
    for name, spec in inventory_cache.COMPONENTS.items():
        obj = cache + spec['offset']
        counters[name] = {str(item['item_id']): struct.unpack(
            '<H', u.mem_read(obj + spec['counters'] + item['item_id'] * 2, 2))[0]
            for item in materials if item['quantity']}
    assert u.mem_read(cache + 8, 1) == b'\x01'
    assert counters_after_load == counters, (counters_after_load, counters)
    assert len(memset['calls']) == 3
    return {
        'player_handle': 0,
        'cache_state_before': 'cold',
        'cache_state_after': 'ready',
        'save_source_record_counts_A_B_C': source_counts,
        'include_C': include_c,
        'missing_source_item_id': missing_item,
        'material_observations': observations,
        'counters_after_native_producers': counters,
        'counters_unchanged_by_requirement_checks': True,
        'final_sufficient_flag': observations[-1]['sufficient_flag_after'],
        'native_memset_calls': memset['calls'],
        'memset_binding': {'name': memset['name'], 'site': memset['site'],
                           'sentinel': memset['sentinel']}
    }


def main():
    assert DB.is_file() and NSO.is_file()
    inventory_requirements.ROOT = DATA
    recipe, decoded, raw = load_resolved('RecipeCraftParam')
    columns = {c['name']: i for i, c in enumerate(recipe['columns'])}
    row = next(r for r in recipe['rows']
               if r[columns['UniqueID']] == 56 and r[columns['Item']] == 975)
    materials = [{'slot': slot,
                  'item_id': row[columns[f'Material{slot + 1}']],
                  'quantity': row[columns[f'Amount{slot + 1}']] & 0xff}
                 for slot in range(6)]
    assert [x['item_id'] for x in materials[:5]] == [2213, 2285, 2287, 2214, 2286]
    assert [x['quantity'] for x in materials[:5]] == [1] * 5
    exact = run_scenario(materials, include_c=True)
    excluded_c = run_scenario(materials, include_c=False)
    one_short = run_scenario(materials, include_c=True, missing_item=materials[4]['item_id'])
    assert exact['final_sufficient_flag'] == 1
    assert excluded_c['final_sufficient_flag'] == 0
    assert excluded_c['material_observations'][4]['counter_C_A_B'][0] == 0
    assert one_short['final_sufficient_flag'] == 0
    assert one_short['material_observations'][4]['counter_C_A_B'] == [0, 0, 0]

    db = sqlite3.connect(f'file:{DB}?mode=ro', uri=True)
    calls = db.execute('select pc from direct_calls where owner_va=? and target_va=? order by pc',
                       (0xedc240, 0xee0be0)).fetchall()
    db.close()
    assert len(calls) == 6
    romfs_recipe = ROMFS / 'Bcsv' / 'RecipeCraftParam.bcsv'
    assert hashlib.sha256(raw).hexdigest() == sha256(romfs_recipe)
    main_nso_hash = sha256(NSO)
    elf_hash = hashlib.sha256(Sandbox().image.data).hexdigest()
    result = {
        'scope': 'Cold-cache acquisition from reconstructed A/B/C save-member records, followed by the native recipe material getter and native material sufficiency helper for RecipeCraftParam ID 56. This is a focused gameplay slice, not a complete crafting transaction.',
        'labels': {
            'RecipeCraftParam ID 56 and ingredient IDs': '[TBL]',
            'recipe ingredient extraction by 0xedac50': '[NATIVE]',
            'save member paths and source layouts': '[PSEUDO: reconstructed fixture]',
            'cold acquisition, native A/B/C loaders/producers and 0xee0be0': '[NATIVE]',
            '0xedc240 six-slot call mapping': '[PSEUDO]'
        },
        'provenance': {
            'main_nso_path': str(NSO),
            'main_nso_sha256': main_nso_hash,
            'analysis_elf_sha256': elf_hash,
            'index_path': str(DB),
            'recipe_romfs_path': str(romfs_recipe),
            'recipe_romfs_sha256': sha256(romfs_recipe),
            'recipe_table_raw_sha256': hashlib.sha256(raw).hexdigest(),
            'itemparam_raw_sha256': json.loads((DATA / 'output' / 'tables_resolved' / 'ItemParam.json').read_text())['raw']['sha256'],
            'itemkind_raw_sha256': json.loads((DATA / 'output' / 'tables_resolved' / 'ItemKind.json').read_text())['raw']['sha256'],
            'native_functions': ['0xedac50', '0xee0be0', '0xeda040', '0xeda160', '0xeda280',
                                 '0xee72b0', '0xee7550', '0xee7800'],
            'native_function_call_counts': {
                '0xedac50': 18,
                '0xee0be0': 18,
                '0xeda040': 3,
                '0xeda160': 3,
                '0xeda280': 3,
                '0xee72b0': 3,
                '0xee7550': 3,
                '0xee7800': 3
            },
            '0xedc240_to_0xee0be0_direct_call_sites': [hex(x[0]) for x in calls],
            'dependencies_stubbed': ['SDK memset import only; byte-fill behavior is emulated by a memory callback because the SDK NSO was not supplied in this worktree.']
        },
        'recipe': {
            'recipe_unique_id': 56,
            'output_item_id': 975,
            'output_label': 'FtrFruitbasket',
            'materials': materials
        },
        'scenarios': {
            'cold_cache_all_five_materials_in_A_B_C_with_C_enabled': exact,
            'same_sources_but_C_excluded_by_native_option': excluded_c,
            'cold_cache_one_required_Peach_missing_from_source_C': one_short
        },
        'verified': [
            'The native recipe getter returns the five one-unit ingredients from table row 56; the sixth slot is empty.',
            'With cache-ready byte initially zero and player handle 0, 0xee0be0 loads A/B/C save-member fixtures through 0xeda040/0xeda160/0xeda280 and invokes their original producer callbacks.',
            'The native helper sets the cache-ready byte after the three loaders, then checks materials using the produced counters.',
            'All five materials pass with C included. Excluding C makes the Peach slot insufficient; omitting Peach from the save fixture also makes that slot insufficient.',
            'The requirement helper does not subtract ingredients, grant item 975, write learned-recipe state, or roll back.'
        ],
        'limits': [
            'No real player save was supplied. Player context and A/B/C member pointers are reconstructed; record contents are fixture data using the source word layout expected by the original loaders.',
            'Save-member names A/B/C remain unresolved. The run proves the native acquisition path from three member accessors, not which named gameplay inventory each group represents.',
            'The SDK memset import uses a byte-accurate callback; all game functions listed above execute their original ELF bytes.',
            'No ingredient consumption, output award, cancel/rollback, learned-recipe query/set path, workbench page interaction, or remake/customization operation is executed.'
        ],
        'mismatches': []
    }
    OUT.mkdir(parents=True, exist_ok=True)
    target = OUT / 'crafting_transaction_followup_native.json'
    target.write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps({'result': str(target), 'native_cache_scenarios': 3,
                      'exact': exact['final_sufficient_flag'],
                      'excluded_C': excluded_c['final_sufficient_flag'],
                      'one_short': one_short['final_sufficient_flag'],
                      'mismatches': 0}))


if __name__ == '__main__':
    main()
