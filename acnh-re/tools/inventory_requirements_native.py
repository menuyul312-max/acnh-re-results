"""Verify the complete warm-cache material requirement reader, not consumption."""
from pathlib import Path
from collections import Counter
import hashlib
import itertools
import json
import struct
import zlib
from native_emulator import Sandbox

ROOT=Path(__file__).resolve().parent.parent

def install_item_tables(s):
    u=s.uc;out=ROOT/'output';region=0x51000000;u.mem_map(region,0x1000000)
    def q(p,v):u.mem_write(p,struct.pack('<Q',v))
    def d(p,v):u.mem_write(p,struct.pack('<I',v))
    def load(name,base):
        t=json.loads((out/f'tables_resolved/{name}.json').read_text())
        e=json.loads((out/'manifest.json').read_text())['entries'][t['source_id']]
        header=json.loads((out/e['decoded']).read_text())['data']
        raw=(out/t['raw']['$blob']).read_bytes();u.mem_write(base,raw)
        return t,header,raw
    ip,ih,iraw=load('ItemParam',region);kind,kh,kraw=load('ItemKind',region+0x500000)
    im=region+0x600000;km=region+0x601000;definition=region+0x610000
    dense=region+0x700000;kind_array=region+0x720000;enum=region+0x730000
    ic={c['name']:i for i,c in enumerate(ip['columns'])};kc={c['name']:i for i,c in enumerate(kind['columns'])}
    min_id=min(r[ic['UniqueID']]for r in ip['rows']);max_id=max(r[ic['UniqueID']]for r in ip['rows'])
    d(im+0x1d8,max_id-min_id+1);q(im+0x1e0,dense);u.mem_write(im+0x1f8,struct.pack('<H',min_id))
    literal_start=s.image.data.find(b'Ftr,RoomWall,RoomFloor,Rug,RugMyDesign,')
    assert literal_start>=0
    native_labels=s.image.data[literal_start:s.image.data.index(b'\0',literal_start)].decode().rstrip(',').split(',')
    assert len(native_labels)==120
    source_by_label={row[kc['Label']]:i for i,row in enumerate(kind['rows'])}
    assert set(native_labels)==set(source_by_label)
    kind_ids={zlib.crc32(label.encode()):i for i,label in enumerate(native_labels)}
    for i,row in enumerate(ip['rows']):
        q(dense+8*(row[ic['UniqueID']]-min_id),region+ih['data_start']+i*ip['row_size'])
        h=int(row[ic['ItemKind']]['hash'],16)
        assert h in kind_ids or h==0
        u.mem_write(enum+i*2,struct.pack('<H',kind_ids.get(h,0)))
    count=len(native_labels)
    d(km+0x1b0,count);d(km+0x1c0,count);q(km+0x1b8,kind_array)
    for i,label in enumerate(native_labels):q(kind_array+8*i,region+0x500000+kh['data_start']+source_by_label[label]*kind['row_size'])
    q(definition+0x57e58,im)
    q(s.image.ptr(0x32d3b88),definition);q(s.image.ptr(0x32f3f40),im);q(s.image.ptr(0x32f3f50),km)
    cache=s.image.ptr(0x32f0a60);d(cache,len(ip['rows']));q(cache+8,enum)
    u.mem_write(s.image.ptr(0x32f0928),b'\x01')
    for i,col in enumerate(ip['columns']):d(s.image.ptr(0x32f0920)+4*i,col['offset'])
    u.mem_write(s.image.ptr(0x32f0418),b'\x01')
    for i,col in enumerate(kind['columns']):d(s.image.ptr(0x32f0420)+4*i,col['offset'])
    return {'item_table':ip,'item_cols':ic,'kind_table':kind,'kind_cols':kc,
            'item_raw_sha256':hashlib.sha256(iraw).hexdigest(),'kind_raw_sha256':hashlib.sha256(kraw).hexdigest(),
            'native_kind_labels':native_labels}


