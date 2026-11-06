#!/usr/bin/env python3
"""Run the native HHA area-denominator switch on controlled records.

The bounded entry starts just after the HHAGradeMailFlag setter in
0x7b1fe0, at the selector dispatch (0x7b2144), and stops immediately after
the switch updates the room record (0x7b224c). The original AArch64 dispatch
and field writes execute; the next unrelated helper is not entered.
"""
import hashlib
import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from nso_sandbox import Sandbox  # noqa: E402

NSO = ROOT / "inputs/additional_exefs/main"
OUT = ROOT / "output/gameplay/house_hha_followup/hha_house_area_denominator_native.json"
BLOCK = 0x7B2144
STOP_AFTER_SWITCH = 0x7B224C
DENOMINATOR_OFFSET = 0x14C
ROOM_COUNT_OFFSET = 0x154
SELECTOR_STACK_OFFSET = 0x198


def run_case(sandbox, selector, initial_denominator=0, initial_room_count=0):
    record = sandbox.alloc(0x160)
    record_pointer_cell = sandbox.alloc(8)
    sandbox.uc.mem_write(record_pointer_cell, struct.pack("<Q", record))
    sandbox.uc.mem_write(record + DENOMINATOR_OFFSET,
                         struct.pack("<I", initial_denominator))
    sandbox.uc.mem_write(record + ROOM_COUNT_OFFSET,
                         struct.pack("<B", initial_room_count))

    stack = sandbox.STACK + 0x3FF000
    sandbox.uc.mem_write(stack + SELECTOR_STACK_OFFSET, struct.pack("<I", selector))

    # x24 is the evaluator's pointer to its current-record pointer.
    sandbox.reg("x24", record_pointer_cell)
    sandbox.call(BLOCK)

    actual_denominator = sandbox.u32(record + DENOMINATOR_OFFSET)
    actual_room_count = sandbox.read(record + ROOM_COUNT_OFFSET, 1)[0]
    return {
        "selector": selector,
        "initial_denominator": initial_denominator,
        "actual_denominator": actual_denominator,
        "initial_room_count": initial_room_count,
        "actual_room_count": actual_room_count,
    }


def main():
    sandbox = Sandbox(NSO)

    def stop_after_switch(sb):
        # Entering in the middle of the evaluator leaves its caller's LR
        # unavailable; restore the sandbox stop address at the block boundary.
        sb.reg("x30", sb.STOP)
        return 0

    sandbox.stub(STOP_AFTER_SWITCH, stop_after_switch)
    expected = {
        2: (36, 1),
        3: (64, 1),
        4: (100, 2),
        5: (136, 3),
        6: (172, 4),
        7: (232, 5),
        8: (292, 6),
    }
    cases = []
    for selector, (denominator, room_count) in expected.items():
        case = run_case(sandbox, selector)
        case["expected_denominator"] = denominator
        case["expected_room_count"] = room_count
        case["match"] = (case["actual_denominator"] == denominator and
                         case["actual_room_count"] == room_count)
        cases.append(case)
        if not case["match"]:
            raise AssertionError(case)

    if any(case["actual_denominator"] <= 0 for case in cases):
        raise AssertionError("valid selector produced a nonpositive denominator")

    result = {
        "schema": "acnh-re/hha-house-area-denominator-native/1",
        "native_elf_sha256": hashlib.sha256(NSO.read_bytes()).hexdigest(),
        "native_block": {
            "start": hex(BLOCK),
            "stop_after_switch": hex(STOP_AFTER_SWITCH),
            "selector_stack_offset": hex(SELECTOR_STACK_OFFSET),
            "denominator_offset": hex(DENOMINATOR_OFFSET),
            "room_count_offset": hex(ROOM_COUNT_OFFSET),
        },
        "contract": (
            "For selectors 2..8, the native switch writes an area denominator "
            "to record +0x14c and a count to +0x154. The tested values are "
            "cumulative: 36, 64, 100, 136, 172, 232, 292; counts 1..6."
        ),
        "scope": (
            "This executes the original switch and field writes only. It begins "
            "after the preceding state lookup and HHAGradeMailFlag setter, and "
            "stops before helper 0x7b7c30. It does not identify the selector's "
            "source field or execute full HHA scoring/mail handling."
        ),
        "cases": len(cases),
        "mismatches": 0,
        "results": cases,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k != "results"}, indent=2))


if __name__ == "__main__":
    main()
