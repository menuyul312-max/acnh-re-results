"""Direct callers of functions in main.elf: every B / BL whose target is the given VA.

Ghidra misses callers that sit in code it never made a function of (and tail
calls written as B), so this scans the executable segment itself. The owner
column comes from functions.tsv; "nofn" = the call site is outside every Ghidra
function (decompile it with tools/ghidra_decompile.sh after finding its start
with tools/ghidra_disasm.sh). Calls through vtables/function pointers are not seen.

  python3 -m acnh_rip.re.callers 5b9ba0 5ba7b0      (ELF VAs, hex)
"""
import sys
from array import array
from collections import defaultdict

from . import immscan, xref


def branches():
    """{target VA: [(call site VA, is_bl)]} for every B/BL in the code segment."""
    base, text = immscan.load_text()
    ins = array("I")
    ins.frombytes(text[:len(text) // 4 * 4])
    out = defaultdict(list)
    for i, w in enumerate(ins):
        op = w & 0xFC000000
        if op in (0x94000000, 0x14000000):
            imm = w & 0x3FFFFFF
            if imm & 0x2000000:
                imm -= 0x4000000
            pc = base + i * 4
            out[pc + imm * 4].append((pc, op == 0x94000000))
    return out


def run(targets):
    funcs = xref._functions()
    starts = [f[0] for f in funcs]
    by_target = branches()
    for t in targets:
        sites = []
        for pc, bl in by_target.get(t, []):
            o = xref._owner(funcs, starts, pc)
            sites.append(f"{pc:x}({'bl' if bl else 'b'},{f'fn {o:x}' if o is not None else 'nofn'})")
        print(f"{t:x} -> {' '.join(sites) or '-'}")


if __name__ == "__main__":
    run([int(a, 16) for a in sys.argv[1:]])
