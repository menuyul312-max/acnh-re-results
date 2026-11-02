"""Execute PlayerActor parameter access and motion-triplet builders in full."""
from pathlib import Path
import hashlib
import itertools
import json
import struct
from native_emulator import Sandbox

ROOT=Path(__file__).resolve().parent.parent
def f(v):return struct.unpack('<f',struct.pack('<f',v))[0]
def main():
    s=Sandbox();u=s.uc;registry=s.HEAP+0x10000;dest=s.HEAP+0x20000
    def q(p,v):u.mem_write(p,struct.pack('<Q',v))
    def d(p,v):u.mem_write(p,struct.pack('<I',v))
    # The actual singleton resolver uses a missing per-type registry entry and
    # an already initialized fallback object; it is never replaced or patched.
    q(s.image.ptr(0x32d16a8),registry)
    u.mem_write(registry,b'\0'*(158*16))
    d(s.image.ptr(0x32d8b28),0)
    u.mem_write(s.image.ptr(0x32fd7e8),b'\x01')
    parameter=s.image.ptr(0x32fd7f0)
    vt=s.image.ptr(0x32d1bf0)+16
    getter=s.image.ptr(vt+0xf0)
    assert getter==0x37a50
    for offset in [0x780,0x7b0]:q(parameter+offset,vt)
    def value(offset,v):u.mem_write(parameter+offset+0x24,struct.pack('<f',v))
    guard=b'\xa5'*16;groups={'gravity_getter':0,'terminal_gravity_triplet':0,'custom_motion_triplet':0}
    default_terminal=struct.unpack('<f',s.image.read(0x29d5c8c,4))[0]
    gravities=[-.25,-.2,0.,1.,-2.1]
    for gravity in gravities:
        gravity=f(gravity);value(0x780,gravity)
        assert s.call(0xe6fb50,(),limit=1000)==parameter
        s.call(0xdb17b0,(),limit=1000)
        assert struct.pack('<f',s.float_result())==struct.pack('<f',gravity)
        groups['gravity_getter']+=1
        for terminal in [-10.,-2.1,-0.,0.,.5,10.]:
            terminal=f(terminal);value(0x7b0,terminal)
            u.mem_write(dest,guard*3)
            s.call(0xda91a0,(dest+16,),limit=1000)
            limit=f(-(-terminal if terminal<0 else terminal))
            expected=struct.pack('<3f',limit,limit,gravity)
            assert bytes(u.mem_read(dest,48))==guard+expected+guard[:4]+guard
            groups['terminal_gravity_triplet']+=1
        for first,g,t in itertools.product([-10.,0.,1.],[-2.,-.25,-0.,0.,1.],[-10.,-2.1,-0.,0.,1.]):
            first,g,t=map(f,(first,g,t));u.mem_write(dest,guard*3)
            s.call(0xdb17f0,(dest+16,),(first,g,t),limit=1000)
            expected=struct.pack('<3f',first,t if t<0 else default_terminal,g if g<0 else gravity)
            assert bytes(u.mem_read(dest,48))==guard+expected+guard[:4]+guard
            groups['custom_motion_triplet']+=1
    local=json.loads((ROOT/'output/byml_resolved/01079.json').read_text())['root']['@PlayerActor']
    result={'groups':groups,'cases':sum(groups.values()),'mismatches':[],
      'native_functions':['0xdb17b0','0xda91a0','0xdb17f0'],
      'callees_executed':['0xe6fb50','0xe70ea0','0x5df70','0x37a50'],
      'parameter_bindings':{'mDefaultGravity':{'member_offset':'0x780','value_offset':'0x7a4','source_value':local['@mDefaultGravity.f32']},
          'mSpeedYMin':{'member_offset':'0x7b0','value_offset':'0x7d4','source_value':local['@mSpeedYMin.f32']}},
      'typed_float_getter':{'vtable':hex(vt),'getter':hex(getter),'value_offset':36},
      'terminal_fallback_constant':default_terminal,
      'rules':{'0xdb17b0':'Returns mDefaultGravity through actual singleton and typed property getter.',
        '0xda91a0':'Writes [negative magnitude of mSpeedYMin, same value, mDefaultGravity], preserving original signed-zero behavior.',
        '0xdb17f0':'Writes [S0, S2 if negative else native fallback, S1 if negative else mDefaultGravity].'},
      'dependencies_stubbed':[],
      'reconstructed_state':['Actor-type registry with absent type entry','Initialized fallback PlayerActor parameter object','Real typed float vtable and selected field values'],
      'scope':'Complete parameter getter and motion-triplet builders on selected resolver path. Full gravity integration, collision response and player state update are not executed.',
      'limits':['Parameter constructors and per-actor registry success branch are not executed.','Finite values only; NaN and infinity behavior is not covered.','Field/argument units and update frequency remain unproven.'],
      'elf_sha256':hashlib.sha256(s.image.data).hexdigest()}
    (ROOT/'output/mechanics/player_motion_native.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'groups':groups,'cases':sum(groups.values()),'terminal_fallback_constant':default_terminal,'mismatches':0}),flush=True)

if __name__=='__main__':main()
