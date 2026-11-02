"""Build a mechanics research ledger and verify original collision-mode clamps."""
from pathlib import Path
from collections import Counter
import hashlib
import json
import re
import sqlite3
import zlib
from native_emulator import Sandbox, regs

ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/'output/mechanics'

def save(name,value):
    (OUT/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')

def main():
    OUT.mkdir(exist_ok=True)
    sandbox=Sandbox()
    db=sqlite3.connect(ROOT/'output/index.sqlite')
    literal=sandbox.image.cstring(0x2965b0c)
    bg_names=[s for s in literal.split(',') if s]
    assert len(bg_names)==7
    table=json.loads((ROOT/'output/tables_resolved/PlayerStateParam.json').read_text())
    cols={c['name']:i for i,c in enumerate(table['columns']) if c.get('name')}
    bg_hashes={f'{zlib.crc32(n.encode()):08x}':i for i,n in enumerate(bg_names)}
    rows=[];bg_counts=Counter();obj_counts=Counter()
    for i,row in enumerate(table['rows']):
        bg=row[cols['BgCheckType']];obj=row[cols['ObjCheckType']]
        index=bg_hashes.get(bg['hash'])
        if index is None:raise ValueError('Local state uses BG enum outside native literal')
        bg_counts[bg_names[index]]+=1
        obj_counts[obj['labels'][0]]+=1
        rows.append({'source_row':i,'state':row[cols['StateName']],
                     'background_mode_index':index,'background_mode':bg_names[index],
                     'object_mode':obj,'object_check_rate':row[cols['ObjCheckRate']],
                     'stop_auto_save':row[cols['StopAutoSave']],
                     'enable_stage_change':row[cols['EnableStageChange']]})
    cases=list(range(65536))+[0x10000,0x7fffffff,0x80000000,0xfffffffe,0xffffffff]
    blocks=[];mismatches=[]
    for pc,limit in [(0xe8dd20,7),(0xe8dd74,7),(0xe8d960,3),(0xe8d9b4,3)]:
        instructions=sandbox.image.disasm(pc,8)
        assert instructions[0].mnemonic=='cmp' and instructions[1].mnemonic=='csel'
        for value in cases:
            sandbox.uc.reg_write(regs.UC_ARM64_REG_X0,value)
            sandbox.uc.emu_start(pc,pc+8,count=2)
            actual=sandbox.uc.reg_read(regs.UC_ARM64_REG_X8)
            expected=value if value<limit else 0
            if actual!=expected:mismatches.append({'pc':hex(pc),'value':value,'actual':actual})
        blocks.append({'begin':hex(pc),'end_exclusive':hex(pc+8),'limit':limit,
                       'cases':len(cases),'sha256':hashlib.sha256(sandbox.image.read(pc,8)).hexdigest(),
                       'instructions':[f'{x.mnemonic} {x.op_str}' for x in instructions]})
    assert not mismatches
    save('collision_states.json',{'rows':rows,'background_mode_names':bg_names,
         'background_mode_counts':dict(bg_counts),'object_mode_counts':dict(obj_counts),
         'source':'tables_resolved/PlayerStateParam.json',
         'scope':'State configuration and native BG enum literal; physical response and units are unproven.'})
    save('collision_native_verification.json',{'blocks':blocks,'comparisons':len(cases)*4,
         'mismatches':mismatches,'dependencies_stubbed':[],
         'scope':'Only the four original unsigned compare/select blocks after enum conversion. Enclosing loaders and enum conversion calls are not executed.',
         'rule':'u32 mode < limit retains value; all other u32 values become zero.',
         'native_bg_literal_va':'0x2965b0c','native_bg_literal':literal,
         'bg_field_reader':'0xe8dbf0','obj_field_reader':'0xe8d830',
         'bg_field_hash':'4045796c','obj_field_hash':'c5567172'})
    patterns={
      'physics_collision':r'Collision|Gravity|BgCheck|ObjCheck|Climb|Stairs',
      'terrain_editing':r'LandMaking|GroundMaker|FieldPreset|Cliff|River',
      'npc_ai_navigation':r'NpcAI|PathFind|Navigation|Steering|NavMesh',
      'items_inventory_crafting':r'Inventory|Pocket|Craft|Recipe|Durability|Remake',
      'save_persistence':r'SaveData|AutoSave|SaveManager|SaveFile',
      'network_multiplayer':r'Network|Sync|Ldn|Communication|SharePlay',
      'plants_and_breeding':r'Flower|Heredity|Watering|Growup|Plant',
      'weather_calendar':r'Weather|Calendar|Season|Aurora|Rainbow',
      'animation_effect_audio':r'Animation|SLink|ELink|Particle|Footstep',
      'economy_progression':r'Turnip|Money|Loan|Unlock|Mileage|ShopPrice'}
    refs=db.execute('select distinct string_va,function_va,text from string_refs').fetchall()
    domains={}
    for domain,pattern in patterns.items():
        regex=re.compile(pattern,re.I)
        evidence=[{'string_va':hex(s),'function_va':hex(f),'text':t}
                  for s,f,t in refs if f is not None and regex.search(t)]
        targets=sorted({int(r['function_va'],16) for r in evidence})
        functions=[]
        for va in targets:
            found=None
            for table_name in ['decomp_new','decomp']:
                row=db.execute(f'select path from {table_name} where va=?',(va,)).fetchone()
                if row:found=row[0];break
            callers=[{'pc':hex(p),'owner_va':hex(o) if o is not None else None}
                     for p,o in db.execute('select pc,owner_va from direct_calls where target_va=?',(va,))]
            functions.append({'va':hex(va),'pseudocode':found,'direct_callers':callers})
        domains[domain]={'status':'research_targets; not complete semantic RE',
                         'string_evidence':evidence,'functions':functions}
    save('systems_research_ledger.json',{'domains':domains,
         'scope':'Keyword evidence is navigation only. Domain membership and call edges do not prove behavior.',
         'model_sound_policy':'Use supplied catalogues as references; no request for missing model/audio sources.',
         'full_game_semantics_complete':False})
    print(json.dumps({'native_block_comparisons':len(cases)*4,'states':len(rows),
          'background_mode_counts':dict(bg_counts),'object_mode_counts':dict(obj_counts),
          'research_targets_by_domain':{k:len(v['functions']) for k,v in domains.items()}}))

if __name__=='__main__':main()
