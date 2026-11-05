"""Native checks of fish selection: position pick 0x5b9ba0, percent pick 0x5b98b0, gate 0x5b9270 and the
hour -> time-slot helpers 0x5e3570 / 0x5e36b0 (fish) and 0x9f1870 / 0x9f1920 (insects).

Runs the original functions from the ExeFS `main` in nso_sandbox. Inputs are the real tables of the local baseline
extraction (FishAppearRiverParam, FishAppearSeaParam, FishStatusParam, ItemParam; never committed). Controlled from
Python: the table row/column accessors (0x5cb050 row, 0x5c97c0 item, 0x5b3860/0x5b5ee0 Prob column, 0x5b2ce0
IsCreateBait, 0xa9f670 ItemKind, 0x1665ea0 status row index), the catch-count gate 0x5b8e30, the clock, the weather
code at the hour (0x204480), the session mode (0xbc82d0) and the RNG word 0x19aa0e0. Loop, mask test, weight sum,
float/integer draw transform, cumulative pick, gate order and fallback value are native. Used by
tools/gameplay_native.py; see docs/GAMEPLAY_SCENARIO.md section 8.
"""
import json
import os
from pathlib import Path
import random
import struct
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from nso_sandbox import Sandbox  # noqa: E402

OUTPUT = Path(os.environ.get('ACNH_RE_OUTPUT', Path(__file__).resolve().parent.parent/'output'))
F = np.float32
MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
FISH_SLOTS = ['MorningAndEvening', 'Daytime', 'Night']
APPEAR_TYPE = ['River', 'RiverCliffTop', 'Pond', 'BrackishWater', 'Sea', 'Anywhere', 'SeaBeachBridge']
KIND_FISH, KIND_ORE = 0x41, 0x37
SIRAKANSU, TRASH = 0x8ec, (0xd8a, 0xd8d, 0xd8e)
TOKEN = 0x1000                      # fake row pointers handed to the native loop: TOKEN + row index
APPEAR_ARRAY = 0x32e5468            # pointer to {u32 count; u16 *AppearType} read by 0x5b9ba0


# ---- tables and documented rules (GAMEPLAY_SCENARIO 9) ----
def _table(name):
    return json.loads((OUTPUT/'tables_resolved'/f'{name}.json').read_text())


def item_kind_names():
    import sqlite3
    db = sqlite3.connect(OUTPUT/'index.sqlite')
    return db.execute("SELECT text FROM string_refs WHERE text LIKE 'Ftr,RoomWall,%' LIMIT 1").fetchone()[0].split(',')


def load_fish():
    kinds = item_kind_names()
    ip = _table('ItemParam')
    c = [x['name'] for x in ip['columns']]
    kind = {r[c.index('UniqueID')]: kinds.index(r[c.index('ItemKind')]['labels'][0]) for r in ip['rows']
            if isinstance(r[c.index('ItemKind')], dict) and r[c.index('ItemKind')]['labels']}
    fs = _table('FishStatusParam')
    c = [x['name'] for x in fs['columns']]
    status = {r[c.index('ItemID')]: {'type': APPEAR_TYPE.index(r[c.index('AppearType')]['labels'][0]),
                                     'bait': r[c.index('IsCreateBait')], 'open': r[c.index('OpenDonatedNum')],
                                     'shadow': r[c.index('ShadowType')]['labels'][0], 'label': r[c.index('Label')]}
              for r in fs['rows']}
    tables = {}
    for water in ('River', 'Sea'):
        t = _table(f'FishAppear{water}Param')
        c = [x['name'] for x in t['columns']]
        for h in (0, 1):
            rows = [r for r in t['rows'] if r[c.index('AppearArea')] == h]
            tables[(water, h)] = [{'item': r[c.index('ItemID')],
                                   'prob': [[r[c.index(f'Prob{m}{s}')] for s in FISH_SLOTS] for m in MONTHS]} for r in rows]
    return tables, status, kind


def fish_slot(hour):
    return 0 if 4 <= hour <= 8 or 16 <= hour <= 20 else 1 if 9 <= hour <= 15 else 2


def insect_slot(hour):
    return 1 if 4 <= hour <= 7 else 2 if 8 <= hour <= 15 else 3 if hour == 16 else 4 if hour in (17, 18) \
        else 5 if 19 <= hour <= 22 else 0


def slot_mask(h0, h1):
    return 0 if h1 < h0 else sum({1 << fish_slot(h) for h in range(h0, h1 + 1)})


