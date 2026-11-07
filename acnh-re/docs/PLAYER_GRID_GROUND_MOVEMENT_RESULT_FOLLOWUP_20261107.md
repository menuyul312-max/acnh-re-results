# ACNH 1.0.0 grid-height and movement-output follow-up

This trace follows resolved spatial-index callback `0x172740` through `0x1577a0` and `0x7bccf0`, then tracks the returned scalar into movement/ground update code. The grid contract is statically recoverable; a live island-specific result remains OPEN because the initialized world, grid, query list, and runtime mode are unavailable. No synthetic query fixture was built and no `0x7bccf0` call was rerun.

## Grid callback and `0x1577a0`

`0x172740(grid, position, status_out, mode)` converts X/Z to a cell with `0x52b280`, checks width at `grid+0x30` and height at `grid+0x34`, and samples a 52-byte cell record. Four 12-byte triplets at offsets `0x00`, `0x0c`, `0x18`, and `0x24` are paired with attribute bytes at `0x30..0x33`. Position within the five-unit cell selects one triplet and its byte. `0x172b00` constructs a plane from the triplet; `0x1a480` evaluates plane height at local X/Z and returns it in `s0`. The selected attribute byte is written to `*status_out` on a valid-cell path.

Mode bit 0 set forces the base record. With bit 0 clear, an in-range overlay record is used when the overlay pointer/count and selected attribute permit it; attribute `7` falls back to base. The spatial-index vtable installed by `0x172090` points slot `+0x30` to `0x172740`; `0x157270` calls that slot with final argument zero. `0x1577a0` calls `0x172740` directly with final argument one. The two paths can sample the same cell in different modes: direct base versus overlay-aware list data.

`0x1577a0` returns the direct base-mode `0x172740` scalar when `context+0x78` contains a grid. It seeds optional status to `0` if `0x18ba40` reports ready, otherwise `7`; on a valid cell, the grid callback writes the selected attribute. `0x18b570` may replace status with guarded `0x157ab0` output when that result is not `7`. If the grid pointer is absent, the scalar is `-500.0` and status is `0` only when readiness succeeds (otherwise `7`).

For an invalid/out-of-range coordinate inside `0x172740`, fallback is `0.0` when `0x18ba40` is true and `100.0` when false. The latter comes from `0x29ee410` via relocated pointer slot `0x32d7198`. This early path does not write the selected attribute.

`0x157270` is the candidate-list counterpart. Its scalar accumulator starts at `-500.0`; for each node it calls vtable slot `+0x30` and keeps the greatest return, copying status only when that return exceeds the accumulator. The spatial index contributes its sampled plane height and attribute. Volume callbacks resolved earlier (`0x171450`, `0x171d40`) return `-500.0` and leave the accumulator/status unchanged. Optional status can be further classified by `0x18b570` and `0x18b5e0`. See [the vtable relocation trace](PLAYER_COLLIDER_VTABLE_CALLBACK_FOLLOWUP_20261107.md) and [the candidate producer trace](PLAYER_COLLIDER_QUERY_CANDIDATE_PRODUCER_FOLLOWUP_20261107.md).

## `0x7bccf0` and movement outputs

At the machine boundary, `0x7bccf0` receives position in `x0`, optional status pointer in `x1`, flags in `w2`, and a scalar/vector baseline in `q0`; it returns the resulting scalar in `s0`/`q0`. It calls `0x1577a0` and `0x157270` for the same position, with separate status words, then applies status-dependent comparisons and additional ground/environment policy. It is not a direct alias for raw grid height. The movement callers below pass null status, so they consume the scalar only.

| Path | Evidence-supported use | Status |
|---|---|---|
| `0x7c5570` → `0x7bccf0` twice | Queries two positions with flags `1`; tests `(y-h0)*(h1-h0)` and, within its gates, smooths the scalar at first input `+4` toward the second height through `0x1eff3d0` (gain `0.35`, max step `5.0`, snap threshold `0.25`). | PSEUDO / STRUCT |
| `0xdac780` → `0x7c5570` | Supplies actor-related vector `actor+0x284`, current position `actor+0x278`, and a target vector from `0xe99510`; calls actor vtable `+0xf8`, then stores result at transform offset `+4` (Y). | PSEUDO / STRUCT |
| `0xdac780` → `0x7bccf0` | Other mode branches query actor position with flags `0`; compare/clamp the scalar with actor Y at `actor+0x27c`, then call actor vtable `+0xf8` and store at transform `+4`. | PSEUDO / STRUCT |
| `0xda86b0` → `0x7bccf0` | Queries actor position with null status; if current Y is below the result, calls actor vtable `+0x110`. Its higher-level meaning is unresolved. | PSEUDO / CAT |
| `0xe42b30` → `0x7bccf0` | Queries a temporary movement position with null status; stores the result in that vector’s Y before later movement/transform work. This function has no indexed direct callers. | PSEUDO / OPEN |

These paths establish that the query scalar can feed actor vertical correction and motion-target preparation. They do not establish a bridge, ladder, cliff, river crossing, landing, or player-input event. `0x7bccf0` also branches on status/mode and can add environmental values after grid/list calls; live branch selection still needs actor/task/world state.

## Runtime and asset boundary

The [terrain native fixture](../tools/terrain_native.py) executes isolated original coordinate/grid/ground helpers on reconstructed memory (1,791 cases). It verifies the record/overlay accessor family, not the player/query-list chain. The prior boundary fixture stops at an invalid sandbox root/grid read; that setup fault is not gameplay evidence. [ColGroundAttributeParam](../../../acnh-re/output/tables_resolved/ColGroundAttributeParam.json) supplies table rows to the terrain fixture, but conversion from 14-byte landmaking preset cells to 52-byte runtime records and live query entries is OPEN.

A faithful result still needs original root initialization at singleton `0x32d0de8`; loaded `root+0xa0` grid/backing arrays and `root+0xf10` ready state; indirect invocation of `0x1978a0`; populated query nodes with relocated vtables; island asset conversion; and the movement frame/actor state selecting `0x7bccf0` branches. These inputs are absent, so no end-to-end scalar/status result is claimed.

Evidence labels: **EF** executable identity/bytes; **TBL** extracted table evidence; **STRUCT** field/argument layout; **PSEUDO** native decompilation/disassembly; **NATIVE** isolated helper execution only; **CAT** interpretation of a query/status use; **OPEN** runtime edge not joined. The requested checkout artifact is `docs/PLAYER_GRID_GROUND_MOVEMENT_RESULT_FOLLOWUP_20261107.md` with its JSON ledger under `output/mechanics/player_collider_query_remainder_20261107/`.
