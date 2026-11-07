#!/usr/bin/env python3
"""Export bounded native evidence for HHA overlap scanning and SystemMailSend.

The script cross-checks indexed pseudocode, the original main NSO, code-pointer
arrays and EventFlow references. It does not execute ACNH or claim mailbox
delivery.
"""
from collections import Counter
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import zlib

ROOT = Path(__file__).resolve().parents[1]
DATA = Path("/workspace/acnh-re")
DB = DATA / "output/index.sqlite"
DECOMP = DATA / "output/binary/analysis_decomp"
POINTER_ARRAYS = DATA / "output/binary/code_pointer_arrays.json"
EVENT_HANDLERS = DATA / "output/binary/event_handlers_resolved.json"
NATIVE_FLAGS = DATA / "output/gameplay/native_flag_refs.json"
FLAG_INDEX = DATA / "output/gameplay/flag_index.json"
NSO = DATA / "inputs/additional_exefs/main"
OUT = ROOT / "output/gameplay/house_hha_followup/hha_overlap_mail_dispatch_static.json"

NSO_SHA256 = "f8d248109ff72999b4600ae3749f8c7397fb960f7ad3ab8dee3018ae9e14e900"
ROUTE_LIST_VA = 0x29BA1DA
ROUTE_LIST = b"cFastToday , cFastTomorrow , cSlowRetry"
ROUTE_METHOD = 0xAC7070
ROUTE_FUNCTION_SIZE = 728
HHA_FLAG = "cPlayer:HHAGradeMailFlag"

if (DATA / ".deps").is_dir():
    sys.path.insert(0, str(DATA / ".deps"))
sys.path.insert(0, str(ROOT / "tools"))
from capstone import Cs, CS_ARCH_ARM64, CS_MODE_ARM  # noqa: E402
from exefs_modules import NsoModule  # noqa: E402


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_decomp(name):
    return (DECOMP / f"{name}.c").read_text()


