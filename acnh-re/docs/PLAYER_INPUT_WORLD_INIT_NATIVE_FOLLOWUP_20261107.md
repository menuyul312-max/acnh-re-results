# ACNH 1.0.0 player-input and world-root initialization follow-up

This note closes the static tracing pass from HID polling toward player movement and from the world singleton toward the terrain/query grid. A machine-readable evidence ledger is [here](../output/mechanics/player_collider_query_remainder_20261107/player_input_world_init_native_followup_20261107.json). It records raw ELF PCs so they can be distinguished from Ghidra's display labels, which in this corpus commonly add `0x100000`. No game execution, save modification, synthetic gameplay claim, or Godot work was performed.

## Finding

The ELF contains a concrete Npad polling routine and a scheduler registration record named `sys::ControllerManager::update()`. The registered task record receives pointer `0x14ceed0` from relocated data slot `0x330ee90`; that routine only copies a controller-subobject field and checks manager state. It contains no call to the Npad sampler or to the mapped player movement helpers. The actual scheduler frame dispatcher, execution of the registered task, and data flow from sampled controller state into player motion remain **OPEN**.

The world path is more complete statically. Root construction is called from `0x96ef0`; a separate unindexed body at `0xfe5a00` calls `0x1978a0`, which tail-branches to grid initializer `0x156e30`. That initializer builds the grid backing storage, installs it at root `+0xa0`, and inserts the grid object into the candidate list traversed by the ground query. The lifecycle target's runtime invocation, the nonzero writer for root readiness byte `+0xf10`, live terrain contents, and a live query result remain **OPEN**.

All addresses below are raw ELF virtual addresses/PCs. Static native disassembly and the indexed call/relocation records are **PSEUDO** evidence; they establish code and edges, not execution during gameplay.

## HID, scheduler, and player movement

### Startup and registered task

| Edge | Exact raw evidence | Result / limit |
|---|---|---|
| Startup creates scheduler groups | `0x1535e90 BL 0x15369c0` | Scheduler group setup is present in startup code. It is not a recovered frame pump. |
| Startup registers controller task | `0x1535eec BL 0x14cef10` | `0x14cef10` initializes task data at manager `+0x288` and links it into scheduler group `+0x5a0` at `0x14cef94 BL 0x1979ff0`. |
| Startup initializes HID services | `0x1535f10 BL 0x14ced30`; within it `0x14ced44 BL 0x220f040` (`InitializeNpad`) and `0x14ced48 BL 0x220f050` (`InitializeTouchScreen`) | This proves service initialization code, not polling or input delivery to a player. |
| Task label | `0x14cef68` forms string pointer `0x293ba29`; the string is `sys::ControllerManager::update()` | The task name is backed by a task record that is actually inserted into the scheduler group. A label does not prove dispatch. |
| Task record pointer | `0x14cef38` loads relocated global slot `0x330ee90`; `0x14cef3c` stores it at manager `+0x2f0`. ELF relative relocation resolves slot `0x330ee90` to `0x14ceed0`. | The registered task record contains pointer `0x14ceed0`. The scheduler's later indirect invocation is not recovered. |
| Registered body | `0x14ceed0` loads manager subobject `[x0+0x210]`; `0x14ceee4` calls `0x14cf380`, which copies subobject field `+0x60` to `+0xdc`; `0x14ceee8` tests manager byte `+0x208`, then exits through `0x14cf390` (`RET`). | This body does not call `0x1968b80`, any `GetNpadStates` wrapper, or mapped player movement/query helpers. The exact task-record ABI and whether the scheduler invokes it remain **OPEN**. |

`0x1979ff0` is the registration/list-link helper called at `0x14cef94`; its code links the task node and does not iterate or execute tasks. Group-state helper `0x197aa70` likewise does not supply the missing per-frame dispatch edge. Therefore the following is the strongest supported chain:

`startup (0x1535ad0) → task registration (0x14cef10) → named task record / pointer 0x14ceed0`

The chain does **not** continue statically to a frame pump or player movement update.

### Npad polling routine

An unindexed raw ELF body at `0x1968b80` is a concrete Npad polling method. The code-pointer sequence beginning at `0x31a4020` contains `0x1968b80` at pointer `0x31a4040` (offset `+0x20`). Constructor code at `0x1968a60` stores a vptr derived from the relocated global at `0x33190068` plus `0x10`. This supports identifying the body as a virtual update entry, while the recognized-pointer-array metadata itself cautions that pointer sequences are not automatically C++ vtables. The body has no indexed function row, so direct-call owner labels are unavailable; the raw instruction PCs below are verified from ELF disassembly.

At `0x1968b80`, the method reads a configured count from object `+0x28`, iterates controller IDs (including the handheld ID `0x20` in the sentinel slot), calls `nn::hid::GetNpadStyleSet` at `0x1968bd4`, and selects one of five imported state readers according to style bits:

| Raw call PC | Imported target | State family |
|---|---|---|
| `0x1968c14` | `0x2210250` | `GetNpadStates(NpadHandheldState*)` |
| `0x1968c2c` | `0x2210260` | `GetNpadStates(NpadJoyDualState*)` |
| `0x1968c44` | `0x2210270` | `GetNpadStates(NpadFullKeyState*)` |
| `0x1968c5c` | `0x2210280` | `GetNpadStates(NpadJoyLeftState*)` |
| `0x1968c74` | `0x2210290` | `GetNpadStates(NpadJoyRightState*)` |

Each call passes an output buffer, count `0x10`, and the selected Npad ID. The method also requests six-axis handles at `0x1968cd4`, vibration handles at `0x1968cfc`, starts sensors at `0x1968d20`, initializes vibration devices at `0x1968d5c`, and samples six-axis states at `0x1968da8`. These calls establish a polling/update routine in the binary, but not its runtime schedule or any interpretation of button bits as player actions.

The five direct import callsites are present in the call index with `owner_va = NULL`, consistent with the containing body being unindexed. Thus the prior broad statement that no Npad `GetNpadStates` calls had been found is superseded: the raw body and five sites are now identified, but no runtime caller or player link is proven.

### Input-to-player chain and adjacent false joins

The movement-side map has helpers that write velocity/movement fields and invoke ground queries, including `0xe17cb0`, `0xe42b30`, `0xdac550`, `0xdac780`, and `0xda86b0`. No direct call from `0x14ceed0` or the polling body `0x1968b80` to those helpers is present. The separate manager queue reader `0x14cf070` copies record words `+0x18/+0x1c` to manager fields `+0x278/+0x27c`, but its indexed caller is `0x14ce8a0`; no producer or bridge from those fields to player movement is established.

Touchscreen service initialization at `0x14ced48` is separate from polling routines that call `GetTouchScreenStates` (`0x14b8ff0` and `0x1302ab4` to import `0x220efa0`) or `GetTouchScreenState` (`0x1efc0cc` to `0x2211720`). Existing UI analysis maps touch polling to UI hit testing; it does not prove that Npad buttons feed player movement. This prevents treating any touch/UI update as the missing player-input edge.

**Status: OPEN** for (1) the real scheduler frame loop and indirect task invocation, (2) the runtime caller/timing of `0x1968b80`, (3) button-state decoding into player commands, (4) producer/consumer relation for manager queue fields `+0x278/+0x27c`, and (5) a scheduled movement helper invocation driven by sampled input.

## World root, grid, and query readiness

### Root construction and lifecycle caller

The root global reference at `0x32d0de8` relocates to singleton storage slot `0x33728b0`. Root constructor `0x197740` allocates `0xf88`, initializes the query context at root `+0x28`, and stores the pointer in the singleton slot. Its only indexed direct callsite is `0x97200` in function `0x96ef0`.

The constructor sets context `+0x48/+0x50` to an empty circular-list sentinel, context `+0x5c` to link bias `8`, context `+0x78` (root `+0xa0`) to null, and context `+0xee8` (root `+0xf10`) to zero. The separate registry at context `+0xef0` is not the query candidate list.

A static lifecycle body exists at raw address `0xfe5a00` without an indexed function row. Recognized relocated pointer sequences at `0x30ed820` and `0x30edad0` contain this target, but those tables alone do not prove runtime invocation. Within the body, `0xfe5ab0–0xfe5ab8` loads the root singleton and pointer, and `0xfe5abc BL 0x1978a0`. The target clears root `+0xf60`; at `0x1978a8` it tail-branches to `0x156e30(root+0x28)`. This is a static caller path to the grid initializer, not a live world-load trace.

### Grid installation and query-list producer

`0x156e30` checks/uses any prior grid at context `+0x60`, otherwise allocates a backing slab, constructs a `0x118` grid object via `0x172090`, and initializes it via `0x1725f0`. Under the default branch it selects dimensions `64×64` and allocates `width × height × 0x80` bytes for the root context's backing slab. The configured alternate branch reads dimensions from context `+0xf24/+0xf28`; the grid initializer also contains an alternate `160×160` path with `0x300000` slab allocation. These are allocation/configuration branches, not proof of an island's loaded terrain values.

`0x1725f0` writes width/height at grid `+0x30/+0x34`, allocates base records of `count × 0x34` bytes at `+0x48`, a `count × 4` flag array at `+0x68`, and optional overlay records of `count × 0x34` bytes at `+0x58`. Its default initializer `0x172280` fills base records with zero floats and sector bytes `7`, initializes flag bits, and fills optional overlay floats with `-500.0` plus sector bytes `7`. This proves default storage initialization only; it does not show that island data is loaded or converted into these runtime cells.

After setting the grid pointer at context `+0x78` (root `+0xa0`), `0x156e30` checks its embedded links. When both links are null, it locks context `+0x8` at `0x156e84`, calls list insertion helper `0x1967c40` at `0x156e94` with list head `context+0x48` and candidate pointer `grid + *(s32*)(context+0x5c)`, increments count at context `+0x58` at `0x156e9c–0x156ea4`, then unlocks at `0x156ea8`. This statically establishes `0x156e30` as a query-candidate producer for the grid object.

