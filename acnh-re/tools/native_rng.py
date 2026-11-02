#!/usr/bin/env python3
"""Specify and compare the supplied native sead-style integer random generator."""
import collections
import hashlib
import json
from pathlib import Path
import random
import struct

from native_byml_verify import ReaderSandbox
from reverse_corpus import dump

ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/'output'
MASK=0xffffffff


def initialize(seed):
    state=[];value=seed&MASK
    for increment in range(1,5):
        value=((value^(value>>30))*0x6c078965+increment)&MASK
        state.append(value)
    return state


def roll(state):
    a,b,c,d=state
    n=(a^(a<<11))&MASK
    value=(n^(n>>8)^d^(d>>19))&MASK
    return value,[b,c,d,value]


def set_state(state):return list(state)if any(state)else initialize(0)


def build():
    s=ReaderSandbox();rng=random.Random(0xac100);p=s.HEAP
    counts=collections.Counter();failures=[]
    def check(group,actual,expected,context):
        counts[group]+=1
        if actual!=expected:failures.append({'group':group,'native':actual,'expected':expected,**context})
    seeds=[0,1,2,0x7fffffff,0x80000000,0xffffffff,0xdeadbeef,
           *[rng.getrandbits(32)for _ in range(1024)]]
    for seed in seeds:
        state=initialize(seed);s.integer_call(0x19aa040,[p,seed])
        check('seed_expansion',list(struct.unpack('<4I',bytes(s.uc.mem_read(p,16)))),state,{'seed':seed})
        for step in range(16):
            value,state=roll(state);actual=s.integer_call(0x19aa0e0,[p])&MASK
            check('next_u32',actual,value,{'seed':seed,'step':step})
            check('next_u32_state',list(struct.unpack('<4I',bytes(s.uc.mem_read(p,16)))),state,{'seed':seed,'step':step})
    states=[[0,0,0,0],[MASK]*4,*[[1<<bit if i==word else 0 for i in range(4)]for word in range(4)for bit in range(32)],
            *[[rng.getrandbits(32)for _ in range(4)]for _ in range(256)]]
    for original in states:
        state=set_state(original);s.integer_call(0x19aa090,[p,*original])
        check('explicit_state',list(struct.unpack('<4I',bytes(s.uc.mem_read(p,16)))),state,{'input_state':original})
        first,state=roll(state);second,state=roll(state)
        native=s.integer_call(0x19aa110,[p])
        expected=(first<<32)|second
        check('next_u64',f'{native:016x}',f'{expected:016x}',{'input_state':original})
        check('next_u64_state',list(struct.unpack('<4I',bytes(s.uc.mem_read(p,16)))),state,{'input_state':original})
        s.uc.mem_write(p+0x100,b'\xcd'*32)
        s.integer_call(0x19aa150,[p,*[p+0x108+i*4 for i in range(4)]])
        check('state_export',bytes(s.uc.mem_read(p+0x100,32)).hex(),
              (b'\xcd'*8+struct.pack('<4I',*state)+b'\xcd'*8).hex(),{'input_state':original})
    if s.strcmp_calls:raise ValueError('integer RNG unexpectedly called the substituted string dependency')
    result={'native_elf_sha256':hashlib.sha256(s.image.data).hexdigest(),
        'addresses':{'seed':'0x19aa040','explicit_state':'0x19aa090','u32':'0x19aa0e0','u64':'0x19aa110','export':'0x19aa150'},
        'seed_formula':'s[i] = ((s[i-1] xor (s[i-1] >> 30))*0x6c078965 + i) mod 2^32, i=1..4; initial s[0] is the input seed.',
        'roll_formula':'n = a xor (a << 11); result = n xor (n >> 8) xor d xor (d >> 19), all u32; next state = [b,c,d,result].',
        'u64_contract':'Two consecutive u32 draws: first in high 32 bits, second in low 32 bits.',
        'zero_explicit_state_fallback':initialize(0),
        'public_reference_difference':'MeteoNook Random::with_state directly accepts all-zero state; native 0x19aa090 replaces it with the seed-0 expanded state. Weather with_seed is consistent.',
        'seed_cases':len(seeds),'explicit_state_cases':len(states),'comparisons':sum(counts.values()),
        'groups':dict(counts),'mismatches':failures,'dependencies_stubbed':[],
        'scope':'Isolated integer RNG only. SDK tick-seeded constructor and all gameplay-specific draw ordering are outside this verification.',
        'reference':{'url':'https://github.com/Treeki/MeteoNook/blob/a7ea07aa9b3db8859b0f476c549a1a2245ad1b07/src/lib.rs',
            'license':'AGPL-3.0','use':'Algorithm comparison; implementation here transcribes the supplied native instructions.'}}
    dump(OUT/'random/native_rng.json',result)
    print(json.dumps({k:v for k,v in result.items()if k not in ['groups','mismatches']},indent=2))
    if failures:raise ValueError(('native RNG mismatch',failures[:5]))


if __name__=='__main__':build()
