#!/usr/bin/env python3
"""Bounded audit of tool wear candidates in ItemParam and native call/xref data.

This records what the 1.0.0 source table and local function index can prove;
it intentionally does not infer durability from telemetry field names.
"""
import argparse
import json
import re
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INDEX = Path("/workspace/acnh-re/output/index.sqlite")
DEFAULT_RESEARCH = Path("/workspace/acnh-re/output")
DEFAULT_OUTPUT = ROOT / "output/gameplay/tool_mechanics_followup/tool_durability_static_audit.json"
OUTFITINFO_FIELD_HASH = 0x68DB76C2

TOOL_KINDS = ("Axe", "Shovel", "Net", "FishingRod", "Slingshot", "Watering")
BREAK_PATHS = {
    "player_tool_break_state": 0xE37A50,
    "break_tool_action": 0xE37830,
    "break_counter_dispatch": 0xE37950,
    "force_break_demo": 0xE37ED0,
}
TOOL_ACTIONS = {
    "axe_hit_tree": 0xE36EC0,
    "shovel_dig": 0xE52390,
    "shovel_bury": 0xE52850,
    "shovel_get_demo": 0xE541A0,
    "net_get_demo": 0xE45B80,
    "rod_get_demo": 0xE4E730,
    "slingshot_shoot": 0xE564B0,
    "watering": 0xE585C0,
}
TELEMETRY = {
    0xEADFA0: {"event_id": 0x15, "context": "rock-strike callbacks", "fields": ["IsPopItem", "PopItemUniqueId", "ToolDamage", "ToolUniqueId"]},
    0xEAE890: {"event_id": 0x16, "context": "tree/item callback; includes tree metadata", "fields": ["IsPopItem", "PopItemUniqueId", "ToolDamage", "ToolUniqueId", "TreeGrowLevel", "TreeKind"]},
    0xEB7D90: {"event_id": 7, "context": "fish-catch event", "fields": ["FishTableId", "FishUniqueId", "ToolDamage", "ToolUniqueId"]},
    0xEB8690: {"event_id": 6, "context": "insect-catch event", "fields": ["InsectTableId", "InsectUniqueId", "ToolDamage", "ToolUniqueId"]},
}
WEAR_FIELD_RE = re.compile(r"durab|wear|break.?count|use.?count|remain.?use|tool.?damage", re.I)


def display(value):
    if isinstance(value, dict):
        labels = value.get("labels") or []
        return labels[0] if labels else value.get("hash")
    return value


def function_record(conn, va):
    name_row = conn.execute("SELECT name FROM native_functions WHERE va=?", (va,)).fetchone()
    if name_row is None:
        name_row = conn.execute("SELECT ghidra_name FROM functions WHERE va=?", (va,)).fetchone()
    paths = conn.execute("SELECT path FROM decomp_new WHERE va=?", (va,)).fetchone()
    if paths is None:
        paths = conn.execute("SELECT decomp_path FROM functions WHERE va=?", (va,)).fetchone()
    calls = [row[0] for row in conn.execute(
        "SELECT DISTINCT target_va FROM direct_calls WHERE owner_va=? ORDER BY target_va", (va,)
    )]
    refs = [row[0] for row in conn.execute(
        "SELECT text FROM string_refs WHERE function_va=? ORDER BY text", (va,)
    )]
    parents = sorted({row[0] for row in conn.execute(
        "SELECT owner_va FROM direct_calls WHERE target_va=? AND owner_va IS NOT NULL", (va,)
    )})
    return {
        "function_va": hex(va),
        "name": name_row[0] if name_row else None,
        "pseudocode": paths[0] if paths else None,
        "string_refs": refs,
        "direct_call_targets": [hex(target) for target in calls],
        "direct_callers": [hex(parent) for parent in parents],
        "directly_calls_inventory_record_writer_f57ed0": 0xF57ED0 in calls,
    }


