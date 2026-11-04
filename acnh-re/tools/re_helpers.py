#!/usr/bin/env python3
"""Small RE lookups used while tracing gameplay logic. Read-only; prints to stdout.

Needs the baseline ZIPs extracted (see docs/WORKFLOW.md): output/index.sqlite,
output/binary/analysis_decomp/, output/binary/event_handlers_resolved.json,
output/tables_resolved/, output/additional_romfs/messages/USen/.

Addresses are ELF VAs. Ghidra pseudocode names are ELF+0x100000 (FUN_01077050 = 0xf77050);
`decomp` rewrites them back to ELF VAs and replaces string operands with their text.

  python tools/re_helpers.py decomp 0xf77050             # pseudocode, strings resolved, callers listed
  python tools/re_helpers.py calls 0xf53a70 --depth 1    # callee tree with referenced strings
  python tools/re_helpers.py strings 0xfd9d10            # strings a function references
  python tools/re_helpers.py refs MuseumBuilt            # functions referencing a string (SQL LIKE allowed: %Visit%)
  python tools/re_helpers.py callers 0xfd9d10
  python tools/re_helpers.py handler DecideSettlerNpc    # EventFlow action/query -> factory, vtable, slots
  python tools/re_helpers.py table CalendarEventParam --rows 20
  python tools/re_helpers.py item 4318 2500              # USen item names (local extraction)
  python tools/re_helpers.py msg 'housing kit' --limit 5 # USen message search (local extraction)
  python tools/re_helpers.py rodata 0x29cadb9 --u32 0x29fa1dc:3   # C string / u32 values from the main NSO
  python tools/re_helpers.py disasm 0xf8de30             # AArch64 disassembly from the main NSO (needs capstone)

`rodata` and `disasm` read the original ExeFS `main` (NSO0, LZ4 segments), default
inputs/additional_exefs/main (see docs/ADDITIONAL_EXEFS.md); override with --nso. They are needed
because index.sqlite string_refs misses short strings (e.g. NPC labels such as 'gul') and some
functions have no pseudocode.

Message and item text comes from your own extraction and is printed only; do not commit it.
"""
import argparse
import collections
import json
import re
import sqlite3
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GHIDRA_BASE = 0x100000


def va(text):
    return int(text, 16) if str(text).lower().startswith('0x') else int(text, 16)


class Index:
    def __init__(self, out):
        self.out = out
        self.db = sqlite3.connect(out/'index.sqlite')
        self._strings = None
        self._fanin = None

    @property
    def strings(self):
        if self._strings is None:
            self._strings = {s: t for s, t in self.db.execute('SELECT DISTINCT string_va, text FROM string_refs')}
        return self._strings

    @property
    def fanin(self):
        if self._fanin is None:
            self._fanin = dict(self.db.execute('SELECT target_va, COUNT(DISTINCT owner_va) FROM direct_calls GROUP BY target_va'))
        return self._fanin

    def callees(self, f):
        return list(dict.fromkeys(t for (t,) in self.db.execute(
            'SELECT target_va FROM direct_calls WHERE owner_va=? ORDER BY pc', (f,))))

    def callers(self, f):
        return sorted({o for (o,) in self.db.execute('SELECT owner_va FROM direct_calls WHERE target_va=?', (f,)) if o is not None})

    def strings_of(self, f):
        return sorted({t for (t,) in self.db.execute('SELECT text FROM string_refs WHERE function_va=?', (f,))})

    def refs(self, text):
        op = 'LIKE' if '%' in text else '='
        return sorted(self.db.execute(f'SELECT DISTINCT function_va, string_va, text FROM string_refs WHERE text {op} ?', (text,)))


