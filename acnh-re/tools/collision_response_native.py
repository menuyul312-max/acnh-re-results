"""Verify bounded collision policy fragments, mask helpers, and scalar smoothing.

No complete player update, geometry solver, or OS runtime is executed.
"""
from pathlib import Path
import hashlib
import itertools
import json
import struct
from native_emulator import Sandbox,regs

ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/'output/mechanics'

def f32(v):return struct.unpack('<f',struct.pack('<f',v))[0]
def bits(v):return struct.unpack('<I',struct.pack('<f',v))[0]

def main():
    s=Sandbox();u=s.uc;p=s.HEAP;c=p+0x4000;inner=p+0x8000;sp=s.STACK+0x10000
    groups={}; samples=[]
    # These helpers are run in full, with an explicitly reconstructed object.
    u.mem_write(c+0x278,struct.pack('<Q',inner))
    count=0
    for mask in list(range(256))+[65535,65536,0x7fffffff,0x80000000,0xfffffffe,0xffffffff]:
        guard=bytes([0xa5])*128;u.mem_write(inner,guard)
        s.call(0x33dd0,(c,mask))
        assert bytes(u.mem_read(inner,128))==guard[:64]+struct.pack('<I',mask)+guard[68:]
        assert s.call(0x33de0,(c,))==mask
        count+=1
    groups['full_mask_set_get_and_guards']=count
    # The actual predicate at dc80a0 is executed by the fragment's original BL.
    count=0
    for table,override,flag,gate,old,predicate in itertools.product(
        range(3),[0,1,2,3,0xffffffff],range(256),range(2),[0,0xa5a5a5a5],[0,1,2,0xffffffff]):
        u.reg_write(regs.UC_ARM64_REG_SP,sp)
        u.reg_write(regs.UC_ARM64_REG_X19,p);u.reg_write(regs.UC_ARM64_REG_X20,c)
        u.reg_write(regs.UC_ARM64_REG_X22,gate)
        u.mem_write(sp+0x18,struct.pack('<I',table))
        u.mem_write(p+0x12ec,struct.pack('<I',override))
        u.mem_write(p+0xf03,bytes([flag]))
        u.mem_write(p+0x178,struct.pack('<I',predicate))
        u.mem_write(c+0x178,struct.pack('<I',old))
        u.emu_start(0xda9a60,0xda9b30,count=120)
        assert u.reg_read(regs.UC_ARM64_REG_PC)==0xda9b30
        mode=table if override==2 else override
        if flag&64 and mode!=2:mode=1
        expected_flag=(old&~1)|((1-gate) if mode in [0,1] else 0)
        needs_predicate=mode==0 and gate==0
        expected_mask=0x201 if mode==1 else (0x80 if predicate==0 else 0x201) if needs_predicate else 0
        actual_mask=u.reg_read(regs.UC_ARM64_REG_X1)
        assert actual_mask==expected_mask
        assert struct.unpack('<I',u.mem_read(c+0x178,4))[0]==expected_flag
        assert u.reg_read(regs.UC_ARM64_REG_X0)==c
        count+=1
        if len(samples)<12 and flag==0 and old==0:
            samples.append({'table':table,'override':override,'gate':gate,
                            'predicate_input':predicate,'mask':actual_mask})
    groups['policy_fragment_cases']=count
    # Finite nonnegative scalar inputs; no claim about radius units or frame time.
    count=0
    values=[0.,0.0001,0.01,0.1,0.5,1.,1.5,2.,10.,100.]
    for previous,target,base in itertools.product(values,values,values):
        previous,target,base=map(f32,(previous,target,base))
        u.reg_write(regs.UC_ARM64_REG_X19,p)
        u.mem_write(p+0x12f0,struct.pack('<f',previous))
        u.reg_write(regs.UC_ARM64_REG_S0,bits(target))
        u.reg_write(regs.UC_ARM64_REG_S8,bits(base))
        u.emu_start(0xda9844,0xda99bc,count=80)
        assert u.reg_read(regs.UC_ARM64_REG_PC)==0xda99bc
        step=f32(base/f32(20.))
        expected=min(target,f32(previous+step)) if previous<target else max(target,f32(previous-step)) if previous>target else previous
        actual=struct.unpack('<I',u.mem_read(p+0x12f0,4))[0]
        assert actual==bits(expected),(previous,target,base,hex(actual),hex(bits(expected)))
        count+=1
    groups['finite_nonnegative_scalar_smoothing_cases']=count
    spans=[(0x33dd0,12),(0x33de0,12),(0xdc80a0,16),(0xda9a60,0xd0),(0xda9844,0x30),(0xda99a0,0x1c)]
    evidence=[{'va':hex(a),'bytes':n,'sha256':hashlib.sha256(s.image.read(a,n)).hexdigest()} for a,n in spans]
    result={'groups':groups,'cases':sum(groups.values()),'mismatches':[],
      'elf_sha256':hashlib.sha256(s.image.data).hexdigest(),'evidence':evidence,
      'policy_samples':samples,'dependencies_stubbed':[],
      'externally_supplied_fragment_inputs':[],
      'executed_predicate':{'callee':'0xdc80a0','rule':'u32 at player+0x178 equals zero',
        'field_inputs':[0,1,2,4294967295],'semantics':'Field gameplay meaning remains unproven.'},
      'policy':{'override_offset':'player+0x12ec','override_passthrough_value':2,
        'flag_offset':'player+0xf03','flag_bit':6,'flag_rule':'If set and effective mode != 2, select mode 1.',
        'collider_flag':'collider+0x178 bit0; other bits preserved',
        'mask_storage':'*(collider+0x278)+0x40','mask_values':[0,128,513],
        'mask_bit_meanings':'Not yet proven; do not assign solver semantics from numeric values.'},
      'scalar_rule':{'storage':'player+0x12f0','step':'f32(base/20)','behavior':'Move toward target, clamping overshoot, with f32 operations.',
        'limits':'Only finite nonnegative cases; no NaN/Inf or full update tested. Units and timestep interpretation unproven.'},
      'scope':'Whole mask storage helpers plus bounded policy/scalar fragments; no full collision solver, navigation, or movement runtime.'}
    (OUT/'collision_response_native.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'groups':groups,'cases':sum(groups.values()),'mismatches':0}),flush=True)

if __name__=='__main__':main()
