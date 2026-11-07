# Residual Catalog Order and Eligibility Trace

This pass closes the variant-selection mechanics around `0x118a3d0`, `0x118a740`, and `0xeecc70`, then follows `CatalogMailSend` and `SystemMailSend` only through their record insertion boundaries. It separates the page's incoming item list from the `ItemCatalogType` table field: the list producer remains unknown, so this work does not claim that an item is orderable or that a message reaches an inbox.

## Catalog page: first registered body variant wins

**[NATIVE]** The indexed direct-call chain is `0x11829d0 → 0x118a3d0 → 0x118a740 → 0xeecc70`. The direct-call inventory has exactly one caller for `0x118a3d0` (`0x11829d0`), one for `0x118a740` (`0x118a3d0`), and three callers for the shared `0xeecc70` helper (`0x1179dd0`, `0x118a740`, `0x1355440`). These boundaries are recorded and checked by the new audit script.

`0x118a3d0` walks the item sequence supplied by its caller, skips the `-2` sentinel records, and validates each remaining record. Valid items go through `0x118a740`; if the validity helper fails, the caller copies the original record through. `0x118a740` builds body-pattern candidates with `0xeecc70` in ascending ordinal order, copies each candidate to its output, maps it through `0xab2940`, and tests the mapped bit in the page-associated `0x7d0`-byte view. A mapped candidate within the 16,000-bit bound whose bit is set exits the loop and remains the output. If none of the generated candidates has a set bit, the helper copies the original input record instead. Thus the list emitted here uses the **first already-set body-pattern variant**, or the unmodified item when there is no hit; it does not itself decide which base item records enter the caller's list.

**[NATIVE + TABLE]** `0xeecc70` resolves the input item's `ItemParam.RemakeID` (`0xcb5eb33f`) to `ItemRemake.UniqueID`, then uses `ItemRemake.ReBodyPatternNum` (`0xb0304b0d`) as the candidate count. For a positive count `N`, it generates ordinals `0..N-1`; the candidate mutator preserves the upper bits of the packed short and writes the ordinal into the low three bits. It does not read `ItemCatalogType` or `ReFabricPatternNum`. The native mapper then computes `RemakeID * 8 + ordinal` for item types whose `ItemKind` remake gate exposes that packed field.

The table join gives concrete candidate fixtures:

| `ItemCatalogType` | Item | `RemakeID` | Body count | Candidate ordinals | Mapper bit indices* |
|---|---|---:|---:|---|---|
| `Sale` | `FtrRailroad` | 197 | 3 | 0–2 | 1576–1578 |
| `NotForSale` | `FtrKatakataToy` | 102 | 5 | 0–4 | 816–820 |
| `NotSee` | `Layout_NpcBromide_NpcNmlAnt00` | 652 | 7 | 0–6 | 5216–5222 |
| `NotSee` | `ToolSmartphoneNormal` | 784 | -1 | none | none |

\* The indices are the mapper's possible bit positions for the listed Ftr rows. The app returns a variant only when its corresponding bit is set. `ToolSmartphoneNormal` illustrates the body-only scope: its table row has `ReBodyPatternNum=-1` while `ReFabricPatternNum=7`, so this candidate builder emits no body candidates for it. That does not rule out a separate fabric-pattern path elsewhere.

**[TABLE + NATIVE]** `ItemRemake` has 654 rows. Twenty-four have `ReBodyPatternNum=-1`; the other 630 contribute 2,549 distinct body-pattern ordinal slots. The distribution and per-category breakdown are in [the generated artifact](../output/gameplay/catalog_order_remainder/catalog_order_remainder_static.json). `ItemParam` has 8,208 rows: 5,778 `Sale`, 1,043 `NotForSale`, and 1,387 `NotSee`. Among the 1,044 rows with a nonnegative `RemakeID`, the categories are 348 `Sale` rows / 348 IDs, 283 `NotForSale` rows / 283 IDs, and 413 `NotSee` rows / 23 IDs.

The 413 `NotSee` rows are highly concentrated: 391 `Bromide` records share `RemakeID=652`, whose joined `ItemRemake` row has seven body patterns and `ItemUniqueID=6426`. Their `ItemKind` is `Bromide` (`ItemRemakeType=Ftr`, `CanFtr=1`); the mapper key ignores their distinct `ItemParam.UniqueID` values and uses `RemakeID` plus the low-three-bit ordinal. Consequently these rows map to the same seven candidate-bit positions, 5216–5222. This is a native key-alias result, not evidence that the 391 records occur in the app's incoming list.

## `ItemCatalogType` and the `NotSee` gate

