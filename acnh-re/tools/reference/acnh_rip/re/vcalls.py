"""Find virtual-call sites: `ldr xN,[xM,#imm]; blr xN` (and `ldr; br`), grouped by offset.

A vtable call site names the slot only as a byte offset, so this lists every
offset N seen with a following BLR/BR, along with the owning Ghidra function.
Use it to locate where a class's virtual at vtable index k (= offset 8k) is
invoked, then decompile the owner and read which class the object is.

[DS] added session 5 (NEXT_SESSION.md 4.1b: who calls FishCreate, slot 43).

  python3 -m acnh_rip.re.vcalls [--offset 0x158] [--around 5a0000 5c0000]
"""
import sys
from array import array

from . import a64, xref

def scan():
    """[(call site VA, offset, owner function or None)] for every ldr+blr/br pair."""
    img = a64.Image()
    funcs = xref._functions()
    starts = [f[0] for f in funcs]
    out = []
    for t, flags, _o, va, _pa, sz in img.segs:
        if t != 1 or not (flags & 1):
            continue
        n = sz // 4
        ins = array("I")
        ins.frombytes(img.data[a64._v2f(img.segs, va):a64._v2f(img.segs, va) + n * 4])
        for i in range(n - 1):
            w = ins[i]
            if (w & 0xFFC00000) != 0xF9400000:      # LDR Xt,[Xn,#imm]
                continue
            rd_load = w & 31
            # the BLR that uses it may follow after other loads (common: ldr vptr; ldr fn; blr)
            for j in range(i + 1, min(n, i + 5)):
                k = ins[j]
                if (k & 0xFFFFFC1F) != 0xD63F0000:      # not BLR/BR
                    # stop if the register is overwritten before use
                    if (k & 0xFFC00000) == 0xF9400000 and (k & 31) == rd_load:
                        break
                    if (k & 0x9F000000) == 0x90000000 and (k & 31) == rd_load:
                        break
                    if (k & 0x7F800000) in (0x11000000, 0x51000000) and (k & 31) == rd_load:
                        break
                    continue
                if ((k >> 5) & 31) != rd_load:          # BLR of another register
                    continue
                pc = va + i * 4
                out.append((pc, ((w >> 10) & 0xFFF) * 8, va + j * 4,
                            xref._owner(funcs, starts, pc)))
                break
    return out

def run(offset=None, around=None, show_all=False):
    rows = scan()
    if around:
        lo, hi = around
        rows = [r for r in rows if lo <= r[0] < hi]
    if offset is not None:
        rows = [r for r in rows if r[1] == offset]
    for pc, off, call, owner in rows:
        o = f"{owner:x}" if owner is not None else "nofn"
        print(f"{pc:x} off 0x{off:x} call {call:x} fn {o}")
    if not show_all:
        from collections import Counter
        c = Counter(r[1] for r in rows)
        print("offsets:", ", ".join(f"0x{k:x}:{v}" for k, v in sorted(c.items())))

if __name__ == "__main__":
    off, around, show_all = None, None, False
    a = sys.argv[1:]
    if "--offset" in a:
        off = int(a[a.index("--offset") + 1], 16)
    if "--around" in a:
        i = a.index("--around")
        around = (int(a[i + 1], 16), int(a[i + 2], 16))
    if "--all" in a:
        show_all = True
    run(off, around, show_all)