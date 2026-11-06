#!/usr/bin/env python3
"""Exercise the native BreakTool action branches at their helper boundaries."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from nso_sandbox import Sandbox  # noqa: E402

NSO = ROOT / "inputs/additional_exefs/main"
OUT = ROOT / "output/gameplay/tool_mechanics_followup/tool_break_action_native.json"
ENTRY = 0xE37830
ACHIEVEMENT_HELPER = 0xF62E90
COUNT_HELPER = 0xE37950


def run():
    sandbox = Sandbox(NSO)
    obj = sandbox.alloc(0x1200)
    calls = []

    def record_helper(name):
        def callback(sb):
            record = {"helper": name}
            if name == "F62E90":
                descriptor = sb.reg("x1")
                key_ptr = sb.u64(descriptor + 8)
                record.update({
                    "key": sb.read(key_ptr, 128).split(b"\0")[0].decode("ascii"),
                    "amount": sb.reg("x2"),
                })
            elif name == "E37950":
                record.update({"arg0": hex(sb.reg("x0")), "arg1": hex(sb.reg("x1"))})
            calls.append(record)
            return 0
        return callback

    for address in (0xDAD700, 0xDA7B10, 0x15BBC00, 0xDA8BA0, 0xDA3FC0,
                    0xDADFE0, 0xDFD7E0, 0xDB5720, 0xDB4360):
        sandbox.stub(address, lambda _sb: 0)
    sandbox.stub(ACHIEVEMENT_HELPER, record_helper("F62E90"))
    sandbox.stub(COUNT_HELPER, record_helper("E37950"))

    cases = []
    for branch_byte in (0, 1):
        sandbox.uc.mem_write(obj + 0x1024, bytes([branch_byte]))
        sandbox.uc.mem_write(obj + 0x898, (0x12345678).to_bytes(4, "little"))
        sandbox.uc.mem_write(obj + 0x89C, b"\x01")
        start = len(calls)
        sandbox.call(ENTRY, (obj,))
        emitted = calls[start:]
        expected_helper = "F62E90" if branch_byte == 0 else "E37950"
        if [entry["helper"] for entry in emitted] != [expected_helper]:
            raise AssertionError({"branch_byte": branch_byte, "helpers": emitted})
        if branch_byte == 0 and emitted[0] != {
            "helper": "F62E90", "key": "BreakTool", "amount": 1
        }:
            raise AssertionError({"branch_byte": branch_byte, "request": emitted[0]})
        if sandbox.u32(obj + 0x898) != 0 or sandbox.read(obj + 0x89C, 1) != b"\0":
            raise AssertionError({"branch_byte": branch_byte, "state_fields_not_cleared": True})
        cases.append({
            "branch_byte": branch_byte,
            "helper_boundary_calls": emitted,
            "state_offset_0x898_after": sandbox.u32(obj + 0x898),
            "state_offset_0x89c_after": sandbox.read(obj + 0x89C, 1)[0],
        })

    if sandbox.unknown_imports:
        raise AssertionError({"unexpected_imports": sandbox.unknown_imports})
    result = {
        "schema": "acnh-re/tool-break-action-native/1",
        "native_elf_sha256": hashlib.sha256(NSO.read_bytes()).hexdigest(),
        "entry": hex(ENTRY),
        "cases": cases,
        "case_count": len(cases),
        "mismatches": 0,
        "dependencies_stubbed": [
            "0xdad700, 0xda7b10, 0x15bbc00 action-context helpers",
            "0xda8ba0, 0xda3fc0 and 0xe37950 nonzero-branch context path",
            "0xf62e90 achievement request boundary",
            "0xdadfe0, 0xdfd7e0, 0xdb5720, 0xdb4360 trailing state helpers",
        ],
        "proven": [
            "The native zero branch requests BreakTool += 1 through 0xf62e90.",
            "The native nonzero branch dispatches to 0xe37950.",
            "Both branches clear the state-local fields at +0x898 and +0x89c.",
        ],
        "remaining": [
            "The 0xe37950 context chain was not executed end-to-end here; 0xda5450 was separately tested at its writer boundary.",
            "No inventory item mutation, per-item use decrement, or break threshold is established.",
            "The save-backed behavior behind 0xf62e90 remains unexecuted.",
        ],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({key: value for key, value in result.items() if key != "cases"}, indent=2))


if __name__ == "__main__":
    run()
