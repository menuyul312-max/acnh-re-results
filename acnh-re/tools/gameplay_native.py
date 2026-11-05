"""Native verification of gameplay readings: run the original functions from the NSO (tools/nso_sandbox.py)
and compare them with the formulas written in docs/GAMEPLAY_*.md. Writes output/gameplay/gameplay_native.json.

Usage: python3 tools/gameplay_native.py [--output-root DIR] [--weeks 3000]
"""
import argparse
import json
from pathlib import Path
import random
import struct
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from nso_sandbox import Sandbox, NSO_SHA256  # noqa: E402
from villager_move_native import villager_cases  # noqa: E402
from visitor_schedule_native import visitor_cases  # noqa: E402
from creature_spawn_native import fish_cases  # noqa: E402
from field_regrowth_native import regrowth_cases  # noqa: E402
from island_content_native import island_content_cases  # noqa: E402
from island_placement_native import placement_cases  # noqa: E402

F = np.float32
RNG_FN = 0x19aa0e0          # xorshift128 draw; stubbed with a controlled stream
FLAG_GET, FLAG_SET = 0xf44d90, 0xf44e70


# ---- formulas as documented (GAMEPLAY_SCENARIO 5.1, GAMEPLAY_FLOW 10.1, GAMEPLAY_SCENARIO 3.7) ----
def friendship_level(v):
    return 1 if v < 30 else 2 if v < 60 else 3 if v < 100 else 4 if v < 150 else 5 if v < 200 else 6


def duplicate_penalty(counter, distinct):
    dup = counter - distinct
    return 0.0 if dup < 5 else F(dup) * F(0.5 if dup <= 9 else 0.75)


SCORE_WEIGHTS = {  # va: f(x)
    0x15c6910: lambda x: x, 0x15c6920: lambda x: F(x) * F(0.25), 0x15c6930: lambda x: x, 0x15c6940: lambda x: F(0),
    0x15c6950: lambda x: F(x) * F(4), 0x15c6960: lambda x: x, 0x15c6970: lambda x: F(x) * F(4),
    0x15c6980: lambda x: F(x) * F(0.2), 0x15c6990: lambda x: min(F(x), F(190)), 0x15c69a0: lambda x: x}

NEXT_PATTERN = {0: (20, 50, 65), 1: (50, 55, 75), 2: (25, 70, 75), 3: (45, 70, 85)}


def next_pattern(prev, r):
    if prev not in NEXT_PATTERN:
        return 2
    a, b, c = NEXT_PATTERN[prev]
    return 0 if r < a else 1 if r < b else 2 if r < c else 3


