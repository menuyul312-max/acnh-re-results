#!/usr/bin/env python3
"""Compare every physical BYML entry with the original native index reader.

The absent SDK strcmp implementation is the sole substituted dependency. The
constructor, header validation, node count, lookup, tags and words are native.
"""
import collections
import hashlib
import json
from pathlib import Path
import struct

from native_emulator import Sandbox,regs
from reverse_corpus import dump
from typed_byml import TYPES
from unicorn import UC_HOOK_CODE

ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/'output'
TAGS={name:tag for tag,name in TYPES.items()}


def strcmp_bytes(a,b):
    for x,y in zip(a+b'\0',b+b'\0'):
        if x!=y:return x-y
    return 0


class ReaderSandbox(Sandbox):
    CONSTRUCTOR=0x1ef43f0
    COUNT=0x1ef45c0
    BY_INDEX=0x1ef4610
    BY_NAME=0x1ef46c0
    STRCMP_PLT=0x220f030

    def __init__(self,substitute_strcmp=True):
        super().__init__()
        self.raw_base=self.HEAP+0x10000
        self.iterator=self.HEAP
        self.data_out=self.HEAP+0x1000
        self.key_pointer=self.HEAP+0x2000
        self.string_cache={};self.query=b'';self.raw_size=0;self.strcmp_calls=0
        self.substitute_strcmp=substitute_strcmp
        if substitute_strcmp:self.uc.hook_add(UC_HOOK_CODE,self._strcmp,begin=self.STRCMP_PLT,end=self.STRCMP_PLT)

    def _string(self,address):
        if address==self.key_pointer:return self.query
        if address in self.string_cache:return self.string_cache[address]
        if self.raw_base<=address<self.raw_base+self.raw_size:
            size=self.raw_base+self.raw_size-address
        else:
            size=4096
        value=bytearray()
        for offset in range(0,size,256):
            chunk=bytes(self.uc.mem_read(address+offset,min(256,size-offset)))
            end=chunk.find(b'\0')
            if end>=0:
                value.extend(chunk[:end]);result=bytes(value)
                self.string_cache[address]=result;return result
            value.extend(chunk)
        raise ValueError(('unterminated strcmp input',hex(address)))

    def _strcmp(self,uc,address,size,user):
        a=self._string(uc.reg_read(regs.UC_ARM64_REG_X0))
        b=self._string(uc.reg_read(regs.UC_ARM64_REG_X1))
        value=strcmp_bytes(a,b)
        uc.reg_write(regs.UC_ARM64_REG_X0,value&((1<<64)-1))
        uc.reg_write(regs.UC_ARM64_REG_PC,uc.reg_read(regs.UC_ARM64_REG_X30))
        self.strcmp_calls+=1

    def integer_call(self,va,args=(),limit=100000):
        # These integer-only entry points have no hidden return pointer or FP
        # arguments. Preserve ordinary AAPCS caller-clobbered register contents;
        # pass only the declared args. Instruction count bounds every call.
        for i,value in enumerate(args):
            self.uc.reg_write(getattr(regs,f'UC_ARM64_REG_X{i}'),value&((1<<64)-1))
        self.uc.reg_write(regs.UC_ARM64_REG_SP,self.STACK+0x1ff000)
        self.uc.reg_write(regs.UC_ARM64_REG_X30,self.STOP)
        self.uc.emu_start(va,self.STOP,count=limit)
        pc=self.uc.reg_read(regs.UC_ARM64_REG_PC)
        if pc!=self.STOP:raise ValueError(('bounded native BYML call did not return',hex(va),hex(pc)))
        return self.uc.reg_read(regs.UC_ARM64_REG_X0)

    def load(self,raw):
        if len(raw)>0x1f0000:raise ValueError('BYML exceeds isolated heap')
        self.raw_size=len(raw);self.string_cache.clear()
        self.uc.mem_write(self.raw_base,raw)
        self.integer_call(self.CONSTRUCTOR,[self.iterator,self.raw_base],limit=1000000)
        return struct.unpack('<QQ',bytes(self.uc.mem_read(self.iterator,16)))

    def at_node(self,offset):
        self.uc.mem_write(self.iterator,struct.pack('<QQ',self.raw_base,self.raw_base+offset))

    def lookup(self,key):
        self.query=key.encode()
        self.uc.mem_write(self.key_pointer,self.query+b'\0')
        return self.integer_call(self.BY_NAME,[self.iterator,self.data_out,self.key_pointer])&1


