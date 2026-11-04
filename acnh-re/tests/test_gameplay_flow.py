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
        driver = [r['function'] for r in refs['day_change_driver_pipeline']]
        for fn in ('0xf545f0', '0xf8b460', '0xfd9d10', '0xd21110'):
            self.assertIn(fn, driver)

    def test_native_only_progress_flags_have_no_eventflow_writer(self):
        for key in ('cLand:MuseumBuilt', 'cLand:MarketBuilt', 'cLand:Museum2Built', 'cLand:BuiltTownOffice',
                    'cLand:CampSiteBuilt', 'cLand:TkkFirstLive', 'cLand:TkkFirstLiveEnable', 'cLand:ImmQ_A_Complete'):
            self.assertEqual(self.flags[key]['eventflow_writers'], [], key)


if __name__ == '__main__':
    unittest.main()
