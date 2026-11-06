#!/usr/bin/env python3
"""Audit museum art/gyroid gaps and reproduce the donation-count gate natively.

The native ItemParam UniqueID lookup and ItemKind getter run over the extracted
ItemParam BCSV. Museum save/view contexts are synthetic; only their manager
wrappers and item-validity/equivalence helpers are controlled.
"""
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import struct
import sys
import zlib

ROOT = Path(__file__).resolve().parent.parent
DATA_ROOT = Path(os.environ.get("ACNH_RE_SOURCE_ROOT", "/workspace/acnh-re"))
OUT = ROOT / "output/gameplay/museum_art_gyroid_followup/native.json"
TOOLS = ROOT / "tools"
sys.path.insert(0, str(DATA_ROOT / ".deps"))
sys.path.insert(0, str(TOOLS))

from native_emulator import Sandbox, regs  # noqa: E402
import inventory_requirements_native as item_tables  # noqa: E402
from nso_sandbox import load_nso, NSO_SHA256 as MAIN_NSO_SHA256  # noqa: E402
from unicorn import UC_HOOK_CODE  # noqa: E402

ITEM_VIEW_INIT = 0xA9C290
ITEM_KIND_GETTER = 0xA9F670
ITEM_KIND_INDEX = 0x1665EA0
DONATION_COUNT = 0xF773F0
DONATION_THRESHOLD_QUERY = 0x416260
KIND_GLOBALS = (0x35EC944, 0x35EC948, 0x35EC94C)
KIND_CODES = {"Fossil": 70, "Fish": 65, "Insect": 64}
SLOT_COUNT = 0x400
SAVE_SIZE = 0x3404
ITEMS_OFFSET = 0x1004
MARKERS_OFFSET = 0x3004


def load_json(path):
    return json.loads(path.read_text())


def label(value):
    if isinstance(value, dict):
        values = value.get("labels") or []
        if values:
            return values[0]
    return value


def compact_flow_event(event, flowchart):
    result = {key: event.get(key) for key in ("name", "type", "params", "cases", "next") if key in event}
    actor_id = event.get("actor")
    if actor_id is not None:
        actor = flowchart["actors"][actor_id]
        if "action" in event:
            result["action"] = actor["actions"][event["action"]]
        if "query" in event:
            result["query"] = actor["queries"][event["query"]]
    return result


