"""Execute active RoomFloor ground selection using original item/floor tables.

The no-resident-map branch is tested end to end. Raw JMP resources are not
supplied; no resource or map resolver is replaced with a callback.
"""
from pathlib import Path
from collections import Counter
import hashlib
import itertools
import json
import struct
from native_emulator import Sandbox, regs
from inventory_requirements_native import install_item_tables
from unicorn import UC_HOOK_CODE

ROOT = Path(__file__).resolve().parent.parent


def install_floor_context(s):
    u = s.uc
    tables = install_item_tables(s)
    def d(p, v): u.mem_write(p, struct.pack('<I', v & 0xffffffff))
    def q(p, v): u.mem_write(p, struct.pack('<Q', v))
    manifest = json.loads((ROOT/'output/manifest.json').read_text())['entries']
    loaded = {}
    for name, base, manager, array in [
            ('RoomFloorParam', 0x51800000, 0x51900000, 0x51910000),
            ('ColGroundAttributeParam', 0x51810000, 0x51901000, 0x51914000)]:
        t = json.loads((ROOT/f'output/tables_resolved/{name}.json').read_text())
        h = json.loads((ROOT/'output'/manifest[t['source_id']]['decoded']).read_text())['data']
        raw = (ROOT/'output'/t['raw']['$blob']).read_bytes(); u.mem_write(base, raw)
        cols = {c['name']: i for i, c in enumerate(t['columns'])}
        uid = cols['UniqueID']; minimum = min(r[uid] for r in t['rows'])
        maximum = max(r[uid] for r in t['rows'])
        d(manager+0x1e0, maximum-minimum+1); q(manager+0x1e8, array)
        u.mem_write(manager+0x200, struct.pack('<H', minimum))
        ordered = array+0x1000
        for i, row in enumerate(t['rows']):
            ptr = base+h['data_start']+i*t['row_size']
            q(array+8*(row[uid]-minimum), ptr); q(ordered+8*i, ptr)
        d(manager+0x1b8, len(t['rows'])); d(manager+0x1c8, len(t['rows']))
        q(manager+0x1c0, ordered)
        # The generic reader obtains the full BCSV through reader+0xb0 -> handle+8.
        handle = manager+0x400; q(manager+0xb8, handle); q(handle+8, base)
        loaded[name] = {'table': t, 'cols': cols, 'manager': manager,
                        'raw_base': base, 'raw_bytes': raw, 'header': h}
    q(s.image.ptr(0x32d3d90), loaded['RoomFloorParam']['manager'])
    q(s.image.ptr(0x32d3d88), loaded['ColGroundAttributeParam']['manager'])
    u.mem_write(s.image.ptr(0x32d70f8), bytes(1))
    u.mem_write(s.image.ptr(0x32d7210), bytes(1))
    task_manager, task, stage, registry, world, grid, base, point, coord, resources = [
        s.HEAP+n for n in (0x10000, 0x20000, 0x30000, 0x40000,
                          0x50000, 0x60000, 0x61000, 0x70000, 0x71000, 0x80000)]
    q(registry, s.image.ptr(0x32d0838)+16)
    q(s.image.ptr(0x32d08d8), registry); q(s.image.ptr(0x32d0c88), task_manager)
    q(task_manager+0x330, task); d(task_manager+0x338, 1); d(task+0x244, 1)
    q(s.image.ptr(0x32d71a0), stage); q(s.image.ptr(0x32d0de8), world)
    q(world+0xa0, grid)
    q(s.image.ptr(0x32d07b8), resources); d(resources+0xf50, 0)
    # Equality with the native default-ID global takes the auxiliary-item
    # branch in0xb6270/0x87a930. The game-wide ID initializer is not executed.
    default_id = bytes(u.mem_read(s.image.ptr(0x32d2598), 2))
    u.mem_write(stage+0xa54, default_id)
    u.mem_write(point, struct.pack('<3f', 2.5, 0., 2.5))
    d(grid+0x30, 1); d(grid+0x34, 1); d(grid+0x40, 1); q(grid+0x48, base)
    u.mem_write(coord, struct.pack('<4i', 0, 0, 0, 0))
    return {'items': tables, 'tables': loaded, 'stage': stage, 'world': world, 'task': task,
            'resources': resources, 'point': point, 'coord': coord, 'base': base,
            'd': d, 'q': q}


