"""Native verification of the weekly special-visitor schedule (GAMEPLAY_SCENARIO 3.3-3.4).

Runs the generator 0xfd8a80 (with its placement helpers 0xfda940, 0xfdad10, 0xfdae20) and the daily validator
0xfd9620 straight from the NSO and compares every output field with a Python model of the documented rules.

Controlled inputs: flags by name (0xf44d90), calendar event days (0xf0790), K.K. concert days (0xf2a30, by
name), the weather-pattern index per date (0x201d90, pattern names in a table shaped like the game's), and the
xorshift draw 0x19aa0e0 (a seeded Python stream; the generator reaches it through the TLS sead::Random).
Native: the save-layout lookups (layout built by 0xf32fa0), the tailor/museum/shop/player-house accessors,
the week/date helpers over nn::time, popcount/bit selection, and both functions' control flow.
Used by tools/gameplay_native.py.
"""
from pathlib import Path
import datetime
import random
import struct
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from nso_sandbox import Sandbox  # noqa: E402

GENERATE, VALIDATE = 0xfd8a80, 0xfd9620
RNG_FN, FLAG_GET = 0x19aa0e0, 0xf44d90
EVENT_DAY, LIVE_DAY, WEATHER_INDEX = 0xf0790, 0xf2a30, 0x201d90
WEATHER_GLOBAL = 0x32d1a38          # GOT entry -> global holding the weather-pattern table object
TIME_GLOBAL = 0x32d1cd0             # GOT entry -> global holding the time manager
NODE_TAILOR, NODE_MUSEUM, NODE_SHOP = 0x1f40c8, 0x20a168, 0x1f3e98
NODE_PLAYER_HOUSE, PLAYER_STRIDE = 0x17cd48, 0xe3b8
RET = 0xd50f0                       # a bare `ret` in .text, used for the pattern-name object's vtable slots
PATTERNS = ['Fine00', 'Fine01', 'Fine02', 'Fine03', 'Fine04', 'Fine05', 'Fine06', 'Cloud00', 'Cloud01', 'Rain00']
FINE_FALLBACK = ('Fine02', 'Fine04', 'Fine06')
WEEKDAY_MAP = {(i + 1) % 7: i for i in range(7)}     # day-of-week index (0 = Sunday) -> offset from Monday


def _packed(t):
    return struct.unpack('<Q', struct.pack('<hbbbbbx', t.year, t.month, t.day, t.hour, t.minute, t.second))[0]


def _unpacked(v):
    y, mo, d = struct.unpack('<hbb', struct.pack('<Q', v)[:4])
    return datetime.date(y, mo, d)


def week_monday(t):
    """0x1fbe10: before 05:00 counts as the previous day; then back to Monday."""
    d = (t - datetime.timedelta(hours=5)).date() if t.hour < 5 else t.date()
    return d - datetime.timedelta(days=d.weekday())


def dow(d):
    return (d.weekday() + 1) % 7


class Draws:
    def __init__(self, seed):
        self.r = random.Random(seed)
        self.used = []

    def __call__(self, sb):
        v = self.r.getrandbits(32)
        self.used.append(v)
        return v


class Env:
    """The controlled world: flags, calendar, concerts, weather, facility states, player house levels."""
    def __init__(self):
        self.flags, self.events, self.lives, self.weather = {}, set(), set(), {}
        self.tailor = self.museum = self.shop = 0
        self.houses = [0] * 8

    def event(self, d):
        return d in self.events

    def live(self, name, d):
        return (name, d) in self.lives

    def blocked(self, d, first=False):
        return self.event(d) or (first and self.live('FirstLive', d)) or self.live('NormalLive', d) or self.live('BirthdayLive', d)


