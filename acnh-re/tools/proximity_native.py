"""Verify XZ proximity and a masked caller fragment with original callees."""
from pathlib import Path
import hashlib
import itertools
import json
import math
import random
import sqlite3
import struct
from native_emulator import Sandbox,regs
from unicorn import UC_HOOK_CODE

ROOT=Path(__file__).resolve().parent.parent
def f(v):return struct.unpack('<f',struct.pack('<f',v))[0]
def bits(v):return struct.unpack('<I',struct.pack('<f',v))[0]
def adjacent(v,delta):return struct.unpack('<f',struct.pack('<I',bits(v)+delta))[0]

def main():
    s=Sandbox();u=s.uc;p=s.HEAP;q=p+0x100;c=p+0x1000;inner=p+0x2000
    actor=p+0x3000;transform=p+0x4000;sp=s.STACK+0x18000
    scale=struct.unpack('<f',s.image.read(0x29d5fb8,4))[0]
    def expected(a,b,r0,r1):
        dx=f(a[0]-b[0]);dz=f(a[2]-b[2])
        distance=f(math.sqrt(f(f(dx*dx)+f(dz*dz))))
        radius=f(f(r1*scale)+r0)
        return int(distance<radius)
    rng=random.Random(0x7c94f0)
    cases=[]
    for _ in range(1024):
        a=tuple(f(rng.uniform(-100,100)) for _ in range(3))
        b=tuple(f(rng.uniform(-100,100)) for _ in range(3))
        cases.append((a,b,f(rng.uniform(0,100)),f(rng.uniform(0,100))))
    for r0,r1 in itertools.product([0.,.5,1.,2.],[0.,.5,1.,2.]):
        radius=f(r0+f(r1*scale))
        ds=[0.,radius,adjacent(radius,1)]
        if radius>0:ds.append(adjacent(radius,-1))
        for distance,y in itertools.product(ds,[0.,10000.,-10000.,float('nan'),float('inf')]):
            cases.append(((distance,y,0.),(0.,0.,0.),r0,r1))
    guard=bytes([0xa5])*32
    for a,b,r0,r1 in cases:
        aa=guard+struct.pack('<3f',*a)+guard;bb=guard+struct.pack('<3f',*b)+guard
        u.mem_write(p,aa);u.mem_write(q,bb)
        actual=s.call(0x7c94f0,(p+32,q+32),(r0,r1),limit=200)
        assert actual==expected(a,b,r0,r1),(a,b,r0,r1,actual)
        assert bytes(u.mem_read(p,len(aa)))==aa
        assert bytes(u.mem_read(q,len(bb)))==bb
    # Original caller fragment: getter -> geometry helper -> vertical filter.
    u.mem_write(c+0x278,struct.pack('<Q',inner))
    u.mem_write(actor+0x68,struct.pack('<Q',transform))
    u.mem_write(transform+0x278,struct.pack('<3f',0,0,0))
    def stop(uc,pc,size,data):
        if pc in [0x7f6b64,0x7f6c9c]:uc.emu_stop()
    hook=u.hook_add(UC_HOOK_CODE,stop)
    count=0;accepted=0
    radius=f(1.+scale)
    distances=[(0.,0.),(adjacent(radius,-1),0.),(radius,0.),(adjacent(radius,1),0.),(.5,.5),(2.,2.)]
    try:
        for mask,(x,z),dy,height in itertools.product([0,128,513,0xffffffff],distances,[0.,.5,1.,2.,-1.],[-1.,0.,.5,1.,2.]):
            u.mem_write(inner+0x40,struct.pack('<I',mask))
            a=(x,dy,z);u.mem_write(p,struct.pack('<3f',*a))
            u.mem_write(sp+0x18,struct.pack('<Q',actor))
            u.reg_write(regs.UC_ARM64_REG_SP,sp)
            u.reg_write(regs.UC_ARM64_REG_X0,c)
            u.reg_write(regs.UC_ARM64_REG_X21,p)
            for reg,value in [(regs.UC_ARM64_REG_S8,height),(regs.UC_ARM64_REG_S9,1.),(regs.UC_ARM64_REG_S10,1.)]:u.reg_write(reg,bits(value))
            u.emu_start(0x7f6b10,s.STOP,count=150)
            pc=u.reg_read(regs.UC_ARM64_REG_PC)
            assert pc in [0x7f6b64,0x7f6c9c]
            wanted=bool(mask==513 and expected(a,(0.,0.,0.),1.,1.) and (height<=0 or abs(dy)<height))
            assert (pc==0x7f6c9c)==wanted,(mask,a,height,hex(pc))
            accepted+=wanted;count+=1
    finally:u.hook_del(hook)
    db=sqlite3.connect(ROOT/'output/index.sqlite')
    callers=[{'pc':hex(pc),'owner_va':hex(va) if va else None}
             for pc,va in db.execute('select pc,owner_va from direct_calls where target_va=?',(0x7c94f0,))]
    evidence=[{'va':hex(va),'bytes':n,'sha256':hashlib.sha256(s.image.read(va,n)).hexdigest()}
              for va,n in [(0x7c94f0,0x6c),(0x7f6b10,0x54),(0x29d5fb8,4)]]
    result={'groups':{'whole_xz_helper_and_source_guards':len(cases),'masked_caller_fragment':count},
        'cases':len(cases)+count,'mismatches':[],'accepted_caller_cases':accepted,
        'scale':scale,'scale_bits':hex(bits(scale)),
        'xz_formula':'f32(sqrt(f32(f32(dx*dx)+f32(dz*dz)))) < f32(r0+f32(r1*scale))',
        'abi':{'helper':'0x7c94f0','x0':'pointer to float[3] A','x1':'pointer to float[3] B','s0':'r0','s1':'r1','w0':'boolean result'},
        'caller_contract':{'start':'0x7f6b10','reject_stop':'0x7f6b64','accept_stop':'0x7f6c9c',
            'rule':'mask == 0x201 and XZ proximity and (height_limit <= 0 or abs(dy) < height_limit)',
            'native_callees_executed':['0x33de0','0x7c94f0']},
        'dependencies_stubbed':[],'sqrtf_fallback_executed':False,
        'limits':['XZ/radius inputs finite and bounded; Y nonfinite probes prove this helper does not use Y.',
                  'NaN/overflow XZ path and SDK sqrtf fallback are not covered.',
                  'Caller fragment begins after actor/type filters; candidate collection and full query are not executed.',
                  'Detection predicate, not full penetration response or movement solver.',
                  'Coordinate units and physical interpretation of radius inputs remain unproven.'],
        'direct_callers':callers,'evidence':evidence,'elf_sha256':hashlib.sha256(s.image.data).hexdigest()}
    (ROOT/'output/mechanics/proximity_native.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ['groups','cases','accepted_caller_cases','scale','mismatches']}),flush=True)

if __name__=='__main__':main()
