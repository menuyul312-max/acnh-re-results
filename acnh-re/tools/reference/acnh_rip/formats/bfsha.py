"""BFSHA (FSHA v0.8, Switch) reader, first pass. See WORKLOG_F4.md.

Verified layout (Park_UBER_All): 64-bit pointers, string = u16 length + bytes, shading model
stride 0x100 at header+0x48, static/dynamic option entries are 0x28 bytes:
  +0x00 name ptr, +0x08 choice dict ptr, +0x18 u32 (choice value offset?), +0x1c u16 choice count,
  +0x1e u8 key word index, +0x1f u8 bit shift, +0x20 u32 mask.
Key table, program array and BNSH variation layout are NOT parsed yet.
"""
import struct
from dataclasses import dataclass, field
from . import compression, sarc

OPTION_STRIDE = 0x28
MODEL_STRIDE = 0x100


@dataclass
class Option:
    name: str
    dict_ptr: int
    choice_count: int
    key_word: int
    shift: int
    mask: int
    raw18: int


@dataclass
class ShadingModel:
    name: str
    static_options: list = field(default_factory=list)
    dynamic_options: list = field(default_factory=list)
    program_count: int = 0
    offsets: dict = field(default_factory=dict)


class Bfsha:
    def __init__(self, data: bytes):
        if data[:8] != b"FSHA    ":
            raise ValueError("not a BFSHA")
        self.d = data
        self.name = self._str(self._q(0x38))
        self.models = self._models()

    @classmethod
    def from_szs(cls, path: str) -> "Bfsha":
        files = sarc.read_sarc(compression.read_file(path))
        name = next(k for k in files if k.endswith(".bfsha"))
        return cls(files[name])

    def _q(self, o): return struct.unpack_from("<Q", self.d, o)[0]
    def _u32(self, o): return struct.unpack_from("<I", self.d, o)[0]
    def _u16(self, o): return struct.unpack_from("<H", self.d, o)[0]

    def _str(self, o):
        n = self._u16(o)
        return self.d[o + 2:o + 2 + n].decode("ascii", "replace")

    def _options(self, array_ptr, count):
        out = []
        for i in range(count):
            b = array_ptr + i * OPTION_STRIDE
            out.append(Option(self._str(self._q(b)), self._q(b + 8), self._u16(b + 0x1c),
                              self.d[b + 0x1e], self.d[b + 0x1f], self._u32(b + 0x20), self._u32(b + 0x18)))
        return out

    def choices(self, opt):
        """Choice names of an option, in choice-index order (dict: u32 sig, u32 count, 16-byte entries, root first)."""
        p = opt.dict_ptr
        n = self._u32(p + 4)
        return [self._str(self._q(p + 8 + 16 * (i + 1) + 8)) for i in range(n)]

    def _models(self):
        base = self._q(0x48)
        count = self._u16(0x78)
        models = []
        for i in range(count):
            o = base + i * MODEL_STRIDE
            m = ShadingModel(self._str(self._q(o)))
            # counts sit after the pointer block: program count @+0xd8, option counts @+0xe4/+0xe6
            m.program_count = self._u32(o + 0xd8)
            n_static, n_dyn = self._u16(o + 0xe4), self._u16(o + 0xe6)
            m.static_options = self._options(self._q(o + 0x8), n_static)
            m.dynamic_options = self._options(self._q(o + 0x18), n_dyn)
            m.offsets = {k: self._q(o + off) for k, off in
                         (("attribs", 0x28), ("samplers", 0x38), ("uniform_blocks", 0x58),
                          ("uniforms", 0x68), ("keys?", 0x88), ("programs?", 0x90), ("bnsh?", 0xa8))}
            models.append(m)
        return models
