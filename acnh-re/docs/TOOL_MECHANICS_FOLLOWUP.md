# Tool mechanics follow-up

Scope: the native `PlayerToolBreak` path, the ItemParam identity lookup it calls, and the available action-state evidence for axe, shovel, net, fishing rod, slingshot, watering can, and tool ring. The work uses the game 1.0.0 main NSO and the indexed source tables/EventFlow. It does not establish a per-tool use limit or durability decrement.

## Break path and counters

Native `PlayerToolBreak` at `0xe37a50` directly calls `0xf58d00` at `0xe37d34`; the latter directly calls the dense ItemParam resolver at `0xa1e8c0`. The reproducer reconstructs the dense UniqueID-to-row index from the source ItemParam BCSV and calls the original `0xf58d00` in the NSO. All 32 selected Axe/Shovel/Net/FishingRod/Slingshot/Watering UniqueIDs resolve, while controls `79`, `12354`, `65534`, and `65535` do not. It records no input item-word changes and no unresolved native imports. This proves the lookup accepts the source tool IDs as ItemParam entries; the helper does not expose durability.

The observed writes in `PlayerToolBreak` increment player-state memory at byte offset `+0x898` on two branches. The `BreakTool` action at `0xe37830` clears `+0x898` and byte `+0x89c`. These are state-local fields in this handler pair; the source does not identify them as a packed-inventory use count, nor does this evidence show an inventory durability decrement or break threshold.

`Player_ToolBreak.bfevfl` has Axe, Scoop, Watering, Net, Slingshot, and FishingRod entries. All entries set the player item-name tag and show `TalkSys/SYS_Player:290`; the Axe entry additionally checks recipe ownership for ItemUniqueID `9617`, checks `cPlayer:GoldenAxeLearningCount` at Border `99`, and can add `1` to that counter or queue the Golden Axe recipe demo. The flag definition calls it a Golden Axe recipe-learning counter (max `200`, default `0`), so it is not evidence of axe wear. The separate `cLifeSupportAchievement:BreakTool` flag is named “broke a tool” and has max `1`, but the indexed 1.0.0 EventFlow has no writer; whether native code writes it remains unresolved.

The named ItemParam columns contain no durability, break-count, use-count, or uses field. Hash-named columns remain unresolved and are not assigned durability semantics without a native consumer. Therefore a claim such as “tool X breaks after N uses” is still open.

## Native break-counter requests

Two native paths tied to the break transition are now separated from durability claims:

- `0xe37830` (`BreakTool`) branches on byte `param+0x1024`; the zero branch calls `0xf62e90` with key `BreakTool` and increment `1`. The local flag index contains `cLifeSupportAchievement:BreakTool` (max 1) but no EventFlow writer. This supplies a native call site for the achievement key; the generic save-backed counter implementation was not executed here.
- `0xe37950` calls `0xda5450`, which constructs the key `BreakToolCount` and requests increment `1` through `0xce9340` only when the input descriptor's first byte is nonzero. `e37950` is used by the tool-break transition; `0xda5450` is also called from net and rod get-demo states, so its name alone does not prove when a break occurred.

`tools/tool_break_counter_native.py` runs the original `0xda5450` instructions for input flag values 0, 1, and 2. The generic writer `0xce9340` is stubbed to capture the request; zero emits none, while nonzero values emit exactly `BreakToolCount += 1` (3 cases, 0 mismatch). It does not execute the save mutation or prove that this counter is a durability value. Result: `output/gameplay/tool_mechanics_followup/tool_break_counter_native.json`.

`tools/tool_break_action_native.py` exercises the original `0xe37830` action with both values of its branch byte at `param+0x1024`. For zero, it observes `BreakTool += 1` at the `0xf62e90` helper boundary; for nonzero, it observes dispatch to `0xe37950`. Both cases clear the state-local `+0x898`/`+0x89c` fields. Context and trailing helpers are stubbed, so this does not execute the nonzero branch's `0xe37950 -> 0xda5450` chain or the save mutation. Result: `output/gameplay/tool_mechanics_followup/tool_break_action_native.json`.

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
| Tool ring | Native menu registry at `0x15566b0` contains `cRingMenuToolsMain` as ordinal `2`. `RingMenuTools.byml` identifies the UI layout. RomFS `LRingMenuTools` contains eight `Inv0`–`Inv7` nodes; `LRingMenuToolsBtn` contains selection, confirm, and equip animation resources. Native binder `0x1424660` maps button indices `0..7` to an eight-entry UI pointer array at `this+0x5d8+index*8`. Constructor `0x14254f0` and lookup `0x1412770` reproduce the internal selector permutation `[2,1,0,7,6,5,4,3]`. | These are UI/control indices; they do not establish which inventory item populates a ring position. The save/inventory slot-to-ring slot relation, selection/equip result, and selected tool’s resulting action remain open. |

`0xdd9a60` is the player-state constructor/registry with strings for the listed tool states. It supports the state-name mapping above; it is not a durability calculator. `PlayerStateParam` rows likewise describe state configuration, not proof that a given world mutation or inventory update occurs.

The tool-ring binder's native path is visible in `0x1424f00 -> 0x1424660`: it builds the `/L_RingTool_00/L_Btn_` child path, resolves the UI node, parses the numeric suffix, rejects indices above 7, then stores the resolved pointer at `this+0x5d8+index*8` (`0x1424978`–`0x1424990`). This closes the UI control's numeric indexing only. It does not connect `Inv0`–`Inv7` or those button nodes to inventory records or equipped ItemUniqueIDs.

The ring page constructor `0x14254f0` also initializes an internal eight-value lookup table at `this+0x1b980` to `[2, 1, 0, 7, 6, 5, 4, 3]`. Native lookup `0x1412770` maps each value back to its table index; the runner verifies all eight values plus the out-of-range sentinel (9 cases, 0 mismatch). This establishes an internal selector permutation, but the values' meaning and relation to player inventory are still open. See `tools/tool_ring_index_native.py` and `output/gameplay/tool_mechanics_followup/tool_ring_index_native.json`.

## Reproduction and inputs

From this worktree, run:

```sh
PYTHONPATH=/workspace/acnh-re/.deps python3 acnh-re/tools/tool_mechanics_followup_native.py
```

The script reads the shared NSO symlink and read-only research tables, invokes the native lookup without stubbing its imports, checks the negative controls, parses the break flow and tool-state rows, and hashes/checks the three compressed RomFS ring layouts. It writes [tool_mechanics_followup_native.json](../output/gameplay/tool_mechanics_followup/tool_mechanics_followup_native.json). Latest result: `36` native lookup cases, `0` mismatches; family counts Axe `4`, Shovel `6`, Net `6`, FishingRod `6`, Slingshot `4`, Watering `6`; state rows `3`, `6`, `4`, `11`, `4`, and `1` respectively; ring page ordinal `2`, with all eight inventory nodes found.

Source checksums: main NSO `f8d248109ff72999b4600ae3749f8c7397fb960f7ad3ab8dee3018ae9e14e900`; ItemParam raw BCSV `89230e97fc877ff2b2b48ac1c707ef32b3a7760118839c307f19797e2553458c`; PlayerStateParam BCSV `746619914744a62365b7b4cc74fd5b7fad169e78dffe74c3c03c726d3ea49b0d`; Player_ToolBreak BFEVFL `5f2b1bb4a72cbed1e299c58b7de7eca8e08127b3a32d4102d613231141487033`; RingMenuTools BYML `3474fa03cd22c72f9258240b3ccb0e698a07c7631abbecd142346ffd2493b32e`. Compressed RomFS layout hashes and sizes are recorded in the JSON output.
