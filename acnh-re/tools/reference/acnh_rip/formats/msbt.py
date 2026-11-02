"""MSBT (MsgStdBn) reader.

Text is UTF-16 (per header encoding byte). Control tags are kept losslessly as
  [tag group=G type=T data=HEX]   for 0x0E tags
  [/tag group=G type=T]           for 0x0F closing tags
so the Godot message renderer can interpret them (colour, pause, variable...).
"""
import struct


def _sections(data, off, count, e):
    for _ in range(count):
        magic = data[off:off + 4]
        size = struct.unpack_from(e + "I", data, off + 4)[0]
        yield magic, data[off + 0x10:off + 0x10 + size]
        off = (off + 0x10 + size + 15) & ~15


def _labels(sec, e):
    n = struct.unpack_from(e + "I", sec, 0)[0]
    out = {}
    for i in range(n):
        cnt, off = struct.unpack_from(e + "II", sec, 4 + i * 8)
        for _ in range(cnt):
            ln = sec[off]
            name = sec[off + 1:off + 1 + ln].decode("utf-8")
            idx = struct.unpack_from(e + "I", sec, off + 1 + ln)[0]
            out[idx] = name
            off += 1 + ln + 4
    return out


def _decode_text(b, e, enc):
    if enc != 1:
        raise ValueError("only UTF-16 MSBT supported")
    ue = "<" if e == "<" else ">"
    out, i, n = [], 0, len(b)
    while i + 1 < n:
        c = struct.unpack_from(ue + "H", b, i)[0]
        i += 2
        if c == 0:
            break
        if c == 0x0E:
            g, t, sz = struct.unpack_from(ue + "HHH", b, i)
            i += 6
            out.append(f"[tag group={g} type={t} data={b[i:i + sz].hex()}]")
            i += sz
        elif c == 0x0F:
            g, t = struct.unpack_from(ue + "HH", b, i)
            i += 4
            out.append(f"[/tag group={g} type={t}]")
        else:
            out.append(chr(c))
    s = "".join(out)
    # Re-join surrogate pairs.
    return s.encode("utf-16", "surrogatepass").decode("utf-16")


def read_msbt(data: bytes):
    if data[:8] != b"MsgStdBn":
        raise ValueError("not MSBT")
    e = "<" if data[8:10] == b"\xff\xfe" else ">"
    enc = data[0xC]
    nsec = struct.unpack_from(e + "H", data, 0xE)[0]
    labels, texts, attrs = {}, [], None
    for magic, sec in _sections(data, 0x20, nsec, e):
        if magic == b"LBL1":
            labels = _labels(sec, e)
        elif magic == b"TXT2":
            n = struct.unpack_from(e + "I", sec, 0)[0]
            offs = list(struct.unpack_from(e + f"{n}I", sec, 4)) + [len(sec)]
            texts = [_decode_text(sec[offs[i]:offs[i + 1]], e, enc) for i in range(n)]
        elif magic == b"ATR1":
            n, sz = struct.unpack_from(e + "II", sec, 0)
            attrs = [sec[8 + i * sz:8 + (i + 1) * sz].hex() for i in range(n)] if sz else None
    out = {}
    for idx, text in enumerate(texts):
        key = labels.get(idx, f"#{idx}")
        out[key] = text if not attrs or not attrs[idx].strip("0") else {"text": text, "attr": attrs[idx]}
    return out
