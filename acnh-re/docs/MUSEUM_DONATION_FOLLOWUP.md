# Museum donation follow-up

This note follows the museum donation queue using the available EventFlow, save-layout, table, and native NSO evidence. The `DonationCheckItemType` registration and its empty-context native branch are reproduced; adjacent branches are recorded as proven, partial, or still open rather than inferred from their names. Machine-readable source details and table counts are in [`audit.json`](../output/gameplay/museum_donation_followup/audit.json).

## Native dispatch: `DonationCheckItemType`

`0x3d9ab0` is the constructor for the handler identified by the literal `DonationCheckItemType` at NSO VA `0x298d4ef`. Its native body writes that string pointer into object offset `+0xc8`, initializes the embedded object at `+0xb8`, and tail-branches to the registration helper at `0x4624d0` with `object + 0xb8`. With the real vtable from the NSO, the primary object's slot `+0x30` resolves to `0x3d9b60`, the predicate method.

The predicate itself is executed from the NSO by [the focused native runner](../tools/museum_donation_native.py). The runner stubs only the generic base initializer (`0x455f90`) and registration callback (`0x4624d0`), then calls the real constructor and real predicate. It confirms the registered name, vtable target, and that the predicate returns false when its evaluation-context pointer at object `+0x8` is null. This proves handler registration and the empty-context exit; it does not exercise accepted or rejected item kinds.

The EventFlow crosswalk connects the handler family to the museum hand-in path: `SNPC_rco_01_Tent_1_Entries:RcoTentFishInsect` selects from `RcoDonationForMuseum` and checks `OwlIsDonation` with `DonationCheckItemType="cUISelect"`. The flow then branches on `MuseumDonationNumCheck Border=5` before giving the first museum tent donation reward. Blathers' later tent and building filters are `OwlTentDonation0`, `OwlTentDonation1`, and `OwlDonation`. These filters establish that the game separates hand-in contexts; they do not reveal the full item-kind predicate. The exact positive `cUISelect` eligibility rule remains open.

Machine-readable runner output: [`native.json`](../output/gameplay/museum_donation_followup/native.json). Reproduce it with:

```sh
PYTHONPATH=/workspace/acnh-re/.deps python3 acnh-re/tools/museum_donation_native.py
```

Source NSO hash: `f8d248109ff72999b4600ae3749f8c7397fb960f7ad3ab8dee3018ae9e14e900`.

## Blathers and fossil assessment

The decoded `SNPC_owl_02_Museum_Judgment` tree is preserved at [`fossil_judgment_flow.txt`](../output/gameplay/museum_donation_followup/fossil_judgment_flow.txt). Its `Root` first requires an unknown fossil (`FossilUnknown`) and opens an `OwlFossilJudgement` item filter. One branch calls `OwlFossilAppraise` and then checks `AppraiseFossilDonationRate`; another calls `Fossil_Check`, whose entry also calls `OwlFossilAppraise`, tags the selected item, and returns to `OwlIsDonation` with `DonationCheckItemType="cUISelect"`. The donation branch then uses `MuseumLevel` and `MuseumDonationNumCheck` borders 20 and 19 before `Donation_Accept` or `Donation_Decline`. Subsequent Blathers dialogue checks `OwlDonationFossilIsParts`, `OwlDonationFossilComplete`, and can set `MuseumFossilComplete`.

This proves the fossil appraisal and donation decision order at the EventFlow layer. It does not establish the calculation behind `AppraiseFossilDonationRate`, what makes a fossil known versus unknown, or which persistent item bits `OwlDonationDone` updates. `MuseumFossilDonateInfo` has 73 display rows: 9 in `IdrMuseumFossil_0`, 54 in `IdrMuseumFossil_1`, and 10 in `IdrMuseumFossil_2`. Its fields are `StageName`, `UniqueID`, `WatchItem`, `ModelID`, and `CameraParamName`, so it describes fossil-room display/model data rather than documenting the appraisal algorithm.

## Save state, donation count, and expansion

The save-layout tree labels a `SaveLand.Museum` block at save offset `0x411a80`, size `0x3404`, crosswalked to `::Game::SaveMuseum`. It exposes a four-byte `MuseumLevel` field at offset `+0`; it does not name the remaining `0x3400` bytes. The flags visible in EventFlow are progression state, not proof of per-species save bits: `cPlayer:OwlDonationDone` is set after the donation path, `cLand:DonationAmountForMuseum` starts at 15 and is decremented by one while the 20-donation border has not been reached, and `cLand:OwlFoundFossil`/`MuseumFossilComplete` control fossil conversation and completion. The location and writer for fish, insect, fossil, art, or gyroid donation bits remain open.

In `SNPC_owl_11_Tent_Entries:owl_Tent_AfterDonation`, the 20-donation check's case 0 path sets `FutaReadyForMuseum`, `FutaReadyForMuseumToday`, and `MuseumGrowupEnable1`. Case 1 subtracts one from `DonationAmountForMuseum` and may offer another item filter. This establishes the EventFlow threshold trigger. The later daily state transition has separate native coverage already recorded in `gameplay_native.json`: `0xf77050` changes the tent into construction and then the completed museum on successive day changes. That native test starts from a supplied `MuseumGrowupEnable1` state; it does not execute or verify the preceding donation writer.

`OpenDonatedNum` belongs to the separate fish-spawn gate. `FishStatusParam` contains 84 rows with thresholds 0 (45 rows), 20 (22), 50 (12), and 100 (5). Existing scenario notes describe `0x5b8e30` as comparing that field with the player's catch count, but mark the comparison `[PSEUDO]` because the accessor is controlled in the native rig. This table/gate evidence concerns how many fish must have been caught for a species to spawn; it does not identify the museum's donated-item ledger.

## Evidence status

| Area | Current evidence | Status |
|---|---|---|
| Item eligibility | Filter/query sequence in decoded flows; native `0x3d9ab0` registration and the `0x3d9b60` null-context branch reproduced | Partial `[EF/N]`; positive per-kind outcomes and duplicate-donation behavior remain open |
| Donation save bits | `SaveLand.Museum` span and its only exposed `MuseumLevel` field located | Open `[SAVE]`; donation-ledger bit offsets and writers are not identified |
| Fossil assessment | `OwlFossilAppraise`, `AppraiseFossilDonationRate`, `Fossil_Check`, and follow-up branches traced | Partial `[EF/TBL]`; native appraisal result and item-ledger writes remain open |
| Tent-to-building trigger | `DonationAmountForMuseum` decrement and `MuseumGrowupEnable1` EventFlow path identified; daily `0xf77050` state transition has existing native test coverage | Partial `[EF/N]`; native link from accepted item to threshold writer remains open |
| `OpenDonatedNum` | Table threshold histogram is confirmed; existing catch-count rule is marked `[PSEUDO]` | `[TBL/PSEUDO]`; native comparison remains open in the related creature-spawn topic |
