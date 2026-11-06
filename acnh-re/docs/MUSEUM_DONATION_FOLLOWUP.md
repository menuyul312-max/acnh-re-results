# Museum donation follow-up

This note follows the museum donation queue using the available EventFlow, save-layout, table, and native NSO evidence. The `DonationCheckItemType` registration and its empty-context native branch are reproduced; adjacent branches are recorded as proven, partial, or still open rather than inferred from their names. Machine-readable source details and table counts are in [`audit.json`](../output/gameplay/museum_donation_followup/audit.json).

## Native dispatch: `DonationCheckItemType`

`0x3d9ab0` is the constructor for the handler identified by the literal `DonationCheckItemType` at NSO VA `0x298d4ef`. Its native body writes that string pointer into object offset `+0xc8`, initializes the embedded object at `+0xb8`, and tail-branches to the registration helper at `0x4624d0` with `object + 0xb8`. With the real vtable from the NSO, the primary object's slot `+0x30` resolves to `0x3d9b60`, the predicate method.

The predicate itself is executed from the NSO by [the focused native runner](../tools/museum_donation_native.py). The runner stubs only the generic base initializer (`0x455f90`) and registration callback (`0x4624d0`), then calls the real constructor and real predicate. It confirms the registered name, vtable target, and that the predicate returns false when its evaluation-context pointer at object `+0x8` is null. This proves handler registration and the empty-context exit; it does not exercise accepted or rejected item kinds.

The EventFlow crosswalk connects the handler family to the museum hand-in path: `SNPC_rco_01_Tent_1_Entries:RcoTentFishInsect` selects from `RcoDonationForMuseum` and checks `OwlIsDonation` with `DonationCheckItemType="cUISelect"`. The flow then branches on `MuseumDonationNumCheck Border=5` before giving the first museum tent donation reward. Blathers' later tent and building filters are `OwlTentDonation0`, `OwlTentDonation1`, and `OwlDonation`. These filters establish that the game separates hand-in contexts. The native SaveMuseum path admits Fossil/Fish/Insect and applies an already-donated gate; the precise EventFlow item-list mapping and live item-key adapters remain open.

Machine-readable runner output: [`native.json`](../output/gameplay/museum_donation_followup/native.json). Reproduce it with:

```sh
PYTHONPATH=/workspace/acnh-re/.deps python3 acnh-re/tools/museum_donation_native.py
```

Source NSO hash: `f8d248109ff72999b4600ae3749f8c7397fb960f7ad3ab8dee3018ae9e14e900`.

## Selected-item duplicate gate — native, controlled context

The native predicate at `0x3d9b60` has a selected-item branch that calls `0xf77f60` with a catalog/list view and the selected item. `0xf77f60` scans up to `0x400` (1,024) entries. For a matching entry, it reads the corresponding marker byte at view offset `+0x3004`; marker `0xff` makes the helper return `0`, while any other marker makes it return `1`. The selected-item predicate inverts that result, so the tested branch accepts when the helper returns `0` and rejects when it returns `1`.

`tools/museum_donation_predicate_native.py` executes original instructions for `0x3d9b60`, `0xf77f60`, and the ordinary-record identity branch of `0xf58af0`. Five predicate cases cover selector tokens `cUISelect` and `cDeliveryItem`, no match, and matched records with marker `0`/`0xff`. The selected-item serializer, selector/context accessors, ItemParam view/type adapters, and lower inventory/equivalence calls are controlled; for the canonical synthetic item, the native matcher compares the 16-bit item ID and flags before the controlled lower checks.

The same runner exercises native `0xf77e00`, the positive precondition used by the item-submission path. Its native `0xa9f670` getter reads a synthetic one-row ItemParam-kind table (the row-index accessor is controlled); the native ItemKind comparison accepts codes 70, 65, and 64. With an ordinary matching item record, a marker other than `0xff` rejects the second donation, while marker `0xff` makes this helper return true. An unmatched record returns true, and another ItemKind (66) is rejected before the 1,024-slot scan. Ten positive/negative cases (three supported kinds × three duplicate states, plus one unsupported kind) pass with zero mismatches. The marker's gameplay meaning still needs a live producer/state crosswalk.

Machine-readable output: [`predicate_native.json`](../output/gameplay/museum_donation_followup/predicate_native.json). Reproduce with:

```sh
PYTHONPATH=/workspace/acnh-re/.deps python3 acnh-re/tools/museum_donation_predicate_native.py
```

The native string initializer at `0x3da0b0` contains `cUISelect , cDeliveryItem`. The two tested tokens are taken from this literal; the fixture supplies parser/token state explicitly. The exact save-backed key adapters and meaning/producer of marker `0xff` remain open.

