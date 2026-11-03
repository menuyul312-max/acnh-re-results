#!/usr/bin/env python3
"""Join 4x4 InnerType masks from terrain-unit rows to all island presets."""
from collections import Counter
import json
import os
from pathlib import Path
import statistics

ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = Path(os.environ.get("ACNH_RESEARCH_ROOT", ROOT))


def matrix_from_row(row, index, prefix):
    values = []
    for y in range(4):
        line = []
        for x in range(4):
            value = row[index[f"InnerType{prefix}{y}{x}"]]
            if isinstance(value, dict):
                value = value["labels"][0]
            line.append(value)
        values.append(line)
    return values


def rotate(matrix, clockwise):
    if clockwise:
        return [[matrix[3 - x][y] for x in range(4)] for y in range(4)]
    return [[matrix[x][3 - y] for x in range(4)] for y in range(4)]


def make_pattern(matrix):
    water = [[value == "River" or value == 1 for value in row] for row in matrix]
    row_bits = tuple(sum((1 << x) for x in range(4) if water[y][x]) for y in range(4))
    return {
        "row_bits": row_bits,
        "left": sum(int(water[y][0]) << y for y in range(4)),
        "right": sum(int(water[y][3]) << y for y in range(4)),
        "top": row_bits[0],
        "bottom": row_bits[3],
        "water_samples": sum(bit.bit_count() for bit in row_bits),
    }


def make_patterns(matrix, mode):
    rotations = []
    current = matrix
    for rotation in range(4):
        if rotation:
            if mode == "clockwise":
                current = rotate(current, True)
            else:
                current = rotate(current, False)
        rotations.append(make_pattern(current))
    return rotations


def count_components(rows):
    parent = []

    def find(value):
        root = value
        while parent[root] != root:
            root = parent[root]
        while parent[value] != value:
            value, parent[value] = parent[value], root
        return root

    def union(left, right):
        left = find(left)
        right = find(right)
        if left != right:
            parent[right] = left

    previous = []
    for bits in rows:
        current = []
        remaining = bits
        while remaining:
            start = (remaining & -remaining).bit_length() - 1
            shifted = remaining >> start
            run_length = (shifted ^ (shifted + 1)).bit_length() - 1
            end = start + run_length
            run_mask = ((1 << run_length) - 1) << start
            remaining &= ~run_mask
            label = len(parent)
            parent.append(label)
            current.append((start, end, label))

        previous_index = 0
        for start, end, label in current:
            while previous_index < len(previous) and previous[previous_index][1] <= start:
                previous_index += 1
            scan = previous_index
            while scan < len(previous) and previous[scan][0] < end:
                prior_start, prior_end, prior_label = previous[scan]
                if prior_start < end and start < prior_end:
                    union(label, prior_label)
                scan += 1
        previous = current

    return len({find(label) for label in range(len(parent))})


