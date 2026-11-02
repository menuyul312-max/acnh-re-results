"""Find every reference to a VA in main.elf that is NOT a B/BL (callers.py covers those).

Three kinds of reference are reported:
  * code:      ADRP+ADD/LDR whose resolved target is the VA (materials the address);
  * reloc:     a writable slot whose R_AARCH64_RELATIVE addend is the VA (real pointer
               in memory, file content is 0) - vtables and global function tables;
  * raw:       an 8-byte little-endian word in a LOAD segment that already holds the VA.

For a relocated slot the containing object is printed too: the run of consecutive
relocated words around it (a vtable) with its start/end, so the owning class can be
decompiled next.  All addresses are ELF VAs (Ghidra = VA + 0x100000, D-013).

[DS] added session 5 for the FishCreate vtable hunt (NEXT_SESSION.md section 4.1b).

  python3 -m acnh_rip.re.ptrscan 59ca80 [more VAs...]
"""
import struct
import sys
from array import array
from collections import defaultdict

from . import a64, xref

def _sections(img):
    """[(va, filesize, is_exec, is_writable)] from the program headers."""
    out = []
    for t, flags, _off, va, _pa, sz in img.segs:
        if t == 1:
            out.append((va, sz, bool(flags & 1), bool(flags & 2)))
    return out

def _locate(img, va):
    o = a64._v2f(img.segs, va)
    return o

def reloc_slots(img):
    """{slot VA: addend} for every R_AARCH64_RELATIVE in the image."""
    return {k: v for k, v in img.rel.items()}

def raw_words(img, target):
    """VAs of 8-byte words in any LOAD segment equal to target."""
    hits = []
    needle = struct.pack("<Q", target)
    for va, sz, _x, _w in _sections(img):
        o = a64._v2f(img.segs, va)
        if o is None:
            continue
        blob = img.data[o:o + sz]
        i = blob.find(needle)
        while i != -1:
            if i % 8 == 0:
                hits.append(va + i)
            i = blob.find(needle, i + 1)
    return hits

def code_refs(img, target):
    """ADRP+ADD/LDR address materialisations of target, found with the a64 decoder."""
    site = []
    for va, sz, is_exec, _w in _sections(img):
        if not is_exec:
            continue
        n = sz // 4
        ins = array("I")
        o = a64._v2f(img.segs, va)
        ins.frombytes(img.data[o:o + n * 4])
        pages = defaultdict(list)  # page -> [register]
        for i, w in enumerate(ins):
            pc = va + i * 4
            op = w & 0x9F000000
            if op == 0x90000000:  # ADRP
                imm = a64._sx(((w >> 5) & 0x7FFFF) << 2 | ((w >> 29) & 3), 21) << 12
                pages[(pc & ~0xFFF) + imm].append((i, w & 31))
        if not pages:
            continue
        for base, regs in pages.items():
            for i, rd in regs:
                for j in range(i + 1, min(n, i + 3)):
                    k = ins[j]
                    kpc = va + j * 4
                    if (k & 0x7F800000) == 0x11000000 and (k >> 5) & 31 == rd:
                        sh = 12 if (k >> 22) & 1 else 0
                        if base + (((k >> 10) & 0xFFF) << sh) == target:
                            site.append((kpc, "add"))
                    elif (k & 0xFFC00000) == 0xF9400000 and (k >> 5) & 31 == rd:
                        if base + ((k >> 10) & 0xFFF) * 8 == target:
                            site.append((kpc, "ldr"))
    return site

def _vtable_extent(img, slot):
    """Grow a run of relocated pointer words that point into the executable segment."""
    rel = reloc_slots(img)
    exec_ranges = [(va, va + sz) for va, sz, x, _w in _sections(img) if x]
    def is_fn(v):
        return any(a <= v < b for a, b in exec_ranges)
    lo = slot
    while lo - 8 in rel and is_fn(rel[lo - 8]):
        lo -= 8
    hi = slot
    while hi + 8 in rel and is_fn(rel[hi + 8]):
        hi += 8
    return lo, hi

def run(targets):
    img = a64.Image()
    rel = reloc_slots(img)
    funcs = xref._functions()
    starts = [f[0] for f in funcs]
    for t in targets:
        owner = xref._owner(funcs, starts, t) if starts else None
        name = f"fn {owner:x}" if owner is not None else "not a Ghidra function"
        print(f"== {t:x} ({name})")
        slots = sorted(k for k, v in rel.items() if v == t)
        for s in slots:
            lo, hi = _vtable_extent(img, s)
            n = (hi - lo) // 8 + 1
            idx = (s - lo) // 8
            print(f"  reloc slot {s:x}  vtable {lo:x}..{hi:x} ({n} slots), index {idx}")
            for k in range(lo, hi + 1, 8):
                v = rel.get(k, 0)
                o = xref._owner(funcs, starts, v) if starts else None
                tag = "  <== target" if k == s else ""
                print(f"    [{ (k-lo)//8:2d}] {k:x} -> {v:x}"
                      f"{f' ({o:x})' if o is not None else ''}{tag}")
        for s in raw_words(img, t):
            print(f"  raw word {s:x}")
        for pc, kind in sorted(code_refs(img, t)):
            o = xref._owner(funcs, starts, pc) if starts else None
            print(f"  code {kind} @{pc:x}" + (f" (fn {o:x})" if o is not None else " (nofn)"))

if __name__ == "__main__":
    run([int(a, 16) for a in sys.argv[1:]])