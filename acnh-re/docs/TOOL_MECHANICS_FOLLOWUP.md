# Tool mechanics follow-up

Scope: the native `PlayerToolBreak` path, the ItemParam identity lookup it calls, and the available action-state evidence for axe, shovel, net, fishing rod, slingshot, watering can, and tool ring. The work uses the game 1.0.0 main NSO and the indexed source tables/EventFlow. A follow-up has now identified the packed current-wear field, its increment/reset helpers, and all 32 tool-row `BreakDamage` limits; the exact threshold-to-break state dispatch and durable save flush remain open.

## Break path and counters

Native `PlayerToolBreak` at `0xe37a50` directly calls `0xf58d00` at `0xe37d34`; the latter directly calls the dense ItemParam resolver at `0xa1e8c0`. The reproducer reconstructs the dense UniqueID-to-row index from the source ItemParam BCSV and calls the original `0xf58d00` in the NSO. All 32 selected Axe/Shovel/Net/FishingRod/Slingshot/Watering UniqueIDs resolve, while controls `79`, `12354`, `65534`, and `65535` do not. It records no input item-word changes and no unresolved native imports. This proves the lookup accepts the source tool IDs as ItemParam entries; the helper does not expose durability.

The observed writes in `PlayerToolBreak` increment player-state memory at byte offset `+0x898` on two branches. The `BreakTool` action at `0xe37830` clears `+0x898` and byte `+0x89c`. These are state-local fields in this handler pair; the source does not identify them as a packed-inventory use count, nor does this evidence show an inventory durability decrement or break threshold.

`Player_ToolBreak.bfevfl` has Axe, Scoop, Watering, Net, Slingshot, and FishingRod entries. All entries set the player item-name tag and show `TalkSys/SYS_Player:290`; the Axe entry additionally checks recipe ownership for ItemUniqueID `9617`, checks `cPlayer:GoldenAxeLearningCount` at Border `99`, and can add `1` to that counter or queue the Golden Axe recipe demo. The flag definition calls it a Golden Axe recipe-learning counter (max `200`, default `0`), so it is not evidence of axe wear. The separate `cLifeSupportAchievement:BreakTool` flag is named “broke a tool” and has max `1`, but the indexed 1.0.0 EventFlow has no writer; whether native code writes it remains unresolved.

ItemParam has no named wear column, but it joins each tool row to `ItemOutfitInfo`. Native item helpers read the packed current `ToolDamage`, add/reset it, and expose `BreakDamage - ToolDamage`; `ItemOutfitInfo.BreakDamage` is the per-variant limit. The six unresolved ItemParam columns remain unclassified and are not needed for this mapping.

## Durability candidate audit

`tools/tool_durability_static_audit.py` records all six unresolved ItemParam fields, joins all 32 player-tool rows to ItemOutfitInfo, and captures the native helper call graph. Reproduce it with:

```sh
python acnh-re/tools/tool_durability_static_audit.py --index-db /workspace/acnh-re/output/index.sqlite --research-root /workspace/acnh-re/output
```

The native field reader is `0xaa7700`: after the ItemParam/ItemOutfitInfo eligibility path, it extracts the low 10 bits of the halfword at packed item-word byte offset `+6`. `0xaa77d0` adds a caller-supplied amount to those bits, clamps the result to `999`, and preserves the upper six bits; `0xaa79a0` clears only the low ten bits. `0xaa7ce0` returns the ItemOutfitInfo `BreakDamage` limit minus current damage. The table column has hash `0x68db76c2`, type `u16`, and row offset `42`; the exact hash is referenced by the native row-value helper `0xaa7b90`.

The four `ToolDamage` string references (`0xeadfa0`, `0xeae890`, `0xeb7d90`, `0xeb8690`) are event-record serializers. They open event IDs `0x15`, `0x16`, `7`, and `6` through `0xed3d30`, and write named fields through `0xed2620`/`0xed2600`; the same records include `ToolUniqueId` plus pop-item, tree, fish, or insect metadata. Their caller contexts are rock/tree/catch reporting. These are telemetry consumers of the item field, not its wear mutator. The actual mutator chain is `0xe893c0 -> 0xe895a0 -> 0xaa77d0`: the first wrapper passes increment `1`, while `0xe895a0` updates the packed descriptor and marks the selected player-item slot dirty (bit `0x4000`).

