"""F6: AnimationSequence state machines -> generated/asb/.

  generated/asb/<name>.json       parsed ASB (nodes = states, transitions, condition
                                  words, parameter table, warp tracks, event lists)
  generated/asb/_registry.json    every clip name referenced by the 83 files with
                                  its resolution against generated/models/*/anim,
                                  plus the per-file node/transition counts.

Nothing is inferred silently: every field whose meaning is not proven keeps its raw
word and the assumption ID (ASSUMPTIONS.md D-042..D-051, A-052..A-059) is cited
in the key name or in WORKLOG_F6.md.
"""
import json
from collections import defaultdict

from ..config import ROMFS, OUT
from ..formats import asb

ASB_DIR = OUT / "asb"


def _anim_index():
    """clip stem (lower case) -> sorted list of archives that ship it."""
    idx = defaultdict(set)
    models = OUT / "models"
    if models.is_dir():
        for d in models.iterdir():
            ad = d / "anim"
            if not ad.is_dir():
                continue
            for f in ad.glob("*.json"):
                idx[f.stem.lower()].add(d.name)
    return {k: sorted(v) for k, v in idx.items()}


def _states(doc):
    """Attach the transition span [first_transition, next_first) to every node.

    The spans partition the transition array in 81/81 files that have nodes
    (D-048).  When two nodes share a first_transition (18 files) the earlier one
    gets an empty span -- that is reported, not silently dropped.
    """
    nodes = doc["nodes"]
    trans = doc["transitions"]
    order = sorted(range(len(nodes)), key=lambda k: (nodes[k]["first_transition"], k))
    out = []
    for pos, k in enumerate(order):
        lo = nodes[k]["first_transition"]
        hi = (nodes[order[pos + 1]]["first_transition"]
              if pos + 1 < len(order) else len(trans))
        out.append((lo, max(hi, lo), k))
    return out


def _export(stem, doc, anims, reg):
    trans = doc["transitions"]
    nodes = doc["nodes"]
    spans = _states(doc)
    span_of = {k: (lo, hi) for lo, hi, k in spans}

    states = []
    for nd in nodes:
        lo, hi = span_of.get(nd["index"], (0, 0))
        clips = []
        for tr in trans[lo:hi]:
            c = tr["condition"].get("clip")
            if c and c not in clips:
                clips.append(c)
        states.append({
            "index": nd["index"],
            "name": nd["name"],
            "property_index": nd["property_index"],
            # node word1 is 0 in 1157/1159 nodes; the two nonzero ones also read
            # as string pool offsets (A-055).  Both readings are exported.
            "property_word1_as_pool_string": nd.get("word1_pool_string"),
            "first_transition": nd["first_transition"],
            "transition_span": [lo, hi],
            "clips": clips,
            "hash": nd["hash"],
        })

    trs = []
    for tr in trans:
        c = tr["condition"]
        rec = {
            "index": tr["index"],
            "source": tr["source_raw"],
            "flags": tr["flags"],
            "target": tr["target_raw"],
            "target_in_space": tr["target"] is not None,
            "target_in_nodes": tr["target_in_nodes"],
            "target_variant": tr["target_variant"],
            "group": tr["group"],
            "condition_offset": c["offset"],
            "flags_word": c.get("flags"),
            "clip": c.get("clip"),
            "value": c.get("value_raw"),
            "value_float": c.get("value_float"),
            "words": c.get("words", []),
            "event_list": None,
            "hash": tr["hash"],
        }
        if tr["event_list_offset"]:
            rec["event_list"] = tr["event_list_offset"]
        trs.append(rec)

        # clip bookkeeping for the registry
        clip = rec["clip"]
        if clip is not None:
            e = reg["clips"].setdefault(clip, {"uses": 0, "files": set()})
            e["uses"] += 1
            e["files"].add(stem)

    evs = {}
    for el in doc["event_lists"]:
        evs[str(el["offset"])] = [v["name"] for v in el["values"]]

    problems = []
    # `target` is now "inside the w17+1 target space" (D-045); a target past the
    # node table is not a problem in itself, it is recorded per transition.
    oor = [t["index"] for t in trans if t["target"] is None]
    if oor:
        problems.append({"kind": "target_outside_target_space", "count": len(oor),
                         "first": oor[:10]})
    beyond = [t["index"] for t in trans if t["target"] is not None and not t["target_in_nodes"]]
    if beyond:
        problems.append({"kind": "target_beyond_node_table", "count": len(beyond),
                         "first": beyond[:10]})
    outside = [t["index"] for t in trans if not t["condition"].get("in_region", False)]
    if outside:
        problems.append({"kind": "condition_outside_region", "count": len(outside),
                         "first": outside[:10]})
    empty = [s["index"] for s in states if s["transition_span"][0] == s["transition_span"][1]]
    if empty:
        problems.append({"kind": "state_without_transitions", "count": len(empty),
                         "first": empty[:10]})
    inexact = sum(1 for t in trans if not t["condition"].get("end_exact", False))
    if inexact:
        problems.append({"kind": "last_condition_block_bound_inexact", "count": inexact})

    return {
        "source": f"AnimationSequence/{stem}.asb",
        "name": doc["name"],
        "version": doc["version"],
        "counts": doc["counts"],
        "regions": doc["regions"],
        "states": states,
        "transitions": trs,
        "parameters": doc["parameter_table"],
        "event_lists": evs,
        "warp_tracks": [{"index": w["index"], "offset": w["offset"],
                         "words": w["words"], "strings": w["strings"]}
                        for w in doc["warps"]],
        "property_table": doc["property_table"],
        "problems": problems,
    }