def analyze_preset(cells, models, patterns):
    width, height = 112, 96
    board_rows = [0] * (height * 4)
    typed_counts = Counter()
    rotation_counts = Counter()
    water_samples = 0
    seam_mismatch = 0
    seam_water_overlap = 0
    seam_comparisons = 0
    seam_type_pairs = Counter()
    seam_type_pair_comparisons = Counter()
    seam_unit_pairs = Counter()
    seam_unit_pair_comparisons = Counter()

    selected = []
    for index, cell in enumerate(cells):
        unit_id, _variation, rotation = cell[:3]
        if unit_id not in models:
            raise AssertionError(f"preset references missing unit ID {unit_id}")
        if not 0 <= rotation <= 3:
            raise AssertionError(f"unit rotation outside 0..3: {rotation}")
        model = models[unit_id]
        typed_counts[model["model_type"]] += 1
        rotation_counts[rotation] += 1
        pattern = patterns[unit_id][rotation]
        water_samples += pattern["water_samples"]
        x, z = index % width, index // width
        selected.append((pattern, model["model_type"], unit_id))
        for y, bits in enumerate(pattern["row_bits"]):
            board_rows[z * 4 + y] |= bits << (x * 4)

    for z in range(height):
        for x in range(width):
            pattern = selected[z * width + x]
            if x + 1 < width:
                neighbor = selected[z * width + x + 1]
                mismatch = (pattern[0]["right"] ^ neighbor[0]["left"]).bit_count()
                seam_mismatch += mismatch
                seam_water_overlap += (pattern[0]["right"] & neighbor[0]["left"]).bit_count()
                seam_comparisons += 4
                key = ("east_west", pattern[1], neighbor[1])
                seam_type_pairs[key] += mismatch
                seam_type_pair_comparisons[key] += 4
                id_key = ("east_west", pattern[2], neighbor[2])
                seam_unit_pairs[id_key] += mismatch
                seam_unit_pair_comparisons[id_key] += 4
            if z + 1 < height:
                neighbor = selected[(z + 1) * width + x]
                mismatch = (pattern[0]["bottom"] ^ neighbor[0]["top"]).bit_count()
                seam_mismatch += mismatch
                seam_water_overlap += (pattern[0]["bottom"] & neighbor[0]["top"]).bit_count()
                seam_comparisons += 4
                key = ("south_north", pattern[1], neighbor[1])
                seam_type_pairs[key] += mismatch
                seam_type_pair_comparisons[key] += 4
                id_key = ("south_north", pattern[2], neighbor[2])
                seam_unit_pairs[id_key] += mismatch
                seam_unit_pair_comparisons[id_key] += 4

    touches_boundary = bool(
        board_rows[0]
        or board_rows[-1]
        or any(row & 1 for row in board_rows)
        or any(row & (1 << (width * 4 - 1)) for row in board_rows)
    )
    occupied_rows = [y for y, bits in enumerate(board_rows) if bits]
    occupied_bits = [bits for bits in board_rows if bits]
    boundary_gaps = None
    if occupied_rows:
        min_x = min((bits & -bits).bit_length() - 1 for bits in occupied_bits)
        max_x = max(bits.bit_length() - 1 for bits in occupied_bits)
        min_y, max_y = occupied_rows[0], occupied_rows[-1]
        boundary_gaps = {
            "north_samples": min_y,
            "south_samples": len(board_rows) - 1 - max_y,
            "west_samples": min_x,
            "east_samples": width * 4 - 1 - max_x,
        }
    return {
        "source_river_unit_cells": typed_counts["River"],
        "source_fall_unit_cells": typed_counts["Fall"],
        "rotation_histogram": {str(k): rotation_counts[k] for k in range(4)},
        "inner_river_samples": water_samples,
        "shared_edge_sample_comparisons": seam_comparisons,
        "shared_edge_mismatches": seam_mismatch,
        "shared_edge_water_water_matches": seam_water_overlap,
        "shared_edge_mismatch_by_type_pair": [
            {
                "edge_orientation": key[0],
                "source_model_type": key[1],
                "neighbor_model_type": key[2],
                "mismatches": count,
                "comparisons": seam_type_pair_comparisons[key],
            }
            for key, count in sorted(seam_type_pairs.items())
        ],
        "shared_edge_mismatch_by_unit_pair": [
            {
                "edge_orientation": key[0],
                "source_unit_id": key[1],
                "neighbor_unit_id": key[2],
                "mismatches": count,
                "comparisons": seam_unit_pair_comparisons[key],
            }
            for key, count in sorted(seam_unit_pairs.items())
        ],
        "connected_components_4way": count_components(board_rows),
        "inner_river_samples_touch_outer_grid": touches_boundary,
        "nearest_inner_river_sample_to_outer_grid": boundary_gaps,
    }