The ItemParam `ItemOutfitInfo` references and `ItemOutfitInfo.BreakDamage` values join for all 32 player-tool rows (the data artifact records each row):

| Family | ItemUniqueID : BreakDamage |
| --- | --- |
| Axe | `2100:100`, `3068:40`, `5856:100`, `9617:200` |
| Shovel | `2099:100`, `3082:40`, `8574:200`, `8575:100`, `8576:100`, `8577:100` |
| Net | `2376:10`, `5784:30`, `8176:30`, `8177:30`, `8178:30`, `8179:90` |
| Fishing rod | `2377:30`, `3084:10`, `8471:30`, `8472:30`, `8473:30`, `8660:90` |
| Slingshot | `2822:20`, `8578:60`, `8579:20`, `8580:20` |
| Watering can | `2379:60`, `3083:20`, `8533:180`, `8534:60`, `8535:60`, `8536:60` |

`tools/tool_durability_native.py` runs the original getter, incrementer, resetter, and remaining-damage helper over every one of these 32 table joins. It verifies threshold-minus-one has one point remaining, a native increment reaches the threshold and returns zero remaining, the field saturates at `999`, and reset preserves the reserved upper bits (96 item-level groups, zero mismatches). It also runs the original `0xe895a0` apply wrapper with UID `2100` at damage `99`: `0xaa77d0` copies damage `100` back into the packed word and the native wrapper sets only pocket slot `3` dirty bit `0x4000`. The item-view construction and item/pocket/cache accessors are bounded stubs; this is not a live inventory/save trace and does not exercise the break-state transition. Output: `output/gameplay/tool_mechanics_followup/tool_durability_native.json`.

The 1.0.0 `RodGetDemo` callsite passes `+2` only when the state field at `param+0x1038` is one of `4`, `5`, or `7` and the held ItemUniqueID compares equal to `3084` (`ToolFishingrodWood`); other branches pass `+1`. The code-level condition is resolved, while the user-visible meaning of those state values is not. `NetGetDemo` passes `+1`, as do the traced `0xe893c0` wrapper calls. The remaining wear gap is the exact transition from exhausted (`remaining == 0`) to `PlayerToolBreak`; state dispatch is partly indirect, and the tool-state runner has not executed a full action. The 1.0.0 static action map shows shovel routes and shared object-result routes entering `0xe893c0`, while net/rod and other action paths also pass through item-update wrappers; family-specific cadence for every action remains open. The packed item copy-back and pocket dirty bit `0x4000` are now executed through `0xe895a0` in a bounded native case; durable save serialization/flush is not exercised. `h_9ec34ed4` remains unclassified and is no longer needed to explain durability.

## Native break-counter requests

Two native paths tied to the break transition are now separated from durability claims:

- `0xe37830` (`BreakTool`) branches on byte `param+0x1024`; the zero branch calls `0xf62e90` with key `BreakTool` and increment `1`. The local flag index contains `cLifeSupportAchievement:BreakTool` (max 1) but no EventFlow writer. This supplies a native call site for the achievement key; the generic save-backed counter implementation was not executed here.
- `0xe37950` calls `0xda5450`, which constructs the key `BreakToolCount` and requests increment `1` through `0xce9340` only when the input descriptor's first byte is nonzero. `e37950` is used by the tool-break transition; `0xda5450` is also called from net and rod get-demo states, so its name alone does not prove when a break occurred.

`tools/tool_break_counter_native.py` runs the original `0xda5450` instructions for input flag values 0, 1, and 2. The generic writer `0xce9340` is stubbed to capture the request; zero emits none, while nonzero values emit exactly `BreakToolCount += 1` (3 cases, 0 mismatch). It does not execute the save mutation or prove that this counter is a durability value. Result: `output/gameplay/tool_mechanics_followup/tool_break_counter_native.json`.

`tools/tool_break_action_native.py` exercises the original `0xe37830` action with both values of its branch byte at `param+0x1024`. For zero, it observes `BreakTool += 1` at the `0xf62e90` helper boundary; for nonzero, it observes dispatch to `0xe37950`. Both cases clear the state-local `+0x898`/`+0x89c` fields. Context and trailing helpers are stubbed, so this does not execute the nonzero branch's `0xe37950 -> 0xda5450` chain or the save mutation. Result: `output/gameplay/tool_mechanics_followup/tool_break_action_native.json`.

