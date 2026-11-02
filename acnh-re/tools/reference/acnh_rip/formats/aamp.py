"""AAMP v2 (Nintendo parameter archive) reader. Names are CRC32 hashes; pass a hash->name dict to resolve.
Layout: 0x14 pio offset, 0x18 list count, 0x1c obj count, 0x20 param count; root list at 0x38 (pio_offset+0x30).
list: u32 hash, u16 lists_off(*4, rel to list), u16 nlists, u16 objs_off(*4), u16 nobjs ... (BOTW layout)
"""
import struct, zlib

TYPES = {0: 'bool', 1: 'f32', 2: 'int', 3: 'vec2', 4: 'vec3', 5: 'vec4', 6: 'color', 7: 'str32', 8: 'str64',
         9: 'curve1', 10: 'curve2', 11: 'curve3', 12: 'curve4', 13: 'buf_int', 14: 'buf_f32', 15: 'str256',
         16: 'quat', 17: 'u32', 18: 'buf_u32', 19: 'buf_bin', 20: 'str512'}
SIZES = {0: 4, 1: 4, 2: 4, 3: 8, 4: 12, 5: 16, 6: 16, 7: 32, 8: 64, 15: 256, 16: 16, 17: 4, 20: 512,
         9: 0x30, 10: 0x60, 11: 0x90, 12: 0xc0}


def crc(name: str) -> int:
    return zlib.crc32(name.encode()) & 0xffffffff


def parse(d: bytes, names=None):
    names = names or {}
    if d[:4] != b'AAMP':
        raise ValueError('not AAMP')
    pio = struct.unpack_from('<I', d, 0x14)[0]
    root = 0x30 + pio

    def nm(h):
        return names.get(h, '%08x' % h)

    def val(off, t):
        if t == 0: return bool(struct.unpack_from('<I', d, off)[0])
        if t == 1: return round(struct.unpack_from('<f', d, off)[0], 6)
        if t in (2, 17): return struct.unpack_from('<I' if t == 17 else '<i', d, off)[0]
        if t in (3, 4, 5, 6, 16):
            n = {3: 2, 4: 3, 5: 4, 6: 4, 16: 4}[t]
            return [round(x, 6) for x in struct.unpack_from('<%df' % n, d, off)]
        if t in (7, 8, 15, 20):
            e = d.find(b'\0', off); return d[off:e].decode('latin1')
        if t in (13, 18):
            n = struct.unpack_from('<I', d, off - 4)[0]; return list(struct.unpack_from('<%di' % n, d, off))
        if t == 14:
            n = struct.unpack_from('<I', d, off - 4)[0]; return [round(x, 6) for x in struct.unpack_from('<%df' % n, d, off)]
        return '<%s>' % TYPES.get(t, t)

    def plist(o):
        h, lo, nl, oo, no = struct.unpack_from('<IHHHH', d, o)
        out = {'_name': nm(h), 'lists': [], 'objs': []}
        lbase = o + lo * 4
        for i in range(nl): out['lists'].append(plist(lbase + i * 12))
        obase = o + oo * 4
        for i in range(no):
            oh, po, pn = struct.unpack_from('<IHH', d, obase + i * 8)
            ob = {'_name': nm(oh), 'params': {}}
            pbase = obase + i * 8 + po * 4
            for j in range(pn):
                w = struct.unpack_from('<II', d, pbase + j * 8)
                ph, w1 = w; t = w1 >> 24; doff = pbase + j * 8 + (w1 & 0xffffff) * 4
                ob['params'][nm(ph)] = val(doff, t)
            out['objs'].append(ob)
        return out
    return plist(root)