def cmd_decomp(ix, args):
    for a in args.va:
        f = va(a)
        path = ix.out/'binary/analysis_decomp'/f'{f:x}.c'
        print(f'######## {f:#x} callers={[hex(c) for c in ix.callers(f)]} strings={len(ix.strings_of(f))}')
        if not path.exists():
            print('  (no pseudocode file; see binary/disassembly_fallback)')
            continue
        src = path.read_text(errors='replace')

        def string_operand(m):
            text = ix.strings.get(int(m.group(1), 16) - GHIDRA_BASE)
            return f'"{text[:70]}"' if text is not None else m.group(0)
        src = re.sub(r'(?:UNK|DAT|PTR_DAT|s)_0*([0-9a-f]{7,8})\b', string_operand, src)
        src = re.sub(r'FUN_0*([0-9a-f]{6,8})\b', lambda m: f'F_{int(m.group(1), 16) - GHIDRA_BASE:x}', src)
        if args.compact:
            keep = re.compile(r'"|F_[0-9a-f]+\(|\bif\b|\belse\b|\bwhile\b|\bfor\b|switch|case |return|\*param_\d+ = |^\S')
            src = '\n'.join(l for l in src.splitlines() if keep.search(l))
        print(src)


def cmd_calls(ix, args):
    seen = set()

    def walk(f, depth, ind):
        if f in seen:
            print(f'{ind}{f:#x} (seen)')
            return
        seen.add(f)
        names = ix.strings_of(f)
        print(f'{ind}{f:#x} callers={ix.fanin.get(f, 0)} strings={len(names)} ' + ' | '.join(n[:40] for n in names[:args.show]))
        if depth:
            for c in ix.callees(f):
                if ix.fanin.get(c, 0) <= args.max_fanin:
                    walk(c, depth - 1, ind + '  ')
    walk(va(args.va), args.depth, '')


def cmd_strings(ix, args):
    for a in args.va:
        print(hex(va(a)), ix.strings_of(va(a)))


def cmd_refs(ix, args):
    by = collections.defaultdict(set)
    for f, s, t in ix.refs(args.text):
        by[t].add(f)
    for t, fs in sorted(by.items()):
        print(f'{t[:60]!r}: {[hex(f) for f in sorted(x for x in fs if x)]}')


def cmd_callers(ix, args):
    for a in args.va:
        print(hex(va(a)), [hex(c) for c in ix.callers(va(a))])


def cmd_handler(ix, args):
    entries = json.loads((ix.out/'binary/event_handlers_resolved.json').read_text())['entries']
    shown = set()
    for e in entries.values():
        if args.name.lower() in e['name'].lower() and e['name'] not in shown:
            shown.add(e['name'])
            keep = {k: e.get(k) for k in ('kind', 'name', 'parameters', 'event_uses', 'factory', 'constructor', 'vtable', 'slots')}
            print(json.dumps(keep, ensure_ascii=False))


def cmd_table(ix, args):
    t = json.loads((ix.out/'tables_resolved'/f'{args.name}.json').read_text())
    cols = [c['name'] or 'h_' + c['hash'] for c in t['columns']]
    print(f'{args.name}: {len(t["rows"])} rows')
    print(cols)
    for row in t['rows'][:args.rows]:
        print([v['labels'][0] if isinstance(v, dict) and 'labels' in v else v for v in row])


def _messages(out, archive=None):
    for f in sorted((out/'additional_romfs/messages/USen').glob('*.json')):
        if archive and f.stem != archive:
            continue
        for member, m in json.loads(f.read_text())['members'].items():
            for msg in m.get('messages', []):
                text = re.sub(r'\s+', ' ', re.sub(r'\[/?tag[^\]]*\]', '', msg.get('text') or '')).strip()
                yield f.stem, member, (msg.get('labels') or [''])[0], text


def cmd_item(ix, args):
    want = {int(x) for x in args.ids}
    for _, member, label, text in _messages(ix.out, 'String'):
        m = re.match(r'.*_(\d{5})$', label)
        if 'ItemName' in member and m and int(m.group(1)) in want:
            print(int(m.group(1)), member.split('/')[-1], text)


def cmd_msg(ix, args):
    pat = re.compile(args.regex, re.I)
    n = 0
    for arch, member, label, text in _messages(ix.out):
        if pat.search(text):
            print(f'{arch}/{member[:-5] if member.endswith(".msbt") else member}:{label} :: {text[:200]}')
            n += 1
            if n >= args.limit:
                break