# ---- model of GAMEPLAY_SCENARIO 3.3 / 3.4 ----
class Model:
    def __init__(self, env, sched, draws):
        self.env, self.s, self.draws, self.k = env, sched, draws, 0

    def rand(self):
        v = self.draws[self.k]
        self.k += 1
        return v

    def pick(self, mask):
        bits = [i for i in range(32) if mask >> i & 1]
        return bits[(self.rand() * len(bits)) >> 32]

    def weekday(self, code, monday):
        e, s = self.env, self.s
        mask = 0
        for i in range(1, 6):
            d = monday + datetime.timedelta(days=i - 1)
            if s['codes'][i] == 0 and not e.blocked(d) and s['celeste'] != i:
                mask |= 1 << i
        if not mask:
            return False
        s['codes'][self.pick(mask)] = code
        return True

    def weekend(self, code, d, idx):
        e, s = self.env, self.s
        if not e.blocked(d) and s['codes'][idx] == 0 and s['celeste'] != idx:
            s['codes'][idx] = code
            return True
        return False

    def generate(self, now, last, first):
        e, s = self.env, self.s
        monday = week_monday(now)
        if not first and week_monday(last) == monday:
            return
        sat, sun = monday + datetime.timedelta(days=5), monday + datetime.timedelta(days=6)
        s['codes'], s['copy'], s['wisp'], s['celeste'] = [0] * 7, [0] * 7, -1, -1
        tailor = e.tailor if e.tailor <= 2 else 0
        museum = e.museum if e.museum <= 4 else 0
        if tailor < 2:                                      # Mabel
            self.weekend(5, sat, 6)
            self.weekend(5, sun, 0)
            self.weekday(5, monday)
        self.weekday(3, monday)                             # Saharah
        if tailor >= 2:
            self.weekday(8, monday)                         # Kicks
        carry, pool = 0, 0
        co = s['carry']
        if tailor >= 2:                                     # Label
            pool |= 1 << 2
            carry |= (1 << 2) if co[2] else 0
        if e.flags.get('BuiltTownOffice'):                  # C.J., Flick
            pool |= 0xc0
            carry |= (0x40 if co[6] else 0) | (0x80 if co[7] else 0)
        if museum >= 2:                                     # Gulliver
            pool |= 1 << 1
            carry |= 2 if co[1] else 0
        for which in ('carry', 'pool'):
            while (carry if which == 'carry' else pool):
                b = self.pick(carry if which == 'carry' else pool)
                if not self.weekday(b, monday):
                    break
                carry &= ~(1 << b)
                pool &= ~(1 << b)
        s['carry'] = [1 if pool >> i & 1 else 0 for i in range(14)]
        if museum > 2:                                      # Celeste
            fine0 = other = 0
            for i in range(7):
                d = monday + datetime.timedelta(days=i)
                if e.blocked(d):
                    continue
                name = PATTERNS[e.weather.get(d, 0)]
                if name == 'Fine00':
                    fine0 |= 1 << dow(d)
                elif name in FINE_FALLBACK:
                    other |= 1 << dow(d)
            mask = fine0 or other
            if mask:
                s['celeste'] = self.pick(mask)
        placed = False
        for _ in range(5):                                  # Wisp
            if not self.weekday(4, monday):
                break
            placed = True
        if not placed:
            m = sum(1 << i for i in range(1, 6) if s['codes'][i])
            s['wisp'] = self.pick(m) if m else -1
        self.weekend(4, sat, 6)
        self.weekend(4, sun, 0)
        s['copy'] = [c if c <= 9 else 0 for c in s['codes']]

    def validate(self, now, elapsed, first):
        e, s = self.env, self.s
        if not first and elapsed == 0:
            return
        d = (now - datetime.timedelta(hours=5)).date() if now.hour < 5 else now.date()
        i = dow(d)
        raw = s['codes'][i]
        c = raw if raw <= 9 else 0
        nl, bl = e.live('NormalLive', d), e.live('BirthdayLive', d)
        if c in (1, 4):
            ok = True
        elif c == 3:
            ok = any((h if h <= 8 else 0) >= 2 for h in e.houses)
        elif c == 5:
            ok = bool(e.flags.get('EnableHghStayField')) and (e.tailor if e.tailor <= 2 else 0) != 2 and not bl and not nl
        else:
            ok = not bl and not nl
        if not ok or e.event(d):
            jt = bool(e.flags.get('JohnnyTalkAnyPlayerFlag'))
            sunday_shop = (e.shop if e.shop <= 3 else 0) >= 2 and i == 0
            museum = e.museum if e.museum <= 4 else 0
            if e.blocked(d, first=True):
                new = 0
            elif jt or sunday_shop:
                new = 4 if jt and raw in (2, 3, 5, 6, 7, 8, 9) else 0
            elif museum < 2 or c == 4:
                new = 0
            else:
                new = 1
            s['codes'][i] = new
        for key in ('wisp', 'celeste'):
            if s[key] == i and e.blocked(d, first=True):
                s[key] = -1