**[NATIVE]** The resolved enum values are `Sale=0`, `NotForSale=1`, and `NotSee=2`; the field hash is `0xdaf0238c`. Function `0xa25760` reads that ItemParam field into a derived cache. The variant-selection path `0x118a3d0 → 0x118a740 → 0xeecc70` does not read `ItemCatalogType`, but the upstream page builder does have a separate category gate.

**[NATIVE]** `0x11829d0` passes literal `2` to bitset filter `0x293cd0` for page selectors 1–3 and 4. The filter builds a callback through `0xa0fdc0`; the relocated code-pointer sequence at `0x30c6398` resolves to `0xa105d0`. That callback resolves each candidate with `0xa9c290` and calls `0xab3160`, which compares the cached `ItemCatalogType` against the closure selector. Therefore the filter's literal `2` is proven to mean `NotSee`, and matching set bits are cleared from the base bitmap. Invalid item handles are also cleared. The callback disassembly, source hashes, and call boundaries are in [the focused gate artifact](../output/gameplay/catalog_order_remainder/catalog_notsee_gate_static.json).

**[NATIVE]** Selectors 1–3 dispatch through `0x118a2e0` to `0x1188cc0`, `0x1188fe0`, or `0x11896d0`. Their ELF disassembly scans the existing 15,000-bit set and the explicit bitmap writes are clear-only (`word &= ~bit`); the common tail enumerates the surviving bits into records before resolving variants. This preserves the `NotSee` exclusion through final item-list construction for selectors 1–3.

**[LIMIT]** Selector 4 scans up to 64 stored item records and calls `0x1189c70` to add runtime entries after the `NotSee` gate. The category of those additions and the final mask behavior remain unresolved, so final-list exclusion is not proven for selector 4. Selector 0 uses an unresolved jump-table path. Item price, order limits, and whether the selected representative variant becomes the purchase payload also remain unknown.

## Mail record insertion boundaries

**[EVENTFLOW]** In `Obj_RcoMachine:RcoMachineOnlineShopping`, `UICatalogHandling` branches on `IsDeliveryToOthers`. The `DeliverVillager` path chooses a resident, edits and saves the `cMsgCard` UI result, then invokes `CatalogMailSend` and resumes with `IsSent=true`; cancellation resumes with `IsSent=false`. The EventFlow inventory has one `EventFlowActionCatalogMailSend` use in `Obj_RcoMachine`. The class audit associates its handler with factory `0x450570`, constructor `0x33a510`, and vtable `0x304c208`. A class-specific method `0x33a570` references `SendLetter` and calls `0xf62e90` and `0xf73ea0`, but its precise vtable-slot role is unresolved.

**[NATIVE]** The `0xf62e90` path obtains a `0x54a8` view at player offset `+0x169d0` and calls `0xf62c00`. That helper updates a keyed count at view offset `+0xe98` and writes added records into the region starting at `+0x2298` with `0x18`-byte stride. The catalog method also opens a destination view of size `0x13418` and calls `0xf73ea0` to copy selected fields into it. This is the static player-associated state/copy boundary reached by the handler association; it does not identify a recipient inbox, delivery clock, or arrival condition.

`SystemMailSend` is a separate EventFlow action. The index contains 50 uses across 13 flows: 15 specify `cFastToday` and 35 `cFastTomorrow`; none of those indexed uses specifies `cSlowRetry`. Its method `0x345890` builds a record with `0xac77a0`, maps the route at `0x27ccd0`, then dispatches at `0x346a50`. The two observed routes go through `0xac7070` to save-backed slot writers (`0xfaabf0` for mode 1 / today, `0xfaa3f0` for mode 2 / tomorrow). The static `cSlowRetry` branch tries `0xac1ff0` before its mode-3 fallback writer `0xfaaeb0`. This stops at queue/collection insertion, as mapped in [the HHA follow-up](HOUSE_HHA_FOLLOWUP.md); it does not prove mailbox visibility or receipt.

## Reproduction and remaining work

The generator reads the native index and resolved table JSON without modifying either input, checks the direct-call boundaries above, and writes only the new artifact:

```sh
python3 acnh-re/tools/catalog_order_remainder_audit.py \
  --index /workspace/acnh-re/output/index.sqlite \
  --tables-root /workspace/acnh-re/output/tables_resolved
```

Before rebuilding the aggregate artifact, regenerate the focused NotSee-gate trace with `PYTHONPATH=/workspace/acnh-re/.deps python3 acnh-re/tools/catalog_notsee_gate_audit.py`; it reads the matching 1.0.0 `main.elf`, native index, and relocated code-pointer inventory. Remaining catalog evidence includes the post-filter helper composition, exact order-price/quantity rules, purchase payload handling, save serialization, mailbox consumption, and actual delivery timing. The aggregate artifact also records the mail action inventories and exact static boundaries found so far.
