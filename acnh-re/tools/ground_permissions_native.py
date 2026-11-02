"""Execute complete ground permission readers with reconstructed lookup/cache."""
from pathlib import Path
import hashlib
import json
import re
import struct
from native_emulator import Sandbox

ROOT=Path(__file__).resolve().parent.parent
def main():
    out=ROOT/'output';s=Sandbox();u=s.uc
    table=json.loads((out/'tables_resolved/ColGroundAttributeParam.json').read_text())
    entry=json.loads((out/'manifest.json').read_text())['entries'][table['source_id']]
    decoded=json.loads((out/entry['decoded']).read_text())['data']
    raw=(out/table['raw']['$blob']).read_bytes()
    obj=s.HEAP;array=obj+0x1000;base=obj+0x4000
    def d(p,v):u.mem_write(p,struct.pack('<I',v&0xffffffff))
    def q(p,v):u.mem_write(p,struct.pack('<Q',v))
    u.mem_write(base,raw)
    d(obj+8+0x1b0,table['row_count']);d(obj+8+0x1c0,table['row_count']);q(obj+8+0x1b8,array)
    for i in range(table['row_count']):q(array+8*i,base+decoded['data_start']+i*table['row_size'])
    flag=s.image.ptr(0x32d7210);cache=s.image.ptr(0x32d7220)
    u.mem_write(flag,b'\x01')
    fields={'WaterCheck':0x18ef20,'CanBury':0x18f1c0,'PlayerNoEntry':0x18f5b0,'NpcNoEntry':0x18f700}
    groups={'source_rows':0,'all_byte_values':0,'out_of_range_indices':0,'missing_field_cache':0}
    details=[]
    for name,va in fields.items():
        index=next(i for i,c in enumerate(table['columns']) if c['name']==name)
        col=table['columns'][index]
        instructions=s.image.disasm(va,0x100)
        loads=[i for i in instructions if i.mnemonic=='ldrsw' and re.fullmatch(r'x8, \[x24(?:, #0x[0-9a-f]+)?\]',i.op_str)]
        assert len(loads)==1,(name,[(i.mnemonic,i.op_str) for i in instructions])
        match=re.search(r'#(0x[0-9a-f]+)',loads[0].op_str);offset=int(match[1],16) if match else 0
        d(cache+offset,col['offset'])
        u.mem_write(base,raw)
        for row,values in enumerate(table['rows']):
            actual=s.call(va,(obj,row),limit=500)
            assert actual==int(bool(values[index])),(name,row,actual,values[index])
            assert bytes(u.mem_read(base,len(raw)))==raw
            groups['source_rows']+=1
        field_address=base+decoded['data_start']+col['offset']
        for value in range(256):
            u.mem_write(field_address,bytes([value]))
            assert s.call(va,(obj,0),limit=500)==int(value!=0)
            groups['all_byte_values']+=1
        u.mem_write(base,raw)
        for invalid in [table['row_count'],table['row_count']+1,0x7fffffff,0xffffffff]:
            assert s.call(va,(obj,invalid),limit=500)==0
            groups['out_of_range_indices']+=1
        d(cache+offset,-2)
        assert s.call(va,(obj,0),limit=500)==0
        groups['missing_field_cache']+=1
        d(cache+offset,col['offset'])
        details.append({'field':name,'reader':hex(va),'offset':col['offset'],
             'hash':col['hash'],'metadata_cache_cell_offset':offset,
             'cache_load_pc':hex(loads[0].address),
             'reader_sha256_first_256_bytes':hashlib.sha256(s.image.read(va,256)).hexdigest(),
             'enabled_rows':[i for i,row in enumerate(table['rows']) if row[index]]})
    result={'groups':groups,'cases':sum(groups.values()),'mismatches':[],'fields':details,
       'elf_sha256':hashlib.sha256(s.image.data).hexdigest(),'source_sha256':hashlib.sha256(raw).hexdigest(),
       'lookup_helper':'0x18f070','lookup_rows':table['row_count'],
       'rule':'Byte zero -> false; every nonzero byte -> true; out-of-range lookup or cached missing field -> false.',
       'dependencies_stubbed':[],
       'scope':'Complete four readers and their actual dense lookup helper. Raw BCSV rows preserved; row-pointer arrays and cached metadata offsets reconstructed. Table constructors, metadata discovery and caller gameplay eligibility not executed.'}
    (out/'mechanics/ground_permissions_native.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'groups':groups,'cases':sum(groups.values()),'mismatches':0}),flush=True)

if __name__=='__main__':main()
