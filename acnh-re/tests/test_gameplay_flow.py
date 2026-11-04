"""Check the gameplay-flow evidence against decoded EventFlow (needs the five baseline ZIPs extracted).

Set ACNH_RE_OUTPUT to use an output folder outside the repo (for example an extraction elsewhere).
"""
import json
import os
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parent.parent
OUT = Path(os.environ.get('ACNH_RE_OUTPUT', ROOT/'output'))
sys.path.insert(0, str(ROOT/'tools'))
import gameplay_flow as gf  # noqa: E402

HAVE_EVENTFLOW = (OUT/'manifest.json').exists() and (OUT/'decoded').is_dir()


def flowchart(name):
    return gf.load(gf.flow_paths(OUT)[name])['data']['flowcharts'][0]


def set_results(fc, entry):
    """SetSubflowResult values reachable from an entry point, as (SetIndex, ResultValue) pairs."""
    seen, stack, found = set(), [fc['entry_points'][entry]['main_event']], set()
    while stack:
        j = stack.pop()
        if j is None or j in seen:
            continue
        seen.add(j)
        e = fc['events'][j]
        if e['type'] == 'action':
            a = fc['actors'][e['actor']]['actions'][e['action']]
            p = e.get('params') or {}
            if a.endswith('SetSubflowResult'):
                found.add((p['SetIndex'], p['ResultValue']))
            stack.append(e.get('next'))
        elif e['type'] == 'switch':
            stack.extend(c['event'] for c in e.get('cases') or [])
        elif e['type'] == 'fork':
            stack.extend(e.get('forks') or [])
            stack.append(e.get('join'))
        else:
            stack.append(e.get('next'))
    return found


def query_params(fc, query):
    out = []
    for e in fc['events']:
        if e['type'] == 'switch' and fc['actors'][e['actor']]['queries'][e['query']] == query:
            out.append(e.get('params') or {})
    return out


