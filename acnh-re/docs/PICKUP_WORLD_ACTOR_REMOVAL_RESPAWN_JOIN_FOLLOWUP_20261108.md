# Pickup world-actor removal and persistence join (2026-11-08)

**Build:** Animal Crossing: New Horizons 1.0.0. **Status:** read-only static native/EventFlow trace. No runtime pickup, native fixture, save mutation, Ghidra rebuild, or Godot edit was performed.

## Result

The pickup descriptor reaches two guarded branches. The ordinary branch reaches the shared 20-record item-view writer `0xf987c0`; `0xefac20` checks that writer's return and the normal branch propagates its result. A separate branch resolves a runtime object, finds a component at `+0x2d8` with type `0x280`, and passes the descriptor to `0xf6a450`. That wrapper writes through an 80-entry, 8-byte descriptor list, but it discards the list helper's result; the `0xdb0450` caller also ignores the later `0xeebe80` result and returns success from that branch. This branch is not evidence of a pocket insertion.

The outer pickup update `0xe21e40` ignores `0xdb0450`'s return and continues its state update. The descriptor producer remains player-side `Player+0x1018`; no source actor handle or actor-specific UID is joined to it. The type-`0x280` component remains an unresolved manager/component candidate: the same accessor and list helper are used from resident move-out/move-in routines, and the index does not identify it as the picked-up actor. No explicit source-object removal, retained-state update, respawn/tombstone scheduling, or durable persistence effect was recovered. The central join therefore remains open:

```text
source actor + item descriptor
  → accepted pocket insertion
  → source actor removal or update
  → durable save / reload
```

Only guarded reachability and branch-specific bookkeeping are statically joined.

## Descriptor consumer and acceptance gates

`PlayerPickupWait` update `0xe20f00` reads the descriptor at player offset `+0x1018`. On one path it sends the descriptor through `0xe07ae0` at call PC `0xe21000`, which stores it at pickup-state context `+0x1c` at `0xe07b1c`; another path stores a constructed descriptor at `0xe211e0`. This narrows the descriptor producer to a player-side field. It does not identify the source world actor or establish that the field is an authoritative actor record.

The `Pickup` update `0xe21490` calls `0xe21e40` at `0xe21688`. The latter reads context `+0x1c` at `0xe21e68`, initializes its mode output to zero, and calls `0xdb0450` at `0xe21e7c`. The descriptor enters the following guarded branches:

| Branch | Raw call chain | Return behavior | What it proves |
|---|---|---|---|
| Pocket item-view writer | `0xe21e40 → 0xdb0450` (`0xe21e7c`) → `0xefab90` (`0xdb0608`) → `0xefac20` (`0xefabf8`) → `0xf987c0` (`0xefad2c`) | `0xefac20` checks `0xf987c0`'s result and returns success only on its success path; `0xefab90` and the normal `0xdb0450` path propagate it. | The native graph can conditionally accept a pocket-view insertion. It does not show that a field pickup reaches this branch or that the slot writer succeeds for a runtime target. |
| Type-`0x280` descriptor list | `0xdb0450` resolves `0xeecf60`, then component `+0x2d8/type 0x280`, and calls `0xf6a450` at `0xdb05a0`; `0xf6a450` calls `0xf6a2f0` at `0xf6a458`. | `0xf6a2f0` scans up to 80 entries with 8-byte stride and may copy the descriptor into a `-2` empty slot. `0xf6a450` is `void` and discards the helper's result. `0xdb0450` then calls `0xeebe80` at `0xdb04bc`, ignores its result, and reports branch success. | A descriptor-list mutation can be attempted on a guarded path. The branch does not call `0xf987c0`; its return does not establish pocket acceptance or source-object removal. |

The mode passed by the `0xe21e40` Pickup call is zero. In the type-`0x280` branch this makes the `0xf6a450` mode argument false; the `0xeebe80` optional flag is also false. The exact item/runtime guards before both branches remain material: this static path is not an unconditional normal-pickup route.

