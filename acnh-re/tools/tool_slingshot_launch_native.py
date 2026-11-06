#!/usr/bin/env python3
"""Run the native slingshot launch handoff with controlled projectile methods."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
import struct
import sys

from unicorn import UC_HOOK_CODE

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from nso_sandbox import NSO_SHA256, Sandbox  # noqa: E402

DEFAULT_RESEARCH_OUTPUT = Path("/workspace/acnh-re/output")
LAUNCH_HANDOFF = 0x803690
PLAYER_SLINGSHOT_SHOOTING = 0xE564B0
PROJECTILE_OUTPUT_HELPER = 0x29AC0
PROJECTILE_LAUNCH_DISPATCH = 0x1F068D0


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def static_callsite(research_output: Path) -> dict:
    with sqlite3.connect(research_output / "index.sqlite") as db:
        rows = db.execute(
            "SELECT owner_va, pc FROM direct_calls "
            "WHERE owner_va=? AND target_va=?",
            (PLAYER_SLINGSHOT_SHOOTING, LAUNCH_HANDOFF),
        ).fetchall()
    expected = [(PLAYER_SLINGSHOT_SHOOTING, 0xE567C0)]
    if rows != expected:
        raise AssertionError(f"slingshot launch callsite changed: {rows}")
    return {"owner_va": hex(rows[0][0]), "call_pc": hex(rows[0][1]),
            "target_va": hex(LAUNCH_HANDOFF)}


def float_words(values: tuple[float, float, float]) -> bytes:
    return struct.pack("<3f", *values)


def run(research_output: Path, nso_path: Path, output: Path) -> dict:
    if sha256(nso_path.read_bytes()) != NSO_SHA256:
        raise ValueError("main NSO does not match the indexed 1.0.0 image")
    callsite = static_callsite(research_output)
    sandbox = Sandbox(nso_path)

    state = sandbox.alloc(0x300)
    projectile = sandbox.alloc(0x100)
    vtable = sandbox.alloc(0x200)
    projectile_output = sandbox.alloc(0x40)
    start_pointer = sandbox.alloc(0x10)
    velocity_pointer = sandbox.alloc(0x10)
    sandbox.uc.mem_write(projectile, struct.pack("<Q", vtable))
    sandbox.uc.mem_write(vtable + 0xF8,
                         struct.pack("<Q", PROJECTILE_OUTPUT_HELPER))
    sandbox.uc.mem_write(state + 0x68, struct.pack("<Q", projectile))

    dispatches: list[dict] = []
    output_helper_calls: list[int] = []

    def controlled_output(sb: Sandbox) -> int:
        output_helper_calls.append(sb.reg("x0"))
        if sb.reg("x0") == projectile:
            return projectile_output
        return sb.reg("x0")

    def capture_dispatch(sb: Sandbox) -> int:
        dispatches.append({"state_pointer": sb.reg("x0"),
                           "launch_flag": sb.reg("x1") & 0xFFFFFFFF})
        return 0

    sandbox.stub(PROJECTILE_OUTPUT_HELPER, controlled_output)
    sandbox.stub(PROJECTILE_LAUNCH_DISPATCH, capture_dispatch)
    entries = {LAUNCH_HANDOFF: 0, PROJECTILE_OUTPUT_HELPER: 0,
               PROJECTILE_LAUNCH_DISPATCH: 0}

    def count_entries(_uc, address, _size, _user_data):
        entries[address] += 1

    for va in entries:
        sandbox.uc.hook_add(UC_HOOK_CODE, count_entries, begin=va, end=va)

    vectors = [
        {"start": (10.5, -2.25, 0.125), "velocity": (1.5, -2.0, 0.25)},
        {"start": (-1.0, 0.0, 3.75), "velocity": (-0.5, 4.0, 0.0)},
    ]
    cases = []
    for index, vector in enumerate(vectors):
        start_bytes = float_words(vector["start"])
        velocity_bytes = float_words(vector["velocity"])
        sandbox.uc.mem_write(state, bytes(0x300))
        sandbox.uc.mem_write(state + 0x68, struct.pack("<Q", projectile))
        sandbox.uc.mem_write(projectile_output, bytes(0x40))
        sandbox.uc.mem_write(start_pointer, start_bytes)
        sandbox.uc.mem_write(velocity_pointer, velocity_bytes)
        dispatch_start = len(dispatches)
        helper_start = len(output_helper_calls)
        try:
            sandbox.call(LAUNCH_HANDOFF,
                         (state, start_pointer, velocity_pointer))
        except Exception as exc:
            raise RuntimeError(
                f"native slingshot handoff failed at pc={sandbox.reg('pc'):#x}, "
                f"lr={sandbox.reg('x30'):#x}, args="
                f"{[hex(sandbox.reg(f'x{i}')) for i in range(6)]}"
            ) from exc

        projectile_start = sandbox.read(projectile_output, 12)
        state_start = sandbox.read(state + 0x280, 12)
        scaled_velocity = sandbox.read(state + 0x274, 12)
        decoded_start = struct.unpack("<3f", state_start)
        decoded_velocity = struct.unpack("<3f", scaled_velocity)
        expected_velocity = tuple(value * 6.0 for value in vector["velocity"])
        case_dispatches = dispatches[dispatch_start:]
        case_helper_calls = output_helper_calls[helper_start:]
        if projectile_start != start_bytes or state_start != start_bytes:
            raise AssertionError({"case": index, "start": vector["start"],
                                  "projectile_start": projectile_start.hex(),
                                  "state_start": state_start.hex()})
        if decoded_velocity != expected_velocity:
            raise AssertionError({"case": index, "velocity": vector["velocity"],
                                  "actual_scaled_velocity": decoded_velocity,
                                  "expected_scaled_velocity": expected_velocity})
        if case_helper_calls != [projectile, state]:
            raise AssertionError({"case": index,
                                  "output_helper_inputs": case_helper_calls})
        if case_dispatches != [{"state_pointer": state, "launch_flag": 1}]:
            raise AssertionError({"case": index,
                                  "launch_dispatches": case_dispatches})
        cases.append({
            "case": index,
            "start_vector": vector["start"],
            "velocity_vector": vector["velocity"],
            "projectile_output_start_hex": projectile_start.hex(),
            "state_start_hex": state_start.hex(),
            "state_scaled_velocity": decoded_velocity,
            "scale_factor": 6.0,
            "launch_dispatch_flag": 1,
        })

    if sandbox.unknown_imports:
        raise AssertionError(f"unexpected native imports: {sandbox.unknown_imports}")
    result = {
        "schema": "acnh-re/tool-slingshot-launch-native/1",
        "native_elf_sha256": sha256(nso_path.read_bytes()),
        "static_callsite": callsite,
        "launch_handoff_va": hex(LAUNCH_HANDOFF),
        "native_functions_executed": [
            "0x803690 original launch handoff instructions",
            "controlled output-method and launch-dispatch boundaries",
        ],
        "native_functions_stubbed": [
            "0x29ac0 supplies the projectile output record and intercepts the post-write helper",
            "0x1f068d0 captures the launch-dispatch flag; projectile creation and physics are outside this harness",
        ],
        "cases": cases,
        "case_count": len(cases),
        "native_function_entry_counts": {
            hex(va): entries[va] for va in sorted(entries)
        },
        "mismatches": 0,
        "unresolved_imports": sandbox.unknown_imports,
        "proven": [
            "PlayerSlingshotShooting directly calls 0x803690 at 0xe567c0.",
            "The native handoff copies the input start vector into the projectile output record and player-state offsets +0x280..+0x288.",
            "The native handoff scales all three supplied velocity components by 6 and records launch flag 1 for the downstream dispatch.",
        ],
        "limits": [
            "The projectile output accessor and downstream launch dispatch are controlled boundaries.",
            "This does not run projectile creation, collision, balloon-item drops, or inventory/save persistence.",
        ],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({key: value for key, value in result.items()
                      if key != "cases"}, indent=2, ensure_ascii=False))
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--research-output", type=Path,
                        default=DEFAULT_RESEARCH_OUTPUT)
    parser.add_argument("--nso", type=Path,
                        default=ROOT / "inputs/additional_exefs/main")
    parser.add_argument("--output", type=Path,
                        default=ROOT / "output/gameplay/tool_mechanics_followup/"
                        "tool_slingshot_launch_native.json")
    args = parser.parse_args()
    run(args.research_output, args.nso, args.output)


if __name__ == "__main__":
    main()
