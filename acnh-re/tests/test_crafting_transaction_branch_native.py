import json
from pathlib import Path
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / 'tools' / 'crafting_transaction_branch_native.py'
RESULT = (ROOT / 'output' / 'gameplay' / 'crafting_transaction_followup'
          / 'crafting_transaction_branch_native.json')
AVAILABLE = (
    Path('/workspace/acnh-re/output/index.sqlite').is_file()
    and Path('/workspace/acnh-re/output/tables_resolved/RecipeCraftParam.json').is_file()
    and (ROOT / 'inputs' / 'additional_exefs' / 'main').is_file()
)


@unittest.skipUnless(AVAILABLE, 'shared ACNH ELF/index/tables are not present')
class CraftingTransactionBranchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        subprocess.run([sys.executable, str(TOOL)], cwd=ROOT.parent, check=True)
        cls.report = json.loads(RESULT.read_text())

    def test_full_pocket_captures_material_and_routes_result_separately(self):
        case = self.report['cases']['full_pocket_marker_zero']
        self.assertEqual(case['native_return'], 1)
        self.assertIsNone(case['native_error'])
        self.assertEqual(case['precheck_descriptor']['precheck_output_item_id'], 2213)
        self.assertEqual(case['pocket_restore_descriptor']['descriptor_item_id'], 2213)
        self.assertEqual(case['result_award_descriptor']['descriptor_item_id'], 975)
        self.assertEqual(case['native_entry_counts']['0xee0ed0'], 1)
        self.assertEqual(case['native_entry_counts']['0xefbd30'], 1)
        self.assertEqual(case['native_entry_counts']['0xf99270'], 1)
        self.assertEqual(case['result_route_reached'], {
            '0xefab90': True, '0xefac20': True, '0xf987c0': False})

    def test_per_material_marker_and_one_free_slot_control(self):
        marker_zero = self.report['cases']['full_pocket_marker_zero']
        marker_one = self.report['cases']['full_pocket_marker_one']
        free_slot = self.report['cases']['one_free_slot_marker_zero']
        self.assertEqual(marker_zero['material_mutator_call_counts'], {'0xee1060': 6})
        self.assertEqual(marker_one['material_mutator_call_counts'], {
            '0xee1060': 5, '0xeff060': 1})
        self.assertEqual(marker_one['material_mutator_calls'][0]['item_id'], 2213)
        self.assertEqual(free_slot['native_entry_counts'].get('0xee0ed0', 0), 0)
        self.assertEqual(free_slot['native_entry_counts'].get('0xefbd30', 0), 0)
        self.assertEqual(free_slot['native_entry_counts'].get('0xf99270', 0), 0)
        self.assertEqual(free_slot['dirty_slot_bytes_after'], [0] * 20)

    def test_compaction_sets_per_slot_dirty_bytes_but_save_edge_stays_open(self):
        case = self.report['cases']['full_pocket_marker_zero']
        self.assertEqual(case['native_f98650_calls'], 24)
        self.assertEqual(case['native_f98650_slot_indices'], list(range(20)) + [0, 1, 2, 3])
        self.assertEqual(case['dirty_slot_bytes_before'], [0] * 20)
        self.assertEqual(case['dirty_slot_bytes_after'], [255] * 20)

        audit = self.report['dirty_marker_save_audit']
        self.assertTrue(audit['saveproc_worker_callback_factory_unresolved'])
        self.assertEqual(audit['direct_dirty_helper_calls_from_saveproc_functions'], [])
        self.assertTrue(all(not row['direct_plus_0x15c_lines']
                            for row in audit['saveproc_static_functions_checked']))
        self.assertIn('UNRESOLVED', audit['serializer_or_flush_relation'])


if __name__ == '__main__':
    unittest.main()
