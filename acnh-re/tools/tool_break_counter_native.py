#!/usr/bin/env python3
"""Run the native BreakToolCount request wrapper at its generic save boundary."""
import hashlib
import json
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from nso_sandbox import Sandbox  # noqa: E402

NSO = ROOT / "inputs/additional_exefs/main"
OUT = ROOT / "output/gameplay/tool_mechanics_followup/tool_break_counter_native.json"
ENTRY = 0xDA5450
SAVE_WRITER = 0xCE9340


def run():
    sandbox = Sandbox(NSO)
    frame = sandbox.alloc(8)
    calls = []
    for address in (0xEAD570, 0xEAD650, 0xEAD5D0):
        sandbox.stub(address, lambda s: 0)

    def record_writer(s):
        descriptor = s.reg("x0")
        key_ptr = s.u64(descriptor + 8)
        key = s.read(key_ptr, 128).split(b"\0")[0].decode("ascii")
        calls.append({"key": key, "amount": s.reg("x1"), "value_context": s.reg("x2")})
        return 0

    sandbox.stub(SAVE_WRITER, record_writer)
    cases = []
    for flag, payload in ((0, b"\x11\x22\x33"), (1, b"\x04\x05\x06"), (2, b"\x07\x08\x09")):
        sandbox.uc.mem_write(frame, bytes([flag]) + payload + b"\0" * 4)
        start = len(calls)
        sandbox.call(ENTRY, (frame,))
        emitted = calls[start:]
        expected_count = 1 if flag != 0 else 0
        if len(emitted) != expected_count:
            raise AssertionError({"flag": flag, "emitted": emitted, "expected_count": expected_count})
        if emitted and (emitted[0]["key"] != "BreakToolCount" or emitted[0]["amount"] != 1):
            raise AssertionError({"flag": flag, "emitted": emitted})
        cases.append({"input_flag": flag, "writer_requests": emitted})

    if sandbox.unknown_imports:
        raise AssertionError({"unexpected_imports": sandbox.unknown_imports})
    result = {
        "schema": "acnh-re/tool-break-counter-native/1",
        "native_elf_sha256": hashlib.sha256(NSO.read_bytes()).hexdigest(),
        "entry": hex(ENTRY),
        "native_contract": "DA5450 returns without a save-writer request when the descriptor's first byte is zero. For nonzero input, its original instructions construct the key BreakToolCount and request increment 1 through CE9340.",
        "static_callers": [
            {"caller": "0xe37950", "context": "called by the PlayerToolBreak/BreakTool action transition at 0xe37a50/0xe37830"},
            {"caller": "0xe45b80", "context": "Net get-demo state; caller-dependent guard data controls whether the wrapper emits"},
            {"caller": "0xe4e730", "context": "Rod get-demo state; caller-dependent guard data controls whether the wrapper emits"}
        ],
        "cases": cases,
        "case_count": len(cases),
        "mismatches": 0,
        "dependencies_stubbed": ["0xead570", "0xead650", "0xead5d0 input descriptor helpers", "0xce9340 generic save writer boundary"],
        "remaining": ["The CE9340/CE9390 backed field mutation was not executed", "BreakToolCount semantics and its relationship to inventory durability remain unproven", "No per-item use decrement or break threshold is established"],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({key: value for key, value in result.items() if key != "cases"}, indent=2))


if __name__ == "__main__":
    run()
