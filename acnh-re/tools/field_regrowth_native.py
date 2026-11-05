"""Native checks of daily field regrowth helpers (docs/GAMEPLAY_SCENARIO.md section 10).

Runs original functions from the ExeFS `main` in nso_sandbox:

* 0x4d7110 rock kind for a new rock: one u32 from the field RNG at 0x344d100 (returned by 0x4c0df0, xorshift128
  0x19aa0e0), index floor(u32 * 5 / 2^32) into the u32 table 0x29f5f90 (StoneA, StoneB, StoneC, StoneD, StoneE).
  Fully native; no stub.
* 0x7abd00 beach shell kind: season code from 0x2035f0 (SeasonCalendar column 5 = Shop), one draw 0..99 from the
  date-seeded day RNG 0x35e9510 through 0xf53420, cumulative thresholds into tables 0x29f7a80 / 0x29ef060.
  Only 0x2035f0 (calendar singleton lookup) is controlled; the RNG, thresholds, tables and item writer are native.
* 0x7a7010 shell caps: scans the beach bitset *0x32e2410 and writes the daily cap (*0x32e24d0) and the total cap
  (*0x32e24e8): 3/9 by default, 8/9 when a beach cell lies at z in [80, 180] on one side (x < 100 or x > 99,
  half-unit coordinates from 0x7b0020), 10/16 when both sides have one. Fully native; the bitset is written by the rig.

Used by tools/gameplay_native.py; the Python models below are the documented rules.
"""
from pathlib import Path
import random
import struct
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from nso_sandbox import Sandbox  # noqa: E402
MASK = 0xffffffff


def initialize(seed):
    """sead xorshift128 seed expansion (0x19aa040; formula verified in tools/native_rng.py)."""
    state, value = [], seed & MASK
    for increment in range(1, 5):
        value = ((value ^ (value >> 30)) * 0x6c078965 + increment) & MASK
        state.append(value)
    return state


def roll(state):
    """One u32 draw of 0x19aa0e0 and the next state."""
    a, b, c, d = state
    n = (a ^ (a << 11)) & MASK
    value = (n ^ (n >> 8) ^ d ^ (d >> 19)) & MASK
    return value, [b, c, d, value]


FIELD_RNG, DAY_RNG = 0x344d100, 0x35e9510
STONES = [0xeb12, 0xeb13, 0xeb16, 0xeb15, 0xeb14]            # StoneA, StoneB, StoneC, StoneD, StoneE (FgMainParam)
SHELL_NORMAL = [(6, 0x560), (17, 0x565), (28, 0x564), (39, 0x55f), (50, 0x55e), (70, 0x566), (100, 0x563)]
SHELL_SUMMER = [(10, 0x175e), (16, 0x560), (26, 0x565), (36, 0x564), (46, 0x55f), (56, 0x55e), (73, 0x566),
                (100, 0x563)]
BEACH_PTR, DAILY_CAP_PTR, TOTAL_CAP_PTR = 0x32e2410, 0x32e24d0, 0x32e24e8


# ---- documented rules ----
def stone_model(state):
    v, state = roll(state)
    return STONES[(v * 5) >> 32], state


def shell_model(season, state):
    v, state = roll(state)
    r = (v * 100) >> 32
    for limit, item in (SHELL_SUMMER if season == 1 else SHELL_NORMAL):
        if r < limit:
            return item, r, state
    raise AssertionError(r)


def shell_cap_model(cells):
    west = east = False
    for x, z in cells:                       # half-unit coordinates: x = 2 * (idx & 0xff), z = 2 * (idx >> 8)
        if 80 <= z <= 180:
            west |= x < 100
            east |= x > 99
    if west and east:
        return 10, 16
    return (8, 9) if west or east else (3, 9)


