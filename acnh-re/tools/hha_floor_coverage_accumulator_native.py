#!/usr/bin/env python3
"""Run the native HHA floor-area accumulator basic block on controlled records."""
import hashlib
import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from nso_sandbox import Sandbox  # noqa: E402

NSO = ROOT / "inputs/additional_exefs/main"
OUT = ROOT / "output/gameplay/house_hha_followup/hha_coverage_accumulator_native.json"
BLOCK = 0x7B2694
STOP_AFTER_STORE = 0x7B26BC
WIDTH_HELPER = 0x52C270
HEIGHT_HELPER = 0x52C290
AREA_OFFSET = 0x150


def run():
    sandbox = Sandbox(NSO)
    room = sandbox.alloc(0x200)
    room_pointer_cell = sandbox.alloc(8)
    area = sandbox.STACK + 0x3FF000 + 0x88
    sandbox.uc.mem_write(room_pointer_cell, struct.pack("<Q", room))

    def stop_after_area_store(_sandbox):
        # Starting in the middle of the enclosing function means LR is the
        # second helper's return site; restore Sandbox's outer stop address.
        _sandbox.reg("x30", _sandbox.STOP)
        return 0

    # This stub is reached immediately after the original MADD/STR sequence.
    # The two size getters and the multiply-add/store remain original code.
    sandbox.stub(STOP_AFTER_STORE, stop_after_area_store)

    cases = []
    for x_min, x_max, y_min, y_max, initial in [
            (0, 0, 0, 0, 0),
            (4, 9, 7, 12, 0),
            (-5, 4, -3, 2, 11),
            (100, 109, 200, 205, 1234),
            (3, 6, 20, 27, 0x100)]:
        # 52c270 reads [area+0x10] and [area+0x20]; 52c290 reads
        # [area+0x14] and [area+0x24]. Both endpoints are inclusive.
        area_record = bytearray(0x30)
        struct.pack_into("<i", area_record, 0x10, x_min)
        struct.pack_into("<i", area_record, 0x20, x_max)
        struct.pack_into("<i", area_record, 0x14, y_min)
        struct.pack_into("<i", area_record, 0x24, y_max)
        sandbox.uc.mem_write(area, bytes(area_record))
        sandbox.uc.mem_write(room + AREA_OFFSET, struct.pack("<i", initial))
        sandbox.uc.mem_write(sandbox.STACK + 0x3FF000 + 0x28,
                             struct.pack("<Q", room_pointer_cell))

        width = x_max + 1 - x_min
        height = y_max + 1 - y_min
        sandbox.call(BLOCK)
        actual = struct.unpack("<i", sandbox.read(room + AREA_OFFSET, 4))[0]
        expected = initial + width * height
        case = {"x_bounds_inclusive": [x_min, x_max],
                "y_bounds_inclusive": [y_min, y_max],
                "width": width, "height": height,
                "initial_area_accumulator": initial,
                "expected_increment": width * height,
                "actual_area_accumulator": actual,
                "expected_area_accumulator": expected,
                "match": actual == expected}
        cases.append(case)
        if actual != expected:
            raise AssertionError(case)

    if sandbox.unknown_imports:
        raise AssertionError({"unexpected_imports": sandbox.unknown_imports})
    result = {
        "schema": "acnh-re/hha-floor-coverage-accumulator-native/1",
        "native_elf_sha256": hashlib.sha256(NSO.read_bytes()).hexdigest(),
        "native_block": {"start": hex(BLOCK), "stop_after_store": hex(STOP_AFTER_STORE),
                         "width_helper": hex(WIDTH_HELPER), "height_helper": hex(HEIGHT_HELPER),
                         "record_area_offset": hex(AREA_OFFSET)},
        "contract": "The original block obtains inclusive X/Z extents from a record, multiplies width by height, and adds the product to the player-evaluation record +0x150.",
        "scope": "Bounded execution begins after the item eligibility branch in 0x7b1fe0. It proves dimension arithmetic and the accumulator write only; it does not execute the containing evaluator, live item lookup, save accessors, or the aa7f80 eligibility condition.",
        "cases": len(cases),
        "mismatches": 0,
        "results": cases,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({key: value for key, value in result.items() if key != "results"}, indent=2))


if __name__ == "__main__":
    run()