def static_audit(data_root, item_table, item_cols, kind_labels):
    out = data_root / "output"
    flow_files = sorted((out / "decoded").glob("*.json"))
    owl_donation_flows = []
    gyroid_flows = []
    fake_rate_declarations = []
    museum_threshold_events = []
    owl_donation_done_events = []
    for path in flow_files:
        try:
            decoded = load_json(path)
        except (OSError, json.JSONDecodeError):
            continue
        if decoded.get("format") != "BFEVFL":
            continue
        for flow in decoded.get("data", {}).get("flowcharts", []):
            actors = flow.get("actors", [])
            all_queries = [query for actor in actors for query in actor.get("queries", [])]
            all_actions = [action for actor in actors for action in actor.get("actions", [])]
            if "EventFlowQueryOwlDonationFakeRate" in all_queries:
                used = [event for event in flow.get("events", [])
                        if event.get("type") == "switch" and
                        actors[event["actor"]]["queries"][event["query"]] == "EventFlowQueryOwlDonationFakeRate"]
                fake_rate_declarations.append({
                    "source": decoded.get("source"), "flowchart": flow.get("name"),
                    "declaration_count": all_queries.count("EventFlowQueryOwlDonationFakeRate"),
                    "event_uses": len(used),
                })
            if any(query in all_queries for query in ("EventFlowQueryOwlDonationItemType",
                                                       "EventFlowQueryOwlDonationFakeRate")) or \
                    any("DonationCheckItemType" in json.dumps(event, ensure_ascii=False)
                        for event in flow.get("events", [])):
                owl_donation_flows.append({
                    "source": decoded.get("source"), "flowchart": flow.get("name"),
                    "queries": sorted({query for query in all_queries if "OwlDonation" in query}),
                    "item_filter_names": sorted({
                        str((event.get("params") or {}).get("ItemFilterType"))
                        for event in flow.get("events", [])
                        if (event.get("params") or {}).get("ItemFilterType")
                    }),
                })
            for event in flow.get("events", []):
                if event.get("type") != "switch":
                    continue
                query = actors[event["actor"]]["queries"][event["query"]]
                if query == "EventFlowQueryMuseumDonationNumCheck":
                    museum_threshold_events.append({
                        "source": decoded.get("source"), "flowchart": flow.get("name"),
                        **compact_flow_event(event, flow),
                    })
            for event in flow.get("events", []):
                if event.get("type") != "action":
                    continue
                action = actors[event["actor"]]["actions"][event["action"]]
                if action == "EventFlowActionOwlDonationDone":
                    owl_donation_done_events.append({
                        "source": decoded.get("source"), "flowchart": flow.get("name"),
                        **compact_flow_event(event, flow),
                    })
            if "Gyroid" in decoded.get("source", "") or "Gyroid" in flow.get("name", ""):
                gyroid_flows.append({
                    "source": decoded.get("source"), "flowchart": flow.get("name"),
                    "actions": sorted({action for action in all_actions
                                       if any(word in action for word in ("PublicWorks", "Money", "Donation"))}),
                    "queries": sorted({query for query in all_queries
                                       if any(word in query for word in ("Donation", "PublicWorks"))}),
                    "events": [compact_flow_event(event, flow) for event in flow.get("events", [])
                               if any(word in json.dumps(event, ensure_ascii=False)
                                      for word in ("RcoBuildBridgeSlopeStatusCounter",
                                                   "FinishDonationBuildBridgeSlope"))],
                })

    handlers = load_json(out / "binary/event_handlers_resolved.json")["entries"]
    fake_rate_registered = any(entry.get("name") == "EventFlowQueryOwlDonationFakeRate"
                               for entry in handlers.values())
    owl_donation_done_handler = next((entry for entry in handlers.values()
                                      if entry.get("name") == "EventFlowActionOwlDonationDone"), None)

    item_filter = load_json(out / "tables_resolved/ItemFilter.json")
    filter_cols = {column["name"]: index for index, column in enumerate(item_filter["columns"])}
    item_filters = {}
    for row in item_filter["rows"]:
        name = row[filter_cols["Label"]]
        if name not in {"RcoDonationForMuseum", "OwlTentDonation0", "OwlTentDonation1",
                        "OwlDonation", "OwlCommentary", "OwlFossilJudgement"}:
            continue
        codes = sorted({row[filter_cols[f"ItemKind{i}"]] for i in range(1, 16)
                        if row[filter_cols[f"ItemKind{i}"]] != 113})
        item_filters[name] = {
            "item_kind_codes": codes,
            "item_kind_labels": [kind_labels[code] if code < len(kind_labels) else "<out-of-range>"
                                 for code in codes],
            "check_donation": row[filter_cols["CheckDonation"]],
            "item_num": row[filter_cols["ItemNum"]],
        }

    fake_art_col = item_cols["FakeArtConvertId"]
    fake_art_nonzero = sum(row[fake_art_col] != 0 for row in item_table["rows"])
    museum_tables = []
    for path in sorted((out / "tables_resolved").glob("Museum*.json")):
        table = load_json(path)
        museum_tables.append({"name": path.stem, "rows": table.get("row_count")})

    gyroid_path = out / "decoded/00486.json"
    gyroid = load_json(gyroid_path)["data"]["flowcharts"][0]
    gyroid_actions = sorted({action for actor in gyroid["actors"] for action in actor.get("actions", [])})
    gyroid_queries = sorted({query for actor in gyroid["actors"] for query in actor.get("queries", [])})
    gyroid_keys = sorted({(event.get("params") or {}).get("AccessKey")
                          for event in gyroid["events"]
                          if (event.get("params") or {}).get("AccessKey")})
    gyroid_museum_refs = [key for key in gyroid_keys if "Museum" in key]
    tent_entries = load_json(out / "decoded/00558.json")["data"]["flowcharts"][0]
    tent_event_map = {event["name"]: event for event in tent_entries["events"]}
    threshold_event = tent_event_map["Event0"]
    threshold_case0 = next(case["event"] for case in threshold_event["cases"] if case["value"] == 0)
    case0_event = tent_event_map[f"Event{threshold_case0}"]
    case0_next = case0_event.get("next")
    case0_next_event = tent_event_map[f"Event{case0_next}"] if case0_next is not None else None
    if case0_next_event and case0_next_event.get("type") == "action":
        actor = tent_entries["actors"][case0_next_event["actor"]]
        case0_next_action = actor["actions"][case0_next_event["action"]]
    else:
        case0_next_action = None

    return {
        "captured_eventflows_scanned": sum(
            1 for path in flow_files
            if (lambda d: d.get("format") == "BFEVFL")(load_json(path))
        ),
        "owl_donation_flows": owl_donation_flows,
        "owl_fake_rate": {
            "declarations": fake_rate_declarations,
            "registered_native_handler": fake_rate_registered,
        },
        "owl_donation_done": {
            "events": owl_donation_done_events,
            "native_handler_slots": owl_donation_done_handler.get("slots") if owl_donation_done_handler else None,
        },
        "museum_donation_threshold_events": museum_threshold_events,
        "tent_expansion_threshold_path": {
            "source": load_json(out / "decoded/00558.json").get("source"),
            "query_event": compact_flow_event(threshold_event, tent_entries),
            "case_0_event": compact_flow_event(case0_event, tent_entries),
            "case_0_next_event": compact_flow_event(case0_next_event, tent_entries) if case0_next_event else None,
            "case_0_next_action": case0_next_action,
            "expansion_flags_in_flow": sorted({
                (event.get("params") or {}).get("AccessKey")
                for event in tent_entries["events"]
                if "Museum" in str((event.get("params") or {}).get("AccessKey", "")) or
                   "FutaReadyForMuseum" in str((event.get("params") or {}).get("AccessKey", ""))
            }),
        },
        "item_filters": item_filters,
        "itemparam": {
            "rows": item_table["row_count"],
            "source": item_table["source"],
            "raw_sha256": item_table["raw"]["sha256"],
            "fake_art_convert_id_nonzero_rows": fake_art_nonzero,
        },
        "museum_tables": museum_tables,
        "gyroid": {
            "flow": gyroid_path.name,
            "source": load_json(gyroid_path).get("source"),
            "flowchart": gyroid["name"],
            "actions": [action for action in gyroid_actions
                        if any(word in action for word in ("PublicWorks", "Money", "TenKey"))],
            "queries": [query for query in gyroid_queries if "Donation" in query],
            "access_keys": gyroid_keys,
            "museum_access_keys": gyroid_museum_refs,
            "conclusion": "The located Gyroid flow pays a public-works bridge/slope project; it does not invoke the museum intake/save path.",
        },
    }


