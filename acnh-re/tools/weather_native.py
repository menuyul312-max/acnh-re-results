#!/usr/bin/env python3
"""Execute the ordinary-day weather selector with local parameter objects."""
import calendar
import datetime as dt
import hashlib
import json
from pathlib import Path
import random
import struct

from native_byml_verify import ReaderSandbox
from native_emulator import regs
from native_rng import initialize,roll
from reverse_corpus import dump

ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/'output'


def predict(stored_seed,year,month,day,tables):
    mixed=(stored_seed+(year*512+month*32+day)*65536)&0xffffffff
    state=initialize(mixed)
    for _ in range(3):value,state=roll(state)
    slot=(value*100)>>32
    table=next(t for t in tables if (month,day)<=(t['end_month'],t['end_day']))
    return table['roll_0_to_99'][slot],state,slot,table['index']


def build(sandbox=None,destination='weather/native_verification.json',full_hours=False):
    s=sandbox or ReaderSandbox();world=s.HEAP+0x80000;controller=s.HEAP+0x70000;date=s.HEAP+0x71000
    rates=json.loads((OUT/'weather/rates.json').read_text())['rates']
    pnext=s.HEAP+0x10000
    def alloc(size):
        nonlocal pnext
        p=pnext;pnext=(pnext+size+15)&~15;return p
    def q(at,value):s.uc.mem_write(at,struct.pack('<Q',value))
    def d(at,value):s.uc.mem_write(at,struct.pack('<I',value))
    # Populate only the parameter fields actually accessed by the native path.
    # Real s8/u8 parameter vtables point at original accessor functions, no stub.
    containers=[]
    for hemi,base in enumerate([0x27120,0x45eb8]):
        container=world+base;array=alloc(20*8);d(container+0xf8,20);q(container+0x100,array)
        for table in rates[hemi]['tables']:
            obj=alloc(0xe0);q(array+table['index']*8,obj)
            q(obj+0x30,0x305ee10);s.uc.mem_write(obj+0x54,bytes([table['end_month']]))
            q(obj+0x60,0x303baf8);s.uc.mem_write(obj+0x84,bytes([table['end_day']]))
            pointers=alloc(52*8);q(obj+0xd0,pointers)
            for i,weight in enumerate(table['weights']+[0]*18):
                parameter=alloc(0x30);q(parameter,0x303baf8);s.uc.mem_write(parameter+0x24,bytes([weight]));q(pointers+i*8,parameter)
        containers.append(container)
    q(s.image.ptr(0x32d1a38),world)
    failures=[];calendar_checks=selector_checks=prediction_checks=state_checks=0;samples=[]
    dates=[(m,d)for m in range(1,13)for d in range(1,calendar.monthrange(2024,m)[1]+1)]
    for hemi in [0,1]:
        d(world+0x651fc,hemi)
        for month,day in dates:
            expected=next(t['index']for t in rates[hemi]['tables']if (month,day)<=(t['end_month'],t['end_day']))
            actual=s.integer_call(0x201dc0,[world,month,day])&0xffffffff;calendar_checks+=1
            if actual!=expected:failures.append(dict(kind='calendar',hemisphere=hemi,month=month,day=day,actual=actual,expected=expected))
        # Exhaust all 100 integer rolls for every supplied table using the
        # original weighted-loop instructions and real native parameter getters.
        for table in rates[hemi]['tables']:
            for slot in range(100):
                sp=s.STACK+0x1ff000;frame=sp-0x100
                for reg,value in [('X21',containers[hemi]),('X19',table['index']),('X22',slot),('X20',0),('X23',0),('X29',frame),('SP',sp)]:
                    s.uc.reg_write(getattr(regs,'UC_ARM64_REG_'+reg),value)
                s.uc.emu_start(0xfddaac,0xfddb3c,count=20000)
                actual=s.uc.reg_read(regs.UC_ARM64_REG_X20);selector_checks+=1
                if s.uc.reg_read(regs.UC_ARM64_REG_PC)!=0xfddb3c or actual!=table['roll_0_to_99'][slot]:
                    failures.append(dict(kind='weighted_selection',hemisphere=hemi,table=table['index'],slot=slot,actual=actual))
    rng=random.Random(0xac101)
    cases=[(seed,2024,m,d,h)for seed in [0,1,0x7fffffff,0x80000000,0xfffffffe,0xffffffff,0x81234567,0xdeadbeef]
        for h in [0,1]for m,d in dates]
    cases.extend((rng.getrandbits(32),rng.randrange(2000,2061),m,d,rng.randrange(2))for m,d in [rng.choice(dates)for _ in range(1024)])
    times=[(0,0,0),(4,59,59),(5,0,0),(23,59,59)]if full_hours else[(12,34,56)]
    cases=[(*case,h,mi,se)for case in cases for h,mi,se in times]
    for seed,year,month,day,hemi,hour,minute,second in cases:
        # Random extra cases may land on Feb 29 of a non-leap year; omit those.
        if day>calendar.monthrange(year,month)[1]:continue
        d(world+0x651fc,hemi);d(controller+0x18,seed)
        s.uc.mem_write(date,struct.pack('<H6B',year,month,day,hour,minute,second,0))
        actual=s.integer_call(0xfdd9b0,[controller,date,0])&0xffffffff
        effective=dt.date(year,month,day)-dt.timedelta(days=int(hour<5))
        expected,state,slot,table=predict(seed,effective.year,effective.month,effective.day,rates[hemi]['tables']);prediction_checks+=1
        if actual!=expected:failures.append(dict(kind='prediction',input=[seed,year,month,day,hemi,hour,minute,second],actual=actual,expected=expected))
        # Its 16-byte local RNG remains in the emulated stack after return.
        actual_state=list(struct.unpack('<4I',bytes(s.uc.mem_read(s.STACK+0x1ff000-0x50,16))));state_checks+=1
        if actual_state!=state:failures.append(dict(kind='draw_order_state',input=[seed,year,month,day,hemi],actual=actual_state,expected=state))
        if len(samples)<12:samples.append(dict(stored_seed=seed,date=[year,month,day],time=[hour,minute,second],
            effective_date=[effective.year,effective.month,effective.day],hemisphere=hemi,pattern_index=actual,roll=slot,rate_index=table))
    if s.strcmp_calls:raise ValueError('unexpected strcmp dependency in weather')
    result=dict(native_elf_sha256=hashlib.sha256(s.image.data).hexdigest(),
        addresses=dict(normal_day_selector='0xfdd9b0',calendar_lookup='0x201dc0',hemisphere_container='0x206ef0',
            weighted_loop_begin='0xfddaac',weighted_loop_stop='0xfddb3c',date_normalizer='0x1fbc00',
            signed_parameter_getter='0x212540',unsigned_parameter_getter='0x47e800'),
        parameter_input='Synthetic in-memory objects filled exclusively from the supplied local weather tables, using original parameter vtables/accessors; constructors and deserialization not run here.',
        seed_contract='Consumes stored u32 seed without adding a high bit. mix = stored_seed + (year*512 + month*32 + day)*65536 modulo 2^32.',
        random_contract='Expand mixed seed; discard two u32 draws; third draw chooses roll=floor(u32*100/2^32); first cumulative signed-s8 weight greater than roll wins.',
        calendar_contract='First table with packed (end_month,end_day) >= requested date; hemisphere 0=North, 1=South; invalid hemisphere falls back to North in original code (not exercised here).',
        verified_entry_domain=('Valid dates at 00:00:00, 04:59:59, 05:00:00 and 23:59:59, flag=0, stored seed full u32; actual SDK date rollback executes through native GOT/PLT.'if full_hours else'Valid dates, hour=12, override flag=0, stored seed full u32. Native date normalizer sets 05:00:00; before-05:00 SDK date subtraction and event override flag=1 are not exercised.'),
        calendar_comparisons=calendar_checks,weighted_selection_comparisons=selector_checks,
        prediction_comparisons=prediction_checks,draw_state_comparisons=state_checks,
        comparisons=calendar_checks+selector_checks+prediction_checks+state_checks,mismatches=failures,
        dependencies_stubbed=[],samples=samples,day_boundary_verified=full_hours,
        remaining=([]if full_hours else['Before-05:00 date rollback through SDK calendar services'])+['Special-event overrides and unlock state',
            'Cloud/fog/rainbow/aurora/stars and visual runtime behavior','Origin/persistence of the stored seed in save data'])
    if full_hours:
        if s.os_calls:raise ValueError('unexpected OS service during linked weather helper')
        result.update(module_linking=s.evidence(),unsupported_os_calls=s.os_calls)
    dump(OUT/destination,result)
    print(json.dumps({k:v for k,v in result.items()if k not in ['samples','mismatches']},indent=2))
    if failures:raise ValueError(('native weather mismatch',failures[:8]))


if __name__=='__main__':build()
