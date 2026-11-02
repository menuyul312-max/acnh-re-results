#!/usr/bin/env python3
"""Verify original SDK Gregorian conversion and main's 05:00 day boundary."""
import calendar
import collections
import datetime as dt
import hashlib
import json
from pathlib import Path
import random
import struct

from native_linker import ModuleSandbox
from reverse_corpus import dump

ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/'output'
UTC=dt.timezone.utc
EPOCH=dt.datetime(1970,1,1,tzinfo=UTC)
MASK=(1<<64)-1


def packed(value):return struct.pack('<h6B',value.year,value.month,value.day,value.hour,value.minute,value.second,0)
def signed(value):return value-(1<<64)if value&(1<<63)else value
def seconds(value):return int((value-EPOCH).total_seconds())
def effective_day(value):return (value-dt.timedelta(days=int(value.hour<5))).replace(hour=5,minute=0,second=0)


def build():
    s=ModuleSandbox();p=s.HEAP+0x4000;groups=collections.Counter();failures=[];samples=[]
    to_posix=s.exported('_ZN2nn4time18ToPosixTimeFromUtcERKNS0_12CalendarTimeE')
    to_calendar=s.exported('_ZN2nn4time19ToCalendarTimeInUtcERKNS0_9PosixTimeE')
    def check(group,actual,expected,context):
        groups[group]+=1
        if actual!=expected:
            failures.append(dict(group=group,actual=actual,expected=expected,**context))
            if len(failures)>10:raise ValueError(('systematic calendar mismatch',failures[:3]))
    def verify_conversion(value):
        expected_seconds=seconds(value);s.uc.mem_write(p,packed(value))
        actual=signed(s.integer_call(to_posix,[p]));check('sdk_calendar_to_posix',actual,expected_seconds,dict(date=value.isoformat()))
        s.uc.mem_write(p,struct.pack('<q',expected_seconds));actual=s.integer_call(to_calendar,[p])
        check('sdk_posix_to_calendar',actual,int.from_bytes(packed(value),'little'),dict(date=value.isoformat()))
    # Complete Gregorian 400-year cycle includes century non-leaps and 2400's
    # boundary through selected anchors. The cycle uses the original SDK API.
    day=dt.datetime(2000,1,1,12,34,56,tzinfo=UTC);end=dt.datetime(2400,1,1,tzinfo=UTC);cycle_dates=0
    while day<end:
        verify_conversion(day);cycle_dates+=1;day+=dt.timedelta(days=1)
        if cycle_dates%20000==0:print(json.dumps(dict(gregorian_dates=cycle_dates,mismatches=len(failures))),flush=True)
    rng=random.Random(0xac106)
    anchors=[dt.datetime(y,m,d,h,mi,se,tzinfo=UTC)for y,m,d in [
        (1,1,1),(1600,2,29),(1700,3,1),(1800,3,1),(1900,3,1),(1969,12,31),
        (1970,1,1),(1999,12,31),(2000,2,29),(2100,3,1),(2400,2,29),(9999,12,31)]
        for h,mi,se in [(0,0,0),(4,59,59),(5,0,0),(23,59,59)]]
    anchors.extend(EPOCH+dt.timedelta(seconds=rng.randrange(-62135596800,253402300800))for _ in range(1024))
    for value in anchors:verify_conversion(value)
    # Every hour of every 2024 date, plus month/year/century boundaries.
    cases=[dt.datetime(2024,m,d,h,59,59,tzinfo=UTC)for m in range(1,13)
        for d in range(1,calendar.monthrange(2024,m)[1]+1)for h in range(24)]
    cases.extend(value for value in anchors if value.year>1)
    for year in range(2000,2401):
        for m,d in [(1,1),(2,28),(3,1),(12,31)]:
            for h,mi,se in [(0,0,0),(4,59,59),(5,0,0),(23,59,59)]:cases.append(dt.datetime(year,m,d,h,mi,se,tzinfo=UTC))
    for value in cases:
        s.uc.mem_write(p,packed(value)+b'\xa5'*8);s.integer_call(0x1fbc00,[p])
        actual=bytes(s.uc.mem_read(p,16));expected=packed(effective_day(value))+b'\xa5'*8
        check('main_day_normalization_and_guard',actual.hex(),expected.hex(),dict(input=value.isoformat()))
        if value.month==3 and value.day==1 and value.hour in [4,5]and len(samples)<24:
            samples.append(dict(input=value.isoformat(),output=effective_day(value).isoformat(),native_hex=actual[:8].hex()))
    # The native day-offset helper multiplies into a signed 64-bit nanosecond
    # span first. Extreme synthetic day counts wrap there; do not invent an
    # unlimited-precision calendar contract for this API.
    shift_cases=[(timestamp,days)for timestamp in [-62135596800,-1,0,1,253402300799]
        for days in [-(1<<31),-106752,-106751,-36600,-1,0,1,36600,106751,106752,(1<<31)-1]]
    shift_cases.extend((rng.randrange(-(1<<63),(1<<63)),rng.randrange(-(1<<31),1<<31))for _ in range(4096))
    for timestamp,days in shift_cases:
        ns=signed((days*86400000000000)&MASK);delta=(abs(ns)//1000000000)*(-1 if ns<0 else 1)
        actual=signed(s.integer_call(0x1fd540,[0,timestamp,days]));expected=signed((timestamp+delta)&MASK)
        check('main_day_offset_integer_contract',actual,expected,dict(timestamp=str(timestamp),days=days))
    relocation_checks=0
    for module,site,kind,value in s.applied:
        actual=struct.unpack('<Q',bytes(s.uc.mem_read(s.BASES[module]+site,8)))[0];relocation_checks+=1
        if actual!=value:raise ValueError(('relocation changed during pure calendar helpers',module,hex(site),actual,value))
    if s.os_calls:raise ValueError('calendar helper unexpectedly called an OS service')
    link=s.evidence();link.update(pointer_checks=relocation_checks,pointer_mismatches=0,
        defined_symbol_policy='Own defined symbols retain module-local addresses. An undefined symbol with exactly one strong export selects it; remaining ambiguous imports are rejected.')
    dump(OUT/'native_modules/relocation_verification.json',link)
    evidence=[]
    for module,va,size in [('sdk',0x2cf740,4),('sdk',0x2cf630,4),('sdk',0x2d4460,0x120),('sdk',0x2d4580,0x180),
        ('main',0x1fbc00,0x70),('main',0x1fd540,0x90)]:
        raw=s.modules[module].read(va,size);path=f'calendar/evidence/{module}_{va:x}.asm'
        target=OUT/path;target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text('\n'.join(f'{i.address:08x} {i.bytes.hex():8s} {i.mnemonic:8s} {i.op_str}'for i in s.image.disassembler.disasm(raw,va))+'\n')
        evidence.append(dict(module=module,va=hex(va),size=size,sha256=hashlib.sha256(raw).hexdigest(),assembly=path))
    result=dict(native_elf_sha256=hashlib.sha256(s.image.data).hexdigest(),sdk_sha256=link['input_sha256']['sdk'],
        gregorian_cycle=dict(start='2000-01-01',end_inclusive='2399-12-31',dates=cycle_dates),
        comparisons=sum(groups.values()),groups=dict(groups),mismatches=failures,dependencies_stubbed=[],unsupported_os_calls=s.os_calls,
        calendar_layout='<s16 year, u8 month, u8 day, u8 hour, u8 minute, u8 second, padding>',
        sdk_conversion_domain='Every date in a complete 400-year Gregorian cycle, anchors and random valid dates in years 1..9999; UTC arithmetic only.',
        effective_day_contract='If input hour <5, subtract one calendar day; then write 05:00:00. At hour 5 exactly, retain the same date. Output is independent of input minutes/seconds.',
        day_offset_contract='Signed s32 days multiplied by 86400000000000 modulo s64 nanoseconds, divided by 1e9 truncating toward zero, then added modulo s64 to Posix seconds.',
        boundary_scope='Real main normalizer and original SDK conversion code execute through relocated GOT/PLT. No host-time, timezone service, clock retrieval, save seed or special-event policy is inferred.',
        addresses=dict(main_normalize='0x1fbc00',main_day_offset='0x1fd540',sdk_to_posix='0x2cf740',sdk_to_calendar='0x2cf630'),
        samples=samples,evidence=evidence,remaining=['Weather special-event overrides','Stored weather seed persistence','Visual weather systems','Real OS/timezone service initialization'])
    dump(OUT/'calendar/native_verification.json',result)
    print(json.dumps({k:v for k,v in result.items()if k not in ['samples','mismatches','evidence']},indent=2))
    if failures:raise ValueError(('native calendar mismatch',failures[:5]))


if __name__=='__main__':build()