def main():
    s = Sandbox(); u = s.uc; setup = install_floor_context(s)
    floors = setup['tables']['RoomFloorParam']; ground = setup['tables']['ColGroundAttributeParam']
    table = floors['table']; fc = floors['cols']; gc = ground['cols']
    ground_ids = {row[gc['UniqueID']]: i for i, row in enumerate(ground['table']['rows'])}
    item_table = setup['items']['item_table']; ic = setup['items']['item_cols']
    item_by_id = {row[ic['UniqueID']]: row for row in item_table['rows']}
    stage = setup['stage']; d = setup['d']; point = setup['point']
    observed = set(); variants = []; watched = {0x16e6d0, 0x855fa0, 0x18adf0}
    def trace(uc, address, size, data):
        if address in watched:
            observed.add(address)
            if address == 0x16e6d0: variants.append(uc.reg_read(regs.UC_ARM64_REG_W2))
    hook = u.hook_add(UC_HOOK_CODE, trace)
    groups = {'source_floor_contexts': 0, 'stage_state_classification': 0,
              'active_ground_permission_callers': 0, 'non_jmp_keeps_terrain': 0}
    samples = []; used_variants = Counter()
    def run(row, state, rotated):
        item = row[fc['ItemTableId']]
        assert item_by_id[item][ic['FloorTableId']] == row[fc['UniqueID']]
        u.mem_write(stage+0xa58, struct.pack('<Q', item))
        u.mem_write(stage+0xa4c, struct.pack('<Q', item))
        u.mem_write(stage+0xab8, bytes([64 if rotated else 0]))
        d(stage+0xa40, state)
        observed.clear(); variants.clear()
        try: actual = s.call(0x18b570, (point,), limit=50000)
        except Exception as error:
            raise RuntimeError(f'item={item}, state={state}, PC={u.reg_read(regs.UC_ARM64_REG_PC):#x}: {error}') from error
        category = 1 if state == 1 else 2 if 2 <= state <= 5 else 3 if 6 <= state <= 16 else 4 if 17 <= state <= 18 else 5 if state == 19 else 3
        enters = row[fc['HasJmp']] != 0 and category in (2, 3, 4)
        expected = ground_ids.get(row[fc['Floorboards']], 0) if enters else 7
        assert actual == expected, (item, state, rotated, actual, expected)
        assert (0x16e6d0 in observed) == enters
        assert (0x855fa0 in observed) == enters
        assert 0x18adf0 not in observed
        if enters:
            variant = category-2 if category < 4 else 2+int(bool(row[fc['Horizon']]) != rotated)
            assert variants == [variant], (item, state, rotated, variants, variant)
            used_variants[variant] += 1
        return actual
    for row, state, rotated in itertools.product(table['rows'], [2, 6, 17], [False, True]):
        result = run(row, state, rotated); groups['source_floor_contexts'] += 1
        if row[fc['HasJmp']] and state == 2 and not rotated:
            samples.append({'item_id': row[fc['ItemTableId']], 'floor_id': row[fc['UniqueID']],
                            'resource_name': row[fc['ResourceName']],
                            'floorboards_id': row[fc['Floorboards']], 'ground_row_index': result})
    row = next(row for row in table['rows'] if row[fc['HasJmp']])
    for state, rotated in itertools.product([-1]+list(range(21))+[-2147483648, 2147483647], [False, True]):
        run(row, state, rotated); groups['stage_state_classification'] += 1
    ground_rows = ground['table']['rows']
    for row in [r for r in table['rows'] if r[fc['HasJmp']]]:
        result = run(row, 2, False)
        for va, field, rule in [(0x187420, 'WaterCheck', 'all'), (0x1874f0, 'PlayerNoEntry', 'any'), (0x187610, 'WaterCheck', 'exactly_two')]:
            false_row = next(i for i, r in enumerate(ground_rows) if not r[gc[field]])
            true_row = next(i for i, r in enumerate(ground_rows) if r[gc[field]])
            ids = [true_row, true_row, false_row, false_row] if rule == 'exactly_two' else [true_row]*4
            u.mem_write(setup['base'], bytes(48)+bytes(ids))
            flag = bool(ground_rows[result][gc[field]])
            expected = flag if rule != 'exactly_two' else False
            assert s.call(va, (setup['coord'],), limit=100000) == int(expected), (hex(va), row[fc['UniqueID']], result)
            # An inactive Stage must keep the base result. All three controls
            # are true by construction, so the active dry-floor override is
            # observable instead of agreeing accidentally with a dry base.
            d(setup['task']+0x244, 0)
            assert s.call(va, (setup['coord'],), limit=100000) == 1
            d(setup['task']+0x244, 1)
            groups['active_ground_permission_callers'] += 1
    row = next(r for r in table['rows'] if not r[fc['HasJmp']])
    assert run(row, 2, False) == 7
    for va, field, rule in [(0x187420, 'WaterCheck', 'all'), (0x1874f0, 'PlayerNoEntry', 'any'), (0x187610, 'WaterCheck', 'exactly_two')]:
        false_row = next(i for i, r in enumerate(ground_rows) if not r[gc[field]])
        true_row = next(i for i, r in enumerate(ground_rows) if r[gc[field]])
        ids = [true_row, true_row, false_row, false_row] if rule == 'exactly_two' else [true_row]*4
        u.mem_write(setup['base'], bytes(48)+bytes(ids))
        assert s.call(va, (setup['coord'],), limit=100000) == 1
        groups['non_jmp_keeps_terrain'] += 1
    u.hook_del(hook)
    for t in setup['tables'].values(): assert bytes(u.mem_read(t['raw_base'], len(t['raw_bytes']))) == t['raw_bytes']
    cache = s.image.ptr(0x32d7100)
    discovered = {name: struct.unpack('<i', u.mem_read(cache+offset, 4))[0]
                  for name, offset in [('HasJmp', 0x34), ('Floorboards', 0x18), ('Horizon', 0x28)]}
    for name, offset in discovered.items(): assert offset == table['columns'][fc[name]]['offset']
    result = {
        'groups': groups, 'cases': sum(groups.values()), 'mismatches': [],
        'native_functions': ['0x18b570', '0x157ab0', '0x856270', '0x16e6d0 (no resident maps)',
                             '0x855fa0', '0x18ee80', '0x881760', '0x881e50',
                             '0x187420', '0x1874f0', '0x187610'],
        'source_floor_rows': len(table['rows']), 'source_has_jmp_rows': sum(bool(r[fc['HasJmp']]) for r in table['rows']),
        'source_item_floor_joins': len(table['rows']), 'native_variant_counts': dict(used_variants),
        'active_inactive_context_paired_controls': 42,
        'metadata_offsets_discovered_by_native': discovered, 'samples': samples,
        'rules': ['This selector reads ItemKind.RoomFloor, ItemParam.FloorTableId and RoomFloorParam.HasJmp.',
                  'HasJmp false returns sentinel7 before map lookup, even for a real floor item.',
                  'When no resident map is found, Floorboards ID is resolved through ColGroundAttributeParam to its row index (or configured remap).',
                  'Stage state2..5 selects variant0;6..16 selects1;17..18 selects2/3 via source Horizon XOR context orientation bit6.',
                  'State1 and19 reject the selector; other tested signed states select category3/variant1.',
                  'The active override reaches original WaterCheck and PlayerNoEntry aggregate callers.'],
        'dependencies_stubbed': [],
        'reconstructed_state': ['Real item/kind definitions and enum cache', 'Dense floor/ground managers and original complete BCSV blobs',
                                'Original task registry vtable and active Stage/world context', 'Resource manager with resident-map count0'],
        'limits': ['No actual resident JMP map or resource loader path executed.',
                   'Ground remap vector is absent; the native row-index path is exercised.',
                   'This is the RoomFloor override path, not proof of island terrain editing or all dynamic-ground sources.',
                   'Inventory/save acquisition and complete scene lifecycle remain unexecuted.'],
        'source_tables': {name: {'json': f'tables_resolved/{name}.json', 'source_id': t['source_id'], 'raw': t['raw']}
                          for name, t in [(n, data['table']) for n, data in setup['tables'].items()]
                          + [('ItemParam', setup['items']['item_table']), ('ItemKind', setup['items']['kind_table'])]},
        'elf_sha256': hashlib.sha256(s.image.data).hexdigest()
    }
    (ROOT/'output/mechanics/room_floor_ground_native.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({'groups': groups, 'cases': result['cases'], 'mismatches': 0}), flush=True)


if __name__ == '__main__': main()
