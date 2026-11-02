"""BCSV ("VSCB", version 10000) table reader.

Layout (little endian):
  0x00 u32 row_count   0x04 u32 row_size   0x08 u16 field_count
  0x0A u8  has_ext_header  0x0B u8 ?   0x0C "VSCB"  0x10 u32 version
  0x1C field table: field_count x (u32 name_hash, u32 offset_in_row)
  rows follow the field table. Bytes 0..3 of every row hold the row's own file
  offset (verified: row k == data_start + k*row_size) and are not a field.

Column names are CRC32("<Name> <type>"). The type comes from the name when the
hash is known; otherwise it is inferred from the column width and its values,
and the column is flagged type_source="inferred".
"""
import math
import struct

from .. import hashdict

_INT_FMT = {"u8": "B", "s8": "b", "u16": "H", "s16": "h", "u32": "I", "s32": "i",
            "u64": "Q", "s64": "q", "f32": "f", "f64": "d", "bool": "B"}
_SIZE = {"u8": 1, "s8": 1, "bool": 1, "u16": 2, "s16": 2, "u32": 4, "s32": 4, "f32": 4,
         "u64": 8, "s64": 8, "f64": 8}


def _plausible_float(raw):
    if raw == 0:
        return True
    f = struct.unpack("<f", struct.pack("<I", raw))[0]
    return math.isfinite(f) and 1e-6 < abs(f) < 1e7


def _infer_type(width, raws):
    if width == 1:
        return "u8"
    if width == 2:
        return "s16" if any(v == 0xFFFF for v in raws) and max(raws) == 0xFFFF and len(set(raws)) > 2 else "u16"
    if width == 4:
        nonzero = [v for v in raws if v]
        if nonzero and all(_plausible_float(v) for v in nonzero) and any(v > 0x00FFFFFF for v in nonzero):
            return "f32"
        if any(v >= 0x80000000 for v in raws) and all(v >= 0xFFFF0000 or v < 0x80000000 for v in raws):
            return "s32"
        return "u32"
    if width == 8:
        return "u64"
    return "string"


def _decode_string(b: bytes):
    s = b.split(b"\0", 1)[0]
    try:
        return s.decode("utf-8")
    except UnicodeDecodeError:
        return s.hex()


def read_bcsv(data: bytes):
    rows_n, row_size, nfields = struct.unpack_from("<IIH", data, 0)
    has_ext = data[0xA]
    if has_ext and data[0xC:0x10] != b"VSCB":
        raise ValueError("unexpected BCSV header")
    hdr = 0x1C if has_ext else 0x0C
    fields = sorted((struct.unpack_from("<II", data, hdr + i * 8) for i in range(nfields)),
                    key=lambda f: f[1])
    data_start = hdr + nfields * 8
    columns = []
    for i, (h, off) in enumerate(fields):
        end = fields[i + 1][1] if i + 1 < len(fields) else row_size
        width = end - off
        name, typ = hashdict.name_typed(h)
        col = {"hash": f"{h:08x}", "name": name or f"h_{h:08x}", "offset": off, "width": width}
        if typ is not None:
            col["type"], col["type_source"] = typ, "name"
        columns.append(col)

    def row_bytes(r):
        base = data_start + r * row_size
        return data[base:base + row_size]

    rows_raw = [row_bytes(r) for r in range(rows_n)]
    for col in columns:
        if "type" in col:
            continue
        w = col["width"]
        if w in (1, 2, 4, 8):
            fmt = {1: "B", 2: "H", 4: "I", 8: "Q"}[w]
            raws = [struct.unpack_from("<" + fmt, rb, col["offset"])[0] for rb in rows_raw]
        else:
            raws = []
        col["type"], col["type_source"] = _infer_type(w, raws), "inferred"

    # u32 columns that hold CRC32 hashes of enum labels (e.g. habitat, kind).
    plain = hashdict.get()["plain"]
    for col in columns:
        if col["type"] not in ("u32", "s32") or col["width"] != 4:
            continue
        vals = {struct.unpack_from("<I", rb, col["offset"])[0] for rb in rows_raw} - {0}
        if len(vals) >= 2 and sum(v in plain for v in vals) * 2 >= len(vals):
            col["enum_hash"] = True

    rows = []
    for rb in rows_raw:
        row = {}
        for col in columns:
            t, off = col["type"], col["offset"]
            if t == "string" or t not in _INT_FMT or _SIZE[t] > col["width"]:
                row[col["name"]] = _decode_string(rb[off:off + col["width"]])
                continue
            v = struct.unpack_from("<" + _INT_FMT[t], rb, off)[0]
            if col.get("enum_hash"):
                raw = v & 0xFFFFFFFF
                v = plain.get(raw, f"h_{raw:08x}") if raw else 0
            elif t == "f32":
                v = float(f"{v:.7g}")
            elif t == "bool":
                v = bool(v)
            row[col["name"]] = v
        rows.append(row)
    return {"columns": columns, "rows": rows}


def load(path):
    from pathlib import Path
    return read_bcsv(Path(path).read_bytes())