@unittest.skipUnless(HAVE_EVENTFLOW, 'extract the baseline ZIPs into output/ first (see docs/WORKFLOW.md)')
class GameplayFlowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.flows, cls.flags, cls.defs, cls.truncated = gf.build(OUT)

    def test_all_flowcharts_and_flag_tables_are_indexed(self):
        self.assertEqual(len(self.flows), 456)
        self.assertEqual(len(self.defs), 1555)
        self.assertEqual([k for k, f in self.flags.items() if not f['definition']], [])

    def test_bool_case_rule_holds_for_nearly_every_guarded_write(self):
        tally = gf.bool_self_check(self.flags)
        consistent = tally.get('write_on_guarded_by_off', 0) + tally.get('write_off_guarded_by_on', 0)
        inconsistent = tally.get('write_on_guarded_by_on', 0) + tally.get('write_off_guarded_by_off', 0)
        self.assertGreater(consistent, 400)
        self.assertGreater(consistent / (consistent + inconsistent), 0.95)

    def test_island_rating_thresholds(self):
        fc = flowchart('System_IslandEvaluationCheck')
        natural = [p['BorderValue'] for p in query_params(fc, 'EventFlowQueryVillageScoreCheckNatural') if 'BorderValue' in p]
        life = [p['BorderValue'] for p in query_params(fc, 'EventFlowQueryVillageScoreCheckLife') if 'BorderValue' in p]
        self.assertEqual(sorted(set(natural)), [200.0, 270.0, 350.0, 450.0])
        self.assertEqual(sorted(set(life)), [80.0, 160.0, 400.0, 650.0])
        houses = {p['Num'] for p in query_params(fc, 'EventFlowQueryNpcHouseNum')}
        self.assertEqual(houses, {7, 8})

    def test_shop_opening_day_announces_the_three_plots(self):
        fc = flowchart('Demo_PublicAnnouncement_21_CmnEvChk')
        self.assertIn((13, 1), set_results(fc, 'ChkMarket'))
        cmn = flowchart('Demo_PublicAnnouncement_00_Cmn')
        targets = {(e.get('flowchart'), e.get('entry_point')) for e in cmn['events'] if e['type'] == 'subflow'}
        self.assertIn(('Demo_PublicAnnouncement_03_Rco_Once', 'TownNews_Rco_HouseBuild'), targets)

    def test_three_star_branch_reaches_kk(self):
        sza = flowchart('SNPC_sza_50_IslandEvaluation')
        self.assertIn('ClearTkkFirstLiveScore', sza['entry_points'])
        writers = {w['flow'] for w in self.flags['cLand:IslandEvaluationClearTkkLive']['eventflow_writers']}
        self.assertEqual(writers, {'SNPC_sza_50_IslandEvaluation'})
        stages = {(e.get('params') or {}).get('TargetStage') for e in flowchart('Demo_PublicAnnouncement')['events']}
        self.assertIn('cMainFieldFirstLive', stages)

    @unittest.skipUnless((OUT/'index.sqlite').exists() and (OUT/'index.sqlite').stat().st_size > 0, 'index.sqlite not extracted')
    def test_native_flag_strings_lead_to_day_change_processors(self):
        refs = gf.native_refs(OUT, self.flags)
        self.assertEqual(refs['counts']['flags_without_eventflow_writer'], 693)
        order = refs['day_change_callees_in_order']
        for fn in ('0xfc4560', '0xf77050', '0xf26330', '0xfd8920', '0x10c26e0'):
            self.assertIn(fn, order)
        self.assertLess(order.index('0xfc4560'), order.index('0xf77050'))
        expect = {'cLand:MuseumBuilt': '0xf77050', 'cLand:Museum2Built': '0xf77050', 'cLand:TailorBuilt': '0xfcc300',
                  'cLand:CampSiteBuilt': '0xf26330', 'cLand:TkkFirstLiveEnable': '0xfd8920', 'cLand:BuiltTownOffice': '0x10c2ad0',
                  'cLand:MarketOpen1stDay1': '0xfc4560'}
        for key, fn in expect.items():
            self.assertIn(fn, refs['flags'][key]['referencing_functions'], key)
        self.assertEqual([refs['visitor_codes'][str(i)] for i in range(10)],
                         ['non', 'gul', 'hgc', 'cml', 'gst', 'hgh', 'bey', 'chy', 'skk', 'ows'])
        for fn in ('0xf8dd70', '0xfd8a80', '0xfd9620', '0xfda940'):
            self.assertIn(fn, refs['all_readings'])
        driver = [r['function'] for r in refs['day_change_driver_pipeline']]
        for fn in ('0xf545f0', '0xf8b460', '0xfd9d10', '0xd21110'):
            self.assertIn(fn, driver)

    def test_weekly_schedule_writer_is_reached_from_the_dispatcher(self):
        import sqlite3
        db = sqlite3.connect(OUT/'index.sqlite')

        def callees(f):
            return {t for (t,) in db.execute('SELECT target_va FROM direct_calls WHERE owner_va=?', (f,))}
        self.assertIn(0xfd8920, callees(gf.DAY_CHANGE_DISPATCHER))
        self.assertTrue({0xfd8a80, 0xfd9620} <= callees(0xfd8920))
        self.assertTrue({0xfda940, 0xfdad10, 0xfdae20, 0x19aa0e0, 0x198b630} <= callees(0xfd8a80))
        self.assertIn(0xfda740, callees(gf.DAY_CHANGE_DRIVER))
        db.close()

    def test_villager_move_chain_is_reached_from_the_dispatcher(self):
        import sqlite3
        db = sqlite3.connect(OUT/'index.sqlite')

        def callees(f):
            return {t for (t,) in db.execute('SELECT target_va FROM direct_calls WHERE owner_va=?', (f,))}
        self.assertIn(0xf84320, callees(gf.DAY_CHANGE_DISPATCHER))
        self.assertTrue({0xf847f0, 0xf84f10} <= callees(0xf84320))
        self.assertTrue({0xf855c0, 0xf53420, 0xf87670} <= callees(0xf847f0))
        self.assertTrue({0xd34a20, 0xf53420} <= callees(0xf87670))
        self.assertTrue({0xf8d640, 0xf8d860, 0xf8cea0, 0xf53420} <= callees(0xf84f10))
        strings = {t for (t,) in db.execute('SELECT text FROM string_refs WHERE function_va=?', (0xf84f10,))}
        self.assertIn('NNpcContractProbablityAddPoint', strings)
        db.close()

    def test_island_score_chain_and_save_writer(self):
        import sqlite3
        db = sqlite3.connect(OUT/'index.sqlite')

        def callees(f):
            return {t for (t,) in db.execute('SELECT target_va FROM direct_calls WHERE owner_va=?', (f,))}
        self.assertTrue({0x15c5120, 0x15c5420} <= callees(0x15c61c0))
        self.assertTrue({0x15c4240, 0x15c48b0} <= callees(0x15c5120))
        self.assertIn(0x15c4590, callees(0x15c4240))
        self.assertTrue({0x15c58f0, 0x15c59d0} <= callees(0x15c61f0))
        self.assertTrue({0x11074d0, 0x11076a0, 0x1106cb0, 0x1106df0} <= callees(0x15c5ef0))
        # the actor calls are inside a span index.sqlite has no function for; pc is still recorded
        calls = dict(db.execute('SELECT pc, target_va FROM direct_calls WHERE pc IN (?, ?)', (0xd4f34, 0xd50d4)).fetchall())
        self.assertEqual(calls, {0xd4f34: 0x15c68c0, 0xd50d4: 0x15c61f0})
        db.close()
        for va in ('0x15c4590', '0x15c61f0', '0x15c68c0', '0x3e4510', '0xf8f190', '0xf7d4c0', '0xfc1b80', '0xbdfd40',
                   '0xf8b460', '0xf6130', '0x4ae640', '0xd21110'):
            self.assertIn(va, gf.PSEUDOCODE_READINGS)
        self.assertEqual(set(gf.ISLAND_SCORE['categories']), {str(i) for i in range(11)})

    def test_native_only_progress_flags_have_no_eventflow_writer(self):
        for key in ('cLand:MuseumBuilt', 'cLand:MarketBuilt', 'cLand:Museum2Built', 'cLand:BuiltTownOffice',
                    'cLand:CampSiteBuilt', 'cLand:TkkFirstLive', 'cLand:TkkFirstLiveEnable', 'cLand:ImmQ_A_Complete'):
            self.assertEqual(self.flags[key]['eventflow_writers'], [], key)


