"""Native checks of island field placement predicates (docs/GAMEPLAY_SCENARIO.md section 10.5).

Runs original functions from the ExeFS `main` in nso_sandbox over a synthetic field work object
(0x2e150 bytes: 5 item-tile bitsets of 0x4008 bytes at +0, then 26 unit bitsets of 0x1008 bytes at +0x14028).

Coordinates: positions are item-tile coordinates (x, z); one unit = 2 x 2 item tiles, unit bitset bit =
(z >> 1) * 256 + (x >> 1). Item-tile bitsets use bit = z * 512 + x.

* 0x7ab350(work, pos, beach) tree spot check, called by tree growth 0x4b99a0 and by the new-island pass of
  0x4ae640 (beach = 1 for palms). The terrain accessors are controlled from a synthetic map:
  0x18c4b0 (all four ground attributes of an item tile have ColGroundAttributeParam.Sand),
  0x18cb10 (one of the four has WaterCheck), 0x18d4c0 (unit height), 0x54c970 (unit CliffLevel) and the
  field rectangle 0xa13a80. Everything else is native: the neighbour scans 0x7b0b30 / 0x7b0890 / 0x7af8a0
  over the work-object bitsets and the slope check 0x7a2e10.

Used by tools/gameplay_native.py; the Python models below are the documented rules.
"""
from pathlib import Path
import random
import struct
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from nso_sandbox import Sandbox  # noqa: E402

WORK_SIZE = 0x2e150
SQUARE = ((0, 0), (1, 0), (0, 1), (1, 1))
UNIT_BASE, UNIT_STRIDE, TILE_STRIDE = 0x14028, 0x1008, 0x4008
LAND_MGR_PTR = 0x32d0de8          # ELF VA of the land-manager pointer; *(*ptr) != 0 enables 0x7a2e10
NEIGHBOURS = [(dx, dz) for dz in (-2, 0, 2) for dx in (-2, 0, 2) if dx or dz]
TREE_SETS = (5, 10, 11)           # trees, palms, bamboo; members of set 9 (growing trees) are ignored
BLOCK_SETS = (19, 18)             # stumps, rocks


class Field:
    """Synthetic terrain and work-object bitsets."""

    def __init__(self, rect=(8, 8, 215, 183)):
        self.rect = rect                          # inclusive item-tile rectangle of the field
        self.sand, self.water = set(), set()      # item tiles
        self.height, self.cliff = {}, {}          # units (x >> 1, z >> 1)
        self.units = {}                           # set index -> set of units
        self.tiles = {}                           # item-tile set index -> set of tiles

    def inside(self, x, z):
        x0, z0, x1, z1 = self.rect
        return x0 <= x and x + 1 <= x1 and z0 <= z and z + 1 <= z1

    def h(self, ux, uz):
        return self.height.get((ux, uz), 0.0)

    def c(self, ux, uz):
        return self.cliff.get((ux, uz), 0)

    def unit_has(self, n, x, z):
        return (x >> 1, z >> 1) in self.units.get(n, ())


# ---- documented rules ----
def slope_model(f, x, z, mode):
    """0x7a2e10: 1 = the spot touches a slope. Heights and CliffLevel are per unit (pos // 2)."""
    h0, c0 = f.h(x >> 1, z >> 1), f.c(x >> 1, z >> 1)
    for dx, dz in NEIGHBOURS:
        nx, nz = x + dx, z + dz
        d = f.h(nx >> 1, nz >> 1) - h0
        if -5.0 < d < 5.0:
            continue
        if not mode:
            return True
        water = sum((nx + a, nz + b) in f.water for a, b in ((0, 0), (1, 0), (0, 1), (1, 1)))
        if water == 4:
            return True
        if dx and dz and water:               # diagonal neighbour that is partly water
            continue
        if f.c(nx >> 1, nz >> 1) != c0:
            return True
    return False


