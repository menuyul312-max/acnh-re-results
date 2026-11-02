"""BFLYT (layout, version 9 as used by ACNH) -> pane tree dict.

Pane common block (0x4C after the 8-byte section header):
  u8 flags (bit0 visible), u8 origin, u8 alpha, u8 part_scale, char name[24],
  char user[8], vec3 translate, vec3 rotate, vec2 scale, vec2 size
pic1: + u32 vertex colours[4] (RGBA8), u16 material, u8 texcoord count, u8 pad, texcoords
txt1: + u16 buf bytes, u16 str bytes, u16 material, u16 font, u8 pos, u8 align, u8 flags,
      u8 pad, f32 italic, u32 text offset, u32 colour top, u32 colour bottom, vec2 font size,
      f32 char space, f32 line space   (text is UTF-16 at the section-relative offset)
Unknown or unparsed pane payloads are kept as hex so nothing is lost.
"""
import struct


def _cstr(b, o, n):
    return b[o:o + n].split(b"\0", 1)[0].decode("utf-8", "replace")


def _rgba(v):
    return [v & 0xFF, (v >> 8) & 0xFF, (v >> 16) & 0xFF, v >> 24]


def _str_table(b, o):
    n = struct.unpack_from("<H", b, o + 8)[0]
    base = o + 0xC
    offs = struct.unpack_from(f"<{n}I", b, base)
    return [b[base + x:b.index(b"\0", base + x)].decode("utf-8", "replace") for x in offs]


def _pane(b, o, kind):
    flags, origin, alpha, pscale = b[o + 8:o + 12]
    p = {"type": kind, "name": _cstr(b, o + 12, 24), "user": _cstr(b, o + 36, 8),
         "visible": bool(flags & 1), "origin": origin, "alpha": alpha,
         "translate": list(struct.unpack_from("<3f", b, o + 44)),
         "rotate": list(struct.unpack_from("<3f", b, o + 56)),
         "scale": list(struct.unpack_from("<2f", b, o + 68)),
         "size": list(struct.unpack_from("<2f", b, o + 76)), "children": []}
    return p


def read_bflyt(b: bytes):
    if b[:4] != b"FLYT":
        raise ValueError("not FLYT")
    hs = struct.unpack_from("<H", b, 6)[0]
    version = struct.unpack_from("<I", b, 8)[0]
    nsec = struct.unpack_from("<H", b, 0x10)[0]
    out = {"version": version, "textures": [], "fonts": [], "materials": [], "root": None,
           "groups": [], "layout": {}}
    stack, last, o = [], None, hs
    for _ in range(nsec):
        magic = b[o:o + 4].decode("ascii", "replace")
        size = struct.unpack_from("<I", b, o + 4)[0]
        if magic == "lyt1":
            out["layout"] = {"origin": b[o + 8], "size": list(struct.unpack_from("<2f", b, o + 0xC)),
                             "name": _cstr(b, o + 0x1C, size - 0x1C)}
        elif magic == "txl1":
            out["textures"] = _str_table(b, o)
        elif magic == "fnl1":
            out["fonts"] = _str_table(b, o)
        elif magic == "mat1":
            n = struct.unpack_from("<H", b, o + 8)[0]
            for i in range(n):
                mo = o + struct.unpack_from("<I", b, o + 0xC + i * 4)[0]
                name = _cstr(b, mo, 28)
                flags = struct.unpack_from("<I", b, mo + 28)[0]
                ntex = flags & 3
                # v9: name[28], u32 flags, u32 (unknown), black, white (RGBA8), texture maps
                texmaps = []
                for k in range(ntex):
                    ti, ws, wt = struct.unpack_from("<HBB", b, mo + 44 + k * 4)
                    texmaps.append({"texture": ti, "wrap_s": ws, "wrap_t": wt})
                out["materials"].append({"name": name, "flags": flags,
                                         "black": _rgba(struct.unpack_from("<I", b, mo + 36)[0]),
                                         "white": _rgba(struct.unpack_from("<I", b, mo + 40)[0]),
                                         "texmaps": texmaps})
        elif magic in ("pan1", "pic1", "txt1", "wnd1", "bnd1", "prt1", "scr1", "ali1", "cpt1"):
            p = _pane(b, o, magic)
            q = o + 8 + 0x4C
            if magic == "pic1":
                cols = struct.unpack_from("<4I", b, q)
                p["vertex_colors"] = [_rgba(c) for c in cols]
                p["material"], ntc = struct.unpack_from("<HB", b, q + 16)
                p["texcoords"] = [list(struct.unpack_from("<8f", b, q + 20 + k * 32)) for k in range(ntc)]
            elif magic == "txt1":
                bufb, strb, mat, font = struct.unpack_from("<4H", b, q)
                p.update(material=mat, font=font, text_position=b[q + 8], text_align=b[q + 9],
                         italic=struct.unpack_from("<f", b, q + 12)[0])
                toff = struct.unpack_from("<I", b, q + 16)[0]
                ct, cb = struct.unpack_from("<2I", b, q + 20)
                p["color_top"], p["color_bottom"] = _rgba(ct), _rgba(cb)
                p["font_size"] = list(struct.unpack_from("<2f", b, q + 28))
                p["char_space"], p["line_space"] = struct.unpack_from("<2f", b, q + 36)
                p["text"] = b[o + toff:o + toff + strb].decode("utf-16-le", "replace").rstrip("\0") if toff and strb else ""
            elif magic == "prt1":
                cnt = struct.unpack_from("<I", b, q)[0]
                p["magnify"] = list(struct.unpack_from("<2f", b, q + 4))
                p["part_layout"] = _cstr(b, q + 12 + cnt * 0x28, 64)
                p["property_count"] = cnt
            elif magic != "pan1":
                p["payload_hex"] = b[q:o + size].hex()
            if stack:
                stack[-1]["children"].append(p)
            elif out["root"] is None:
                out["root"] = p
            last = p
        elif magic == "pas1":
            stack.append(last)
        elif magic == "pae1":
            stack.pop()
        elif magic == "grp1":
            name = _cstr(b, o + 8, 33)
            n = struct.unpack_from("<H", b, o + 8 + 34)[0]
            out["groups"].append({"name": name, "panes": [_cstr(b, o + 8 + 36 + k * 24, 24) for k in range(n)]})
        o += size
    return out


def read_bflan_summary(b: bytes):
    """Animation header only: name/frame range/tags kept for the runtime; payload as hex."""
    if b[:4] != b"FLAN":
        raise ValueError("not FLAN")
    hs = struct.unpack_from("<H", b, 6)[0]
    nsec = struct.unpack_from("<H", b, 0x10)[0]
    out, o = {"sections": []}, hs
    for _ in range(nsec):
        magic = b[o:o + 4].decode("ascii", "replace")
        size = struct.unpack_from("<I", b, o + 4)[0]
        if magic == "pai1":
            out["frame_size"] = struct.unpack_from("<H", b, o + 8)[0]
            out["loop"] = bool(b[o + 10])
        out["sections"].append({"magic": magic, "size": size, "hex": b[o + 8:o + size].hex()})
        o += size
    return out