def gate(item, kind, weather, mode):
    if item == SIRAKANSU and weather not in (4, 5):
        return False
    return not (mode >= 2 and (item in TRASH or kind.get(item) == KIND_ORE))


def model_position_pick(rows, status, kind, month, slot, mask, draw, weather=1, mode=0, catches=1000):
    """Position pick 0x5b9ba0; returns (item or None, weight)."""
    cand = []
    for r in rows:
        s = status.get(r['item'])
        if not s or not s['bait'] or kind.get(r['item']) != KIND_FISH or not (mask >> s['type'] & 1):
            continue
        if gate(r['item'], kind, weather, mode) and s['open'] <= catches:
            cand.append(r)
    w = F(0)
    for r in cand:
        w = F(w + F(r['prob'][month][slot]))
    if w == 0:
        return None, float(w)
    u = F(np.uint32(0x3f800000 | (draw >> 9)).view(np.float32)) - F(1)
    t = F(F(w * u) + F(0))
    acc = F(0)
    for r in cand:
        acc = F(acc + F(r['prob'][month][slot]))
        if t < acc:
            return r['item'], float(w)
    return None, float(w)


def model_percent_pick(rows, status, kind, month, slot, draw, weather=1, mode=0, catches=1000):
    """Type pick 0x5b98b0; returns item or None (0xfffe)."""
    t, acc = (draw * 100) >> 32, 0
    for r in rows:
        acc = (acc + r['prob'][month][slot]) & 0xffffffff
        if t < (acc & 0xffff):
            s = status.get(r['item'], {'open': 0})
            ok = gate(r['item'], kind, weather, mode) and s['open'] <= catches
            return r['item'] if ok else None
    return None


# ---- native rig ----
def packed(y, mo, d, h, mi=0, s=0):
    return struct.pack('<hbbbbbx', y, mo, d, h, mi, s)


class FishRig:
    def __init__(self):
        self.tables, self.status, self.kind = load_fish()
        self.sb = sb = Sandbox()
        self.rows, self.month, self.slot = [], 0, 0
        self.weather, self.mode, self.catches, self.draw = 1, 0, 1000, 0
        self.now, self.last_item, self.gate_calls = packed(2020, 4, 1, 12), 0, []
        self.mgr, self.table = sb.alloc(0x400), sb.alloc(0x400)
        self.out, self.pm, self.ps, self.pmask = sb.alloc(8), sb.alloc(8), sb.alloc(8), sb.alloc(8)
        n = 0x4000
        ptrs, types = sb.alloc(8*n), sb.alloc(2*n)
        sb.uc.mem_write(ptrs, struct.pack(f'<{n}Q', *range(1, n + 1)))       # status row token = item + 1
        sb.uc.mem_write(types, struct.pack(f'<{n}H', *[self.status.get(i, {'type': 7})['type'] for i in range(n)]))
        sb.uc.mem_write(self.mgr + 0x320, struct.pack('<I', n))
        sb.uc.mem_write(self.mgr + 0x328, struct.pack('<Q', ptrs))
        sb.uc.mem_write(self.mgr + 0x340, struct.pack('<H', 0))
        sb.uc.mem_write(sb.u64(APPEAR_ARRAY), struct.pack('<IIQ', n, 0, types))

        def row(s):
            return self.rows[s.reg('x0') - TOKEN]

        def prob(s):
            m, sl = s.u32(s.reg('x2')), s.u32(s.reg('x3'))
            return self.rows[s.reg('x1') - TOKEN]['prob'][m][sl]

        def item(s, reg='x1'):
            self.last_item = s.reg(reg) & 0xffff
        sb.stub(0x5cb050, lambda s: TOKEN + (s.reg('x1') & 0xffffffff))
        sb.stub(0x5c97c0, lambda s: row(s)['item'])
        sb.stub(0x5b3860, prob)
        sb.stub(0x5b5ee0, prob)
        sb.stub(0x5b2ce0, lambda s: self.status.get(s.reg('x1') & 0xffff, {'bait': 0})['bait'])
        sb.stub(0xf588a0, lambda s: item(s) or None)
        sb.stub(0xa9c290, lambda s: 0)
        sb.stub(0xa9f670, lambda s: self.kind.get(self.last_item, 0))
        sb.stub(0xf58d00, lambda s: 1)
        sb.stub(0xa9cb60, lambda s: 1 if self.kind.get(self.last_item) == (s.reg('x1') & 0xff) else 0)
        sb.stub(0x1665ea0, lambda s: s.reg('x0') - 1)
        sb.stub(0x5b8e30, lambda s: self.gate_calls.append(s.reg('x1') & 0xffff)
                or (1 if self.status.get(s.reg('x1') & 0xffff, {'open': 0})['open'] <= self.catches else 0))
        sb.stub(0x1fcac0, lambda s: struct.unpack('<Q', self.now)[0])
        sb.stub(0x204480, lambda s: self.weather)
        sb.stub(0xbc82d0, lambda s: self.mode)
        sb.stub(0x19a9fe0, lambda s: 0)
        sb.stub(0x19aa0e0, lambda s: self.draw)

    def setup(self, water, hemi, month, slot, **kw):
        self.rows = self.tables[(water, hemi)]
        self.month, self.slot = month, slot
        for k, v in kw.items():
            setattr(self, k, v)
        sb = self.sb
        sb.uc.mem_write(self.table + 0x1c0, struct.pack('<i', len(self.rows)))
        sb.uc.mem_write(self.pm, struct.pack('<I', month))
        sb.uc.mem_write(self.ps, struct.pack('<I', slot))

    def position_pick(self, mask):
        sb = self.sb
        sb.uc.mem_write(self.pmask, bytes([mask]))
        ok = sb.call(0x5b9ba0, (self.mgr, self.out, self.table, self.pm, self.ps, self.pmask, 0), limit=20_000_000) & 1
        it = sb.u32(self.out)
        return (it if ok else None), it

    def percent_pick(self):
        self.gate_calls.clear()
        ok = self.sb.call(0x5b98b0, (self.mgr, self.out, self.table, self.pm, self.ps), limit=20_000_000) & 1
        it = self.sb.u32(self.out)
        return (it if ok else None), it

    def gate(self, item):
        return self.sb.call(0x5b9270, (0, item), limit=2_000_000) & 1


