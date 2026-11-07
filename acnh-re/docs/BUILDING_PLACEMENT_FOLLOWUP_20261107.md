# Building placement transform-chain follow-up

**Date:** 2026-11-07  
**Scope:** ACNH 1.0.0 reverse-engineering only. This follow-up focuses on the site-selection and transform gap for the player tent, first bridge, and the three settler plots. It traces EventFlow inputs, the generic preview/build flow, `StructurePresetA00.mSiteList`, and the available native static-analysis path. No Godot scene, build, or game execution was performed. Record-level evidence and hashes are in [building_placement_followup_20261107.json](../output/gameplay/building_placement_followup_20261107.json).

## Result

Native analysis now joins the registered `BuildStructure` method to a six-entry list-selection path: it selects an available index, writes it to the actor's `BuildingSiteIndex` AI blackboard key, parses the selected pair, and passes it into actor-context handling. `FieldMainFieldParam` row `UniqueID=0` selects `StructurePresetA00`; the source list has six cells and a six-child loader. The specific runtime preset instance and assignments of those indices to the player tent, bridge, or plot A/B/C remain open, as do world-position conversion, rotation, footprint, model instance, save record, and collider. See [the blackboard and selected-site native follow-up](BUILDING_SITE_INDEX_BLACKBOARD_NATIVE_FOLLOWUP_20261107.md).

An earlier pass treated the actor key as unresolved because pseudocode display address `UNK_02a80082` was searched without removing the `+0x100000` display bias. Direct byte inspection now resolves ELF VA `0x2980082` to `BuildingSiteIndex`; the BuildStructure candidate uses the same actor blackboard storage shape and writes its selected list index there. The function calls ELF VA `0x4e1d80` (display label `FUN_005e1d80`), the real list accessor; the separate four-byte empty stub is ELF VA `0x5e1d80` / `FUN_006e1d80` and is not called. This is a static selector/key/record-handoff trace, not a live placement or world-transform result; full details are in [the native follow-up](BUILDING_SITE_INDEX_BLACKBOARD_NATIVE_FOLLOWUP_20261107.md).

## Exact source joins

`B_data/EventFlow/Player_HousingKit.bfevfl` (manifest ID 516, SHA-256 `6b7e56629772c85053c44b399d9e1a9bdf1d8f147cceb8bb499cc8c8918a0383`) sends these selector values through `EventFlowSystemActor`:

- First bridge: `EventFlowQueryCanBuildHere` event 16 uses `StructureType=cBridge`, `StructureBuildPosType=cPlayer`; preview-guide action event 156 uses the same pair.
- Player house/tent kit: query event 30 and preview event 151 use `cPlayerHouse` / `cPlayer`.
- Settler plots A/B/C: query events 120/121/122 and preview events 168/169/170 use `cReserveNpcHouse` / `cSettlerQuest`.

These are distinct graph calls, but they do not contain a site index. In `System_Structure_Common.bfevfl` (ID 658, SHA-256 `e64c08ddc898616e354c6951ae891597726d78c4ca2c61e4257264d837033c12`), `PreviewStructure` passes `StructureType`, `StructureBuildPosType`, and `StructureBuildTiming` to `PreviewStructure`; `DeletePreviewAndBuildStructure` deletes preview then passes the same inputs to `BuildStructure`; `BuildStructure` calls `BuildStructure` and hides the share-play demo state. This confirms generic EventFlow pass-through and lifecycle order, not native action behavior or a selected coordinate.

`FieldMainFieldParam.bcsv` (ID 41, SHA-256 `3ebd1057e41b0666aa30c6d8beee9220b52d8fb5280c478e8eb13eaca5d27944`) row 0 is `[0, "FieldPresetA00", 0, "VillagePresetA00", "StructurePresetA00", "ItemPresetA00"]`; the column `StructureData` explicitly selects the preset resource name. The BYML `B_data/Param/Field/MainFieldPreset/StructurePresetA00.byml` (ID 2729, SHA-256 `2a0be5f7a0904fe09c5ead536802749696e317bf1261d22327811aafb036436e`) has six entries under `root.@StructurePresetA00.@mSiteList[]`:

| Array index | `@mUnitX.s32` | `@mUnitZ.s32` | Role |
|---:|---:|---:|---|
| 0 | 61 | 66 | OPEN |
| 1 | 78 | 77 | OPEN |
| 2 | 49 | 79 | OPEN |
| 3 | 88 | 80 | OPEN |
| 4 | 97 | 84 | OPEN |
| 5 | 69 | 90 | OPEN |

