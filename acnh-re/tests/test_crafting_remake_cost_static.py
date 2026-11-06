import json
from pathlib import Path
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / 'tools' / 'crafting_remake_cost_static.py'
NATIVE_RUNNER = ROOT / 'tools' / 'crafting_remake_inventory_native.py'
RESULT = ROOT / 'output' / 'gameplay' / 'crafting_transaction_remainder' / 'crafting_remake_cost_static.json'
NATIVE_RESULT = ROOT / 'output' / 'gameplay' / 'crafting_transaction_remainder' / 'crafting_remake_inventory_native.json'


class CraftingRemakeCostStaticTests(unittest.TestCase):
    def test_native_table_to_inventory_quantity_chain(self):
        proc = subprocess.run([sys.executable, str(RUNNER)], cwd=ROOT,
                              check=True, capture_output=True, text=True)
        self.assertIn('"result": "pass"', proc.stdout)
        report = json.loads(RESULT.read_text())
        self.assertEqual(report['table_case']['ItemParam.RemakeID'], 168)
        self.assertEqual(report['table_case']['ItemRemake.RemakeKitNum'], 2)
        self.assertEqual(report['table_case']['values_over_255'], 0)
        self.assertEqual(report['claims']['normal_remake_cost_row_to_inventory_quantity'],
                         'PROVEN_STATIC')
        self.assertEqual(report['claims']['tutorial_displaytype_to_flag_bit4_mapping'],
                         'UNRESOLVED')
        self.assertEqual(report['rollback_boundary']['kit_update_call_sites_in_0x335d10'], 1)
        self.assertFalse(report['rollback_boundary']['return_value_checked_immediately_after_call'])
        self.assertEqual(report['rollback_boundary']['explicit_kit_refund_calls_in_handler'], 0)
        self.assertIn('#201 IF SubflowResultChoice2', report['transaction_order']['eventflow_tree'])
        self.assertEqual(report['transaction_order']['native_handler']['ordered_calls'][0]['target'],
                         '0xefbdf0')

    def test_native_helper_partial_and_insufficient_fixture_paths(self):
        proc = subprocess.run([sys.executable, str(NATIVE_RUNNER)], cwd=ROOT,
                              check=True, capture_output=True, text=True)
        self.assertIn('"result": "pass"', proc.stdout)
        report = json.loads(NATIVE_RESULT.read_text())
        sufficient = report['cases']['sufficient_stack']
        self.assertEqual(sufficient['freeparam_before'], 49)
        self.assertEqual(sufficient['freeparam_after'], 47)
        insufficient = report['cases']['insufficient_stack']
        self.assertEqual(insufficient['native_return'], 0)
        self.assertTrue(insufficient['inventory_bytes_unchanged'])
        exact = report['cases']['exact_stack_boundary']
        self.assertEqual(exact['native_return'], 1)
        self.assertTrue(exact['inventory_bytes_unchanged'])
        self.assertIn('UNRESOLVED_FIXTURE', report['claims']['exact_stack_boundary'])


if __name__ == '__main__':
    unittest.main()
