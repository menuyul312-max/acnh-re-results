"""Read ELF virtual addresses and disassemble AArch64 without executing the game."""
from pathlib import Path
import io
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / '.deps'))
from capstone import Cs, CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN
from elftools.elf.elffile import ELFFile

_manifest = Path(__file__).resolve().parent.parent/'output/manifest.json'
DEFAULT = Path(json.loads(_manifest.read_text())['source_root'])/'A_logic/main.elf'


class Image:
    def __init__(self, source=DEFAULT):
        self.data = source.read_bytes()
        self.elf = ELFFile(io.BytesIO(self.data))
        self.segments = [s for s in self.elf.iter_segments() if s['p_type'] == 'PT_LOAD']
        self.relocations = {}
        for section in self.elf.iter_sections():
            if section['sh_type'] == 'SHT_RELA':
                for rel in section.iter_relocations():
                    if rel['r_info_type'] == 1027:
                        self.relocations[rel['r_offset']] = rel['r_addend']
        self.disassembler = Cs(CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN)
        self.disassembler.detail = True

    def offset(self, va):
        for s in self.segments:
            if s['p_vaddr'] <= va < s['p_vaddr'] + s['p_filesz']:
                return s['p_offset'] + va - s['p_vaddr']
        raise ValueError(f'VA not file-backed: {va:#x}')

    def read(self, va, size):
        off = self.offset(va)
        if size < 0 or off + size > len(self.data):
            raise ValueError('read outside ELF')
        return self.data[off:off + size]

    def ptr(self, va):
        return self.relocations.get(va, int.from_bytes(self.read(va, 8), 'little'))

    def cstring(self, va, limit=512):
        off = self.offset(va)
        return self.data[off:off + limit].split(b'\0')[0].decode('utf-8', 'replace')

    def disasm(self, va, size=256):
        return list(self.disassembler.disasm(self.read(va, size), va))


if __name__ == '__main__':
    image = Image()
    va = int(sys.argv[1], 16)
    size = int(sys.argv[2], 0) if len(sys.argv) > 2 else 256
    for ins in image.disasm(va, size):
        print(f'{ins.address:08x} {ins.bytes.hex():8s} {ins.mnemonic:8s} {ins.op_str}')
