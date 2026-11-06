# Museum donation follow-up

This note follows the museum donation queue using the available EventFlow, save-layout, table, and native NSO evidence. The first completed slice is the `DonationCheckItemType` native dispatch. Other slices are recorded as proven, partial, or still open rather than inferred from their names.

## Native dispatch: `DonationCheckItemType`

`0x3d9ab0` is the constructor for the handler identified by the literal `DonationCheckItemType` at NSO VA `0x298d4ef`. Its native body writes that string pointer into object offset `+0xc8`, initializes the embedded object at `+0xb8`, and tail-branches to the registration helper at `0x4624d0` with `object + 0xb8`. With the real vtable from the NSO, the primary object's slot `+0x30` resolves to `0x3d9b60`, the predicate method.

The predicate itself is executed from the NSO by [the focused native runner](../tools/museum_donation_native.py). The runner stubs only the generic base initializer (`0x455f90`) and registration callback (`0x4624d0`), then calls the real constructor and real predicate. It confirms the registered name, vtable target, and that the predicate returns false when its evaluation-context pointer at object `+0x8` is null. This proves handler registration and the empty-context exit; it does not exercise accepted or rejected item kinds.

The EventFlow crosswalk connects the handler family to the museum hand-in path: `SNPC_rco_01_Tent_1_Entries:RcoTentFishInsect` checks `OwlIsDonation` with `DonationCheckItemType="cUISelect"` after a UI item selection. That flow then branches on `MuseumDonationNumCheck Border=5` before giving the first museum tent donation reward. The exact positive `cUISelect` eligibility predicate remains open.

Machine-readable runner output: [`native.json`](../output/gameplay/museum_donation_followup/native.json). Reproduce it with:

```sh
PYTHONPATH=/workspace/acnh-re/.deps python3 acnh-re/tools/museum_donation_native.py
```

Source NSO hash: `f8d248109ff72999b4600ae3749f8c7397fb960f7ad3ab8dee3018ae9e14e900`.

## Remaining donation paths

| Area | Current evidence | Status |
|---|---|---|
| Item eligibility | EventFlow uses item filters `RcoDonationForMuseum`, `OwlTentDonation0/1`, then `OwlIsDonation`; native registration/predicate null-context branch verified above | Partial; per-kind acceptance and already-donated rejection are open |
| Donation save bits | save-layout names a `SaveLand.Museum` block at save offset `0x411a80`, size `0x3404`; its exposed field is only `MuseumLevel` at offset `+0` | Open; donation-ledger bit offsets/writers are not identified in the available layout |
| Fossil assessment | Blathers EventFlow calls `SNPC_owl_02_Museum_Judgment:Fossil_Check`, then checks `MuseumLevel`, known/unknown fossil state, `OwlDonationFossilIsParts`, and completion | Partial [EF]; assessment result and item ledger writes are not native-verified |
| Tent-to-building trigger | EventFlow `owl_Tent_AfterDonation` sets `OwlDonationDone`; if the 20-donation check reaches case 0 it enables `MuseumGrowupEnable1`; otherwise it subtracts 1 from `DonationAmountForMuseum` (default/max 15). Daily facility processing and the museum level progression are documented separately at `0xf77050` | [EF] trigger verified; per-item native writer and end-to-end native path open |
| `OpenDonatedNum` | Fish table threshold and the fish-spawn rule are documented in `GAMEPLAY_SCENARIO.md` §8; the catch-count gate `0x5b8e30` is explicitly marked `[PSEUDO]` because the count accessor is stubbed in the rig | Table rule available; native comparison remains open and belongs to the related creature-spawn queue |

The table `MuseumFossilDonateInfo` has 73 rows and fields `StageName`, `UniqueID`, `WatchItem`, `ModelID`, and `CameraParamName`; it describes fossil-room display/model metadata. Its schema alone does not establish fossil appraisal or donation persistence semantics.
