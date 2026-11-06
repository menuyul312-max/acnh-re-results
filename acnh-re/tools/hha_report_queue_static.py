#!/usr/bin/env python3
"""Export static call-chain and EventFlow evidence for HHA report/mail follow-up."""
import hashlib
import json
import sqlite3
import struct
from pathlib import Path

from exefs_modules import NsoModule

ROOT = Path(__file__).resolve().parent.parent
DATA = Path("/workspace/acnh-re")
DB = DATA / "output/index.sqlite"
FLAG_REFS = DATA / "output/gameplay/native_flag_refs.json"
DECOMP = DATA / "output/binary/analysis_decomp"
NSO = DATA / "inputs/additional_exefs/main"
POINTER_ARRAYS = DATA / "output/binary/code_pointer_arrays.json"
EVENT_HANDLERS = DATA / "output/binary/event_handlers_resolved.json"
USEN_MESSAGES = DATA / "output/additional_romfs/messages/USen"
OUT = ROOT / "output/gameplay/house_hha_followup/hha_report_queue_static.json"

BUCKET = 0x7B4FC0
BUCKET_RECEIVER = 0x7B6470
REPORT_RECORD_BUILDER = 0xAC77A0
REPORT_QUEUE_APPEND = 0xABF610
REPORT_BUILDERS = [0x7B6470, 0x7B53B0, 0x7B55E0, 0x7B5E60, 0x7B61E0]
HHA_GRADE_LABEL_RECORD_CODES = {
    "0x7b5b00": {
        "meaning": "selected report-condition ordinal",
        "codes": [1, 2, 5, 10, 11, 12, 15, 20, 25, 30],
    },
    "0x7b6470": {
        "meaning": "score/report-mask index",
        "codes": [40, 41, 42, 44, 45, 46, 48, 51, 52, 53, 54, 55, 56, 57],
    },
    "0x7b61e0": {
        "meaning": "HHA report subcategory ordinal",
        "codes": [70, 71, 72, 73, 74, 75, 76, 77, 78, 80, 81],
    },
}
HHA_REPORT_VTABLE_GLOBAL = 0x32E8CB0
HHA_REPORT_VTABLE_HEADER = 0x3088400
HHA_REPORT_VTABLE_SLOTS = {
    0x28: 0xAC78F0,
    0x38: 0xAC7350,
    0x40: 0x348250,
    0x48: 0xAC7A00,
    0x50: 0x7B8420,
}
HHA_MESSAGE_REGISTRY_VA = 0x29501DF
HHA_MESSAGE_REGISTRY_SIZE = 0x1AB
SCORE_TOTAL_EVALUATOR = 0x7B1FE0
ITEM_SCORE_ACCUMULATOR = 0x7B36B0
SCORE_BUCKET = 0x7B4FC0
SCORE_BUCKET_RECEIVER = 0x7B6470
ITEM_SCORE_ACCUMULATOR_CALL_PC = 0x7B265C
ITEM_SCORE_HELPER_CALL_PC = 0x7B37B8

QUEUE_LIFECYCLE = {
    "append": 0xABF610,
    "flush": 0xABF910,
    "nonempty": 0xABF960,
    "filter_dispatch_remove": 0xABFA00,
    "consume_type_3": 0xABFB40,
    "pump": 0xAC0A60,
    "event_handoff": 0xAC13F0,
}
HHA_UI_FUNCTIONS = {0xAC2E30, 0xAC3360}
HHA_UI_TRAMPOLINES = {0x7B8420, 0x7B8270}
BUILD_CELEBRATION_NATIVE_CHAIN = [
    (0xF53A70, 0xABA970, 0xF53F28),
    (0xABA970, 0xABA9D0, 0xABA9B8),
    (0xABA9D0, 0xABB250, 0xABA9F0),
    (0xABB250, 0xABB3F0, 0xABB318),
    (0xABB3F0, 0x7B1960, 0xABB44C),
    (0xABB3F0, 0xABF610, 0xABB990),
    (0x7B1960, 0xF95610, 0x7B19FC),
]
HHA_MESSAGE_MEMBERS = (
    "Sp/HHA/STR_HHA_Rank.msbt",
    "Sp/HHA/STR_HHA_RoomLocation.msbt",
    "Sp/HHA/STR_HHA_Set.msbt",
    "Sp/HHA/STR_HHA_Situation.msbt",
    "Sp/HHA/STR_HHA_Theme.msbt",
    "Sp/HHA/MAIL_SP_HHA_Grade.msbt",
    "Sp/HHA/MAIL_SP_HHA_GradeFixedPoints.msbt",
    "Sp/HHA/MAIL_SP_HHA_GradeMission.msbt",
    "Sp/HHA/MAIL_SP_HHA_Mission.msbt",
    "Sp/HHA/MAIL_SP_HHA_BuildCelebration.msbt",
)


