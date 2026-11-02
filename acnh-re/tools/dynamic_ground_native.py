"""Execute the runtime ground-map sector lookup with original coordinate helpers."""
from pathlib import Path
import hashlib
import itertools
import json
import math
import random
import struct
from native_emulator import Sandbox

ROOT=Path(__file__).resolve().parent.parent
def f(x):return struct.unpack('<f',struct.pack('<f',x))[0]
def index(v):return math.trunc(f(f(math.trunc(v))/5.))-int(v<0)

def main():
    s=Sandbox();u=s.uc;m=s.HEAP;p=m+0x10000
    width,height=3,2;groups={'map_sector_lookup':0,'null_map':0,'all_attribute_byte_values':0}
    guard=b'\xa5'*16;examples=[]
    def expected(wx,wz,ox,oz):
        x=f(wx-f(f(ox)*5.));z=f(wz-f(f(oz)*5.));ix,iz=index(x),index(z)
        if ix<0 or iz<0 or ix>=width or iz>=height:return 7
        dx=f(x-f(f(ix)*5.));dz=f(z-f(f(iz)*5.))
        a=f(dz-dx);b=f(f(dx+dz)-5.)
        lane=(2 if b>=0 else 1)if a>=0 else(3 if b>=0 else 0)
        return 10+4*(ix+width*iz)+lane
    local=[0.,.01,.5,1.25,2.5,3.75,4.5,4.99,5.]
    for ox,oz in [(0,0),(-2,3),(4,-1)]:
        raw=bytearray(20+width*height*52)
        struct.pack_into('<IIIii',raw,0,0,width,height,ox,oz)
        for i in range(width*height):raw[20+52*i+48:20+52*i+52]=bytes(10+4*i+j for j in range(4))
        u.mem_write(m,guard+raw+guard)
        for ix,iz,a,b in itertools.product(range(width),range(height),local,local):
            wx=f(f((ix+ox)*5.)+a);wz=f(f((iz+oz)*5.)+b)
            position=struct.pack('<3f',wx,12345.,wz);u.mem_write(p,position)
            actual=s.call(0x18adf0,(m+16,p),limit=500)
            assert actual==expected(wx,wz,ox,oz),(ox,oz,wx,wz,actual,expected(wx,wz,ox,oz))
            assert bytes(u.mem_read(m,len(raw)+32))==guard+raw+guard
            assert bytes(u.mem_read(p,12))==position
            groups['map_sector_lookup']+=1
        for wx,wz in [(ox*5.-.1,oz*5.),((ox+width)*5.,oz*5.),(ox*5.,(oz+height)*5.)]:
            u.mem_write(p,struct.pack('<3f',wx,0,wz))
            assert s.call(0x18adf0,(m+16,p),limit=500)==7
            groups.setdefault('outside_map',0);groups['outside_map']+=1
    for x,z in [(0.,0.),(-5.,5.),(999.,-999.)]:
        u.mem_write(p,struct.pack('<3f',x,0,z));assert s.call(0x18adf0,(0,p),limit=500)==7
        groups['null_map']+=1
    raw=bytearray(20+52);struct.pack_into('<IIIii',raw,0,0,1,1,0,0)
    for lane,(x,z) in enumerate([(2.5,1.25),(1.25,2.5),(2.5,3.75),(3.75,2.5)]):
        for value in range(256):
            raw[20+48:20+52]=bytes([99]*4);raw[20+48+lane]=value
            u.mem_write(m,bytes(raw));u.mem_write(p,struct.pack('<3f',x,0,z))
            assert s.call(0x18adf0,(m,p),limit=500)==value
            groups['all_attribute_byte_values']+=1
    result={'groups':groups,'cases':sum(groups.values()),'mismatches':[],
      'helper':'0x18adf0','native_callees':['0x52b420','0x52b430','0x52b280','0x52b4c0','0x52b3e0'],
      'header':{'width':4,'height':8,'origin_x_s32':12,'origin_z_s32':16,'record_start':20,'record_stride':52},
      'sector_rule':'u = localX - indexX*5; v = localZ - indexZ*5; a=f32(v-u); b=f32(f32(u+v)-5). a>=0,b>=0 -> lane2; a>=0,b<0 -> lane1; a<0,b>=0 -> lane3; both negative -> lane0.',
      'sector_bytes':[48,49,50,51],'invalid_or_null_map_result':7,'byte_semantics':'All u8 values returned unchanged, including 7; inheritance is handled by consumers.',
      'dependencies_stubbed':[], 'scope':'Complete ground-map lookup and its original coordinate helpers, with reconstructed map records. World/object selection and active global override dispatch are not executed.',
      'limits':['Map loader and selection by active room/object context remain unverified.','Map record geometry before the last four bytes is not decoded by this helper.','No complete collision response or movement simulation.'],
      'elf_sha256':hashlib.sha256(s.image.data).hexdigest(),
      'helper_sha256':hashlib.sha256(s.image.read(0x18adf0,0x144)).hexdigest()}
    (ROOT/'output/mechanics/dynamic_ground_native.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'groups':groups,'cases':sum(groups.values()),'mismatches':0}),flush=True)

if __name__=='__main__':main()
