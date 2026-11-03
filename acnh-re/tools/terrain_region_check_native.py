"""Original rectangular terrain flag/height predicate on reconstructed grids."""
from pathlib import Path
import hashlib,itertools,json,struct
from terrain_nav_flags_native import WorldHarness
ROOT=Path(__file__).resolve().parent.parent

def main():
 h=WorldHarness();h.reset();s=h.s;u=h.u
 rect=s.HEAP+0x170000
 threshold=struct.unpack('<f',u.mem_read(h.im.ptr(0x32d71a8),4))[0]
 groups={'complete_region_predicate':0};samples=[];outcomes={'true':0,'false':0}
 for mode,bounds,overlay,delta,flags in itertools.product([0,1],[(0,2),(-1,1),(8,10)],['none','active','inherit'],[0.,threshold,threshold+.25],[0,1,2,3]):
  h.reset()
  for x in range(8):
   for z in range(8):
    level=delta if x==2 else 0.
    u.mem_write(h.tile((x,z)),struct.pack('<12f',*([level]*12))+bytes(4))
    u.mem_write(h.overlay+52*(x+8*z),struct.pack('<12f',*([2*level]*12))+bytes([7 if overlay=='inherit' else 0])*4)
    h.d(h.word_address((x,z)),flags)
  h.d(h.world+0x50,64 if overlay!='none' else 0);h.q(h.world+0x58,h.overlay if overlay!='none' else 0)
  s.call(0x52b340,(rect+8,bounds[0]&0xffffffff,0));s.call(0x52b340,(rect+24,bounds[1],0))
  valid=[x for x in range(bounds[0],bounds[1]+1) if 0<=x<8]
  levels=[(delta if x==2 else 0.)*(2 if mode==0 and overlay=='active' else 1) for x in valid]
  expected=not valid or bool(flags&(1<<mode)) and max(levels)-min(levels)<=threshold
  source=bytes(u.mem_read(h.base,52*64))+bytes(u.mem_read(h.overlay,52*64))+bytes(u.mem_read(h.words,4*64))+bytes(u.mem_read(rect,40))
  result=s.call(0x181fa0,(h.world,rect,mode),limit=100000)
  assert result==int(expected),(mode,bounds,overlay,delta,flags,result,expected)
  assert source==bytes(u.mem_read(h.base,52*64))+bytes(u.mem_read(h.overlay,52*64))+bytes(u.mem_read(h.words,4*64))+bytes(u.mem_read(rect,40))
  groups['complete_region_predicate']+=1;outcomes['true' if result else 'false']+=1
  if bounds==(0,2) and flags==3:samples.append({'mode':mode,'overlay':overlay,'height_difference':delta,'native_result':result})
 result={'cases':sum(groups.values()),'groups':groups,'mismatches':[],'threshold':threshold,'samples':samples,'outcomes':outcomes,
  'native_functions':['0x181fa0','0x52c950','0x52c970','0x52c9b0','0x52c9e0'],
  'rules':['Iterates the inclusive rectangular cell range; out-of-world cells are skipped. An entirely outside region returns true in these tests.',
   'Mode low bit0 requires world-word bit0 and reads base or an available overlay whose first attribute byte is not7. Mode low bit1 requires word bit1 and reads base only.',
   'The running maximum-minus-minimum of record float0 must not exceed the original threshold; equality passes. Input records are preserved.'],
  'scope':'Complete original rectangle predicate on finite reconstructed base/overlay heights and word flags; independent flag/range oracle.',
  'limits':['This checks record float0, not all12 terrain samples or geometric collision.','Preset/PBC loader, source word generation, inverted rectangles, NaN/infinite heights and live placement callers remain unproven.'],
  'source_reference':['mechanics/terrain_nav_flags_native.json','mechanics/continuation_frontier.json'],
  'dependencies_stubbed':[],'elf_sha256':hashlib.sha256(h.im.data).hexdigest()}
 (ROOT/'output/mechanics/terrain_region_check_native.json').write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps({'cases':result['cases'],'threshold':threshold,'outcomes':outcomes}),flush=True)
if __name__=='__main__':main()
