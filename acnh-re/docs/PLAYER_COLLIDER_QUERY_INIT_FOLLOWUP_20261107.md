# Player collider query initialization follow-up

This follow-up traces the `0x7bccf0` sandbox boundary through its world singleton, constructor, grid accessor, and registry list. It also checks how the query reaches movement helpers. Scope is ACNH 1.0.0 native source and existing repository fixtures; no Godot or build work was done.

## Finding

The fault at `0x172780` is a sandbox setup fault. The singleton slot is null, so `0x7bccf0` forms the invalid context pointer `0x28`; `0x1577a0` then reads mapped ELF bytes as if they were the grid pointer at context `+0x78` (root `+0xa0`). That fabricated value reaches `0x172740`, which faults while reading grid `+0x30`. This is not evidence of an ACNH gameplay fault or a terrain result. The earlier reproduction remains in [player_7bccf0_boundary_native.json](../output/mechanics/player_collider_query_remainder_20261107/player_7bccf0_boundary_native.json).

Static source gives a useful root layout, but not a faithful live root/grid/list fixture. The singleton constructor `0x197740` is called directly only from the broad initializer `0x96ef0`; it allocates `0xf88` bytes, constructs the root context at `root+0x28`, and initializes the query list to empty. It explicitly leaves the grid pointer at `root+0xa0` null. The actual loader that installs a live grid, its terrain records, and the query-candidate list is still **OPEN**.

## Root and accessor layout

| Native source | Exact access | Evidence and limit |
|---|---|---|
| Singleton `0x32d0de8` | Relocation points to slot `0x33728b0`; the slot holds the root pointer. In a fresh `Sandbox`, the slot is zero. | **PSEUDO/NATIVE**. The address and empty value are from the verified ELF sandbox. |
| Constructor `0x197740` | Allocates `0xf88`; constructs members at root `+0xf68`, `+0x8`, and `+0x28`; sets root `+0xf60` to zero; stores the root in the singleton slot. | **PSEUDO**. Its only indexed direct caller is `0x96ef0` ([analysis_decomp/96ef0.c:120](../output/binary/analysis_decomp/96ef0.c:120)). The root is not produced by the isolated terrain fixtures. |
| Query context `root+0x28` | `0x156840` initializes the lock at context `+0x8`, circular-list sentinel at `+0x48/+0x50`, signed link bias `+0x5c = 8`, and zeroes the grid pointer at context `+0x78` (root `+0xa0`). It also clears the readiness byte at context `+0xee8` (root `+0xf10`). | **PSEUDO**. These are constructor defaults, not proof that startup or island loading later fills them. |
| `0x1577a0` → grid query | Reads `context+0x78`; when non-null, calls `0x172740(grid, position, status, 1)`. `0x18ba40` separately requires a non-null root, non-null root `+0xa0`, and a nonzero byte at root `+0xf10`. | **PSEUDO**. The test's fabricated pointer came from the null-root sandbox, not a valid grid. |
| Grid accessor `0x172740` | Converts the position through `0x52b280`; checks x/z against width `grid+0x30` and height `grid+0x34`; reads geometry floats at `+0x20/+0x24`, base records through `+0x48`, overlay count `+0x50`, and overlay pointer `+0x58`. It indexes `x + width*z`; records have stride `0x34`, with quadrant attributes at bytes `0x30..0x33`. Overlay byte `7`, missing overlay storage, or flag bit 0 selects the base record. | **PSEUDO**; the compatible record/overlay accessor is also exercised in the separate **NATIVE** terrain fixture. That fixture does not execute `0x7bccf0` or populate the full root. |
| Candidate list in `0x157270` | Locks context `+0x8`; empty when `*(context+0x50) == context+0x48`; otherwise uses bias `*(s32*)(context+0x5c)`, calls each candidate's vtable slot `+0x30`, and advances through a link at `candidate+bias+8`. | **PSEUDO**. Constructor gives the empty sentinel shape and bias 8. Candidate object vtables, populated list contents, and their runtime producer remain **OPEN**. This list is distinct from the additional registry at context `+0xef0`, which registration helper `0x1651b0` updates. |

The two list structures matter: the constructor's query list is at context `+0x48/+0x50`; the registration helper writes to the separate context `+0xef0` list. The latter cannot, by itself, supply the candidate list consumed by `0x157270`.

