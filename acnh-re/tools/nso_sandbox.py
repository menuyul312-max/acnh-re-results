"""Bounded AArch64 emulation of isolated functions straight from the ExeFS `main` (NSO0).

No console OS and no game launch: the three NSO segments are mapped at their ELF VAs, .bss is zeroed,
R_AARCH64_RELATIVE relocations from the MOD0 dynamic table are applied, and calls to chosen VAs can be
replaced by Python stubs. Needs `pip install unicorn capstone` and the NSO in inputs/additional_exefs/main
(or ACNH_RE_NSO). Used by tools/gameplay_native.py; see docs/HANDOFF.md.
"""
from pathlib import Path
import datetime
import os
import struct
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import re_helpers  # noqa: E402

DEFAULT_NSO = Path(os.environ.get('ACNH_RE_NSO', Path(__file__).resolve().parent.parent/'inputs'/'additional_exefs'/'main'))
NSO_SHA256 = 'f8d248109ff72999b4600ae3749f8c7397fb960f7ad3ab8dee3018ae9e14e900'


def load_nso(path=DEFAULT_NSO):
    raw = Path(path).read_bytes()
    segs = re_helpers.nso_segments(path)
    bss = struct.unpack_from('<I', raw, 0x3c)[0]
    text_off, text = segs[0]
    mod0 = struct.unpack_from('<I', text, 4)[0]
    image = {off: bytearray(data) for off, data in segs}
    return segs, bss, mod0, image


_EPOCH = datetime.datetime(1970, 1, 1)


def _to_posix(sb, ptr, *_):
    y, mo, d, h, mi, se = struct.unpack('<hbbbbb', sb.read(ptr, 7))
    return int((datetime.datetime(y, mo, d, h, mi, se) - _EPOCH).total_seconds())


def _to_calendar(sb, ptr, *_):
    t = _EPOCH + datetime.timedelta(seconds=struct.unpack('<q', sb.read(ptr, 8))[0])
    return struct.unpack('<Q', struct.pack('<hbbbbbx', t.year, t.month, t.day, t.hour, t.minute, t.second))[0]


def _day_of_week(sb, y, m, d):
    y, m, d = (struct.unpack('<i', struct.pack('<I', v & 0xffffffff))[0] for v in (y, m, d))  # int args in w0..w2
    return (datetime.date(y, m, d).weekday() + 1) % 7  # nn::time: 0 = Sunday


def _is_valid_date(sb, y, m, d):
    try:
        _day_of_week(sb, y, m, d)
        return 1
    except ValueError:
        return 0


# nn::time imports used by the calendar helpers (0x1fb9a0..0x1fd960)
TIME_IMPORTS = {
    '_ZN2nn4time11IsValidDateEiii': _is_valid_date,
    '_ZN2nn4time12GetDayOfWeekEiii': _day_of_week,
    '_ZN2nn4time18ToPosixTimeFromUtcERKNS0_12CalendarTimeE': _to_posix,
    '_ZN2nn4time19ToCalendarTimeInUtcERKNS0_9PosixTimeE': _to_calendar,
}


# mutex calls are no-ops: the sandbox runs one thread
SINGLE_THREAD_NOOPS = {
    '_ZN2nn2os15InitializeMutexEPNS0_9MutexTypeEbi',
    '_ZN2nn2os13FinalizeMutexEPNS0_9MutexTypeE',
    '_ZN2nn2os9LockMutexEPNS0_9MutexTypeE',
    '_ZN2nn2os11UnlockMutexEPNS0_9MutexTypeE',
}


