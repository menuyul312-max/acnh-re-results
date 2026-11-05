"""Native checks of the starting fruit and flowers of a new island (docs/GAMEPLAY_SCENARIO.md section 10.4).

Runs original functions from the ExeFS `main` in nso_sandbox:

* 0xf50ad0 flower pick: month m (1..12; shifted by six months when the hemisphere word at
  (*0x32d1a38)+0x651fc is 1), candidate indices 0..7 whose month mask (u16 at 0x35e913c + 8*i) has bit m-1 and
  that are not one of the three excluded indices, one draw of 0xf53420(count). With no candidate the last
  exclusion that is not -1 is dropped and the pick repeats; with none left the result is 3. Only 0xf53420 is
  controlled (it returns the requested position and records the count); the table init, masks, hemisphere
  shift, exclusions and the fallback are native.
* 0xf50f50 / 0xf51040: SaveFg.SpecialityFlower (+0x925) / VillageFlower (+0x924) index -> ItemFrom value of the
  seed group (0x52 + ...). Fully native.
* 0xf509e0 new-island fruit: SpecialityFruit (+0x900) = 0xab4470(exclude=0), forced to Apple 0x8a5 when the byte
  (*0x32d0600)+0x52a is set; SisterFruit (+0x902) = 0xab4470(exclude=1). 0xab4470 builds the item set
  {Apple, Orange, Pear, Peach, Cherry}, removes SpecialityFruit when asked, seeds a local xorshift from one draw of
  the thread RNG (TLS state) and picks candidate floor(u32 * n / 2^32) in item-ID order (0xa120c0, 0x4b5a20).
  Controlled: save-node accessors 0xeecf20/0xeecf00/0xee9350/0xee93d0 (they hand out the Fg block or a zero block),
  the item-existence check 0xa1e8c0 (answered from the real ItemParam UniqueIDs), two item-parameter helpers
  that need the full item tables (0xaabd20 variant adjuster run by 0xa120c0 on the picked item: skipped, it only
  rewrites variant bits; 0xaab800 stackable test: answers 0), the item-by-index table *0x32f02d0
  (filled with plain items 0..14999, normally built by a static initializer), the TLS RNG state and the force-apple byte; the set code, both RNG steps and the pick are native.

nn::os::GetSystemTick (seed of the unused own RNG of item-set objects) returns a constant.
Used by tools/gameplay_native.py; the Python models below are the documented rules.
"""
from pathlib import Path
import random
import struct
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from nso_sandbox import Sandbox  # noqa: E402
from field_regrowth_native import initialize, roll  # noqa: E402

# index -> (ItemFrom seed group, month mask); ItemFrom list at 0x29b535d (0x52 ShopSeed_Chrysanthemum ...)
FLOWERS = [(0x57, 0x81f), (0x55, 0x00e), (0x58, 0x03c), (0x56, 0xe70),
           (0x54, 0x7c0), (0x53, 0x1e0), (0x52, 0xf81), (0x59, 0xc0f)]
SEED_GROUP = {0x52: 'Chrysanthemum', 0x53: 'Lily', 0x54: 'Cosmos', 0x55: 'Hyacinth',
              0x56: 'Rose', 0x57: 'Anemone', 0x58: 'Tulip', 0x59: 'Pansy'}
FRUITS = [0x8a5, 0x8a6, 0x8ed, 0x8ee, 0x8ef]            # Apple, Orange, Pear, Peach, Cherry (ItemParam)
FG_NODE = 0x20d0e0                                      # SaveLand.Fg (0x928 bytes, data 0x4150b4)
ROOT = Path(__file__).resolve().parent.parent


def item_ids():
    import json
    d = json.loads((ROOT/'output'/'tables_resolved'/'ItemParam.json').read_text())
    col = [c['name'] if isinstance(c, dict) else c for c in d['columns']].index('UniqueID')
    return {r[col] for r in d['rows']}


# ---- documented rules ----
def flower_candidates(month, south, excl):
    m = month - 1 if 1 <= month <= 12 else 0
    if 1 <= month <= 12 and south:
        shifted = month + 6
        m = (shifted - 12 if shifted > 12 else shifted) - 1
    return [i for i, (_, mask) in enumerate(FLOWERS) if i not in excl and mask >> m & 1]


