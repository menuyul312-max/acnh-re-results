# UI/HUD lifecycle, input routing, and renderer flags

Status: 6 November 2026. Source build: ACNH 1.0.0 ExeFS `main`, SHA-256 `f8d248109ff72999b4600ae3749f8c7397fb960f7ad3ab8dee3018ae9e14e900`. This follow-up reads the available native image, the shared read-only index, and committed RomFS-derived catalogue records. It does not contain a synchronized game capture.

## Page loader and lifecycle

`[NATIVE STATIC + RELOCATION]` The catalogue still contains 135 page factories following the common constructor/registration pattern. Each observed page pointer sequence has slot 46 (`+0x170`) relocated to a unique three-instruction string getter; 134 return a name that matches a catalogued BFLYT and `SwkbdPage` returns `SwkbdDummy`. The page audit finds no direct `B`/`BL` instruction to any of the 135 getter targets. This proves a page-to-identifier crosswalk, not that a scheduler calls the getter or passes its result to the layout loader.

`[NATIVE STATIC]` All 135 factories call the shared registration helper `0x1da8220`. It calls `0x1da40b0`, which writes `2` at page object `+0x48` and branches through page slot 5 (`+0x28`) to `0x1da5380`; it then inserts an intrusive-list node and increments a collection count. The earlier helper `0x1da8210` writes `1` at the same offset. Those are observed values and transitions; the field is not identified as an open, active, or visible state.

The only indexed direct caller of candidate selector `0x1da8270` is `0x1cbac50`. That selector walks a collection, calls page slot 17 (`+0x88`), whose common thunk forwards to slot 30 (`+0xf0`), and returns an entry address when the result bit is set. This is a selection predicate for a candidate collection entry; the available code does not connect it to slot 46, a page scheduler, or a global open/close/back stack. Loader handoff, page update scheduling, modal order, focus restoration, and page teardown remain unresolved.

## Npad to action route

`[NATIVE STATIC + INDEX]` The Npad update method `0x1968b80` has eleven direct `BL` targets in the indexed call table and no direct call to the generic UI action dispatcher `0x14845a0`. The dispatcher has 28 indexed direct callsites, but these alone do not identify which platform input or scheduler reaches them. Npad sampling, the 13 named UI action IDs, and the separately mapped touch-to-target-control path are not statically joined. A virtual callback or intermediate state translation could still connect them.

## Hit-pane identity and declared visibility

The controller constructor and the separate controller-side `Hit` binding use the same dynamic name source, lookup context, descriptor base, helper, and literal token `Hit`. The first lookup result is stored at inline hit node `+0x20`; the second is stored at controller `+0x420+0x70`. Native code does not compare those returns. The asset catalogue gives 18 same-layout `B_Hit` BND1 / `B_Hit:Hit` CNT1 pairs, and all 18 BND1 records declare `visible=true`. This strengthens the static name crosswalk, but the dynamic prefix and an instance pointer comparison are absent.

The BFLYT catalogue also contains two `ScissorPane` records, `S_Scissor_00` and `S_Scissor_01` in `LMyDesignEditCanvas`; both declare `visible=true` and size 650×650. These are serialized asset properties, not current runtime flag values.

## Renderer gates and ScissorPane bounds flag

`[NATIVE STATIC]` The generic pane renderer `0x192fb20` calls a pane vtable callback at `+0xa8` only when its raw object checks pass: byte `+0x58` has mask `0x81` set, byte `+0x5c` has bit 4 set, byte `+0x5a` is nonzero, and byte `+0x62` has bit 1 clear. It later traverses child panes through slot `+0xa0`. The instructions expose these byte tests but do not label them as active-state names. The hit visibility helper `0x14c80d0` also checks bit 0 of pane byte `+0x58` and can walk ancestor panes according to its input options.

The ScissorPane setter `0x14c8d00` stores `1` in byte `+0xe0` and copies four 32-bit bounds to `+0xf0..+0xfc`. Its render callback `0x14c8d30` uses those stored values when `+0xe0` is nonzero; when it is zero, it derives a rectangle from the pane transform. Both branches reach the scissor-stack push call at `0x14c8e44`. Thus `+0xe0` selects the source of bounds; it does not disable the clipping callback. Native stack bookkeeping was exercised by the existing 11-case synthetic fixture, which stubs the push/apply boundaries and does not issue NVN commands.

`[NATIVE STATIC + API RESOLUTION]` The push helper `0x14c8fe0` intersects incoming left/top/right/bottom bounds with the current top entry. If the intersection is inverted on either axis, it replaces all four values with zero, then applies the result in mode 1 and stores it when the prior stack count is at most five (six saved rectangles). At count six, another push still applies its intersection but exits without saving or incrementing the stack. The restore helper `0x14c9250` decrements the count and reapplies the previous entry in mode 1; on an empty stack it applies a zero rectangle in mode 0. In `0x14c90e0`, mode 1 reaches separate viewport/depth (`0x19a9c60`) and scissor (`0x19a9d50`) updates, while mode 0 reaches the combined update (`0x19a9960`). The two paths resolve through the GOT cells associated with the `nvnCommandBufferSetViewport` and `nvnCommandBufferSetScissor` strings. This traces submission of transformed rectangles into native NVN calls; it does not prove the GPU's pixel coverage. In particular, the empty-stack logical zero rectangle still passes through the live viewport/coordinate transform, whose runtime values and displayed result were not captured. The existing fixture does not exercise balanced traversal beyond six saved entries.

The separate parent-bound pointer at hit node `+0x28` is inherited under node flag `0x40` and participates in hit-rectangle intersection. Native does not call that field a render clip. The ScissorPane render path is direct static evidence for scissor submission, but which callback flags and bounds are active for a live BFLYT instance, the resulting pixel coverage, and framebuffer origin remain unmeasured.

## Evidence boundary

The current worktree has the ExeFS `main` input and committed RomFS-derived catalogue JSON, but no raw RomFS archive under `inputs/`. No synchronized live capture aligns page events, Npad samples, dynamic controller parameters, live pane pointers, renderer flag values, or GPU output. The absence is material: the remaining loader/input/instance identity and pixel-clipping claims cannot be resolved from the committed dump/index records alone.

The raw-instruction and index summary is generated by [ui_hud_lifecycle_static_trace.py](../tools/ui_hud_lifecycle_static_trace.py); the result is [page_input_renderer_static.json](../output/ui_hud/runtime_followup/page_input_renderer_static.json). It complements [UI_HUD_RUNTIME_FOLLOWUP.md](UI_HUD_RUNTIME_FOLLOWUP.md), the hit-node proof, and the ScissorPane restore fixture.