**[TBL] Counter meaning:** `EventFlagsPlayerActivityParam` row `UniqueID=16` has `Key=BreakToolCount`, Japanese name `道具を壊した回数` (“number of tools broken”), and `MaxValue=64`. The native `0xda5450 -> 0xce9340` request therefore names an activity count for tool-break events; it is not evidence of a per-item wear value. This table/flag is separate from `cLifeSupportAchievement:BreakTool` (the one-time named achievement flag).

`tools/tool_break_transition_native.py` joins the action and counter evidence by running original instructions `0xe37830 -> 0xe37950 -> 0xda5450` through the `0xce9340` writer boundary. Six controlled cases pass with zero mismatches: the zero action branch does not call the counter chain; the nonzero branch requests `BreakToolCount += 1` when a controlled `0xeaace0` guard is nonzero, while a zero guard emits no request. The `0xce9340` save mutation, player animation/context, and guard producer are stubbed. This closes the native call chain to a named activity writer request, but does not establish the zero-remaining-to-break-state transition. Output: `output/gameplay/tool_mechanics_followup/tool_break_transition_native.json`.

## Net and rod result inventory insertion

The indexed direct-call map confirms that both `NetGetDemo` (`0xe45b80`, call at `0xe45dfc`) and `RodGetDemo` (`0xe4e730`, call at `0xe4ebd0`) call the shared `0xefec70` result-to-inventory helper. The helper validates the result word with the same `0xf58d00 -> 0xa1e8c0` ItemParam lookup used elsewhere, scans the active 20-entry inventory view for the first item ID `-2`/`0xfffe`, then dispatches the chosen slot and result word through `0xefee80 -> 0xf57ed0`. If all 20 slots are occupied, it writes the shared empty-item word to slot 0, calls `0xeffea0` to shift slots 1–19 left, and inserts the result at slot 19. The bounded native runner verifies this behavior for one insect and one fish; the original packed-word writer and compactor run against synthetic inventory memory.

`tools/tool_catch_inventory_native.py` reconstructs the 1.0.0 ItemParam resolver from the indexed BCSV and tests two valid result examples: Insect ID `582` (`FtrInsectAburazemi`) and Fish ID `328` (`FtrFishFuna`). Each is placed into every first-empty slot position `0..19`; all 40 cases pass, the selected 8-byte record receives the base result word, and every neighboring slot stays unchanged. Two more full-pocket cases pass: original slot 0 is evicted, original slots 1–19 retain their packed words at slots 0–18, and the catch is written to slot 19. The sandbox does not run game global constructors, so the full-pocket cases initialize global pointer `0x32d25e0` with a synthetic item word whose ID is `0xfffe`. `0xeebe80` catalog registration is captured but not executed. Player lookup and inventory-view selection are controlled, and optional item normalization is held at identity because its manager context is absent. This proves the shared insertion and full-pocket replacement behavior in the bounded in-memory view; it does not prove either caller produced the result, passed catch eligibility, or persisted the mutation. Output: `output/gameplay/tool_mechanics_followup/tool_catch_inventory_native.json`.

Both get-demo callers also reach `0xdb00f0` before inventory insertion (`0xe45cbc` in `PlayerNetGetDemo`, `0xe4ea70` in `ToolRodGetDemo`). `0xdb00f0` gates through `0xe895a0` and then calls `0xdafee0` on success; each caller later passes a temporary result descriptor to `0xefec70`. This maps the result-state handoff, but neither the caller's catch eligibility and result selection nor the writer behind the player/save data is executed by the bounded insertion probe. The runner records these callsites in `static_catch_result_preparation_calls`.

## Tool-ring selected-item slot read

In `0x1417f70`, native instructions form the stored index address at `page + 0x1b9f8`, load that value into `w2`, then call `0x11b7210`. The runner checks those instructions and the indexed direct-call chain. It executes the original `0x11b7210 -> 0xef7260 -> 0xf589e0` read/copy path with eight valid ItemParam tool words. For indices `0..7`, `0xef7260` computes `pocket_base + 0x3f00 + index*0x2450`, and `0x11b7210` reads the packed item word at record offset `0x2418`; all eight copied words match their source records. Output: `output/gameplay/tool_mechanics_followup/tool_ring_inventory_native.json`.