# ---- native rig ----
class Rig:
    def __init__(self):
        self.sb = sb = Sandbox()
        self.env = Env()
        root, save = sb.alloc(0x400000), sb.alloc(0x500000)
        sb.call(0xf32fa0, (root,))
        stack = [root]
        while stack:                                       # attach every layout node to one save buffer
            x = stack.pop()
            sb.uc.mem_write(x + 8, struct.pack('<Q', save))
            c = sb.u64(x + 0x18)
            while c:
                stack.append(c)
                c = sb.u64(c + 0x20)
        self.root, self.save = root, save
        sb.stub(0xeecf00, lambda s: root)
        self.off = {n: sb.u64(root + n + 0x10) for n in (NODE_TAILOR, NODE_MUSEUM, NODE_SHOP)}
        self.house = [sb.u64(root + NODE_PLAYER_HOUSE + i * PLAYER_STRIDE + 0x10) for i in range(8)]

        def text(s, p):
            return s.read(p, 64).split(b'\0')[0].decode()
        self.flag_reads = set()

        def flag(s):
            name = text(s, s.u64(s.reg('x0') + 8))
            self.flag_reads.add(name)
            return 1 if self.env.flags.get(name) else 0
        sb.stub(FLAG_GET, flag)
        sb.stub(EVENT_DAY, lambda s: 1 if self.env.event(_unpacked(s.u64(s.reg('x1')))) else 0)
        sb.stub(LIVE_DAY, lambda s: 1 if self.env.live(text(s, s.u64(s.reg('x1') + 8)), _unpacked(s.u64(s.reg('x2')))) else 0)
        sb.stub(WEATHER_INDEX, lambda s: self.env.weather.get(_unpacked(s.u64(s.reg('x1'))), 0))
        # pattern table: obj+0x100 count, obj+0x108 -> element pointers; element+0x30 is the name object
        vt, obj, arr = sb.alloc(0x100), sb.alloc(0x200), sb.alloc(8 * len(PATTERNS))
        sb.uc.mem_write(vt + 0x18, struct.pack('<Q', RET))
        sb.uc.mem_write(vt + 0xf0, struct.pack('<Q', RET))    # "get name object" returns the element's own +0x30
        for i, name in enumerate(PATTERNS):
            el, txt = sb.alloc(0x40), sb.alloc(16)
            sb.uc.mem_write(txt, name.encode() + b'\0')
            sb.uc.mem_write(el + 0x30, struct.pack('<QQ', vt, txt))
            sb.uc.mem_write(arr + 8 * i, struct.pack('<Q', el))
        sb.uc.mem_write(obj + 0x100, struct.pack('<I', len(PATTERNS)))
        sb.uc.mem_write(obj + 0x108, struct.pack('<Q', arr))
        sb.uc.mem_write(sb.u64(WEATHER_GLOBAL), struct.pack('<Q', obj))
        mgr = sb.alloc(0x5000)
        sb.uc.mem_write(sb.u64(TIME_GLOBAL), struct.pack('<Q', mgr))
        self.sched, self.info = sb.alloc(0x78), sb.alloc(0x20)

    def _load(self, s):
        e, sb = self.env, self.sb
        sb.uc.mem_write(self.save + self.off[NODE_TAILOR], struct.pack('<I', e.tailor))
        sb.uc.mem_write(self.save + self.off[NODE_MUSEUM], struct.pack('<I', e.museum))
        sb.uc.mem_write(self.save + self.off[NODE_SHOP], struct.pack('<I', e.shop))
        for off, h in zip(self.house, e.houses):
            sb.uc.mem_write(self.save + off, struct.pack('<I', h))
        blob = struct.pack('<7I12x', *s['codes']) + b'\0' * 0x1c + struct.pack('<7I', *s['copy']) \
            + bytes(s['carry']) + b'\0\0' + struct.pack('<ii', s['wisp'], s['celeste'])
        assert len(blob) == 0x78
        sb.uc.mem_write(self.sched, blob)

    def _read(self):
        b = self.sb.read(self.sched, 0x78)
        return {'codes': list(struct.unpack_from('<7I', b, 0)), 'copy': list(struct.unpack_from('<7I', b, 0x44)),
                'carry': list(b[0x60:0x6e]), 'wisp': struct.unpack_from('<i', b, 0x70)[0],
                'celeste': struct.unpack_from('<i', b, 0x74)[0]}

    def run(self, va, s, now, last, elapsed, first, draws):
        self._load(s)
        self.sb.uc.mem_write(self.info, struct.pack('<qQQB7x', elapsed, _packed(now), _packed(last) if last else 0, first))
        self.sb.stub(RNG_FN, draws)
        self.sb.call(va, (self.sched, self.info))
        return self._read()