def _draws(rng, n):
    return [0, 0xffffffff, 0x80000000] + [rng.getrandbits(32) for _ in range(n)]


MASKS = {'river': 0b1, 'river mouth': 0b1001, 'pond': 0b100, 'cliff': 0b11, 'sea': 0b10000, 'pier': 0b1010000}


def position_cases(rig, rng, per=6):
    out, mism, n, fallback = {}, [], 0, 0
    for water, masks in (('River', ('river', 'river mouth', 'pond', 'cliff')), ('Sea', ('sea', 'pier'))):
        for hemi in (0, 1):
            for month in range(12):
                for slot in range(3):
                    for name in masks:
                        weather, mode, catches = rng.choice([1, 4]), rng.choice([0, 0, 2]), rng.choice([0, 20, 1000])
                        rig.setup(water, hemi, month, slot, weather=weather, mode=mode, catches=catches)
                        for d in _draws(rng, per):
                            rig.draw = d
                            got, _ = rig.position_pick(MASKS[name])
                            exp, _ = model_position_pick(rig.rows, rig.status, rig.kind, month, slot, MASKS[name], d,
                                                         weather, mode, catches)
                            n += 1
                            fallback += got is None
                            if got != exp:
                                mism.append([water, hemi, month, slot, name, weather, mode, catches, d, got, exp])
    out['0x5b9ba0 fish position pick'] = {
        'samples': n, 'no_candidate_runs': fallback, 'mismatches': mism[:10], 'pass': not mism,
        'rule': 'candidates IsCreateBait, ItemKind Fish, AppearType in mask, gate 0x5b9270, OpenDonatedNum <= catches; '
                'r = W * (float(0x3f800000 | u >> 9) - 1); first running sum > r'}
    return out


def percent_cases(rig, rng, per=8):
    mism, n, none = [], 0, 0
    for water in ('River', 'Sea'):
        for hemi in (0, 1):
            for month in range(12):
                for slot in range(3):
                    weather, mode, catches = rng.choice([1, 4]), rng.choice([0, 2]), rng.choice([0, 1000])
                    rig.setup(water, hemi, month, slot, weather=weather, mode=mode, catches=catches)
                    for d in _draws(rng, per):
                        rig.draw = d
                        got, raw = rig.percent_pick()
                        exp = model_percent_pick(rig.rows, rig.status, rig.kind, month, slot, d, weather, mode, catches)
                        n += 1
                        none += got is None
                        if got != exp or (got is None and raw != 0xfffe):
                            mism.append([water, hemi, month, slot, weather, mode, catches, d, got, raw, exp])
    return {'0x5b98b0 fish percent pick': {
        'samples': n, 'no_item_runs': none, 'mismatches': mism[:10], 'pass': not mism,
        'rule': 'r = u * 100 >> 32; first row with running sum of Prob > r (trash rows included); picked row must pass '
                '0x5b9270 and 0x5b8e30, else 0xfffe'}}


