#!/usr/bin/env python3
"""Extract 8-byte item values and verify isolated original AArch64 helpers."""
import collections
import hashlib
import json
from pathlib import Path
import random
import struct
import zlib

from native_emulator import Sandbox
from reverse_corpus import dump

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT/'output'
ITEM_KEY = '5bc12308'


def decode_word(word):
    if not isinstance(word, int) or not 0 <= word < 1 << 64:
        raise ValueError('item word outside u64')
    raw = word.to_bytes(8, 'little')
    return {'decimal':str(word), 'hex_u64':f'{word:016x}', 'bytes_le':raw.hex(),
        'stored_item_id':int.from_bytes(raw[:2],'little'), 'system_param':raw[2],
        'additional_param':raw[3], 'free_param_u32':int.from_bytes(raw[4:],'little'),
        'free_param_s32':int.from_bytes(raw[4:],'little',signed=True)}


def lookup_id(word, papers):
    r = decode_word(word); item = r['stored_item_id']; flags = r['additional_param']
    mode = flags & 3
    if not mode or item == 0x16a1: return item
    if mode == 3: return 0x1225
    if mode == 2: return 0x1180
    return papers[(flags >> 2) & 15]


def table_index(name):
    table = json.loads((OUT/f'tables_resolved/{name}.json').read_text())
    columns = [c['name'] for c in table['columns']]
    at = columns.index('UniqueID')
    keep = ['UniqueID','Label','ItemName','ItemKind','ResName','ModelName','Kind','ItemSize']
    return {row[at]:{'table':name,'source_id':table['source_id'],'row_index':i,
        'fields':{k:row[columns.index(k)] for k in keep if k in columns}}
        for i,row in enumerate(table['rows'])}


def verify(s, words, papers, descriptors):
    counts = collections.Counter(); failures = []
    p, dest, argument = s.HEAP, s.HEAP+0x100, s.HEAP+0x200
    def check(group, got, expected, context):
        counts[group] += 1
        if got != expected: failures.append({'group':group,'context':context,'native':got,'expected':expected})
    # Exhaust all eight AdditionalParam bits across IDs including special cases;
    # also exercise every unique word actually present in the primary corpus.
    synthetic = [item | (flags << 24) for item in [0,1234,0x16a1,0x3100,0xfffd,0xfffe,0xffff,60000]
                 for flags in range(256)]
    for word in sorted(set(words) | set(synthetic)):
        s.uc.mem_write(p,word.to_bytes(8,'little'))
        got = s.call(0xf58a90,[p]) & 0xffffffff
        check('lookup_id',got,lookup_id(word,papers),f'{word:016x}')
    for index in [*range(256),0x7fffffff,0x80000000,0xffffffff]:
        expected = papers[index if index < 16 else 0]
        check('paper_index',s.call(0xab4420,[index]) & 0xffffffff,expected,index)
    random_words = random.Random(0xac100).randbytes(8*128)
    basis = [0,(1<<64)-1,*[1<<i for i in range(64)],
             *[int.from_bytes(random_words[i:i+8],'little') for i in range(0,len(random_words),8)]]
    for word in basis:
        raw = word.to_bytes(8,'little'); src = b'\xa7'*16+raw+b'\xa7'*16
        for fn in [0xf589b0,0xf589e0]:
            s.uc.mem_write(p,src); s.uc.mem_write(dest,b'\xcd'*40)
            s.call(fn,[dest+16,p+16])
            check('copy_8_bytes',bytes(s.uc.mem_read(dest,40)).hex(),
                  (b'\xcd'*16+raw+b'\xcd'*16).hex(),[hex(fn),f'{word:016x}'])
            check('copy_source_unchanged',bytes(s.uc.mem_read(p,40)).hex(),src.hex(),hex(fn))
    for item in [0,1234,0x16a1,0xfffd,0xfffe,0xffff]:
        for x in [0,1,127,255]:
            for y in [0,1,127,255]:
                s.uc.mem_write(p,struct.pack('<HHHBB',item,0x235a,0x1678,x,y))
                before=b'\xcd'*32; s.uc.mem_write(dest,before)
                got=s.call(0xf59f70,[p,dest]) & 0xffffffff
                expected=bytearray(before)
                if item == 0xfffd:struct.pack_into('<II',expected,8,x,y)
                check('extension_result',got,int(item==0xfffd),[item,x,y])
                check('extension_write_bounds',bytes(s.uc.mem_read(dest,32)).hex(),expected.hex(),[item,x,y])
    for word in basis:
        s.uc.mem_write(p,b'\xcd'*16+word.to_bytes(8,'little')+b'\xcd'*16)
        s.call(0x1a6560,[p+16])
        check('empty_reset',bytes(s.uc.mem_read(p,40)).hex(),
              (b'\xcd'*16+(0xfffe).to_bytes(8,'little')+b'\xcd'*16).hex(),f'{word:016x}')
    for descriptor in descriptors:
        raw=descriptor.encode();s.uc.mem_write(p,raw+b'\0')
        check('descriptor_crc32',s.call(0x19ab050,[p]) & 0xffffffff,zlib.crc32(raw),descriptor)
    result = {'native_elf_sha256':hashlib.sha256(s.image.data).hexdigest(),
        'comparisons':sum(counts.values()),'groups':dict(counts),'mismatches':failures,
        'dependencies_stubbed':[], 'execution_scope':'isolated original helpers; no game/OS execution',
        'addresses':{'copy':['0xf589b0','0xf589e0'],'empty_reset':'0x1a6560',
            'lookup_id':'0xf58a90','paper_index':'0xab4420','paper_table':'0x29f859c',
            'extension_coordinates':'0xf59f70','crc32':'0x19ab050'}}
    dump(OUT/'items/native_verification.json',result)
    if failures:raise ValueError(('item native verification failed',failures[:5]))
    return result


