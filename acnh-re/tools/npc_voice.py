#!/usr/bin/env python3
"""Map six unnamed NPC columns to native voice-configuration byte positions.

The bounded block starts after NPC selection and enum initialization. It runs
original metadata/hash/cache readers, using complete raw BCSV files, and stops
before audio-device construction. No dependency implementation is replaced.
"""
import collections
import hashlib
import json
from pathlib import Path
import struct

from native_byml_verify import ReaderSandbox
from native_emulator import regs
from reverse_corpus import dump

ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/'output'
HASHES=['21c5bbd6','42f255d5','e52f0037']
DEFAULTS=[5,4,1]
BINDINGS=[
    dict(table='NmlNpcParam',begin=0x160b144,guard=0x32d3790,cache=0x32d3798,slots=[0x6c,0x68,0x64]),
    dict(table='SpNpcParam',begin=0x160b584,guard=0x32d3778,cache=0x32d3780,slots=[0x30,0x2c,0x54])]


def build():
    s=ReaderSandbox();manifest=json.loads((OUT/'manifest.json').read_text())['entries']
    groups=collections.Counter();failures=[];tables=[];synthetic=[]
    config=s.HEAP+0x80000;sp=s.STACK+0x1ff000;stop=0x160ba54
    def check(kind,actual,expected,context):
        groups[kind]+=1
        if actual!=expected:
            failures.append(dict(kind=kind,actual=actual,expected=expected,**context))
            if len(failures)>10:raise ValueError(('systematic native NPC mismatch',failures[:3]))
    def run(begin,row):
        s.uc.mem_write(config+0x810,b'\xcd'*49)
        for reg,value in [('X19',config),('X21',row),('X22',config+0x83c),('X25',config+0x810),('SP',sp)]:
            s.uc.reg_write(getattr(regs,'UC_ARM64_REG_'+reg),value)
        s.uc.mem_write(sp,struct.pack('<QQ',config+0x810,config+0x83c))
        s.uc.emu_start(begin,stop,count=20000)
        if s.uc.reg_read(regs.UC_ARM64_REG_PC)!=stop:raise ValueError('bounded NPC block did not reach audio-construction boundary')
        return bytes(s.uc.mem_read(config+0x810,49))
    def expected_config(values):
        result=bytearray(b'\xcd'*49);result[44:47]=bytes(values);return bytes(result).hex()
    for binding in BINDINGS:
        name=binding['table'];table=json.loads((OUT/f'tables_resolved/{name}.json').read_text())
        source=manifest[table['source_id']];decoded=json.loads((OUT/source['decoded']).read_text())['data']
        raw=(OUT/table['raw']['$blob']).read_bytes();start=decoded['data_start'];size=table['row_size']
        columns=[next((i,c)for i,c in enumerate(table['columns'])if c['hash']==h)for h in HASHES]
        guard=s.image.ptr(binding['guard']);cache=s.image.ptr(binding['cache'])
        s.uc.mem_write(guard,b'\0');s.uc.mem_write(s.raw_base,raw);rows=[]
        for row_index,values in enumerate(table['rows']):
            row=s.raw_base+start+row_index*size
            actual=run(binding['begin'],row);expected=[values[i]for i,c in columns]
            check('source_row_config_and_guards',actual.hex(),expected_config(expected),dict(table=name,row=row_index))
            rows.append(dict(row_index=row_index,config_bytes_44_45_46=expected,
                source_byte_offsets=[start+row_index*size+c['offset']for i,c in columns]))
        check('source_buffer_unchanged',bytes(s.uc.mem_read(s.raw_base,len(raw))).hex(),raw.hex(),dict(table=name))
        for h,slot,(i,col) in zip(HASHES,binding['slots'],columns):
            offset=struct.unpack('<i',bytes(s.uc.mem_read(cache+slot,4)))[0]
            check('native_hash_to_column_offset',offset,col['offset'],dict(table=name,hash=h))
        # Every possible unsigned byte reaches each of the three output bytes.
        # Input is an in-memory copy of row 0; original disk sources stay intact.
        for byte in range(256):
            values=[byte,byte^0xa5,255-byte];changed=bytearray(raw)
            for value,(i,col) in zip(values,columns):changed[start+col['offset']]=value
            s.uc.mem_write(s.raw_base,bytes(changed))
            actual=run(binding['begin'],s.raw_base+start)
            check('synthetic_all_byte_values',actual.hex(),expected_config(values),dict(table=name,input=values))
        # Missing fields exercise actual uncached metadata search and defaults.
        # All eight presence combinations are compared, independently per table.
        metadata=0x1c if raw[0xa]else 0xc
        for present_mask in range(8):
            changed=bytearray(raw);values=[]
            for j,(h,(i,col),fallback) in enumerate(zip(HASHES,columns,DEFAULTS)):
                present=bool(present_mask&(1<<j));values.append(table['rows'][0][i]if present else fallback)
                if not present:
                    matches=[offset for offset in range(metadata,metadata+len(table['columns'])*8,8)
                        if struct.unpack_from('<I',changed,offset)[0]==int(h,16)]
                    if len(matches)!=1:raise ValueError('native metadata entry not unique')
                    struct.pack_into('<I',changed,matches[0],int(h,16)^0xffffffff)
            s.uc.mem_write(s.raw_base,bytes(changed));s.uc.mem_write(guard,b'\0')
            actual=run(binding['begin'],s.raw_base+start)
            check('synthetic_missing_fields',actual.hex(),expected_config(values),dict(table=name,present_mask=present_mask))
            synthetic.append(dict(table=name,present_mask=present_mask,config_bytes_44_45_46=list(actual[44:47])))
        fields=[dict(hash=h,original_name=None,column_offset=col['offset'],native_cache_slot=hex(slot),
            config_offset=44+j,owner_offset=hex(0x83c+j),native_read_type='u8',fallback=DEFAULTS[j],
            functional_alias=f'voice_configuration_byte_{44+j}',
            meaning_limit='Exact byte transport to voice configuration; acoustic meaning (pitch/timbre/speed etc.) is not established.')
            for j,(h,slot,(i,col))in enumerate(zip(HASHES,binding['slots'],columns))]
        tables.append(dict(table=name,source_id=table['source_id'],source=table['source'],source_sha256=source['sha256'],
            raw=table['raw'],row_count=table['row_count'],begin=hex(binding['begin']),stop=hex(stop),
            initialization_guard_pointer=hex(binding['guard']),initialization_guard_va=hex(guard),
            cache_pointer=hex(binding['cache']),cache_va=hex(cache),fields=fields,rows=rows))
    if s.strcmp_calls:raise ValueError('unexpected substituted dependency during native NPC block')
    # Prove downstream context from the local ELF and supplied block code rather
    # than assigning a guessed auditory meaning to these three bytes.
    labels={hex(va):s.image.cstring(va)for va in [0x29946e1,0x29987fd,0x29a2b8d]}
    result=dict(native_elf_sha256=hashlib.sha256(s.image.data).hexdigest(),owner_function='0x160aff0',
        scope='Bounded three-byte configuration block after NPC/row selection and enum initialization, before audio-device creation; not whole-function emulation.',
        source_rows_checked=sum(t['row_count']for t in tables),table_count=len(tables),column_bindings=6,
        comparisons=sum(groups.values()),groups=dict(groups),mismatches=failures,dependencies_stubbed=[],
        raw_metadata_readers=['0x1665e50','0x1665e60','0x1665e80'],
        voice_configuration_base_owner_offset='0x810',audio_consumer='0x1043b10',
        evidence_strings=labels,tables=tables,missing_field_cases=synthetic,
        original_names_recovered=0,semantic_status='Native transport binding verified; original names and acoustic roles remain unresolved.')
    dump(OUT/'npc/voice_configuration_native.json',result)
    print(json.dumps({k:v for k,v in result.items()if k not in ['tables','missing_field_cases','mismatches']},indent=2))
    if failures:raise ValueError(('native NPC voice binding mismatch',failures[:5]))


if __name__=='__main__':build()