def gate_cases(rig):
    res, ok = [], True
    for item in (SIRAKANSU, 2264, *TRASH, 2502):
        for weather in range(8):
            for mode in (0, 1, 2, 3):
                rig.weather, rig.mode = weather, mode
                got = rig.gate(item)
                exp = int(gate(item, rig.kind, weather, mode))
                ok &= got == exp
                if weather in (1, 4, 6) and mode in (0, 2):
                    res.append([hex(item), weather, mode, got])
    return {'0x5b9270 fish gate': {'results': res, 'pass': bool(ok),
                                   'rule': 'Sirakansu needs weather code 4 or 5 at the hour; session mode >= 2 drops Can/Boot/Tire and ItemKind Ore'}}


def slot_cases(rig):
    sb = rig.sb
    buf, a, b = sb.alloc(0x20), sb.alloc(0x20), sb.alloc(0x20)
    pm, ps = sb.alloc(8), sb.alloc(8)
    out = {}

    def now(h):
        sb.stub(0x1fb9c0, lambda s: s.uc.mem_write(s.reg('x0'), packed(2020, 7, 1, h)) or None)
    fish, ins, ins2 = [], [], []
    for h in range(24):
        now(h)
        sb.call(0x5e3570, (pm, ps))
        fish.append((sb.u32(pm), sb.u32(ps)))
        sb.call(0x9f1870, (pm, ps))
        ins.append((sb.u32(pm), sb.u32(ps)))
        sb.uc.mem_write(buf, packed(2020, 7, 1, h))
        sb.call(0x9f1920, (buf, pm, ps))
        ins2.append((sb.u32(pm), sb.u32(ps)))
    out['0x5e3570 fish time slot'] = {'native': [s for _, s in fish], 'pass': fish == [(6, fish_slot(h)) for h in range(24)]}
    out['0x9f1870 / 0x9f1920 insect time slot'] = {'native': [s for _, s in ins],
                                                   'pass': ins == ins2 == [(6, insect_slot(h)) for h in range(24)]}
    mism = []
    for h0 in range(24):
        for h1 in range(24):
            sb.uc.mem_write(a, packed(2020, 7, 1, h0))
            sb.uc.mem_write(b, packed(2020, 7, 1, h1))
            sb.uc.mem_write(buf, b'\xff')
            sb.call(0x5e36b0, (buf, a, b))
            got = sb.read(buf, 1)[0]
            if got != slot_mask(h0, h1):
                mism.append([h0, h1, got, slot_mask(h0, h1)])
    out['0x5e36b0 fish slot mask over an hour range'] = {'samples': 576, 'mismatches': mism[:10], 'pass': not mism}
    return out


INSECT_MONTHS = ['January', 'Februay', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October',
                 'November', 'December']      # 'Februay' is the column spelling in InsectAppearParam
INSECT_SLOTS = ['Midnight', 'Morning', 'Daytime', 'Evening1', 'Evening2', 'Night']


def insect_getter_case(sb):
    """0x95ebe0 fills the InsectAppearParam getter array at +0x170 (16 bytes per entry); entry k reads one column."""
    from capstone import Cs, CS_ARCH_ARM64, CS_MODE_ARM
    md = Cs(CS_ARCH_ARM64, CS_MODE_ARM)
    byhash = {int(c['hash'], 16): c['name'] for c in _table('InsectAppearParam')['columns']}
    obj = sb.alloc(0x1000)
    sb.call(0x95ebe0, (obj,))
    got = []
    for k in range(72):
        fn, regs, names = sb.u64(obj + 0x170 + 16*k), {}, set()
        for i in md.disasm(bytes(sb.read(fn, 0x130)), fn):
            if i.mnemonic in ('mov', 'movz', 'movk') and ', #' in i.op_str:
                r, rest = i.op_str.split(', #', 1)
                if i.mnemonic == 'movk':
                    v, sh = rest.split(', lsl #')
                    regs[r] = (regs.get(r, 0) & 0xffff) | (int(v, 16) << int(sh))
                else:
                    try:
                        regs[r] = int(rest, 16) & 0xffffffff
                    except ValueError:
                        continue
                if regs[r] in byhash:
                    names.add(byhash[regs[r]])
            if i.mnemonic == 'ret':
                break
        got.append(sorted(names))
    exp = [[f'Prob{INSECT_MONTHS[k // 6]}{INSECT_SLOTS[k % 6]}'] for k in range(72)]
    return {'0x95ebe0 insect Prob getter index = month * 6 + slot': {
        'entries': 72, 'mismatches': [[k, g] for k, (g, e) in enumerate(zip(got, exp)) if g != e][:10], 'pass': got == exp,
        'reader': '0x9582d0(table, hemisphere, &month, &slot, item) calls entry month * 6 + slot (index > 71 -> entry 0)'}}


