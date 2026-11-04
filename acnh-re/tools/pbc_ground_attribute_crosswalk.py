#!/usr/bin/env python3
"""Emit the local ColGround row-index mapping used to interpret PBC material bytes.

The external HeavenTool enum defines PBC material IDs as row indices. This tool
keeps those indices distinct from this build's ColGround UniqueID column.
"""
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = Path(os.environ.get("ACNH_RESEARCH_ROOT", ROOT))


def main():
    path = SOURCE_ROOT / "output/tables_resolved/ColGroundAttributeParam.json"
    table = json.loads(path.read_text())
    columns = {c["name"]: i for i, c in enumerate(table["columns"]) if c.get("name")}
    required = {"UniqueID", "DebugName", "WaterCheck", "PlayerNoEntry", "NpcNoEntry"}
    assert required <= columns.keys(), columns.keys()
    rows = table["rows"]
    assert len(rows) == table["row_count"] == 63
    unique_ids = [row[columns["UniqueID"]] for row in rows]
    assert len(set(unique_ids)) == len(unique_ids)

    crosswalk = []
    for row_index, row in enumerate(rows):
        crosswalk.append({
            "pbc_material_row_index": row_index,
            "local_unique_id": row[columns["UniqueID"]],
            "debug_name": row[columns["DebugName"]],
            "water_check": row[columns["WaterCheck"]],
            "player_no_entry": row[columns["PlayerNoEntry"]],
            "npc_no_entry": row[columns["NpcNoEntry"]],
        })

    assert crosswalk[26]["local_unique_id"] == 29
    assert crosswalk[27]["local_unique_id"] == 30
    assert crosswalk[28]["local_unique_id"] == 31
    result = {
        "scope": "Build-local ColGroundAttributeParam row-index crosswalk for the four PBC material bytes. PBC byte=row index is corroborated by the pinned HeavenTool enum; local native paths resolve ground IDs to row indices, but no local PBC payload is available to test every value.",
        "source": {
            "table": "ColGroundAttributeParam",
            "source_id": table["source_id"],
            "source": table["source"],
            "row_count": len(rows),
            "raw_sha256": table["raw"]["sha256"],
        },
        "external_reference": {
            "repository": "acnhmodding/HeavenTool",
            "commit": "e3ddf830a4ae360657917d3d598c79170273d056",
            "tile_type_source": "https://github.com/acnhmodding/HeavenTool/blob/e3ddf830a4ae360657917d3d598c79170273d056/HeavenTool.IO/FileFormats/PBC/TileType.cs",
            "declared_encoding": "zero-based row indices in ColGroundAttributeParam",
            "pinned_enum_entries": 73,
        },
        "local_native_evidence": {
            "pbc_attribute_reader": "0x181cd0 returns bytes at record offsets 48..51 in direction order; see output/mechanics/terrain_native.json.",
            "row_index_resolver": "0x18b570 floor override resolves Floorboards UniqueID through ColGroundAttributeParam and returns the row index; see output/mechanics/room_floor_ground_native.json.",
            "limit": "No local native trace directly binds each PBC byte to this table. A later user archive exposes values matching row indices 0..62 and the decoded table, but the byte-to-row-index encoding still relies on the pinned external format contract; see output/ui_island/manifests_pbc_audit.json."
        },
        "version_difference": {
            "local_rows": len(rows),
            "local_indices_present": [0, len(rows) - 1],
            "external_enum_values_missing_from_local_table": list(range(len(rows), 73)),
            "row_index_vs_unique_id_example": [
                {"row_index": i, "unique_id": crosswalk[i]["local_unique_id"], "debug_name": crosswalk[i]["debug_name"]}
                for i in (25, 26, 27, 28, 29)
            ],
        },
        "rows": crosswalk,
    }
    out = ROOT / "output/ui_island/pbc_ground_attribute_crosswalk.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"output": str(out.relative_to(ROOT)), "rows": len(rows),
                      "example_indices_26_28_unique_ids": [crosswalk[i]["local_unique_id"] for i in (26, 27, 28)]}, indent=2))


if __name__ == "__main__":
    main()
