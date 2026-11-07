# Building-site component vptr and lifecycle boundary

**Date:** 2026-11-07
**Scope:** ACNH 1.0.0 static trace of the actor component used by the building-site coordinate callback. This follows the actor constructor and its base initializer, checks the outer actor vptr relocation separately, and records where the inner `actor + 0x68` virtual target remains dynamic. No game, save, Godot scene, model/audio payload, or build was executed or changed.

## Result

The native `BuildStructure` chain reaches a coordinate-bearing indirect call through the object loaded from `actor + 0x68`: helper `0x2eae0` reads that object's vptr slot `+0x128` and calls it with the converted coordinate vector. I traced the owner constructor and its base initialization. That chain explicitly zeros the owner field at `+0x68`; it does not statically bind the placement call's component object or its vptr.

The constructor does resolve the **outer actor's** vptr-like pointer. A relocation at global slot `0x32f7a18` resolves to pointer-sequence base `0x30d5890`; the constructor adds `0x10` and stores `0x30d58a0` at the owner object's offset zero. In the indexed sequence, outer slot `+0x128` is `0x30d59c8 -> 0xbe89e0`. This is a separate outer-object dispatch and supplies no evidence that `*(actor + 0x68)` has the same vptr or that `0xbe89e0` implements the placement coordinate callback.

So this pass narrows the missing edge: a runtime lifecycle path must populate `actor + 0x68` after constructor initialization (or replace the object before placement). That attachment/setter and the inner vptr's class/global instance remain unresolved. The transform write, height/yaw, footprint, terrain/overlap decision, preview/model/PBC, and durable save handoff also remain open as documented in the prior coordinate follow-up.

## Proven chain and boundaries

Raw PCs and instruction bytes below refer to the ACNH 1.0.0 `main.elf`, SHA-256 `5bf707c3dc5dac0ad9635af7d336ec580f81c3f7876d0f55400d1900e3415d74`. Raw ELF VAs are used; Ghidra display labels in the pseudocode add `0x100000`.

| Step | Evidence | Finding | Level |
|---|---|---|---|
| Owner constructor enters base initializer | Constructor `0xbe5e40` calls `0x7bbe20` at PC `0xbe5e6c`, bytes `ed57ef97`. Function inventory identifies raw VA `0xbe5e40` as a 284-byte function (`FUN_00ce5e40`). | The actor construction chain reaches the common base initializer with the actor object. | **EF / PSEUDO** |
| Base initializer clears component slots | `0x7bbe20` calls `0x27c70` at PC `0x7bbe38`, bytes `8eafe197`. At PC `0x27d48`, bytes `dffe06a9`, instruction is `STP XZR,XZR,[X22,#0x68]`. Decompiled `27c70.c` writes zero to `param_1[0xd]` and `[0xe]`. | The base initialization explicitly zeros owner offsets `+0x68` and `+0x70`. This is a constructor-time state, not evidence that the field stays null during gameplay. | **EF / PSEUDO** |
| Outer actor vptr-like pointer | `main.elf` relocation `R_AARCH64_RELATIVE` at `0x32f7a18` has addend `0x30d5890`. Constructor PC `0xbe5e98`, bytes `680200f9`, stores loaded pointer plus `0x10` to `[X19]`. | The constructor initializes the outer actor's offset-zero pointer to `0x30d58a0`. The indexed pointer sequence has entry `0x30d59c8` at outer offset `+0x128`, target `0xbe89e0`. | **EF / STRUCT** |
| Placement consumes inner component | `0xbe6340` loads `*(actor + 0x68)` and calls `0x2eae0` at PC `0xbe6370`, bytes `dc21d197`. The coordinate argument remains in `X1`. | The call object is the runtime pointer stored at owner `+0x68`, distinct from the outer actor's offset-zero vptr. | **PSEUDO / EF** |
| Inner slot target call | In `0x2eae0`, PC `0x2eb04`, bytes `089540f9`, loads `[vptr + 0x128]`; PC `0x2eb10`, bytes `00013fd6`, performs `BLR X8` with the component and coordinate pointer. | Slot `+0x128` is proven as a coordinate-bearing virtual call. The target cannot be substituted with the outer actor sequence target: the actual vptr is read from the object at `actor + 0x68`, whose runtime instance is unresolved. | **EF / PSEUDO; target OPEN** |
| Position-like sibling use | Actor method `0xbe93e0` reads the inner object at `actor + 0x68`, passes its `+0x278` region to a position-like helper, then calls its vtable slot `+0x110`. | This supports that the inner object is a component/entity-like object with position state. It does not identify slot `+0x128` or connect this method to the build callback's runtime component instance. | **PSEUDO / STRUCT** |

## Bounded negative and remaining work

The bounded negative is only about the statically traced constructor chain: `0xbe5e40 -> 0x7bbe20 -> 0x27c70` clears `actor + 0x68`; the inspected chain contains no assignment of an inner component vptr after that clear. This does **not** prove that no later actor-spawn, component-registration, or runtime factory path assigns the field.

The outer actor's relocation and pointer sequence are resolved as a control case. Their slot values must not be used to name the inner indirect target without proving `*(actor + 0x68)` points into that same sequence. The dynamic object instance, class-specific vptr, and slot implementation remain **OPEN**.

Still open on the building placement path:

1. Runtime writer/attachment for the owner's `+0x68` component and the exact vptr/global instance used by this event.
2. Implementation and effects of the inner slot `+0x128`, including any final transform write, origin/frame adjustment, height, or rotation.
3. Building footprint expansion and placement rejection across terrain, water, cliffs, existing structures, and other collision state.
4. Preview-to-built actor/model/collider/PBC handoff and durable save-instance serialization/completion.

The earlier coordinate report remains the source for the selected pair conversion, grid query branches, and the bounded non-join to named model/PBC resources. The earlier native-handler report remains the source for registered `BuildStructure`/preview/query candidates and its direct-call/string search bounds. This report does not change either prior artifact.

## Reproducibility

The companion JSON records the binary identity, input/source hashes, exact raw PCs and bytes, outer relocation/sequence crosswalk, evidence levels, and unresolved runtime boundary. Instruction bytes were read from the identified `main.elf`; relocation evidence was checked with the ELF relocation table; pseudocode joins use the hash-identified snapshots listed in the JSON. Static inspection only; no runtime or save data was touched.
