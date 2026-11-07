# Player input, scheduler, and traversal indirect-dispatch follow-up

This ACNH 1.0.0 follow-up checks the controller/HID side of the movement chain, scheduler registration and indirect edges, and ladder/river/cliff/bridge traversal. It adds static evidence to [the world-root initialization follow-up](PLAYER_COLLIDER_QUERY_INIT_FOLLOWUP_20261107.md). No Godot or build work was done, no new native fixture was run, and the synthetic world-root fixtures were left unchanged.

## Finding

Static source now proves that startup initializes the scheduler and controller manager, registers a task named `sys::ControllerManager::update()` into the `SysCalc_Controller` group, and separately initializes Nintendo Npad and touchscreen services. Another controller-manager routine copies a queued record's two 32-bit fields to manager offsets `+0x278/+0x27c`. This narrows the control-side map, but it does not identify a HID sampling function, the record producer, the task-dispatch frame loop, or a path from those manager fields to the player movement fields used by the bounded physics helpers. That integration remains **OPEN**.

Ladder-related state and action code is present, and river-maker actions perform spatial checks through the ground-query helper. These are **PSEUDO** evidence for tool/state checks, not a successful climb, river crossing, cliff traversal, or bridge crossing. The earlier `0x7bccf0` query fault still cannot be used as gameplay evidence: no faithful initialized world root, loaded terrain grid, query list, and candidate vtables are available in the native fixtures.

## Controller and frame-scheduler chain

| Edge | Source evidence | Status and limit |
|---|---|---|
| System startup → scheduler/controller setup | `0x1535ad0` allocates/constructs the scheduler at global `0x340e1e0`, calls `0x15369c0`, creates the controller manager at `0x340e6e0`, calls `0x14cef10`, then `0x14ced30`. The indexed direct-caller list for `0x1535ad0` is empty, so this is an initializer path, not a recovered frame entry. | **PSEUDO**. Startup is established in source; execution timing is not. |
| Scheduler group registration | `0x15369c0` assigns group-name strings at offsets including `+0x5e8`, registers child groups at `+0x508/+0x5a0/+0x638`, and toggles group state through `0x197aa70`. The string reference resolves `+0x5e8` to `SysCalc_Controller`; the group object containing that name begins at `+0x5a0`. | **PSEUDO**. Group setup only. |
| Controller task registration | `0x14cef10` prepares the task record at manager `+0x288`, stores unresolved context/pointer fields from globals, labels it `sys::ControllerManager::update()`, and calls `0x1979ff0(scheduler+0x5a0, task)`. `0x1979ff0` links the task into the group list; it does not execute the task. | **PSEUDO**. The name and list registration are known; the callback implementation and dispatch are **OPEN**. |
| HID initialization | `0x14ced30` calls `nn::hid::InitializeNpad`, `nn::hid::InitializeTouchScreen`, then `0x14ced60`. The latter has no saved pseudocode; its disassembly shows internal record allocation/setup and cleanup, but no Npad sample call is present in the visible range. | **PSEUDO**. Service initialization is not controller polling. |
| HID polling | The imported `GetNpadStates` wrappers (`0x2210250–0x2210290`) have no indexed direct callers. Searches of decomp sources find wrapper stubs but no game-side sample call. | **OPEN**. This does not exclude an unrecognized indirect/import path. |
| Controller-manager fields | `0x14cf070` moves a queued record through the manager list and copies record fields `+0x18/+0x1c` into manager `+0x278/+0x27c`; if the list is empty it copies fallback fields. The indexed direct caller is `0x14ce8a0`, which also removes/clears the record. | **PSEUDO**. Queue-node producer, sample meaning, and relation to player input are **OPEN**. |
| Group dispatch → frame/update | `0x1979ff0` is a list-link helper. `0x197aa70` changes group states via virtual calls. The recovered registration code does not show the scheduler iterating tasks and invoking the named update task. | **OPEN**. Need the actual task-manager frame pump and the task object's resolved callback/vtable target. |

