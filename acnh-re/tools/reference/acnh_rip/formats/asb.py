"""AnimationSequence (*.root.asb) reader -- the animation state machine format.

Layout measured against all 83 files of `romfs/AnimationSequence` (ASB v0x407 in
81 files, v0x405 in ObjectAirConditioner.root and ResolvedByHelper.root).
Everything is little endian.  Facts are recorded in ASSUMPTIONS.md D-042..D-051;
open questions A-052..A-059 (A-051 is deliberately skipped so the ASB rows do not
collide with a number another session may have taken).  Nothing here is guessed:
every field that could
not be proven is kept raw and named `*_raw`.

Header (24 u32 at 0x00)                                                   D-042
  0x00 magic "ASB " (0x20425341)
  0x04 version (0x407 / 0x405)
  0x08 reserved (0)
  0x0C node count          n
  0x10 transition count    t
  0x14 warp record count   (0 in 73 files)
  0x18, 0x1C reserved
  0x20 [16]u32 = header words 8..23.  Their roles are NOT uniform (D-043):
         section offsets, inside the file in 83/83 -- w8, w9, w10, w11, w12,
           w13, w14, w15, w16, w18, w21, w22.  They are not stored in address
           order; proven identities:
             w9  = string pool, always last and ends exactly at EOF (83/83)
             w12 = end of the transition array = 0x68 + n*0x28 + t*0x24 (83/83)
             w10 = parameter table; w10 + 4 + 12*count == w9 (83/83)
             w11 = warp region head, w13 = warp region end
             w22 = interleaved region holding event lists (EVENT LISTS)
         w20 = string pool size, len(data) - w9 (83/83) -- not an offset
         w17 = target index space size - 1 = max transition target (81/81) --
               not an offset; see TRANSITION RECORD and A-052
         w6, w7, w19, w23 = small counts of unknown meaning (A-056); w23 is 0
           in all 83 files, w19 is 0 in 82 and 10 in CharaCommon

Node record, 0x28 bytes at 0x68, n records                                  D-044
  0x00 u32 name            offset into the string pool (valid in 83/83)
  0x04 u32 word1           0 in 1157/1159 nodes.  The two exceptions are
                           CharaCommon nodes 239/240 ("CharaCommon.root" and
                           "CharaCommon.rootJoint"); their value is a valid
                           string pool offset only when read directly
                           (4129 "TestHesitate", 4142 "TestHesitateJoint"),
                           while as an index into the w8 word array the same
                           value gives one non-string and one string word.
                           Both readings are recorded, nothing is chosen
                           (A-055)
  0x08 f32 -1.0            constant 0xbf800000 in every record
  0x0C, 0x10 u32 0         reserved
  0x14 [4]u32 hash         1001 distinct over 1159 nodes, never equal to a
                           transition hash (0/81 files).  Not CRC32, Murmur3 or
                           FNV-1a of the node name -- kept raw (D-050)
  0x24 u32 first_transition, index into the transition array (D-048)

Transition record, 0x24 bytes = 9 u32 at 0x68 + n*0x28, t records          D-045
  0x00 u32 source low16 | flags high16.  flags is exactly one of 0x0100 (8724),
           0x0101 (1264), 0 (9) or 1 (4).  The low 16 bits take only 20
           distinct values over the whole set (max 23) and are NOT node
           indices (source set is a subset of the target set in 1/81 files);
           the space they index is unknown (A-053).
  0x04 u32 event-list offset  (0 in 9409; 592 nonzero, all inside [w22, w10),
           all resolving to a count-prefixed pool-offset array)
  0x08 u32 condition block offset (unique per transition in 83/83 files)
  0x0C u32 target low16 | variant high16.  target values form exactly the set
           0..w17 in 81/81 files with transitions, i.e. they live in their own
           space of size w17+1, which only coincides with the node table in
           most files (9954/10001 < n; 47 values in 6 files exceed n).  Which
           object they address is not proven (A-052).  variant is 0 or 1 (114
           ones).
  0x10 u32 group, dense 0..K-1 per file and non-decreasing along the array
           (81/81 files)
  0x14 [4]u32 hash        9517 distinct over 10001, disjoint from node hashes;
           kept raw (A-053)

Condition block (variable length, starting at trans_end + 4*warp)            D-046
  Offsets are unique and ascending in 83/83 files; block i ends where block
  i+1 starts.  The last block ends at the smallest section offset that begins
  after it (w15 in 32 files, w11 = w14 = w15 in 49 -- the same address), and
  its size is a multiple of 4 in 81/81.  Word offsets inside a block are NOT
  proven, so every word is kept raw (D-047):
    word 0 = flags, 1343 distinct values (0 in 7894 records, 0x80000000-based,
             0xd0000000-based, ...)
    word 1 = clip name pool offset (8116 records) or a numeric value (1885
             records: float constant, small int or file offset into the
             condition region when the parameter is a table)
    later words mix tag words (0x02000002, 0x03000300, 0x03000003), pool
             offsets, file offsets and transition indices (A-054)

Parameter table at w10                                                      D-047
  u32 count, then count x 3 u32 = (offset a, parameter name pool offset b,
  parameter value pool offset c); w10 + 4 + 12*count == w9 in 83/83 files.
  b/c are always (parameter, value) pairs, e.g. ("TrueFalse","True"),
  ("Foot","Left"), ("CharaKind","Player"); 1895 records over 34 names, 184
  values and 195 distinct pairs.  `a` lies inside a condition block for
  760/1895 records, and each of those 760 blocks belongs to transitions with
  exactly one target index -- the only measured link between parameters and
  transitions.

Event lists at w22 (only reachable through transition word 1)
  u32 count, then count x u32 pool offsets.  The w22 region also holds warp
  bodies and condition blocks, so sequential walking is invalid -- the only
  correct entry points are transition offsets.

Warp records: offsets listed at trans_end .. trans_end + 4*warp_count, sorted,
  region [w11, w13).  They hold bone / IK / control names (Face, LookIKControll,
  DisableBlink, NpcMouth_00, ...) and floats, i.e. animation warp tracks, not
  clips.  Field meanings are not proven; decoded as a raw u32 word list with
  pool strings resolved (A-058).
"""
import struct

