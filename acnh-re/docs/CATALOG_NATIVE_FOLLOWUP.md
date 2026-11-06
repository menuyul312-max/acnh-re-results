# Catalog Bitset Native Follow-up

## Proven setter behavior

The native function at `0xeecad0` is the item catalog bit setter. It first calls `0xab2940` with the supplied item ID; the mapper's result is then used as the catalog bit index. A result of `0xffffffff` returns `0` without opening the bitset wrapper. Otherwise, the function obtains the catalog context at world offset `+0x10d8`, requests a `0x7d0`-byte view, and sets the mapped bit when the index is less than `0x3e80` (16,000). The setter returns `1` for every non-sentinel mapper result, including indices outside that range.

`tools/catalog_bitset_native.py` runs the original `0xeecad0` instructions for indices `0`, `31`, `32`, `15999`, `16000`, and `0xffffffff`. It checks the return value and all 500 words of the 2,000-byte bitset. The six controlled cases have zero mismatches. The test stubs the item-to-index mapper and the context/bitset wrapper calls; it proves the native bit operation and boundary behavior, not the actual item mapping.

Run it with:

```sh
PYTHONPATH=/workspace/acnh-re/.deps python acnh-re/tools/catalog_bitset_native.py
```

The generated record is `output/gameplay/catalog_bitset_native.json`.

## Static trigger evidence and open work

- `0xeec010` references `MarketBuiltMyVillage` and `FillCatalog`, then invokes the catalog fill writer when those checks pass.
- `0xeec0b0` and `0xeec280` call `0xeecad0` on conditional acquisition paths and update a second item bitset through `0xf57920`/`0xf57880`. Their exact conditions and bitset meaning still need a complete caller-level trace.
- `0x118a8a0` writes `BuyItem`, `HowmuchBuyItem`, and `BuyItemCatalog` achievement counters from a purchase-page callback. This proves the page's achievement updates, not delivery or mailbox timing.
- `0xa1bda0` references mailbox/critter-book catalog strings, but the mailbox catalog's save transitions and delivery behavior remain unresolved.

The larger catalog queue item remains open. Concrete item-to-index mappings, all acquisition triggers, save persistence, Nook Shopping order eligibility, and mailbox delivery require additional tracing and controlled native cases.
