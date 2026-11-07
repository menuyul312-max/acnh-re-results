import json
from pathlib import Path
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / 'tools' / 'crafting_pocket_manager_probe.py'
RESULT = ROOT / 'output' / 'gameplay' / 'crafting_transaction_followup' / 'crafting_pocket_manager_probe.json'
AVAILABLE = (
    Path('/workspace/acnh-re/output/index.sqlite').is_file()
    and (Path('/workspace/acnh-re/output/tables_resolved/RecipeCraftParam.json').is_file())
    and (ROOT / 'inputs' / 'additional_exefs' / 'main').is_file()
)


@unittest.skipUnless(AVAILABLE, 'shared ACNH ELF/index/tables are not present')
class CraftingPocketManagerProbeTests(unittest.TestCase):
    def test_reconstructed_manager_reaches_pocket_helper_and_bounds_mutation(self):
        subprocess.run([sys.executable, str(TOOL)], cwd=ROOT.parent, check=True)
        report = json.loads(RESULT.read_text())
        contract = report['fixture_contract']['world_player_manager_contract']
        self.assertEqual(contract['count_member_offset'], '0xe8')
        self.assertEqual(contract['member_array_pointer_offset'], '0xf0')
        self.assertEqual(contract['member_stride'], '0x3ce50')
        self.assertEqual(contract['active_view_pointer_offset'], '0x118')

        material = report['probes']['material']
        for va in ('0xefbd30', '0xe670b0', '0xf2d640', '0xf8f400',
                   '0xee9350', '0xee94f0', '0xf99270', '0xf98650'):
            self.assertIn(va, material['executed_native_vas'])
        self.assertIsNone(material['native_error'])
        self.assertIsNone(material['first_unmapped_access'])
        self.assertEqual(material['descriptor_item_id'], 2213)
        self.assertEqual(len(material['slot_mutator_calls']), 2)
        self.assertEqual(material['slot0_before'], [2213, 0, 0])
        self.assertEqual(material['slot0_after'], [2213, 0, 0])
        self.assertEqual(material['dirty_slot0_before'], 0)
        self.assertEqual(material['dirty_slot0_after'], 0xff)
        self.assertEqual(material['pocket_changed_offsets'], ['0x15c'])

        result = report['probes']['result_descriptor_control']
        self.assertEqual(result['descriptor_item_id'], 975)
        self.assertIn('0xf99270', result['executed_native_vas'])
        self.assertNotIn('0xf98650', result['executed_native_vas'])
        self.assertEqual(result['pocket_write_events'], [])
        self.assertEqual(result['pocket_changed_offsets'], [])
        self.assertEqual(result['dirty_slot0_after'], 0)


if __name__ == '__main__':
    unittest.main()
