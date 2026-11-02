"""BYML (versions 2-4, either endianness) reader.

Node types:
  0xA0 string  0xA1 binary  0xC0 array  0xC1 dict  0xC2 string table
  0xD0 bool    0xD1 s32     0xD2 f32    0xD3 u32   0xD4 s64  0xD5 u64  0xD6 f64
  0xFF null
Binary blobs are returned as bytes; JSON exporters encode them separately.
"""
import struct

STRING, BINARY, ARRAY, DICT, STRTAB = 0xA0, 0xA1, 0xC0, 0xC1, 0xC2
BOOL, S32, F32, U32, S64, U64, F64, NULL = 0xD0, 0xD1, 0xD2, 0xD3, 0xD4, 0xD5, 0xD6, 0xFF


class BymlError(ValueError):
    pass


def _read_strtab(data, off, e):
    if off == 0:
        return []
    if data[off] != STRTAB:
        raise BymlError(f"expected string table at {off:#x}")
    n = _count(data, off, e)
    offs = struct.unpack_from(f"{e}{n + 1}I", data, off + 4)
    out = []
    for i in range(n):
        s = data[off + offs[i]:off + offs[i + 1]]
        out.append(s.split(b"\0", 1)[0].decode("utf-8"))
    return out


def _count(data, off, e):
    # Node header: type byte first, then a 24-bit count in file endianness.
    b = data[off + 1:off + 4]
    return int.from_bytes(b, "little" if e == "<" else "big")


def read_byml(data: bytes):
    if data[:2] == b"YB":
        e = "<"
    elif data[:2] == b"BY":
        e = ">"
    else:
        raise BymlError("not a BYML")
    version = struct.unpack_from(e + "H", data, 2)[0]
    key_off, str_off, root_off = struct.unpack_from(e + "III", data, 4)
    keys = _read_strtab(data, key_off, e)
    strings = _read_strtab(data, str_off, e)

    def value(t, raw_off):
        v = struct.unpack_from(e + "I", data, raw_off)[0]
        if t == STRING:
            return strings[v]
        if t in (ARRAY, DICT):
            return node(v)
        if t == BINARY:
            size = struct.unpack_from(e + "I", data, v)[0]
            return bytes(data[v + 4:v + 4 + size])
        if t == BOOL:
            return v != 0
        if t == S32:
            return struct.unpack_from(e + "i", data, raw_off)[0]
        if t == F32:
            return struct.unpack_from(e + "f", data, raw_off)[0]
        if t == U32:
            return v
        if t == S64:
            return struct.unpack_from(e + "q", data, v)[0]
        if t == U64:
            return struct.unpack_from(e + "Q", data, v)[0]
        if t == F64:
            return struct.unpack_from(e + "d", data, v)[0]
        if t == NULL:
            return None
        raise BymlError(f"unknown node type {t:#x} at {raw_off:#x}")

    def node(off):
        t = data[off]
        n = _count(data, off, e)
        if t == DICT:
            d = {}
            for i in range(n):
                p = off + 4 + i * 8
                k = int.from_bytes(data[p:p + 3], "little" if e == "<" else "big")
                d[keys[k]] = value(data[p + 3], p + 4)
            return d
        if t == ARRAY:
            types = data[off + 4:off + 4 + n]
            vbase = off + 4 + ((n + 3) & ~3)
            return [value(types[i], vbase + i * 4) for i in range(n)]
        raise BymlError(f"root/container type {t:#x} at {off:#x}")

    root = node(root_off) if root_off else None
    return {"version": version, "root": root}


def load(path):
    from .compression import read_file
    return read_byml(read_file(path))["root"]
