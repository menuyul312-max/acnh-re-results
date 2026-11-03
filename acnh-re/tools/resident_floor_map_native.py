"""Execute resident RoomFloor .pbc selection, transform and ground consumers.

SARC/PBC test data and loaded-resource state are reconstructed. Original
constructor/parser, class checks, filename lookup, map resolver and consumer
instructions execute without replacement callbacks or patched instructions.
"""
from pathlib import Path
from collections import Counter
import hashlib
import itertools
import json
import struct
from native_emulator import Sandbox, regs
from native_sdk_memory import install_sdk_memory
from native_archive import initialize_resource_types, make_sarc, install_ready_archive, open_native_archive
from room_floor_ground_native import install_floor_context
from dynamic_ground_native import f, index
from unicorn import UC_HOOK_CODE

ROOT = Path(__file__).resolve().parent.parent


def map_bytes(variant):
    data = bytearray(20+3*2*52)
    struct.pack_into('<IIIii', data, 0, 0, 3, 2, -1, -1)
    for cell in range(6):
        data[20+cell*52+48:20+cell*52+52] = bytes((17*variant+4*cell+lane) % 63 for lane in range(4))
    return bytes(data)


def map_value(raw, x, z):
    _, width, height, ox, oz = struct.unpack_from('<IIIii', raw)
    x, z = f(x-f(f(ox)*5.)), f(z-f(f(oz)*5.))
    ix, iz = index(x), index(z)
    if not (0 <= ix < width and 0 <= iz < height): return 7
    u, v = f(x-f(f(ix)*5.)), f(z-f(f(iz)*5.))
    lane = (2 if f(f(u+v)-5.) >= 0 else 1) if f(v-u) >= 0 else (3 if f(f(u+v)-5.) >= 0 else 0)
    return raw[20+52*(ix+width*iz)+48+lane]