def _vsnprintf(sb, fmt, va):
    """Integer/string subset of printf over an AAPCS64 va_list {stack, gr_top, vr_top, gr_offs, vr_offs}."""
    import re
    stack, gr_top, _vr_top, gr_offs = struct.unpack('<QQQi', sb.read(va, 28))

    def arg():
        nonlocal stack, gr_offs
        if gr_offs < 0:
            v = sb.u64(gr_top + gr_offs)
            gr_offs += 8
        else:
            v = sb.u64(stack)
            stack += 8
        return v
    out = []
    for m in re.finditer(rb'%([-0 #+]*)(\d*)(?:\.(\d+))?(hh|h|ll|l|z)?([diuxXscp%])|[^%]+|%', fmt):
        if not m.group(5):
            out.append(m.group(0))
            continue
        flags, width, conv = m.group(1), int(m.group(2) or 0), m.group(5)
        if conv == b'%':
            out.append(b'%')
            continue
        v = arg()
        if conv == b's':
            s = sb.read(v, 256).split(b'\0')[0] if v else b'(null)'
        elif conv == b'c':
            s = bytes([v & 0xff])
        else:
            if conv in b'di':
                v &= 0xffffffffffffffff if m.group(4) in (b'l', b'll', b'z') else 0xffffffff
                bits = 64 if m.group(4) in (b'l', b'll', b'z') else 32
                v = v - (1 << bits) if v >> (bits - 1) else v
                s = str(v).encode()
            else:
                v &= 0xffffffffffffffff if m.group(4) in (b'l', b'll', b'z') or conv == b'p' else 0xffffffff
                s = (b'%x' % v) if conv in b'xp' else (b'%X' % v) if conv == b'X' else str(v).encode()
        pad = b'0' if b'0' in flags and conv not in b'sc' and b'-' not in flags else b' '
        s = s.ljust(width) if b'-' in flags else s.rjust(width, pad)
        out.append(s)
    return b''.join(out)