class SaveLayoutTests(unittest.TestCase):
    def test_committed_layout_matches_pseudocode_sizes(self):
        doc = json.loads((ROOT/'output'/'gameplay'/'save_layout.json').read_text())
        by = {m['node']: m for m in doc['members']}
        self.assertEqual(by['0x0']['size'], '0x4fa0d8')
        self.assertEqual((by['0xa8']['size'], by['0x20a210']['size'], by['0x24fdb0']['size']), ('0x1d6d48', '0x78', '0x250'))
        self.assertEqual(doc['meta']['unhandled_imports'], {})


class NativeVerificationTests(unittest.TestCase):
    def test_committed_native_cases_pass(self):
        doc = json.loads((ROOT/'output'/'gameplay'/'gameplay_native.json').read_text())
        self.assertTrue(doc['all_pass'])
        self.assertEqual(doc['meta']['unhandled_imports'], {})
        self.assertGreaterEqual(doc['cases']['0xfc6d00 turnip prices']['weeks'], 3000)


NSO = Path(os.environ.get('ACNH_RE_NSO', ROOT/'inputs'/'additional_exefs'/'main'))


@unittest.skipUnless(NSO.exists(), 'put the original ExeFS main (NSO0) in inputs/additional_exefs/main (see docs/HANDOFF.md)')
class VisitorScheduleNsoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import re_helpers
        cls.read = staticmethod(lambda addr, n, segs=re_helpers.nso_segments(NSO): re_helpers._read(segs, addr, n))

    def cstr(self, addr):
        return self.read(addr, 64).split(b'\0', 1)[0].decode()

    def test_code_labels_and_celeste_weather_patterns(self):
        self.assertEqual(self.cstr(0x2947a90), 'non,gul,hgc,cml,gstA,hgh,bey,chy,skk,ows')
        self.assertEqual([self.cstr(a) for a in (0x29c0d53, 0x29333a7, 0x297fc20, 0x29a0ae8)],
                         ['Fine00', 'Fine02', 'Fine04', 'Fine06'])

    def test_generator_stores_celeste_and_wisp_days(self):
        word = lambda a: int.from_bytes(self.read(a, 4), 'little')  # noqa: E731
        self.assertEqual(word(0xfd94b4), 0xb9007660)  # str w0, [x19, #0x74] after the n-th-bit pick
        self.assertEqual(word(0xfd9584), 0xb9007260)  # str w0, [x19, #0x70]

    def test_move_out_and_move_in_roll_formulas(self):
        word = lambda a: int.from_bytes(self.read(a, 4), 'little')  # noqa: E731
        self.assertEqual(word(0xf84eb0), 0x0b000809)  # add w9, w0, w0, lsl #2   (5 * settled)
        self.assertEqual(word(0xf84eb4), 0x0b080134)  # add w20, w9, w8          (+ days since talk)
        self.assertEqual(word(0xf852b4), 0x0b080908)  # add w8, w8, w8, lsl #2   (move-in points * 5)
        self.assertEqual(word(0xf852b8), 0x531f7914)  # lsl w20, w8, #1          (* 2 = * 10 percent)

    def test_island_score_weights_and_save_fields(self):
        word = lambda a: int.from_bytes(self.read(a, 4), 'little')  # noqa: E731
        self.assertEqual(word(0x15c6920), 0x1e2a1001)  # fmov s1, #0.25  (category 0 -> Natural)
        self.assertEqual(word(0x15c6950), 0x1e221001)  # fmov s1, #4.0   (category 2 -> Life)
        self.assertEqual(word(0x29d6328), 0x3e4ccccd)  # 0.2f            (category 4 -> Life)
        self.assertEqual(word(0x15c6998), 0x1e217800)  # fminnm s0, s0, s1 with 190.0f below
        self.assertEqual(word(0x29d5f28), 0x433e0000)  # 190.0f          (category 5 cap)
        self.assertEqual(word(0x15c673c), 0x0aa87d08)  # bic w8, w8, w8, asr #31  (max(bridges - 1, 0))
        self.assertEqual(word(0x15c6754), 0x1e25d000)  # fmov s0, #15.0
        self.assertEqual(word(0x15c4e38), 0x1e2c1001)  # fmov s1, #0.5   (duplicate penalty)
        self.assertEqual(word(0x15c4e40), 0x1e2d1001)  # fmov s1, #0.75
        self.assertEqual(word(0x15c4790), 0x5289c3e8)  # mov w8, #0x4e1f (price > 19999)
        self.assertEqual(word(0x15c47a4), 0x711f401f)  # cmp w0, #0x7d0  (price >= 2000)
        self.assertEqual([word(a) for a in (0x15c68e0, 0x15c68e8, 0x15c68f0, 0x15c68f8)],
                         [0xb9024268, 0xb9024668, 0xb9024a68, 0xb9024e68])  # str w8, [x19, #0x240/#0x244/#0x248/#0x24c]
        self.assertEqual([word(a) for a in (0x29d6464, 0x29d613c)], [0x43100000, 0x43000000])  # 144.0f, 128.0f

    def test_kk_live_date_rules(self):
        lst = lambda a: self.read(a, 256).split(b'\0', 1)[0].decode().split(',')  # noqa: E731
        word = lambda a: int.from_bytes(self.read(a, 4), 'little')  # noqa: E731
        self.assertEqual(lst(0x29b9f72)[:5], ['Global', 'Region', 'Other', 'Totakeke', 'None'])
        self.assertEqual(lst(0x298d19c)[:3], ['Before', 'Skip', 'Same'])
        self.assertEqual((word(0xf03b8), word(0xf03bc)), (0x321f07e9, 0x4b080121))  # mov w9, #6; sub w1, w9, w8 (Saturday)
        self.assertEqual(word(0xf92198), 0x528002a1)  # mov w1, #0x15 (birthday scan starts 21 days ahead)

    def test_turnip_and_shop_stock(self):
        import struct
        f = lambda a: round(struct.unpack('<f', self.read(a, 4))[0], 5)  # noqa: E731
        self.assertEqual([f(a) for a in (0x29d5e8c, 0x29d5d94, 0x29d5e28, 0x29d6248, 0x29d5dbc, 0x29d5f24, 0x29d5c84)],
                         [0.9, 1.4, 0.6, -0.2, 0.8, -0.05, -0.03])
        frm = self.read(0x29b535d, 4096).split(b'\0', 1)[0].decode().split(',')
        self.assertEqual([frm[i] for i in (1, 2, 3, 4, 48, 49, 50, 51, 52)],
                         ['ShopDefault', 'ShopMiscGoods', 'ShopLargeGoods', 'ShopHighClass', 'RugS', 'RugM', 'RugL', 'LaurentWallFloor', 'ShoesBagShop'])

    def test_save_layout_emulation(self):
        try:
            import unicorn  # noqa: F401
        except ImportError:
            self.skipTest('pip install unicorn')
        import save_layout_native
        rows, unknown = save_layout_native.build(1)
        by = {r['node']: r for r in rows}
        self.assertEqual(unknown, {})
        self.assertEqual((by['0x0']['size'], by['0x20a210']['data'], by['0x24fdb0']['data']), ('0x4fa0d8', '0x414e84', '0x4f8b34'))

    def test_native_cases_rerun(self):
        try:
            import unicorn  # noqa: F401
        except ImportError:
            self.skipTest('pip install unicorn')
        import gameplay_native
        res = gameplay_native.verify(weeks=200)
        self.assertTrue(res['all_pass'], {k: v['pass'] for k, v in res['cases'].items()})

    def test_island_score_enum_lists(self):
        lst = lambda a: self.read(a, 4096).split(b'\0', 1)[0].decode().split(',')  # noqa: E731
        self.assertEqual(lst(0x2955748)[26:28], ['Bridge', 'Slope'])
        kinds = lst(0x29336c2)
        self.assertEqual([kinds[i] for i in (0x2e, 0x2f, 0x3f, 0x42)], ['Fruit', 'Mushroom', 'StarPiece', 'ShellDrift'])
        fg = lst(0x293f104)
        self.assertEqual((fg[5], fg[10], fg[16], fg[18], fg[26], fg[27], fg[28], fg[29]),
                         ('TreePalm', 'WeedSpr', 'WeedWin1', 'FlwCosmos', 'FlwSuzuran', 'Hole', 'Fence', 'Stone'))
        self.assertEqual(lst(0x296542f)[:3], ['None', 'DirectionOutdoor', 'DirectionIndoor'])
        self.assertEqual(lst(0x29568b7)[3:6], ['3_0x1_0', '3_0x2_0', '3_0x3_0'])


if __name__ == '__main__':
    unittest.main()
