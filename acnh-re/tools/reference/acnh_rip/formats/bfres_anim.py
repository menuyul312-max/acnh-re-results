"""BFRES skeletal animation (FSKA, v0.9) reader and sampler.

FSKA (0x50):  0x04 flags (0x4 loop, 0x7000 rotation mode: 0x1000 = euler XYZ)
              0x08 name  0x20 bind-index array  0x28 bone-anim array
              0x40 u32 frame_count  0x44 u32 curve_count  0x4C u16 bone_anim_count
BoneAnim (0x38): 0x00 name  0x08 curves  0x10 base data  0x28 u32 flags
              0x2E u8 curve_count ; base flags 0x08 scale / 0x10 rotate / 0x20 translate
Curve (0x30): 0x00 frames  0x08 keys  0x10 u16 flags  0x12 u16 key_count
              0x14 u32 target offset  0x18 start  0x1C end  0x20 scale  0x24 offset  0x28 delta
  flags: bits0-1 frame type (f32, fixed 10.5 s16, u8), bits2-3 key type
         (f32, s16, s8), bits4-6 curve type (cubic, linear, baked float, ...)
Target offsets: scale 0x04/0x08/0x0C, translate 0x10/0x14/0x18, rotate 0x20..0x2C.
"""
import struct

_TARGET = {0x04: ("s", 0), 0x08: ("s", 1), 0x0C: ("s", 2),
           0x10: ("t", 0), 0x14: ("t", 1), 0x18: ("t", 2),
           0x20: ("r", 0), 0x24: ("r", 1), 0x28: ("r", 2), 0x2C: ("r", 3)}


def _read_curve(r, c):
    flags, nkey = r.u16(c + 0x10), r.u16(c + 0x12)
    target = r.u32(c + 0x14)
    start, end, scale, offset = r.fs(c + 0x18, 4)
    ftype, ktype, ctype = flags & 3, (flags >> 2) & 3, (flags >> 4) & 7
    fp, kp = r.u64(c), r.u64(c + 8)
    if ftype == 0:
        frames = list(r.fs(fp, nkey))
    elif ftype == 1:
        frames = [v / 32.0 for v in struct.unpack_from(f"<{nkey}h", r.b, fp)]
    else:
        frames = list(r.b[fp:fp + nkey])
    ncoef = {0: 4, 1: 2}.get(ctype, 1)
    n = nkey * ncoef
    code = {0: "f", 1: "h", 2: "b"}[ktype]
    raw = struct.unpack_from(f"<{n}{code}", r.b, kp)
    keys = []
    for k in range(nkey):
        co = raw[k * ncoef:(k + 1) * ncoef]
        if ktype == 0:
            vals = list(co)
        else:
            vals = [co[0] * scale + offset] + [v * scale for v in co[1:]]
        keys.append(vals)
    return {"target": target, "type": ctype, "frames": frames, "keys": keys,
            "start": start, "end": end}


def eval_curve(cv, frame):
    fr, keys = cv["frames"], cv["keys"]
    if frame <= fr[0]:
        return keys[0][0]
    for i in range(len(fr) - 1):
        if fr[i] <= frame < fr[i + 1]:
            k = keys[i]
            t = (frame - fr[i]) / (fr[i + 1] - fr[i])
            if cv["type"] == 0:
                return k[0] + k[1] * t + k[2] * t * t + k[3] * t * t * t
            if cv["type"] == 1:
                return k[0] + k[1] * t
            return k[0]
    k = keys[-1]
    if cv["type"] == 0:  # last segment evaluated at its end
        return k[0] + k[1] + k[2] + k[3]
    if cv["type"] == 1:
        return k[0] + k[1]
    return k[0]


def read_fska(r, o):
    if r.b[o:o + 4] != b"FSKA":
        raise ValueError("FSKA expected")
    flags = r.u32(o + 0x04)
    anim = {"name": r.str_at(o + 0x08), "flags": flags, "loop": bool(flags & 0x4),
            "euler": (flags & 0x7000) == 0x1000, "frame_count": r.u32(o + 0x40), "bones": []}
    n_bone = r.u16(o + 0x4C)
    for i in range(n_bone):
        e = r.u64(o + 0x28) + i * 0x38
        bflags = r.u32(e + 0x28)
        base, p = {}, r.u64(e + 0x10)
        if bflags & 0x08:
            base["s"] = r.fs(p, 3); p += 12
        if bflags & 0x10:
            base["r"] = r.fs(p, 4); p += 16
        if bflags & 0x20:
            base["t"] = r.fs(p, 3); p += 12
        curves = [_read_curve(r, r.u64(e + 0x08) + k * 0x30) for k in range(r.u8(e + 0x2E))]
        anim["bones"].append({"name": r.str_at(e), "flags": bflags, "base": base, "curves": curves})
    return anim


def sample(anim):
    """Per bone: {"t": [[x,y,z]...], "r": [[x,y,z,w]...] (quaternion), "s": [...]}
    sampled at every integer frame 0..frame_count. Components without curves use
    the base value; channels with neither curve nor base are omitted (rest pose)."""
    from .bfres import _euler_to_quat
    n = anim["frame_count"] + 1
    out = {}
    for b in anim["bones"]:
        tracks = {}
        by_ch = {"s": {}, "t": {}, "r": {}}
        for cv in b["curves"]:
            ch, comp = _TARGET.get(cv["target"], (None, None))
            if ch:
                by_ch[ch][comp] = cv
        for ch, size in (("s", 3), ("t", 3), ("r", 4)):
            if not by_ch[ch] and ch not in b["base"]:
                continue
            base = list(b["base"].get(ch, (1.0, 1.0, 1.0) if ch == "s" else (0.0, 0.0, 0.0, 1.0)[:size]))
            if not by_ch[ch]:
                vals = [base]
            else:
                vals = []
                for f in range(n):
                    v = list(base)
                    for comp, cv in by_ch[ch].items():
                        v[comp] = eval_curve(cv, f)
                    vals.append(v)
            if ch == "r" and anim["euler"]:
                vals = [list(_euler_to_quat(v[:3])) for v in vals]
            tracks[ch] = [[round(x, 6) for x in v] for v in vals]
        if tracks:
            out[b["name"]] = tracks
    return out
