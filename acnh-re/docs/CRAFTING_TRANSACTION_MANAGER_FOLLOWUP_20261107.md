# Craft transaction manager and Apple gate follow-up

**Build:** Animal Crossing: New Horizons 1.0.0. **Status:** bounded source/native follow-up; no live save or game process. This report supersedes the row-pointer explanation in `CRAFTING_TRANSACTION_REMAINDER_20261107.md` and narrows the Apple result to the helper and fixture actually tested.

Evidence labels here are `[TBL]` source BCSV/schema joins, `[NATIVE]` original instructions executed in the Unicorn sandbox, `[NATIVE STATIC]` callsite/control-flow mapping, `[OPEN]` unproved joins, and `[CAT]` asset name candidates only.

The earlier `0xeff060` probe did not show a runtime Apple rejection. Its reconstructed item object carried a source ItemParam row pointer where the native accessor expected a dense ItemParam index. With the clean `inventory_requirements_native.install_item_tables` setup, Apple row pointer `0x5103c9d8` maps through `0x1665ea0` to dense index `495`; `0xaac730` then reads the mapped ItemKind field `SaveCountMaxNum=0`. This explains the zero predicate in this fixture. It does not establish why the game chooses that helper for any live recipe, nor that Apple is invalid as a material.

## Dense index and field semantics

The source ItemParam table has 8,208 rows. The clean install maps its `UniqueID` lookup to BCSV row pointers, installs the ItemKind table and row-ordinal cache, then publishes the manager globals. Native `0xa9c290` stores the actual ItemParam Apple row pointer at object `+0x10`. The call into `0x1665ea0` converts that pointer to dense row index `495`; `0xaac730` uses the resulting index in the ItemParam-to-ItemKind ordinal cache and reads the Fruit row.

| Source/native value | Result | Meaning established |
|---|---:|---|
| ItemParam Apple `UniqueID` | `2213` | Source item key |
| Apple ItemParam source row | `495` | Dense row ordinal |
| Object `+0x10` before conversion | `0x5103c9d8` | Pointer into installed ItemParam BCSV rows |
| `0x1665ea0` result | `495` | Dense ItemParam index |
| ItemKind | `UniqueID=51`, `Label=Fruit` | ItemParam-to-ItemKind join |
| Fruit `MultiHoldMaxNum` | `10` | Separate stack-limit field used by the existing inventory counter producer |
| Fruit `SaveCountMaxNum` | `0` | Exact field returned by `0xaac730` in the tested helper path |

The schema identifies `ItemKind.SaveCountMaxNum` as hash `0x0ce69142`, `u16` at offset `26`. `0xaac730` reads it and `0xaac910` returns its nonzero predicate. The native callsite is `0xf9e840` at `0xf9e874`; when the predicate is zero, that helper takes its return-zero branch at `0xf9ebf8`. `0xf9e410` calls `0xf9e840` at `0xf9e430` and branches at `0xf9e434` around its slot scan/count writes when it receives zero. The tested signed delta was `-1`; the fixture bytes stayed unchanged.

The callsite matters: `0xf9e410` is reached through `0xeff060`, the alternate per-material route in `0xee1420`. The selector-zero/default branch in `0xee1420` instead calls `0xee1060` for the material slots with mode argument `0` and null output pointer. Therefore the `SaveCountMaxNum=0` result is specific to this generic signed count-update path. It does not explain the default recipe-56 route or prove an in-game rejection.

Apple's ItemParam `ItemOutfitInfo` reference resolves to label `None`, row ordinal `30`; that ItemOutfitInfo row has raw `Storage` value `0`. Recipe 56's Pear, Cherry, Orange, and Peach rows resolve to the same reference/value. The external schema only declares `ItemOutfitInfo.Storage` as two-byte `RawData` (hash `0xc89fb7af`); this report assigns it no stronger semantic meaning. The separate `0xa9f140` query reached from `0xee1060` returned zero for each of the five fruit fixtures. That observation is not treated as a stack-count result, `SaveCountMaxNum` result, or proof that crafting rejects fruit.

## Original `0xee1060` fixture run

The runner reconstructs the additional ItemOutfitInfo manager used by `0xa9e440 -> 0xa774c0 -> 0xab9400`, alongside the ItemParam/ItemKind managers. The ItemOutfitInfo BCSV has 108 source rows (row size 144; raw SHA-256 `0a5544498bd41f7db79101f845d1007f47425510654d1a8ab82f00b679620aa9`). ItemParam's `ItemOutfitInfo` labels are converted into row ordinals at the native cache global. This removes the prior unmapped-manager fault at `0xab941c`.

