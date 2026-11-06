#!/usr/bin/env python3
"""Bounded evidence builder for the island outer-generator path.

Reads the indexed main.elf, index.sqlite, the partial additional RomFS and
existing committed island summaries. Writes only into this new artifact folder.
"""
from collections import Counter
import hashlib
import json
from pathlib import Path
import sqlite3
import struct
import sys

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "output/ui_island/island_loader_followup"
ROMFS = Path("/workspace/downloads/acnh_additional_romfs_2026-11-02/romfs")
INDEX = Path("/workspace/acnh-re/output/index.sqlite")

# The managed dependency bundle is read-only and is already used by the source
# checkout's native harnesses. No packages are installed by this script.
for candidate in (Path("/workspace/acnh-re/.deps"), ROOT / ".deps"):
    if candidate.is_dir():
        sys.path.insert(0, str(candidate))
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tools/reference"))

from native_emulator import Sandbox  # noqa: E402
from native_image import Image  # noqa: E402


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def read_indexed_bcsv(raw, table_name, con):
    """Decode selected primitive fields using the read-only SQLite schema."""
    row_count, row_size, field_count = struct.unpack_from("<IIH", raw, 0)
    header = 0x1C if raw[0xA] else 0x0C
    if raw[0xA]:
        assert raw[0xC:0x10] == b"VSCB"
    data_start = header + field_count * 8
    descriptors = [
        struct.unpack_from("<II", raw, header + index * 8)
        for index in range(field_count)
    ]
    descriptors.sort(key=lambda item: item[1])
    schema_rows = con.execute(
        "SELECT hash,name,type,offset,width FROM columns_resolved WHERE table_name=?",
        (table_name,),
    ).fetchall()
    schema = {int(row[0]): {"name": row[1], "type": row[2], "offset": row[3], "width": row[4]} for row in schema_rows}
    columns = []
    for index, (field_hash, offset) in enumerate(descriptors):
        width = (descriptors[index + 1][1] if index + 1 < len(descriptors) else row_size) - offset
        resolved = schema.get(field_hash)
        if resolved:
            assert resolved["offset"] == offset, (table_name, resolved, offset)
            assert resolved["width"] == width, (table_name, resolved, width)
        columns.append({"hash": field_hash, "offset": offset, "width": width, **(resolved or {"name": f"h_{field_hash:08x}", "type": "bytes"})})
    assert data_start + row_count * row_size == len(raw), (table_name, data_start, row_count, row_size, len(raw))
    rows = []
    for index in range(row_count):
        start = data_start + index * row_size
        row_data = raw[start:start + row_size]
        assert struct.unpack_from("<I", row_data, 0)[0] == start, (table_name, index)
        row = {}
        for column in columns:
            offset, width, typ = column["offset"], column["width"], column["type"]
            if typ.startswith("string"):
                value = row_data[offset:offset + width].split(b"\0", 1)[0].decode("utf-8")
            elif typ == "u8":
                value = struct.unpack_from("<B", row_data, offset)[0]
            elif typ == "u16":
                value = struct.unpack_from("<H", row_data, offset)[0]
            elif typ == "u32":
                value = struct.unpack_from("<I", row_data, offset)[0]
            else:
                value = None
            row[column["name"]] = value
        rows.append(row)
    return {"rows": rows, "columns": columns, "row_size": row_size, "data_start": data_start}


def native_rng_check():
    sandbox = Sandbox()
    state_ptr = sandbox.HEAP + 0x18000
    seed = 0x4D41504A
    sandbox.call(0x19AA040, [state_ptr, seed])
    state = list(struct.unpack("<4I", bytes(sandbox.uc.mem_read(state_ptr, 16))))
    value = seed
    expected = []
    for increment in range(1, 5):
        value = ((value ^ (value >> 30)) * 0x6C078965 + increment) & 0xFFFFFFFF
        expected.append(value)
    assert state == expected, (state, expected)

    draws = []
    for _ in range(8):
        a, b, c, d = state
        t = (a ^ (a << 11)) & 0xFFFFFFFF
        draw = (t ^ (t >> 8) ^ d ^ (d >> 19)) & 0xFFFFFFFF
        state = [b, c, d, draw]
        native = sandbox.call(0x19AA0E0, [state_ptr]) & 0xFFFFFFFF
        after = list(struct.unpack("<4I", bytes(sandbox.uc.mem_read(state_ptr, 16))))
        assert native == draw, (native, draw)
        assert after == state, (after, state)
        draws.append({"u32": native, "state_after": state})
    return {
        "seed": hex(seed),
        "native_functions": ["0x19aa040", "0x19aa0e0"],
        "draws_checked": len(draws),
        "draws": draws,
        "mismatches": 0,
        "scope": "Original seed expansion and xorshift instructions ran natively on a deterministic seed. This does not execute 0x529910's GetSystemTick-seeded constructor or its caller draw order.",
    }


