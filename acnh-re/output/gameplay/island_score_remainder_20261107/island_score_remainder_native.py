#!/usr/bin/env python3
"""Bounded native checks for island-score classification and synthetic score slices.

Runs the original ExeFS main functions through tools/nso_sandbox.py. The item/
field accessors are controlled fixtures; the classifier, block counter, duplicate
penalty, weight functions, and save-copy function execute from the NSO.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import struct
import sys


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
TOOL_DIR = REPO / "tools"
sys.path.insert(0, str(TOOL_DIR))
for candidate in (
    Path(os.environ.get("ACNH_RE_DEPS", "/nonexistent")),
    Path("/workspace/acnh-re/.deps"),
    REPO / ".deps",
):
    if candidate.is_dir():
        sys.path.insert(0, str(candidate))

from nso_sandbox import NSO_SHA256, Sandbox  # noqa: E402


CLASSIFIER = 0x15C4590
COUNT_LAYER0 = 0x15C4240
COUNT_LAYER1 = 0x15C48B0
DUPLICATE_PENALTY = 0x15C4DB0
SAVE_COPY = 0x15C68C0
BLOCK_SIZE = 0x228
BLOCK_COUNT = 18 * 16
DISTINCT_SENTINEL = 0xFFFE

WEIGHTS = {
    "life_c0": 0x15C6910,
    "natural_c0": 0x15C6920,
    "life_c1": 0x15C6930,
    "natural_c1": 0x15C6940,
    "life_c2": 0x15C6950,
    "natural_c2": 0x15C6960,
    "life_c3": 0x15C6970,
    "life_c4": 0x15C6980,
    "natural_c5": 0x15C6990,
    "natural_c7": 0x15C69A0,
}


def f32(value: float) -> float:
    return struct.unpack("<f", struct.pack("<f", value))[0]


def s0_float(sb: Sandbox) -> float:
    bits = sb.reg("s0") & 0xFFFFFFFF
    return struct.unpack("<f", struct.pack("<I", bits))[0]


def set_s0_float(sb: Sandbox, value: float) -> None:
    bits = struct.unpack("<I", struct.pack("<f", value))[0]
    sb.reg("s0", bits)


class NativeFixture:
    """Sandbox with item-table and field-table accessors replaced by fixture values."""

    def __init__(self) -> None:
        self.sb = Sandbox()
        self.state: dict[str, int] = {}
        self.item = self.sb.alloc(0x20)
        self.class_out = self.sb.alloc(1)
        self.bonus_out = self.sb.alloc(4)
        self._install_stubs()

    def _install_stubs(self) -> None:
        accessors = {
            0xF58D00: "has_item_param",
            0xAA7F80: "shown_as_furniture",
            0xAA8690: "has_diy_recipe",
            0xAA8780: "passes_non_diy_check",
            0xAAB060: "item_size",
            0xAAAA80: "price_times_stack",
            0xAA9590: "priority_place_is_outdoor",
            0xAA8310: "furniture_collision",
            0xF59370: "has_unit_icon",
            0xA9F670: "item_kind",
            0xF58F20: "has_fg_main_param",
            0x4D5430: "is_tree_nature",
            0x4D56E0: "tree_nature_subtype",
            0x4D5B30: "is_flower_nature",
            0x4D66D0: "is_fence_kind",
            0x4D6620: "is_weed_nature",
            0x4D66C0: "has_category10_nature_bit",
            0x4D4BD0: "fg_kind",
            0xAA4650: "item_variant",
        }
        for va, key in accessors.items():
            self.sb.stub(va, lambda sb, key=key: self.state.get(key, 0))

        # The native accessors below only supply fixture identifiers or build a
        # temporary ItemParam/FgMainParam view. Their classification consumers run.
        self.sb.stub(0xA9C290, lambda _sb: 0)
        self.sb.stub(0x4D4A90, lambda _sb: 0)
        self.sb.stub(0xF58A90, self._item_id)

    def _item_id(self, sb: Sandbox) -> int:
        return struct.unpack("<H", sb.read(sb.reg("x0"), 2))[0]

    def write_item(self, item_id: int) -> None:
        self.sb.uc.mem_write(self.item, struct.pack("<H", item_id) + bytes(0x1E))

    def classifier(self, item_id: int, state: dict[str, int], layer0: bool = True) -> dict[str, float | int]:
        self.state = state
        self.write_item(item_id)
        self.sb.uc.mem_write(self.class_out, b"\xff")
        self.sb.uc.mem_write(self.bonus_out, bytes(4))
        mask = self.sb.call(
            CLASSIFIER,
            (self.class_out, self.bonus_out, self.item, 1, int(layer0)),
        )
        return {
            "mask": int(mask),
            "class": self.sb.read(self.class_out, 1)[0],
            "price_bonus": struct.unpack("<f", self.sb.read(self.bonus_out, 4))[0],
        }

    def new_block(self) -> int:
        block = self.sb.alloc(BLOCK_SIZE)
        raw = bytearray(BLOCK_SIZE)
        for entry in range(128):
            struct.pack_into("<H", raw, 0x20 + 4 * entry, DISTINCT_SENTINEL)
        self.sb.uc.mem_write(block, bytes(raw))
        return block

    def count_item(
        self,
        block: int,
        item_id: int,
        state: dict[str, int],
        *,
        layer0: bool = True,
        amount: int = 1,
    ) -> None:
        self.state = state
        self.write_item(item_id)
        entry = COUNT_LAYER0 if layer0 else COUNT_LAYER1
        self.sb.call(entry, (block, self.item, 1, amount))

    def counts(self, block: int) -> list[int]:
        return list(struct.unpack("<11H", self.sb.read(block, 22)))

    def block_bonus(self, block: int) -> float:
        return struct.unpack("<f", self.sb.read(block + 0x1C, 4))[0]

    def penalty(self, block: int, category: int) -> float:
        self.sb.call(DUPLICATE_PENALTY, (block, category))
        return s0_float(self.sb)

    def weight(self, va: int, value: float) -> float:
        set_s0_float(self.sb, value)
        self.sb.call(va, ())
        return s0_float(self.sb)


def base_furniture(**updates: int) -> dict[str, int]:
    state = {
        "has_item_param": 1,
        "shown_as_furniture": 1,
        "has_diy_recipe": 1,
        "passes_non_diy_check": 0,
        "item_size": 1,
        "price_times_stack": 0,
        "priority_place_is_outdoor": 0,
        "furniture_collision": 0,
        "has_unit_icon": 0,
        "item_kind": 1,
        "has_fg_main_param": 0,
        "is_tree_nature": 0,
        "tree_nature_subtype": 0,
        "is_flower_nature": 0,
        "is_fence_kind": 0,
        "is_weed_nature": 0,
        "has_category10_nature_bit": 0,
        "fg_kind": 4,
        "item_variant": 0,
    }
    state.update(updates)
    return state


def base_field(**updates: int) -> dict[str, int]:
    state = base_furniture(
        has_item_param=0,
        has_fg_main_param=1,
        is_tree_nature=0,
        tree_nature_subtype=0,
        is_flower_nature=0,
        is_fence_kind=0,
        is_weed_nature=0,
        has_category10_nature_bit=0,
        fg_kind=4,
    )
    state.update(updates)
    return state


def expected_mask_counters(mask: int) -> list[int]:
    return [int(bool(mask & (1 << category))) for category in range(11)]


def run_classifier_fixtures(fx: NativeFixture) -> dict[str, object]:
    fixtures: list[tuple[str, int, dict[str, int], int, int, float, bool]] = [
        ("category_0_small_diy", 3000, base_furniture(price_times_stack=2000), 0x001, 0, 1.0, True),
        ("category_1_small_non_diy", 3001, base_furniture(has_diy_recipe=0, passes_non_diy_check=1, price_times_stack=1999, priority_place_is_outdoor=1), 0x002, 1, 0.5, True),
        ("category_2_wide_diy", 3002, base_furniture(item_size=3, price_times_stack=20000), 0x004, 0xFF, 2.0, True),
        ("category_3_wide_non_diy", 3003, base_furniture(has_diy_recipe=0, passes_non_diy_check=1, item_size=5, price_times_stack=1500, priority_place_is_outdoor=1), 0x008, 0xFF, 0.5, True),
        ("category_4_fence", 3004, base_field(is_fence_kind=1), 0x010, 0xFF, 0.0, True),
        ("category_5_tree", 3005, base_field(is_tree_nature=1), 0x020, 0xFF, 0.0, True),
        ("category_6_palm_subset", 3006, base_field(is_tree_nature=1, tree_nature_subtype=1), 0x060, 0xFF, 0.0, True),
        ("category_7_flower", 3007, base_field(is_flower_nature=1), 0x080, 0xFF, 0.0, True),
        ("category_8_weed", 3008, base_field(is_weed_nature=1), 0x100, 0xFF, 0.0, True),
        ("category_9_unit_icon", 3009, base_furniture(shown_as_furniture=0, has_unit_icon=1), 0x200, 0xFF, 0.0, True),
        ("category_10_furniture_collision", 3010, base_furniture(price_times_stack=1999, furniture_collision=1), 0x401, 0, 0.0, True),
        ("category_10_field_nature", 3011, base_field(has_category10_nature_bit=1, fg_kind=4), 0x400, 0xFF, 0.0, True),
        ("category_10_hole_excluded", 3012, base_field(has_category10_nature_bit=1, fg_kind=0x1D), 0x000, 0xFF, 0.0, True),
        ("category_10_stone_excluded", 3013, base_field(has_category10_nature_bit=1, fg_kind=0x1B), 0x000, 0xFF, 0.0, True),
    ]
    outputs: list[dict[str, object]] = []
    all_pass = True
    for index, (name, item_id, state, expected_mask, expected_class, expected_bonus, layer0) in enumerate(fixtures):
        actual = fx.classifier(item_id, state, layer0)
        block = fx.new_block()
        fx.count_item(block, item_id, state, layer0=layer0)
        actual_counts = fx.counts(block)
        wanted_counts = expected_mask_counters(expected_mask)
        counts_pass = actual_counts == wanted_counts
        result_pass = (
            actual["mask"] == expected_mask
            and actual["class"] == expected_class
            and abs(float(actual["price_bonus"]) - expected_bonus) < 1e-5
            and counts_pass
            and abs(fx.block_bonus(block) - expected_bonus) < 1e-5
        )
        all_pass &= result_pass
        outputs.append({
            "case": name,
            "item_id": item_id,
            "layer": 0 if layer0 else 1,
            "fixture_accessors": state,
            "expected": {"mask": expected_mask, "class": expected_class, "price_bonus": expected_bonus, "counters": wanted_counts},
            "native": {**actual, "counters": actual_counts, "block_bonus": fx.block_bonus(block)},
            "pass": result_pass,
        })

    # The unit-icon exclusions are an important negative branch in the real classifier.
    excluded = [(0x9C4, 1), (0x9C6, 1), (3100, 0x2F), (3101, 0x3F), (3102, 0x42)]
    exclusion_results = []
    for item_id, item_kind in excluded:
        state = base_furniture(shown_as_furniture=0, has_unit_icon=1, item_kind=item_kind)
        actual = fx.classifier(item_id, state)
        passed = actual["mask"] == 0
        all_pass &= passed
        exclusion_results.append({"item_id": item_id, "item_kind": item_kind, "native_mask": actual["mask"], "pass": passed})

    price_cases = [
        ("price_1999_indoor", 1999, 0, 0.0),
        ("price_1999_outdoor", 1999, 1, 0.5),
        ("price_2000_indoor", 2000, 0, 1.0),
        ("price_19999_outdoor", 19999, 1, 1.5),
        ("price_20000_outdoor", 20000, 1, 2.5),
    ]
    price_results = []
    for name, price, outdoor, wanted in price_cases:
        actual = fx.classifier(3200 + len(price_results), base_furniture(price_times_stack=price, priority_place_is_outdoor=outdoor))
        passed = actual["mask"] == 1 and abs(float(actual["price_bonus"]) - wanted) < 1e-5
        all_pass &= passed
        price_results.append({"case": name, "price_times_stack": price, "outdoor": bool(outdoor), "expected_bonus": wanted,
                              "native_bonus": actual["price_bonus"], "pass": passed})

    # 0x15c4240 enables the category-10 bit, while 0x15c48b0 omits it for layer 1.
    layer_state = base_furniture(furniture_collision=1)
    layer_results = {}
    for layer0, name in ((True, "layer0"), (False, "layer1")):
        actual = fx.classifier(3300, layer_state, layer0)
        block = fx.new_block()
        fx.count_item(block, 3300, layer_state, layer0=layer0)
        want = 0x401 if layer0 else 0x001
        passed = actual["mask"] == want and fx.counts(block) == expected_mask_counters(want)
        all_pass &= passed
        layer_results[name] = {"native_mask": actual["mask"], "native_counters": fx.counts(block), "expected_mask": want, "pass": passed}

    return {
        "category_classifier_and_cell_counter": outputs,
        "unit_icon_exclusions": exclusion_results,
        "price_boundaries": price_results,
        "layer0_category10_gate": layer_results,
        "pass": all_pass,
    }


def make_island(fx: NativeFixture) -> tuple[int, list[int]]:
    data = fx.sb.alloc(BLOCK_COUNT * BLOCK_SIZE)
    raw = bytearray(BLOCK_COUNT * BLOCK_SIZE)
    for block_index in range(BLOCK_COUNT):
        for entry in range(128):
            struct.pack_into("<H", raw, block_index * BLOCK_SIZE + 0x20 + entry * 4, DISTINCT_SENTINEL)
    fx.sb.uc.mem_write(data, bytes(raw))
    return data, [data + index * BLOCK_SIZE for index in range(BLOCK_COUNT)]


def native_formula_score(fx: NativeFixture, blocks: list[int], active: set[int]) -> dict[str, object]:
    total_counts = [0] * 11
    adjusted = {0: 0.0, 1: 0.0}
    penalties: list[dict[str, float | int]] = []
    total_bonus = 0.0
    for index in sorted(active):
        block = blocks[index]
        counters = fx.counts(block)
        total_counts = [left + right for left, right in zip(total_counts, counters)]
        block_penalties = {}
        for category in (0, 1):
            penalty = fx.penalty(block, category)
            adjusted[category] += counters[category] - penalty
            block_penalties[str(category)] = penalty
        penalties.append({"block_index": index, "counts": counters, "penalties": block_penalties})
        total_bonus = f32(total_bonus + fx.block_bonus(block))

    natural_terms = {
        "category_0": fx.weight(WEIGHTS["natural_c0"], adjusted[0]),
        "category_2": fx.weight(WEIGHTS["natural_c2"], total_counts[2]),
        "category_5_capped": fx.weight(WEIGHTS["natural_c5"], total_counts[5]),
        "category_7": fx.weight(WEIGHTS["natural_c7"], total_counts[7]),
    }
    life_terms = {
        "category_0": fx.weight(WEIGHTS["life_c0"], adjusted[0]),
        "category_1": fx.weight(WEIGHTS["life_c1"], adjusted[1]),
        "category_2": fx.weight(WEIGHTS["life_c2"], total_counts[2]),
        "category_3": fx.weight(WEIGHTS["life_c3"], total_counts[3]),
        "category_4": fx.weight(WEIGHTS["life_c4"], total_counts[4]),
        "furniture_price_bonus": total_bonus,
    }
    natural = f32(0.0)
    for value in natural_terms.values():
        natural = f32(natural + value)
    life = f32(0.0)
    for value in life_terms.values():
        life = f32(life + value)

    documented_natural = 0.25 * adjusted[0] + total_counts[2] + min(total_counts[5], 190) + total_counts[7]
    documented_life = (adjusted[0] + adjusted[1] + 4 * total_counts[2] + 4 * total_counts[3]
                       + 0.2 * total_counts[4] + total_bonus)
    passed = abs(natural - documented_natural) < 1e-4 and abs(life - documented_life) < 1e-4
    return {
        "counts": total_counts,
        "category_0_1_adjusted_after_native_block_penalty": {"0": adjusted[0], "1": adjusted[1]},
        "native_block_penalties": penalties,
        "native_price_bonus_sum": total_bonus,
        "native_weight_terms": {"natural": natural_terms, "life": life_terms},
        "native_weight_score": {"natural": natural, "life": life},
        "documented_formula_score": {"natural": documented_natural, "life": documented_life},
        "assumed_zero_inputs": ["bridge/slope counts", "shop/museum/tailor facility flags", "terrain counters"],
        "pass": passed,
    }


def save_copy(fx: NativeFixture, grid_data: int, natural: float, life: float,
              category9: int, category5: int) -> dict[str, object]:
    grid = fx.sb.alloc(0x18)
    descriptor = bytearray(0x18)
    struct.pack_into("<I", descriptor, 8, 18)
    struct.pack_into("<I", descriptor, 12, 16)
    struct.pack_into("<Q", descriptor, 16, grid_data)
    fx.sb.uc.mem_write(grid, bytes(descriptor))

    accumulator = fx.sb.alloc(0x50)
    fx.sb.uc.mem_write(accumulator, struct.pack("<Q", grid) + bytes(0x48))
    fx.sb.uc.mem_write(accumulator + 0x18, struct.pack("<f", natural))
    fx.sb.uc.mem_write(accumulator + 0x1C, struct.pack("<f", life))
    fx.sb.uc.mem_write(accumulator + 0x20, struct.pack("<i", category9))
    fx.sb.uc.mem_write(accumulator + 0x38, struct.pack("<i", category5))
    save_member = fx.sb.alloc(0x250)
    fx.sb.uc.mem_write(save_member, bytes(0x250))
    fx.sb.call(SAVE_COPY, (accumulator, save_member))
    copied = fx.sb.read(save_member, 0x250)
    grid_values = list(struct.unpack_from("<288H", copied, 0))
    copied_scores = {
        "natural": struct.unpack_from("<f", copied, 0x240)[0],
        "life": struct.unpack_from("<f", copied, 0x244)[0],
        "category9_count": struct.unpack_from("<i", copied, 0x248)[0],
        "category5_count": struct.unpack_from("<i", copied, 0x24C)[0],
    }
    return {"save_copy_function": hex(SAVE_COPY), "copied_scores": copied_scores, "copied_clutter_grid": grid_values}


def finish_island(fx: NativeFixture, name: str, data: int, blocks: list[int], active: set[int]) -> dict[str, object]:
    score = native_formula_score(fx, blocks, active)
    counts = score["counts"]
    copied = save_copy(fx, data, float(score["native_weight_score"]["natural"]),
                       float(score["native_weight_score"]["life"]), int(counts[9]), int(counts[5]))
    expected_grid = []
    for row in range(18):
        for col in range(16):
            source_index = col * 18 + row
            expected_grid.append(fx.sb.u32(blocks[source_index] + 0x14) & 0xFFFF)
    grid_pass = copied["copied_clutter_grid"] == expected_grid
    copied_score_pass = (
        abs(copied["copied_scores"]["natural"] - score["native_weight_score"]["natural"]) < 1e-5
        and abs(copied["copied_scores"]["life"] - score["native_weight_score"]["life"]) < 1e-5
        and copied["copied_scores"]["category9_count"] == counts[9]
        and copied["copied_scores"]["category5_count"] == counts[5]
    )
    copied["grid_mapping"] = "save[row, col] = source block[col * 18 + row].category10"
    copied["grid_mapping_pass"] = grid_pass
    copied["score_fields_pass"] = copied_score_pass
    copied["nonzero_saved_grid_cells"] = [
        {"row": i // 16, "column": i % 16, "half_units": value}
        for i, value in enumerate(copied["copied_clutter_grid"]) if value
    ]
    return {"island": name, "active_blocks": sorted(active), "score": score, "native_save_copy": copied,
            "pass": bool(score["pass"] and grid_pass and copied_score_pass)}


def run_synthetic_islands(fx: NativeFixture) -> dict[str, object]:
    outputs: list[dict[str, object]] = []

    # One classified representative of each category, with category 10 supplied
    # by two tree cells, one palm cell, and one collidable furniture cell.
    data, blocks = make_island(fx)
    balanced_specs = [
        (0, 3000, base_furniture(price_times_stack=2000)),
        (1, 3001, base_furniture(has_diy_recipe=0, passes_non_diy_check=1, price_times_stack=1999, priority_place_is_outdoor=1)),
        (2, 3002, base_furniture(item_size=3, price_times_stack=20000)),
        (3, 3003, base_furniture(has_diy_recipe=0, passes_non_diy_check=1, item_size=5, price_times_stack=1500, priority_place_is_outdoor=1)),
        (4, 3004, base_field(is_fence_kind=1)),
        (5, 3005, base_field(is_tree_nature=1, has_category10_nature_bit=1)),
        (6, 3006, base_field(is_tree_nature=1, tree_nature_subtype=1, has_category10_nature_bit=1)),
        (7, 3007, base_field(is_flower_nature=1)),
        (8, 3008, base_field(is_weed_nature=1)),
        (9, 3009, base_furniture(shown_as_furniture=0, has_unit_icon=1)),
        (10, 3010, base_furniture(price_times_stack=1999, furniture_collision=1)),
    ]
    for block_index, item_id, state in balanced_specs:
        fx.count_item(blocks[block_index], item_id, state)
    outputs.append(finish_island(fx, "balanced_categories", data, blocks, set(range(11))))
    outputs[-1]["fixture_items"] = [
        {"block_index": block_index, "item_id": item_id, "fixture_accessors": state}
        for block_index, item_id, state in balanced_specs
    ]

    # Duplicate penalty boundary and within-block distinct (item, variant) behavior.
    data, blocks = make_island(fx)
    block = blocks[0]
    for _ in range(6):
        fx.count_item(block, 3300, base_furniture(price_times_stack=0))
    for _ in range(11):
        fx.count_item(block, 3301, base_furniture(has_diy_recipe=0, passes_non_diy_check=1, price_times_stack=0))
    outputs.append(finish_island(fx, "duplicate_penalty_thresholds", data, blocks, {0}))
    outputs[-1]["fixture_items"] = [
        {"block_index": 0, "item_id": 3300, "category": 0, "variant": 0, "repetitions": 6},
        {"block_index": 0, "item_id": 3301, "category": 1, "variant": 0, "repetitions": 11},
    ]

    data, blocks = make_island(fx)
    for block_index in (0, 1):
        for _ in range(4):
            fx.count_item(blocks[block_index], 3400, base_furniture(price_times_stack=0))
    outputs.append(finish_island(fx, "duplicate_penalty_is_per_block", data, blocks, {0, 1}))
    outputs[-1]["fixture_items"] = [
        {"block_index": block_index, "item_id": 3400, "category": 0, "variant": 0, "repetitions": 4}
        for block_index in (0, 1)
    ]

    # The Natural category-5 leaf is capped at 190; use one native cell call per tree.
    data, blocks = make_island(fx)
    tree = base_field(is_tree_nature=1)
    for serial in range(191):
        fx.count_item(blocks[0], 3500 + serial, tree)
    outputs.append(finish_island(fx, "natural_tree_cap_190", data, blocks, {0}))
    outputs[-1]["fixture_items"] = [{"block_index": 0, "category": 5, "native_cell_calls": 191, "has_category10_bit": False}]

    return {"synthetic_islands": outputs, "pass": all(bool(case["pass"]) for case in outputs)}


def run_duplicate_behavior(fx: NativeFixture) -> dict[str, object]:
    cases: list[dict[str, object]] = []
    all_pass = True
    for category in (0, 1):
        for repetitions in (5, 6, 10, 11):
            block = fx.new_block()
            state = (base_furniture(price_times_stack=0) if category == 0 else
                     base_furniture(has_diy_recipe=0, passes_non_diy_check=1, price_times_stack=0))
            item_id = 3700 + category * 100 + repetitions
            for _ in range(repetitions):
                fx.count_item(block, item_id, state)
            counts = fx.counts(block)
            distinct = fx.sb.u32(block + 0x220)
            duplicates = counts[category] - distinct
            expected_penalty = (0.0 if duplicates < 5 else
                                duplicates * (0.5 if duplicates <= 9 else 0.75))
            native_penalty = fx.penalty(block, category)
            passed = (counts[category] == repetitions and distinct == 1
                      and abs(native_penalty - expected_penalty) < 1e-5)
            all_pass &= passed
            cases.append({
                "category": category,
                "repetitions": repetitions,
                "distinct_item_variant_pairs": distinct,
                "duplicates": duplicates,
                "expected_native_penalty": expected_penalty,
                "native_penalty": native_penalty,
                "pass": passed,
            })

    # Different variants of one item ID occupy distinct dedupe pairs.
    block = fx.new_block()
    for serial in range(10):
        fx.count_item(block, 3899, base_furniture(price_times_stack=0, item_variant=serial & 1))
    raw = fx.counts(block)[0]
    distinct = fx.sb.u32(block + 0x220)
    native_penalty = fx.penalty(block, 0)
    duplicates = raw - distinct
    expected_penalty = duplicates * 0.5 if 5 <= duplicates <= 9 else duplicates * 0.75 if duplicates >= 10 else 0.0
    variant_case = {
        "category": 0,
        "item_id": 3899,
        "repetitions": 10,
        "variants": [0, 1],
        "distinct_item_variant_pairs": distinct,
        "duplicates": duplicates,
        "expected_native_penalty": expected_penalty,
        "native_penalty": native_penalty,
        "pass": raw == 10 and distinct == 2 and abs(native_penalty - expected_penalty) < 1e-5,
    }
    all_pass &= bool(variant_case["pass"])
    return {"threshold_matrix": cases, "variant_pair_case": variant_case, "pass": all_pass}


def run_clutter_grid(fx: NativeFixture) -> dict[str, object]:
    data, blocks = make_island(fx)
    items = []
    for block_index, count in enumerate((179, 180, 181)):
        for serial in range(count):
            item_id = 3600 + block_index * 200 + serial
            fx.count_item(blocks[block_index], item_id, base_field(has_category10_nature_bit=1, fg_kind=4))
        items.append({"block_index": block_index, "category10_half_units": count, "native_cell_calls": count})

    copied = save_copy(fx, data, 0.0, 0.0, 0, 0)
    values = copied["copied_clutter_grid"]
    # Source blocks 0, 1, 2 map to save coordinates [0,0], [1,0], [2,0].
    observed = [values[0], values[16], values[32]]
    expected = [179, 180, 181]
    threshold_count = sum(value >= 180 for value in observed)
    passed = observed == expected and threshold_count == 2
    return {
        "fixture_blocks": items,
        "save_grid_samples": {"source_indices": [0, 1, 2], "save_offsets_u16": [0, 16, 32], "native": observed},
        "documented_very_messy_threshold": 180,
        "blocks_at_or_above_threshold": threshold_count,
        "eventflow_query_executed": False,
        "pass": passed,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output", type=Path, default=HERE / "island_score_remainder_native.json")
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)

    fx = NativeFixture()
    classifier = run_classifier_fixtures(fx)
    duplicates = run_duplicate_behavior(fx)
    islands = run_synthetic_islands(fx)
    clutter = run_clutter_grid(fx)
    result = {
        "meta": {
            "source": f"ExeFS main sha256 {NSO_SHA256}",
            "harness": "output/gameplay/island_score_remainder_20261107/island_score_remainder_native.py (tools/nso_sandbox.py; Unicorn)",
            "native_functions_executed": [
                hex(CLASSIFIER), hex(COUNT_LAYER0), hex(COUNT_LAYER1), hex(DUPLICATE_PENALTY),
                *[hex(va) for va in WEIGHTS.values()], hex(SAVE_COPY),
            ],
            "accessors_stubbed": {
                "item_param_and_item_fields": ["0xf58d00", "0xaa7f80", "0xaa8690", "0xaa8780", "0xaab060", "0xaaaa80", "0xaa9590", "0xaa8310", "0xa9f670", "0xaa4650"],
                "field_item_fields": ["0xf58f20", "0x4d5430", "0x4d56e0", "0x4d5b30", "0x4d66d0", "0x4d6620", "0x4d66c0", "0x4d4bd0"],
                "temporary_view_constructors": ["0xa9c290", "0x4d4a90"],
                "item_unique_id": "0xf58a90 reads the u16 ID from the synthetic item fixture",
                "controlled_fixture_boundary": "all ItemParam/FgMainParam/table results are supplied per item; the classifier and block counter are native",
            },
            "full_score_aggregator_executed": False,
            "full_score_aggregator_note": "0x15c61f0 and its VillageScoreMgr container/structure/facility inputs are not reconstructed by this isolated fixture.",
        },
        "classifier_fixtures": classifier,
        "duplicate_pair_verification": duplicates,
        "synthetic_scores": islands,
        "clutter_grid_save_copy": clutter,
    }
    result["all_pass"] = bool(classifier["pass"] and duplicates["pass"] and islands["pass"] and clutter["pass"])
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"output": str(args.output), "all_pass": result["all_pass"],
                      "classifier_pass": classifier["pass"], "synthetic_score_pass": islands["pass"],
                      "clutter_grid_pass": clutter["pass"]}, indent=2))
    return 0 if result["all_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
