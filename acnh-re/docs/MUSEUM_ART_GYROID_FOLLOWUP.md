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

The `OwlDonationDone` method at `0x2c2410` passes its event context `+0x2a8` to
`0xf780e0` after the item-kind/already-donated gate succeeds. `0xda3fc0` takes
the first context byte and normalizes values above 7 to `0xff`; this is the
mode-2 query selector. `0xf780e0` calls `0xef62f0` and forwards its return in
`w0` to `0xf78130`, which stores a successful byte at SaveMuseum
`+0x3004 + slot`. `0xeaa8c0` returns `0xffffffff` for a context-token mismatch,
missing/inactive row, or nonzero state kind; `0xf78130` rejects that negative
result. On success, `0xeaa8c0` returns the selected active kind-0 row's
`+0xb0d` byte as an unsigned byte. The duplicate gate `0xf77f60` treats a
saved `0xff` as a non-duplicate exemption, while the donation threshold
counter does not read marker bytes.

Native `0xe68280` manages eight state records with stride `0xb28`. A new row
starts as kind 3, inactive, with u16 `+0xb0d = 0x0100`; when the state-kind
argument is below 3, the writer stores that kind at `+0xb08`, activates
`+0xb0c`, writes the low byte of its third argument to `+0xb0d`, and stores the
low bit of its fourth argument at `+0xb0e`. The Museum value source is visible
in the other half of the call graph: `0xcfad0` calls `0xe684f0` for each
runtime configuration row, passing kind from bit 0 of the row's second word
and the row's first u32 as the third argument. `0xe684f0` forwards that u32 to
`0xe68280`; `0xeaa8c0` returns its low byte only for the selected active
kind-0 row. This joins the saved Museum byte to the low byte of a CFAD0 runtime
configuration key. The concrete keys are stored in a runtime row list and do
not appear in the extracted EventFlow or table data.

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
  that entry's first u32. It forwards both values to `0xe68280`, which stores
  the key's low byte at `+0xb0d`, then reconciles the matching row. The exact
  configuration words are not present as static values in the captured data.

The Museum marker therefore has a precise storage-level label: the low byte of
the selected active kind-0 CFAD0 configuration key. Its successful query
domain is a byte (`0x00..0xff`); query failure is the separate `0xffffffff`
sentinel and causes the writer to exit without inserting. A successful value
whose low byte is `0xff` would be stored as `0xff` and receive the duplicate
gate exemption too. The captured files do not show whether any active CFAD0
key has that value or whether a key maps to the donating player, so the marker
cannot be labeled a donor ID or donation-status enum. The other kind-0
callers' 0–7 values are generic state-manager uses, not observed Museum keys.
The bounds and state transitions are static `[PSEUDO]` evidence, not a live
state trace. A bounded native fixture executes `0xe68280`, `0xe684f0`,
`0xe68900`, `0xeaa8c0`, `0xfa4100`, and `0xfa4300`: all 32 cases pass, including
the 0–7 writer/query round trips, synthetic wrapper keys, pair-map
assignment/lookup, kind-2 rejection, kind-1 rejection, token mismatch, absent
row, out-of-range row, and full-map sentinels. Results are in
[`marker_state_native.json`](../output/gameplay/museum_donation_followup/marker_state_native.json);
the fixture controls the context snapshot, row view, allocation helpers, and
manager memory. Its row values are synthetic and do not stand in for the
CFAD0 keys used by Museum. The larger pair/context caller bodies remain
static-only.

## Save-to-expansion boundary

The static path joins the writer, count, flag, and day-change code. Native
caller `0x2c2410` opens `SaveLand.Museum` at node `+0x20a168` (size `0x3404`),
runs the item-kind/already-donated gate `0xf77e00`, and calls `0xf780e0` when
that gate succeeds. The writer inserts into the same item list that
`0xf773f0` scans; the counter counts Fossil/Fish/Insect records and ignores
marker bytes. EventFlow query `0x416260` returns `count < Border`, so its
`Border=20` case 0 branch is the at-least-20 path. In
`SNPC_owl_11_Tent_Entries:owl_Tent_AfterDonation`, that branch sets `FutaReadyForMuseum`,
`FutaReadyForMuseumToday`, and `MuseumGrowupEnable1`.

The day-change driver `0xf53a70` calls `0xf545f0`; that dispatcher acquires the
same Museum save member and calls `0xf77050` with it. In the native transition,
saved level 1 advances to 2 when the museum-tent structure is present. At saved
level 2, a supplied `MuseumGrowupEnable1` flag is cleared; with the fixture's
initial construction counter at 0, one elapsed day sets it to 1, and a second
elapsed day advances the saved level to 3, clears the counter, and sets
`Museum2Built`. The existing native fixture supplies saved level 2, the flag,
and two one-day calls, and confirms those two outputs. EventFlow's
`MuseumLevel` query at `0x416b00` reads the same save member and maps saved
levels 0–4 through `0xf772c0` and rodata `0x29f1f94` (`[3, 3, 0, 1, 2]`), so
EventFlow values 0 and 1 correspond to saved levels 2 and 3.

The stages remain separate in execution: `0xf780e0`/`0xf78130` and
`0x416260`/`0xf773f0` ran against synthetic save views; EventFlow supplies the
20-record flag path; `0xf77050` ran with the level, day deltas, and expansion
flag supplied. No real save or running process is available to show that a
particular donation set the flag in the same save later advanced by the daily
dispatcher. The machine-readable stage map and marker join are in
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
- The concrete `0xcfad0` runtime configuration keys used by Museum and whether
  any key encodes the donating player. The static join shows only the selected
  kind-0 key's low byte reaching the per-item marker.
- A live end-to-end proof that a donation saved into a real Museum list caused
  `MuseumGrowupEnable1` to be set and the next daily dispatcher pass advanced
  that same save's MuseumLevel.

## Reproduction

From this worktree, run:

```sh
python3 -m py_compile acnh-re/tools/museum_art_gyroid_followup_native.py
python3 acnh-re/tools/museum_art_gyroid_followup_native.py
PYTHONPATH=/workspace/acnh-re/.deps python3 acnh-re/tools/museum_marker_state_native.py
```

The native image and raw ItemParam SHA-256 values, tested cases, controlled
boundaries, and static EventFlow/table summaries are recorded in `native.json`.