def summarize(rows):
    components = [row["connected_components_4way"] for row in rows]
    mismatch = sum(row["shared_edge_mismatches"] for row in rows)
    comparisons = sum(row["shared_edge_sample_comparisons"] for row in rows)
    gap_names = ("north_samples", "south_samples", "west_samples", "east_samples")
    type_pair_mismatches = Counter()
    type_pair_comparisons = Counter()
    unit_pair_mismatches = Counter()
    unit_pair_comparisons = Counter()
    for row in rows:
        for edge in row["shared_edge_mismatch_by_type_pair"]:
            key = (edge["edge_orientation"], edge["source_model_type"], edge["neighbor_model_type"])
            type_pair_mismatches[key] += edge["mismatches"]
            type_pair_comparisons[key] += edge["comparisons"]
        for edge in row["shared_edge_mismatch_by_unit_pair"]:
            key = (edge["edge_orientation"], edge["source_unit_id"], edge["neighbor_unit_id"])
            unit_pair_mismatches[key] += edge["mismatches"]
            unit_pair_comparisons[key] += edge["comparisons"]
    gap_ranges = {}
    for key in gap_names:
        values = [row["nearest_inner_river_sample_to_outer_grid"][key] for row in rows]
        gap_ranges[key] = [min(values), statistics.median(values), max(values)]
    return {
        "preset_count": len(rows),
        "total_inner_river_samples": sum(row["inner_river_samples"] for row in rows),
        "shared_edge_sample_comparisons": comparisons,
        "shared_edge_mismatches": mismatch,
        "shared_edge_mismatch_percent": round(100 * mismatch / comparisons, 6),
        "shared_edge_water_water_matches": sum(row["shared_edge_water_water_matches"] for row in rows),
        "shared_edge_mismatch_by_type_pair": [
            {
                "edge_orientation": key[0],
                "source_model_type": key[1],
                "neighbor_model_type": key[2],
                "mismatches": count,
                "comparisons": type_pair_comparisons[key],
                "mismatch_percent": round(100 * count / type_pair_comparisons[key], 6),
            }
            for key, count in sorted(type_pair_mismatches.items())
        ],
        "highest_mismatch_unit_pairs": [
            {
                "edge_orientation": key[0],
                "source_unit_id": key[1],
                "neighbor_unit_id": key[2],
                "mismatches": count,
                "comparisons": unit_pair_comparisons[key],
                "mismatch_percent": round(100 * count / unit_pair_comparisons[key], 6),
            }
            for key, count in sorted(unit_pair_mismatches.items(), key=lambda item: (-item[1], item[0]))[:32]
        ],
        "connected_components_total": sum(components),
        "connected_components_min_median_max": [min(components), statistics.median(components), max(components)],
        "component_count_histogram": dict(sorted(Counter(components).items())),
        "presets_touching_outer_grid": sum(row["inner_river_samples_touch_outer_grid"] for row in rows),
        "nearest_sample_boundary_gap_min_median_max": gap_ranges,
    }


