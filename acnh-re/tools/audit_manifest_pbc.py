#!/usr/bin/env python3
"""Audit an extracted ACNH manifest ZIP against the local island corpus.

The ZIP is read in place; no members are extracted or executed. The output is
derived metadata only and does not copy PBC geometry into the repository.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path, PurePosixPath
import zipfile


ROOT = Path(__file__).resolve().parents[1]
TABLES = (
    "FieldLandMakingUnitModelParam",
    "FieldOutsideParts",
    "FieldOutsideTemplate",
    "ColGroundAttributeParam",
    "RoomFloorParam",
)
GRID_FIELDS = {
    "unit_id": "unit0",
    "unit_variation": "variation0",
    "unit_rot": "rotation0",
    "road_id": "unit1",
    "road_Sub": "variation1",
    "road_rot": "rotation1",
    "elevation": "height",
}
PBC_DIRECTIONS = ("-z", "-x", "+z", "+x")
WATER_IDS = {1, 5, 12, 54}


def json_member(archive: zipfile.ZipFile, name: str):
    return json.loads(archive.read(name))


def local_table(source_root: Path, name: str):
    return json.loads((source_root / "output/tables_resolved" / f"{name}.json").read_text())


def first_label(value):
    if isinstance(value, dict) and "labels" in value:
        return value["labels"][0]
    return value


def source_field_name(field: str) -> str:
    name = field.split(".", 1)[0].split(" ", 1)[0]
    if name.startswith("0x"):
        return "h_" + name[2:]
    return name


def compare_tables(archive: zipfile.ZipFile, source_root: Path):
    result = {}
    for name in TABLES:
        raw = json_member(archive, f"data/bcsv/{name}.json")
        local = local_table(source_root, name)
        field_names = [source_field_name(field) for field in raw["fields"]]
        local_columns = {column["name"]: index for index, column in enumerate(local["columns"])}
        if set(field_names) != set(local_columns):
            raise AssertionError((name, set(field_names) ^ set(local_columns)))
        if len(raw["rows"]) != len(local["rows"]):
            raise AssertionError((name, len(raw["rows"]), len(local["rows"])))
        compared = mismatches = 0
        for row_index, (raw_row, local_row) in enumerate(zip(raw["rows"], local["rows"])):
            for field_index, field in enumerate(raw["fields"]):
                local_name = field_names[field_index]
                if isinstance(raw_row, dict):
                    raw_key = field.split(".", 1)[0].split(" ", 1)[0]
                    raw_value = raw_row[field] if field in raw_row else raw_row[raw_key]
                else:
                    raw_value = raw_row[field_index]
                resolved_value = first_label(local_row[local_columns[local_name]])
                compared += 1
                mismatches += raw_value != resolved_value
                if raw_value != resolved_value:
                    raise AssertionError((name, row_index, local_name, raw_value, resolved_value))
        result[name] = {
            "rows": len(raw["rows"]),
            "fields": len(raw["fields"]),
            "values_compared": compared,
            "mismatches": mismatches,
        }
    return result


def archive_preset_grid(archive: zipfile.ZipFile, preset: str):
    name = f"data/byml/Param/Field/MainFieldPreset/{preset}_LandMaking.byml.json"
    wrapper = json_member(archive, name)
    grid = next(value for outer in wrapper.values() for value in outer.values()
                if isinstance(value, dict) and value.get("_type") == "LandMakingGrid")
    if grid["width"] != 112 or grid["height"] != 96 or grid["stride_bytes"] != 14:
        raise AssertionError((preset, grid.get("width"), grid.get("height"), grid.get("stride_bytes")))
    return grid


def compare_preset_grids(archive: zipfile.ZipFile, source_root: Path):
    local_paths = sorted((source_root / "output/world").glob("FieldPreset*_LandMaking.json"))
    if len(local_paths) != 96:
        raise AssertionError(f"expected 96 local LandMaking grids, found {len(local_paths)}")
    cells_compared = mismatches = layer1_nonzero = 0
    used_ids = Counter()
    height_by_unit = defaultdict(Counter)
    by_preset = {}
    for path in local_paths:
        preset = path.stem.removesuffix("_LandMaking")
        local = json.loads(path.read_text())
        source = archive_preset_grid(archive, preset)
        if local["grid"] != [112, 96] or len(local["cells"]) != 112 * 96:
            raise AssertionError((preset, local["grid"], len(local["cells"])))
        raw_columns = {field: index for index, field in enumerate(source["fields"])}
        source_cells = source["cells"]
        if len(source_cells) != len(local["cells"]):
            raise AssertionError((preset, len(source_cells), len(local["cells"])))
        preset_mismatches = 0
        for raw_cell, local_cell in zip(source_cells, local["cells"]):
            for raw_name, local_name in GRID_FIELDS.items():
                cells_compared += 1
                if raw_cell[raw_columns[raw_name]] != local_cell[local["cell_fields"].index(local_name)]:
                    mismatches += 1
                    preset_mismatches += 1
            unit_id = local_cell[0]
            used_ids[unit_id] += 1
            height_by_unit[unit_id][local_cell[6]] += 1
            layer1_nonzero += local_cell[3] != 0
        by_preset[preset] = {"cells": len(source_cells), "mismatches": preset_mismatches}
    if mismatches:
        raise AssertionError(f"{mismatches} mismatched LandMaking values")
    return {
        "preset_count": len(local_paths),
        "grid_dimensions": [112, 96],
        "cells_compared": sum(row["cells"] for row in by_preset.values()),
        "field_values_compared": cells_compared,
        "mismatches": mismatches,
        "layer1_nonzero_cells": layer1_nonzero,
        "used_unit_cell_counts": {str(k): used_ids[k] for k in sorted(used_ids)},
        "elevation_byte_histogram_by_used_unit": {
            str(unit_id): {str(k): values[k] for k in sorted(values)}
            for unit_id, values in sorted(height_by_unit.items())
        },
        "per_preset": by_preset,
    }


def pbc_path_info(name: str, data: dict):
    source = data["source"]
    source_path = PurePosixPath(source)
    group = source_path.parent.name.removesuffix("_pbc")
    stem = source_path.stem
    model_name = stem[3:] if stem.startswith("col") else stem
    return group, model_name


def rotate_ccw(pbc: dict):
    """Rotate square PBC cells and the four directional values CCW once."""
    width, height = pbc["w"], pbc["h"]
    if width != height:
        raise AssertionError(("expected square PBC asset", width, height))
    old_attr, old_heights = pbc["attributes"], pbc["heights"]
    new_attr, new_heights = [None] * (width * height), [None] * (width * height)
    for new_z in range(height):
        for new_x in range(width):
            old_x, old_z = width - 1 - new_z, new_x
            old_index = old_z * width + old_x
            new_index = new_z * width + new_x
            # New [-z,-x,+z,+x] receives old [+x,-z,-x,+z].
            new_attr[new_index] = [old_attr[old_index][3], old_attr[old_index][0],
                                   old_attr[old_index][1], old_attr[old_index][2]]
            old_height = old_heights[old_index]
            new_heights[new_index] = [*old_height[9:12], *old_height[0:3],
                                      *old_height[3:6], *old_height[6:9]]
    return {**pbc, "w": width, "h": height, "attributes": new_attr, "heights": new_heights}


def rotate_n(pbc: dict, count: int):
    current = pbc
    for _ in range(count % 4):
        current = rotate_ccw(current)
    return current


def side_profile(pbc: dict, water_ids: set[int]):
    width, height, attrs = pbc["w"], pbc["h"], pbc["attributes"]
    heights = pbc["heights"]
    return {
        "left": ([attrs[z * width][1] in water_ids for z in range(height)],
                 [[heights[z * width][4], heights[z * width][5]] for z in range(height)]),
        "right": ([attrs[z * width + width - 1][3] in water_ids for z in range(height)],
                  [[heights[z * width + width - 1][10], heights[z * width + width - 1][11]] for z in range(height)]),
        "top": ([attrs[x][0] in water_ids for x in range(width)],
                [[heights[x][1], heights[x][2]] for x in range(width)]),
        "bottom": ([attrs[(height - 1) * width + x][2] in water_ids for x in range(width)],
                   [[heights[(height - 1) * width + x][7], heights[(height - 1) * width + x][8]] for x in range(width)]),
    }


def pbc_seam_stats(archive: zipfile.ZipFile, pbc_by_model: dict, unit_rows: dict,
                   used_ids: set[int], source_root: Path, water_ids: set[int]):
    variants = {}
    for unit_id in used_ids:
        model_name = unit_rows[unit_id]["ModelName"]
        base = pbc_by_model[model_name]
        variants[unit_id] = []
        for rotation in range(4):
            variants[unit_id].append(side_profile(rotate_n(base, rotation), water_ids))

    result = {}
    for mode in ("unrotated", "clockwise", "counterclockwise"):
        mismatch = overlap = comparisons = 0
        pair_mismatches = Counter()
        same_elevation_mismatch = same_elevation_comparisons = 0
        endpoint_mismatch = endpoint_comparisons = 0
        for path in sorted((source_root / "output/world").glob("FieldPreset*_LandMaking.json")):
            data = json.loads(path.read_text())
            cells = data["cells"]
            selected = []
            for cell in cells:
                rotation = cell[2]
                if mode == "clockwise":
                    rotation = (-rotation) % 4
                elif mode == "unrotated":
                    rotation = 0
                selected.append(variants[cell[0]][rotation])
            for index, cell in enumerate(cells):
                x, z = index % 112, index // 112
                current = selected[index]
                if x + 1 < 112:
                    neighbor_cell = cells[index + 1]
                    neighbor = selected[index + 1]
                    for left_water, right_water, left_height, right_height in zip(
                        current["right"][0], neighbor["left"][0],
                        current["right"][1], neighbor["left"][1],
                    ):
                        comparisons += 1
                        mismatch += left_water != right_water
                        overlap += left_water and right_water
                        key = (cell[0], neighbor_cell[0])
                        pair_mismatches[key] += left_water != right_water
                        for a, b in zip(left_height, reversed(right_height)):
                            endpoint_comparisons += 1
                            endpoint_mismatch += a != b
                            if cell[6] == neighbor_cell[6]:
                                same_elevation_comparisons += 1
                                same_elevation_mismatch += a != b
                if z + 1 < 96:
                    neighbor_cell = cells[index + 112]
                    neighbor = selected[index + 112]
                    for top_water, bottom_water, top_height, bottom_height in zip(
                        current["bottom"][0], neighbor["top"][0],
                        current["bottom"][1], neighbor["top"][1],
                    ):
                        comparisons += 1
                        mismatch += top_water != bottom_water
                        overlap += top_water and bottom_water
                        key = (cell[0], neighbor_cell[0])
                        pair_mismatches[key] += top_water != bottom_water
                        for a, b in zip(top_height, reversed(bottom_height)):
                            endpoint_comparisons += 1
                            endpoint_mismatch += a != b
                            if cell[6] == neighbor_cell[6]:
                                same_elevation_comparisons += 1
                                same_elevation_mismatch += a != b
        result[mode] = {
            "directional_triangle_comparisons": comparisons,
            "water_check_mismatches": mismatch,
            "water_check_mismatch_percent": round(100 * mismatch / comparisons, 6),
            "water_check_water_water_matches": overlap,
            "top_mismatching_unit_id_pairs": [
                {"source": a, "neighbor": b, "mismatches": count}
                for (a, b), count in pair_mismatches.most_common(12)
            ],
            "raw_height_endpoint_comparisons": endpoint_comparisons,
            "raw_height_endpoint_mismatches_zero_elevation_offset": endpoint_mismatch,
            "raw_height_endpoint_mismatch_percent": round(100 * endpoint_mismatch / endpoint_comparisons, 6),
            "same_elevation_byte_endpoint_comparisons": same_elevation_comparisons,
            "same_elevation_byte_endpoint_mismatches": same_elevation_mismatch,
            "same_elevation_byte_mismatch_percent": round(100 * same_elevation_mismatch / same_elevation_comparisons, 6),
        }
    return result


def river_outlet_alignment(source_root: Path, coast_assembly_path: Path):
    table = local_table(source_root, "FieldLandMakingUnitModelParam")
    indexes = {column["name"]: i for i, column in enumerate(table["columns"])}
    models = {}
    for row in table["rows"]:
        unit_id = row[indexes["UniqueID"]]
        matrix = []
        for z in range(4):
            line = []
            for x in range(4):
                value = row[indexes[f"InnerType0{z}{x}"]]
                line.append(first_label(value) == "River" or first_label(value) == 1)
            matrix.append(line)
        models[unit_id] = matrix

    def ccw(matrix):
        return [[matrix[x][3 - z] for x in range(4)] for z in range(4)]

    pattern_lookup = {}
    for unit_id, matrix in models.items():
        pattern_lookup[unit_id] = []
        current = matrix
        for rotation in range(4):
            if rotation:
                current = ccw(current)
            pattern_lookup[unit_id].append([
                sum((1 << x) for x in range(4) if current[z][x]) for z in range(4)
            ])

    pool_data = json.loads((source_root / "output/ui_island/preset_template_candidate_pools.json").read_text())
    categories = {row["field_data"]: row["enum_label"] for row in pool_data["preset_to_candidate_pools"]}
    assembly = json.loads(coast_assembly_path.read_text())
    slots_by_category = {}
    for category, details in assembly["river_coast_slot_summary"]["templates_by_template_kind"].items():
        slots_by_category[category] = [slot["grid_xy"] for pattern in details["river_slot_patterns"]
                                       for slot in pattern["slots"]]
    counts = Counter()
    failures = []
    gap_histogram = Counter()
    per_category = defaultdict(Counter)
    for path in sorted((source_root / "output/world").glob("FieldPreset*_LandMaking.json")):
        preset = path.stem.removesuffix("_LandMaking")
        category = categories[preset]
        data = json.loads(path.read_text())
        raster = [0] * (96 * 4)
        for index, cell in enumerate(data["cells"]):
            x, z = index % 112, index // 112
            for local_z, bits in enumerate(pattern_lookup[cell[0]][cell[2]]):
                raster[z * 4 + local_z] |= bits << (x * 4)
        nonempty_rows = [index for index, bits in enumerate(raster) if bits]
        south_row = nonempty_rows[-1]
        south_bits = raster[south_row]
        south_segments = sorted({(x // 64) + 1 for x in range(448) if south_bits & (1 << x)})
        all_bits = 0
        for bits in raster:
            all_bits |= bits
        min_x = (all_bits & -all_bits).bit_length() - 1
        max_x = max(bits.bit_length() - 1 for bits in raster if bits)
        west_segments = sorted({(z // 64) + 1 for z, bits in enumerate(raster) if bits & (1 << min_x)})
        east_segments = sorted({(z // 64) + 1 for z, bits in enumerate(raster) if bits & (1 << max_x)})
        north_row = nonempty_rows[0]
        north_segments = sorted({(x // 64) + 1 for x in range(448) if raster[north_row] & (1 << x)})
        actual = {"south": south_segments, "west": west_segments, "east": east_segments,
                  "north": north_segments}
        expected = {"south": []}
        for x, z in slots_by_category[category]:
            edge = "south" if z == 6 else "west" if x == 1 else "east" if x == 7 else "north"
            expected.setdefault(edge, []).append(x if edge == "south" else z)
        expected = {key: sorted(set(value)) for key, value in expected.items()}
        # The selected 3B templates have two River slots, both on south and/or a side.
        checks = {edge: actual[edge] == expected.get(edge, []) for edge in expected}
        passed = all(checks.values())
        counts["presets"] += 1
        counts["matched_presets"] += passed
        per_category[category]["presets"] += 1
        per_category[category]["matched_presets"] += passed
        per_category[category]["expected_outlet_checks"] += len(checks)
        per_category[category]["matched_outlet_checks"] += sum(checks.values())
        gap = 383 - south_row
        gap_histogram[gap] += 1
        if not passed:
            failures.append({"preset": preset, "category": category, "actual": actual, "expected": expected})
    return {
        "scope": "CCW candidate InnerType0 4x4 water mask; outlet identity is compared by 64-sample coastal segment, without asserting world-space transform or mesh continuity.",
        "grid_partition": {"landmaking_cells_per_coast_segment": 16, "mask_samples_per_segment": 64,
                           "coast_grid_spacing_native_units": 160, "source_tile_spacing_candidate": 10},
        "presets": counts["presets"],
        "presets_matching_all_expected_river_slot_segments": counts["matched_presets"],
        "failure_count": len(failures),
        "southmost_mask_gap_samples_histogram": {str(k): gap_histogram[k] for k in sorted(gap_histogram)},
        "per_template_category": {
            category: dict(per_category[category]) for category in sorted(per_category)
        },
        "failures": failures,
        "limitation": "This joins symbolic template slots and a best-continuity mask orientation. It cannot establish parent/world origin, coast-piece transform, selected model variant, terminal collision triangles, water surface, or actual gameplay flow.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest_zip", type=Path, help="extracted manifests ZIP; read-only")
    parser.add_argument("--research-root", type=Path, default=ROOT,
                        help="checkout containing output/tables_resolved and output/world")
    parser.add_argument("--output", type=Path, default=ROOT / "output/ui_island/manifests_pbc_audit.json")
    args = parser.parse_args()
    source_root = args.research_root.resolve()
    output = args.output if args.output.is_absolute() else ROOT / args.output
    archive_path = args.manifest_zip.resolve()
    digest = hashlib.sha256()
    with archive_path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)

    with zipfile.ZipFile(archive_path) as archive:
        bad_member = archive.testzip()
        if bad_member:
            raise AssertionError(f"ZIP CRC failed: {bad_member}")
        members = archive.namelist()
        pbc_members = [name for name in members if name.endswith(".pbc.json")]
        pbc_by_model = {}
        pbc_data_by_model = {}
        pbc_info = {}
        all_material_ids = set()
        for name in pbc_members:
            data = json_member(archive, name)
            group, model_name = pbc_path_info(name, data)
            if len(data["attributes"]) != data["w"] * data["h"] or len(data["heights"]) != data["w"] * data["h"]:
                raise AssertionError((name, data["w"], data["h"], len(data["attributes"]), len(data["heights"])))
            if data["triangle_sides"] != list(PBC_DIRECTIONS) or len(data["triangle_corners"]) != 4:
                raise AssertionError((name, data["triangle_sides"], data["triangle_corners"]))
            for cell in data["attributes"]:
                if len(cell) != 4:
                    raise AssertionError((name, cell))
                all_material_ids.update(cell)
            pbc_info[name] = {"group": group, "model_name": model_name, "data": data}
            pbc_data_by_model[model_name] = data
            if group.startswith("FldUnit") or model_name.startswith("FldOut"):
                pbc_by_model[model_name] = data

        table_comparison = compare_tables(archive, source_root)
        grid_comparison = compare_preset_grids(archive, source_root)
        used_ids = {int(key) for key in grid_comparison["used_unit_cell_counts"]}
        unit_table = local_table(source_root, "FieldLandMakingUnitModelParam")
        unit_columns = {column["name"]: index for index, column in enumerate(unit_table["columns"])}
        unit_rows = {row[unit_columns["UniqueID"]]: {
            "UniqueID": row[unit_columns["UniqueID"]],
            "ModelName": row[unit_columns["ModelName"]],
            "ModelType": first_label(row[unit_columns["ModelType"]]),
            "Variation": row[unit_columns["Variation"]],
        } for row in unit_table["rows"]}
        all_unit_names = {row["ModelName"] for row in unit_rows.values()}
        unit_pbc_names = {info["model_name"] for info in pbc_info.values()
                          if info["group"].startswith("FldUnit")}
        coast_table = local_table(source_root, "FieldOutsideParts")
        coast_columns = {column["name"]: index for index, column in enumerate(coast_table["columns"])}
        coast_names = {row[coast_columns["ModelName"]] for row in coast_table["rows"]}
        coast_pbc_names = {info["model_name"] for info in pbc_info.values()
                           if info["model_name"].startswith("FldOut")}

        ground = local_table(source_root, "ColGroundAttributeParam")
        ground_columns = {column["name"]: index for index, column in enumerate(ground["columns"])}
        water_rows = {index for index, row in enumerate(ground["rows"])
                      if row[ground_columns["WaterCheck"]]}
        ground_crosswalk = [
            {"pbc_row_index": index,
             "local_unique_id": row[ground_columns["UniqueID"]],
             "debug_name": row[ground_columns["DebugName"]],
             "water_check": bool(row[ground_columns["WaterCheck"]])}
            for index, row in enumerate(ground["rows"])
        ]
        if water_rows != WATER_IDS:
            raise AssertionError((water_rows, WATER_IDS))

        used_unit_details = []
        used_attribute_histogram = Counter()
        for unit_id in sorted(used_ids):
            model_name = unit_rows[unit_id]["ModelName"]
            data = pbc_by_model[model_name]
            heights = [value for cell in data["heights"] for value in cell]
            attr_hist = Counter(value for cell in data["attributes"] for value in cell)
            used_attribute_histogram.update(attr_hist)
            used_unit_details.append({
                **unit_rows[unit_id],
                "preset_cell_uses": grid_comparison["used_unit_cell_counts"][str(unit_id)],
                "pbc_model_match": model_name,
                "pbc_grid": [data["w"], data["h"]],
                "pbc_origin_cell": data["origin_cell"],
                "pbc_cell_size": data["cell_size"],
                "pbc_height_min_max": [min(heights), max(heights)],
                "pbc_material_rows_present": sorted(attr_hist),
                "pbc_watercheck_material_rows_present": sorted(water_rows & set(attr_hist)),
            })

        coast_materials = {}
        for model_name in sorted(coast_names & coast_pbc_names):
            data = pbc_by_model[model_name]
            attrs, width = data["attributes"], data["w"]
            by_row = {}
            for row_index in sorted(water_rows):
                positions = [(index % width, index // width)
                             for index, cell in enumerate(attrs) if row_index in cell]
                if positions:
                    by_row[str(row_index)] = {
                        "triangle_count": sum(cell.count(row_index) for cell in attrs),
                        "cell_bbox_xy": [min(x for x, _ in positions), min(y for _, y in positions),
                                         max(x for x, _ in positions), max(y for _, y in positions)],
                    }
            water_positions = [(index % width, index // width)
                               for index, cell in enumerate(attrs) if any(value in water_rows for value in cell)]
            coast_materials[model_name] = {
                "grid": [data["w"], data["h"]],
                "cell_size": data["cell_size"],
                "watercheck_cell_bbox_xy": [min(x for x, _ in water_positions), min(y for _, y in water_positions),
                                            max(x for x, _ in water_positions), max(y for _, y in water_positions)] if water_positions else None,
                "watercheck_by_material_row": by_row,
            }

        room_floors = local_table(source_root, "RoomFloorParam")
        room_floor_columns = {column["name"]: index for index, column in enumerate(room_floors["columns"])}
        room_floor_variants = ("6x6", "8x8", "10x6", "10x6_R")
        room_floor_rows = [row for row in room_floors["rows"] if row[room_floor_columns["HasJmp"]]]
        room_floor_assets = {}
        room_floor_missing_allowed = []
        for row in room_floor_rows:
            floor_id = row[room_floor_columns["UniqueID"]]
            resource_name = row[room_floor_columns["ResourceName"]]
            allowed_variants = room_floor_variants[:3] + ((room_floor_variants[3],)
                                                            if row[room_floor_columns["Rotatable"]] else ())
            variants_data = {}
            for variant in allowed_variants:
                model_name = f"{resource_name}_{variant}"
                data = pbc_data_by_model.get(model_name)
                if data is None:
                    room_floor_missing_allowed.append(model_name)
                    continue
                materials = Counter(value for cell in data["attributes"] for value in cell)
                water_positions = [(index % data["w"], index // data["w"])
                                   for index, cell in enumerate(data["attributes"])
                                   if any(value in water_rows for value in cell)]
                variants_data[variant] = {
                    "model_name": model_name,
                    "grid": [data["w"], data["h"]],
                    "origin_cell": data["origin_cell"],
                    "cell_size": data["cell_size"],
                    "height_min_max": [min(value for cell in data["heights"] for value in cell),
                                       max(value for cell in data["heights"] for value in cell)],
                    "material_rows_present": sorted(materials),
                    "watercheck_material_rows_present": sorted(water_rows & set(materials)),
                    "watercheck_cell_bbox_xy": [min(x for x, _ in water_positions),
                                                min(y for _, y in water_positions),
                                                max(x for x, _ in water_positions),
                                                max(y for _, y in water_positions)] if water_positions else None,
                }
            room_floor_assets[str(floor_id)] = {
                "unique_id": floor_id,
                "resource_name": resource_name,
                "rotatable": bool(row[room_floor_columns["Rotatable"]]),
                "floorboards_unique_id": row[room_floor_columns["Floorboards"]],
                "allowed_variants": list(allowed_variants),
                "pbc_variants": variants_data,
            }
        if room_floor_missing_allowed:
            raise AssertionError(("missing allowed RoomFloor PBCs", room_floor_missing_allowed))

        coast_assembly_path = ROOT / "output/ui_island/coast_part_assembly_native.json"
        outlet_alignment = river_outlet_alignment(source_root, coast_assembly_path)
        seam_stats = pbc_seam_stats(archive, pbc_by_model, unit_rows, used_ids,
                                    source_root, water_rows)

        unit_shapes = Counter(tuple((info["data"]["w"], info["data"]["h"], info["data"]["cell_size"]))
                              for info in pbc_info.values() if info["group"].startswith("FldUnit"))
        coast_shapes = Counter(tuple((info["data"]["w"], info["data"]["h"], info["data"]["cell_size"]))
                               for info in pbc_info.values() if info["model_name"].startswith("FldOut"))
        manifest_meta = json_member(archive, "manifests/extract.json")
        collision_meta = json_member(archive, "manifests/collision.json")
        result = {
            "scope": "Read-only comparison of an extracted manifest ZIP to the local ACNH build corpus; raw archive members are not copied to this report.",
            "archive": {
                "filename": archive_path.name,
                "size_bytes": archive_path.stat().st_size,
                "sha256": digest.hexdigest(),
                "zip_members": len(members),
                "uncompressed_bytes": sum(item.file_size for item in archive.infolist()),
                "zip_crc_bad_member": None,
                "extract_manifest_output_count": manifest_meta.get("output_count"),
                "collision_manifest_output_count": collision_meta.get("output_count"),
                "collision_manifest_pbc_count": collision_meta.get("extra", {}).get("pbc"),
                "collision_pbc_failed": collision_meta.get("extra", {}).get("pbc_failed"),
            },
            "exact_corpus_matches": {
                "tables": table_comparison,
                "landmaking_grids": grid_comparison,
            },
            "pbc_inventory": {
                "pbc_json_members": len(pbc_members),
                "field_unit_pbc_members": len(unit_pbc_names),
                "field_outside_pbc_members": len(coast_pbc_names),
                "unit_model_table_rows": unit_table["row_count"],
                "unique_unit_model_names": len(all_unit_names),
                "unit_model_names_with_pbc_count": len(all_unit_names & unit_pbc_names),
                "unit_model_names_missing_pbc": sorted(all_unit_names - unit_pbc_names),
                "unit_pbc_names_not_in_model_table": sorted(unit_pbc_names - all_unit_names),
                "used_unit_names_missing_pbc": sorted({unit_rows[i]["ModelName"] for i in used_ids} - unit_pbc_names),
                "used_unique_ids_have_pbc_count": len(used_ids & set(unit_rows)),
                "coast_parts_in_local_table": len(coast_names),
                "coast_parts_with_pbc": len(coast_names & coast_pbc_names),
                "coast_model_names_missing_pbc": sorted(coast_names - coast_pbc_names),
                "coast_pbc_names_not_in_model_table": sorted(coast_pbc_names - coast_names),
                "unit_shape_counts": [
                    {"width": key[0], "height": key[1], "cell_size": key[2], "count": value}
                    for key, value in sorted(unit_shapes.items())
                ],
                "coast_shape_counts": [
                    {"width": key[0], "height": key[1], "cell_size": key[2], "count": value}
                    for key, value in sorted(coast_shapes.items())
                ],
                "all_material_row_indices": sorted(all_material_ids),
                "ground_material_crosswalk": ground_crosswalk,
                "watercheck_material_rows": [ground_crosswalk[index] for index in sorted(water_rows)],
                "used_unit_material_triangle_counts_by_row_index": {
                    str(key): used_attribute_histogram[key] for key in sorted(used_attribute_histogram)
                },
                "used_unit_models": used_unit_details,
                "river_coast_water_material_layout": coast_materials,
                "resident_roomfloor_pbc": {
                    "roomfloor_table_rows": room_floors["row_count"],
                    "has_jmp_floors": len(room_floor_rows),
                    "allowed_variant_files": sum(len(row["allowed_variants"]) for row in room_floor_assets.values()),
                    "allowed_variant_files_found": sum(len(row["pbc_variants"]) for row in room_floor_assets.values()),
                    "allowed_variant_files_missing": room_floor_missing_allowed,
                    "floors": room_floor_assets,
                },
                "pbc_water_seam_comparisons": seam_stats,
            },
            "river_outlet_slot_alignment": outlet_alignment,
            "interpretation_limits": [
                "PBC JSON payloads prove parsed static data exists in this archive; they do not prove the game loaded or rendered every asset at runtime.",
                "The CCW rotation candidate is supported by continuity ranking and exact outlet-segment correspondence, but its renderer transform is not directly observed.",
                "LandMaking/PBC and coast/PBC dimensions fit the native 10-unit terrain tile and 160-unit coast spacing. A shared world origin, parent transform, vertical offset, or seam weld is still unproven.",
                "Height values in PBC are local payload values. The LandMaking elevation byte-to-world-height conversion and dynamic-ground override remain unresolved.",
                "PBC water-check attributes map to static ground permissions, not visible water flow, waves, waterfall effects, actor navigation, or gameplay physics by themselves.",
                "Only the used terrain units and the catalogued 136 coast pieces are fully matched. One unused unit name and one extra road PBC remain unmatched to the 246-row model table.",
            ],
        }

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({
        "output": str(output),
        "archive_sha256": result["archive"]["sha256"],
        "pbc_json_members": len(pbc_members),
        "used_unit_pbc_coverage": result["pbc_inventory"]["used_unique_ids_have_pbc_count"],
        "coast_pbc_coverage": result["pbc_inventory"]["coast_parts_with_pbc"],
        "outlet_presets_matched": outlet_alignment["presets_matching_all_expected_river_slot_segments"],
        "ccw_water_seam_mismatch_percent": seam_stats["counterclockwise"]["water_check_mismatch_percent"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
