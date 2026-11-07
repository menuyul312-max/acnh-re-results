# World item pickup interaction follow-up (2026-11-07)

**Build:** Animal Crossing: New Horizons 1.0.0. **Scope:** ordinary player pickup states, the path to the shared inventory slot writer, the full-pocket exchange UI, candidate pickup counters, and the save boundary. This is static native/EventFlow evidence, not a live pickup transaction.

## Result

The pickup path is now bounded farther than in the core item-loop report: `PlayerStateParam` rows 30–32 join to native callbacks for `PickupWait`, `Pickup`, and `PickupGetDemo`. The `Pickup` and `PickupGetDemo` callback graphs both have guarded direct-call paths to the shared 20-slot item-view writer `0xf987c0`. This establishes that those states can reach the inventory insertion routine. It does **not** prove that a particular ground item is accepted, that the writer succeeds for that item, or that the source world object is removed.

The `Player_GetDemo:Get_Pickup` EventFlow branch includes collection-type checks and a full-pocket exchange UI configured with `FilterType=cPickupFull`, `ItemUniqueID=65534`, and `Mode=cExchangeByPickup`. That graph is post-get feedback and exchange handling; it does not itself contain a pocket-write or ground-object-delete action. No named save serializer/flush/reload boundary was tied to the pickup writer. `PickupWait`, `Pickup`, and `PickupGetDemo` all carry `stop_auto_save=1` in the state table.

## Evidence

### Native state wiring

Raw addresses below are offsets in ExeFS `main/0.bin`.

| `PlayerStateParam` row | State | Entry callback | Update callback | Native evidence |
|---:|---|---|---|---|
| 30 (`0x1e`) | `PickupWait` | `0xde3160` calls `0xe20eb0` (`PlayerPickupWait`) | `0xde31a0` calls `0xe20f00` | State wrapper passes ID `0x1e`; row has Normal background, Heavy object mode, `stop_auto_save=1`. |
| 31 (`0x1f`) | `Pickup` | `0xde3360` calls `0xe21270` (`PlayerPickup`) | `0xde33a0` calls `0xe21490` | State wrapper passes ID `0x1f`; `0xe21490` references `Player_GetDemo` / `Get_Pickup`. |
| 32 (`0x20`) | `PickupGetDemo` | `0xde3560` calls `0xe220a0` (`PlayerPickupGetDemo`) | `0xde35a0` calls `0xe22220` | State wrapper passes ID `0x20`; `0xe22220` references `Player_GetDemo` / `Get_Pickup`. |

The entry wrapper pattern calls `dd7df0(state_id)`, invokes the state callback with the actor and `actor+0xffc` state context, then calls `dd8980(state_id)`. The matching update wrapper invokes its state update callback while the state is active. These edges establish state registration/use, not a complete input-target validator.

### Guarded path to the item slot writer

The original native direct-call chain from the `Pickup` update is:

```text
0xe21490 --[0xe21688]--> 0xe21e40
0xe21e40 --[0xe21e7c]--> 0xdb0450
0xdb0450 --[0xdb0608, guarded]--> 0xefab90
0xefab90 --[0xefabf8, guarded]--> 0xefac20
0xefac20 --[0xefad2c]--> 0xf987c0
```

`0xe21e40` receives the pickup-state context, checks a state-context bit, and passes a descriptor built from that context to `0xdb0450`. On one guarded branch, `0xdb0450` calls `0xefab90` with mode `1` and optional value `0`. `0xefab90` validates actor/descriptor context before invoking `0xefac20`. `0xefac20` resolves a typed runtime component (`0x17c`) and calls `0xf987c0` on its item view. `0xf987c0` scans the 20-record views, handles occupied/empty (`-2`, or `0xfffe`) slots and merge cases, then calls its record writer (`0xf98650`); its return value is propagated as a success bit.

`PickupGetDemo` has a second path: raw call site `0xe22928` in `0xe22220` invokes `0xefab90(actor, descriptor, 1, 0)`, which reaches `0xefac20` and `0xf987c0` under its own guards. Thus the slot writer is in the static path of both the pickup action update and its get-demo update. The existing native fixture for `0xf987c0` in the core item-loop report proves slot insertion for its controlled craft-result fixture; this report did not execute the pickup state or its guards.

The exact incoming item UID, source actor/item identity, and success result are still unresolved. The state context is passed as an opaque descriptor through these functions; the present indexes do not prove which world-item actor supplies it or what conditions make the guarded branch succeed in a live pickup.