RecipeCraftParam ID `56` has result item `975` and five required material rows, each amount `1`: Apple `2213`, Pear `2285`, Cherry `2287`, Orange `2214`, and Peach `2286`. The bounded runner calls original `0xee1060` once for each material with the matching recipe slot and default-mode arguments. The calls return `1`, have no unmapped accesses, and leave all observed pocket-record bytes unchanged. The fixture contains one synthetic pocket item word per material, but its A/B/C inventory count caches and the source-record producers feeding those caches are not initialized. A zero FreeParam word is recorded as fixture data only; it is not asserted to encode one unit. Thus this is **not** a faithful material-count fixture and no consumption is claimed.

The previous `0xee1420` branch probe remains useful for call routing: with its synthetic `+0x38` guard, `+0x3c==0` calls `0xee1060` for all six material slots; a nonzero selector routes the marked material through `0xeff060`. That probe stubs both per-material handlers and does not establish real UI payload-builder marker values. The controlled result-insertion cases in `crafting_transaction_branch_native.json` demonstrate result `975` insertion into a synthetic pocket only; they do not demonstrate a successful craft or a balanced material/result transaction.

The runner records direct call traces, the raw source table hashes, the Apple pointer-to-index conversion, the exact predicate/callsite probe, the ItemOutfitInfo mapping and every pocket write observed. Reproduction from the repository root (set `ACNH_SOURCE_ROOT` to the local decoded source dataset if it is not the sibling directory named `acnh-re`):

```sh
ACNH_SOURCE_ROOT=/path/to/acnh-re python acnh-re/tools/crafting_transaction_manager_followup_native.py
python -m json.tool acnh-re/output/gameplay/crafting_transaction_manager_followup_20261107.json >/dev/null
```

Analysis ELF SHA-256 is `5bf707c3dc5dac0ad9635af7d336ec580f81c3f7876d0f55400d1900e3415d74`; main NSO SHA-256 is `f8d248109ff72999b4600ae3749f8c7397fb960f7ad3ab8dee3018ae9e14e900`. Full machine-readable evidence is in [`crafting_transaction_manager_followup_20261107.json`](../output/gameplay/crafting_transaction_manager_followup_20261107.json), generated by [`crafting_transaction_manager_followup_native.py`](../tools/crafting_transaction_manager_followup_native.py).

## Remaining open joins and asset notes

- **OPEN:** The A/B/C cache constructor, component loaders, and source-record producer paths are now traced in [CRAFTING_INVENTORY_COUNT_CONTEXT_TRACE_20261107.md](CRAFTING_INVENTORY_COUNT_CONTEXT_TRACE_20261107.md). Bind those structural groups to named save members and combine the cold cache with the same original `0xee1420`/`0xee1060` transaction context and faithful pocket counts; the current one-word-per-item fixture does not do this.
- **OPEN:** Run the full original `0xee1420`/`0xeff060` transaction with the real `0xedf8e0` UI payload and a valid active player/view plus count manager. Do not infer a reject from this bounded run or replace a failed predicate with success.
- **OPEN:** Establish whether material deletions and result award are balanced under success, insufficient materials, cancellation, or interruption. No rollback/atomicity claim is supported here.
- **OPEN:** Follow in-memory pocket/recipe changes through SaveProc serialization, file write/flush, and reload. This probe never writes or saves material changes.

For the broader story item loop, see `CORE_ITEM_CRAFTING_LOOP_PROOF_20261107.md`; the workshop page factory is `0x1596020`, while live selection/confirm/cancel binding remains open. Workbench layout/animation candidates are `WorkBenchInfo`, `WorkBench`, and `WorkBenchBG` BFLAN; decode BFLYT as pane trees and BFLAN as animation-section data while retaining source identity. Recipe, item, structure, and world table mappings are source-backed BCSV joins; placement transforms and collision ownership remain open, and `.phive` collision sources are absent. Item models (`FtrWorkbench`, bridge/furniture `ResName` matches) and sound cues (`Npc_Diy_Hummer_*`, workbench decide/invalid) are catalog-only because the raw model/audio archives are absent. Preserve these as `[CAT]` candidates; no GLB or audio conversion is justified from the available files. Existing story, tool, NPC text, and asset conversion limits remain in `CORE_ITEM_CRAFTING_LOOP_PROOF_20261107.md` and `TOOL_MECHANICS_FOLLOWUP.md`.
