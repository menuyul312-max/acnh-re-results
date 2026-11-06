"""Native checks of weed growth, spread and seasonal conversion (docs/GAMEPLAY_SCENARIO.md section 10.3).

Runs the original functions from the ExeFS `main` in nso_sandbox over a synthetic field work object
(the PlacementRig of tools/island_placement_native.py: 5 item-tile bitsets + 26 unit bitsets).

* 0x4b6000(work, first, count, cap, a, b, c, d) weed growth. Every weed unit (set 17) grows one GrowupFg step
  when rand100 <= threshold: stage 1 uses a (b on a watered tile on the first simulated day), stage 2 uses c (d).
* 0x4b63e0(work, season, first, &count, cap, a, b, c, d, mask) weed spread. Every weed of the set-17 snapshot
  spreads when rand100 <= threshold: stage 1 a (b when first and watered), stage 2 10 (c), stage 3 80 (d).
  The child goes to a uniformly drawn neighbour unit (8 around, set 2, inside the field, |height| <= 5,
  in `mask` when given) whose layer-0 tile is empty; it is a stage-1 weed of `season` (see child_model).
  Stops when count reaches cap.
* 0x4ba120(season, work) seasonal conversion: every weed keeps its slot (1A/1B/1C/2A/2B/2C/3) in the
  7-entry table of the new season (tables at 0x3060b80, pointers 0x3060cb0).

Controlled: item layer read/write (0xa13f30, 0xa13fe0, 0x4ad1f0, 0x4ad3b0), item existence 0xf58f20,
the FgMainParam row wrapper 0x4d4a90 with its Kind/Grow getters 0x4d6620/0x4d6650 and the GrowupFg step
0x4d5ca0 (over the real FgMainParam rows), unit height 0x18d4c0, the field rectangle 0xa13a80 and the
day-RNG draws 0xf53420/0xf53450 (one recorded stream shared with the model). Native: unit iteration,
bitset copies and tests (set 17 snapshot, set 2, watered tile set 3, mask), the 8-neighbour scan, the height
window 0x7a2da0, the uniform bit pick 0x7afca0, the season tables and slot lookups 0x4b2f10/0x4b6c10,
the child pick 0x4b6d90, the set updates 0x7aa200/0x7aff70 and the weed counter 0x7aa360.
"""
import json
import os
from pathlib import Path
import random
import struct
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from island_placement_native import Field, PlacementRig, UNIT_BASE, UNIT_STRIDE, TILE_STRIDE  # noqa: E402

OUTPUT = Path(os.environ.get('ACNH_RE_OUTPUT', Path(__file__).resolve().parent.parent/'output'))
WEED_TABLE, WEED_PTRS = 0x3060b80, 0x3060cb0
WEED_KINDS = ('WeedSpr', 'WeedSmr', 'WeedAut0', 'WeedAut1', 'WeedAut2', 'WeedWin0', 'WeedWin1')
WEED_SET, FREE_SET, WATER_TILES = 17, 2, 3
COUNTER = 0x2e144
EMPTY = 0xfffe
NEIGHBOURS = [(dx, dz) for dz in (-2, 0, 2) for dx in (-2, 0, 2) if dx or dz]
DAILY_GROW = (20, 50, 5, 10)              # 0x4b6e70 -> 0x4b6000, cap 150
DAILY_SPREAD = (0, 5, 20, 100)            # 0x4b6e70 -> 0x4b63e0, cap 150, no mask
NEW_ISLAND_GROW = (5, 5, 2, 2)            # 0x4ae640 -> 0x4b6000, cap 1300
NEW_ISLAND_SPREAD = (20, 20, 10, 80)      # 0x4ae640 -> 0x4b63e0, cap 1300, mask


def weed_rows():
    """FgMainParam weed rows: UniqueID -> (kind index 0-6, Grow, GrowupFg, Label)."""
    t = json.loads((OUTPUT/'tables_resolved/FgMainParam.json').read_text())
    cols = [c['name'] for c in t['columns']]

    def val(row, col):
        v = row[cols.index(col)]
        return v['labels'][0] if isinstance(v, dict) and 'labels' in v else v
    rows = {}
    for r in t['rows']:
        kind = val(r, 'Kind')
        if kind in WEED_KINDS:
            rows[val(r, 'UniqueID')] = (WEED_KINDS.index(kind), val(r, 'Grow'), val(r, 'GrowupFg'), val(r, 'Label'))
    return rows