The movement-side helpers remain as mapped in the prior report: `0xe17cb0` writes velocity at player `+0x574` and a movement triplet at `+0xf58` from supplied timing/target inputs; `0xdac550` consumes movement components and moves the actor at `+0x278`; `0xe42b30`, `0xdac780`, and `0xda86b0` reach `0x7bccf0` on selected branches. Their direct-caller/dispatch links do not identify a HID source or a scheduler invocation. Existing bounded native executions are listed in [WORLD_TERRAIN_MOVEMENT_PROOF_20261107.md](WORLD_TERRAIN_MOVEMENT_PROOF_20261107.md); they use prepared fields and are not a live controller trace.

## Indirect-edge search

The registered task label is stronger than a name-string hit alone because `0x14cef10` actually inserts its task record into scheduler group `+0x5a0`. It still does not reveal the function reached by the scheduler. The record stores a global pointer from `0x340ee90`, while the group task-list and manager use virtual calls; the source/indexed relocation data did not resolve the pointer to a task body.

I filtered the repository's recognized `code_pointer_arrays.json` targets for the movement, controller, ladder, and river functions. The filter did not find targets for the movement helpers, `0x14ced30/0x14ced60/0x14cef10`, `0xe409c0`, `0xe40b70`, `0xe40ce0`, `0xe3f100`, `0xe49f90`, or `0xe4a500`. This is only a scan of the recognized relocated pointer sequences; it cannot rule out runtime-built vtables or unrecognized tables.

One apparent ladder-state hit needs a specific caution. `0xe41170` appears at pointer `0x3338170` in the ELF `.init_array` (`0x3332298`, size `0xbc30`). Its decompilation is a static initializer that registers strings including `PlayerLadderReadyWait` and `PlayerLadderAction`. This is constructor registration, not a runtime movement callback. The `0x585c80` reference to `State::cSwimRiver` and `State::cDriftRiver` is likewise a string reference in one initializer; by itself it does not prove a player swim/drift routine.

## Traversal paths

| Route/action | Static evidence | Status and limit |
|---|---|---|
| Bridge | The story flow previews `cBridge`, grants construction kit UID 7211, and records the selected bridge placement flag. Bridge/table IDs and model variants are **TBL**; the story does not supply bridge endpoint cells, transform, a physical crossing action, or a crossing result. | **EF/TBL/OPEN**. No bridge crossing is proven. |
| Ladder | `0xe409c0` sets ladder-related state flags and emits `PlayerLadderIsSkew` / `PlayerLadderToUp` labels; it is reached from `0xe40b70` and `0xe40ce0` after position/state checks. A separate action dispatcher `0xdaf680` routes case `0x10` to `0xe3f100`, whose source calls `0x7bccf0` in spatial checks and contains `Player_ToolActionError` / `DisableLadder` state names. | **PSEUDO/OPEN**. Ladder state and a ladder-related action gate exist; there is no validated climb, live callback chain, or native success trace. |
| River | `0xe49f90` and `0xe4a500` contain `PlayerRiverMakerDig/FallDig` and `PlayerRiverMakerBury/FallBury` action labels and use `0x7bccf0` before later action helpers. These names and calls concern river-making tool actions. | **PSEUDO/OPEN**. Terraform action checks are not river crossing. |
| Water/swim/drift | `State::cSwimRiver` / `State::cDriftRiver` strings reference `0x585c80`; no player traversal execution or input-to-state dispatch was recovered. | **PSEUDO/OPEN**. State labels alone do not establish swimming/drifting behavior. |
| Cliff | The earlier native/parameter reports include cliff/water jump-distance parameter names and Island Designer cliff-maker action labels. No player input → cliff-edge validator → movement update → successful traversal chain is established. | **TBL/PSEUDO/OPEN**. NPC A* flags and edit actions are not player cliff crossing. |

