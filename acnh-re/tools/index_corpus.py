#!/usr/bin/env python3
"""Build queryable binary/data relationships without modifying a Godot project."""
import argparse
import bisect
import collections
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import struct
import sys
import zlib

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from reverse_corpus import dump, sha


def elf(data):
    if data[:6] != b'\x7fELF\x02\x01':
        raise ValueError('requires little-endian ELF64')
    phoff, shoff = struct.unpack_from('<QQ', data, 0x20)
    phe, phn, she, shn, strndx = struct.unpack_from('<5H', data, 0x36)
    segs = []
    for i in range(phn):
        t, flags, off, va, pa, fs, ms, align = struct.unpack_from('<II6Q', data, phoff + i * phe)
        if off + fs > len(data):
            raise ValueError('ELF segment out of bounds')
        segs.append({'type': t, 'flags': flags, 'offset': off, 'va': va, 'file_size': fs,
                     'memory_size': ms, 'alignment': align})
    sections = []
    for i in range(shn):
        vals = struct.unpack_from('<II4QII2Q', data, shoff + i * she)
        sections.append(dict(zip(['name_offset', 'type', 'flags', 'va', 'offset', 'size',
                                  'link', 'info', 'alignment', 'entry_size'], vals)))
    strings = sections[strndx]
    for s in sections:
        at = strings['offset'] + s.pop('name_offset')
        end = data.find(b'\0', at)
        s['name'] = data[at:end].decode('ascii')
    reloc_types = collections.Counter()
    for s in sections:
        if s['type'] == 4:
            for off in range(s['offset'], s['offset'] + s['size'], s['entry_size']):
                _, info, _ = struct.unpack_from('<QQq', data, off)
                reloc_types[str(info & 0xffffffff)] += 1
    return {'machine': struct.unpack_from('<H', data, 18)[0],
            'entry_va': struct.unpack_from('<Q', data, 24)[0],
            'segments': segs, 'sections': sections, 'relocation_types': dict(reloc_types)}


def category(name):
    rules = [('event_flags', ('EventFlags',)), ('world_and_terrain', ('Field', 'Fg', 'Col', 'Structure', 'MysteryTour')),
             ('fish', ('Fish',)), ('insects', ('Insect',)), ('items_and_crafting', ('Item', 'Recipe', 'Mannequin', 'MaterialType')),
             ('npc', ('Npc', 'NmlNpc', 'SpNpc', 'VMMultistep', 'AITag', 'Amiibo')),
             ('player', ('Player', 'Human', 'CharaMake')),
             ('calendar_and_seasons', ('Calendar', 'Season', 'Release')),
             ('audio', ('Sound', 'Bgm', 'Ducking', 'Radio', 'TV')),
             ('interiors_and_museum', ('Room', 'Indoor', 'Museum')),
             ('messages_and_localization', ('Message', 'Localize'))]
    for group, prefixes in rules:
        if name.startswith(prefixes):
            return group
    return 'other'


