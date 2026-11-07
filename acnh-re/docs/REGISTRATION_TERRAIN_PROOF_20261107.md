# Registration and terrain-selection proof

This report follows the ACNH 1.0.0 new-player route from boot/title through name, birthday, avatar, weather-area choice, island-card selection, `NewGame`, and the opening landing stage. It records only source-backed links and marks unfinished joins `OPEN`. The machine-readable companion is [registration_terrain_proof_20261107.json](../output/gameplay/registration_terrain_proof_20261107.json).

The status labels are `EF` (decoded EventFlow), `TBL` (source table), `STRUCT` (parsed source structure), `PSEUDO` (static code string correspondence), `NATIVE` (original native behavior exercised or statically resolved), `CAT` (catalogue-only candidate), and `OPEN` (unresolved join). Main flow/table/stage evidence is indexed in [manifest.json](../output/manifest.json). The supplemental RomFS UI and message files are structural comparison evidence only: the local inventory warns against inferring exact version from filenames. The Model and Sound raw archives are absent.

## Proven route

| Order | Source evidence | What it establishes |
|---|---|---|
| Boot | `System_BootSequence.bfevfl`, source 627, SHA-256 `49d5c698a84ff22a8e469b382bad9b5471d9c6dc137b083c592f3906cc88f0d0` | `Root` calls `SaveSimpleLoad {Process:cAll}`. On success case 0, it calls `SaveCopyToEnv`, `CreateStaticField`, language check, then PC-save check. This does not prove the durable save lifecycle. |
| Title | `System_Title.bfevfl`, source 659, SHA-256 `0cc338bc2f0e739193b742ccc0f603148b0b0149282e5db4a169f6d8dea39333` | `UITitleResult` case 1 requests stage `cCharacterOrder`. The precise handoff from `CharacterOrder` to the airport departure stage remains `OPEN`. |
| Registration stage | `IdrAirPortDemoDeparture.byml`, source 2887, SHA-256 `2004fd9b04cf7a7216a00fd6f6d410357f510b45adf56ee66b1e7952b5b382e5` | Contains launcher `rcm/AIC:Demo/DMF:Tutorials_Prologue1_Charactermaking`, actor labels `rco`/`rct`, and `CameraTag:Root`. The two actors are at `(120,160,0)` and camera at `(160,160,0)`; this does not identify player spawn. |
| Name/birthday | `Tutorials_Prologue1_Charactermaking.bfevfl`, source 661, SHA-256 `cbf8fc7e4f5df544398f8dfd4b401f558bf386862af1abac72b8ab57c1d8688d` | `EnteringNameAndBday` invokes `UISoftwareKeyboardHandling {FormType:cName}`, saves `cPlayerName`, sets the `cPlayerNameNoGender` tag, invokes `UIDateHandling {DateInputType:cOpeningBirthday}`, then saves `cBirthDay`. |
| Avatar | Same source 661 | `Charactermaking` invokes `UICharactermakingCreate`, `UICharactermakingHandling {CharctermakingFilterType:cFirstTime}`, then saves `cCharaMakeResult`. |
| Region/weather area | `Tutorials_Prologue1_Areacheck.bfevfl`, source 660, SHA-256 `e0a2260e57821e0d874eef053df88720a2a8e027d135fd4b94bbee8638f6704b` | Choice branches call `EnvWeatherArea` with `cWeatherArea_North` or `cWeatherArea_South` before the island-card flow. This is separate from choosing among the map cards. Its save field is `OPEN`. |
| Island card | Same source 661 | On the new-prologue branch (`cLand:ValidateVillageSave` OFF), `Apply` calls `Areacheck`, then `TerrainSelect`; that entry invokes `UIMapSelectHandling` and saves the result as `cVillage`. The concrete map-card identity and its preset/save mapping remain `OPEN`. |
| First-time setup | Same source 661 | The first-time path sets demo time to 14:00 and `cLockDemo`, sets `cPlayer:MakeVillagePlayerFlag`, `cLandTemp:IsFirstPrologue`, and `cLand:OpeningSeqBGMChangeCounter=1`, reserves `PrologueTanukichi`, then hands off to `cOpeningMovie`. `DoneCharacterCreation` and `EntryGame` are on the validated-save branch. |
| NewGame | `System_GrowUp.bfevfl`, source 645, SHA-256 `ff6c2241927e1f657e941b504dd99ac3a27ba0fee296afba47c144eddee0ecb7` | `NewGame` performs date/game-process/first-day/weather setup, calls `SaveGrowUp {GrowUpSituation:cStart}`, unlocks time, and requests `cMainFieldDemoLanding`. The dispatcher from `cOpeningMovie` into this entry is `OPEN`. |
| Landing | `Tutorials_Prologue_DemoLanding.bfevfl`, source 670, SHA-256 `3853a5ab67854826784baba8cd77f30b9081f18fbdd5ea37a0567b7fed8324b5` | Its `Root` runs the landing cut, `UILogoAppear {SelectKind:cTitle}`, `Flight_Landing`, and requests `cFrontOfAirPort`. `MainFieldDemoLanding.byml`, source 2910, SHA-256 `f65850ad99eec9bc52861a2a9591f46358ea3ad09bb14273f40ba5751e918143`, contains the flow launcher and `AirportDemoAirplaneShadow`. Player spawn and actor/model binding remain `OPEN`. |

