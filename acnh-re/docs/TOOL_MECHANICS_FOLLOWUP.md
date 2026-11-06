# Tool mechanics follow-up

Scope: the native `PlayerToolBreak` path, the ItemParam identity lookup it calls, and the available action-state evidence for axe, shovel, net, fishing rod, slingshot, watering can, and tool ring. The work uses the game 1.0.0 main NSO and the indexed source tables/EventFlow. It does not establish a per-tool use limit or durability decrement.

## Break path and counters

Native `PlayerToolBreak` at `0xe37a50` directly calls `0xf58d00` at `0xe37d34`; the latter directly calls the dense ItemParam resolver at `0xa1e8c0`. The reproducer reconstructs the dense UniqueID-to-row index from the source ItemParam BCSV and calls the original `0xf58d00` in the NSO. All 32 selected Axe/Shovel/Net/FishingRod/Slingshot/Watering UniqueIDs resolve, while controls `79`, `12354`, `65534`, and `65535` do not. It records no input item-word changes and no unresolved native imports. This proves the lookup accepts the source tool IDs as ItemParam entries; the helper does not expose durability.

The observed writes in `PlayerToolBreak` increment player-state memory at byte offset `+0x898` on two branches. The `BreakTool` action at `0xe37830` clears `+0x898` and byte `+0x89c`. These are state-local fields in this handler pair; the source does not identify them as a packed-inventory use count, nor does this evidence show an inventory durability decrement or break threshold.

`Player_ToolBreak.bfevfl` has Axe, Scoop, Watering, Net, Slingshot, and FishingRod entries. All entries set the player item-name tag and show `TalkSys/SYS_Player:290`; the Axe entry additionally checks recipe ownership for ItemUniqueID `9617`, checks `cPlayer:GoldenAxeLearningCount` at Border `99`, and can add `1` to that counter or queue the Golden Axe recipe demo. The flag definition calls it a Golden Axe recipe-learning counter (max `200`, default `0`), so it is not evidence of axe wear. The separate `cLifeSupportAchievement:BreakTool` flag is named “broke a tool” and has max `1`, but the indexed 1.0.0 EventFlow has no writer; whether native code writes it remains unresolved.

The named ItemParam columns contain no durability, break-count, use-count, or uses field. Hash-named columns remain unresolved and are not assigned durability semantics without a native consumer. Therefore a claim such as “tool X breaks after N uses” is still open.

## Per-family action evidence

“Proven” below is limited to the stated static identity/state/handler evidence. “Open” means the world or inventory result has not been connected. The native action anchors are function/string-reference matches in the indexed main NSO; they are not full action simulations.

| Family | Proven | Open / blocker |
| --- | --- | --- |
| Axe | Four ItemParam rows; `AxeReady`, `AxeReadyWait`, and `AxeHitTree` state rows; native handler strings `PlayerAxeHitTree` and `PlayerAxeDullHitTree` at `0xe36ec0`; Axe break recipe-learning flow. | Tree-hit/drop result and any inventory or durability mutation. |
| Shovel | Six ItemParam rows; six `Scoop*` state rows; handlers identified by `PlayerScoopDig`, `PlayerScoopBury`, and `PlayerScoopDigGetDemo` references at `0xe52390`, `0xe52850`, and `0xe541a0`. | Dig/bury world result and any inventory or durability mutation. |
| Net | Six ItemParam rows; `NetWait`, `NetSwing`, `NetGetDemo`, and `NetRelease` state rows; `CommonNetSwing` and `PlayerNetGetDemo` handler references. | Capture eligibility, caught-insect inventory result, and any durability mutation. |
| Fishing rod | Six ItemParam rows and eleven rod state rows; native casting, wait, catch, and get-demo handler references at `0xe4bb10`, `0xe4d420`, `0xe4dd40`, and `0xe4e730`. | Bite/catch/release output, inventory result, and any durability mutation. The get-demo function also references `CatchFishContinuously`/`CatchFishContinueCount`, but that alone does not establish the catch result or rod wear. |
| Slingshot | Four ItemParam rows and four state rows. `PlayerSlingshotShooting` at `0xe564b0` calls `0x803690`; static decompilation shows that consumer writes projectile start/direction state and scales the supplied velocity components by `6`. | Projectile creation/collision and dropped-item result, plus any inventory or durability mutation. This is a mapped launch handoff, not a reproduced shot. |
| Watering can | Six ItemParam rows; `Watering` state row; `CommonWatering`/`CommonWateringUpperLevel` handler references at `0xe585c0`. | Plant watering mutation, flower response, and any durability mutation. |
| Tool ring | Native menu registry at `0x15566b0` contains `cRingMenuToolsMain` as ordinal `2`. `RingMenuTools.byml` identifies the UI layout. RomFS `LRingMenuTools` contains eight `Inv0`–`Inv7` nodes; `LRingMenuToolsBtn` contains selection, confirm, and equip animation resources. | Runtime item-to-slot mapping, selection handler, and the selected tool’s resulting action are not present in these layout assets. This mapping remains blocked on a source that connects the UI slots to inventory items. |

`0xdd9a60` is the player-state constructor/registry with strings for the listed tool states. It supports the state-name mapping above; it is not a durability calculator. `PlayerStateParam` rows likewise describe state configuration, not proof that a given world mutation or inventory update occurs.

## Reproduction and inputs

From this worktree, run:

```sh
PYTHONPATH=/workspace/acnh-re/.deps python3 acnh-re/tools/tool_mechanics_followup_native.py
```

The script reads the shared NSO symlink and read-only research tables, invokes the native lookup without stubbing its imports, checks the negative controls, parses the break flow and tool-state rows, and hashes/checks the three compressed RomFS ring layouts. It writes [tool_mechanics_followup_native.json](../output/gameplay/tool_mechanics_followup/tool_mechanics_followup_native.json). Latest result: `36` native lookup cases, `0` mismatches; family counts Axe `4`, Shovel `6`, Net `6`, FishingRod `6`, Slingshot `4`, Watering `6`; state rows `3`, `6`, `4`, `11`, `4`, and `1` respectively; ring page ordinal `2`, with all eight inventory nodes found.

Source checksums: main NSO `f8d248109ff72999b4600ae3749f8c7397fb960f7ad3ab8dee3018ae9e14e900`; ItemParam raw BCSV `89230e97fc877ff2b2b48ac1c707ef32b3a7760118839c307f19797e2553458c`; PlayerStateParam BCSV `746619914744a62365b7b4cc74fd5b7fad169e78dffe74c3c03c726d3ea49b0d`; Player_ToolBreak BFEVFL `5f2b1bb4a72cbed1e299c58b7de7eca8e08127b3a32d4102d613231141487033`; RingMenuTools BYML `3474fa03cd22c72f9258240b3ccb0e698a07c7631abbecd142346ffd2493b32e`. Compressed RomFS layout hashes and sizes are recorded in the JSON output.
