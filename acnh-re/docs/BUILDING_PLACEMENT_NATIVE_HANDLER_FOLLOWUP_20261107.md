# Native placement handler and transform follow-up

**Date:** 2026-11-07  
**Scope:** ACNH 1.0.0 reverse-engineering only. This pass follows the native registrations and direct-call index for `EventFlowQueryCanBuildHere`, `StructureStartPreviewGuide`, `PreviewStructure`, `BuildStructure`, and the `StructurePresetA00.mSiteList` consumer. The companion ledger is [building_placement_native_handler_followup_20261107.json](../output/gameplay/building_placement_native_handler_followup_20261107.json). No runtime, game, Godot, or build execution was performed.

## New native links

The full resolved handler registry is in `/workspace/acnh-re/output/binary/event_handlers_resolved.json` (SHA-256 `dfc298dfcb1b288b8fda9cd6a49c728fdad903b41f8fc1c9288df7d732ec92a5`), bound from `B_data/EventFlow/Info/BindInfo.byml` (manifest ID 307, SHA-256 `d5867e0729d4d0eb222c27ff8a6b5cdc0ac401f34feadd3353f420c36368e999`) and ELF image SHA-256 `5bf707c3dc5dac0ad9635af7d336ec580f81c3f7876d0f55400d1900e3415d74`. It maps the flow action/query names to factories, constructors and vtables:

- `EventFlowQueryCanBuildHere`: factory `0x4572b0`, constructor `0x408bc0`, vtable `0x3056760`; parameter metadata contains `StructureType`, `StructureBuildPosType` and `StructureBuildTiming`. Raw slot list index 6 contains function `0x408cd0`. This function parses those fields, calls pose helper `0x3771d0` at PC `0x408e5c`, then returns a boolean-like value.
- `EventFlowActionStructureStartPreviewGuide`: factory `0x453270`, constructor `0x344490`, vtable `0x304cdf8`; raw slot list index 8 contains `0x3445b0`. Its pseudocode calls `0x3771d0` at PC `0x344730`, then configures an actor-like object from the result. The object’s class/resource key is not resolved there.
- `EventFlowActionPreviewStructure`: factory `0x453970`, constructor `0x36e010`, vtable `0x3050190`; slot-list index 8 contains `0x36e140`. That function calls `0x3771d0` at PC `0x36e2d0` and copies pose-like fields into an actor-context object at `+0x288`.
- `EventFlowActionBuildStructure`: factory `0x44ce70`, constructor `0x369c10`, vtable `0x304fd90`; slot-list index 8 contains `0x369d50`. This function parses the same selectors, calls `0x3771d0`, and accesses a six-entry structure-like list.

The registry calls these factory/constructor mappings, but slot roles are explicitly partial. I treat the listed methods as registered vtable candidates whose code is consistent with their action parameters, not as proven runtime callbacks.

The shared pose helper has seven indexed direct-call PCs from these parameterized action/query functions: `0x338f68`, `0x344730`, `0x369ef0`, `0x36b284`, `0x36e2d0`, `0x408e5c`, and `0x443a0c`. It calls `0x376eb0`, branches on the `StructureBuildPosType` enum, and fills a pose-like record with three floats, another scalar and a 16-byte field. `FUN_00439550` maps `cPlayer`, `cNpc`, `cSettlerQuest` to enum values 0, 1, 2. The observed branches use player/context helpers for 0, read NPC-like position fields at `+0x278/+0x27c/+0x280` for 1, and use an input actor transform at `+0x2a8` with a `-20` adjustment to the third float for 2. These operations establish selector-specific pose preparation, but they do not label world axes/origin or consume the selected site-cell pair.

## StructurePresetA00 consumer evidence

The existing source join remains: `FieldMainFieldParam.bcsv` row `UniqueID=0` selects `StructurePresetA00`; that BYML has six `(mUnitX,mUnitZ)` s32 pairs: `(61,66)`, `(78,77)`, `(49,79)`, `(88,80)`, `(97,84)`, `(69,90)`.

