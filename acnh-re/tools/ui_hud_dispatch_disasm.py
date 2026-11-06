#!/usr/bin/env python3
"""Disassemble UI component-dispatch candidates from the supplied main NSO.

Uses the local LLVM C disassembler so this narrow UI audit does not depend on
the optional Capstone package used by re_helpers.py's general disasm command.
It reads only the local index, trace JSON, and `inputs/additional_exefs/main`.
"""
from __future__ import annotations

import argparse
import ctypes
import ctypes.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import re_helpers  # noqa: E402


def load_llvm():
    names = [ctypes.util.find_library("LLVM-19"), ctypes.util.find_library("LLVM"), "libLLVM.so.19.1"]
    error = None
    for name in dict.fromkeys(n for n in names if n):
        try:
            lib = ctypes.CDLL(name)
            for symbol in (
                "LLVMInitializeAArch64TargetInfo",
                "LLVMInitializeAArch64Target",
                "LLVMInitializeAArch64TargetMC",
                "LLVMInitializeAArch64Disassembler",
            ):
                init = getattr(lib, symbol)
                init.argtypes = []
                init.restype = None
                init()
            create = lib.LLVMCreateDisasm
            create.argtypes = [ctypes.c_char_p, ctypes.c_void_p, ctypes.c_int,
                               ctypes.c_void_p, ctypes.c_void_p]
            create.restype = ctypes.c_void_p
            disasm = lib.LLVMDisasmInstruction
            disasm.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t,
                               ctypes.c_uint64, ctypes.c_void_p, ctypes.c_size_t]
            disasm.restype = ctypes.c_size_t
            dispose = lib.LLVMDisasmDispose
            dispose.argtypes = [ctypes.c_void_p]
            dispose.restype = None
            context = create(b"aarch64-unknown-linux-gnu", None, 0, None, None)
            if not context:
                raise RuntimeError("LLVM did not create an AArch64 disassembly context")
            return lib, context, disasm, dispose
        except (OSError, AttributeError, RuntimeError) as exc:
            error = exc
    raise RuntimeError(f"local LLVM AArch64 disassembler is unavailable: {error}")


def default_targets(output_root: Path):
    import json

    trace = json.loads((output_root / "native_ui_traces.json").read_text())
    candidates = trace["focus_and_action_dispatch"]["ui_component_dispatch"]
    obs = candidates["pointer_array_candidates"]["followup_target_body_observations"]
    rows = obs["return_only_candidates"] + obs["nontrivial_candidates"]
    return sorted({(int(row["target_va"], 16), row["size_bytes"]) for row in rows})


def disassemble(va: int, size: int, data: bytes, context, llvm_disasm) -> list[str]:
    lines = []
    offset = 0
    while offset < size:
        out = ctypes.create_string_buffer(192)
        consumed = llvm_disasm(context, ctypes.c_char_p(data[offset:]), size - offset,
                               va + offset, out, len(out))
        if not consumed:
            lines.append(f"{va + offset:#x}  <undecoded>")
            break
        lines.append(f"{va + offset:#x}  {out.value.decode(errors='replace')}")
        offset += consumed
    return lines


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", nargs="*", help="function target as VA:SIZE (both hexadecimal)")
    parser.add_argument("--output-root", type=Path, default=ROOT / "output/ui_hud",
                        help="directory containing native_ui_traces.json")
    args = parser.parse_args()
    targets = []
    if args.target:
        for spec in args.target:
            va, size = spec.split(":", 1)
            targets.append((int(va, 16), int(size, 16)))
    else:
        targets = default_targets(args.output_root)

    segments = re_helpers.nso_segments(ROOT / "inputs/additional_exefs/main")
    _, context, llvm_disasm, dispose = load_llvm()
    try:
        for va, size in targets:
            data = re_helpers._read(segments, va, size)
            print(f"\n{va:#x} size={size}")
            print("\n".join(disassemble(va, size, data, context, llvm_disasm)))
    finally:
        dispose(context)


if __name__ == "__main__":
    main()
