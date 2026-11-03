"""Reproducible structural UI/FLAN and island-reference audit; no game execution.

Offsets are relative to the decompressed member unless explicitly stated.
Curve target IDs are intentionally numeric: decoding bytes does not establish
the engine's target-property meanings, controller bindings or interpolation.
"""
from pathlib import Path
from collections import Counter, defaultdict
import hashlib
import json
import math
import struct
import sqlite3

from audit_additional_romfs import ROMFS, inflate, sarc_members, dump

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'output/ui_island'


def sha(b):
    return hashlib.sha256(b).hexdigest()


def sections(b):
    assert b[4:6] == b'\xff\xfe', 'unsupported byte order'
    pos = struct.unpack_from('<H', b, 6)[0]
    assert struct.unpack_from('<I', b, 12)[0] == len(b)
    for _ in range(struct.unpack_from('<H', b, 16)[0]):
        assert pos + 8 <= len(b)
        size = struct.unpack_from('<I', b, pos + 4)[0]
        assert size >= 8 and pos + size <= len(b)
        yield pos, b[pos:pos + 4].decode('ascii'), b[pos:pos + size]
        pos += size
    assert pos == len(b), 'unassigned bytes after section table'


def cstr(b, o, end=None):
    return b[o:b.index(b'\0', o, end)].decode('utf-8')