# ---- rig ----
class RegrowthRig:
    def __init__(self):
        self.sb = Sandbox()
        self.out = self.sb.alloc(0x40)
        self.season = 0
        self.sb.stub(0x2035f0, lambda s: self.season)

    def _state(self, addr, state=None):
        if state is not None:
            self.sb.uc.mem_write(addr, struct.pack('<4I', *state))
        return list(struct.unpack('<4I', self.sb.read(addr, 16)))

    def _indirect(self, va, args=()):
        self.sb.uc.mem_write(self.out, b'\xcd' * 0x40)
        self.sb.reg('x8', self.out)
        self.sb.call(va, args)
        return struct.unpack('<H', self.sb.read(self.out, 2))[0]

    def stone(self, state):
        self._state(FIELD_RNG, state)
        item = self._indirect(0x4d7110)
        return item, self._state(FIELD_RNG)

    def shell(self, season, state):
        self.season = season
        self._state(DAY_RNG, state)
        item = self._indirect(0x7abd00)
        return item, self._state(DAY_RNG)

    def shell_caps(self, indices):
        beach = self.sb.u64(BEACH_PTR)
        words = [0] * 0x400
        for i in indices:
            words[i >> 5] |= 1 << (i & 31)
        self.sb.uc.mem_write(beach + 8, struct.pack('<1024I', *words))
        daily, total = self.sb.u64(DAILY_CAP_PTR), self.sb.u64(TOTAL_CAP_PTR)
        self.sb.uc.mem_write(daily, b'\xee')
        self.sb.uc.mem_write(total, b'\xee')
        self.sb.call(0x7a7010)
        return self.sb.read(daily, 1)[0], self.sb.read(total, 1)[0]


def _cell(idx):
    return 2 * (idx & 0xff), 2 * (idx >> 8)


def regrowth_cases(samples=3000):
    rig, rng = RegrowthRig(), random.Random(20200321)
    out = {}

    mism, seen = [], {}
    for _ in range(samples):
        state = initialize(rng.getrandbits(32))
        expect, expect_state = stone_model(state)
        got, got_state = rig.stone(state)
        seen[hex(got)] = seen.get(hex(got), 0) + 1
        if (got, got_state) != (expect, expect_state):
            mism.append({'state': state, 'native': [got, got_state], 'model': [expect, expect_state]})
    out['0x4d7110 new rock kind'] = {'samples': samples, 'kinds_seen': seen, 'mismatches': mism[:5],
                                     'pass': not mism and len(seen) == 5}

    mism, buckets = [], {0: set(), 1: set()}
    for season in (0, 1, 2, 3):
        for _ in range(samples):
            state = initialize(rng.getrandbits(32))
            expect, r, expect_state = shell_model(season, state)
            got, got_state = rig.shell(season, state)
            buckets[1 if season == 1 else 0].add(got)
            if (got, got_state) != (expect, expect_state):
                mism.append({'season': season, 'r': r, 'native': got, 'model': expect})
    out['0x7abd00 shell kind'] = {'samples': 4 * samples, 'seasons': [0, 1, 2, 3],
                                  'items_seen': {k: sorted(hex(i) for i in v) for k, v in buckets.items()},
                                  'mismatches': mism[:5],
                                  'pass': not mism and len(buckets[0]) == 7 and len(buckets[1]) == 8}

    def idx(x, z):
        return (z // 2) * 256 + x // 2
    fixed = {'empty': [], 'south only': [idx(110, 190)], 'west z=80': [idx(98, 80)], 'west z=78': [idx(98, 78)],
             'east z=180': [idx(100, 180)], 'east z=182': [idx(100, 182)], 'both sides': [idx(20, 120), idx(200, 120)],
             'x=98/x=100': [idx(98, 100), idx(100, 100)], 'one side twice': [idx(10, 90), idx(60, 170)]}
    runs, mism = {}, []
    cases = list(fixed.items())
    for n in range(400):
        cases.append((f'random {n}', sorted({rng.randrange(0x60 * 256) for _ in range(rng.randrange(1, 12))})))
    for name, cells in cases:
        expect = shell_cap_model([_cell(i) for i in cells])
        got = rig.shell_caps(cells)
        if name in fixed:
            runs[name] = list(got)
        if got != expect:
            mism.append({'case': name, 'native': got, 'model': expect})
    out['0x7a7010 shell caps'] = {'cases': len(cases), 'fixed': runs, 'mismatches': mism[:5], 'pass': not mism}
    out['meta_unhandled'] = rig.sb.unknown_imports
    return out


if __name__ == '__main__':
    import json
    print(json.dumps({k: (v['pass'] if isinstance(v, dict) and 'pass' in v else v)
                      for k, v in regrowth_cases().items()}, indent=1))
