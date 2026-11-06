#!/usr/bin/env python3
"""Run the native break-action→counter-request chain on controlled state."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from nso_sandbox import Sandbox  # noqa: E402

NSO = ROOT / "inputs/additional_exefs/main"
OUT = ROOT / "output/gameplay/tool_mechanics_followup/tool_break_transition_native.json"
ENTRY = 0xE37830
SAVE_WRITER = 0xCE9340


def run():
    sandbox = Sandbox(NSO)
    obj = sandbox.alloc(0x1200)
    state = {"writer_enabled": 1}
    requests = []

    for address in (
        0xDAD700, 0xDA7B10, 0x15BBC00, 0xDA8BA0, 0xDA3FC0,
        0xDC9600, 0xDC94F0, 0xDAFEE0, 0xF589B0, 0xDA4020,
        0xF589E0, 0xEAD570, 0xEAD650, 0xEAD5D0,
        0xDADFE0, 0xDFD7E0, 0xDB5720, 0xDB4360, 0xF62E90,
    ):
        sandbox.stub(address, lambda _s: 0)
    sandbox.stub(0xEAACE0, lambda _s: state["writer_enabled"])

    def record_writer(sb):
        descriptor = sb.reg("x0")
        key_ptr = sb.u64(descriptor + 8)
        requests.append({
            "key": sb.read(key_ptr, 128).split(b"\0")[0].decode("ascii"),
            "amount": sb.reg("x1"),
        })
        return 0

    sandbox.stub(SAVE_WRITER, record_writer)
    cases = []

    # The outer byte selects BreakTool's nonzero branch. The adjacent byte is
    # read by E37950 as its context subtype (0, 1, 2, or out of range).
    for outer_branch, context_kind, writer_enabled in [
            (0, 0, 1),
            (1, 0, 0), (1, 0, 1),
            (1, 1, 1), (1, 2, 1), (1, 3, 1)]:
        state["writer_enabled"] = writer_enabled
        sandbox.uc.mem_write(obj + 0x1024, bytes([outer_branch]))
        sandbox.uc.mem_write(obj + 0x1025, bytes([context_kind]))
        start = len(requests)
        sandbox.call(ENTRY, (obj,))
        emitted = requests[start:]
        expected = ([{"key": "BreakToolCount", "amount": 1}]
                    if outer_branch and writer_enabled else [])
        if emitted != expected:
            raise AssertionError({"outer_branch": outer_branch,
                                  "context_kind": context_kind,
                                  "writer_enabled": writer_enabled,
                                  "emitted": emitted, "expected": expected})
        cases.append({
            "break_action_branch_byte": outer_branch,
            "counter_context_kind_byte": context_kind,
            "writer_enabled_by_controlled_eaace0_return": bool(writer_enabled),
            "writer_requests": emitted,
        })

    if sandbox.unknown_imports:
        raise AssertionError({"unexpected_imports": sandbox.unknown_imports})
    result = {
        "schema": "acnh-re/tool-break-transition-native/1",
        "native_elf_sha256": hashlib.sha256(NSO.read_bytes()).hexdigest(),
        "entry": hex(ENTRY),
        "native_chain": ["0xe37830 BreakTool action", "0xe37950 nonzero branch",
                         "0xda5450 counter wrapper", "0xce9340 save-writer boundary"],
        "cases": cases,
        "case_count": len(cases),
        "mismatches": 0,
        "dependencies_stubbed": [
            "animation/action context helpers and trailing state helpers",
            "0xeaace0 return is controlled to exercise DA5450's guard",
            "0xce9340 captures the requested key/increment; save storage is not executed",
        ],
        "proven": [
            "The original BreakTool action's zero branch does not enter the tested BreakToolCount chain.",
            "For its nonzero branch, original E37950 and DA5450 reach the writer boundary and request BreakToolCount += 1 when the controlled EAACE0 result is nonzero.",
            "A zero EAACE0 result suppresses that writer request; context-kind bytes 0, 1, 2, and out-of-range 3 do not alter the key/increment in these controlled cases.",
        ],
        "limits": [
            "Action context, animation, and EAACE0 outcome are synthetic; this is not an end-to-end player save run.",
            "CE9340's backing save mutation, actual tool-wear decrement, and break threshold remain unproven.",
        ],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({key: value for key, value in result.items() if key != "cases"}, indent=2))


if __name__ == "__main__":
    run()
