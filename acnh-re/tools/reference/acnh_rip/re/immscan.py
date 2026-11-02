"""Scan AArch64 code in main.elf for 32-bit constants built with MOVZ(+MOVK).

The game compares CRC32/Murmur hashes of names (BCSV columns, BYML keys,
EventFlow actions, ...) as immediates, so finding where a hash is materialised
tells which function uses which name. Output: {constant: [code addresses]}.
"""
import struct
from array import array
from collections import defaultdict

from ..config import EXEFS


def load_text():
    """Return (vaddr, bytes) of the executable LOAD segment of main.elf."""
    data = (EXEFS / "main.elf").read_bytes()
    phoff, phentsize, phnum = struct.unpack_from("<Q", data, 0x20)[0], *struct.unpack_from("<HH", data, 0x36)
    for i in range(phnum):
        p_type, p_flags, p_off, p_vaddr, _, p_filesz = struct.unpack_from("<IIQQQQ", data, phoff + i * phentsize)
        if p_type == 1 and p_flags & 1:
            return p_vaddr, data[p_off:p_off + p_filesz]
    raise ValueError("no executable segment")


def scan(window=6):
    base, text = load_text()
    ins = array("I")
    ins.frombytes(text[:len(text) // 4 * 4])
    consts = defaultdict(list)
    n = len(ins)
    for i in range(n):
        w = ins[i]
        if (w & 0x7F800000) != 0x52800000:      # MOVZ (32 or 64-bit)
            continue
        rd, hw, imm = w & 31, (w >> 21) & 3, (w >> 5) & 0xFFFF
        val = imm << (16 * hw)
        for j in range(i + 1, min(n, i + window)):
            k = ins[j]
            if (k & 0x7F800000) == 0x72800000 and (k & 31) == rd:   # MOVK same register
                khw = (k >> 21) & 3
                if khw < 2:
                    val = (val & ~(0xFFFF << (16 * khw))) | (((k >> 5) & 0xFFFF) << (16 * khw))
        consts[val & 0xFFFFFFFF].append(base + i * 4)
    return consts


def murmur3(key: bytes, seed=0):
    h, c1, c2, n = seed, 0xcc9e2d51, 0x1b873593, len(key)
    for i in range(0, n - n % 4, 4):
        k = int.from_bytes(key[i:i + 4], "little")
        k = (k * c1) & 0xFFFFFFFF; k = ((k << 15) | (k >> 17)) & 0xFFFFFFFF; k = (k * c2) & 0xFFFFFFFF
        h ^= k; h = ((h << 13) | (h >> 19)) & 0xFFFFFFFF; h = (h * 5 + 0xe6546b64) & 0xFFFFFFFF
    t, k = key[n - n % 4:], 0
    if len(t) >= 3: k ^= t[2] << 16
    if len(t) >= 2: k ^= t[1] << 8
    if len(t) >= 1:
        k ^= t[0]; k = (k * c1) & 0xFFFFFFFF; k = ((k << 15) | (k >> 17)) & 0xFFFFFFFF; k = (k * c2) & 0xFFFFFFFF; h ^= k
    h ^= n; h ^= h >> 16; h = (h * 0x85ebca6b) & 0xFFFFFFFF; h ^= h >> 13; h = (h * 0xc2b2ae35) & 0xFFFFFFFF; h ^= h >> 16
    return h
