#!/usr/bin/env python3
"""Validate prior exports, preserve supplementary data, and recover audio conditions."""
import collections
import json
from pathlib import Path
import struct
import sys
import zlib

from reverse_corpus import dump, sha
from conditions import read_condition, parse_text, normalized

ROOT = Path(__file__).resolve().parent.parent
SOURCE = Path('/workspace/downloads/ACNH_island_RE/ACNH_island_RE')
OUT = ROOT / 'output'
REF = SOURCE / 'C_reverse'


def store(data):
    digest = sha(data)
    p = OUT / 'blobs' / (digest + '.bin')
    p.parent.mkdir(parents=True, exist_ok=True)
    if not p.exists():
        p.write_bytes(data)
    return {'$blob': str(p.relative_to(OUT)), 'size': len(data), 'sha256': digest}


def build():
    manifest = json.loads((OUT / 'manifest.json').read_text())['entries']
    tables = {}
    checked_values = 0
    representation_changes = 0
    mismatches = []
    for e in manifest:
        if e['format'] != 'BCSV':
            continue
        table = Path(e['source']).stem
        d = json.loads((OUT / e['decoded']).read_text())['data']
        prior = json.loads((REF / 'generated/data/bcsv' / (table + '.json')).read_text())
        raw_col = {c['hash']: (i, c) for i, c in enumerate(d['columns'])}
        for c in prior['columns']:
            ci, newc = raw_col[c['hash']]
            for i, row in enumerate(prior['rows']):
                old, new = row[c['name']], d['rows'][i][ci]
                equal = old == new
                if isinstance(new, dict) and new.get('$bytes_hex') == old:
                    equal = True
                    representation_changes += 1
                if c.get('enum_hash') and isinstance(old, str):
                    h = int(old[2:], 16) if old.startswith('h_') else zlib.crc32(old.encode()) & 0xffffffff
                    equal = (new & 0xffffffff) == h
                if c['type'] == 'f32':
                    equal = isinstance(new, (int, float)) and abs(old - new) <= max(1e-12, abs(new) * 6e-7)
                checked_values += 1
                if not equal:
                    mismatches.append({'table': table, 'row': i, 'column': c['hash'], 'old': old, 'new': new})
        tables[table] = prior

    # All BYML-derived JSON and binary references are checked, including 58 exports
    # with no corresponding raw BYML. Those are explicitly marked lower evidence.
    byml_dir = REF / 'generated/data/byml'
    blobs_seen = {}
    blob_errors = []
    supplement = []
    conditions = []
    for p in sorted(byml_dir.rglob('*.json')):
        rel = p.relative_to(byml_dir)
        raw_present = (SOURCE / 'B_data' / rel.with_suffix('.byml')).exists()
        original = json.loads(p.read_text())
        def visit(x, path=()):
            if isinstance(x, dict):
                if '$bin' in x:
                    f = (p.parent / x['$bin']).resolve()
                    if not f.is_relative_to(byml_dir.resolve()):
                        raise ValueError('unsafe prior blob reference')
                    if not f.is_file() or f.stat().st_size != x['size']:
                        blob_errors.append({'source': str(rel), 'reference': x})
                        return x
                    raw = f.read_bytes()
                    blobs_seen[str(f.relative_to(byml_dir))] = sha(raw)
                    return {**store(raw), 'prior_reference': x['$bin']}
                for k, v in x.items():
                    if k.endswith('Bin') and isinstance(v, dict) and '$bin' in v:
                        raw = (p.parent / v['$bin']).read_bytes()
                        if raw[:2] == b'C1':
                            text = x.get(k[:-3])
                            record = {'source': str(rel), 'path': '/'.join(path + (k,)),
                                      'text': text, 'raw': store(raw)}
                            try:
                                decoded = read_condition(raw)
                                expected = parse_text(text)
                                record.update(decoded=decoded,
                                    conventional_text_ast_matches=normalized(decoded['ast']) == normalized(expected))
                                if not record['conventional_text_ast_matches']:
                                    record['text_ast_conventional_precedence'] = expected
                            except Exception as error:
                                record['error'] = str(error)
                            conditions.append(record)
                return {k: visit(v, path + (k,)) for k, v in x.items()}
            if isinstance(x, list):
                return [visit(v, path + (str(i),)) for i, v in enumerate(x)]
            return x
        converted = visit(original)
        if not raw_present:
            target = Path('supplementary/byml') / rel
            dump(OUT / target, {'schema': 'acnh-re/1', 'source': str(p), 'source_sha256': sha(p.read_bytes()),
                'evidence': 'prior_json_export; original_BYML_not_supplied', 'data': converted})
            supplement.append({'path': str(rel), 'decoded': str(target), 'sha256': sha(p.read_bytes())})
    dump(OUT / 'supplementary/manifest.json', {'entries': supplement, 'checked_blob_references': blobs_seen,
                                            'blob_errors': blob_errors})

    bgm = json.loads((byml_dir / 'Sound/Bgm/BgmStatic.json').read_text())
    properties = bgm['GlobalProperty']
    # Expose explicit order, which is different from BgmPropertyParam.UniqueID.
    dump(OUT / 'audio/condition_bytecode.json', {'schema': 'acnh-re/1',
        'global_properties': [{'index': i, **v} for i, v in enumerate(properties)],
        'conditions': conditions,
        'warning': 'Use the decoded binary AST. One source expression differs under conventional boolean precedence.'})
    graph_nodes, graph_edges, missing_dest = 0, 0, []
    graph_types = collections.Counter()
    for name, graph in bgm['BGM'].items():
        nodes = graph['Node']
        names = {n['Name'] for n in nodes}
        graph_nodes += len(nodes)
        for n in nodes:
            graph_types[n['Type']] += 1
            for t in n.get('Transition', []):
                graph_edges += 1
                if t.get('DestinationNode') not in names:
                    missing_dest.append({'graph': name, 'destination': t.get('DestinationNode')})
    property_controls = []
    props_by_id = {r['UniqueID']: r['h_13ab5198'] for r in tables['BgmPropertyParam']['rows']}
    names_to_index = {p['Name']: i for i, p in enumerate(properties)}
    for r in tables['BgmPropertyControlParam']['rows']:
        name = props_by_id.get(r['h_4e46c669'])
        property_controls.append({'control_id': r['UniqueID'], 'value': r['Value'],
             'property_id': r['h_4e46c669'], 'property_name': name,
             'global_property_index': names_to_index.get(name), 'description': r['h_85cf1615']})
    dump(OUT / 'audio/property_controls.json', {'evidence': 'ID joins and exact name joins; no guessed renumbering',
                                              'controls': property_controls})

    # Recipe pair candidates: all material IDs resolve to ItemParam; missing IDs
    # agree with zero quantities across all rows. This is data inference, not a
    # claim about recovered original field names or native consumption order.
    item_ids = {r['UniqueID'] for r in tables['ItemParam']['rows']}
    recipe = tables['RecipeCraftParam']
    id_cols, count_cols = [], []
    for c in recipe['columns']:
        if c['type'] != 'u16' or not c['name'].startswith('h_'):
            continue
        values = [r[c['name']] for r in recipe['rows']]
        if all(v in item_ids or v == 65534 for v in values):
            id_cols.append(c['name'])
        if all(0 <= v <= 100 for v in values):
            count_cols.append(c['name'])
    pairs = []
    for ic in id_cols:
        matches = [qc for qc in count_cols if all((r[ic] == 65534) == (r[qc] == 0) for r in recipe['rows'])]
        pairs.append({'item_column': ic, 'quantity_candidates': matches,
                      'active_rows': sum(r[ic] != 65534 for r in recipe['rows'])})
    dump(OUT / 'relations/recipe_material_candidates.json', {'status': 'data_inferred; native reader confirmation pending',
        'native_reader_candidate_va': '0xedc240', 'rows_checked': len(recipe['rows']),
        'sentinel': 65534, 'pairs': pairs})

    # Recheck the already-converted world records against every byte of raw
    # LandMaking cells. Keep Godot files read-only and publish only evidence.
    by_source = {e['source']: e for e in manifest}
    byte_values = [collections.Counter() for _ in range(14)]
    terrain_mismatches, terrain_missing_ids, terrain_records, presets = [], set(), 0, []
    unit_ids = {r['UniqueID'] for r in tables['FieldLandMakingUnitModelParam']['rows']}
    def find_blob(x):
        if isinstance(x, dict):
            if '$blob' in x:
                return x
            for v in x.values():
                found = find_blob(v)
                if found:
                    return found
        return None
    for p in sorted((REF / 'generated/world').glob('MainField_*.json')):
        w = json.loads(p.read_text())
        preset = w['preset']
        source = f'B_data/Param/Field/MainFieldPreset/FieldPreset{preset}_LandMaking.byml'
        e = by_source[source]
        blob = find_blob(json.loads((OUT / e['decoded']).read_text())['data']['root'])
        raw = (OUT / blob['$blob']).read_bytes()
        if len(raw) != 112 * 96 * 14:
            raise ValueError('unexpected terrain blob size')
        for i, cell in enumerate(w['cells']):
            b = raw[i * 14:(i + 1) * 14]
            if cell[-1] != b.hex() or cell[0] != struct.unpack_from('<H', b)[0] or cell[3] != b[4] or cell[4] != b[12]:
                terrain_mismatches.append({'preset': preset, 'cell': i})
            for k, v in enumerate(b):
                byte_values[k][v] += 1
            if cell[0] not in unit_ids:
                terrain_missing_ids.add(cell[0])
            terrain_records += 1
        presets.append({'preset': preset, 'source_id': e['id'], 'cells': len(w['cells']),
                        'prior_export': str(p), 'prior_export_sha256': sha(p.read_bytes())})
    terrain = {'presets': presets, 'record_size': 14, 'grid': [112, 96], 'records_checked': terrain_records,
               'mismatches': terrain_mismatches, 'unknown_unit_ids': sorted(terrain_missing_ids),
               'field_layout': [{'offset': 0, 'size': 2, 'type': 'u16_le', 'role': 'FieldLandMakingUnitModelParam.UniqueID'},
                                {'offset': 4, 'size': 1, 'role': 'rotation_quarter_turns', 'evidence': 'prior_RE_plus_byte_recheck'},
                                {'offset': 12, 'size': 1, 'role': 'terrain_level', 'evidence': 'prior_RE_plus_byte_recheck'}],
               'byte_statistics': [{'offset': k, 'distinct_values': len(c), 'counts': dict(c)} for k, c in enumerate(byte_values)],
               'unresolved_byte_offsets': [2, 3, 5, 6, 7, 8, 9, 10, 11, 13]}
    dump(OUT / 'relations/terrain.json', terrain)

    stats = {'bcsv_values_checked_against_prior_export': checked_values,
             'bcsv_hex_strings_now_explicit_bytes': representation_changes,
             'bcsv_export_mismatches': len(mismatches), 'supplementary_byml_exports': len(supplement),
             'prior_binary_references_checked': len(blobs_seen), 'prior_binary_reference_errors': len(blob_errors),
             'condition_blobs_decoded': sum('decoded' in r for r in conditions),
             'condition_decode_errors': sum('error' in r for r in conditions),
             'condition_conventional_ast_matches': sum(r.get('conventional_text_ast_matches', False) for r in conditions),
             'condition_precedence_discrepancies': sum('decoded' in r and not r['conventional_text_ast_matches'] for r in conditions),
             'bgm_graphs': len(bgm['BGM']), 'bgm_nodes': graph_nodes, 'bgm_transitions': graph_edges,
             'bgm_missing_destinations': len(missing_dest), 'bgm_node_types': dict(graph_types),
             'recipe_material_pair_candidates': len(pairs), 'terrain_records_checked': terrain_records,
             'terrain_mismatches': len(terrain_mismatches)}
    dump(OUT / 'semantic_summary.json', stats)
    dump(OUT / 'validation_discrepancies.json', {'bcsv': mismatches, 'bgm_destinations': missing_dest,
          'condition_precedence': [r for r in conditions if 'decoded' in r and not r['conventional_text_ast_matches']]})
    print(json.dumps(stats, indent=2))


if __name__ == '__main__':
    if len(sys.argv) > 1:
        SOURCE = Path(sys.argv[1]).resolve()
        REF = SOURCE / 'C_reverse'
    build()