def random_world(rng, env, monday):
    env.flags = {'BuiltTownOffice': rng.random() < 0.6, 'EnableHghStayField': rng.random() < 0.6,
                 'JohnnyTalkAnyPlayerFlag': rng.random() < 0.5}
    env.tailor = rng.choice([0, 1, 2, 2, 2, 3])          # 3 is out of range: the accessor clamps it to 0
    env.museum = rng.choice([0, 1, 2, 3, 3, 4, 5])
    env.shop = rng.choice([0, 1, 2, 3, 4])
    env.houses = [rng.choice([0, 0, 1, 1, 2, 5, 9]) for _ in range(8)]
    days = [monday + datetime.timedelta(days=i) for i in range(7)]
    env.events = {d for d in days if rng.random() < 0.12}
    env.lives = set()
    for d in days:
        for name, p in (('NormalLive', 0.1), ('BirthdayLive', 0.06), ('FirstLive', 0.04)):
            if rng.random() < p:
                env.lives.add((name, d))
    env.weather = {d: rng.randrange(len(PATTERNS)) for d in days}


def empty_schedule(rng=None):
    carry = [rng.randrange(2) if rng and i in (1, 2, 6, 7) else 0 for i in range(14)]
    return {'codes': [0] * 7, 'copy': [0] * 7, 'carry': carry, 'wisp': -1, 'celeste': -1}


def generator_case(weeks=1500):
    rig = Rig()
    mism, stats = [], {'weeks': 0, 'carry_used': 0, 'celeste_set': 0, 'wisp_extra': 0, 'skipped_same_week': 0,
                       'pool_carried_over': 0, 'mabel_weeks': 0, 'kicks_weeks': 0}
    inv = dict.fromkeys(('weekend_only_mabel_or_wisp', 'code_9_never_written', 'once_per_week_except_mabel_wisp',
                         'copy_equals_codes'), True)
    full_unlock = []
    for seed in range(weeks):
        rng = random.Random(seed)
        now = datetime.datetime(2020, 3, 2) + datetime.timedelta(days=rng.randrange(700), hours=rng.randrange(24))
        monday = week_monday(now)
        random_world(rng, rig.env, monday)
        sched = empty_schedule(rng)
        first = rng.random() < 0.2
        same_week = not first and rng.random() < 0.1
        last = now - datetime.timedelta(days=rng.randrange(0, 3) if same_week else rng.randrange(7, 30))
        if same_week and week_monday(last) != monday:
            last = datetime.datetime.combine(monday, datetime.time(6))
        if same_week:
            sched['codes'] = [rng.randrange(10) for _ in range(7)]
        draws = Draws(seed)
        native = rig.run(GENERATE, dict(sched, carry=list(sched['carry'])), now, last, 0, first, draws)
        model = dict(sched, codes=list(sched['codes']), copy=list(sched['copy']), carry=list(sched['carry']))
        m = Model(rig.env, model, draws.used + [0] * 4)
        m.generate(now, last, first)
        stats['weeks'] += 1
        stats['skipped_same_week'] += same_week
        stats['carry_used'] += any(sched['carry'])
        stats['celeste_set'] += native['celeste'] >= 0
        stats['wisp_extra'] += native['wisp'] >= 0
        stats['pool_carried_over'] += any(native['carry'])
        stats['mabel_weeks'] += 5 in native['codes']
        stats['kicks_weeks'] += 8 in native['codes']
        regenerated = first or week_monday(last) != monday
        if regenerated:
            c = native['codes']
            inv['weekend_only_mabel_or_wisp'] &= c[0] in (0, 4, 5) and c[6] in (0, 4, 5)
            inv['code_9_never_written'] &= 9 not in c
            inv['once_per_week_except_mabel_wisp'] &= all(c.count(k) <= 1 for k in (1, 2, 3, 6, 7, 8))
            inv['copy_equals_codes'] &= native['copy'] == c
            if rig.env.tailor == 2 and 2 <= rig.env.museum <= 4 and rig.env.flags['BuiltTownOffice'] and not any(
                    rig.env.blocked(monday + datetime.timedelta(days=i)) for i in range(5)):
                full_unlock.append(sum(native['carry']))
        if native != model or m.k != len(draws.used):
            mism.append({'seed': seed, 'native': native, 'model': model, 'draws_native': len(draws.used), 'draws_model': m.k})
    return {'0xfd8a80 weekly visitor generator': {
        **stats, 'flags_read': sorted(rig.flag_reads), 'invariants': inv,
        'all_unlocked_weeks_without_blocked_weekdays': {'weeks': len(full_unlock),
                                                         'carried_over_count': sorted(set(full_unlock))},
        'mismatches': len(mism), 'first_mismatches': mism[:3],
        'pass': not mism and all(inv.values()) and set(full_unlock) == {1}}}, rig.sb.unknown_imports


