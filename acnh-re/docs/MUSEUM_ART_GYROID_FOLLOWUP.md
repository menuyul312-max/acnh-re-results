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

The successful byte has a traced producer and callers that narrow its value
to an eight-slot context/player index on several paths. Native `0xe68280`
manages eight state records with stride `0xb28`. A new row starts as kind 3,
inactive, with u16 `+0xb0d = 0x0100`; when the state-kind argument is below 3,
the writer stores that kind at `+0xb08`, activates `+0xb0c`, writes the low
byte of its third argument to `+0xb0d`, and stores the low bit of its fourth
argument at `+0xb0e`. `0xeaa8c0` returns `+0xb0d` only when mode 2's context
token matches, `0xe68900` finds an active row, and the row kind is 0. Kinds 1
and 2 are active but do not satisfy this query.

The direct caller audit follows each value to its source:

- `0xccd40` calls the writer at `0xccff0` and `0xcd350` with state kind 2,
  value 0, and fourth argument 1. This creates an active kind-2 row; the mode-2
query returns `0xffffffff` for it because its kind is nonzero.
- `0xcd9f0` passes a 16-byte identity pair to `0xfa4300`. That helper returns
  the matching row number in an eight-entry pair map, 0–7, or `0xffffffff`;
  only a successful match reaches `0xe68280` with state kind 0 and that row
  number as the third argument.
- `0x2ee460` is an additional direct caller. When `0xfa3c10` says an identity
  pair is not already mapped, `0xfa4100` stores it in the first free slot of
  the same eight-entry map and returns 0–7 (or `0xffffffff` when full). The
  caller copies the associated context data and writes that assigned slot as
  the third argument with state kind 0.
- `0x2f5240` receives the result of `0x2f5030` from its caller `0x2f4f40`.
  The selector loop in `0x2f5030` is bounded to slots 0–7 and queries the
  literal `MakeVillagePlayerFlag`; its successful result is the slot whose
  flag is set, while the no-match path returns `0xffffffff`. The local
  EventFlow crosswalk uses `MakeVillagePlayerFlag` for the island
  representative, so this caller stores that representative's slot index.
- The wrapper `0xe684f0`, called by `0xcfad0`, receives a state kind of 0 or 1
  from bit 0 of each runtime configuration entry and its third argument from
  that entry's first word. It forwards both values to `0xe68280`, then
  reconciles the matching row. Those configuration words are not present as
  static values in the captured data.

These paths show that the field can carry an eight-slot player/context index;
they do not establish that the byte in `SaveMuseum` is a donor ID or donation
status. The bounds and transitions are static `[PSEUDO]` evidence, not a live
state trace. A bounded native fixture now executes `0xe68280`, `0xe684f0`,
`0xe68900`, `0xeaa8c0`, `0xfa4100`, and `0xfa4300`: all 32 cases pass, including
the 0–7 writer/query round trips, pair-map assignment/lookup, kind-2 rejection,
kind-1 rejection, token mismatch, absent row, out-of-range row, and full-map
sentinels. Results are in
[`marker_state_native.json`](../output/gameplay/museum_donation_followup/marker_state_native.json);
the fixture controls the context snapshot, row view, allocation helpers, and
manager memory; the larger pair/context caller bodies remain static-only. It
validates the native data contract rather than the live meaning of a Museum
marker.

## Save-to-expansion boundary

The captured path can be joined at the code and data-contract level. Static
native caller `0x2c2410` opens the `SaveLand.Museum` member at node `+0x20a168`
(size `0x3404`), runs the item-kind/already-donated gate `0xf77e00`, and calls
`0xf780e0` when that gate succeeds. The writer inserts into the same list that
`0xf773f0` scans. EventFlow query `0x416260` compares that count with its
`Border`; the decoded `SNPC_owl_11_Tent_Entries:owl_Tent_AfterDonation` flow uses
`Border=20`, and its case 0 path sets `MuseumGrowupEnable1`. The daily native
updater `0xf77050` consumes that flag and advances the museum from tent to
construction and then to the completed building.

The stages have separate controlled boundaries in the current evidence:
`0xf780e0`/`0xf78130` and `0x416260`/`0xf773f0` were run against synthetic save
views; the EventFlow link is decoded static data; `0xf77050` was run with the
expansion flag supplied. No real save file or running game process is available
here, so a live end-to-end check from a donation through the next-day museum
level change remains open. The machine-readable stage map is in
[`native.json`](../output/gameplay/museum_art_gyroid_followup/native.json).

The following questions need more evidence than this dump provides:

- An art-specific acceptance filter, native save writer, and art-room catalog
  mapping. The local build may predate or omit the relevant art data, so the
  absence here is not a universal game claim.
- Whether gyroids can be donated through a separate path outside the captured
  filters/EventFlows/save handler family.
- A live SaveMuseum item view and live ItemParam table-manager instance, plus
  item records with flags set, to validate behavior beyond the reconstructed
  native fixtures.
- Whether the successful player/context index means “donating player” in the
  Museum flow, plus the concrete third-argument values supplied by the
  `0xcfad0` runtime configuration entries.
- A live end-to-end proof that the selected player/context index is saved for
  a donation and that the donor count causes the museum level to change after
  its scheduled daily transition.

## Reproduction

From this worktree, run:

```sh
python3 -m py_compile acnh-re/tools/museum_art_gyroid_followup_native.py
python3 acnh-re/tools/museum_art_gyroid_followup_native.py
PYTHONPATH=/workspace/acnh-re/.deps python3 acnh-re/tools/museum_marker_state_native.py
```

The native image and raw ItemParam SHA-256 values, tested cases, controlled
boundaries, and static EventFlow/table summaries are recorded in `native.json`.