One ring-page refresh path (`0x11c2da0`) invokes a vtable getter via `0x11aee20` to fill a temporary set of nine item descriptors, then calls `0x11b67a0` with a context at `page+0x1f8` and the page's `+0x1bb38` index; it refreshes the page if that method reports a change. This traces a second ring-page index/data path, but it does not connect controller input to `0x1417f70`'s `+0x1b9f8` field or identify how the player-record pocket slots are initially populated.

This closes the runtime-index-to-pocket-record read. The accessor path is `0x11b7210 -> 0xef7260 -> 0xeab1f0`: `0xeab1f0` uses the supplied player-context mode and player index to resolve a per-player record, after which `0xef7260` applies the 8-slot address formula. That ties the slot read to a player record, but the exact 1.0.0 save serializer field for this region is not identified; the public `SavePlayerItemPocket` label is cross-version evidence only. The widget binder maps UI button suffixes to an internal pointer array, but callback setters `0x1416a00/0x1416a30` have no direct caller in the indexed call map, so the stored index is not traced back to a button event or controller input. The eight pocket records' assignment provenance, selected word's transfer into the held-hand object, and equip/action transition remain open. The internal selector permutation `[2,1,0,7,6,5,4,3]` is separately reproduced; its connection to the pocket records is not established.

## Per-family action evidence

“Proven” below is limited to the stated static identity/state/handler evidence. “Open” means the world or inventory result has not been connected. The native action anchors are function/string-reference matches in the indexed main NSO; they are not full action simulations.

| Family | Proven | Open / blocker |
| --- | --- | --- |
| Axe | Four ItemParam rows, all joined to `BreakDamage`; `AxeReady`, `AxeReadyWait`, and `AxeHitTree` state rows; native handler strings `PlayerAxeHitTree` and `PlayerAxeDullHitTree` at `0xe36ec0`; Axe break recipe-learning flow. | Which axe-result paths invoke the +1 wear wrapper and the exact zero-remaining break transition. |
| Shovel | Six ItemParam rows, all joined to `BreakDamage`; six `Scoop*` state rows; `PlayerScoopDig`, `PlayerScoopBury`, and `PlayerScoopDigGetDemo` at `0xe52390`, `0xe52850`, and `0xe541a0`; native get-demo route reaches `0xe893c0` with +1. | Dig/bury world result and the exact zero-remaining break transition. |
| Net | Six ItemParam rows, all joined to `BreakDamage`; `NetWait`, `NetSwing`, `NetGetDemo`, and `NetRelease` state rows; `NetGetDemo` calls `0xdb00f0` with +1 before `0xefec70`; insertion and full-pocket compaction are native-probed. | Catch eligibility/result selection, durable save write, and the exact zero-remaining break transition. |
| Fishing rod | Six ItemParam rows, all joined to `BreakDamage`; eleven rod state rows; `RodGetDemo` calls `0xdb00f0` with +1 or +2 before `0xefec70`; insertion and full-pocket compaction are native-probed. The +2 branch is conditioned by a rod/item predicate whose complete user-visible meaning remains open. | Bite/catch/release output selection, family-specific wear condition, durable save write, and the exact zero-remaining break transition. |
| Slingshot | Four ItemParam rows, all joined to `BreakDamage`, and four state rows. `PlayerSlingshotShooting` at `0xe564b0` calls `0x803690`; native probes confirm launch handoff scales velocity by `6`, with downstream launch flag `1`. | Projectile creation, collision, dropped-item result, and the path that applies the wear helper/break transition. |
| Watering can | Six ItemParam rows, all joined to `BreakDamage`; `Watering` state row; `CommonWatering`/`CommonWateringUpperLevel` handler references at `0xe585c0`. | Plant watering mutation, flower response, and the path that applies the wear helper/break transition. |
| Tool ring | Native menu registry at `0x15566b0` contains `cRingMenuToolsMain` as ordinal `2`. `RingMenuTools.byml` identifies the UI layout. RomFS `LRingMenuTools` contains eight `Inv0`–`Inv7` nodes; `LRingMenuToolsBtn` contains selection, confirm, and equip animation resources. Native binder `0x1424660` maps button indices `0..7` to an eight-entry UI pointer array at `this+0x5d8+index*8`. Constructor `0x14254f0` and lookup `0x1412770` reproduce the internal selector permutation `[2,1,0,7,6,5,4,3]`. In callback `0x1417f70`, the stored index at `page+0x1b9f8` is passed in `w2` to `0x11b7210`; native probes confirm indices `0..7` read and copy the packed word from the matching pocket record. | The mapping from UI nodes/controller input to the callback's stored index and the assignment of saved inventory items to pocket records remain open. The read does not establish transfer into the held-hand object, the equip transition, or the selected tool's resulting action. |

