import json
from pathlib import Path
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "tool_ring_inventory_native.py"
RESULT = ROOT / "output" / "gameplay" / "tool_mechanics_followup" / "tool_ring_inventory_native.json"
RESEARCH = Path("/workspace/acnh-re/output")
AVAILABLE = (
    (ROOT / "inputs" / "additional_exefs" / "main").is_file()
    and (RESEARCH / "index.sqlite").is_file()
    and (RESEARCH / "tables_resolved" / "ItemParam.json").is_file()
)
EXPECTED_LABELS = [
    "ToolAxe", "ToolScoop", "ToolNet", "ToolAngling",
    "ToolSlingshot", "ToolWatering", "ToolAxeGold", "ToolNetGold",
]


@unittest.skipUnless(AVAILABLE, "shared ACNH NSO and analysis environment are not present")
class ToolRingInventoryNativeTest(unittest.TestCase):
    def test_native_ring_selection_reads_each_pocket_item_word(self):
        subprocess.run(
            [sys.executable, str(TOOL)],
            cwd=ROOT.parent.parent,
            check=True,
        )
        result = json.loads(RESULT.read_text())
        self.assertEqual((result["case_count"], result["mismatches"]), (8, 0))
        self.assertEqual(result["unresolved_imports"], {})
        self.assertEqual(
            {(call["owner_va"], call["call_pc"], call["target_va"])
             for call in result["static_call_chain"]},
            {
                ("0x1417f70", "0x1418008", "0x11b7210"),
                ("0x11b7210", "0x11b7264", "0xef7260"),
            },
        )
        self.assertEqual(
            [case["ring_selection_index"] for case in result["cases"]],
            list(range(8)),
        )
        self.assertEqual([case["item_label"] for case in result["cases"]], EXPECTED_LABELS)
        self.assertTrue(all(
            case["ring_selection_index"] == case["pocket_inventory_slot"]
            and case["source_record_offset_from_pocket_base"] ==
            hex(0x3F00 + case["ring_selection_index"] * 0x2450 + 0x2418)
            and case["exact_word_copied"]
            for case in result["cases"]
        ))
        argument = result["callback_index_argument"]
        self.assertEqual(argument["stored_index_field_offset_from_page"], "0x1b9f8")
        self.assertEqual(argument["reader_argument_register"], "w2")
        self.assertEqual(argument["reader_va"], "0x11b7210")


if __name__ == "__main__":
    unittest.main()