def table_from_rows(rows):
    """Expected 7-slot table per season from FgMainParam order (1A, 1B, 1C, 2A, 2B, 2C, 3)."""
    out = []
    for k in range(7):
        ids = [u for u, r in rows.items() if r[0] == k]
        by_label = sorted(ids, key=lambda u: (rows[u][1], rows[u][3]))
        out.append(by_label)
    return out


class Draws:
    """One day-RNG stream: draw(n) in [0, n). Native stubs and the model consume it in the same order."""

    def __init__(self, seed):
        self.rng, self.log = random.Random(seed), []

    def __call__(self, n):
        v = self.rng.randrange(n) if n > 0 else 0
        self.log.append((n, v))
        return v


# ---- documented rules ----
def scan(f):
    x0, z0, x1, z1 = f.rect
    for z in range(z0 + (z0 & 1), z1 + 1, 2):
        for x in range(x0 + (x0 & 1), x1 + 1, 2):
            yield x, z


def watered(f, x, z):
    return (x, z) in f.tiles.get(WATER_TILES, ())


def grow_model(f, items, rows, first, count, cap, p, draw):
    """0x4b6000. items: unit-origin tile -> UniqueID. Returns the writes [(pos, id)]."""
    a, b, c, d = p
    writes = []
    if count >= cap:
        return writes
    for x, z in scan(f):
        if not f.unit_has(WEED_SET, x, z) or items.get((x, z)) not in rows:
            continue
        uid = items[(x, z)]
        stage, w = rows[uid][1], first and watered(f, x, z)
        if stage == 1:
            thr = b if w else a
        elif stage == 2:
            thr = d if w else c
        else:
            continue
        if draw(100) <= thr and rows[uid][2] != EMPTY:
            items[(x, z)] = rows[uid][2]
            writes.append(((x, z), items[(x, z)]))
    return writes


def child_model(table, slot, draw):
    """0x4b6d90: stage-3 parent -> any stage-1 slot; slot A -> B/C, B -> A/C, C -> A/B (stage 1 or 2 parent)."""
    if slot == 6:
        return table[draw(3)]
    r = draw(2)
    return table[{0: r + 1, 3: r + 1, 2: r, 5: r}.get(slot, 2 if r == 1 else 0)]


def slot_of(tables, uid):
    for t in tables:
        if uid in t:
            return t.index(uid)
    return None


def spread_model(f, items, rows, tables, season, first, count, cap, p, mask, draw):
    """0x4b63e0. Mutates items, f.units (sets 0-4, 24 lose the unit, 17 gains it). Returns (count, placed)."""
    a, b, c, d = p
    placed = []
    if count >= cap:
        return count, placed
    snapshot = set(f.units.get(WEED_SET, ()))
    x0, z0, x1, z1 = f.rect
    for x, z in scan(f):
        if (x >> 1, z >> 1) not in snapshot or items.get((x, z)) not in rows:
            continue
        uid = items[(x, z)]
        stage, w = rows[uid][1], first and watered(f, x, z)
        thr = {1: b if w else a, 2: c if w else 10, 3: d if w else 80}.get(stage)
        if thr is None or draw(100) > thr:
            continue
        h0 = f.h(x >> 1, z >> 1)
        cand = []
        for dx, dz in NEIGHBOURS:
            nx, nz = x + dx, z + dz
            if not (x0 <= nx <= x1 and z0 <= nz <= z1) or not f.unit_has(FREE_SET, nx, nz):
                continue
            if mask is not None and (nx >> 1, nz >> 1) not in mask:
                continue
            if abs(f.h(nx >> 1, nz >> 1) - h0) <= 5.0:
                cand.append((nx, nz))
        if not cand:
            continue
        cand.sort(key=lambda t: t[1] * 512 + t[0])
        nx, nz = cand[draw(len(cand))]
        child = child_model(tables[season], slot_of(tables, uid), draw)
        if items.get((nx, nz), EMPTY) != EMPTY:
            continue
        items[(nx, nz)] = child
        unit = (nx >> 1, nz >> 1)
        for k in (0, 1, 2, 3, 4, 24):
            f.units.get(k, set()).discard(unit)
        f.units.setdefault(WEED_SET, set()).add(unit)
        count += 1
        placed.append(((nx, nz), child))
        if count >= cap:
            break
    return count, placed