The readable `@` labels are reversible descriptor annotations in the resolved BYML view; the raw decoded keys are `31ddae5c` (`StructurePresetA00`), `29ef254c` (`mSiteList[]`), `962fa959` (`mUnitX.s32`), and `eceffa39` (`mUnitZ.s32`). Values are typed `s32` in little-endian BYML. These values are preset grid cells only; they do not establish the cell origin, units, world X/Z mapping, Y height, rotation, or footprint anchor.

## Native static-analysis boundary

The read-only analysis index is `/workspace/acnh-re/output/index.sqlite` (SHA-256 `a78c7af27d37b8fd931bba8bc611623dacf7685cb6e8b4f827effa0765340aad`) and associates both `mSiteList` and `SiteList` string references with ELF VA `0x55dfd0`. Pseudocode `binary/analysis_decomp/55dfd0.c` (SHA-256 `9d1f91df09702094ef72ad160bd6d5f04d1dcbd3af36bda5df74192abe29f05e`) constructs a descriptor containing those references. Pseudocode at VA `0x4e1db0`, `binary/analysis_decomp/4e1db0.c` (SHA-256 `4a17909774882f113dcc2e69efa953606b04624041b77fd45bbf8c044a7cbacb`), calls that descriptor path and explicitly walks six child-pointer positions, indices 0 through 5. VA `0x5651b0`, `binary/analysis_decomp/5651b0.c` (SHA-256 `6834b80ca4e44c2c4a58a6f7e39bbf87d2eaa9670966505e6ef6fda3c2b66eda`), is associated with the string `ValidateVillageSave` and passes a member at offset `+0x3a50` to the six-slot loader.

That is a static load/deserialization lead, not a runtime placement trace. The ELF metadata records source image SHA-256 `5bf707c3dc5dac0ad9635af7d336ec580f81c3f7876d0f55400d1900e3415d74`. The pseudocode file labels display an observed `+0x100000` offset relative to database ELF VAs (for example, VA `0x55dfd0` is labelled `FUN_0065dfd0`); this is only an address cross-reference rule.

A second decompilation at VA `0x369d50` (`FUN_00469d50`) accesses structure-like members `+0x3a50/+0x3a58/+0x3a60`, enumerates indices 0–5, selects an available list index, writes that value under the native key `BuildingSiteIndex`, parses the selected record and forwards the pair to actor-context helpers. The direct raw-string join and helper operations are detailed in [the selected-site follow-up](BUILDING_SITE_INDEX_BLACKBOARD_NATIVE_FOLLOWUP_20261107.md). A deeper trace proves the adjusted pair becomes X/Z lanes `10*n+5` and is quantized by a downstream 5-unit grid lookup; [the coordinate trace](BUILDING_SITE_WORLD_POSITION_TRANSFORM_FOLLOWUP_20261107.md) leaves global frame/origin, final transform, height/yaw, and footprint unresolved. The method calls VA `0x4e1d80` (`FUN_005e1d80`, file `analysis_decomp/4e1d80.c`), a 48-byte list accessor that bounds-checks indices 0–5. A separate function at VA `0x5e1d80` (`FUN_006e1d80`, `analysis_decomp/5e1d80.c`) is a four-byte empty stub, but it is not this call target.

The prologue AN/HA flows do show the literal EventFlow blackboard key `BuildingSiteIndex`: the two AI flows initialize it to `-1`, the common flow queries it with `Border=0`, and the orientation flows reset it to `-1`. Those graph nodes do not write an index in range 0–5 or connect the key to `StructurePresetA00`. The bounded 221-entry native handler report did not resolve the mapping. A later full-registry follow-up maps the named registrations to factories, constructors and vtable candidates; slot roles and complete action/validator semantics remain partial. Preview actor class strings exist in the native index, but are only class/resource candidates.

## Remaining OPEN joins

- `cPlayerHouse`, `cBridge`, and `cReserveNpcHouse` + `cSettlerQuest` to a particular `mSiteList` array index.
- `EventFlowQueryCanBuildHere` and the preview/build actions to an exact native query/action implementation and footprint validator.
- The parser now maps adjusted `mUnitX/mUnitZ` values to X/Z lanes as `10*n+5`, while downstream grid queries use 5-unit cells. Island/world origin, frame, elevation, rotation, footprint origin, and final model transform remain **OPEN**.
- EventFlow structure selector strings to table-local `StructureInfoParam`, `StructureBridgeParam`, or other UIDs.
- A placed save/actor instance to a model resource, rendered mesh, world transform, and PBC/collider.
- Plot A/B/C to distinct cells; their graph calls are distinct, but their params do not state cell indices.

The inspected table schemas contain structure/model/form/material/door keys but no site index or coordinates; the bridge tables contain no endpoint pair. Model or audio catalog matches remain CAT and provide no evidence for these joins. Sources, hashes, claims, and open questions are structured in the companion JSON.

## Validation

JSON syntax and structural invariants were checked after writing. No build, game, or Godot validation was run.
