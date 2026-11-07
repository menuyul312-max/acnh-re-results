#!/usr/bin/env python3
"""Reproduce one native region-release mutation and bind the action-path gap."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sqlite3
import struct
import sys


OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
SHARED_OUTPUT = Path("/workspace/acnh-re/output")
SHARED_INDEX = SHARED_OUTPUT / "index.sqlite"
ROMFS = Path("/workspace/downloads/acnh_additional_romfs_2026-11-02/romfs")
ACTION_BCSV = ROMFS / "Bcsv/FieldLandMakingActionParam.bcsv"
ACTION_TABLE_JSON = SHARED_OUTPUT / "tables_resolved/FieldLandMakingActionParam.json"
DECOMP = SHARED_OUTPUT / "binary/analysis_decomp"
PBC_AUDIT = ROOT / "output/ui_island/manifests_pbc_audit.json"
EXPECTED_ELF_SHA256 = "5bf707c3dc5dac0ad9635af7d336ec580f81c3f7876d0f55400d1900e3415d74"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def label(value):
    if isinstance(value, dict):
        labels = value.get("labels") or []
        return labels[0] if labels else value.get("hash")
    return value


def action_slice() -> dict:
    table = json.loads(ACTION_TABLE_JSON.read_text())
    columns = [column["name"] for column in table["columns"]]
    by_name = {name: i for i, name in enumerate(columns)}
    required = {"ActionRange", "Layer", "SuccessResult", "FallActionType", "FallToRiver", "MainType"}
    assert required <= by_name.keys(), (required, by_name)
    rows = []
    for row_index, values in enumerate(table["rows"]):
        action = {name: values[by_name[name]] for name in required}
        if label(action["FallActionType"]) not in {"None", None}:
            rows.append({
                "source_row_index": row_index,
                "action_range": label(action["ActionRange"]),
                "layer": label(action["Layer"]),
                "success_result": label(action["SuccessResult"]),
                "fall_action_type": label(action["FallActionType"]),
                "fall_to_river": action["FallToRiver"],
                "main_type_raw_u8": action["MainType"],
            })
    assert len(table["rows"]) == 17
    assert [(row["fall_action_type"], row["fall_to_river"]) for row in rows] == [
        ("MakeFall", 0), ("BreakFall", 1)
    ]
    raw_sha = sha256_file(ACTION_BCSV)
    assert raw_sha == table["raw"]["sha256"] == "fe3f06ae6fb26c95631e842cd043a52348ba2c7399fc5d6085ff13dcfed0af9a"

    # Capture the ELF locations that reference the three action fields used here.
    db = sqlite3.connect(f"file:{SHARED_INDEX}?mode=ro", uri=True)
    field_locations = {}
    for name in ("FallActionType", "FallToRiver", "MainType"):
        column = next(column for column in table["columns"] if column["name"] == name)
        field_hash = int(column["hash"], 16)
        refs = db.execute(
            "SELECT pc, owner_va FROM hash_refs WHERE hash=? ORDER BY owner_va,pc",
            (field_hash,),
        ).fetchall()
        owners = sorted({owner for _, owner in refs})
        caller_rows = []
        for owner in owners:
            caller_rows.extend(db.execute(
                "SELECT pc, owner_va, target_va FROM direct_calls WHERE target_va=? ORDER BY owner_va,pc",
                (owner,),
            ).fetchall())
        field_locations[name] = {
            "hash": hex(field_hash),
            "elf_hash_reference_locations": [
                {"pc": hex(pc), "owner_function": hex(owner)} for pc, owner in refs
            ],
            "direct_callers_of_reference_functions": [
                {"pc": hex(pc), "owner_function": hex(caller), "target_function": hex(target)}
                for pc, caller, target in caller_rows
            ],
        }
    db.close()

    return {
        "source": {
            "path": str(ACTION_BCSV),
            "sha256": raw_sha,
            "bytes": ACTION_BCSV.stat().st_size,
            "resolved_json_path": str(ACTION_TABLE_JSON),
            "resolved_json_sha256": sha256_file(ACTION_TABLE_JSON),
            "row_count": len(table["rows"]),
        },
        "fall_action_rows": rows,
        "field_hash_reference_inventory": field_locations,
        "limits": [
            "MakeFall/BreakFall and FallToRiver are table values; this slice does not identify the live player action, validation callback, or save transaction that consumes them.",
            "MainType is preserved as a raw byte because its enum meaning is not established here.",
            "Hash-reference locations show where field hashes occur; they do not alone prove runtime row consumption.",
        ],
    }


def direct_calls(db, owner: int) -> list[dict]:
    rows = db.execute(
        "SELECT pc,target_va FROM direct_calls WHERE owner_va=? ORDER BY pc",
        (owner,),
    ).fetchall()
    return [{"pc": hex(pc), "target": hex(target)} for pc, target in rows]


def direct_callers(db, target: int) -> list[dict]:
    rows = db.execute(
        "SELECT pc,owner_va FROM direct_calls WHERE target_va=? ORDER BY owner_va,pc",
        (target,),
    ).fetchall()
    return [{"pc": hex(pc), "caller": hex(owner)} for pc, owner in rows]


def trace_fixture() -> dict:
    # Import the project harness, which loads original AArch64 instructions.
    sys.path.insert(0, str(ROOT / "tools"))
    sys.path.insert(0, "/workspace/acnh-re/.deps")
    from terrain_nav_flags_native import WorldHarness  # noqa: E402

    harness = WorldHarness()
    harness.reset()
    sandbox, memory, image = harness.s, harness.u, harness.im
    elf_sha = hashlib.sha256(image.data).hexdigest()
    assert elf_sha == EXPECTED_ELF_SHA256

    owner = sandbox.HEAP + 0x180000
    entries = sandbox.HEAP + 0x170000
    sentinel = owner + 0xF08
    link_offset = 0x48
    worlds = [harness.world, sandbox.HEAP + 0x182000, sandbox.HEAP + 0x183000]
    words = [harness.words, sandbox.HEAP + 0x184000, sandbox.HEAP + 0x185000]
    for i, (world, data) in enumerate(zip(worlds, words)):
        if i:
            memory.mem_write(world, bytes(memory.mem_read(harness.world, 0x100)))
        harness.q(world + 0x68, data)
        memory.mem_write(data, struct.pack("<I", 0x1F40) * 64)
        harness.q(owner + 0x60 + 8 * i, world)

    nodes = [entries + 0x100 * i + link_offset for i in range(3)]
    harness.q(sentinel, nodes[-1])
    harness.q(sentinel + 8, nodes[0])
    harness.d(owner + 0xF18, 3)
    harness.d(owner + 0xF1C, link_offset)

    selected_index = 1
    selected_entry = entries + 0x100 * selected_index
    for i, node in enumerate(nodes):
        entry = entries + 0x100 * i
        memory.mem_write(entry, bytes(0x80))
        sandbox.call(0x52B340, (entry + 0x20, 1, 2))
        sandbox.call(0x52B340, (entry + 0x30, 3, 4))
        memory.mem_write(entry + 0x40, bytes([1]))
        harness.d(entry + 0x44, 1 if i == selected_index else 1)
        harness.q(node, sentinel if i == 0 else nodes[i - 1])
        harness.q(node + 8, sentinel if i == 2 else nodes[i + 1])

    harness.q(image.ptr(0x32D0DE8), owner - 0x28)
    # This original wrapper calls 0x165240, which releases the list entry and
    # calls 0x181ae0 for kind 1; no function body is replaced with a stub.
    sandbox.call(0x168140, (selected_entry,), limit=100000)

    assert harness.rd(owner + 0xF18) == 2
    assert memory.mem_read(selected_entry + 0x40, 1) == b"\x00"
    assert memory.mem_read(selected_entry + link_offset, 16) == bytes(16)
    expected_nodes = [nodes[0], nodes[2]]
    actual_nodes = []
    node = harness.rq(sentinel + 8)
    previous = sentinel
    while node != sentinel:
        assert node not in actual_nodes
        assert harness.rq(node) == previous
        actual_nodes.append(node)
        previous, node = node, harness.rq(node + 8)
    assert actual_nodes == expected_nodes
    assert harness.rq(sentinel) == expected_nodes[-1]

    cell_changes = []
    for world_index, data in enumerate(words):
        for z in range(8):
            for x in range(8):
                actual = harness.rd(data + 4 * (x + 8 * z))
                expected = 0x1F00 if world_index == 0 and 1 <= x <= 3 and 2 <= z <= 4 else 0x1F40
                assert actual == expected, (world_index, x, z, hex(actual), hex(expected))
                if actual != 0x1F40:
                    cell_changes.append({"world_member_index": world_index, "x": x, "z": z, "word_after": hex(actual)})

    return {
        "source_elf_sha256": elf_sha,
        "native_functions_entered": ["0x168140", "0x165240", "0x181ae0"],
        "dependency_stubs": [],
        "synthetic_fixture": {
            "entry_kind": 1,
            "entry_enabled_low_bit": 1,
            "owner_entry_count_before_after": [3, 2],
            "list_node_count_before_after": [3, 2],
            "fixture_link_offset": hex(link_offset),
            "selected_rectangle_inclusive": [1, 2, 3, 4],
            "three_distinct_worlds": True,
            "initial_runtime_word": "0x1f40",
        },
        "observed_mutation": {
            "selected_world_member": "owner+0x60 (kind 1)",
            "word_bit_cleared": "0x40",
            "changed_cells": cell_changes,
            "all_other_cells_and_worlds_preserved": True,
            "selected_entry_enabled_byte_after": 0,
            "selected_link_bytes_after": "00000000000000000000000000000000",
        },
        "result": "PASS: original wrapper -> release -> rectangle bit mutation executed on the prepared fixture.",
        "limits": [
            "The entry/list, owner, three world records, and 0x48 link offset are constructed fixture values, not a capture of the live editor.",
            "This exercises registry release and region-flag cleanup; it does not show MakeFall/BreakFall or RiverMaker/CliffMaker invoking the cleanup path.",
            "It does not modify the 14-byte LandMaking record, generate water geometry, update mesh/collision, or serialize a save.",
        ],
    }


def main() -> None:
    manifest = json.loads((ROOT / "output/manifest.json").read_text())
    elf_path = Path(manifest["source_root"]) / "A_logic/main.elf"
    assert elf_path.resolve() == Path("/workspace/downloads/ACNH_island_RE/ACNH_island_RE/A_logic/main.elf").resolve()
    assert sha256_file(elf_path) == EXPECTED_ELF_SHA256
    assert SHARED_INDEX.stat().st_size == 63_946_752

    db = sqlite3.connect(f"file:{SHARED_INDEX}?mode=ro", uri=True)
    relevant = [0x181FA0, 0x181AE0, 0x165240, 0x168140]
    graph = {
        hex(function): {
            "name_size": db.execute(
                "SELECT ghidra_name,size FROM functions WHERE va=?", (function,)
            ).fetchone(),
            "direct_calls": direct_calls(db, function),
            "direct_callers": direct_callers(db, function),
        }
        for function in relevant
    }
    assert {int(item["caller"], 16) for item in graph["0x181fa0"]["direct_callers"]} == {0x163740, 0x164E90}
    assert {int(item["caller"], 16) for item in graph["0x181ae0"]["direct_callers"]} == {0x165240}
    assert {int(item["caller"], 16) for item in graph["0x165240"]["direct_callers"]} == {0x168140}
    assert {int(item["target"], 16) for item in graph["0x168140"]["direct_calls"]} == {0x165240}
    assert any(int(item["target"], 16) == 0x181AE0 for item in graph["0x165240"]["direct_calls"])

    downstream_release_callers = [0x156970, 0x15F4E0, 0x160940]
    release_callers = {int(item["caller"], 16) for item in graph["0x168140"]["direct_callers"]}
    assert release_callers == set(downstream_release_callers)

    action = action_slice()
    native = trace_fixture()
    pbc_metadata = json.loads(PBC_AUDIT.read_text())["archive"]
    decomp_files = [
        DECOMP / f"{va:x}.c"
        for va in (0x181FA0, 0x181AE0, 0x165240, 0x168140, 0x156970, 0x15F4E0, 0x160940)
    ]
    assert all(path.is_file() for path in decomp_files)

    inputs = {
        "elf": {"path": str(elf_path), "bytes": elf_path.stat().st_size, "sha256": sha256_file(elf_path)},
        "additional_exefs_main_nso": {
            "path": str(ROOT / "inputs/additional_exefs/main"),
            "bytes": (ROOT / "inputs/additional_exefs/main").stat().st_size,
            "sha256": sha256_file(ROOT / "inputs/additional_exefs/main"),
            "executed_by_this_harness": False,
        },
        "native_dependency_bundle": {
            "path": "/workspace/acnh-re/.deps",
            "note": "Read-only shared Python dependencies used by Unicorn/Capstone/pyelftools imports.",
        },
        "shared_sqlite_index": {
            "path": str(SHARED_INDEX),
            "bytes": SHARED_INDEX.stat().st_size,
            "sha256": sha256_file(SHARED_INDEX),
            "note": "This is the valid shared index; the delivery-checkout copy is empty and is not opened.",
        },
        "action_parameter_bcsv": action["source"],
        "action_parameter_decompilation": [
            {"path": str(path), "sha256": sha256_file(path)} for path in decomp_files
        ],
        "pbc_audit_metadata": {
            "path": str(PBC_AUDIT),
            "sha256": sha256_file(PBC_AUDIT),
            "historically_referenced_archive": pbc_metadata,
        },
    }

    result = {
        "scope": "One native region-release-to-flag-mutation fixture plus a static boundary between the FieldLandMakingActionParam waterfall rows and the cleanup path.",
        "action_table": action,
        "native_direct_call_graph": graph,
        "blocker": {
            "validation": "0x181fa0 is reached directly through 0x163740/0x164e90 forwarders.",
            "mutation": "0x181ae0 is called directly by 0x165240; 0x165240 is called directly by wrapper 0x168140.",
            "release_wrapper_callers": [hex(caller) for caller in downstream_release_callers],
            "finding": "The supplied direct-call index binds validation and release mutation to separate paths. No direct edge connects the MakeFall/BreakFall table rows or 0x181fa0 validation to 0x165240/0x181ae0. Indirect dispatch may exist, so this is a bounded missing-link result, not proof that no live path exists.",
            "action_path_closed": False,
        },
        "native_release_fixture": native,
        "inputs": inputs,
        "stubbed_dependencies": {
            "native_function_stubs": [],
            "fixture_state": "Owner/list entries, enabled byte, rectangle, singleton world reference and three world records are synthetic. The original code and helper callees execute from the checksum-verified ELF.",
        },
        "reproduction": {
            "script": str(Path(__file__).resolve()),
            "script_sha256": sha256_file(Path(__file__).resolve()),
            "shared_index_path_used": str(SHARED_INDEX),
            "checks": [
                "ELF path and SHA256 match the repository manifest and expected 1.0.0 source.",
                "SQLite size and call graph match the shared index, not the zero-byte delivery copy.",
                "Raw ActionParam BCSV hash matches its resolved table source hash; waterfall rows are MakeFall/FallToRiver=0 and BreakFall/FallToRiver=1.",
                "Original 0x168140 -> 0x165240 -> 0x181ae0 chain clears only the selected inclusive rectangle's bit6 and releases exactly one prepared list entry.",
            ],
            "status": "PASS: bounded native mutation reproduced; live terraform/action/save and water rendering remain open.",
        },
    }

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "action_table_slice.json").write_text(json.dumps(action, indent=2, ensure_ascii=False) + "\n")
    (OUT / "native_region_release_trace.json").write_text(json.dumps(native, indent=2, ensure_ascii=False) + "\n")
    (OUT / "result.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({
        "outputs": [str(OUT / name) for name in ("action_table_slice.json", "native_region_release_trace.json", "result.json")],
        "action_rows": len(action["fall_action_rows"]),
        "native_functions_executed": native["native_functions_entered"],
        "changed_cells": len(native["observed_mutation"]["changed_cells"]),
        "direct_action_link": "UNPROVEN",
    }, indent=2))


if __name__ == "__main__":
    main()
