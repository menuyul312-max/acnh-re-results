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
    row = sandbox.alloc(0x20)
    remake_id_field = sandbox.alloc(2)
    variant_field = sandbox.alloc(1)
    sandbox.uc.mem_write(manager + 8, struct.pack("<Q", bits))
    sandbox.uc.mem_write(manager + 16, struct.pack("<Q", 0))
    inputs = {"valid_item": True, "variant_present": True}

    # Run EECAD0, AB2940 and F5AB10 as original instructions. Stub only the
    # item/table and save-wrapper boundaries, with controlled ItemParam fields.
    sandbox.stub(0xF58D00, lambda s: int(inputs["valid_item"]))

    def bind_item_row(s):
        s.uc.mem_write(s.reg("x0") + 0x10, struct.pack("<Q", row))
        return 0

    sandbox.stub(0xA9C290, bind_item_row)
    sandbox.stub(0xAAC250, lambda s: 1)
    sandbox.stub(0xA1E920, lambda s: remake_id_field)
    sandbox.stub(0xAB0F50, lambda s: variant_field if inputs["variant_present"] else 0)
    sandbox.stub(0xF8F400, lambda s: s.reg("x0"))  # preserve world pointer
    sandbox.stub(0xEE9350, lambda s: 0)

    def bind_manager(s):
        s.uc.mem_write(s.reg("x0") + 8, struct.pack("<Q", manager))
        return 0

    sandbox.stub(0xEE9490, bind_manager)
    sandbox.stub(0xEE94F0, lambda s: 0)
    sandbox.stub(0xEE93D0, lambda s: 0)

    results = []
    case_count = 0

    def check_case(remake_id, variant, *, valid_item=True, variant_present=True, record=False):
        nonlocal case_count
        inputs["valid_item"] = valid_item
        inputs["variant_present"] = variant_present
        sandbox.uc.mem_write(remake_id_field, struct.pack("<h", remake_id))
        sandbox.uc.mem_write(variant_field, bytes([variant & 0xff]))
        sandbox.uc.mem_write(bits, bytes(2000))
        returned = sandbox.call(SETTER, (world, 4318))
        if not valid_item or remake_id < 0:
            mapped_index = 0xFFFFFFFF
            returned_expected = 0
            expected = bytes(2000)
        else:
            mapped_index = remake_id * 8 + ((variant & 7) if variant_present else 0)
            returned_expected = 1
            expected = bytearray(2000)
            if mapped_index < 16000:
                word_offset = (mapped_index // 32) * 4
                expected[word_offset:word_offset + 4] = struct.pack("<I", 1 << (mapped_index & 31))
            expected = bytes(expected)
        actual = sandbox.read(bits, 2000)
        case_count += 1
        if returned != returned_expected or actual != expected:
            raise AssertionError({"remake_id": remake_id, "variant": variant,
                                  "variant_present": variant_present, "valid_item": valid_item,
                                  "mapped_index": mapped_index, "returned": returned,
                                  "expected_return": returned_expected})
        if record:
            results.append({"remake_id": remake_id, "variant_input": variant & 0xff,
                            "variant_masked": (variant & 7) if variant_present else 0,
                            "variant_present": variant_present, "valid_item": valid_item,
                            "mapped_index": (None if mapped_index == 0xFFFFFFFF else mapped_index),
                            "return": returned, "bitset_matches": True})

    # Exhaust every valid catalog index in the 2000 x 8 RemakeID/variant space.
    for remake_id in range(2000):
        for variant in range(8):
            check_case(remake_id, variant)
    # Cover invalid mapper, absent variant byte, and the upper range boundary.
    for remake_id, variant, valid_item, variant_present in [
            (-1, 0, True, True), (7, 0xFF, True, False),
            (2000, 0, True, True), (2000, 7, True, True), (0, 0, False, True)]:
        check_case(remake_id, variant, valid_item=valid_item,
                   variant_present=variant_present, record=True)
    for remake_id, variant in [(0, 0), (3, 7), (31, 0), (31, 7), (1999, 0), (1999, 7)]:
        check_case(remake_id, variant, record=True)

    if sandbox.unknown_imports:
        raise AssertionError({"unexpected_imports": sandbox.unknown_imports})
    result = {
        "native_elf_sha256": hashlib.sha256(NSO.read_bytes()).hexdigest(),
        "addresses": {"setter": hex(SETTER), "item_to_catalog_index": hex(ITEM_TO_CATALOG_INDEX)},
        "setter_contract": "After the mapper returns an index, EECAD0 accepts 0..15999, sets exactly that bit in a 2000-byte bitset, and returns 1. A mapper result of 0xffffffff returns 0. An index >=16000 returns 1 without setting a bit.",
        "mapper_formula_static": "AB2940 reads ItemParam.RemakeID (field hash 0xcb5eb33f, s16); a negative RemakeID is rejected. Otherwise F5AB10 returns RemakeID*8 + (byte returned by AB0F50 & 7), with zero variant bits when AB0F50 returns null.",
        "synthetic_input_item_id": 4318,
        "mapper": "AB2940 and F5AB10 run as native instructions across every RemakeID 0..1999 and variant 0..7. Stubs supply controlled item validity, ItemParam.RemakeID field lookup, variant-byte pointer, and the save/context wrapper; real item rows and low-bit semantics are not exercised.",
        "static_call_paths": [
            {"entry": "0xeebe80", "trace": ["item validation/conversion", "conditional 0xeecad0 catalog-bit set", "0xf57920 and 0xf57880 secondary bitset helpers", "conditional 0xeec010"], "evidence": "Ghidra pseudocode; predicate semantics and save-backed wrapper contents are not dynamically verified"},
            {"entry": "0xeec010", "strings": ["MarketBuiltMyVillage", "FillCatalog"], "effect": "calls 0xf62b50 for the FillCatalog counter after the MarketBuiltMyVillage checks", "evidence": "Ghidra pseudocode"},
            {"entry": "0x118a8a0", "strings": ["BuyItem", "HowmuchBuyItem", "BuyItemCatalog"], "effect": "purchase-page callback updates these achievement fields", "evidence": "Ghidra pseudocode; order eligibility and delivery are open"}
        ],
        "native_cases": case_count,
        "exhaustive_valid_index_cases": 16000,
        "mismatches": 0,
        "dependencies_stubbed": ["0xf58d00 item validity", "0xa9c290/0xaac250 ItemParam row selection", "0xa1e920 RemakeID field lookup", "0xab0f50 variant-byte source", "0xf8f400 world/context accessor", "0xee9350/0xee9490/0xee94f0/0xee93d0 bitset access wrapper"],
        "results": results,
        "open": ["Concrete item-to-RemakeID/variant values and semantics of the low three bits", "Which acquisition paths call FillCatalog and under what conditions", "Save persistence and Nook Shopping/mailbox delivery flow"],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({key: value for key, value in result.items() if key != "results"}, indent=2))


if __name__ == "__main__":
    run()
