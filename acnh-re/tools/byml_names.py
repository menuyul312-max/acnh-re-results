#!/usr/bin/env python3
"""Recover native parameter descriptors, retaining original hashes and wire types.

Descriptor recovery is separate from gameplay semantic verification. Only unique
hash matches from native/local-data strings are applied to the reversible view.
"""
import collections
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import zlib

from native_image import Image
from reverse_corpus import dump
from acnh_rip.re.immscan import murmur3

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'output'


def native_types(im):
    """Find template vtables whose name formatter uses the native '%s.%s'."""
    getters = {}
    for seg in im.segments:
        if not seg['p_flags'] & 1:
            continue
        raw, base = seg.data(), seg['p_vaddr']
        for m in re.finditer(b'\xc0\x03\x5f\xd6', raw):
            off = m.start() - 8
            if off < 0 or off % 4:
                continue
            a = int.from_bytes(raw[off:off+4], 'little')
            b = int.from_bytes(raw[off+4:off+8], 'little')
            if a & 0x9f00001f != 0x90000000 or b & 0xffc003ff != 0x91000000:
                continue
            ins = im.disasm(base+off, 12)
            va = ins[0].operands[1].imm + ins[1].operands[2].imm
            try:
                name = im.cstring(va)
                if re.fullmatch(r'[A-Za-z0-9_:<>\[\],*]{1,80}', name):
                    getters[base+off] = (name, va)
            except ValueError:
                pass
    result = collections.defaultdict(list)
    for p, target in im.relocations.items():
        if target not in getters:
            continue
        vt = p - 0xe8
        try:
            formatter = im.ptr(vt+0x58)
            # add x1,x1,#0x23b: check its preceding ADRP to verify the literal VA.
            ins = []
            for instruction in im.disasm(formatter, 160):
                ins.append(instruction)
                if instruction.mnemonic in ('ret','b','br'): break
            has_format = any(a.mnemonic == 'adrp' and a.op_str.startswith('x1,')
                and b.mnemonic == 'add' and b.op_str.startswith('x1, x1,')
                and a.operands[1].imm+b.operands[2].imm == 0x292423b
                for a, b in zip(ins, ins[1:]))
            if not has_format:
                continue
            name, va = getters[target]
            result[name].append({'vtable':hex(vt), 'formatter':hex(formatter),
                'type_function':hex(target), 'type_string':hex(va)})
        except ValueError:
            pass
    if im.cstring(0x292423b) != '%s.%s' or not {'s32','u64','u8','V3f','Str'} <= result.keys():
        raise ValueError('native descriptor evidence changed')
    return dict(sorted(result.items()))


def family(value):
    if isinstance(value, bool): return 'bool'
    if isinstance(value, int): return 'integer'
    if isinstance(value, float): return 'float'
    if isinstance(value, str): return 'string'
    if isinstance(value, list): return 'array'
    if isinstance(value, dict): return 'binary' if '$blob' in value else 'dict'
    return 'null'


def native_array_types(im):
    """Array nodes return 'yml'; the element type is in their name formatter."""
    if im.cstring(0x29b9f57) != '%s[].%s':raise ValueError('typed-array formatter changed')
    result=collections.defaultdict(list)
    for location,target in im.relocations.items():
        if target != 0x2c140:continue
        vt=location-0xe8
        try:
            formatter=im.ptr(vt+0x58);instructions=[]
            for instruction in im.disasm(formatter,160):
                instructions.append(instruction)
                if instruction.mnemonic in ('ret','b','br'):break
            has_format=False;element=None;type_va=None
            for a,b in zip(instructions,instructions[1:]):
                if a.mnemonic!='adrp' or b.mnemonic!='add':continue
                if not a.operands[0].reg==b.operands[0].reg==b.operands[1].reg:continue
                register=a.reg_name(a.operands[0].reg)
                address=a.operands[1].imm+b.operands[2].imm
                if register=='x1' and address==0x29b9f57:has_format=True
                if register=='x3':element=im.cstring(address);type_va=address
            if has_format and element and len(element)<32:
                result[element].append({'vtable':hex(vt),'formatter':hex(formatter),
                    'format_string':'0x29b9f57','element_type_string':hex(type_va),
                    'typed_name_predicate':hex(im.ptr(vt+0x120))})
        except ValueError:pass
    if not {'bool','s32','Str','Enum'}<=result.keys():raise ValueError('typed array evidence incomplete')
    return dict(sorted(result.items()))


