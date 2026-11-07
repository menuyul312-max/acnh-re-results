# ACNH 1.0.0 — SaveProc runtime callback closure

**Result:** the static SaveProc chain reaches a runtime name registry and a generic task executor, but the concrete registered callback/vtable is not present in the available file-backed data. The registry pointer lands in the main module's MOD0 BSS. This pass used the existing indexes, decompressed ExeFS segments, relocation metadata and raw ELF; it did not rebuild Ghidra or run the game.

## What the static image does establish

The `SaveProc` string is at main ELF VA `0x2963e21`. The indexed string-reference table has exactly three main-module users: startup/config initializer `0xC470`, request queue builder `0xFB3160`, and manager registration function `0xFB4150`.

At `0xFB4150`, the code passes the `SaveProc` descriptor and player/save context to generic factory `0xD4240` (`BL` at `0xFB41AC`). `0xFB3160` puts the same name in its `0x38`-byte worker record and enqueues it through `0xFAF180` at `0xFB3234`. This confirms name-based manager registration and request submission, not a callback body.

A separate initializer at `0xC470` places the same string pointer into a BSS record at ELF VA `0x333FCC8`; its adjacent fields are initialized at `0x333FCD0` (`0x100000014`), `0x333FCD8` (`0x8000000000001`), and `0x333FCE0` (`2`). The surrounding records contain names such as `EventFlowAsyncExecutor`, `AsyncWorker`, `ActorLoad1/2`, `SceneLoad`, `ResLoad1/2`, and `DebugSave`. This identifies `SaveProc` as a configured worker/service label. It does not provide a function pointer or name-to-callback mapping.

## Registry and executor boundary

The main ELF has an `R_AARCH64_RELATIVE` relocation at site `0x32D08A0` whose target is `0x3A86B70`. The generic factory `0xD4240` dereferences this registry slot and, at callsite `0xD4538`, invokes registry vtable slot `+0x10` with the request descriptor. The target `0x3A86B70` lies inside MOD0 BSS `[0x333DEF8, 0x3AB6A48)` (offset `0x748C78` from BSS start; `0x2FED8` bytes remain to its end). The BSS is `NOBITS` in `main.elf`; the pointer relocation only identifies the BSS address, not its runtime contents. The other file-backed main segments likewise stop before this BSS range.

The accepted factory path allocates a generic `0x138`-byte executor and calls `0x2201D30` at `0xD4588`. That helper invokes an interface method at supplied object vtable offset `+0x98`, installs a type-erased delegate, and calls a supplied callback interface. The delegate thunk at `0xD1F60` reads payload fields at `+8` and `+0x10`, then branches indirectly at `0xD1F88`. No static target identifies the SaveProc implementation.

The manager object itself is more concrete than the queued task. `0xFB40C0` creates a `0x48`-byte singleton through `0xD40A0`; its root vptr resolves through relocation site `0x32D52E8` to pointer table `0x302E960`, whose entries target `0xD40C0` and `0xD4200`. The manager’s nested object at `+0x28` gets its vptr through relocation site `0x32FF9D0` to table `0x30ED368`, with entries `0xFB3FE0` and `0xFB4050`. This identifies manager-side interfaces only. Those tables do not identify the generic task object later dequeued and virtually invoked by `0x2201820`; several targets also lack recovered function bodies in the existing index.

The queue consumer's wrapper `0xD45C0` submits the executor to `0x2201820` at `0xD466C`; `0x2201820` later invokes the first virtual method of a task object taken from runtime state. No recovered vtable or concrete SaveProc task object ties that call to a serializer. Thus the joins `SaveProc name → registry result → task vtable → task method` remain unresolved.

## Commit and durable-write joins

The SaveSimpleSave path still proves a flag-compatible operation: dispatch `0x338080` constructs first-word flags `0x108` and transfers the operation to the `SaveProc` queue at `0x3380F8`. The sibling state path is `0xFB2F30 → 0xFB3010 → 0xFAF360 → 0xFAF4E0 → 0xF21F30`, with the last function calling `nn::fs::Commit` at `0xF22230`. `0x108 & 0x20F8 == 8`, so the flag guard is compatible. The queued request is not proven to enter that path: indexed direct calls to `0xFB3010` are at `0xFB2FAC` from `0xFB2F30` and at `0xFB2F18` from an unindexed six-instruction routine beginning at `0xFB2F10`; neither callsite is in the SaveProc queue chain.

The indexed main-module direct `WriteFile` wrapper sites remain `0x1970020`, `0x1C2FAB4`, `0x1C2FE18`, and `0x1FC8C7C`. Direct `FlushFile` wrapper sites remain `0x196FDE8`, `0x196FE2C`, `0x1C2F94C`, `0x1FC8BC0`, `0x1FC8C10`, `0x1FC8DB8`, and `0x1FC8E00`. No indexed direct edge joins these wrappers to the SaveProc queue, executor, or Commit path. A runtime virtual serializer may still reach one; its identity is unavailable.

## Pocket and save-member boundary

The craft paths still expose only unnamed in-memory views: material handling resolves a player context view at `+0x1C0` of size `0x140`, while result insertion resolves a view at `+0x70` of size `0x17C`. The local SaveLand layout sampled previously does not label either view as the pocket member, and its available tree is shallow. No SaveProc callback or serializer was recovered to join these views to a saved member. Therefore no durable pocket/save-field mapping or write-and-reload path is established.

## Bounded search and remaining blocker

The search covered the indexed main ELF direct-call and string-reference rows; all 18,348 sequences in the existing main `code_pointer_arrays.json`; all three decompressed segments for each of the available `main`, `rtld`, `subsdk0`, and `sdk` modules (the `SaveProc` literal occurs in `main/1.bin` only); the main ELF dynamic relocations and MOD0/ELF load bounds; and existing native decompilation for the registry and SaveProc addresses. It found no static write that populates the registry target and no SaveProc executor target. The four available modules are the complete local decompressed module set for this pass; `multimedia.nss`, which main lists as a needed library, is not among them. The `sdk` module (`nnSdk.nss`) is present.

The decisive gap is the live registry/task state in BSS plus indirect dispatch. Without a runtime capture, memory dump, or the missing callback-bearing runtime module if it participates, static artifacts cannot establish the concrete SaveProc vtable, whether it reaches the conditional Commit branch, which serializer writes the save, or the named pocket member. This result is bounded to the supplied ACNH 1.0.0 image and indexed artifacts; it does not claim the runtime path is absent.

## Source hashes

The machine-readable companion records SHA-256 hashes for the exact main ELF, decompressed segments of all available modules, extra main NSO, native-module inventory, call/pointer indexes, and the prior SaveProc trace used as context.
