#!/usr/bin/env python3
"""Candidate names from local strings and an attributed public AAMP name list.

A hash equality is deliberately not represented as proof of field semantics.
"""
import collections
import hashlib
import json
from pathlib import Path
import re
import zlib

from reverse_corpus import dump
from acnh_rip.re.immscan import murmur3
from resolve_schemas import read_reference

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT/'output'
SRC = Path(json.loads((OUT/'manifest.json').read_text())['source_root'])


def build():
    observed = json.loads((OUT/'hash_names.json').read_text())
    enum_misses = json.loads((OUT/'schemas/enum_unresolved.json').read_text())
    wanted = {int(h,16) for h in observed} | {int(r['hash'],16) for r in enum_misses}
    names = collections.defaultdict(set)
    def add(name, evidence):
        if isinstance(name,str) and len(name) <= 256:
            names[name].add(evidence)
    for match in re.finditer(rb'[\x20-\x7e]{1,256}', (SRC/'A_logic/main.elf').read_bytes()):
        s = match.group().decode('ascii')
        add(s,'main.elf:string')
        for word in re.findall(r'[A-Za-z_][A-Za-z0-9_]{1,127}',s):
            add(word,'main.elf:token')
    for n in range(2048):
        add(str(n),'generated_decimal_candidate')
    def collect(x):
        if isinstance(x,dict):
            for k,v in x.items():
                if not re.fullmatch(r'(?:h_)?[0-9a-f]{8}',k):
                    add(k,'decoded_json_key')
                collect(v)
        elif isinstance(x,list):
            for v in x: collect(v)
        elif isinstance(x,str):
            add(x,'decoded_json_string')
    for p in (OUT/'decoded').glob('*.json'):
        doc = json.loads(p.read_text())
        if doc['format'] == 'BYML': collect(doc['data']['root'])
    _, enums, descriptors = read_reference()
    for descriptor in descriptors.values():
        add(descriptor,'CylindricalEarth:descriptor')
        add(descriptor.split(' ')[0].removesuffix('.hshCstringRef'),'CylindricalEarth:field_name')
    for values in enums.values():
        for en,jp in values:
            add(en,'CylindricalEarth:enum'); add(jp,'CylindricalEarth:enum')
    external = ROOT/'tools/external/roead/botw_hashed_names.txt'
    for line in external.read_text().splitlines():
        add(line,'roead:botw_hashed_names.txt')
    found = collections.defaultdict(list)
    for s, evidence in names.items():
        for algorithm, h in [('CRC32',zlib.crc32(s.encode())),('Murmur3_32_seed0',murmur3(s.encode()))]:
            if h in wanted:
                found[f'{h:08x}'].append({'name': s,'algorithm': algorithm,'sources': sorted(evidence)})
    result = {h:{'occurrences': r['occurrences'], 'candidates': found.get(h,[]),
                 'status': 'candidate_only; do not replace original keys automatically'} for h,r in observed.items()}
    dump(OUT/'hash_names_expanded.json',result)
    enum = {h:found.get(h,[]) for h in sorted({r['hash'] for r in enum_misses})}
    dump(OUT/'schemas/enum_label_candidates.json',enum)
    stats = {'candidate_strings': len(names), 'distinct_observed_keys': len(observed),
        'key_occurrences': sum(r['occurrences'] for r in observed.values()),
        'keys_with_candidates': sum(bool(r['candidates']) for r in result.values()),
        'occurrences_with_candidates': sum(r['occurrences'] for r in result.values() if r['candidates']),
        'warning': 'Numeric key IDs are included; unidentified keys are not necessarily unknown field names.',
        'external_name_list': {'url':'https://github.com/NiceneNerd/roead/blob/2afd32710a186fcc2ec096a6b46aa768d0e76e01/data/botw_hashed_names.txt',
            'sha256':hashlib.sha256(external.read_bytes()).hexdigest(), 'license':'GPL-3.0-or-later','author':'Caleb Smith'}}
    dump(OUT/'schemas/hash_candidates_summary.json',stats)
    print(json.dumps(stats,indent=2))
    print('enum candidates',json.dumps(enum,ensure_ascii=False)[:5000])


if __name__ == '__main__':
    build()
