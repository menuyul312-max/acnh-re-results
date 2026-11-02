#!/usr/bin/env python3
"""Resolve native dispatch through the shipped BindInfo aliases, not guesses."""
import json
import os
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parent.parent
SRC = Path(json.loads((ROOT/'output/manifest.json').read_text())['source_root'])
os.environ.update(ACNH_ROMFS=str(SRC/'B_data'), ACNH_EXEFS=str(SRC/'A_logic'), ACNH_OUT=str(ROOT/'work'))
sys.path.insert(0, str(ROOT/'tools/reference'))
from acnh_rip.re import a64, evfl_vtables
from acnh_rip.re.immscan import murmur3
from native_image import Image
from vptr_trace import trace
from reverse_corpus import dump


def build():
    out = ROOT/'output'
    img = Image()
    legacy = a64.Image()
    manifest = json.loads((out/'manifest.json').read_text())['entries']
    bind = next(e for e in manifest if e['source'].endswith('/Info/BindInfo.byml'))
    bindings = json.loads((out/bind['decoded']).read_text())['data']['root']
    registry = json.loads((ROOT/'work/eventflow/_registry.json').read_text())
    records = {}
    for ptr_va, target in img.relocations.items():
        try:
            h, pad = struct.unpack('<II', img.read(ptr_va-8,8))
            if pad == 0 and 0 < target < 0x2500000:
                records.setdefault(h, []).append((ptr_va-8, target))
        except ValueError:
            continue
    result = {'binding_source_id': bind['id'], 'binding_raw': bind['raw'], 'entries': {}, 'unresolved': []}
    traced={};corrections=[]
    for kind, group in registry.items():
        aliases = {r['Key']: r['Value'] for r in bindings['ActionBindData' if kind == 'actions' else 'QueryBindData']}
        for key, old in group.items():
            name = key.split('.',1)[1]
            canonical = aliases.get(name, name)
            h = murmur3(canonical.encode())
            found = list(set(records.get(h, [])))
            rec = {'kind': kind, 'name': name, 'canonical_name': canonical,
                   'alias_evidence': 'BindInfo.byml' if name != canonical else None,
                   'registration_hash': f'{h:08x}', 'event_uses': old['uses'], 'parameters': old['params']}
            if len(found) == 1:
                va, factory = found[0]
                size, ctor = evfl_vtables.factory_info(legacy, factory)
                if ctor not in traced:
                    traced[ctor]=trace(img,ctor) if ctor else (None,[])
                    old_vtable=evfl_vtables.ctor_vtable(legacy,ctor) if ctor else None
                    if old_vtable!=traced[ctor][0]:
                        corrections.append({'constructor':hex(ctor) if ctor else None,
                            'legacy_candidate':hex(old_vtable) if old_vtable else None,
                            'outer_object_vtable':hex(traced[ctor][0]) if traced[ctor][0] else None})
                vtable,stores=traced[ctor]
                evidence = 'bounded_constructor_trace; exact outer_object_offset_zero_store'
                slots,raw_slots,stop = [],[],'limit_256'
                if vtable:
                    for i in range(256):
                        p = img.ptr(vtable+8*i)
                        if not p:
                            stop='zero_pointer'
                            break
                        if p % 4 or not any(seg['p_flags'] & 1 and seg['p_vaddr'] <= p < seg['p_vaddr'] + seg['p_filesz'] for seg in img.segments):
                            # Some tables are followed directly by non-vtable data.
                            # A fixed slot count must not turn it into function targets.
                            stop='non_executable_or_unaligned_pointer';break
                        raw_slots.append(hex(p))
                        slots.append(hex(evfl_vtables._follow(legacy,p)))
                rec.update(status='native_factory', registration_va=hex(va), factory=hex(factory),
                    constructor=hex(ctor) if ctor else None, object_size=size,
                    vtable=hex(vtable) if vtable else None, vtable_evidence=evidence,
                    vptr_stores=stores,slots=slots,slots_raw=raw_slots,
                    slot_span_stop=stop,slot_span_evidence='contiguous code pointers; later class-specific slot roles unresolved')
            elif name == 'EventFlowActionExitFlowchart':
                rec.update(status='runner_builtin', evidence='no native factory; flowchart runner exit operation',
                           initializer='0x446800', native_start='0x447060', native_predicate='0x4474e0',
                           behavior_verification='binary/exit_flowchart_verification.json',
                           native_effect='completion byte at object+0x50 becomes 1; returns success')
            else:
                rec.update(status='unresolved', candidates=[list(v) for v in found])
                result['unresolved'].append(key)
            result['entries'][key] = rec
    result['counts'] = {'dispatch_names': len(result['entries']),
        'native_factories': sum(r['status']=='native_factory' for r in result['entries'].values()),
        'with_vtable': sum(bool(r.get('vtable')) for r in result['entries'].values()),
        'aliases_applied': sum(bool(r['alias_evidence']) for r in result['entries'].values()),
        'runner_builtins': sum(r['status']=='runner_builtin' for r in result['entries'].values()),
        'unique_native_factories':len({r['factory'] for r in result['entries'].values() if r.get('factory')}),
        'unique_vtables':len({r['vtable'] for r in result['entries'].values() if r.get('vtable')}),
        'constructors_traced':len(traced),
        'slot_spans_hitting_limit':sum(r.get('slot_span_stop')=='limit_256' for r in result['entries'].values()),
        'unresolved': len(result['unresolved'])}
    result['legacy_vptr_corrections']=corrections
    result['trace_limitations']='Bounded linear constant propagation with AAPCS caller-clobbers; not full path-sensitive constructor emulation.'
    dump(out/'binary/event_handlers_resolved.json', result)
    print(json.dumps(result['counts'], indent=2))
    print('unresolved', result['unresolved'])


if __name__ == '__main__':
    build()