def itemparam_audit(conn, research_root):
    table_path = research_root / "tables_resolved/ItemParam.json"
    table = json.loads(table_path.read_text())
    columns = {column["name"]: index for index, column in enumerate(table["columns"])}
    unknown = [column for column in table["columns"] if column.get("name_evidence") == "unresolved"]
    tool_rows = {kind: [] for kind in TOOL_KINDS}
    for row_index, row in enumerate(table["rows"]):
        kind = display(row[columns["ItemKind"]])
        if kind not in tool_rows:
            continue
        tool_rows[kind].append({
            "row_index": row_index,
            "unique_id": row[columns["UniqueID"]],
            "item_name": row[columns["ItemName"]],
            "unknown_fields": {column["name"]: display(row[index])
                               for index, column in enumerate(table["columns"])
                               if column.get("name_evidence") == "unresolved"},
        })
    named_candidates = [name for name in columns if WEAR_FIELD_RE.search(name)]
    unresolved_fields = []
    for column in unknown:
        raw_hash = int(column["hash"], 16)
        refs = []
        for pc, owner in conn.execute(
            "SELECT pc,owner_va FROM hash_refs WHERE hash=? ORDER BY pc", (raw_hash,)
        ):
            refs.append({"pc": hex(pc), "owner_va": hex(owner) if owner is not None else None})
        nondefault = []
        for kind, rows in tool_rows.items():
            for row in rows:
                value = row["unknown_fields"][column["name"]]
                if value not in (None, 0, "None", "未設定"):
                    nondefault.append({"item_kind": kind, "unique_id": row["unique_id"], "value": value})
        unresolved_fields.append({
            "name": column["name"],
            "offset": column.get("offset"),
            "width": column.get("width"),
            "type": column.get("type"),
            "hash": column["hash"],
            "native_hash_refs": refs,
            "nondefault_tool_rows": nondefault,
        })
    counts = {kind: len(rows) for kind, rows in tool_rows.items()}
    return {
        "source_sha256": table.get("raw", {}).get("sha256"),
        "row_count": table.get("row_count"),
        "column_count": len(columns),
        "named_wear_or_damage_columns": named_candidates,
        "tool_item_rows_by_kind": counts,
        "tool_items": tool_rows,
        "unresolved_fields": unresolved_fields,
        "interpretation_limit": (
            "No named wear/durability field exists in this resolved ItemParam schema. "
            "Unresolved values remain candidates only; their native field readers do not establish semantics."
        ),
    }


