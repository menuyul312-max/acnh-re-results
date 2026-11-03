"""Execute original selector on supplied BCSV plus reconstructed runtime caches.

Prepared cache categories are deliberately synthetic; enum hash/category wiring
and resource loading remain separate research questions. No patched instructions.
"""
from pathlib import Path
import json, struct, random, hashlib, zlib
from native_emulator import Sandbox

ROOT=Path(__file__).resolve().parents[1]

def next_draw(state):
    a,b,c,d=state
    t=(a^(a<<11))&0xffffffff
    x=(t^(t>>8)^d^(d>>19))&0xffffffff
    return x,[b,c,d,x]

def main():
    s=Sandbox();u=s.uc;im=s.image
    def q(p,v):u.mem_write(p,struct.pack('<Q',v))
    def w(p,v):u.mem_write(p,struct.pack('<I',v&0xffffffff))
    def h(p,v):u.mem_write(p,struct.pack('<H',v))
    data=json.loads((ROOT/'output/tables_resolved/FieldOutsideTemplate.json').read_text())
    manifest=json.loads((ROOT/'output/manifest.json').read_text())['entries']
    start=json.loads((ROOT/'output'/manifest[data['source_id']]['decoded']).read_text())['data']['data_start']
    raw=(ROOT/'output'/data['raw']['$blob']).read_bytes()
    base=s.HEAP;owner=base+0x10000;ptrs=base+0x20000;cache=base+0x30000;category=base+0x31000;rng=base+0x32000;resource=base+0x33000
    u.mem_write(base,raw)
    q(im.ptr(0x32d1ba8),owner)
    q(owner+0xb58+0xb0,resource);q(resource+8,base)
    w(owner+0xd30,data['row_count']);q(owner+0xd38,ptrs)
    h(owner+0xd50,0);h(owner+0xd52,data['row_count']-1)
    for i in range(data['row_count']):q(ptrs+8*i,base+start+i*data['row_size'])
    # Original selector reads an existing typed cache, not TemplateKind hashes.
    typed=im.ptr(0x32e3a78);w(typed,data['row_count']);q(typed+8,category)
    u.mem_write(im.ptr(0x32e2b38),b'\x01')
    uid_col=next(c['offset'] for c in data['columns'] if c['name']=='UniqueID')
    w(im.ptr(0x32e2b40)+0x64,uid_col)
    uid_index=next(i for i,c in enumerate(data['columns']) if c['name']=='UniqueID')
    ids=[row[uid_index] for row in data['rows']]
    enum_literal=im.cstring(0x2933de2)
    enum_names=[n.strip() for n in enum_literal.split(',') if n.strip()]
    assert len(enum_names)==3,enum_names
    kind_index=next(i for i,c in enumerate(data['columns']) if c['name']=='TemplateKind')
    enum_hashes={f'{zlib.crc32(n.encode()):08x}':i for i,n in enumerate(enum_names)}
    source_kinds=[enum_hashes[row[kind_index]['hash']] for row in data['rows']]
    prng=random.Random(42);cases=[]
    assignments=[[i%3 for i in range(36)],[0]*36,[1]*36,[2]*36,[7]*36,
                 [prng.randrange(5) for i in range(36)]]
    assignments.append(source_kinds)
    fixtures=[(kinds,ids) for kinds in assignments]
    fixtures.extend((source_kinds,[offset+i for i in range(36)]) for offset in (32,64,96))
    fixtures.append((source_kinds,[7]*36))
    for fi,(kinds,fixture_ids) in enumerate(fixtures):
        for i,uid in enumerate(fixture_ids):h(base+start+i*data['row_size']+uid_col,uid)
        for i,k in enumerate(kinds):h(category+2*i,k)
        for wanted in (0,1,2,3):
            eligible=sorted(set(fixture_ids[i] for i,k in enumerate(kinds) if (k if k<=2 else 0)==wanted and fixture_ids[i]<=127))
            for ri in range(12):
                state=[prng.getrandbits(32) for _ in range(4)]
                u.mem_write(rng,struct.pack('<4I',*state))
                draw,next_state=next_draw(state)
                expected=eligible[(draw*len(eligible))>>32] if eligible else 0
                got=s.call(0x552bb0,[0,wanted,rng])&0xffffffff
                after=list(struct.unpack('<4I',bytes(u.mem_read(rng,16))))
                assert got==expected,(fi,wanted,got,expected)
                assert after==(next_state if eligible else state)
                cases.append({'fixture':fi,'requested_kind':wanted,'eligible_ids':eligible,'rng_before':state,'result':got})
    result={'source_elf_sha256':hashlib.sha256(im.data).hexdigest(),'function':'0x552bb0',
            'scope':'Full original selector with original 36-row BCSV and reconstructed registry/typed-cache fixtures.',
            'cases':len(cases),'mismatches':[],'dependencies_stubbed':[],
            'instruction_evidence':{'va':'0x552bb0','bytes':992,
                'sha256':hashlib.sha256(im.read(0x552bb0,992)).hexdigest(),
                'listing':'ui_island/island_template_selector.asm'},
            'enum_static_evidence':{'literal_va':'0x2933de2','literal':enum_literal,'order':enum_names,
                'enum_initializer':'0x50ea00','hash_to_index_initializer':'0x50dff0',
                'contract':'Order comes from static code and CRC32 labels; cache is reconstructed, original initialization not executed.'},
            'fixture_contract':'First seven scenarios retain original source IDs; last four use synthetic IDs for upper words, >=128 rejection and duplicate collapse.',
            'verified':['Filter uses existing u16 category cache indexed by native row index; values >2 become 0.',
                        'Eligible source UniqueID values populate a 128-bit bitset; duplicate IDs collapse.',
                        'Selection uses floor(next_u32 * popcount / 2^32) as rank among ascending set bits.',
                        'Empty eligible set returns 0 without consuming RNG; nonempty consumes one draw.'],
            'limits':['Enum order is supported by static initialization and original CRC32 labels; actual cache initialization remains unexecuted.',
                      'No proof of live registry allocation, resource loading, transforms, collision or water behavior.'],
            'fixtures':cases}
    out=ROOT/'output/ui_island/island_template_selector_native.json'
    out.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='fixtures'},indent=2))

if __name__=='__main__':main()
