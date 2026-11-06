"""Native checks of the island insect draw 0x957940 and the AppearFg filter 0x958570.

Runs the original functions from the ExeFS `main` in nso_sandbox. Inputs are the real tables of the local baseline
extraction (InsectAppearParam, InsectStatusParam; never committed).

0x957940(mgr): month/slot from the clock (0x9f1870, already verified natively), hemisphere from save root +0x651fc,
table per hemisphere from 0x957bf0; candidates are rows with Prob(month * 6 + slot) != 0 that 0x958570 does not
reject; W = sum Prob; r = rand32 * W >> 32; the first candidate with r < Prob (after subtracting the earlier
weights) is returned as an ItemID, 0xfffe when W = 0.

Controlled from Python: 0x9f1870 (writes month/slot), 0x957bf0 (table token per hemisphere), the row accessor
0x965400, the ItemID accessor 0x95a110, the 72 Prob column getters (the getter array itself is built by the
original constructor 0x95ebe0 and dispatched natively through its member-function pointers), the InsectStatusParam
row lookup 0x9e7400 and AppearFg column accessor 0x8e17f0 (real 3 AppearFg bytes), and the RNG word 0x19aa0e0.
Loop, candidate test, AppearFg bit mask, special-ID list, weight sum, draw transform and cumulative pick are native.
Used by tools/gameplay_native.py; see docs/GAMEPLAY_SCENARIO.md section 8.2.
"""
import json
import os
from pathlib import Path
import random
import struct
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from nso_sandbox import Sandbox  # noqa: E402

OUTPUT = Path(os.environ.get('ACNH_RE_OUTPUT', Path(__file__).resolve().parent.parent/'output'))
MONTHS = ['January', 'Februay', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October',
          'November', 'December']      # 'Februay' is the column spelling in InsectAppearParam
SLOTS = ['Midnight', 'Morning', 'Daytime', 'Evening1', 'Evening2', 'Night']
TOKEN = 0x10000                       # fake row pointers: TOKEN * (hemisphere + 1) + row index
STATUS_TOKEN = 0x40000                # fake InsectStatusParam row pointers: STATUS_TOKEN + ItemID
SAVE_ROOT_GOT = 0x32d1a38             # GOT slot -> pointer to the save root (hemisphere at +0x651fc)
NO_ITEM = 0xfffe
# ItemIDs that 0x958570 rejects although their AppearFg is 0 (they spawn through their own paths) [PSEUDO -> native]
SPECIAL = (0x24b, 0x250, 0x252, 0x25c, 0x268, 0x28b, 0x1425)


def _table(name):
    return json.loads((OUTPUT/'tables_resolved'/f'{name}.json').read_text())


def load_insects():
    """Rows per hemisphere in table order: item and 72 Prob values; AppearFg (3 raw bytes) per ItemID."""
    t = _table('InsectAppearParam')
    c = [x['name'] for x in t['columns']]
    cols = [c.index(f'Prob{MONTHS[k // 6]}{SLOTS[k % 6]}') for k in range(72)]
    tables = {h: [{'item': r[c.index('ItemID')], 'prob': [r[i] for i in cols]}
                  for r in t['rows'] if r[c.index('AppearArea')] == h] for h in (0, 1)}
    st = _table('InsectStatusParam')
    sc = [x['name'] for x in st['columns']]
    col = next(x for x in st['columns'] if x['name'] == 'AppearFg')
    raw = (OUTPUT/st['raw']['$blob']).read_bytes()
    n, size = struct.unpack_from('<II', raw, 0)
    head = len(raw) - n*size
    fg = {}
    for k, r in enumerate(st['rows']):
        b = raw[head + k*size + col['offset']: head + k*size + col['offset'] + 3]
        fg[r[sc.index('ItemID')]] = b
    return tables, fg


def model_filter(item, fg):
    """0x958570: true (reject) when AppearFg has any bit except bit 3, or the item is in SPECIAL."""
    b = fg.get(item, b'\0\0\0')
    return bool((b[0] & 0xf7) or b[1] or b[2] or item in SPECIAL)


def model_draw(rows, fg, month, slot, draw):
    k = month*6 + slot
    cand = [r for r in rows if r['prob'][k] and not model_filter(r['item'], fg)]
    w = sum(r['prob'][k] for r in cand)
    if not w:
        return NO_ITEM
    x = (draw * w) >> 32
    for r in cand:
        if x < r['prob'][k]:
            return r['item']
        x -= r['prob'][k]
    return NO_ITEM


