"""Bounded emulation of isolated AArch64 helpers; no console OS or game launch."""
from pathlib import Path
import struct
import hashlib
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / '.deps'))
from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM, UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE
from unicorn import arm64_const as regs
from native_image import Image


class Sandbox:
    STACK = 0x40000000
    HEAP = 0x50000000
    STOP = 0x60000000

    def __init__(self, image=None):
        self.image = image or Image()
        if hashlib.sha256(self.image.data).hexdigest() != '5bf707c3dc5dac0ad9635af7d336ec580f81c3f7876d0f55400d1900e3415d74':
            raise ValueError('native helper VAs are verified only for the supplied ELF checksum')
        self.uc = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
        for seg in self.image.segments:
            start = seg['p_vaddr'] & ~4095
            end = (seg['p_vaddr'] + seg['p_memsz'] + 4095) & ~4095
            self.uc.mem_map(start, end - start)
            off, size = seg['p_offset'], seg['p_filesz']
            self.uc.mem_write(seg['p_vaddr'], self.image.data[off:off + size])
        for off, value in self.image.relocations.items():
            self.uc.mem_write(off, struct.pack('<Q', value))
        self.uc.mem_map(self.STACK, 0x200000)
        self.uc.mem_map(self.HEAP, 0x200000)
        self.uc.mem_map(self.STOP, 4096)
        # Enable FP/SIMD for helpers using ARM64 scalar float instructions.
        self.uc.reg_write(regs.UC_ARM64_REG_CPACR_EL1, 3 << 20)

    def call(self, va, args=(), fargs=(), limit=1000000):
        for i in range(8):
            self.uc.reg_write(getattr(regs, f'UC_ARM64_REG_X{i}'), args[i] if i < len(args) else 0)
            value = struct.unpack('<I', struct.pack('<f', fargs[i]))[0] if i < len(fargs) else 0
            self.uc.reg_write(getattr(regs, f'UC_ARM64_REG_S{i}'), value)
        self.uc.reg_write(regs.UC_ARM64_REG_SP, self.STACK + 0x1ff000)
        self.uc.reg_write(regs.UC_ARM64_REG_X30, self.STOP)
        self.uc.emu_start(va, self.STOP, timeout=5_000_000, count=limit)
        pc = self.uc.reg_read(regs.UC_ARM64_REG_PC)
        if pc != self.STOP:
            raise ValueError(f'isolated helper did not return within bounds: pc={pc:#x}')
        return self.uc.reg_read(regs.UC_ARM64_REG_X0)

    def float_result(self):
        return struct.unpack('<f', struct.pack('<I', self.uc.reg_read(regs.UC_ARM64_REG_S0)))[0]
