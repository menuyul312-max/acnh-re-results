#!/usr/bin/env python3
"""Validate supplied NSO modules and resolve symbols, without running a game."""
import collections
import ctypes
import ctypes.util
import hashlib
import json
from pathlib import Path
import struct
import sys

from native_image import Image
from reverse_corpus import dump

ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/'output'
DEFAULT_INPUT=ROOT/'inputs/additional_exefs'


def sha(data):return hashlib.sha256(data).hexdigest()


class NsoModule:
    def __init__(self,raw):
        self.raw=raw
        if len(raw)<256 or raw[:4]!=b'NSO0':raise ValueError('invalid NSO0 header')
        self.flags=struct.unpack_from('<I',raw,12)[0]
        self.build_id=raw[0x40:0x60].hex();self.segments=[]
        library=ctypes.util.find_library('lz4')
        if not library:raise ValueError('liblz4 required to decompress the supplied NSO segments')
        self._lz4=ctypes.CDLL(library);decompress=self._lz4.LZ4_decompress_safe
        decompress.argtypes=[ctypes.c_void_p,ctypes.c_void_p,ctypes.c_int,ctypes.c_int];decompress.restype=ctypes.c_int
        for i,(name,offset) in enumerate([('text',0x10),('rodata',0x20),('data',0x30)]):
            file_offset,va,size=struct.unpack_from('<III',raw,offset)
            compressed=bool(self.flags&(1<<i));stored_size=struct.unpack_from('<I',raw,0x60+i*4)[0]if compressed else size
            if size>128*1024*1024 or file_offset<256 or file_offset+stored_size>len(raw):raise ValueError('NSO segment bounds')
            stored=raw[file_offset:file_offset+stored_size]
            if compressed:
                source=ctypes.create_string_buffer(stored);target=ctypes.create_string_buffer(size)
                count=decompress(source,target,stored_size,size)
                if count!=size:raise ValueError('NSO LZ4 decompressed size mismatch')
                data=target.raw
            else:data=stored
            expected=raw[0xa0+i*32:0xc0+i*32].hex();hashed=bool(self.flags&(1<<(i+3)))
            if hashed and sha(data)!=expected:raise ValueError(('NSO segment SHA-256 mismatch',name))
            self.segments.append(dict(name=name,va=va,size=size,file_offset=file_offset,stored_size=stored_size,
                compressed=compressed,sha256=sha(data),header_hash_verified=hashed,data=data))
        self.bss_size=struct.unpack_from('<I',raw,0x3c)[0]
        self.mod0=struct.unpack('<I',self.read(4,4))[0]
        if self.read(self.mod0,4)!=b'MOD0':raise ValueError('missing MOD0')
        self.dynamic_va=self.mod0+struct.unpack('<i',self.read(self.mod0+4,4))[0]
        self.dynamic=[]
        for offset in range(0,65536,16):
            tag,value=struct.unpack('<qQ',self.read(self.dynamic_va+offset,16));self.dynamic.append((tag,value))
            if tag==0:break
        else:raise ValueError('unterminated dynamic table')
        self.tags=dict(self.dynamic)
        self.strings=self.read(self.tags[5],self.tags[10])
        if self.tags.get(11)!=24:raise ValueError('unexpected AArch64 symbol size')
        self.symbol_count=struct.unpack('<II',self.read(self.tags[4],8))[1]
        if struct.unpack_from('<I',raw,0x9c)[0]!=self.symbol_count*24:raise ValueError('NSO/dynamic symbol counts differ')
        self.symbols=[]
        for i in range(self.symbol_count):
            name,info,visibility,section,va,size=struct.unpack('<IBBHQQ',self.read(self.tags[6]+i*24,24))
            self.symbols.append(dict(index=i,name=self.string(name),binding=info>>4,type=info&15,
                visibility=visibility&3,section=section,va=hex(va),size=size))
        self.needed=[self.string(v)for t,v in self.dynamic if t==1]
        self.soname=self.string(self.tags[14])if 14 in self.tags else None
        self.references=collections.defaultdict(list);self.relocation_types=collections.Counter()
        regions=[]
        if 7 in self.tags:regions.append((self.tags[7],self.tags.get(8,0),self.tags.get(9)))
        if 23 in self.tags:
            if self.tags.get(20)!=7:raise ValueError('expected AArch64 RELA PLT')
            regions.append((self.tags[23],self.tags.get(2,0),24))
        seen=set()
        for base,size,stride in regions:
            if stride!=24 or size%24:raise ValueError('invalid RELA span')
            for offset in range(0,size,24):
                if base+offset in seen:continue
                seen.add(base+offset);site,info,addend=struct.unpack('<QQq',self.read(base+offset,24));symbol=info>>32;kind=info&0xffffffff
                if symbol>=len(self.symbols):raise ValueError('relocation symbol index out of range')
                self.relocation_types[kind]+=1
                if symbol:self.references[symbol].append(dict(site=hex(site),type=kind,addend=addend))

    def read(self,va,size):
        if size<0:raise ValueError('negative virtual read')
        for segment in self.segments:
            offset=va-segment['va']
            if 0<=offset and offset+size<=segment['size']:return segment['data'][offset:offset+size]
        raise ValueError(('NSO virtual read outside file-backed segments',hex(va),size))

    def string(self,offset):
        if not 0<=offset<len(self.strings):raise ValueError('dynamic string offset')
        end=self.strings.find(b'\0',offset)
        if end<0:raise ValueError('unterminated dynamic string')
        return self.strings[offset:end].decode('utf-8',errors='strict')


