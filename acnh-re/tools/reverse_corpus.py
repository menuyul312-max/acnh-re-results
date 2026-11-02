#!/usr/bin/env python3
"""Engine-neutral, provenance-preserving audit of the supplied ACNH corpus."""
import argparse
import base64
import collections
import hashlib
import importlib
import json
import math
from pathlib import Path
import re
import struct
import sys
import zlib

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / 'reference'))
from acnh_rip.formats import byml, bfevfl, bfres, bntx


def sha(data):
    return hashlib.sha256(data).hexdigest()


def clean(value):
    if isinstance(value, float) and not math.isfinite(value):
        return {'$nonfinite': repr(value)}
    if isinstance(value, dict):
        return {str(k): clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean(v) for v in value]
    return value


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(clean(value), ensure_ascii=False, separators=(',', ':'), allow_nan=False))


def need(data, off, size):
    if off < 0 or size < 0 or off + size > len(data):
        raise ValueError(f'out of bounds: offset={off:#x}, size={size}, file={len(data)}')


def yaz0(data):
    need(data, 0, 16)
    if data[:4] != b'Yaz0':
        raise ValueError('not Yaz0')
    target = struct.unpack_from('>I', data, 4)[0]
    if target > 512 * 1024 * 1024:
        raise ValueError('Yaz0 output exceeds analysis limit')
    out = bytearray()
    pos = 16
    while len(out) < target:
        need(data, pos, 1)
        code = data[pos]
        pos += 1
        for bit in range(7, -1, -1):
            if len(out) == target:
                break
            if code & (1 << bit):
                need(data, pos, 1)
                out.append(data[pos])
                pos += 1
            else:
                need(data, pos, 2)
                a, b = data[pos:pos + 2]
                pos += 2
                distance = ((a & 15) << 8 | b) + 1
                count = a >> 4
                if count:
                    count += 2
                else:
                    need(data, pos, 1)
                    count = data[pos] + 0x12
                    pos += 1
                if distance > len(out) or len(out) + count > target:
                    raise ValueError('invalid Yaz0 back-reference')
                for _ in range(count):
                    out.append(out[-distance])
    return bytes(out), {'declared_size': target, 'consumed_bytes': pos, 'trailing_bytes': len(data) - pos}


def sarc(data):
    need(data, 0, 0x14)
    bom = data[6:8]
    endian = '<' if bom == b'\xff\xfe' else '>' if bom == b'\xfe\xff' else None
    if endian is None:
        raise ValueError('invalid SARC BOM')
    u16 = lambda o: struct.unpack_from(endian + 'H', data, o)[0]
    u32 = lambda o: struct.unpack_from(endian + 'I', data, o)[0]
    header, size, payload = u16(4), u32(8), u32(12)
    if size != len(data):
        raise ValueError('SARC file size mismatch')
    need(data, header, 12)
    if data[header:header + 4] != b'SFAT':
        raise ValueError('missing SFAT')
    n, multiplier = u16(header + 6), u32(header + 8)
    nodes = header + u16(header + 4)
    need(data, nodes, n * 16)
    sfnt = nodes + n * 16
    need(data, sfnt, 8)
    if data[sfnt:sfnt + 4] != b'SFNT':
        raise ValueError('missing SFNT')
    names = sfnt + u16(sfnt + 4)
    members = []
    seen = set()
    for i in range(n):
        h, attr, start, end = struct.unpack_from(endian + 'IIII', data, nodes + i * 16)
        if start > end:
            raise ValueError('SARC inverted member range')
        need(data, payload + start, end - start)
        name = f'unnamed_{h:08x}'
        hash_ok = None
        if attr >> 24:
            off = names + (attr & 0xffffff) * 4
            need(data, off, 1)
            stop = data.find(b'\0', off, payload)
            if stop < 0:
                raise ValueError('unterminated SARC member name')
            name = data[off:stop].decode('utf-8')
            accum = 0
            for byte in name.encode():
                accum = (accum * multiplier + byte) & 0xffffffff
            hash_ok = accum == h
            if not hash_ok:
                raise ValueError('SARC member name hash mismatch')
        if name in seen:
            raise ValueError('duplicate SARC member name')
        seen.add(name)
        members.append((name, data[payload + start:payload + end], {
            'offset': payload + start, 'size': end - start,
            'name_hash': f'{h:08x}', 'name_hash_valid': hash_ok, 'attributes': attr}))
    return members, {'endian': endian, 'file_size': size, 'data_offset': payload,
                     'member_count': n, 'hash_multiplier': multiplier}