EventFlow uses `SaveSetFromUIResult`; that shows the named result handoff, not a proven disk write. The native save-layout index identifies birthday at player-record node `0x16a08`, save-data offset `0x11478`, size 2, and names `PlayerBirthday` references at `0xefe10` and `0xf920f0`. The connection from `cBirthDay` to that member, plus the name/avatar/`cVillage` final writer and first durable save commit, is still `OPEN`. `SaveGrowUp` is not treated as proof of a completed durable save.

## UI, text, and input assets

The base main NSO hash used by the static UI analysis is `f8d248109ff72999b4600ae3749f8c7397fb960f7ad3ab8dee3018ae9e14e900`. [page_layout_method_bindings.json](../output/ui_hud/page_layout_method_bindings.json) finds an exact returned layout-name string at vtable method slot 46, offset `0x170`, for these classes:

| Page class | Getter | Returned layout | Parsed BFLYT hash |
|---|---:|---|---|
| `TitlePage` | `0x156cde0` | `Title` | `40b872f05178df2009b2c5cca853e86120d9e01dee729fd4c54b5ad388749d0c` |
| `CharaMakePage` | `0x11959c0` | `CharaMake` | `251b48fc218d87ed64305d3b00bb20874daf5dcb3b99103dd90941ab3fa82a01` |
| `DateInputPage` | `0x11e1cc0` | `DateInput` | `2f2faed68871c59992eafa1ce96e38b83b441e965b45f798e42cb1648be5cb0d` |
| `MapSelectPage` | `0x1241910` | `CharaMakeMap` | `b110eb4c09bb23ce89f3f7a32139a68d1cc6b37c615788d75284a113941ca6ea` |
| `PrologueBGPage` | `0x140efd0` | `WipePrologue` | `411ad0aee7fb031004d5246ba101471a108e0cb964b2b2ae7761721bdb8588bc` |

These are `PSEUDO` page/layout correspondences, not proof of a caller, handler-to-page handoff, loader, runtime instantiation, or rendering. Their BFLYT structures come from supplemental archives and are `STRUCT`, with exact 1.0.0 identity still open. Their layouts show:

- `Title`: 1920×1080, 22 panes, prompt part `L_BtnPressA_00 → LTitlePressABtn`, regional title parts.
- `CharaMake`: 1920×1080, 120 panes with face, hair, eye, nose, mouth, cheek, design, body and completion-dialog part families.
- `DateInput`: 1920×1080, 36 panes, month/day selector parts and birthday confirmation.
- `CharaMakeMap`: 1920×1080, 18 panes and four map-card parts `L_Btn_00`…`03`, each `562×438`, centered at `(-260,76)`, `(260,76)`, `(-260,-220)`, `(260,-220)` in layout coordinates. Each card references `LCharaMakeMapBtn`; parent `CharaMakeMap` does not identify the preview picture source.
- `WipePrologue`: 1920×1080, 3 panes.

Parsed supplemental `BFLAN` members include title `In`/`Out`/`InPressA`; character creation `In`/`Out`/`FinishOut`/`Type`/`CategoryNum`/`HairColorPos`/`Equip`/`Share`/`RegionLanguageType`/`3DPoseWait`; date `In`/`Out`/`RegionLanguageType`; map `In`/`Out`/`RegionLanguageType`; and prologue wipe `In`/`Out`. These are `STRUCT` resources; runtime trigger and timing are unproved. BNTX metadata also joins same-archive BFLYT texture names to exact members: CharaMake face/mouth/nose icon textures, DateInput/CharaMakeMap common header/window textures, Title `Capture^t`, and WipePrologue `Black_00^r`. Map preview imagery is not proven by the parent BNTX; the child map-card parts still need inspection against exact 1.0.0 sources.