## SaveMuseum donation-list writer — native with controlled adapters

The NSO save-layout audit places `SaveLand.Museum` at save offset `0x411a80`, size `0x3404`. Native `0xf77f60` reads item records beginning at view `+0x1004` and marker bytes at `+0x3004`. The insertion routine `0xf78130` confirms a 1,024-slot layout: it probes a signed 16-bit ID at `+0x1004 + 8*i` and treats `-2` as empty; it copies an 8-byte item record to that slot, writes a packed calendar date (`year:u16, month:u8, day:u8`) at `+4 + 4*i`, and writes one marker byte at `+0x3004 + i`. Native `0xf41eb0` copies those date fields from the calendar source and calls the `nn::time::IsValidDate` import. With `MuseumLevel` at `+0`, these fields exactly fill the `0x3404` block.

`0xf78130` compares the item's native `ItemKind` value with three globals (at `0x35ec944`, `0x35ec948`, `0x35ec94c`) and only inserts values 70, 65, and 64. The local resolved ItemParam enum crosswalk labels those Fossil, Fish, and Insect, respectively. The runner executes native `0xa9f670` over a synthetic one-row kind table while controlling its row index; this tests the category gates but not the live ItemParam row selection.

The static native caller `FUN_003c2410` (`0x2c2410`) resolves the same save member via `base + 0x20a168`, then calls `0xf77e00` at `0x2c2588` before `0xf780e0` at `0x2c25b8`. `0xf77e00` filters the same three kinds and inverts the `0xf77f60` duplicate result; `0xf780e0` obtains a marker through `0xef62f0` and calls `0xf78130` at `0xf78118`. This gives a concrete caller path: for the three supported kinds, the submission path tests the existing museum list and then enters the list writer when the helper returns true. The function has no stronger semantic label in the current index than `FUN_003c2410`.

`tools/museum_donation_writer_native.py` executes the original `0xf780e0 → 0xf78130` chain, native `0xa9f670` kind lookup, and calendar packing in `0xf41eb0`. Seven full-block comparisons cover Fossil/Fish/Insect insertion, first-empty-slot selection (including slot 1,024), rejected kinds, invalid items, the sign-bit early exit, and a full list; all pass with zero mismatches. Save-view, marker, calendar source, item-validity, ItemParam view, and row index adapters are controlled, so this proves the writer's native slot and field behavior, not live event state or the gameplay meaning attached to the stored date.

Reproduce the native checks with:

```sh
PYTHONPATH=/workspace/acnh-re/.deps python3 acnh-re/tools/museum_donation_predicate_native.py
PYTHONPATH=/workspace/acnh-re/.deps python3 acnh-re/tools/museum_donation_writer_native.py
```

Machine-readable outputs: [`predicate_native.json`](../output/gameplay/museum_donation_followup/predicate_native.json) and [`writer_native.json`](../output/gameplay/museum_donation_followup/writer_native.json).

## Blathers and fossil assessment

The decoded `SNPC_owl_02_Museum_Judgment` tree is preserved at [`fossil_judgment_flow.txt`](../output/gameplay/museum_donation_followup/fossil_judgment_flow.txt). Its `Root` first requires an unknown fossil (`FossilUnknown`) and opens an `OwlFossilJudgement` item filter. One branch calls `OwlFossilAppraise` and then checks `AppraiseFossilDonationRate`; another calls `Fossil_Check`, whose entry also calls `OwlFossilAppraise`, tags the selected item, and returns to `OwlIsDonation` with `DonationCheckItemType="cUISelect"`. The donation branch then uses `MuseumLevel` and `MuseumDonationNumCheck` borders 20 and 19 before `Donation_Accept` or `Donation_Decline`. Subsequent Blathers dialogue checks `OwlDonationFossilIsParts`, `OwlDonationFossilComplete`, and can set `MuseumFossilComplete`.

This proves the fossil appraisal and donation decision order at the EventFlow layer. It does not establish the calculation behind `AppraiseFossilDonationRate`, what makes a fossil known versus unknown, or which persistent item bits `OwlDonationDone` updates. `MuseumFossilDonateInfo` has 73 display rows: 9 in `IdrMuseumFossil_0`, 54 in `IdrMuseumFossil_1`, and 10 in `IdrMuseumFossil_2`. Its fields are `StageName`, `UniqueID`, `WatchItem`, `ModelID`, and `CameraParamName`, so it describes fossil-room display/model data rather than documenting the appraisal algorithm.

## Save state, donation count, and expansion