class Corpus:
    def __init__(self, source, output):
        self.source, self.output = source, output
        self.reference = source / 'C_reverse'
        self.entries = []
        self.names = collections.defaultdict(set)
        self.hash_observed = collections.Counter()
        self.bcsv_tables = {}
        self.flows = {}
        self.aamp_types = collections.Counter()
        self.unknown_aamp = collections.Counter()
        self.named_keys = 0
        self.total_keys = 0
        self.load_names()

    def load_names(self):
        def add(s):
            if isinstance(s, str) and 0 < len(s) <= 256:
                self.names[zlib.crc32(s.encode()) & 0xffffffff].add(s)
        data = (self.source / 'A_logic/main.elf').read_bytes()
        for match in re.finditer(rb'[\x20-\x7e]{3,256}', data):
            s = match.group().decode('ascii')
            add(s)
            for word in re.findall(r'[A-Za-z_][A-Za-z0-9_]{1,127}', s):
                add(word)
            if ',' in s:
                for item in s.split(','):
                    add(item.strip())
        for p in (self.reference / 'generated/data/bcsv').glob('*.json'):
            j = json.loads(p.read_text())
            for col in j['columns']:
                if not col['name'].startswith('h_'):
                    add(col['name'])
            for row in j['rows']:
                for v in row.values():
                    if isinstance(v, str):
                        add(v)
        catalog = json.loads((self.reference / 'export/fld_models_aabb_materials.json').read_text())
        def collect(x):
            if isinstance(x, dict):
                for k, v in x.items():
                    add(k)
                    collect(v)
            elif isinstance(x, list):
                for v in x:
                    collect(v)
            elif isinstance(x, str):
                add(x)
        collect(catalog)

    def name(self, h):
        names = sorted(self.names.get(h, []))
        self.hash_observed[h] += 1
        self.total_keys += 1
        self.named_keys += len(names) == 1
        return names

    def store(self, data):
        digest = sha(data)
        p = self.output / 'blobs' / (digest + '.bin')
        if not p.exists():
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(data)
        return {'$blob': str(p.relative_to(self.output)), 'size': len(data), 'sha256': digest}

    def json_value(self, x):
        if isinstance(x, bytes):
            return self.store(x)
        if isinstance(x, list):
            return [self.json_value(v) for v in x]
        if isinstance(x, dict):
            out = {}
            for k, v in x.items():
                if re.fullmatch('[0-9a-fA-F]{1,8}', k):
                    self.name(int(k, 16))
                out[k] = self.json_value(v)
            return out
        return x

    def bcsv(self, data, table):
        need(data, 0, 0x1c)
        n, stride, nc = struct.unpack_from('<IIH', data)
        extended = bool(data[10])
        header = 0x1c if extended else 0x0c
        if extended and data[12:16] != b'VSCB':
            raise ValueError('invalid BCSV magic')
        start = header + nc * 8
        need(data, header, nc * 8)
        need(data, start, n * stride)
        fields = sorted(struct.unpack_from('<II', data, header + i * 8) for i in range(nc))
        fields.sort(key=lambda x: x[1])
        refp = self.reference / 'generated/data/bcsv' / (table + '.json')
        reference = json.loads(refp.read_text()) if refp.exists() else {'columns': [], 'rows': []}
        refs = {int(c['hash'], 16): c for c in reference['columns']}
        columns, rows = [], []
        formats = {'u8': 'B', 's8': 'b', 'bool': 'B', 'u16': 'H', 's16': 'h',
                   'u32': 'I', 's32': 'i', 'u64': 'Q', 's64': 'q', 'f32': 'f', 'f64': 'd'}
        for i, (h, off) in enumerate(fields):
            width = (fields[i + 1][1] if i + 1 < nc else stride) - off
            if off < 4 or width <= 0 or off + width > stride:
                raise ValueError('invalid BCSV field range')
            r = refs.get(h, {})
            name, typ = r.get('name'), r.get('type')
            trusted_name = bool(name and not name.startswith('h_') and
                                zlib.crc32(f'{name} {typ}'.encode()) & 0xffffffff == h)
            if r and (r['offset'] != off or r['width'] != width):
                raise ValueError('reference BCSV layout mismatch')
            columns.append({'hash': f'{h:08x}', 'offset': off, 'width': width,
                            'name': name if trusted_name else None,
                            'name_evidence': 'crc32_name_space_type' if trusted_name else 'unresolved',
                            'type': typ, 'type_evidence': 'name_hash' if trusted_name else 'reference_inference',
                            'reference_enum_hash': bool(r.get('enum_hash'))})
        for i in range(n):
            base = start + i * stride
            if struct.unpack_from('<I', data, base)[0] != base:
                raise ValueError(f'row self-offset mismatch at row {i}')
            row = []
            for c in columns:
                pos, width, typ = base + c['offset'], c['width'], c['type']
                raw = data[pos:pos + width]
                if typ in formats and struct.calcsize('<' + formats[typ]) <= width:
                    v = struct.unpack_from('<' + formats[typ], raw)[0]
                    if typ == 'bool':
                        v = bool(v)
                elif typ == 'string':
                    b = raw.split(b'\0', 1)[0]
                    try:
                        v = b.decode('utf-8')
                    except UnicodeDecodeError:
                        v = {'$bytes_hex': b.hex()}
                else:
                    v = {'$bytes_hex': raw.hex()}
                row.append(v)
            rows.append(row)
        doc = {'row_count': n, 'row_size': stride, 'extended_header': extended,
               'version': struct.unpack_from('<I', data, 16)[0] if extended else None,
               'data_start': start, 'trailing_bytes': len(data) - start - n * stride,
               'columns': columns, 'rows': rows,
               'note': 'Rows follow column order. Raw source is authoritative; inferred types remain provisional.'}
        self.bcsv_tables[table] = doc
        return doc

    def aamp(self, data):
        need(data, 0, 0x30)
        words = struct.unpack_from('<12I', data)
        if words[1] != 2 or words[3] != len(data) or not words[2] & 1:
            raise ValueError('unsupported AAMP header, size, or endian')
        root = 0x30 + words[5]
        seen_lists, seen_objects, params = set(), set(), []
        def named(h):
            return {'hash': f'{h:08x}', 'name_candidates': self.name(h)}
        def plist(off):
            need(data, off, 12)
            if off in seen_lists:
                raise ValueError('repeated/cyclic AAMP list')
            seen_lists.add(off)
            h, lo, nl, oo, no = struct.unpack_from('<IHHHH', data, off)
            out = {'offset': off, **named(h), 'lists': [], 'objects': []}
            for i in range(nl):
                out['lists'].append(plist(off + lo * 4 + i * 12))
            for i in range(no):
                ob = off + oo * 4 + i * 8
                need(data, ob, 8)
                if ob in seen_objects:
                    raise ValueError('repeated AAMP object')
                seen_objects.add(ob)
                oh, po, pn = struct.unpack_from('<IHH', data, ob)
                obj = {'offset': ob, **named(oh), 'parameters': []}
                for k in range(pn):
                    p = ob + po * 4 + k * 8
                    need(data, p, 8)
                    ph, raw = struct.unpack_from('<II', data, p)
                    typ, valueoff = raw >> 24, p + (raw & 0xffffff) * 4
                    need(data, valueoff, 0)
                    param = {'offset': p, **named(ph), 'type_code': typ, 'data_offset': valueoff,
                             'pointer_word_hex': f'{raw:08x}'}
                    params.append(param)
                    obj['parameters'].append(param)
                out['objects'].append(obj)
            return out
        tree = plist(root)
        bounds = sorted({p['data_offset'] for p in params} | {len(data)})
        import bisect
        unresolved = []
        type_names = {0: 'bool', 1: 'f32', 2: 's32', 3: 'vec2', 4: 'vec3', 5: 'vec4',
                      6: 'color4', 7: 'str32', 8: 'str64', 9: 'curve1', 10: 'curve2',
                      11: 'curve3', 12: 'curve4', 13: 'buffer_s32', 14: 'buffer_f32',
                      15: 'str256', 16: 'quaternion', 17: 'u32', 18: 'buffer_u32',
                      19: 'buffer_bytes', 20: 'string_reference'}
        for p in params:
            t, off = p['type_code'], p['data_offset']
            p['type'] = type_names.get(t, 'unknown')
            self.aamp_types[p['type']] += 1
            if t in (0, 1, 2, 17):
                need(data, off, 4)
                v = struct.unpack_from('<' + {0: 'I', 1: 'f', 2: 'i', 17: 'I'}[t], data, off)[0]
                p['value'] = bool(v) if t == 0 else v
                p['value_size'] = 4
            elif t in (3, 4, 5, 6, 16):
                n = {3: 2, 4: 3, 5: 4, 6: 4, 16: 4}[t]
                need(data, off, n * 4)
                p['value'] = list(struct.unpack_from('<' + str(n) + 'f', data, off))
                p['value_size'] = n * 4
            elif t in (7, 8, 15, 20):
                stop = data.find(b'\0', off)
                if stop < 0:
                    raise ValueError('unterminated AAMP string')
                p['value'] = data[off:stop].decode('utf-8', 'surrogateescape')
                p['value_size'] = stop - off + 1
            elif t in (13, 14, 18, 19):
                need(data, off - 4, 4)
                n = struct.unpack_from('<I', data, off - 4)[0]
                width = 1 if t == 19 else 4
                need(data, off, n * width)
                if t == 19:
                    p['value'] = self.store(data[off:off + n])
                else:
                    fmt = {13: 'i', 14: 'f', 18: 'I'}[t]
                    p['value'] = list(struct.unpack_from('<' + str(n) + fmt, data, off))
                p['value_size'] = n * width
            elif t in (9, 10, 11, 12):
                n = t - 8
                need(data, off, n * 128)
                p['value_size'] = n * 128
                p['curves'] = [{'word0': struct.unpack_from('<I', data, off + k * 128)[0],
                                'word1': struct.unpack_from('<I', data, off + k * 128 + 4)[0],
                                'payload_f32': list(struct.unpack_from('<30f', data, off + k * 128 + 8)),
                                'raw': self.store(data[off + k * 128:off + (k + 1) * 128])}
                               for k in range(n)]
                recognized = all(c['word1'] in (7, 10) and 6 <= c['word0'] <= 30 and c['word0'] % 3 == 0 for c in p['curves'])
                if recognized:
                    for c in p['curves']:
                        c['num_use'] = c['word0']
                        c['kind'] = c['word1']
                        c['points'] = [c['payload_f32'][i:i+3] for i in range(0,c['num_use'],3)]
                    p['semantic_status'] = 'sead Hermit2D/Hermit2DSmooth; native differential evidence in environment/curves.json'
                else:
                    p['semantic_status'] = '128-byte records retained; curve kind or layout unresolved'
                    unresolved.append(t)
                    self.unknown_aamp[p['type']] += 1
            else:
                stop = bounds[bisect.bisect_right(bounds, off)] if off < len(data) else off
                p['raw_span_to_next_data_reference'] = self.store(data[off:stop])
                p['semantic_status'] = 'unresolved; span is not a proven record length'
                unresolved.append(t)
                self.unknown_aamp[p['type']] += 1
        observed = [len(seen_lists), len(seen_objects), len(params)]
        declared = list(words[6:9])
        if observed != declared:
            raise ValueError(f'AAMP declared/observed counts differ: {declared}/{observed}')
        return {'version': words[1], 'flags': words[2], 'file_size': len(data),
                'header_words': list(words), 'declared_counts': declared, 'observed_counts': observed,
                'unresolved_parameter_types': dict(collections.Counter(unresolved)), 'root': tree}

    def visit(self, source, data, parent=None, member=None, depth=0):
        if depth > 12:
            raise ValueError('container nesting exceeds limit')
        i = len(self.entries)
        rec = {'id': i, 'source': source, 'parent_id': parent, 'size': len(data), 'sha256': sha(data),
               'magic_hex': data[:16].hex(), 'member': member, 'status': 'pending'}
        self.entries.append(rec)
        rec['raw'] = self.store(data)
        try:
            if data[:4] == b'Yaz0':
                raw, meta = yaz0(data)
                rec.update(format='Yaz0', status='container_validated', metadata=meta)
                rec['children'] = [self.visit(source + '!decompressed', raw, i, depth=depth + 1)]
                return i
            if data[:4] == b'SARC':
                members, meta = sarc(data)
                rec.update(format='SARC', status='container_validated', metadata=meta)
                rec['children'] = [self.visit(source + '!' + name, raw, i, desc, depth + 1)
                                   for name, raw, desc in members]
                return i
            if data[:2] in (b'BY', b'YB'):
                rec['format'] = 'BYML'
                doc = byml.read_byml(data)
                doc['root'] = self.json_value(doc['root'])
            elif data[:6] == b'BFEVFL':
                rec['format'] = 'BFEVFL'
                doc = bfevfl.read_bfevfl(data)
                problems = bfevfl.validate(doc)
                if problems:
                    raise ValueError(str(problems))
                doc['validation_problems'] = problems
                doc['float_note'] = 'f32 parameters preserved without decimal rounding; original bytes retained.'
                self.flows[Path(source.split('!')[-1]).stem] = doc
            elif source.endswith('.bcsv') or (len(data) >= 16 and data[12:16] == b'VSCB'):
                rec['format'] = 'BCSV'
                doc = self.bcsv(data, Path(source).stem)
            elif data[:4] == b'AAMP':
                rec['format'] = 'AAMP'
                doc = self.aamp(data)
            elif data[:4] == b'FRES':
                rec['format'] = 'BFRES'
                obj = bfres.Bfres(data)
                doc = {'name': obj.name, 'version': obj.version, 'counts': obj.counts,
                       'models': obj.models(), 'external_files': []}
                rec['children'] = []
                for name, raw in obj.external_files().items():
                    child = self.visit(source + '!' + name, raw, i, depth=depth + 1)
                    rec['children'].append(child)
                    doc['external_files'].append({'name': name, 'source_id': child})
            elif data[:4] == b'BNTX':
                rec['format'] = 'BNTX'
                textures = bntx.read_bntx(data)
                arr = struct.unpack_from('<Q', data, 0x28)[0]
                for k, texture in enumerate(textures):
                    block = struct.unpack_from('<Q', data, arr + k * 8)[0]
                    tab = struct.unpack_from('<Q', data, block + 0x70)[0]
                    offsets = list(struct.unpack_from('<' + str(texture['mip_count']) + 'Q', data, tab))
                    image_end = offsets[0] + texture['image_size']
                    need(data, offsets[0], texture['image_size'])
                    texture['mips'] = []
                    for level, off in enumerate(offsets):
                        end = offsets[level + 1] if level + 1 < len(offsets) else image_end
                        if end < off:
                            raise ValueError('BNTX nonmonotonic mip offsets')
                        need(data, off, end - off)
                        texture['mips'].append({'level': level, 'offset': off,
                            'width': max(1, texture['width'] >> level),
                            'height': max(1, texture['height'] >> level),
                            'storage': 'GPU tiled, original compressed blocks',
                            'raw': self.store(data[off:end])})
                doc = {'textures': textures}
            else:
                rec.update(format='unclassified', status='opaque_preserved')
                rec['raw'] = self.store(data)
                return i
            rec['status'] = 'structure_decoded'
            doc = {'schema': 'acnh-re/1', 'source_id': i, 'source': source,
                   'source_sha256': rec['sha256'], 'format': rec['format'], 'data': doc}
            p = self.output / 'decoded' / (f'{i:05d}.json')
            dump(p, doc)
            rec['decoded'] = str(p.relative_to(self.output))
        except Exception as error:
            rec['status'] = 'error_preserved'
            rec['error'] = f'{type(error).__name__}: {error}'
            rec['raw'] = self.store(data)
        return i

    def build(self):
        for p in sorted((self.source / 'B_data').rglob('*')):
            if p.is_file():
                self.visit(str(p.relative_to(self.source)), p.read_bytes())
        dump(self.output / 'manifest.json', {'schema': 'acnh-re/1', 'source_root': str(self.source),
                                             'entries': self.entries})
        dump(self.output / 'hash_names.json', {f'{h:08x}': {'occurrences': n,
              'candidates': sorted(self.names.get(h, [])), 'evidence': 'crc32_candidate_match'}
              for h, n in sorted(self.hash_observed.items())})
        summary = {'source_files': sum(e['parent_id'] is None for e in self.entries),
                   'all_entries': len(self.entries),
                   'formats': dict(collections.Counter(e.get('format', 'unknown') for e in self.entries)),
                   'statuses': dict(collections.Counter(e['status'] for e in self.entries)),
                   'errors': [{'source': e['source'], 'error': e['error']} for e in self.entries if 'error' in e],
                   'aamp_parameter_types': dict(self.aamp_types), 'aamp_unresolved_types': dict(self.unknown_aamp),
                   'hash_key_occurrences': self.total_keys, 'hash_key_single_candidate': self.named_keys,
                   'bcsv_tables': len(self.bcsv_tables), 'eventflow_files': len(self.flows)}
        dump(self.output / 'summary.json', summary)
        return summary


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--source', type=Path, default=Path('/workspace/downloads/ACNH_island_RE/ACNH_island_RE'))
    p.add_argument('--output', type=Path, default=HERE.parent / 'output')
    args = p.parse_args()
    print(json.dumps(Corpus(args.source.resolve(), args.output.resolve()).build(), indent=2))
