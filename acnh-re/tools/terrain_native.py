"""Execute coordinate conversion, terrain lookup and complete ground aggregators.

Runtime buffers and initialized metadata are reconstructed; actual code and
callees remain unchanged. Dynamic object-ground overrides are gated off by the
original native context check with its manager explicitly null.
"""
from pathlib import Path
import itertools
import hashlib
import json
import random
import struct
import math
from native_emulator import Sandbox
from native_emulator import regs
from unicorn import UC_HOOK_CODE

ROOT=Path(__file__).resolve().parent.parent
def f(v):return struct.unpack('<f',struct.pack('<f',v))[0]
def main():
    s=Sandbox();u=s.uc;out=ROOT/'output'
    world=s.HEAP+0x10000;grid=s.HEAP+0x20000;base=s.HEAP+0x30000
    overlay=s.HEAP+0x40000;point=s.HEAP+0x50000;dest=s.HEAP+0x60000
    def d(p,v):u.mem_write(p,struct.pack('<I',v&0xffffffff))
    def q(p,v):u.mem_write(p,struct.pack('<Q',v))
    def coord(x,z):u.mem_write(point,b'\xa5'*8+struct.pack('<ii',x,z))
    groups={};r=random.Random(0x181cd0)
    bounds=[-2147483648,-16777217,-1,0,1,16777217,2147483647]
    coords=list(itertools.product(bounds,repeat=2))+[(r.randint(-2147483648,2147483647),r.randint(-2147483648,2147483647))for _ in range(512)]
    for x,z in coords:
        coord(x,z);before=bytes(u.mem_read(point,16));guard=b'\xa5'*32;u.mem_write(dest,guard)
        s.call(0x52b5a0,(point,dest+8))
        expected=guard[:8]+struct.pack('<f',f(f(f(x)*5.)+2.5))+guard[12:16]+struct.pack('<f',f(f(f(z)*5.)+2.5))+guard[20:]
        assert bytes(u.mem_read(dest,32))==expected
        assert bytes(u.mem_read(point,16))==before
    s.call(0x52b5a0,(0,0))
    groups['coordinate_converter_and_guards']=len(coords)+1
    # The reverse constructor is not simply floor(world/5): inspect negative edges.
    edges=[float(i) for i in range(-25,26,5)]+[-0.0,-0.1,0.1]
    world_cases=[(x,z) for x in edges for z in edges]+[(f(r.uniform(-1000000,1000000)),f(r.uniform(-1000000,1000000)))for _ in range(256)]
    groups['world_to_index_constructor']=0;negative_edges=[]
    for x,z in world_cases:
        x,z=f(x),f(z)
        raw_position=struct.pack('<3f',x,12345.,z);u.mem_write(point,raw_position)
        u.mem_write(dest,b'\xa5'*32)
        s.call(0x52b280,(dest+8,point))
        expected=[math.trunc(f(f(math.trunc(v))/5.))-int(v<0.)for v in [x,z]]
        assert list(struct.unpack('<ii',u.mem_read(dest+16,8)))==expected
        assert bytes(u.mem_read(dest,8))==b'\xa5'*8 and bytes(u.mem_read(dest+24,8))==b'\xa5'*8
        assert bytes(u.mem_read(point,12))==raw_position
        groups['world_to_index_constructor']+=1
        if z==0. and x in [-10.,-5.,0.,5.,10.]:negative_edges.append({'x':x,'index':expected[0]})
    groups['coordinate_roundtrip']=0
    for _ in range(128):
        x,z=r.randint(-1000,1000),r.randint(-1000,1000);coord(x,z)
        s.call(0x52b5a0,(point,dest))
        s.call(0x52b280,(dest+32,dest))
        assert struct.unpack('<ii',u.mem_read(dest+40,8))==(x,z)
        groups['coordinate_roundtrip']+=1
    d(grid+0x30,3);d(grid+0x34,2);d(grid+0x40,6);q(grid+0x48,base)
    base_values=[];overlay_values=[]
    for i in range(6):
        vals=[i,i+10,i+20,i+30];base_values.append(vals)
        u.mem_write(base+0x34*i,b'\xa5'*0x30+bytes(vals))
    groups['base_overlay_lookup']=0
    for mask,count,present in itertools.product(range(16),[0,3,6],[False,True]):
        for i in range(6):
            vals=[7 if mask&(1<<j) else i+40+j for j in range(4)]
            u.mem_write(overlay+0x34*i,b'\x5a'*0x30+bytes(vals))
        d(grid+0x50,count);q(grid+0x58,overlay if present else 0)
        for i in range(6):
            coord(i%3,i//3);u.mem_write(dest,b'\xa5'*32)
            result=s.call(0x181cd0,(grid,point,dest,dest+8,dest+16,dest+24))
            expected=[base_values[i][j] if not present or i>=count or mask&(1<<j) else i+40+j for j in range(4)]
            assert result==1
            for j in range(4):
                assert bytes(u.mem_read(dest+j*8,8))==struct.pack('<I',expected[j])+b'\xa5'*4
            groups['base_overlay_lookup']+=1
    groups['out_of_bounds_no_output_write']=0
    for x,z in [(-1,0),(0,-1),(3,0),(0,2),(-2147483648,0),(2147483647,0)]:
        coord(x,z);u.mem_write(dest,b'\xa5'*32)
        assert s.call(0x181cd0,(grid,point,dest,dest+8,dest+16,dest+24))==0
        assert bytes(u.mem_read(dest,32))==b'\xa5'*32
        groups['out_of_bounds_no_output_write']+=1
    # Install the actual source ground rows and previously verified cache layout.
    table=json.loads((out/'tables_resolved/ColGroundAttributeParam.json').read_text())
    entry=json.loads((out/'manifest.json').read_text())['entries'][table['source_id']]
    original=json.loads((out/entry['decoded']).read_text())['data']
    raw=(out/table['raw']['$blob']).read_bytes()
    manager=s.HEAP+0x100000;array=manager+0x1000;raw_base=manager+0x4000
    u.mem_write(raw_base,raw)
    d(manager+8+0x1b0,len(table['rows']));d(manager+8+0x1c0,len(table['rows']));q(manager+8+0x1b8,array)
    for i in range(len(table['rows'])):q(array+8*i,raw_base+original['data_start']+i*table['row_size'])
    cache=s.image.ptr(0x32d7220);u.mem_write(s.image.ptr(0x32d7210),b'\x01')
    fields=json.loads((out/'mechanics/ground_permissions_native.json').read_text())['fields']
    for row in fields:d(cache+row['metadata_cache_cell_offset'],row['offset'])
    q(s.image.ptr(0x32d3d88),manager)
    q(s.image.ptr(0x32d0de8),world);q(world+0xa0,grid)
    q(s.image.ptr(0x32d71a0),0)
    d(grid+0x30,1);d(grid+0x34,1);d(grid+0x40,1);d(grid+0x50,0);q(grid+0x58,0)
    sample_positions=[]
    def observe(uc,pc,size,data):
        if pc==0x18b570:
            ptr=uc.reg_read(regs.UC_ARM64_REG_X0)
            xyz=struct.unpack('<3f',uc.mem_read(ptr,12))
            sample_positions.append([xyz[0],xyz[2]])
    hook=u.hook_add(UC_HOOK_CODE,observe)
    try:
        coord(0,0)
        assert s.call(0x162dc0,(world+0x28,point,dest,dest+8,dest+16,dest+24),limit=10000)==1
    finally:u.hook_del(hook)
    assert sample_positions==[[2.5,1.25],[1.25,2.5],[2.5,3.75],[3.75,2.5]]
    groups['four_point_native_call_trace']=1
    functions=[(0x187420,'WaterCheck','all'),(0x1874f0,'PlayerNoEntry','any'),(0x187610,'WaterCheck','exactly_two')]
    cols={c['name']:i for i,c in enumerate(table['columns']) if c.get('name')}
    examples=[];groups['complete_four_ground_aggregators']=0
    for va,name,rule in functions:
        false_row=next(i for i,row in enumerate(table['rows'])if row[cols[name]]==0)
        true_row=next(i for i,row in enumerate(table['rows'])if row[cols[name]]!=0)
        for mask in range(16):
            flags=[bool(mask&(1<<i)) for i in range(4)]
            ids=[true_row if b else false_row for b in flags]
            u.mem_write(base+0x30,bytes(ids));coord(0,0)
            expected=all(flags) if rule=='all' else any(flags) if rule=='any' else sum(flags)==2
            assert s.call(va,(point,),limit=10000)==int(expected),(hex(va),mask)
            assert bytes(u.mem_read(raw_base,len(raw)))==raw
            groups['complete_four_ground_aggregators']+=1
        examples.append({'function':hex(va),'field':name,'rule':rule,'true_source_row':true_row,'false_source_row':false_row})
    groups['complete_aggregator_invalid_coordinates']=0
    for va,name,rule in functions:
        for x,z in [(-1,0),(1,0),(0,-1),(0,1)]:
            coord(x,z);assert s.call(va,(point,),limit=10000)==0
            groups['complete_aggregator_invalid_coordinates']+=1
    groups['complete_aggregator_missing_world']=0
    for missing in ['world','grid']:
        q(s.image.ptr(0x32d0de8),0 if missing=='world' else world)
        q(world+0xa0,0 if missing=='grid' else grid)
        for va,name,rule in functions:
            coord(0,0);assert s.call(va,(point,),limit=10000)==0
            groups['complete_aggregator_missing_world']+=1
    evidence=[{'va':hex(a),'bytes':n,'sha256':hashlib.sha256(s.image.read(a,n)).hexdigest()}for a,n in
              [(0x52b5a0,0x38),(0x52b280,0x80),(0x181cd0,0xfc),(0x162dc0,0x120),(0x18b570,0x70),(0x880740,0x50)]]
    result={'groups':groups,'cases':sum(groups.values()),'mismatches':[],
      'coordinate_rule':'XZ = f32(f32(f32(s32 index)*5.0)+2.5); Y and other bytes are preserved; null output is a no-op.',
      'reverse_coordinate_rule':'For bounded finite world v: trunc(f32(f32(trunc(v))/5.0)) - int(v<0). This differs from floor(v/5) at negative exact multiples.',
      'reverse_coordinate_negative_edges':negative_edges,
      'grid_contract':{'record_stride':52,'attribute_offsets':[48,49,50,51],'index':'x + width*z',
          'overlay_sentinel':7,'rule':'Each overlay byte independently replaces base unless it equals 7; missing/out-of-count overlay uses base.',
          'bounds':'Negative coordinates or x>=width/z>=height return false without writing output.'},
      'aggregators':examples,'dependencies_stubbed':[],
      'native_sample_xz_positions_at_index_0_0':sample_positions,
      'native_chain':['0x187420/0x1874f0/0x187610','0x162dc0','0x181cd0','0x52b5a0','0x18b570','0x880740','ground readers + 0x18f070'],
      'reconstructed_state':['Runtime grid/base/overlay arrays','Ground row-pointer lookup and metadata cache','World/ground singleton pointers','Context manager at *ptr(0x32d71a0) is null: original 0x880740 returns false, original 0x18b570 returns sentinel 7.'],
      'limits':['Active dynamic object-ground overrides are not covered.','Grid 52-byte runtime records are not the 14-byte terrain preset; conversion between them remains unproven.',
          'Coordinate units relative to Godot and all gameplay coordinate classes remain unproven.',
          'These aggregators do not represent every rule for walking, burying or water interactions.'],
      'elf_sha256':hashlib.sha256(s.image.data).hexdigest(),'evidence':evidence}
    (out/'mechanics/terrain_native.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'groups':groups,'cases':sum(groups.values()),'mismatches':0}),flush=True)

if __name__=='__main__':main()
