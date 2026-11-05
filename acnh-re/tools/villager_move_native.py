"""Native checks of the villager move-out roll (0xf847f0), candidate pick (0xf87670) and move-in (0xf84f10).

Runs the original functions from the ExeFS `main` in nso_sandbox. Save data is a zeroed 0x1d6d48-byte villager
block (save layout node 0xa8): 10 slots of 0x12ab0 bytes. Only accessors are controlled from Python: flag get/set
by name, side-effect writers (house, letters, memory reset), per-player friendship records, the game date, and the
RNG word 0x19aa0e0. The move-in cases load the real NmlNpcParam.bcsv (local baseline extraction, never committed)
and build the runtime NPC tables with the game's own initialisers 0xcc89e0 and 0xcd4050. Used by
tools/gameplay_native.py; see docs/GAMEPLAY_SCENARIO.md 5.1-5.2.
"""
from collections import Counter
import ast
import datetime
import json
import os
from pathlib import Path
import random
import struct
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from nso_sandbox import Sandbox  # noqa: E402

OUTPUT = Path(os.environ.get('ACNH_RE_OUTPUT', Path(__file__).resolve().parent.parent/'output'))
SLOT, FLAGS, STATUS = 0x12ab0, 0x11efc, 0x11efa
CAND, GAP, DAYS, CONF, LASTIN, LASTSTAY = 0x1d6d3d, 0x1d6d3e, 0x1d6d3f, 0x1d6d40, 0x1d6d41, 0x1d6d42
EXCLUDE = 0xbaae0          # per-species bitset of villagers that already lived here
DAILY_MODE = 0x35ee058     # 1 = draws come from the date-seeded RNG 0x35e9510 (set by 0xf84320)
PMASK = 0x35ee084          # personality mask used by the move-in filter 0xf8d7d0
NML_COLUMNS = {'BirthMDay': 269, 'BirthMonth': 270, 'Label': 273}


def packed(t):
    return struct.unpack('<Q', struct.pack('<hbbbbbx', t.year, t.month, t.day, t.hour, t.minute, t.second))[0]


