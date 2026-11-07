# External ACNH reverse-engineering reference audit

**Date:** 2026-11-07  
**Purpose:** Check whether public GitHub projects add missing source material or provide independent cross-checks for registration, island presets, story flags, and placement. This is a reference audit; the external repositories are not treated as the source of the local ACNH 1.0.0 evidence.

## Findings

| Public source | What it provides | How it applies here | Limit |
|---|---|---|---|
| [ACNHRecomp README, commit `6adabcb`](https://github.com/Nycolazs/ACNHRecomp/blob/6adabcb5cf30f8a7b3dfa8988159a5faa361442e/README.md) | Describes static recompilation and explicitly says no game code, assets, keys, or firmware are included; users prepare their own game files. | Useful implementation/reference project, but it cannot supply the absent ROMFS model/audio/layout payloads. | It is not an asset dump. No placement or terrain consumer result was found in the code search performed for this audit. |
| [NookKit page catalog, commit `a60e27d`](https://github.com/acnhmodding/nookkit/blob/a60e27dd1c0bb7e92393acc97200c531120a74d6/data/pages-3.0.3.tsv) | Maps `MapSelectPage` to `CharaMakeMap`. | Independently corroborates the local static page/layout name join. | It does not map the four card instances to `FieldMainFieldParam`, `cVillage`, or a LandMaking preset. |
| [Treeki/CylindricalEarth `specs_100.py`, commit `bb09c0e`](https://github.com/Treeki/CylindricalEarth/blob/bb09c0ee71a4aa6011de088b88ea55fdee0bf6e9/specs_100.py) | Declares the `FieldMainFieldParam` row schema and field hashes for ACNH 1.0.0. | Independent table-schema cross-check. | A schema does not establish the native consumer, island card selection, coordinate transform, or placement collider. |
| [ACNH_Resources `FieldMainFieldParam.csv`, commit `a84c243`](https://github.com/969981/ACNH_Resources/blob/a84c243fdb4361d462e439a43c64155de5ee1a04/UnPack/1/Bcsv/FieldMainFieldParam.csv) and [acnh-csv copy, commit `129e7ac`](https://github.com/McSpazzy/acnh-csv/blob/129e7acab3536be56ac6edbc37575316da918ccd/FieldMainFieldParam.csv) | Both indexed results show row `UniqueID=0` selecting `FieldPresetA00`, `VillagePresetA00`, and `StructurePresetA00`. | Cross-checks the same table row already decoded and hashed in the local source. | GitHub code search returned no indexed exact hit for `mSiteList` or `FieldPresetA00_LandMaking` in the searched resource repository. This is a search limit, not proof that no copy exists elsewhere. |
| [NHSE `EventFlagLand.cs`, commit `cb07454`](https://github.com/kwsch/NHSE/blob/cb0745415945776f73375bf0a434a8babf059307/NHSE.Core/Structures/Records/EventFlagLand.cs) | Contains the `TkkFirstLiveEnable` flag record. | Independent name/flag-index cross-check for the local static disassembly. | The local AArch64 bytes remain the proof for the gate conditions and writes. |

The GitHub code search found no additional indexed source for the specific `BuildingSiteIndex`→site-list consumer or `MapSelectPage`→preset selector. Search results are scoped to indexed public source and do not prove global absence. The `ACNHRecomp` README is explicit that it does not distribute the required game files, so it does not resolve the missing same-build asset payloads.

## Evidence policy

These links corroborate names, schemas, and table rows only. The local manifest, EventFlow sources, binary hashes, parsed layouts, and static/native evidence remain the basis for the current mappings. No external game asset or dump was copied into this repository. Raw model/audio, UI runtime consumers, island-card-to-preset selection, structure transforms, world/collider population, and end-to-end save traces remain open in the linked local proof ledgers.
