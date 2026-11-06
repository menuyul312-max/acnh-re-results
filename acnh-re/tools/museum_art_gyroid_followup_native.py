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
            "input_selector_source": "OwlDonationDone passes its event context +0x2a8 to F780E0; DA3FC0 uses its first byte, replacing values >7 with 0xff.",
            "query_behavior": "EF62F0 queries mode 2. EAA8C0 returns 0xffffffff if the current state token mismatches or the selected state view is absent/errored; otherwise it returns the byte at that view +0xb0d. F780E0 forwards the returned low byte into F78130.",
            "known_duplicate_gate_effect": "F77F60 treats marker 0xff as a non-duplicate exemption; F773F0 does not read marker bytes when counting accepted records.",
            "remaining_meaning": "The successful state object's +0xb0d field and its runtime producer have no semantic label in the captured data; 0xff can also be a returned field value.",
        },
        "static_findings": static,
        "hook_counts": {hex(address): count for address, count in sorted(hook_counts.items())},
        "limits": [
            "No live save file or live table-manager memory is available; the SaveMuseum records and table manager are reconstructed fixtures.",
            "The native item key lookup and field getter are exercised across every local ItemParam row, but item-flag variants are not tested.",
            "No art-specific item/filter/handler path is proven in the captured data; this does not establish that the full game has no art donations.",
            "The 0xff marker can be returned by a failed/mismatched context-state lookup, but the byte at the successful state object +0xb0d has no gameplay label in the dump.",
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