def hsha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def hex_addr(value):
    return f"0x{value:x}"


def localized_inventory():
    """Return HHA message IDs and counts only; never copy localized bodies."""
    inventory = {}
    for archive in ("String", "Mail"):
        path = USEN_MESSAGES / f"{archive}.json"
        if not path.is_file():
            continue
        payload = json.loads(path.read_text())
        for member in HHA_MESSAGE_MEMBERS:
            if member not in payload["members"]:
                continue
            entry = payload["members"][member]
            messages = entry.get("messages", [])
            inventory[member] = {
                "entry_count": len(messages),
                "labels": [label for row in messages for label in row.get("labels", [])],
            }
    return inventory


def relative_relocations(nso):
    """Read RELA entries needed to resolve the HHA report-record vtable."""
    regions = []
    if 7 in nso.tags:
        regions.append((nso.tags[7], nso.tags.get(8, 0), nso.tags.get(9)))
    if 23 in nso.tags:
        regions.append((nso.tags[23], nso.tags.get(2, 0), 24))

    result = {}
    visited = set()
    for table_va, size, stride in regions:
        if stride != 24 or size % 24:
            raise AssertionError({"invalid_rela_region": [hex(table_va), size, stride]})
        for offset in range(0, size, 24):
            record_va = table_va + offset
            if record_va in visited:
                continue
            visited.add(record_va)
            site, info, addend = struct.unpack("<QQq", nso.read(record_va, 24))
            kind = info & 0xFFFFFFFF
            if site == HHA_REPORT_VTABLE_GLOBAL or (
                HHA_REPORT_VTABLE_HEADER <= site < HHA_REPORT_VTABLE_HEADER + 0x80
            ):
                result[site] = {"type": kind, "addend": addend}
    return result


