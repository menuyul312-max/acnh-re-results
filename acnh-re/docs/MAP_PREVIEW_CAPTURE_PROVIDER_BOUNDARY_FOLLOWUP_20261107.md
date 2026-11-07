# ACNH registration map-preview capture boundary

**Status:** bounded static trace. It identifies the shared map-card texture slot and a generic native UI capture subsystem, but does not prove that subsystem supplies the registration thumbnails. The ROMFS layout sources used here are supplemental archives with no build identifier; their compatibility with ACNH 1.0.0 remains open.

## Asset chain

The supplemental `CharaMakeMap.bflyt` contains four card panes, `L_Btn_00` through `L_Btn_03`, all using the same `LCharaMakeMapBtn` child layout. In that child, `N_Capture_00` contains `L_MapChoice_00` (`LMapChoice`) and a separate `P_Capture_00` picture. `LMapChoice.bflyt` binds `P_Map_00` material texture index 0 to `Capture^t`; `P_Material_00` is a separate overlay using `Noise^r`.

The `LMapChoice` BNTX manifest identifies `Capture^t` as BC5_UNORM, 8×8, one mip. The reproducible mip-0/layer-0 PNG has SHA-256 `58014df8c2e6a72b5323bfbb0a565ffb403ce1008215afbda789624c5b0f9ea7`; all 64 decoded pixels are the same `(255,255,255,0)` transparent value. It is a placeholder texture in the supplied archive, not a static island preview. The outer `P_Capture_00` material binds `Black_00^r` and `Noise+r`, which are mask/noise inputs; it does not identify the image provider.

The BFLYT projection contains no per-card image path, terrain `UniqueID`, `CaptureTarget`, or `cVillage` value. The parent supplies four visual slots but does not encode a card-to-island mapping. The raw `Param/Layout/CharaMakeMap.byml` is not present; the available converted JSON only records `UI_CharaMakeMap` and dialog aliases, as documented in the existing card-asset trace.

## Generic native capture subsystem

The ACNH 1.0.0 main-ELF string-reference index has a separate cluster of capture-related names. Function VAs in `string_refs.tsv` use the generated analysis address space; the raw ELF VA is `listed VA - 0x100000`.

| String reference | Raw function VA | Static evidence |
|---|---:|---|
| `CapturePaneWork` | `0x1b619a0` | Worker computes capture dimensions from pane/viewport values and constructs a capture/render work request. |
| `CaptureUseName`, `CaptureUseIndex` | `0x1b5d4d0` | A capture-use name/index reader. |
| `DynamicCaptureUseName`, `DynamicCaptureUseIndex` | `0x1b5dad0` | A distinct dynamic-capture name/index reader. |
| `DynamicCaptureOn` | `0x1b620b0` | Constructor initializes a capture-work object and delegates parsed state to `0x1b62130`. |
| `CaptureScale`, `DynamicCaptureScaled` | `0x1b625b0` | Capture-work routine gates on object state and calls `0x1b619a0` at `0x1b6261c`. |
| `*CaptureTarget` | `0x1db7e30` | A graphics-object constructor stores a target-property name before generic setup. |
| `N_Capture_00` | `0x11949a0`, `0x1347d20` | Name references in generic layout/resource helpers; they do not identify a MapSelectPage instance. |

The call edges support a shared UI capture path: raw `0x1b5f810` calls the capture-use handler at `0x1b5d4d0` (`0x1b5f830`) and tail-branches to the dynamic handler at `0x1b5dad0` (`0x1b5f844`). The recursive pane walker at `0x1cf0fa0` calls those handlers at `0x1cf103c` and `0x1cf1048`. Separately, `0x1b625b0` calls the render/work routine `0x1b619a0` at `0x1b6261c` and then updates an associated capture-work list. This establishes generic capture infrastructure and dynamic-capture metadata handling. It does not establish which layout or texture is its output.

## MapSelectPage and capture are not joined

The native page catalog records `MapSelectPage` factory `0x1242550`, constructor `0x12406d0`, and a relocated 79-entry pointer sequence beginning at address point `0x3110b38`. Its slot-46 getter at `0x1241910` returns the layout identifier `CharaMakeMap`. The separate candidate layout consumer at `0x1243980` passes the `CharaMakeMap` string to a resource-loading helper. These are static page/layout candidates; the existing request-ID-42-to-page join remains open.

A bounded immediate-branch scan covered all 79 pointer-sequence targets with extents in `analyzed_functions.tsv`, plus the factory, constructor, and `CharaMakeMap` consumer (82 functions total). It found no direct AArch64 `B`/`BL` target to the nine known capture-helper targets listed in the JSON. The reverse scan of nine capture/layout-walker functions found no direct `B`/`BL` to a `MapSelectPage` pointer-sequence target, its factory, constructor, or layout consumer. These are bounded direct-branch negatives: virtual calls, common UI traversal, runtime registries, omitted modules, or a capture provider selected from data can still connect them.

The other registration chain is also separate. `UIMapSelectHandling` writes request ID 42 to a shared state channel; the `cVillage` result consumer stores a selected option index and a `FieldMainFieldParam.UniqueID` into the in-memory main-field save object. The four candidate IDs are sampled dynamically without replacement. No static edge maps `L_Btn_00..03` to those IDs, assigns the `Capture^t` source, or connects the generic capture target/use-name state to that save/result context.

## Conversion and remaining proof

For accurate static reproduction, retain the original `.zs` hash, decompress and parse both SARC levels, parse BFLYT while preserving pane order, `prt1` links, material/texture indices, dimensions, alpha, and coordinates, then decode BNTX mip 0/layer 0 to PNG while retaining format/channel provenance. The relevant supplemental archive hashes and parsed-output hashes are in the JSON. A screenshot implementation cannot be inferred from the transparent placeholder or the generic capture subsystem alone. The archive release/build identity is unknown, so its BFLYT structure is a source-backed candidate, not a confirmed 1.0.0 runtime asset.

The missing joins are: page request to page instance; `MapSelectPage`/`N_Capture_00` to the dynamic-capture walker; capture-use/target state to the `P_Map_00` material texture; card index to a particular `UniqueID`; and that ID to the preview scene/preset/seed and selected `cVillage` result. No game render was observed, and no dynamic texture output was generated.

Source IDs, hashes, selected function extents, the 82-function and reverse branch scans, and the exact remaining links are recorded in [the JSON ledger](../output/ui_island/map_preview_capture_provider_boundary_20261107.json). The full source/output hashes and reproducible BFLYT/BNTX conversion context are in [the card-asset trace](REGISTRATION_CHARAMAKEMAP_CARD_ASSET_TRACE_20261107.md) and [its JSON](../output/gameplay/registration_charamakemap_card_asset_trace_20261107.json).