def candidate_table():
    """Per hemisphere, month and slot: fish weights per water kind and insect weights, ItemID only [TBL]."""
    tables, status, kind = load_fish()
    fish = {}
    for name, mask in MASKS.items():
        water = 'Sea' if mask & 0b1010000 else 'River'
        for h in (0, 1):
            for m in range(12):
                for s in range(3):
                    rows = [(r['item'], r['prob'][m][s]) for r in tables[(water, h)]
                            if status[r['item']]['bait'] and kind.get(r['item']) == KIND_FISH
                            and mask >> status[r['item']]['type'] & 1 and r['prob'][m][s]]
                    fish[f'{name}/{"NS"[h]}/{m + 1}/{FISH_SLOTS[s]}'] = rows
    t = _table('InsectAppearParam')
    c = [x['name'] for x in t['columns']]
    st = _table('InsectStatusParam')
    sc = [x['name'] for x in st['columns']]
    weather = {r[sc.index('ItemID')]: r[sc.index('AppearWeather')]['labels'][0] for r in st['rows']}
    insects = {}
    for h in (0, 1):
        rows = [r for r in t['rows'] if r[c.index('AppearArea')] == h]
        for m in range(12):
            for s in range(6):
                col = c.index(f'Prob{INSECT_MONTHS[m]}{INSECT_SLOTS[s]}')
                insects[f'{"NS"[h]}/{m + 1}/{INSECT_SLOTS[s]}'] = [(r[c.index('ItemID')], r[col]) for r in rows if r[col]]
    return {'fish_position_pick': fish, 'insect_prob': insects,
            'insect_appear_weather': weather,
            'fish_gates': {'rain_only': [SIRAKANSU], 'open_catch_count': {i: s['open'] for i, s in status.items() if s['open']}},
            'fish_shadow': {i: s['shadow'] for i, s in status.items()},
            'fish_fallback': {'river': 0x148, 'pond': 0x8ae, 'sea': 0x8d8},
            'fish_slot_by_hour': [fish_slot(h) for h in range(24)], 'insect_slot_by_hour': [insect_slot(h) for h in range(24)]}


def fish_cases():
    rig, rng = FishRig(), random.Random(20200320)
    out = {}
    out.update(insect_getter_case(rig.sb))
    out.update(slot_cases(rig))
    out.update(gate_cases(rig))
    out.update(position_cases(rig, rng))
    out.update(percent_cases(rig, rng))
    out['meta_unhandled'] = rig.sb.unknown_imports
    return out


def main():
    """`table` writes output/gameplay/creature_spawn.json (numbers and ItemIDs only); otherwise runs the native cases."""
    if sys.argv[1:] == ['table']:
        doc = {'meta': {'schema': 'acnh-re/gameplay/creature_spawn/1', 'game_version': '1.0.0',
                        'evidence': '[TBL] FishAppear*/FishStatusParam/ItemParam/InsectAppearParam/InsectStatusParam; '
                                    'pick rules terbukti native (see gameplay_native.json); insect pick itself still [PSEUDO]',
                        'keys': 'fish: <water kind>/<N|S>/<month>/<slot> -> [ItemID, Prob]; insects: <N|S>/<month>/<slot>'},
               'data': candidate_table()}
        path = OUTPUT/'gameplay'/'creature_spawn.json'
        path.write_text(json.dumps(doc, separators=(',', ':')) + '\n')
        print(path, path.stat().st_size)
        return
    print(json.dumps({k: (v['pass'] if isinstance(v, dict) and 'pass' in v else v) for k, v in fish_cases().items()}, indent=1))


if __name__ == '__main__':
    main()
