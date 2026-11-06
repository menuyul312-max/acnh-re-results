#!/usr/bin/env python3
"""Run the native item-ID membership/set helpers on a synthetic bitset."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from nso_sandbox import Sandbox  # noqa: E402

NSO = ROOT / "inputs/additional_exefs/main"
OUT = ROOT / "output/gameplay/catalog_unique_id_bitset_native.json"
IS_SET = 0xA0F440
SET_BIT = 0xA0F510
LIMIT = 15000
BITSET_SIZE = 0x754


def run():
    sandbox = Sandbox(NSO)
    manager = sandbox.alloc(0x40)
    vtable = sandbox.alloc(0x40)
    bitset = sandbox.alloc(BITSET_SIZE)
    item = sandbox.alloc(8)
    inputs = {"unique_id": 0}

    sandbox.uc.mem_write(manager, vtable.to_bytes(8, "little"))
    sandbox.uc.mem_write(vtable + 0x18, (0x1665EA0).to_bytes(8, "little"))
    sandbox.uc.mem_write(vtable + 0x20, (0x1665EA0).to_bytes(8, "little"))

    # Original A0F440/A0F510 bit arithmetic and bounds are retained. The
    # vtable accessor, item-ID canonicalizer and cItem normalizer are controlled.
    sandbox.stub(0x1665EA0, lambda s: bitset)
    sandbox.stub(0xF58A90, lambda s: inputs["unique_id"])
    sandbox.stub(0xF591A0, lambda s: 1)

    records = []

    def exercise(unique_id):
        inputs["unique_id"] = unique_id
        sandbox.uc.mem_write(bitset, bytes(BITSET_SIZE))
        before = sandbox.call(IS_SET, (manager, item))
        sandbox.call(SET_BIT, (manager, item))
        after = sandbox.call(IS_SET, (manager, item))
        expected = bytearray(BITSET_SIZE)
        in_range = 0 <= unique_id < LIMIT
        if in_range:
            expected[unique_id >> 3] |= 1 << (unique_id & 7)
        actual = sandbox.read(bitset, BITSET_SIZE)
        record = {
            "item_unique_id": unique_id,
            "in_15000_id_range": in_range,
            "membership_before": bool(before),
            "membership_after": bool(after),
            "expected_after": in_range,
            "bitset_matches": actual == bytes(expected),
        }
        if before != 0 or bool(after) != in_range or actual != bytes(expected):
            raise AssertionError(record)
        records.append(record)

    for unique_id in [0, 1, 31, 32, 14992, 14999, 15000, 15001, 0xFFFF]:
        exercise(unique_id)

    # Confirm that the first unused ID remains invisible even if its padded
    # storage bit is manually set; the native helper enforces the 15,000 cap.
    inputs["unique_id"] = LIMIT
    sandbox.uc.mem_write(bitset, bytes(BITSET_SIZE))
    sandbox.uc.mem_write(bitset + (LIMIT >> 3), bytes([1 << (LIMIT & 7)]))
    padded_query = sandbox.call(IS_SET, (manager, item))
    records.append({"item_unique_id": LIMIT, "preseeded_padding_bit": True,
                    "membership_after_preseed": bool(padded_query),
                    "expected_membership": False,
                    "bitset_matches": not bool(padded_query)})
    if padded_query:
        raise AssertionError("unused padded bit must be rejected by the native range guard")

    if sandbox.unknown_imports:
        raise AssertionError({"unexpected_imports": sandbox.unknown_imports})
    result = {
        "native_elf_sha256": hashlib.sha256(NSO.read_bytes()).hexdigest(),
        "native_functions": {"membership": hex(IS_SET), "set_bit": hex(SET_BIT)},
        "bitset_bytes": BITSET_SIZE,
        "valid_unique_id_count": LIMIT,
        "scope": "Original membership and set-bit functions run on a synthetic 0x754-byte bitset. The vtable data accessor, Item ID normalization, and cItem canonicalizer are stubbed; no live save or ItemParam row is loaded.",
        "cases": len(records),
        "mismatches": 0,
        "dependencies_stubbed": ["bitset data accessor vtable slots", "F58A90 item-ID mapping", "F591A0 cItem normalizer"],
        "results": records,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({key: value for key, value in result.items() if key != "results"}, indent=2))


if __name__ == "__main__":
    run()
