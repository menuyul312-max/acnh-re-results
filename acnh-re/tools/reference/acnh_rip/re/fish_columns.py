"""Map FishAppear{River,Sea}Param columns to (month, time slot) from the column
accessors in main.elf (0x5b3860 river, 0x5b5ee0 sea): `switch (*month)` (0..11,
u16 jump table) then `*slot` 2 / 1 / 0 branches; each leaf loads the column hash
with movz/movk w27. Input: generated/re/disasm_fishcols.txt (tools/ghidra_disasm.sh
with "5b3860 2400" and "5b5ee0 2400"). Output: generated/re/fish_columns.json.
"""
import json
import re
import struct

from ..config import OUT
from . import a64
from .evfl_handlers import _v2f

GHIDRA_BASE = 0x100000
FUNCS = {"FishAppearRiverParam": 0x5b3860, "FishAppearSeaParam": 0x5b5ee0}


def _listing():
    ins = {}
    for line in (OUT / "re/disasm_fishcols.txt").read_text().splitlines():
        m = re.match(r"([0-9a-f]+)  (.*)", line)
        if m:
            ins[int(m.group(1), 16)] = m.group(2)
    return ins


def _target(text):
    return int(re.search(r"0x([0-9a-f]+)$", text).group(1), 16) - GHIDRA_BASE


def _hash_from(ins, pc):
    lo = None
    for a in range(pc, pc + 0x200, 4):
        t = ins.get(a, "")
        m = re.match(r"mov w27,#0x([0-9a-f]+)$", t)
        if m:
            lo = int(m.group(1), 16)
        m = re.match(r"movk w27,#0x([0-9a-f]+), LSL #16$", t)
        if m and lo is not None:
            return lo | int(m.group(1), 16) << 16
    return None


def run():
    img = a64.Image()
    ins = _listing()
    out = {}
    for table, fn in FUNCS.items():
        cols = {c["hash"]: c["name"] for c in json.loads((OUT / f"data/bcsv/{table}.json").read_text())["columns"]}
        adrp = next(a for a in range(fn, fn + 0x40, 4) if ins[a].startswith("adrp x9"))
        base = int(re.search(r"0x([0-9a-f]+)", ins[adrp]).group(1), 16) + int(re.search(r"#0x([0-9a-f]+)", ins[adrp + 4]).group(1), 16) - GHIDRA_BASE
        case0 = int(re.search(r"0x([0-9a-f]+)", ins[adrp + 8]).group(1), 16) - GHIDRA_BASE
        grid = []
        for month in range(12):
            off = struct.unpack_from("<H", img.data, _v2f(img.segs, base + 2 * month))[0]
            t = case0 + 4 * off
            assert ins[t].startswith("ldr w8,[x3]"), (table, month, hex(t), ins[t])
            slot2, slot1 = _target(ins[t + 8]), _target(ins[t + 16])
            leaf = {0: t + 24, 1: slot1, 2: slot2}
            row = []
            for slot in range(3):
                h = _hash_from(ins, leaf[slot])
                row.append({"hash": f"{h:08x}", "column": cols.get(f"{h:08x}")})
            grid.append(row)
        out[table] = grid
    (OUT / "re/fish_columns.json").write_text(json.dumps(out, indent=1))
    return {t: sum(1 for r in g for c in r if c["column"]) for t, g in out.items()}
