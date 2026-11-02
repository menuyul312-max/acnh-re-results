"""Map InsectAppearParam columns to (month, time slot) from the column accessors
in main.elf. [A2]

Unlike the fish tables (0x5b3860 / 0x5b5ee0) the insect accessors are not one
`switch (month)` function: the insect manager holds a dispatch table of 73
entries x 16 bytes at manager+0x170 (filled by 0x95ebe0, one getter pointer +
one cached column offset per entry):

    manager + 0x170 + 16*i  ->  getter(i)      (vtable of relocated pointers
                                                at ELF VA 0x32ee0e0 + 8*i)
    manager + 0x178 + 16*i  ->  cached offset  (-1 while unresolved)

The callers compute the entry index as `month*6 + slot` (0x965550, 0x957940,
0x957d70) and mask out index > 0x47 (72 excluded -> entry 0), so entries 0..71
are the 12 months x 6 time slots and entry 72 is the hemisphere column.

Every getter carries exactly one column hash (movz/movk w27) and caches the
column offset it resolved (ldrsw x8,[x20,#0xN] / str w26 (= 0xfffffffe) / str
w8). The BCSV reader offsets are `4 + 2*i` for InsectAppearParam and the cached
value is `4 * column_index`, so the hash and the cache offset are two
independent derivations of the same column: this script asserts both agree.

Input : the ELF itself (tools/acnh_rip/re/a64.py) plus the Ghidra listing
        generated/re/a2_insect_disasm.txt ("95f040 2600" — the getter bodies).
Output: generated/re/insect_columns.json
        {"InsectAppearParam": [[{hash, column} x 6] x 12]}
"""
import json
import re

from ..config import OUT
from . import a64

VTABLE = 0x32ee0e0  # ELF VA of the 73 relocated getter pointers
ENTRIES = 73  # 72 hour cells + hemisphere
SLOTS = 6  # hours -> slot ladder is 6-way for insects (0x9f1870)
MONTHS = 12
TABLE = "InsectAppearParam"

def _listing():
    """Ghidra listing of the getter bodies -> {va: instruction text}."""
    ins = {}
    for line in (OUT / "re/a2_insect_disasm.txt").read_text().splitlines():
        m = re.match(r"([0-9a-f]+)  (.*)", line)
        if m:
            ins[int(m.group(1), 16)] = m.group(2)
    return ins

def _scan(ins, entry):
    """(hash, cache offset) of one getter, or (None, None)."""
    h = None
    lo = None
    cache = None
    for a in range(entry, entry + 0x160, 4):
        t = ins.get(a, "")
        m = re.match(r"mov w27,#0x([0-9a-f]+)$", t)
        if m:
            lo = int(m.group(1), 16)
        m = re.match(r"movk w27,#0x([0-9a-f]+), LSL #16$", t)
        if m and lo is not None:
            h = lo | int(m.group(1), 16) << 16
        # cache slot: `ldrsw x8,[x20, #0x..]` (mov w21,#0x12c is the memset size,
        # w26/w25 are the sentinel/flag and w27 the hash)
        m = re.match(r"ldrsw x8,\[x20, #0x([0-9a-f]+)\]$", t)
        if m:
            cache = int(m.group(1), 16)
    return h, cache

def run():
    img = a64.Image()
    ins = _listing()
    cols = json.loads((OUT / f"data/bcsv/{TABLE}.json").read_text())["columns"]
    by_hash = {c["hash"]: (i, c["name"]) for i, c in enumerate(cols)}

    cells = []  # (entry, hash, column index, column name, cache)
    mismatch = []
    for i in range(ENTRIES):
        entry = img.ptr(VTABLE + 8 * i)
        h, cache = _scan(ins, entry)
        hn = f"{h:08x}" if h is not None else None
        idx, name = by_hash.get(hn, (None, None))
        cells.append((i, hn, idx, name, cache))
        if cache is None or idx is None or cache != 4 * idx:
            mismatch.append((i, hn, name, cache, idx))

    grid = []
    for month in range(MONTHS):
        row = []
        for slot in range(SLOTS):
            _, hn, idx, name, _ = cells[month * SLOTS + slot]
            row.append({"hash": hn, "column": name})
        grid.append(row)
    out = {TABLE: grid}
    (OUT / "re/insect_columns.json").write_text(json.dumps(out, indent=1))
    return {
        "entries": len(cells),
        "resolved": sum(1 for c in cells if c[3]),
        "cache_mismatch": mismatch,
        "hemisphere": cells[ENTRIES - 1],
        "slot_hashes_unique": len({c[1] for c in cells[: MONTHS * SLOTS]}),
    }

if __name__ == "__main__":
    print(json.dumps(run(), indent=1))