def main():
    if sha256(NSO) != NSO_SHA256:
        raise AssertionError("main NSO hash differs from the indexed 1.0.0 build")
    nso = NsoModule(NSO.read_bytes())
    if nso.read(ROUTE_LIST_VA, len(ROUTE_LIST)) != ROUTE_LIST:
        raise AssertionError("route enum string list changed")

    db = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    flag_string_refs = [dict(r) for r in db.execute(
        "SELECT string_va,function_va,text FROM string_refs WHERE text=? ORDER BY string_va,function_va",
        ("HHAGradeMailFlag",),
    )]
    if [(r["string_va"], r["function_va"]) for r in flag_string_refs] != [(0x292E423, 0x7B1FE0)]:
        raise AssertionError({"unexpected_grade_flag_string_xrefs": flag_string_refs})
    flag_string_xrefs_output = [
        {"string_va": f"0x{r['string_va']:x}", "function_va": f"0x{r['function_va']:x}", "text": r["text"]}
        for r in flag_string_refs
    ]
    flag_hash_refs = {}
    for label in ("HHAGradeMailFlag", HHA_FLAG):
        crc = zlib.crc32(label.encode("utf-8")) & 0xFFFFFFFF
        refs = [dict(r) for r in db.execute(
            "SELECT hash,pc,owner_va FROM hash_refs WHERE hash=? ORDER BY pc", (crc,)
        )]
        flag_hash_refs[label] = {"crc32": f"0x{crc:08x}", "refs": refs}
        if refs:
            raise AssertionError({"unexpected_crc32_flag_refs": flag_hash_refs})

    native_flags = json.loads(NATIVE_FLAGS.read_text())["data"]["flags"][HHA_FLAG]
    flag_entry = json.loads(FLAG_INDEX.read_text())["data"][HHA_FLAG]
    if native_flags["referencing_functions"] != ["0x7b1fe0"] or native_flags["pseudocode_readings"]:
        raise AssertionError({"native_flag_index_changed": native_flags})
    if flag_entry["eventflow_readers"] or flag_entry["eventflow_writers"]:
        raise AssertionError({"eventflow_flag_access_changed": flag_entry})
    flag_param_actions = [dict(r) for r in db.execute(
        "SELECT flow,event_index,name,params_json FROM event_calls "
        "WHERE params_json LIKE '%HHAGradeMailFlag%' ORDER BY flow,event_index"
    )]

    hha_eval = read_decomp("7b1fe0")
    iterator = read_decomp("52c970")
    resolver = read_decomp("a13fe0")
    cell_reader = read_decomp("52d640")
    grid_write = read_decomp("52df00")
    grid_fill = read_decomp("52e360")
    if not all(s in hha_eval for s in (
        "uVar16 = iStack_14f0 + iStack_14ec * iVar6;",
        "*(uint *)(*plVar2 + (ulong)(uVar16 >> 5) * 4 + 0xee8)",
        "FUN_00b13fe0(asStack_1510,alStack_1440,lVar18,auStack_14e8,auStack_1508);",
        "FUN_00ba7f80();",
        "*(int *)(*plVar1 + 0x150) =",
        "FUN_0062c400(&uStack_1538,auStack_14f8);",
        "*(uint *)(lVar19 + 0xee8) =",
        "lVar18 = lVar18 + 1;",
    )):
        raise AssertionError("HHA evaluator scan/score/footprint evidence changed")
    if not all(s in iterator for s in (
        "if ((int)param_1[3] < *(int *)(param_1[1] + 8))",
        "*(int *)(param_1 + 3) = (int)param_1[3] + 1;",
        "*(int *)((long)param_1 + 0x1c) = *(int *)((long)param_1 + 0x1c) + 1;",
    )):
        raise AssertionError("grid iterator traversal changed")
    if not all(s in resolver for s in (
        "FUN_0062f220();",
        "FUN_010589b0(param_1,auStack_38);",
    )):
        raise AssertionError("HHA cell resolver path changed")
    if not all(s in cell_reader for s in (
        "if (*psVar9 != -3)",
        "FUN_010589b0(param_1,psVar9);",
        "FUN_010589b0(param_1,lVar10 + (long)plVar11);",
    )):
        raise AssertionError("single-cell / -3 fallback behavior changed")
    if "FUN_010589e0(plStack_80[1] + (long)plVar5,param_2);" not in grid_write:
        raise AssertionError("grid cell writer no longer replaces one cell value")
    if "FUN_0062df00(param_1,uVar9,&lStack_f8);" not in grid_fill:
        raise AssertionError("grid rectangle updater no longer calls the cell writer")
    grid_writer_callers = sorted({r[0] for r in db.execute(
        "SELECT DISTINCT owner_va FROM direct_calls WHERE target_va=0x52df00"
    )})
    if grid_writer_callers != [0x52D980, 0x52E360]:
        raise AssertionError({"grid_writer_callers": [hex(x) for x in grid_writer_callers]})

    route_parser = read_decomp("27ccd0")
    route_dispatch = read_decomp("346a50")
    if not all(s in route_parser for s in (
        "uVar4 = 0;", "uVar4 = 1;", "uVar4 = 2;",
    )):
        raise AssertionError("route string-to-ordinal parser changed")
    if not all(s in route_dispatch for s in (
        "FUN_00bbf6a0(param_1,uVar7 & 0xffffffff);",
        "FUN_00bbf730(param_1,uVar7 & 0xffffffff);",
        "FUN_00bc1ff0(param_1,lVar1 + lVar6,&uStack_68,uVar5 & 0xffffffff);",
        "FUN_00bbf740(param_1,uVar7 & 0xffffffff);",
    )):
        raise AssertionError("SystemMailSend route dispatcher branches changed")

    event_handler = json.loads(EVENT_HANDLERS.read_text())["entries"][
        "EventFlowSystemActor.EventFlowActionSystemMailSend"
    ]
    event_rows = [dict(r) for r in db.execute(
        "SELECT flow,event_index,actor,kind,name,params_json FROM event_calls "
        "WHERE name='EventFlowActionSystemMailSend' ORDER BY flow,event_index"
    )]
    route_counts = Counter(json.loads(r["params_json"]).get("Route") for r in event_rows)
    if len(event_rows) != 50 or route_counts != {"cFastTomorrow": 35, "cFastToday": 15}:
        raise AssertionError({"system_mail_event_routes": dict(route_counts), "count": len(event_rows)})
    hha_actions = [r for r in event_rows if
                    "cHHA" in r["params_json"] or "MAIL_SP_HHA" in r["params_json"]]

    pointer_arrays = json.loads(POINTER_ARRAYS.read_text())
    candidate_arrays = {"0x30883a8", "0x3088410"}
    route_slot_candidates = []
    for candidate in pointer_arrays:
        if candidate["start_va"] not in candidate_arrays:
            continue
        start = int(candidate["start_va"], 16)
        slot_30 = next((e for e in candidate["entries"]
                        if int(e["pointer_va"], 16) == start + 0x30), None)
        route_slot_candidates.append({"address_point": candidate["start_va"],
                                      "slot_va": f"0x{start + 0x30:x}",
                                      "target_va": slot_30["target_va"] if slot_30 else None})
    if len(route_slot_candidates) != len(candidate_arrays) or any(
        row["target_va"] != hex(ROUTE_METHOD) for row in route_slot_candidates
    ):
        raise AssertionError({"unexpected_route_virtual_slots": route_slot_candidates})

    decoder = Cs(CS_ARCH_ARM64, CS_MODE_ARM)
    method_insns = {i.address: i for i in decoder.disasm(
        nso.read(ROUTE_METHOD, ROUTE_FUNCTION_SIZE), ROUTE_METHOD
    )}
    expected_calls = {
        0xAC71B0: "#0xfad540",  # route helper mode 1: four-entry path
        0xAC71D0: "#0xfaabf0",
        0xAC7258: "#0xfad340",  # route helper mode 2: sixteen-entry path
        0xAC727C: "#0xfaa3f0",
        0xAC72A0: "#0xfacaa0",
        0xAC72F8: "#0xfaa230",
        0xAC720C: "#0xfad540",  # route helper mode 3 fallback
        0xAC722C: "#0xfaaeb0",
    }
    for pc, target in expected_calls.items():
        ins = method_insns.get(pc)
        if not ins or ins.mnemonic != "bl" or ins.op_str != target:
            raise AssertionError({"route_method_call": hex(pc),
                                  "expected": target,
                                  "actual": (ins.mnemonic, ins.op_str) if ins else None})
    expected_modes = {
        0xAC7170: ("cmp", "w19, #3"),
        0xAC7178: ("b.eq", "#0xac71e8"),
        0xAC717C: ("cmp", "w19, #2"),
        0xAC7180: ("b.eq", "#0xac7234"),
        0xAC7184: ("cmp", "w19, #1"),
        0xAC7188: ("b.ne", "#0xac72fc"),
    }
    for pc, expected in expected_modes.items():
        ins = method_insns.get(pc)
        actual = (ins.mnemonic, ins.op_str) if ins else None
        if actual != expected:
            raise AssertionError({"route_mode_branch": hex(pc), "expected": expected,
                                  "actual": actual})
    for pc in (0xAC7198, 0xAC71F4, 0xAC7240):
        ins = method_insns.get(pc)
        if not ins or ins.mnemonic != "mov" or ins.op_str != "w1, #0x9610":
            raise AssertionError({"save_lookup_key": hex(pc),
                                  "actual": (ins.mnemonic, ins.op_str) if ins else None})

    four_slot_picker = read_decomp("fad540")
    sixteen_slot_picker = read_decomp("fad340")
    today_writer = read_decomp("faabf0")
    retry_writer = read_decomp("faaeb0")
    tomorrow_writer = read_decomp("faa3f0")
    expected_four = [0x7C58, 0x7F10, 0x81C8, 0x8480]
    expected_sixteen = [0x5118 + 0x2B4 * i for i in range(16)]
    import re
    four_offsets = list(dict.fromkeys(
        int(x, 16) for x in re.findall(r"param_1 \+ 0x([0-9a-f]+)U;", four_slot_picker)
    ))
    sixteen_offsets = list(dict.fromkeys(
        int(x, 16) for x in re.findall(r"param_1 \+ 0x([0-9a-f]+)U;", sixteen_slot_picker)
    ))
    if four_offsets != expected_four or sixteen_offsets != expected_sixteen:
        raise AssertionError({"mail_slot_offsets": {"four": four_offsets, "sixteen": sixteen_offsets}})
    if "*(undefined2 *)(param_1 + 0x2b0) = 0x101;" not in today_writer:
        raise AssertionError("FastToday record state write changed")
    if "*(undefined2 *)(param_1 + 0x2b0) = 0x103;" not in retry_writer:
        raise AssertionError("slow retry fallback record state write changed")
    if "FUN_01073b00" not in tomorrow_writer or "param_1[0x2b0]" not in tomorrow_writer:
        raise AssertionError("FastTomorrow record copy/state path changed")

    doc = {
        "schema": 1,
        "scope": "Indexed static evidence for HHA scan/overlap suppression, HHAGradeMailFlag xrefs, and SystemMailSend record queueing. It stops before live mailbox delivery.",
        "source": {
            "main_nso": str(NSO),
            "main_nso_sha256": NSO_SHA256,
            "index_database": str(DB),
            "indexed_build_match": True,
        },
        "hha_overlap": {
            "scan": {
                "room_passes": 8,
                "cell_count_bound": "0x400 per room scan",
                "cell_index": "x_offset + z_offset * width",
                "order": "x increases first within each row; at row end x resets to row start and z increments",
                "visited_bitmap_offset": "evaluation record +0xee8",
                "evidence": ["0x7b1fe0", "0x52c970"],
            },
            "candidate_rules": {
                "lookup": "For each unvisited anchor, 0x7b1fe0 calls 0xb13fe0; a valid returned object descriptor proceeds to footprint handling.",
                "score_gate": "Only the iVar24 == 0 path and successful 0xba7f80 predicate add width * depth to +0x150.",
                "footprint_mark": "After that conditional score block, the returned object's full footprint is traversed and its scan bitmap cells are marked regardless of whether the score predicate passed.",
                "empty_or_failed_lookup": "Empty (-2) and failed auxiliary lookup paths mark only the anchor bit; they do not add area.",
            },
            "deterministic_overlap_consequence": {
                "contained_later_anchor": "If an earlier scanned valid object marks a later object's anchor cell, the later anchor is skipped before resolver lookup. This can suppress its score contribution even when the earlier object's own score predicate failed.",
                "overlap_without_contained_anchor": "If both anchors remain unvisited, both eligible objects can contribute their full width * depth; the accumulator does not subtract intersection area.",
                "same_anchor": "The resolver returns one cell descriptor. The indexed getter does not enumerate all objects occupying that coordinate, so it cannot identify which same-cell furniture record won.",
                "ordering": "For distinct anchors, the first scanned anchor's footprint can determine whether a later anchor is visited; this is a deterministic x-fast row-major scan rule, not evidence of which object occupies a single grid cell.",
            },
            "resolver_and_grid_limit": {
                "resolver_chain": ["0x7b1fe0", "0xb13fe0", "0x52f220", "0x52d640"],
                "cell_getter": "0x52d640 reads a single short cell value; sentinel -3 decodes a coordinate and makes one fallback lookup in the alternate grid.",
                "generic_writer": "0x52df00 unconditionally writes a single cell value; rectangle updater 0x52e360 calls it. Indexed direct callers of 0x52df00 are 0x52d980 and 0x52e360.",
                "generic_writer_callers": [hex(x) for x in grid_writer_callers],
                "unresolved": "The static corpus does not tie the furniture-grid population/update sequence to object creation order at a shared anchor. Exact same-cell winner remains unproven without a matching grid writer path or runtime grid capture.",
            },
        },
        "grade_mail_flag": {
            "key": HHA_FLAG,
            "definition": flag_entry["definition"],
            "indexed_native_name_xrefs": flag_string_xrefs_output,
            "indexed_native_flag_record": native_flags,
            "eventflow_readers": flag_entry["eventflow_readers"],
            "eventflow_writers": flag_entry["eventflow_writers"],
            "event_calls_mentioning_key": flag_param_actions,
            "crc32_xref_checks": flag_hash_refs,
            "conclusion": "All indexed exact-name native references point to the setter path 0x7b1fe0. No indexed EventFlow read/write, exact-name native reader/clearer, pseudocode reading, or CRC32-key reference was found. This does not exclude a consumer that uses an unresolved encoding or requires runtime observation.",
            "runtime_capture": "none",
        },
        "system_mail_send": {
            "registration": {
                "canonical_name": event_handler["canonical_name"],
                "event_uses": event_handler["event_uses"],
                "parameters": event_handler["parameters"],
                "method": "0x345890",
                "record_builder": "0xac77a0",
                "route_dispatcher": "0x346a50",
            },
            "route_enum": [
                {"ordinal": 0, "label": "cFastToday", "dispatcher": "0xabf6a0", "record_mode": 1},
                {"ordinal": 1, "label": "cFastTomorrow", "dispatcher": "0xabf730", "record_mode": 2},
                {"ordinal": 2, "label": "cSlowRetry", "dispatcher": "0xac1ff0 first; 0xabf740 fallback", "record_mode": 3, "note": "The direct handler is attempted before the mode-3 fallback."},
            ],
            "eventflow_route_counts": dict(sorted(route_counts.items())),
            "indexed_hha_actions": [
                {"flow": r["flow"], "event_index": r["event_index"], "params": json.loads(r["params_json"])}
                for r in hha_actions
            ],
            "record_paths": {
                "fast_today_mode_1": {
                    "native_method": "0xac7070 via record virtual slot +0x30; both indexed record pointer-array candidates resolve to this method",
                    "save_lookup_key": "0x9610 (label unresolved in local schema)",
                    "slot_picker": "0xfad540 chooses the first available record among four slots",
                    "slot_offsets": [f"+0x{x:x}" for x in expected_four],
                    "record_writer": "0xfaabf0 copies the formatted record; writes 0x0101 at destination +0x2b0",
                    "conclusion": "A save-backed mail record is copied into the four-slot route collection when the native eligibility/payload checks pass.",
                },
                "fast_tomorrow_mode_2": {
                    "native_method": "0xac7070 via record virtual slot +0x30; both indexed record pointer-array candidates resolve to this method",
                    "save_lookup_key": "0x9610 (label unresolved in local schema)",
                    "slot_picker": "0xfad340 checks sixteen slots and returns the first available slot plus its ordinal",
                    "slot_offsets": [f"+0x{x:x}" for x in expected_sixteen],
                    "slot_stride": "0x2b4",
                    "record_writer": "0xfaa3f0 copies the action's formatted record payload into the selected slot; follow-up code counts valid slots and updates related save state",
                    "conclusion": "The cFastTomorrow route reaches a native save-backed 16-slot record insertion path at action execution, subject to its validity and free-slot checks.",
                },
                "slow_retry_mode_3_fallback": {
                    "native_method": "0xac7070 via record virtual slot +0x30 after 0xac1ff0 returns false",
                    "save_lookup_key": "0x9610 (label unresolved in local schema)",
                    "slot_picker": "0xfad540, same four-slot path",
                    "record_writer": "0xfaaeb0; writes 0x0103 at destination +0x2b0",
                },
            },
            "eventflow_example": "The only indexed HHA mail action is BuildCelebration, with Route=cFastTomorrow; it therefore reaches the mode-2 record path. It is not the HHA grade report producer.",
            "timing_and_boundary": "The action inserts a save-backed route record when its EventFlow method executes. The route names identify Today/Tomorrow paths, but static evidence does not prove the exact clock/date at delivery, eventual mailbox visibility, inbox insertion, or successful arrival. No live runtime capture was available.",
        },
        "static_checks": {
            "route_table_bytes": ROUTE_LIST.decode("ascii"),
            "route_virtual_slot": {"slot_offset": "+0x30", "target": hex(ROUTE_METHOD),
                                    "indexed_address_point_candidates": route_slot_candidates,
                                    "exact_constructor_global_crosswalk": "unresolved; both candidate arrays agree on the +0x30 target"},
            "method_native_calls": {hex(pc): target for pc, target in expected_calls.items()},
            "method_route_mode_branches": {hex(pc): list(value) for pc, value in expected_modes.items()},
            "save_lookup_key_pcs": [hex(pc) for pc in (0xAC7198, 0xAC71F4, 0xAC7240)],
            "status": "PASS",
        },
    }
    OUT.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({
        "output": str(OUT.relative_to(ROOT)),
        "hha_flag_exact_name_refs": len(flag_string_refs),
        "system_mail_actions": len(event_rows),
        "route_counts": dict(route_counts),
        "fast_tomorrow_slots": len(expected_sixteen),
        "status": "PASS",
    }, indent=2))


if __name__ == "__main__":
    main()
