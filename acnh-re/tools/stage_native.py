#!/usr/bin/env python3
"""Index Stage actors/includes/transitions and verify native placement math."""
import collections
import hashlib
import json
import math
from pathlib import Path
import random
import re
import sqlite3
import struct

from native_byml_verify import ReaderSandbox
from native_emulator import regs
from reverse_corpus import dump
from acnh_rip.re.immscan import murmur3

ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/'output'


def f32(x):return struct.unpack('<f',struct.pack('<f',x))[0]


def initialize_keys(s):
    # Only the independent SafeString-table store suffix is executed. The
    # preceding unrelated SDK error/network/tick initialization is skipped.
    sp=s.STACK+0x1ff000
    s.uc.mem_write(sp,bytes(32));s.uc.mem_write(sp+0x18,struct.pack('<Q',s.STOP))
    s.uc.reg_write(regs.UC_ARM64_REG_X19,0x35fed70)
    s.integer_call(0xffa3b0)
    keys=[]
    for index in range(40):
        obj=s.integer_call(0xffa690,[index])
        pointer=struct.unpack('<Q',bytes(s.uc.mem_read(obj+8,8)))[0]
        key=s.image.cstring(pointer)
        if not re.fullmatch('[0-9a-f]{1,8}',key):raise ValueError(('native stage key',index,key))
        keys.append({'index':index,'object_va':hex(obj),'string_va':hex(pointer),'hash':key})
    for index in [40,255,0x7fffffff,0x80000000,0xffffffff]:
        if s.integer_call(0xffa690,[index])!=0x35fedb8:raise ValueError('native key fallback changed')
    return keys


def project_vector(image,angle,distance):
    table=image.ptr(0x32d1428)
    fraction=f32((angle&0xffffff)*struct.unpack('<f',image.read(0x29d5c7c,4))[0])
    a,b,c,d=struct.unpack('<4f',image.read(table+((angle>>24)&255)*16,16))
    sine=f32(a+f32(b*fraction));cosine=f32(c+f32(d*fraction))
    return [f32(sine*distance),0.0,f32(cosine*distance)]


def actor_type_registry(s):
    sp=s.STACK+0x1ff000
    s.uc.mem_write(sp,bytes(32));s.uc.mem_write(sp+0x18,struct.pack('<Q',s.STOP))
    s.uc.reg_write(regs.UC_ARM64_REG_X19,0x3347860)
    s.integer_call(0x61ee0)
    hash_table=s.image.ptr(0x32d2718)
    pairs=[struct.unpack('<II',s.image.read(hash_table+i*8,8))for i in range(158)]
    if not all(a[0]<b[0]for a,b in zip(pairs,pairs[1:])):raise ValueError('actor table is not sorted')
    mapping={h:i for h,i in pairs};records=[]
    for index in range(158):
        obj=s.integer_call(0x62870,[index]);ptr=struct.unpack('<Q',bytes(s.uc.mem_read(obj+8,8)))[0]
        name=s.image.cstring(ptr);h=murmur3(name.encode())
        native=s.integer_call(0x628b0,[h])&0xffffffff
        if native!=index or mapping.get(h)!=index:raise ValueError(('actor name/hash/index mismatch',name,index,native))
        records.append({'index':index,'name':name,'murmur_hash_u32':h,
            'name_object_va':hex(obj),'name_string_va':hex(ptr),
            'raw_property_62880':s.integer_call(0x62880,[index])&0xffffffff,
            'raw_property_62890':s.integer_call(0x62890,[index])&0xffffffff})
    return records


def geometry_expected(image,record,include_extra):
    pos=record['90dcd485'];angle=record['6be92e19']
    scale=struct.unpack('<f',image.read(0x29d6388,4))[0]
    angle32=int(f32(f32(angle)*scale))&0xffffffff
    amount=f32(f32(f32(record['57da4c0d'])*0.5)+f32(record.get('17e534ec',0)))
    amount=f32(amount+(f32(record.get('422c21d8',0))if include_extra else 0.0))
    vector=project_vector(image,angle32,amount)
    point=[f32(pos[key]+vector[i])for i,key in enumerate(['2814d70c','dd29f651','3dbac09d'])]
    return point,angle32,record.get('daf58d2f',0)