def convert_model(f, items, tables, season):
    """0x4ba120: [(pos, new id)] for every weed unit in scan order."""
    out = []
    for x, z in scan(f):
        if f.unit_has(WEED_SET, x, z) and (x, z) in items:
            uid = items[(x, z)]
            s = slot_of(tables, uid)
            items[(x, z)] = tables[season][s] if s is not None else uid
            out.append(((x, z), items[(x, z)]))
    return out


# ---- rig ----
class WeedRig(PlacementRig):
    def __init__(self):
        super().__init__()
        sb = self.sb
        self.rows = weed_rows()
        self.items, self.writes, self.draw = {}, [], None
        self.mask_ptr = sb.alloc(0x1008)
        self.count_ptr = sb.alloc(0x10)
        for va in (0xa13820, 0x4bb670):
            sb.stub(va, None)
        sb.stub(0xa13f30, self._read_item)
        sb.stub(0xa13fe0, self._read_item)
        sb.stub(0x4ad1f0, self._write_item)
        sb.stub(0x4ad3b0, self._write_item)
        sb.stub(0xf58f20, lambda s: int(self._u16(s.reg('x0')) in self.rows))
        sb.stub(0x4d4a90, self._wrap)
        sb.stub(0x4d6620, lambda s: int(self._u16(s.reg('x0') + 8) in self.rows))
        sb.stub(0x4d6650, lambda s: self.rows.get(self._u16(s.reg('x0') + 8), (0, 1))[1])
        sb.stub(0x4d5ca0, self._grow)
        sb.stub(0xf53420, lambda s: self.draw(s.reg('x0') & 0xffffffff))
        sb.stub(0xf53450, lambda s: (s.reg('x0') & 0xffffffff) + self.draw((s.reg('x1') - s.reg('x0')) & 0xffffffff))

    def _u16(self, p):
        return struct.unpack('<H', self.sb.read(p, 2))[0]

    def _item(self, uid):
        return struct.pack('<HBBI', uid, 0, 0, 0)

    def _read_item(self, s):
        # struct return: item word to x8, position in x2 (x0 = layer, x1 = layer index)
        x, z = struct.unpack('<ii', s.read(s.reg('x2') + 8, 8))
        s.uc.mem_write(s.reg('x8'), self._item(self.items.get((x, z), EMPTY)))
        return None

    def _write_item(self, s):
        x, z = struct.unpack('<ii', s.read(s.reg('x3') + 8, 8))
        uid = self._u16(s.reg('x2'))
        self.items[(x, z)] = uid
        self.writes.append(((x, z), uid))
        return 1

    def _wrap(self, s):
        w, item = s.reg('x0'), s.reg('x1')
        s.uc.mem_write(w + 8, s.read(item, 8))
        s.uc.mem_write(w + 0x10, struct.pack('<Q', w + 8))
        return None

    def _grow(self, s):
        p = s.reg('x0') + 8
        nxt = self.rows.get(self._u16(p), (0, 0, EMPTY))[2]
        if nxt == EMPTY:
            return 0
        s.uc.mem_write(p, struct.pack('<H', nxt))
        return 1

    def native_tables(self):
        sb = self.sb
        ptrs = [WEED_TABLE] + [sb.u64(WEED_PTRS + 8 * i) for i in range(6)]
        return [list(struct.unpack('<7I', sb.read(p, 28))) for p in ptrs]

    def unit_set(self, n):
        words = struct.unpack('<1024I', self.sb.read(self.work + UNIT_BASE + n * UNIT_STRIDE + 8, 0x1000))
        return {((i << 5 | b) & 255, (i << 5 | b) >> 8) for i, w in enumerate(words) if w for b in range(32) if w >> b & 1}

    def counter(self):
        return self.sb.u32(self.work + COUNTER) >> 8 & 0x7ff

    def prepare(self, f, items, seed, census=0):
        self.load(f)
        self.items, self.writes, self.draw = dict(items), [], Draws(seed)
        self.sb.uc.mem_write(self.work + COUNTER, struct.pack('<I', census << 8))

    def grow(self, first, count, cap, p):
        self.sb.call(0x4b6000, (self.work, first, count, cap) + tuple(p))

    def spread(self, season, first, count, cap, p, mask=None):
        sb = self.sb
        mp = 0
        if mask is not None:
            words = [0] * 0x400
            for ux, uz in mask:
                i = uz * 256 + ux
                words[i >> 5] |= 1 << (i & 31)
            sb.uc.mem_write(self.mask_ptr + 8, struct.pack('<1024I', *words))
            mp = self.mask_ptr
        sb.uc.mem_write(self.count_ptr, struct.pack('<I', count))
        sp = sb.STACK + 0x3ff000
        sb.uc.mem_write(sp, struct.pack('<QQ', p[3], mp))
        sb.call(0x4b63e0, (self.work, season, first, self.count_ptr, cap, p[0], p[1], p[2]))
        return sb.u32(self.count_ptr)

    def convert(self, season):
        self.sb.call(0x4ba120, (season, self.work))