class Sandbox:
    STACK, HEAP, STOP, STUB = 0x70000000, 0x80000000, 0x6f000000, 0x6e000000

    def __init__(self, path=DEFAULT_NSO, heap_size=0x4000000):
        from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM, UC_HOOK_CODE
        from unicorn import arm64_const as R
        self.R = R
        segs, bss, mod0, _ = load_nso(path)
        self.uc = uc = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
        end = 0
        for off, data in segs:
            end = max(end, off + len(data))
        self.image_end = (end + bss + 0xfff) & ~0xfff
        uc.mem_map(0, self.image_end)
        for off, data in segs:
            uc.mem_write(off, bytes(data))
        self.relocations = self._relocate(segs[0][0] + mod0)
        uc.mem_map(self.STACK, 0x400000)
        uc.mem_map(self.HEAP, heap_size)
        uc.mem_map(self.STOP, 0x1000)
        uc.mem_map(self.STUB, 0x100000)
        uc.reg_write(R.UC_ARM64_REG_CPACR_EL1, 3 << 20)
        self.heap_next = self.HEAP
        self.stubs = {}
        self.trace = []
        uc.mem_write(self.STUB, b'\xc0\x03\x5f\xd6' * (0x100000 // 4))  # ret
        self.unknown_imports = {}
        uc.hook_add(UC_HOOK_CODE, self._hook, begin=0, end=self.image_end)
        uc.hook_add(UC_HOOK_CODE, self._import, begin=self.STUB, end=self.STUB + 0xfffff)

    def _relocate(self, mod0):
        uc = self.uc
        magic, dyn_off = struct.unpack('<4si', uc.mem_read(mod0, 8))
        if magic != b'MOD0':
            raise ValueError('MOD0 header not found')
        dyn = mod0 + dyn_off
        tags = {}
        for i in range(512):
            tag, val = struct.unpack('<qQ', uc.mem_read(dyn + i*16, 16))
            if tag == 0:
                break
            tags[tag] = val
        symtab, strtab = tags.get(6, 0), tags.get(5, 0)

        def symname(idx):
            name_off = struct.unpack('<I', uc.mem_read(symtab + idx*24, 4))[0]
            return bytes(uc.mem_read(strtab + name_off, 128)).split(b'\0')[0].decode()
        self.imports = {}
        count = 0
        for rela, size in ((tags.get(7, 0), tags.get(8, 0)), (tags.get(23, 0), tags.get(2, 0))):
            for i in range(size // 24):
                off, info, addend = struct.unpack('<QQq', uc.mem_read(rela + i*24, 24))
                kind, sym = info & 0xffffffff, info >> 32
                if kind == 0x403:
                    uc.mem_write(off, struct.pack('<Q', addend & 0xffffffffffffffff))
                    count += 1
                elif kind in (0x401, 0x402) and sym:
                    name = symname(sym)
                    addr = self.STUB + 4*len(self.imports)
                    self.imports[addr] = name
                    uc.mem_write(off, struct.pack('<Q', addr))
        return count

    def alloc(self, size, align=0x10):
        p = (self.heap_next + align - 1) & ~(align - 1)
        self.heap_next = p + size
        return p

    def stub(self, va, fn=None):
        """Replace the function at va: fn(sandbox) runs instead and its return value goes to x0 (default 0)."""
        self.stubs[va] = fn

    def reg(self, name, value=None):
        r = getattr(self.R, f'UC_ARM64_REG_{name.upper()}')
        if value is None:
            return self.uc.reg_read(r)
        self.uc.reg_write(r, value)

    def _hook(self, uc, address, size, _):
        if address in self.stubs:
            fn = self.stubs[address]
            result = fn(self) if fn else 0
            if result is not None:
                self.reg('x0', result & 0xffffffffffffffff)
            self.reg('pc', self.reg('x30'))

    def _import(self, uc, address, size, _):
        name = self.imports.get(address, '?')
        x0, x1, x2 = self.reg('x0'), self.reg('x1'), self.reg('x2')
        base = name.lstrip('_')
        if base == 'memset':
            uc.mem_write(x0, bytes([x1 & 0xff]) * x2)
        elif base in ('memcpy', 'memmove'):
            uc.mem_write(x0, bytes(uc.mem_read(x1, x2)))
        elif base == 'strlen':
            self.reg('x0', self.read(x0, 4096).index(b'\0'))
        elif base == 'memcmp':
            a, b = self.read(x0, x2), self.read(x1, x2)
            diff = next((i for i in range(x2) if a[i] != b[i]), None)
            self.reg('x0', 0 if diff is None else (a[diff] - b[diff]) & 0xffffffffffffffff)
        elif base in ('strcmp', 'strncmp'):
            n = x2 if base == 'strncmp' else 4096
            a, b = self.read(x0, n).split(b'\0')[0], self.read(x1, n).split(b'\0')[0]
            self.reg('x0', (a > b) - (a < b))
        elif base == 'cxa_guard_acquire':      # one-time init of function-local statics: 1 = caller constructs
            self.reg('x0', 0 if self.read(x0, 1)[0] else 1)
        elif base == 'cxa_guard_release':
            uc.mem_write(x0, b'\x01')
        elif base == 'cxa_guard_abort' or name in SINGLE_THREAD_NOOPS:
            pass
        elif name == '_ZN2nn2os11GetTlsValueENS0_7TlsSlotE':
            if not hasattr(self, 'tls'):
                self.tls = self.alloc(0x100)
            self.reg('x0', self.tls)
        elif name == '_ZN2nn4util9VSNPrintfEPcmPKcSt9__va_list':
            text = _vsnprintf(self, self.read(x2, 512).split(b'\0')[0], self.reg('x3'))
            if x1:
                out = text[:x1 - 1] + b'\0'
                uc.mem_write(x0, out)
            self.reg('x0', len(text))
        elif name in TIME_IMPORTS:
            self.reg('x0', TIME_IMPORTS[name](self, x0, x1, x2) & 0xffffffffffffffff)
        else:
            self.unknown_imports[name] = self.unknown_imports.get(name, 0) + 1
            self.reg('x0', 0)

    def read(self, addr, n):
        return bytes(self.uc.mem_read(addr, n))

    def u32(self, addr):
        return struct.unpack('<I', self.read(addr, 4))[0]

    def u64(self, addr):
        return struct.unpack('<Q', self.read(addr, 8))[0]

    def call(self, va, args=(), limit=20_000_000):
        for i in range(8):
            self.reg(f'x{i}', args[i] if i < len(args) else 0)
        self.reg('sp', self.STACK + 0x3ff000)
        self.reg('x30', self.STOP)
        self.uc.emu_start(va, self.STOP, count=limit)
        if self.reg('pc') != self.STOP:
            raise ValueError(f'function {va:#x} did not return within bounds: pc={self.reg("pc"):#x}')
        return self.reg('x0')