Crucially, `0xe21e40` does not test or store the return from `0xdb0450` before it continues with `0xdc9600` and later pickup-state work. The raw instructions confirm the decompiler's return-flow interpretation:

| PC | Raw word | Decode / effect |
|---|---:|---|
| `0xdb05a0` | `0x9406e7ac` | `BL 0xf6a450` |
| `0xdb05a4` | `0x910003e0` | `ADD X0, SP, #0`, replacing the wrapper return before the cleanup call at `0xdb05a8` (`BL 0xee93d0`). |
| `0xdb04bc` | `0x9404ee71` | `BL 0xeebe80` |
| `0xdb04c0` | `0x320003f4` | `MOV W20, #1`; the branch result is overwritten with the success/result value used by `0xdb0450`. |
| `0xe21e7c` | `0x97fe3975` | `BL 0xdb0450` |
| `0xe21e80` | `0xaa1303e0` | `MOV X0, X19`, replacing the call result before the next calls and later branch. |
| `0xefad2c` | `0x940276a5` | `BL 0xf987c0` |
| `0xefad30` | `0x2a0003f6` | `MOV W22, W0`; the slot-writer result is retained. After cleanup at `0xefad38`, `0xefad40` tests bit zero of `W22` (`TBZ`) before the success-only updates. |

Thus the inner pocket writer has an explicit acceptance gate, while the type-`0x280` branch and its outer pickup caller do not consume their respective results. The previous native `0xf987c0` fixture exercised controlled craft-result inputs, not the Player pickup guards, a source world actor, or a live pickup.

## Type-`0x280` candidate is not a source-actor join

The type-`0x280` component and `0xf6a2e0` list helper are shared by other indexed flows. `0xf8c2d0` calls `0xf6a2e0` at PCs `0xf8c428` and `0xf8c510`; it is reached from `0xf847f0`, whose strings include `ForceMoveOut` and `AbandonedHouse`. `0xf8de90` calls `0xf6a2e0` at `0xf8dfe8`; it is reached from move-in routines carrying `MoveInOrder` / `MoveInCompletion` string references. These cross-calls show the component is used outside the pickup call graph, but they do not name its semantic owner or resolve it to the source field item.

`0xeebe80` is another bookkeeping candidate on the type-`0x280` branch. It resolves additional player-side context, conditionally sets a named property for one item kind, and operates on a `0x754`-byte view through `0xf57920` and `0xf57880`. The caller does not consume its return. No source actor identifier, destroy/request-remove callback, or respawn decision is visible in this helper. Accordingly, both the component-list write and this later view update remain candidates for bookkeeping, not proven world-item lifecycle side effects.

## Bounded source-actor, removal, and respawn scan

The inspected direct graph covered `0xe20f00`, `0xe07ae0`, `0xe21490`, `0xe21e40`, `0xdb0450`, `0xefab90`, `0xefac20`, `0xeebe80`, `0xf6a450`, `0xf6a2f0`, `0xeecf60`, and `0xdafee0`. The type-`0x280` cross-check included `0xf8c2d0` and `0xf8de90` plus their callers. No direct source actor pointer is passed into the pocket writer; no direct named destroy/remove/detach/despawn/tombstone/respawn call is exposed in this inspected graph.

This is a bounded negative. The component found via `0xeecf60` and its virtual/runtime ownership are not resolved, and an indirect actor-manager method, another world-item lifecycle callback, or external runtime code may perform removal or respawn. The report does not claim those effects are absent from the game.

The reachable `Player_GetDemo:Get_Pickup` route remains post-get feedback. Event index 7 configures the full-pocket exchange UI with `FilterType=cPickupFull`, `ItemUniqueID=65534`, and `Mode=cExchangeByPickup`; the reachable route contains neither `DeleteTargetItem` nor `SetItemToPocket`. This UI branch does not join a successful native pocket insertion to a world actor delete request. The separate `Player_PickupFullItem` flow remains a full/error handler, not the normal source-actor transaction.