def main():
    s = Sandbox(); u = s.uc; setup = install_floor_context(s)
    sdk = install_sdk_memory(s); type_cells = initialize_resource_types(s)
    def q(p, v): u.mem_write(p, struct.pack('<Q', v))
    def d(p, v): u.mem_write(p, struct.pack('<I', v & 0xffffffff))
    floors = setup['tables']['RoomFloorParam']; fc = floors['cols']
    ground = setup['tables']['ColGroundAttributeParam']; gc = ground['cols']
    source_floors = [row for row in floors['table']['rows'] if row[fc['HasJmp']]]
    ground_ids = {row[gc['UniqueID']]: i for i, row in enumerate(ground['table']['rows'])}
    variants = s.image.cstring(0x293eabb).split(',')
    extension = s.image.cstring(0x2929873)
    assert variants == ['6x6', '8x8', '10x6', '10x6_R'] and extension == '.pbc'
    variant_array = 0x51b03000
    for i, label in enumerate(variants):
        pointer = 0x51b03100+32*i
        u.mem_write(pointer, label.encode()+b'\0'); q(variant_array+8*i, pointer)
    q(s.image.ptr(0x32d7110), variant_array)
    records, ids, loaded = 0x51b00000, 0x51b02000, {}
    for i, row in enumerate(source_floors):
        floor_id = row[fc['UniqueID']]
        names = [row[fc['ResourceName']]+'_'+label+extension for label in variants]
        files = {name: map_bytes(v) for v, name in enumerate(names)}
        raw, offsets = make_sarc(files, '<' if i % 2 == 0 else '>')
        state = install_ready_archive(s, records+72*i, 0x51b10000+i*0x10000, raw)
        state.update({'files': files, 'offsets': offsets, 'names': names, 'floor': row, 'endian': '<' if i % 2 == 0 else '>'})
        loaded[floor_id] = state
        u.mem_write(ids+2*i, struct.pack('<H', floor_id))
    resource_manager = setup['resources']
    d(resource_manager+0xf50, len(source_floors)); q(resource_manager+0xf58, ids)
    d(resource_manager+0xf60, len(source_floors)); q(resource_manager+0xf68, records)
    stage, point = setup['stage'], setup['point']
    observed = {}; hooks = []
    def trace(uc, pc, size, data):
        if pc == 0x16e6d0:
            observed.setdefault('variants', []).append(uc.reg_read(regs.UC_ARM64_REG_W2))
        elif pc == 0x1c84e50:
            string = uc.reg_read(regs.UC_ARM64_REG_X1)
            ptr = struct.unpack('<Q', uc.mem_read(string+8, 8))[0]
            name = bytes(uc.mem_read(ptr, 256)).split(b'\0', 1)[0].decode()
            observed.setdefault('names', []).append(name)
        elif pc == 0x18adf0:
            ptr = uc.reg_read(regs.UC_ARM64_REG_X1)
            observed.setdefault('maps', []).append({'ptr': uc.reg_read(regs.UC_ARM64_REG_X0),
                                                   'position': tuple(struct.unpack('<3f', uc.mem_read(ptr, 12)))})
        else: observed['fallback'] = True
    for address in [0x16e6d0, 0x1c84e50, 0x18adf0, 0x855fa0]:
        hooks.append(u.hook_add(UC_HOOK_CODE, trace, begin=address, end=address))
    groups = {'resident_selection_transform': 0, 'resource_guards_and_missing_file': 0,
              'complete_ground_consumers': 0}
    outcomes = Counter(); samples = []
    def configure(row, state, orientation, offset):
        item = row[fc['ItemTableId']]
        u.mem_write(stage+0xa58, struct.pack('<Q', item)); u.mem_write(stage+0xa4c, struct.pack('<Q', item))
        d(stage+0xa40, state); u.mem_write(stage+0xab8, bytes([64 if orientation else 0]))
        u.mem_write(stage+0x968, struct.pack('<3f', *offset))
    def variant_for(row, state, orientation):
        flip = bool(row[fc['Horizon']]) != orientation
        return (0 if state == 2 else 1 if state == 6 else 2+int(flip)), flip
    def expected(row, state, orientation, position, offset):
        variant, flip = variant_for(row, state, orientation)
        if variant == 3 and not row[fc['Rotatable']]:
            return ground_ids.get(row[fc['Floorboards']], 0), None, None
        local = [f(a-b) for a, b in zip(position, offset)]
        if variant < 2 and flip: local[0], local[2] = local[2], f(-local[0])
        entry = loaded[row[fc['UniqueID']]]; name = entry['names'][variant]
        return map_value(entry['files'][name], local[0], local[2]), entry['blob']+entry['offsets'][name]['offset'], tuple(local)
    local_points = [(-2.5, -3.75), (-2.5, -1.25), (-1.25, -2.5), (-3.75, -2.5),
                    (2.5, 1.25), (1.25, 2.5), (2.5, 3.75), (3.75, 2.5),
                    (20., 0.), (0., -20.), (0., 0.), (5., 0.)]
    for row, state, orientation, offset, (x, z) in itertools.product(
            source_floors, [2, 6, 17], [False, True],
            [(0., 0., 0.), (12.5, -4.25, -13.75)], local_points):
        configure(row, state, orientation, offset)
        position = (f(x+offset[0]), f(20.+offset[1]), f(z+offset[2]))
        raw_point = struct.pack('<3f', *position); u.mem_write(point, raw_point); observed.clear()
        wanted, map_ptr, local = expected(row, state, orientation, position, offset)
        try: result = s.call(0x18b570, (point,), limit=100000)
        except Exception as error: raise RuntimeError(f'{state=}, {orientation=}, PC={u.reg_read(regs.UC_ARM64_REG_PC):#x}: {error}') from error
        variant, flip = variant_for(row, state, orientation)
        assert result == wanted, (row[fc['UniqueID']], state, orientation, position, result, wanted)
        assert observed['variants'] == [variant]
        if map_ptr is None:
            assert observed.get('fallback') and not observed.get('maps') and not observed.get('names')
            outcomes['variant3_disallowed_fallback'] += 1
        else:
            assert observed['names'] == [loaded[row[fc['UniqueID']]]['names'][variant]]
            assert observed['maps'] == [{'ptr': map_ptr, 'position': local}]
            assert not observed.get('fallback')
            outcomes['resident_map'] += 1
            if result == 7: outcomes['resident_sentinel_without_floorboards_fallback'] += 1
        assert bytes(u.mem_read(point, 12)) == raw_point
        groups['resident_selection_transform'] += 1
        if len(samples) < 8 and map_ptr is not None and x == 2.5 and z == 1.25 and offset[0] == 0:
            samples.append({'floor_id': row[fc['UniqueID']], 'state': state, 'orientation': orientation,
                            'variant': variant, 'requested_file': observed['names'][0],
                            'world_position': position, 'map_position': local, 'attribute': result})
    # Resource readiness, type and missing-entry failures all reach the real
    # Floorboards fallback. These mutate data state only; no code is patched.
    row = source_floors[0]; entry = loaded[row[fc['UniqueID']]]
    configure(row, 2, False, (0., 0., 0.)); u.mem_write(point, struct.pack('<3f', 2.5, 0., 1.25))
    fallback = ground_ids.get(row[fc['Floorboards']], 0)
    mutations = [(resource_manager+0xf50, struct.pack('<I', 0)),
                 (ids, b'\xff\xff'), (resource_manager+0xf60, struct.pack('<I', 0)),
                 (entry['record']+0x18, b'\x00'), (entry['record']+0x20, bytes(8)),
                 (entry['unit']+0x10, struct.pack('<I', 0)),
                 (entry['unit']+0x108, struct.pack('<I', 2)),
                 (entry['unit']+0x30, bytes(8)),
                 (entry['resource'], struct.pack('<Q', 0x32cdb18))]
    for address, value in mutations:
        before = bytes(u.mem_read(address, len(value))); u.mem_write(address, value); observed.clear()
        assert s.call(0x18b570, (point,), limit=100000) == fallback
        assert observed.get('fallback') and not observed.get('maps')
        u.mem_write(address, before); groups['resource_guards_and_missing_file'] += 1
    missing_name = entry['names'][0]
    subset = {name: data for name, data in entry['files'].items() if name != missing_name}
    raw, _ = make_sarc(subset)
    assert open_native_archive(s, entry['archive'], entry['blob'], raw) == 1
    observed.clear(); assert s.call(0x18b570, (point,), limit=100000) == fallback
    assert observed.get('fallback') and observed['names'] == [missing_name]
    groups['resource_guards_and_missing_file'] += 1
    assert open_native_archive(s, entry['archive'], entry['blob'], entry['raw']) == 1
    ground_rows = ground['table']['rows']
    sample_xz = [(2.5, 1.25), (1.25, 2.5), (2.5, 3.75), (3.75, 2.5)]
    for row, state, orientation in itertools.product(source_floors, [2, 6, 17], [False, True]):
        configure(row, state, orientation, (0., 0., 0.))
        base_ids = [0, 1, 2, 3]; u.mem_write(setup['base'], bytes(48)+bytes(base_ids))
        ids_for_samples = [expected(row, state, orientation, (x, 0., z), (0., 0., 0.))[0] for x, z in sample_xz]
        ids_for_samples = [base_ids[i] if value == 7 else value for i, value in enumerate(ids_for_samples)]
        for va, field, rule in [(0x187420, 'WaterCheck', 'all'), (0x1874f0, 'PlayerNoEntry', 'any'), (0x187610, 'WaterCheck', 'two')]:
            flags = [bool(ground_rows[value][gc[field]]) for value in ids_for_samples]
            wanted = all(flags) if rule == 'all' else any(flags) if rule == 'any' else sum(flags) == 2
            assert s.call(va, (setup['coord'],), limit=400000) == int(wanted), (hex(va), row[fc['UniqueID']], state, orientation, flags)
            groups['complete_ground_consumers'] += 1
    for hook in hooks: u.hook_del(hook)
    for data in loaded.values(): assert bytes(u.mem_read(data['blob']-16, len(data['raw'])+32)) == b'\xa5'*16+data['raw']+b'\xa5'*16
    for table in setup['tables'].values(): assert bytes(u.mem_read(table['raw_base'], len(table['raw_bytes']))) == table['raw_bytes']
    result = {'groups': groups, 'cases': sum(groups.values()), 'mismatches': [], 'outcomes': dict(outcomes),
              'native_filename_contract': {'resource_column': 'RoomFloorParam.ResourceName', 'separator': '_',
                                           'variants': variants, 'extension': extension,
                                           'variant_literal_va': '0x293eabb', 'extension_literal_va': '0x2929873'},
              'source_floors': len(source_floors), 'constructed_resident_archives': len(loaded),
              'samples': samples, 'rtti_cells_reconstructed': type_cells, 'sdk': sdk, 'dependencies_stubbed': [],
              'native_chain': ['0x18b570', '0x157ab0', '0x16e6d0', '0xc69e0',
                               'original resource readiness/type functions', '0x1c84e50', '0x1f05d90',
                               'original SARC lookup', '0x880680', '0x881e50', '0x18adf0'],
              'rules': ['Resident archive uses real ready-handle checks, original vtables, native SARC constructor/parser and filename lookup.',
                        'Variants0/1/2/3 use6x6/8x8/10x6/10x6_R; variant3 additionally requires source Rotatable.',
                        'Subtract Stage-manager position at+0x968 before map lookup. For variants0/1 when Horizon XOR context orientation is true, map X/Z becomes(localZ,-localX).',
                        'A found map returning attribute7 or outside-map sentinel7 does not call Floorboards fallback. Map-not-found/unready/disallowed paths do.',
                        'Higher ground consumers inherit terrain base for sentinel7 and otherwise use the resident-map attribute.'],
              'source_tables': {'RoomFloorParam': {'json': 'tables_resolved/RoomFloorParam.json', 'source_id': floors['table']['source_id'], 'raw': floors['table']['raw']},
                                'ColGroundAttributeParam': {'json': 'tables_resolved/ColGroundAttributeParam.json', 'source_id': ground['table']['source_id'], 'raw': ground['table']['raw']}},
              'scope': 'Complete resident-map selector and ground-query chain on reconstructed loaded SARC archives and PBC map bytes, with original source floor/item definitions.',
              'limits': ['No original PBC files are present in the supplied corpus; map data and resident-resource state are reconstructed, not extracted from a running scene.',
                         'Only consumed PBC header/sector fields are specified. First4 header bytes and the first48 bytes of each52-byte record remain semantically unproven.',
                         'File-system loading, decompression, async jobs and resource allocation/lifetime are not executed.',
                         'Only the native SARC archive constructor/parser is run; ready-resource wrapper/RTTI and variant-string cache state are prepared explicitly.',
                         'This does not prove all collision geometry, island terraforming or NPC navigation.'],
              'elf_sha256': hashlib.sha256(s.image.data).hexdigest()}
    (ROOT/'output/mechanics/resident_floor_map_native.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({'groups': groups, 'cases': result['cases'], 'outcomes': dict(outcomes), 'mismatches': 0}), flush=True)


if __name__ == '__main__': main()
