"""Audit the additional user inputs without running game code or changing Godot.

This is a structural audit. Container decoding and hash matches are not proof of
complete animation, text-rendering, shader, effect or audio runtime semantics.
"""
from collections import Counter, defaultdict
from dataclasses import asdict
from pathlib import Path
import csv
import hashlib
import json
import re
import struct
import subprocess
import sys
import tempfile
import zlib

import zstandard

sys.path.insert(0, str(Path(__file__).resolve().parent / 'reference'))
from acnh_rip.formats import asb, bfsha, bflyt, bntx, byml, msbt

INPUT = Path('/workspace/downloads/acnh_additional_romfs_2026-11-02')
ROMFS = INPUT / 'romfs'
OUT = Path('/workspace/acnh-re/output/additional_romfs')
YAZ = Path('/workspace/acnh-re/work/yaz0dec-additional')
ZSTD = zstandard.ZstdDecompressor()


def sha(data):
    return hashlib.sha256(data).hexdigest()


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, separators=(',', ':'),
                               allow_nan=False) + '\n')


def inflate(data):
    if data[:4] == b'\x28\xb5\x2f\xfd':
        return ZSTD.decompress(data, max_output_size=256 * 1024 * 1024)
    if data[:4] == b'Yaz0':
        expected = struct.unpack_from('>I', data, 4)[0]
        if expected > 256 * 1024 * 1024:
            raise ValueError('Yaz0 exceeds decompression budget')
        with tempfile.TemporaryDirectory(dir='/workspace/acnh-re/work') as temp:
            inp, out = Path(temp) / 'input', Path(temp) / 'output'
            inp.write_bytes(data)
            subprocess.run([str(YAZ), str(inp), str(out)], check=True,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            result = out.read_bytes()
        if len(result) != expected:
            raise ValueError('Yaz0 size mismatch')
        return result
    return data


def sarc_members(data):
    if data[:4] != b'SARC' or data[6:8] != b'\xff\xfe':
        raise ValueError('Expected little-endian SARC')
    header = struct.unpack_from('<H', data, 4)[0]
    declared, payload = struct.unpack_from('<II', data, 8)
    if not payload <= declared <= len(data):
        raise ValueError('SARC size bounds')
    if data[header:header+4] != b'SFAT':
        raise ValueError('Missing SFAT')
    fat_size, count, hash_key = struct.unpack_from('<HHI', data, header+4)
    nodes = header + fat_size
    nt = nodes + count*16
    if data[nt:nt+4] != b'SFNT':
        raise ValueError('Missing SFNT')
    names = nt + struct.unpack_from('<H', data, nt+4)[0]
    seen = set()
    for i in range(count):
        name_hash, attr, start, end = struct.unpack_from('<IIII', data, nodes+i*16)
        if not 0 <= start <= end <= declared-payload:
            raise ValueError('SARC member bounds')
        named = bool(attr & 0x01000000)
        if named:
            offset = names + (attr & 0xFFFFFF)*4
            terminator = data.index(b'\0', offset, payload)
            name_bytes = data[offset:terminator]
            name = name_bytes.decode('utf-8')
            check = 0
            for byte in name_bytes:
                check = (check*hash_key + byte) & 0xFFFFFFFF
            if check != name_hash:
                raise ValueError('SARC filename hash mismatch')
        else:
            name = f'{name_hash:08x}'
        if name in seen:
            raise ValueError('Duplicate SARC member name')
        seen.add(name)
        yield name, payload+start, data[payload+start:payload+end]


def read_message(data):
    if data[:8] != b'MsgStdBn' or data[8:10] != b'\xff\xfe':
        raise ValueError('Expected little-endian MSBT')
    if struct.unpack_from('<I', data, 0x12)[0] != len(data):
        raise ValueError('MSBT declared size mismatch')
    count = struct.unpack_from('<H', data, 0xE)[0]
    off = 0x20
    sections = {}
    for _ in range(count):
        size = struct.unpack_from('<I', data, off+4)[0]
        if off+16+size > len(data):
            raise ValueError('MSBT section outside file')
        magic = data[off:off+4].decode('ascii')
        if magic in sections:
            raise ValueError('Duplicate MSBT section')
        sections[magic] = (off+16, data[off+16:off+16+size])
        off = (off+16+size+15) & ~15
    labels = defaultdict(list)
    _, lbl = sections['LBL1']
    groups = struct.unpack_from('<I', lbl)[0]
    for i in range(groups):
        n, o = struct.unpack_from('<II', lbl, 4+i*8)
        for _ in range(n):
            length = lbl[o]
            label = lbl[o+1:o+1+length].decode('utf-8')
            idx = struct.unpack_from('<I', lbl, o+1+length)[0]
            labels[idx].append(label)
            o += length+5
    base, txt = sections['TXT2']
    n = struct.unpack_from('<I', txt)[0]
    offsets = list(struct.unpack_from(f'<{n}I', txt, 4)) + [len(txt)]
    if offsets != sorted(offsets) or offsets[0] < 4+4*n or offsets[-1] > len(txt):
        raise ValueError('MSBT text offset bounds')
    if any(i >= n for i in labels):
        raise ValueError('MSBT label index outside text array')
    attrs = None
    if 'ATR1' in sections:
        _, attr = sections['ATR1']
        ac, stride = struct.unpack_from('<II', attr)
        if ac != n or 8+ac*stride > len(attr):
            raise ValueError('MSBT attribute bounds')
        attrs = [attr[8+i*stride:8+(i+1)*stride].hex() for i in range(ac)]
    records = []
    for i in range(n):
        raw = txt[offsets[i]:offsets[i+1]]
        text = msbt._decode_text(raw, '<', data[0xC])
        records.append({'index': i, 'labels': labels[i], 'text': text,
                        'attributes_hex': attrs[i] if attrs is not None else None,
                        'source_offset': base+offsets[i], 'source_bytes': len(raw)})
    return {'sha256': sha(data), 'section_ranges':
            {k: {'offset': v[0], 'bytes': len(v[1])} for k,v in sections.items()},
            'messages': records}


def read_bdli(data, message):
    version, n = struct.unpack_from('<HH', data, 4)
    start, end = struct.unpack_from('<II', data, 12)
    if data[:4] != b'BDLI' or version != 2 or start != 20 or end != 20+16*n:
        raise ValueError('BDLI header bounds/version')
    names = defaultdict(list)
    if message:
        for row in message['messages']:
            for label in row['labels']:
                names[zlib.crc32(label.encode())].append({'label': label, 'text_index': row['index']})
    records = []
    total = 0
    regions = []
    for i in range(n):
        o = start+16*i
        magic, count, relative, label_hash = struct.unpack_from('<4sIII', data, o)
        target = o+relative
        if magic != b'LBLI' or target < end or target+count*20 > len(data):
            raise ValueError('BDLI record bounds')
        block = data[target:target+count*20]
        records.append({'index': i, 'label_hash': f'{label_hash:08x}',
                        'label_candidates': names.get(label_hash, []),
                        'payload_count': count, 'payload_offset': target,
                        'payload_sha256': sha(block), 'payload_first_record_hex': block[:20].hex()})
        total += count
        if count:
            regions.append((target,target+count*20))
    cursor = end
    for a,b in sorted(regions):
        if a != cursor:
            raise ValueError('BDLI payload gap or overlap')
        cursor = b
    if cursor != len(data) or end+total*20 != len(data):
        raise ValueError('BDLI payload coverage')
    return {'version':version, 'sha256':sha(data), 'bytes':len(data),
            'header_word_8_raw':struct.unpack_from('<I',data,8)[0],
            'payload_record_stride':20, 'records':records}


def audit_catalogues():
    results = {}
    for name in ['KATALOG_MODEL_ACNH.csv', 'KATALOG_AUDIO_ACNH.csv']:
        with (INPUT/name).open(encoding='utf-8-sig',newline='') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        typ = 'model' if 'MODEL' in name else 'audio'
        source_key = 'Berkas_Sumber_RomFS'
        present = sum((ROMFS/r[source_key]).is_file() for r in rows if r.get(source_key))
        counts = {key: dict(Counter(r[key] for r in rows)) for key in reader.fieldnames
                  if key in ['Kategori','Ada_Model_3D','Format_File','Tipe_Audio','Kategori_Spesifik']}
        summary = {'rows':len(rows), 'columns':reader.fieldnames, 'counts':counts,
                   'raw_romfs_source_path_matches':present if typ=='audio' else None,
                   'generated_paths_are_references_only': True}
        dump(OUT/'catalogues'/f'{typ}.json', {'summary':summary,'entries':rows})
        results[typ] = summary
    return results


def main():
    errors = []
    counts = Counter()
    catalogues = audit_catalogues()
    manifest = json.loads((OUT/'extracted_manifest.json').read_text())
    old = {x['path']:x['original_B_data'] for x in manifest['files']}
    resources = []
    signatures = Counter()
    processed_bdli = set()
    languages = Counter()
    asb_counts = Counter()

    def inspect(source, member, data, depth=0):
        if depth > 4:
            raise ValueError('Container nesting limit')
        data = inflate(data)
        magic = data[:8]
        signatures[magic.hex()] += 1
        record = {'source':source, 'member':member, 'bytes':len(data),
                  'sha256':sha(data), 'magic_hex':magic.hex()}
        resources.append(record)
        if data[:4] == b'SARC':
            members = list(sarc_members(data))
            counts['sarc_containers'] += 1
            counts['sarc_members'] += len(members)
            for name, offset, content in members:
                nested_name = member+'!'+name if member else name
                try:
                    inspect(source, nested_name, content, depth+1)
                except Exception as e:
                    errors.append({'source':source,'member':nested_name,'error':str(e)})
            record['members'] = len(members)
        elif data[:4] == b'FLYT':
            tree = bflyt.read_bflyt(data)
            dump(OUT/'ui'/f'{sha((source+"!"+member).encode())}.json',
                 {'source':source,'member':member,'layout':tree})
            counts['bflyt_layouts'] += 1
        elif data[:4] == b'BNTX':
            textures = bntx.read_bntx(data)
            record['textures'] = textures
            counts['bntx_containers'] += 1
            counts['bntx_textures'] += len(textures)
        elif data[:8] == b'FSHA    ':
            shader = bfsha.Bfsha(data)
            models = []
            for model in shader.models:
                value = asdict(model)
                for kind in ['static_options','dynamic_options']:
                    for opt, original in zip(value[kind],getattr(model,kind)):
                        opt['choices'] = shader.choices(original)
                models.append(value)
            dump(OUT/'shaders'/f'{sha((source+"!"+member).encode())}.json',
                 {'source':source,'member':member,'name':shader.name,'models':models,
                  'scope':'Option/choice metadata; GPU programs are not decompiled.'})
            counts['bfsha_archives'] += 1
            counts['shading_models'] += len(models)
            counts['shader_program_slots'] += sum(m.program_count for m in shader.models)

    # Decode each language archive and bind its BDLI hashes to actual labels.
    for p in sorted((ROMFS/'Message').glob('*.sarc.zs')):
        source = str(p.relative_to(ROMFS))
        match = re.fullmatch(r'(.+)_([A-Z]{2}[a-z]{2})\.sarc\.zs',p.name)
        if not match:
            errors.append({'source':source,'error':'Unknown language archive naming'})
            continue
        domain, lang = match.groups()
        messages = {}
        indices = {}
        try:
            data = inflate(p.read_bytes())
            members = list(sarc_members(data))
            counts['message_archives'] += 1
            for name,offset,content in members:
                if content[:8] != b'MsgStdBn':
                    errors.append({'source':source,'member':name,'error':'Non-MSBT message member'})
                    continue
                try:
                    msg = read_message(content)
                    msg['archive_member_offset'] = offset
                    messages[name] = msg
                    counts['msbt_files'] += 1
                    counts['messages'] += len(msg['messages'])
                    counts['message_labels'] += sum(len(r['labels']) for r in msg['messages'])
                    languages[lang] += len(msg['messages'])
                    target = ROMFS/'BDLI'/domain/lang/(Path(name).stem+'.bdli.zs')
                    if target.is_file():
                        key = str(target.relative_to(ROMFS))
                        if key in processed_bdli:
                            raise ValueError('Ambiguous BDLI to MSBT member mapping')
                        bdli = read_bdli(inflate(target.read_bytes()), msg)
                        bdli['source'] = key
                        bdli['message_member'] = name
                        indices[key] = bdli
                        processed_bdli.add(key)
                        counts['bdli_files_matched_to_msbt'] += 1
                        for row in bdli['records']:
                            counts['bdli_label_records'] += 1
                            counts['bdli_payload_records'] += row['payload_count']
                            counts['bdli_unique_crc_label_matches'] += len(row['label_candidates']) == 1
                            counts['bdli_crc_unmatched'] += len(row['label_candidates']) == 0
                            counts['bdli_crc_ambiguous'] += len(row['label_candidates']) > 1
                except Exception as e:
                    errors.append({'source':source,'member':name,'error':str(e)})
            dump(OUT/'messages'/lang/f'{domain}.json', {'source':source,'members':messages})
            dump(OUT/'bdli'/lang/f'{domain}.json', {'message_archive':source,'files':indices,
                 'scope':'CRC-linked labels and bounded payload records; 20-byte payload semantics unproven.'})
        except Exception as e:
            errors.append({'source':source,'error':str(e)})
        print(json.dumps({'message_archive':p.name,'messages_total':counts['messages'],
                          'errors':len(errors)}),flush=True)

    for p in sorted((ROMFS/'BDLI').rglob('*.zs')):
        key = str(p.relative_to(ROMFS))
        if key not in processed_bdli:
            try:
                result = read_bdli(inflate(p.read_bytes()),None)
                counts['bdli_files_without_msbt'] += 1
                dump(OUT/'bdli_unmatched'/f'{sha(key.encode())}.json',{'source':key,**result})
            except Exception as e:
                errors.append({'source':key,'error':str(e)})

    for p in sorted(ROMFS.rglob('*')):
        if not p.is_file():
            continue
        source = str(p.relative_to(ROMFS))
        if source.startswith(('BDLI/','Message/')) or old[source] == 'identical':
            continue
        try:
            data = p.read_bytes()
            if p.suffix == '.asb':
                parsed = asb.parse(data,source)
                w = struct.unpack_from('<24I',data)
                if w[10]+4+12*parsed['counts']['parameter_cases'] != w[9]:
                    raise ValueError('ASB parameter/pool boundary mismatch')
                if not parsed['string_pool']['size_matches_word20']:
                    raise ValueError('ASB string pool size mismatch')
                dump(OUT/'animation_sequences'/(p.name+'.json'),parsed)
                asb_counts.update(parsed['counts'])
                counts['asb_files'] += 1
            elif p.suffix == '.byml':
                parsed = byml.read_byml(data)
                def jsonify(x):
                    if isinstance(x,bytes):return {'bytes_hex':x.hex()}
                    if isinstance(x,dict):return {k:jsonify(v) for k,v in x.items()}
                    if isinstance(x,list):return [jsonify(v) for v in x]
                    return x
                dump(OUT/'new_byml'/(source+'.json'),{'source':source,'data':jsonify(parsed)})
                counts['new_raw_byml_files'] += 1
            else:
                inspect(source,'',data)
        except Exception as e:
            errors.append({'source':source,'error':str(e)})
    dump(OUT/'resource_inventory.json',{'resources':resources,
         'decompressed_magic_counts':dict(signatures)})
    summary = {'input_comparison':manifest['summary'],'counts':dict(counts),
               'message_counts_by_language':dict(languages),'asb_counts':dict(asb_counts),
               'catalogues':catalogues,'errors':errors,
               'limits':['No complete-game runtime execution.',
                         'ASB conditions and transition index meanings remain partial.',
                         'BDLI payload semantics are not inferred from hash/bounds matches.',
                         'BFSHA option metadata is not shader source reconstruction.',
                         'No Model or Sound/Resource source directories in the supplied archive.',
                         'Godot and the original source package remain unchanged.']}
    dump(OUT/'summary.json',summary)
    print(json.dumps({'completed':True,'counts':dict(counts),'asb_counts':dict(asb_counts),
                      'errors':len(errors)}),flush=True)


if __name__ == '__main__':
    main()
