#!/usr/bin/env python3
"""Focused native probe for the tool-break ItemParam lookup and action catalog."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sqlite3
import struct
from pathlib import Path

from nso_sandbox import NSO_SHA256, Sandbox


ROOT = Path(__file__).resolve().parent.parent
FAMILIES = ("Axe", "Shovel", "Net", "FishingRod", "Slingshot", "Watering")
STATE_NAMES = {
    "Axe": ["AxeReady", "AxeReadyWait", "AxeHitTree"],
    "Shovel": ["ScoopReady", "ScoopReadyWait", "ScoopDig", "ScoopDigGetPutaway",
               "ScoopDigGetDemo", "ScoopBury"],
    "Net": ["NetWait", "NetSwing", "NetGetDemo", "NetRelease"],
    "FishingRod": ["RodCasting", "RodCastingFail", "RodWaitHit", "RodFall", "RodHit",
                   "RodReturnFloat", "RodFight", "RodCatch", "RodGetDemo",
                   "RodReleaseFish", "RodReleaseTrash"],
    "Slingshot": ["SlingshotWait", "SlingshotShooting", "SlingshotDropWait",
                  "SlingshotShocked"],
    "Watering": ["Watering"],
}
ACTION_ANCHORS = {
    "Axe": [0xE36EC0],
    "Shovel": [0xE52390, 0xE52850, 0xE541A0],
    "Net": [0xE43F30, 0xE45B80],
    "FishingRod": [0xE4BB10, 0xE4D420, 0xE4DD40, 0xE4E730],
    "Slingshot": [0xE564B0],
    "Watering": [0xE585C0],
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def source_record(db: sqlite3.Connection, source: str) -> dict:
    row = db.execute("SELECT id, sha256, size, format FROM files WHERE source=?", (source,)).fetchone()
    if row is None:
        raise KeyError(f"source absent from index.sqlite: {source}")
    return {"source_id": row[0], "sha256": row[1], "size": row[2], "format": row[3]}


def refs_for(db: sqlite3.Connection, function_va: int) -> list[dict]:
    return [
        {"va": hex(va), "text": text}
        for va, text in db.execute(
            "SELECT string_va, text FROM string_refs WHERE function_va=? ORDER BY string_va",
            (function_va,),
        )
    ]


def direct_calls_to(db: sqlite3.Connection, owner_va: int, target_va: int) -> list[dict]:
    return [
        {"pc": hex(pc), "target": hex(target), "instruction": op}
        for pc, target, op in db.execute(
            "SELECT pc, target_va, instruction FROM direct_calls "
            "WHERE owner_va=? AND target_va=? ORDER BY pc",
            (owner_va, target_va),
        )
    ]


def item_word_lookup(nso_path: Path, research_output: Path, item_table: dict) -> dict:
    """Run original 0xf58d00 over source ItemParam IDs in a reconstructed dense table."""
    if sha256(nso_path.read_bytes()) != NSO_SHA256:
        raise ValueError("main NSO does not match the 1.0.0 image required by this probe")

    table = load_json(item_table)
    manifest = load_json(research_output / "manifest.json")
    entry = manifest["entries"][table["source_id"]]
    decoded = load_json(research_output / entry["decoded"])["data"]
    raw_path = research_output / table["raw"]["$blob"]
    raw = raw_path.read_bytes()
    if sha256(raw) != table["raw"]["sha256"]:
        raise ValueError("ItemParam raw table checksum mismatch")

    col_index = {column["name"]: i for i, column in enumerate(table["columns"])}
    uid_index = col_index["UniqueID"]
    kind_index = col_index["ItemKind"]
    ids = [row[uid_index] for row in table["rows"]]
    if len(ids) != len(set(ids)):
        raise ValueError("ItemParam UniqueID is not unique in this source table")
    minimum, maximum = min(ids), max(ids)

    sandbox = Sandbox(nso_path)
    table_va = sandbox.alloc(len(raw))
    sandbox.uc.mem_write(table_va, raw)
    dense_count = maximum - minimum + 1
    dense_va = sandbox.alloc(dense_count * 8)
    sandbox.uc.mem_write(dense_va, bytes(dense_count * 8))
    meta_va = sandbox.alloc(0x200)
    definition_va = sandbox.alloc(0x57E60)
    for row_index, row in enumerate(table["rows"]):
        row_va = table_va + decoded["data_start"] + row_index * table["row_size"]
        sandbox.uc.mem_write(dense_va + (row[uid_index] - minimum) * 8,
                             struct.pack("<Q", row_va))
    sandbox.uc.mem_write(meta_va + 0x1D8, struct.pack("<I", dense_count))
    sandbox.uc.mem_write(meta_va + 0x1E0, struct.pack("<Q", dense_va))
    sandbox.uc.mem_write(meta_va + 0x1F8, struct.pack("<H", minimum))
    sandbox.uc.mem_write(definition_va + 0x57E58, struct.pack("<Q", meta_va))
    global_definition_ptr = sandbox.u64(0x32D3B88)
    sandbox.uc.mem_write(global_definition_ptr, struct.pack("<Q", definition_va))

    item_rows = []
    family_ids = {family: [] for family in FAMILIES}
    for row in table["rows"]:
        kind = row[kind_index]
        labels = kind.get("labels") if isinstance(kind, dict) else None
        if labels and labels[0] in family_ids:
            family = labels[0]
            family_ids[family].append(row[uid_index])
            item_from = row[col_index["ItemFrom"]]
            item_rows.append({
                "unique_id": row[uid_index],
                "label": row[col_index["Label"]],
                "item_name_ja": row[col_index["ItemName"]],
                "item_kind": family,
                "item_from": item_from.get("labels", [None])[0]
                if isinstance(item_from, dict) else None,
                "diy_recipe_id": row[col_index["DiyRecipeID"]],
                "remake_id": row[col_index["RemakeID"]],
            })

    word_va = sandbox.alloc(8)
    positives = []
    negatives = []
    unchanged_words = 0
    for item_id in sorted({item["unique_id"] for item in item_rows}):
        word = struct.pack("<HBBI", item_id, 0, 0, 0)
        sandbox.uc.mem_write(word_va, word)
        before = sandbox.read(word_va, 8)
        accepted = sandbox.call(0xF58D00, (word_va,), limit=10_000) & 1
        after = sandbox.read(word_va, 8)
        if accepted != 1:
            raise AssertionError(f"native ItemParam check rejected tool ItemUniqueID {item_id}")
        unchanged_words += before == after
        positives.append(item_id)

    negative_ids = sorted({minimum - 1, maximum + 1, 0xFFFE, 0xFFFF})
    for item_id in negative_ids:
        word = struct.pack("<HBBI", item_id, 0, 0, 0)
        sandbox.uc.mem_write(word_va, word)
        before = sandbox.read(word_va, 8)
        accepted = sandbox.call(0xF58D00, (word_va,), limit=10_000) & 1
        after = sandbox.read(word_va, 8)
        if accepted != 0:
            raise AssertionError(f"native ItemParam check accepted invalid item ID {item_id}")
        unchanged_words += before == after
        negatives.append({"unique_id": item_id, "accepted": False})

    if sandbox.unknown_imports:
        raise AssertionError(f"unexpected imported calls in native probe: {sandbox.unknown_imports}")
    return {
        "function_va": "0xf58d00",
        "native_callee_va": "0xa1e8c0",
        "caller_va": "0xe37a50",
        "caller_string": "PlayerToolBreak",
        "itemparam_dense_table": {
            "source_id": table["source_id"],
            "raw_sha256": table["raw"]["sha256"],
            "row_count": table["row_count"],
            "row_size": table["row_size"],
            "unique_id_range": [minimum, maximum],
            "reconstructed_rows": len(ids),
            "item_definition_lookup_contract":
                "0xf58d00 -> 0xa1e8c0 checks the dense ItemParam row pointer for the item's UniqueID.",
        },
        "positive_tool_ids": positives,
        "negative_ids": negatives,
        "cases": len(positives) + len(negatives),
        "mismatches": [],
        "item_word_mutations": len(positives) + len(negatives) - unchanged_words,
        "native_function_stubs": [],
        "unresolved_import_calls": sandbox.unknown_imports,
        "reconstructed_state": [
            "ItemParam BCSV row bytes copied to a sandbox allocation.",
            "Dense UniqueID-to-row pointer index and ItemParam definition wrapper.",
            "Packed item words with the tested UniqueID and zero remaining fields.",
        ],
    }, item_rows, family_ids


def parse_flow_tree(path: Path) -> dict:
    entries: dict[str, list[dict]] = {}
    current = None
    pattern = re.compile(r"^\s+#(\d+)\s+([^\s]+)(?:\s+(.*))?$")
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("== ENTRY "):
            current = line.removeprefix("== ENTRY ").strip()
            entries[current] = []
            continue
        match = pattern.match(line)
        if current is not None and match:
            tail = match.group(3) or ""
            params = None
            if tail.startswith("{") and tail.endswith("}"):
                params = json.loads(tail)
            entries[current].append({
                "event_index": int(match.group(1)),
                "op": match.group(2),
                "params": params,
                "text": None if params is not None else tail or None,
            })
    return entries


def state_summary(table_path: Path) -> tuple[dict, dict]:
    table = load_json(table_path)
    index = {column["name"]: i for i, column in enumerate(table["columns"])}
    rows = {row[index["StateName"]]: row for row in table["rows"]}
    result = {}
    for family, names in STATE_NAMES.items():
        summary = []
        for name in names:
            if name not in rows:
                raise AssertionError(f"PlayerStateParam state not found: {name}")
            row = rows[name]
            summary.append({key: row[index[key]] for key in (
                "StateName", "PacketType", "ToolState", "ObjCheckRate", "ObjCheckType",
                "ChangeDemo", "BgCheckType", "EnableRodCloth")
                if key in index})
        result[family] = summary
    return {"source_id": table["source_id"], "raw": table["raw"], "states": result}, result


def activity_counter_summary(table_path: Path) -> dict:
    """Resolve the named BreakToolCount activity-counter definition."""
    table = load_json(table_path)
    index = {column["name"]: i for i, column in enumerate(table["columns"])}
    rows = [row for row in table["rows"] if row[index["Key"]] == "BreakToolCount"]
    if len(rows) != 1:
        raise AssertionError(f"expected one BreakToolCount activity row, found {len(rows)}")
    row = rows[0]
    record = {name: row[index[name]] for name in (
        "UniqueID", "MessageLabel", "TalkValueVisitor", "TalkValueVillager",
        "MaxValue", "FlagsFlowAccess", "Name", "Key")}
    return {
        "source_id": table["source_id"],
        "source": table["source"],
        "raw": table["raw"],
        "record": record,
        "interpretation": "The source activity table labels this key as 道具を壊した回数 (number of tools broken), with MaxValue 64. It is an activity count, not a per-item wear value; the save-backed mutation remains unexecuted.",
    }


def ring_summary(path: Path) -> dict:
    doc = load_json(path)
    xlink = doc["root"]["@XLink"]
    return {
        "source_id": doc["source_id"],
        "source": doc["source"],
        "source_sha256": doc["source_sha256"],
        "user_name": xlink["@mUserName.Str"],
        "parts": [{
            "group": part["@mGroupName.Str"],
            "path": part["@mPath.Str"],
            "base_option": part["@mBaseOption.Bit"],
            "animations": [
                {"tag": animation["@mTagName.Str"],
                 "option": animation["@mAnimOpeOption.Bit"]}
                for animation in part["@mAnimOperationParamBuffer[]"]
            ],
        } for part in xlink["@mPartsParamBuffer[]"]],
        "tool_item_assignments_present_in_byml": False,
    }


def romfs_ring_layout_summary(romfs: Path) -> dict:
    layout_dir = romfs / "Layout"
    names = ("RingMenuTools.Nin_NX_NVN.zs", "LRingMenuTools.Nin_NX_NVN.zs",
             "LRingMenuToolsBtn.Nin_NX_NVN.zs")
    result = {}
    for name in names:
        path = layout_dir / name
        compressed = path.read_bytes()
        unpacked = subprocess.run(["zstd", "-dc", str(path)], check=True,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout
        strings = sorted({match.decode("ascii") for match in re.findall(
            rb"[\x20-\x7e]{4,}", unpacked)})
        result[name] = {
            "path": str(path),
            "compressed_sha256": sha256(compressed),
            "compressed_size": len(compressed),
            "embedded_layout_members": [s for s in strings
                                         if s.endswith((".arc", ".bflyt", ".bflan", ".bntx"))],
            "inventory_slot_nodes": [s for s in strings
                                     if re.fullmatch(r"Inv[0-7]", s)],
            "animation_names": [s for s in strings
                                if s in {"Select", "UnSelect", "Confirm", "EquipIn",
                                         "EquipOut", "ActiveReg", "SelectActiveReg",
                                         "DecideActiveReg", "UnSelectActiveReg", "InvAnim",
                                         "In", "Out", "InEffect", "Loop", "Inv0", "Inv1",
                                         "Inv2", "Inv3", "Inv4", "Inv5", "Inv6", "Inv7"}],
            "ring_root_node_present": "L_RingTool_00" in strings,
        }
    left_ring = result["LRingMenuTools.Nin_NX_NVN.zs"]
    button = result["LRingMenuToolsBtn.Nin_NX_NVN.zs"]
    if left_ring["inventory_slot_nodes"] != [f"Inv{i}" for i in range(8)]:
        raise AssertionError("expected eight Inv0..Inv7 nodes in the left tool-ring layout")
    if not {"Confirm", "EquipIn", "EquipOut"}.issubset(button["animation_names"]):
        raise AssertionError("expected confirm/equip animation names in the tool-ring button layout")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--nso", type=Path, default=ROOT / "inputs/additional_exefs/main")
    parser.add_argument("--research-output", type=Path,
                        default=Path("/workspace/acnh-re/output"))
    parser.add_argument("--itemparam", type=Path)
    parser.add_argument("--player-state", type=Path)
    parser.add_argument("--activity-param", type=Path)
    parser.add_argument("--ring-menu", type=Path)
    parser.add_argument("--tool-break-tree", type=Path,
                        default=ROOT / "output/gameplay/trees/Player_ToolBreak.txt")
    parser.add_argument("--flag-index", type=Path,
                        default=Path("/workspace/acnh-re/output/gameplay/flag_index.json"))
    parser.add_argument("--romfs", type=Path,
                        default=Path("/workspace/downloads/acnh_additional_romfs_2026-11-02/romfs"))
    parser.add_argument("--output", type=Path,
                        default=ROOT / "output/gameplay/tool_mechanics_followup/tool_mechanics_followup_native.json")
    args = parser.parse_args()
    itemparam_path = args.itemparam or args.research_output / "tables_resolved/ItemParam.json"
    player_state_path = args.player_state or args.research_output / "tables_resolved/PlayerStateParam.json"
    activity_param_path = args.activity_param or args.research_output / "tables_resolved/EventFlagsPlayerActivityParam.json"
    ring_path = args.ring_menu or args.research_output / "byml_resolved/01692.json"

    db = sqlite3.connect(args.research_output / "index.sqlite")
    try:
        native, item_rows, family_ids = item_word_lookup(args.nso, args.research_output,
                                                        itemparam_path)
        items_table = load_json(itemparam_path)
        items_columns = [column["name"] for column in items_table["columns"]]
        family_counts = {family: len(ids) for family, ids in family_ids.items()}
        state_table, states = state_summary(player_state_path)
        activity_counter = activity_counter_summary(activity_param_path)
        activity_counter = activity_counter_summary(activity_param_path)
        flow = parse_flow_tree(args.tool_break_tree)
        ring = ring_summary(ring_path)
        flag_index = load_json(args.flag_index)["data"]
        golden_axe_counter = flag_index["cPlayer:GoldenAxeLearningCount"]["definition"]
        break_achievement = flag_index["cLifeSupportAchievement:BreakTool"]["definition"]
        ring_layout_assets = romfs_ring_layout_summary(args.romfs)

        itemparam_match = direct_calls_to(db, 0xE37A50, 0xF58D00)
        dense_lookup_calls = direct_calls_to(db, 0xF58D00, 0xA1E8C0)
        slingshot_launch_call = direct_calls_to(db, 0xE564B0, 0x803690)
        if not itemparam_match:
            raise AssertionError("PlayerToolBreak no longer directly calls ItemParam item lookup")
        if not dense_lookup_calls:
            raise AssertionError("Item-word lookup no longer directly calls dense ItemParam resolver")
        if not slingshot_launch_call:
            raise AssertionError("PlayerSlingshotShooting no longer calls projectile-state consumer")
        native["native_callee_calls"] = dense_lookup_calls

        break_flow_source = source_record(db, "B_data/EventFlow/Player_ToolBreak.bfevfl")
        state_source = source_record(db, "B_data/Bcsv/PlayerStateParam.bcsv")
        activity_source = source_record(db, "B_data/Bcsv/EventFlagsPlayerActivityParam.bcsv")
        activity_source = source_record(db, "B_data/Bcsv/EventFlagsPlayerActivityParam.bcsv")
        ring_source = source_record(db, "B_data/Pack/StaticParam.pack!Param/Layout/RingMenuTools.byml")
        break_refs = refs_for(db, 0xE37A50)
        break_action_refs = refs_for(db, 0xE37830)
        slingshot_refs = refs_for(db, 0xE564B0)
        ring_refs = refs_for(db, 0x15566B0)
        action_anchor_refs = {
            family: [{"function_va": hex(va), "string_refs": refs_for(db, va)}
                     for va in vas]
            for family, vas in ACTION_ANCHORS.items()
        }
        state_registry_tool_refs = [
            ref for ref in refs_for(db, 0xDD9A60)
            if re.search(r"State::c(?:Axe|Scoop|Net|Rod|Slingshot|Watering)", ref["text"])
        ]
        ring_enum = next((r["text"] for r in ring_refs if "cRingMenuToolsMain" in r["text"]), None)
        ring_names = re.split(r"\s*,\s*", ring_enum) if ring_enum else []
        ring_page_ordinal = ring_names.index("cRingMenuToolsMain") if "cRingMenuToolsMain" in ring_names else None

        result = {
            "schema": "acnh-tool-mechanics-followup/1",
            "sources": {
                "main_nso_sha256": sha256(args.nso.read_bytes()),
                "main_nso_path": str(args.nso),
                "itemparam": {"source_id": items_table["source_id"],
                              "raw": items_table["raw"]},
                "player_state_param": state_source,
                "player_tool_break_eventflow": break_flow_source,
                "ring_menu_tools": ring_source,
            },
            "native_itemparam_probe": native,
            "itemparam_tool_families": {
                "families": family_counts,
                "items": sorted(item_rows, key=lambda row: (row["item_kind"], row["unique_id"])),
                "named_durability_columns": [name for name in items_columns
                    if any(token in name.lower() for token in ("durab", "break", "usecount", "uses"))],
                "unresolved_hashed_columns": [name for name in items_columns if name.startswith("h_")],
            },
            "player_state_param_tool_states": {
                "source": state_table,
                "families": states,
            },
            "player_tool_break_eventflow": {
                "source": break_flow_source,
                "entries": flow,
                "counters_and_flags": {
                    "break_tool_count_activity_counter": {
                        **activity_counter,
                        "indexed_source": activity_source,
                    },
                    "golden_axe_recipe_learning_counter": {
                        "key": "cPlayer:GoldenAxeLearningCount",
                        "definition": golden_axe_counter,
                        "interpretation": "Separate recipe-learning counter changed by ToolBreak_Axe; not tool durability.",
                    },
                    "break_tool_achievement": {
                        "key": "cLifeSupportAchievement:BreakTool",
                        "definition": break_achievement,
                        "interpretation": "Achievement flag named for breaking a tool; the indexed 1.0.0 EventFlow data has no writer, so native writer or lack of write is unresolved.",
                    },
                    "break_tool_count_activity_counter": {
                        **activity_counter,
                        "indexed_source": activity_source,
                    },
                },
                "axe_entry_observations": [
                    "ToolBreak_Axe checks PlayerHasCraftRecipe for ItemUniqueId 9617.",
                    "It checks cPlayer:GoldenAxeLearningCount against Border 99.",
                    "On case 1 it adds 1 to cPlayer:GoldenAxeLearningCount; case 0 can queue GetRecipe_GoldenAxe when MainmenuRecipe is on.",
                ],
            },
            "native_break_path": {
                "player_tool_break_va": "0xe37a50",
                "player_tool_break_strings": break_refs,
                "break_tool_action_va": "0xe37830",
                "break_tool_action_strings": break_action_refs,
                "itemparam_lookup_call": itemparam_match,
                "state_counter_instruction_sites": [
                    {"va": "0xe37c60", "bytes": "08050011", "instruction": "add w8, w8, #1"},
                    {"va": "0xe37c64", "bytes": "689a08b9", "instruction": "str w8, [x19, #0x898]"},
                    {"va": "0xe37c70", "bytes": "08050011", "instruction": "add w8, w8, #1"},
                    {"va": "0xe37c74", "bytes": "689a08b9", "instruction": "str w8, [x19, #0x898]"},
                    {"va": "0xe37904", "bytes": "7f9a08b9", "instruction": "str wzr, [x19, #0x898]"},
                    {"va": "0xe37908", "bytes": "7f722239", "instruction": "strb wzr, [x19, #0x89c]"},
                ],
                "counter_interpretation": "The native PlayerToolBreak state increments its local +0x898 field on these branches; BreakTool clears +0x898 and +0x89c. This does not establish per-tool inventory durability or a decrement.",
            },
            "tool_action_results": {
                "native_action_anchor_refs": action_anchor_refs,
                "state_registry": {
                    "function_va": "0xdd9a60",
                    "tool_state_string_refs": state_registry_tool_refs,
                    "interpretation": "Constructor/registry evidence for tool state names, not a durability calculator or proof of world-result mutation.",
                },
                "Axe": {"status": "state-and-break-flow-proven", "open": ["tree-hit result, drop result, and inventory/durability mutation"]},
                "Shovel": {"status": "state-proven", "open": ["dig/bury world result and inventory/durability mutation"]},
                "Net": {"status": "state-proven", "open": ["capture eligibility, caught-insect inventory result, and durability mutation"]},
                "FishingRod": {"status": "state-proven", "open": ["bite/catch/release output, inventory result, and durability mutation"]},
                "Slingshot": {"status": "native-launch-call-mapped", "function_va": "0xe564b0",
                    "string_refs": slingshot_refs, "launch_consumer_call": slingshot_launch_call,
                    "result": "On its valid-target path PlayerSlingshotShooting reaches 0x803690 to write projectile start/direction state; the consumer scales the three supplied velocity components by 6.",
                    "open": ["projectile actor creation/collision, inventory result, and durability mutation"]},
                "Watering": {"status": "state-proven", "open": ["plant watering mutation, flower response, and durability mutation"]},
            },
            "tool_ring": {
                "layout": ring,
                "native_menu_type_string": ring_enum,
                "native_menu_type_ordinal": ring_page_ordinal,
                "native_initializer_va": "0x15566b0",
                "native_initializer_refs": ring_refs,
                "romfs_layout_assets": ring_layout_assets,
                "native_slot_widget_binding": {
                    "setup_va": "0x1424f00",
                    "binder_va": "0x1424660",
                    "binder_string_refs": refs_for(db, 0x1424660),
                    "parsed_index": {"parser_va": "0x1992970", "maximum": 7,
                                     "bounds_check_va": "0x1424984"},
                    "widget_pointer_array": {
                        "base_offset_from_this": "0x5d8",
                        "stride_bytes": 8,
                        "address_calculation_va": "0x142498c",
                        "pointer_store_va": "0x1424990",
                    },
                    "interpretation": "The numeric button index selects one of eight UI widget-pointer entries. This is not a ring-slot-to-inventory-item mapping.",
                },
                "native_selector_permutation": {
                    "constructor_va": "0x14254f0",
                    "lookup_va": "0x1412770",
                    "array_offset_from_this": "0x1b980",
                    "table_values_by_index": [2, 1, 0, 7, 6, 5, 4, 3],
                    "native_probe_result": "output/gameplay/tool_mechanics_followup/tool_ring_index_native.json",
                    "interpretation": "Verified internal selector transform; semantic source and inventory relationship remain unresolved.",
                },
                "layout_interpretation": "RomFS layout strings establish eight inventory-slot nodes and select/confirm/equip animations; they do not identify the runtime item stored in a slot.",
                "open": ["inventory item-to-ring-slot map, selection/equip handler, and resulting tool action"],
            },
            "limitations": [
                "The ItemParam probe verifies that tool UniqueIDs resolve to real ItemParam rows through the exact lookup called by PlayerToolBreak; it does not read or prove a durability value.",
                "ItemParam exposes no column named durability, break count, use count, or uses; unresolved hashed columns remain possible but are not treated as durability without consumer evidence.",
                "The full PlayerToolBreak/BreakTool state routines were not emulated. The observed +0x898 increment and reset are state-local memory operations, not a verified inventory durability counter.",
                "BreakToolCount is identified by EventFlagsPlayerActivityParam as a count of tools broken. Its save mutation and relationship to per-item wear remain unexecuted.",
                "BreakToolCount is identified by EventFlagsPlayerActivityParam as a count of broken tools. Its save mutation and relationship to per-item wear remain unexecuted.",
                "Axe, shovel, net, rod, and watering action states are sourced from PlayerStateParam; their world-result and item-consumption chains remain open.",
                "The RingMenuTools BYML, native page registry, and slot-widget binder identify UI layout and button indexing; they do not connect a ring position to a runtime inventory item.",
            ],
        }
    finally:
        db.close()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8")
    print(json.dumps({
        "output": str(args.output),
        "native_tool_item_cases": result["native_itemparam_probe"]["cases"],
        "native_tool_item_mismatches": len(result["native_itemparam_probe"]["mismatches"]),
        "families": result["itemparam_tool_families"]["families"],
        "state_rows": {family: len(rows) for family, rows in states.items()},
        "ring_menu_page_ordinal": ring_page_ordinal,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