The candidate consumer `0x157270` walks context `+0x48/+0x50` and indirect-calls each candidate's vtable slot `+0x30` at PCs `0x1572f8` and `0x157350`. The relocated code-pointer sequence at `0x30376a8` contains target `0x172740` at pointer `0x30376d8`, exactly sequence offset `+0x30`; `0x172740` is also directly reached from grid accessor `0x1577a0` at `0x1577f0`. This supports a static grid-candidate dispatch target, with the array's own caveat that pointer sequences alone are not proof of a C++ vtable or invocation.

### Readiness and live result

Readiness predicate `0x18ba40` returns true only if the root singleton is nonnull, root `+0xa0` is nonnull, and root byte `+0xf10` is nonzero. The root constructor clears that byte. The grid lifecycle path `0x156e30` writes context `+0x78` but does not set context `+0xee8` / root `+0xf10`. No nonzero setter for this exact root field was established in the inspected static path. The source of readiness and the runtime lifecycle event that would satisfy it remain **OPEN**.

Consequently, the initializer and candidate-list producer are statically mapped, while the live producer/result remain **OPEN**: there is no verified execution showing this lifecycle body running, island terrain populating the backing cells, readiness becoming true, or `0x7bccf0` returning a gameplay ground/collision result.

## Existing fixture coverage

No fixture in the repository gives a faithful live result for these chains, and no new fixture was run.

| Existing artifact | What it covers | Why it does not close this chain |
|---|---|---|
| `tools/terrain_native.py` / `output/mechanics/terrain_native.json` | Bounded native terrain/grid access with supplied `world+0xa0 → grid` and runtime record data | Does not execute the root constructor or lifecycle, build the query list, or invoke authentic candidate vtables. |
| `tools/ground_context_gate_native.py` / `output/mechanics/ground_context_gate_native.json` | Selected stage/readiness guard paths with prepared state | Uses synthetic guard memory and an empty-item early return; it is not a loaded world. |
| `tools/player_7bccf0_boundary_native.py` / `output/mechanics/player_collider_query_remainder_20261107/player_7bccf0_boundary_native.json` | Null singleton boundary in a fresh sandbox | Singleton is null; the resulting invalid read at `0x172780` is emulator setup failure, not a gameplay result. |
| `tools/world_registry_release_native.py` / `output/mechanics/world_registry_release_native.json` | Separate region-registry unlink/release behavior | Registry layout at context `+0xef0` is not the query list at context `+0x48`. |

No faithful initialized world root/grid/readiness/list/vtable fixture exists, and no fixture connects the HID poller or scheduler task to a live player movement update. Hand-building those runtime objects would only test guessed state, so it was not done.

## Evidence still required to close

1. Identify the scheduler's frame/update iteration and show the registered `0x14ceed0` task is dispatched; separately identify the runtime call path for virtual Npad update `0x1968b80`.
2. Trace sampled Npad buttons through command/state translation into the player actor, including the caller that writes movement inputs and invokes the mapped movement helpers.
3. Recover the source and semantics of queue nodes consumed by `0x14cf070` and join manager fields `+0x278/+0x27c` to player-input fields if they are on the movement path.
4. Prove which runtime load event invokes `0xfe5a00`/`0x1978a0`, locate the nonzero writer to root readiness `+0xf10`, and observe the actual loaded terrain/backing data.
5. Obtain a faithful native execution with the original root, populated grid, candidate list, and relocated candidate implementations that produces a valid `0x7bccf0` result.

The static initializer chain and candidate producer are now mapped; the HID-to-player link and the world runtime producer/readiness/result are not. Overall gameplay integration remains **OPEN**.

### Source identity and references

- Main ELF SHA-256: `5bf707c3dc5dac0ad9635af7d336ec580f81c3f7876d0f55400d1900e3415d74`.
- Recognized relocated code-pointer array JSON SHA-256: `64d474068ca289f9146f7f32e6647a16a05e8f5be8e635615a478744b62ef822`.
- Main source: `output/binary/analysis_decomp/1535ad0.c`, `14cef10.c`, `14ced30.c`, `14cf070.c`, `197740.c`, `156840.c`, `156e30.c`, `172090.c`, `1725f0.c`, `172280.c`, `157270.c`, `1577a0.c`, and `18ba40.c`.
- Raw-only bodies: `0x1968b80` and `0xfe5a00`; neither has an indexed function row. Their PCs above come from direct ELF disassembly.
- Pointer evidence: `output/binary/code_pointer_arrays.json`, entries at `0x31a4020`, `0x30ed820`, `0x30edad0`, and `0x30376a8`.
- Related reports: `PLAYER_INPUT_TRAVERSAL_INDIRECT_FOLLOWUP_20261107.md`, `PLAYER_COLLIDER_QUERY_INIT_FOLLOWUP_20261107.md`, and `WORLD_TERRAIN_MOVEMENT_PROOF_20261107.md`.