def draw_for(r, n):
    """RNG word u such that 0xf53420(n) = (u * n) >> 32 returns r."""
    return -(-(r << 32) // n)


def nml_blob():
    meta = json.loads((OUTPUT/'tables_resolved'/'NmlNpcParam.json').read_text())
    raw = meta['raw'] if isinstance(meta['raw'], dict) else ast.literal_eval(meta['raw'])
    return (OUTPUT/raw['$blob']).read_bytes()


class VillagerRig:
    def __init__(self, pick_native=False):
        self.sb = sb = Sandbox()
        self.block = sb.alloc(0x1d6d48)
        self.flags, self.calls, self.bounds, self.draws = {}, [], [], []
        self.elapsed, self.out = sb.alloc(8), sb.alloc(8)

        def slot_of(p, off):
            return (p - off - self.block) // SLOT

        def name(desc):
            return sb.read(sb.u64(desc + 8), 64).split(b'\0')[0].decode()
        self.name = name
        sb.stub(0xf49620, lambda s: self.flags.get((slot_of(s.reg('x0'), FLAGS), name(s.reg('x1'))), 0))
        sb.stub(0xf497c0, lambda s: self.calls.append(('flag_set', slot_of(s.reg('x0'), FLAGS), name(s.reg('x2')), s.reg('x3') & 0xffffffff)))
        sb.stub(0xf44e70, lambda s: self.calls.append(('global_flag_set', name(s.reg('x0')), s.reg('x1') & 0xffffffff)))
        for va, tag in ((0xf8c2d0, 'history'), (0xf01640, 'slot_init'), (0xf866c0, 'house'), (0xd1fcf0, 'world'),
                        (0xf05d00, 'status2'), (0xf05b80, 'memory_reset')):
            sb.stub(va, (lambda t: lambda s: self.calls.append((t, slot_of(s.reg('x0'), 0))))(tag))
        sb.stub(0xf8a410, lambda s: self.calls.append(('leave', slot_of(s.reg('x1'), 0), s.reg('x2') & 0xff)))
        if not pick_native:
            sb.stub(0xf87670, lambda s: self.calls.append(('pick',)))
        sb.stub(0x19aa0e0, lambda s: self.draws.pop(0) if self.draws else 0)
        from unicorn import UC_HOOK_CODE
        sb.uc.hook_add(UC_HOOK_CODE, lambda uc, a, size, _: self.bounds.append(sb.reg('x0') & 0xffffffff), begin=0xf53420, end=0xf53420)
        sb.uc.mem_write(DAILY_MODE, b'\x01')

    def valid_ids(self, species=range(1, 0x23), count=20):
        """Synthetic NPC-id validity tables (filled at runtime from NmlNpcParam in the game)."""
        cnt, bits = self.sb.u64(0x32fa3b0), self.sb.u64(0x32fa3b8)
        for sp in species:
            self.sb.uc.mem_write(cnt + sp, bytes([count]))
            self.sb.uc.mem_write(bits + 4*sp, struct.pack('<I', (1 << count) - 1))

    def slot(self, i, npc=None):
        self.sb.uc.mem_write(self.block + i*SLOT, bytes(npc) if npc else b'\0\0\0')

    def state(self, **kw):
        offs = dict(cand=CAND, gap=GAP, days=DAYS, conf=CONF, lastin=LASTIN, laststay=LASTSTAY)
        for k, v in kw.items():
            self.sb.uc.mem_write(self.block + offs[k], struct.pack('<b', v))
        return {k: struct.unpack('<b', self.sb.read(self.block + o, 1))[0] for k, o in offs.items()}

    def lazy_draws(self, values):
        """Answer each 0xf53420(n) with the next wanted result r (clamped to n - 1)."""
        values = list(values)

        def draw(s):
            n = self.bounds[-1]
            return draw_for(min(values.pop(0) if values else 0, n - 1), n)
        self.sb.stubs[0x19aa0e0] = draw


# ---- move-out roll 0xf847f0 (pick 0xf87670 stubbed) ----
def _island(rig, n=10, **st):
    rig.flags.clear()
    for i in range(10):
        rig.slot(i, (1 + i, 0) if i < n else None)
        if i < n:
            rig.flags[(i, 'MoveInCompletion')] = 1
    base = dict(cand=-1, gap=0, days=0, conf=0, lastin=-1, laststay=-1)
    base.update(st)
    rig.state(**base)


def _day(rig, elapsed=1, r=None):
    rig.calls.clear()
    rig.bounds.clear()
    rig.lazy_draws([] if r is None else [r])
    rig.sb.uc.mem_write(rig.elapsed, struct.pack('<q', elapsed))
    rig.sb.uc.mem_write(rig.out, b'\0' * 8)
    rig.sb.call(0xf847f0, (rig.block, rig.out, rig.elapsed))
    return rig.state(), list(rig.calls), rig.sb.u32(rig.out)


def move_out_cases():
    rig = VillagerRig()
    rig.valid_ids()
    out = {}
    rows = {}
    for n in (5, 6, 8, 10):
        for d in (4, 5, 12, 30):
            want = 5*n + d if n > 5 and d > 4 else None
            res = {}
            for r in ((want - 1, want) if want else (0,)):
                _island(rig, n, days=d - 1)
                _, calls, _ = _day(rig, r=r)
                res[r] = {'drew': bool(rig.bounds), 'bound': rig.bounds[0] if rig.bounds else None, 'pick': ('pick',) in calls}
            if want:
                ok = res[want - 1]['pick'] and not res[want]['pick'] and res[want]['bound'] == 100
            else:
                ok = not res[0]['drew'] and rig.state()['cand'] == -1
            rows[f'settled={n} counter={d}'] = {'threshold_model': want, 'runs': res, 'ok': ok}
    out['0xf847f0 move-out roll threshold (r < 5 x settled + counter)'] = {'rows': rows, 'pass': all(v['ok'] for v in rows.values())}

    _island(rig, 10, gap=15, days=28)
    st, calls, _ = _day(rig, elapsed=3)
    out['0xf847f0 gap and counter update'] = {'state': st, 'drew': bool(rig.bounds), 'pass': st['gap'] == 12 and st['days'] == 30 and not rig.bounds}

    _island(rig, 10, cand=3, days=2)
    rig.flags[(3, 'AbandonedHouse')] = 1
    st, calls, vac = _day(rig)
    out['0xf847f0 abandoned candidate leaves'] = {'state': st, 'calls': calls, 'vacated_bits': vac,
                                                  'pass': vac == 1 << 3 and st['cand'] == -1 and st['gap'] == 14 and ('slot_init', 3) in calls}

    _island(rig, 10, days=2)
    rig.flags[(4, 'ForceMoveOut')] = 1
    rig.flags[(6, 'ForceMoveOut')] = 1
    st, calls, vac = _day(rig)
    out['0xf847f0 ForceMoveOut (first slot only)'] = {'state': st, 'calls': calls, 'vacated_bits': vac,
                                                      'pass': vac == 1 << 4 and ('leave', 4, 2) in calls and ('flag_set', 4, 'ForceMoveOut', 0) in calls and st['gap'] == 0}

    _island(rig, 10, cand=2, conf=1, days=3)
    day1 = _day(rig)
    status = rig.sb.read(rig.block + 2*SLOT + STATUS, 1)[0]
    day2 = _day(rig)
    out['0xf847f0 confirmed move: status 2, then leave'] = {
        'day1': {'state': day1[0], 'calls': day1[1], 'slot_status': status}, 'day2': {'state': day2[0], 'calls': day2[1], 'vacated_bits': day2[2]},
        'pass': status == 2 and day1[1] == [('status2', 2)] and day1[0]['days'] == 3 and ('leave', 2, 1) in day2[1]
        and day2[2] == 1 << 2 and day2[0]['gap'] == 15 and day2[0]['cand'] == -1}

    _island(rig, 6, days=20)
    rig.flags[(0, 'AbandonedHouse')] = 2
    _day(rig, r=0)
    not_settled = not rig.bounds
    _island(rig, 6, days=20)
    rig.flags[(0, 'AbandonedHouse')] = 1
    _, calls, _ = _day(rig, r=0)
    out['0xf855c0 settled count (AbandonedHouse < 2 and MoveInCompletion)'] = {
        'abandoned_2_drops_below_6': not_settled, 'abandoned_1_still_counts': ('pick',) in calls,
        'pass': not_settled and ('pick',) in calls}
    out['meta_unhandled'] = dict(rig.sb.unknown_imports)
    return out


# ---- candidate pick 0xf87670 ----
class PickRig(VillagerRig):
    def __init__(self):
        super().__init__(pick_native=True)
        sb = self.sb
        self.valid_ids()
        self.friend, self.players, self.birthday, self.struct_index = {}, 1, {}, None
        self.now = datetime.datetime(2020, 4, 10, 9)
        self.cur = [0, 0]
        sb.uc.mem_write(sb.u64(0x32d3788), struct.pack('<Q', sb.alloc(0x200)))     # NmlNpcParam table present
        sb.uc.mem_write(sb.u64(0x32d3790), b'\x01')                                # column offset cache valid
        cache = sb.u64(0x32d3798)
        sb.uc.mem_write(cache + 0x8c, struct.pack('<i', NML_COLUMNS['BirthMonth']))
        sb.uc.mem_write(cache + 0x88, struct.pack('<i', NML_COLUMNS['BirthMDay']))
        self.rows = {i: sb.alloc(0x200) for i in range(10)}
        self.mgr = sb.alloc(0x5000)
        sb.uc.mem_write(sb.u64(0x32d1cd0), struct.pack('<Q', self.mgr))
        root = sb.alloc(0x100)
        self.desc, self.data = sb.alloc(0x20), sb.alloc(0x40)
        sb.uc.mem_write(self.desc + 8, struct.pack('<QQ', 0, self.data))
        sb.stub(0xeecf40, lambda s: root if self.struct_index is not None else 0)
        sb.stub(0xee9350, lambda s: s.uc.mem_write(s.reg('x0') + 8, struct.pack('<Q', self.desc)))
        sb.stub(0xee93d0, lambda s: 0)

        def npc(s):
            self.cur[0] = (s.reg('x0') - self.block) // SLOT
            return 0x100 + self.cur[0]
        sb.stub(0xd35570, npc)
        sb.stub(0xd353f0, lambda s: 1)
        sb.stub(0x89ce0, lambda s: self.rows[self.cur[0]] if self.cur[0] in self.birthday else 0)

        def player(s):
            self.cur[1] = s.reg('x0') & 0xffffffff
            return sb.alloc(0x20000) if self.cur[1] < self.players else 0
        sb.stub(0xef6440, player)
        sb.stub(0xf97870, lambda s: s.uc.mem_write(s.reg('x0'), struct.pack('<I', self.cur[1])))
        sb.stub(0xf152d0, lambda s: (0x60000000 + ((s.reg('x0') - self.block) // SLOT) * 0x1000 + s.u32(s.reg('x1')) * 0x100)
                if ((s.reg('x0') - self.block) // SLOT, s.u32(s.reg('x1'))) in self.friend else 0)

        def points(s):
            assert self.name(s.reg('x1')) == 'Friendship'
            m = s.reg('x0') - 0x38 - 0x60000000
            return self.friend[(m // 0x1000, (m % 0x1000) // 0x100)]
        sb.stub(0xf486c0, points)

    def setup(self, n=10):
        self.friend.clear()
        self.birthday.clear()
        self.struct_index = None
        for i in range(10):
            self.slot(i, (1 + i, 0) if i < n else None)
        self.state(cand=-1, lastin=-1, laststay=-1, conf=1)

    def pick(self, r):
        sb = self.sb
        sb.uc.mem_write(self.mgr + 0x4068, struct.pack('<Q', packed(self.now)))
        sb.uc.mem_write(self.data, struct.pack('<I', 0xffffffff if self.struct_index is None else self.struct_index))
        for i, (m, d) in self.birthday.items():
            sb.uc.mem_write(self.rows[i], struct.pack('<I', 1))
            sb.uc.mem_write(self.rows[i] + NML_COLUMNS['BirthMDay'], bytes([d, m]))
        self.calls.clear()
        self.bounds.clear()
        self.lazy_draws([r])
        sb.call(0xf87670, (self.block,))
        return self.state()['cand']


def _f32(x):
    return struct.unpack('<f', struct.pack('<f', x))[0]


def pick_weights(friend, players, eligible):
    """Documented weight: floor((300 - floor(sum / players)) * 0.1) - players at level 6 (float32 as in 0xf87670)."""
    w = {}
    for s in eligible:
        pts = [friend.get((s, p), 0) for p in range(players)]
        avg = int(_f32(_f32(1.0 / players) * sum(pts)))
        w[s] = int(_f32(_f32(300 - avg) * _f32(0.1))) - sum(1 for v in pts if v >= 200)
    return w


def _cumulative(w, r):
    for s in sorted(w):
        if r < w[s]:
            return s
        r -= w[s]
    return -1


def pick_cases():
    rig, out = PickRig(), {}
    rig.setup()
    rig.players = 3
    rnd = random.Random(7)
    for s in range(10):
        for p in range(3):
            if (s + p) % 4:
                rig.friend[(s, p)] = rnd.choice([0, 15, 45, 99, 149, 199, 200, 255])
    w = pick_weights(rig.friend, 3, range(10))
    total = sum(w.values())
    got = [rig.pick(r) for r in range(total)]
    bound = rig.bounds[-1]
    want = [_cumulative(w, r) for r in range(total)]
    tail = rig.calls
    out['0xf87670 weighted pick (3 players, level-6 deduction)'] = {
        'weights_model': w, 'total_native': bound, 'total_model': total, 'all_draws_match': got == want,
        'after_pick_calls': tail, 'pass': got == want and bound == total and ('global_flag_set', 'IsMovingConsultationToPlayer', 0) in tail
        and tail[-1][0] == 'memory_reset' and rig.state()['conf'] == 0}

    def eligible():
        seen, total = set(), None
        for r in range(0, 600, 25):                    # every villager weighs 25 here
            c = rig.pick(r)
            total = rig.bounds[-1]
            if r >= total:
                break
            seen.add(c)
        return sorted(seen), total
    rig.setup()
    rig.players = 1
    for s in range(10):
        rig.friend[(s, 0)] = 50                       # weight 25 each
    rig.state(lastin=1, laststay=2)
    rig.struct_index = 3
    rig.slot(4)
    elig, total = eligible()
    out['0xf87670 exclusions (last moved in, persuaded, StructureMoveSaveIndex, empty slot)'] = {
        'eligible': elig, 'total': total, 'pass': elig == [0, 5, 6, 7, 8, 9] and total == 150}

    windows = {}
    for label, now, bdays, want in (
            ('09:00 on 04-10', datetime.datetime(2020, 4, 10, 9), {5: (4, 12), 6: (4, 10), 7: (4, 17), 8: (4, 18), 9: (4, 9), 0: (4, 19)}, [0, 1, 2, 3, 4, 9]),
            ('04:00 on 04-10 (game day 04-09)', datetime.datetime(2020, 4, 10, 4), {6: (4, 10), 7: (4, 17), 8: (4, 18), 9: (4, 9)}, [0, 1, 2, 3, 4, 5, 8]),
            ('09:00 on 12-28 (year wrap)', datetime.datetime(2020, 12, 28, 9), {1: (1, 3), 2: (1, 5), 3: (1, 6), 4: (12, 27)}, [0, 3, 4, 5, 6, 7, 8, 9])):
        rig.setup()
        rig.players = 1
        for s in range(10):
            rig.friend[(s, 0)] = 50
        rig.now, rig.birthday = now, bdays
        elig, total = eligible()
        windows[label] = {'birthdays': {k: f'{m:02d}-{d:02d}' for k, (m, d) in bdays.items()}, 'eligible': elig, 'expected': want, 'ok': elig == want}
    out['0xf87670 birthday window (trunc((birthday 05:00 - now) / day) in 0..7)'] = {'runs': windows, 'pass': all(v['ok'] for v in windows.values())}
    out['meta_unhandled'] = dict(rig.sb.unknown_imports)
    return out


# ---- move-in 0xf84f10 with the real NmlNpcParam ----
def load_nml(sb):
    """Place NmlNpcParam.bcsv in memory as the game's table object (rows at +0x1b8, label index at +0x1f0)."""
    b = nml_blob()
    rc, rs, fc, fl = struct.unpack_from('<IIHB', b, 0)
    base = (0x1c if fl else 0xc) + fc*8
    h = sb.alloc(len(b) + 0x100)
    sb.uc.mem_write(h, b)
    rows = [h + base + i*rs for i in range(rc)]
    t = sb.alloc(0x400)
    arr = sb.alloc(8*rc)
    sb.uc.mem_write(arr, struct.pack(f'<{rc}Q', *rows))
    sb.uc.mem_write(t + 0x1b0, struct.pack('<I', rc))
    sb.uc.mem_write(t + 0x1b8, struct.pack('<Q', arr))
    sb.uc.mem_write(t + 0x1c0, struct.pack('<I', rc))
    sb.uc.mem_write(sb.u64(0x32d3788), struct.pack('<Q', t))
    ents, ptrs = sb.alloc(0x28*rc), sb.alloc(8*rc)
    for i, r in enumerate(rows):
        hsh = sb.call(0x1bf0, (r + NML_COLUMNS['Label'], 0)) & 0xffffffff   # the game's label hash
        sb.uc.mem_write(ents + 0x28*i, struct.pack('<I', i))
        sb.uc.mem_write(ents + 0x28*i + 0x20, struct.pack('<I', hsh))
        sb.uc.mem_write(ptrs + 8*i, struct.pack('<Q', ents + 0x28*i))
    sb.uc.mem_write(t + 0x1e8, struct.pack('<i', rc))
    sb.uc.mem_write(t + 0x1f0, struct.pack('<Q', ptrs))
    pers = sb.alloc(2*rc)
    sb.uc.mem_write(sb.u64(0x32d9910), struct.pack('<IIQ', rc, 0, pers))
    loader, inner = sb.alloc(0x100), sb.alloc(0x20)
    sb.uc.mem_write(loader + 0xb0, struct.pack('<Q', inner))
    sb.uc.mem_write(inner + 8, struct.pack('<Q', h))
    sb.call(0xcc89e0, (loader,), limit=50_000_000)    # per-row builders, incl. personality 0xcc8ad0
    sb.call(0xcd4050, (), limit=50_000_000)           # NPC id validity tables
    return rows, pers


class MoveInRig(VillagerRig):
    def __init__(self):
        super().__init__()
        sb = self.sb
        del sb.stubs[0xf01640]                         # empty slots are initialised natively
        self.rows, self.pers_rows = load_nml(sb)
        self.ints, self.plots, self.waiting = {}, set(range(10)), False
        self.now = datetime.datetime(2020, 4, 10, 9)
        sb.stub(0x1fcac0, lambda s: packed(self.now))
        sb.stub(0x110a240, lambda s: 0)
        sb.stub(0xf8c540, lambda s: self.calls.append(('plot_path',)) or 0)
        obj = sb.alloc(0x30000)
        sb.uc.mem_write(obj + 0x2c674, struct.pack('<i', -1))
        sb.stub(0xd1c3d0, lambda s: obj)
        sb.stub(0xf8d210, lambda s: self.calls.append(('move_in_order',)) or 0)
        sb.stub(0xef44c0, lambda s: 1 if (s.reg('x0') & 0xffffffff) in self.plots else 0)
        sb.stub(0xf8cea0, lambda s: self.calls.append(('waiting_npc', (s.reg('x1') - self.block) // SLOT)) or (1 if self.waiting else 0))
        sb.stub(0xf44ad0, lambda s: self.ints.get(self.name(s.reg('x0')), 0))
        sb.stub(0xf03360, lambda s: self.calls.append(('move_in', (s.reg('x0') - self.block) // SLOT, tuple(s.read(s.reg('x1'), 3)))))
        sb.stub(0xf496c0, lambda s: None)
        sb.stub(0xd35570, lambda s: 0xffffffff)
        sb.stub(0xef4200, lambda s: 0)
        self.vac = sb.alloc(8)
        self.pers = {}                                 # (species, index) -> personality, from the native filter
        buf = sb.alloc(0x100)
        for p in range(8):
            sb.uc.mem_write(PMASK, struct.pack('<I', 1 << p))
            sb.call(0xcd2f40, (buf, 0xf8d7d0), limit=50_000_000)
            for sp in range(0x23):
                w = sb.u32(buf + 4*sp)
                for k in range(32):
                    if w >> k & 1:
                        self.pers[(sp, k)] = p

    def island(self, residents):
        sb = self.sb
        self.flags.clear()
        sb.stubs[0x19aa0e0] = lambda s: 0
        sb.uc.mem_write(self.block + EXCLUDE, b'\0' * 0x8c)
        for i in range(10):
            sb.uc.mem_write(self.block + i*SLOT, b'\0' * SLOT)
            if i < len(residents) and residents[i]:
                s, k = residents[i]
                self.slot(i, (s, k, self.pers[(s, k)]))
                self.flags[(i, 'MoveInCompletion')] = 1
                w = self.block + EXCLUDE + 4*s
                sb.uc.mem_write(w, struct.pack('<I', sb.u32(w) | 1 << k))
            else:
                sb.call(0xf01640, (self.block + i*SLOT,), limit=5_000_000)

    def day(self, vacated=0, draws=(0, 0, 0, 0)):
        sb = self.sb
        self.calls.clear()
        self.bounds.clear()
        sb.uc.mem_write(self.elapsed, struct.pack('<q', 1))
        sb.uc.mem_write(self.vac, struct.pack('<I', vacated))
        self.lazy_draws(draws)                         # plot, odds, species, villager
        sb.call(0xf84f10, (self.block, self.elapsed, self.vac), limit=50_000_000)
        moved = next((c for c in self.calls if c[0] == 'move_in'), None)
        return moved, list(self.bounds), sb.u32(PMASK)


def move_in_cases():
    rig, out = MoveInRig(), {}
    counts = Counter(rig.pers.values())
    byp = {p: sorted(k for k, v in rig.pers.items() if v == p) for p in range(8)}
    rnd = random.Random(3)

    def residents(perslist):
        used, res = set(), []
        for p in perslist:
            c = rnd.choice([x for x in byp[p] if x not in used])
            used.add(c)
            res.append(c)
        return res
    names = ['Boy_normal', 'Boy_active', 'Boy_pride', 'Boy_snobby', 'Girl_normal', 'Girl_active', 'Girl_pride', 'Girl_big_sis']
    looks = [str(r[[c['name'] for c in json.loads((OUTPUT/'tables_resolved'/'NmlNpcParam.json').read_text())['columns']].index('NpcLooks')])
             for r in json.loads((OUTPUT/'tables_resolved'/'NmlNpcParam.json').read_text())['rows']]
    per_row = struct.unpack(f'<{len(rig.rows)}H', rig.sb.read(rig.pers_rows, 2*len(rig.rows)))
    pairs = Counter((next((n for n in names if f"'{n}'" in lk), lk), v) for lk, v in zip(looks, per_row))
    mapping = {n: sorted({v for (m, v) in pairs if m == n}) for n in names}
    table = json.loads((OUTPUT/'tables_resolved'/'NmlNpcParam.json').read_text())
    init_live = sum(1 for r in table['rows'] if r[[c['name'] for c in table['columns']].index('InitLive')])
    out['0xcc8ad0 personality = NpcLooks enum index (397 real rows)'] = {
        'mapping': mapping, 'rows': len(per_row), 'move_in_candidates_per_personality': dict(sorted(counts.items())),
        'move_in_pool': len(rig.pers), 'rows_with_InitLive': init_live,
        'pass': all(mapping[n] == [i] for i, n in enumerate(names)) and len(rig.pers) == init_live}

    odds = {}
    for n in (3, 4, 5, 6, 7, 8, 9):
        for plots in (1, 3):
            for add in ((0, 3) if 5 <= n <= 7 else (0,)):
                rig.plots, rig.ints = set(range(plots)), {'NNpcContractProbablityAddPoint': add}
                res = residents([rnd.randrange(8) for _ in range(n)])
                want = None if n < 5 else (10 - n + (add if n <= 7 else 0) + plots) * 10
                want = None if want is not None and want >= 100 else want
                runs = {}
                for r in ((99,) if want is None else (want - 1, want)):
                    rig.island(res)
                    moved, bounds, _ = rig.day(draws=(0, r, 0, 0))
                    runs[r] = {'moved_in': moved is not None, 'odds_bound': bounds[1] if len(bounds) > 1 else None}
                ok = runs[99]['moved_in'] if want is None else runs[want - 1]['moved_in'] and not runs[want]['moved_in']
                odds[f'villagers={n} free_plots={plots} contract_points={add}'] = {'threshold_model': want, 'runs': runs, 'ok': ok}
    out['0xf84f10 move-in odds'] = {'rows': odds, 'pass': all(v['ok'] for v in odds.values())}

    picks = []
    rig.plots, rig.ints = set(range(10)), {}
    for _ in range(12):
        res = residents([rnd.randrange(8) for _ in range(rnd.randrange(1, 10))])
        c = Counter(rig.pers[x] for x in res)
        low = min(min(c.get(p, 0) for p in range(8)), 10)
        mask = sum(1 << p for p in range(8) if c.get(p, 0) == low)
        cand = sorted(k for k, v in rig.pers.items() if mask >> v & 1 and k not in res)
        species = sorted({s for s, _ in cand})
        r1 = rnd.randrange(len(species))
        inside = sorted(k for s, k in cand if s == species[r1])
        r2 = rnd.randrange(len(inside))
        rig.island(res)
        moved, bounds, got_mask = rig.day(draws=(0, 0, r1, r2))
        want_id = (species[r1], inside[r2], rig.pers[(species[r1], inside[r2])])
        marked = rig.sb.u32(rig.block + EXCLUDE + 4*species[r1]) >> inside[r2] & 1
        picks.append({'villagers': len(res), 'mask': got_mask, 'mask_model': mask, 'draw_bounds': bounds[2:4],
                      'draw_bounds_model': [len(species), len(inside)], 'id': list(moved[2]) if moved else None, 'id_model': list(want_id),
                      'ok': moved is not None and moved[2] == want_id and got_mask == mask and bounds[2:4] == [len(species), len(inside)] and marked == 1})
    out['0xf84f10 personality mask and two-stage pick (species, then villager)'] = {'runs': picks, 'pass': all(p['ok'] for p in picks)}

    res = residents([0, 1, 2, 3, 4, 5, 6])
    rig.island(res)
    for s, k in byp[7]:
        w = rig.block + EXCLUDE + 4*s
        rig.sb.uc.mem_write(w, struct.pack('<I', rig.sb.u32(w) | 1 << k))
    moved, bounds, mask = rig.day()
    sp7 = len({s for s, _ in byp[7]})
    out['0xf84f10 all candidates excluded -> exclusion ignored'] = {
        'mask': mask, 'species_bound': bounds[2] if len(bounds) > 2 else None, 'species_with_personality_7': sp7, 'id': list(moved[2]) if moved else None,
        'pass': mask == 0x80 and moved is not None and moved[2][2] == 7 and bounds[2] == sp7}

    rig.island(residents([0, 1, 2, 3, 4, 5]))
    moved, _, _ = rig.day(vacated=1 << 6)
    rig.island(residents([0, 1, 2, 3, 4, 5, 6, 7, 0]))
    moved2, _, _ = rig.day(vacated=1 << 9)
    out['0xf84f10 slot vacated today is not refilled'] = {
        'target_when_slot_6_vacated': moved[1] if moved else None, 'only_free_slot_vacated_calls': list(rig.calls),
        'pass': moved is not None and moved[1] == 7 and moved2 is None and ('plot_path',) not in rig.calls}

    rig.waiting = True
    rig.island(residents([0, 1]))
    moved, bounds, _ = rig.day()
    rig.waiting = False
    out['0xf84f10 waiting NPC takes the plot before the draw'] = {'calls': list(rig.calls), 'draw_bounds': bounds,
                                                                  'pass': moved is None and bounds == [10] and ('waiting_npc', 2) in rig.calls}
    out['meta_unhandled'] = dict(rig.sb.unknown_imports)
    return out


def villager_cases():
    out, unhandled = {}, {}
    for fn in (move_out_cases, pick_cases, move_in_cases):
        part = fn()
        unhandled.update(part.pop('meta_unhandled'))
        out.update(part)
    out['meta_unhandled'] = unhandled
    return out


if __name__ == '__main__':
    res = villager_cases()
    print(json.dumps({k: (v['pass'] if isinstance(v, dict) and 'pass' in v else v) for k, v in res.items()}, indent=1))
