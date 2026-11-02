"""BFRES (Switch, version 0.9.x as used by ACNH 1.0) reader.

Offsets below were mapped from the game's own files (PlayerBody,
CharactorAnimation) and cross-checked with element counts.
Covers: models (skeleton, vertex buffers with all attribute formats, shapes,
LOD meshes, skinning), materials (textures, samplers, shader assign, render
info, shader params), external files (embedded BNTX) and animations
(FSKA skeletal, FMAA material, FVIS bone visibility; see anim section).
"""
import math
import struct

# --- vertex attribute formats: byte 1 = layout, byte 0 = numeric type -------
# layout -> component bit sizes
_LAYOUTS = {
    0x02: (8,), 0x09: (8, 8), 0x0A: (16,), 0x0B: (8, 8, 8, 8),
    0x0E: (10, 10, 10, 2), 0x12: (16, 16), 0x14: (32,), 0x15: (16, 16, 16, 16),
    0x17: (32, 32), 0x18: (32, 32, 32), 0x19: (32, 32, 32, 32),
}
UNORM, SNORM, UINT, SINT, FLOAT = 1, 2, 3, 4, 5


class BfresError(ValueError):
    pass


class Reader:
    def __init__(self, data: bytes):
        self.b = data

    def u8(self, o): return self.b[o]
    def u16(self, o): return struct.unpack_from("<H", self.b, o)[0]
    def s16(self, o): return struct.unpack_from("<h", self.b, o)[0]
    def u32(self, o): return struct.unpack_from("<I", self.b, o)[0]
    def s32(self, o): return struct.unpack_from("<i", self.b, o)[0]
    def f32(self, o): return struct.unpack_from("<f", self.b, o)[0]
    def u64(self, o): return struct.unpack_from("<Q", self.b, o)[0]
    def fs(self, o, n): return struct.unpack_from(f"<{n}f", self.b, o)

    def string(self, ptr):
        if ptr == 0:
            return None
        n = self.u16(ptr)
        return self.b[ptr + 2:ptr + 2 + n].decode("utf-8", "replace")

    def str_at(self, o):
        return self.string(self.u64(o))

    def dict_keys(self, ptr):
        """ResDic: u32 magic/0, u32 count, then (count+1) nodes of 0x10; node 0 is root."""
        if ptr == 0:
            return []
        n = self.s32(ptr + 4)
        return [self.str_at(ptr + 8 + (i + 1) * 0x10 + 8) for i in range(n)]


def decode_attribute(raw: bytes, fmt: int, count: int, stride: int, offset: int):
    """Decode a vertex attribute into a list of tuples of Python numbers."""
    typ, lay = fmt & 0xFF, fmt >> 8
    if lay not in _LAYOUTS:
        raise BfresError(f"unsupported attribute layout {fmt:#06x}")
    bits = _LAYOUTS[lay]
    out = []
    if bits == (10, 10, 10, 2):
        for i in range(count):
            v = struct.unpack_from("<I", raw, offset + i * stride)[0]
            comps = []
            for sh in (0, 10, 20):
                c = (v >> sh) & 0x3FF
                if typ == SNORM:
                    c = c - 1024 if c >= 512 else c
                    comps.append(max(c / 511.0, -1.0))
                else:
                    comps.append(c / 1023.0)
            w = v >> 30
            comps.append((w - 4 if w >= 2 else w) if typ == SNORM else w / 3.0)
            out.append(tuple(comps))
        return out
    size = bits[0]
    n = len(bits)
    code = {(8, UNORM): "B", (8, UINT): "B", (8, SNORM): "b", (8, SINT): "b",
            (16, UNORM): "H", (16, UINT): "H", (16, SNORM): "h", (16, SINT): "h", (16, FLOAT): "e",
            (32, UINT): "I", (32, SINT): "i", (32, FLOAT): "f", (32, UNORM): "I", (32, SNORM): "i"}
    key = (size, typ if typ in (UNORM, SNORM, UINT, SINT, FLOAT) else UINT)
    if key not in code:
        raise BfresError(f"unsupported attribute format {fmt:#06x}")
    st = struct.Struct("<" + code[key] * n)
    norm = {(8, UNORM): 255.0, (16, UNORM): 65535.0, (8, SNORM): 127.0, (16, SNORM): 32767.0}.get(key)
    for i in range(count):
        v = st.unpack_from(raw, offset + i * stride)
        if norm:
            v = tuple(max(c / norm, -1.0) for c in v)
        out.append(v)
    return out


