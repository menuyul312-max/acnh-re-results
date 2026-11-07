#!/usr/bin/env python3
"""Reproduce the bounded static audit for the next DIY transaction boundary.

Reads the shared dump/index and existing evidence without modifying them. The
only output is next_boundary_audit.json in this directory.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3

WORKTREE = Path(__file__).resolve().parents[4]
PROJECT = WORKTREE / "acnh-re"
SHARED = Path("/workspace/acnh-re")
OUT = Path(__file__).resolve().parent


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def file_info(path):
    path = Path(path)
    if not path.is_file():
        return {"path": str(path), "exists": False}
    stat = path.stat()
    return {
        "path": str(path),
        "exists": True,
        "bytes": stat.st_size,
        "sha256": sha256(path),
        "mtime_utc": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
    }


def read_json(path):
    return json.loads(Path(path).read_text())


def table_info(name):
    table_path = SHARED / "output" / "tables_resolved" / f"{name}.json"
    table = read_json(table_path)
    blob = SHARED / "output" / table["raw"]["$blob"]
    actual_blob_hash = sha256(blob)
    assert actual_blob_hash == table["raw"]["sha256"], f"{name} BCSV blob hash mismatch"
    return {
        "resolved_json": file_info(table_path),
        "rows": len(table["rows"]),
        "raw_bcsv": {
            "path": str(blob),
            "bytes": blob.stat().st_size,
            "sha256": actual_blob_hash,
        },
        "data": table,
    }


def selected_edges(db_path):
    db = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        edges = {}
        for owner, target in (
            (0xEE1420, 0xEE0ED0),
            (0xEE1420, 0xEFF060),
            (0xEE1420, 0xEE1060),
            (0xEE1420, 0xEFBD30),
            (0xEFF060, 0xF9E410),
        ):
            pcs = [f"0x{pc:x}" for (pc,) in db.execute(
                "SELECT pc FROM direct_calls WHERE owner_va=? AND target_va=? ORDER BY pc",
                (owner, target),
            )]
            edges[f"0x{owner:x}->0x{target:x}"] = pcs
        assert len(edges["0xee1420->0xeff060"]) == 6
        assert len(edges["0xee1420->0xee1060"]) == 6
        assert edges["0xeff060->0xf9e410"] == ["0xeff0e4"]
        return edges
    finally:
        db.close()


def main():
    output_root = SHARED / "output"
    manifest_path = output_root / "manifest.json"
    manifest = read_json(manifest_path)
    analysis_elf = Path(manifest["source_root"]) / "A_logic" / "main.elf"
    main_nso = SHARED / "inputs" / "additional_exefs" / "main"
    index_path = output_root / "index.sqlite"
    local_index = PROJECT / "output" / "index.sqlite"

    assert analysis_elf.is_file() and main_nso.is_file() and index_path.is_file()
    assert index_path.stat().st_size > 0
    with sqlite3.connect(f"file:{index_path}?mode=ro", uri=True) as db:
        available_tables = {row[0] for row in db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        assert {"direct_calls", "native_functions", "decomp_new"} <= available_tables

    queue_path = PROJECT / "docs" / "re_queue.json"
    queue = read_json(queue_path)
    craft_item = next(item for item in queue["items"] if item["id"] == "crafting-diy")
    followup_doc = PROJECT / "docs" / "CRAFTING_TRANSACTION_FOLLOWUP.md"

    old_branch = PROJECT / "output/gameplay/crafting_transaction_followup/crafting_transaction_branch_native.json"
    new_branch = OUT / "crafting_transaction_branch_native.json"
    old_branch_data = read_json(old_branch)
    new_branch_data = read_json(new_branch)
    assert old_branch_data == new_branch_data, "bounded branch reproduction differs from 08:41 artifact"
    assert old_branch_data["provenance"]["analysis_elf_sha256"] == sha256(analysis_elf)
    assert old_branch_data["provenance"]["main_nso_sha256"] == sha256(main_nso)

    fixture_attempt_path = PROJECT / "output/gameplay/crafting_transaction_followup/crafting_transaction_fixture_attempt.json"
    fixture_attempt = read_json(fixture_attempt_path)
    blocker = fixture_attempt["blockers"]["ee1420"]
    assert blocker["first_unmapped_access"]["pc"] == "0xab941c"

    recipe = table_info("RecipeCraftParam")
    itemparam = table_info("ItemParam")
    itemkind = table_info("ItemKind")
    columns = {column["name"]: i for i, column in enumerate(recipe["data"]["columns"])}
    row56 = next(row for row in recipe["data"]["rows"] if row[columns["UniqueID"]] == 56)
    recipe56 = {
        "recipe_id": row56[columns["UniqueID"]],
        "result_item_id": row56[columns["Item"]],
        "materials": [
            {
                "slot": i + 1,
                "item_id": row56[columns[f"Material{i + 1}"]],
                "amount": row56[columns[f"Amount{i + 1}"]],
            }
            for i in range(6)
        ],
    }
    assert recipe56["result_item_id"] == 975
    assert [m["item_id"] for m in recipe56["materials"]] == [2213, 2285, 2287, 2214, 2286, 65534]

    recipe_flow_path = PROJECT / "output/gameplay/crafting_transaction_followup/crafting_recipe_flow_native.json"
    recipe_flow = read_json(recipe_flow_path)
    leaf_probe = recipe_flow["material_and_workbench"]["consumption_leaf_probe"]

    result = {
        "schema": "acnh.crafting.transaction_remainder_boundary_audit.v1",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "Read-only provenance and boundary audit. It reproduces the existing bounded native branch artifact and identifies the next material-consumption boundary; it does not execute a full craft transaction.",
        "queue_snapshot": {
            "source": file_info(queue_path),
            "crafting_diy_status": craft_item["status"],
            "goal": craft_item["goal"],
            "remaining": craft_item.get("remaining", []),
        },
        "sources": {
            "analysis_elf": file_info(analysis_elf),
            "main_nso": file_info(main_nso),
            "shared_index": file_info(index_path),
            "shared_manifest": file_info(manifest_path),
            "worktree_same_name_index": {
                **file_info(local_index),
                "used": False,
                "reason": "This worktree copy is empty; queries use the valid shared index above.",
            },
            "tables": {
                "RecipeCraftParam": {k: v for k, v in recipe.items() if k != "data"},
                "ItemParam": {k: v for k, v in itemparam.items() if k != "data"},
                "ItemKind": {k: v for k, v in itemkind.items() if k != "data"},
            },
            "recipe_56": recipe56,
        },
        "existing_evidence": {
            "followup_doc": file_info(followup_doc),
            "08_41_branch_artifact": file_info(old_branch),
            "bounded_branch_reproduction": file_info(new_branch),
            "reproduction_byte_identical_to_08_41": sha256(old_branch) == sha256(new_branch),
            "fixture_attempt": file_info(fixture_attempt_path),
            "recipe_flow_leaf_probe": file_info(recipe_flow_path),
            "signed_delta_leaf_probe": {
                "helper_va": leaf_probe["signed_count_helper_va"],
                "stack_match_gate_va": leaf_probe["stack_match_gate_va"],
                "cases": [
                    {k: case[k] for k in ("case", "item_id", "available_count_before", "requested_remove", "available_count_after", "changed_byte_offsets")}
                    for case in leaf_probe["cases"]
                ],
                "limitation": leaf_probe["stubbed_boundary"],
            },
            "prior_ee1420_fixture_blocker": {
                "path": blocker["path"],
                "dependency_global": blocker["dependency_global"],
                "first_unmapped_access": blocker["first_unmapped_access"],
                "interpretation": blocker["behavior"],
            },
        },
        "native_static_edges": selected_edges(index_path),
        "bounded_branch_result": {
            "schema": old_branch_data["schema"],
            "case_names": list(old_branch_data["cases"]),
            "branch_findings": old_branch_data["branch_findings"],
            "transaction_limits": old_branch_data["transaction_limits"],
            "sample_fixture_stubs": old_branch_data["cases"]["full_pocket_marker_zero"]["stubs_and_limits"],
        },
        "next_boundary": {
            "target": "Run the original 0xeff060 per-material mutator through 0xf9e410 for one table-backed material, beginning with RecipeCraftParam row 56 / Apple item 2213.",
            "reason": "The current branch probe has already covered the pocket-full gate, material-descriptor source, and result-insertion route, but replaces both 0xeff060 and 0xee1060 with no-op callbacks. The signed quantity leaf 0xf9e410 was separately exercised on a controlled slot fixture, so the missing high-value seam is the native wrapper plus its item-data/player-view lookup context.",
            "required_fixture_work": [
                "Reconstruct or reach the runtime item-data/index manager required by the original 0xa9e440 -> 0xa774c0 -> 0xab9400 lookup; available RecipeCraftParam, ItemParam, and ItemKind tables supply rows, not the live manager pointer graph.",
                "Supply the minimum player/view service data used by 0xeff060, then leave its 0xf9e410 call and the 0xaac730 item/stack gate native; do not force the gate to success.",
                "First prove one Apple count delta and unchanged item identity in a controlled pocket fixture. Then extend to the five recipe-56 materials and an insufficient-material control before reopening the full 0xee1420 branch.",
            ],
            "boundaries_still_open": [
                "0xee1060 branch behavior and complete material sufficiency/consumption in the transaction.",
                "Real 0xedf8e0 UI payload and full SaveSetFromUIResult cWorkCraft dispatch.",
                "Cancellation/interruption and rollback/atomicity after native mutations.",
                "SaveProc serializer callback, durable write/flush, and linkage from the in-memory dirty slot marker.",
            ],
            "evidence_class": "All current transaction runs use controlled synthetic fixtures; no live game process or real player save was supplied.",
        },
    }

    out_path = OUT / "next_boundary_audit.json"
    out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(out_path)


if __name__ == "__main__":
    main()