def main():
    table_path = SOURCE_ROOT / "output/tables_resolved/FieldLandMakingUnitModelParam.json"
    table = json.loads(table_path.read_text())
    columns = table["columns"]
    index = {column["name"]: i for i, column in enumerate(columns)}
    rows_by_id = {}
    for row in table["rows"]:
        unit_id = row[index["UniqueID"]]
        if unit_id in rows_by_id:
            raise AssertionError(f"duplicate UniqueID {unit_id}")
        inner0 = matrix_from_row(row, index, "0")
        inner1 = matrix_from_row(row, index, "1")
        model_type = row[index["ModelType"]]["labels"][0]
        river_mask_count = sum(value == "River" or value == 1 for line in inner0 for value in line)
        rows_by_id[unit_id] = {
            "unit_id": unit_id,
            "model_name": row[index["ModelName"]],
            "model_type": model_type,
            "variation_limit": row[index["Variation"]],
            "inner_type_000": inner0[0][0],
            "inner_type_prefix0_raw": inner0,
            "inner_type_prefix1_raw": inner1,
            "river_mask_samples": river_mask_count,
        }

    preset_files = sorted((SOURCE_ROOT / "output/world").glob("FieldPreset*_LandMaking.json"))
    if len(preset_files) != 96:
        raise AssertionError(f"expected 96 presets, found {len(preset_files)}")
    preset_inputs = []
    used_ids = set()
    for path in preset_files:
        data = json.loads(path.read_text())
        if data["grid"] != [112, 96] or len(data["cells"]) != 112 * 96:
            raise AssertionError(f"invalid source grid {path.name}")
        if data["raw"]["size"] != 112 * 96 * 14:
            raise AssertionError(f"invalid source record size {path.name}")
        used_ids.update(cell[0] for cell in data["cells"])
        preset_inputs.append((path.name, data))
    missing = sorted(used_ids - rows_by_id.keys())
    if missing:
        raise AssertionError(f"missing unit model rows: {missing}")

    used_models = {unit_id: rows_by_id[unit_id] for unit_id in sorted(used_ids)}
    invalid_water_rows = [
        model["model_name"]
        for model in used_models.values()
        if model["river_mask_samples"] and model["model_type"] not in ("River", "Fall")
    ]
    if invalid_water_rows:
        raise AssertionError(f"water-coded mask on unexpected model types: {invalid_water_rows}")

    mode_results = {}
    for mode in ("unrotated", "clockwise", "counterclockwise"):
        pattern_lookup = {}
        for unit_id, model in used_models.items():
            patterns = []
            matrix = model["inner_type_prefix0_raw"]
            if mode == "unrotated":
                patterns = [make_pattern(matrix)] * 4
            else:
                current = matrix
                clockwise = mode == "clockwise"
                for rotation in range(4):
                    if rotation:
                        current = rotate(current, clockwise)
                    patterns.append(make_pattern(current))
            pattern_lookup[unit_id] = patterns
        per_preset = []
        for filename, data in preset_inputs:
            result = analyze_preset(data["cells"], used_models, pattern_lookup)
            result["file"] = filename
            result["source_sha256"] = data["raw"]["sha256"]
            per_preset.append(result)
        summary = summarize(per_preset)
        # Pair-level counters are useful in the cross-preset summary; retaining
        # them on every preset would multiply the JSON size without adding
        # distinct interpretation.
        for row in per_preset:
            row.pop("shared_edge_mismatch_by_type_pair")
            row.pop("shared_edge_mismatch_by_unit_pair")
        mode_results[mode] = {"summary": summary, "per_preset": per_preset}

    catalog = []
    for unit_id, model in used_models.items():
        if model["model_type"] in ("River", "Fall"):
            catalog.append(model)
    result = {
        "scope": "Data-level reconstruction of the 4x4 InnerType prefix-0 masks joined to every LandMaking preset. Rotation handedness is ranked by cross-cell mask continuity; this does not execute mesh/PBC loading or prove world-space dimensions.",
        "source_elf_sha256": "5bf707c3dc5dac0ad9635af7d336ec580f81c3f7876d0f55400d1900e3415d74",
        "source_table": {
            "file": str(table_path.relative_to(SOURCE_ROOT / "output")),
            "row_count": table["row_count"],
            "raw_sha256": table["raw"]["sha256"],
            "used_unique_ids": len(used_ids),
            "used_unique_ids_by_model_type": dict(sorted(Counter(model["model_type"] for model in used_models.values()).items())),
            "used_river_and_fall_models": catalog,
        },
        "inner_type_layout": {
            "sample_grid": [4, 4],
            "field_name_interpretation": "InnerType0 followed by two index digits; matrix uses the middle digit as row and last digit as column.",
            "water_code_rule": "River enum label at InnerType000 or byte value 1 in other prefix-0 cells; used rows with such values are exclusively ModelType River/Fall.",
            "prefix1_used_byte_values": sorted({v for m in used_models.values() for row in m["inner_type_prefix1_raw"] for v in row}),
            "limits": [
                "The 4x4 sample coordinates are not proven to be four world-space collision cells.",
                "The source-table variation limit is catalogued but does not reveal PBC geometry for each selected variation.",
                "The direction of native rotation is not read directly; candidate handedness is inferred from mask continuity across the 96 presets.",
            ],
        },
        "rotation_consistency": {
            "test": "For adjacent 112x96 preset cells, compare their opposing edges across four prefix-0 InnerType samples, then count 4-way connected components on the assembled 448x384 sample raster.",
            "native_rotation_field_transfer": "0x558f40 copies each source rotation byte into the destination cell; see island_terrain_loader_native.json.",
            "candidate_results": mode_results,
            "best_continuity_candidate": "counterclockwise",
            "inference_limit": "A lower mismatch/component score is consistency evidence, not a native proof of rotation handedness or rendered water connectivity. Remaining edge mismatches may involve Falls, height transitions, or other terrain rules.",
        },
    }
    out = ROOT / "output/ui_island/river_inner_grid_topology.json"
    out.write_text(json.dumps(result, indent=2) + "\n")
    ccw = mode_results["counterclockwise"]["summary"]
    print(json.dumps({
        "output": str(out.relative_to(ROOT)),
        "presets": len(preset_inputs),
        "used_ids": len(used_ids),
        "river_fall_model_rows": len(catalog),
        "ccw_mismatches": ccw["shared_edge_mismatches"],
        "ccw_mismatch_percent": ccw["shared_edge_mismatch_percent"],
        "ccw_unit_pair_leader": ccw["highest_mismatch_unit_pairs"][0],
    }, indent=2))


if __name__ == "__main__":
    main()
