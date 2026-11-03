"""Original registered-region unlink, world dispatch and release wrapper."""
from pathlib import Path
import hashlib,itertools,json,struct
from terrain_nav_flags_native import WorldHarness
ROOT=Path(__file__).resolve().parent.parent

def main():
 h=WorldHarness();h.reset();s=h.s;u=h.u
 owner=s.HEAP+0x180000;entries=s.HEAP+0x170000;sentinel=owner+0xf08;link_offset=0x48
 worlds=[h.world,s.HEAP+0x182000,s.HEAP+0x183000];words=[h.words,s.HEAP+0x184000,s.HEAP+0x185000]
 groups={'complete_registry_removal':0,'release_wrapper':0,'null_entry_guard':0,'repeat_call_contract':0};samples=[]
 def prepare(kind,enabled,index):
  h.reset();u.mem_write(owner,bytes(0x1100))
  for i,(world,data) in enumerate(zip(worlds,words)):
   if i:u.mem_write(world,bytes(u.mem_read(h.world,0x100)))
   h.q(world+0x68,data);u.mem_write(data,struct.pack('<I',0x1f40)*64);h.q(owner+0x60+8*i,world)
  nodes=[entries+0x100*i+link_offset for i in range(3)]
  h.q(sentinel,nodes[-1]);h.q(sentinel+8,nodes[0]);h.d(owner+0xf18,3);h.d(owner+0xf1c,link_offset)
  for i,node in enumerate(nodes):
   entry=entries+0x100*i;u.mem_write(entry,bytes(0x80))
   s.call(0x52b340,(entry+0x20,1,2));s.call(0x52b340,(entry+0x30,3,4))
   u.mem_write(entry+0x40,bytes([enabled if i==index else 1]));h.d(entry+0x44,kind if i==index else 1)
   h.q(node,sentinel if i==0 else nodes[i-1]);h.q(node+8,sentinel if i==2 else nodes[i+1])
  h.q(h.im.ptr(0x32d0de8),owner-0x28)
  return entries+0x100*index,nodes
 def verify(entry,nodes,index,removed,kind):
  assert h.rd(owner+0xf18)==3-int(removed)
  expected=[n for i,n in enumerate(nodes) if not(removed and i==index)]
  actual=[];p=h.rq(sentinel+8);last=sentinel
  while p!=sentinel:
   assert p not in actual and h.rq(p)==last;actual.append(p);last=p;p=h.rq(p+8)
  assert actual==expected and h.rq(sentinel)==last
  if removed:assert bytes(u.mem_read(entry+link_offset,16))==bytes(16)
  for i,data in enumerate(words):
   for z in range(8):
    for x in range(8):
     clear=removed and kind==i+1 and 1<=x<=3 and 2<=z<=4
     assert h.rd(data+4*(x+8*z))==(0x1f00 if clear else 0x1f40)
 for kind,enabled,index in itertools.product([0,1,2,3,4],[0,1,2,3,255],range(3)):
  entry,nodes=prepare(kind,enabled,index)
  s.call(0x165240,(owner,entry),limit=100000)
  verify(entry,nodes,index,bool(enabled&1),kind)
  assert bytes(u.mem_read(entry+0x40,1))==bytes([enabled])
  groups['complete_registry_removal']+=1
 for kind,enabled,index in itertools.product([1,2,3,4],[0,1,2,3],range(3)):
  entry,nodes=prepare(kind,enabled,index)
  s.call(0x168140,(entry,),limit=100000)
  verify(entry,nodes,index,bool(enabled&1),kind)
  assert bytes(u.mem_read(entry+0x40,1))==b'\0'
  groups['release_wrapper']+=1
 entry,nodes=prepare(1,1,1);before=bytes(u.mem_read(owner,0x1100))
 s.call(0x165240,(owner,0));assert before==bytes(u.mem_read(owner,0x1100));groups['null_entry_guard']+=1
 for wrapped in [False,True]:
  entry,nodes=prepare(1,1,1)
  for _ in range(2):s.call(0x168140 if wrapped else 0x165240,(entry,) if wrapped else (owner,entry),limit=100000)
  expected=2 if wrapped else 1;assert h.rd(owner+0xf18)==expected
  samples.append({'wrapped':wrapped,'calls':2,'remaining_count':expected,'enabled_byte':bytes(u.mem_read(entry+0x40,1))[0]});groups['repeat_call_contract']+=1
 result={'cases':sum(groups.values()),'groups':groups,'mismatches':[],'samples':samples,
  'native_functions':['0x165240','0x168140','0x168180','0x168190','0x1967c60','0x181ae0'],
  'layout':{'owner_world_members':['0x60','0x68','0x70'],'owner_count':'0xf18','owner_link_offset_s32':'0xf1c','entry_enabled_byte':'0x40','entry_kind_s32':'0x44','entry_rectangle':'0x18'},
  'rules':['Null entry or enabled low bit clear skips removal. An accepted entry is unlinked and count decremented before checking its kind.',
   'Kinds1/2/3 clear word bit6 over the entry rectangle in owner worlds+0x60/+0x68/+0x70. Other tested kinds still unlink/decrement but do not mutate a world.',
   'Direct removal leaves the enabled byte intact. Wrapper0x168140 obtains the owner from the world singleton and clears the byte after the call, including when its low bit was already clear.',
   'Two direct calls on the prepared entry decrement twice; two wrapper calls decrement once. This is a helper lifecycle contract, not a demonstrated live-game bug.'],
  'scope':'Complete original release chain on prepared three-node lists and three distinct runtime world grids.',
  'limits':['Entry allocation, registration/insertion, original owner constructor and full actor identity/lifetime remain unproven.','Link offset is configured to0x48 in the fixture, not claimed as the sole original layout. Negative/custom link offsets and invalid list state are untested.','No live placement, async task, steering or physics is executed.'],
  'source_reference':['mechanics/terrain_region_mutation_native.json','mechanics/terrain_nav_flags_native.json'],'dependencies_stubbed':[],'elf_sha256':hashlib.sha256(h.im.data).hexdigest()}
 (ROOT/'output/mechanics/world_registry_release_native.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'cases':result['cases'],'groups':groups,'samples':samples}))
if __name__=='__main__':main()