def runtime_row_boundary_audit(static):
    """Record which parts of the CFAD0 key path exist only at runtime.

    The module's BSS range is derived from the supplied NSO segments. The
    field contracts are from the static decompilation and EventFlow/table
    index; this function intentionally does not synthesize row values.
    """
    nso_path = ROOT / "inputs/additional_exefs/main"
    segments, bss_size, _mod0, _image = load_nso(nso_path)
    nso_hash = hashlib.sha256(nso_path.read_bytes()).hexdigest()
    if nso_hash != MAIN_NSO_SHA256:
        raise AssertionError(f"unexpected main NSO hash: {nso_hash}")

    segment_ranges = [
        {"va_start": hex(va), "file_end_va": hex(va + len(data)), "bytes": len(data)}
        for va, data in segments
    ]
    bss_start = max(va + len(data) for va, data in segments)
    bss_end = bss_start + bss_size
    global_cells = [0x33D3CB0, 0x33D4FF0]
    if any(not (bss_start <= cell < bss_end) for cell in global_cells):
        raise AssertionError({"bss": (hex(bss_start), hex(bss_end)),
                              "global_cells": [hex(cell) for cell in global_cells]})

    index_path = DATA_ROOT / "output/index.sqlite"
    with sqlite3.connect(f"file:{index_path}?mode=ro", uri=True) as index_db:
        cfad0_callers = sorted(row[0] for row in index_db.execute(
            "SELECT DISTINCT owner_va FROM direct_calls WHERE target_va = ?", (0xCFAD0,)
        ))
    if cfad0_callers != [0xCF420]:
        raise AssertionError({"unexpected direct CFAD0 callers": [hex(x) for x in cfad0_callers]})

    pointer_map_path = DATA_ROOT / "output/binary/code_pointer_arrays.json"
    pointer_map = load_json(pointer_map_path)
    pointer_targets = (0xCFAD0, 0xCFCE0, 0xD0090, 0xD0310, 0xE684F0, 0xE68280)
    pointer_map_hits = {hex(target): [] for target in pointer_targets}
    for array in pointer_map:
        for entry in array.get("entries", []):
            target = int(entry.get("target_va", "0"), 16)
            if target in pointer_targets:
                pointer_map_hits[hex(target)].append({
                    "array_va": array.get("start_va"),
                    "pointer_va": entry.get("pointer_va"),
                })

    flow_events = static["owl_donation_done"].get("events", [])
    flow_use_counts = Counter(event.get("flowchart") for event in flow_events)
    if flow_use_counts != Counter({
        "SNPC_owl_01_Museum_Donation": 2,
        "SNPC_rco_01_Tent_1_Entries": 1,
    }):
        raise AssertionError({"unexpected OwlDonationDone EventFlow use counts": flow_use_counts})
    event_param_keys = sorted({
        key for event in flow_events for key in (event.get("params") or {})
    })
    if event_param_keys != [
        "EntryVariableKeyBool_MultiComplete",
        "EntryVariableKeyInt_CompleteRoomType",
    ]:
        raise AssertionError({"unexpected OwlDonationDone EventFlow params": event_param_keys})

    def rows_by_key(table_name, wanted):
        table_path = DATA_ROOT / "output/tables_resolved" / f"{table_name}.json"
        table = load_json(table_path)
        columns = [column["name"] for column in table["columns"]]
        rows = [dict(zip(columns, row)) for row in table["rows"]]
        found = {row["Key"]: row for row in rows if row.get("Key") in wanted}
        if set(found) != set(wanted):
            raise AssertionError({"table": table_name, "missing_keys": sorted(set(wanted) - set(found))})
        return found

    player_flags = rows_by_key("EventFlagsPlayerParam", {"OwlDonationDone"})
    land_flags = rows_by_key("EventFlagsLandParam", {
        "MuseumGrowupEnable1", "MuseumConstruction1", "Museum2Built"
    })

    museum_table_schemas = {}
    for table_name in (
        "MuseumFossilDonateInfo", "MuseumNPCLayoutInfo", "MuseumNPCSilhouette",
        "MuseumNPCSpotTalk", "MuseumNameboardInfo", "MuseumWatchPoint",
    ):
        table = load_json(DATA_ROOT / "output/tables_resolved" / f"{table_name}.json")
        museum_table_schemas[table_name] = {
            "rows": len(table["rows"]),
            "columns": [column["name"] for column in table["columns"]],
        }
    resolved_table_files = sorted((DATA_ROOT / "output/tables_resolved").glob("*.json"))
    museum_named_table_files = [path.stem for path in resolved_table_files
                                if "museum" in path.stem.lower()]
    local_save_layout = load_json(DATA_ROOT / "output/gameplay/save_layout.json")
    layout_root = next(member for member in local_save_layout["members"]
                       if member.get("parent") is None)
    local_museum_member = next(member for member in local_save_layout["members"]
                               if member.get("node") == "0x20a168")
    if (layout_root.get("size"), local_museum_member.get("data"),
            local_museum_member.get("size")) != ("0x4fa0d8", "0x411a80", "0x3404"):
        raise AssertionError({"unexpected local SaveLand.Museum layout": {
            "root": layout_root, "museum": local_museum_member,
        }})

    return {
        "source_nso_sha256": nso_hash,
        "file_backed_segments": segment_ranges,
        "zero_fill_bss_range": {"start_va": hex(bss_start), "end_va_exclusive": hex(bss_end),
                                "bytes": bss_size},
        "runtime_global_pointer_cells": [
            {"va": hex(cell), "file_backed": False,
             "role": "CFAD0/EAA8C0 state-manager pointer cell; runtime value is not in the NSO image"}
            for cell in global_cells
        ],
        "static_reference_inventory": {
            "function_index_direct_callers": [hex(address) for address in cfad0_callers],
            "code_pointer_array_catalog": {
                "sequences_scanned": len(pointer_map),
                "entries_scanned": sum(len(array.get("entries", [])) for array in pointer_map),
                "target_hits": pointer_map_hits,
                "scope_limit": "The catalog lists relocated code-pointer sequences, not arbitrary object memory or CFAD0 runtime rows; a miss does not exclude indirect references outside this catalog.",
            },
            "resolved_tables_scanned": len(resolved_table_files),
            "museum_named_tables": museum_named_table_files,
            "eventflows_scanned": static["captured_eventflows_scanned"],
            "owl_donation_done_uses": len(flow_events),
            "local_save_layout_crosscheck": {
                "root_size": layout_root["size"],
                "museum_node": local_museum_member["node"],
                "museum_gsave_land_relative_data_offset": local_museum_member["data"],
                "museum_size": local_museum_member["size"],
            },
        },
        "cfad0_runtime_row_list": {
            "enumerator_va": "0xcfad0",
            "direct_caller_va": "0xcf420",
            "count_offset": "+0xf8",
            "pointer_array_offset": "+0x100",
            "row_payload": ["u32 key at row+0", "u32 flags at row+4; bit0 selects kind 0/1"],
            "state_writer_call": "E684F0(manager, row[1] & 1, row[0])",
            "row_list_mutators": ["0xcfce0", "0xd0090", "0xd0310"],
            "storage_status": "The row pointer array and its records are object-owned runtime state; CFAD0 dereferences them and the captured static image has no literal row-value array.",
            "concrete_key_values": None,
        },
        "owl_donation_done_context_selection": {
            "action_va": "0x2c2410",
            "context_to_writer_va": ["0xf780e0", "0xef62f0", "0xeaa8c0"],
            "selector_normalizer_va": "0xda3fc0",
            "selector_rule": "Reads the context's first byte; values above 7 become 0xff.",
            "selector_resolver_va": "0xeaa990",
            "resolver_rule": "For session modes below 2, the selector is used as the state-row index and the row must be active. In mode 2, the selector must equal the current session-context byte from CC85B0, then F68930 maps it to an active row index.",
            "query_rule": "EAA8C0 returns the selected active kind-0 row's +0xb0d byte; nonzero kind, inactive/missing row, or selector mismatch returns 0xffffffff.",
            "eventflow_action_uses": flow_events,
            "eventflow_parameter_keys": event_param_keys,
            "interpretation_limit": "The selector participates in context/active-row selection, but its mapping to a donor/player number is not proven. A separate NHSE save-format/editor cross-check labels the returned saved byte as the donating player number.",
            "eventflow_action_use_counts": dict(sorted(flow_use_counts.items())),
        },
        "external_save_format_crosscheck": {
            "repository": "kwsch/NHSE",
            "commit": "cb0745415945776f73375bf0a434a8babf059307",
            "source_files": {
                "museum_struct": {
                    "url": "https://github.com/kwsch/NHSE/blob/cb0745415945776f73375bf0a434a8babf059307/NHSE.Core/Structures/Misc/Museum.cs",
                    "blob_sha": "ead687405381cb1e48ba832f2354d678e5b076f7",
                },
                "museum_editor": {
                    "url": "https://github.com/kwsch/NHSE/blob/cb0745415945776f73375bf0a434a8babf059307/NHSE.Core/Structures/Misc/MuseumEditor.cs",
                    "blob_sha": "08758d0ec31ba9558954051b00f8b7603c6ac2eb",
                },
                "version_1_0_offsets": {
                    "url": "https://github.com/kwsch/NHSE/blob/cb0745415945776f73375bf0a434a8babf059307/NHSE.Core/Save/Offsets/MainSaveOffsets10.cs",
                    "blob_sha": "a756da713c8b0fe28b974f55767db542b97165d1",
                },
                "editor_form": {
                    "url": "https://github.com/kwsch/NHSE/blob/cb0745415945776f73375bf0a434a8babf059307/NHSE.WinForms/Subforms/Map/MuseumEditor.cs",
                    "blob_sha": "3f1feaf364e05bdbea94bf5029bd6c5e13e35a4d",
                },
            },
            "corroborated_layout": {
                "size": "0x3404",
                "entry_count": 1024,
                "dates_offset": "+0x0004",
                "items_offset": "+0x1004",
                "players_offset": "+0x3004",
                "player_bytes": 1024,
                "version_1_0_museum_save_offset": "GSaveLandStart + 0x411a80",
                "version_1_0_gsave_land_start": "0x108",
                "version_1_0_absolute_museum_offset": "0x411b88",
                "local_layout_root_size": layout_root["size"],
                "local_museum_data_offset_relative_to_layout_root": local_museum_member["data"],
            },
            "semantic_crosscheck": "NHSE calls the +0x3004 1024-byte field Players; its editor reads/writes Players[index] and renders entries as 'Player {player} donated a(n) {name}'. This independently labels the saved marker byte as a donor/player number.",
            "scope_limit": "The Museum structure is generic NHSE code; the separate MainSaveOffsets10 source matches this build's v1.0.0 Museum suboffset (+0x411a80 from GSaveLandStart 0x108, absolute MainSave offset 0x411b88; the native layout root size 0x4fa0d8 is the GSaveLand payload). This third-party save-format/editor cross-check does not expose the game's live CFAD0 row list, full u32 keys, runtime selector-to-player mapping, or a same-save day-change trace. NHSE's UI permits byte values 0..255 and does not establish which values the game emits.",
            "semantic_join": "The game's static path stores the selected active kind-0 CFAD0 row key's low byte into SaveMuseum +0x3004+slot; NHSE's crosswalk labels that saved byte as the donor/player number. The low-byte meaning is cross-checked; the full runtime key and selected row values remain unknown.",
        },
        "captured_museum_table_schemas": museum_table_schemas,
        "separate_progression_flag_crosswalk": {
            "EventFlagsPlayerParam": {
                key: {"UniqueID": row["UniqueID"], "DefaultValue": row["DefaultValue"],
                      "MaxValue": row["MaxValue"]}
                for key, row in player_flags.items()
            },
            "EventFlagsLandParam": {
                key: {"UniqueID": row["UniqueID"], "DefaultValue": row["DefaultValue"],
                      "MaxValue": row["MaxValue"]}
                for key, row in land_flags.items()
            },
            "limit": "These EventFlow progression flags are table-backed but do not provide the runtime CFAD0 row list or selected row values; the saved marker's player-number meaning comes from the separate NHSE cross-check.",
        },
        "real_save_day_change_boundary": {
            "static_join": "Accepted-item writer and 20-record flag path target SaveLand.Museum; day-change dispatcher later reads the same member and runs F77050.",
            "native_fixture_scope": "Writer/count/marker/day-change helpers run on controlled or supplied state; the level-2 plus flag fixture advances across two one-day calls.",
            "same_save_end_to_end": False,
            "missing_runtime_evidence": ["a real SaveMuseum image", "live CFAD0 row values", "one same-save trace from donation through MuseumGrowupEnable1 to a later daily transition"],
        },
    }


