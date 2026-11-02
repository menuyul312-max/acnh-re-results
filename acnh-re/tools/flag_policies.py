#!/usr/bin/env python3
"""Specify the unnamed row selector used by native flag-default reset paths."""
import collections
import hashlib
import json
from pathlib import Path
import struct

from native_emulator import Sandbox
from reverse_corpus import dump

ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/'output'


def eligible(policy,counter,auxiliary):
    if policy==1:return counter!=0
    if policy==2:return counter!=0 or auxiliary!=0
    if policy==3:return True
    if policy==4:return counter>0
    return False


def build():
    sandbox=Sandbox();context=sandbox.HEAP;cases=0;failures=[]
    counters=[-(1<<63),-1,0,1,(1<<63)-1]
    for policy in range(256):
        for counter in counters:
            for auxiliary in range(256) if policy<5 else [0,255]:
                raw=bytearray(32);struct.pack_into('<q',raw,0,counter);raw[0x1a]=auxiliary
                sandbox.uc.mem_write(context,bytes(raw))
                result=sandbox.call(0xf54530,[context,policy])&1
                expected=int(eligible(policy,counter,auxiliary));cases+=1
                if result!=expected:failures.append({'policy':policy,'counter':str(counter),
                    'auxiliary_byte':auxiliary,'native':result,'expected':expected})
    tables=[];rows=[];policy_counts=collections.Counter()
    for path in (OUT/'tables_resolved').glob('EventFlags*.json'):
        table=json.loads(path.read_text());columns=table['columns']
        index=next((i for i,c in enumerate(columns)if c['hash']=='5140e4b4'),None)
        if index is None:continue
        fields={c['name']:i for i,c in enumerate(columns)}
        selected=[]
        for row_index,row in enumerate(table['rows']):
            policy=row[index];policy_counts[policy]+=1
            selected.append({'row_index':row_index,'raw_policy':policy,
                'native_effective_policy':policy if 0<=policy<5 else 0,
                **{k:row[fields[k]]for k in ['UniqueID','Key','Name','DefaultValue']if k in fields}})
        tables.append({'table':path.stem,'source_id':table['source_id'],'column_hash':'5140e4b4',
            'column_offset':columns[index]['offset'],'raw':table['raw'],'rows':selected})
    result={'native_elf_sha256':hashlib.sha256(sandbox.image.data).hexdigest(),
        'predicate_va':'0xf54530','column_hash':'5140e4b4','original_field_name':None,
        'functional_alias':'default_reset_predicate_selector',
        'context_layout':{'0x00':'signed 64-bit counter','0x1a':'auxiliary byte'},
        'context_meaning_status':'The predicate is fully specified; higher-level meanings of the two context members are not yet proven.',
        'rules':{'0':'false','1':'counter != 0','2':'counter != 0 or auxiliary_byte != 0',
            '3':'true','4':'counter > 0','other':'false'},
        'callers':{'0xf43220':'Checks row policy <5, invokes predicate, then reads DefaultValue (0x4c24f1cf)',
            '0xf46200':'Additional reader of the same policy hash',
            '0xf482c0':'Additional reader of the same policy hash',
            '0xf491f0':'Additional reader of the same policy hash',
            '0xf4a1b0':'Additional reader of the same policy hash',
            '0xf4bcd0':'Additional reader of the same policy hash'},
        'table_association_status':'Tables are associated by the shared column hash and observed 0..4 domain; individual caller-to-table bindings are not claimed.',
        'comparisons':cases,'mismatches':failures,'dependencies_stubbed':[],
        'table_count':len(tables),'row_count':sum(len(t['rows'])for t in tables),
        'observed_policy_counts':dict(policy_counts),'tables':tables}
    dump(OUT/'flags/reset_policy_native.json',result)
    print(json.dumps({k:v for k,v in result.items()if k not in ['tables','mismatches']},indent=2))
    if failures:raise ValueError(('flag predicate mismatch',failures[:5]))


if __name__=='__main__':build()
