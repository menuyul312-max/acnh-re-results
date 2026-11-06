import json
import os
from pathlib import Path
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "tool_slingshot_launch_native.py"
RESULT = ROOT / "output" / "gameplay" / "tool_mechanics_followup" / "tool_slingshot_launch_native.json"
RESEARCH = Path("/workspace/acnh-re/output")
AVAILABLE = (
    (ROOT / "inputs" / "additional_exefs" / "main").is_file()
    and (RESEARCH / "index.sqlite").is_file()
)


@unittest.skipUnless(AVAILABLE, "shared ACNH NSO and analysis environment are not present")
class ToolSlingshotLaunchNativeTest(unittest.TestCase):
    def test_native_launch_handoff_copies_start_and_scales_velocity(self):
        env = os.environ.copy()
        env["PYTHONPATH"] = "/workspace/acnh-re/.deps" + os.pathsep + env.get("PYTHONPATH", "")
        subprocess.run([sys.executable, str(TOOL)], cwd=ROOT.parent.parent,
                       env=env, check=True, capture_output=True, text=True)
        result = json.loads(RESULT.read_text())
        self.assertEqual((result["case_count"], result["mismatches"]), (2, 0))
        self.assertEqual(result["static_callsite"], {
            "owner_va": "0xe564b0", "call_pc": "0xe567c0", "target_va": "0x803690",
        })
        self.assertEqual(
            [case["state_scaled_velocity"] for case in result["cases"]],
            [[9.0, -12.0, 1.5], [-3.0, 24.0, 0.0]],
        )
        self.assertTrue(all(case["launch_dispatch_flag"] == 1
                            for case in result["cases"]))
        self.assertEqual(result["native_function_entry_counts"], {
            "0x29ac0": 4, "0x803690": 2, "0x1f068d0": 2,
        })
        self.assertEqual(result["unresolved_imports"], {})


if __name__ == "__main__":
    unittest.main()
