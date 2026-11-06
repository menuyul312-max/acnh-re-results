# Museum art and gyroid donation follow-up

This follow-up isolates the remaining art/gyroid question and adds native checks
for the live ItemParam key-to-kind adapter and the museum donation threshold.
Machine-readable details are in
[`native.json`](../output/gameplay/museum_art_gyroid_followup/native.json); the
reproduction is [`museum_art_gyroid_followup_native.py`](../tools/museum_art_gyroid_followup_native.py).

## What the captured build proves

- The original ItemParam lookup path (`0xa9c290` → `0x1665ea0` → `0xa9f670`)
  resolves each of the 8,208 local ItemParam `UniqueID` values to the same
  `ItemKind` recorded by the raw BCSV. The runner reports zero mismatches. The
  table-manager structures and generic item-view helpers are reconstructed or
  stubbed, so this validates the native key/row/field adapter, not a live game
  process or every item-flag variant.
- Blathers' captured hand-in filters (`OwlTentDonation0`, `OwlTentDonation1`,
  `OwlDonation`) allow ItemKinds 64/65/70, with `FossilUnknown` (71) only in
  specified tent/commentary filters. The native
  `EventFlowQueryOwlDonationItemType` method at `0x3d8d10` uses a seven-entry
  result table: ItemKind 65→4, 70→3, 71→2; other values in 64–71 return 0.
  This is a static native/rodata mapping; EventFlow callback execution was not
  emulated.
- The local `ItemParam` has 8,208 rows and zero nonzero `FakeArtConvertId`
  values. The captured extracted tables include six `Museum*` tables (fossil
  donate info, NPC layout/silhouette/spot-talk, nameboard, and watch-point),
  and none is art-specific. Across the 456 decoded EventFlows, the museum
  hand-in filters found in the data do not admit the general furniture
  ItemKind. This is evidence that an art-item path is not present in the
  captured build/data set; it does **not** prove that all ACNH releases lack
  art donations.
- The located Gyroid flow is
  `B_data/EventFlow/Obj_Gyroid_BuildDonation.bfevfl`. It uses the
  `RcoBuildBridgeSlopeStatusCounter` key and public-works Bell/name/update
  actions. It has no museum access keys and does not call the museum save
  writer. Thus this flow is a bridge/slope project contribution flow, not a
  museum gyroid intake flow. The current extracted ItemKind/filter evidence
  does not establish a separate gyroid museum submission path.
- The native museum threshold query at `0x416260` and counter at `0xf773f0`
  were run against reconstructed synthetic SaveMuseum records. All 12 cases
  matched: below/at/above a threshold and exclusion of unsupported ItemKinds.
  The counter scans 1,024 records and counts only Fossil 70, Fish 65, and
  Insect 64. In the tent expansion EventFlow, `Border=20` and case 0 means
  `count >= 20`; that path opens the museum-expansion dialogue and sets
  `cLand:MuseumGrowupEnable1`. The daily `FutaReadyForMuseum` transition and
  MuseumLevel update were traced in the earlier
  [`MUSEUM_DONATION_FOLLOWUP.md`](MUSEUM_DONATION_FOLLOWUP.md); this follow-up
  does not claim a live end-to-end level transition.

## Marker and remaining unknowns

The native `OwlDonationDone` handler passes its context selector through
`0xf780e0`; the writer `0xf78130` stores a byte at SaveMuseum `+0x3004 + slot`.
The wrapper obtains that byte from a state query (`0xef62f0` → `0xeaa8c0`) and
forwards the low byte. A failed, absent, or mismatched state lookup can return
`0xff`; the duplicate gate `0xf77f60` treats `0xff` as a non-duplicate
exemption, while the donation threshold counter does not read marker bytes.
However, the successful state object's `+0xb0d` byte has no semantic name in
the available symbols/data. The marker's intended gameplay meaning and its
producer therefore remain unresolved.

The following questions need more evidence than this dump provides:

- An art-specific acceptance filter, native save writer, and art-room catalog
  mapping. The local build may predate or omit the relevant art data, so the
  absence here is not a universal game claim.
- Whether gyroids can be donated through a separate path outside the captured
  filters/EventFlows/save handler family.
- A live SaveMuseum item view and live ItemParam table-manager instance, plus
  item records with flags set, to validate behavior beyond the reconstructed
  native fixtures.
- The semantic label/producer of the marker's successful `+0xb0d` state byte,
  and a live end-to-end proof that the donor count causes the museum level to
  change after its scheduled daily transition.

## Reproduction

From this worktree, run:

```sh
python3 -m py_compile acnh-re/tools/museum_art_gyroid_followup_native.py
python3 acnh-re/tools/museum_art_gyroid_followup_native.py
```

The native image and raw ItemParam SHA-256 values, tested cases, controlled
boundaries, and static EventFlow/table summaries are recorded in `native.json`.
