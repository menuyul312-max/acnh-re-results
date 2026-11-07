# Island Designer edit/apply path, ACNH 1.0.0

This report follows the post-unlock Island Designer path as far as the supplied
1.0.0 evidence allows. The EventFlow reaches the construction-tool selector,
and ROMFS data describes make/break actions and blocker messages. The current
binary path from that selector into a LandMaking cell write, undo/apply
transaction, and save serializer is still open. No native edit/apply fixture is
supported by the available dump.

The machine-readable edge map, all 17 action-parameter rows, the 12 error rows,
source hashes, exact PCs, and bounded negatives are in
[`island_designer_edit_loop.json`](../output/ui_island/island_designer_edit_loop.json).

## EventFlow and native action boundary

`Player_ConstructionLicenseApp.Root` branches to `Start_Construction` at
subflow event 30, `End_Construction` at event 29, and `SaveEquipLicense` at
event 93. The start path checks the current stage (`cField`),
`cPlayer:ConstructionWorkToday`, and solo-controller state. It sets
`EquipLicenseHelmet` and `ConstructionWorkToday`; the end path clears the helmet
flag. The app also stores `LastUseLicense` values 0–3. These are unlock,
eligibility, and tool-state operations, not proof of an edit commit.

The parsed flow contains four `Player.EventFlowActionPlayerOutfitFieldMakeToolKit`
actions: event 112 selects `cGround`, event 110 selects `cRiver`, event 8 selects
`cCliff`, and event 9 selects `cOff`. The native action factory is `0x452fb0`,
its constructor is `0x2de340`, its vtable is `0x3045be8`, and its enter/update/
exit slots resolve to `0x2de3f0`, `0x2de870`, and `0x2de8c0`. That is the last
unbroken EventFlow-to-native-action edge established here.

`Restart` routes among app entries including `End_Construction`,
`Start_Construction`, manual pages, and `SaveEquipLicense`; it does not establish
world rollback. This flow has no dedicated `Apply`, `Commit`, `Undo`, or `Cancel`
entry. The `RemoveHistory` value in the action table is attached to an
unresolved column and has no proven caller or UI binding, so it cannot be
identified as the player's undo operation.

The main binary's string-reference index shows RiverMaker/CliffMaker vocabulary
at `0x2a260e8 → 0xf4a500` (`PlayerRiverMakerFallBury`),
`0x2a2f53f → 0xed9a60` (`State::cRiverMakerBury`),
`0x2a2f640 → 0xf3b130` (`PlayerCliffMakerActionDelete`),
`0x2a659ea → 0xed9a60` (`State::cCliffMakerReady`),
`0x2a65ab2 → 0xf39950` (`PlayerCliffMakerNGReady`), and
`0x2a65adb → 0xf48e80` (`PlayerRiverMakerNGReady`). These are string xrefs, not
a recovered live dispatch chain. In particular, they do not prove how an input
chooses a parameter row or how an action is committed.

## Data, validation, and world mutation

`FieldLandMakingActionParam.bcsv` has 17 rows of 40 bytes. Its recovered fields
describe `1x1`/`3x3` ranges, layer, make/break result, cliff-level and plane
changes, edge direction, waterfall transitions, update-part and river flags,
main type, and lock range. The native BCSV getter PCs are `0x4f3880`, `0x4f3a40`,
`0x4f3c00`, `0x4f3dc0`, `0x4f3f80`, `0x4f4140`, `0x4f4300`, `0x4f44c0`,
`0x533120`, `0x533260`, `0x532f40`, and `0x532de0`, respectively. The readers
prove native access to the parameter columns; they are not yet joined to the
RiverMaker/CliffMaker state references. Two column names remain unresolved:
`h_75fee4b0` (values include `NoChange`, `AddCliffLevel`, `RemoveHistory`) and
`h_7674c4d6` (values `None`, `1x1`, `3x3`).

