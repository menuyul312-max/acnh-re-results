# Registration UID to LandMaking world-builder follow-up (ACNH 1.0.0)

This pass follows the candidate `FieldMainFieldParam.UniqueID` past the registration option builder into its preset-data consumer. It also checks the saved-ID world setup and the EventPlaza side data. The native path now proves a UID-keyed read of the matching LandMaking resource and a 112×96 cell-transfer loop. The exact handoff from the user's `cVillage` result to the world-init call, player spawn, full collision build, and durable save remain open.

No game process or save was run or changed. PCs below are raw ELF VAs. The main binary, generated decompilation, SQLite call index, and source-data hashes are recorded in the companion JSON.

## Candidate option to terrain-data path

`0x529910` constructs four option entries. Its four calls to `0x528bf0` are at `0x529a80`, `0x529b90`, `0x529ca0`, and `0x529db0`. The builder writes each row candidate's u16 ID at entry `+0x0c`, the outside-template ID at `+0x0e`, and the ordinal at `+0xb8`.

At `0x528bf0`, the ID at `+0x0c` is passed to `0x558ea0` at `0x528c78`, which stores it in the typed preset-ID wrapper. The candidate builder then calls `0x558f40` at `0x528c98` and `0x5598c0` at `0x528ca8`. These calls establish per-candidate preset-data assembly; they do not prove the data is drawn into the `CharaMakeMap` card texture.

`0x558f40` reads the wrapper ID and calls `0x54e190` at `0x558f84`. That accessor subtracts the configured ID base at context `+0x1128`, bounds-checks against `+0x1108`, and resolves the row through the pointer array at `+0x1110`. The table metadata identifies the row key hash `0x54706054` as `UniqueID` (`u16`), and `0x6e1ac981` as `FieldData` (`string32`).

At `0x558ff4`, `0x558f40` calls `0x54e7f0` on the resolved row. This getter reads `FieldData` and applies the resource-name format `%s_LandMaking`. The native resource wrapper is initialized with the `FieldPresetParamsLandMakingHeap` class/name, then the loader processes the 112×96 grid (96 outer by 112 inner iterations), using a 14-byte source stride and transferring the two terrain layers and height fields into a destination cell accessor. The exact seven meaningful source fields and destination offsets are already recorded in [the island-loader follow-up](ISLAND_LOADER_FOLLOWUP.md); the source cell is not the separate 52-byte ground/collision record.

The table has 96 distinct IDs. Every `FieldData` value has a matching `*_LandMaking.byml` and `*_EventPlaza.byml` file in the supplied data set (192 files checked). For example, ID `0` resolves to `FieldPresetA00`, whose LandMaking source is `B_data/Param/Field/MainFieldPreset/FieldPresetA00_LandMaking.byml`. This is a direct native ID→row→resource-name join, while the exact visual thumbnail/capture update remains open.

## EventPlaza side data

The adjacent `0x5598c0` consumer performs the same ID-indexed row lookup at `0x5598f0`, reads `FieldData` through `0x54e840` at `0x559950`, and formats `%s_EventPlaza`. It loads the corresponding `FieldPresetParamsEventPlazaHeap` data. The helper `0xf74c50` is called at `0x559ad4` and copies two 32-bit values into `SaveMainField` offsets `+0xcfa2c` and `+0xcfa30`, immediately after the u16 preset ID at `+0xcfa2a`.

The native getter `0xf74c30` reads those two saved values, constructs a two-value spatial object, and is used by `0x47c1e0`; that method then updates a bounded spatial region. The individual BYML parameter hashes remain unnamed, and the binary does not prove these values are the player's spawn coordinates. Preserve them as raw preset-specific values in a conversion until their field semantics and coordinate units are established.

## Saved UID and world setup

The selected-entry block at `0x529ea0` is reached by a tail branch from `0x529e50` at PC `0x529e94`. The generated `functions` extent covers this address as part of `0x529e50`, while the newer `native_functions` inventory also records a split entry at `0x529ea0`; the control-flow edge is proven, but the index sources disagree on the function boundary. At `0x529ea0`, the selected entry's `+0x0c` u16 is loaded at PC `0x529f34` and written through the `SaveMainField` accessor at PC `0x529f44` to `+0xcfa2a`. The prior option-to-save follow-up records the exact instruction bytes. `0x565e30` later reads a u16 from the same save offset, wraps that value through `0x558ea0`, and calls `0x558ef0` at `0x566220`; `0x558ef0` calls the same LandMaking loader `0x558f40` at `0x558f28`. The same setup routine also calls `0x5598c0` for EventPlaza data and `0x559b80` for an additional LandMaking-heap consumer.

There are two direct callers of `0x565e30` in the indexed main-ELF direct-call table: `0x5662e0` at PC `0x5665c4` and `0xcd270` at PC `0xcd2c0`. The first function independently samples a preset ID, writes `MainFieldParamUniqueID` and related outside-field values, then calls `0x565e30`; it proves the creator-to-world-setup path, but its random draw must not be equated with the user's chosen card. The second call is in the `ValidateVillageSave`-associated handler. Those calls prove the saved-ID consumer exists, but no direct call/data-flow edge joins the cVillage result writer at `0x529ea0` to the `0x565e30` invocation. That stage/lifecycle handoff remains **OPEN**.

The prologue flow independently shows `TerrainSelect → UIMapSelectHandling → SaveSetFromUIResult(SaveType=cVillage)`. Its later `SetupActorPosition(Type=3)` and EventPlaza camera actions do not name the selected UID or call the loader. Thus the player-spawn coordinate and the transition from the selected map result into the world-init call remain unproven.

## Conversion boundary and remaining proof

For an accurate future conversion, resolve the chosen u16 UID through `FieldMainFieldParam`, then use the row's exact `FieldData` stem. Preserve each LandMaking file as a 112×96 grid and retain both layers, variations, rotations, height, and padding/source bytes. Do not infer collision geometry by expanding a 14-byte terrain cell into the 52-byte runtime ground record. Keep EventPlaza values keyed by their source hashes until their names, units, and relationship to the plaza/player are proven. Model and audio remain catalogue-only references under the existing asset policy.

The open edges are: the runtime candidate-array/range initializer and actual four IDs for a run; the UI result-to-world-init lifecycle call; the EventPlaza hash meanings and world coordinate transform; player/airplane spawn selection; collision/PBC expansion and terrain actor/model construction; any seed field beyond the sampled preset/template IDs; and durable save/round-trip behavior. Existing archive boundaries still omit raw PBC and model/audio payloads needed to prove those later stages.

## Evidence identity and scope

The main NSO SHA-256 is `f8d248109ff72999b4600ae3749f8c7397fb960f7ad3ab8dee3018ae9e14e900`; its raw executable segment `main/0.bin` SHA-256 is `9c9b45d8e7a58706ca59e7244b3aebac2325ef98faa205e007974eeeb2f758e9`. The SQLite direct-call/cross-reference index SHA-256 is `a78c7af27d37b8fd931bba8bc611623dacf7685cb6e8b4f827effa0765340aad`. The JSON ledger provides hashes for all consulted decomp files and data sources, exact call sites, and bounded negatives. The selected-entry PC/byte evidence is carried forward from [the option-to-save follow-up](REGISTRATION_TERRAIN_OPTION_SAVE_JOIN_FOLLOWUP_20261107.md). This is static analysis; it is not an executed map-load or spawn fixture.