def flower_model(month, south, excl, pick):
    """pick(n) -> position; returns (index, [counts passed to 0xf53420])."""
    excl, counts = list(excl), []
    while True:
        cands = flower_candidates(month, south, excl)
        if cands:
            counts.append(len(cands))
            return cands[pick(len(cands))], counts
        last = max((k for k in range(3) if excl[k] != -1), default=None)
        if last is None:
            return 3, counts
        excl = [e if k < last else -1 for k, e in enumerate(excl)]


def fruit_pick_model(tls_state, exclude=None):
    seed, tls_state = roll(tls_state)
    local = initialize(seed)
    v, _ = roll(local)
    cands = [f for f in FRUITS if f != exclude]
    return cands[(v * len(cands)) >> 32], tls_state


def new_island_fruit_model(tls_state, force_apple):
    first, tls_state = fruit_pick_model(tls_state)
    special = 0x8a5 if force_apple else first
    sister, tls_state = fruit_pick_model(tls_state, special)
    return special, sister, tls_state


# ---- rig ----
class _Sandbox(Sandbox):
    """Answers nn::os::GetSystemTick with a constant: 0x19a9fe0 seeds the own RNG of every item-set object
    (0xa0ee00) from it; the picks here use the RNG passed in, never that one."""
    def _import(self, uc, address, size, _):
        if self.imports.get(address) == '_ZN2nn2os13GetSystemTickEv':
            self.reg('x0', 0x5eed)
            return
        super()._import(uc, address, size, _)


class IslandContentRig:
    def __init__(self):
        sb = self.sb = _Sandbox()
        self.fg = sb.alloc(0x1000)
        self.root = sb.alloc(0x10)
        self.zero = sb.alloc(0x1000)
        self.desc = sb.alloc(0x20)
        self.hemi_obj = sb.alloc(0x66000)
        sb.uc.mem_write(sb.u64(0x32d1a38), struct.pack('<Q', self.hemi_obj))
        self.force_obj = sb.alloc(0x1000)
        sb.uc.mem_write(sb.u64(0x32d0600), struct.pack('<Q', self.force_obj))
        self.pick, self.counts = (lambda n: 0), []

        def draw(s):
            n = s.reg('x0') & 0xffffffff
            self.counts.append(n)
            return self.pick(n)
        sb.stub(0xf53420, draw)
        for va in (0xeecf20, 0xeecf00):
            sb.stub(va, lambda s: self.root)

        def node(s):
            data = self.fg if s.reg('x1') == self.root + FG_NODE else self.zero
            s.uc.mem_write(self.desc, struct.pack('<QQQ', 0, 0, data))
            s.uc.mem_write(s.reg('x0') + 8, struct.pack('<Q', self.desc))
        sb.stub(0xee9350, node)
        sb.stub(0xee93d0, lambda s: 0)
        sb.stub(0xee9490, lambda s: 0)
        sb.stub(0xee94f0, lambda s: 0)
        ids = item_ids()
        sb.stub(0xa1e8c0, lambda s: 1 if (s.reg('x1') & 0xffff) in ids else 0)
        sb.stub(0xaabd20, lambda s: None)
        sb.stub(0xaab800, lambda s: 0)
        table = sb.u64(0x32f02d0)                      # item-by-index table (15000 plain items, static init)
        sb.uc.mem_write(table, b''.join(struct.pack('<HHI', i, 0, 0) for i in range(0x3a99)))
        self.tls = None

    def flower(self, month, south, excl, pick):
        self.sb.uc.mem_write(self.hemi_obj + 0x651fc, struct.pack('<I', 1 if south else 0))
        self.pick, self.counts = pick, []
        e = [x & 0xffffffff for x in excl]
        got = self.sb.call(0xf50ad0, (self.fg, month, *e))
        return self.sb.reg('x0') & 0xffffffff, list(self.counts)

    def flower_key(self, index, field):
        self.sb.uc.mem_write(self.fg + field, bytes([index]))
        self.sb.call(0xf50f50 if field == 0x925 else 0xf51040, (self.fg,))
        return self.sb.reg('x0') & 0xffffffff

    def new_island_fruit(self, tls_state, force_apple):
        sb = self.sb
        if self.tls is None:
            sb._import(sb.uc, next(a for a, n in sb.imports.items() if n == '_ZN2nn2os11GetTlsValueENS0_7TlsSlotE'), 4, None)
            self.tls = sb.tls
        sb.uc.mem_write(self.tls, struct.pack('<4I', *tls_state))
        sb.uc.mem_write(self.force_obj + 0x52a, bytes([1 if force_apple else 0]))
        sb.uc.mem_write(self.fg + 0x900, b'\xee\xee\xee\xee')
        sb.call(0xf509e0, (self.root,))
        special, sister = struct.unpack('<HH', sb.read(self.fg + 0x900, 4))
        return special, sister, list(struct.unpack('<4I', sb.read(self.tls, 16)))


