# Resident/camper visible-actor spawn follow-up (ACNH 1.0.0)

This pass follows the resident and campsite requests past `0xc6c210`, adds the move-in and house-parameter paths, and checks the common field and `NpcHouse` stage rows. It extends the request-builder and plot-to-first-live reports without repeating their save-selection or EventFlow traces. The paired [JSON ledger](../output/gameplay/resident_visible_actor_spawn_followup_20261107.json) records source hashes, raw callsites, and bounded searches.

## Result

The resident and campsite builders reach a shared generic request service: `0xc6c210 → 0x490f0 → 0x49360`, then `0xd45c0 → 0x2201820`. The last helper dispatches through an indirect request-object method and queues work. Its concrete NPC actor consumer and actor factory are unresolved, so this closes the request handoff only to a generic asynchronous queue.

The manager update also calls `0xc687f0` at `0xc6869c`. That sibling scans resident slots for `MoveInCompletion`, updates a manager-local bitmask and name list, while `0xc68f30` separately reads `AbandonedHouse` as it builds actor requests. The two reads are in separate functions; the decompilation does not show the cache list feeding the request builder.

The house side adds two static links. The day-change move-in routine `0xf84f10` calls `0xf8cea0`, which consumes a waiting-NPC record and updates house-parameter data. Separately, `0xd21110` scans eligible resident slots and constructs a `Param/NpcHouse/<species><nn>.byml` request. These paths establish a resident-to-house-interior-data relationship. They do not provide the resident's outdoor house transform or a visible NPC instance.

## Request service and owner

`0xc68f30` and `0xc6ce40` submit resident and campsite records through `0xc6c210` at `0xc695cc`, `0xc698ac`, and `0xc6d128`. The request submitter calls `0x490f0` at `0xc6cbe4`; the direct-call index attributes that edge to `0xc6c210`.

Inside the generic helper, `0x49360` is called at `0x4929c`, and `0xd45c0` is called at `0x4930c`. `0xd45c0` forwards an envelope to `0x2201820` at `0xd466c`. The latter invokes an indirect method on the request object before queueing work. The indexed `0x490f0` target has 133 call rows, 71 with an owner, which supports treating it as a shared service rather than an NPC-specific consumer. No static edge from this queue reaches the registered `NpcActor` factory.

## Move-in activation and house data

The call to `0xc687f0` at `0xc6869c` is recorded with a null `owner_va`, but its PC falls inside the 584-byte `0xc685a0` function extent (`0xc685a0–0xc687e7`). The method sequence and extent identify `0xc685a0` as the `NpcActorMgr` update method. In `0xc687f0`, the ten-slot loop reads `AbandonedHouse` and `MoveInCompletion`. For qualifying slots it sets a bit in the manager field at `+0x10220` and appends a generated resident name to the list at `+0x10228`, with count at `+0x103a8`. This is manager-local activation bookkeeping; no later consumer of those literal offsets appears in the generated decompilation set.

The sibling request builder `0xc68f30` also scans ten records at stride `0x12ab0`, but its field read is `AbandonedHouse`. Its actor-name/resource-path construction uses unresolved global callback pointers at `0x33f9160`, `0x33f9168`, `0x33f9170`, and `0x33f9178`; the targets do not identify a position setter or actor constructor in this evidence set.

The separate day-change path has a clearer move-in owner: `0xf84f10` calls `0xf8cea0` at `0xf851a4` and `0xf8520c`. The native summary identifies `0xf8cea0` as the waiting-NPC move-in/house-build helper. Its body selects from four temporary NPC records by state byte `3`, updates the selected resident record, and, when a house-parameter handle is present, passes the `0x1d4`-byte row through `0xf826c0` and `0xf814c0`. This is an authored house-data update path, not a recovered world-coordinate or transform assignment.

`0xd21110` is a separate house-interior-data consumer. Its ten-slot loop requires `AbandonedHouse < 2` and `MoveInCompletion` on, increments a resident-house count at `+0x63b0`, builds the `NpcHouse` resource path from the species and NPC number, and reaches the generic resource request helper `0x1f05a80` at `0xd21354`. Its indexed direct callers are `0xbbe5a0` (`0xbbf068`), `0xbbf3e0` (`0xbbfeac`), `0xbc0430` (`0xbc04c8`), and `0xf53a70` (`0xf53f50`); a fifth call row at `0xce438` has no owner. This establishes static selection/request of interior parameters, not loading completion or a rendered room occupant.