The native list-load chain is static pseudocode: descriptor VA `0x55dfd0` references `mSiteList`; VA `0x4e1db0` calls it and enumerates six child slots; VA `0x5651b0`, associated by its string refs with `ValidateVillageSave`, passes member `param_1+0x3a50` to the loader. The `BuildStructure` slot candidate at VA `0x369d50` reads structure-like fields `+0x3a50/+0x3a58/+0x3a60`, builds an availability bitset for indices 0 through 5, selects an index, then fetches `+0x3a60[index]` and passes it to VA `0x4e1670`. A later address-normalization check resolved its previously unknown key to the exact string `BuildingSiteIndex`; the selected index is written through the native actor-blackboard setter. The parsed pair is also passed to an actor-context helper. Exact PCs and remaining transform limits are documented in [the BuildingSiteIndex follow-up](BUILDING_SITE_INDEX_BLACKBOARD_NATIVE_FOLLOWUP_20261107.md).

The follow-up resolves the key and the selected-index-to-blackboard edge. The six-entry list's runtime preset identity and the story structure assigned to an index remain open.

One address correction matters here. The build-action body calls ELF VA `0x4e1d80` (`FUN_005e1d80`, file `analysis_decomp/4e1d80.c`, 48 bytes). It is an array accessor: reject indices above 5, bounds-check against the list count, fetch the pointer at `+0x10+index*8`, and call `0x4e1430`. This is distinct from ELF VA `0x5e1d80` (`FUN_006e1d80`, the four-byte empty stub). An earlier follow-up conflated their displayed function labels; this report corrects that mapping.

## What remains open

The EventFlow nodes prove `cBridge/cPlayer`, `cPlayerHouse/cPlayer`, and three separate `cReserveNpcHouse/cSettlerQuest` query/preview calls. The native registry and pseudocode show those selector values entering registered action/query classes. The earlier `string_refs` exact/prefix search returned no literal `BuildingSiteIndex`, but that is a false negative for the pseudocode address normalization: direct segment-byte inspection maps `UNK_02a80082` to ELF VA `0x2980082`, the exact `BuildingSiteIndex` string. The BuildStructure method statically writes the selected six-list index under this key; it does not assign which story structure receives each index. The event-handler slot remains a static candidate, and no game dispatch was run.

The list record parser produces an adjusted two-component value and a separate follow-up proves it becomes X/Z lanes using `10*n+5`, then enters a dynamic actor-component vcall; see [the coordinate conversion trace](BUILDING_SITE_WORLD_POSITION_TRANSFORM_FOLLOWUP_20261107.md). That partial transform does not identify global origin/frame, height, yaw, footprint, or the dynamic vcall target. The shared pose helper separately consumes player/NPC/quest actor context; the checked direct call chain does not show the selected pair flowing into that helper. The registered handlers have no direct indexed model or PBC resource strings, and their direct-call target sets do not include the indexed functions that reference named PBC resources. Preview actor class strings occur in separate global actor/module initialization references; a dynamic relationship to `StructureStartPreviewGuide` remains unproven. Model mesh and collider joins remain OPEN; catalog names stay CAT.

## Bounded search and validation

This pass used the full 1,057-entry `event_handlers_resolved.json`, not just the earlier 221-entry `focus7/native_event_handlers.json` subset. Exact/prefix `string_refs` searches found no native string for `CanBuildHere`, `StructureStartPreviewGuide`, `PreviewStructure`, `DeletePreviewStructure` or `BuildingSiteIndex`; the action names are linked through the BindInfo hash registration instead. Direct-call search found the seven pose-helper callsites listed above, but no named PBC/model references in the handler/pose functions. Those are bounded negatives; indirect resource dispatch remains possible.

The JSON passed syntax and structural checks for four registered actions, seven pose-helper sites, six preset cells, and seven OPEN joins. No game, Godot, or build execution was run.