`FieldLandMakingError.bcsv` contains 12 error categories, including nearby
trees, structures, cliffs, water, and waterfall orientation. Its unresolved
signed-byte field is read at `0xe323e0` (value load `0xe325a4`, `ldrsb`) as an
error-counter comparison threshold. That table/read view does not recover the
full placement validator or the geometry behind each blocker.

Existing native terrain evidence proves a 52-byte runtime ground record,
`x + width*z` indexing, and read aggregators at `0x187420` (all
`WaterCheck`), `0x1874f0` (any `PlayerNoEntry`), and `0x187610` (exactly two
`WaterCheck`). Existing region helpers prove the rectangle predicate at
`0x181fa0`, bit-region mutations at `0x181ae0` and `0x185c80`, the guarded world
wrapper at `0x1637b0`, height forwarders at `0x163740` and `0x164e90`, and the
word decoder at `0x185e70`. The prior test fixtures covered 216 predicate cases
and 164 mutation cases with no mismatches. They are generic read/region
operations: neither they nor their callers are joined to a live construction
tool action or a LandMaking cell setter.

The data conversion context is present. The 96 `FieldPreset*_LandMaking.byml`
presets are 112×96 grids of 14-byte cells. The prior PBC audit matched
1,032,192 preset cells with no mismatches and records River/Fall model/PBC
assets. This establishes static terrain assets and parameter metadata, not the
runtime conversion from a 14-byte preset cell to a 52-byte ground record, nor
an edit-time cell transaction.

## Undo, apply, persistence, and day gate

There is no proven preview buffer, undo snapshot, cancel rollback, apply step,
or post-write mesh/collision refresh in this path. `FieldLandMakingActionParam`
describes prospective action settings, and `FieldLandMakingError` describes
error labels, but neither asset identifies the call site that reads them. The
separate region flag mutators cannot stand in for a terrain-cell change.

The current native `save_layout.json` does not expose a named `LandMakingMap`
member or a writer-to-serializer edge in the available save-layout view. The
external `CylindricalEarth/save_keys.json` labels `LandMakingMap`, `CliffLevel`,
and `::Game::SaveFieldLandMakingMapData`; those are useful search names, not
proof of the 1.0.0 save path. The exact missing join is:

`tool/action dispatch → parameter/error lookup → LandMaking cell write → world refresh → current save member/serializer`.

`ConstructionWorkToday` (event flag UniqueID 523) is checked and set by the
construction flow. Its table has raw fields `h_5140e4b4=0` and
`h_bed25a86=1`, whose reset semantics have not been decoded. No day-transition
writer is linked here, so the flow proves a work gate, not a confirmed once-per-
day reset or persistent terrain behavior.

## Evidence identity and limits

The source `main.elf` SHA-256 is
`5bf707c3dc5dac0ad9635af7d336ec580f81c3f7876d0f55400d1900e3415d74`; the
supplied ExeFS `main` NSO is
`f8d248109ff72999b4600ae3749f8c7397fb960f7ad3ab8dee3018ae9e14e900`. The
EventFlow, action table, and error table SHA-256 values are respectively
`d0edd2da56e0d462137601fddf1b09a69305ac58cbf3232d348dabd37db798b4`,
`fe3f06ae6fb26c95631e842cd043a52348ba2c7399fc5d6085ff13dcfed0af9a`, and
`232d276ed81ab7792b0e64fa6c10e7141702a63434c7e273041557cb0751de23`.

This report adds a static map of proven edges and open joins only. It does not
run the game, execute or mutate a save, or claim that the existing region
fixtures model Island Designer edits. The earlier
[`ISLAND_WATER_TERRAFORM_FOLLOWUP.md`](../../acnh-parallel/water_terrain/acnh-re/docs/ISLAND_WATER_TERRAFORM_FOLLOWUP.md)
and its open `island-water-terraform` queue item remain the source for preset,
PBC, and terrain-region evidence summarized above.
