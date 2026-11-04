#!/usr/bin/env python3
"""Cross-reference native save vtables against a named public save schema.

The input schema is optional external metadata. This tool preserves ambiguity and
does not treat a cross-version offset/size match as a confirmed C++ RTTI name.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_URL = (
    "https://github.com/Treeki/CylindricalEarth/blob/"
    "bb09c0ee71a4aa6011de088b88ea55fdee0bf6e9/"
    "savefile/save_schema_111_103.json"
)
SCHEMA_GIT_BLOB = "541781086431876e827de9ffb6be1f268c71517c"


def _hex(value):
    return int(value, 16) if isinstance(value, str) else int(value)


def crosswalk(save_layout, schema):
    types = schema["types"]
    by_id = {int(key): value for key, value in types.items()}
    root_pair = next(
        ((key, value) for key, value in by_id.items()
         if value.get("name") == "::Game::SaveLand"
         and value.get("size") == _hex(save_layout["members"][0]["size"])),
        None,
    )
    if root_pair is None:
        raise ValueError("schema has no ::Game::SaveLand matching local root size")
    root_id, root = root_pair

    def find_matches(type_id, base, target, size, path, depth=0, seen=None):
        if depth > 24:
            return []
        seen = set() if seen is None else seen
        visit = (int(type_id), base)
        if visit in seen:
            return []
        seen.add(visit)
        type_def = by_id.get(int(type_id))
        if not type_def:
            return []
        matches = []
        if base == target and type_def.get("size") == size:
            matches.append({"path": path, "type": type_def["name"], "kind": "struct_size"})

        for field in type_def.get("fields", []):
            field_base = base + int(field["offset"])
            dims = field.get("length") or [1, 1]
            dims = [int(dims[0] or 1), int(dims[1] or 1)]
            field_type = by_id.get(int(field["type"]))
            element_size = int(field.get("size") or (field_type or {}).get("size") or 0)
            total_size = element_size * math.prod(dims)
            if not total_size or not (field_base <= target < field_base + total_size):
                continue

            rel = target - field_base
            row = rel // (element_size * dims[1])
            col = (rel // element_size) % dims[1]
            suffix = ""
            element_base = field_base
            if math.prod(dims) > 1:
                suffix = f"[{row}]" + (f"[{col}]" if dims[1] > 1 else "")
                element_base += (row * dims[1] + col) * element_size
            field_path = f"{path}.{field['name']}{suffix}"

            if field_base == target and total_size == size:
                matches.append({
                    "path": field_path,
                    "type": (field_type or {}).get("name", "primitive"),
                    "kind": "field_size",
                })
            if field_type and field_type.get("fields"):
                matches.extend(find_matches(
                    field["type"], element_base, target, size, field_path,
                    depth + 1, set(seen),
                ))
        return matches

    local_member_by_node = {entry["node"]: entry for entry in save_layout["members"]}

    def depth_aligned(matches, depth):
        return [match for match in matches if match["path"].count(".") == depth]

    rows = []
    for entry in save_layout["type_census"]:
        target, size = _hex(entry["sample_data"]), _hex(entry["size"])
        matches = find_matches(root_id, 0, target, size, "SaveLand")
        matches = list({(m["path"], m["type"], m["kind"]): m for m in matches}.values())
        struct_types = sorted({m["type"] for m in matches if m["kind"] == "struct_size"})
        field_types = sorted({m["type"] for m in matches if m["kind"] == "field_size"})
        sample_member = local_member_by_node.get(entry["sample_node"])
        aligned = depth_aligned(matches, sample_member["depth"]) if sample_member else []
        aligned_struct_types = sorted({m["type"] for m in aligned if m["kind"] == "struct_size"})
        if len(struct_types) == 1:
            status = "one_struct_type_candidate"
        elif struct_types:
            status = "multiple_struct_type_candidates"
        elif matches:
            status = "field_only_candidate"
        else:
            status = "no_exact_path"
        rows.append({
            "vtable": entry["vtable"],
            "size": entry["size"],
            "sample_node": entry["sample_node"],
            "sample_data": entry["sample_data"],
            "instances": entry["instances"],
            "status": status,
            "depth_reference": ({"local_depth": sample_member["depth"], "sample_node": entry["sample_node"]}
                                 if sample_member else None),
            "depth_aligned_struct_type_candidates": aligned_struct_types,
            "depth_aligned_matches": sorted(aligned, key=lambda m: (m["kind"], m["path"], m["type"])),
            "struct_type_candidates": struct_types,
            "field_type_candidates": field_types,
            "matches": sorted(matches, key=lambda m: (m["kind"], m["path"], m["type"])),
        })

    counts = {
        "vtable_count": len(rows),
        "exact_offset_and_size_path": sum(bool(row["matches"]) for row in rows),
        "one_struct_type_candidate": sum(row["status"] == "one_struct_type_candidate" for row in rows),
        "multiple_struct_type_candidates": sum(row["status"] == "multiple_struct_type_candidates" for row in rows),
        "field_only_candidate": sum(row["status"] == "field_only_candidate" for row in rows),
        "no_exact_path": sum(row["status"] == "no_exact_path" for row in rows),
        "vtable_samples_with_member_depth": sum(row["depth_reference"] is not None for row in rows),
        "depth_aligned_one_struct_type_candidate": sum(
            len(row["depth_aligned_struct_type_candidates"]) == 1 for row in rows
        ),
    }
    member_rows = []
    for entry in save_layout["members"]:
        matches = find_matches(root_id, 0, _hex(entry["data"]), _hex(entry["size"]), "SaveLand")
        matches = list({(m["path"], m["type"], m["kind"]): m for m in matches}.values())
        aligned = depth_aligned(matches, entry["depth"])
        aligned_struct_types = sorted({
            match["type"] for match in aligned
            if match["kind"] == "struct_size" and match["type"] != "primitive"
        })
        aligned_named_types = sorted({
            match["type"] for match in aligned if match["type"] != "primitive"
        })
        if len(aligned_struct_types) == 1:
            status = "one_struct_type_candidate"
        elif aligned_struct_types:
            status = "multiple_struct_type_candidates"
        elif aligned:
            status = "field_or_primitive_only_candidate"
        else:
            status = "no_exact_path"
        member_rows.append({
            "node": entry["node"],
            "parent": entry["parent"],
            "depth": entry["depth"],
            "data": entry["data"],
            "size": entry["size"],
            "local_name": entry.get("name"),
            "status": status,
            "depth_aligned_named_type_candidates": aligned_named_types,
            "depth_aligned_struct_type_candidates": aligned_struct_types,
            "depth_aligned_matches": sorted(aligned, key=lambda m: (m["kind"], m["path"], m["type"])),
            "matches": sorted(matches, key=lambda m: (m["kind"], m["path"], m["type"])),
        })
    counts.update({
        "member_count": len(member_rows),
        "member_depth_aligned_exact_paths": sum(bool(row["depth_aligned_matches"]) for row in member_rows),
        "member_one_struct_type_candidate": sum(row["status"] == "one_struct_type_candidate" for row in member_rows),
        "member_multiple_struct_type_candidates": sum(row["status"] == "multiple_struct_type_candidates" for row in member_rows),
        "member_field_or_primitive_only_candidate": sum(row["status"] == "field_or_primitive_only_candidate" for row in member_rows),
        "member_no_exact_path": sum(row["status"] == "no_exact_path" for row in member_rows),
    })
    return {
        "schema": "acnh.save-layout-schema-crosswalk.v1",
        "external_schema": {
            "url": SCHEMA_URL,
            "git_blob_sha": SCHEMA_GIT_BLOB,
            "root_type": root["name"],
            "root_size": hex(root["size"]),
            "version_note": "The external schema file is named save_schema_111_103; the local executable is the supplied 1.0.0 build.",
        },
        "method": "Compare native vtable sample_data and size, and selected member data offsets and sizes, with paths under external ::Game::SaveLand. When a native sample node is present in the local member tree, align path depth to local node depth to distinguish same-address wrapper/field candidates. Retain all candidates; names are cross-version evidence, not local RTTI proof.",
        "counts": counts,
        "member_crosswalk": member_rows,
        "vtable_crosswalk": rows,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--save-layout", type=Path, default=ROOT / "output/gameplay/save_layout.json")
    parser.add_argument("--schema", type=Path, required=True, help="Downloaded save_schema_111_103.json")
    parser.add_argument("--output", type=Path, default=ROOT / "output/gameplay/save_layout_external_crosswalk.json")
    args = parser.parse_args()
    save_layout_bytes = args.save_layout.read_bytes()
    save_layout = json.loads(save_layout_bytes)
    schema = json.loads(args.schema.read_text())
    result = crosswalk(save_layout, schema)
    result["local_save_layout_sha256"] = hashlib.sha256(save_layout_bytes).hexdigest()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result["counts"], sort_keys=True))


if __name__ == "__main__":
    main()
