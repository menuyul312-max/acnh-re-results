#!/usr/bin/env python3
"""Run native missing-catalog-variant selection and item-byte update."""
import hashlib
import json
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from nso_sandbox import Sandbox  # noqa: E402

from unicorn import UC_HOOK_CODE  # noqa: E402

NSO = ROOT / "inputs/additional_exefs/main"
OUT = ROOT / "output/gameplay/catalog_variant_selection_native.json"
SELECT = 0xF5AB20
SET_VARIANT = 0xAABF10
REMAKE_ID = 5
VARIANT_COUNT = 8


def run():
    sandbox = Sandbox(NSO)
    row = sandbox.alloc(0x20)
    remake_id_field = sandbox.alloc(2)
    sandbox.uc.mem_write(remake_id_field, struct.pack("<h", REMAKE_ID))

    # A9C290 supplies a controlled item wrapper, AAC250 the supported variant
    # count, and AB0F50 the variant field. AB2810 and AABF10 stay native.
    sandbox.stub(0xF58D00, lambda sb: 1)

    def copy_item(sb):
        destination, source = sb.reg("x0"), sb.reg("x1")
        sb.uc.mem_write(destination + 8, sb.read(source, 8))
        sb.uc.mem_write(destination + 0x10, struct.pack("<Q", row))
        return destination

    sandbox.stub(0xA9C290, copy_item)
    sandbox.stub(0xAAC250, lambda sb: VARIANT_COUNT)
    sandbox.stub(0xA1E920, lambda sb: remake_id_field)
    sandbox.stub(0xAB0F50, lambda sb: sb.reg("x0") + 0x0C)
    sandbox.stub(0x19AA040, lambda sb: 0)

    rng = {"value": 0}
    sandbox.stub(0x19AA0E0, lambda sb: rng["value"])
    sandbox.stub(0xA0F4B0, lambda sb: 0)

    setter_calls = {"count": 0}

    def count_setter(uc, address, size, _):
        setter_calls["count"] += 1

    sandbox.uc.hook_add(UC_HOOK_CODE, count_setter,
                        begin=SET_VARIANT, end=SET_VARIANT)

    cases = [
        {"name": "first-uncollected", "collected": [0, 2, 5],
         "rng": 0, "expected": 1},
        {"name": "middle-uncollected", "collected": [0, 2, 5],
         "rng": 0x80000000, "expected": 4},
        {"name": "last-uncollected", "collected": [0, 2, 5],
         "rng": 0xFFFFFFFF, "expected": 7},
        {"name": "single-uncollected", "collected": [0, 1, 2, 3, 4, 5, 7],
         "rng": 0xFFFFFFFF, "expected": 6},
        {"name": "all-collected", "collected": list(range(8)),
         "rng": 0x12345678, "expected": None},
    ]
    results = []
    for case in cases:
        bits = sandbox.alloc(2000)
        item = sandbox.alloc(8)
        output = sandbox.alloc(8)
        sandbox.uc.mem_write(bits, bytes(2000))
        sandbox.uc.mem_write(item, struct.pack("<HBBI", 4318, 1, 0, 0xA8))
        sandbox.uc.mem_write(output, bytes(8))
        for variant in case["collected"]:
            index = REMAKE_ID * 8 + variant
            offset = (index // 32) * 4
            word = sandbox.u32(bits + offset) | (1 << (index & 31))
            sandbox.uc.mem_write(bits + offset, struct.pack("<I", word))

        before = setter_calls["count"]
        rng["value"] = case["rng"]
        # The native function returns its 8-byte item through the AAPCS64
        # indirect-result register x8; x0 is the catalog bitset, x1 the item.
        sandbox.reg("x8", output)
        returned = sandbox.call(SELECT, (bits, item, 0))
        after = setter_calls["count"]
        payload = sandbox.read(output, 8)
        if returned != output:
            raise AssertionError({"case": case["name"], "return": hex(returned),
                                  "expected_output": hex(output)})

        if case["expected"] is None:
            if after != before:
                raise AssertionError({"case": case["name"],
                                      "unexpected_setter_calls": after - before})
            actual = None
        else:
            missing = [v for v in range(VARIANT_COUNT)
                       if v not in case["collected"]]
            rank = (case["rng"] * len(missing)) >> 32
            expected_from_rank = missing[rank]
            actual = payload[4] & 7
            if (expected_from_rank != case["expected"] or
                    actual != case["expected"] or after - before != 1):
                raise AssertionError({"case": case["name"], "actual": actual,
                                      "expected": case["expected"],
                                      "rank_expected": expected_from_rank,
                                      "setter_calls": after - before})

        results.append({
            "name": case["name"], "collected_variants": case["collected"],
            "missing_variants": [v for v in range(8)
                                 if v not in case["collected"]],
            "rng_u32": case["rng"], "selected_variant": actual,
            "output_payload_byte_at_offset_4": payload[4],
            "native_setter_calls": after - before, "match": True,
        })

    if sandbox.unknown_imports:
        raise AssertionError({"unexpected_imports": sandbox.unknown_imports})
    result = {
        "native_elf_sha256": hashlib.sha256(NSO.read_bytes()).hexdigest(),
        "native_functions": {"select_missing_variant": hex(SELECT),
                             "set_item_variant": hex(SET_VARIANT),
                             "item_remake_id": "0xab2810"},
        "scope": "F5AB20, AB2810 and AABF10 execute native code. Stubs supply item validity, ItemParam wrapper/RemakeID field lookup, supported variant count, variant-byte pointer, and deterministic RNG. The 2,000-byte bitset and item payload are synthetic; no live save or real item row is loaded.",
        "formula": "For the eight slots RemakeID*8..RemakeID*8+7, native F5AB20 counts clear bits and selects rank floor(rng_u32*missing_count/2^32); AABF10 writes that zero-based variant ordinal to the payload's low three bits.",
        "cases": len(results), "mismatches": 0,
        "dependencies_stubbed": ["item validity", "A9C290 item wrapper",
                                  "AAC250 variant count", "A1E920 RemakeID field adapter",
                                  "AB0F50 variant-byte pointer", "19AA040/19AA0E0 RNG"],
        "results": results,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k != "results"}, indent=2))


if __name__ == "__main__":
    run()
