# Recipe 56 crafting callsite and transaction boundary

**Build:** Animal Crossing: New Horizons 1.0.0. **Date:** 2026-11-07. **Status:** static callsite/dataflow join plus existing bounded helper fixtures. This report does not claim a successful end-to-end craft.

## Result

Recipe 56 is concretely identified as the fruit basket: output item `975` (`FtrFruitbasket`), with one Apple `2213`, Pear `2285`, Cherry `2287`, Orange `2214`, and Peach `2286`. The source and native evidence connect its material-availability query, the `cWorkCraft` payload builder, transaction dispatcher, and result-insertion helper. They still do not demonstrate material debit and result award in one source-authentic player context. The bounded result insertion is real native code operating on a synthetic pocket; the material mutators were stubbed in that fixture.

## Recipe and requirement check

The `RecipeCraftParam` row for `UniqueID=56` names output `975`; `ItemParam` resolves it to `FtrFruitbasket` and points its `DiyRecipeID` back to `56`. Its five populated material slots each require one unit. The table joins and source hashes are recorded in [the machine-readable evidence ledger](../output/gameplay/crafting_transaction_followup/crafting_payload_builder_callsite_20261107.json).

The original cold availability checker `0xee0be0` reads the A and B structural counters and includes C when option bit 0 is enabled. Its recipe-56 fixture passes all five materials with C installed and reports Peach short when C is excluded or its source record is omitted. This checker populates availability state; it does **not** subtract items. Its A/B/C records are reconstructed fixture data and are not mapped to named save members.

## Original caller and payload

The `SaveSetFromUIResult cWorkCraft` handler at raw VA `0x3358c0` prepares a stack payload with `0xedf8e0`. At `0x335a60`, it passes the global context in `x0`, stack payload at `sp+0x128` in `x1`, recipe ID from `[x19+0xa]` in `x2`, action context in `x3`, and mode `1` in `x4`. At `0x335a64`, a zero builder result branches away; only success proceeds to `0xee1420` at `0x335aa8`, using the same payload.

Static code for `0xedf8e0` shows the recipe lookup and construction of the result descriptor plus six material records. The builder also clears a byte in the caller context and returns success after its table/context path completes. This callsite is direct raw ELF disassembly. The builder itself was not executed here with a complete original player-manager context.

## Material and result routes

`0xee1420` first requires a nonzero payload sufficiency byte at `+0x25`. Its payload selector at `+0x3c` chooses between six default `0xee1060` material calls and marked `0xeff060` signed-delta calls. The default call PCs are `0xee15a0`, `0xee15c4`, `0xee15e8`, `0xee160c`, `0xee1630`, and `0xee1654`; the alternate PCs are `0xee14dc` through `0xee157c`. A separate direct `0xee1060` fixture returned success for each of recipe 56's five fruit materials but left the synthetic pocket bytes unchanged and did not install the A/B/C count cache. It does not prove consumption.

A prior transaction-branch fixture exercised the route `0xee1420 → 0xefab90 → 0xefac20 → 0xf987c0`. With a controlled actor resolver and explicit no-match registry response, native code inserted result item `975` into a synthetic 19/20 pocket at slot 19. In the 20/20 synthetic case, a compaction path opened a slot and inserted `975` at slot 4. The same fixture stubbed both material mutators, set payload halfword `+0x38` to select a branch, and bypassed the real `0xedf8e0` builder. It therefore proves result insertion behavior under those controls, not a whole craft.

When all 20 synthetic pocket slots are occupied, a separate branch enters `0xee0ed0 → 0xefbd30 → 0xf99270`; the temporary descriptor is copied from Material1 (Apple `2213`). This is a conditional material-descriptor insertion/compaction path. Its gameplay purpose is unknown, so this evidence does not label it rollback or recovery.

## Fixture boundary, atomicity, and save identity

The partial `0xee1420` execution stopped at `0xab941c`: its synthetic setup left item-data global `0x32f3f78` / cell `0x354ce00` null, so the original lookup chain dereferenced an invalid pointer before it reached material processing or result award. That is a fixture limitation, **not** evidence that the game rejects recipe 56 or lacks materials.

No single execution has run the original requirement query, actual material debit, and result insertion with one source-authentic player context. No cancellation/interruption matrix tests whether material and result changes are atomic, and no rollback semantic has been proven. The inventory views observed by the native paths are not directly bound to a named local 1.0.0 SaveLand/player-pocket member. No serializer, file write/flush, or reload is joined to this transaction, so this report assigns no named save field and makes no durability claim.

## Reproduction and provenance

The raw main ELF SHA-256 is `5bf707c3dc5dac0ad9635af7d336ec580f81c3f7876d0f55400d1900e3415d74`; the supplied main NSO is `f8d248109ff72999b4600ae3749f8c7397fb960f7ad3ab8dee3018ae9e14e900`. Raw ELF VAs are used here; the supplied Ghidra pseudocode prints a `0x100000` image base (for example, raw `0xee1420` appears as `FUN_00fe1420`). Table, decompilation, index, and prior-probe hashes are in the [JSON ledger](../output/gameplay/crafting_transaction_followup/crafting_payload_builder_callsite_20261107.json).

The broader evidence remains in [the core crafting proof](CORE_ITEM_CRAFTING_LOOP_PROOF_20261107.md), [the inventory-count trace](CRAFTING_INVENTORY_COUNT_CONTEXT_TRACE_20261107.md), [the transaction-manager follow-up](CRAFTING_TRANSACTION_MANAGER_FOLLOWUP_20261107.md), and [the persistence boundary](CRAFTING_PERSISTENCE_TRANSACTION_BOUNDARY_20261107.md). The next closure needs one shared, source-authentic workbench/player context, actual accepting material-debit path, same-context result insertion, interruption controls, and a direct save-member-to-serializer trace.