### Collection checks and full-pocket exchange

`Player_GetDemo.bfevfl` entry `Get_Pickup` starts at event index 11. A reachable graph route checks `cLostItem`, checks an item unlock (`ItemUniqueId=3406`), checks collection kind and pickup-full AI state, then can reach event 7. Event 7 invokes `EventFlowActionUIItemSelectWindowHandling` with:

```json
{"FilterType":"cPickupFull","ItemUniqueID":65534,"ItemKindType":"","ItemFilterType":"","Mode":"cExchangeByPickup"}
```

The following system query is `EventFlowQueryUIResultMenuDecide`; the player actor exposes `PlayerGetDemoCollectStatus`, `PlayerGetDemoCheckItem`, and `PlayerHasExchaneableItem` queries. This proves a full-pocket exchange/collection-feedback path and its parameters. The decoded `Get_Pickup` route contains no `SetItemToPocket` or `DeleteTargetItem` action, so it does not establish the native insertion or world-item deletion transaction.

The separate `Player_PickupFullItem` flow contains target-specific full-inventory message entries. Native function `0xe015b0` references that flow and calls helper `0xe5ad90`, which has a `PlayerPickupEnable` string reference. This associates the pickup-enable gate with a full/error handler; it is not evidence that `PlayerPickupEnable` is the sole normal-pickup acceptance test.

### Counter and persistence boundary

`0xe21490` calls `0xda4370` at raw PC `0xe21a94`. The helper's string-reference set includes `PickUpFirst`, `FenceEditCount`, and `MoveFurnitureFieldCount`; its code selects among several type-dependent branches. This identifies a candidate pickup/stat notifier reached from the pickup update, but the available trace does not show that the `PickUpFirst` branch is selected or that a quest counter is incremented.

The `0xe21e40` continuation also reaches generic record-update helpers after the slot-writer branch. Their record type/key is not named in the native index, and no call was tied to world-actor deletion, respawn scheduling, a quest counter commit, or a serializer/flush/reload operation. The `stop_auto_save=1` state-table field is only a state setting; it is not a persistence proof.

## Remaining proof gaps

- Which interaction/input and target-availability predicates select `PickupWait` → `Pickup` for a specific field item.
- The mapping from the opaque pickup-state descriptor to the source world actor and item UID.
- A successful native pickup fixture covering the actor guards, `0xf987c0` result, and any full-pocket branch.
- Whether/when the source world actor is deleted, retained, or respawned after insertion.
- Whether `PickUpFirst` or another counter is actually selected and committed for a field pickup.
- The named save object, serialization operation, durable write, and reload result for the new pocket record.

## Reproduction and provenance

The investigation used the existing `index.sqlite` (`direct_calls`, `native_functions`, and `string_refs`), Capstone over `main/0.bin`, generated EventFlow JSON, and the decoded `PlayerStateParam` output. It did not rebuild Ghidra or edit any indexes/crosswalks.

Source hashes:

| Input | SHA-256 |
|---|---|
| ExeFS `main/0.bin` | `9c9b45d8e7a58706ca59e7244b3aebac2325ef98faa205e007974eeeb2f758e9` |
| `A_logic/main.elf` | `5bf707c3dc5dac0ad9635af7d336ec580f81c3f7876d0f55400d1900e3415d74` |
| `B_data/EventFlow/Player_GetDemo.bfevfl` | `b5ac3c44b5161615ed6b245fce3e9289c2f6d7b9ec186941ce9790ea624703fa` |
| `B_data/EventFlow/Player_PickupFullItem.bfevfl` | `757f28163719419d7fb606793c256d52bc42396676518933e442fe9a60175911` |
| `B_data/Bcsv/PlayerStateParam.bcsv` | `746619914744a62365b7b4cc74fd5b7fad169e78dffe74c3c03c726d3ea49b0d` |
| Decoded `Player_GetDemo.json` | `e937aee95d923bfbdde2e923e1783f5a9001a3d716768e06bde8f1212cd96052` |
| Decoded `collision_states.json` | `329ef1728c1737bf1a0fd9be9b6465b5abb694b6261c53389b25c5d1e576256d` |

The previous core item-loop proof remains the source for the controlled native behavior of `0xf987c0` and its explicit fixture limits: [CORE_ITEM_CRAFTING_LOOP_PROOF_20261107.md](CORE_ITEM_CRAFTING_LOOP_PROOF_20261107.md).
