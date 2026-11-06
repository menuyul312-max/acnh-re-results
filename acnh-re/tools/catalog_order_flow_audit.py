#!/usr/bin/env python3
"""Extract the catalog-mail and online-shopping unlock paths from Obj_RcoMachine."""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT_ROOT = Path("/workspace/acnh-re/output")
SOURCE_ID = 494
HANDLER_KEY = "EventFlowSystemActor.EventFlowActionCatalogMailSend"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    args = parser.parse_args()
    root = args.output_root
    source = json.loads((root / "decoded/00494.json").read_text())
    flow = next(fc for fc in source["data"]["flowcharts"] if fc["name"] == "Obj_RcoMachine")
    handlers = json.loads((root / "binary/event_handlers_resolved.json").read_text())
    actions_by_actor = [actor.get("actions", []) for actor in flow["actors"]]
    queries_by_actor = [actor.get("queries", []) for actor in flow["actors"]]
    events = flow["events"]

    def describe(event_index):
        event = events[event_index]
        record = {"event_index": event_index, "source_event_name": event["name"], "type": event["type"]}
        if event["type"] == "action":
            actor = event.get("actor", 0)
            record.update(action=actions_by_actor[actor][event["action"]], params=event.get("params"),
                          next=event.get("next"))
        elif event["type"] == "switch":
            actor = event.get("actor", 0)
            record.update(query=queries_by_actor[actor][event["query"]], params=event.get("params"),
                          cases=event.get("cases", []))
        elif event["type"] == "subflow":
            record.update(flowchart=event.get("flowchart"), entry_point=event.get("entry_point"),
                          next=event.get("next"))
        return record

    selections = {
        "RcoMachineOnlineShopping": [58, 138, 60, 78, 80, 79, 82, 81, 84, 85, 83, 86, 87],
        "DeliverVillager": [68, 69, 61, 62, 63, 64, 65, 66, 74, 67, 71, 73, 70, 72, 75],
    }
    entrypoints = flow["entry_points"]
    selected = {}
    for entry, event_ids in selections.items():
        if entry not in entrypoints:
            raise ValueError(f"missing entry point: {entry}")
        selected[entry] = {
            "main_event": entrypoints[entry]["main_event"],
            "events": [describe(event_index) for event_index in event_ids],
        }
    handler = handlers["entries"][HANDLER_KEY]
    result = {
        "schema": "acnh-re/catalog-order-flow-audit/1",
        "evidence_level": "EVENTFLOW_AND_STATIC_HANDLER_TRACE",
        "source": source["source"],
        "source_sha256": source["source_sha256"],
        "entrypoints": selected,
        "catalog_mail_send_handler": {key: handler[key] for key in
            ("name", "event_uses", "parameters", "factory", "constructor", "vtable", "slots", "slot_span_evidence")},
        "catalog_mail_send_static_method_trace": {
            "function": "0x33a570",
            "string_references": ["SendLetter"],
            "calls": ["0xf62e90", "0xf73ea0"],
            "limitation": "The resolver does not assign the method's vtable slot a semantic role; this is a static association only.",
        },
        "unlock_threshold": {"flag": "cLifeSupportAchievement:BuyItemCatalog", "border": 100,
                             "check_type": 3, "player_flag": "cPlayer:MainmenuOnlineShopping",
                             "application": "cCatalog", "event_type": "cInstall"},
        "open": ["Which items UICatalogHandling accepts and how prices/order limits work",
                 "Actual item mail payload construction and delivery arrival timing",
                 "Whether ItemMailboxCatalogData governs this mail flow or a separate mailbox UI"],
    }
    output = ROOT / "output/gameplay/catalog_order_flow_audit.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({key: value for key, value in result.items() if key != "entrypoints"}, indent=2))


if __name__ == "__main__":
    main()
