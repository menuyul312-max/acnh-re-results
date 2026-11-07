# cVillage result-context follow-up

This follow-up resolves the `cVillage` value path through its source result context and identifies the target global and container field. It reaches a native option-index consumer, but the first durable save commit and the option-index-to-terrain-preset mapping remain open. This is an isolated report; no Godot work, build, commit, or push was performed.

## Target global and field

The decomp pseudoname `0x33d1ba8` maps to raw ELF slot `0x32d1ba8`. The ELF has an `R_AARCH64_RELATIVE` relocation at that slot to raw VA `0x345ff98`, which is in the memory-only tail of the writable load segment and therefore zero-fill BSS. The target field address is `0x3464588` (`object+0x45f0`); its containing subobject begins at `0x3464568` (`object+0x45d0`).

The surrounding aggregate is a large field-system context/singleton shape. `0x564da0` is its accessor: a null pointer takes a branch that allocates `0x47d0` bytes and calls constructor `0x564e30`. The field-subobject constructor call at `0x564ec0` enters `0x529810`, which initializes a 0x28-byte container: status `+8`, count `+0x10`, entry pointer `+0x18`, and the selected-result u32 at `+0x20` are zeroed. `0x529910` later populates four entries of 0xe0 bytes each.

Startup function `0x96ef0` calls accessor `0x564da0` at PC `0x972f0`, then calls `0x5650b0` at `0x972f8` with the accessor result. The relocation pre-seeds the global pointer to non-null BSS storage, so this call does not prove that the accessor's null-branch constructor ran. No relocations were found inside the `0x47d0`-byte candidate object span; the explicit constructor effect is proven, while actual C++ vptr/constructor execution for the pre-pointed instance remains open. The field bytes themselves begin as zero-fill. `0x564e30` contains the member descriptor string `FieldSystem` at string VA `0x29c150d`, associated with a member at `+0x4658`; this is not enough to name the aggregate's C++ class.

## Source value and dataflow

The source result is a separate global context. Decomp pseudoname `0x33d07c0` maps to raw slot `0x32d07c0`, relocated to BSS at raw VA `0x3715c40`. Startup `0x96ef0` calls parent initializer `0x1541960` at PC `0x97664`. That initializer allocates a `0xb0c8`-byte child at parent `+0x28`, calls `0x1544de0` at PC `0x15419d0`, then stores the child pointer at `+0x28`. The child initializer clears storage including `+0xae3c`.

A relocated callback sequence starting at `0x3307ba0`, consumed by `0x1242ce0`, contains callback `0x1243260` at entry 8 (`0x3307be0`). In its result path, callback `0x1243260` reads the current option index from `[x19+0x2cc]`, places it at stack `+0xc`, and calls wrapper `0x154a100` at PC `0x124338c`. The wrapper reaches setter `0x1547600`, which stores the 32-bit value into the result child at `+0xae3c`.

The `cVillage` branch in SaveSetFromUIResult method `0x334650` calls getter wrapper `0x154a130` at PC `0x334d68`, loads the u32 at returned pointer `+0xc` (child `+0xae3c`), then writes it to `*0x33d1ba8+0x45f0`. This statically establishes option-index propagation into the field-system container. The action/page/controller identity that produces the callback remains unjoined, and the index-to-preset mapping is not established.

## Recovered consumer and stopping point

`0x565300` calls container cleanup method `0x529e50` at PC `0x565368`. When feature/status guards pass, `0x529e50` reads the stored index from subobject `+0x20` and tail-branches to `0x529ea0`. The latter bounds-checks the index against the four-entry count at `+0x10`, selects `entry[index]` from the pointer array at `+0x18`, then applies entry data through native runtime-object APIs. The destination's game meaning is not named in recovered code.

This is evidence of a transient four-option result index and a cleanup/entry-consumer path. It does not prove a durable save write or seed/preset choice. The shallow emulated `save_layout.json` does not name this native field. The prior table work joins `FieldMainFieldParam.bcsv` source 41 to `FieldPresetA00_LandMaking.byml` source 2442 by the row's `FieldData` filename stem, but no native edge connects index 0–3 or `+0x45f0` to `UniqueID`, `FieldData`, or a LandMaking preset.

A separate placement path also reads the `*0x33d1ba8` manager, but its candidate `BuildingSiteIndex` lookup uses member `+0x3a50`, distinct from this result container at `+0x45d0` and its index at `+0x45f0`; no dataflow between those members was recovered.

## Bounded search and validation

The fixed-string search for `+ 0x45f0` in recovered decompilation returns one hit: the case-5 store in `334650.c`. The fixed-string search for `0xae3c` returns the initializer clear in `1544de0.c` and the setter write in `1547600.c`. The native call index records the setter-wrapper/callback chain and destructor cleanup caller, although some callback-owner fields are null; raw instructions confirm the exact PCs above. The constructor is only directly called by the lazy accessor in the generated index, and that accessor may be skipped because the global pointer is relocation-initialized non-null.

The companion JSON parses with `python -m json.tool`; all listed source hashes were checked. Earlier registration reports and shared crosswalks were not edited.
