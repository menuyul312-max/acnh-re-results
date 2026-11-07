import json
from pathlib import Path
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / 'tools' / 'crafting_transaction_followup_static.py'
RESULT = ROOT / 'output' / 'gameplay' / 'crafting_transaction_followup' / 'crafting_transaction_followup_static.json'
RECIPE_FLOW_RESULT = ROOT / 'output' / 'gameplay' / 'crafting_transaction_followup' / 'crafting_recipe_flow_native.json'
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
        pocket_add = proof['conditional_pocket_add']
        self.assertEqual(pocket_add['calls'][0]['target'], '0xefbd30')
        self.assertIn('0xf99270', [call['target'] for call in pocket_add['helper_chain']])
        self.assertIn('0xefb090', [call['target'] for call in pocket_add['helper_chain']])
        self.assertIn('RecipeCraftParam.MaterialN', pocket_add['claim'])
        self.assertIn('initial 0xefa9a0 pocket-empty test is false', pocket_add['gate'])
        shared_add = pocket_add['shared_generic_item_add_path']
        self.assertEqual(shared_add['general_inventory_add_va'], '0xf987c0')
        self.assertEqual(shared_add['general_inventory_add_calls'][0]['target'], '0xf99270')
        self.assertIn('generic item-award insertion path', shared_add['interpretation'])

        native = json.loads(RECIPE_FLOW_RESULT.read_text())[
            'material_and_workbench']['craft_full_pocket_precheck']
        self.assertEqual(native['status'], 'NATIVE_STATIC_ASSEMBLY; not dynamically executed')
        self.assertEqual(native['precheck_counts']['slot_and_total_counter_va'], '0xeda620')
        self.assertIn('0xee104c', native['capture_conditions_static'][0])
        self.assertEqual(native['post_consumption_gate']['pocket_add_helper_va'], '0xefbd30')

    def test_explicit_save_request_is_separate_from_crafting_mutation(self):
        save = self.report['save_flush_boundary']
        self.assertEqual(save['explicit_save_event_action_count'], 12)
        self.assertEqual(save['system_save_close_event']['params'], {'Process': 'cAll'})
        self.assertIn('tail-dispatches to 0x338080', save['native_request_path']['claim'])
        self.assertIn('0xfb3160', save['native_request_path']['claim'])
        self.assertFalse(save['craft_path_relation']['direct_save_request_calls_found'])
        self.assertIn('OPEN', save['durable_flush_status'])

    def test_remake_cost_is_table_evidence_and_rollback_remains_open(self):
        remake = self.report['workbench_page_and_remake']['remake_item']
        self.assertEqual(remake['tutorial_item_unique_id'], 3436)
        self.assertEqual(remake['kit_item_unique_id'], 2513)
        self.assertEqual(remake['table_cost'], 2)
        quantity_flow = self.report['workbench_page_and_remake']['save_set_handler']['kit_quantity_argument_disassembly']
        self.assertEqual(quantity_flow['0x335d64'], 'mov w1, #0x9d1')
        self.assertEqual(quantity_flow['0x335d78'], 'mov w2, w21')
        self.assertEqual(quantity_flow['0xefbe88'], 'mov w2, w19')
        self.assertEqual(self.report['status_by_slice']['cancel_or_rollback'],
                         'OPEN; a conditional pocket insertion from the precheck object is present, but its trigger/identity is unresolved; full rollback behavior is not established')


if __name__ == '__main__':
    unittest.main()