def run():
    ASB_DIR.mkdir(parents=True, exist_ok=True)
    anims = _anim_index()
    reg = {"clips": {}}
    files = 0
    total = defaultdict(int)
    errs = []
    per_file = {}
    for p in sorted((ROMFS / "AnimationSequence").glob("*.asb")):
        try:
            doc = asb.load(p)
        except asb.AsbError as e:
            errs.append(str(e))
            continue
        stem = p.stem
        out = _export(stem, doc, anims, reg)
        (ASB_DIR / f"{stem}.json").write_text(
            json.dumps(out, ensure_ascii=False, separators=(",", ":")))
        files += 1
        total["states"] += out["counts"]["nodes"]
        total["transitions"] += out["counts"]["transitions"]
        total["warps"] += out["counts"]["warps"]
        total["parameter_cases"] += out["counts"]["parameter_cases"]
        for pr in out["problems"]:
            total["problem_" + pr["kind"]] += pr["count"]
        per_file[stem] = {"states": out["counts"]["nodes"],
                          "transitions": out["counts"]["transitions"],
                          "warps": out["counts"]["warps"],
                          "parameter_cases": out["counts"]["parameter_cases"]}

    clips = {}
    resolved = unresolved = 0
    self_ref = {}
    empty_name = {"uses": 0, "files": set()}
    for name, v in sorted(reg["clips"].items(),
                          key=lambda kv: (-kv[1]["uses"], kv[0])):
        if name == "":
            empty_name["uses"] += v["uses"]
            empty_name["files"] |= v["files"]
            continue
        hit = anims.get(name.lower())
        if hit:
            resolved += 1
            clips[name] = {"uses": v["uses"], "files": len(v["files"]),
                           "archives": hit}
            continue
        if v["files"] == {name}:
            # the pool string equals the name of every file that uses it.  The
            # measurement is D-049; reading it as "self reference to the ASB
            # file" rather than a clip name is A-057.
            self_ref[name] = {"uses": v["uses"], "files": len(v["files"])}
            continue
        unresolved += 1
        clips.setdefault("_unresolved", {})[name] = {
            "uses": v["uses"], "files": len(v["files"])}
    un = clips.pop("_unresolved", {})
    registry = {
        "source_dir": "AnimationSequence",
        "files": per_file,
        "totals": dict(total),
        "clips": {"unique": resolved + unresolved, "resolved": resolved,
                  "unresolved": unresolved, "by_name": clips},
        "unresolved_clips": un,
        "self_reference_names": self_ref,
        "empty_name": {"uses": empty_name["uses"],
                       "files": len(empty_name["files"])},
        "errors": errs,
    }
    (ASB_DIR / "_registry.json").write_text(
        json.dumps(registry, indent=1, ensure_ascii=False))
    return {"files": files, "states": total["states"],
            "transitions": total["transitions"],
            "clips_unique": resolved + unresolved, "clips_resolved": resolved,
            "clips_unresolved": unresolved,
            "problems": {k[8:]: v for k, v in total.items() if k.startswith("problem_")},
            "errors": len(errs)}