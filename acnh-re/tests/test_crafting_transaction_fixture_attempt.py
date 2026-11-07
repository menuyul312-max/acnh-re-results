import json
from pathlib import Path
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / 'tools' / 'crafting_transaction_fixture_attempt.py'
RESULT = ROOT / 'output' / 'gameplay' / 'crafting_transaction_followup' / 'crafting_transaction_fixture_attempt.json'
AVAILABLE = (Path('/workspace/acnh-re/output/index.sqlite').is_file()
             and (ROOT / 'inputs' / 'additional_exefs' / 'main').is_file())


@unittest.skipUnless(AVAILABLE, 'shared ACNH ELF/index are not present')
class CraftingTransactionFixtureAttemptTests(unittest.TestCase):
    def test_partial_fixtures_do_not_claim_the_insert_or_rollback_path(self):
        subprocess.run([sys.executable, str(TOOL)], cwd=ROOT.parent.parent, check=True)
        report = json.loads(RESULT.read_text())
        craft = report['probes']['ee1420']
        self.assertFalse(craft['target_helper_reached'])
        self.assertIn('0xeff060', craft['executed_watchpoints'])
        self.assertEqual(craft['first_unmapped_access']['pc'], '0xab941c')
        self.assertEqual(craft['fixture']['item_cache_global']['value_before_call'], '0x0')

        insertion = report['probes']['efbd30']
        self.assertFalse(insertion['target_helper_reached'])
        self.assertIn('0xe670b0', insertion['executed_watchpoints'])
        self.assertEqual(insertion['return_value'], '0x0')
        self.assertEqual(insertion['fixture']['world_service_global']['value_before_call'], '0x0')
        self.assertIn('serializer/write-to-file remains static-only', report['status'])


if __name__ == '__main__':
    unittest.main()
