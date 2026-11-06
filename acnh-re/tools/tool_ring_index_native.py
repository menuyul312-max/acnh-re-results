#!/usr/bin/env python3
"""Verify the native RingMenuTools eight-entry selector index transform."""
import hashlib
import json
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from nso_sandbox import Sandbox  # noqa: E402

NSO = ROOT / "inputs/additional_exefs/main"
OUT = ROOT / "output/gameplay/tool_mechanics_followup/tool_ring_index_native.json"
CONSTRUCTOR = 0x14254F0
LOOKUP = 0x1412770
ARRAY_OFFSET = 0x1B980
EXPECTED = [2, 1, 0, 7, 6, 5, 4, 3]


def run():
    sandbox = Sandbox(NSO)
    obj = sandbox.alloc(0x1BC00)

    # These initialize unrelated UI-runtime state; the tested table is populated by
    # the constructor's own native stores and read by the original lookup routine.
    sandbox.stub(0x14103F0, lambda _sb: 0)
    sandbox.stub(0x1CFA8D0, lambda _sb: 0)
    sandbox.call(CONSTRUCTOR, (obj,))
    table = list(struct.unpack("<8I", sandbox.read(obj + ARRAY_OFFSET, 32)))
    if table != EXPECTED:
        raise AssertionError({"table": table, "expected": EXPECTED})

    cases = []
    for value in range(9):
        sandbox.call(LOOKUP, (obj, value))
        actual = sandbox.reg("x0") & 0xFFFFFFFF
        expected = EXPECTED.index(value) if value < 8 else 0xFFFFFFFF
        if actual != expected:
            raise AssertionError({"value": value, "actual": actual, "expected": expected})
        cases.append({"input_value": value, "native_table_index": actual})

    if sandbox.unknown_imports:
        raise AssertionError({"unexpected_imports": sandbox.unknown_imports})
    result = {
        "schema": "acnh-re/tool-ring-index-native/1",
        "native_elf_sha256": hashlib.sha256(NSO.read_bytes()).hexdigest(),
        "constructor": hex(CONSTRUCTOR),
        "lookup": hex(LOOKUP),
        "array_offset_from_this": hex(ARRAY_OFFSET),
        "table_values_by_index": table,
        "cases": cases,
        "case_count": len(cases),
        "mismatches": 0,
        "dependencies_stubbed": [
            "0x14103f0 unrelated UI setup helper",
            "0x1cfa8d0 unrelated UI state initializer",
        ],
        "interpretation": "Native constructor and lookup establish an eight-value permutation for an internal ring selector table. The values' semantic source and relationship to saved inventory items are not established.",
        "remaining": [
            "No item or inventory record is connected to these indices.",
            "The menu selection/equip result is not exercised by this probe.",
        ],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({key: value for key, value in result.items() if key != "cases"}, indent=2))


if __name__ == "__main__":
    run()