The save-layout tree labels a `SaveLand.Museum` block at save offset `0x411a80`, size `0x3404`, crosswalked to `::Game::SaveMuseum`. It exposes a four-byte `MuseumLevel` field at offset `+0`; native readers/writer map the remaining bytes to 1,024 item records, 1,024 packed year/month/day words, and 1,024 marker bytes. The traced insertion path accepts Fossil, Fish, and Insect. It does not establish whether art or gyroids use a separate ledger, whether the 1,024-entry data is the complete museum ledger, or the live meaning of each marker/date field. The flags visible in EventFlow are progression state, not proof of per-species save bits: `cPlayer:OwlDonationDone` is set after the donation path, `cLand:DonationAmountForMuseum` starts at 15 and is decremented by one while the 20-donation border has not been reached, and `cLand:OwlFoundFossil`/`MuseumFossilComplete` control fossil conversation and completion.

In `SNPC_owl_11_Tent_Entries:owl_Tent_AfterDonation`, the 20-donation check's case 0 path sets `FutaReadyForMuseum`, `FutaReadyForMuseumToday`, and `MuseumGrowupEnable1`. Case 1 subtracts one from `DonationAmountForMuseum` and may offer another item filter. This establishes the EventFlow threshold trigger. The later daily state transition has separate native coverage already recorded in `gameplay_native.json`: `0xf77050` changes the tent into construction and then the completed museum on successive day changes. That native test starts from a supplied `MuseumGrowupEnable1` state; it does not execute or verify the preceding donation writer.

`OpenDonatedNum` belongs to the separate fish-spawn gate. `FishStatusParam` contains 84 rows with thresholds 0 (45 rows), 20 (22), 50 (12), and 100 (5). Existing scenario notes describe `0x5b8e30` as comparing that field with the player's catch count, but mark the comparison `[PSEUDO]` because the accessor is controlled in the native rig. This table/gate evidence concerns how many fish must have been caught for a species to spawn; it does not identify the museum's donated-item ledger.

## `OpenDonatedNum` fish-spawn gate — native, controlled accessors

`tools/open_donated_native.py` now executes the original `0x5b8e30` for all 84 local `FishStatusParam` rows and all session modes 0–3. It runs 828 threshold-boundary cases (`threshold-1`, `threshold`, and `threshold+1`; threshold 0 uses counts 0 and 1), with zero mismatches. The native cache initializer/search resolves hash `0xeac6a012`, stores the controlled value offset `+4`, and reuses it. The local fish table supplies each actual `ItemID` and `OpenDonatedNum`; synthetic row views expose those values as the adapter's `(hash, value)` pair.

The native branch queries `CatchFish` in modes 0/1 and `FishNetHostCatchNumResult` in modes 2/3, then returns true exactly when `OpenDonatedNum <= selected catch count`. Save and table accessors are controlled, so this does not prove how live save state or network ownership populates those counters. This is a fish-spawn unlock gate; it remains separate from museum donation persistence.

Machine-readable output: [`open_donated_native.json`](../output/gameplay/museum_donation_followup/open_donated_native.json). Reproduce with:

```sh
PYTHONPATH=/workspace/acnh-re/.deps python3 acnh-re/tools/open_donated_native.py
```

## Evidence status

| Area | Current evidence | Status |
|---|---|---|
| Item eligibility | Filter/query sequence; native `F77E00` supports Fossil/Fish/Insect and rejects an ordinary duplicate with marker other than `0xff`; predicate and ordinary ID comparison reproduced | Partial `[EF/N/TBL]`; item-key adapters, uncommon item flags, and marker semantics remain controlled/open |
| Donation save state | `SaveLand.Museum` spans `0x3404`; native list layout, 1,024 slots, sentinel, packed date words/markers, caller, and writer traced | Partial `[SAVE/N]`; art/gyroid ledger, full-list semantics, and live date/marker meaning remain open |
| Fossil assessment | `OwlFossilAppraise`, `AppraiseFossilDonationRate`, `Fossil_Check`, and follow-up branches traced; writer admits ItemKind Fossil | Partial `[EF/TBL/N]`; native appraisal result and the acceptance-to-20-donation counter link remain open |
| Tent-to-building trigger | `DonationAmountForMuseum` decrement and `MuseumGrowupEnable1` EventFlow path identified; daily `0xf77050` transition is reproduced; item submission path reaches SaveMuseum writer | Partial `[EF/N]`; native link from accepted donation count to threshold/counter writer remains open |
| `OpenDonatedNum` | All 84 table rows; 828 native boundary cases across session modes 0–3 | `[TBL/N]` with controlled field/save accessors; live persistence and host ownership remain open |
