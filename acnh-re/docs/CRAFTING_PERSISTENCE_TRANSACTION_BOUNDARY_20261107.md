# Crafting Persistence and SaveProc Boundary Follow-up

**Build:** Animal Crossing: New Horizons 1.0.0. **Status:** static call-graph and save-layout audit, with review of prior bounded file-helper fixtures. No live save, new native execution, or write is claimed.

This follow-up separates three things that earlier work could otherwise blur: craft inventory mutation in memory, an explicit SaveSimpleSave request with a completion poll, and the unresolved serializer/disk boundary.

## Craft mutation and save-member identity

The EventFlow Ftr_Working craft path calls SaveSetFromUIResult with cWorkCraft at index 212. Its handler is registered at 0x334650 and dispatches cWorkCraft to 0x3358c0, which calls 0xee1420 at 0x335aa8. In 0xee1420, a branch sends material slots through 0xeff060; another calls 0xee1060 for slots 0 through 5. The source shows later material processing and a result-award branch, but neither native transaction branch has been executed end to end with a player save.

The alternate material path has a concrete in-memory update chain: 0xee1420 calls 0xeff060 at 0xee14dc through 0xee157c; 0xeff060 resolves a player context at 0xeff098, opens an accessor at object-relative +0x1c0 with a 0x140-byte view, then calls 0xf9e410 at 0xeff0e4. This is the signed pocket-slot update path. The source identifies the accessor offset and view length, but does not name it as a local SaveLand member.

The result path is similarly concrete. 0xee1420 calls 0xefab90 at 0xee17bc; 0xefab90 reaches 0xefac20 at 0xefabf8; 0xefac20 opens a view at its context-relative +0x70 with length 0x17c, then calls the general item insertion routine 0xf987c0 at 0xefad2c. Afterward, 0xee17e0 calls the bounded marker helper 0xf29080 at 0xee185c. This establishes a native in-memory inventory insertion path and a marker update; it does not identify the serialized save field or prove the result survived a save/reload.

The local layout report at [save_layout.json](../output/gameplay/save_layout.json) does expose offsets, but they are not enough to name these views. The comparison is recorded in [save_layout_external_crosswalk.json](../output/gameplay/save_layout_external_crosswalk.json). Its metadata defines node as an accessor-node offset and data as an offset in saved bytes. In the separate player-record layout from constructor 0xf8f580, node +0x70 points to data +0x4 with size 1 and no name; node +0xa8 points to data +0x8 with size 0xaf90 and no name. The crafting result accessor at context +0x70 returns a 0x17c view. These equal node offsets do not establish a shared root or a named SaveLand field. The alternate material accessor at +0x1c0 / 0x140 likewise has no matching named local member.

The external crosswalk aligns selected local root members to a different-version SaveLand schema by offsets, sizes, and tree depth. Its root size matches 0x4fa0d8, but its schema is named save_schema_111_103 while this binary is the supplied 1.0.0 build. The ledger covers 88 sampled members, not the per-player pocket views above; it contains no 0x17c member. Its path names remain cross-version candidates, not local RTTI. Thus neither current layout artifact maps craft material/result mutation to an exact named local save member.

## SaveSimpleSave request versus durable write

The static call-graph ledger is [crafting_transaction_followup_static.json](../output/gameplay/crafting_transaction_followup/crafting_transaction_followup_static.json). The prior direct file-helper run is recorded in output/gameplay/tool_mechanics_followup/tool_state_callback_native.json. The EventFlow index contains 12 SaveSimpleSave actions. System_SaveGameClose index 1 requests SaveSimpleSave with Process=cAll. The handler constructor is 0x337e30; its request stage is 0x337f00, process dispatch is 0x338080, and completion stage is 0x338120. The request path tail-dispatches to 0x338080; that dispatcher calls 0xfb3160 at 0x3380f8, and 0xfb3160 queues a SaveProc operation through 0xfaf180 at 0xfb3234. The action later polls completion through 0xf1da80 at 0x3381b8. The tail edge to 0x338080 is decompiler control flow, not an indexed direct BL call.

SaveProc's registration at 0xfb4150 packages its name and context into a generic worker factory at 0xd4240. The worker queue stores 0x38-byte task records; its dispatch selects an indirect callback, and 0xd45c0 reaches generic executor 0x2201820, which makes another indirect callback at 0x22018e8. The callback identity and serializer are not statically bound. Indexed craft calls do not directly target the SaveSimpleSave/SaveProc request functions.

There is a candidate file-oriented family, but it is not a proven SaveProc serializer. A relocated pointer sequence at 0x32ff8d8 contains 0xfafec0, which dispatches helpers including 0xfb1e10, 0xfb1ff0, 0xfb2200, 0xfb23e0, and 0xfb25e0. Those helpers reach 0xf214a0 and 0xf21350. A prior bounded fixture called those two helpers directly with synthetic manager data and SDK boundary stubs: it observed MountDeviceSaveData("ACNH_SAVE"), OpenFile("ACNH_SAVE:/PlayerData.bin", mode 2), SetFileSize(0x4000), and CloseFile. It observed no WriteFile, FlushFile, or slot serialization, and did not execute the worker queue. The pointer sequence has not been tied to the SaveProc object or its queued callback.

Main-module filesystem imports resolve to SDK exports, including OpenFile, WriteFile, FlushFile, and Commit. WriteFile and FlushFile have indexed callers elsewhere in file-stream or engine code; no direct call from the SaveProc request, queue, or candidate task-helper spans reaches those wrappers. The unresolved indirect callback could still reach them, so this scan bounds known edges rather than proving absence. No reload of PlayerData.bin or before/after file comparison exists.

## Dirty marking is not persistence

A separate tool-wear path sets bit 0x4000 in the per-player slot-state word at context+0x204+slot*8 in 0xe895a0 and clears it with mask 0xffffbfff in 0xe767b0. The available decompilation scan does not find these exact slot-context accesses in 0x337f00, 0xfb3160, 0xfaf180, or 0xf1da80; 0x338080 lacks a decomp snapshot. This proves a local dirty marker on that tool path, not that crafting sets the same bit or that SaveProc serializes it. A SaveSimpleSave request and its completion poll also prove request lifecycle only, not bytes written or durable commit.

The current boundary is therefore exact as far as the evidence allows: craft helpers mutate pocket/item views in memory; SaveSimpleSave queues and polls a generic SaveProc request; a candidate file helper can size PlayerData.bin; serializer identity, player-member mapping, WriteFile/FlushFile/Commit from that callback, and reload persistence remain open.

**OPEN:** Identify the wrapper root and map the +0x1c0/0x140 and +0x70/0x17c views to a named 1.0.0 save member using direct local evidence. Bind the runtime SaveProc registry callback to its queued task and serialized player bytes. Trace an actual WriteFile plus FlushFile/Commit edge from that callback, then prove reload reads the same bytes. No rollback, atomicity, or durable craft-result claim is supported.

Machine-readable evidence and source artifact hashes are in [crafting_persistence_transaction_boundary_20261107.json](../output/gameplay/crafting_persistence_transaction_boundary_20261107.json).
