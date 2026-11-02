"""Factory -> constructor -> vtable for every EventFlow action/query (formula F1).

FACTORY: mov x19,x0 ; movz x0,<size> ; bl <allocator> ; mov x1,x19 ; bl <CTOR>
CTOR:    bl <base ctor> ; ... add x8, <vtable>+16 ; str x8, [x19]
The last store to [x19+0] in the constructor is the most-derived vtable.
A slot target shared by >=25% of the distinct vtables of its kind is a base-class
default; the rest are overridden per class and hold the behaviour. A vtable ends at
the first null word (the offset-to-top/typeinfo header of the next class's vtable;
this build has no RTTI). Slot roles (from WaitFrame, SetSubflowResult, PercentChoice):
  action: 0 RTTI check, 1 get RTTI, 2/3 dtor, 8 enter, 9 update (sets done @+0xb0),
          10 exit, 11 instant execute; 12+ class-specific virtuals.
  query:  0 RTTI check, 1 get RTTI, 2/3 dtor, 6 evaluate (returns the case value).
Parameter i (ctor order) is a 0x28-byte record at +0xb8+0x28*i (query: +0xb0+...),
value at +0x20 in the record. Result: generated/re/evfl_vtables.json.
"""
import json
from collections import Counter

from ..config import OUT
from . import a64

ALLOCATOR = 0x1967710
NSLOTS = {"actions": 15, "queries": 16}


def _follow(img, va, depth=4):
    """Resolve tail-call thunks (a lone `b X`)."""
    for _ in range(depth):
        if a64._v2f(img.segs, va) is None:
            return va
        ins = a64.decode(img.u32(va), va)
        if ins[0] != "b":
            break
        va = ins[1]
    return va


def factory_info(img, factory):
    size, bls = None, []
    for pc, ins, _ in a64.walk(img, factory, 32):
        if ins[0] == "movz" and ins[1] == 0 and size is None:
            size = ins[2]
        if ins[0] == "bl":
            bls.append(ins[1])
    ctor = next((b for b in bls if b != ALLOCATOR), None)
    return size, ctor


def ctor_vtable(img, ctor):
    """Track x19 (=this) and register values; last `str reg,[x19,#0]` with a known value."""
    vt, regs, this = None, {}, {0}
    for pc, ins, _ in a64.walk(img, ctor, 256):
        op = ins[0]
        if op == "mov" and ins[2] in this:
            this.add(ins[1])
        elif op == "adrp":
            regs[ins[1]] = ins[2]
        elif op == "add" and ins[2] in regs:
            regs[ins[1]] = regs[ins[2]] + ins[3]
        elif op == "ldr" and ins[2] in regs:
            try:
                regs[ins[1]] = img.ptr(regs[ins[2]] + ins[3])
            except Exception:
                regs.pop(ins[1], None)
        elif op == "str" and ins[2] in this and ins[3] == 0 and ins[1] in regs:
            vt = regs[ins[1]]
        elif op == "bl":
            this = {r for r in this if r >= 19}  # x0..x18 are caller-saved
            regs = {r: v for r, v in regs.items() if r >= 19}
    return vt


def run():
    img = a64.Image()
    reg = json.loads((OUT / "eventflow/_registry.json").read_text())
    out = {}
    for kind, n in NSLOTS.items():
        recs = {}
        for key, rec in reg[kind].items():
            f = rec.get("main_elf_function")
            if not f:
                continue
            fac = int(f, 16)
            size, ctor = factory_info(img, fac)
            vt = ctor_vtable(img, ctor) if ctor else None
            slots = None
            if vt:
                raw = [img.ptr(vt + 8 * i) for i in range(n)]
                raw = raw[:raw.index(0)] if 0 in raw else raw
                slots = [_follow(img, p) for p in raw]
            recs[key] = {"factory": fac, "size": size, "ctor": ctor, "vtable": vt, "slots": slots}
        # base-class default per slot = most common target among distinct vtables
        vts = {r["vtable"]: r["slots"] for r in recs.values() if r["slots"]}
        common = Counter(t for s in vts.values() for t in set(s))
        shared = {t for t, c in common.items() if c * 4 >= len(vts)}
        for r in recs.values():
            if r["slots"]:
                r["overridden"] = {i: f"{s:x}" for i, s in enumerate(r["slots"]) if s not in shared}
            for k in ("factory", "ctor", "vtable"):
                r[k] = f"{r[k]:x}" if r[k] else None
            r["slots"] = [f"{s:x}" for s in r["slots"]] if r["slots"] else None
        out[kind] = {"shared_targets": sorted(f"{s:x}" for s in shared), "entries": recs}
    path = OUT / "re/evfl_vtables.json"
    path.write_text(json.dumps(out, indent=1))
    return {k: {"entries": len(v["entries"]),
                "with_vtable": sum(1 for r in v["entries"].values() if r["vtable"]),
                "distinct_vtables": len({r["vtable"] for r in v["entries"].values() if r["vtable"]})}
            for k, v in out.items()}
