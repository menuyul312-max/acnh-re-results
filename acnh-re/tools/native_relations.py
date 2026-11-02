#!/usr/bin/env python3
"""Publish terrain/recipe semantics supported by the newly inspected native code."""
import collections
import json
from pathlib import Path
import struct

from reverse_corpus import dump

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'output'
SRC = Path(json.loads((OUT/'manifest.json').read_text())['source_root'])


def rows(name):
    table = json.loads((OUT/'tables_resolved'/f'{name}.json').read_text())
    return [dict(zip([c['name'] for c in table['columns']], r)) for r in table['rows']]


def blobs(node):
    if isinstance(node, dict):
        if '$blob' in node:
            yield node
        else:
            for v in node.values():
                yield from blobs(v)
    elif isinstance(node, list):
        for v in node:
            yield from blobs(v)


def build():
    units = {r['UniqueID']: r for r in rows('FieldLandMakingUnitModelParam')}
    archive_path = SRC/'C_reverse/generated/world/unit_models.json'
    archives = json.loads(archive_path.read_text())
    index = json.loads((OUT/'manifest.json').read_text())['entries']
    terrain = {'record_size': 14, 'endianness': 'little',
        'layout': [{'offset': layer*6, 'size': 2, 'role': f'layer{layer}.unit_id'} for layer in range(2)]
        + [{'offset': layer*6+2, 'size': 2, 'role': f'layer{layer}.variation_index'} for layer in range(2)]
        + [{'offset': layer*6+4, 'size': 1, 'role': f'layer{layer}.rotation_quarter_turns'} for layer in range(2)]
        + [{'offset': off, 'size': 1, 'role': 'padding'} for off in (5,11,13)]
        + [{'offset': 12, 'size': 1, 'role': 'height'}],
        'native_evidence': {'component_constructor': '0x543230', 'record_constructor': '0x542d70',
            'record_copy': '0x542db0', 'preset_loader': '0x558f40', 'variation_limit_reader': '0x547520',
            'model_name_formatter':'0x543340', 'model_format_string_va':'0x2996f6e',
            'model_format_string':'%s_%d', 'out_of_range_variation_fallback':0,
            'height_reader': '0xf52860', 'height_valid_range': [0,5], 'height_invalid_fallback':4,
            'differential_check': 'native_verification.json'},
        'variation_note': 'BCSV Variation is the maximum permitted index; select the record variant, not the maximum.',
        'models': {}, 'presets': [], 'unknown_unit_ids': {}, 'out_of_range_variants': [],
        'legacy_layer0_model_disagreements': 0, 'layer_counts': [dict(),dict()]}
    counts = [collections.Counter(), collections.Counter()]
    for uid, row in units.items():
        terrain['models'][str(uid)] = {'base': row['ModelName'], 'max_variation': row['Variation'],
            'variants': [{'index': v, 'model': f"{row['ModelName']}_{v}",
                'archive': archives.get(f"{row['ModelName']}_{v}")} for v in range(row['Variation']+1)]}
    total = 0
    for entry in index:
        if '/MainFieldPreset/' not in entry['source'] or not entry['source'].endswith('_LandMaking.byml'):
            continue
        name = Path(entry['source']).stem
        refs = list(blobs(json.loads((OUT/entry['decoded']).read_text())['data']['root']))
        assert len(refs) == 1
        ref = refs[0]
        raw = (OUT/ref['$blob']).read_bytes()
        assert len(raw) == 112*96*14
        cells = []
        for i in range(112*96):
            off = i*14
            a, av, ar = struct.unpack_from('<HHB', raw, off)
            b, bv, br = struct.unpack_from('<HHB', raw, off+6)
            height = raw[off+12]
            for layer, uid, variant in [(0,a,av),(1,b,bv)]:
                counts[layer][uid] += 1
                if uid not in units:
                    terrain['unknown_unit_ids'][str(uid)] = terrain['unknown_unit_ids'].get(str(uid),0)+1
                elif variant > units[uid]['Variation']:
                    terrain['out_of_range_variants'].append([name,i,layer,uid,variant])
            if a in units and av != units[a]['Variation']:
                terrain['legacy_layer0_model_disagreements'] += 1
            cells.append([a,av,ar,b,bv,br,height])
        dest = f'world/{name}.json'
        dump(OUT/dest, {'source_id': entry['id'], 'raw': ref, 'grid': [112,96],
            'order': 'row_major', 'cell_fields': ['unit0','variation0','rotation0','unit1','variation1','rotation1','height'],
            'cells': cells, 'model_lookup': '../relations/terrain_native.json#models'})
        terrain['presets'].append({'source_id': entry['id'], 'json': dest, 'cells': len(cells)})
        total += len(cells)
    terrain['records'] = total
    terrain['layer_counts'] = [dict(c) for c in counts]
    dump(OUT/'relations/terrain_native.json', terrain)

    hashes = [('1bbfa75e','13a65775'),('5c1fdd8e','54062da5'),('617ff43e','69660415'),
              ('d35f282e','db46d805'),('ee3f019e','e626f1b5'),('a99f7b4e','a1868b65')]
    table = json.loads((OUT/'tables_resolved/RecipeCraftParam.json').read_text())
    positions = {c['hash']: i for i,c in enumerate(table['columns'])}
    ingredients = []
    for row in table['rows']:
        ingredients.append([{'slot': slot, 'material_id': row[positions[m]], 'quantity': row[positions[q]]}
                            for slot,(m,q) in enumerate(hashes) if row[positions[m]] != 65534])
    recipe = {'evidence': 'native switch cases 0..5 in 0xedac50', 'native_getter_va': '0xedac50',
        'status': 'slot_order_and_material_quantity_hash_pairs_native_verified', 'empty_material_sentinel': 65534,
        'quantity_native_output_type': 'u8', 'source_table': 'tables_resolved/RecipeCraftParam.json',
        'slot_hashes': [{'slot': i,'material':m,'quantity':q} for i,(m,q) in enumerate(hashes)],
        'row_ingredients': ingredients}
    dump(OUT/'relations/recipe_materials_native.json', recipe)
    print(json.dumps({'terrain_records': total, 'legacy_wrong_model_selections': terrain['legacy_layer0_model_disagreements'],
        'unknown_unit_ids': terrain['unknown_unit_ids'], 'out_of_range_variants': len(terrain['out_of_range_variants']),
        'recipe_rows': len(ingredients)}, indent=2))


if __name__ == '__main__':
    build()
