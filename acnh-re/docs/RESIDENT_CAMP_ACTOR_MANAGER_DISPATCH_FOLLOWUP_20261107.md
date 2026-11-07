# Resident/camper actor-manager dispatch follow-up (ACNH 1.0.0)

This pass resolves a missing caller for the resident actor-request builder and ties the first-camper actor builder to the same manager update path. The earlier direct-caller index reported no caller for `0xc68f30`; raw disassembly shows the call is inside `NpcActorMgr` method `0xc685a0`, but the `direct_calls` database row has a null `owner_va`, which caused that caller query to miss it.

## Manager update to resident requests

The `NpcActorMgr` registration/vptr evidence in [the component-boundary report](BUILDING_ACTOR_MGR_COMPONENT_BOUNDARY_20261107.md) maps its relocated method sequence at `0x30d9a50`, slot `+0x38` / pointer cell `0x30d9a88`, to `0xc685a0`. The raw body saves the manager receiver from `x0` into `x19` at `0xc685cc`. At `0xc686ac`, it calls `0xc70da0` with that receiver. If bit 0 of the return value is set, `tbnz` at `0xc686b0` skips the next builder; otherwise it restores the same manager pointer to `x0` and calls `0xc68f30` at `0xc686b8`.

The recorded function extent for `0xc685a0` is 584 bytes (`end_va=0xc687e7` in `analyzed_functions.tsv`), so `0xc686b8` lies inside the method body. The `direct_calls` entry for target `0xc68f30` correctly records call PC `0xc686b8`, but leaves `owner_va` null. Resolving the PC against the raw function extent establishes this direct edge:

`NpcActorMgr` slot `+0x38` → `0xc685a0` → (conditional on `0xc70da0` return bit 0 being clear) `0xc68f30`.

This is a static call route. It does not establish that a stage loader created the manager or dispatched its method during a live game.

## Resident-slot scan and campsite builder

`0xc68f30` iterates ten NPC records at stride `0x12ab0`. For each record it reads the `AbandonedHouse` field, constructs the actor/resource request when the record passes its branch conditions, and submits requests through `0xc6c210` (call PCs include `0xc695cc` and `0xc698ac`). The same routine calls the campsite builder `0xc6ce40` at `0xc69838` on a separate conditional path. The campsite builder reads campsite member data at manager offset `+0x20d578`, resolves the visitor record, constructs an `E_%s_NPC_%02d` actor name and `AI_NPC_Camp` path, then submits through `0xc6c210` at `0xc6d128`.

The request submitter `0xc6c210` reaches generic helper `0x490f0` at `0xc6cbe4`. This confirms that the resident and campsite routines pass records into a shared native request-processing path. The helper and its indirect resource/actor dispatch have not been joined to a concrete visible actor instance, so “request submitted” must not be promoted to “NPC rendered/spawned.”

The earlier move-in proof records the same ten-slot NPC-save layout and stride: A/B/C move-in writes populate this save member, and `Set6thVillager(Step=0)` writes the first camper into slot 5, which falls within the manager builder's ten-record scan. This establishes a static save-layout relationship and a candidate path for later actor requests. It does not show that the slot-5 write immediately reaches `0xc68f30`, that its request is accepted, or that its home coordinate is used.

One precision correction: `MoveInCompletion` is read in sibling manager method `0xc687f0`, also called by `0xc685a0`; the resident builder `0xc68f30` itself contains the `AbandonedHouse` field read. These adjacent reads belong to the same manager update class but are not evidence that one builder branch checks both fields.

## What remains open

- The `commonOutdoor` stage record has type index 5 (`NpcActorMgr`), and the native registry maps that type to the manager factory. Stage alias/include resolution and actual manager construction are still not observed.
- The manager-method and builder calls are static; no field-frame callback timing or live actor-request execution was observed.
- The actor request has not been connected to a concrete resident house/site transform, terrain/overlap validator, collision object, or visible model instance.
- The camper's campsite visitor request and its later slot-5 resident record remain distinct stages. The `c68f30` loop covers slot 5 structurally, but the day/housing gates that transition this record to its house and visible actor remain open.
- Model and audio payloads remain catalogue-only; this trace uses only native/data evidence.

Raw VAs, instruction bytes, source hashes, call-index records, and the bounded interpretation are in [the JSON ledger](../output/gameplay/resident_camp_actor_manager_dispatch_followup_20261107.json). No game or save was executed, no save was modified, and no Godot content was changed.
