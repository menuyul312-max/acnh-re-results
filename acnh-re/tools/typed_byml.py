#!/usr/bin/env python3
"""Independently validate BYML and retain numeric tags, offsets and 64-bit bits."""
import collections
import hashlib
import json
from pathlib import Path
import struct

from reverse_corpus import clean, dump

ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/'output'
TYPES={0xa0:'string',0xa1:'binary',0xc0:'array',0xc1:'dict',0xd0:'bool',0xd1:'s32',
       0xd2:'f32',0xd3:'u32',0xd4:'s64',0xd5:'u64',0xd6:'f64',0xff:'null'}


def decode(raw):
    endian='<' if raw[:2]==b'YB' else '>' if raw[:2]==b'BY' else None
    if endian is None:raise ValueError('bad BYML magic')
    def need(off,n):
        if off<0 or n<0 or off+n>len(raw):raise ValueError(('BYML bounds',off,n,len(raw)))
    def unpack(fmt,off):
        need(off,struct.calcsize(endian+fmt));return struct.unpack_from(endian+fmt,raw,off)[0]
    def count(off):
        need(off,4);return int.from_bytes(raw[off+1:off+4],'little' if endian=='<' else 'big')
    def strings(off):
        if not off:return []
        need(off,4)
        if raw[off]!=0xc2:raise ValueError('expected BYML string table')
        n=count(off);need(off+4,(n+1)*4)
        offsets=[unpack('I',off+4+i*4) for i in range(n+1)]
        result=[]
        for start,end in zip(offsets,offsets[1:]):
            if start>end:raise ValueError('inverted string span')
            need(off+start,end-start)
            data=raw[off+start:off+end]
            if b'\0' not in data:raise ValueError('missing string terminator')
            result.append(data.split(b'\0',1)[0].decode('utf-8'))
        return result
    version=unpack('H',2);keyoff=unpack('I',4);stroff=unpack('I',8);rootoff=unpack('I',12)
    keys,values=strings(keyoff),strings(stroff)
    nodes={};flat_cache={};active=set();stats=collections.Counter();large=[];duplicate=[]
    def scalar(tag,off):
        if tag not in TYPES:raise ValueError(('unknown BYML tag',tag,off))
        word=unpack('I',off);name=TYPES[tag];stats[name]+=1
        item={'type':name,'word_offset':off,'raw_word_hex':raw[off:off+4].hex()}
        if tag in (0xc0,0xc1):
            node,flat=container(word)
            return {'type':name,'word_offset':off,'node':word},flat
        if tag==0xa0:
            if word>=len(values):raise ValueError('string index out of bounds')
            value=values[word];item.update(string_index=word,value=value)
        elif tag==0xa1:
            n=unpack('I',word);need(word+4,n);data=raw[word+4:word+4+n]
            digest=hashlib.sha256(data).hexdigest()
            value={'$blob':f'blobs/{digest}.bin','size':n,'sha256':digest}
            if not (OUT/value['$blob']).is_file():raise ValueError('BYML binary absent from raw blob store')
            item.update(data_offset=word+4,value=value)
        elif tag==0xd0:value=word!=0;item['value']=value
        elif tag in (0xd1,0xd2,0xd3):
            value=unpack({0xd1:'i',0xd2:'f',0xd3:'I'}[tag],off);item['value']=value
        elif tag in (0xd4,0xd5,0xd6):
            value=unpack({0xd4:'q',0xd5:'Q',0xd6:'d'}[tag],word)
            item.update(data_offset=word,raw_value_hex=raw[word:word+8].hex())
            if tag==0xd6:item['value']=value
            else:
                item['decimal']=str(value)
                if abs(value)>2**53-1:large.append({'offset':off,'type':name,'decimal':str(value)})
        elif tag==0xff:value=None;item['value']=None
        return item,value
    def container(off):
        if off in active:raise ValueError('cyclic BYML graph')
        if off in nodes:return nodes[off],flat_cache[off]
        need(off,4);tag=raw[off];n=count(off)
        if tag not in (0xc0,0xc1):raise ValueError('unsupported BYML container')
        active.add(off);stats['containers']+=1
        node={'offset':off,'type':TYPES[tag],'count':n,'entries':[]}
        if tag==0xc1:
            need(off+4,n*8);flat={}
            for i in range(n):
                p=off+4+i*8
                k=int.from_bytes(raw[p:p+3],'little' if endian=='<' else 'big')
                if k>=len(keys):raise ValueError('BYML key index out of bounds')
                key=keys[k]
                val,value=scalar(raw[p+3],p+4)
                node['entries'].append({'key':key,'key_index':k,'value':val})
                if key in flat:duplicate.append({'offset':off,'key':key})
                flat[key]=value
        else:
            need(off+4,n);base=off+4+((n+3)&~3);need(base,n*4);flat=[]
            for i in range(n):
                val,value=scalar(raw[off+4+i],base+i*4);node['entries'].append(val);flat.append(value)
        active.remove(off);nodes[off]=node;flat_cache[off]=flat
        return node,flat
    if rootoff:_,flat=container(rootoff)
    else:flat=None
    return {'version':version,'endianness':'little' if endian=='<' else 'big','root_offset':rootoff,
        'key_table':{'offset':keyoff,'strings':keys},'value_string_table':{'offset':stroff,'strings':values},
        'nodes':list(nodes.values()),'tag_counts':dict(stats),'integers_outside_json_safe_range':large,
        'duplicate_dictionary_keys':duplicate},flat


def build():
    catalogue=[];counts=collections.Counter();large=duplicates=0
    for entry in json.loads((OUT/'manifest.json').read_text())['entries']:
        if entry['format']!='BYML':continue
        raw=(OUT/entry['raw']['$blob']).read_bytes()
        graph,flat=decode(raw)
        old=json.loads((OUT/entry['decoded']).read_text())['data']['root']
        if clean(flat)!=old:raise ValueError(('independent BYML mismatch',entry['source']))
        large+=len(graph['integers_outside_json_safe_range']);duplicates+=len(graph['duplicate_dictionary_keys'])
        counts.update(graph['tag_counts'])
        path=f"byml_typed/{entry['id']:05d}.json"
        dump(OUT/path,{'source_id':entry['id'],'source':entry['source'],'raw':entry['raw'],**graph})
        catalogue.append({'source_id':entry['id'],'source':entry['source'],'json':path})
    summary={'files':len(catalogue),'independent_tree_matches':len(catalogue),'tag_counts':dict(counts),
        'integers_outside_json_safe_range':large,'duplicate_dictionary_keys':duplicates,
        'integer_contract':'s64/u64 use decimal strings plus exact raw hex; do not route through JSON double'}
    dump(OUT/'byml_typed/catalogue.json',catalogue);dump(OUT/'byml_typed/summary.json',summary)
    print(json.dumps(summary,indent=2))


if __name__=='__main__':build()