def run_native_audit():
    item_tables.ROOT = DATA_ROOT
    sb = Sandbox()
    uc = sb.uc
    tables = item_tables.install_item_tables(sb)
    item_table = tables["item_table"]
    cols = tables["item_cols"]
    kind_labels = tables["native_kind_labels"]
    kind_by_crc = {zlib.crc32(name.encode("utf-8")): index
                   for index, name in enumerate(kind_labels)}
    for address, value in zip(KIND_GLOBALS, (KIND_CODES["Fossil"], KIND_CODES["Fish"], KIND_CODES["Insect"])):
        uc.mem_write(address, struct.pack("<I", value))

    # The exact native UID->row adapter and ItemKind field getter run against
    # the raw BCSV. Only generic item-record helpers are replaced.
    controlled_returns = {0xF58D00: 1, 0xF589B0: 0, 0xA9C3A0: 0}
    hook_counts = Counter()

    def hooked_return(engine, address, _size, _user_data):
        if address not in controlled_returns:
            return
        hook_counts[address] += 1
        engine.reg_write(regs.UC_ARM64_REG_X0, controlled_returns[address])
        engine.reg_write(regs.UC_ARM64_REG_PC, engine.reg_read(regs.UC_ARM64_REG_X30))

    uc.hook_add(UC_HOOK_CODE, hooked_return,
                begin=min(controlled_returns), end=max(controlled_returns))

    probe_record = 0x501F0000
    probe_view = 0x501F1000
    uid_mismatches = []
    for row_index, row in enumerate(item_table["rows"]):
        uid = row[cols["UniqueID"]]
        kind_value = row[cols["ItemKind"]]
        kind_hash = int(kind_value["hash"], 16) if isinstance(kind_value, dict) else 0
        expected = kind_by_crc.get(kind_hash, 0)
        uc.mem_write(probe_record, struct.pack("<H", uid) + bytes(6))
        sb.call(ITEM_VIEW_INIT, (probe_view, probe_record), limit=100000)
        actual = sb.call(ITEM_KIND_GETTER, (probe_view,), limit=100000)
        if actual != expected:
            uid_mismatches.append({"uid": uid, "row": row_index, "expected": expected, "actual": actual})
            if len(uid_mismatches) >= 10:
                break

    if uid_mismatches:
        raise AssertionError({"ItemParam native row/key mismatches": uid_mismatches})

    # Synthetic view wrapper for the real native DonationNumCheck query. The
    # query and F773F0 counter run natively; the save-member manager boundary
    # is explicit and controlled.
    view_memory = 0x501F2000
    save_ptr = 0x501F4000
    query_ptr = 0x501F8000
    root_context = 0x501F9000
    uc.mem_write(view_memory, bytes(0x20))
    uc.mem_write(view_memory + 8, struct.pack("<Q", 0))
    uc.mem_write(view_memory + 16, struct.pack("<Q", save_ptr))

    def hook_save_context(engine, address, _size, _user_data):
        if address == 0xEECF00:
            engine.reg_write(regs.UC_ARM64_REG_X0, root_context)
            engine.reg_write(regs.UC_ARM64_REG_PC, engine.reg_read(regs.UC_ARM64_REG_X30))
        elif address == 0xEE9350:
            target = engine.reg_read(regs.UC_ARM64_REG_X0)
            engine.mem_write(target + 8, struct.pack("<Q", view_memory))
            engine.reg_write(regs.UC_ARM64_REG_X0, 0)
            engine.reg_write(regs.UC_ARM64_REG_PC, engine.reg_read(regs.UC_ARM64_REG_X30))
        elif address == 0xEE93D0:
            engine.reg_write(regs.UC_ARM64_REG_X0, 0)
            engine.reg_write(regs.UC_ARM64_REG_PC, engine.reg_read(regs.UC_ARM64_REG_X30))

    for address in (0xEECF00, 0xEE9350, 0xEE93D0):
        uc.hook_add(UC_HOOK_CODE, hook_save_context, begin=address, end=address)

    first_uid_by_kind = {}
    for row in item_table["rows"]:
        kind_value = row[cols["ItemKind"]]
        kind_hash = int(kind_value["hash"], 16) if isinstance(kind_value, dict) else 0
        kind_name = kind_labels[kind_by_crc.get(kind_hash, 0)]
        first_uid_by_kind.setdefault(kind_name, row[cols["UniqueID"]])
    if not all(name in first_uid_by_kind for name in ("Ftr", "Insect", "Fish", "Fossil", "FossilUnknown")):
        raise AssertionError("Expected ItemParam sample kind is missing")

    count_scenarios = {
        "below_20": {"Insect": 7, "Fish": 6, "Fossil": 6},
        "at_20": {"Insect": 7, "Fish": 6, "Fossil": 7},
        "above_20": {"Insect": 7, "Fish": 6, "Fossil": 8},
        "non_donation_kinds_excluded": {
            "Insect": 6, "Fish": 6, "Fossil": 7,
            "FossilUnknown": 10,
            "FishToy": 10,
            "InsectToy": 10,
        },
    }
    results = []
    for scenario, counts in count_scenarios.items():
        sequence = [kind for kind, count in counts.items() for _ in range(count)]
        sequence.extend(["Ftr"] * (SLOT_COUNT - len(sequence)))
        block = bytearray(SAVE_SIZE)
        for slot, kind_name in enumerate(sequence):
            uid = first_uid_by_kind[kind_name]
            struct.pack_into("<HBBI", block, ITEMS_OFFSET + slot * 8, uid, 0, 0, 0)
            block[MARKERS_OFFSET + slot] = 0xFF if kind_name in KIND_CODES else 0x7E
        uc.mem_write(save_ptr, bytes(block))
        count_expected = sum(counts.get(kind, 0) for kind in KIND_CODES)
        for border in (5, 19, 20):
            uc.mem_write(query_ptr, bytes(0x100))
            uc.mem_write(query_ptr + 0xD0, struct.pack("<I", border))
            actual = sb.call(DONATION_THRESHOLD_QUERY, (query_ptr,), limit=10000000)
            expected = int(count_expected < border)
            if actual != expected:
                raise AssertionError({"scenario": scenario, "count": count_expected,
                                      "border": border, "actual": actual, "expected": expected})
            results.append({"scenario": scenario, "supported_record_count": count_expected,
                            "border": border, "native_returns_count_below_border": actual,
                            "expected": expected})

    static = static_audit(DATA_ROOT, item_table, cols, kind_labels)
    runtime_row_boundary = runtime_row_boundary_audit(static)
    donation_type_table = struct.unpack("<7I", sb.image.read(0x29F1E68, 28))
    donation_type_map = {str(kind): (donation_type_table[kind - 65] if 65 <= kind <= 71 else 0)
                         for kind in range(64, 72)}
    return {
        "schema": "acnh-re/museum-art-gyroid-followup/1",
        "native_image_sha256": hashlib.sha256(sb.image.data).hexdigest(),
        "itemparam_native_adapter": {
            "itemparam_raw_sha256": tables["item_raw_sha256"],
            "itemkind_raw_sha256": tables["kind_raw_sha256"],
            "source_rows_checked": item_table["row_count"],
            "unique_id_lookups_checked": item_table["row_count"],
            "mismatches": 0,
            "native_path": [hex(ITEM_VIEW_INIT), hex(ITEM_KIND_INDEX), hex(ITEM_KIND_GETTER)],
            "contract": "A9C290 resolves the item’s first u16 UniqueID through the ItemParam base/count/row map; 1665EA0 derives its raw-BCSV row index; A9F670 reads the ItemKind enum column.",
            "controlled": [
                "the native ItemParam manager, row-pointer map, and enum column vector are reconstructed from the exact local BCSV blobs",
                "0xf58d00 item-record-validity return",
                "0xf589b0 temporary item-view initialization",
                "0xa9c3a0 item-view equivalence/fallback result",
            ],
        },
        "donation_count_native": {
            "query_va": hex(DONATION_THRESHOLD_QUERY),
            "counter_va": hex(DONATION_COUNT),
            "kind_globals": {hex(address): KIND_CODES[label]
                             for address, label in zip(KIND_GLOBALS, ("Fossil", "Fish", "Insect"))},
            "counted_item_kinds": KIND_CODES,
            "save_slots": SLOT_COUNT,
            "marker_bytes_in_counted_slots": "0xff (marker is not read by F773F0; its record and ItemKind still contribute)",
            "native_cases": len(results),
            "mismatches": 0,
            "cases": results,
            "controlled": [
                "SaveLand.Museum view acquisition at EECF00/EE9350/EE93D0",
                "F58D00 item-record-validity return; all 1024 synthetic item records are valid",
            ],
        },
        "save_to_expansion_boundary": {
            "status": "cross-layer path is reconstructed from static native call sites, decoded EventFlow, and separately executed native functions; live end-to-end state is unavailable",
            "steps": [
                {
                    "stage": "accepted item submission",
                    "evidence": "Static FUN_003c2410 at 0x2c2410 opens SaveLand.Museum node +0x20a168 (0x3404 bytes), calls 0xf77e00, then calls 0xf780e0 only when the duplicate/category gate succeeds.",
                    "source": "museum_donation_followup/writer_native.json static_save_member_caller",
                },
                {
                    "stage": "SaveMuseum insertion",
                    "evidence": "The separate writer runner executes 0xf780e0 -> 0xf78130 with a synthetic save block and controlled save/item/state adapters.",
                    "source": "museum_donation_followup/writer_native.json",
                },
                {
                    "stage": "20-record threshold query",
                    "evidence": "Native 0xf773f0 counts Fossil/Fish/Insect records; native 0x416260 returns count < Border. The decoded SNPC_owl_11_Tent_Entries Border=20 case-0 branch is therefore the at-least-20 path and sets MuseumGrowupEnable1.",
                    "source": "donation_count_native and static_findings.tent_expansion_threshold_path",
                },
                {
                    "stage": "daily museum upgrade",
                    "evidence": "The day-change dispatcher 0xf545f0 acquires the same 0x3404 SaveLand.Museum member at node +0x20a168 and calls 0xf77050. With saved level 2, elapsed days [1, 1], and MuseumGrowupEnable1 supplied on entry, the native fixture consumes the flag and reaches level 2 with MuseumConstruction1=1, then reaches level 3 and sets Museum2Built on the next call.",
                    "source": "gameplay_native.json (0xf77050 museum upgrade)",
                },
            ],
            "museum_level_query_mapping": {
                "query_method_va": "0x416b00",
                "normalizer_va": "0xf772c0",
                "mapping_rodata_va": "0x29f1f94",
                "saved_museum_level_to_eventflow_value": {"0": 3, "1": 3, "2": 0, "3": 1, "4": 2},
                "evidence": "0x416b00 reads SaveLand.Museum at node +0x20a168, calls 0xf772c0 (clamp above 4 to 0), and indexes the five-u32 rodata map [3, 3, 0, 1, 2].",
            },
            "remaining_gap": "No captured live game process or real save file connects the accepted donation, the EventFlow flag write, and a later daily pass in one execution. The SaveMuseum writer/counter/query and daily updater use controlled or supplied state at their boundaries. NHSE cross-checks the saved marker byte as a donor/player number, but the active CFAD0 row values and the selector-to-player mapping are runtime data absent from the captured tables.",
        },
        "owl_donation_item_type_static_native_map": {
            "handler_method_va": "0x3d8d10",
            "enum_result_table_va": "0x29f1e68",
            "enum_result_table_u32": list(donation_type_table),
            "item_kind_to_eventflow_result": donation_type_map,
            "item_kind_labels": {str(code): kind_labels[code] for code in range(64, 72)},
            "execution_scope": "Static original instructions and rodata table; no EventFlow callback/context is emulated.",
        },
        "marker_trace_static": {
            "action_method_va": "0x2c2410",
            "writer_wrapper_va": "0xf780e0",
            "writer_va": "0xf78130",
            "query_wrapper_va": "0xef62f0",
            "query_body_va": "0xeaa8c0",
            "stored_marker_offset": "+0x3004 + slot",
            "input_selector_source": "OwlDonationDone method 0x2c2410 passes event context +0x2a8 to F780E0. DA3FC0 reads its first byte and normalizes values above 7 to 0xff; this is the mode-2 query selector, not the saved marker value.",
            "query_behavior": "F780E0 passes the DA3FC0 selector to EF62F0 and forwards EF62F0's return in w0 to F78130. EAA8C0 returns 0xffffffff on context-token mismatch, absent/inactive row, or nonzero state kind; on success it returns the selected active kind-0 row's +0xb0d byte as u8. F78130 rejects the negative 0xffffffff result and stores a successful u8 at SaveMuseum +0x3004 + slot.",
            "saved_marker_value_join": {
                "owl_donation_done_save_member": {"node_offset": "+0x20a168", "size": "0x3404"},
                "accepted_item_gate_va": "0xf77e00",
                "marker_writer_path": ["0x2c2410", "0xf780e0", "0xef62f0", "0xeaa8c0", "0xf78130"],
                "cfad0_runtime_row_path": {
                    "caller_va": "0xcf420",
                    "enumerator_va": "0xcfad0",
                    "runtime_rows": "runtime pointers at param_1+0x100, count at param_1+0xf8; concrete rows are not present in captured static tables",
                    "wrapper_va": "0xe684f0",
                    "writer_va": "0xe68280",
                    "argument_flow": "CFAD0 calls E684F0(manager, second_word & 1, first_u32); E684F0 forwards that first_u32 to E68280, which stores its low byte at the active row +0xb0d.",
                    "query_join": "OwlDonationDone's mode-2 query selects an active state row using its event-context selector and returns that row's +0xb0d byte; this becomes the per-item SaveMuseum marker, which the NHSE save-format/editor cross-check labels as the donor/player number.",
                    "concrete_active_row_keys": "Unavailable: the key values are supplied by the runtime row list, which is not embedded in the extracted EventFlow or table files.",
                },
                "persisted_semantic_label": "donor/player number; game-side producer is the low byte of the selected active kind-0 CFAD0 runtime row key (NHSE save-format/editor cross-check)",
                "byte_domain": "On a successful state query the value is a u8 (0x00..0xff). Query failure returns 0xffffffff and F78130 exits without writing. F77F60 treats a saved 0xff byte as a non-duplicate exemption; static evidence does not show whether any active CFAD0 key has low byte 0xff.",
                "donor_identity_status": "The saved +0x3004 byte is labeled as the donor/player number by the NHSE Museum save-format/editor cross-check. The game's stored value is the low byte of the selected active CFAD0 row key; its concrete runtime full-u32 key and the selector-to-player mapping are still unavailable. Other E68280 callers passing 0..7 are generic state-manager evidence and do not provide Museum's runtime row keys.",
            },
            "state_byte_producer": {
                "producer_va": "0xe68280",
                "lookup_va": "0xe68900",
                "state_record_stride": "0xb28",
                "state_record_slots": 8,
                "successful_query_condition": "EAA8C0 verifies the mode-2 context token, resolves a row index through EAA990/E68900, then returns 0xffffffff unless the row is active and +0xb08 is 0; on success it returns row +0xb0d as u8.",
                "writes": [
                    "E68280 initializes the selected row as kind 3/inactive with u16 +0xb0d = 0x0100; for param_2 < 3 it writes the state kind at +0xb08, active byte +0xb0c = 1, param_3 to byte +0xb0d, and param_4 & 1 at +0xb0e.",
                    "E68280's row is selected from eight 0xb28-byte records; E68900 checks the requested index is below eight and the row active byte at +0xb0c is nonzero.",
                ],
                "direct_callers": [
                    {"va": "0xccd40", "observed_arguments": "two branches call E68280(row, 2, 0, 1); active kind-2 rows are rejected by EAA8C0 mode 2"},
                    {"va": "0xcd9f0", "observed_arguments": "FA4300 maps an identity pair to an existing slot 0..7; on match, E68280(row, 0, slot, 1)"},
                    {"va": "0x2ee460", "observed_arguments": "when FA3C10 finds no pair match, FA4100 allocates the pair in a free slot 0..7; after associated context copies, E68280(row, 0, slot, 1)"},
                    {"va": "0x2f5240", "observed_arguments": "called by 0x2f4f40 with the 0x2f5030 result; 0x2f5030 selects a 0..7 slot whose MakeVillagePlayerFlag query succeeds, or returns 0xffffffff"},
                    {"va": "0xe684f0", "observed_arguments": "wrapper called by 0xcfad0; forwards kind 0/1 and param_3 from a runtime row"},
                ],
                "meaning_status": "The Museum marker path returns the active kind-0 row's +0xb0d byte; CFAD0 populates that byte from the low byte of a runtime row's first u32. NHSE labels the matching SaveMuseum byte as the donating player number. Exact CFAD0 row values and selector-to-player mapping still require runtime evidence; other E68280 callers' 0..7 values are not substitutes for those rows.",
                "evidence": "Static Ghidra decompilation of the original NSO plus bounded fixture output at museum_donation_followup/marker_state_native.json; caller objects and live save state were not executed.",
            },
            "bounded_native_fixture": {
                "runner": "tools/museum_marker_state_native.py",
                "output": "museum_donation_followup/marker_state_native.json",
                "cases": 32,
                "mismatches": 0,
                "scope": "Original E68280/E684F0/E68900/EAA8C0/FA4100/FA4300 bodies; context, state views, and manager memory are synthetic or controlled.",
            },
            "known_duplicate_gate_effect": "F77F60 treats marker 0xff as a non-duplicate exemption; F773F0 does not read marker bytes when counting accepted records.",
            "remaining_meaning": "NHSE's save-format/editor cross-check labels the Museum saved marker as the donor/player number; the game's static path obtains it as the low byte of an active kind-0 CFAD0 runtime row key. The key's concrete runtime full-u32 value, active row list, and selector-to-player mapping remain unobserved. Query failure is 0xffffffff and is rejected by the writer; saved 0xff is instead the duplicate gate's exemption value.",
        },
        "runtime_row_boundary": runtime_row_boundary,
        "static_findings": static,
        "hook_counts": {hex(address): count for address, count in sorted(hook_counts.items())},
        "limits": [
            "No live save file or live table-manager memory is available; the SaveMuseum records and table manager are reconstructed fixtures.",
            "The native item key lookup and field getter are exercised across every local ItemParam row, but item-flag variants are not tested.",
            "No art-specific item/filter/handler path is proven in the captured data; this does not establish that the full game has no art donations.",
            "A bounded state fixture validates native value forwarding and kind/token gates, but its row values are synthetic. The game's static code joins the Museum marker to the active kind-0 CFAD0 key byte; NHSE independently labels the saved byte as the donor/player number. Concrete CFAD0 runtime row values and selector-to-player mapping are unavailable.",
        ],
    }


def main():
    result = run_native_audit()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({
        "itemparam_rows_checked": result["itemparam_native_adapter"]["source_rows_checked"],
        "itemparam_mismatches": result["itemparam_native_adapter"]["mismatches"],
        "native_threshold_cases": result["donation_count_native"]["native_cases"],
        "threshold_mismatches": result["donation_count_native"]["mismatches"],
        "art_filter_names": sorted(result["static_findings"]["item_filters"]),
        "gyroid_flow": result["static_findings"]["gyroid"]["flowchart"],
        "output": str(OUT),
    }, indent=2))


if __name__ == "__main__":
    main()
