"""Phase 7 groundwork: EventFlow graphs + the action/query registry.

  generated/eventflow/<name>.json    parsed BFEVFL (flowcharts, actors, events, entry points)
  generated/eventflow/_registry.json  every "Actor.Action" / "Actor.Query" used by the game with
                                      use counts, files and the parameter keys/types seen.
                                      This is the work list of native functions to port from main.elf.
"""
import json
from collections import defaultdict

from ..config import ROMFS, OUT
from ..formats import bfevfl

EVF = OUT / "eventflow"


def _ptype(v):
    return type(v).__name__ if not isinstance(v, dict) else ("arg" if "$arg" in v else "dict")


def run():
    EVF.mkdir(parents=True, exist_ok=True)
    reg = {"actions": defaultdict(lambda: {"uses": 0, "files": set(), "params": {}}),
           "queries": defaultdict(lambda: {"uses": 0, "files": set(), "params": {}, "case_values": set()})}
    n = errs = 0
    for p in sorted((ROMFS / "EventFlow").glob("*.bfevfl")):
        doc = bfevfl.read_bfevfl(p.read_bytes())
        problems = bfevfl.validate(doc)
        errs += len(problems)
        doc["source"] = f"EventFlow/{p.name}"
        doc["problems"] = problems
        (EVF / f"{p.stem}.json").write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")))
        n += 1
        for fc in doc["flowcharts"]:
            for ev in fc["events"]:
                if ev["type"] not in ("action", "switch"):
                    continue
                actor = fc["actors"][ev["actor"]]
                if ev["type"] == "action":
                    key, kind = f"{actor['name']}.{actor['actions'][ev['action']]}", "actions"
                else:
                    key, kind = f"{actor['name']}.{actor['queries'][ev['query']]}", "queries"
                e = reg[kind][key]
                e["uses"] += 1
                e["files"].add(p.stem)
                for k, v in (ev.get("params") or {}).items():
                    e["params"][k] = _ptype(v)
                for c in ev.get("cases", []):
                    e["case_values"].add(c["value"])
    out = {}
    for kind, d in reg.items():
        out[kind] = {}
        for k, v in sorted(d.items(), key=lambda kv: -kv[1]["uses"]):
            rec = {"uses": v["uses"], "files": len(v["files"]), "params": v["params"],
                   "implemented": False, "main_elf_function": None}
            if "case_values" in v:
                rec["case_values"] = sorted(v["case_values"])
            out[kind][k] = rec
    (EVF / "_registry.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
    return {"files": n, "validation_errors": errs, "actions": len(out["actions"]), "queries": len(out["queries"])}