class InsectRig:
    def __init__(self):
        self.tables, self.fg = load_insects()
        self.sb = sb = Sandbox()
        self.month, self.slot, self.hemi, self.draw = 0, 0, 0, 0
        self.mgr = sb.alloc(0x1000)
        sb.call(0x95ebe0, (self.mgr,))                     # original getter array at +0x170
        self.getters = [(sb.u64(self.mgr + 0x170 + 16*k), sb.u64(self.mgr + 0x178 + 16*k)) for k in range(72)]
        assert len({g for g, _ in self.getters}) == 72 and all(a == 0 for _, a in self.getters)
        self.tbl = {h: sb.alloc(0x400) for h in (0, 1)}
        for h in (0, 1):
            sb.uc.mem_write(self.tbl[h] + 0x1c0, struct.pack('<i', len(self.tables[h])))
        self.root = sb.alloc(0x652000)
        sb.uc.mem_write(sb.u64(SAVE_ROOT_GOT), struct.pack('<Q', self.root))
        self.fgmem = sb.alloc(4 * 0x2000)
        for item, b in self.fg.items():
            sb.uc.mem_write(self.fgmem + 4*item, b)

        def row(s):
            v = s.reg('x0')
            h = v // TOKEN - 1
            return self.tables[h][v % TOKEN]

        def write_slot(s):
            s.uc.mem_write(s.reg('x0'), struct.pack('<I', self.month))
            s.uc.mem_write(s.reg('x1'), struct.pack('<I', self.slot))
        sb.stub(0x9f1870, write_slot)
        sb.stub(0x957bf0, lambda s: self.tbl[s.u32(s.reg('x1'))])
        sb.stub(0x965400, lambda s: TOKEN * (1 + [h for h in (0, 1) if self.tbl[h] == s.reg('x0')][0])
                + (s.reg('x1') & 0xffffffff))
        sb.stub(0x95a110, lambda s: row(s)['item'])
        for k, (g, _) in enumerate(self.getters):
            sb.stub(g, lambda s, k=k: row(s)['prob'][k])
        sb.stub(0x9e7400, lambda s: STATUS_TOKEN + (s.reg('x1') & 0xffff) if (s.reg('x1') & 0xffff) in self.fg else 0)
        sb.stub(0x8e17f0, lambda s: self.fgmem + 4*(s.reg('x0') - STATUS_TOKEN))
        sb.stub(0x19aa0e0, lambda s: self.draw)

    def pick(self, hemi, month, slot, draw):
        self.hemi, self.month, self.slot, self.draw = hemi, month, slot, draw
        self.sb.uc.mem_write(self.root + 0x651fc, struct.pack('<I', hemi))
        return self.sb.call(0x957940, (self.mgr,), limit=20_000_000) & 0xffff

    def filtered(self, item):
        p = self.sb.alloc(4)
        self.sb.uc.mem_write(p, struct.pack('<I', item))
        return bool(self.sb.call(0x958570, (0, p), limit=2_000_000) & 1)


def draw_cases(rig, rng, per=4):
    mism, n, empty = [], 0, 0
    for h in (0, 1):
        for m in range(12):
            for s in range(6):
                for d in [0, 0xffffffff, 0x80000000] + [rng.getrandbits(32) for _ in range(per)]:
                    got, exp = rig.pick(h, m, s, d), model_draw(rig.tables[h], rig.fg, m, s, d)
                    n += 1
                    empty += exp == NO_ITEM
                    if got != exp:
                        mism.append([h, m, s, d, got, exp])
    return {'0x957940 insect weighted draw': {
        'samples': n, 'no_candidate_samples': empty, 'mismatches': mism[:10], 'pass': not mism,
        'rule': 'candidates = rows (hemisphere table, table order) with Prob(month*6+slot) != 0 and 0x958570 false; '
                'r = rand32 * sum(Prob) >> 32; first candidate with r < Prob after subtracting earlier weights; 0xfffe if none'}}


def filter_cases(rig):
    items = sorted(set(rig.fg) | set(SPECIAL))
    got = {i: rig.filtered(i) for i in items}
    mism = [[hex(i), got[i], model_filter(i, rig.fg)] for i in items if got[i] != model_filter(i, rig.fg)]
    # bit 3 alone does not reject: flip every single AppearFg bit on one plain insect
    plain = next(i for i in items if not model_filter(i, rig.fg))
    bits = {}
    for bit in range(24):
        b = bytearray(3)
        b[bit // 8] |= 1 << (bit % 8)
        rig.sb.uc.mem_write(rig.fgmem + 4*plain, bytes(b))
        bits[bit] = rig.filtered(plain)
    rig.sb.uc.mem_write(rig.fgmem + 4*plain, rig.fg[plain])
    ok_bits = all(bits[b] == (b != 3) for b in bits)
    return {'0x958570 insect AppearFg filter': {
        'items': len(items), 'rejected': sorted(hex(i) for i in items if got[i]), 'single_bit_reject': bits,
        'mismatches': mism[:10], 'pass': not mism and ok_bits}}


def cases():
    rig, rng = InsectRig(), random.Random(20200320)
    out = {}
    out.update(filter_cases(rig))
    out.update(draw_cases(rig, rng))
    out['meta_unhandled'] = rig.sb.unknown_imports
    return out


if __name__ == '__main__':
    print(json.dumps({k: (v['pass'] if isinstance(v, dict) and 'pass' in v else v) for k, v in cases().items()}, indent=1))
