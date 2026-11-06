import json
from pathlib import Path
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "tool_catch_inventory_native.py"
RESULT = ROOT / "output" / "gameplay" / "tool_mechanics_followup" / "tool_catch_inventory_native.json"
RESEARCH = Path("/workspace/acnh-re/output")
AVAILABLE = (
    (ROOT / "inputs" / "additional_exefs" / "main").is_file()
    and (RESEARCH / "index.sqlite").is_file()
    and (RESEARCH / "tables_resolved" / "ItemParam.json").is_file()
)


@unittest.skipUnless(AVAILABLE, "shared ACNH NSO and analysis environment are not present")
class ToolCatchInventoryNativeTest(unittest.TestCase):
    def test_native_net_rod_helper_inserts_result_in_all_pocket_slots(self):
        subprocess.run([sys.executable, str(TOOL)], cwd=ROOT.parent.parent,
                       check=True, capture_output=True, text=True)
        result = json.loads(RESULT.read_text())
        self.assertEqual((result["case_count"], result["mismatches"]), (42, 0))
        self.assertEqual(
            (result["first_empty_case_count"], result["full_inventory_case_count"]),
            (40, 2),
        )
        native_entries = result["native_function_entry_counts"]
        for function_va in ("0xefec70", "0xefee80", "0xf57ed0",
                            "0xf589b0", "0xf589e0"):
            self.assertGreaterEqual(native_entries[function_va], 40)
        self.assertEqual(native_entries["0xefec70"], 42)
        self.assertEqual(native_entries["0xeffea0"], 2)
        self.assertGreater(native_entries["0xf58d00"], 0)
        self.assertGreater(native_entries["0xa1e8c0"], 0)
        self.assertEqual(
            {(call["owner_va"], call["call_pc"])
             for call in result["static_result_helper_callers"]},
            {("0xe45b80", "0xe45dfc"), ("0xe4e730", "0xe4ebd0")},
        )
        self.assertEqual(
            {(call["owner_va"], call["call_pc"], call["target_va"])
             for call in result["static_catch_result_preparation_calls"]},
            {("0xe45b80", "0xe45cbc", "0xdb00f0"),
             ("0xe4e730", "0xe4ea70", "0xdb00f0")},
        )
        by_kind = {kind: [case["first_empty_slot"] for case in result["cases"]
                          if case["result_kind"] == kind]
                   for kind in ("Fish", "Insect")}
        self.assertEqual(by_kind, {"Fish": list(range(20)), "Insect": list(range(20))})
        self.assertTrue(all(case["stored_word_hex"] == case["source_word_hex"]
                            for case in result["cases"]))
        full_by_kind = {case["result_kind"]: case
                        for case in result["full_inventory_cases"]}
        self.assertEqual(set(full_by_kind), {"Fish", "Insect"})
        for case in full_by_kind.values():
            self.assertEqual(case["helper_return"], 1)
            self.assertEqual(case["evicted_initial_slot"], 0)
            self.assertEqual(case["result_stored_at_slot"], 19)
            self.assertTrue(case["all_original_items_except_slot_zero_preserved"])
        self.assertEqual(result["unresolved_imports"], {})
        self.assertIn("catalog/save persistence", " ".join(result["limits"]))


if __name__ == "__main__":
    unittest.main()
