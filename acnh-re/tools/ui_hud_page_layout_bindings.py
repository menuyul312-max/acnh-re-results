#!/usr/bin/env python3
"""Resolve page slot-46 string getters against the local BFLYT screen catalog.

This is a static identifier crosswalk only: it does not establish which page
manager calls the getter, whether that name is passed to a loader, or whether a
matching layout is ever instantiated or rendered at runtime.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import re
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import re_helpers  # noqa: E402
from ui_hud_dispatch_disasm import disassemble, load_llvm  # noqa: E402


def read_virtual(segments, address: int, size: int) -> bytes:
    return re_helpers._read(segments, address, size)


def relative_relocations(segments) -> dict[int, int]:
    text_base, text = segments[0]
    mod0 = text_base + struct.unpack_from("<I", text, 4)[0]
    magic, dynamic_offset = struct.unpack("<4si", read_virtual(segments, mod0, 8))
    if magic != b"MOD0":
        raise ValueError("MOD0 header was not present in the main NSO")

    dynamic = mod0 + dynamic_offset
    tags: dict[int, int] = {}
    for index in range(512):
        tag, value = struct.unpack("<qQ", read_virtual(segments, dynamic + index * 16, 16))
        if tag == 0:
            break
        tags[tag] = value

    result: dict[int, int] = {}
    for relocation_address, relocation_size in (
        (tags.get(7, 0), tags.get(8, 0)),
        (tags.get(23, 0), tags.get(2, 0)),
    ):
        for index in range(relocation_size // 24):
            slot, info, addend = struct.unpack(
                "<QQq", read_virtual(segments, relocation_address + index * 24, 24)
            )
            relocation_type = info & 0xFFFFFFFF
            symbol_index = info >> 32
            if relocation_type == 0x403 and symbol_index == 0:  # R_AARCH64_RELATIVE
                result[slot] = addend & 0xFFFFFFFFFFFFFFFF
    return result


def getter_target(target: int, segments, context, llvm_disasm) -> tuple[int, list[str]]:
    lines = disassemble(target, 12, read_virtual(segments, target, 12), context, llvm_disasm)
    instructions = [line.split("  ", 1)[1].strip() for line in lines]
    if len(instructions) != 3 or instructions[2] != "ret":
        raise ValueError(f"slot target {target:#x} was not a 3-instruction string getter: {instructions}")

    adrp = re.fullmatch(r"adrp\s+x0, #(-?\d+)", instructions[0])
    add = re.fullmatch(r"add\s+x0, x0, #(-?\d+)", instructions[1])
    if not adrp or not add:
        raise ValueError(f"slot target {target:#x} has an unexpected getter body: {instructions}")
    string_address = (target & ~0xFFF) + int(adrp.group(1)) + int(add.group(1))
    return string_address, instructions


def direct_branch_reference_counts(segments, targets: set[int]) -> dict[int, int]:
    """Count AArch64 direct B/BL instructions in the executable text segment."""
    base, text = segments[0]
    word_count = len(text) // 4
    words = struct.unpack(f"<{word_count}I", text[:word_count * 4])
    counts: Counter[int] = Counter()
    for index, word in enumerate(words):
        opcode = word & 0xFC000000
        if opcode not in (0x14000000, 0x94000000):  # B or BL, immediate
            continue
        immediate = word & 0x03FFFFFF
        if immediate & (1 << 25):
            immediate -= 1 << 26
        target = base + index * 4 + (immediate << 2)
        if target in targets:
            counts[target] += 1
    return dict(counts)


def build_bindings(output_root: Path, nso_path: Path) -> dict:
    factory_path = output_root / "page_factory_catalog.json"
    screens_path = output_root / "screen_catalog.json"
    factories = json.loads(factory_path.read_text())
    screens = json.loads(screens_path.read_text())
    layouts = {row["name"]: row for row in screens["layouts"]}
    segments = re_helpers.nso_segments(nso_path)
    relocations = relative_relocations(segments)
    _, context, llvm_disasm, dispose = load_llvm()

    entries = []
    try:
        for page in factories["pages"]:
            address_point = int(page["vtable_address_point_va"], 16)
            registry_slot_17_target = relocations.get(address_point + 17 * 8)
            registry_slot_30_target = relocations.get(address_point + 30 * 8)
            if registry_slot_17_target is None or registry_slot_30_target is None:
                raise ValueError(f"missing shared registry slot relocation for {page['class_name']}")
            slot_index = 46
            relocation_slot = address_point + slot_index * 8
            target = relocations.get(relocation_slot)
            if target is None:
                raise ValueError(f"missing relative relocation at {relocation_slot:#x}")
            string_address, instructions = getter_target(target, segments, context, llvm_disasm)
            identifier = read_virtual(segments, string_address, 256).split(b"\0", 1)[0].decode(
                "utf-8", "replace"
            )
            layout = layouts.get(identifier)
            entries.append({
                "page_class": page["class_name"],
                "factory_va": page["factory_va"],
                "constructor_va": page["constructor_va"],
                "constructor_vptr_relocation_slot_va": page["elf_relocation"]["slot_va"],
                "address_point_va": page["vtable_address_point_va"],
                "registry_query_slot_17_target_va": hex(registry_slot_17_target),
                "registry_page_slot_30_target_va": hex(registry_slot_30_target),
                "method_slot_index": slot_index,
                "method_slot_offset_bytes": hex(slot_index * 8),
                "method_relocation_slot_va": hex(relocation_slot),
                "method_relocation_type": "R_AARCH64_RELATIVE",
                "method_va": hex(target),
                "method_body": instructions,
                "returned_string_va": hex(string_address),
                "returned_identifier": identifier,
                "exact_layout_name_match": layout is not None,
                "layout": ({
                    "name": layout["name"],
                    "source": layout["source"],
                    "member": layout["member"],
                    "sha256": layout["sha256"],
                } if layout else None),
            })
    finally:
        dispose(context)

    matched = sum(row["exact_layout_name_match"] for row in entries)
    identifier_counts = Counter(row["returned_identifier"] for row in entries)
    duplicate_identifiers = {
        identifier: count for identifier, count in sorted(identifier_counts.items()) if count > 1
    }
    getter_targets = {int(row["method_va"], 16) for row in entries}
    direct_refs = direct_branch_reference_counts(segments, getter_targets)
    relocation_target_counts = Counter(relocations.values())
    getter_relocation_counts = [relocation_target_counts[target] for target in getter_targets]
    slot_17_distribution = Counter(row["registry_query_slot_17_target_va"] for row in entries)
    slot_30_distribution = Counter(row["registry_page_slot_30_target_va"] for row in entries)
    return {
        "schema": "acnh.ui_page_layout_identifier_bindings.v1",
        "source_build": factories["source_build"],
        "main_nso_sha256": hashlib.sha256(nso_path.read_bytes()).hexdigest(),
        "source_artifacts": [
            "output/ui_hud/page_factory_catalog.json",
            "output/ui_hud/screen_catalog.json",
            "inputs/additional_exefs/main",
        ],
        "method": {
            "slot_index": 46,
            "slot_offset_bytes": "0x170",
            "resolution": "R_AARCH64_RELATIVE relocation at address_point + 0x170 resolves to an AArch64 ADRP/ADD/RET getter; its returned NUL-terminated string is compared exactly to screen_catalog layout names.",
            "interpretation": "The code-pointer slot returns a string identical to a catalogued layout name. This is a static page-to-layout identifier crosswalk; the slot's semantic name, caller, loader handoff, runtime ownership, instantiation, and rendering are not established.",
        },
        "summary": {
            "factory_pages_examined": len(entries),
            "unique_method_targets": len({row["method_va"] for row in entries}),
            "unique_returned_identifiers": len(identifier_counts),
            "duplicate_returned_identifiers": duplicate_identifiers,
            "exact_layout_name_matches": matched,
            "returned_identifiers_without_catalogued_layout": len(entries) - matched,
            "getter_targets_with_direct_B_or_BL_references": len(direct_refs),
            "direct_B_or_BL_reference_sites_to_getters": sum(direct_refs.values()),
            "getter_targets_with_exactly_one_relative_relocation": sum(count == 1 for count in getter_relocation_counts),
            "registry_query_slot_17_target_distribution": dict(sorted(slot_17_distribution.items())),
            "registry_page_slot_30_target_distribution": dict(sorted(slot_30_distribution.items())),
            "unmatched_pages": [
                {"page_class": row["page_class"], "returned_identifier": row["returned_identifier"]}
                for row in entries if not row["exact_layout_name_match"]
            ],
        },
        "limits": [
            "The 135 pages are those matching the existing shared-factory scan, not a proof of every page in the game.",
            "An exact returned string does not prove that a loader calls the method or that the page loads, owns, or renders that BFLYT.",
            "No direct B/BL instruction targets any of the 135 getter functions; indirect calls are not associated with a page receiver by this static crosswalk.",
            "A returned identifier absent from the available 523-layout catalog may resolve through another archive, version, alias, or no resource; this static corpus does not decide which.",
        ],
        "pages": entries,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=ROOT / "output/ui_hud")
    parser.add_argument("--nso", type=Path, default=ROOT / "inputs/additional_exefs/main")
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    result = build_bindings(args.output_root, args.nso)
    destination = args.output or args.output_root / "page_layout_method_bindings.json"
    destination.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"output": str(destination), **result["summary"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
