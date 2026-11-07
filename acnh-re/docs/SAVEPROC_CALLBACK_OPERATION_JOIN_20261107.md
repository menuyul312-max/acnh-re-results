# ACNH 1.0.0 — SaveProc callback and operation-flag join

**Status:** static native-code trace. No game or save was executed, and no synthetic save fixture was created.

This follow-up narrows one part of the SaveProc persistence boundary. The `System_SaveGameClose` EventFlow entry carries `SaveSimpleSave(Process=cAll)`. Its native dispatch builds an operation whose first word is `0x108` before it queues the named `SaveProc` task. The separate operation-state driver selects its row 1 for bit 8, and the later `nn::fs::Commit` guard accepts this operation word because `0x108 & 0x20f8 == 0x8`. This is a compatible flag match, not proof that the queued SaveProc callback reaches that state driver: the worker callback remains selected through runtime registry and virtual-dispatch objects.

## SaveSimpleSave operation word

The EventFlow record is `System_SaveGameClose`, action index 1, `EventFlowActionSaveSimpleSave`, with `Process=cAll`. The action request stage at `0x337f00` tail-branches to `0x338080` at PC `0x338060` after its property-change checks.

In `0x338080`, the operation begins at action object `+0xf0`. At PC `0x3380a4`, `0xfb35f0` zeroes its first word and second word. The next two calls use literal zero arguments:

| Call PC | Target | Effect on operation first word |
| --- | --- | --- |
| `0x3380cc` | `0xfb3560(operation, 0)` | Clears bits 3–5 then sets bit 3 (`0x8`). |
| `0x3380d8` | `0xfb35d0(operation, 0)` | Sets bit 8 (`0x100`). |

The resulting first word is `0x108`; the action then tail-branches to `0xfb3160` at PC `0x3380f8`. `0xfb3160` stores that operation pointer at manager `+8` and enqueues a `0x38`-byte record named `SaveProc` through `0xfaf180` at PC `0xfb3234`.

The `cAll` string is confirmed at the EventFlow/action level, but the inspected bit-setting calls receive literal zero. The native path therefore proves that this SaveSimpleSave dispatch creates `0x108`; it does not prove that the text value `cAll` is what selects those bits.

## Compatibility with the conditional commit guard

The sibling state-processing entry `0xfb2f30` validates an operation with `0xfb2c60`, stores the operation pointer, then tail-branches to `0xfb3010` at PC `0xfb2fac`. `0xfb3010` checks the operation first word. If bit 8 is set, it selects state row 1 from the table at `0x30ed140`; row 1 starts at `0x30ed160`, whose relocated callback entries point to `0xf2e970` and `0xf2ea40`. It then calls `0xfaf360` at PC `0xfb30e4`.

`0xfaf360` calls `0xfaf4e0` at PC `0xfaf374`. The latter calls `0xf21f30` only if the operation word has a nonzero `0x20f8` mask, byte `+1` bit 4 is clear, and the save-path manager global is present. The operation built by the SaveSimpleSave dispatcher has `0x108 & 0x20f8 == 0x8`; its byte `+1` bit 4 is clear because initialization zeroes that word and the two flag helpers only modify the first word. Thus the first two guard terms match. Manager presence remains runtime state.

The queue path and state-driver path do not meet in a recovered direct call: `0xfb3160` enqueues the request, whereas the indexed direct caller of `0xfb3010` is `0xfb2f30`. The queue consumer proceeds through `0xfaf210` → `0xfb41c0`/`0xd45c0` → `0x2201820`; no direct edge from this chain to `0xfb2f30` or `0xfb3010` was found. An indirect callback could make that connection, but its target is unresolved. Therefore the conditional Commit is **flag-compatible** with the queued SaveSimpleSave operation, but is not proven to be executed by that exact request.

## Runtime callback boundary

`0xfb4150` passes the literal `SaveProc` descriptor and context to generic factory `0xd4240`. At PC `0xd4538`, that factory calls slot `+0x10` on the runtime registry object addressed through the pointer slot at raw data `0x32d08a0`. The slot has a relative relocation to `0x3a86b70`, within the NSO MOD0 BSS range `0x333def8..0x3ab6a48`; the on-disk image therefore does not provide the live registry object's vtable contents or its mapping for `SaveProc`.

On the accepted registry path, `0xd4240` constructs a generic `0x138` executor object at worker `+0x20` and calls `0x2201d30`. The relocated code sequence at `0x302e710` begins with `0xd1f60`; that function reads a delegate payload from object offsets `+8` and `+0x10` and ends with an indirect branch at `0xd1f88`. This identifies a type-erased dispatch thunk, not the SaveProc target. The worker wrapper `0xd45c0` later passes the generic executor to `0x2201820`. At `0x22018e8`, the executor invokes the first virtual method of a task object popped from its runtime queue. Its vtable and target are not statically bound to a save serializer.

Consequently, the exact unresolved joins are: `SaveProc` name → registry result; registry result → queued task object's vtable; queued task method → `0xfb2f30`/`0xfb3010` state driver; and any serializer → a durable `WriteFile`/`FlushFile` caller. No craft handler has a direct edge into the SaveSimpleSave request path in the indexed native call graph. The previous file-I/O and pocket-layout findings remain as recorded in [the earlier trace](CRAFTING_SAVEPROC_FILEIO_TRACE_20261107.md).

## Evidence boundary

**Newly proven:** the SaveSimpleSave dispatch's operation first word is `0x108`; the sibling state driver routes bit 8 through row 1; and that same first word satisfies the `0x20f8` portion of the conditional Commit guard.

**Still unproven:** the literal `cAll` value's semantic effect on those bits; whether the SaveProc queue callback forwards this operation to the sibling state driver; whether runtime manager state satisfies the third Commit prerequisite; the concrete serializer callback; any SaveProc-linked file write/flush; and craft-result persistence or reload.

The JSON companion records call PCs, calculations, relocated table entries, unresolved joins, and source hashes.