def elf_direct_calls(image, va, size):
    calls = []
    for instruction in image.disasm(va, size):
        if instruction.mnemonic == "bl" and instruction.op_str.startswith("#0x"):
            calls.append({"pc": hex(instruction.address), "target": hex(int(instruction.op_str[1:], 16))})
    return calls


def main():
    assert ROMFS.is_dir(), ROMFS
    assert INDEX.is_file(), INDEX
    image = Image()
    elf_sha = sha256(image.data)
    assert elf_sha == "5bf707c3dc5dac0ad9635af7d336ec580f81c3f7876d0f55400d1900e3415d74", elf_sha

    main_table_path = ROMFS / "Bcsv/FieldMainFieldParam.bcsv"
    outside_table_path = ROMFS / "Bcsv/FieldOutsideTemplate.bcsv"
    unit_table_path = ROMFS / "Bcsv/FieldLandMakingUnitModelParam.bcsv"
    main_table_raw = main_table_path.read_bytes()
    outside_table_raw = outside_table_path.read_bytes()
    unit_table_raw = unit_table_path.read_bytes()
    con = sqlite3.connect(f"file:{INDEX}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    main_table = read_indexed_bcsv(main_table_raw, "FieldMainFieldParam", con)
    outside_table = read_indexed_bcsv(outside_table_raw, "FieldOutsideTemplate", con)
    unit_table = read_indexed_bcsv(unit_table_raw, "FieldLandMakingUnitModelParam", con)

    assert len(main_table["rows"]) == 96
    assert len(outside_table["rows"]) == 36
    assert len(unit_table["rows"]) == 246
    main_columns = {column["name"]: column for column in main_table["columns"]}
    outside_columns = {column["name"]: column for column in outside_table["columns"]}
    unit_columns = {column["name"]: column for column in unit_table["columns"]}
    assert {"UniqueID", "OutsideTemplateKind", "FieldData"} <= main_columns.keys()
    assert {"UniqueID", "TemplateKind"} <= outside_columns.keys()
    assert {"UniqueID", "Variation", "ModelName"} <= unit_columns.keys()
    preset_ids = [row["UniqueID"] for row in main_table["rows"]]
    assert len(set(preset_ids)) == len(preset_ids) == 96
    category_counts = Counter(row["OutsideTemplateKind"] for row in main_table["rows"])
    assert set(category_counts) == {0, 1, 2}
    assert sorted(category_counts.values()) == [30, 33, 33]

    preset_paths = sorted((ROMFS / "Param/Field/MainFieldPreset").glob("FieldPreset*_LandMaking.byml"))
    assert len(preset_paths) == 96, len(preset_paths)
    loader = json.loads((ROOT / "output/ui_island/island_terrain_loader_native.json").read_text())
    assert loader["preset_collection"]["count"] == 96
    assert loader["preset_collection"]["source_record_size_bytes"] == 14
    assert loader["native_transfer"]["grid_iteration"]["width"] == 112
    assert loader["native_transfer"]["grid_iteration"]["height"] == 96
    transfer_offsets = [field["offset"] for field in loader["native_transfer"]["destination_cell_writes"]]
    assert transfer_offsets == [0, 2, 4, 6, 8, 10, 12]

    function_rows = {}
    direct_calls = {}
    binary_calls = {}
    for va in (0x529910, 0x528BF0, 0x558F40, 0x54E330, 0x552BB0):
        row = con.execute("SELECT va,size,ghidra_name FROM functions WHERE va=?", (va,)).fetchone()
        assert row is not None, hex(va)
        function_rows[hex(va)] = {"size_bytes": row["size"], "name": row["ghidra_name"]}
        calls = con.execute(
            "SELECT pc,target_va FROM direct_calls WHERE owner_va=? ORDER BY pc", (va,)
        ).fetchall()
        direct_calls[hex(va)] = [
            {"pc": hex(call["pc"]), "target": hex(call["target_va"])} for call in calls
        ]
        binary_calls[hex(va)] = elf_direct_calls(image, va, row["size"])
        assert binary_calls[hex(va)] == direct_calls[hex(va)], hex(va)
    generator_bl = [call["target"] for call in direct_calls["0x529910"]]
    assert generator_bl.count("0x552bb0") == 4
    assert generator_bl.count("0x528bf0") == 4
    assert any(call["target"] == "0x558f40" for call in direct_calls["0x528bf0"])
    core_calls = {
        "0x529910": [call for call in direct_calls["0x529910"] if call["target"] in {"0x552bb0", "0x528bf0"}],
        "0x528bf0": [call for call in direct_calls["0x528bf0"] if call["target"] == "0x558f40"],
    }

    pbc_named_files = [
        path.relative_to(ROMFS).as_posix()
        for path in ROMFS.rglob("*")
        if path.is_file() and "pbc" in path.name.lower()
    ]
    indexed_pbc = con.execute(
        "SELECT COUNT(*) FROM files WHERE lower(source) LIKE '%pbc%'"
    ).fetchone()[0]
    assert not pbc_named_files
    assert indexed_pbc == 0
    con.close()

    pbc_consumers = json.loads((ROOT / "output/mechanics/terrain_pbc_native_consumers.json").read_text())
    terrain = json.loads((ROOT / "output/mechanics/terrain_native.json").read_text())
    pbc_layout = pbc_consumers["pbc_record_serialization"]
    assert pbc_layout["record_stride_bytes"] == 52
    assert pbc_layout["height_float32_byte_range_exclusive"] == [0, 48]
    assert pbc_layout["material_byte_range_exclusive"] == [48, 52]
    assert terrain["grid_contract"]["record_stride"] == 52
    assert loader["source_record_layout"][-1]["field"] == "padding"

    rng = native_rng_check()
    result = {
        "scope": "One bounded outer-generator path audit plus deterministic execution of the native integer RNG helpers. The four-slot 0x529910 body and 0x528bf0 setup are not invoked in this iteration.",
        "evidence_labels": {
            "NATIVE": "ELF instructions, call sites, and bounded original-instruction harness results.",
            "PSEUDO": "Control-flow interpretation derived from the native instruction sequence/decompilation.",
            "TBL": "Raw BCSV/BYML data read from the supplied additional RomFS and cross-checked with committed summaries.",
            "EF": "Inference or limitation requiring unavailable PBC payloads or unexecuted runtime resource state.",
        },
        "sources": {
            "elf_sha256": elf_sha,
            "index_sqlite": str(INDEX),
            "additional_romfs": str(ROMFS),
            "raw_tables": {
                "FieldMainFieldParam": {"sha256": sha256(main_table_raw), "rows": len(main_table["rows"])},
                "FieldOutsideTemplate": {"sha256": sha256(outside_table_raw), "rows": len(outside_table["rows"])},
                "FieldLandMakingUnitModelParam": {"sha256": sha256(unit_table_raw), "rows": len(unit_table["rows"])},
            },
        },
        "generator_path": {
            "label": "[NATIVE] call graph / [PSEUDO] execution order",
            "function_sizes_from_index": function_rows,
            "callsites": core_calls,
            "direct_call_counts": {
                "0x529910": {"0x552bb0": 4, "0x528bf0": 4},
                "0x528bf0": {"0x558f40": sum(call["target"] == "0x558f40" for call in direct_calls["0x528bf0"])},
            },
            "ELF_vs_index_calls_match": True,
            "per_slot_flow": [
                "0x529910 builds a row-eligibility bitset from FieldMainFieldParam.",
                "The original xorshift draw is multiplied by the eligible count; 0x52a110 returns the ranked source row, then its bit is removed.",
                "0x54e190 binds the source row and 0x54e330 reads OutsideTemplateKind.",
                "0x552bb0 selects a FieldOutsideTemplate UniqueID for that category using the shared RNG state.",
                "0x529910 constructs a 0xe0-byte setup parameter with the source-row UID, selected template UID and slot index, then calls 0x528bf0.",
                "0x528bf0 calls 0x558f40 only when the template resource and destination grid are non-null.",
            ],
            "slot_invariants": {
                "generator_selector_calls": 4,
                "generator_setup_calls": 4,
                "unique_source_rows": True,
                "raw_table_category_counts": {str(key): category_counts[key] for key in sorted(category_counts)},
                "source_preset_uid_range": [min(preset_ids), max(preset_ids)],
                "template_rows": len(outside_table["rows"]),
                "landmaking_unit_rows": len(unit_table["rows"]),
            },
            "native_execution_status": "[NATIVE] The standalone RNG seed-expansion and eight draw steps pass. [PSEUDO] The parent generator sequence is documented from code and its four call sites; this iteration does not invoke 0x529910 or 0x528bf0.",
            "rng": rng,
        },
        "preset_to_runtime": {
            "label": "[NATIVE] field transfer / [EF] PBC and transform join",
            "source_record": {"stride_bytes": 14, "fields": loader["source_record_layout"]},
            "preset_collection": {
                "count": len(preset_paths),
                "grid": [112, 96],
                "all_grid_cells": len(preset_paths) * 112 * 96,
            },
            "native_transfer": loader["native_transfer"],
            "runtime_ground_record": {
                "stride_bytes": pbc_layout["record_stride_bytes"],
                "height_bytes": pbc_layout["height_float32_byte_range_exclusive"],
                "material_bytes": pbc_layout["material_byte_range_exclusive"],
                "grid_index": terrain["grid_contract"]["index"],
            },
            "join_status": "[EF] 0x558f40 transfers the 14-byte preset schema into destination LandMaking cell fields; it does not expand the cell into the separate 52-byte ground/PBC record. ModelName + '_pbc' resource naming is statically cataloged, but payload values are absent from both this partial RomFS and the indexed source corpus.",
            "transform_status": "[EF] The 2x2 PBC-per-unit and 5.0-unit PBC cell model is carried by earlier audit metadata; the exact 14-byte cell to PBC subcell rotation/origin/height transform and runtime cache bootstrap are not proven by this loader.",
            "variation_cache_rule": loader["native_transfer"]["variation_rule"],
            "height_rule": loader["native_transfer"]["height_rule"],
            "missing_assets": {
                "pbc_named_files_in_additional_romfs": pbc_named_files,
                "pbc_named_files_in_index_sqlite": indexed_pbc,
                "blocker": "The user-supplied additional RomFS is partial and contains no PBC-named payloads; exact 52-byte record join and per-cell transform cannot be validated from missing asset bytes.",
            },
        },
        "verification": {
            "assertions_passed": [
                "Raw additional BCSV row counts: FieldMainFieldParam=96, FieldOutsideTemplate=36, FieldLandMakingUnitModelParam=246.",
                "FieldMainFieldParam contains 96 unique preset UIDs and category counts 30/33/33 for OutsideTemplateKind 0..2.",
                "The additional RomFS contains 96 LandMaking preset BYML files.",
                "Disassembled ELF direct BL targets match the index.sqlite call graph; 0x529910 has exactly four 0x552bb0 and four 0x528bf0 calls, and 0x528bf0 directly references 0x558f40.",
                "The 14-byte destination field offsets are [0,2,4,6,8,10,12], and the separate runtime/PBC record stride is 52 bytes.",
                "No PBC-named file is present in the additional RomFS or index.sqlite.",
                "Original native RNG seed expansion and eight deterministic u32 draws match independent arithmetic with unchanged state transitions.",
            ],
            "mismatches": 0,
        },
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "result.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"output": str(OUT / "result.json"), "elf_sha256": elf_sha, "rng_draws": len(rng["draws"]), "assertions": len(result["verification"]["assertions_passed"]), "pbc_files": len(pbc_named_files)}, indent=2))


if __name__ == "__main__":
    main()
