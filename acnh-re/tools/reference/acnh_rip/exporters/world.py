"""Phase 5: island presets -> world JSON for the Godot FieldBuilder.

Facts used (each verified against the data, see ASSUMPTIONS.md "Derived"):
  * FieldPreset*_LandMaking holds a binary blob of 112 x 96 cells x 14 bytes,
    row-major (level coherence 0.98 row-major vs 0.92 per-acre ordering).
  * cell bytes: u16[0] unit id -> FieldLandMakingUnitModelParam.UniqueID;
    byte 4 = rotation in 90 degree steps (seam error 0.64 vs >3 for others);
    byte 12 = terrain level. Bytes 2 and 5..11, 13 are kept raw (meaning unknown).
  * unit models are 10 x 10 units (FldUnit Base_0 spans -5..5); one level is
    15 units (cliff models drop 15.0x; 95% exact edge matches at 15).
  * Item presets use a 224 x 192 grid (2 per land cell); X key h_696eda33 has the
    wider range, Z key h_13ae8953. Structure presets use the 112 x 96 land grid.
  * ItemPreset values store mItemSaveParam; the low 16 bits are an item id that
    resolves to FgMainParam.UniqueID (60000-60612: trees, weeds, flowers) or
    ItemParam.UniqueID; upper bits are kept raw in save_param.
"""
import json
from pathlib import Path

from ..config import ROMFS, OUT
from ..formats import sarc, compression, bfres

DATA = OUT / "data"
WORLD = OUT / "world"
GRID_W, GRID_H, CELL_BYTES = 112, 96, 14
CELL_SIZE, LEVEL_HEIGHT = 10.0, 15.0
UNIT_ARCHIVES = ["FldUnit", "FldUnitCliff", "FldUnitRiver", "FldUnitFall", "FldUnitRoadBrick",
                 "FldUnitRoadDarkSoil", "FldUnitRoadFanPattern", "FldUnitRoadMyDesign", "FldUnitRoadSand",
                 "FldUnitRoadSoil", "FldUnitRoadStone", "FldUnitRoadTile", "FldUnitRoadWood"]


def _unit_model_archives():
    """model name -> archive name, read from the unit archives themselves."""
    out = {}
    for arch in UNIT_ARCHIVES:
        p = ROMFS / "Model" / f"{arch}.Nin_NX_NVN.zs"
        if not p.exists():
            continue
        for n, b in sarc.read_sarc(compression.read_file(p)).items():
            if b[:4] == b"FRES":
                for m in bfres.Bfres(b).models():
                    out[m["name"]] = arch
    return out


def _load(rel):
    return json.loads((DATA / rel).read_text())


def export_preset(preset, units, model_arch, items_by_id, fg_by_id):
    base = DATA / "byml/Param/Field/MainFieldPreset"
    land = json.loads((base / f"FieldPreset{preset}_LandMaking.json").read_text())
    blob_ref = next(iter(next(iter(land.values())).values()))
    blob = (base / blob_ref["$bin"]).read_bytes()
    if len(blob) != GRID_W * GRID_H * CELL_BYTES:
        raise ValueError(f"{preset}: unexpected land blob size {len(blob)}")
    cells, missing = [], set()
    for i in range(GRID_W * GRID_H):
        c = blob[i * CELL_BYTES:(i + 1) * CELL_BYTES]
        uid = c[0] | c[1] << 8
        row = units.get(uid)
        model = f"{row['h_39b5a93d']}_{row['Variation']}" if row else None
        if model and model not in model_arch:
            missing.add(model)
        cells.append([uid, model, model_arch.get(model), c[4], c[12], c.hex()])
    out = {"preset": preset, "grid": [GRID_W, GRID_H], "cell_size": CELL_SIZE,
           "level_height": LEVEL_HEIGHT, "cell_fields": ["unit_id", "model", "archive", "rotation",
                                                         "level", "raw"],
           "cells": cells, "missing_unit_models": sorted(missing)}

    st = json.loads((base / f"StructurePreset{preset}.json").read_text())
    entries = next(iter(next(iter(st.values())).values()))
    out["structure_points"] = {"note": "list key h_29ef254c; meaning of the points is not named in the data",
                               "grid": "land", "points": [[e["h_962fa959"], e["h_eceffa39"]] for e in entries]}

    it = json.loads((base / f"ItemPreset{preset}.json").read_text())
    entries = next(iter(next(iter(it.values())).values()))
    items = []
    for e in entries:
        # key CRC32 0xd1541039 resolves to "mItemSaveParam" via the main.elf dictionary
        save = next(iter(e["mItemSaveParam"].values()))
        iid = save & 0xFFFF
        rec = {"x": e["h_696eda33"], "z": e["h_13ae8953"], "layer": e["h_3d1976e3"],
               "item_id": iid, "save_param": save}
        if iid in fg_by_id:
            fg = fg_by_id[iid]
            # h_39b5a93d is the model inside archive h_48ef0398 (e.g. PltTreeOak4 in PltTreeOak);
            # h_87bf00e8 names an extra model (e.g. PltTreeApple for fruit trees)
            rec.update(table="FgMainParam", kind=fg["h_9b7aa0a0"], model=fg["h_39b5a93d"],
                       model_archive=fg["h_48ef0398"], extra_model=fg["h_87bf00e8"])
        elif iid in items_by_id:
            info = items_by_id[iid]
            rec.update(table="ItemParam", label=info.get("h_48ef0398"), model=info.get("h_3febc642"),
                       name=info.get("display_name"))
        items.append(rec)
    out["items"] = {"grid": "item (2 per land cell)", "list": items}

    plaza = json.loads((base / f"FieldPreset{preset}_EventPlaza.json").read_text())
    out["event_plaza_raw"] = plaza
    WORLD.mkdir(parents=True, exist_ok=True)
    (WORLD / f"MainField_{preset}.json").write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")))
    return len(missing)


def run():
    units = {r["UniqueID"]: r for r in _load("bcsv/FieldLandMakingUnitModelParam.json")["rows"]}
    items_by_id = {i["UniqueID"]: i for i in _load("items.json")["items"]}
    fg_by_id = {r["UniqueID"]: r for r in _load("bcsv/FgMainParam.json")["rows"]}
    model_arch = _unit_model_archives()
    presets = [r["h_6e1ac981"].replace("FieldPreset", "") for r in _load("bcsv/FieldMainFieldParam.json")["rows"]]
    done, miss = 0, 0
    for p in presets:
        if (DATA / f"byml/Param/Field/MainFieldPreset/FieldPreset{p}_LandMaking.json").exists():
            miss += export_preset(p, units, model_arch, items_by_id, fg_by_id)
            done += 1
    # outer ring templates/parts are exported as-is; template selection is code-side (unknown)
    WORLD.mkdir(parents=True, exist_ok=True)
    for t in ("FieldOutsideTemplate", "FieldOutsideParts"):
        (WORLD / f"{t}.json").write_text((DATA / f"bcsv/{t}.json").read_text())
    (WORLD / "unit_models.json").write_text(json.dumps(model_arch, indent=0))
    return {"presets": done, "missing_unit_models": miss, "unit_models": len(model_arch)}