def build():
    names = json.loads((OUT/'schemas/byml_names.json').read_text())['keys']
    def readable(key):
        r=names.get(key,{}).get('selected');return r['descriptor'] if r else key
    s=Sandbox();papers=list(struct.unpack('<16I',s.image.read(0x29f859c,64)))
    item_table,field_table=table_index('ItemParam'),table_index('FgMainParam')
    occurrences=collections.Counter();contexts=collections.Counter();coordinates=collections.Counter()
    catalogue=[];all_occurrences=0
    for entry in json.loads((OUT/'manifest.json').read_text())['entries']:
        if entry['format'] != 'BYML':continue
        root=json.loads((OUT/entry['decoded']).read_text())['data']['root'];rows=[]
        def walk(value,path='',ancestors=()):
            if isinstance(value,dict):
                for k,v in value.items():
                    keypath=path+'/'+k
                    if k==ITEM_KEY:
                        record=decode_word(v);occurrences[v]+=1
                        context=path.rsplit('/',1)[-1];contexts[readable(context)]+=1
                        row={'source_pointer':keypath,'word_hex':record['hex_u64'],
                             'container_hash':context,'container_name':readable(context)}
                        for parent in reversed(ancestors):
                            coords={readable(h):x for h,x in parent.items() if
                                names.get(h,{}).get('selected',{} ) and names[h]['selected']['name'] in
                                ['mUnitX','mUnitZ','mLayer','mHalfUnitX','mHalfUnitZ','mItemLayerID']}
                            if coords:
                                row['coordinates']=coords;coordinates['placement_records']+=1
                                break
                        rows.append(row)
                    walk(v,keypath,(*ancestors,value))
            elif isinstance(value,list):
                for i,v in enumerate(value):walk(v,path+'/'+str(i),ancestors)
        walk(root)
        if rows:
            path=f"items/by_source/{entry['id']:05d}.json"
            dump(OUT/path,{'source_id':entry['id'],'source':entry['source'],'source_sha256':entry['sha256'],
                'raw':entry['raw'],'word_dictionary':'../words.json','coordinate_contract':
                'Native member names/values; no world-unit or Godot coordinate conversion is inferred.',
                'items':rows})
            catalogue.append({'source_id':entry['id'],'source':entry['source'],'json':path,'count':len(rows)})
            all_occurrences+=len(rows)
    words=[];joins=collections.Counter();systems=collections.Counter();additional=collections.Counter()
    for word,count in sorted(occurrences.items()):
        r=decode_word(word);item=r['stored_item_id'];r['occurrences']=count
        r['native_lookup_item_id']=lookup_id(word,papers)
        match=item_table.get(item) or field_table.get(item)
        r['definition']=match
        status='empty' if item==0xfffe else 'extension' if item==0xfffd else match['table'] if match else 'unresolved'
        r['definition_status']=status;joins[status]+=count
        systems[r['system_param']]+=count;additional[r['additional_param']]+=count
        if item==0xfffd:r['extension_coordinates']={'x':(word>>48)&255,'y':(word>>56)&255}
        words.append(r)
    verification=verify(s,occurrences,papers,[r['selected']['descriptor'] for r in names.values()
        if r['selected'] and r['selected']['algorithm']=='CRC32'])
    summary={'native_elf_sha256':verification['native_elf_sha256'],'source_files_with_items':len(catalogue),
        'item_word_occurrences':all_occurrences,'unique_item_words':len(words),
        'definition_occurrences':dict(joins),'container_occurrences':dict(contexts),
        'placements_with_named_coordinates':coordinates['placement_records'],
        'system_param_byte_occurrences':dict(systems),'additional_param_byte_occurrences':dict(additional),
        'native_comparisons':verification['comparisons'],'native_mismatches':len(verification['mismatches']),
        'layout':'<u16 stored ID, u8 SystemParam, u8 AdditionalParam, u32 FreeParam>',
        'wrapping_version_limit':'Native 1.0.0 helper: MessageBottle 0x16a1 bypass; no later Egg/Festive special cases inferred.',
        'free_param_contract':'Raw signed/unsigned views only; union interpretation depends on item kind.',
        'system_param_semantics':'NHSE rotation/buried/dropped interpretations remain external hypotheses until locally verified.'}
    dump(OUT/'items/words.json',{'summary':summary,'paper_item_ids':papers,'words':words})
    dump(OUT/'items/catalogue.json',catalogue);dump(OUT/'items/summary.json',summary)
    print(json.dumps(summary,indent=2))


if __name__=='__main__':build()