def turnip_week(prev, draws):
    """Documented generator; draws() returns the next u32 of the RNG. Returns u32[17] like the save struct."""
    it = iter(draws)

    def u32():
        return next(it)

    def randint(n):
        return (u32() * n) >> 32

    def uf():
        return F(struct.unpack('<f', struct.pack('<I', (u32() >> 9) | 0x3f800000))[0]) - F(1)

    def price(rate):
        return int(F(F(rate) * F(base)) + F(0.99999))
    s = [0] * 17
    base = s[0] = randint(21) + 90
    pat = s[15] = next_pattern(prev, randint(100))
    p = {}
    if pat == 0:
        dec1 = 3 if u32() >= 0x80000000 else 2
        dec2 = 5 - dec1
        hi1 = randint(7)
        rest = 7 - hi1
        hi3 = randint(rest)
        i = 2
        for _ in range(hi1):
            p[i] = price(F(uf() * F(0.5)) + F(0.9)); i += 1
        rate = F(uf() * F(-0.2)) + F(0.8)
        for _ in range(dec1):
            p[i] = price(rate); i += 1
            rate = F(F(rate + F(-0.04)) + F(uf() * F(-0.06)))
        for _ in range(rest - hi3):
            p[i] = price(F(uf() * F(0.5)) + F(0.9)); i += 1
        rate = F(uf() * F(-0.2)) + F(0.8)
        for _ in range(dec2):
            p[i] = price(rate); i += 1
            rate = F(F(rate + F(-0.04)) + F(uf() * F(-0.06)))
        for _ in range(hi3):
            p[i] = price(F(uf() * F(0.5)) + F(0.9)); i += 1
    elif pat in (1, 3):
        peak = s[16] = randint(7) + 3 if pat == 1 else (u32() >> 29) + 2
        rate = F(uf() * F(-0.05 if pat == 1 else -0.5)) + F(0.9)
        i = 2
        while i < peak:
            p[i] = price(rate); i += 1
            rate = F(F(rate + F(-0.03)) + F(uf() * F(-0.02)))
        if pat == 1:
            for lo, span in ((0.9, 0.5), (1.4, 0.6), (2.0, 4.0), (1.4, 0.6), (0.9, 0.5)):
                p[i] = price(F(uf() * F(span)) + F(lo)); i += 1
            while i < 14:
                p[i] = price(F(uf() * F(0.5)) + F(0.4)); i += 1
        else:
            p[i] = price(F(uf() * F(0.5)) + F(0.9))
            p[i + 1] = price(F(uf() * F(0.5)) + F(0.9))
            peak_rate = F(uf() * F(0.6)) + F(1.4)
            p[i + 3] = price(peak_rate)
            span = F(peak_rate + F(-1.4))
            p[i + 2] = int(F(F(int(F(F(F(span * uf()) + F(1.4)) * F(base)) + F(0.99999))) + F(-1)))
            p[i + 4] = int(F(F(int(F(F(F(span * uf()) + F(1.4)) * F(base)) + F(0.99999))) + F(-1)))
            i += 5
            rate = F(uf() * F(-0.5)) + F(0.9)
            while i < 14:
                p[i] = price(rate); i += 1
                rate = F(F(rate + F(-0.03)) + F(uf() * F(-0.02)))
    elif pat == 2:
        rate = F(uf() * F(-0.05)) + F(0.9)
        for i in range(2, 14):
            p[i] = price(rate)
            rate = F(F(rate + F(-0.03)) - F(uf() * F(0.02)))
    for i, v in p.items():
        s[i + 1] = v
    return s


# ---- emulation ----
class Stream:
    def __init__(self, seed):
        self.r = random.Random(seed)
        self.used = []

    def __call__(self, sb):
        v = self.r.getrandbits(32)
        self.used.append(v)
        return v


