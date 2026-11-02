"""BFTTF/BFOTF (Switch obfuscated TrueType/OpenType) -> plain font bytes.

Layout: u32 magic^key, u32 size^key, then the font XORed with a repeating u32
key (big-endian words). The key is recovered from the data itself: a decoded
font must start with the sfnt version 0x00010000 or 'OTTO'; the result is only
accepted when the sfnt table directory then checks out.
"""
import struct


def _xor(data: bytes, key: int) -> bytes:
    n = len(data) // 4
    words = struct.unpack(f">{n}I", data[:n * 4])
    out = struct.pack(f">{n}I", *(w ^ key for w in words))
    return out + data[n * 4:]


def _valid_sfnt(b: bytes) -> bool:
    if len(b) < 12:
        return False
    num = struct.unpack_from(">H", b, 4)[0]
    if not 0 < num < 64:
        return False
    for i in range(num):
        tag, _, off, ln = struct.unpack_from(">4sIII", b, 12 + i * 16)
        if not tag.isascii() or off + ln > len(b) + 3:
            return False
    return True


def decode(data: bytes):
    """Returns (font_bytes, extension) or raises ValueError."""
    first = struct.unpack_from(">I", data, 8)[0]
    for version, ext in ((0x00010000, ".ttf"), (0x4F54544F, ".otf")):
        key = first ^ version
        size = struct.unpack_from(">I", data, 4)[0] ^ key
        body = _xor(data[8:], key)
        if size <= len(body):
            body = body[:size]
        if _valid_sfnt(body):
            return body, ext
    raise ValueError("could not recover BFTTF key")