`0xdd9a60` is the player-state constructor/registry with strings for the listed tool states. It supports the state-name mapping above; it is not a durability calculator. `PlayerStateParam` rows likewise describe state configuration, not proof that a given world mutation or inventory update occurs.

The tool-ring binder's native path is visible in `0x1424f00 -> 0x1424660`: it builds the `/L_RingTool_00/L_Btn_` child path, resolves the UI node, parses the numeric suffix, rejects indices above 7, then stores the resolved pointer at `this+0x5d8+index*8` (`0x1424978`–`0x1424990`). The selected-item reader separately connects a callback index to the matching pocket record. Together these checks still do not connect `Inv0`–`Inv7` or those button nodes to the saved pocket contents or equipped ItemUniqueIDs.

The ring page constructor `0x14254f0` also initializes an internal eight-value lookup table at `this+0x1b980` to `[2, 1, 0, 7, 6, 5, 4, 3]`. Native lookup `0x1412770` maps each value back to its table index; the runner verifies all eight values plus the out-of-range sentinel (9 cases, 0 mismatch). This establishes an internal selector permutation, but the values' meaning and relation to player inventory are still open. See `tools/tool_ring_index_native.py` and `output/gameplay/tool_mechanics_followup/tool_ring_index_native.json`.

## Reproduction and inputs

From this worktree, run:

```sh
PYTHONPATH=/workspace/acnh-re/.deps python3 acnh-re/tools/tool_mechanics_followup_native.py
python3 acnh-re/tools/tool_durability_static_audit.py --index-db /workspace/acnh-re/output/index.sqlite --research-root /workspace/acnh-re/output
PYTHONPATH=/workspace/acnh-re/.deps:/workspace/acnh-re-github/acnh-re/tools python3 acnh-re/tools/tool_durability_native.py --research-root /workspace/acnh-re/output
PYTHONPATH=/workspace/acnh-re/.deps python3 acnh-re/tools/tool_catch_inventory_native.py
PYTHONPATH=/workspace/acnh-re/.deps python3 acnh-re/tools/tool_ring_inventory_native.py
PYTHONPATH=/workspace/acnh-re/.deps python3 acnh-re/tools/tool_slingshot_launch_native.py
```

The audit reads the external read-only index/tables and writes `tool_durability_static_audit.json`. The durability runner executes the original native wear helper instructions over all 32 joined tool rows; its eligibility/cache and threshold table getter are explicitly stubbed. Latest result: 96 grouped cases, zero mismatches, and no unresolved imports. The existing tool runner reads the shared NSO symlink and read-only research tables, checks the ItemParam positive/negative controls, parses the break flow and tool-state rows, and hashes/checks the three compressed RomFS ring layouts. It writes [tool_mechanics_followup_native.json](../output/gameplay/tool_mechanics_followup/tool_mechanics_followup_native.json). Latest result: `36` native lookup cases, `0` mismatches; family counts Axe `4`, Shovel `6`, Net `6`, FishingRod `6`, Slingshot `4`, Watering `6`; state rows `3`, `6`, `4`, `11`, `4`, and `1` respectively; ring page ordinal `2`, with all eight inventory nodes found.

Source checksums: main NSO `f8d248109ff72999b4600ae3749f8c7397fb960f7ad3ab8dee3018ae9e14e900`; ItemParam raw BCSV `89230e97fc877ff2b2b48ac1c707ef32b3a7760118839c307f19797e2553458c`; PlayerStateParam BCSV `746619914744a62365b7b4cc74fd5b7fad169e78dffe74c3c03c726d3ea49b0d`; Player_ToolBreak BFEVFL `5f2b1bb4a72cbed1e299c58b7de7eca8e08127b3a32d4102d613231141487033`; RingMenuTools BYML `3474fa03cd22c72f9258240b3ccb0e698a07c7631abbecd142346ffd2493b32e`. Compressed RomFS layout hashes and sizes are recorded in the JSON output.