def island_content_cases(samples=2000):
    rig, rng = IslandContentRig(), random.Random(20200320)
    out = {}

    # every month x hemisphere x exclusion pattern x draw position
    mism, runs, per_month = [], 0, {}
    excl_sets = [(-1, -1, -1)] + [(i, -1, -1) for i in range(8)] + [(i, j, -1) for i in range(8) for j in range(8) if i != j]
    excl_sets += [(0, 2, 7), (1, 2, 4), (4, 5, 6), (3, 6, 0), (1, 1, 1), (2, 2, -1)]
    for month in list(range(1, 13)) + [0, 13]:
        for south in (False, True):
            for excl in excl_sets:
                n = len(flower_candidates(month, south, list(excl)))
                for pos in range(max(n, 1)):
                    pick = (lambda p: (lambda k: min(p, k - 1)))(pos)
                    got = rig.flower(month, south, excl, pick)
                    expect = flower_model(month, south, list(excl), pick)
                    runs += 1
                    if excl == (-1, -1, -1) and 1 <= month <= 12:
                        per_month.setdefault(f'{"S" if south else "N"}{month}', set()).add(got[0])
                    if got != (expect[0], expect[1]):
                        mism.append({'month': month, 'south': south, 'excl': excl, 'pos': pos,
                                     'native': got, 'model': expect})
    out['0xf50ad0 island flower pick'] = {
        'runs': runs, 'mismatches': mism[:5],
        'north_by_month': {k: sorted(v) for k, v in per_month.items() if k[0] == 'N'},
        'pass': not mism}

    keys = {'SpecialityFlower +0x925 (0xf50f50)': [rig.flower_key(i, 0x925) for i in range(8)],
            'VillageFlower +0x924 (0xf51040)': [rig.flower_key(i, 0x924) for i in range(8)]}
    expect = [k for k, _ in FLOWERS]
    out['0xf50f50 / 0xf51040 flower index -> ItemFrom seed group'] = {
        'native': {k: [hex(x) for x in v] for k, v in keys.items()},
        'species': [SEED_GROUP[k] for k in expect],
        'pass': all(v == expect for v in keys.values())}

    mism, seen = [], {}
    for n in range(samples):
        state = initialize(rng.getrandbits(32))
        force = n % 10 == 0
        expect = new_island_fruit_model(state, force)
        got = rig.new_island_fruit(state, force)
        seen.setdefault('forced' if force else 'random', {}).setdefault(hex(got[0]), set()).add(hex(got[1]))
        if got != expect:
            mism.append({'state': state, 'force': force, 'native': got, 'model': expect})
    out['0xf509e0 speciality and sister fruit'] = {
        'samples': samples, 'mismatches': mism[:5],
        'seen': {k: {f: sorted(s) for f, s in v.items()} for k, v in seen.items()},
        'pass': not mism and len(seen.get('random', {})) == 5 and set(seen.get('forced', {})) == {'0x8a5'}}
    out['meta_unhandled'] = rig.sb.unknown_imports
    return out


if __name__ == '__main__':
    import json
    res = island_content_cases(400)
    print(json.dumps({k: (v['pass'] if isinstance(v, dict) and 'pass' in v else v) for k, v in res.items()}, indent=1))
    for k, v in res.items():
        if isinstance(v, dict) and not v.get('pass', True):
            print(k, json.dumps(v, default=str)[:1500])
