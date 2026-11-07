# Crafting transaction remainder boundary

**Date:** 2026-11-07
**Scope:** Continue the open `crafting-diy` transaction item without changing the shared queue or earlier follow-up artifacts.

## Next boundary

The next useful native boundary is the material-removal wrapper `0xeff060` through its quantity helper `0xf9e410`, first for Apple item `2213` from `RecipeCraftParam.UniqueID=56`. The `0xee1420` branch probe now covers the pocket-full decision, the temporary material descriptor, and the controlled result-insertion route. It still replaces both per-material handlers, `0xeff060` and `0xee1060`, with no-op callbacks. A separate leaf probe already exercises signed quantity updates in `0xf9e410`; the missing seam is the wrapper's runtime item-data and player-view context.

The indexed original code has six `0xee1420 -> 0xeff060` call sites (`0xee14dc` through `0xee157c`) and six alternate `0xee1420 -> 0xee1060` call sites. `0xeff060` reaches `0xf9e410` at `0xeff0e4`. The earlier partial transaction attempt reached the original item lookup chain `0xa9e440 -> 0xa774c0 -> 0xab9400`, then faulted at `0xab941c` because its item-data manager global was null. It did not reach the quantity helper. The dump contains the source tables, but not that runtime manager graph.

The first follow-up fixture should reconstruct or reach the minimum item-data/index manager and player-view fields required by that chain, then let the original `0xaac730` stack predicate, `0xeff060`, and `0xf9e410` execute without forcing their results. Start with one Apple count change and verify the item ID remains unchanged; then cover all five row-56 materials and an insufficient-material control. Only after that should the complete `0xee1420` path be retried.

## Evidence and limits

The 08:41 branch artifact is at [crafting_transaction_branch_native.json](../output/gameplay/crafting_transaction_followup/crafting_transaction_branch_native.json). I reran its existing probe with its output redirected to the new remainder directory; the reproduced JSON is byte-identical to the 08:41 artifact. In the controlled 20/20 pocket fixture, the precheck copies Material1 (Apple `2213`) into the temporary descriptor passed to `0xefbd30`; the 19/20 control skips the precheck. The result descriptor (`975`) follows a separate path through `0xefab90 -> 0xefac20`. Controlled actor-resolution and registry responses let the native insertion helper mutate a fixture slot.

These runs use reconstructed synthetic player, manager, pocket, and actor-registry data. The fixture sets the entry halfword at `+0x38`, bypasses dynamic UI/event setup at `0xee1698`, stubs both material mutators and the made-recipe marker writer, and uses bounded view-method stubs. The controlled result-insertion follow-up also supplies an explicit no-match registry response. The earlier leaf probe patches `0xaac730` to return true. None of this uses a live game process or real player save.

The available `RecipeCraftParam`, `ItemParam`, and `ItemKind` inputs are internally hash-checked by the audit script. The original analysis ELF SHA-256 is `5bf707c3dc5dac0ad9635af7d336ec580f81c3f7876d0f55400d1900e3415d74`; the matching 1.0.0 main NSO SHA-256 is `f8d248109ff72999b4600ae3749f8c7397fb960f7ad3ab8dee3018ae9e14e900`. The valid shared index is `/workspace/acnh-re/output/index.sqlite` (SHA-256 `a78c7af27d37b8fd931bba8bc611623dacf7685cb6e8b4f827effa0765340aad`). The same-named index in this worktree is empty and was not queried. Full paths and table/blob hashes are recorded in [next_boundary_audit.json](../output/gameplay/crafting_transaction_remainder_20261107/next_boundary_audit.json).

## Reproduction

From the worktree root, reproduce the bounded native branch run into the new output directory, then rebuild the static provenance and call-site audit:

```sh
python3 acnh-re/output/gameplay/crafting_transaction_remainder_20261107/reproduce_branch_native.py
python3 acnh-re/output/gameplay/crafting_transaction_remainder_20261107/next_boundary_audit.py
```

The first command invokes the existing bounded native probe but redirects its output to the new directory, preserving the 08:41 artifact. The second reads the shared SQLite index in read-only mode, verifies input and table hashes, checks direct call sites, compares the reproduced branch JSON with the 08:41 artifact, and writes `next_boundary_audit.json`.

Material consumption through the transaction wrapper is still open. Cancellation, interruption, rollback/atomicity, the real `SaveSetFromUIResult cWorkCraft` UI payload, and the `SaveProc` serializer/write/flush path also remain open. This evidence does not establish complete crafting or durable save behavior.
