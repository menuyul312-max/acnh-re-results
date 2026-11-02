"""Resolve supplied module relocations for isolated native helper execution.

This is a bounded analysis harness, not a replacement for the console loader or
OS. It maps file/BSS segments and resolves supported ELF relocation kinds. No
module constructors, TLS setup or OS services are synthesized.
"""
import collections
import hashlib
import struct

from exefs_modules import NsoModule,DEFAULT_INPUT
from native_byml_verify import ReaderSandbox
from native_emulator import regs
from unicorn import UC_HOOK_INTR


def relocations(module):
    tags=module.tags;regions=[];seen=set()
    if 7 in tags:regions.append((tags[7],tags.get(8,0)))
    if 23 in tags:regions.append((tags[23],tags.get(2,0)))
    for base,size in regions:
        for offset in range(0,size,24):
            if base+offset in seen:continue
            seen.add(base+offset)
            site,info,addend=struct.unpack('<QQq',module.read(base+offset,24))
            yield site,info&0xffffffff,info>>32,addend


class ModuleSandbox(ReaderSandbox):
    BASES=dict(main=0,sdk=0x70000000,subsdk0=0x80000000,rtld=0x90000000)

    def __init__(self):
        super().__init__(substitute_strcmp=False)
        self.modules={name:NsoModule((DEFAULT_INPUT/name).read_bytes())for name in self.BASES}
        for name,module in self.modules.items():
            if name=='main':continue
            base=self.BASES[name]
            for segment in module.segments:
                extra=module.bss_size if segment['name']=='data'else 0
                self.uc.mem_map(base+segment['va'],(segment['size']+extra+4095)&~4095)
                self.uc.mem_write(base+segment['va'],segment['data'])
        self.exports=collections.defaultdict(list)
        for name,module in self.modules.items():
            for symbol in module.symbols:
                if symbol['name']and symbol['section']and symbol['binding']in [1,2]and symbol['visibility']in [0,3]:
                    self.exports[symbol['name']].append((name,symbol))
        self.relocation_counts={};self.weak_unresolved=[];self.applied=[]
        for name,module in self.modules.items():
            counts=collections.Counter();base=self.BASES[name]
            for site,kind,index,addend in relocations(module):
                if kind==1027:value=base+addend
                elif kind in [257,1025,1026]:
                    symbol=module.symbols[index]
                    if symbol['section']:address=self.symbol_address(name,symbol)
                    elif not symbol['name']:address=0
                    else:
                        candidates=self.exports.get(symbol['name'],[])
                        strong=[c for c in candidates if c[1]['binding']==1]
                        if len(strong)==1:candidates=strong
                        if not candidates:
                            if symbol['binding']!=2:raise ValueError(('unresolved strong symbol',name,symbol['name']))
                            address=0;self.weak_unresolved.append(dict(module=name,symbol=symbol['name'],site=hex(site),type=kind))
                        elif len(candidates)==1:address=self.symbol_address(*candidates[0])
                        else:raise ValueError(('ambiguous symbol binding',name,symbol['name']))
                    value=address+addend
                else:raise ValueError(('unsupported relocation type',name,kind))
                value&=(1<<64)-1
                self.uc.mem_write(base+site,struct.pack('<Q',value));counts[kind]+=1
                self.applied.append((name,site,kind,value))
            self.relocation_counts[name]=dict(counts)
        self.os_calls=[]
        self.uc.hook_add(UC_HOOK_INTR,self._unsupported_os)

    def symbol_address(self,module,symbol):
        return int(symbol['va'],16)+(0 if symbol['section']==0xfff1 else self.BASES[module])

    def exported(self,name,module='sdk'):
        found=[s for s in self.modules[module].symbols if s['name']==name and s['section']]
        if len(found)!=1:raise ValueError(('export not unique',module,name))
        return self.symbol_address(module,found[0])

    def _unsupported_os(self,uc,number,user):
        item=dict(interrupt=number,pc=hex(uc.reg_read(regs.UC_ARM64_REG_PC)))
        self.os_calls.append(item)
        raise RuntimeError(('OS service reached; no substitute is installed',item))

    def evidence(self):
        return dict(module_bases={k:hex(v)for k,v in self.BASES.items()},
            input_sha256={k:hashlib.sha256(v.raw).hexdigest()for k,v in self.modules.items()},
            relocations_applied={k:{str(t):n for t,n in v.items()}for k,v in self.relocation_counts.items()},
            weak_zero_bindings=self.weak_unresolved,unsupported_os_calls=self.os_calls,
            initializers_executed=False,tls_initialized=False,dependencies_stubbed=[],
            scope='Supported relocations for isolated helper execution; full loader/OS initialization is not claimed.')
