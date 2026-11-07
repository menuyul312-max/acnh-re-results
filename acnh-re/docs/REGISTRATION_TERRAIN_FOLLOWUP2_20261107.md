# Registration-to-terrain follow-up 2

This pass resolves the native EventFlow action objects and strengthens the owner evidence for callback `0x1242fa0`. It proves a native factory for `UIMapSelectHandling` and a native `cVillage` result-store branch. It does not prove the action-to-page/controller edge, the card-to-preset value, or the durable save commit.

This supplements the [registration/terrain proof](REGISTRATION_TERRAIN_PROOF_20261107.md) and the [first terrain follow-up](REGISTRATION_TERRAIN_FOLLOWUP_20261107.md). No Godot implementation, build, or commit was made.

## EventFlow action and page boundary

In `B_data/EventFlow/Tutorials_Prologue1_Charactermaking.bfevfl` (source ID 661, SHA-256 `cbf8fc7e4f5df544398f8dfd4b401f558bf386862af1abac72b8ab57c1d8688d`), `TerrainSelect` calls `UIMapSelectHandling {}` and then `SaveSetFromUIResult {SaveType:cVillage}` (`EF`).

The 1.0.0 native event-action index resolves `EventFlowSystemActor.EventFlowActionUIMapSelectHandling` (registration hash `1a24f4b5`) to factory `0x44cb30`, constructor `0x356e90`, object size 192 bytes, and vtable address point `0x304e3e0` (`NATIVE`, static resolution). This closes the EventFlow-action-to-native-action-object edge. It does not identify this action factory as the map page/controller: the action record does not name `MapSelectPage`, `cMapSelect`, or `CharaMakeMap`, and no direct handoff from it to the page factory is recovered.

The separate page registry records `cMapSelect` at helper `0x1549400`, with raw integer argument `[19]`, and a normalized-name candidate `MapSelectPage` factory `0x1242550`. The helper argument is an observed flag-byte offset, not a proven page ID. The row-to-factory relation is explicitly `normalized_name_candidate_unproven`. `MapSelectPage` constructor `0x12406d0` and layout getter `0x1241910` return/layout-bind the exact name `CharaMakeMap`; this remains a separate `PSEUDO` correspondence, not an action-to-page edge.

## Callback `0x1242fa0`

The raw main image is the local ACNH 1.0.0 main NSO (SHA-256 `f8d248109ff72999b4600ae3749f8c7397fb960f7ad3ab8dee3018ae9e14e900`). The relocated pointer index contains callback `0x1242fa0` at `0x3307ba0[3]`, pointer slot `0x3307bb8`. Function `0x1242ce0` consumes that pointer sequence when setting up callback records; `0x1242ce0` is entry 59 at `0x3110fb8` in the sequence beginning `0x3110de0`.

Constructor `0x1242060` writes its vptr from pseudo-global `0x3407b70` and initializes object fields at offsets `+0x210` and `+0x218`. The ELF relocation at `0x3307b70` targets `0x3110dd0`, yielding address point `0x3110de0`; those same `+0x210/+0x218` offsets are read by callback `0x1242fa0` and helper `0x1243980`. This supports an unnamed object-shape owner: `0x1242ce0` is a virtual setup method on an object initialized by `0x1242060`, and its callback table includes `0x1242fa0` (`PSEUDO`).

Callback `0x1242fa0` calls `0x1243980` at PC `0x1242fc8`; helper `0x1243980` passes literal `CharaMakeMap` into a resource-loading path. The callback also accesses four child slots with literal indices 0–3. This is strong map-screen/four-child evidence. The class name and the owner of constructor call site `0x15556d0` remain unresolved, and this evidence does not connect that object to `UIMapSelectHandling` or `MapSelectPage`.

Measured index results: `direct_calls` has zero direct callers for `0x1242ce0` and `0x1242fa0`; it records one call to constructor `0x1242060`, at PC `0x15556d0`, with no caller owner. Native `string_refs` has zero matches for `UIMapSelectHandling`, `EventFlowActionUIMapSelectHandling`, or `SaveSetFromUIResult`. These are bounded searches; the callback pointers are indirect and absence of literal strings does not rule out dispatch through a manager.

## Native `cVillage` result-store

The native event-action index resolves `EventFlowActionSaveSetFromUIResult` (hash `c930dc34`) to factory `0x452f30`, constructor `0x3345a0`, object size 240 bytes, and vtable `0x304be70`. Method `0x334650` is in slot 11 and branches over the SaveType string list. Helper `0x3362f0` refers to the list at string VA `0x29918c3`, whose ordered prefix is `cPlayerName`, `cBirthDay`, `cNickname`, `cPhrase`, `cGreeting`, `cVillage`; therefore `cVillage` is switch case 5 (`PSEUDO`, grounded in native code).

Case 5 calls helper `0x0164a130` and stores a 32-bit value at `*plRam00000000033d1ba8 + 0x45f0`. The decompilation expresses the right-hand side as `*(undefined4 *)(lVar16 + 0xc)`, but the live source of that value is not recovered. This proves a native `cVillage` result-branch store, not a durable save writer. The target object's type and field name are not recovered, and the static evidence does not trace that store to serialization or a first durable commit (`OPEN`). The emulated `save_layout.json` has maximum traversal depth 2 and does not name this context field.

## Terrain, asset, and remaining joins

The callback's four indices agree in count with the four `CharaMakeMap` card parts, but neither the layout nor callback exposes a card ID or index-to-result mapping. The child picture uses generic `Capture^t`, not four named static map images. The prior follow-up records the exact `STRUCT` resource hashes; those supplemental UI archives are not confirmed as ACNH 1.0.0.

The existing table join remains `TBL`: `B_data/Bcsv/FieldMainFieldParam.bcsv` (source 41, SHA-256 `3ebd1057e41b0666aa30c6d8beee9220b52d8fb5280c478e8eb13eaca5d27944`) has 96 rows; `UniqueID:0` names `FieldPresetA00`. Its exact filename-stem join is `B_data/Param/Field/MainFieldPreset/FieldPresetA00_LandMaking.byml` (source 2442, SHA-256 `cba1ab90d21982b443e719e30a19c80fa9aa9ead86f03705f5ecbd3c821d4aca`). Neither that data join nor the matching four-slot count ties a card or `cVillage` value to a row or LandMaking file (`OPEN`).

Raw Model and Sound archives remain unavailable. Names including `NpcSpRco`, `StrcAirPortA00`, `Demo_Plane_Inside`, and `BGM_Field_Prologue_Phase1` remain catalogue-only candidates (`CAT`). For later Godot conversion, preserve four card transforms/nested parts, retain BNTX channel/compression metadata, and leave `Capture^t` runtime-fed only after its producer is identified. No conversion was implemented here.

Remaining exact edges are: `UIMapSelectHandling` action object → `cMapSelect`/`MapSelectPage` controller; unnamed callback object `0x1242060` → that action or page; card indices 0–3 → `cVillage` value; `cVillage` result store → named persistent save field and durable commit; and selected value → `FieldMainFieldParam.UniqueID`/`FieldData` → LandMaking BYML.

Validation: companion JSON parses with `python -m json.tool`; listed source hashes were checked against local artifacts. Shared crosswalks, README, HANDOFF, and other reports were not edited.