MAGIC = 0x20425341  # "ASB "
HEADER_WORDS = 24
NODE_BASE = 0x68
NODE_SIZE = 0x28
TRANS_SIZE = 0x24

# header word indices (word = u32 at 0x00 + 4*index)
W_NODE_COUNT = 3
W_TRANS_COUNT = 4
W_WARP_COUNT = 5
W_POOL = 9
W_PARAMS = 10
W_WARP_HEAD = 11
W_TRANS_END = 12
W_WARP_END = 13
W_PROPS = 8
W_TARGET_SPACE = 17
W_POOL_SIZE = 20
W_EVENTS = 22

# header words 8..23 that are file offsets in 83/83 files (D-042).  The others
# in that range are counts/sizes and must never be used as a section bound.
SECTION_WORDS = (8, 9, 10, 11, 12, 13, 14, 15, 16, 18, 21, 22)


class AsbError(ValueError):
    pass


def _f32(u):
    return struct.unpack("<f", struct.pack("<I", u))[0]


class _Pool:
    """String pool reader: a valid offset must start a NUL-terminated token."""

    def __init__(self, data, off):
        self.data = data
        self.off = off
        self.size = len(data) - off
        self.raw = data[off:]

    def string(self, off):
        if off is None or off < 0 or off >= self.size:
            return None
        if off and self.raw[off - 1] != 0:      # not the start of a token
            return None
        end = self.raw.find(b"\0", off)
        if end < 0:
            return None
        try:
            return self.raw[off:end].decode("utf-8")
        except UnicodeDecodeError:
            return None