def tool_break_thresholds(itemparam_path, outfitinfo_path):
    """Join each player tool's ItemParam.ItemOutfitInfo value to BreakDamage."""
    item_table = json.loads(itemparam_path.read_text())
    outfit_table = json.loads(outfitinfo_path.read_text())
    item_cols = {column["name"]: index for index, column in enumerate(item_table["columns"])}
    outfit_cols = {column["name"]: index for index, column in enumerate(outfit_table["columns"])}
    required_item = {"UniqueID", "ItemKind", "ItemOutfitInfo", "Label"}
    required_outfit = {"UniqueID", "Label", "BreakDamage"}
    if not required_item.issubset(item_cols) or not required_outfit.issubset(outfit_cols):
        raise ValueError("resolved ItemParam/ItemOutfitInfo schemas lack required columns")

    outfit_by_label = {
        row[outfit_cols["Label"]]: (row_index, row)
        for row_index, row in enumerate(outfit_table["rows"])
    }
    joined = []
    for row in item_table["rows"]:
        kind = display(row[item_cols["ItemKind"]])
        if kind not in TOOL_KINDS:
            continue
        reference = row[item_cols["ItemOutfitInfo"]]
        labels = reference.get("labels", []) if isinstance(reference, dict) else []
        matches = [outfit_by_label[label] for label in labels if label in outfit_by_label]
        if len(matches) != 1:
            raise ValueError(
                f"ItemParam tool {row[item_cols['UniqueID']]} has {len(matches)} ItemOutfitInfo matches"
            )
        outfit_row_index, outfit_row = matches[0]
        joined.append({
            "unique_id": row[item_cols["UniqueID"]],
            "label": row[item_cols["Label"]],
            "item_kind": kind,
            "item_outfit_info_ref": reference,
            "item_outfit_info_unique_id": outfit_row[outfit_cols["UniqueID"]],
            "item_outfit_info_row_index": outfit_row_index,
            "item_outfit_info_label": outfit_row[outfit_cols["Label"]],
            "break_damage": outfit_row[outfit_cols["BreakDamage"]],
        })

    if len(joined) != 32:
        raise ValueError(f"expected 32 tool ItemParam rows joined, found {len(joined)}")
    return {
        "source_sha256": outfit_table.get("raw", {}).get("sha256"),
        "row_count": outfit_table.get("row_count"),
        "break_damage_column": {
            "name": "BreakDamage",
            "hash": f"{OUTFITINFO_FIELD_HASH:08x}",
            "offset": 42,
            "width": 2,
            "type": "u16",
            "resolved_name_evidence": "crc32_exact_descriptor_and_local_schema",
        },
        "tool_rows": sorted(joined, key=lambda item: (TOOL_KINDS.index(item["item_kind"]), item["unique_id"])),
        "interpretation": (
            "Native helpers read the current ToolDamage field, add wear to it, and read the ItemOutfitInfo "
            "BreakDamage field used as the item's damage limit. The field and table join are proven; the "
            "exact threshold-to-PlayerToolBreak transition is not established by this table join alone."
        ),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--index-db", type=Path, default=DEFAULT_INDEX)
    parser.add_argument("--research-root", type=Path, default=DEFAULT_RESEARCH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    uri = f"file:{args.index_db.resolve()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    telemetry_functions = {}
    for va, metadata in TELEMETRY.items():
        record = function_record(conn, va)
        direct_targets = {int(item, 16) for item in record["direct_call_targets"]}
        telemetry_functions[hex(va)] = {
            **metadata,
            **record,
            "telemetry_helpers_present": {
                hex(target): target in direct_targets
                for target in (0xED3D30, 0xED2620, 0xED2600)
            },
        }
    result = {
        "schema": "acnh-re/tool-durability-static-audit/1",
        "evidence_level": "STATIC_INDEX_AND_TABLE_AUDIT",
        "game_version": "1.0.0",
        "itemparam": itemparam_audit(conn, args.research_root),
        "tool_break_thresholds": tool_break_thresholds(
            args.research_root / "tables_resolved/ItemParam.json",
            args.research_root / "tables_resolved/ItemOutfitInfo.json",
        ),
        "break_path_functions": {
            name: function_record(conn, va) for name, va in BREAK_PATHS.items()
        },
        "tool_action_functions": {
            name: function_record(conn, va) for name, va in TOOL_ACTIONS.items()
        },
        "tool_damage_telemetry_functions": telemetry_functions,
        "wear_native_functions": {
            "tool_damage_getter": function_record(conn, 0xAA7700),
            "tool_damage_incrementer": function_record(conn, 0xAA77D0),
            "tool_damage_reset": function_record(conn, 0xAA79A0),
            "remaining_damage_getter": function_record(conn, 0xAA7CE0),
            "break_damage_table_getter": function_record(conn, 0xAA7B90),
            "wear_apply_and_slot_dirty_marker": function_record(conn, 0xE895A0),
            "tool_action_wear_wrapper": function_record(conn, 0xE893C0),
            "tool_item_commit_wrapper": function_record(conn, 0xDB00F0),
        },
        "wear_contract": {
            "current_damage_word_offset": 6,
            "current_damage_width_bits": 10,
            "increment_clamp": 999,
            "increment_by_action_wrapper": 1,
            "break_damage_source": "ItemOutfitInfo.BreakDamage (hash 0x68db76c2, u16 offset 42)",
            "remaining_formula": "BreakDamage - current ToolDamage",
            "e895a0_effect": "Adds the supplied amount, copies the packed word back, and marks the selected player-item slot dirty (bit 0x4000).",
            "e893c0_effect": "Calls e895a0 with amount 1 before continuing its player/save state path.",
            "edge_evidence": {
                "e893c0_to_e895a0": "direct native call with w2 = 1 at 0xe89420-0xe89428",
                "e895a0_to_aa77d0": "direct native call with w1 = supplied amount at 0xe895e8-0xe895f0",
                "break_damage_hash_readers": ["0xaa7a30", "0xaa7b90"],
            },
        },
        "telemetry_interpretation": (
            "The ToolDamage string references are field labels in four event-record serializers. "
            "They call the event-ID/counter serializer at 0xed3d30 and field writers at "
            "0xed2620/0xed2600; their callers are rock/tree/catch reporting paths. Their value "
            "comes through 0xe89360 -> 0xaa7700, the same packed current-damage getter used by the "
            "wear helpers. These serializers report the field; they do not mutate it or flush saves."
        ),
        "remaining_blockers": [
            "The native wear field and per-tool BreakDamage limits are identified, but the exact condition/call edge that transitions a zero-remaining tool into PlayerToolBreak is not recovered; action/state dispatch is partly indirect.",
            "ItemParam unresolved fields, including h_9ec34ed4 (nondefault on four shovel rows), remain unclassified; they are not needed for the proven BreakDamage join.",
            "The e893c0/e895a0 path updates the packed item descriptor and dirty marker, but a live save flush/serializer trace is unavailable.",
            "No live tool-use sequence is available to verify family-specific wear cadence and the visible break transition end to end.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    conn.close()
    print(json.dumps({
        "schema": result["schema"],
        "named_wear_or_damage_columns": result["itemparam"]["named_wear_or_damage_columns"],
        "tool_item_rows_by_kind": result["itemparam"]["tool_item_rows_by_kind"],
        "unresolved_field_count": len(result["itemparam"]["unresolved_fields"]),
        "telemetry_functions": len(result["tool_damage_telemetry_functions"]),
        "output": str(args.output),
    }, indent=2))


if __name__ == "__main__":
    main()