# ---- cases ----
def _random_weed_field(rng, rows, tables, rect, density):
    f = Field(rect)
    x0, z0, x1, z1 = rect
    units = [(x, z) for z in range(z0, z1 + 1, 2) for x in range(x0, x1 + 1, 2)]
    items = {}
    p_h = rng.choice([0, 0.1, 0.3])
    for x, z in units:
        u = (x >> 1, z >> 1)
        if rng.random() < p_h:
            f.height[u] = rng.choice([4.0, 5.0, 5.5, -5.0, 10.0])
        roll = rng.random()
        if roll < density:
            season = rng.randrange(7)
            items[(x, z)] = rng.choice(tables[season])
            f.units.setdefault(WEED_SET, set()).add(u)
        elif roll < density + 0.03:
            items[(x, z)] = 0x0b38            # an occupied tile that is still in set 2 (child refused)
            f.units.setdefault(FREE_SET, set()).add(u)
        elif rng.random() < 0.8:
            f.units.setdefault(FREE_SET, set()).add(u)
        if rng.random() < 0.3:
            f.tiles.setdefault(WATER_TILES, set()).add((x, z))
    # tiles just outside the field rectangle: set 2 there must never receive a child
    for x in range(x0 - 2, x1 + 3, 2):
        for z in (z0 - 2, z1 + 1 + ((z1 + 1) & 1)):
            f.units.setdefault(FREE_SET, set()).add((x >> 1, z >> 1))
    return f, items


