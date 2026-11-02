#!/usr/bin/env python3
"""Validate community field descriptors against local CRCs, offsets and bytes.

External Python is parsed with ast.literal_eval, never imported or executed.
"""
import ast
import collections
import hashlib
import json
from pathlib import Path
import struct
import zlib

from reverse_corpus import dump

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'output'
EXT = ROOT / 'tools/external/CylindricalEarth'
COMMIT = 'bb09c0ee71a4aa6011de088b88ea55fdee0bf6e9'


def read_reference():
    tree = ast.parse((EXT / 'specs_100.py').read_text())
    tables, enums = {}, {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.value, (ast.List, ast.Tuple)):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id.startswith('enum_'):
                    enums[target.id] = ast.literal_eval(node.value)
        if not isinstance(node, ast.ClassDef):
            continue
        fields = {}
        for field in node.body:
            if not isinstance(field, ast.Assign) or not isinstance(field.value, ast.Call):
                continue
            call = field.value
            if not call.args or not isinstance(call.args[0], ast.Constant):
                continue
            key = call.args[0].value
            if not isinstance(key, int):
                continue
            typ = call.func.attr if isinstance(call.func, ast.Attribute) else call.func.id
            fields[f'{key:08x}'] = {'name': field.targets[0].id, 'type': typ,
                'line': field.lineno, 'enum': call.args[1].id if typ == 'Enum' else None}
        if fields:
            tables[node.name] = fields
    names = {}
    for node in ast.walk(ast.parse((EXT / 'build_specs.py').read_text())):
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'preset_names' for t in node.targets):
            value = ast.literal_eval(node.value)
            for key, descriptor in value.items():
                h = f'{key:08x}' if isinstance(key, int) else key
                if zlib.crc32(descriptor.encode()) == int(h, 16):
                    names[h] = descriptor
    return tables, enums, names


def build():
    tables, enums, names = read_reference()
    native_fields=json.loads((ROOT/'tools/knowledge/bcsv_native_types.json').read_text())['fields']
    native_types={(f['table'],f['hash']):f for f in native_fields}
    manifest = json.loads((OUT / 'manifest.json').read_text())['entries']
    stats = collections.Counter()
    unresolved, enum_misses, corrections, catalogue = [], [], [], []
    scalar = {'u8': 'B', 'u16': 'H', 'u32': 'I', 's8': 'b', 's16': 'h', 's32': 'i', 'f32': 'f'}
    for entry in manifest:
        if entry['format'] != 'BCSV':
            continue
        old = json.loads((OUT / entry['decoded']).read_text())['data']
        name = Path(entry['source']).stem
        specs = tables[name]
        raw = (OUT / entry['raw']['$blob']).read_bytes()
        cols, decoded = [], []
        for col in old['columns']:
            h = col['hash']
            spec = specs[h]
            desc = names.get(h)
            enum = spec.get('enum')
            values = {}
            if enum:
                for en, jp in enums[enum]:
                    label = jp if raw[11] == 0 else en
                    eh = zlib.crc32(label.encode())
                    if eh in values and values[eh] != [en, jp]:
                        raise ValueError('enum hash collision')
                    values[eh] = [en, jp]
            field = {**col, 'descriptor': desc, 'reference_type': spec['type'],
                     'reference_line': spec['line'], 'enum_values': {f'{k:08x}': v for k,v in values.items()} if enum else None}
            if desc:
                assert zlib.crc32(desc.encode()) == int(h,16)
                if desc.endswith('.hshCstringRef'):
                    field.update(name=desc.removesuffix('.hshCstringRef'), type='enum_crc32')
                else:
                    label, typ = desc.rsplit(' ',1)
                    field.update(name=label, type=typ)
                field['name_evidence'] = 'crc32_exact_descriptor_and_local_schema'
                field['type_evidence'] = 'crc32_exact_descriptor'
                field['name_reference'] = 'CylindricalEarth/build_specs.py:preset_names'
                stats['named_columns'] += 1
            else:
                field.update(name='h_' + h, name_evidence='unresolved')
                unresolved.append({'table': name, 'hash': h, 'reference_type': spec['type'], 'offset': col['offset'], 'width': col['width']})
            if enum:
                field['type'] = 'enum_crc32'
            native=native_types.get((name,h))
            if native:
                if desc:raise ValueError(('native override unexpectedly overlaps named descriptor',name,h))
                field.update(type=native['type'],type_evidence='native_read_view; original descriptor unresolved',
                    native_read_evidence=native)
                stats['native_read_views']+=1
            if col['type'] != field['type']:
                corrections.append({'table': name, 'hash': h, 'old_inferred_type': col['type'], 'resolved_type': field['type'], 'descriptor': desc})
            cols.append(field)
        for row_index in range(old['row_count']):
            row = []
            for index, col in enumerate(cols):
                off = old['data_start'] + row_index * old['row_size'] + col['offset']
                typ, width = col['type'], col['width']
                if typ in scalar:
                    assert struct.calcsize(scalar[typ]) <= width
                    v = struct.unpack_from('<' + scalar[typ], raw, off)[0]
                elif typ == 'enum_crc32':
                    h = struct.unpack_from('<I', raw, off)[0]
                    labels = col['enum_values'].get(f'{h:08x}') if col['enum_values'] else None
                    v = {'hash': f'{h:08x}', 'labels': labels}
                    stats['enum_values'] += 1
                    if labels:
                        stats['enum_values_resolved'] += 1
                    else:
                        enum_misses.append({'table': name, 'row': row_index, 'field': col['name'], 'hash': f'{h:08x}'})
                elif typ.startswith('string'):
                    n = int(typ[6:]) if typ[6:] else width
                    assert n <= width
                    text_bytes = raw[off:off+n].split(b'\0')[0]
                    try:
                        v = text_bytes.decode('utf-8')
                    except UnicodeDecodeError:
                        v = {'$bytes_hex': text_bytes.hex(), 'encoding': 'invalid_or_truncated_utf8'}
                        stats['invalid_utf8_preserved'] += 1
                else:
                    v = old['rows'][row_index][index]
                row.append(v)
            decoded.append(row)
        dest = 'tables_resolved/' + name + '.json'
        dump(OUT / dest, {'source_id': entry['id'], 'raw': entry['raw'], 'source': entry['source'],
            'row_count': old['row_count'], 'row_size': old['row_size'], 'columns': cols,
            'rows': decoded, 'enum_language': 'Japanese' if raw[11] == 0 else 'English',
            'reference': {'repository': 'Treeki/CylindricalEarth', 'commit': COMMIT, 'file': 'specs_100.py'},
            'note': 'Rows follow columns. Unnamed fields retain provisional types; raw source is authoritative.'})
        catalogue.append({'table': name, 'json': dest, 'rows': len(decoded), 'columns': len(cols)})
        stats.update(tables=1, columns=len(cols), rows=len(decoded))
    dump(OUT / 'schemas/catalogue.json', catalogue)
    dump(OUT / 'schemas/unresolved_names.json', unresolved)
    dump(OUT / 'schemas/enum_unresolved.json', enum_misses)
    dump(OUT / 'schemas/type_changes.json', corrections)
    dump(OUT / 'schemas/summary.json', {'counts': dict(stats), 'unresolved_columns': len(unresolved),
        'type_changes': len(corrections), 'external_reference': {'repository': 'https://github.com/Treeki/CylindricalEarth',
        'commit': COMMIT, 'license': 'GPL-3.0', 'author': 'Ash Wolf / Ninji',
        'files': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in EXT.iterdir() if p.is_file()}}})
    print(json.dumps(dict(stats), indent=2))


if __name__ == '__main__':
    build()
