#!/usr/bin/env python3
"""Verify native byte access and audit public CRC descriptors against local data."""
import collections
import hashlib
import json
from pathlib import Path
import sqlite3
import struct
import zlib

from native_emulator import Sandbox,regs
from reverse_corpus import dump

ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/'output'


def build():
    knowledge=json.loads((ROOT/'tools/knowledge/bcsv_native_types.json').read_text())
    s=Sandbox();db=sqlite3.connect(OUT/'index.sqlite');manifest=json.loads((OUT/'manifest.json').read_text())['entries']
    cases=0;failures=[];views=[];raw_rows=0
    for field in knowledge['fields']:
        pc=int(field['value_load_pc'],16);ins=s.image.disasm(pc,4)[0]
        expected_operands=f"{field['register']}, [{field['base_register']}]"
        if ins.mnemonic!=field['instruction']or ins.op_str!=expected_operands:
            raise ValueError(('native byte instruction changed',field,ins.mnemonic,ins.op_str))
        base_reg=getattr(regs,'UC_ARM64_REG_'+field['base_register'].upper())
        result_reg=getattr(regs,'UC_ARM64_REG_X'+field['register'][1:])
        for value in range(256):
            s.uc.mem_write(s.HEAP,bytes([value]));s.uc.reg_write(base_reg,s.HEAP)
            s.uc.emu_start(pc,pc+4,count=1)
            actual=s.uc.reg_read(result_reg)&0xffffffff
            if field['type']=='s8'and actual&0x80000000:actual-=1<<32
            expected=value-256 if field['type']=='s8'and value>=128 else value
            cases+=1
            if actual!=expected:failures.append({'table':field['table'],'input':value,'native':actual,'expected':expected})
        table=json.loads((OUT/f"tables_resolved/{field['table']}.json").read_text())
        col_index=next(i for i,c in enumerate(table['columns'])if c['hash']==field['hash'])
        col=table['columns'][col_index];entry=manifest[table['source_id']]
        original=json.loads((OUT/entry['decoded']).read_text())['data'];raw=(OUT/table['raw']['$blob']).read_bytes()
        changed=0
        for index,row in enumerate(table['rows']):
            offset=original['data_start']+index*table['row_size']+col['offset']
            value=raw[offset];expected=value-256 if field['type']=='s8'and value>=128 else value
            raw_rows+=1
            if row[col_index]!=expected:failures.append({'table':field['table'],'row':index,'decoded':row[col_index],'expected':expected})
            if original['rows'][index][col_index]!=row[col_index]:changed+=1
        native_refs=db.execute('select pc,owner_va from hash_refs where hash=? and owner_va=?',
            (int(field['hash'],16),int(field['reader'],16))).fetchall()
        if not native_refs:raise ValueError(('native hash reader missing',field['hash']))
        views.append({**field,'column_offset':col['offset'],'column_span':col['width'],'native_value_bytes':1,
            'source_id':table['source_id'],'source':table['source'],'raw':table['raw'],
            'rows_checked':table['row_count'],'values_changed_from_provisional_view':changed,
            'load_raw_hex':ins.bytes.hex(),'hash_instruction_candidates':
                [{'pc':hex(p),'owner':hex(o)}for p,o in native_refs],
            'original_descriptor':None,'storage_status':'native access verified; original name/declared descriptor remains unresolved'})
    # Execute the exact signed-selector/fallback block, stopping before its call
    # into the animation system. Its enclosing function applies this block only
    # when the third argument is 2 or 3.
    fallback_cases=0
    for value in range(256):
        for fallback in [0,17,255,0x7fffffff]:
            s.uc.mem_write(s.HEAP,bytes([value]));s.uc.reg_write(regs.UC_ARM64_REG_X8,s.HEAP)
            s.uc.reg_write(regs.UC_ARM64_REG_X19,s.HEAP+0x1000)
            s.uc.reg_write(regs.UC_ARM64_REG_X20,2)
            s.uc.reg_write(regs.UC_ARM64_REG_X21,fallback)
            s.uc.emu_start(0x7d16c4,0x7d16ec,count=20)
            actual=s.uc.reg_read(regs.UC_ARM64_REG_X1)&0xffffffff
            expected=value if value<128 else fallback
            fallback_cases+=1
            if s.uc.reg_read(regs.UC_ARM64_REG_PC)!=0x7d16ec or actual!=expected:
                failures.append({'kind':'animation_selector','input':value,'fallback':fallback,'native':actual,'expected':expected})
    public=json.loads((ROOT/'tools/knowledge/public_bcsv_candidates.json').read_text());audit=[]
    facts={f['hash']:f for f in public['candidates']}
    scalar_width={'s8':1,'u8':1,'bool':1,'s16':2,'u16':2,'int16':2,'s32':4,'u32':4,'f32':4}
    for p in (OUT/'tables_resolved').glob('*.json'):
        table=json.loads(p.read_text())
        for col in table['columns']:
            candidate=facts.get(col['hash'])
            if not candidate:continue
            descriptor=candidate['descriptor']
            if zlib.crc32(descriptor.encode())!=int(col['hash'],16):raise ValueError('public descriptor CRC mismatch')
            typ='enum_crc32'if descriptor.endswith('.hshCstringRef')else descriptor.rsplit(' ',1)[-1]
            width=4 if typ=='enum_crc32'else int(typ[6:])if typ.startswith('string')and typ[6:].isdigit()else scalar_width.get(typ)
            fits=width is not None and width<=col['width']
            audit.append({'table':p.stem,'source_id':table['source_id'],'column_hash':col['hash'],
                'column_span':col['width'],'local_read_view':col['type'],'candidate':candidate,
                'candidate_declared_bytes':width,'fits_local_span':fits,
                'status':'rejected_width_exceeds_column_span'if not fits else'candidate_only; native role/original name not established',
                'promoted':False})
    db.close()
    result={'native_elf_sha256':hashlib.sha256(s.image.data).hexdigest(),
        'native_byte_view_count':len(views),'byte_load_comparisons':cases,
        'animation_fallback_comparisons':fallback_cases,'raw_rows_checked':raw_rows,
        'mismatches':failures,'dependencies_stubbed':[],
        'scope':'Original byte-load instructions and one bounded animation-selector basic block; full owning functions are not claimed emulated.',
        'animation_block':{'begin':'0x7d16c4','stop_before_call':'0x7d16ec',
            'rule':'When this block is reached: signed byte >=0 selects that value; any negative byte selects the caller fallback.',
            'enclosing_guard':'third function argument is 2 or 3'},'fields':views}
    dump(OUT/'schemas/native_read_views.json',result)
    dump(OUT/'schemas/public_descriptor_audit.json',{'source':public['source'],
        'matching_columns':len(audit),'width_rejections':sum(not a['fits_local_span']for a in audit),
        'promoted':0,'columns':audit,
        'conclusion':'CRC32 matches can have impossible local widths. Width-compatible matches still do not establish an original field name.'})
    print(json.dumps({k:v for k,v in result.items()if k not in ['fields','mismatches']},indent=2))
    if failures:raise ValueError(('native BCSV read view mismatches',failures[:5]))


if __name__=='__main__':build()
