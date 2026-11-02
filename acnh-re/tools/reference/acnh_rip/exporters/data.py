"""Phase 2: export every table, parameter file and message archive to JSON.

Output (generated/data/):
  bcsv/<Table>.json         {"source", "columns": [...], "rows": [...]}
  byml/<relative path>.json BYML trees; binary blobs are written next to the
                            JSON as <name>.<key>.bin and referenced as {"$bin": file}
  static/<path in pack>.json  the 1,764 BYML of Pack/StaticParam.pack (Param/Actor,
                            Param/Fish, Param/Weather, ...), same encoding as byml/
  msg/<lang>/<archive>.json {"<msbt path>": {"<label>": text}}
  items.json                ItemParam rows joined with their display names
"""
import json
import re
from pathlib import Path

from ..config import ROMFS, OUT
from ..formats import bcsv, byml, msbt, sarc, compression
from .. import hashdict

DATA = OUT / "data"


def _dump(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")))


def export_bcsv():
    out = DATA / "bcsv"
    stats = {"tables": 0, "columns": 0, "named_columns": 0}
    for p in sorted((ROMFS / "Bcsv").glob("*.bcsv")):
        t = bcsv.load(p)
        _dump(out / f"{p.stem}.json", {"source": f"Bcsv/{p.name}", **t})
        stats["tables"] += 1
        stats["columns"] += len(t["columns"])
        stats["named_columns"] += sum(c["type_source"] == "name" for c in t["columns"])
    return stats


def _key_name(k):
    # BYML dictionary keys stored as hex CRC32 strings; resolve when known.
    if re.fullmatch(r"[0-9a-f]{1,8}", k):
        return hashdict.get()["plain"].get(int(k, 16), f"h_{int(k, 16):08x}")
    return k


def _jsonify(x, bin_base: Path, path=()):
    if isinstance(x, dict):
        return {_key_name(k): _jsonify(v, bin_base, path + (_key_name(k),)) for k, v in x.items()}
    if isinstance(x, list):
        return [_jsonify(v, bin_base, path + (str(i),)) for i, v in enumerate(x)]
    if isinstance(x, bytes):
        name = f"{bin_base.name}.{'.'.join(path) or 'root'}.bin"
        f = bin_base.parent / name
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(x)
        return {"$bin": name, "size": len(x)}
    return x


def export_byml():
    out = DATA / "byml"
    n = 0
    for p in sorted(ROMFS.rglob("*.byml")):
        rel = p.relative_to(ROMFS).with_suffix("")
        tree = byml.load(p)
        _dump(out / rel.with_suffix(".json"), _jsonify(tree, out / rel))
        n += 1
    return {"byml_files": n}


def export_static_params():
    out = DATA / "static"
    files = sarc.read_sarc(compression.read_file(ROMFS / "Pack/StaticParam.pack"))
    n = errors = 0
    for name, blob in sorted(files.items()):
        if not name.endswith(".byml"):
            continue
        rel = Path(name).with_suffix("")
        try:
            tree = byml.read_byml(blob)["root"]
        except byml.BymlError:
            errors += 1
            continue
        _dump(out / rel.with_suffix(".json"), _jsonify(tree, out / rel))
        n += 1
    return {"static_params": n, "static_param_errors": errors}


def export_messages(langs=None):
    out = DATA / "msg"
    n_msgs = 0
    for p in sorted((ROMFS / "Message").glob("*.sarc.zs")):
        m = re.match(r"(.+)_([A-Z]{2}[a-z]{2})\.sarc\.zs$", p.name)
        if not m:
            continue
        archive, lang = m.groups()
        if langs and lang not in langs:
            continue
        files = sarc.read_sarc(compression.read_file(p))
        res = {}
        for name, b in sorted(files.items()):
            if name.endswith(".msbt"):
                res[name] = msbt.read_msbt(b)
                n_msgs += len(res[name])
        _dump(out / lang / f"{archive}.json", res)
    return {"messages": n_msgs}


def _plain_text(t):
    if isinstance(t, dict):
        t = t["text"]
    return re.sub(r"\[/?tag[^\]]*\]", "", t)


def export_items(lang="USen"):
    """Join ItemParam with item display names (STR_ItemName_* labels end in the UniqueID)."""
    table = json.loads((DATA / "bcsv" / "ItemParam.json").read_text())
    strings = json.loads((DATA / "msg" / lang / "String.json").read_text())
    names = {}
    for path, msgs in strings.items():
        if not path.startswith("Item/STR_ItemName_"):
            continue
        for label, text in msgs.items():
            m = re.match(r"(.+)_(\d+)$", label)
            if m:
                names[int(m.group(2))] = {"name": _plain_text(text), "msg": f"{path}:{label}"}
    items = []
    for row in table["rows"]:
        uid = row["UniqueID"]
        item = {"UniqueID": uid, **row}
        if uid in names:
            item["display_name"] = names[uid]["name"]
            item["display_name_source"] = names[uid]["msg"]
        items.append(item)
    _dump(DATA / "items.json", {"source": "Bcsv/ItemParam.bcsv + Message/String_%s" % lang,
                                "lang": lang, "items": items})
    return {"items": len(items), "items_with_name": sum("display_name" in i for i in items)}


def run():
    stats = {}
    stats.update(export_bcsv())
    stats.update(export_byml())
    stats.update(export_static_params())
    stats.update(export_messages())
    stats.update(export_items())
    _dump(DATA / "_stats.json", stats)
    return stats
