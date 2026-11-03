"""Original region word-bit mutations and their terrain/navigation consumers."""
from pathlib import Path
import hashlib,itertools,json,struct
from terrain_nav_flags_native import WorldHarness
ROOT=Path(__file__).resolve().parent.parent

def main():
 h=WorldHarness();h.reset();s=h.s;u=h.u
 rect=s.HEAP+0x170000;owner=s.HEAP+0x180000;other=s.HEAP+0x181000
 groups={'complete_region_bit_mutators':0,'world_height_forwarders':0,'null_world_mutation_wrapper':0,'active_world_mutation_wrapper':0,'region_to_navigation_decoder':0}
 rectangles=[(0,0,2,2),(-1,-1,1,1),(7,7,9,9),(8,8,10,10),(3,4,3,4)]
 def rectangle(b):
  x,z,a,c=b;s.call(0x52b340,(rect+8,x&0xffffffff,z&0xffffffff));s.call(0x52b340,(rect+24,a,c))
 def check_words(before,b,mask,enabled):
  for z in range(8):
   for x in range(8):
    selected=b[0]<=x<=b[2] and b[1]<=z<=b[3]
    expected=(before|mask if enabled else before&~mask) if selected else before
    assert h.rd(h.word_address((x,z)))==expected
 for va,mask,mode,b,word in itertools.product([0x181ae0,0x185c80],[0],range(4),rectangles,[0,0xffffffff,0x1f00]):
  mask=0x40 if va==0x181ae0 else 4
  h.reset();rectangle(b)
  for point in h.cells:h.d(h.word_address(point),word)
  unchanged=bytes(u.mem_read(h.base,52*64))+bytes(u.mem_read(rect,40))
  args=(h.world,mode,rect) if va==0x181ae0 else (h.world,rect,mode)
  s.call(va,args,limit=100000)
  check_words(word,b,mask,bool(mode&1))
  assert unchanged==bytes(u.mem_read(h.base,52*64))+bytes(u.mem_read(rect,40))
  assert bytes(u.mem_read(h.words-16,16))==b'\xa5'*16 and bytes(u.mem_read(h.words+256,16))==b'\xa5'*16
  groups['complete_region_bit_mutators']+=1
 # Distinct denied/allowed grids prove the forwarded member selection.
 for va,offset,mode,allowed in itertools.product([0x163740,0x164e90],[0],range(4),[False,True]):
  offset=0x78 if va==0x163740 else 0x60
  h.reset();rectangle((0,0,1,1));u.mem_write(owner,bytes(0x100));u.mem_write(other,bytes(u.mem_read(h.world,0x100)))
  other_words=s.HEAP+0x182000;u.mem_write(other_words,bytes(256));h.q(other+0x68,other_words)
  for point in h.cells:h.d(h.word_address(point),3)
  h.q(owner+offset,h.world if allowed else other)
  h.q(owner+(0x60 if offset==0x78 else 0x78),other if allowed else h.world)
  assert s.call(va,(owner,rect,mode),limit=100000)==int(allowed)
  groups['world_height_forwarders']+=1
 for mode in range(4):
  h.reset();rectangle((0,0,2,2));u.mem_write(owner,bytes(0x100))
  before=bytes(u.mem_read(h.words,256));s.call(0x1637b0,(owner,rect,mode))
  assert bytes(u.mem_read(h.words,256))==before;groups['null_world_mutation_wrapper']+=1
 for mode,b in itertools.product(range(4),rectangles):
  h.reset();rectangle(b);u.mem_write(owner,bytes(0x100));h.q(owner+0x78,h.world)
  s.call(0x1637b0,(owner,rect,mode),limit=100000);check_words(0,b,4,bool(mode&1))
  groups['active_world_mutation_wrapper']+=1
 samples=[]
 for mode in range(4):
  h.reset();rectangle((3,3,3,3));h.d(h.word_address((3,3)),0x1f40)
  s.call(0x181ae0,(h.world,mode,rect),limit=100000)
  h.set_coord((3,3));s.call(0x185e70,(h.world,h.coord,h.output))
  value=bytes(u.mem_read(h.output+8,1))[0]
  assert value==(15 if mode&1 else 31)
  samples.append({'mode':mode,'runtime_word':hex(h.rd(h.word_address((3,3)))),'decoded_navigation_byte':value})
  groups['region_to_navigation_decoder']+=1
 result={'cases':sum(groups.values()),'groups':groups,'mismatches':[],'samples':samples,
  'native_functions':{'word_bit6_region':'0x181ae0','word_bit2_region':'0x185c80','guarded_world_mutator':'0x1637b0','height_forwarders':['0x163740','0x164e90'],'word_decoder':'0x185e70'},
  'rules':['Original inclusive region iterators modify only the in-world intersection. Mode low bit chooses set/clear; unrelated word bits are preserved.',
   '0x181ae0 modifies word bit6;0x185c80 modifies bit2.0x1637b0 uses owner+0x78 and safely skips a null world.',
   'Height predicate forwarders0x163740/0x164e90 select owner+0x78/+0x60 respectively and return the original boolean, despite void pseudocode signatures.',
   'A native region bit6 mutation changes whether word bit12 reaches navigation byte bit4; setting and clearing are verified through the original decoder.'],
  'scope':'Complete region mutation functions, native world wrappers and a decoder integration on reconstructed grids.',
  'limits':['This does not establish all gameplay meanings of word bits2/6 or a complete placement rule.','Actor registry removal0x165240, live caller reachability, dynamic terraform, steering and async lifecycle remain unexecuted.'],
  'source_reference':['mechanics/terrain_region_check_native.json','mechanics/terrain_nav_flags_native.json'],'dependencies_stubbed':[],'elf_sha256':hashlib.sha256(h.im.data).hexdigest()}
 (ROOT/'output/mechanics/terrain_region_mutation_native.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'cases':result['cases'],'groups':groups}))
if __name__=='__main__':main()
