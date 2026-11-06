#!/usr/bin/env python3
"""Exercise the native FillCatalog bitset setter after its item-index mapper."""
import hashlib
import json
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from nso_sandbox import Sandbox  # noqa: E402

NSO = ROOT / "inputs/additional_exefs/main"
OUT = ROOT / "output/gameplay/catalog_bitset_native.json"
SETTER = 0xEECAD0
ITEM_TO_CATALOG_INDEX = 0xAB2940


def run():
    sandbox = Sandbox(NSO)
    manager = sandbox.alloc(0x40)
    bits = sandbox.alloc(2000)
    world = sandbox.alloc(0x2000)
    sandbox.uc.mem_write(manager + 8, struct.pack("<Q", bits))
    sandbox.uc.mem_write(manager + 16, struct.pack("<Q", 0))
    mapped_index = {"value": 0}

    # Replace only service/context boundaries. The setter's range check,
    # address calculation and bit operation execute as original instructions.
    sandbox.stub(ITEM_TO_CATALOG_INDEX, lambda s: mapped_index["value"])
    sandbox.stub(0xF8F400, lambda s: s.reg("x0"))  # preserve world pointer
    sandbox.stub(0xEE9350, lambda s: 0)

    def bind_manager(s):
        s.uc.mem_write(s.reg("x0") + 8, struct.pack("<Q", manager))
        return 0

    sandbox.stub(0xEE9490, bind_manager)
    sandbox.stub(0xEE94F0, lambda s: 0)
    sandbox.stub(0xEE93D0, lambda s: 0)

    cases = [0, 31, 32, 15999, 16000, 0xFFFFFFFF]
    results = []
    for index in cases:
        mapped_index["value"] = index
        sandbox.uc.mem_write(bits, bytes(2000))
        returned = sandbox.call(SETTER, (world, 4318))
        words = struct.unpack("<500I", sandbox.read(bits, 2000))
        expected = [0] * 500
        if index != 0xFFFFFFFF:
            returned_expected = 1
            if index < 16000:
                expected[index // 32] = 1 << (index & 31)
        else:
            returned_expected = 0
        changed = [(i, f"0x{word:08x}") for i, word in enumerate(words) if word]
        expected_changed = [(i, f"0x{word:08x}") for i, word in enumerate(expected) if word]
        if returned != returned_expected or changed != expected_changed:
            raise AssertionError({"mapped_index": index, "returned": returned,
                                  "changed": changed, "expected": expected_changed})
        results.append({"stubbed_mapped_index": index, "return": returned,
                        "set_words": changed})

    if sandbox.unknown_imports:
        raise AssertionError({"unexpected_imports": sandbox.unknown_imports})
    result = {
        "native_elf_sha256": hashlib.sha256(NSO.read_bytes()).hexdigest(),
        "addresses": {"setter": hex(SETTER), "item_to_catalog_index": hex(ITEM_TO_CATALOG_INDEX)},
        "setter_contract": "After the mapper returns an index, EECAD0 accepts 0..15999, sets exactly that bit in a 2000-byte bitset, and returns 1. A mapper result of 0xffffffff returns 0. An index >=16000 returns 1 without setting a bit.",
        "input_item_id": 4318,
        "mapper": "Stubbed to the listed controlled outputs; this verifies the native setter only, not real item-to-catalog mapping or event triggers.",
        "native_cases": len(results),
        "mismatches": 0,
        "dependencies_stubbed": ["0xab2940 item-to-catalog mapper", "0xf8f400 world/context accessor", "0xee9350/0xee9490/0xee94f0/0xee93d0 bitset access wrapper"],
        "results": results,
        "open": ["Which concrete items map to catalog indices", "Which acquisition paths call FillCatalog and under what conditions", "Save persistence and Nook Shopping/mailbox delivery flow"],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({key: value for key, value in result.items() if key != "results"}, indent=2))


if __name__ == "__main__":
    run()