def npdm_info(raw):
    if len(raw)<128 or raw[:4]!=b'META':raise ValueError('invalid NPDM')
    aci,aci_size,acid,acid_size=struct.unpack_from('<4I',raw,0x70)
    if aci+aci_size>len(raw)or acid+acid_size>len(raw)or raw[aci:aci+4]!=b'ACI0'or raw[acid+512:acid+516]!=b'ACID':
        raise ValueError('NPDM descriptor bounds/magic')
    return dict(size=len(raw),sha256=sha(raw),program_id=f'{struct.unpack_from("<Q",raw,aci+0x10)[0]:016x}',
        acid_program_id_min=f'{struct.unpack_from("<Q",raw,acid+0x210)[0]:016x}',
        acid_program_id_max=f'{struct.unpack_from("<Q",raw,acid+0x218)[0]:016x}',
        aci0_offset=aci,acid_offset=acid,acid_signature_and_public_key_range=[acid,acid+512])


def build(directory=DEFAULT_INPUT):
    directory=Path(directory);modules={name:NsoModule((directory/name).read_bytes())for name in ['rtld','main','subsdk0','sdk']}
    exports=collections.defaultdict(list)
    for module,parsed in modules.items():
        for symbol in parsed.symbols:
            if symbol['name']and symbol['section']and symbol['binding']in [1,2]and symbol['visibility']in [0,3]:
                exports[symbol['name']].append(dict(module=module,**symbol))
    resolution={};catalogue=[];im=Image();segment_comparison=[]
    for module,parsed in modules.items():
        bindings=[]
        for symbol in parsed.symbols:
            if not symbol['name']or symbol['section']:continue
            candidates=[r for r in exports.get(symbol['name'],[])if r['module']!=module]
            bindings.append(dict(symbol=symbol,export_candidates=candidates,relocations=parsed.references.get(symbol['index'],[]),
                status='unique_export_match'if len(candidates)==1 else'ambiguous_export_match'if candidates else'no_export_match'))
        resolution[module]=dict(imports=len(bindings),with_export_candidate=sum(bool(r['export_candidates'])for r in bindings),
            unique_export_matches=sum(r['status']=='unique_export_match'for r in bindings),
            unresolved=[r for r in bindings if not r['export_candidates']],bindings=bindings,
            interpretation='Static name resolution; relocation application, load order, TLS, initialization and syscall runtime are separate work.')
        segments=[{k:v for k,v in s.items()if k!='data'}for s in parsed.segments]
        doc=dict(module=module,input_file=str(directory/module),input_sha256=sha(parsed.raw),input_bytes=len(parsed.raw),
            format='NSO0',build_id=parsed.build_id,mod0_va=hex(parsed.mod0),dynamic_va=hex(parsed.dynamic_va),
            soname=parsed.soname,needed=parsed.needed,bss_size=parsed.bss_size,segments=segments,
            symbol_count=len(parsed.symbols),symbols=parsed.symbols,
            exported_symbols=sum(bool(s['name']and s['section']and s['binding']in [1,2]and s['visibility']in [0,3])for s in parsed.symbols),
            relocation_types={str(k):v for k,v in sorted(parsed.relocation_types.items())},
            address_contract='VA relative to this module; do not combine with main ELF addresses without load-base relocation.')
        path=f'native_modules/{module}.json';dump(OUT/path,doc)
        catalogue.append({k:doc[k]for k in ['module','input_sha256','input_bytes','build_id','soname','needed','symbol_count','exported_symbols']})
        catalogue[-1]['json']=path
        if module=='main':
            for segment in parsed.segments:
                existing=im.read(segment['va'],segment['size']);same=existing==segment['data']
                segment_comparison.append(dict(name=segment['name'],va=hex(segment['va']),bytes=segment['size'],
                    nso_sha256=segment['sha256'],previous_elf_sha256=sha(existing),exact_match=same))
            if not all(s['exact_match']for s in segment_comparison):raise ValueError('uploaded main is not the previously verified native image')
    npdm=(directory/'main.npdm').read_bytes();old_path=Path(json.loads((OUT/'manifest.json').read_text())['source_root'])/'A_logic/main.npdm'
    previous=old_path.read_bytes();npdm_record=npdm_info(npdm);old_info=npdm_info(previous)
    differences=[i for i,(a,b)in enumerate(zip(previous,npdm))if a!=b]
    start,end=npdm_record['acid_signature_and_public_key_range']
    comparison=dict(uploaded=npdm_record,previous=old_info,exact_match=npdm==previous,
        equal_size=len(npdm)==len(previous),differing_byte_count=len(differences),
        changes_confined_to_acid_signature_and_public_key=len(npdm)==len(previous)and all(start<=i<end for i in differences),
        remaining_bytes_identical=previous[:start]+previous[end:]==npdm[:start]+npdm[end:],
        signature_validation='Cryptographic signatures not verified; descriptor comparison only.')
    dump(OUT/'native_modules/npdm_comparison.json',comparison)
    dump(OUT/'native_modules/import_resolution.json',resolution)
    main=resolution['main'];unresolved=main['unresolved']
    result=dict(additional_input_root=str(directory),catalogue=catalogue,
        segment_hashes_verified=sum(s['header_hash_verified']for m in modules.values()for s in m.segments),
        main_segment_comparison=segment_comparison,main_matches_previous_elf=all(s['exact_match']for s in segment_comparison),
        npdm_program_id_match=npdm_record['program_id']==old_info['program_id'],
        main_imports=main['imports'],main_imports_with_export_candidate=main['with_export_candidate'],
        main_imports_without_export_candidate=[dict(name=r['symbol']['name'],binding=r['symbol']['binding'],
            relocation_count=len(r['relocations']))for r in unresolved],
        symbols_all_modules=sum(len(m.symbols)for m in modules.values()),
        scope='Validated/decompressed NSO files, dynamic symbols and static import resolution. Original SDK/multimedia module bytes are now supplied; full game/OS execution is not claimed.',
        missing_romfs_assets='These ExeFS modules do not supply missing model, animation, waveform, VFX, shader or Havok archives.',
        originals_bundled=False)
    dump(OUT/'native_modules/summary.json',result)
    print(json.dumps({k:v for k,v in result.items()if k!='catalogue'},indent=2))


if __name__=='__main__':build(sys.argv[1]if len(sys.argv)>1 else DEFAULT_INPUT)
