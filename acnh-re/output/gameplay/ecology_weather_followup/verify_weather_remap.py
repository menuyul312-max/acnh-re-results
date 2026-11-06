#!/usr/bin/env python3
"""Re-run and check the committed 96-case native weather remap artifact.

Run from any directory with:
    python3 /path/to/verify_weather_remap.py

Requires the repository's additional ExeFS main and Unicorn/pyelftools. The
runner searches ACNH_RE_DEPS, the repository-local .deps, then the shared
analysis environment at /workspace/acnh-re/.deps. Set ACNH_RE_DEPS when the
dependencies are installed elsewhere.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import struct
import sys
from collections import Counter


SCRIPT = Path(__file__).resolve()
REPO = SCRIPT.parents[4]
TOOLS = REPO / "acnh-re" / "tools"
ARTIFACT = SCRIPT.with_name("weather_remap_native.json")
MAIN = REPO / "acnh-re" / "inputs" / "additional_exefs" / "main"


def add_dependency_paths() -> None:
    candidates = [
        os.environ.get("ACNH_RE_DEPS"),
        str(REPO / "acnh-re" / ".deps"),
        "/workspace/acnh-re/.deps",
    ]
    for candidate in candidates:
        if candidate:
            path = Path(candidate)
            if path.is_dir() and str(path) not in sys.path:
                sys.path.insert(0, str(path))
    if str(TOOLS) not in sys.path:
        sys.path.insert(0, str(TOOLS))


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run() -> dict:
    add_dependency_paths()
    try:
        from native_emulator import Sandbox, regs
        from unicorn import UC_HOOK_CODE
    except ModuleNotFoundError as exc:
        raise SystemExit(
            "Missing native-emulation dependency. Install requirements-native.txt "
            "or set ACNH_RE_DEPS to a directory containing Unicorn and pyelftools."
        ) from exc

    if not MAIN.is_file():
        raise SystemExit(f"Missing ExeFS main: {MAIN}")
    if not ARTIFACT.is_file():
        raise SystemExit(f"Missing expected result artifact: {ARTIFACT}")
    expected = json.loads(ARTIFACT.read_text())

    sandbox = Sandbox()
    uc = sandbox.uc
    world = sandbox.HEAP + 0x80000
    pointers = sandbox.HEAP + 0x10000
    table_entry = sandbox.HEAP + 0x11000
    hour_array = sandbox.HEAP + 0x12000
    parameter_vtable = sandbox.HEAP + 0x13000
    fake_getter = sandbox.STOP + 0x100

    def write_u64(address: int, value: int) -> None:
        uc.mem_write(address, struct.pack("<Q", value))

    def write_u32(address: int, value: int) -> None:
        uc.mem_write(address, struct.pack("<I", value))

    def write_u8(address: int, value: int) -> None:
        uc.mem_write(address, bytes([value]))

    write_u32(world + 0x653B0, 1)
    write_u32(world + 0x100, 1)
    write_u64(world + 0x108, pointers)
    write_u64(pointers, table_entry)
    write_u64(table_entry + 0xD8, hour_array)

    for hour in range(24):
        parameter = sandbox.HEAP + 0x14000 + hour * 0x20
        value = sandbox.HEAP + 0x15000 + hour * 0x10
        write_u64(hour_array + hour * 8, parameter)
        write_u64(parameter, parameter_vtable)
        write_u64(parameter + 8, value)
        write_u32(value, hour % 8)

    write_u64(parameter_vtable + 0xF0, fake_getter)
    write_u8(world + 0x651DA, 1)
    write_u8(world + 0x651DB, 1)

    controls = {
        "snow_term": 0,
        "table_index": 0,
        "stub_calls": Counter(),
        "target_calls": Counter(),
    }

    def controlled_dependency(engine, address, size, user_data) -> None:
        x0 = engine.reg_read(regs.UC_ARM64_REG_X0)
        return_address = engine.reg_read(regs.UC_ARM64_REG_X30)
        if address == 0x201B90:
            controls["stub_calls"]["0x201b90"] += 1
            result = controls["table_index"]
        elif address == 0x202490:
            controls["stub_calls"]["0x202490"] += 1
            result = controls["snow_term"]
        elif address == fake_getter:
            controls["stub_calls"]["synthetic_vtable_getter"] += 1
            result = struct.unpack("<Q", bytes(engine.mem_read(x0 + 8, 8)))[0]
        else:
            return
        engine.reg_write(regs.UC_ARM64_REG_X0, result)
        engine.reg_write(regs.UC_ARM64_REG_PC, return_address)

    for address in (0x201B90, 0x202490, fake_getter):
        uc.hook_add(UC_HOOK_CODE, controlled_dependency, begin=address, end=address)

    def count_target_entry(engine, address, size, user_data) -> None:
        controls["target_calls"][hex(address)] += 1

    uc.hook_add(UC_HOOK_CODE, count_target_entry, begin=0x204480, end=0x204480)
    uc.hook_add(UC_HOOK_CODE, count_target_entry, begin=0x204590, end=0x204590)

    cases = []
    mismatches = []
    direct_calls = 0
    wrapper_calls = 0
    for snow_term in (0, 1):
        controls["snow_term"] = snow_term
        for hour in range(24):
            raw_code = hour % 8
            expected_code = {4: 6, 5: 7}.get(raw_code, raw_code) if snow_term else raw_code
            direct_calls += 1
            effective_code = sandbox.call(0x204480, (world, hour), limit=200_000) & 0xFFFFFFFF
            wrapper_calls += 1
            rain_predicate = sandbox.call(0x204590, (world, hour), limit=200_000) & 1
            expected_rain = (expected_code | 1) == 5
            cases.append({
                "hour": hour,
                "controlled_pattern_code": raw_code,
                "snow_predicate": bool(snow_term),
                "effective_code": effective_code,
                "rain_predicate_0x204590": bool(rain_predicate),
            })
            if effective_code != expected_code:
                mismatches.append({"function": "0x204480", "hour": hour,
                                   "snow_predicate": snow_term, "actual": effective_code,
                                   "expected": expected_code})
            if bool(rain_predicate) != expected_rain:
                mismatches.append({"function": "0x204590", "hour": hour,
                                   "snow_predicate": snow_term, "actual": bool(rain_predicate),
                                   "expected": expected_rain})

    def code_result(snow: bool, code: int, field: str):
        return next(case[field] for case in cases
                    if case["snow_predicate"] is snow and case["controlled_pattern_code"] == code)

    observed_matrix = {
        "input_codes": list(range(8)),
        "snow_predicate_false": [code_result(False, code, "effective_code") for code in range(8)],
        "snow_predicate_true": [code_result(True, code, "effective_code") for code in range(8)],
        "rain_gate_false": [code_result(False, code, "rain_predicate_0x204590") for code in range(8)],
        "rain_gate_true": [code_result(True, code, "rain_predicate_0x204590") for code in range(8)],
    }

    checks = {
        "native_elf_sha256": sha256_bytes(sandbox.image.data),
        "input_main_sha256": sha256_file(MAIN),
        "cases": cases,
        "matrix": observed_matrix,
        "mismatches": mismatches,
        "target_entries": controls["target_calls"].get("0x204480", 0),
        "wrapper_entries": controls["target_calls"].get("0x204590", 0),
        "stub_calls": controls["stub_calls"],
    }

    if checks["native_elf_sha256"] != expected["native_elf_sha256"]:
        raise SystemExit("ELF checksum differs from the committed artifact")
    if checks["input_main_sha256"] != expected["input_main_sha256"]:
        raise SystemExit("ExeFS main checksum differs from the committed artifact")
    execution = expected["execution"]
    if execution["cases"] != cases:
        raise SystemExit("Replayed cases differ from weather_remap_native.json")
    if execution["code_matrix"] != observed_matrix:
        raise SystemExit("Replayed code matrix differs from weather_remap_native.json")
    if execution["comparisons"] != len(cases) * 2 or mismatches:
        raise SystemExit(f"Native comparison failed: {mismatches[:4]}")
    if execution["0x204480_direct_calls"] != direct_calls:
        raise SystemExit("Direct 0x204480 call count differs from the committed artifact")
    if execution["0x204480_calls_via_0x204590"] != wrapper_calls:
        raise SystemExit("Wrapped 0x204480 call count differs from the committed artifact")
    if execution["0x204480_total_entries"] != checks["target_entries"]:
        raise SystemExit("0x204480 entry count differs from the committed artifact")
    if execution["0x204590_calls"] != checks["wrapper_entries"]:
        raise SystemExit("0x204590 call count differs from the committed artifact")
    if controls["stub_calls"] != Counter({
        "0x201b90": 96,
        "0x202490": 96,
        "synthetic_vtable_getter": 96,
    }):
        raise SystemExit(f"Unexpected controlled dependency call counts: {controls['stub_calls']}")

    return {
        "status": "pass",
        "artifact": str(ARTIFACT),
        "artifact_sha256": sha256_file(ARTIFACT),
        "runner_sha256": sha256_file(SCRIPT),
        "input_main_sha256": checks["input_main_sha256"],
        "native_elf_sha256": checks["native_elf_sha256"],
        "0x204480_entries": checks["target_entries"],
        "0x204590_entries": checks["wrapper_entries"],
        "comparisons": execution["comparisons"],
        "mismatches": len(mismatches),
        "controlled_dependencies": controls["stub_calls"],
    }


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2))