def main():
    nso = NsoModule(NSO.read_bytes())
    relocs = relative_relocations(nso)
    vtable_global_reloc = relocs.get(HHA_REPORT_VTABLE_GLOBAL)
    if not vtable_global_reloc or vtable_global_reloc["type"] != 1027:
        raise AssertionError({"missing_hha_vtable_global_relocation": vtable_global_reloc})
    if vtable_global_reloc["addend"] != HHA_REPORT_VTABLE_HEADER:
        raise AssertionError({"unexpected_hha_vtable_header": vtable_global_reloc})
    vtable_slot_relocations = {}
    for slot, expected_target in HHA_REPORT_VTABLE_SLOTS.items():
        site = HHA_REPORT_VTABLE_HEADER + 0x10 + slot
        row = relocs.get(site)
        if not row or row["type"] != 1027 or row["addend"] != expected_target:
            raise AssertionError({"unexpected_hha_vtable_slot": {
                "slot": hex(slot), "site": hex(site), "expected_target": hex(expected_target),
                "actual": row,
            }})
        vtable_slot_relocations[slot] = {"site": site, **row}

    registry_raw = nso.read(HHA_MESSAGE_REGISTRY_VA, HHA_MESSAGE_REGISTRY_SIZE)
    registry_text = registry_raw.split(b"\0", 1)[0].decode("ascii")
    registry_entries = [part.strip() for part in registry_text.split(",")]
    if len(registry_entries) <= 0x0B or registry_entries[0x0B] != "MAIL_SP_HHA_Grade":
        raise AssertionError({"unexpected_message_registry_entry_11": registry_entries[:14]})

    db = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    db.row_factory = sqlite3.Row

    hha_record_producers = [0x7B5B00, 0x7B61E0, 0x7B6470]
    for function in hha_record_producers:
        path = DECOMP / f"{function:x}.c"
        if not path.is_file() or "33e8cb0" not in path.read_text(errors="replace"):
            raise AssertionError({"missing_hha_record_vtable_reference": hex(function)})

    def xrefs(target, owner=None):
        if owner is None:
            rows = db.execute(
                "SELECT pc,owner_va,instruction FROM direct_calls WHERE target_va=? ORDER BY pc",
                (target,))
        else:
            rows = db.execute(
                "SELECT pc,owner_va,instruction FROM direct_calls "
                "WHERE target_va=? AND owner_va=? ORDER BY pc", (target, owner))
        return [{"pc": f"0x{r['pc']:x}",
                 "owner": f"0x{r['owner_va']:x}" if r["owner_va"] is not None else None,
                 "instruction": r["instruction"]} for r in rows]

    def xrefs_in_function(target, function):
        row = db.execute("SELECT va,span_end_va FROM native_functions WHERE va=?",
                         (function,)).fetchone()
        if not row:
            raise AssertionError({"missing_function": hex(function)})
        rows = db.execute(
            "SELECT pc,owner_va,instruction FROM direct_calls "
            "WHERE target_va=? AND pc>=? AND pc<=? ORDER BY pc",
            (target, row["va"], row["span_end_va"]))
        return [{"pc": f"0x{r['pc']:x}",
                 "owner": f"0x{r['owner_va']:x}" if r["owner_va"] is not None else None,
                 "instruction": r["instruction"]} for r in rows]

    core_chain = [
        {"caller": 0x7B29D0, "target": BUCKET, "call_pc": 0x7B2BEC},
        {"caller": BUCKET, "target": BUCKET_RECEIVER, "call_pc": 0x7B52B0},
        {"caller": BUCKET_RECEIVER, "target": REPORT_RECORD_BUILDER, "call_pc": 0x7B66F0},
        {"caller": BUCKET_RECEIVER, "target": REPORT_QUEUE_APPEND, "call_pc": 0x7B6724},
    ]
    for edge in core_chain:
        actual = xrefs_in_function(edge["target"], edge["caller"])
        if not any(int(row["pc"], 16) == edge["call_pc"] for row in actual):
            raise AssertionError({"missing_call_edge": edge, "actual": actual})
        edge["caller"] = f"0x{edge['caller']:x}"
        edge["target"] = f"0x{edge['target']:x}"
        edge["call_pc"] = f"0x{edge['call_pc']:x}"

    report_branches = []
    for function in REPORT_BUILDERS:
        report_branches.append({
            "function": f"0x{function:x}",
            "record_builder_calls": xrefs_in_function(REPORT_RECORD_BUILDER, function),
            "queue_append_calls": xrefs_in_function(REPORT_QUEUE_APPEND, function),
        })

    hha_mail_rows = [dict(r) for r in db.execute(
        "SELECT flow,event_index,actor,kind,name,params_json FROM event_calls "
        "WHERE params_json LIKE '%MAIL_SP_HHA%' OR params_json LIKE '%cHHA%' "
        "ORDER BY flow,event_index")]

    grade_resource = localized_inventory().get("Sp/HHA/MAIL_SP_HHA_Grade.msbt", {})
    grade_message_labels = sorted(set(grade_resource.get("labels", [])))
    grade_label_codes = {
        source: {
            "meaning": record_source["meaning"],
            "record_codes": record_source["codes"],
            "formatter_input_label_ids": [f"{code:03d}" for code in record_source["codes"]],
            "matched_grade_archive_label_ids": [
                f"{code:03d}" for code in record_source["codes"]
                if f"{code:03d}" in grade_message_labels
            ],
            "unmatched_grade_archive_label_ids": [
                f"{code:03d}" for code in record_source["codes"]
                if f"{code:03d}" not in grade_message_labels
            ],
        }
        for source, record_source in HHA_GRADE_LABEL_RECORD_CODES.items()
    }
    grade_label_crosswalk = {
        "evidence_level": "HHA_PACKAGE_AND_LABEL_FORMATTER_ROUTE",
        "resource": "Sp/HHA/MAIL_SP_HHA_Grade.msbt",
        "resource_label_count": len(grade_message_labels),
        "record_code_field": "0xac77a0 stores caller param_6 as u8 at record offset +0x38; 0xac7a00 reads +0x38 and forwards it to the localized text builder.",
        "message_resource_selector": {
            "record_offset": "0x34",
            "builder_param": "param_5",
            "hha_caller_value": 11,
            "native_registry_string_va": hex_addr(HHA_MESSAGE_REGISTRY_VA),
            "native_registry_index": 11,
            "selected_registry_entry": registry_entries[11],
            "native_registry_entry_count": len(registry_entries),
            "selection_function_va": "0xac7a00",
            "text_builder_chain": ["0xac7a00", "0xf71be0", "0xf71cd0"],
        },
        "formatter": {
            "record_label_offset": "0x38",
            "hha_vtable_pointer_site": hex_addr(HHA_REPORT_VTABLE_GLOBAL),
            "hha_vtable_header_relocation": hex_addr(HHA_REPORT_VTABLE_HEADER),
            "report_record_producers": [hex_addr(x) for x in hha_record_producers],
            "generic_type_3_handler_va": "0xac1ff0",
            "hha_virtual_dispatch": {
                f"+0x{slot:x}": hex_addr(target) for slot, target in HHA_REPORT_VTABLE_SLOTS.items()
            },
            "formatter_method_va": "0xac7a00",
            "label_is_passed_to_text_builder": True,
        },
        "record_code_sources": grade_label_codes,
        "all_listed_codes_match_resource_label_ids": all(
            not row["unmatched_grade_archive_label_ids"] for row in grade_label_codes.values()
        ),
        "interpretation_limit": (
            "Static vtable relocation and dispatch evidence proves HHA records select MAIL_SP_HHA_Grade and pass "
            "record +0x38 through the localized text builder; all 35 valid numeric codes from three HHA producers "
            "match exact label IDs. "
            "This proves message formatting inputs, not mail insertion, HHAGradeMailFlag consumption, or delivery timing."
        ),
    }

    build_celebration_edges = []
    for caller, target, call_pc in BUILD_CELEBRATION_NATIVE_CHAIN:
        actual = xrefs_in_function(target, caller)
        if not any(int(row["pc"], 16) == call_pc for row in actual):
            raise AssertionError({
                "missing_build_celebration_edge": {
                    "caller": hex(caller), "target": hex(target), "call_pc": hex(call_pc)
                },
                "actual": actual,
            })
        build_celebration_edges.append({
            "caller_va": hex(caller), "target_va": hex(target), "call_pc": hex(call_pc)
        })
    build_flag = json.loads(FLAG_REFS.read_text())["data"]["flags"][
        "cNpcMemory:HHABuildCelebraition"
    ]
    build_celebration_route = {
        "daily_processor_chain": build_celebration_edges,
        "native_flag": "cNpcMemory:HHABuildCelebraition",
        "native_flag_name_ja": build_flag["name_ja"],
        "native_flag_referencing_functions": build_flag["referencing_functions"],
        "event_builder_va": "0xabb3f0",
        "event_builder_string_reference": "HHABuildCelebraition",
        "queue_append_va": "0xabf610",
        "house_state_helper_va": "0x7b1960",
        "helper_house_state_stride": "0x160",
        "helper_active_state_bit": 6,
        "helper_reads_saved_byte_via": "0xf95610",
        "builder_gate": "(state_word_at_house_row_plus_0x144 & 0xfffffffc) == 4",
        "build_celebration_eventflow_mail": [
            {
                "flow": row["flow"], "event_index": row["event_index"],
                "actor": row["actor"], "kind": row["kind"], "name": row["name"],
                "params_json": row["params_json"],
            }
            for row in hha_mail_rows
            if "MAIL_SP_HHA_BuildCelebration" in row["params_json"]
        ],
        "interpretation_limit": (
            "This is an adjacent house-expansion celebration producer. It queues a generic type-3 event and "
            "shares a saved-byte reader with HHA evaluation, but no edge proves that it sends the grade mail, "
            "consumes HHAGradeMailFlag, or matches the HHA report queue records."
        ),
    }

    score_decomp = {
        name: DECOMP / f"{name}.c"
        for name in ("7b1fe0", "7b4fc0", "7b6470", "ab9050")
    }
    for path in score_decomp.values():
        if not path.is_file():
            raise AssertionError({"missing_score_bridge_decomp": str(path)})
    item_accumulator_calls = xrefs_in_function(ITEM_SCORE_ACCUMULATOR, SCORE_TOTAL_EVALUATOR)
    if not any(int(row["pc"], 16) == ITEM_SCORE_ACCUMULATOR_CALL_PC
               for row in item_accumulator_calls):
        raise AssertionError({"missing_item_accumulator_call": item_accumulator_calls})
    item_helper_call = db.execute(
        "SELECT pc,target_va,instruction FROM direct_calls WHERE pc=? AND target_va=?",
        (ITEM_SCORE_HELPER_CALL_PC, 0xAB9050)).fetchone()
    if not item_helper_call:
        raise AssertionError({"missing_item_score_helper_call": hex(ITEM_SCORE_HELPER_CALL_PC)})
    score_total_bridge = {
        "evaluator_va": f"0x{SCORE_TOTAL_EVALUATOR:x}",
        "item_score_accumulator_va": f"0x{ITEM_SCORE_ACCUMULATOR:x}",
        "item_score_accumulator_call_pc": f"0x{ITEM_SCORE_ACCUMULATOR_CALL_PC:x}",
        "item_score_helper_va": "0xab9050",
        "item_score_helper_call_pc": f"0x{ITEM_SCORE_HELPER_CALL_PC:x}",
        "category_accumulator_offsets": [f"0x{x:x}" for x in range(0x24, 0x51, 4)],
        "temporary_total_offset": "0x136c",
        "per_area_delta_offset": "0xd8",
        "bucket_va": f"0x{SCORE_BUCKET:x}",
        "bucket_receiver_va": f"0x{SCORE_BUCKET_RECEIVER:x}",
        "bucket_area_count_offset": "0x154",
        "bucket_max_area_index_offset": "0x155",
        "bucket_min_area_index_offset": "0x156",
        "bucket_report_index_codes": {
            "mask_bit_8": {"mask": "0x100", "record_code": "0x33", "index_offset": "0x155"},
            "mask_bit_9": {"mask": "0x200", "record_code": "0x34", "index_offset": "0x156"},
        },
        "decomp_sha256": {f"{name}.c": hsha(path)
                           for name, path in score_decomp.items()},
        "static_trace": (
            "0x7b1fe0 calls item accumulator 0x7b36b0, which calls 0xab9050 for the item score; "
            "the native item accumulator adds the returned score to the current category field, "
            "then the evaluator recomputes +0x136c as the sum of twelve fields +0x24..+0x50, "
            "and stores the change from the previous total at +0xd8 + 4*min(area_index,5). "
            "0x7b4fc0 scans that +0xd8 array up to +0x154, records maximum/minimum indices "
            "at +0x155/+0x156, and sets mask bits 0x100/0x200; 0x7b6470 maps those bits "
            "to queued record codes 0x33/0x34."
        ),
        "limits": [
            "This is a static cross-reference of separate native functions, not an end-to-end native execution.",
            "The aggregate +0x136c is not itself mapped to a displayed HHA rank or threshold; the proven downstream values are per-area deltas and report-mask details.",
            "The HHA report-record formatter receives the package selector and label byte described in grade_mail_label_candidate_crosswalk; this proves formatted text inputs, not a sent mail or rank cutoff.",
        ],
    }

    grade_flag_eventflow_rows = [dict(r) for r in db.execute(
        "SELECT flow,event_index,actor,kind,name,params_json FROM event_calls "
        "WHERE params_json LIKE '%HHAGradeMailFlag%' OR name LIKE '%HHAGradeMailFlag%' "
        "ORDER BY flow,event_index")]
    flag = json.loads(FLAG_REFS.read_text())["data"]["flags"]["cPlayer:HHAGradeMailFlag"]

    queue_lifecycle = {
        "shared_queue_global_va": "0x33d4ff8",
        "helpers": {
            name: {"function_va": hex_addr(va), "direct_callers": xrefs(va)}
            for name, va in QUEUE_LIFECYCLE.items()
        },
        "static_behavior": {
            "append": "0xabf610 appends a record object to the shared queue when its virtual eligibility method succeeds.",
            "pump": "0xac0a60 dispatches the generic queue, handles type-3 entries, then checks and flushes the queue.",
            "type_3": "0xabfb40 selects entries whose virtual type at +0x14 equals 3 and invokes the generic record handler.",
            "event_handoff": "0xac13f0 routes a generic event record through 0xabfa00 filter/dispatch/remove.",
            "generic_record_handler": "0xac1ff0 invokes record vtable slots +0x28, +0x38, and +0x40; the HHA +0x38 method reaches its +0x48 formatter for HHA records whose +0x10 sentinel is -1.",
        },
        "hha_specific_consumer_found": True,
        "hha_report_record_dispatch": {
            "record_producers": [hex_addr(x) for x in hha_record_producers],
            "vtable_global_pointer_site": hex_addr(HHA_REPORT_VTABLE_GLOBAL),
            "relative_relocation_type": vtable_global_reloc["type"],
            "vtable_header_addend": hex_addr(vtable_global_reloc["addend"]),
            "runtime_vtable_address_point": hex_addr(vtable_global_reloc["addend"] + 0x10),
            "slot_targets": {
                f"+0x{slot:x}": {
                    "function_va": hex_addr(target),
                    "relative_relocation_site": hex_addr(vtable_slot_relocations[slot]["site"]),
                    "relative_relocation_type": vtable_slot_relocations[slot]["type"],
                }
                for slot, target in HHA_REPORT_VTABLE_SLOTS.items()
            },
            "queue_to_formatter": ["0xabfb40", "0xac1ff0", "vtable +0x38 -> 0xac7350", "vtable +0x48 -> 0xac7a00"],
            "grade_mail_send_proven": False,
            "limits": [
                "The formatter selects the MAIL_SP_HHA_Grade registry entry and passes the +0x38 label value into the text builder.",
                "The queue handler does not call EventFlowActionSystemMailSend; indexed HHA EventFlow still exposes only BuildCelebration.",
                "HHAGradeMailFlag is still only referenced by its native setter path; no reader/clear or mailbox insertion edge is proven.",
            ],
        },
        "limits": [
            "The HHA-specific queue record class and localized formatter are resolved through static RELATIVE relocations and the generic type-3 dispatch.",
            "The resolved consumer proves which package and label byte are formatted; it does not establish an actual grade-mail send, delivery timing, or flag consumption.",
        ],
    }

    ui_localization_refs = {}
    for function in HHA_UI_FUNCTIONS:
        rows = db.execute(
            "SELECT string_va,text FROM string_refs WHERE function_va=? ORDER BY string_va",
            (function,))
        ui_localization_refs[hex_addr(function)] = [
            {"string_va": hex_addr(row["string_va"]), "message_id": row["text"]}
            for row in rows if row["text"].startswith("STR_HHA_")
        ]

    ui_pointer_arrays = []
    if POINTER_ARRAYS.is_file():
        for array in json.loads(POINTER_ARRAYS.read_text()):
            entries = array.get("entries", [])
            targets = {row.get("target_va") for row in entries}
            if targets & {hex_addr(x) for x in HHA_UI_TRAMPOLINES}:
                ui_pointer_arrays.append({
                    "start_va": array["start_va"],
                    "hha_trampoline_targets": sorted(targets & {hex_addr(x) for x in HHA_UI_TRAMPOLINES}),
                    "targets": [row.get("target_va") for row in entries],
                })

    crosswalk_path = ROOT / "output/gameplay/save_layout_external_crosswalk.json"
    selector_candidate = {}
    saved_byte_candidate = {}
    player_house_level_query = {}
    if EVENT_HANDLERS.is_file():
        entries = json.loads(EVENT_HANDLERS.read_text())["entries"]
        handler = entries.get("EventFlowSystemActor.EventFlowQueryPlayerHouseLevel")
        getter_decomp = DECOMP / "42bfb0.c"
        evaluator_decomp = DECOMP / "7b1fe0.c"
        if not handler or len(handler.get("slots", [])) <= 6:
            raise AssertionError("missing EventFlowQueryPlayerHouseLevel handler")
        if handler["slots"][6] != "0x42bfb0":
            raise AssertionError({"unexpected_player_house_level_getter": handler["slots"]})
        if not getter_decomp.is_file() or "33dc730" not in getter_decomp.read_text(errors="replace"):
            raise AssertionError("PlayerHouseLevel getter no longer references the HHA selector accessor")
        if not evaluator_decomp.is_file() or "33dc730" not in evaluator_decomp.read_text(errors="replace"):
            raise AssertionError("HHA evaluator selector accessor evidence is missing")
        player_house_level_query = {
            "registered_handler": handler["name"],
            "event_uses": handler.get("event_uses"),
            "vtable": handler.get("vtable"),
            "getter_slot_index": 6,
            "getter_va": handler["slots"][6],
            "getter_node_accessor_global_va": "0x33dc730",
            "same_node_accessor_as_hha_evaluator": True,
            "getter_value_normalization": "Reads u32; values > 8 become 0; returns level-1 for raw 1..8 and 0 for raw 0/invalid.",
            "semantic_conclusion": "EventFlow PlayerHouseLevel query and HHA evaluator read the same local 4-byte descriptor; its HouseLevel meaning is established even though the descriptor itself has no recovered local name.",
        }
    if crosswalk_path.is_file():
        crosswalk = json.loads(crosswalk_path.read_text())
        for row in crosswalk.get("vtable_crosswalk", []):
            if row.get("sample_node") == "0x17cd80":
                selector_candidate = {
                    "local_sample_node": row.get("sample_node"),
                    "local_vtable": row.get("vtable"),
                    "sample_data": row.get("sample_data"),
                    "size": row.get("size"),
                    "instances": row.get("instances"),
                    "external_matches": row.get("matches", []),
                    "confidence_note": "The local descriptor is unnamed. The registered PlayerHouseLevel query reads the same accessor, while HouseLevel remains the exact external offset/size candidate rather than local RTTI proof.",
                }
            if row.get("sample_node") == "0x18b058":
                saved_byte_candidate = {
                    "local_sample_node": row.get("sample_node"),
                    "local_vtable": row.get("vtable"),
                    "sample_data": row.get("sample_data"),
                    "size": row.get("size"),
                    "instances": row.get("instances"),
                    "external_matches": row.get("matches", []),
                    "confidence_note": "The one-byte local sample has no exact external path and no local semantic name.",
                }

    selector_and_saved_flag = {
        "selector": {
            "evaluator_va": "0x7b1fe0",
            "node_accessor_global_va": "0x33dc730",
            "read_type": "u32",
            "invalid_value_behavior": "values > 8 are clamped to 0",
            "semantic_name": "PlayerHouseLevel",
            "local_descriptor_name": None,
            "switch_values": {
                "2": {"area_denominator": 36, "area_count": 1},
                "3": {"area_denominator": 64, "area_count": 1},
                "4": {"area_denominator": 100, "area_count": 2},
                "5": {"area_denominator": 136, "area_count": 3},
                "6": {"area_denominator": 172, "area_count": 4},
                "7": {"area_denominator": 232, "area_count": 5},
                "8": {"area_denominator": 292, "area_count": 6},
            },
            "eventflow_semantic_cross_reference": player_house_level_query,
            "save_layout_candidate": selector_candidate,
        },
        "saved_grade_mail_flag_source": {
            "evaluator_va": "0x7b1fe0",
            "helper_va": "0xf95610",
            "helper_read": "signed byte at SavePlayerHouse + 0x263d0",
            "stored_evaluator_offset": "0x158",
            "setter_flag": "cPlayer:HHAGradeMailFlag",
            "setter_conditions": ["player index is nonzero", "selector > 1", "saved byte != -1"],
            "related_house_updater_va": "0xf949c0",
            "related_record_builder_va": "0xf95620",
            "related_house_updater_behavior": "For house levels 4-6 and a non--1 byte, 0xf95620 queues record code 0x19 and sets RcoWallFtrRemoveHouseRemodel from the byte.",
            "adjacent_byte_use": "0xf95ba0 compares a candidate against signed bytes +0x263d0 and +0x263d1; 0xf95ca0 serializes both when non--1.",
            "save_layout_candidate": saved_byte_candidate,
            "semantic_name": None,
            "confidence_note": "Native reads and consumers are identified, but the byte's local field name and its relationship to grade-mail delivery are unresolved.",
        },
    }

    fixed_points = {
        "function_va": "0x7b4720",
        "input_record_offset": "0x110",
        "input_value_type": "signed i32",
        "milestone_thresholds": [10000, 20000, 30000, 50000, 70000, 100000, 150000],
        "progress_member_size_bytes": "0x23c",
        "progress_update": "When the +0x110 value reaches the next band and its saved milestone index is behind, the function increments that index and calls 0x7b52d0.",
        "limit": "These are fixed-point progression cutoffs; no mapping from them or from +0x136c to the displayed S/A/B rank thresholds is proven.",
    }

    decomp_hashes = {}
    for name in ("7b1dd0", "7b1fe0", "7b1960", "7b29d0", "7b4720", "7b4a20",
                 "7b4fc0", "7b5b00", "7b6470", "aba970", "aba9d0", "abb250",
                 "abb3f0", "ac77a0", "abf610", "7b53b0", "7b55e0", "7b5e60", "7b61e0",
                 "7b8420", "f71be0", "f71cd0"):
        path = DECOMP / f"{name}.c"
        if path.exists():
            decomp_hashes[f"{name}.c"] = hsha(path)

    result = {
        "schema": "acnh-re/hha-report-queue-static/1",
        "native_elf_sha256": hsha(NSO),
        "core_bucket_report_call_chain": core_chain,
        "report_record_builder_nso_va": "0xac77a0",
        "report_queue_append_nso_va": "0xabf610",
        "report_branches": report_branches,
        "grade_mail_label_candidate_crosswalk": grade_label_crosswalk,
        "build_celebration_native_route": build_celebration_route,
        "score_total_to_report_bridge": score_total_bridge,
        "shared_queue_lifecycle": queue_lifecycle,
        "selector_and_saved_flag_source": selector_and_saved_flag,
        "fixed_point_progression_thresholds": fixed_points,
        "ui_localization": {
            "native_functions": ui_localization_refs,
            "trampoline_pointer_arrays": ui_pointer_arrays,
            "us_en_resource_inventory": localized_inventory(),
            "limits": [
                "0xac2e30 and 0xac3360 reference localized HHA UI message IDs, but no direct call from the shared queue consumer to these builders is established.",
                "Only message IDs, labels, and counts are exported; localized message bodies are deliberately omitted.",
            ],
        },
        "mail_lookup": {
            "indexed_hha_mail_actions": hha_mail_rows,
            "indexed_grade_flag_eventflow_accesses": grade_flag_eventflow_rows,
            "native_flag_references": flag["referencing_functions"],
            "native_flag_name_ja": flag["name_ja"],
        },
        "decomp_sha256": decomp_hashes,
        "scope": (
            "Static references establish HHA score/report record creation, a shared queue lifecycle, "
            "the HHA report-record vtable consumer and localized formatter route selecting MAIL_SP_HHA_Grade, "
            "fixed-point progression cutoffs, and the label-byte mapping. They do not establish HHAGradeMailFlag "
            "consumption, mailbox insertion/delivery, or displayed rank point cutoffs."
        ),
    }
    db.close()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"output": str(OUT),
                      "core_edges": len(core_chain),
                      "report_branches": len(report_branches),
                      "queue_lifecycle_helpers": len(queue_lifecycle["helpers"]),
                      "localized_hha_resources": len(result["ui_localization"]["us_en_resource_inventory"]),
                      "indexed_hha_mail_actions": len(hha_mail_rows),
                      "indexed_grade_flag_eventflow_accesses": len(grade_flag_eventflow_rows)},
                     indent=2))


if __name__ == "__main__":
    main()
