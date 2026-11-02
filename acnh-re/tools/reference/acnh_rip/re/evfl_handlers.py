"""Map EventFlow action/query names to their native functions in main.elf.

Found in the binary (no symbols needed):
  * the game keeps a table sorted by Murmur3_32(name) (seed 0) of 16-byte
    records {u32 hash, u32 pad, u64 function pointer};
  * the pointer is 0 in the file and filled by an R_AARCH64_RELATIVE dynamic
    relocation whose addend is the function address.
890 of 1,057 names resolve this way. Families whose name carries a suffix
(RandomChoice<N>, RandomChoiceExcludePrevious<N>, MultiKindItemSelectIncludeChoice<N>,
SetCheckResult<Kind>) are registered under the longest prefix that is in the table;
those records get "match": "prefix". The function is a small per-action entry
(consecutive, 0x40 apart); follow it in Ghidra to the action object's vtable for
the real behaviour. Results are written into generated/eventflow/_registry.json.
"""
import json
import struct

from ..config import EXEFS, OUT
from .immscan import murmur3


def _elf():
    data = (EXEFS / "main.elf").read_bytes()
    phoff = struct.unpack_from("<Q", data, 0x20)[0]
    phn = struct.unpack_from("<H", data, 0x38)[0]
    segs = [struct.unpack_from("<IIQQQQ", data, phoff + i * 56) for i in range(phn)]
    return data, segs


def _f2v(segs, o):
    for t, _, off, va, _, sz in segs:
        if t == 1 and off <= o < off + sz:
            return va + (o - off)


def _v2f(segs, v):
    for t, _, off, va, _, sz in segs:
        if t == 1 and va <= v < va + sz:
            return off + (v - va)


def relocations(data, segs):
    dyn = next(s for s in segs if s[0] == 2)
    tags = {}
    for i in range(0, dyn[5], 16):
        t, v = struct.unpack_from("<qQ", data, dyn[2] + i)
        if t == 0:
            break
        tags[t] = v
    base, n = _v2f(segs, tags[7]), tags[8] // 24  # DT_RELA, DT_RELASZ
    out = {}
    for i in range(n):
        off, info, add = struct.unpack_from("<QQq", data, base + i * 24)
        out[off] = add
    return out


def run():
    data, segs = _elf()
    rel = relocations(data, segs)
    reg_path = OUT / "eventflow/_registry.json"
    reg = json.loads(reg_path.read_text())
    by_hash = {}
    for kind in reg.values():
        for key in kind:
            by_hash.setdefault(murmur3(key.split(".", 1)[1].encode()), []).append(key)
    data_seg = next(s for s in segs if s[0] == 1 and s[1] & 2)  # writable LOAD (.data)
    found, table = {}, {}
    for o in range(data_seg[2], data_seg[2] + data_seg[5] - 16, 4):
        w = struct.unpack_from("<I", data, o)[0]
        ptr = rel.get(_f2v(segs, o) + 8)
        if ptr:
            table.setdefault(w, ptr)
        if w in by_hash and ptr:
            for key in by_hash[w]:
                found[key] = f"{ptr:x}"
    for kind in reg.values():
        for key, rec in kind.items():
            rec["main_elf_function"] = found.get(key)
            rec.pop("match", None)
            if rec["main_elf_function"]:
                continue
            name = key.split(".", 1)[1]
            for n in range(len(name) - 1, len("EventFlowQuery"), -1):
                ptr = table.get(murmur3(name[:n].encode()))
                if ptr:
                    rec["main_elf_function"], rec["match"] = f"{ptr:x}", "prefix"
                    found[key] = rec["main_elf_function"]
                    break
    reg_path.write_text(json.dumps(reg, indent=1, ensure_ascii=False))
    total = sum(len(k) for k in reg.values())
    return {"registry_entries": total, "with_function": len(found)}
