# ACNH 1.0.0 — SaveProc worker, file I/O, and pocket-field trace

**Status:** static native-code trace. This work did not run the game, write a save, create synthetic save fixtures, or test reload persistence.

The trace adds one positive persistence finding: the save-operation state machine has a conditional call to Nintendo's `nn::fs::Commit`. It still does not establish which exact SaveSimpleSave/crafting request satisfies that branch, identify the SaveProc serializer callback, or connect a `WriteFile`/`FlushFile` call to it. The local 1.0.0 layout also does not name the pocket views reached by the craft helpers.

## SaveProc registration and queued work

Startup function `0x96ef0` creates the SaveProc manager through `0xfb40c0` and registers it at `0xfb4150` (call PC `0x970ec`). `0xfb4150` supplies the name `SaveProc` and the player/save context to generic registration/factory `0xd4240`.

The `SaveSimpleSave` handler's request path reaches dispatcher `0x338080`, which tail-branches to `0xfb3160` at PC `0x3380f8`. `0xfb3160` stores the operation pointer at its manager object's `+8`, builds a 0x38-byte worker record whose name is `SaveProc`, and enqueues it through `0xfaf180` at PC `0xfb3234`. The queue consumer `0xfaf210` first calls readiness thunk `0xd47a0` at PC `0xfaf240`; that thunk forwards its worker-state object to `0x22fe870`. On the ready path, `0xfaf210` calls thunk `0xfb41c0` at PC `0xfaf274`; it tail-branches to generic task wrapper `0xd45c0`, which submits a message to `0x2201820` at PC `0xd466c`.

The task framework's callback remains indirect. `0xfaf360` selects a nested object at task `+0x10` or `+0x30`, checks its virtual readiness slot at vtable `+0x10`, then invokes the object's first virtual method. `0x2201820` similarly operates on a generic executor/message object through an indirect vtable method. The static registration shows a name and context, but no recovered function target that can be labeled “the SaveProc serializer.”

## Conditional worker commit

A related operation-state path has a concrete commit edge. `0xfb2f30` calls `0xfb3010`; `0xfb3010` selects a state row from table `0x30ed140` and calls its indirect state callback, then invokes `0xfaf360` at PC `0xfb30e4`. `0xfaf360` begins by calling `0xfaf4e0` at PC `0xfaf374` before its per-object callback dispatch.

In `0xfaf4e0`, when the active operation flags satisfy `(flags & 0x20f8) != 0` and bit 4 of operation byte `+1` is clear, and the save-path manager global is present, it calls `0xf21f30` at PC `0xfaf86c`. `0xf21f30` gathers up to nine path strings from registered path providers and calls `nn::fs::Commit(const char *const *, int)` at PC `0xf22230`. It maps a zero API result to status `1`; other results become status `7`. The subsequent state path may call `0xf21cf0`, which releases the path providers and unmounts the registered device.

This establishes a conditional commit operation in the save worker/state machinery. It does **not** prove that one specific `SaveSimpleSave` request or the crafting flow satisfies the flag condition: the operation enum/bit mapping and the indirect link from the queued `SaveProc` task to this state transition remain unresolved. The direct SaveProc callback identity is therefore still open.

## WriteFile and FlushFile callers

The direct `nn::fs::WriteFile` callers indexed in this main module are:

| Call PC | Enclosing function | Evidence |
| --- | --- | --- |
| `0x1970020` | `0x196ffd0` | File object write wrapper; advances its byte offset on success. |
| `0x1c2fab4` | `0x1c2fa70` | File-handle/offset write wrapper. |
| `0x1c2fe18` | `0x1c2fdd0` | Nested file-handle/offset write wrapper. |
| `0x1fc8c7c` | `0x1fc8c40` | File-stream write method; handle at object `+0x18`, position at `+0x28`. |

The direct `nn::fs::FlushFile` call sites are `0x196fde8` in `0x196fda0`, `0x196fe2c` in `0x196fe10`, `0x1c2f94c` in `0x1c2f920`, `0x1fc8bc0` in `0x1fc8b90`, `0x1fc8c10` in `0x1fc8be0`, `0x1fc8db8` in `0x1fc8db0`, and `0x1fc8e00` in `0x1fc8de0`.

The vtable-shaped relocated pointer sequence at `0x321cef0` contains the `0x1fc8c40` writer and its flush/destructor methods. Its constructor `0x1fc8a40` opens a path and carries the retained Havok source string `hkNxStreamWriter.cpp`, identifying a generic/Havok file-stream class rather than evidence of the SaveProc serializer. Other listed file wrappers have no direct call edge from the known SaveProc queue or `0xfaf4e0` branch. A virtual serializer could still reach a writer indirectly, so this bounds indexed direct calls; it does not prove that no runtime path writes.

The existing helper pair `0xf214a0`/`0xf21350` has a separate, bounded path: it mounts `ACNH_SAVE`, opens `ACNH_SAVE:/PlayerData.bin`, sets size to `0x4000`, and closes the file. That path has no observed `WriteFile` or `FlushFile` call and has not been tied to the queued SaveProc callback. The worker `Commit` call takes a list of provider-generated paths; the index does not show that this list is the same path as `PlayerData.bin`.

## Pocket view and local SaveLand naming

The previously traced craft helpers still establish in-memory views only:

| Helper path | Context accessor | View | Mutation |
| --- | --- | --- | --- |
| Materials | `0xeff060`, resolved player context + `0x1c0` | `0x140` bytes | Calls `0xf9e410` to update pocket slots. |
| Result item | `0xefac20`, resolved player context + `0x70` | `0x17c` bytes | Calls `0xf987c0` to insert an item. |

The local layout artifact defines `node` as an accessor-node offset and `data` as an offset in saved bytes. Its root is `0x4fa0d8`; the available tree is capped at depth 2 and does not label either craft view as a pocket field. The sampled player-record layout has node `+0x70` / data `+0x4` / size `1` and node `+0xa8` / data `+0x8` / size `0xaf90`, both unnamed. Those broad or one-byte members do not identify either craft view. The external comparison uses a schema named `save_schema_111_103`, whereas this executable is 1.0.0; it is candidate cross-version naming only and does not produce an exact local pocket-member mapping.

## Boundary after this trace

**Now statically proven:** SaveSimpleSave queues a named SaveProc task; the generic worker executor uses indirect callback objects; the operation-state worker contains a conditional `nn::fs::Commit` edge; generic direct `WriteFile` and `FlushFile` wrappers exist; craft material and result helpers mutate in-memory views.

**Still unproven:** the concrete SaveProc callback/serializer target; which operation flags are set by `SaveSimpleSave(cAll)` and whether that exact request reaches the commit condition; any `WriteFile` or `FlushFile` call from the SaveProc serializer; whether the commit list includes `PlayerData.bin`; the exact named 1.0.0 SaveLand/player pocket member behind the `+0x1c0/0x140` and `+0x70/0x17c` views; and a durable write/reload round trip.

The remaining blocker is static identity resolution for generic registry/virtual callbacks plus missing member names in the local save layout. This report does not treat a conditional Commit call as proof of craft persistence.

## Source hashes

The machine-readable companion records hashes for the main executable, code segment, native index, layout artifacts, and decompilation snapshots used for the key call sites.