def build(sandbox=None,destination='byml_typed/native_verification.json'):
    sandbox=sandbox or ReaderSandbox();counts=collections.Counter();failures=[];files=[]
    vocabulary=set();data_abi=set();root_abi=set()
    def check(group,got,expected,context):
        counts[group]+=1
        if got!=expected:
            failures.append({'group':group,'native':got,'expected':expected,**context})
            if len(failures)>100:raise ValueError(('native BYML systematic mismatch',failures[:3]))
    catalogue=json.loads((OUT/'byml_typed/catalogue.json').read_text())
    for file_index,record in enumerate(catalogue):
        graph=json.loads((OUT/record['json']).read_text());raw=(OUT/graph['raw']['$blob']).read_bytes()
        source_id=graph['source_id'];base,root=sandbox.load(raw)
        wanted_root=sandbox.raw_base+graph['root_offset'] if graph['root_offset'] else 0
        context={'source_id':source_id}
        check('constructor_base',base,sandbox.raw_base,context)
        check('constructor_root',root,wanted_root,context)
        if base!=sandbox.raw_base or root!=wanted_root:
            files.append({**record,'native_constructor_accepted':False});continue
        local=collections.Counter();before=sandbox.strcmp_calls
        for node in graph['nodes']:
            sandbox.at_node(node['offset']);context={'source_id':source_id,'node_offset':node['offset']}
            check('container_count',sandbox.integer_call(sandbox.COUNT,[sandbox.iterator]),node['count'],context)
            for index,entry in enumerate(node['entries']):
                value=entry['value'] if node['type']=='dict' else entry
                tag=TAGS[value['type']];offset=value['word_offset']
                # Native 0x1ef5cf0 normalizes the u32 word before storing it,
                # then writes tag at +4. Bytes +5..7 are unused ABI padding.
                word=int.from_bytes(raw[offset:offset+4],graph['endianness'])
                expected=struct.pack('<I',word)+bytes([tag])
                sandbox.uc.mem_write(sandbox.data_out,b'\xcd'*16)
                got=sandbox.integer_call(sandbox.BY_INDEX,[sandbox.iterator,sandbox.data_out,index])&1
                detail={**context,'entry_index':index,'word_offset':offset}
                check('entry_index_found',got,1,detail)
                actual=bytes(sandbox.uc.mem_read(sandbox.data_out,16))
                check('entry_tag_word',actual[:5].hex(),expected.hex(),detail)
                check('entry_output_guard',actual[8:].hex(),(b'\xcd'*8).hex(),detail)
                local[node['type']+'_entries']+=1
                if (tag,graph['endianness']) not in data_abi:
                    data_abi.add((tag,graph['endianness']))
                    check('tag_accessor',sandbox.integer_call(0x1ef5d10,[sandbox.data_out])&255,tag,detail)
                    expected_word=int.from_bytes(raw[offset:offset+4],graph['endianness'])
                    check('word_accessor',sandbox.integer_call(0x1ef5d20,[sandbox.data_out])&0xffffffff,expected_word,detail)
                if node['type']=='dict':
                    key=entry['key'];identity=(key,tag,graph['endianness'])
                    if identity not in vocabulary:
                        vocabulary.add(identity)
                        check('name_lookup_found',sandbox.lookup(key),1,{**detail,'key':key})
                        actual=bytes(sandbox.uc.mem_read(sandbox.data_out,5))
                        check('name_lookup_value',actual.hex(),expected.hex(),{**detail,'key':key})
                        local['name_probes']+=1
            # Probe both invalid upper boundary and unsigned -1 once per file
            # and container kind; all actual entries above are still checked.
            boundary_identity=(source_id,node['type'])
            if boundary_identity not in root_abi:
                root_abi.add(boundary_identity)
                for bad in [node['count'],0xffffffff]:
                    result=sandbox.integer_call(sandbox.BY_INDEX,[sandbox.iterator,sandbox.data_out,bad])&1
                    if node['type']=='array':
                        check('array_invalid_index_rejected',result,0,{**context,'index':bad})
                    else:
                        # 0x1ef63d0 only checks nonempty count. This deliberately
                        # demonstrates the original unchecked dictionary path;
                        # bytes from outside the node are never treated as data.
                        check('dict_unchecked_index_behavior',result,int(node['count']!=0),{**context,'index':bad})
                if node['type']=='dict':
                    check('missing_key_rejected',sandbox.lookup('\x01__acnh_re_missing__'),0,context)
        check('source_memory_unchanged',bytes(sandbox.uc.mem_read(sandbox.raw_base,len(raw)))==raw,True,{'source_id':source_id})
        files.append({**record,'source_sha256':graph['raw']['sha256'],'native_constructor_accepted':True,
            'containers':len(graph['nodes']),**dict(local),'strcmp_calls_after_constructor':sandbox.strcmp_calls-before})
        if (file_index+1)%100==0:
            print(json.dumps({'native_byml_files':file_index+1,'of':len(catalogue),
                'entries':sum(f.get('dict_entries',0)+f.get('array_entries',0)for f in files),
                'mismatches':len(failures)}),flush=True)
    result={'native_elf_sha256':hashlib.sha256(sandbox.image.data).hexdigest(),
        'files':len(files),'constructors_accepted':sum(f['native_constructor_accepted']for f in files),
        'physical_dictionary_entries':sum(f.get('dict_entries',0)for f in files),
        'physical_array_entries':sum(f.get('array_entries',0)for f in files),
        'distinct_key_tag_endian_probes':len(vocabulary),'native_tag_endian_combinations':len(data_abi),
        'comparisons':sum(counts.values()),'groups':dict(counts),'mismatches':failures,
        'strcmp_calls':sandbox.strcmp_calls,
        'substituted_dependency':{'name':'strcmp','plt_va':hex(sandbox.STRCMP_PLT),
            'contract':'Unsigned byte comparison through terminating NUL; no game logic is substituted.'}if sandbox.substitute_strcmp else None,
        'dependencies_stubbed':['strcmp']if sandbox.substitute_strcmp else [],
        'dictionary_index_contract':{'unchecked_helper':'0x1ef63d0',
            'behavior':'Direct dictionary by-index read checks nonempty count but not index bounds. Callers must validate indices.',
            'checked_helper':'0x1ef6510','name_lookup':'0x1ef46c0 uses checked dictionary entries during binary search.'},
        'scope':'All physical BYML graph entries are read by native index lookup; all observed key/tag pairs also have a native name lookup. Counts are physical entries, not expanded shared-tree occurrences.',
        'addresses':{'constructor':hex(sandbox.CONSTRUCTOR),'count':hex(sandbox.COUNT),
            'index_lookup':hex(sandbox.BY_INDEX),'name_lookup':hex(sandbox.BY_NAME)},
        'file_results':files}
    if hasattr(sandbox,'linked_module_evidence'):result['linked_module']=sandbox.linked_module_evidence
    dump(OUT/destination,result)
    print(json.dumps({k:v for k,v in result.items()if k not in ['file_results','mismatches']},indent=2))
    if failures:raise ValueError(('native BYML mismatches',failures[:5]))
    return result


if __name__=='__main__':build()
