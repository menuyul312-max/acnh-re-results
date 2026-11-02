"""Join Ghidra exports with data hashes.

Inputs: generated/re/functions.tsv, string_refs.tsv (from AcnhExport.java) and
the MOVZ/MOVK immediate scan (immscan). Ghidra loads the PIE main.elf at image
base 0x100000, so its exports are shifted back to ELF virtual addresses here; all
outputs use ELF VAs (same space as immscan / a64 / _registry.json).
Outputs generated/re/:
  bcsv_readers.json  table -> {column -> [function entries]}  (hash-constant xref)
  table_functions.json  function -> [tables it reads]          (who uses what)
  state_handlers.json   "Class::cState" string -> [functions]  (state machines)
"""
import bisect
import json
from collections import defaultdict

from ..config import OUT
from . import immscan

RE = OUT / "re"
GHIDRA_BASE = 0x100000  # Ghidra image base for main.elf (functions.tsv: _DT_INIT @ 0x100030)


def _functions():
    funcs = []
    for line in (RE / "functions.tsv").read_text(errors="replace").split("\n"):
        parts = line.split("\t", 2)
        if len(parts) != 3:
            continue
        e, size, name = parts
        funcs.append((int(e, 16) - GHIDRA_BASE, int(size), name))
    funcs.sort()
    return funcs


def _owner(funcs, starts, addr):
    i = bisect.bisect_right(starts, addr) - 1
    if i >= 0 and addr < funcs[i][0] + max(funcs[i][1], 4):
        return funcs[i][0]
    return None


def run():
    funcs = _functions()
    starts = [f[0] for f in funcs]
    consts = immscan.scan()
    readers, by_func = {}, defaultdict(set)
    for p in sorted((OUT / "data/bcsv").glob("*.json")):
        t = json.loads(p.read_text())
        cols = {}
        for c in t["columns"]:
            h = int(c["hash"], 16)
            owners = sorted({o for a in consts.get(h, []) if (o := _owner(funcs, starts, a))})
            cols[c["name"]] = [f"{o:x}" for o in owners]
            for o in owners:
                by_func[o].add(p.stem)
        readers[p.stem] = cols
    RE.mkdir(parents=True, exist_ok=True)
    (RE / "bcsv_readers.json").write_text(json.dumps(readers, indent=1))
    (RE / "table_functions.json").write_text(json.dumps({f"{k:x}": sorted(v) for k, v in by_func.items()}, indent=1))
    states = defaultdict(set)
    # strings may contain \r or other separators: split on \n only, skip continuation fragments
    for line in (RE / "string_refs.tsv").read_text(errors="replace").split("\n"):
        parts = line.split("\t", 2)
        if len(parts) != 3:
            continue
        _, fe, s = parts
        if "::c" in s and " " not in s:
            states[s].add(f"{int(fe, 16) - GHIDRA_BASE:x}")
    (RE / "state_handlers.json").write_text(json.dumps({k: sorted(v) for k, v in sorted(states.items())}, indent=1))
    return {"functions": len(funcs), "tables": len(readers), "functions_reading_tables": len(by_func),
            "state_strings": len(states)}