def value_name_candidates(image,manifest,wanted):
    names=collections.defaultdict(set)
    def add(value,source):
        if isinstance(value,str) and 0<len(value)<=256 and all(c.isprintable()for c in value):
            names[value].add(source)
        elif isinstance(value,dict):
            for v in value.values():add(v,source)
        elif isinstance(value,list):
            for v in value:add(v,source)
    for match in re.finditer(rb'[\x20-\x7e]{2,65536}',image.data):
        value=match.group().decode()
        add(value,'native_string')
        for word in re.findall('[A-Za-z_][A-Za-z0-9_]{1,127}',value):add(word,'native_token')
    for entry in manifest:
        if entry['format']=='BYML':add(Path(entry['source']).stem,'local_source_filename')
    for p in (OUT/'tables_resolved').glob('*.json'):add(json.loads(p.read_text())['rows'],'local_table_value')
    result=collections.defaultdict(list)
    for name,evidence in names.items():
        value=murmur3(name.encode())
        if value in wanted:result[str(value)].append({'name':name,'algorithm':'Murmur3_32_seed0','sources':sorted(evidence)})
    return dict(result)


def build():
    s=ReaderSandbox();keys=initialize_keys(s);registered_types=actor_type_registry(s)
    actor_types={r['murmur_hash_u32']:r for r in registered_types}
    key_index={k['hash']:k['index']for k in keys}
    common=[]
    for index in range(4):
        obj=s.integer_call(0xffa630,[index]);ptr=struct.unpack('<Q',bytes(s.uc.mem_read(obj+8,8)))[0]
        name=s.image.cstring(ptr);h=murmur3(name.encode())
        if s.integer_call(0xffa270,[h])!=index:raise ValueError('native common-stage reverse mapping')
        common.append({'index':index,'name':name,'hash_u32':h,'object_va':hex(obj)})
    manifest=json.loads((OUT/'manifest.json').read_text())['entries']
    stage_entries=[e for e in manifest if e['format']=='BYML'and e['source'].startswith('B_data/Stage/')]
    documents={e['id']:json.loads((OUT/e['decoded']).read_text())['data']['root']for e in stage_entries}
    paths={Path(e['source']).stem:e for e in stage_entries}
    includes={c['hash_u32']:c for c in common};wanted=set();actors=collections.Counter();env=collections.Counter()
    geometry_checks=0;failures=[];catalogue=[];all_actors=all_transitions=0;unregistered=[]
    degree_scale=struct.unpack('<f',s.image.read(0x29d6388,4))[0]
    key_counts=collections.Counter()
    for entry in stage_entries:
        root=documents[entry['id']]
        if not isinstance(root,dict):
            catalogue.append({'source_id':entry['id'],'source':entry['source'],'status':'non-dictionary Stage resource; retained in BYML catalogue'});continue
        source_includes=[]
        for value in root.get('5cee711c',[]):
            selected=includes.get(value);wanted.add(value)
            target=paths.get(selected['name'])if selected else None
            source_includes.append({'hash_u32':value,'native_index':s.integer_call(0xffa270,[value]),
                'name':selected['name']if selected else None,'source_id':target['id']if target else None})
        actor_records=[]
        for i,record in enumerate(root.get('3cbaa541',[])):
            value=record.get('a1ddf1de');parent=record.get('dcfc7603');wanted.add(value);actors[value]+=1
            if parent is not None:wanted.add(parent)
            kind=s.integer_call(0x628b0,[value])&0xffffffff
            if kind==0xffffffff:
                unregistered.append({'source_id':entry['id'],'source':entry['source'],
                    'source_pointer':f'/3cbaa541/{i}','actor_kind_hash':value})
            actor_records.append({'source_pointer':f'/3cbaa541/{i}','actor_kind_hash':value,
                'native_actor_kind_index':kind,'native_actor_kind_name':actor_types.get(value,{}).get('name'),
                'native_registration_status':'registered'if kind!=0xffffffff else'unregistered; 0xfeb390 skips this kind',
                'parent_actor_kind_hash':parent,'position':record.get('90dcd485'),
                'angle_y_degrees':record.get('6be92e19'),'argument_string':record.get('e46fbfe4'),
                'raw_record':record})
        for value in root.get('1d8284c5',[]):wanted.add(value);env[value]+=1
        source_transitions=[]
        volumes=root.get('5cf34787',[])
        if volumes:
            graph=json.loads((OUT/f"byml_typed/{entry['id']:05d}.json").read_text())
            nodes={n['offset']:n for n in graph['nodes']}
            root_node=nodes[graph['root_offset']]
            array_ref=next(x['value']['node']for x in root_node['entries']if x['key']=='5cf34787')
            array=nodes[array_ref];s.load((OUT/entry['raw']['$blob']).read_bytes())
            for i,(record,element)in enumerate(zip(volumes,array['entries'])):
                target=record.get('3350c97d');wanted.add(target)
                result={'source_pointer':f'/5cf34787/{i}','target_stage_hash':target,
                    'raw_record':record,'native_projection_modes':[]}
                for mode in [0,1]:
                    s.at_node(element['node']);point=s.HEAP+0x4000;angle=s.HEAP+0x5000;parameter=s.HEAP+0x6000
                    s.uc.mem_write(point,b'\xcd'*16)
                    ok=s.integer_call(0xfeeeb0,[point,angle,parameter,s.iterator,mode])&1
                    actual=list(struct.unpack('<3f',bytes(s.uc.mem_read(point,12))))
                    actual_angle=struct.unpack('<I',bytes(s.uc.mem_read(angle,4)))[0]
                    actual_parameter=struct.unpack('<I',bytes(s.uc.mem_read(parameter,4)))[0]
                    expected,expected_angle,expected_parameter=geometry_expected(s.image,record,mode)
                    geometry_checks+=1
                    if ok!=1 or struct.pack('<3f',*actual)!=struct.pack('<3f',*expected) or actual_angle!=expected_angle or actual_parameter!=expected_parameter:
                        failures.append({'source_id':entry['id'],'record':i,'mode':mode,'success':ok,
                            'native_point':actual,'expected_point':expected,'native_angle':actual_angle,'expected_angle':expected_angle,
                            'native_parameter':actual_parameter,'expected_parameter':expected_parameter})
                    result['native_projection_modes'].append({'mode_bit0':mode,'point':actual,'angle32':actual_angle,
                        'create_parameter_hash':actual_parameter})
                source_transitions.append(result)
        for key in root:key_counts[key]+=1
        path=f"stage/by_source/{entry['id']:05d}.json"
        dump(OUT/path,{'source_id':entry['id'],'source':entry['source'],'source_sha256':entry['sha256'],
            'raw':entry['raw'],'includes':source_includes,'actors':actor_records,
            'environment_modules':[{'hash_u32':v,'native_index':s.integer_call(0xffa6d0,[v])}for v in root.get('1d8284c5',[])],
            'transitions':source_transitions,
            'parent_contract':'Parent is an actor-kind hash, not a unique instance ID. Multiple actors can share ActorName.',
            'projection_contract':'Output of 0xfeeeb0; interpretation as a particular spawn/exit direction needs caller context.'})
        catalogue.append({'source_id':entry['id'],'source':entry['source'],'json':path,
            'actor_count':len(actor_records),'transition_count':len(source_transitions)})
        all_actors+=len(actor_records);all_transitions+=len(source_transitions)
    # Independent exact f32 transcription of the 256-entry sin/cos interpolation.
    rng=random.Random(0xac100);trig_cases=[]
    for angle in [0,1,0xffffff,0x1000000,0x3fffffff,0x40000000,0x80000000,0xc0000000,0xffffffff,
                  *[rng.getrandbits(32)for _ in range(256)]]:
        distance=f32(rng.uniform(-1024,1024));s.uc.mem_write(s.HEAP+0x5000,struct.pack('<I',angle))
        s.uc.reg_write(regs.UC_ARM64_REG_S0,struct.unpack('<I',struct.pack('<f',distance))[0])
        s.integer_call(0x1cb70,[s.HEAP+0x5000,s.HEAP+0x4000])
        actual=bytes(s.uc.mem_read(s.HEAP+0x4000,12));expected=struct.pack('<3f',*project_vector(s.image,angle,distance))
        trig_cases.append({'angle32':angle,'distance':distance,'native_hex':actual.hex(),'expected_hex':expected.hex()})
        if actual!=expected:failures.append({'kind':'trig','angle':angle,'native':actual.hex(),'expected':expected.hex()})
    labels=value_name_candidates(s.image,manifest,wanted-{None})
    inverse_scenes=collections.defaultdict(list)
    for entry in stage_entries:inverse_scenes[murmur3(Path(entry['source']).stem.encode())].append(entry['id'])
    # Record exact matches separately from logical stage names with no exact raw
    # file; native scene factories can select concrete files using parameters.
    targets={}
    for value in sorted(wanted-{None}):
        targets[str(value)]={'name_candidates':labels.get(str(value),[]),
            'exact_stage_source_ids':inverse_scenes.get(value,[])}
    db=sqlite3.connect(OUT/'index.sqlite');calls=[]
    for pc,owner in db.execute('select pc,owner_va from direct_calls where target_va=?',(0xffa690,)):
        calls.append({'pc':hex(pc),'owner_va':hex(owner)if owner is not None else None})
    db.close()
    for key in keys:key['root_file_occurrences']=key_counts[key['hash']]
    role_evidence=json.loads((ROOT/'tools/knowledge/stage_key_roles.json').read_text())
    for field in role_evidence['fields']:
        if keys[field['native_index']]['hash']!=field['hash']:raise ValueError('native stage role registry mismatch')
    result={'native_elf_sha256':hashlib.sha256(s.image.data).hexdigest(),
        'stage_resources':len(stage_entries),'actor_occurrences':all_actors,'unique_actor_kind_hashes':len(actors),
        'registered_actor_types':len(registered_types),'unregistered_actor_occurrences':len(unregistered),
        'unregistered_actor_hashes':len({x['actor_kind_hash']for x in unregistered}),
        'transition_occurrences':all_transitions,'native_projection_checks':geometry_checks,
        'native_trig_checks':len(trig_cases),'mismatches':failures,'degree_to_angle32_f32':degree_scale,
        'initializer':{'full_entry':'0xffa310','executed_suffix':'0xffa3b0',
            'scope':'Independent SafeString table stores only; unrelated SDK prefix skipped; X19 base and saved stack return explicitly supplied.'},
        'substituted_dependency':'SDK strcmp through ReaderSandbox; native projection, trig and enum lookups are original instructions.',
        'projection_formula':'angle32 = trunc(f32(f32(degrees) * 11930465.0)) mod 2^32; distance = f32(f32(depth*0.5 + key_17e534ec) + (mode_bit0 ? key_422c21d8 : 0)); point = f32(Pos + native_interpolated_direction(angle32)*distance). Optional addends default to 0.',
        'projection_extra_field_observed':False,
        'trig_contract':'256 entries of [sin, deltaSin, cos, deltaCos]; upper angle byte selects entry, low 24 bits give f32 interpolation fraction. X=sin*distance, Y=0, Z=cos*distance.',
        'key_registry':keys,'common_types':common,'role_evidence':role_evidence,
        'actor_registry_initializer':{'full_entry':'0x61e40','executed_suffix':'0x61ee0',
            'name_getter':'0x62870','hash_to_index':'0x628b0','sorted_hash_table':'0x29d775c',
            'scope':'Independent SafeString stores; skipped unrelated SDK prefix; all 158 labels validated through native lookup.'},
        'registry_call_sites':calls,'environment_hash_counts':dict(env),
        'original_field_name_limit':'Opaque properties retain hashes and functional roles; names are not fabricated from CRC preimages.'}
    dump(OUT/'stage/native_summary.json',result)
    dump(OUT/'stage/actor_type_registry.json',{'native_elf_sha256':result['native_elf_sha256'],
        'entries':registered_types,'unregistered_scene_actor_occurrences':unregistered})
    dump(OUT/'stage/hash_targets.json',targets);dump(OUT/'stage/catalogue.json',catalogue)
    dump(OUT/'stage/trig_verification.json',{'cases':trig_cases,'mismatches':[f for f in failures if f.get('kind')=='trig']})
    print(json.dumps({k:v for k,v in result.items()if k not in ['key_registry','common_types','role_evidence','registry_call_sites','mismatches']},indent=2))
    if failures:raise ValueError(('native stage verification mismatch',failures[:5]))


if __name__=='__main__':build()