## Constructor probe and fixture comparison

Calling the original `0x197740` in a fresh `Sandbox` does not construct a root. The allocator global at `0x33d08a8` is zero, so `0x1967780` takes its malloc fallback. The fallback reaches an unresolved PLT/GOT path: `0x220e3a8` loads `x17` from `0x32ce7a0`, then `0x220e3b0` branches through it. That slot is zero in the sandbox, and emulation stops at PC zero with `UC_ERR_EXCEPTION`. There is no invalid-memory hook event, and the singleton slot remains zero. This is an emulator/runtime dependency, not game behavior. The constructor path needs the initialized allocator/runtime and surrounding subsystem globals that `0x96ef0` relies on.

The existing native fixtures deliberately reconstruct narrower contracts:

- [terrain_native.py](../tools/terrain_native.py) writes `0x32d0de8 → world` and `world+0xa0 → grid`, then executes terrain and ground aggregators. It verifies the grid record contract, but does not construct the `0xf88` root or populate its query-candidate list.
- [ground_context_gate_native.py](../tools/ground_context_gate_native.py) sets the same singleton and a synthetic `world+0xa0` pointer to exercise stage/readiness guards. It forces the selector's empty-item branch (`stage_manager+0xa58 = 0xfffe`); this is not a loaded grid.
- [world_registry_release_native.py](../tools/world_registry_release_native.py) points the singleton at `owner-0x28` so wrapper `0x168140` can recover an owner at singleton `+0x28`. That fixture tests unlink/release behavior and does not represent the world-root constructor or query list.

Because none supplies a live root, actual terrain loader output, readiness state, and candidate vtables, I did **not** rerun `0x7bccf0` with a hand-patched root. A non-null grid pointer alone would not make the full query faithful.

## Movement and scheduling connection

Static call paths connect the query to movement code, but not to raw controller input or a frame scheduler:

- `0xe42b30` calls `0x7bccf0` with its method position (`&fStack_b0`) and then stores motion state at `param_4+0x574` and `param_4+0xf58`. The path uses time/target and actor state supplied to it; the producer of those inputs is not established.
- `0xdac780` and `0xda86b0` call `0x7bccf0` with the actor's position at `actor+0x278` for selected correction branches. `0xda86b0` has the direct caller `0xdac780`.
- `0xdac550` reads the stored components at `param_2+0xf50/+0xf58` and adjusts the referenced actor position. `0xdac550`, `0xdac780`, `0xe17cb0`, and `0xe42b30` have no direct callers in the indexed call graph. No target edge for `0xe17cb0` or `0xe42b30` appears in the repository's recognized relocated code-pointer arrays. These absences leave indirect dispatch possible; they do not prove the functions are unused.

Therefore the source supports a **PSEUDO** movement-helper ↔ ground-query relationship, but the HID/controller sample → stored-field producer → scheduled helper invocation path remains **OPEN**. Existing bounded movement executions use supplied fields and do not close that chain. This follow-up executes no bridge crossing, ladder climb, river/cliff traversal, or player build edit; those links remain **OPEN** as mapped in the broader movement report.

## Asset and conversion limit

The terrain fixture's runtime ground records are 52 bytes with four sector-attribute bytes. The island preset artifacts are a separate 14-byte-per-cell BYML structure. The repository has static preset-transfer evidence and catalogued `_pbc` names (**STRUCT/CAT**), but no proven conversion from the 14-byte preset cells or PBC payloads into this runtime grid/collider layout. That conversion remains **OPEN**; the fixture's 52-byte records must not be described as extracted game collision geometry.

Evidence labels retain the shared convention: EF (EventFlow), TBL (tables), STRUCT (parsed asset/layout), PSEUDO (static native source), NATIVE (bounded original-code fixture), CAT (catalog candidate), and OPEN (unproven link). This follow-up adds **PSEUDO** root/grid/list offsets and records a **NATIVE** harness initialization failure; it produces no gameplay query result. See [WORLD_TERRAIN_MOVEMENT_PROOF_20261107.md](WORLD_TERRAIN_MOVEMENT_PROOF_20261107.md) for the broader story, terrain, and traversal map.
