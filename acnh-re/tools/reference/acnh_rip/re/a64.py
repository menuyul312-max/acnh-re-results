"""Minimal AArch64 decoder for following pointers without Ghidra.

Covers the instructions that matter for walking factory functions and vtables:
ADRP, ADD/SUB imm, LDR/STR (unsigned imm, 32/64), LDP/STP, MOVZ/MOVK/MOV(reg),
ORR imm with zero source (as movz), B, BL, BR, BLR, RET, CBZ/CBNZ. Everything else is printed raw.
Also resolves the value of ADRP+ADD/LDR pairs and reads pointers through the
dynamic relocations (R_AARCH64_RELATIVE addends).
"""
import struct

from .evfl_handlers import _elf, _v2f, relocations  # noqa: F401 (_v2f re-exported)


class Image:
    def __init__(self):
        self.data, self.segs = _elf()
        self.rel = relocations(self.data, self.segs)

    def u32(self, va):
        return struct.unpack_from("<I", self.data, _v2f(self.segs, va))[0]

    def ptr(self, va):
        """64-bit pointer at va, honouring relocations (file holds 0 for relocated slots)."""
        if va in self.rel:
            return self.rel[va]
        return struct.unpack_from("<Q", self.data, _v2f(self.segs, va))[0]

    def cstr(self, va, n=96):
        o = _v2f(self.segs, va)
        b = self.data[o:o + n]
        return b.split(b"\0", 1)[0].decode("utf-8", "replace")


def _sx(v, bits):
    return v - (1 << bits) if v & (1 << (bits - 1)) else v


def _bitmask(sf, n, immr, imms):
    """DecodeBitMasks for logical immediates."""
    size = 64 if n else next(e for e in (32, 16, 8, 4, 2) if not (imms & e))
    s, r = imms & (size - 1), immr
    elem = (1 << (s + 1)) - 1
    elem = ((elem >> r) | (elem << (size - r))) & ((1 << size) - 1)
    width = 64 if sf else 32
    return sum(elem << i for i in range(0, width, size)) & ((1 << width) - 1)


def decode(w, pc):
    r = lambda n: "xzr" if n == 31 else f"x{n}"
    if (w & 0x9F000000) == 0x90000000:  # ADRP
        imm = _sx(((w >> 5) & 0x7FFFF) << 2 | ((w >> 29) & 3), 21) << 12
        return ("adrp", w & 31, (pc & ~0xFFF) + imm)
    if (w & 0x7F800000) == 0x11000000:  # ADD imm (64/32)
        sh = 12 if (w >> 22) & 1 else 0
        return ("add", w & 31, (w >> 5) & 31, ((w >> 10) & 0xFFF) << sh)
    if (w & 0x7F800000) == 0x51000000:
        sh = 12 if (w >> 22) & 1 else 0
        return ("sub", w & 31, (w >> 5) & 31, ((w >> 10) & 0xFFF) << sh)
    if (w & 0xFFC00000) == 0xF9400000:
        return ("ldr", w & 31, (w >> 5) & 31, ((w >> 10) & 0xFFF) * 8)
    if (w & 0xFFC00000) == 0xB9400000:
        return ("ldr32", w & 31, (w >> 5) & 31, ((w >> 10) & 0xFFF) * 4)
    if (w & 0xFFC00000) == 0xF9000000:
        return ("str", w & 31, (w >> 5) & 31, ((w >> 10) & 0xFFF) * 8)
    if (w & 0xFFC00000) == 0xB9000000:
        return ("str32", w & 31, (w >> 5) & 31, ((w >> 10) & 0xFFF) * 4)
    if (w & 0xFC000000) == 0x94000000:
        return ("bl", pc + (_sx(w & 0x3FFFFFF, 26) << 2))
    if (w & 0xFC000000) == 0x14000000:
        return ("b", pc + (_sx(w & 0x3FFFFFF, 26) << 2))
    if (w & 0xFFFFFC1F) == 0xD65F0000:
        return ("ret",)
    if (w & 0xFFFFFC1F) == 0xD61F0000:
        return ("br", (w >> 5) & 31)
    if (w & 0xFFFFFC1F) == 0xD63F0000:
        return ("blr", (w >> 5) & 31)
    if (w & 0x7F800000) == 0x52800000:
        return ("movz", w & 31, ((w >> 5) & 0xFFFF) << (16 * ((w >> 21) & 3)))
    if (w & 0x7F800000) == 0x72800000:
        return ("movk", w & 31, (w >> 5) & 0xFFFF, (w >> 21) & 3)
    if (w & 0x7F8003E0) == 0x320003E0:  # ORR imm with xzr/wzr source = mov
        return ("movz", w & 31, _bitmask((w >> 31) & 1, (w >> 22) & 1, (w >> 16) & 63, (w >> 10) & 63))
    if (w & 0x7FE0FFE0) == 0x2A0003E0:
        return ("mov", w & 31, (w >> 16) & 31)
    if (w & 0x7F000000) == 0x34000000:
        return ("cbz" if not (w >> 24) & 1 else "cbnz", w & 31, pc + (_sx((w >> 5) & 0x7FFFF, 19) << 2))
    return ("?", f"{w:08x}")


def walk(img, va, max_ins=64, stop_at_ret=True):
    """Linear disassembly with register value tracking for adrp/add/ldr chains."""
    regs, out = {}, []
    for i in range(max_ins):
        pc = va + i * 4
        ins = decode(img.u32(pc), pc)
        note = ""
        op = ins[0]
        if op == "adrp":
            regs[ins[1]] = ins[2]
        elif op == "add" and ins[2] in regs:
            regs[ins[1]] = regs[ins[2]] + ins[3]
            note = f"= {regs[ins[1]]:#x}"
        elif op == "ldr" and ins[2] in regs:
            addr = regs[ins[2]] + ins[3]
            try:
                regs[ins[1]] = img.ptr(addr)
                note = f"[{addr:#x}] = {regs[ins[1]]:#x}"
            except Exception:
                regs.pop(ins[1], None)
        elif op in ("ldr", "ldr32", "add", "sub", "movz", "mov"):
            regs.pop(ins[1], None)
        out.append((pc, ins, note))
        if stop_at_ret and op in ("ret", "b", "br"):
            break
    return out
