# Resident Services through Island Designer: story and asset crosswalk

**Date:** 2026-11-07
**Scope:** ACNH 1.0.0 office completion/Isabelle, campsite and first camper, island evaluation, first K.K. live and credits boundary, then Island Designer unlock. The machine-readable part is [office_kk.json](../output/gameplay/story_asset_parts/office_kk.json).

## What the sources establish

EventFlow provides a usable progression spine. The office completion path records `BuiltTownOffice` and announcement checks; the office introduction entries turn on `IslandDevQuestRunning` and have Isabelle cast as `sza`. The decoded ceremony graph requests `cMainFieldCeremonyOffice`. A disassembly summary says the day-change office processor checks structure kind 1 and sets `BuiltTownOffice`, `BuiltTownOfficeToday`, `GlobalEventReady` and `EventPlazaBuilt`; that is PSEUDO evidence, not a native fixture execution.

Tom Nook's campsite request (`SNPC_rco_54_IslandDevelopment:CampSiteRequest`) unlocks the campsite recipe and sets the ongoing flag. The day-change campsite processor summary (`0xf26330`) checks structure kind 6 and sets `CampSiteBuilt`, `CampSiteBuiltToday` and `CeremonyBuildCampSite`. EventFlow requests `cMainFieldCeremonyCampSite`. The first-camper day-change entry, personality-specific `NNPC_Spot_Camp:Flow_FirstCamper*`, and Tom Nook's `SetFirstCamperHouseRequest` trace the visitor and a `SetItemToPocket` grant of item 3349. The flow index shows eight personality variants, so there is no evidence here for one fixed camper species/model.

`Root3IslandEvaluation` leads to `IslandEvaluationRunning`, which writes `IslandEvaluationUnlock`. Isabelle's evaluation graph calls `System_IslandEvaluationCheck:IslandEvaluationChk`. The score companion reconstructs the nature/life thresholds and penalties from disassembly, including the score member and native helper addresses, but does not execute the full score aggregator through save state and unlock. Accordingly, this crosswalk treats the score calculations as PSEUDO and leaves the end-to-end score-to-rating UI and placement-input joins open.

For K.K., the qualifying Isabelle path checks the island-development completion state, the rating result and the representative-player flag, then calls `ClearTkkFirstLiveScore`. A later native day-change path enables `TkkFirstLiveEnable`, but one second flag condition is unresolved in the decompilation. Public-announcement EventFlow reserves the first live, has Isabelle announce it, and requests `cMainFieldFirstLive`. `SNPC_tkk_Live` contains the contextual song request, camera key, live enter/exit actions, and post-performance first-live flags. Afterward, `SNPC_rco_55_TkkFirstLive:InvitePlayerHouse` grants song 4318, sets `MainmenuConstructLicense`, and requests the `cConstructLicense` app UI.

## Asset and placement boundary

The model catalog contains `StrcOfficeA01` (labelled Resident Services Town Hall), plus campsite candidates `StrcCampsiteTentA00` and `StrcCampsiteA00`. They remain `CAT`: no structure-table row, stage loader or runtime binding has been joined to those catalog IDs. The audio catalog contains 98 K.K. live entries, but the EventFlow's context-based song request does not identify which recording is used for the first performance. The `StaffCredit` layout and `StaffCredit_CorporationIn.bflan` exist in the UI catalog, while the indexed flow trees contain no `StaffCredit` or `STR_StaffList` invocation. The credits trigger and its timing relative to the first concert remain open.

The two ceremony stage transitions and the first-live stage transition are backed by EventFlow stage names. Those names do not supply a world-space anchor. Office/campsite coordinates, plot/kit transforms, spawn points, performer/chair/player-camera anchors, object layouts, and collision/render consumers all remain open. The part JSON records each asset family separately; every unresolved family has an explicit OPEN placeholder. Catalog-only candidates are clearly labeled and are not described as converted or runtime-verified.

## Evidence and reproduction

The crosswalk cites decoded sources in each record. The main references are:

- `acnh-re/docs/GAMEPLAY_FLOW.md` §§8–10 for the office, campsite, score thresholds, K.K. gate and post-live app unlock.
- `acnh-re/output/gameplay/flow_index.json` and `acnh-re/output/gameplay/trees/` for flow entries, flag writes, messages and stage requests. The K.K. stage transition is in `trees/Demo_PublicAnnouncement.txt`; ceremony stage calls are in `trees/SNPC_rco_05_ChkCeremony.txt`.
- `acnh-re/output/gameplay/native_flag_refs.json` for PSEUDO office/campsite and day-change gate summaries.
- `acnh-re/docs/ISLAND_SCORE_REMAINDER_20261107.md` for the native score classifier/aggregator boundary.
- `/workspace/acnh-re/output/additional_romfs/catalogues/{model,audio}.json` for catalog-only candidates. The zero-byte repo-local `acnh-re/output/index.sqlite` was not used.
- `acnh-re/output/ui_hud/screen_catalog.json` and related page catalogs for the StaffCredit page/animation presence, without a story invocation join.

Validate the part against the current schema with:

```sh
python -m jsonschema -i acnh-re/output/gameplay/story_asset_parts/office_kk.json acnh-re/output/gameplay/story_asset_crosswalk.schema.json
```

This checks record shape and required per-family placeholders. It does not prove resource selection, native runtime behavior, conversion fidelity, or world placement. No executable/gameplay test was run for this static crosswalk.