def verify(weeks=3000):
    sb = Sandbox()
    cases = {}
    # friendship level 0xd34a20
    vals = [0, 29, 30, 59, 60, 99, 100, 149, 150, 199, 200, 255]
    got = [sb.call(0xd34a20, (v,)) for v in vals]
    cases['0xd34a20 friendship level'] = {'inputs': vals, 'native': got, 'pass': got == [friendship_level(v) for v in vals]}
    # score weights 0x15c6910..0x15c69a0
    ok, n = True, 0
    for va, fn in SCORE_WEIGHTS.items():
        for x in (0.0, 1.0, 7.0, 37.5, 189.0, 190.0, 250.0):
            sb.reg('s0', struct.unpack('<I', struct.pack('<f', x))[0])
            sb.call(va, ())
            out = struct.unpack('<f', struct.pack('<I', sb.reg('s0') & 0xffffffff))[0]
            ok &= abs(out - float(fn(F(x)))) < 1e-4
            n += 1
    cases['0x15c6910..0x15c69a0 island score weights'] = {'samples': n, 'pass': bool(ok)}
    # duplicate penalty 0x15c4db0 on a synthetic 0x228-byte block
    ok, n = True, 0
    blk = sb.alloc(0x228)
    for cat in (0, 1, 2):
        for counter in (0, 4, 5, 9, 10, 20):
            for distinct in (0, 1, 3):
                if distinct > counter:
                    continue
                buf = bytearray(0x228)
                struct.pack_into('<H', buf, cat * 2, counter)
                for k in range(distinct):
                    struct.pack_into('<HBB', buf, 0x20 + 4 * k, 100 + k, cat << 4, 0)
                struct.pack_into('<I', buf, 0x220, distinct)
                sb.uc.mem_write(blk, bytes(buf))
                sb.call(0x15c4db0, (blk, cat))
                out = struct.unpack('<f', struct.pack('<I', sb.reg('s0') & 0xffffffff))[0]
                want = float(duplicate_penalty(counter, distinct)) if cat <= 1 else 0.0
                ok &= abs(out - want) < 1e-4
                n += 1
    cases['0x15c4db0 duplicate penalty'] = {'samples': n, 'pass': bool(ok)}
    # turnip generator 0xfc6d00 with a controlled RNG stream
    sb.stub(FLAG_GET, lambda s: 0)
    sb.stub(FLAG_SET, lambda s: 0)
    week = sb.alloc(0x44)
    mism, per_pattern = [], {0: 0, 1: 0, 2: 0, 3: 0}
    for seed in range(weeks):
        prev = seed % 4
        stream = Stream(seed)
        sb.stub(RNG_FN, stream)
        sb.uc.mem_write(week, struct.pack('<17I', *([0] * 15 + [prev, 0])))
        sb.call(0xfc6d00, (week,))
        native = list(struct.unpack('<17I', sb.read(week, 0x44)))
        model = turnip_week(prev, stream.used + [0] * 8)
        per_pattern[native[15]] += 1
        if native[:16] != model[:16] or (native[15] in (1, 3) and native[16] != model[16]):
            mism.append({'seed': seed, 'prev': prev, 'native': native, 'model': model})
    cases['0xfc6d00 turnip prices'] = {'weeks': weeks, 'patterns_seen': per_pattern, 'mismatches': len(mism),
                                      'first_mismatches': mism[:3], 'pass': not mism}
    cases.update(turnip_query_cases())
    cases.update(calendar_cases())
    fac = facility_cases()
    unhandled_fac = fac.pop('meta_unhandled')
    cases.update(fac)
    vil = villager_cases()
    unhandled_vil = vil.pop('meta_unhandled')
    cases.update(vil)
    vis = visitor_cases(weeks=weeks // 2, days=weeks)
    unhandled_vis = vis.pop('meta_unhandled')
    cases.update(vis)
    fish = fish_cases()
    unhandled_fish = fish.pop('meta_unhandled')
    cases.update(fish)
    field = regrowth_cases(samples=weeks)
    unhandled_field = field.pop('meta_unhandled')
    cases.update(field)
    island = island_content_cases(samples=weeks)
    unhandled_island = island.pop('meta_unhandled')
    cases.update(island)
    placement = placement_cases(samples=weeks // 5)
    unhandled_placement = placement.pop('meta_unhandled')
    cases.update(placement)
    return {'meta': {'source': f'ExeFS main sha256 {NSO_SHA256}', 'harness': 'tools/gameplay_native.py (nso_sandbox, unicorn)',
                     'stubs': {'0x19aa0e0': 'RNG draw replaced by a seeded Python stream', '0xf44d90/0xf44e70': 'flag get/set -> 0',
                               '0x3cca80 case': 'save-node lookup, base-price member, quantity accessor, requested amount, and quantity setter are controlled; the query function itself is native',
                               'villager cases': 'see tools/villager_move_native.py: flag get/set by name, side-effect writers, friendship records and the date are controlled; roll, weights, pick, odds, personality mask and NPC tables are native (move-in uses the real NmlNpcParam)',
                               'visitor schedule cases': 'see tools/visitor_schedule_native.py: flags by name, calendar event days, K.K. concert days, the weather-pattern index per date and the xorshift draw are controlled; save-layout lookups, facility/house accessors, week/date helpers, bit selection and both functions are native',
                               'fish cases': 'see tools/creature_spawn_native.py: table row/column accessors over the real FishAppear*/FishStatusParam/ItemParam rows, the catch-count gate 0x5b8e30, clock, weather code, session mode and the RNG word are controlled; loops, mask tests, weight sums, draw transforms, cumulative picks, the 0x5b9270 gate and the hour-to-slot helpers are native',
                               'field regrowth cases': 'see tools/field_regrowth_native.py: only the season lookup 0x2035f0 is controlled; the field RNG 0x344d100, the day RNG 0x35e9510 (0xf53420), xorshift 0x19aa0e0, thresholds, item tables, the item writer 0xf588a0 and the beach-bitset scan of 0x7a7010 are native',
                               'island content cases': 'see tools/island_content_native.py: flower pick 0xf50ad0 with only 0xf53420 controlled (returns the requested position, records the count); flower groups 0xf50f50/0xf51040 fully native; fruit 0xf509e0 with save-node accessors, the item-existence check 0xa1e8c0 (real ItemParam UniqueIDs), 0xaabd20/0xaab800, the item-by-index table, the TLS RNG state and nn::os::GetSystemTick (seed of the unused own RNG of item sets) controlled; set code, both xorshift steps and the pick are native',
                               'island placement cases': 'see tools/island_placement_native.py: synthetic field; ground-attribute accessors 0x18c4b0 (Sand) and 0x18cb10 (WaterCheck), unit height 0x18d4c0, unit CliffLevel 0x54c970, the field rectangle 0xa13a80 and (for 0x4b5cc0) the day-RNG draw 0xf53420 are controlled; 0x7ab350, its neighbour scans 0x7b0b30/0x7b0890/0x7af8a0/0x7af200, the slope check 0x7a2e10 and the neighbour pick 0x4b5cc0 run native over real work-object bitsets'},
                     'unhandled_imports': {**sb.unknown_imports, **unhandled_fac, **unhandled_vil, **unhandled_vis, **unhandled_fish, **unhandled_field, **unhandled_island, **unhandled_placement}},
            'cases': cases, 'all_pass': all(c['pass'] for c in cases.values())}


def turnip_query_cases():
    """Exercise the native query's three result codes with controlled save/input accessors."""
    sb = Sandbox()
    root = sb.alloc(0x209000)
    descriptor, data = sb.alloc(0x20), sb.alloc(8)
    sb.uc.mem_write(descriptor + 8, struct.pack('<QQ', 0, data))
    sb.uc.mem_write(data, struct.pack('<I', 100))
    quantity_scale = [2]
    requested_amount = [199]
    setter_accepts = [1]
    setter_calls = []
    sb.stub(0x154a800, lambda s: 0x1234)
    sb.stub(0x15449f0, lambda s: quantity_scale[0])
    sb.stub(0xeecf00, lambda s: root)

    def resolve_price_node(s):
        # FUN_00fe9350 writes a node descriptor; the native query reads data[0] from it.
        s.uc.mem_write(s.reg('x0') + 8, struct.pack('<Q', descriptor))

    sb.stub(0xee9350, resolve_price_node)
    sb.stub(0xee93d0, lambda s: 0)
    sb.stub(0x455d00, lambda s: s.reg('x0'))
    sb.stub(0xefd1a0, lambda s: requested_amount[0])

    def quantity_setter(s):
        setter_calls.append({'quantity': s.reg('x1'), 'accepts': setter_accepts[0]})
        return setter_accepts[0]

    sb.stub(0xefcc40, quantity_setter)
    obj = sb.alloc(0x20)

    def run(quantity, amount, accepts):
        sb.uc.mem_write(obj + 8, struct.pack('<Q', quantity))
        requested_amount[0], setter_accepts[0] = amount, accepts
        return sb.call(0x3cca80, (obj,))

    got = {
        'quantity_missing': run(0, 999, 1),
        'below_base_times_quantity': run(1, 199, 1),
        'setter_accepts_at_threshold': run(1, 200, 1),
        'setter_rejects_at_threshold': run(1, 200, 0),
    }
    want = {'quantity_missing': 2, 'below_base_times_quantity': 1,
            'setter_accepts_at_threshold': 0, 'setter_rejects_at_threshold': 2}
    return {'0x3cca80 Daisy Mae turnip purchase query': {'base_price': 100, 'quantity_scale': quantity_scale[0],
            'results': got, 'expected': want, 'setter_calls': setter_calls, 'pass': got == want}}


def _packed(t):
    return struct.unpack('<Q', struct.pack('<hbbbbbx', t.year, t.month, t.day, t.hour, t.minute, t.second))[0]


def calendar_cases():
    """NormalLive 0xf0330, Daisy Mae 0xfdafa0 and today's visitor 0xfdc020 with nn::time served by nso_sandbox."""
    import datetime
    out = {}
    sb = Sandbox()
    sb.stub(FLAG_GET, lambda s: 1)                       # TkkFirstLive on
    event_days = set()
    sb.stub(0xf0790, lambda s: 1 if struct.unpack('<HBB', s.read(s.reg('x1'), 4)) in event_days else 0)
    vt, txt = sb.alloc(0x40), sb.alloc(16)
    sb.uc.mem_write(vt + 0x18, struct.pack('<Q', 0xd50f0))  # bare 'ret' for the label object's vtable call
    sb.uc.mem_write(txt, b'Ev\0')
    sb.stub(0xf0940, lambda s: s.uc.mem_write(s.reg('x8'), struct.pack('<QQ', vt, txt)))
    sb.stub(0xf6f30, lambda s: 0x1000)                   # calendar row found
    sb.stub(0x1665ea0, lambda s: 0)                      # row index 0
    skip_arr = sb.alloc(16)
    g = sb.u64(0x32d5848)                                # TkkSkipNormal array object
    sb.uc.mem_write(g, struct.pack('<I', 1))
    sb.uc.mem_write(g + 8, struct.pack('<Q', skip_arr))
    cal = sb.alloc(0x1000)
    week = [datetime.date(2020, 3, d) for d in range(8, 15)]   # Sunday 8 .. Saturday 14 March 2020
    expect = {('none', ()): ['Sat'],
              ('Before', (14,)): ['Fri'], ('Before', (13, 14)): ['Thu'], ('Before', tuple(range(9, 15))): [],
              ('Skip', (14,)): [], ('Same', (14,)): ['Sat'], ('Same', tuple(range(9, 15))): ['Sat']}
    got = {}
    for (rule, days), want in expect.items():
        sb.uc.mem_write(skip_arr, struct.pack('<H', {'none': 0, 'Before': 0, 'Skip': 1, 'Same': 2}[rule]))
        event_days.clear()
        event_days.update((2020, 3, d) for d in days)
        got[f'{rule} {list(days)}'] = [d.strftime('%a') for d in week if sb.call(0xf0330, (cal, d.year, d.month, d.day)) & 1]
    out['0xf0330 NormalLive date'] = {'results': got, 'pass': list(got.values()) == list(expect.values())}

    sb = Sandbox()
    root, save = sb.alloc(0x400000), sb.alloc(0x500000)
    sb.call(0xf32fa0, (root,))
    stack = [root]
    while stack:                                        # attach every layout node to the save buffer
        x = stack.pop()
        sb.uc.mem_write(x + 8, struct.pack('<Q', save))
        c = sb.u64(x + 0x18)
        while c:
            stack.append(c)
            c = sb.u64(c + 0x20)
    sb.stub(0xeecf00, lambda s: root)
    now = [datetime.datetime(2020, 3, 1, 9)]
    sb.stub(0x1fcac0, lambda s: _packed(now[0]))
    shop = sb.u64(root + 0x1f3e98 + 0x10)
    table = {}
    for state in range(4):
        sb.uc.mem_write(save + shop, struct.pack('<I', state))
        row = []
        for d in range(1, 8):
            now[0] = datetime.datetime(2020, 3, d, 9)
            row.append(sb.call(0xfdafa0, ()) & 1)
        table[state] = row
    want = {s: [1 if s >= 2 and d == 0 else 0 for d in range(7)] for s in range(4)}
    out['0xfdafa0 Daisy Mae (shop state x Sun..Sat)'] = {'results': table, 'pass': table == want}

    var, mgr = sb.u64(0x32d1cd0), sb.alloc(0x5000)
    sb.uc.mem_write(var, struct.pack('<Q', mgr))
    sched = sb.alloc(0x78)
    sb.uc.mem_write(sched, struct.pack('<7I', 10, 1, 2, 3, 4, 5, 6))
    codes = []
    for d in range(1, 8):
        sb.uc.mem_write(mgr + 0x4068, struct.pack('<Q', _packed(datetime.datetime(2020, 3, d, 9))))
        codes.append(sb.call(0xfdc020, (sched,)))
    out['0xfdc020 today visitor code (Sun..Sat)'] = {'results': codes, 'pass': codes == [0, 1, 2, 3, 4, 5, 6]}

    # campsite visitor odds 0xf7d7e0: smallest day-RNG float u that fails, per days since the last camper
    sb.stub(FLAG_GET, lambda s: 0)                       # CampFirstCamperVisit off
    sb.stub(0xf4db0, lambda s: 0)
    sb.stub(0xf4e00, lambda s: 0)
    u = [0.0]

    def draw(s):
        s.reg('s0', struct.unpack('<I', struct.pack('<f', u[0]))[0])
    sb.stub(0xf53490, draw)
    sb.uc.mem_write(save + sb.u64(root + 0x20d4d0 + 0x10), struct.pack('<I', 2))   # campsite state 2
    camper = sb.alloc(0x200)
    now[0] = datetime.datetime(2020, 3, 20, 9)
    first_fail = {}
    for days in range(9):
        sb.uc.mem_write(camper + 0x10c, struct.pack('<Q', _packed(now[0] - datetime.timedelta(days=days))))
        first_fail[days] = 1.0
        for k in range(0, 1000, 5):
            u[0] = k / 1000
            if not sb.call(0xf7d7e0, (camper,)) & 1:
                first_fail[days] = u[0]
                break
    want = {0: 0.0, 1: 0.0, 2: 0.0, 3: 0.055, 4: 0.105, 5: 0.155, 6: 0.205, 7: 0.205, 8: 0.205}
    out['0xf7d7e0 campsite visitor odds'] = {'first_failing_u_by_days': first_fail, 'documented': '0 / 5 / 10 / 15 / 20 %',
                                             'pass': first_fail == want}
    return out


class FacilityRig:
    """Flags by name (get bool 0xf44d90, get int 0xf44ad0, set 0xf44e70 / 0xf45380, player set 0xf4b870) and a
    structure query (0x1105130 -> 0x1071bd0 / 0x1072210) answered from a Python set of structure kinds."""
    def __init__(self):
        self.sb = sb = Sandbox()
        self.flags, self.present, self.player = {}, set(), {}

        def name(s):
            return s.read(s.u64(s.reg('x0') + 8), 64).split(b'\0')[0].decode()

        def setf(s):
            self.flags[name(s)] = s.reg('x1') & 0xffffffff
        sb.stub(FLAG_GET, lambda s: 1 if self.flags.get(name(s), 0) else 0)
        sb.stub(0xf44ad0, lambda s: self.flags.get(name(s), 0))
        sb.stub(FLAG_SET, setf)
        sb.stub(0xf45380, setf)
        sb.stub(0xf4b870, lambda s: self.player.__setitem__(name(s), s.reg('x1') & 0xff))
        mgr = sb.alloc(0x40)
        sb.uc.mem_write(mgr + 8, struct.pack('<Q', 1))
        sb.stub(0x1105130, lambda s: mgr)
        sb.stub(0x1071bd0, lambda s: s.uc.mem_write(s.reg('x0'), struct.pack('<IIII', s.reg('x1') & 0xff, 0, 1, 0)))
        sb.stub(0x1072210, lambda s: 1 if s.u32(s.reg('x1')) in self.present else 0)
        sb.stub(0x1071cd0, lambda s: None)
        sb.stub(0x1106cb0, lambda s: 1 if (s.reg('x0') & 0xff) in self.present else 0)   # structure of kind present
        self.state, self.info = sb.alloc(16), sb.alloc(0x20)

    def run(self, va, kind, state, elapsed, kit_from=0, flags=None):
        self.flags.clear(); self.flags.update(flags or {})
        self.present.clear(); self.player.clear()
        self.sb.uc.mem_write(self.state, struct.pack('<I', state))
        out = []
        for day, el in enumerate(elapsed):
            if day >= kit_from:
                self.present.add(kind)
            self.sb.uc.mem_write(self.info, struct.pack('<q', el))
            self.sb.call(va, (self.state, self.info))
            out.append([self.sb.u32(self.state), dict(sorted(self.flags.items()))])
        return out


def facility_cases():
    rig, out = FacilityRig(), {}
    tailor = {'1+1+1': rig.run(0xfcc300, 5, 1, [1, 1, 1]), '2 at once': rig.run(0xfcc300, 5, 1, [2]),
              'no kit': rig.run(0xfcc300, 5, 1, [1, 1], kit_from=9)}
    ok = (tailor['1+1+1'][0][0] == 1 and tailor['1+1+1'][0][1].get('TailorConstruction1') == 1
          and tailor['1+1+1'][1][0] == 2 and tailor['1+1+1'][1][1].get('TailorBuilt') == 1 and tailor['1+1+1'][1][1].get('TailorBuiltToday') == 1
          and tailor['2 at once'][0][0] == 2 and 'TailorBuiltToday' not in tailor['2 at once'][0][1]
          and all(r[0] == 1 for r in tailor['no kit']))
    out['0xfcc300 Able Sisters construction'] = {'runs': tailor, 'pass': ok}
    museum = {'tent': rig.run(0xf77050, 2, 1, [1]), 'tent 2 days': rig.run(0xf77050, 2, 1, [2])}
    ok = museum['tent'][0][0] == 2 and museum['tent'][0][1].get('MuseumBuilt') == 1 and museum['tent'][0][1].get('MuseumTentBuiltToday') == 1 \
        and museum['tent 2 days'][0][0] == 2 and 'MuseumTentBuiltToday' not in museum['tent 2 days'][0][1]
    out['0xf77050 museum tent'] = {'runs': museum, 'pass': ok}
    museum_upgrade = rig.run(0xf77050, 2, 2, [1, 1], flags={'MuseumGrowupEnable1': 1})
    ok = (museum_upgrade[0][0] == 2 and museum_upgrade[0][1].get('MuseumConstruction1') == 1
          and museum_upgrade[0][1].get('MuseumConstructionToday') == 1
          and museum_upgrade[1][0] == 3 and museum_upgrade[1][1].get('Museum2Built') == 1
          and museum_upgrade[1][1].get('Museum2BuiltToday') == 1
          and museum_upgrade[1][1].get('MuseumConstruction1') == 0)
    out['0xf77050 museum upgrade'] = {'runs': museum_upgrade, 'pass': ok}
    camp = {'kit': rig.run(0xf26330, 6, 1, [1]), 'no kit': rig.run(0xf26330, 6, 1, [1], kit_from=9)}
    ok = camp['kit'][0][0] == 2 and camp['kit'][0][1].get('CampSiteBuilt') == 1 and camp['kit'][0][1].get('CeremonyBuildCampSite') == 1 \
        and camp['no kit'][0][0] == 1
    out['0xf26330 campsite'] = {'runs': camp, 'pass': ok}
    out['meta_unhandled'] = rig.sb.unknown_imports
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--output-root', default=str(Path(__file__).resolve().parent.parent/'output'))
    ap.add_argument('--weeks', type=int, default=3000)
    a = ap.parse_args()
    res = verify(a.weeks)
    path = Path(a.output_root)/'gameplay'/'gameplay_native.json'
    path.write_text(json.dumps(res, indent=1) + '\n')
    print(path, {k: v['pass'] for k, v in res['cases'].items()})


if __name__ == '__main__':
    main()
