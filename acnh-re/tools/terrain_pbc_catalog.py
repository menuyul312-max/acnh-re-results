#!/usr/bin/env python3
"""Link terrain-unit ModelName rows to native PBC resource-name generation."""
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = Path(os.environ.get("ACNH_RESEARCH_ROOT", ROOT))
sys.path.insert(0, str(ROOT / "tools"))
from native_image import Image  # noqa: E402


def main():
    image = Image()
    table = json.loads((SOURCE_ROOT / "output/tables_resolved/FieldLandMakingUnitModelParam.json").read_text())
    relation = json.loads((SOURCE_ROOT / "output/relations/terrain_native.json").read_text())
    manifest = json.loads((SOURCE_ROOT / "output/manifest.json").read_text())
    columns = {c["name"]: i for i, c in enumerate(table["columns"]) if c.get("name")}
    assert table["row_count"] == 246
    assert {"UniqueID", "Variation", "ModelName"} <= columns.keys()

    rows = []
    archive_counts = Counter()
    missing_archive_map = []
    for row in table["rows"]:
        uid = row[columns["UniqueID"]]
        model_name = row[columns["ModelName"]]
        model = relation["models"].get(str(uid))
        assert model is not None, uid
        archive = model["variants"][0].get("archive")
        if archive is None:
            missing_archive_map.append(uid)
        else:
            archive_counts[archive] += 1
        rows.append({
            "unique_id": uid,
            "variation_limit": row[columns["Variation"]],
            "model_name": model_name,
            "native_resource_name_candidate": model_name + "_pbc",
            "archive_group_hint": archive,
            "archive_name_candidate": archive + "_pbc" if archive else None,
            "native_model_variants": model["variants"],
        })

    group_literal = image.cstring(0x2955998)
    groups = [item.strip() for item in group_literal.split(",") if item.strip()]
    expected_groups = [
        "FldUnit_pbc", "FldUnitCliff_pbc", "FldUnitFall_pbc", "FldUnitRiver_pbc",
        "FldUnitRoadStone_pbc", "FldUnitRoadSoil_pbc", "FldUnitRoadBrick_pbc",
        "FldUnitRoadDarkSoil_pbc", "FldUnitRoadFanPattern_pbc", "FldUnitRoadSand_pbc",
        "FldUnitRoadTile_pbc", "FldUnitRoadWood_pbc",
    ]
    assert groups == expected_groups, groups
    format_string = image.cstring(0x2946397)
    assert format_string == "%s_pbc", format_string

    absent_from_manifest = []
    for entry in manifest["entries"]:
        source = str((entry.get("source", ""), entry.get("member", "")))
        if ".pbc" in source.lower() or "fldunit" in source.lower():
            absent_from_manifest.append(source)
    assert not absent_from_manifest

    code = image.read(0x16A43C, 0x4C)
    listing = image.disasm(0x16A43C, 0x4C)
    assembly = "\n".join(
        f"{i.address:08x} {i.bytes.hex():8s} {i.mnemonic:8s} {i.op_str}"
        for i in listing
    ) + "\n"
    (ROOT / "output/ui_island/terrain_unit_pbc_loader.asm").write_text(assembly)

    result = {
        "scope": "Static resource-name path from terrain unit ModelName rows to the PBC resource helper. This does not recover or parse the expected PBC members.",
        "source_elf_sha256": hashlib.sha256(image.data).hexdigest(),
        "table": {
            "name": "FieldLandMakingUnitModelParam",
            "source_id": table["source_id"],
            "source": table["source"],
            "row_count": table["row_count"],
            "source_sha256": table["raw"]["sha256"],
            "model_name_field": {"crc32": "0x39b5a93d", "native_reader": "0x16bae0"},
            "variation_field": {"crc32": "0xc733aa77", "type": "u16 maximum valid index"},
        },
        "native_path": {
            "function": "0x169b90",
            "relevant_block": "0x16a43c-0x16a488",
            "steps": [
                "0x16bae0 reads a ModelName BCSV field (hash 0x39b5a93d).",
                "0x12930 formats the returned name with literal '%s_pbc'.",
                "0xc9bc0 receives the generated resource name and resource manager arguments.",
            ],
            "group_literal_va": "0x2955998",
            "archive_groups": groups,
            "native_loader_call_is_not_execution_proof": True,
        },
        "catalog": {
            "rows": len(rows),
            "unique_model_names": len({r["model_name"] for r in rows}),
            "unique_candidate_archive_members": len({(r["archive_name_candidate"], r["native_resource_name_candidate"]) for r in rows}),
            "rows_without_archive_hint": missing_archive_map,
            "archive_row_counts_from_terrain_native_relation": dict(sorted(archive_counts.items())),
            "entries": rows,
        },
        "corpus_check": {
            "pbc_or_fldunit_source_manifest_matches": len(absent_from_manifest),
            "meaning": "No PBC/FldUnit-named member is present in the currently indexed source manifest. This says nothing about resources outside that supplied corpus.",
        },
        "limits": [
            "Archive group assignment for each row is linked from decoded terrain metadata; only the 12 group names and ModelName_PBC formatting are directly visible in native code here.",
            "One unit (UniqueID 41, Cliff8) has no archive hint in the current terrain metadata link.",
            "Presence, byte layout, geometry, collision semantics and runtime load success for any generated PBC name remain unverified.",
            "The PBC resource helper 0xc9bc0 was not executed with the original resource archive.",
        ],
        "instruction_evidence": {
            "loader_block_sha256": hashlib.sha256(code).hexdigest(),
            "model_name_reader_va": "0x16bae0",
            "model_name_reader_sha256": hashlib.sha256(image.read(0x16BAE0, 0x12C)).hexdigest(),
            "format_string_va": "0x2946397",
            "format_string": format_string,
            "archive_list_sha256": hashlib.sha256(group_literal.encode()).hexdigest(),
        },
    }
    out = ROOT / "output/ui_island/terrain_unit_pbc_catalog.json"
    out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({
        "output": str(out.relative_to(ROOT)),
        "table_rows": len(rows),
        "unique_model_names": result["catalog"]["unique_model_names"],
        "archive_groups": len(groups),
        "source_manifest_pbc_hits": len(absent_from_manifest),
    }, indent=2))


if __name__ == "__main__":
    main()
