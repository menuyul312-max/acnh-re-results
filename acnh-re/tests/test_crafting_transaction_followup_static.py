import json
from pathlib import Path
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / 'tools' / 'crafting_transaction_followup_static.py'
RESULT = ROOT / 'output' / 'gameplay' / 'crafting_transaction_followup' / 'crafting_transaction_followup_static.json'
AVAILABLE = (Path('/workspace/acnh-re/output/index.sqlite').is_file()
             and Path('/workspace/acnh-re/output/tables_resolved/ItemRemake.json').is_file()
             and (ROOT / 'inputs' / 'additional_exefs' / 'main').is_file())


@unittest.skipUnless(AVAILABLE, 'shared ACNH index, tables, and ELF are not present')
class CraftingTransactionFollowupStaticTests(unittest.TestCase):
    def setUp(self):
        subprocess.run([sys.executable, str(TOOL)], cwd=ROOT.parent.parent, check=True)
        self.report = json.loads(RESULT.read_text())

    def test_tutorial_unlocks_map_to_native_unlock_enum(self):
        proof = self.report['recipe_learning']
        self.assertEqual(proof['tutorial_unlock_indices'], {
            'DIYtutorial1': 12,
            'DIYtutorial2': 13,
        })
        self.assertEqual(proof['status'],
                         'EVENTFLOW_AND_NATIVE_STATIC_PROVEN; not executed against a real save')

    def test_craft_handler_reaches_six_signed_material_mutators_and_result_add(self):
        proof = self.report['craft_transaction']['transaction_helper']
        self.assertEqual(len(proof['material_mutator_call_sites']), 6)
        self.assertEqual(proof['inventory_delta_helper']['va'], '0xeff060')
        self.assertEqual(proof['signed_quantity_helper']['va'], '0xf9e410')
        self.assertEqual(proof['result_award_route']['general_add']['add_impl_va'], '0xf987c0')
        self.assertIn('One conditional native branch', proof['claim'])

    def test_remake_cost_is_table_evidence_and_rollback_remains_open(self):
        remake = self.report['workbench_page_and_remake']['remake_item']
        self.assertEqual(remake['tutorial_item_unique_id'], 3436)
        self.assertEqual(remake['kit_item_unique_id'], 2513)
        self.assertEqual(remake['table_cost'], 2)
        self.assertEqual(self.report['status_by_slice']['cancel_or_rollback'],
                         'OPEN; no rollback behavior established')


if __name__ == '__main__':
    unittest.main()