## `PickUpFirst` and persistence boundary

The `Pickup` update reaches shared notifier `0xda4370` at `0xe21a94`. Under a type-dependent predicate, `0xda4370` calls property setter `0xf4a8f0` at `0xda4454` with key `PickUpFirst` (string VA `0x029d183a`) and value `1`. This is a conditional in-memory property assignment. The predicate is shared with neighboring handlers, and the trace does not show it selected for an ordinary field item, gated by the `0xf987c0` result, incrementing a counter, or being written to durable storage.

`PickupWait`, `Pickup`, and `PickupGetDemo` have `stop_auto_save=1` in `PlayerStateParam`; that state field is not a save operation. Existing SaveProc reports establish name-based registration and queueing, a runtime callback/registry gap, and a conditional `nn::fs::Commit` path whose link to the exact queued request remains unproven. They do not identify a serializer, direct `WriteFile`/`FlushFile` from that serializer, the named local pocket member, or a write-and-reload result. Craft/inventory reports likewise keep the `+0x70/+0x17c` item view and pocket/save identity separate. Therefore neither the inventory insertion nor `PickUpFirst` is joined to durable pickup persistence.

See [the interaction trace](WORLD_ITEM_PICKUP_INTERACTION_FOLLOWUP_20261107.md), [the source-actor side-effect trace](WORLD_ITEM_PICKUP_SOURCE_ACTOR_SIDE_EFFECTS_FOLLOWUP_20261107.md), [the core item/crafting loop proof](CORE_ITEM_CRAFTING_LOOP_PROOF_20261107.md), [the inventory count context trace](CRAFTING_INVENTORY_COUNT_CONTEXT_TRACE_20261107.md), [the SaveProc callback trace](SAVEPROC_RUNTIME_CALLBACK_CLOSURE_20261107.md), [the SaveProc operation join](SAVEPROC_CALLBACK_OPERATION_JOIN_20261107.md), and [the SaveProc file-I/O trace](CRAFTING_SAVEPROC_FILEIO_TRACE_20261107.md).

## Provenance and reproduction

Addresses in this report are raw ExeFS `main/0.bin` offsets. The analysis read the existing `index.sqlite` (`direct_calls`, `native_functions`, `string_refs`, and `event_calls`), existing decompilation snapshots, decoded EventFlow, and the linked reports. No indexes, crosswalks, or source assets were edited.

Key source hashes:

| Input | SHA-256 |
|---|---|
| ExeFS `main/0.bin` | `9c9b45d8e7a58706ca59e7244b3aebac2325ef98faa205e007974eeeb2f758e9` |
| `A_logic/main.elf` (recorded by the prior 1.0.0 reports; ELF is not in the current worktree) | `5bf707c3dc5dac0ad9635af7d336ec580f81c3f7876d0f55400d1900e3415d74` |
| `Player_GetDemo.bfevfl` | `b5ac3c44b5161615ed6b245fce3e9289c2f6d7b9ec186941ce9790ea624703fa` |
| Decoded `Player_GetDemo.json` | `e937aee95d923bfbdde2e923e1783f5a9001a3d716768e06bde8f1212cd96052` |
| `Player_PickupFullItem.bfevfl` | `757f28163719419d7fb606793c256d52bc42396676518933e442fe9a60175911` |
| Decoded `Player_PickupFullItem.json` | `df828fe11607a563db8dce060b38407d5a24cd8357890e8027037ca438a0b481` |
| `PlayerStateParam.bcsv` | `746619914744a62365b7b4cc74fd5b7fad169e78dffe74c3c03c726d3ea49b0d` |
| Existing `index.sqlite` | `a78c7af27d37b8fd931bba8bc611623dacf7685cb6e8b4f827effa0765340aad` |

The companion JSON contains hashes for the prior pickup/crafting/SaveProc ledgers and the decompilation snapshots used for this follow-up. No runtime behavior is claimed.
