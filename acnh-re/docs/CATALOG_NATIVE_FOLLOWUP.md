# Catalog Bitset Native Follow-up

## Proven setter behavior

The native function at `0xeecad0` is the item catalog bit setter. It first calls `0xab2940` with the supplied item ID; the mapper's result is then used as the catalog bit index. A result of `0xffffffff` returns `0` without opening the bitset wrapper. Otherwise, the function obtains the catalog context at world offset `+0x10d8`, requests a `0x7d0`-byte view, and sets the mapped bit when the index is less than `0x3e80` (16,000). The setter returns `1` for every non-sentinel mapper result, including indices outside that range.

Static tracing of `0xab2940` recovers the mapper expression: it reads `ItemParam.RemakeID` through field hash `0xcb5eb33f` (the local schema identifies this as signed 16-bit `RemakeID`), rejects a negative value, then calls `0xf5ab10`. That helper returns `RemakeID * 8 + (byte_from_0xab0f50 & 7)`; if `0xab0f50` returns null, the low three bits are zero. The expression allocates eight possible catalog indices per `RemakeID`, consistent with the setter's 16,000-bit capacity. The meaning of each low-bit variant and the concrete item rows that select it are not established yet.

`tools/catalog_bitset_native.py` runs the original `0xeecad0` instructions for indices `0`, `31`, `32`, `15999`, `16000`, and `0xffffffff`. It checks the return value and all 500 words of the 2,000-byte bitset. The six controlled cases have zero mismatches. The test stubs the item-to-index mapper and the context/bitset wrapper calls; it proves the native bit operation and boundary behavior, not the actual ItemParam lookup. The mapper expression above is recovered statically from the NSO and the resolved local BCSV schema.

Run it with:

```sh
PYTHONPATH=/workspace/acnh-re/.deps python acnh-re/tools/catalog_bitset_native.py
```

The generated record is `output/gameplay/catalog_bitset_native.json`.

## Static trigger evidence and open work

- **[PSEUDO] Acquisition path:** `0xeebe80` validates/converts an item, conditionally calls `0xeecad0`, then passes through `0xf57920` and `0xf57880` for two additional `0x754`-byte bitset views. When the first helper reports no change and the second reports a change, it calls `0xeec010`. The call order is visible; the exact semantic meaning of each view and save-backed state is not established by this trace.
- `0xeec010` references `MarketBuiltMyVillage` and `FillCatalog`, then invokes the catalog fill writer when those checks pass.
- `0xeec0b0` and `0xeec280` call `0xeecad0` on conditional acquisition paths and update a second item bitset through `0xf57920`/`0xf57880`. Their exact conditions and bitset meaning still need a complete caller-level trace.
- `0x118a8a0` writes `BuyItem`, `HowmuchBuyItem`, and `BuyItemCatalog` achievement counters from a purchase-page callback. This proves the page's achievement updates, not delivery or mailbox timing.
- `0xa1bda0` is reached from the `0xa18db0` initialization chain and references the `MailboxCatalog` key, but the mailbox catalog's save transitions and delivery behavior remain unresolved.

The larger catalog queue item remains open. Concrete item-to-RemakeID/variant values, the meaning of the low three bits, all acquisition triggers, save persistence, Nook Shopping order eligibility, and mailbox delivery require additional tracing and controlled native cases.
