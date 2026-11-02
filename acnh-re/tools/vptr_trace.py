"""Track constructor stores to the outer object, including pointer offsets.

This avoids treating writes to embedded SafeString objects as outer vptr stores.
It is bounded static propagation, not execution or a full control-flow proof.
"""
from capstone.arm64 import ARM64_OP_REG,ARM64_OP_IMM,ARM64_OP_MEM


def trace(image,va,limit=2048):
    values={'x0':('this',0)};stores=[]
    def regname(ins,reg):
        name=ins.reg_name(reg)
        if name.startswith('w') and name[1:].isdigit():return 'x'+name[1:]
        return name
    def value(ins,operand):
        if operand.type==ARM64_OP_IMM:return operand.imm
        if operand.type==ARM64_OP_REG:
            if ins.reg_name(operand.reg) in ('xzr','wzr'):return 0
            return values.get(regname(ins,operand.reg))
        return None
    def plus(v,n):
        if isinstance(v,int):return v+n
        if isinstance(v,tuple):return (v[0],v[1]+n)
        return None
    for ins in image.disasm(va,limit*4):
        op,operands=ins.mnemonic,ins.operands
        _,written=ins.regs_access()
        assigned={regname(ins,r):None for r in written}
        if op in ('mov','adr','adrp') and len(operands)>=2:
            assigned[regname(ins,operands[0].reg)]=value(ins,operands[1])
        elif op in ('add','sub') and len(operands)>=3 and operands[2].type==ARM64_OP_IMM:
            amount=operands[2].imm << operands[2].shift.value
            assigned[regname(ins,operands[0].reg)]=plus(value(ins,operands[1]),amount if op=='add' else -amount)
        elif op in ('ldr','ldur') and len(operands)>=2 and operands[1].type==ARM64_OP_MEM:
            mem=operands[1].mem
            if not mem.index:
                address=plus(values.get(regname(ins,mem.base)),mem.disp)
                if isinstance(address,int) and ins.reg_name(operands[0].reg).startswith('x'):
                    try:assigned[regname(ins,operands[0].reg)]=image.ptr(address)
                    except ValueError:pass
        elif op in ('str','stur','stp'):
            memop=next((o for o in operands if o.type==ARM64_OP_MEM),None)
            if memop is not None and not memop.mem.index:
                address=plus(values.get(regname(ins,memop.mem.base)),memop.mem.disp)
                sources=[o for o in operands if o.type==ARM64_OP_REG]
                for i,source in enumerate(sources):
                    target=plus(address,8*i)
                    val=value(ins,source)
                    if target==('this',0) and isinstance(val,int):
                        stores.append({'pc':hex(ins.address),'vtable':val,'instruction':op+' '+ins.op_str})
        elif op in ('bl','blr'):
            for i in range(19):assigned['x'+str(i)]=None
        # Writing a W register zero-extends the physical X register; a pointer
        # alias cannot survive truncation to 32 bits.
        if operands and operands[0].type==ARM64_OP_REG and ins.reg_name(operands[0].reg).startswith('w'):
            target=regname(ins,operands[0].reg)
            if target in assigned and isinstance(assigned[target],tuple):assigned[target]=None
        for name,v in assigned.items():
            if v is None:values.pop(name,None)
            else:values[name]=v
        if op=='ret':break
    return stores[-1]['vtable'] if stores else None,stores