# --------------------------------------------------------------------------
class Bfres:
    def __init__(self, data: bytes):
        if data[:4] != b"FRES":
            raise BfresError("not BFRES")
        r = self.r = Reader(data)
        self.version = r.u32(0x8)
        if (self.version >> 16) != 9:
            raise BfresError(f"unsupported BFRES version {self.version:#x}")
        self.name = r.str_at(0x20)
        bufinfo = r.u64(0xB0)
        self.gpu_base = r.u32(bufinfo + 8) if bufinfo else 0
        self.counts = {
            "model": r.u16(0xDC), "skeletal_anim": r.u16(0xE2), "material_anim": r.u16(0xE4),
            "bone_vis_anim": r.u16(0xE6), "shape_anim": r.u16(0xE8), "scene_anim": r.u16(0xEA),
            "external": r.u16(0xEC),
        }
        self._model_arr = r.u64(0x28)
        self._ska_arr = r.u64(0x58)
        self._maa_arr = r.u64(0x68)
        self._bva_arr = r.u64(0x78)
        self._ext_arr = r.u64(0xB8)
        self._ext_dict = r.u64(0xC0)

    # ---- external files (BNTX) ----
    def external_files(self):
        names = self.r.dict_keys(self._ext_dict)
        out = {}
        for i in range(self.counts["external"]):
            o = self._ext_arr + i * 0x10
            off, size = self.r.u64(o), self.r.u32(o + 8)
            out[names[i] if i < len(names) else f"ext{i}"] = self.r.b[off:off + size]
        return out

    # ---- models ----
    def models(self):
        return [self._model(self._model_arr + i * 0x78) for i in range(self.counts["model"])]

    def _model(self, o):
        r = self.r
        m = {"name": r.str_at(o + 0x08)}
        m["skeleton"] = self._skeleton(r.u64(o + 0x18))
        n_vb, n_shape, n_mat = r.u16(o + 0x68), r.u16(o + 0x6A), r.u16(o + 0x6C)
        vbs = [self._vertex_buffer(r.u64(o + 0x20) + i * 0x58) for i in range(n_vb)]
        m["materials"] = [self._material(r.u64(o + 0x38) + i * 0xA8) for i in range(n_mat)]
        m["shapes"] = [self._shape(r.u64(o + 0x28) + i * 0x60, vbs) for i in range(n_shape)]
        return m

    def _skeleton(self, o):
        r = self.r
        flags = r.u32(o + 0x04)
        n_bone, n_smooth, n_rigid = r.u16(o + 0x38), r.u16(o + 0x3A), r.u16(o + 0x3C)
        bones = []
        euler = (flags & 0x7000) == 0x1000
        for i in range(n_bone):
            b = r.u64(o + 0x10) + i * 0x60
            rot = r.fs(b + 0x44, 4)
            bones.append({
                "name": r.str_at(b),
                "index": r.u16(b + 0x28),
                "parent": r.s16(b + 0x2A),
                "smooth_index": r.s16(b + 0x2C),
                "rigid_index": r.s16(b + 0x2E),
                "billboard": r.s16(b + 0x30),
                "flags": r.u32(b + 0x34),
                "scale": r.fs(b + 0x38, 3),
                "rotation": _euler_to_quat(rot[:3]) if euler else rot,
                "translation": r.fs(b + 0x54, 3),
            })
        n_mat = n_smooth + n_rigid
        mtx_to_bone = [r.u16(r.u64(o + 0x18) + i * 2) for i in range(n_mat)] if n_mat else []
        inv = r.u64(o + 0x20)
        inverse = [r.fs(inv + i * 48, 12) for i in range(n_smooth)] if inv else []
        return {"flags": flags, "bones": bones, "matrix_to_bone": mtx_to_bone,
                "num_smooth": n_smooth, "num_rigid": n_rigid, "inverse_model": inverse}

    def _vertex_buffer(self, o):
        r = self.r
        if self.r.b[o:o + 4] != b"FVTX":
            raise BfresError("FVTX expected")
        n_attr, n_buf = r.u8(o + 0x4C), r.u8(o + 0x4D)
        count = r.u32(o + 0x50)
        sizes = [r.u32(r.u64(o + 0x30) + i * 0x10) for i in range(n_buf)]
        strides = [r.u32(r.u64(o + 0x38) + i * 0x10) for i in range(n_buf)]
        base = self.gpu_base + r.u32(o + 0x48)
        offs, cur = [], base
        for s in sizes:
            cur = (cur + 7) & ~7
            offs.append(cur)
            cur += s
        attrs = {}
        for i in range(n_attr):
            a = r.u64(o + 0x08) + i * 0x10
            name = r.str_at(a)
            fmt = r.u8(a + 8) | (r.u8(a + 9) << 8)
            boff, bidx = r.u16(a + 0x0C), r.u16(a + 0x0E)
            attrs[name] = {"format": fmt, "buffer": bidx, "offset": boff}
        return {"count": count, "attrs": attrs, "buf_offsets": offs, "strides": strides,
                "skin_influence": r.u32(o + 0x54)}

    def read_attribute(self, vb, name):
        a = vb["attrs"][name]
        return decode_attribute(self.r.b, a["format"], vb["count"], vb["strides"][a["buffer"]],
                                vb["buf_offsets"][a["buffer"]] + a["offset"])

    def _shape(self, o, vbs):
        r = self.r
        s = {
            "name": r.str_at(o + 0x08),
            "flags": r.u32(o + 0x04),
            "material": r.u16(o + 0x52),
            "bone": r.u16(o + 0x54),
            "vertex_buffer": r.u16(o + 0x56),
            "skin_count": r.u8(o + 0x5A),
        }
        n_skin, n_mesh = r.u16(o + 0x58), r.u8(o + 0x5B)
        s["skin_bones"] = [r.u16(r.u64(o + 0x20) + i * 2) for i in range(n_skin)] if n_skin else []
        meshes = []
        for i in range(n_mesh):
            m = r.u64(o + 0x18) + i * 0x38
            prim, ifmt, icount = r.u32(m + 0x24), r.u32(m + 0x28), r.u32(m + 0x2C)
            first = r.u32(m + 0x30)
            start = self.gpu_base + r.u32(m + 0x20)
            code = {0: "B", 1: "H", 2: "I"}[ifmt]
            idx = struct.unpack_from(f"<{icount}{code}", self.r.b, start)
            meshes.append({"primitive": prim, "indices": [i + first for i in idx] if first else list(idx)})
        s["lods"] = meshes
        s["vb"] = vbs[s["vertex_buffer"]]
        return s

    def _material(self, o):
        r = self.r
        n_ri, n_tex, n_samp = r.u16(o + 0x9A), r.u8(o + 0x9C), r.u8(o + 0x9D)
        n_param = r.u16(o + 0x9E)
        mat = {"name": r.str_at(o + 0x08), "flags": r.u32(o + 0x04)}
        mat["textures"] = [r.str_at(r.u64(o + 0x30) + i * 8) for i in range(n_tex)]
        # +0x38 runtime sampler slots, +0x40 sampler info (0x20 each), +0x48 sampler dict
        samp_names = r.dict_keys(r.u64(o + 0x48))
        sampler_arr = r.u64(o + 0x40)
        mat["samplers"] = []
        for i in range(n_samp):
            sd = r.b[sampler_arr + i * 0x20:sampler_arr + i * 0x20 + 0x20]
            mat["samplers"].append({"name": samp_names[i] if i < len(samp_names) else f"s{i}",
                                    "wrap": [sd[0], sd[1], sd[2]], "desc": sd.hex()})
        # render info
        ri = []
        for i in range(n_ri):
            e = r.u64(o + 0x10) + i * 0x18
            name, dptr, cnt, typ = r.str_at(e), r.u64(e + 8), r.u16(e + 0x10), r.u8(e + 0x12)
            if typ == 0:
                val = [r.s32(dptr + k * 4) for k in range(cnt)]
            elif typ == 1:
                val = [r.f32(dptr + k * 4) for k in range(cnt)]
            else:
                val = [r.str_at(dptr + k * 8) for k in range(cnt)]
            ri.append((name, val))
        mat["render_info"] = dict(ri)
        # shader assign
        sa = r.u64(o + 0x20)
        if sa:
            n_attr_a, n_samp_a, n_opt = r.u8(sa + 0x44), r.u8(sa + 0x45), r.u16(sa + 0x46)
            mat["shader"] = {
                "archive": r.str_at(sa), "model": r.str_at(sa + 8),
                "attrib_assign": dict(zip(r.dict_keys(r.u64(sa + 0x18)),
                                          [r.str_at(r.u64(sa + 0x10) + i * 8) for i in range(n_attr_a)])),
                "sampler_assign": dict(zip(r.dict_keys(r.u64(sa + 0x28)),
                                           [r.str_at(r.u64(sa + 0x20) + i * 8) for i in range(n_samp_a)])),
                "options": dict(zip(r.dict_keys(r.u64(sa + 0x38)),
                                    [r.str_at(r.u64(sa + 0x30) + i * 8) for i in range(n_opt)])),
            }
        # shader params (values read from the source param block)
        src = r.u64(o + 0x60)
        params = {}
        for i in range(n_param):
            p = r.u64(o + 0x50) + i * 0x20
            name, typ, size, doff = r.str_at(p + 8), r.u8(p + 0x10), r.u8(p + 0x11), r.u16(p + 0x12)
            raw = r.b[src + doff:src + doff + size]
            if size < 4:
                params[name] = list(raw)
            elif typ < 12:              # bool/int/uint (vectors)
                params[name] = list(struct.unpack(f"<{size // 4}i", raw))
            else:                       # float, floatNxM, srt
                params[name] = [round(v, 6) for v in struct.unpack(f"<{size // 4}f", raw)]
        mat["params"] = params
        return mat

    # ---- animations (filled by bfres_anim) ----
    def skeletal_anims(self):
        from .bfres_anim import read_fska
        return [read_fska(self.r, self._ska_arr + i * 0x50) for i in range(self.counts["skeletal_anim"])]


def _euler_to_quat(e):
    x, y, z = e
    cx, sx = math.cos(x / 2), math.sin(x / 2)
    cy, sy = math.cos(y / 2), math.sin(y / 2)
    cz, sz = math.cos(z / 2), math.sin(z / 2)
    # XYZ intrinsic order (R = Rz * Ry * Rx), as used by NintendoWare.
    return (sx * cy * cz - cx * sy * sz,
            cx * sy * cz + sx * cy * sz,
            cx * cy * sz - sx * sy * cz,
            cx * cy * cz + sx * sy * sz)
