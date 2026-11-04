#!/usr/bin/env python3
"""Scan supplied ExeFS NSOs for selected gameplay strings and C++ type anchors."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

from exefs_modules import NsoModule

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUT = ROOT / "inputs" / "additional_exefs"
OUTPUT = ROOT / "output" / "native_modules" / "gameplay_symbol_scan.json"
MODULES = ("main", "rtld", "subsdk0", "sdk")
TARGET_STRINGS = (
    "AbandonedHouse",
    "EventFlowQueryBoaCanSetKabu",
    "VillageScore",
    "KabuBuyPage",
    "DragSE",
    "ItemParam",
    "NpcSave",
    "IslandEvaluation",
    "VillageScoreMgr",
)
TARGET_RTTI_TERMS = (
    "AbandonedHouse",
    "IslandEvaluation",
    "ItemParam",
    "NpcSave",
    "Nook",
    "PlayerActor",
    "VillageScore",
    "VillageScoreMgr",
)
RTTI_PATTERN = re.compile(rb"(?:__)?_ZT(?:I|S|V)[A-Za-z0-9_.$]+")


def build(input_root=DEFAULT_INPUT):
    input_root = Path(input_root)
    records = {}
    for name in MODULES:
        path = input_root / name
        parsed = NsoModule(path.read_bytes())
        data = b"".join(segment["data"] for segment in parsed.segments)
        rtti = sorted({
            match.decode("ascii", errors="replace")
            for match in RTTI_PATTERN.findall(data)
        })
        rtti_term_hits = {
            term: [name for name in rtti if term.lower() in name.lower()]
            for term in TARGET_RTTI_TERMS
        }
        records[name] = {
            "sha256": hashlib.sha256(parsed.raw).hexdigest(),
            "build_id": parsed.build_id,
            "decompressed_bytes": sum(segment["size"] for segment in parsed.segments),
            "gameplay_string_occurrences": {
                term: data.count(term.encode("ascii")) for term in TARGET_STRINGS
            },
            "rtti_like_symbol_count": len(rtti),
            "rtti_like_symbols": rtti,
            "rtti_like_symbols_matching_gameplay_terms": rtti_term_hits,
        }

    result = {
        "schema": "acnh-re/exefs-gameplay-symbol-scan/1",
        "scope": "The four supplied NSO modules only; this does not claim a complete ExeFS inventory.",
        "available_input_names": [
            "main", "main.npdm", "rtld", "subsdk0", "sdk"
        ],
        "scan_method": "SHA-256 verified NSO segment decompression, then exact byte-string counts and bounded ASCII RTTI-mangling scan.",
        "target_strings": list(TARGET_STRINGS),
        "target_rtti_terms": list(TARGET_RTTI_TERMS),
        "modules": records,
        "findings": {
            "supplementary_modules_have_zero_target_string_hits": all(
                count == 0
                for module in ("rtld", "subsdk0", "sdk")
                for count in records[module]["gameplay_string_occurrences"].values()
            ),
            "main_rtti_like_names_are_only_generic_anchors": records["main"]["rtti_like_symbols"] == [
                "_ZTIN2nn4util17IntrusiveListNodeE",
                "_ZTSN2nn4util17IntrusiveListNodeE",
                "_ZTVN10__cxxabiv117__class_type_infoE",
                "_ZTVN10__cxxabiv120__si_class_type_infoE",
                "_ZTVN10__cxxabiv121__vmi_class_type_infoE",
            ],
            "no_module_rtti_name_matches_target_gameplay_terms": all(
                not hits
                for module in MODULES
                for hits in records[module]["rtti_like_symbols_matching_gameplay_terms"].values()
            ),
        },
        "interpretation": "The supplied runtime modules add SDK/media implementation and generic C++ metadata, but no scanned target gameplay type or callback name that resolves the open save-vtable and AbandonedHouse dispatch identities.",
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({
        "output": str(OUTPUT),
        "supplementary_modules_have_zero_target_string_hits": result["findings"]["supplementary_modules_have_zero_target_string_hits"],
        "main_rtti_like_symbols": records["main"]["rtti_like_symbols"],
        "module_counts": {
            name: {
                "decompressed_bytes": value["decompressed_bytes"],
                "rtti_like_symbol_count": value["rtti_like_symbol_count"],
                "target_hits": sum(value["gameplay_string_occurrences"].values()),
            }
            for name, value in records.items()
        },
    }, indent=2))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-root", type=Path, default=DEFAULT_INPUT)
    args = parser.parse_args()
    try:
        build(args.input_root)
    except (OSError, ValueError) as exc:
        print(f"ExeFS gameplay scan failed: {exc}", file=sys.stderr)
        raise SystemExit(2)
