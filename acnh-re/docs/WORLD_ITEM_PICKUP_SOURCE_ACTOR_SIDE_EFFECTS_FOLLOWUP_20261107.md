# World-item pickup source actor and side effects (2026-11-07)

**Build:** ACNH 1.0.0. **Addresses:** raw ELF virtual addresses/offsets in `main/0.bin`; generated Ghidra labels use an image base `+0x100000` (for example, raw `0xe21e40` is displayed as `FUN_00f21e40`). This is a static follow-up to [the pickup interaction report](WORLD_ITEM_PICKUP_INTERACTION_FOLLOWUP_20261107.md). No Ghidra rebuild or runtime pickup fixture was used.

## Result

The ordinary pickup state passes an item descriptor from the player object field at `Player+0x1018` into its state context at `+0x1c`; the pickup update later passes that state-context descriptor to the guarded item insertion helper. This narrows the descriptor's producer, but does **not** identify the source world-item actor or prove that this field is the actor's authoritative item record. The traced post-insertion calls remain player/item-view bookkeeping; no direct world-object deletion or respawn call was found in this bounded call graph.

A shared notifier reached from the `Pickup` update has a conditional branch that writes the named property `PickUpFirst` to value `1`. The setter and key are directly evidenced, but the branch predicate does not establish that a normal field-item pickup selects it, nor that the property is a durable statistic or incrementing counter.

## Descriptor producer and insertion path

The relevant data path is:

```text
PlayerPickupWait update 0xe20f00
  ├─ [0xe21000] -> 0xe07ae0: copies its input descriptor to state context +0x1c
  └─ [0xe211e0] -> copies the constructed descriptor to state context +0x1c
PlayerPickup update 0xe21490
  └─ [0xe21688] -> 0xe21e40
       ├─ [0xe21e68] reads the state descriptor at context +0x1c
       ├─ [0xe21e7c] -> 0xdb0450 (guarded insertion preparation)
       │    └─ [0xdb0608] -> 0xefab90 (guarded)
       │         └─ [0xefabf8] -> 0xefac20 (guarded)
       │              └─ [0xefad2c] -> 0xf987c0 (shared slot writer)
       ├─ [0xe21f10] -> 0xefc2f0 (player item-view update)
       └─ [0xe21f1c] -> 0xdafee0 (player/item-view side effects)
```

`0xe20f00`'s `PickupWait` branch copies the object field `Player+0x1018`, parses the copied item value through `0xb9c290`/`0xb9f670`, and stores it in the next state context. On the branch at `0xe21000`, helper `0xe07ae0` writes the supplied descriptor to `state+0x1c` at `0xe07b1c`. On another branch, `0xe20f00` writes the constructed descriptor to `state+0x1c` at `0xe211e0`. The active `Pickup` update at `0xe21e40` reads that field and sends it into `0xdb0450` at `0xe21e7c`.

The copied field is a player-side item descriptor, not a traced source-actor pointer: the visible producer stores item data in the player state, and the insertion bridge receives the player actor handle plus this descriptor. The scan did not resolve a world actor ID/handle, a target-object component, or a descriptor-to-source-actor lookup. The item helpers and guards also prevent inferring a runtime UID or successful insertion from static reachability.

## Post-insertion side effects and deletion scan

The guarded shared writer `0xf987c0` is reached through `0xefac20` only after its checks. On its success path, `0xefac20` conditionally calls `0xeec280`, then mode-specific `0xefadc0` or `0xefaf00`, and `0xefb090`. The decompilation of these helpers shows item-view/property updates through the player-side components at `actor+0x70` (component `0x17c`) and `actor+0x1a78` (component `0x8b8`). The follow-up after `0xe21e40` also calls `0xefc2f0` and `0xdafee0`; these resolve/update the same player-side item view and apply item-param bookkeeping. They do not receive an identified source world actor.

One unresolved boundary remains inside `0xdb0450`: at `0xdb0540` it obtains a manager/result from `0xeecf60`; when non-null it resolves a component at offset `+0x2d8`, type `0x280`, and calls `0xf6a450` with the item descriptor. The static output does not identify this component as the source object and does not show that method deleting or respawning it. This is an indirect/runtime-manager candidate, not proof of world-item removal.

I found no direct call to a named world-actor destroy, detach, remove, or respawn routine in the inspected pickup call graph (`0xe20f00`, `0xe07ae0`, `0xe21490`, `0xe21e40`, `0xdb0450`, `0xefab90`, `0xefac20`, `0xdafee0`) or the reachable `Player_GetDemo:Get_Pickup` EventFlow branch. That branch remains post-get feedback and full-pocket exchange (`FilterType=cPickupFull`, `Mode=cExchangeByPickup`); it has no `DeleteTargetItem` or `SetItemToPocket` action. This negative is bounded: an unresolved indirect method, actor-manager dispatch, or external world-item lifecycle handler could still perform removal.

## `PickUpFirst` property branch

The pickup update calls the shared notifier `0xda4370` at PC `0xe21a94`. `0xda4370` also has direct callers at `0xe22054` (`0xe21fb0`), `0xe07f6c` (`0xe07c70`), `0xe08370` (`0xe082c0`), `0xe3cd08` (`0xe3ca10`), and `0xe3d170` (`0xe3d0b0`), so it is shared by neighboring item/action handlers.

In `0xda4370`, the branch after the `0xf25d00` and `0x1059370` checks calls `0xf4a8f0` at `0xda4454` with the key string `PickUpFirst` (string VA `0x029d183a`) and value `1`. `0xf4a8f0` resolves the object's property component at `+0x16998` (component type `0x1000`) and dispatches to `0xf4a9a0`; that helper compares the old value and writes the supplied value when it differs. The same notifier has other type-dependent named paths for `FenceEditCount` and `MoveFurnitureFieldCount`.

This proves a conditional in-memory `PickUpFirst=1` property write reachable from `Pickup`. It does not prove the notifier branch is selected for a normal dropped item, that it increments a count, or that this property is committed to durable save data. The separate `PickUpFirst` string reference in `0x1214110` is not joined by this trace to the pickup transaction.

## Remaining gaps

- Identify the field-item actor and the interaction/target handle that supplies the `Player+0x1018` descriptor.
- Resolve the `0xeecf60` / component `0x280` / method `0xf6a450` indirect path and any external actor-manager dispatch.
- Establish whether insertion success triggers source-object deletion, a retained state, or respawn scheduling.
- Execute or otherwise obtain a native fixture that shows the `PickUpFirst` predicate and its actual behavior for an ordinary field pickup.
- Link the property write and pocket mutation to serialization, durable write, and reload behavior.

## Provenance

The evidence uses `index.sqlite` direct-call/native/string-reference indexes, the existing decompilation files for the listed raw addresses, raw `main/0.bin` disassembly context, and the decoded `Player_GetDemo.json` EventFlow. Existing build hashes: `main/0.bin` SHA-256 `9c9b45d8e7a58706ca59e7244b3aebac2325ef98faa205e007974eeeb2f758e9`; `A_logic/main.elf` SHA-256 `5bf707c3dc5dac0ad9635af7d336ec580f81c3f7876d0f55400d1900e3415d74`; decoded `Player_GetDemo.json` SHA-256 `e937aee95d923bfbdde2e923e1783f5a9001a3d716768e06bde8f1212cd96052`.