The story ordering remains placement/progression, not route validation: bridge placement is followed by housing kits and a ladder recipe, and the later plot flow checks furnishings and quest flags. No EventFlow step requires the player to cross the bridge or climb a ladder before continuing. The ladder recipe UID 2615 and bridge kit UID 7211 are **TBL/EF** evidence for unlock and placement workflow, not traversal.

## Fixture and asset limits

No new native execution was appropriate for this pass. The available controller and movement fixtures do not provide a real HID sample, scheduled task frame, or live player-input producer. For `0x7bccf0`, the fresh sandbox world singleton is null; existing terrain fixtures seed only the narrower `world+0xa0 → grid` access contract and do not provide the initialized `0xf88` root, readiness state, live candidate list, or candidate vtables. I did not synthesize those values or rerun the original query.

The existing **NATIVE** terrain fixtures use runtime records with a 52-byte stride and four sector-attribute bytes. Parsed LandMaking presets are **STRUCT** data with 14-byte cells; `_pbc` resources and model/collision families remain **CAT** candidates. No conversion from preset cells/PBC into the runtime grid or player collision records is proven, so that join remains **OPEN**.

The status labels used here are **EF** (EventFlow structure), **TBL** (game tables), **STRUCT** (parsed asset/layout), **PSEUDO** (static native code), **NATIVE** (bounded original-instruction fixture), **CAT** (catalog candidate), and **OPEN** (unproven integration). The only new evidence in this follow-up is **PSEUDO**; it adds no NATIVE gameplay result.

## Exact remaining inputs

To close the controller-to-traversal chain, the missing evidence is specific: (1) the actual HID sampler or its indirect target, (2) the producer and record semantics for nodes consumed by `0x14cf070`, (3) the task-manager frame loop and resolved `0x340ee90` callback/vtable target, (4) a field/data-flow join from controller manager `+0x278/+0x27c` to the player movement inputs or velocity fields, and (5) a faithful world-root/grid/readiness/candidate-list fixture for `0x7bccf0`. For physical traversal, a live bridge/ladder/water/cliff state path and a successful collision/traversal result are still required.

Overall status remains **OPEN**. The prior native sandbox fault remains an emulator/setup boundary, not a gameplay failure.

### Source references

- [1535ad0.c](../../../acnh-re/output/binary/analysis_decomp/1535ad0.c:189), [15369c0.c](../../../acnh-re/output/binary/analysis_decomp/15369c0.c:11), [14cef10.c](../../../acnh-re/output/binary/analysis_decomp/14cef10.c:10), [14ced30.c](../../../acnh-re/output/binary/analysis_decomp/14ced30.c:2)
- [14cf070.c](../../../acnh-re/output/binary/analysis_decomp/14cf070.c:11), [1979ff0.c](../../../acnh-re/output/binary/analysis_decomp/1979ff0.c:2), [197a3a0.c](../../../acnh-re/output/binary/analysis_decomp/197a3a0.c:1), [197aa70.c](../../../acnh-re/output/binary/analysis_decomp/197aa70.c:1)
- [e17cb0.c](../../../acnh-re/output/binary/analysis_decomp/e17cb0.c:2), [e409c0.c](../../../acnh-re/output/binary/analysis_decomp/e409c0.c:2), [e49f90.c](../../../acnh-re/output/binary/analysis_decomp/e49f90.c:2), [e4a500.c](../../../acnh-re/output/binary/analysis_decomp/e4a500.c:2)
- [e3f100.c](../../../acnh-re/output/binary/analysis_decomp/e3f100.c:5), [daf680.c](../../../acnh-re/output/binary/analysis_decomp/daf680.c:276), [e41170.c](../../../acnh-re/output/binary/analysis_decomp/e41170.c:1), [585c80.c](../../../acnh-re/output/binary/analysis_decomp/585c80.c:1)
- [ELF section map](../../../acnh-re/output/binary/elf.json), [recognized pointer arrays](../../../acnh-re/output/binary/code_pointer_arrays.json), and [world-root fault/fixture ledger](../output/mechanics/player_collider_query_remainder_20261107/player_7bccf0_boundary_native.json)