def main():
    s=Sandbox();u=s.uc;tables=install_item_tables(s);ip=tables['item_table'];ic=tables['item_cols']
    kind=tables['kind_table'];kc=tables['kind_cols']
    kind_count={zlib.crc32(row[kc['Label']].encode()):row[kc['SaveCountMaxNum']]for row in kind['rows']}
    recipe_table=json.loads((ROOT/'output/tables_resolved/RecipeCraftParam.json').read_text())
    material_columns=[i for i,c in enumerate(recipe_table['columns'])if c['name'].startswith('Material')]
    materials=Counter(row[i]for row in recipe_table['rows']for i in material_columns if row[i]!=65534)
    eligible={row[ic['UniqueID']]for row in ip['rows']if row[ic['RemakeID']]==-1 and row[ic['UniqueID']]<15000 and kind_count.get(int(row[ic['ItemKind']]['hash'],16),0)==0}
    items=[uid for uid,n in materials.most_common()if uid in eligible][:6]
    assert items
    cache=s.HEAP+0x40000;recipe=s.HEAP+0x10000;handle=s.HEAP+0x20000
    u.mem_write(handle,b'\xff'+b'\0'*7)
    u.mem_write(cache+8,b'\x01')
    groups={'warm_cache_requirement':0};samples=[]
    def set16(p,v):u.mem_write(p,struct.pack('<H',v&65535))
    for item,slot,(a,b,c),needed,include,initial in itertools.product(items,[0,2,5],
        [(0,0,0),(2,3,0),(2,3,4),(20,10,50),(65535,1,0)], [0,1,5,6,9,31],[0,1],[0,1]):
        u.mem_write(recipe,b'\0'*0xb0);u.mem_write(recipe+0x25,bytes([initial]))
        entry=recipe+0x2c+20*slot
        u.mem_write(entry,struct.pack('<Q',item));set16(entry+8,needed)
        set16(cache+0x308+item*2,a);set16(cache+0x7b30+item*2,b);set16(cache+0x23020+item*2,c)
        try:s.call(0xee0be0,(cache,recipe,handle,slot,include),limit=20000)
        except Exception as error:
            from native_emulator import regs
            raise RuntimeError(f'Native failure at PC {u.reg_read(regs.UC_ARM64_REG_PC):#x}, item={item}, {error}')from error
        if needed==0:
            expected_flag=initial
        else:
            total=(a+b)&65535;total=(total+c)&65535 if include else total
            expected_flag=initial if total>=needed else 0
            actual=struct.unpack('<HHHH',u.mem_read(entry+10,8))
            assert actual[:3]==(c if include else 0,a,b),(item,slot,a,b,c,needed,include,actual)
        assert u.mem_read(recipe+0x25,1)[0]==expected_flag,(item,slot,a,b,c,needed,include)
        assert struct.unpack('<H',u.mem_read(cache+0x308+item*2,2))[0]==a
        assert struct.unpack('<H',u.mem_read(cache+0x7b30+item*2,2))[0]==b
        assert struct.unpack('<H',u.mem_read(cache+0x23020+item*2,2))[0]==c
        groups['warm_cache_requirement']+=1
        if len(samples)<8:samples.append({'item':item,'slot':slot,'A':a,'B':b,'C':c,'required':needed,'include_C':include,'sufficient_flag':expected_flag})
    groups['sequential_material_checks']=0
    for fail_slot in [-1]+list(range(len(items))):
        u.mem_write(recipe,b'\0'*0xb0);u.mem_write(recipe+0x25,b'\x01')
        for slot,item in enumerate(items):
            entry=recipe+0x2c+20*slot;u.mem_write(entry,struct.pack('<Q',item));set16(entry+8,1)
            amount=0 if slot==fail_slot else 1
            set16(cache+0x308+item*2,amount);set16(cache+0x7b30+item*2,0);set16(cache+0x23020+item*2,0)
            s.call(0xee0be0,(cache,recipe,handle,slot,0),limit=20000)
            assert u.mem_read(recipe+0x25,1)[0]==int(fail_slot<0 or slot<fail_slot)
            assert struct.unpack('<H',u.mem_read(cache+0x308+item*2,2))[0]==amount
        groups['sequential_material_checks']+=1
    result={'groups':groups,'cases':sum(groups.values()),'mismatches':[],
      'helper':'0xee0be0','source_item_ids':items,'samples':samples,
      'rules':['Need zero returns without changing the sufficient flag.','For selected normal items, A+B is narrowed to u16.','Optional C is included only when bit0 of the option is set.','Insufficient material clears record+0x25; sufficient material leaves that flag unchanged.'],
      'dependencies_stubbed':[],
      'scope':'Complete requirement reader on initialized counter-cache path with reconstructed item definitions, kind enums and invalid player handle. No source inventory loading or item removal executed.',
      'limits':['Selected normal items with RemakeID=-1 and source SaveCountMaxNum=0.','Wrapped/remade items, cold cache and alternate save-count branch unverified.','Counter groups A/B/C are not assigned gameplay storage names before validating their producers.'],
      'native_item_kind_order':tables['native_kind_labels'],
      'item_kind_index_contract':'ItemParam.ItemKind CRC matches ItemKind.Label in native enum order. ItemKind.UniqueID is not the enum ordinal.',
      'recipe_source_duplicate_material_rows':sum(len([row[i]for i in material_columns if row[i]!=65534])!=len({row[i]for i in material_columns if row[i]!=65534})for row in recipe_table['rows']),
      'source_tables':{name:{'json':f'tables_resolved/{name}.json','source_id':table['source_id'],'raw':table['raw']}for name,table in [('ItemParam',ip),('ItemKind',kind),('RecipeCraftParam',recipe_table)]},
      'elf_sha256':hashlib.sha256(s.image.data).hexdigest(),
      'table_sha256':{'ItemParam':tables['item_raw_sha256'],'ItemKind':tables['kind_raw_sha256']}}
    (ROOT/'output/mechanics/inventory_requirements_native.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'groups':groups,'cases':sum(groups.values()),'mismatches':0}),flush=True)

if __name__=='__main__':main()