The first-camper EventFlow and native action trace in the prior continuity report ends at writing the visitor ID into NPC save slot 5. Slot 5 falls inside the manager's ten-slot scan, but no static edge connects that talk write to the four-record waiting-NPC buffer consumed by `0xf8cea0`, to `0xd21110`'s ready-house predicate, or to a successful field actor request. The campsite visitor request and later resident-house path remain separate stages in the recovered graph.

## Stage rows and actor factory boundary

`MainField.byml` includes `commonOutdoor`; that common resource contains a registered `NpcActorMgr` row at `/3cbaa541/2` with no position or argument string. `commonIndoor` also contains a generic `NpcActorMgr` row at `/3cbaa541/0`, likewise without a transform. All ten `NpcHouse0` through `NpcHouse9` templates include `commonIndoor`; each local actor list contains only `PlayerActorMgr` at the same interior position record and no resident `Npc` row. These are stage-resource candidates and interior spawn data, not proof that a particular resident house or actor was instantiated.

For comparison, `Dream_Tkk.byml` has a static `Npc` row with an explicit position and `AI_NPC_Tkk_Dream` path, parented to the `NpcActorMgr` actor-kind hash. That control row shows that the stage projection can represent a positioned NPC. It does not map resident save slots or house transforms into such a row.

The prior component-boundary trace distinguishes the manager factory (`NpcActorMgr`, `0xc67fa0`) from the separate `NpcActor` class factory (`0xbe5e40`). The actor-kind registry lists `NpcActorMgr` as index 5 and `Npc` as index 6. The manager factory is established, and the `NpcActor` registration is established, but the request queue has no recovered edge to `0xbe5e40`; the stage-kind-to-class dispatch remains indirect. These factories must not be conflated.

## Join status

| Join | Status | Evidence and boundary |
|---|---|---|
| `NpcActorMgr` update → resident/campsite request builders | **Static confirmed** | Prior raw callsite and extent trace: `0xc685a0 → 0xc68f30`, with `0xc6ce40` as the campsite builder. |
| Resident/campsite request → generic asynchronous queue | **Static confirmed** | `0xc6c210 → 0x490f0 → 0x49360 / 0xd45c0 → 0x2201820`; queue target and indirect handler are generic. |
| `MoveInCompletion` → `NpcActorMgr` bookkeeping | **Static confirmed** | `0xc687f0` sets a manager-local slot mask/name list; no consumer join to `0xc68f30` recovered. |
| Move-in processor → `NpcHouse` parameter path | **Static confirmed** | `0xf84f10 → 0xf8cea0` updates house parameters; `0xd21110` requests per-resident `Param/NpcHouse` data. |
| Resident/camper request → concrete `NpcActor` factory or visible instance | **Open** | No direct or resolved indirect edge from the generic request queue to `0xbe5e40`, a model instance, or a field actor. |
| Resident save slot → outdoor house transform/placement | **Open** | Stage manager rows have no transform; house interior templates expose the player spawn only. No slot-to-plot coordinate or final transform setter was recovered here. |
| First-camper slot 5 → move-in house/visible actor | **Open** | The talk write is statically confirmed, but no edge to the waiting-NPC buffer, house-ready load, or accepted field actor request was recovered. |

## Bounded searches and limits

The machine-readable ledger records the input and analysis hashes. The direct-call counts refer only to `output/index.sqlite`; null owner rows and indirect calls are not treated as missing execution. The stage sweep covers the 108 projected stage sources in `output/stage/catalogue.json`, including all ten `NpcHouse` templates. The generated native decompilation search for `+0x10220` and `+0x10228` finds those literal manager-cache fields only in `0xc687f0`; indirect field access may be outside that textual check.

The supplied `output/additional_romfs` extract and the additional-ROMFS ZIP listing contain no `Param/NpcHouse` payload, so the path evidence is native string/use evidence only. No game or save was run, no save was modified, and no Godot content was changed. Static function bodies and resource records do not prove callback timing, accepted resource loads, actor construction, house placement, rendering, collision, or talk-entry selection.
