# Placement preview actor and asset join — bounded follow-up

**Date:** 2026-11-07. **Scope:** ACNH 1.0.0 static trace from `StructureStartPreviewGuide` through actor loading, then a data/catalog-only join for facility model keys. The companion ledger is [building_preview_actor_asset_join_followup_20261107.json](../output/gameplay/building_preview_actor_asset_join_followup_20261107.json). No Ghidra rebuild, game run, model/PBC payload inspection, Godot edit, index/crosswalk edit, or commit was performed.

## Result

The `StructureStartPreviewGuide` handler candidate does reach a generic actor manager. At raw PC `0x344818`, handler `0x3445b0` calls actor-load helper `0x490f0`. That helper copies an actor request descriptor, invokes manager path `0x49360`, and the latter dispatches through an indexed actor-manager factory table at `0x407e0`. The handler then retains a 32-bit request/actor-related field at `+0x150`, resolves it through the actor manager, and writes position-like values through the resolved manager-backed object/context at `+0x274`, `+0x27c`, `+0x284`, and `+0x28c`.

This still does **not** prove which numeric actor-type slot the request selects. The generic loader reads the request selector at `+0xc8`; when it equals `4`, it falls back to the value at `+0x18`. The trace does not statically resolve the relevant request value at that point. Therefore `StructureActor`, `StructurePreviewSwapActor`, `StructurePreviewActor`, and `StructurePreviewGuideActor` remain named actor candidates, not proven outputs of this handler.

The data side is more concrete: `StructureInfoParam` and `StructureFacilityModel` join facility IDs to exact `ModelName` keys, and every one of the 19 model keys has matching model and `_pbc` entries in the model catalogue. For example, `StructureFacilityModel.UniqueID=31` uses `ModelName=StrcCampsiteTentA00` and links to `StructureInfoUniqueID=25`; the model catalogue contains asset IDs `StrcCampsiteTentA00` and `StrcCampsiteTentA00_pbc`. This is a static table-to-catalogue join only. No traced EventFlow handler selects that row, binds the `_pbc` entry to a collision component, or proves the final build/save instance.

## Native chain and limits

The resolved handler registry maps `EventFlowActionStructureStartPreviewGuide` to factory `0x453270`, constructor `0x344490`, and registered-slot candidate `0x3445b0`. The exact handler call at `0x344818` targets `0x490f0`. In `0x490f0`, the request is copied and normalized before calling `0x49360`; `string_refs.tsv` records the `ActorLoad` string at `0x2a69b55` with exporter function-column addresses `0x1490f0` and `0x1031a90`. Those Ghidra display addresses normalize to raw ELF VAs `0x490f0` and `0x31a90` (subtract `0x100000`). In `0x49360`, the request fields at `+0xc8` and `+0x18` select an indexed manager entry; `0x407e0` reads the chosen entry and enters an allocator/constructor path. The table dispatch establishes dynamic actor creation, but not the selected class name or a model/PBC key.

After the load request, `0x3445b0` uses `0x3fa40` to resolve its stored 32-bit field. That helper queries manager subobject `+0x1c0` through `0x62e50`. The handler writes position-like lanes through the resolved manager-backed object/context. This is a preview-side instance update, but the pseudocode does not identify whether the object is a preview guide, a building ghost, or another manager-owned actor.

`PreviewStructure` candidate `0x36e140` copies pose and metadata into actor-context memory at `+0x288`; its direct body has no named actor/model/PBC load. `BuildStructure` candidate `0x369d50` selects a saved site-list entry, writes `BuildingSiteIndex`, and hands the parsed coordinate to the unresolved component virtual call documented in [the component-vptr boundary](BUILDING_SITE_COMPONENT_VPTR_LIFECYCLE_BOUNDARY_20261107.md). Neither method resolves the final structure actor, collision resource, durable instance record, or build-completion save.

The actor registry contains these exact candidates:

| Registry index | Actor key | Murmur hash | Status for this handler |
|---:|---|---:|---|
| 9 | `StructureActor` | `1515884610` | Registry entry only; selection unproven |
| 10 | `StructurePreviewSwapActor` | `2060124920` | Registry entry only; selection unproven |
| 56 | `StructurePreviewActor` | `2115111211` | Registry entry only; selection unproven |
| 80 | `StructurePreviewGuideActor` | `586259887` | Registry entry only; selection unproven |

## Facility table to catalogue candidates

The table join uses the static `StructureInfoParam.UniqueID` / `StructureFacilityModel.StructureInfoUniqueID` relationship, then checks the resulting `ModelName` against the model catalogue `Asset_ID`. The companion JSON contains all 19 exact rows, model catalogue paths, and same-name `_pbc` catalogue entries. The catalogue is being used only as an inventory/reference; no model or PBC payload was opened. A `_pbc` catalogue entry alone does not prove what native collider component consumes it.

## Bounded negative

The source slices checked were the registered handler, its request helper, actor-manager dispatch, `PreviewStructure`, and `BuildStructure`, with the indexed actor registry and structure tables/catalogue. This recovered a generic actor-creation mechanism and complete facility-table-to-catalogue key coverage. It did not recover (1) the selected actor-type index for the handler, (2) a native model key read/bound by that actor path, (3) a PBC/collider component construction or registration, or (4) a final persistent building instance/save write. Those gaps are specifically unresolved static edges; indirect actor/resource dispatch remains possible.

## Reproducibility

All native addresses are raw ELF VAs. The source `main.elf` identity is SHA-256 `5bf707c3dc5dac0ad9635af7d336ec580f81c3f7876d0f55400d1900e3415d74`. The companion JSON records hashes for the checked decompilation snapshots, actor registry, string-reference index, structure tables, and model catalogue, along with the call path and exact catalogue IDs. The handler registration remains a static candidate; no runtime dispatch was tested.
