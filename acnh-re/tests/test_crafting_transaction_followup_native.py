import json
from pathlib import Path
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / 'tools' / 'crafting_transaction_followup_native.py'
RESULT = ROOT / 'output' / 'gameplay' / 'crafting_transaction_followup' / 'crafting_transaction_followup_native.json'
AVAILABLE = (Path('/workspace/acnh-re/output/index.sqlite').is_file()
             and Path('/workspace/acnh-re/output/tables_resolved/RecipeCraftParam.json').is_file()
             and (ROOT / 'inputs' / 'additional_exefs' / 'main').is_file())


@unittest.skipUnless(AVAILABLE, 'shared ACNH ELF, index, and tables are not present')
class CraftingTransactionFollowupNativeTest(unittest.TestCase):
    def test_recipe_row_runs_from_cold_save_cache(self):
        subprocess.run([sys.executable, str(TOOL)], cwd=ROOT.parent.parent, check=True)
        result = json.loads(RESULT.read_text())
        scenarios = result['scenarios']
        full = scenarios['cold_cache_all_five_materials_in_A_B_C_with_C_enabled']
        excluded = scenarios['same_sources_but_C_excluded_by_native_option']
        missing = scenarios['cold_cache_one_required_Peach_missing_from_source_C']

        self.assertEqual(full['cache_state_before'], 'cold')
        self.assertEqual(full['cache_state_after'], 'ready')
        self.assertEqual(full['save_source_record_counts_A_B_C'], [2, 2, 1])
        self.assertEqual(full['final_sufficient_flag'], 1)
        self.assertTrue(full['counters_unchanged_by_requirement_checks'])
        self.assertEqual(excluded['final_sufficient_flag'], 0)
        self.assertEqual(missing['final_sufficient_flag'], 0)
        self.assertEqual(missing['material_observations'][4]['counter_C_A_B'], [0, 0, 0])
        self.assertIn('SDK memset import only', result['provenance']['dependencies_stubbed'][0])
        self.assertEqual(result['mismatches'], [])


if __name__ == '__main__':
    unittest.main()
