#!/usr/bin/env python3
"""Check the runner's ExitFlowchart special path without running the game."""
import json
import hashlib
from pathlib import Path
import struct
from native_emulator import Sandbox
from reverse_corpus import dump

ROOT = Path(__file__).resolve().parent.parent


def build():
    s = Sandbox()
    obj, owner, runtime, vt, method, text, builtin = [s.HEAP+n for n in
        [0,0x1000,0x2000,0x3000,0x4000,0x5000,0x6000]]
    q = lambda addr,value: s.uc.mem_write(addr,struct.pack('<Q',value))
    # The SafeString virtual callback only assures its string terminator in this
    # path. Use already-terminated bounded strings and a RET stub for that callback.
    s.uc.mem_write(method,bytes.fromhex('c0035fd6'))
    q(vt+0x18,method)
    q(obj+8,vt); q(obj+0x10,text); q(obj+0x48,owner); q(owner+0x288,runtime)
    q(0x34181f0,vt); q(0x34181f8,builtin)
    s.uc.mem_write(builtin,b'EventFlowActionExitFlowchart\0')
    checks = []
    for name in ['EventFlowActionExitFlowchart','EventFlowActionWaitFrame','EventFlowActionDummy',
                 'EventFlowActionExitFlowchartSuffix','']:
        for mode in [0,1]:
            s.uc.mem_write(text,name.encode()+b'\0')
            s.uc.mem_write(runtime+0x26,bytes([mode]))
            got = s.call(0x4474e0,[obj]) & 0xffffffff
            expected = int(not mode and name != 'EventFlowActionExitFlowchart')
            checks.append({'name':name,'runtime_flag':mode,'native':got,'expected':expected})
    s.uc.mem_write(text,b'EventFlowActionExitFlowchart\0')
    s.uc.mem_write(runtime+0x26,b'\0')
    s.uc.mem_write(obj+0x50,b'\0')
    returned = s.call(0x447060,[obj,0,obj+0x18]) & 0xffffffff
    done = bytes(s.uc.mem_read(obj+0x50,1))[0]
    result = {'native_elf_sha256':hashlib.sha256(s.image.data).hexdigest(),
        'initializer_va':'0x446800', 'name_object_va':'0x34181f0',
        'predicate_va':'0x4474e0','start_va':'0x447060','poll_va':'0x447620',
        'predicate_checks':checks, 'start_check':{'return':returned,'completion_byte_at_0x50':done},
        'stubbed_dependency':'SafeString terminator callback only; all strings explicitly terminated',
        'mismatches':sum(r['native']!=r['expected'] for r in checks)+int(returned!=1 or done!=1)}
    dump(ROOT/'output/binary/exit_flowchart_verification.json',result)
    print(json.dumps(result,indent=2))
    if result['mismatches']:raise SystemExit(1)


if __name__ == '__main__': build()
