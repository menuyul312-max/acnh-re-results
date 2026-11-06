#!/usr/bin/env python3
"""Run ACNH's native rectangle transform on synthetic UI viewport fixtures."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import struct

from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM
from unicorn.arm64_const import (
    UC_ARM64_REG_PC, UC_ARM64_REG_SP, UC_ARM64_REG_X0, UC_ARM64_REG_X1,
    UC_ARM64_REG_X2, UC_ARM64_REG_X30,
)

import re_helpers

ROOT = Path(__file__).resolve().parent.parent
NSO = ROOT / "inputs/additional_exefs/main"
OUTPUT = ROOT / "output/ui_hud/runtime_followup/scissor_coordinate_native.json"
TRANSFORM = 0x19A9A80
RECT_ADDR = 0x40000000
OUT_ADDR = RECT_ADDR + 0x100
VIEWPORT_ADDR = RECT_ADDR + 0x200
STACK_TOP = 0x50008000
RETURN_ADDR = 0x50000000


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def native_transform(uc: Uc, mode: int, rect: tuple[float, float, float, float],
                     viewport: tuple[float, float, float, float, float, float]) -> tuple[float, float]:
    rect_mem = bytearray(0x30)
    struct.pack_into("<4f", rect_mem, 0x08, *rect)
    struct.pack_into("<I", rect_mem, 0x18, mode)
    viewport_mem = bytearray(0x30)
    struct.pack_into("<6f", viewport_mem, 0x08, *viewport)
    uc.mem_write(RECT_ADDR, bytes(rect_mem))
    uc.mem_write(VIEWPORT_ADDR, bytes(viewport_mem))
    uc.reg_write(UC_ARM64_REG_X0, RECT_ADDR)
    uc.reg_write(UC_ARM64_REG_X1, OUT_ADDR)
    uc.reg_write(UC_ARM64_REG_X2, VIEWPORT_ADDR)
    uc.reg_write(UC_ARM64_REG_SP, STACK_TOP)
    uc.reg_write(UC_ARM64_REG_X30, RETURN_ADDR)
    uc.reg_write(UC_ARM64_REG_PC, TRANSFORM)
    uc.emu_start(TRANSFORM, RETURN_ADDR, count=1000)
    return struct.unpack("<2f", uc.mem_read(OUT_ADDR, 8))


def main() -> None:
    rect = (10.0, 20.0, 40.0, 60.0)  # left, top, right, bottom
    viewport = (100.0, 200.0, 5.0, 7.0, 205.0, 407.0)
    expected_pixels = {
        0: (25.0, 47.0),
        1: (45.0, 327.0),
        2: (85.0, 27.0),
        3: (125.0, 287.0),
        4: (125.0, 47.0),
        5: (25.0, 287.0),
    }
    operations = {
        0: "identity",
        1: "counter-clockwise rotation",
        2: "clockwise rotation",
        3: "180-degree rotation",
        4: "horizontal reflection",
        5: "vertical reflection",
    }

    uc = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
    segments = re_helpers.nso_segments(NSO)
    for base, data in segments:
        map_start = base & ~0xFFF
        map_end = (base + len(data) + 0xFFF) & ~0xFFF
        uc.mem_map(map_start, map_end - map_start)
        uc.mem_write(base, data)
    uc.mem_map(RECT_ADDR, 0x10000)
    uc.mem_map(RETURN_ADDR, 0x10000)

    checks = []
    for mode, expected in expected_pixels.items():
        actual = native_transform(uc, mode, rect, viewport)
        passed = all(abs(a - e) < 1e-4 for a, e in zip(actual, expected))
        checks.append({"mode": mode, "derived_operation": operations[mode],
                       "expected_target_pixel_origin": list(expected),
                       "native_target_pixel_origin": [round(v, 6) for v in actual],
                       "passed": passed})
    mismatches = [check for check in checks if not check["passed"]]
    result = {
        "schema": "acnh.ui_hud_runtime_followup.scissor_coordinate_native.v1",
        "source": {"game_build": "ACNH 1.0.0", "module": "ExeFS main",
                   "main_sha256": sha256_file(NSO),
                   "native_function": hex(TRANSFORM),
                   "evidence_kind": "Original AArch64 instructions executed in Unicorn with controlled rectangle/viewport memory; no game capture."},
        "fixture": {"source_rect_ltrb": list(rect), "viewport_logical_wh_and_target_ltrb": list(viewport),
                    "target_pixel_bounds": [5.0, 7.0, 205.0, 407.0]},
        "coordinate_modes": {"derived_operations": operations,
                             "label_limit": "The geometric operation is formula-derived; the game's enum names for values 0–5 remain unknown."},
        "checks": checks,
        "mismatches": len(mismatches),
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"artifact": str(OUTPUT), "checks": len(checks),
                      "mismatches": len(mismatches), "mismatch_modes": [x["mode"] for x in mismatches]}, indent=2))
    if mismatches:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
