"""Execute all six recipe material outputs through the complete native getter."""
from pathlib import Path
import hashlib
import json
import struct
from native_emulator import Sandbox

ROOT=Path(__file__).resolve().parent.parent
def main():
    s=Sandbox();u=s.uc;out=ROOT/'output';manager=s.HEAP+0x80000;base=s.HEAP+0x10000;array=s.HEAP+0x30000
    item=s.HEAP+0x50000;quantity=item+0x100
    table=json.loads((out/'tables_resolved/RecipeCraftParam.json').read_text())
    entry=json.loads((out/'manifest.json').read_text())['entries'][table['source_id']]
    original=json.loads((out/entry['decoded']).read_text())['data'];raw=(out/table['raw']['$blob']).read_bytes()
    cols={c['name']:i for i,c in enumerate(table['columns'])};uid=cols['UniqueID']
    minimum=min(r[uid]for r in table['rows']);maximum=max(r[uid]for r in table['rows']);span=maximum-minimum+1
    u.mem_write(base,raw);u.mem_write(array,b'\0'*(span*8))
    u.mem_write(manager+0x8f320,struct.pack('<H',minimum))
    u.mem_write(manager+0x8f300,struct.pack('<I',span));u.mem_write(manager+0x8f308,struct.pack('<Q',array))
    for i,row in enumerate(table['rows']):u.mem_write(array+(row[uid]-minimum)*8,struct.pack('<Q',base+original['data_start']+i*table['row_size']))
    u.mem_write(s.image.ptr(0x32fe548),b'\x01');cache=s.image.ptr(0x32fe550)
    for i,col in enumerate(table['columns']):u.mem_write(cache+4*i,struct.pack('<I',col['offset']))
    groups={'source_recipe_slots':0,'slot_boundary_and_u8_alias':0,'invalid_recipe_no_output_write':0,'u16_recipe_id_narrowing':0,'quantity_low_byte':0,'null_output_guards':0}
    source_written=0;source_untouched=0
    def prepare():u.mem_write(item,b'\xa5'*40);u.mem_write(quantity,b'\x5a'*24)
    for row in table['rows']:
        for slot in range(6):
            prepare();status=s.call(0xedac50,(manager,item+16,quantity+8,row[uid],slot),limit=2000)
            material=row[cols[f'Material{slot+1}']];amount=row[cols[f'Amount{slot+1}']]&255
            writes=material!=65534 and amount!=0
            assert status==int(writes)
            expected=struct.pack('<Q',material)
            assert bytes(u.mem_read(item,40))==(b'\xa5'*16+expected+b'\xa5'*16 if writes else b'\xa5'*40),(row[uid],slot,material)
            assert bytes(u.mem_read(quantity,24))==(b'\x5a'*8+bytes([amount])+b'\x5a'*15 if writes else b'\x5a'*24)
            source_written+=writes;source_untouched+=not writes
            groups['source_recipe_slots']+=1
    assert bytes(u.mem_read(base,len(raw)))==raw
    sample=table['rows'][0]
    for slot in [6,7,255,256]:
        prepare();s.call(0xedac50,(manager,item+16,quantity+8,sample[uid],slot),limit=2000)
        # The slot is passed as u8, so 256 selects slot zero.
        if slot==256:
            assert struct.unpack('<Q',u.mem_read(item+16,8))[0]==sample[cols['Material1']]
        else:
            assert bytes(u.mem_read(item,40))==b'\xa5'*40 and bytes(u.mem_read(quantity,24))==b'\x5a'*24
        groups['slot_boundary_and_u8_alias']+=1
    missing=[i for i in range(minimum,maximum+1)if i not in {r[uid]for r in table['rows']}][:3]+[65535]
    for recipe in missing:
        prepare();s.call(0xedac50,(manager,item+16,quantity+8,recipe,0),limit=2000)
        assert bytes(u.mem_read(item,40))==b'\xa5'*40 and bytes(u.mem_read(quantity,24))==b'\x5a'*24
        groups['invalid_recipe_no_output_write']+=1
    for bits in [0x10000,0x80000000,0xffff0000]:
        prepare();s.call(0xedac50,(manager,item+16,quantity+8,bits|sample[uid],0),limit=2000)
        assert struct.unpack('<Q',u.mem_read(item+16,8))[0]==sample[cols['Material1']]
        groups['u16_recipe_id_narrowing']+=1
    amount_col=table['columns'][cols['Amount1']]
    address=base+original['data_start']+amount_col['offset']
    for amount in [0,1,255,256,511,65535]:
        u.mem_write(address,struct.pack('<H',amount));prepare()
        s.call(0xedac50,(manager,item+16,quantity+8,sample[uid],0),limit=2000)
        assert u.mem_read(quantity+8,1)[0]==(amount&255 if amount&255 else 0x5a)
        groups['quantity_low_byte']+=1
    u.mem_write(base,raw)
    for a,b in [(0,quantity+8),(item+16,0)]:
        prepare();assert s.call(0xedac50,(manager,a,b,sample[uid],0),limit=2000)==0
        assert bytes(u.mem_read(item,40))==b'\xa5'*40 and bytes(u.mem_read(quantity,24))==b'\x5a'*24
        groups['null_output_guards']+=1
    result={'groups':groups,'cases':sum(groups.values()),'mismatches':[],'recipes':len(table['rows']),
       'getter':'0xedac50','all_source_rows_unchanged':bytes(u.mem_read(base,len(raw)))==raw,
       'source_sha256':hashlib.sha256(raw).hexdigest(),'dependencies_stubbed':[],
       'source_slot_outputs_written':source_written,'source_slot_outputs_untouched':source_untouched,
       'native_return_contract':'W0 boolean: one when outputs are written, zero when not written. Automatic pseudocode void signature is incomplete.',
       'rules':['Six slots 0..5 write complete eight-byte material item and u8 quantity only if material != 0xfffe and low quantity byte != 0.','Empty material or zero low quantity byte leaves caller output unchanged.','Recipe ID uses low 16 bits; slot argument uses low 8 bits.','Missing recipe and invalid slot leave caller output unchanged.','Source quantity storage is u16 but this output uses its low byte; callers must initialize outputs.'],
       'reconstructed_state':['Dense recipe lookup with sparse null entries','Native field metadata cache offsets','Raw BCSV rows'],
       'scope':'Complete material getter and actual item construction/copy helpers. Inventory availability, crafting transaction, ingredient consumption and recipe unlock rules are not executed.',
       'elf_sha256':hashlib.sha256(s.image.data).hexdigest()}
    (out/'mechanics/crafting_materials_native.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'groups':groups,'cases':sum(groups.values()),'mismatches':0}),flush=True)

if __name__=='__main__':main()