def build(source, root):
    out = root / 'output'
    manifest = json.loads((out / 'manifest.json').read_text())['entries']
    reference = source / 'C_reverse'
    db = sqlite3.connect(out / 'index.sqlite')
    db.executescript('''
      DROP TABLE IF EXISTS files; DROP TABLE IF EXISTS functions; DROP TABLE IF EXISTS direct_calls;
      DROP TABLE IF EXISTS string_refs; DROP TABLE IF EXISTS columns; DROP TABLE IF EXISTS hash_refs;
      DROP TABLE IF EXISTS event_calls; DROP TABLE IF EXISTS asset_entries; DROP TABLE IF EXISTS decomp;
      CREATE TABLE files(id INTEGER PRIMARY KEY, source TEXT, format TEXT, size INTEGER, sha256 TEXT, decoded TEXT);
      CREATE TABLE functions(va INTEGER PRIMARY KEY, size INTEGER, ghidra_name TEXT, decomp_path TEXT);
      CREATE TABLE direct_calls(pc INTEGER PRIMARY KEY, owner_va INTEGER, target_va INTEGER, instruction TEXT);
      CREATE TABLE string_refs(string_va INTEGER, function_va INTEGER, text TEXT);
      CREATE TABLE columns(table_name TEXT, hash INTEGER, name TEXT, offset INTEGER, width INTEGER,
                           type TEXT, evidence TEXT, PRIMARY KEY(table_name,hash));
      CREATE TABLE hash_refs(hash INTEGER, pc INTEGER, owner_va INTEGER);
      CREATE TABLE event_calls(flow TEXT, event_index INTEGER, actor TEXT, kind TEXT, name TEXT, params_json TEXT);
      CREATE TABLE asset_entries(name TEXT PRIMARY KEY, metadata_json TEXT);
      CREATE TABLE decomp(va INTEGER PRIMARY KEY, path TEXT, sha256 TEXT, in_function_snapshot INTEGER);
    ''')
    db.executemany('INSERT INTO files VALUES(?,?,?,?,?,?)',
                   [(e['id'], e['source'], e['format'], e['size'], e['sha256'], e.get('decoded')) for e in manifest])
    data = (source / 'A_logic/main.elf').read_bytes()
    info = elf(data)
    dump(out / 'binary/elf.json', {'schema': 'acnh-re/1', 'sha256': sha(data), **info})
    funcs = []
    for line in (reference / 'generated/re/functions.tsv').read_text().splitlines():
        parts = line.split('\t', 2)
        if len(parts) != 3:
            continue
        va, size, name = int(parts[0], 16) - 0x100000, int(parts[1]), parts[2]
        path = reference / 'generated/re/decomp' / (f'{va:x}.c')
        funcs.append((va, size, name, str(path) if path.exists() else None))
    funcs.sort()
    starts = [f[0] for f in funcs]
    by_va = {f[0]: f for f in funcs}
    db.executemany('INSERT INTO functions VALUES(?,?,?,?)', funcs)
    decomp = []
    for p in sorted((reference / 'generated/re/decomp').glob('*.c')):
        va = int(p.stem, 16)
        target = out / 'binary/decomp' / p.name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(p.read_bytes())
        decomp.append((va, str(target.relative_to(out)), sha(p.read_bytes()), va in by_va))
    db.executemany('INSERT INTO decomp VALUES(?,?,?,?)', decomp)
    def owner(pc):
        idx = bisect.bisect_right(starts, pc) - 1
        if idx >= 0 and pc < starts[idx] + max(funcs[idx][1], 4):
            return starts[idx]
        return None
    calls = []
    for seg in info['segments']:
        if seg['type'] != 1 or not seg['flags'] & 1:
            continue
        raw = data[seg['offset']:seg['offset'] + seg['file_size']]
        for i, (word,) in enumerate(struct.iter_unpack('<I', raw[:len(raw) // 4 * 4])):
            opcode = word & 0xfc000000
            if opcode not in (0x94000000, 0x14000000):
                continue
            delta = word & 0x3ffffff
            if delta & 0x2000000:
                delta -= 0x4000000
            pc = seg['va'] + i * 4
            target = pc + delta * 4
            own = owner(pc)
            if opcode == 0x94000000 or (target in by_va and own != target):
                calls.append((pc, own, target, 'BL' if opcode == 0x94000000 else 'B_to_function_entry'))
    db.executemany('INSERT INTO direct_calls VALUES(?,?,?,?)', calls)
    refs = []
    for line in (reference / 'generated/re/string_refs.tsv').read_text().splitlines():
        parts = line.split('\t', 2)
        if len(parts) == 3:
            try:
                refs.append((int(parts[0], 16) - 0x100000, int(parts[1], 16) - 0x100000, parts[2]))
            except ValueError:
                pass
    db.executemany('INSERT INTO string_refs VALUES(?,?,?)', refs)
    table_docs = {}
    table_source = {}
    for e in manifest:
        if e['format'] == 'BCSV':
            j = json.loads((out / e['decoded']).read_text())['data']
            name = Path(e['source']).stem
            table_docs[name] = j
            table_source[name] = e
            db.executemany('INSERT INTO columns VALUES(?,?,?,?,?,?,?)',
                [(name, int(c['hash'], 16), c['name'], c['offset'], c['width'], c['type'], c['type_evidence'])
                 for c in j['columns']])
    os.environ['ACNH_EXEFS'] = str(source / 'A_logic')
    os.environ['ACNH_OUT'] = str(root / 'work')
    from acnh_rip.re import immscan
    consts = immscan.scan()
    targets = {int(c['hash'], 16) for j in table_docs.values() for c in j['columns']}
    all_hashes = targets | {int(h, 16) for h in json.loads((out / 'hash_names.json').read_text())}
    xrefs = [(h, pc, owner(pc)) for h in all_hashes for pc in consts.get(h, [])]
    db.executemany('INSERT INTO hash_refs VALUES(?,?,?)', xrefs)

    # Only literal names from this ELF, existing table values, and exported metadata.
    # A CRC match is a candidate, never automatically promoted to proven semantics.
    words = set()
    for match in re.finditer(rb'[\x20-\x7e]{2,256}', data):
        s = match.group().decode('ascii')
        words.add(s)
        words.update(re.findall(r'[A-Za-z_][A-Za-z0-9_]{1,127}', s))
    for p in (reference / 'generated/data/bcsv').glob('*.json'):
        j = json.loads(p.read_text())
        for c in j['columns']:
            if not c['name'].startswith('h_'):
                words.add(c['name'])
        for row in j['rows']:
            words.update(v for v in row.values() if isinstance(v, str) and len(v) < 128)
    candidates = collections.defaultdict(set)
    for word in words:
        for typ in ('u8', 's8', 'bool', 'u16', 's16', 'u32', 's32', 'f32', 'u64', 's64', 'f64', 'string'):
            h = zlib.crc32((word + ' ' + typ).encode()) & 0xffffffff
            if h in targets:
                candidates[h].add((word, typ))
    del words
    domains = collections.defaultdict(list)
    known, unknown = 0, 0
    for name, table in table_docs.items():
        enriched = []
        for ci, c in enumerate(table['columns']):
            h = int(c['hash'], 16)
            vals = [row[ci] for row in table['rows']]
            numeric = [v for v in vals if type(v) in (int, float)]
            count = collections.Counter(json.dumps(v, sort_keys=True) for v in vals)
            fits = []
            widths = {'u8': 1, 's8': 1, 'bool': 1, 'u16': 2, 's16': 2, 'u32': 4, 's32': 4,
                      'f32': 4, 'u64': 8, 's64': 8, 'f64': 8}
            for word, typ in sorted(candidates[h]):
                if (typ == 'string' and c['width'] > 8) or widths.get(typ) == c['width'] or (c['name'] == word and c['type'] == typ):
                    fits.append({'name': word, 'type': typ, 'status': 'crc32_candidate_only'})
            known += c['name'] is not None
            unknown += c['name'] is None
            enriched.append({**c, 'name_candidates': fits, 'distinct_values': len(count),
                'min': min(numeric) if numeric else None, 'max': max(numeric) if numeric else None,
                'most_common': [{'value': json.loads(v), 'count': n} for v, n in count.most_common(5)],
                'immediate_reference_count': len(consts.get(h, [])),
                'function_candidates': sorted({f'{owner(pc):x}' for pc in consts.get(h, []) if owner(pc) is not None})})
        entry = {'table': name, 'source_id': table_source[name]['id'], 'row_count': table['row_count'],
                 'columns': enriched, 'domain_evidence': 'filename_classification',
                 'xref_caution': 'Shared hashes do not prove which table a function accesses; immediate scan is a candidate finder.'}
        dump(out / 'tables' / (name + '.json'), entry)
        domains[category(name)].append({'table': name, 'rows': table['row_count'],
                                       'named_columns': sum(c['name'] is not None for c in enriched),
                                       'columns': len(enriched), 'schema': f'tables/{name}.json'})

    # Event graph calls, message references, flag references, and subflow linking.
    flowdocs = {}
    for e in manifest:
        if e['format'] == 'BFEVFL':
            flowdocs[Path(e['source']).stem] = json.loads((out / e['decoded']).read_text())['data']
    flow_names = {fc['name'] for d in flowdocs.values() for fc in d['flowcharts']}
    entries_by_flow = {fc['name']: set(fc['entry_points']) for d in flowdocs.values() for fc in d['flowcharts']}
    event_rows, message_ids, flag_refs, subflows = [], [], [], []
    flag_labels = {}
    for name in table_docs:
        if name.startswith('EventFlags'):
            j = json.loads((reference / 'generated/data/bcsv' / (name + '.json')).read_text())
            flag_labels[name] = {r.get('h_45f320f2') for r in j['rows']}
    for file, doc in flowdocs.items():
        for fc in doc['flowcharts']:
            for i, ev in enumerate(fc['events']):
                actor = None
                if ev['type'] in ('action', 'switch'):
                    a = fc['actors'][ev['actor']]
                    kind = 'actions' if ev['type'] == 'action' else 'queries'
                    name = a[kind][ev['action'] if kind == 'actions' else ev['query']]
                    actor = a['name']
                    event_rows.append((file, i, actor, kind, name, json.dumps(ev.get('params'))))
                p = ev.get('params') or {}
                for k, v in p.items():
                    if k == 'MessageID' and isinstance(v, str) and v:
                        message_ids.append({'flow': file, 'event': i, 'id': v,
                                            'resolution': 'message_archive_not_supplied'})
                    if k == 'AccessKey' and isinstance(v, str) and ':' in v:
                        table, label = v.split(':', 1)
                        table = 'EventFlags' + table.removeprefix('c') + 'Param'
                        flag_refs.append({'flow': file, 'event': i, 'access_key': v,
                                          'table': table, 'label_exists': label in flag_labels.get(table, set())})
                if ev['type'] == 'subflow':
                    target = ev.get('flowchart') or fc['name']
                    subflows.append({'flow': file, 'event': i, 'target': target,
                                     'entry': ev.get('entry_point'),
                                     'target_exists': target in flow_names,
                                     'entry_exists': ev.get('entry_point') in entries_by_flow.get(target, set())})
    db.executemany('INSERT INTO event_calls VALUES(?,?,?,?,?,?)', event_rows)
    relations = {'message_references': message_ids, 'event_flag_references': flag_refs, 'subflows': subflows}
    dump(out / 'relations/eventflow.json', relations)

    # Exported model catalogue is metadata evidence, independent of Godot runtime.
    catalog_path = reference / 'export/fld_models_aabb_materials.json'
    catalog = json.loads(catalog_path.read_text())
    db.executemany('INSERT INTO asset_entries VALUES(?,?)', [(k, json.dumps(v)) for k, v in catalog.items()])
    dump(out / 'assets/catalogue.json', {'source': str(catalog_path), 'source_sha256': sha(catalog_path.read_bytes()),
                                       'evidence': 'prior_export_metadata', 'entries': catalog})
    native_registry = json.loads((root / 'work/eventflow/_registry.json').read_text())
    vtables = json.loads((root / 'work/re/evfl_vtables.json').read_text())
    dump(out / 'binary/event_handlers.json', {'evidence': 'regenerated_from_eventflows_and_ELF',
            'factory_mapping_caution': 'Exact and prefix hash matches are distinguished; factories are not behavior implementations.',
            'registry': native_registry, 'vtables': vtables})
    npdm = (source / 'A_logic/main.npdm').read_bytes()
    aci = npdm.find(b'ACI0')
    dump(out / 'binary/npdm.json', {'source_sha256': sha(npdm), 'magic': npdm[:4].decode(),
        'application_name': npdm[0x20:0x30].split(b'\0')[0].decode(), 'aci0_offset': aci,
        'program_id': f'{struct.unpack_from("<Q", npdm, aci + 0x10)[0]:016x}' if aci >= 0 else None,
        'raw': {'base64': __import__('base64').b64encode(npdm).decode()}})
    db.executescript('''CREATE INDEX calls_by_target ON direct_calls(target_va);
      CREATE INDEX refs_by_owner ON hash_refs(owner_va); CREATE INDEX refs_by_hash ON hash_refs(hash);
      CREATE INDEX strings_by_function ON string_refs(function_va);
      CREATE INDEX event_names ON event_calls(name);''')
    db.commit()
    stats = {'functions_indexed': len(funcs), 'functions_with_decomp': sum(f[3] is not None for f in funcs),
             'direct_branch_records': len(calls), 'string_references': len(refs),
             'bcsv_columns_named': known, 'bcsv_columns_unresolved': unknown,
             'unique_column_hashes': len(targets),
             'decompiled_files_indexed': len(decomp),
             'column_hashes_with_immediate_candidates': len({x[0] for x in xrefs if x[0] in targets}),
             'column_immediate_references': sum(x[0] in targets for x in xrefs),
             'all_field_immediate_references': len(xrefs),
             'event_action_query_occurrences': len(event_rows),
             'event_flag_references': len(flag_refs), 'event_flag_labels_resolved': sum(r['label_exists'] for r in flag_refs),
             'subflows': len(subflows), 'subflow_targets_missing': sum(not r['target_exists'] for r in subflows),
             'subflow_entries_missing': sum(not r['entry_exists'] for r in subflows),
             'message_references': len(message_ids),
             'native_handler_names': sum(len(v) for v in native_registry.values()),
             'native_factory_matches': sum(bool(r.get('main_elf_function')) for v in native_registry.values() for r in v.values()),
             'factory_exact_matches': sum(bool(r.get('main_elf_function')) and r.get('match') != 'prefix' for v in native_registry.values() for r in v.values()),
             'factory_prefix_candidates': sum(r.get('match') == 'prefix' for v in native_registry.values() for r in v.values()),
             'asset_catalogue_entries': len(catalog),
             'asset_catalogue_materials': sum(len(x['materials']) for x in catalog.values())}
    dump(out / 'domains.json', {'schema': 'acnh-re/1', 'domains': domains})
    dump(out / 'index_summary.json', stats)
    db.close()
    print(json.dumps(stats, indent=2))


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--source', type=Path, default=Path('/workspace/downloads/ACNH_island_RE/ACNH_island_RE'))
    p.add_argument('--root', type=Path, default=HERE.parent)
    a = p.parse_args()
    build(a.source.resolve(), a.root.resolve())
