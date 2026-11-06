#!/usr/bin/env python3
"""Run native UI point/bounds and recursive hit-priority logic with controlled fixtures."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import struct

from nso_sandbox import Sandbox

ROOT = Path(__file__).resolve().parent.parent
NSO = ROOT / "inputs/additional_exefs/main"
OUT = ROOT / "output/ui_hud/runtime_followup/native_geometry_priority.json"
GEOMETRY = 0x14B7820
TREE_HIT = 0x14B8850
PANE_VISIBILITY = 0x14C80D0
BOUND_SETUP = 0x14B87B0


def write_u16(sandbox: Sandbox, addr: int, value: int) -> None:
    sandbox.uc.mem_write(addr, struct.pack("<H", value))


def write_u64(sandbox: Sandbox, addr: int, value: int) -> None:
    sandbox.uc.mem_write(addr, struct.pack("<Q", value))


def write_f32(sandbox: Sandbox, addr: int, value: float) -> None:
    sandbox.uc.mem_write(addr, struct.pack("<f", value))


def set_node_geometry(sandbox: Sandbox, node: int, pane: int, rect_a: tuple[float, ...],
                      rect_b: tuple[float, ...], secondary_enabled: bool) -> None:
    sandbox.uc.mem_write(node, bytes(0x80))
    write_u16(sandbox, node + 0x50, 1)
    write_u64(sandbox, node + 0x20, pane)
    write_u64(sandbox, node + 0x28, pane if secondary_enabled else 0)
    for offset, value in zip((0x30, 0x34, 0x38, 0x3C), rect_a):
        write_f32(sandbox, node + offset, value)
    for offset, value in zip((0x40, 0x44, 0x48, 0x4C), rect_b):
        write_f32(sandbox, node + offset, value)


def point_test(sandbox: Sandbox, node: int, point: int, xy: tuple[float, float]) -> int:
    sandbox.uc.mem_write(point, struct.pack("<ff", *xy))
    return sandbox.call(GEOMETRY, (node, point, 0)) & 1


def set_pane_flags(sandbox: Sandbox, pane: int, visible: bool, active: bool = True,
                   parent: int = 0, requires_parent_active: bool = False,
                   parent_active: bool = True) -> None:
    sandbox.uc.mem_write(pane, bytes(0x100))
    flags = int(visible) | (int(requires_parent_active) << 1)
    sandbox.uc.mem_write(pane + 0x58, bytes([flags]))
    sandbox.uc.mem_write(pane + 0x59, bytes([int(parent_active)]))
    sandbox.uc.mem_write(pane + 0x5A, bytes([int(active)]))
    write_u64(sandbox, pane + 0x18, parent)


def visibility_case(sandbox: Sandbox, visible: bool, mode: int, *, active: bool = True,
                    parent_visible: bool | None = None, parent_requires_active: bool = False,
                    parent_active: bool = True) -> int:
    pane = sandbox.alloc(0x100)
    parent = sandbox.alloc(0x100) if parent_visible is not None else 0
    set_pane_flags(sandbox, pane, visible, active, parent,
                   requires_parent_active=parent_requires_active, parent_active=parent_active)
    if parent:
        set_pane_flags(sandbox, parent, bool(parent_visible), active=True,
                       requires_parent_active=parent_requires_active, parent_active=parent_active)
    ref = sandbox.alloc(8)
    write_u64(sandbox, ref, pane)
    return sandbox.call(PANE_VISIBILITY, (ref, mode)) & 1


def make_tree(sandbox: Sandbox) -> tuple[int, int, int, int]:
    root, first, second, leaf = (sandbox.alloc(0x80) for _ in range(4))
    for node in (root, first, second, leaf):
        sandbox.uc.mem_write(node, bytes(0x80))
    for node in (root, first, second, leaf):
        write_u16(sandbox, node + 0x50, 1)
    write_u64(sandbox, root + 0x8, first)
    write_u64(sandbox, first + 0x18, second)
    write_u64(sandbox, second + 0x8, leaf)
    return root, first, second, leaf


def tree_case(sandbox: Sandbox, nodes: tuple[int, ...], hits: set[int], flags: dict[int, int] | None = None):
    root = nodes[0]
    for node in nodes:
        write_u16(sandbox, node + 0x50, (flags or {}).get(node, 1))
    visits: list[int] = []

    def controlled_geometry(s: Sandbox) -> int:
        node = s.reg("x0")
        visits.append(node)
        return int(node in hits)

    sandbox.stub(GEOMETRY, controlled_geometry)
    selected = sandbox.call(TREE_HIT, (root, 0, 0))
    return selected, visits


def run() -> None:
    sandbox = Sandbox(NSO)
    pane = sandbox.alloc(0x100)
    node = sandbox.alloc(0x80)
    point = sandbox.alloc(8)
    set_pane_flags(sandbox, pane, True)

    visibility_cases = []
    visibility_checks = [
        ("visible_pane_mode_0", True, 0, {}, 1),
        ("hidden_pane_mode_0", False, 0, {}, 0),
        ("mode_1_rejects_inactive_target_pane", True, 1, {"active": False}, 0),
        ("mode_0_rejects_hidden_ancestor", True, 0, {"parent_visible": False}, 0),
        ("mode_1_rejects_ancestor_missing_active_flag", True, 1,
         {"parent_visible": True, "parent_requires_active": True, "parent_active": False}, 0),
        ("mode_1_accepts_visible_active_ancestor", True, 1,
         {"parent_visible": True, "parent_requires_active": True, "parent_active": True}, 1),
    ]
    for name, visible, mode, kwargs, expected in visibility_checks:
        actual = visibility_case(sandbox, visible, mode, **kwargs)
        if actual != expected:
            raise AssertionError({"case": name, "actual": actual, "expected": expected})
        visibility_cases.append({"case": name, "mode": mode, "expected": expected, "actual": actual,
                                 "inputs": {"visible": visible, **kwargs}})

    rect_a = (0.0, 0.0, 100.0, 100.0)
    rect_b = (50.0, 50.0, 150.0, 150.0)
    geometry_cases = []
    checks = [
        ("inside_intersection", rect_a, rect_b, True, (75.0, 75.0), 1),
        ("inside_first_only_is_rejected", rect_a, rect_b, True, (25.0, 25.0), 0),
        ("intersection_edge_is_inclusive", rect_a, rect_b, True, (50.0, 50.0), 1),
        ("disjoint_rectangles_reject_all_points", rect_a, (120.0, 120.0, 160.0, 160.0), True, (130.0, 130.0), 0),
        ("null_secondary_pointer_uses_first_rect", rect_a, rect_b, False, (25.0, 25.0), 1),
        ("reversed_endpoints_are_normalized", (100.0, 100.0, 0.0, 0.0), (150.0, 150.0, 50.0, 50.0), True, (75.0, 75.0), 1),
    ]
    for name, a, b, enabled, xy, expected in checks:
        set_node_geometry(sandbox, node, pane, a, b, enabled)
        actual = point_test(sandbox, node, point, xy)
        if actual != expected:
            raise AssertionError({"case": name, "actual": actual, "expected": expected})
        geometry_cases.append({"case": name, "rect_a": a, "rect_b": b, "secondary_pointer_nonnull": enabled,
                               "point": xy, "expected": expected, "actual": actual})

    # F_14b87b0 inherits the parent's secondary-bound pointer for nodes whose
    # flag 0x40 is set. Stub its setup helpers; the copy/check stays native.
    parent = sandbox.alloc(0x80)
    child = sandbox.alloc(0x80)
    inherited = sandbox.alloc(0x100)
    previous = sandbox.alloc(0x100)
    sandbox.stub(0x14D9AA0, lambda s: 0)
    sandbox.stub(0x14D9990, lambda s: 0)
    bound_cases = []
    for name, flags, expected_pointer in (
        ("flag_0x40_inherits_parent_secondary_bound", 0x40, inherited),
        ("without_flag_0x40_preserves_existing_secondary_bound", 0, previous),
    ):
        sandbox.uc.mem_write(parent, bytes(0x80))
        sandbox.uc.mem_write(child, bytes(0x80))
        write_u16(sandbox, child + 0x50, flags)
        write_u64(sandbox, parent + 0x28, inherited)
        write_u64(sandbox, child + 0x28, previous)
        sandbox.call(BOUND_SETUP, (child, parent))
        actual_pointer = sandbox.u64(child + 0x28)
        if actual_pointer != expected_pointer:
            raise AssertionError({"case": name, "actual": hex(actual_pointer),
                                 "expected": hex(expected_pointer)})
        bound_cases.append({"case": name, "child_flags": hex(flags),
                            "parent_bound": hex(inherited), "before": hex(previous),
                            "after": hex(actual_pointer), "expected_after": hex(expected_pointer)})

    # The tree walker itself executes natively. Only the per-node geometry
    # predicate is replaced so candidate priority can be isolated.
    nodes = make_tree(sandbox)
    root, first, second, leaf = nodes
    traversal_cases = []
    for name, hits, expected, flags in (
        ("all_hits_depth_first_last_candidate_wins", set(nodes), leaf, None),
        ("later_sibling_overwrites_earlier_sibling", {root, first, second}, second, None),
        ("ancestor_survives_when_children_miss", {root}, root, None),
        ("special_0x200_node_returns_before_children", {root, first}, root, {root: 0x200}),
    ):
        selected, visits = tree_case(sandbox, nodes, hits, flags)
        expected_visits = [root] if name == "special_0x200_node_returns_before_children" else list(nodes)
        if selected != expected or visits != expected_visits:
            raise AssertionError({"case": name, "selected": hex(selected), "expected": hex(expected),
                                 "visits": [hex(x) for x in visits],
                                 "expected_visits": [hex(x) for x in expected_visits]})
        traversal_cases.append({"case": name, "hit_nodes": [hex(x) for x in sorted(hits)],
                                "visit_order": [hex(x) for x in visits], "selected": hex(selected),
                                "expected_selected": hex(expected), "geometry_predicate": "stubbed"})

    if sandbox.unknown_imports:
        raise AssertionError({"unexpected_imports": sandbox.unknown_imports})
    result = {
        "schema": "acnh.ui_hud_runtime_followup.native_hit_geometry_priority.v1",
        "source": {"game_build": "ACNH 1.0.0", "module": "ExeFS main",
                   "main_sha256": hashlib.sha256(NSO.read_bytes()).hexdigest(),
                   "evidence_kind": "Original AArch64 geometry and tree-walker instructions under controlled in-memory fixtures; no game capture."},
        "addresses": {"point_bounds": hex(GEOMETRY), "recursive_tree_hit": hex(TREE_HIT),
                      "pane_visibility_chain": hex(PANE_VISIBILITY), "bound_setup": hex(BOUND_SETUP)},
        "visibility_contract": "0x14c80d0 requires visibility bit 0 on the pane and every ancestor. Mode 1 additionally requires the target pane's +0x5a byte and, for ancestors whose +0x58 bit 1 is set, their +0x59 byte.",
        "visibility_cases": visibility_cases,
        "geometry_contract": "The original point test checks the target pane/ancestor visibility chain, normalizes each rectangle's endpoints, and performs an inclusive point-in-rectangle test. When node+0x28 is non-null it intersects the +0x30..+0x3c and +0x40..+0x4c rectangles; when null, it tests only the first rectangle. The setup path copies the parent's +0x28 pointer into a child when child flag 0x40 is set. The second rectangle therefore carries a parent-propagated bound context; the code does not label that context as a render clip.",
        "geometry_cases": geometry_cases,
        "secondary_bound_inheritance_cases": bound_cases,
        "tree_contract": "For ordinary nodes (flags bit 0 set, bit 1 clear), the native recursive walker tests the node before visiting the first child at +0x8 and following siblings at +0x18. A hit replaces the incoming candidate; later depth-first hits replace earlier candidates. A node with bit 0 clear and bit 0x200 set uses a separate geometry mode and returns immediately when it hits.",
        "traversal_cases": traversal_cases,
        "comparisons": len(visibility_cases) + len(geometry_cases) + len(bound_cases) + len(traversal_cases), "mismatches": 0,
        "dependencies_stubbed": ["0x14b7820 point predicate returns fixture values in recursive-walker tests",
                                 "0x14d9aa0 and 0x14d9990 node setup helpers are stubbed in bound inheritance tests"],
        "button_pane_lookup": {"constructor_helper": "0x14885b0", "consumer": "0x14888b0", "consumer_caller": "0x148b2b0", "finding": "The helper searches for Cursor/P_BtnFocusKey/C_Cursor and an unnamed pane; if the latter is absent it falls back to B_Hit at control+0x70. If control+0x68 is still null, it copies +0x70 there. 0x14888b0 reads +0x70 then +0x68 and calls 0x14c80d0, which checks pane/ancestor visibility flags. This connects B_Hit to a control-side pane-visibility gate, but not to the hit-node rectangle source.",
                             "evidence_kind": "Static decompiler output; no pane instance pointer identity was recovered."},
        "parent_bound_static_evidence": {"bounds_update": "0x14b84f0 recursively calls 0x14b8540 for Pane pointers at node+0x20 and node+0x28, writing transformed rectangles at +0x30 and +0x40.",
                                         "inheritance": "0x14b87b0 inserts a child node in the parent/sibling list via 0x14d9990 and copies parent+0x28 into child+0x28 when child flag 0x40 is set.",
                                         "limit": "This proves propagation of the secondary bound pointer, not that it is the B_Hit pane or a GPU clip rectangle."},
        "limits": ["The +0x28 field is a parent-propagated bound pointer under child flag 0x40; whether its semantic role is clipping or another interaction constraint remains unresolved.",
                   "The recursive ordering is proven for controlled flags and tree links; real layout z-order meaning is not established.",
                   "The control-side B_Hit pointer reaches a pane-visibility gate, but no recovered def-use connects it to the hit-node pane pointer at +0x20 or the parent-propagated bound at +0x28.",
                   "No BND1-to-hit-node runtime instance trace or synchronized game capture was available."]
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({key: value for key, value in result.items() if key not in ("visibility_cases", "geometry_cases", "secondary_bound_inheritance_cases", "traversal_cases")}, indent=2))


if __name__ == "__main__":
    run()
