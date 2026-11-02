"""Trace constructor name stores and PlayerActor property-access candidates.

Static evidence only: a name-store match or a getter call is not execution of
the full constructor, all branches, or a gameplay update.
"""
from pathlib import Path
import hashlib
import json
import re
import sqlite3
import argparse
from native_image import Image
from capstone.arm64_const import ARM64_OP_IMM,ARM64_OP_MEM,ARM64_OP_REG

ROOT=Path(__file__).resolve().parent.parent
def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--constructor',type=lambda x:int(x,0),default=0xdc98f0)
    parser.add_argument('--byml',default='01079')
    parser.add_argument('--singleton',type=lambda x:int(x,0),default=0xe6fb50)
    parser.add_argument('--output',default='player_parameter_bindings.json')
    args=parser.parse_args();constructor=args.constructor
    im=Image();db=sqlite3.connect(ROOT/'output/index.sqlite')
    size=db.execute('select size from native_functions where va=?',(constructor,)).fetchone()[0]
    names={a:t for a,t in db.execute('select distinct string_va,text from string_refs where function_va=?',(constructor,)) if t.startswith('m')}
    registers={'x0':('object',0)};stores={};bindings=[]
    def key(reg):
        n=im.disassembler.reg_name(reg)
        if n in ['fp','lr']:return 'x29' if n=='fp' else 'x30'
        if re.fullmatch('[wx][0-9]+',n):return 'x'+n[1:]
        return None
    def value(op):
        if op.type==ARM64_OP_IMM:return ('constant',op.imm)
        if op.type==ARM64_OP_REG:return registers.get(key(op.reg))
    def plus(a,b):return (a[0],a[1]+b) if a else None
    def memory(op):return plus(registers.get(key(op.mem.base)),op.mem.disp) if not op.mem.index else None
    for ins in im.disasm(constructor,size):
        ops=ins.operands;updates={};writeback=None
        if ins.mnemonic in ['adr','adrp'] and len(ops)==2:updates[key(ops[0].reg)]=('constant',ops[1].imm)
        elif ins.mnemonic=='mov' and len(ops)==2:updates[key(ops[0].reg)]=value(ops[1])
        elif ins.mnemonic in ['add','sub'] and len(ops)==3 and ops[2].type==ARM64_OP_IMM:
            amount=ops[2].imm*(1<<ops[2].shift.value)
            updates[key(ops[0].reg)]=plus(value(ops[1]),amount if ins.mnemonic=='add' else -amount)
        elif ins.mnemonic=='ldr' and len(ops)==2 and ops[1].type==ARM64_OP_MEM:
            address=memory(ops[1]);v=None
            if address and address[0]=='constant':
                try:v=('constant',im.ptr(address[1]))
                except ValueError:pass
            updates[key(ops[0].reg)]=v
        if ins.mnemonic in ['str','stp'] and ops[-1].type==ARM64_OP_MEM:
            address=memory(ops[-1]);width=8 if im.disassembler.reg_name(ops[0].reg).startswith('x')else 4
            if address and address[0]=='object':
                for i,operand in enumerate(ops[:-1]):
                    v=value(operand);offset=address[1]+i*width
                    if v and v[0]=='constant':
                        stores[offset]={'value':v[1],'pc':hex(ins.address),'instruction':ins.mnemonic+' '+ins.op_str}
                        if v[1] in names:
                            member=offset-8;vt=stores.get(member);getter=None
                            if vt:
                                try:getter=im.ptr(vt['value']+0xf0)
                                except ValueError:pass
                            bindings.append({'name':names[v[1]],'name_va':hex(v[1]),'member_offset':member,
                              'name_store_pc':hex(ins.address),'instruction':ins.mnemonic+' '+ins.op_str,
                              'vtable_store_candidate':vt,'getter_f0_candidate':hex(getter) if getter else None})
            if ins.writeback:writeback=(key(ops[-1].mem.base),address)
        for reg in ins.regs_access()[1]:
            k=key(reg)
            if k:registers.pop(k,None)
        if ins.mnemonic in ['bl','blr']:
            for i in range(19):registers.pop('x'+str(i),None)
        for k,v in updates.items():
            if k and v:registers[k]=v
        if writeback and writeback[0] and writeback[1]:registers[writeback[0]]=writeback[1]
    unique={(b['name'],b['member_offset']):b for b in bindings};bindings=list(unique.values())
    cpp_path=None
    for tab in ['decomp_new','decomp']:
        found=db.execute('select path from '+tab+' where va=?',(constructor,)).fetchone()
        if found:cpp_path=ROOT/'output'/found[0];break
    cpp=cpp_path.read_text() if cpp_path else ''
    cpppairs=set()
    for slot,address in re.findall(r'param_1\[(0x[0-9a-f]+|[0-9]+)\] = \(long\)&UNK_([0-9a-f]+)',cpp):
        native=int(address,16)-0x100000
        if native in names:cpppairs.add((names[native],int(slot,0)*8-8))
    byml=json.loads((ROOT/f'output/byml_resolved/{args.byml}.json').read_text())
    assert len(byml['root'])==1
    data=next(iter(byml['root'].values()))
    for b in bindings:
        b['cpp_store_agrees']=(b['name'],b['member_offset']) in cpppairs
        b['local_values']=[{'descriptor':k[1:],'value':v}for k,v in data.items() if k.startswith('@'+b['name']+'.') or k.startswith('@'+b['name']+'[')]
    by_offset={b['member_offset']:b for b in bindings}
    accesses=[]
    for pc,owner in db.execute('select pc,owner_va from direct_calls where target_va=?',(args.singleton,)) if args.singleton else []:
        for ins in im.disasm(pc+4,64):
            if ins.mnemonic in ['bl','blr','b','ret']:break
            op=ins.operands;offset=None
            if ins.mnemonic=='add'and len(op)==3 and op[1].type==ARM64_OP_REG and im.disassembler.reg_name(op[1].reg)=='x0'and op[2].type==ARM64_OP_IMM:offset=op[2].imm
            if offset in by_offset:
                accesses.append({'parameter':by_offset[offset]['name'],'member_offset':offset,
                    'singleton_call_pc':hex(pc),'member_address_pc':hex(ins.address),
                    'owner_va':hex(owner)if owner is not None else None,'instruction':ins.mnemonic+' '+ins.op_str})
    result={'constructor':hex(constructor),'constructor_bytes':size,'bindings':bindings,'bindings_count':len(bindings),
      'cpp_name_pairs':len(cpppairs),'cpp_agree_count':sum(b['cpp_store_agrees']for b in bindings),
      'property_access_candidates':accesses,'access_candidate_count':len(accesses),
      'local_byml':f'byml_resolved/{args.byml}.json','source':byml['source'],'source_sha256':byml['source_sha256'],
      'scope':'Linear symbolic trace of original name/vtable stores, cross-checked with pseudocode. Member-address candidates after parameter singleton calls are navigation evidence; constructor and complete callers not executed.',
      'limits':['Unknown branch reachability and omitted access patterns remain.','Parameter names and values do not prove units or feature reachability.','Getter +0xf0 candidates require separate validation.'],
      'constructor_sha256':hashlib.sha256(im.read(constructor,size)).hexdigest()}
    if constructor==0xc9f360:
        owner=(ROOT/'output/binary/analysis_decomp/c9e140.c').read_text()
        assert 'FUN_00d9f360(param_1 + 0x20e,' in owner
        call=im.disasm(0xc9e40c,4)[0]
        assert call.mnemonic=='bl' and call.operands[0].imm==constructor
        result['embedding_evidence']={'owner_constructor':'0xc9e140','parameter_constructor':'0xc9f360',
            'call_site':'0xc9e40c','member_offset':0x1070,
            'scope':'Owner pseudocode gives member expression; original BL confirms callee. Constructor not executed.'}
    (ROOT/'output/mechanics'/args.output).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'bindings':len(bindings),'cpp_agree':sum(b['cpp_store_agrees']for b in bindings),'accesses':len(accesses),
         'gravity_accesses':[a for a in accesses if 'Gravity' in a['parameter']]}),flush=True)

if __name__=='__main__':main()
