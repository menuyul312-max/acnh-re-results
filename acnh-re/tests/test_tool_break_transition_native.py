import json
from pathlib import Path
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / 'tools' / 'tool_break_transition_native.py'
RESULT = ROOT / 'output' / 'gameplay' / 'tool_mechanics_followup' / 'tool_break_transition_native.json'
AVAILABLE = (Path('/workspace/acnh-re/output/index.sqlite').is_file()
             and (ROOT / 'inputs' / 'additional_exefs' / 'main').is_file())


@unittest.skipUnless(AVAILABLE, 'shared ACNH NSO and analysis environment are not present')
class ToolBreakTransitionNativeTest(unittest.TestCase):
    def test_break_action_reaches_activity_counter_writer_boundary(self):
        subprocess.run([sys.executable, str(TOOL)], cwd=ROOT.parent.parent, check=True)
        result = json.loads(RESULT.read_text())
        cases = result['cases']
        self.assertEqual((result['case_count'], result['mismatches']), (6, 0))
        self.assertEqual(cases[0]['writer_requests'], [])
        self.assertEqual(cases[1]['writer_requests'], [])
        self.assertEqual(cases[2]['writer_requests'], [{'key': 'BreakToolCount', 'amount': 1}])
        for case in cases[3:]:
            self.assertEqual(case['writer_requests'], [{'key': 'BreakToolCount', 'amount': 1}])
        self.assertIn('save mutation', ' '.join(result['limits']))


if __name__ == '__main__':
    unittest.main()