def validator_case(days=3000):
    rig = Rig()
    mism, outcomes = [], {}
    for seed in range(days):
        rng = random.Random(10_000 + seed)
        now = datetime.datetime(2020, 3, 2) + datetime.timedelta(days=rng.randrange(700), hours=rng.randrange(24))
        random_world(rng, rig.env, week_monday(now))
        today = (now - datetime.timedelta(hours=5)).date() if now.hour < 5 else now.date()
        now = datetime.datetime.combine(today, datetime.time(5))   # the driver 0xf53a70 normalises +8 with 0x1fbc00
        for name, p in (('FirstLive', 0.08), ('NormalLive', 0.1), ('BirthdayLive', 0.08)):
            if rng.random() < p:
                rig.env.lives.add((name, today))
        sched = empty_schedule(rng)
        sched['codes'] = [rng.choice(range(12)) for _ in range(7)]
        sched['wisp'] = rng.choice([-1, dow(today), rng.randrange(7)])
        sched['celeste'] = rng.choice([-1, dow(today), rng.randrange(7)])
        first = rng.random() < 0.1
        elapsed = 0 if rng.random() < 0.1 else rng.randrange(1, 4)
        draws = Draws(seed)
        native = rig.run(VALIDATE, sched, now, now - datetime.timedelta(days=1), elapsed, first, draws)
        model = dict(sched, codes=list(sched['codes']), carry=list(sched['carry']))
        Model(rig.env, model, []).validate(now, elapsed, first)
        i = dow(today)
        key = f"{sched['codes'][i]}->{native['codes'][i]}"
        outcomes[key] = outcomes.get(key, 0) + 1
        if native != model or draws.used:
            mism.append({'seed': seed, 'today': str(today), 'native': native, 'model': model})
    return {'0xfd9620 daily visitor validator': {
        'days': days, 'today_code_transitions': dict(sorted(outcomes.items())), 'flags_read': sorted(rig.flag_reads),
        'mismatches': len(mism), 'first_mismatches': mism[:3], 'pass': not mism}}, rig.sb.unknown_imports


def wrapper_case(_n=0):
    """0xfd8920: K.K. first-concert enable, then generator and validator, then RctInTent and JohnnyRequirePartsNum."""
    sb = Sandbox()
    flags, sets, calls = {}, [], []

    def name(s):
        return s.read(s.u64(s.reg('x0') + 8), 64).split(b'\0')[0].decode()
    sb.stub(FLAG_GET, lambda s: 1 if flags.get(name(s)) else 0)
    sb.stub(0xf44e70, lambda s: sets.append((name(s), s.reg('x1') & 0xffffffff)))
    sb.stub(GENERATE, lambda s: calls.append('0xfd8a80'))
    sb.stub(VALIDATE, lambda s: calls.append('0xfd9620'))
    hour = [0]
    sb.stub(0x1fcac0, lambda s: _packed(datetime.datetime(2020, 4, 1, hour[0])))
    info = sb.alloc(0x20)
    mism, n = [], 0
    for clear in (0, 1):
        for already in (0, 1):
            for elapsed in (0, 1, 3):
                for first in (0, 1):
                    for h in range(24):
                        flags.clear()
                        flags.update({'IslandEvaluationClearTkkLive': clear, 'TkkFirstLive': already})
                        sets.clear(); calls.clear()
                        hour[0] = h
                        sb.uc.mem_write(info, struct.pack('<qQQB7x', elapsed, 0, 0, first))
                        sb.call(0xfd8920, (sb.alloc(0x78), info))
                        want = ([('TkkFirstLiveEnable', 1)] if elapsed > 0 and clear and not already else []) \
                            + [('RctInTent', 0 if 5 <= h <= 19 else 1)] \
                            + ([('JohnnyRequirePartsNum', 5)] if first or elapsed else [])
                        n += 1
                        if sets != want or calls != ['0xfd8a80', '0xfd9620']:
                            mism.append({'clear': clear, 'TkkFirstLive': already, 'elapsed': elapsed, 'first': first,
                                         'hour': h, 'native': sets, 'calls': calls, 'model': want})
    return {'0xfd8920 visitor/K.K. day-change wrapper': {
        'samples': n, 'mismatches': len(mism), 'first_mismatches': mism[:3], 'pass': not mism}}, sb.unknown_imports


def visitor_cases(weeks=1500, days=3000):
    out, unhandled = {}, {}
    for fn, n in ((generator_case, weeks), (validator_case, days), (wrapper_case, 0)):
        res, unk = fn(n)
        out.update(res)
        unhandled.update(unk)
    out['meta_unhandled'] = unhandled
    return out


if __name__ == '__main__':
    import json
    print(json.dumps(visitor_cases(200, 400), indent=1)[:6000])