def parse(data: bytes, name: str = "") -> dict:
    if len(data) < HEADER_WORDS * 4:
        raise AsbError(f"{name}: shorter than the ASB header")
    w = struct.unpack_from("<24I", data, 0)
    if w[0] != MAGIC:
        raise AsbError(f"{name}: bad magic {w[0]:#x}")
    n, t, nwarp = w[W_NODE_COUNT], w[W_TRANS_COUNT], w[W_WARP_COUNT]
    sections = list(w[8:24])                       # raw words 8..23, for reference
    section_offsets = [w[i] for i in SECTION_WORDS]  # only the real offsets
    pool = _Pool(data, w[W_POOL])
    if w[W_POOL] >= len(data):
        raise AsbError(f"{name}: string pool offset {w[W_POOL]:#x} past EOF")

    node_end = NODE_BASE + n * NODE_SIZE
    trans_end = node_end + t * TRANS_SIZE
    if trans_end != w[W_TRANS_END]:
        raise AsbError(f"{name}: transition array ends at {trans_end:#x}, "
                       f"header word 12 says {w[W_TRANS_END]:#x}")
    if trans_end > len(data):
        raise AsbError(f"{name}: transition array past EOF")

    nodes = []
    for i in range(n):
        o = NODE_BASE + i * NODE_SIZE
        name_off, prop, f008, r0c, r10 = struct.unpack_from("<5I", data, o)
        h = list(struct.unpack_from("<4I", data, o + 0x14))
        first = struct.unpack_from("<I", data, o + 0x24)[0]
        nodes.append({
            "index": i,
            "name": pool.string(name_off),
            "name_offset": name_off,
            "property_index": prop,
            # the rival reading of word1 (A-055): a direct string pool offset.
            # Meaningful only when word1 is nonzero, so it stays None otherwise.
            "word1_pool_string": pool.string(prop) if prop else None,
            "raw_f32_0x08": _f32(f008),
            "raw_0x0c": r0c,
            "raw_0x10": r10,
            "hash": h,
            "first_transition": first,
        })

    transitions = []
    ntarget = w[W_TARGET_SPACE] + 1
    for i in range(t):
        o = node_end + i * TRANS_SIZE
        ws = struct.unpack_from("<9I", data, o)
        s = ws[0] & 0xFFFF
        g = ws[3] & 0xFFFF
        transitions.append({
            "index": i,
            "source_raw": s,
            "source_index": s if s < n else None,
            "flags": ws[0] >> 16,
            "event_list_offset": ws[1],
            "condition_offset": ws[2],
            "target_raw": g,
            # targets live in their own index space of size w17+1 (D-045); the
            # node index is only a candidate reading, kept separately
            "target": g if g < ntarget else None,
            "target_in_nodes": g < n,
            "target_variant": ws[3] >> 16,
            "group": ws[4],
            "hash": list(ws[5:9]),
        })

    # -- condition blocks: contiguous, sorted by offset -----------------------
    # Block k ends exactly where block k+1 starts (offsets unique and ascending
    # in 83/83 files).  The last block ends at the smallest real section offset
    # that starts after it (D-046) -- non-offset words must not be candidates.
    order = sorted(range(t), key=lambda k: transitions[k]["condition_offset"])
    cond_lo = trans_end + 4 * nwarp
    last_end = None
    if order:
        last_start = transitions[order[-1]]["condition_offset"]
        after = [v for v in section_offsets if v > last_start]
        last_end = min(after) if after else len(data)
    cond_hi = last_end if last_end is not None else cond_lo
    for pos, k in enumerate(order):
        tr = transitions[k]
        start = tr["condition_offset"]
        if pos + 1 < len(order):
            end = transitions[order[pos + 1]]["condition_offset"]
            exact = True
        else:
            end = last_end
            exact = False
        block = {"offset": start, "size": max(0, end - start),
                 "end_exact": exact,
                 "in_region": cond_lo <= start and start < max(end, 1)}
        if start + 4 <= len(data) and end > start:
            count = min((end - start) // 4, max(0, (len(data) - start) // 4))
            words = list(struct.unpack_from("<%dI" % count, data, start)) if count else []
            block["flags"] = words[0] if words else None
            block["words"] = words
            if len(words) > 1:
                v = words[1]
                clip = pool.string(v)
                if clip is not None:
                    block["clip"] = clip
                    block["value_raw"] = None
                else:
                    block["clip"] = None
                    block["value_raw"] = v
                    block["value_kind"] = _num_kind(v, cond_lo, cond_hi)
                    if block["value_kind"] == "float":
                        block["value_float"] = _f32(v)
        tr["condition"] = block

    # -- parameter/value table (w10) -----------------------------------------
    params = []
    if w[W_PARAMS] + 4 <= len(data):
        count = struct.unpack_from("<I", data, w[W_PARAMS])[0]
        room = (len(data) - w[W_PARAMS] - 4) // 12
        count = min(count, room)
        for i in range(count):
            a, b, c = struct.unpack_from("<3I", data, w[W_PARAMS] + 4 + 12 * i)
            params.append({"offset": a, "parameter": pool.string(b), "value": pool.string(c)})
    params_end = w[W_PARAMS] + 4 + 12 * len(params)

    # -- event lists referenced from transitions -----------------------------
    event_lists = {}
    for tr in transitions:
        off = tr["event_list_offset"]
        if not off:
            continue
        if off in event_lists:
            continue
        if off + 4 > len(data):
            event_lists[off] = {"offset": off, "count": None, "values": []}
            continue
        count = struct.unpack_from("<I", data, off)[0]
        count = min(count, max(0, (len(data) - off - 4) // 4))
        vals = []
        for j in range(count):
            v = struct.unpack_from("<I", data, off + 4 + 4 * j)[0]
            vals.append({"offset": v, "name": pool.string(v)})
        event_lists[off] = {"offset": off, "count": count, "values": vals}

    # -- warp records --------------------------------------------------------
    warps = []
    warp_lo, warp_hi = w[W_WARP_HEAD], w[W_WARP_END]
    offsets = []
    for i in range(nwarp):
        p = trans_end + 4 * i
        if p + 4 <= len(data):
            offsets.append(struct.unpack_from("<I", data, p)[0])
    for i, start in enumerate(offsets):
        end = offsets[i + 1] if i + 1 < len(offsets) else warp_hi
        if end <= start or start < 0 or start >= len(data):
            warps.append({"index": i, "offset": start, "words": []})
            continue
        count = min((end - start) // 4, max(0, (len(data) - start) // 4))
        words = list(struct.unpack_from("<%dI" % count, data, start))
        warps.append({
            "index": i,
            "offset": start,
            "size": end - start,
            "words": words,
            "strings": [pool.string(v) for v in words],
        })

    # -- w8 property table ---------------------------------------------------
    props = []
    if w[W_PROPS] < len(data):
        count = min((w[W_POOL] - w[W_PROPS]) // 4, (len(data) - w[W_PROPS]) // 4)
        if count > 0:
            props = list(struct.unpack_from("<%dI" % count, data, w[W_PROPS]))

    # can nodes partition the transition array by first_transition?  (D-048)
    firsts_ok = bool(n) and all(nodes[k]["first_transition"] < max(t, 1) for k in range(n))
    firsts_sorted = firsts_ok and all(
        nodes[k]["first_transition"] <= nodes[k + 1]["first_transition"] for k in range(n - 1))

    return {
        "name": name,
        "size": len(data),
        "version": w[1],
        "counts": {"nodes": n, "transitions": t, "warps": nwarp,
                   "parameter_cases": len(params), "target_space": ntarget},
        "header": {"reserved_0x08": w[2], "reserved": [w[6], w[7]],
                   "words_8_23": sections,
                   "section_offsets": {str(i): w[i] for i in SECTION_WORDS},
                   "counts_unknown": {"w17_target_space-1": w[W_TARGET_SPACE],
                                      "w19": w[19], "w23": w[23]},
                   "pool_size_word": w[W_POOL_SIZE]},
        "string_pool": {"offset": w[W_POOL], "size": pool.size,
                        "ends_at_eof": w[W_POOL] + pool.size == len(data),
                        "size_matches_word20": w[W_POOL_SIZE] == pool.size},
        "regions": {"nodes": [NODE_BASE, node_end], "transitions": [node_end, trans_end],
                    "warp_offsets": [trans_end, trans_end + 4 * nwarp],
                    "condition": [cond_lo, cond_hi], "params": [w[W_PARAMS], params_end],
                    "warp_records": [warp_lo, warp_hi]},
        "nodes": nodes,
        "transitions": transitions,
        "parameter_table": params,
        "event_lists": [event_lists[k] for k in sorted(event_lists)],
        "warps": warps,
        "property_table": props,
        "partition_hint": {"first_transition_in_range": firsts_ok,
                           "first_transition_sorted": firsts_sorted},
    }


def _num_kind(v, lo, hi):
    """Classify a numeric condition word; the split itself is A-054."""
    if lo <= v < hi:
        return "offset"
    if v in (0x3f800000, 0x40800000, 0x41800000, 0xbf800000, 0x3dcccccd) or (v & 0x7F800000) == 0x7F800000:
        return "float"
    if abs(_f32(v)) > 1e-6 and abs(_f32(v)) < 1e6:
        return "float"
    return "int"


def load(path):
    from pathlib import Path
    p = Path(path)
    return parse(p.read_bytes(), p.name)


def stats(paths):
    """Run over every file and return a coverage report (used by the exporter)."""
    from collections import Counter
    c = Counter()
    bad = []
    for p in paths:
        try:
            d = load(p)
        except AsbError as e:
            bad.append(str(e))
            continue
        c["files"] += 1
        c["nodes"] += d["counts"]["nodes"]
        c["transitions"] += d["counts"]["transitions"]
        c["warps"] += d["counts"]["warps"]
        c["parameter_cases"] += d["counts"]["parameter_cases"]
        c["event_lists"] += len(d["event_lists"])
        c["cond_with_clip"] += sum(1 for tr in d["transitions"] if tr["condition"].get("clip"))
        c["cond_with_value"] += sum(1 for tr in d["transitions"] if tr["condition"].get("value_raw") is not None)
        c["cond_outside_region"] += sum(1 for tr in d["transitions"] if not tr["condition"].get("in_region", False))
        c["targets_out_of_range"] += sum(1 for tr in d["transitions"] if tr["target"] is None)
        c["pool_ends_at_eof"] += int(d["string_pool"]["ends_at_eof"])
        c["first_transition_sorted"] += int(d["partition_hint"]["first_transition_sorted"])
    return {"counts": dict(c), "errors": bad}