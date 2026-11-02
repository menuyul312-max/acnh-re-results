"""Extract sead-style enums: one rodata string "A , B , C" (or "A ,B ,C") split at
runtime into the value names (index = enum value). Examples: EventFlag tables
"cPlayer , cPlayerVisit , ...", stages "cTalkingNpcHouse , ...", emoticons "EmotEnd ,Smiling ,...".
Output generated/re/enums.json: {string VA: {"values": [...], "functions": [VA, ...]}}
(functions = referencing functions from string_refs.tsv, ELF VAs).
"""
import json
import re

from ..config import OUT
from . import a64
from .xref import GHIDRA_BASE

_ITEM = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def run():
    img = a64.Image()
    refs = {}
    for line in (OUT / "re/string_refs.tsv").read_text(errors="replace").split("\n"):
        p = line.split("\t", 2)
        if len(p) == 3:
            refs.setdefault(int(p[0], 16) - GHIDRA_BASE, set()).add(int(p[1], 16) - GHIDRA_BASE)
    out = {}
    for va in sorted(refs):
        try:
            s = img.cstr(va, 8192)
        except Exception:
            continue
        if "," not in s:
            continue
        vals = [v.strip() for v in s.split(",")]
        if len(vals) < 2 or not all(_ITEM.match(v) for v in vals):
            continue
        out[f"{va:x}"] = {"values": vals, "functions": sorted(f"{f:x}" for f in refs[va])}
    (OUT / "re/enums.json").write_text(json.dumps(out, indent=1))
    return {"enums": len(out), "values": sum(len(v["values"]) for v in out.values())}