def _lz4_block(src, size):
    dst = bytearray()
    i = 0
    while i < len(src):
        token = src[i]
        i += 1
        lit = token >> 4
        if lit == 15:
            while True:
                b = src[i]; i += 1; lit += b
                if b != 255:
                    break
        dst += src[i:i + lit]
        i += lit
        if i >= len(src):
            break
        off = src[i] | (src[i + 1] << 8)
        i += 2
        ml = token & 15
        if ml == 15:
            while True:
                b = src[i]; i += 1; ml += b
                if b != 255:
                    break
        start = len(dst) - off
        for k in range(ml + 4):
            dst.append(dst[start + k])
    if len(dst) != size:
        raise ValueError('LZ4 size mismatch')
    return bytes(dst)


def nso_segments(path):
    """[(memory_offset, bytes)] for text, rodata, data of an NSO0 image (main uses ELF VA = memory offset)."""
    d = Path(path).read_bytes()
    if d[:4] != b'NSO0':
        raise ValueError(f'{path} is not NSO0')
    flags = struct.unpack_from('<I', d, 0xc)[0]
    segs = []
    for n, (hdr, csz) in enumerate(((0x10, 0x60), (0x20, 0x64), (0x30, 0x68))):
        foff, moff, size = struct.unpack_from('<III', d, hdr)
        raw = d[foff:foff + struct.unpack_from('<I', d, csz)[0]]
        segs.append((moff, _lz4_block(raw, size) if flags & (1 << n) else raw))
    return segs


def _read(segs, addr, n):
    for moff, data in segs:
        if moff <= addr < moff + len(data):
            return data[addr - moff:addr - moff + n]
    raise ValueError(f'{addr:#x} outside NSO segments')


def cmd_rodata(ix, args):
    segs = nso_segments(args.nso)
    for a in args.va:
        addr = va(a)
        blob = _read(segs, addr, 256)
        print(hex(addr), repr(blob.split(b'\0', 1)[0].decode('utf-8', 'replace')))
    for spec in args.u32 or []:
        a, n = spec.split(':')
        print(a, [hex(x) for x in struct.unpack(f'<{int(n)}I', _read(segs, va(a), 4 * int(n)))])


def cmd_disasm(ix, args):
    import capstone
    segs = nso_segments(args.nso)
    md = capstone.Cs(capstone.CS_ARCH_ARM64, capstone.CS_MODE_ARM)
    addr = va(args.va)
    for n, ins in enumerate(md.disasm(_read(segs, addr, 4 * args.count), addr)):
        print(f'{ins.address:#x}: {ins.mnemonic} {ins.op_str}')
        if ins.mnemonic == 'ret' and not args.past_ret:
            break


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--output-root', default=str(ROOT/'output'))
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('decomp'); p.add_argument('va', nargs='+'); p.add_argument('--compact', action='store_true')
    p = sub.add_parser('calls'); p.add_argument('va'); p.add_argument('--depth', type=int, default=1)
    p.add_argument('--max-fanin', type=int, default=25); p.add_argument('--show', type=int, default=8)
    p = sub.add_parser('strings'); p.add_argument('va', nargs='+')
    p = sub.add_parser('refs'); p.add_argument('text')
    p = sub.add_parser('callers'); p.add_argument('va', nargs='+')
    p = sub.add_parser('handler'); p.add_argument('name')
    p = sub.add_parser('table'); p.add_argument('name'); p.add_argument('--rows', type=int, default=30)
    p = sub.add_parser('item'); p.add_argument('ids', nargs='+')
    p = sub.add_parser('msg'); p.add_argument('regex'); p.add_argument('--limit', type=int, default=20)
    nso = str(ROOT/'inputs/additional_exefs/main')
    p = sub.add_parser('rodata'); p.add_argument('va', nargs='*'); p.add_argument('--u32', action='append')
    p.add_argument('--nso', default=nso)
    p = sub.add_parser('disasm'); p.add_argument('va'); p.add_argument('--count', type=int, default=200)
    p.add_argument('--past-ret', action='store_true'); p.add_argument('--nso', default=nso)
    args = ap.parse_args()
    ix = Index(Path(args.output_root))
    globals()['cmd_' + args.cmd](ix, args)


if __name__ == '__main__':
    main()
