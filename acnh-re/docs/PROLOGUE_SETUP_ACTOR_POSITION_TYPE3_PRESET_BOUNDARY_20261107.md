# Prologue `SetupActorPosition(Type=3)` and UID-selected EventPlaza anchor

**Date:** 2026-11-07
**Scope:** Static join of the prologue arrival EventFlow, the UID-selected `FieldMainFieldParam` row and `_EventPlaza` BYML, and native `SetupActorPosition` Type 3. This pass does not rebuild or execute the game.

## Result

A direct static data path from the selected preset's `FieldData_EventPlaza` row into the Type 3 position request is proven. The two integer values under BYML hashes `h_035daede` and `h_799dfdbe` are copied by the EventPlaza loader into `SaveMainField` offsets `+0xcfa2c` and `+0xcfa30`. A native updater reads that saved pair and updates the same global position object returned by `0x469680`; Type 3 calls that getter, samples the current root-grid ground, adds observed offsets `-7.5` and `+15.0`, and submits a generic position request.

That establishes an EventPlaza-anchor input to Type 3. It does **not** prove that the two values themselves are the player's or airplane's named spawn coordinates, nor which actor receives the generic request. Their hash names, units, axes/origin, and the final visible landing target remain open.

## EventFlow branch and camera cue

`Tutorials_Prologue2_Arrival` Event2 switches on `cLand:ValidateVillageSave`. The literal case value `0` goes through messages 003/004, a wait and fade, then Event5 invokes `EventFlowSystemActor.EventFlowActionSetupActorPosition` with `Type=3`. Literal value `1` goes to messages 001/002 and ends. This report preserves the literal values without assuming boolean polarity.

After the position action, the flow sets the `FirstPlayAfterPlayerMake` flag, then a camera action targets `Npc:rco` with parameter `EventPlazaPrologue`. That camera key is a separate cue and does not identify the actor in the Type 3 request.

## Native evidence

The resolved action registration identifies parameter `Type: int`, registration hash `0x5233e4d1`, constructor `0x2fe930`, and the vtable slot 8 handler at raw `main.elf` VA `0x2ff0d0`. In that function's Type 3 case:

- `0x2ff250` calls `0x469680`, which returns `*(global 0x32d6f98) + 0x40`.
- `0x2ff284` calls `0x1577a0` with the current root-grid context (`root + 0x28`) to sample/adjust against terrain.
- `0x2ff2a4` calls the vector/transform helper `0x11c780`; the case-3 decomp includes offsets `-7.5` and `+15.0`.
- `0x2ff2d4` / `0x2ff2e8` build the position request; `0x2ff30c` calls `0xca4370` to dispatch it through a generic callback list.

The dispatcher iterates a list and invokes the supplied callback's virtual method. It does not identify a player or airplane object. Consequently the name `SetupActorPosition` and the prologue context do not, by themselves, prove the request's actor target.

## UID → EventPlaza → shared anchor

The native EventPlaza loader at `0x5598c0` resolves the selected UID through the `FieldMainFieldParam` row and builds the `<FieldData>_EventPlaza` resource name. The table has 96 rows, and all 96 corresponding decoded EventPlaza JSON resources were found. Each has two integer values under hashes `h_035daede` and `h_799dfdbe`.

At `0x559ad4`, the loader calls `0xf74c50`, which writes the two values to `SaveMainField+0xcfa2c` and `SaveMainField+0xcfa30`. The loader then calls `0x47c1e0` with `global 0x32d6f98 + 0x10`. That updater reads the saved pair through `0xf74c30`, passes it into `0x52bcf0`, and calls `0x52c5f0(param+8, param+0x30)`. Since `param` is `global+0x10`, `param+0x30` is `global+0x40`, the same pointer returned by `0x469680` and consumed by Type 3. This is the direct shared-object relation between the UID-keyed EventPlaza row and the Type 3 request.

The external save crosswalk proposes names `EventPlazaLeftUpX` and `EventPlazaLeftUpZ` for those offsets, based on an external Treeki/CylindricalEarth schema. Those names are not local native symbols, and the alignment does not establish units or coordinate origin.

## Conversion guidance

Preserve the chosen UID, `FieldData` stem, and both raw hash values. Reproduce their native route into the shared anchor, then apply the root-grid height query and the observed Type 3 offsets before generic callback dispatch. Keep the Rco camera cue separate. Do not label the result as player/airplane spawn until the generic receiver identity and the pair's coordinate semantics are proven.

## Evidence artifact

The paired JSON contains the exact EventFlow event records, registration fields, raw PCs/call edges, 96-row UID/EventPlaza inventory with decoded-file SHA-256 hashes, and hashes for the main ELF and referenced analysis sources:

`output/gameplay/prologue_setup_actor_position_type3_preset_boundary_20261107.json`