Base 1.0.0 parameter BYMLs corroborate the layout families: `Param/Layout/CharaMake.byml` (source 936, SHA-256 `ea4e732051fb0ce166c2a49d63da29451cbbefd6b758a8d5f791cc69aba6e17d`) uses `UI_CharaMake` and face/hair/eye/nose/mouth/cheek/OK parts; `Param/Layout/CharaMakeMap.byml` (source 1652, SHA-256 `c46216c67b2bfe46641ce6981ddef4334a5c6f302a96d8e68b7e41708b9c0e56`) uses `UI_CharaMakeMap` and map dialog/button part paths. These rows do not establish handler bindings.

The flow keys call `Tutorials/Tutorials_Prologue1_Airport:003_02`, `005_01`, `005_02`, `021`–`024`. The supplemental US-English MSBT member (`Tutorials_Prologue1_Airport.msbt`, SHA-256 `7e17eb63129ef707e9bff5773648a55cc38a0342b36a726e6b095508f7a99e6f`; containing archive SHA-256 `2cc35ef4907f06a53213f44adab3f6bb9047fe196290413ec47a2246f652da73`) gives examples asking for name/birthday at `003_02`, appearance/photo at `005_01`, and island choice at `021`/`022`. It is `STRUCT` supplemental text; exact version and rendered-dialog association are not proven.

## Tables and terrain/world data

The 1.0.0 manifest includes eight `TBL` character customization tables: `CharaMakeCheekTypeParam` (source 5), `CharaMakeEyeColorParam` (6), `CharaMakeEyeTypeParam` (7), `CharaMakeHairColorParam` (8), `CharaMakeHairStyleParam` (9), `CharaMakeMouthTypeParam` (10), `CharaMakeNoseTypeParam` (11), and `CharaMakeSkinColorParam` (12). Their full source paths and SHA-256 values are in the JSON companion. These tables prove parameter families exist; the exact native UI consumer is still open.

Terrain/world source tables are `FieldMainFieldParam` (source 41, 96 rows, SHA-256 `3ebd1057e41b0666aa30c6d8beee9220b52d8fb5280c478e8eb13eaca5d27944`), `FieldOutsideParts` (source 45, 136 rows, SHA-256 `1d244d825f4ef111afae5df2568486ceab243caccd21c17259b5ec59830650e6`), and `FieldOutsideTemplate` (source 46, 36 rows, SHA-256 `1c615f1c8b42d4f690f81fd577261a3daf61f814bb3b1f93354fd1b714c5a314`). The local [island table crosswalk](../output/ui_island/island.json) relates field-data basenames to LandMaking/EventPlaza, structure-preset and item-preset assets, and outside templates to candidate parts.

A separate `NATIVE` proof in [island_template_selector_native.json](../output/ui_island/island_template_selector_native.json) executes the original selector against reconstructed typed-cache fixtures: 528 cases, no mismatches. Functions `0x54e330`/`0x5089e0` read the preset/template kinds; selector `0x552bb0` maps each of 96 presets to a candidate pool of 12 templates of kind `3B_S2`, `3B_SE` or `3B_SW`. This is coast/outside-template selection—not the player's four visible map cards. Original cache initialization, live RNG integration, selected map/preset, and final `cVillage` linkage remain open. [TERRAIN_RUNTIME.md](TERRAIN_RUNTIME.md) documents supporting 112×96 LandMaking and PBC scale evidence while keeping preset-to-runtime loader and world transforms unresolved.

## Catalogue-only assets and remaining joins

Model candidates such as `NpcSpRco`, `StrcAirPortA00`, and `StrcAirPortA00Deck`, and audio candidates such as `Demo_Plane_Inside`, `Demo_Plane_Landing`, and `BGM_Field_Prologue_Phase1`, are `CAT`. The supplied catalogue has generated reference paths only; the raw Model sources are absent, and the raw Sound source-path match count is zero. EventFlow `BGMPropertyControl` values 55/54 and `Flight_Landing` identify action keys, not exact sound files. No model/audio file existence or runtime playback is asserted.

The principal unresolved links are the title/departure stage transition; UI handler to instantiated page/layout and input callbacks; the four map preview images and their cVillage data; cVillage to a field preset and selected coast template; exact first save writer; cOpeningMovie to `System_GrowUp:NewGame`; and stage actor/spawn to raw model, rig, collision, and audio members.

For Godot-facing conversion, preserve the decoded BFLYT part hierarchy and 1920×1080 layout coordinates; decode BNTX block-compressed formats/channel swizzles before texture import; keep BFLAN tracks as named animation resources until triggers are known; and normalize BCSV/BYML while retaining source IDs, enum order, and unknown fields. Do not treat generated GLB/OGG catalogue paths as present assets.

Validation: the JSON companion parses with `python -m json.tool`; its cited source hashes were spot-checked against the local manifest and supplemental inventory. No shared crosswalk, README, HANDOFF, or implementation files were changed.
