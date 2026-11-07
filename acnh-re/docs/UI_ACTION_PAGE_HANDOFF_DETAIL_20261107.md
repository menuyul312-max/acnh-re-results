# UI action → page handoff follow-up — ACNH 1.0.0

This pass strengthens the `UIMenuDeviceAppear` trace and bounds the other open UI joins. It is static analysis of the supplied ACNH 1.0.0 `main` NSO; no game or Godot runtime was used. The machine-readable evidence ledger contains code-span hashes, call PCs/instruction bytes, selected page-factory and getter rows, and supplemental layout/BFLAN hashes: [ui_action_page_handoff_detail_20261107.json](../output/gameplay/ui_action_page_handoff_detail_20261107.json).

## MenuDevice: action and page-side code share a request/result channel

The EventFlow registry identifies `EventFlowActionUIMenuDeviceAppear` (registration hash `49f7be22`, constructor `0x357660`, callback `0x357770`) with `EventType` and `Application` string parameters. The `SNPC_rco_55_TkkFirstLive:InvitePlayerHouse` flow uses `EventType=cInstall`, `Application=cConstructLicense` at event 17; the initial smartphone boot flow also uses `cBoot/cNone`.

At PC `0x357984`, the native callback directly calls `0x164a040`. That wrapper obtains a singleton manager through `0x1644dc0` and calls `0x16479b0`, which copies packet fields into the manager record at `+0xb038/+0xb03c`. The matching reader wrapper `0x164a070` uses the same singleton and calls `0x1647940`; that function checks and consumes the pending record at `+0xb038` through a virtual call at `+0x18`, clears it, and writes a status byte. These are direct writer/reader links to one shared UI-event channel.

A 0x634-byte function at `0x125bcd0` makes two direct calls to the reader at PCs `0x125bd4c` and `0x125be04`, and a direct call to the writer at `0x125c1cc`. The function is in the MenuDevice page-code neighborhood and is one entry of an untyped relocated pointer sequence at `0x3308100`. Separately, `MenuDevicePage` has a registered factory at `0x125ae40`, a constructor at `0x1258460`, and a slot-46 method at `0x12595f0` that returns the exact layout identifier `MenuDevice`.

This proves a direct EventFlow-action→shared manager request and identifies a strong MenuDevice-side consumer candidate. The exact owner of function `0x125bcd0`, the `cConstructLicense` payload value, its association with a particular `MenuDevicePage` instance, and the later call to the `MenuDevice` BFLYT/BFLAN loader remain open. The generic page factory handoff and exact string getter do not by themselves prove an action-triggered page load.

## Remaining focus areas

`UIMapSelectHandling` callback `0x356f10` only writes status `0x2a` at object offset `+0xb8`; it does not call a page factory or the shared UI-event helper. `MapSelectPage` factory `0x1242550` and getter `0x1241910 → CharaMakeMap` are separate static evidence. The `cMapSelect` registry row has raw integer argument 19 and only a normalized-name candidate factory, so the action-to-page join remains open.

`Ftr_Working` and the DIY flows show workbench/crafting operations; page factories and exact slot-46 getters exist for `WorkCraftListPage → WorkBench`, `WorkCraftInfoPage → WorkBenchInfo`, and `WorkCraftBgPage → WorkBenchBG`. The `cWorkCraft` registry row does not normalize to an exact factory class. The EventFlow action-to-page path and BFLAN triggers remain open; this does not replace the separate crafting-transaction evidence.

`StructureStartPreviewGuide` is natively registered with `StructureType`, `StructureBuildPosType`, and `StructureBuildTiming`. Its native handler at `0x3445b0` calls position helper `0x3771d0` at PC `0x344730`; that helper builds/tests a world position from the selected build-position mode and returns a validity bit. A sibling path at `0x344d20` calls the generic `cBuildStructure/cDefault` command helper. This maps position/command handling, not the visible placement ghost or its renderer. `ShopBridgeSlope` remains a shop/style page candidate, not proof of a placement-preview screen.

The Island Evaluation flow references score-check logic and dialogue/choice branches; no dedicated rating page action was found. `CmnDialog` is only a generic dialog candidate. The StaffCredit native path reaches a generic `State::cPlay` helper with a `StaffCredit` case, while `StaffCreditPage → StaffCredit` is a separate exact getter; no first-live trigger connects the two.

## Resource and version boundary

Selected layout records provide useful conversion references: `MenuDevice` has a `DemoInstall` BFLAN tag, WorkBench layouts have their craft/remake presentation tags, and `StaffCredit` has `CorporationIn`. The selected container sources are marked `new_path` in the supplemental manifest. Their hashes identify the indexed bytes but do not pin an exact update patch or prove runtime use. Model and audio remain catalogue-only references.

The full main-text direct-`BL` scan confirms two call sites to `0x164a040` and two to `0x164a070`, with the reader calls both inside `0x125bcd0`. It finds no direct branch/call reference to the selected slot-46 layout getter functions. This scan does not cover indirect dispatch, so those routes remain unresolved rather than disproven.

Validation: JSON parses; function SHA-256 values are calculated from exact raw NSO text spans, call PCs and instruction bytes were read from the same text segment, and all selected supplemental layout records remain explicitly version-unpinned.
