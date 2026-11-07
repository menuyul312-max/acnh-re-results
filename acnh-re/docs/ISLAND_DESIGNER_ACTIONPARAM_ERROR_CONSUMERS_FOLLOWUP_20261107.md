# Island Designer action-parameter and error consumers, ACNH 1.0.0

This follow-up extends the existing [edit/apply trace](ISLAND_DESIGNER_EDIT_LOOP.md) with a native consumer chain for `FieldLandMakingActionParam`. The table now reaches a point/3×3 spatial check, a temporary four-layer 12×12 work grid, and a 3×3 output copy. These are real native calculations and local writes. The available evidence still does not join them to the canonical island grid, a world edit commit, an undo snapshot, or the save serializer.

The exact PCs, source hashes, direct-call results, field/cache details, EventFlow paths, module scan, and open joins are in the [machine-readable ledger](../output/ui_island/island_designer_actionparam_error_consumers_followup_20261107.json).

## ActionParam consumer path

The BCSV reader at `0x4f44c0` resolves column hash `0x7674c4d6` and stores the cached enum values in the cache global later read by `0x5330d0`. Its resolved values are `None`, `1x1`, and `3x3`; the original column name remains unknown. `0x531790` builds a row view from the shared LandMaking table context (`global + 0x3d0`), calls `0x5330d0`, and passes its result to `0x5318e0`. Value 2 makes `0x5318e0` form bounds one cell around the position and iterate that 3×3 region; value 1 takes a point check. This is evidence for a validation-footprint range, not a recovered original field name.

The same row view reaches `0x533400`, which has multiple callers in this subsystem (`0x531790`, `0x5318e0`, `0x531ba0`, `0x53e680`, and `0x53f100` among them). In the result-building path, `0x531ad0` initializes temporary contexts, calls the thunk at `0x53e4e0` into `0x53e4f0` with the decoded row, and—on success—calls `0x54dc70`. That helper copies a bounded 3×3 block of records to the caller-provided output object using 14-byte spacing; its helper copies 11 payload bytes at offsets 0–4, 6–10, and 12. The output shape is patch-like; its application to world state is not identified.

Inside `0x53e4f0`, `0x53ecd0` and `0x53f200` process a four-layer 12×12 integer work grid. The per-layer stride is `0x240` bytes, so each layer has 144 32-bit cells. `0x53ced0` writes a cell, and `0x53db10` stamps pattern values into the same local array. The helpers use 5 as an out-of-bounds/no-update sentinel. `0x53f890` also collects a 3×3 affected-position mask. Later helpers update derived records inside the same nested context.

This is stronger than the earlier state of the trace: it proves a table-driven footprint check and local work-grid mutation. It remains short of a canonical island-cell setter. The nearest outer function, `0x540a10`, calls the validator at `0x540a64`, but no incoming direct call or detected code-pointer-array target for `0x540a10` identifies how the active tool/input path invokes it. The toolkit lifecycle methods likewise remain unjoined to this consumer subgraph.

## Error rows and EventFlow

`FieldLandMakingError`'s signed-byte field hash `0x0b3be609` is read at `0xe323e0` with `ldrsb`. Its three direct callers are inside functions referencing `PlayerCliffMakerNGReady`, `PlayerLinecarReady`/`PlayerLinecarDeleteReady`, and `PlayerRiverMakerNGReady`. The value acts as an error-counter comparison threshold; it does not reveal the geometric cause or full validation rule.

The error handlers also read `AsCommand` at `0xe3a750` and `EventFlowEntryName` at `0xe3a890`, assemble a generic record, and invoke a dynamic method at `+0x18`. This proves an error-row-to-generic-dispatch path. Resolution of the event-flow entry and its runtime invocation are still open.

There are six parsed `Player.EventFlowActionPlayerOutfitFieldMakeToolKit` instances across the construction app, airport, and fitting-room flows. The construction app selects `cGround`, `cRiver`, and `cCliff`, then also uses `cOff`. The three Airport `LandMakingRemove_*` entry points reach `cOff` along both query branches. Those entries establish toolkit cleanup, not terrain rollback or undo. The `RemoveHistory` token remains in unresolved ActionParam column `0x75fee4b0`; its native getter is only reached through the row parser in the bounded direct-call scan.

## Module scan and remaining boundary

The available `rtld`, `subsdk0`, and `sdk` module images and their exported/import-resolution text contain no ASCII occurrences of the tested LandMaking/CliffMaker/RiverMaker/ConstructionLicense tokens. This only rules out those literal/export-name clues; it cannot exclude stripped code. The extracted set has no `nnSdk.nss` or `multimedia.nss` image.

The main unresolved joins are the outer tool/input dispatch into `0x540a10`, the identity of the 12×12 work-grid structure, the destination and meaning of the 3×3 output buffer, and the path from a successful result to world terrain refresh and save. No apply/commit/undo transaction is proven. The scan is static; it does not execute the game or mutate a save.