def animation(b):
    out = {'sections': [], 'contents': []}
    for off, kind, s in sections(b):
        out['sections'].append({'offset': off, 'kind': kind,
                                'size': len(s), 'sha256': sha(s)})
        if kind == 'pat1':
            order, count, nameoff, groupoff = struct.unpack_from('<HHII', s, 8)
            out['tag'] = {'order': order, 'name': cstr(s, nameoff),
                          'groups': [s[groupoff + i*36:groupoff + i*36 + 33]
                                     .split(b'\0')[0].decode('utf-8') for i in range(count)]}
            assert groupoff + count*36 <= len(s)
        if kind != 'pai1':
            continue
        frames, loop, _, textures, count, table = struct.unpack_from('<HBBHHI', s, 8)
        out.update(frames=frames, loop_byte=loop, texture_count=textures)
        assert table + count*4 <= len(s)
        for i in range(count):
            co = struct.unpack_from('<I', s, table + i*4)[0]
            assert co + 32 <= len(s)
            name = s[co:co + 28].split(b'\0')[0].decode('utf-8')
            infos, target_type = s[co + 28:co + 30]
            item = {'offset': off + co, 'name': name,
                    'target_type_id': target_type, 'infos': []}
            info_table = co + 32
            if target_type == 2:
                relative_table, relative_name = struct.unpack_from('<II', s, co + 32)
                info_table = co + relative_table
                item['extended_target_name'] = cstr(s, co + relative_name)
                item['extended_info_table_relative_offset'] = relative_table
            for j in range(infos):
                io = co + struct.unpack_from('<I', s, info_table + j*4)[0]
                assert io + 8 <= len(s)
                magic, targets = s[io:io + 4].decode('ascii'), s[io + 4]
                info = {'offset': off + io, 'kind': magic, 'targets': []}
                for k in range(targets):
                    to = io + struct.unpack_from('<I', s, io + 8 + k*4)[0]
                    assert to + 12 <= len(s)
                    index, prop, curve, reserved, nkeys, pad, keyoff = struct.unpack_from('<BBBBHHI', s, to)
                    target = {'offset': off + to, 'index_id': index,
                              'property_id': prop, 'curve_type_id': curve,
                              'key_count': nkeys, 'key_data_offset':off + to + keyoff,
                              'reserved_byte':reserved,'reserved_u16':pad}
                    assert curve in (1, 2), ('unknown curve', curve)
                    stride = 8 if curve == 1 else 12
                    ko = to + keyoff
                    assert ko + nkeys*stride <= len(s)
                    keys = []
                    for q in range(nkeys):
                        p = ko + q*stride
                        if curve == 2:
                            key = list(struct.unpack_from('<fff', s, p))
                        else:
                            frame, value, spare = struct.unpack_from('<fHH', s, p)
                            key = [frame, value, spare]
                        assert all(math.isfinite(x) for x in key)
                        keys.append(key)
                    target['key_encoding'] = 'f32_frame_f32_value_f32_slope' if curve == 2 else 'f32_frame_u16_value_u16_reserved'
                    target['keys'] = keys
                    info['targets'].append(target)
                item['infos'].append(info)
            out['contents'].append(item)
    return out


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    counts, errors = Counter(), []
    layouts, anims, other = [], [], []
    parsed = {}
    for p in sorted((ROOT/'output/additional_romfs/ui').glob('*.json')):
        d = json.loads(p.read_text())
        parsed[(d['source'], d['member'])] = (p, d['layout'])

    def inspect(source, member, data):
        data = inflate(data)
        if data[:4] == b'SARC':
            for n, _, c in sarc_members(data):
                inspect(source, member + '!' + n if member else n, c)
            return
        ref = {'source': source, 'member': member, 'sha256': sha(data), 'bytes': len(data)}
        if data[:4] == b'FLAN':
            counts['animation_members'] += 1
            try:
                a = animation(data)
                ident = sha((source + '!' + member).encode())
                path = OUT/'animations'/f'{ident}.json'
                dump(path, {**ref, **a})
                summary = {**ref, 'json': str(path.relative_to(ROOT/'output')),
                           **{k: v for k, v in a.items() if k not in ('contents', 'sections')}}
                summary['targets'] = [{'name': x['name'], 'target_type_id': x['target_type_id']}
                                      for x in a['contents']]
                summary['track_count'] = sum(len(info['targets']) for x in a['contents'] for info in x['infos'])
                summary['key_count'] = sum(t['key_count'] for x in a['contents'] for info in x['infos'] for t in info['targets'])
                counts['animation_tracks'] += summary['track_count']
                counts['animation_keys'] += summary['key_count']
                anims.append(summary)
            except Exception as e:
                errors.append({**ref, 'error': str(e), 'scope': 'animation'})
        elif data[:4] == b'FLYT':
            counts['layout_members'] += 1
            p, tree = parsed[(source, member)]
            record = {**ref, 'decoded_json': str(p.relative_to(ROOT/'output')),
                      'name': tree['layout'].get('name'), 'components': [],
                      'materials': tree['materials'], 'textures': tree['textures'],
                      'fonts': tree['fonts'], 'groups': tree['groups'], 'sections': []}
            def walk(pane, parent):
                if pane is None:
                    return
                ident = len(record['components'])
                record['components'].append({'id': ident, 'parent_id': parent,
                                             **{k:v for k,v in pane.items() if k != 'children'}})
                counts['panes'] += 1
                counts['pane_'+pane['type']] += 1
                for c in pane['children']:
                    walk(c, ident)
            walk(tree['root'], None)
            for off, kind, s in sections(data):
                record['sections'].append({'offset': off, 'kind': kind, 'size': len(s), 'sha256': sha(s)})
                counts['layout_section_'+kind] += 1
            layouts.append(record)
        else:
            other.append({**ref, 'magic_hex': data[:8].hex()})

    for p in sorted((ROMFS/'Layout').iterdir()):
        inspect(str(p.relative_to(ROMFS)), '', p.read_bytes())

    # Exact names only; alternatives retained instead of selecting an arbitrary component.
    by_name = defaultdict(list)
    by_container = defaultdict(list)
    resources = json.loads((ROOT/'output/additional_romfs/resource_inventory.json').read_text())['resources']
    texture_sources = defaultdict(list)
    font_sources = defaultdict(list)
    for resource in resources:
        for texture in resource.get('textures', []):
            texture_sources[texture['name']].append({'source':resource['source'],'member':resource['member'],
                                                     'container_sha256':resource['sha256'],'metadata':texture})
        if resource['magic_hex'].startswith(('46435058','46464e54')):
            font_sources[Path(resource['member'].split('!')[-1]).name].append(
                {k:resource[k] for k in ('source','member','sha256')})
    for l in layouts:
        by_name[Path(l['member'].split('!')[-1]).stem].append(l)
        by_container[(l['source'], l['member'].split('!')[:-1][0] if '!' in l['member'] else '')].append(l)
    for a in anims:
        container = a['member'].split('!')[:-1][0] if '!' in a['member'] else ''
        hosts = by_container.get((a['source'], container), [])
        a['host_layout_candidates'] = [{'source':l['source'],'member':l['member']} for l in hosts]
        for t in a['targets']:
            matches = []
            for l in hosts:
                if t['target_type_id'] in (0, 2):
                    matches.extend({'layout_member':l['member'],'component_id':c['id']} for c in l['components'] if c['name']==t['name'])
                elif t['target_type_id'] == 1:
                    matches.extend({'layout_member':l['member'],'material_index':i} for i,m in enumerate(l['materials']) if m['name']==t['name'])
            t['same_container_name_candidates'] = matches
            counts['animation_content_targets'] += 1
            counts['animation_content_targets_with_name_match'] += bool(matches)
    unresolved_parts = []
    for l in layouts:
        l['texture_refs'] = []
        l['font_refs'] = []
        for name in l['textures']:
            candidates=[r for r in texture_sources[name] if r['source']==l['source']]
            scope='same-source-archive'
            if not candidates:
                candidates=texture_sources[name]
                scope='global-name-only'
            l['texture_refs'].append({'name':name,'match_scope':scope,'candidates':candidates})
            counts['texture_refs']+=1
            counts['texture_refs_with_candidates']+=bool(candidates)
        for name in l['fonts']:
            candidates=[r for r in font_sources[name] if r['source']==l['source']]
            scope='same-source-archive'
            if not candidates:
                candidates=font_sources[name]
                scope='global-name-only'
            l['font_refs'].append({'name':name,'match_scope':scope,'candidates':candidates})
            counts['font_refs']+=1
            counts['font_refs_with_candidates']+=bool(candidates)
        names = Counter(c['name'] for c in l['components'])
        for c in l['components']:
            if 'part_layout' in c:
                name = Path(c['part_layout']).stem
                candidates = by_name.get(name, [])
                c['part_layout_candidates'] = [{'source': x['source'], 'member': x['member']} for x in candidates]
                c['candidate_content_sha256'] = sorted({x['sha256'] for x in candidates})
                counts['part_refs'] += 1
                if len(candidates) == 1:
                    counts['part_refs_unique'] += 1
                else:
                    unresolved_parts.append({'source': l['source'], 'pane': c['name'], 'name': name,
                                             'candidate_count': len(candidates)})
                if candidates and len({x['sha256'] for x in candidates}) == 1:
                    counts['part_refs_single_content'] += 1
            if 'material' in c and not (0 <= c['material'] < len(l['materials'])):
                errors.append({'scope':'material_index', 'source':l['source'], 'pane':c['name'], 'index':c['material']})
            if 'font' in c and not (0 <= c['font'] < len(l['fonts'])):
                errors.append({'scope':'font_index', 'source':l['source'], 'pane':c['name'], 'index':c['font']})
        for group in l['groups']:
            group['unmatched_panes'] = [n for n in group['panes'] if not names[n]]
        for material in l['materials']:
            for texmap in material['texmaps']:
                if not (0 <= texmap['texture'] < len(l['textures'])):
                    errors.append({'scope':'texture_index','source':l['source'],'material':material['name'],'index':texmap['texture']})
    dump(OUT/'layouts.json', {'scope': 'Structural pane fields inherited from baseline parser; not a render validation.',
                              'layouts': layouts, 'unresolved_part_refs': unresolved_parts})
    dump(OUT/'animations.json', {'scope': 'Decoded FLAN offsets, numeric targets and keys; controller/interpolation runtime unverified.',
                                 'animations': anims})
    dump(OUT/'other_layout_members.json', {'members':other})

    def table(name):
        d = json.loads((ROOT/'output/tables_resolved'/f'{name}.json').read_text())
        cols = [x['name'] for x in d['columns']]
        return d, [dict(zip(cols, row)) for row in d['rows']]
    td, templates = table('FieldOutsideTemplate')
    pd, parts = table('FieldOutsideParts')
    md, main_rows = table('FieldMainFieldParam')
    part_kinds = defaultdict(list)
    for r in parts:
        part_kinds[r['PartsKind']['hash']].append(r)
    coast = []
    for t in templates:
        slots = []
        for name, value in t.items():
            if not name.endswith('Parts'):
                continue
            candidates = part_kinds.get(value['hash'], [])
            slots.append({'slot': name, 'kind':value, 'candidate_parts':candidates})
            counts['coast_slots'] += 1
            counts['coast_slots_without_candidates'] += not bool(candidates)
        coast.append({'template':{k:v for k,v in t.items() if not k.endswith('Parts')}, 'slots':slots})
    catalog = json.loads((ROOT/'output/byml_resolved/catalogue.json').read_text())
    by_stem = defaultdict(list)
    for c in catalog:
        by_stem[Path(c['source']).stem].append(c)
    bindings = []
    for row in main_rows:
        links = {}
        for key in ('FieldData','Label','StructureData','ItemData'):
            if key == 'FieldData':
                links[key] = {suffix:by_stem.get(row[key]+'_'+suffix, []) for suffix in ('LandMaking','EventPlaza')}
                counts['preset_'+key+'_matched'] += all(len(c)==1 for c in links[key].values())
            else:
                candidates = by_stem.get(row[key], [])
                links[key] = candidates
                counts['preset_'+key+'_matched'] += len(candidates) == 1
        bindings.append({'row': row, 'links':links,
                         'outside_template_selection': 'OutsideTemplateKind is a category, not a template UniqueID; native category selection and all 96 candidate pools are documented in preset_template_candidate_pools.json; final UID remains RNG/cache-dependent'})
    dump(OUT/'island.json', {
        'tables': {n:{'source_id':d['source_id'],'json':f'tables_resolved/{n}.json'} for n,d in
                   [('FieldOutsideTemplate',td),('FieldOutsideParts',pd),('FieldMainFieldParam',md)]},
        'coast_templates':coast, 'parts':parts, 'preset_bindings':bindings,
        'native_terrain_reference':'relations/terrain_native.json',
        'contracts':[
            'Slot PartsKind hash selects a candidate set. Native 0x4dea40/0x4dfeb0 prove per-slot selection; 9x8 assembly and guarded center-of-cell instance placement are documented in ui_island/coast_part_assembly_native.json and coast_part_instantiation_native.json.',
            'Main-field preset links are exact filename-stem matches, not proof of loader order.',
            'Structure site coordinates do not identify building types without further code evidence.',
            'ItemNameParam u64 remains packed; do not equate the full value to an item ID.',
            'UnitX/UnitZ and HalfUnitX/HalfUnitZ retain original units; no world-scale conversion is assumed.',
            'River/waterfall model references do not prove water geometry, flow, foam or collision.'
        ]})
    counts.update(coast_templates=len(templates), coast_parts=len(parts), main_presets=len(main_rows))
    # Source-derived strings are candidate code entry points, never proven handlers.
    db = sqlite3.connect(ROOT/'output/index.sqlite')
    candidates = []
    exact = defaultdict(list)
    for va, owner, text in db.execute('SELECT DISTINCT string_va,function_va,text FROM string_refs WHERE length(text)<100'):
        exact[text].append({'string_va':hex(va),'function_va':hex(owner)})
    for name in sorted(by_name):
        hits = exact.get(name, [])
        if hits:
            candidates.append({'layout_name':name,'string_ref_candidates':hits})
    counts['layout_names_with_exact_native_string_candidates'] = len(candidates)
    dump(OUT/'native_candidates.json', {'evidence_level':'Exact string-reference candidates only; no controller/handler assignment asserted.',
                                        'layouts':candidates})
    dump(OUT/'component_coverage.json', {'levels':{
        'S':'source structure decoded','L':'static reference linked','C':'native candidate only','U':'unproven'},
        'components':[
            {'component':'UI pane hierarchy/transforms/text/material indices','level':'S','evidence':'ui_island/layouts.json','open':'Full material shader, window rendering, localization substitution and visual equivalence'},
            {'component':'UI reusable parts','level':'L','evidence':'ui_island/layouts.json','open':'Ambiguous source aliases and native resource-loader precedence'},
            {'component':'UI animation tracks/keyframes','level':'S','evidence':'ui_island/animations.json','open':'Numeric property mapping, interpolation, animation triggers and state machines'},
            {'component':'UI controller definitions/user data','level':'U','evidence':'ui_island/layouts.json sections cnt1/usd1','open':'356 cnt1 sections and 2164 usd1 sections remain semantically unparsed'},
            {'component':'UI input/focus/modal/lifecycle','level':'C','evidence':'ui_island/native_candidates.json','open':'String candidates do not prove button handlers or input routing'},
            {'component':'Main terrain/event-plaza/structure/item preset joins','level':'L','evidence':'ui_island/island.json','open':'Label/VillagePreset is not proven to be a filename; structure identities and packed item bits need code proof'},
            {'component':'Outer coast template slots, part candidates, sea ring and instance placement','level':'L','evidence':'ui_island/coast_part_assembly_native.json; ui_island/coast_part_instantiation_native.json; ui_island/island.json','open':'Parent RNG end-to-end, parent/world transform, per-part rotation, model/PBC loading, seams and collision'},
            {'component':'Terrain unit schema/variation/height','level':'S','evidence':'relations/terrain_native.json','open':'Runtime world-loader chain; prior native proof scope is recorded separately'},
            {'component':'River/waterfall/ocean rendering and simulation','level':'U','evidence':'relations/terrain_native.json; ui_island/river_grid_topology.json; ui_island/coast_part_assembly_native.json; ui_island/coast_part_instantiation_native.json','open':'River-to-coast seam, geometry, flow, foam, shoreline, crossing and runtime editing'},
            {'component':'Island placement validation and commit','level':'U','evidence':'mechanics/continuation_frontier.json','open':'Footprints, previews, terrain edits, permissions, atomic save/rollback and runtime integration'}]})
    summary = {'schema':'acnh-ui-island/1', 'date':'2026-11-03', 'counts':dict(counts), 'errors':errors,
               'native_case_count_added':0,
               'completion':'Partial: source component inventory and binary structures; not complete UI or island gameplay.',
               'limits':['UI input routing, handlers, focus/navigation, modal/lifecycle and text substitution remain unproven.',
                         'FLAN numeric property IDs and engine interpolation are not runtime validated.',
                         'Additional layout members (including control definitions) are inventoried, not semantically decoded.',
                         'Coast parent/world transform, rotation and model loading, placement transactions and full river physics remain open.',
                         'Godot remains unchanged.']}
    dump(OUT/'summary.json', summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
