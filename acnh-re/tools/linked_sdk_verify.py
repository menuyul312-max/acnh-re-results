#!/usr/bin/env python3
"""Resolve the actual main->SDK strcmp import and rerun the BYML evidence."""
import hashlib
import json
from pathlib import Path
import struct

from exefs_modules import NsoModule,DEFAULT_INPUT
from native_byml_verify import ReaderSandbox,build as verify_byml,strcmp_bytes
from native_emulator import regs
from reverse_corpus import dump
from unicorn import UC_HOOK_CODE

ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/'output'


class LinkedSdkReader(ReaderSandbox):
    SDK_BASE=0x70000000

    def __init__(self):
        super().__init__(substitute_strcmp=False)
        sdk=NsoModule((DEFAULT_INPUT/'sdk').read_bytes())
        symbol=next(s for s in sdk.symbols if s['name']=='strcmp'and s['section'])
        self.sdk_strcmp=self.SDK_BASE+int(symbol['va'],16)
        text=sdk.segments[0];self.uc.mem_map(self.SDK_BASE+text['va'],(text['size']+4095)&~4095)
        self.uc.mem_write(self.SDK_BASE+text['va'],text['data'])
        main=json.loads((OUT/'native_modules/import_resolution.json').read_text())['main']
        binding=next(b for b in main['bindings']if b['symbol']['name']=='strcmp')
        if len(binding['relocations'])!=1 or binding['relocations'][0]['type']!=1026:raise ValueError('unexpected strcmp relocation')
        site=int(binding['relocations'][0]['site'],16)
        self.uc.mem_write(site,struct.pack('<Q',self.sdk_strcmp))
        self.uc.hook_add(UC_HOOK_CODE,self._observe_strcmp,begin=self.sdk_strcmp,end=self.sdk_strcmp)
        self.linked_module_evidence=dict(module='sdk',module_sha256=hashlib.sha256(sdk.raw).hexdigest(),
            build_id=sdk.build_id,strcmp_module_va=symbol['va'],emulated_module_base=hex(self.SDK_BASE),
            main_got_relocation_site=hex(site),relocation_type='R_AARCH64_JUMP_SLOT',
            linking='Original main PLT reads its GOT; only the imported GOT pointer is resolved. Main/SDK instructions are unchanged.',
            scope='Only SDK text needed by the self-contained strcmp routine is mapped. Other SDK imports, initializers and syscalls are not executed.')
        code=sdk.read(int(symbol['va'],16),0xcc)
        assembly='\n'.join(f'{i.address:08x} {i.bytes.hex():8s} {i.mnemonic:8s} {i.op_str}'for i in self.image.disassembler.disasm(code,int(symbol['va'],16)))+'\n'
        (OUT/'native_modules/sdk_strcmp.asm').write_text(assembly)
        self.linked_module_evidence.update(routine_raw_sha256=hashlib.sha256(code).hexdigest(),assembly='native_modules/sdk_strcmp.asm')

    def _observe_strcmp(self,uc,address,size,user):self.strcmp_calls+=1


def build():
    sandbox=LinkedSdkReader();cases=0;failures=[]
    def check(a,b,oa=0,ob=0):
        nonlocal cases
        pa=sandbox.HEAP+0x1a0000+oa;pb=sandbox.HEAP+0x1b0000+ob
        sandbox.uc.mem_write(pa,a+b'\0');sandbox.uc.mem_write(pb,b+b'\0')
        value=sandbox.integer_call(sandbox.sdk_strcmp,[pa,pb])&0xffffffff
        actual=value-(1<<32)if value&0x80000000 else value
        expected=strcmp_bytes(a,b);cases+=1
        if actual!=expected:failures.append(dict(a_hex=a.hex(),b_hex=b.hex(),offsets=[oa,ob],actual=actual,expected=expected))
    for a in range(256):
        for b in range(256):check(bytes([a]),bytes([b]))
    for oa in range(8):
        for ob in range(8):
            for length in [0,1,2,3,4,7,8,9,15,16,17,31,32,63,64,127,128]:
                prefix=b'x'*length
                check(prefix+b'A',prefix+b'B',oa,ob);check(prefix,prefix,oa,ob)
    check('動物の森'.encode(),'動物の森'.encode());check(b'\xff'*4096,b'\xff'*4095+b'\xfe')
    direct=dict(comparisons=cases,mismatches=failures,dependencies_stubbed=[],linked_module=sandbox.linked_module_evidence,
        scope='Actual SDK strcmp executed on every byte pair, aligned/unaligned prefixes, UTF-8, long strings. Input buffers are NUL terminated inside mapped memory.')
    dump(OUT/'native_modules/strcmp_native_verification.json',direct)
    if failures:raise ValueError(('original SDK strcmp mismatch',failures[:5]))
    sandbox.strcmp_calls=0
    result=verify_byml(sandbox,'native_modules/linked_byml_verification.json')
    if result['strcmp_calls']!=84560:raise ValueError('native SDK strcmp did not traverse the expected BYML calls')
    print(json.dumps(dict(sdk_strcmp_comparisons=cases,linked_byml_comparisons=result['comparisons'],
        actual_sdk_strcmp_calls=result['strcmp_calls'],dependencies_stubbed=[]),indent=2))


if __name__=='__main__':build()
