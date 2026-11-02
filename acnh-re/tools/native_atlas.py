#!/usr/bin/env python3
"""Index ELF imports and relocated native pointer arrays with evidence bounds."""
import collections
import hashlib
import json
from pathlib import Path
import sqlite3

from native_image import Image
from reverse_corpus import dump

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT/'output'


def build():
    im = Image()
    def executable(va):
        return va%4 == 0 and any(s['p_flags']&1 and s['p_vaddr']<=va<s['p_vaddr']+s['p_filesz'] for s in im.segments)
    symbols = []
    for section in im.elf.iter_sections():
        if section['sh_type'] not in ('SHT_DYNSYM','SHT_SYMTAB'): continue
        for i,sym in enumerate(section.iter_symbols()):
            if not sym.name: continue
            symbols.append({'table':section.name,'index':i,'name':sym.name,'value_va':hex(sym['st_value']),
                'size':sym['st_size'],'type':sym['st_info']['type'],'binding':sym['st_info']['bind'],
                'section':sym['st_shndx'],'undefined':sym['st_shndx']=='SHN_UNDEF'})
    needed = []
    for seg in im.elf.iter_segments():
        if seg['p_type']=='PT_DYNAMIC':
            needed += [t.needed for t in seg.iter_tags() if t.entry.d_tag=='DT_NEEDED']
    dump(OUT/'binary/symbols.json',{'symbols':symbols,'needed_libraries':needed,
        'warning':'Undefined dynamic functions are imports; their implementations are not in the supplied A_logic directory.'})
    pointers = sorted((va,target) for va,target in im.relocations.items() if executable(target))
    groups,group = [],[]
    for va,target in pointers:
        if group and va != group[-1][0]+8:
            groups.append(group);group=[]
        group.append((va,target))
    if group:groups.append(group)
    arrays = [{'start_va':hex(g[0][0]),'entries':[{'pointer_va':hex(va),'target_va':hex(t)} for va,t in g],
               'status':'relocated code pointer sequence; not automatically a C++ vtable'} for g in groups if len(g)>=2]
    dump(OUT/'binary/code_pointer_arrays.json',arrays)
    result = {'elf_sha256':hashlib.sha256(im.data).hexdigest(),'symbols':len(symbols),
        'undefined_symbols':sum(s['undefined'] for s in symbols),'needed_libraries':needed,
        'relative_relocations':len(im.relocations),'relocated_code_pointers':len(pointers),
        'code_pointer_arrays':len(arrays),'distinct_relocated_code_targets':len({p for _,p in pointers})}
    dump(OUT/'binary/native_atlas_summary.json',result)
    print(json.dumps(result,indent=2))


if __name__ == '__main__': build()