def weed_cases(samples=120):
    rig, rng = WeedRig(), random.Random(20200320)
    rows = rig.rows
    out = {}

    native = rig.native_tables()
    expect = table_from_rows(rows)
    out['0x3060b80 weed season tables'] = {
        'tables': [[f'{u:#x}' for u in t] for t in native],
        'labels': [[rows[u][3] for u in t] for t in native],
        'pass': native == expect and all(rows[t[i]][1] == (1, 1, 1, 2, 2, 2, 3)[i] for t in native for i in range(7))}
    tables = native

    rect = (40, 40, 71, 65)
    mism, writes, grown = [], 0, {1: 0, 2: 0}
    for n in range(samples):
        f, items = _random_weed_field(rng, rows, tables, rect, rng.choice([0.2, 0.5]))
        first = n & 1
        p = DAILY_GROW if n % 3 else NEW_ISLAND_GROW
        cap, count = (150, 0) if n % 7 else (150, 150)
        seed = rng.getrandbits(32)
        rig.prepare(f, items, seed)
        rig.grow(first, count, cap, p)
        got = rig.writes
        m_items = dict(items)
        want = grow_model(f, m_items, rows, first, count, cap, p, Draws(seed))
        writes += len(got)
        for pos, uid in want:
            grown[rows[items[pos]][1]] += 1
        if got != want:
            mism.append({'case': n, 'first': first, 'native': got[:4], 'model': want[:4]})
    out['0x4b6000 weed growth'] = {'runs': samples, 'writes': writes, 'grown_by_stage': grown, 'mismatches': mism[:3],
                                   'thresholds': {'daily': DAILY_GROW, 'new_island': NEW_ISLAND_GROW},
                                   'pass': not mism and grown[1] > 0 and grown[2] > 0}

    mism, placed_total, capped, refused_outside, slots = [], 0, 0, 0, set()
    for n in range(samples):
        f, items = _random_weed_field(rng, rows, tables, rect, rng.choice([0.05, 0.2, 0.5]))
        season, first = rng.randrange(7), (n >> 1) & 1
        new_island = n % 2
        p = NEW_ISLAND_SPREAD if new_island else DAILY_SPREAD
        cap = 1300 if new_island else 150
        count = rng.choice([0, 10, cap - 3, cap - 1]) if n % 5 == 0 else rng.randrange(0, 60)
        mask = None
        if new_island:
            mask = {(x >> 1, z >> 1) for x, z in scan(f) if rng.random() < 0.7}
        seed = rng.getrandbits(32)
        rig.prepare(f, items, seed)
        got_count = rig.spread(season, first, count, cap, p, mask)
        got_17, got_2 = rig.unit_set(WEED_SET), rig.unit_set(FREE_SET)
        mf = Field(rect)
        mf.units = {k: set(v) for k, v in f.units.items()}
        mf.tiles, mf.height = f.tiles, f.height
        m_items = dict(items)
        draws = Draws(seed)
        want_count, want = spread_model(mf, m_items, rows, tables, season, first, count, cap, p, mask, draws)
        placed_total += len(want)
        capped += int(want_count >= cap and count < cap)
        x0, z0, x1, z1 = rect
        refused_outside += sum(1 for (x, z), _ in want if not (x0 <= x <= x1 and z0 <= z <= z1))
        for pos, uid in want:
            slots.add(slot_of(tables, uid))
        ok = (got_count == want_count and rig.writes == want and got_17 == mf.units.get(WEED_SET, set())
              and got_2 == mf.units.get(FREE_SET, set()) and rig.counter() == min(150, len(want)))
        if not ok:
            mism.append({'case': n, 'count': [got_count, want_count], 'native': rig.writes[:4], 'model': want[:4],
                         'set17_equal': got_17 == mf.units.get(WEED_SET, set()),
                         'set2_equal': got_2 == mf.units.get(FREE_SET, set()), 'counter': rig.counter()})
    out['0x4b63e0 weed spread'] = {'runs': samples, 'children': placed_total, 'runs_that_hit_cap': capped,
                                   'child_slots_seen': sorted(slots), 'mismatches': mism[:3],
                                   'thresholds': {'daily': DAILY_SPREAD, 'new_island': NEW_ISLAND_SPREAD},
                                   'pass': not mism and placed_total > 0 and capped > 0 and slots == {0, 1, 2}
                                   and refused_outside == 0}

    mism, runs = [], 0
    for n in range(samples // 4):
        f, items = _random_weed_field(rng, rows, tables, rect, 0.4)
        season = n % 7
        rig.prepare(f, items, 0)
        rig.convert(season)
        m_items = dict(items)
        want = convert_model(f, m_items, tables, season)
        runs += 1
        if rig.writes != want:
            mism.append({'case': n, 'season': season, 'native': rig.writes[:4], 'model': want[:4]})
    out['0x4ba120 weed season conversion'] = {'runs': runs, 'mismatches': mism[:3], 'pass': not mism}
    out['meta_unhandled'] = rig.sb.unknown_imports
    return out


if __name__ == '__main__':
    res = weed_cases()
    print(json.dumps({k: (v['pass'] if isinstance(v, dict) and 'pass' in v else v) for k, v in res.items()}, indent=1))
    for k, v in res.items():
        if isinstance(v, dict) and not v.get('pass', True):
            print(k, json.dumps(v, default=str)[:3000])