def tree_spot_model(f, x, z, beach):
    """0x7ab350: 1 = a tree (beach = 0) or palm (beach = 1) may stand at item tile (x, z)."""
    for dz in (-2, 0, 2):
        for dx in (-2, 0, 2):
            nx, nz = x + dx, z + dz
            if ((nx, nz) in f.sand) != bool(beach):
                return False
            water = sum((nx + a, nz + b) in f.water for a, b in ((0, 0), (1, 0), (0, 1), (1, 1)))
            if water == 4 or (water and not (dx and dz)):
                return False
    for n in TREE_SETS:
        if any(not f.inside(x + dx, z + dz) or (f.unit_has(n, x + dx, z + dz) and not f.unit_has(9, x + dx, z + dz))
               for dx, dz in NEIGHBOURS):
            return False
    for n in BLOCK_SETS:
        if any(not f.inside(x + dx, z + dz) or f.unit_has(n, x + dx, z + dz) for dx, dz in NEIGHBOURS):
            return False
    tiles = f.tiles.get(1, set())
    for dx, dz in NEIGHBOURS:
        nx, nz = x + dx, z + dz
        if not f.inside(nx, nz) or all((nx + a, nz + b) in tiles for a, b in ((0, 0), (1, 0), (0, 1), (1, 1))):
            return False
    return not slope_model(f, x, z, 1)


FREE_ORDER = [(-2, -2), (2, -2), (-2, 0), (2, 0), (-2, 2), (0, 2), (2, 2)]   # (0, -2) is never a candidate


def free_neighbour_model(f, x, z, use_n3, use_n20, pick):
    """0x4b5cc0: random neighbour unit from set 3 (use_n3) or set 1, optionally intersected with set 20."""
    x0, z0, x1, z1 = f.rect
    cand = []
    for dx, dz in FREE_ORDER:
        nx, nz = x + dx, z + dz
        if not (x0 <= nx <= x1 and z0 <= nz <= z1):
            continue
        if f.unit_has(3 if use_n3 else 1, nx, nz) and (not use_n20 or f.unit_has(20, nx, nz)):
            cand.append((nx, nz))
    if not cand:
        return 0, 0, None
    return 1, len(cand), cand[min(pick, len(cand) - 1)]


# ---- rig ----
class PlacementRig:
    def __init__(self):
        sb = self.sb = Sandbox()
        self.work = sb.alloc(WORK_SIZE)
        self.point = sb.alloc(0x10)
        self.rect = sb.alloc(0x30)
        self.field = Field()
        mgr = sb.u64(LAND_MGR_PTR)
        sb.uc.mem_write(mgr, struct.pack('<Q', sb.alloc(0x100)))
        sb.stub(0x18c4b0, lambda s: int(self._xz(s) in self.field.sand))
        sb.stub(0x18cb10, lambda s: int(self._xz(s) in self.field.water))
        sb.stub(0x18d4c0, self._height)
        sb.stub(0x54c970, lambda s: self.field.c(*self._xz(s)))
        sb.stub(0xa137b0, None)
        sb.stub(0xa13a80, lambda s: self.rect)

    @staticmethod
    def _xz(s):
        return struct.unpack('<ii', s.read(s.reg('x0') + 8, 8))

    def _height(self, s):
        s.reg('s0', struct.unpack('<I', struct.pack('<f', self.field.h(*self._xz(s))))[0])
        return None

    def load(self, f):
        self.field = f
        sb = self.sb
        sb.uc.mem_write(self.work, bytes(WORK_SIZE))
        x0, z0, x1, z1 = f.rect
        sb.uc.mem_write(self.rect + 0x10, struct.pack('<ii', x0, z0))
        sb.uc.mem_write(self.rect + 0x20, struct.pack('<ii', x1, z1))
        for n, cells in f.units.items():
            words = [0] * 0x400
            for ux, uz in cells:
                i = uz * 256 + ux
                words[i >> 5] |= 1 << (i & 31)
            sb.uc.mem_write(self.work + UNIT_BASE + n * UNIT_STRIDE + 8, struct.pack('<1024I', *words))
        for n, cells in f.tiles.items():
            words = [0] * 0x1000
            for x, z in cells:
                i = z * 512 + x
                words[i >> 5] |= 1 << (i & 31)
            sb.uc.mem_write(self.work + n * TILE_STRIDE + 8, struct.pack('<4096I', *words))

    def _pos(self, x, z):
        self.sb.uc.mem_write(self.point + 8, struct.pack('<ii', x, z))
        return self.point

    def tree_spot(self, x, z, beach):
        return self.sb.call(0x7ab350, (self.work, self._pos(x, z), beach)) & 1

    def slope(self, x, z, mode):
        return self.sb.call(0x7a2e10, (self._pos(x, z), mode)) & 1

    def free_neighbour(self, x, z, use_n3, use_n20, pick=0):
        """0x4b5cc0(out, work, pos, use_n3, use_n20) with the day-RNG draw 0xf53420(n) forced to `pick`."""
        drawn = []

        def draw(s):
            drawn.append(s.reg('x0') & 0xffffffff)
            return min(pick, drawn[-1] - 1)
        self.sb.stub(0xf53420, draw)
        out = self.sb.alloc(0x10)
        self.sb.uc.mem_write(out, b'\xee' * 0x10)
        found = self.sb.call(0x4b5cc0, (out, self.work, self._pos(x, z), use_n3, use_n20)) & 1
        self.sb.stub(0xf53420, None)
        del self.sb.stubs[0xf53420]
        return found, (drawn[0] if drawn else 0), struct.unpack('<ii', self.sb.read(out + 8, 8)) if found else None