def compatible(declared, observed):
    allowed = {
        's8':{'integer'}, 'u8':{'integer'}, 'u16':{'integer'}, 's32':{'integer'},
        'u32':{'integer'}, 'u64':{'integer'}, 'f32':{'integer','float'},
        'bool':{'bool'}, 'Bit':{'bool','integer'}, 'Enum':{'string','integer'},
        'Str':{'string'}, 'V3f':{'array'}, 'V4f':{'array'}, 'V2f':{'array'},
        'V2i':{'array'}, 'V3i':{'array'}, 'C4f':{'array'}, 'C4u8':{'array'},
        'Rangef':{'array'}, 'Curvef':{'array','binary'}, 'StructBinary':{'binary'},
    }
    return (set(observed)-{'null'}) <= allowed.get(declared, set())


def rename_tree(value, mapping, reverse=False):
    if isinstance(value, dict):
        result = {}
        for k, v in value.items():
            name = mapping.get(k, k)
            if name in result:
                raise ValueError(('readable key collision', name))
            result[name] = rename_tree(v, mapping, reverse)
        return result
    if isinstance(value, list): return [rename_tree(v, mapping, reverse) for v in value]
    return value


def build():
    im = Image()
    types = native_types(im)
    array_types=native_array_types(im)
    observations = collections.defaultdict(lambda: {'occurrences':0, 'families':collections.Counter(), 'sources':set()})
    docs = []
    for entry in json.loads((OUT/'manifest.json').read_text())['entries']:
        if entry['format'] != 'BYML': continue
        doc = json.loads((OUT/entry['decoded']).read_text())
        root = doc['data']['root']
        docs.append((entry, root))
        def walk(value):
            if isinstance(value, dict):
                for k, v in value.items():
                    if re.fullmatch('[0-9a-f]{1,8}', k):
                        r = observations[k]; r['occurrences'] += 1
                        r['families'][family(v)] += 1; r['sources'].add(entry['id'])
                    walk(v)
            elif isinstance(value, list):
                for v in value: walk(v)
        walk(root)
    names = collections.defaultdict(set)
    def local_names(value, evidence):
        if isinstance(value, str) and re.fullmatch('[A-Za-z_][A-Za-z0-9_]{0,127}',value):
            names[value].add(evidence)
        elif isinstance(value, dict):
            for key, child in value.items():
                local_names(key,evidence);local_names(child,evidence)
        elif isinstance(value,list):
            for child in value:local_names(child,evidence)
    for entry,root in docs:
        names[Path(entry['source']).stem].add('local_source_filename')
        local_names(root,'local_BYML_string')
    for p in (OUT/'tables_resolved').glob('*.json'):
        table=json.loads(p.read_text())
        local_names(table['rows'],'local_BCSV_string')
        for column in table['columns']:
            if column['descriptor']:names[column['name']].add('local_BCSV_field_name')
    for raw in im.data.split(b'\0'):
        if len(raw)>512 or not any(b>=128 for b in raw):continue
        try: text=raw.decode('utf8')
        except UnicodeDecodeError:continue
        if text and all(c.isprintable() for c in text) and any(ord(c)>127 for c in text):
            names[text].add('native_utf8_string')
    for match in re.finditer(rb'[\x20-\x7e]{1,65536}', im.data):
        s = match.group().decode('ascii')
        if re.fullmatch('[A-Za-z_][A-Za-z0-9_]{0,127}', s):
            names[s].add('native_exact_string')
        for token in re.findall(r'[A-Za-z_][A-Za-z0-9_]{1,127}', s):
            names[token].add('native_string_token')
            for i in range(1,len(token)):
                if token[i].isupper() and token[i-1].islower():
                    names[token[i:]].add('native_camel_suffix_candidate')
        if ',' in s:
            members=s.split(',')
            for i,member in enumerate(members):
                member=member.strip()
                # A bounded scan chunk may split a list entry at either end.
                if i==0 and match.start() and im.data[match.start()-1] != 0:continue
                if i==len(members)-1 and match.end()<len(im.data) and im.data[match.end()] != 0:continue
                if re.fullmatch('[A-Za-z_][A-Za-z0-9_]{0,127}',member):
                    names[member].add('native_comma_list_member')
    db = sqlite3.connect(OUT/'index.sqlite')
    string_refs=collections.defaultdict(list)
    for s,a,b in db.execute('select distinct text,string_va,function_va from string_refs'):
        string_refs[s].append({'string_va':hex(a),'function_va':hex(b)})
        if re.fullmatch('[A-Za-z_][A-Za-z0-9_]{0,127}', s):
            names[s].add('native_referenced_string')
    db.close()
    save_reference = ROOT/'tools/external/CylindricalEarth/save_keys.json'
    save_count = 0; rejected_save = []
    for group in json.loads(save_reference.read_text()).values():
        for h, name in group.items():
            if name is None: continue
            if murmur3(name.encode()) != int(h,16):
                rejected_save.append({'hash':h,'name':name,'reason':'Murmur3 seed0 mismatch'})
                continue
            names[name].add('CylindricalEarth:save_keys.json'); save_count += 1
    role_evidence={}
    for field in json.loads((ROOT/'tools/knowledge/stage_key_roles.json').read_text())['fields']:
        if murmur3(field['name'].encode())!=int(field['hash'],16):raise ValueError('stage role hash mismatch')
        names[field['name']].add('native_reader_role')
        role_evidence[field['name']]=field
    if im.cstring(0x29b4d3c) != '%s[]': raise ValueError('native array formatter changed')
    spellings = collections.defaultdict(list)
    for key in observations: spellings[f'{int(key,16):08x}'].append(key)
    candidates = collections.defaultdict(list)
    for name, evidence in names.items():
        for declared in [None, 'array', *types, *['array<'+t+'>' for t in array_types]]:
            element=declared[6:-1] if declared and declared.startswith('array<') else None
            descriptor = name+'[].'+element if element else name + '[]' if declared == 'array' else name + '.' + declared if declared else name
            h = f'{zlib.crc32(descriptor.encode()):08x}'
            if h not in spellings: continue
            # ELF string pooling can point into a suffix of a longer C string.
            # Require a terminating NUL for those token-only candidates too.
            if not {'native_exact_string','native_referenced_string'} & evidence:
                location = im.data.find(name.encode()+b'\0')
                if location >= 0: evidence.add('native_terminated_suffix')
            for spelling in spellings[h]:
                families = observations[spelling]['families']
                valid = set(families) <= {'array','null'} if declared == 'array' or element else compatible(declared, families) if declared else set(families) <= {'dict','array','null'}
                candidates[spelling].append({'descriptor':descriptor, 'name':name, 'declared_type':declared,
                    'array_element_type':element,
                    'algorithm':'CRC32', 'sources':sorted(evidence-{'native_reader_role'}), 'wire_family_compatible':valid})
        h = f'{murmur3(name.encode()):08x}'
        if h in spellings and not {'native_exact_string','native_referenced_string','native_utf8_string'} & evidence:
            if im.data.find(name.encode()+b'\0') >= 0:evidence.add('native_terminated_suffix')
        for spelling in spellings.get(h,[]):
            candidates[spelling].append({'descriptor':name, 'name':name, 'declared_type':None,
                'algorithm':'Murmur3_32_seed0', 'sources':sorted(evidence),
                'native_role_evidence':role_evidence.get(name),
                'wire_family_compatible':True})
    mapping = {}; records = {}
    for h, observed in sorted(observations.items()):
        possible = candidates.get(h, [])
        eligible = [p for p in possible if p['wire_family_compatible'] and
            {'native_exact_string','native_referenced_string','native_terminated_suffix',
             'native_comma_list_member','native_utf8_string',
             'local_source_filename','local_BYML_string','local_BCSV_string','local_BCSV_field_name',
             'native_reader_role'} & set(p['sources'])]
        selected = eligible[0] if len(eligible) == 1 else None
        # Prefix prevents confusion with existing, unhashed literal keys in other
        # files (EventFlowInfo contains both named and hashed key vocabularies).
        if selected: mapping[h] = '@' + selected['descriptor']
        for p in possible:
            p['native_string_refs'] = string_refs.get(p['name'],[])
        records[h] = {'occurrences':observed['occurrences'], 'value_families':dict(observed['families']),
            'source_ids':sorted(observed['sources']), 'selected':selected, 'candidates':possible,
            'status':'unique_local_descriptor_match' if selected else 'unresolved_or_ambiguous',
            'semantic_status':'name/type recovered by hash; gameplay meaning requires separate evidence'}
    inverse = {name:h for h,name in mapping.items()}
    if len(inverse) != len(mapping): raise ValueError('non-bijective name mapping')
    catalogue = []; roundtrips = 0
    for entry, root in docs:
        readable = rename_tree(root, mapping)
        if rename_tree(readable, inverse) != root: raise ValueError(('BYML name roundtrip',entry['source']))
        roundtrips += 1
        path = f"byml_resolved/{entry['id']:05d}.json"
        dump(OUT/path, {'source_id':entry['id'], 'source':entry['source'], 'source_sha256':entry['sha256'],
            'raw':entry['raw'], 'key_dictionary':'../schemas/byml_names.json',
            'key_contract':'@descriptor denotes a recovered hash key; literal source keys remain unchanged.',
            'numeric_contract':'Readable values follow decoded JSON; consult byml_typed for exact wire tags and 64-bit hex/decimal.',
            'root':readable})
        catalogue.append({'source_id':entry['id'],'source':entry['source'],'json':path,
            'typed_json':f"byml_typed/{entry['id']:05d}.json"})
    total = sum(r['occurrences'] for r in records.values())
    recovered = sum(r['occurrences'] for r in records.values() if r['selected'])
    algorithms = collections.Counter()
    for r in records.values():
        if r['selected']: algorithms[r['selected']['algorithm']] += r['occurrences']
    summary = {'native_elf_sha256':hashlib.sha256(im.data).hexdigest(), 'byml_files':len(docs),
        'native_type_names':len(types), 'candidate_strings':len(names), 'hashed_keys':len(records),
        'native_array_element_types':len(array_types),
        'hashed_key_occurrences':total, 'unique_recovered_keys':len(mapping),
        'recovered_key_occurrences':recovered, 'recovered_occurrence_percent':round(100*recovered/total,3),
        'unresolved_keys':len(records)-len(mapping), 'unresolved_key_occurrences':total-recovered,
        'recovered_occurrences_by_algorithm':dict(algorithms),
        'external_save_dictionary':{'verified_murmur_entries':save_count,
            'rejected_entries':rejected_save,
            'sha256':hashlib.sha256(save_reference.read_bytes()).hexdigest(),
            'promotion':'External-only candidates stay unresolved; selected names require a native or local-data string.'},
        'lossless_key_roundtrips':roundtrips,
        'native_descriptor_rule':{'formatter':'0x67770 (s32 template; other templates in native_types)',
            'format_string':'0x292423b: %s.%s', 'type_virtual_slot':'0xe8', 'name_virtual_slot':'0x58',
            'array_formatter':'0xd47710 -> 0x29b4d3c: %s[]',
            'typed_array_formatter':'0x10c1740 / 0x9393a0 -> 0x29b9f57: %s[].%s',
            'descriptor_hash':'0x1c87110 -> 0x19ab050: CRC32 IEEE; raw initial 0xffffffff and complement'},
        'scope':'Only primary BYML hashed keys. Numeric identifiers may remain intentionally unnamed. Recovered descriptors are not proof of full behavior.'}
    dump(OUT/'schemas/byml_names.json', {'summary':summary, 'native_types':types,
        'native_array_types':array_types,'keys':records})
    dump(OUT/'schemas/byml_names_summary.json',summary)
    dump(OUT/'byml_resolved/catalogue.json',catalogue)
    dump(OUT/'schemas/byml_names_unresolved.json',sorted(
        [{'hash':h,**r} for h,r in records.items() if not r['selected']],key=lambda r:-r['occurrences']))
    print(json.dumps(summary,indent=2))


if __name__ == '__main__': build()
