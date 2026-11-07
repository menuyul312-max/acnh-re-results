#!/usr/bin/env python3
"""Replay the bounded island-loader audit and inventory currently available inputs."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import zipfile


OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
WORKSPACE = Path("/workspace")
BASELINE_SCRIPT = ROOT / "output/ui_island/island_loader_followup/reproduce.py"
ROMFS = Path("/workspace/downloads/acnh_additional_romfs_2026-11-02/romfs")
INDEX = Path("/workspace/acnh-re/output/index.sqlite")
ISLAND_ZIP = WORKSPACE / "downloads/ACNH_island_RE.zip"
ADDITIONAL_ROMFS_ZIP = WORKSPACE / "acnh-re-additional-romfs.zip"
ADDITIONAL_ROMFS_PARTS = sorted(
    (WORKSPACE / "acnh-re-delivery/additional_romfs").glob("*.zip")
)
SOURCE_ELF = WORKSPACE / "downloads/ACNH_island_RE/ACNH_island_RE/A_logic/main.elf"
ADDITIONAL_EXEFS_MAIN = ROOT / "inputs/additional_exefs/main"
PBC_AUDIT = ROOT / "output/ui_island/manifests_pbc_audit.json"
PRESET_DIR = ROMFS / "Param/Field/MainFieldPreset"


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def pbc_named(path: str) -> bool:
    return "pbc" in path.lower()


def archive_inventory(path: Path) -> dict:
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        matches = [name for name in names if pbc_named(name)]
    return {
        "path": str(path),
        "size_bytes": path.stat().st_size,
        "sha256": sha256_path(path),
        "zip_members": len(names),
        "pbc_named_members": matches,
    }


def current_inputs() -> dict:
    manifest = json.loads((ROOT / "output/manifest.json").read_text())
    manifest_elf = Path(manifest["source_root"]) / "A_logic/main.elf"
    assert manifest_elf.resolve() == SOURCE_ELF.resolve(), (manifest_elf, SOURCE_ELF)
    assert sha256_path(SOURCE_ELF) == "5bf707c3dc5dac0ad9635af7d336ec580f81c3f7876d0f55400d1900e3415d74"

    tables = {}
    for table_name in (
        "FieldMainFieldParam.bcsv",
        "FieldOutsideTemplate.bcsv",
        "FieldLandMakingUnitModelParam.bcsv",
    ):
        path = ROMFS / "Bcsv" / table_name
        tables[table_name] = {
            "path": str(path),
            "size_bytes": path.stat().st_size,
            "sha256": sha256_path(path),
        }

    preset_paths = sorted(PRESET_DIR.glob("FieldPreset*_LandMaking.byml"))
    assert len(preset_paths) == 96, len(preset_paths)
    presets = [
        {
            "path": str(path),
            "size_bytes": path.stat().st_size,
            "sha256": sha256_path(path),
        }
        for path in preset_paths
    ]

    artifact_paths = [
        ROOT / "output/manifest.json",
        ROOT / "docs/ISLAND_LOADER_FOLLOWUP.md",
        ROOT / "docs/ISLAND_TEMPLATE_SELECTOR_NATIVE.md",
        ROOT / "output/ui_island/island_loader_followup/reproduce.py",
        ROOT / "output/ui_island/island_loader_followup/result.json",
        ROOT / "output/ui_island/island_terrain_loader_native.json",
        ROOT / "output/mechanics/terrain_native.json",
        ROOT / "output/mechanics/terrain_pbc_native_consumers.json",
        ROOT / "output/ui_island/manifests_pbc_audit.json",
    ]

    archive_paths = [ISLAND_ZIP, ADDITIONAL_ROMFS_ZIP, *ADDITIONAL_ROMFS_PARTS]
    archives = [archive_inventory(path) for path in archive_paths if path.is_file()]
    extraction_hits = sorted(
        str(path.relative_to(WORKSPACE / "downloads/ACNH_island_RE"))
        for path in (WORKSPACE / "downloads/ACNH_island_RE").rglob("*")
        if path.is_file() and pbc_named(str(path.relative_to(WORKSPACE / "downloads/ACNH_island_RE")))
    )
    romfs_hits = sorted(
        str(path.relative_to(ROMFS))
        for path in ROMFS.rglob("*")
        if path.is_file() and pbc_named(path.name)
    )

    pbc_audit = json.loads(PBC_AUDIT.read_text())
    historical_pbc_archive = pbc_audit["archive"]
    same_hash_local_archives = [
        archive["path"] for archive in archives
        if archive["sha256"] == historical_pbc_archive["sha256"]
    ]
    referenced_archive_names = sorted(
        path.name for path in WORKSPACE.rglob(historical_pbc_archive["filename"])
        if path.is_file()
    )

    assert not extraction_hits, extraction_hits
    assert not romfs_hits, romfs_hits
    assert all(not archive["pbc_named_members"] for archive in archives), archives
    assert not same_hash_local_archives, same_hash_local_archives
    assert not referenced_archive_names, referenced_archive_names

    return {
        "source_elf": {
            "path": str(SOURCE_ELF),
            "size_bytes": SOURCE_ELF.stat().st_size,
            "sha256": sha256_path(SOURCE_ELF),
        },
        "additional_exefs_main_nso": {
            "path": str(ADDITIONAL_EXEFS_MAIN),
            "size_bytes": ADDITIONAL_EXEFS_MAIN.stat().st_size,
            "sha256": sha256_path(ADDITIONAL_EXEFS_MAIN),
            "note": "This is the separate raw ExeFS main input. The replay harness reads A_logic/main.elf above.",
        },
        "indexed_source": {
            "index_sqlite": {
                "path": str(INDEX),
                "size_bytes": INDEX.stat().st_size,
                "sha256": sha256_path(INDEX),
            },
            "raw_bcsv": tables,
            "raw_landmaking_presets_byml": presets,
            "raw_bcsv_directory": str(ROMFS),
        },
        "prior_docs_and_analysis_artifacts": [
            {"path": str(path), "sha256": sha256_path(path)}
            for path in artifact_paths
        ],
        "available_archives": archives,
        "extracted_additional_romfs_pbc_named_files": romfs_hits,
        "extracted_island_source_pbc_named_files": extraction_hits,
        "historical_pbc_audit_reference": {
            "filename": historical_pbc_archive["filename"],
            "size_bytes": historical_pbc_archive["size_bytes"],
            "sha256": historical_pbc_archive["sha256"],
            "reported_pbc_payloads": historical_pbc_archive["collision_manifest_pbc_count"],
            "matching_files_by_name_in_workspace": referenced_archive_names,
            "matching_archive_hashes_among_current_sources": same_hash_local_archives,
            "boundary": "The archive filename is absent from /workspace, and its recorded checksum matches none of the current primary or split island/RomFS source archives inventoried here; the PBC payload bytes cannot be replayed from these inputs.",
        },
    }


def main() -> None:
    spec = importlib.util.spec_from_file_location("island_loader_followup_reproduce", BASELINE_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load prior bounded replay: {BASELINE_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    module.OUT = OUT
    module.main()

    result_path = OUT / "result.json"
    result = json.loads(result_path.read_text())
    result["remainder_20261107"] = {
        "scope": "Replay of the existing bounded loader audit plus an inventory of the exact inputs currently available in this workspace. This does not add execution of 0x529910 or 0x528bf0.",
        "prior_reproducer": {
            "path": str(BASELINE_SCRIPT),
            "sha256": sha256_path(BASELINE_SCRIPT),
            "previous_result_path": str(BASELINE_SCRIPT.parent / "result.json"),
            "previous_result_sha256": sha256_path(BASELINE_SCRIPT.parent / "result.json"),
        },
        "current_reproducer": {
            "path": str(Path(__file__).resolve()),
            "sha256": sha256_path(Path(__file__).resolve()),
        },
        "current_inputs": current_inputs(),
        "stubbed_dependencies": {
            "native_rng_leafs": [],
            "explanation": "0x19aa040 and 0x19aa0e0 execute original ELF instructions in the bounded Sandbox. The Sandbox supplies synthetic seed/state memory, stack, heap, and a return sentinel; it does not stub calls inside either RNG leaf. No system tick, registry/cache bootstrap, resource manager, or world object is supplied because the parent generator/setup functions are not executed.",
        },
        "checks": {
            "replayed_assertion_count": len(result["verification"]["assertions_passed"]),
            "current_relevant_archives_have_zero_pbc_named_members": True,
            "historical_manifest_archive_name_absent_and_hash_matches_no_current_source_archive": True,
            "status": "PASS: bounded checks replay; full generator-to-world gate remains open.",
        },
    }
    result_path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    inventory_path = OUT / "source_inventory.json"
    inventory_path.write_text(json.dumps(result["remainder_20261107"]["current_inputs"], indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({
        "result": str(result_path),
        "source_inventory": str(inventory_path),
        "replayed_assertions": len(result["verification"]["assertions_passed"]),
        "pbc_payload_gate": "OPEN",
    }, indent=2))


if __name__ == "__main__":
    main()