# ---- cases ----
def _random_field(rng, x, z):
    f = Field()
    p_sand = rng.choice([0, 0.02, 0.98, 1])
    p_water = rng.choice([0, 0, 0.02, 0.1])
    p_h, p_c = rng.choice([0, 0, 0.05, 0.3]), rng.choice([0, 0.1])
    p_u, p_t = rng.choice([0, 0, 0.01, 0.05]), rng.choice([0, 0.5, 0.97])
    tiles = set()
    for tx in range(x - 6, x + 8):
        for tz in range(z - 6, z + 8):
            if rng.random() < p_sand:
                f.sand.add((tx, tz))
            if rng.random() < p_water:
                f.water.add((tx, tz))
            if rng.random() < p_t:
                tiles.add((tx, tz))
    f.tiles[1] = tiles
    for ux in range(x // 2 - 4, x // 2 + 5):
        for uz in range(z // 2 - 4, z // 2 + 5):
            if rng.random() < p_h:
                f.height[(ux, uz)] = rng.choice([-10.0, -5.0, -4.9, 4.9, 5.0, 8.0])
            if rng.random() < p_c:
                f.cliff[(ux, uz)] = rng.choice([1, 2])
            for n in (1, 3, 5, 9, 10, 11, 18, 19, 20):
                if rng.random() < p_u:
                    f.units.setdefault(n, set()).add((ux, uz))
    return f


def _perturbations(x, z):
    """One feature at a time around a clean grass spot: (name, field, beach)."""
    out = []
    for dx in (-2, 0, 2):
        for dz in (-2, 0, 2):
            nx, nz = x + dx, z + dz
            tag = f'({dx:+d},{dz:+d})'
            f = Field(); f.sand.add((nx, nz)); out.append((f'sand {tag}', f, 0))
            f = Field(); f.sand = {(a, b) for a in range(x - 4, x + 6) for b in range(z - 4, z + 6)} - {(nx, nz)}
            out.append((f'beach without sand {tag}', f, 1))
            for k, (a, b) in enumerate(SQUARE):
                f = Field(); f.water.add((nx + a, nz + b)); out.append((f'one water tile {k} {tag}', f, 0))
            f = Field(); f.water = {(nx + a, nz + b) for a, b in SQUARE}; out.append((f'all water {tag}', f, 0))
            if not (dx or dz):
                continue
            for n in TREE_SETS + BLOCK_SETS:
                f = Field(); f.units[n] = {(nx >> 1, nz >> 1)}; out.append((f'set {n} {tag}', f, 0))
            for n in TREE_SETS:
                f = Field(); f.units[n] = f.units[9] = {(nx >> 1, nz >> 1)}; out.append((f'set {n} and 9 {tag}', f, 0))
            f = Field(); f.tiles[1] = {(nx + a, nz + b) for a, b in SQUARE}; out.append((f'tile set 1 full {tag}', f, 0))
            f = Field(); f.tiles[1] = {(nx + a, nz + b) for a, b in SQUARE[:3]}; out.append((f'tile set 1 3/4 {tag}', f, 0))
            for h in (4.9, 5.0, -5.0, -4.9):
                f = Field(); f.height[(nx >> 1, nz >> 1)] = h; out.append((f'height {h:+} {tag}', f, 0))
            f = Field(); f.height[(nx >> 1, nz >> 1)] = 6.0; f.cliff[(nx >> 1, nz >> 1)] = 1
            out.append((f'height and cliff {tag}', f, 0))
            f = Field(); f.height[(nx >> 1, nz >> 1)] = -6.0; f.water.add((nx, nz))
            out.append((f'low with one water tile {tag}', f, 0))
    for name, rect in (('field edge west ok', (x - 2, 8, 215, 183)), ('field edge west cut', (x - 1, 8, 215, 183)),
                       ('field edge south ok', (8, 8, 215, z + 3)), ('field edge south cut', (8, 8, 215, z + 2))):
        out.append((name, Field(rect), 0))
    return out


def placement_cases(samples=600):
    rig, rng = PlacementRig(), random.Random(20200322)
    out = {}
    x, z = 100, 100

    mism, fixed, runs, accepted = [], {}, 0, 0
    for name, f, beach in _perturbations(x, z):
        rig.load(f)
        got, expect = rig.tree_spot(x, z, beach), int(tree_spot_model(f, x, z, beach))
        fixed[name] = got
        runs += 1
        if got != expect:
            mism.append({'case': name, 'native': got, 'model': expect})
    for n in range(samples):
        px, pz = x + rng.choice([0, 1]), z + rng.choice([0, 1])
        f = _random_field(rng, px, pz)
        rig.load(f)
        for beach in (0, 1):
            got, expect = rig.tree_spot(px, pz, beach), int(tree_spot_model(f, px, pz, beach))
            runs += 1
            accepted += got
            if got != expect:
                mism.append({'case': f'random {n}', 'beach': beach, 'native': got, 'model': expect})
    rejected_by = sorted(k for k, v in fixed.items() if not v)
    out['0x7ab350 tree spot'] = {'runs': runs, 'random_accepted': accepted, 'single_feature_rejected': len(rejected_by),
                                 'single_feature_accepted': sorted(k for k, v in fixed.items() if v),
                                 'mismatches': mism[:5], 'pass': not mism and 0 < accepted}

    mism, runs, hits = [], 0, 0
    for n in range(samples):
        px, pz = x + rng.choice([0, 1]), z + rng.choice([0, 1])
        f = _random_field(rng, px, pz)
        rig.load(f)
        for mode in (0, 1):
            got, expect = rig.slope(px, pz, mode), int(slope_model(f, px, pz, mode))
            runs += 1
            hits += got
            if got != expect:
                mism.append({'case': n, 'mode': mode, 'native': got, 'model': expect})
    out['0x7a2e10 slope check'] = {'runs': runs, 'slopes_found': hits, 'mismatches': mism[:5],
                                   'pass': not mism and 0 < hits < runs}

    mism, runs, counts = [], 0, set()
    for n in range(samples):
        f = _random_field(rng, x, z) if n % 2 else Field()
        if n % 2 == 0:
            for k in (1, 3, 20):
                f.units[k] = {((x + dx) >> 1, (z + dz) >> 1) for dx in (-2, 0, 2) for dz in (-2, 0, 2)
                              if n < 8 or rng.random() < 0.6}
        if n % 7 == 0:
            f.rect = (x - 2, z - 2, x + 1, z + 1)
        rig.load(f)
        use_n3, use_n20, pick = n & 1, (n >> 1) & 1, (n >> 1) % 8 if n < 16 else rng.randrange(8)
        got = rig.free_neighbour(x, z, use_n3, use_n20, pick)
        expect = free_neighbour_model(f, x, z, use_n3, use_n20, pick)
        runs += 1
        counts.add(got[1])
        if got != expect:
            mism.append({'case': n, 'native': got, 'model': expect})
    out['0x4b5cc0 free neighbour'] = {'runs': runs, 'candidate_counts_seen': sorted(counts), 'order': FREE_ORDER,
                                      'mismatches': mism[:5], 'pass': not mism and 7 in counts}
    out['meta_unhandled'] = rig.sb.unknown_imports
    return out


if __name__ == '__main__':
    import json
    res = placement_cases()
    print(json.dumps({k: (v['pass'] if isinstance(v, dict) and 'pass' in v else v) for k, v in res.items()}, indent=1))
    for k, v in res.items():
        if isinstance(v, dict) and not v.get('pass', True):
            print(k, json.dumps(v, default=str)[:2000])
