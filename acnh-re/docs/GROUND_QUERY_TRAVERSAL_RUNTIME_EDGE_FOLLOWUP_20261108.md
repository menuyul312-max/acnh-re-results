# Ground-query and player-traversal runtime edge follow-up, ACNH 1.0.0

This static pass joins the world-root/grid lifecycle, readiness predicate, grid query callback, state-gated base-grid writer, and the previously mapped player movement and traversal branches. It finds a direct setup edge that installs the query grid and a separate writer that changes its base records. It still does not establish a nonzero root readiness write, live query result, Npad-to-player state edge, or successful bridge/ladder/water traversal. No game execution, save mutation, Ghidra rebuild, or Godot work was done.

## Finding

`0xfe5a00` loads the object in singleton slot `0x32d0de8` and calls `0x1978a0` at `0xfe5abc`. `0x1978a0` clears root byte `+0xf60` and calls `0x156e30(root+0x28)`. That initializer allocates/configures the spatial grid, stores it at `root+0xa0`, and adds the spatial index to the query list. This is a concrete static root-to-grid setup path. The setup routine itself has no indexed direct caller, and neither it nor `0x156e30` writes the distinct readiness byte at `root+0xf10`.

The query callback is statically resolved: `0x1577a0` calls grid callback `0x172740` in base-only mode, while `0x157270` dispatches list candidates through slot `+0x30` in overlay-aware mode. `0x7bccf0` combines those results and selected movement branches feed its scalar into actor Y correction. A separate state-gated handler, `0x8445d0`, writes base-grid attributes and plane fields through `0x163780`/`0x163760`, so the callback can read those fields if the same root/grid is active and ready. Those are static dataflow edges only.

The readiness predicate `0x18ba40` requires a non-null root, non-null `root+0xa0`, and nonzero `root+0xf10`. The query-context constructor initializes `root+0xf10` to zero. No nonzero writer to that exact root byte was identified in the bounded raw-store scan. As a result, root construction and grid installation do not yet prove that the grid query can return an island-specific result at runtime.

## Root, grid, readiness, and writer edges

| Edge | Evidence | Boundary |
|---|---|---|
| Root construction | `0x197740` allocates a `0xf88` root and calls query-context constructor `0x156840` for `root+0x28`. Constructor `0x156840` initializes context `+0xee8` to zero, which is `root+0xf10`. | Static constructor path; runtime root creation is not observed. |
| Root setup owner → grid lifecycle | In `0xfe5a00`, PCs `0xfe5ab0..0xfe5abc` load singleton slot `0x32d0de8` into `x0` and `BL 0x1978a0`. Indexed direct-call inventory records this one callsite; the containing native span is `0xfe5a00..0xfe5c43`. | The owner routine has no indexed direct caller, so its execution/cadence remains open. |
| Grid installation | `0x1978a0` clears `root+0xf60`, then calls `0x156e30(root+0x28)`. `0x156e30` initializes the `0x118` spatial-index object and dimensions/backing storage, stores it at context `+0x78` (`root+0xa0`), and inserts it into the query list. | This establishes a static grid pointer writer and candidate insertion, not loaded island records or a live list. |
| Readiness reader | `0x18ba40` returns true only if the singleton root exists, `root+0xa0` is non-null, and byte `root+0xf10` is nonzero. | Read branch is exact; the true runtime value is not established. |
| Readiness writer | `0x156840` definitely clears `root+0xf10`. The four main-module direct byte stores at context displacement `+0xee8` include that clear and a nonzero store at `0x11196bc`; the latter receiver is loaded through a separate relocation/global path and is not joined to the root. The other clear receivers are not proven to be the root. | No nonzero write to the root readiness byte is resolved. The all-module raw scan also finds wider stores at `+0xee8/+0xf10`, but does not join their receivers to this root. |
| State-gated base-grid mutation | `0x8445d0` calls state getter `0x878b60` on the object at `+0x998`. State `1` branches to `0x8306c0`. States `2` or `3` continue only when `0x84fdf0` succeeds. That branch builds a rectangle from object fields at `+0x978/+0x988`, then calls `0x163780` at `0x8446fc` with attribute `6` and `0x163760` at `0x844710` with float `0.0`. | The handler writes the singleton root's base grid through `root+0xa0`; no direct call owner or runtime branch is identified. It writes base records, not a complete collision response. |
| Writer callback candidate | The recognized pointer sequence beginning `0x308ce28` has 31 entries; its `+0x38` entry at `0x308ce60` is `0x8445d0`. Constructor-like code at `0x8301a0` loads relocation cell `0x32e9e28` (addend `0x308ce18`), adds `0x10`, and stores that address as an object pointer. | This associates the function with a vptr-like function table. The table remains untyped and no indirect callsite to this slot is resolved. Indexed direct-call callers for `0x8445d0` are zero. |

The root/grid join is stronger than the previous pointer-only evidence: the owner callsite passes the value loaded from the exact singleton slot used by `0x18ba40` and the grid mutator wrappers. It still stops before a live-ready state. In particular, the call to `0x1978a0` does not set `root+0xf10`; the state-gated `0x8445d0` writer mutates the grid but also does not establish readiness.

## Query callback to movement outputs

`0x172740(grid, position, status_out, mode)` converts X/Z to a cell, selects one of four 12-byte plane triplets and the matching attribute byte in a 52-byte record, evaluates the plane, and returns its height. `0x1577a0` calls it with mode `1` for base-only sampling. `0x157270` walks the intrusive query list and calls candidate slot `+0x30` with mode `0`; the spatial-index table entry at `0x30376d8` resolves to `0x172740`. The optional candidate list and overlay records are not populated in a faithful world fixture.

`0x7bccf0` calls `0x1577a0` and `0x157270`, applies status/mode and environment comparisons, and returns an adjusted scalar. It is not simply the raw plane height. Movement consumers use that scalar in bounded branches:

- `0xdac780` calls `0x7c5570` at `0xdac808`; `0x7c5570` queries `0x7bccf0` twice and tests the two heights. Other `0xdac780` branches call `0x7bccf0` at `0xdac8bc` or `0xdac9bc`. The selected value is sent through actor vtable slot `+0xf8` and stored as transform Y. The function has one indexed incoming callsite from `0xda8560`.
- `0xda86b0`, reached from `0xdac780`, calls `0x7bccf0` at `0xda8748` and `0xda87b0`; selected branches call actor slot `+0x110`. The slot meaning and live state are unresolved.
- `0xe42b30` calls `0x7bccf0` at `0xe42ba0` and writes the scalar into a temporary movement vector's Y. Its indexed incoming callsite is `0xdf59d8`, with no established scheduler or Npad source.
- `0xe17cb0` writes velocity and movement fields from supplied timing/target data, while `0xdac550` consumes movement components to update actor position. Their input producers and frame scheduling remain open.

These joins show a path from a ready grid callback result to vertical correction in selected movement branches. They do not show player steering, a collision-solver completion, a landing result, or a successful traversal event. Existing fixture runs use prepared grids/fields, and the `0x7bccf0` boundary fixture stops on its null-root sandbox state before producing a result.

## Traversal-state readers and tool checks

The ladder routines read player state and position directly; they do not read the sampled Npad record in the inspected bodies:

- `0xe40b70` compares a selected state value to player state at `actor+0x2b4`, then checks X/Z deltas from `actor+0x278/+0x280` against a fixed threshold. If the state matches and both deltas pass, it calls `0xe409c0` at `0xe40cac`; otherwise it calls `0xe40450`. Its only indexed direct caller is `0xdf0584` in native span `0xdf0560`.
- `0xe40ce0` calls `0xe409c0` at `0xe40ee0` only after its object/result gates pass; its only indexed direct caller is `0xdf05d8` in native span `0xdf05a0`. This body has no direct `0x7bccf0` call.
- `0xe409c0` sets bits `0x6` in player field `+0xefc` and emits `PlayerLadderIsSkew` / `PlayerLadderToUp` labels. Its two callers are the selected branches above. This is a state/action transition fragment, not a validated climb.
- `0xe3f100` is reached from dispatcher `0xdaf680` case `0x10` at `0xdafb9c`. The dispatcher itself is called at `0xdae998` from `0xdae8c0`. `0xe3f100` contains nine direct `0x7bccf0` calls (at `0xe3f2e8`, `0xe3f480`, `0xe3f4ec`, `0xe3f6b8`, `0xe3f6d0`, `0xe3f744`, `0xe3f9e0`, `0xe3fae0`, and `0xe3faf8`) and references `DisableLadder` / `Player_ToolActionError`. This is a ladder-related tool/action check using ground queries; a successful climb or input-to-action edge is not established.

The `PlayerLadderReadyWait` and `PlayerLadderAction` strings are referenced by initializer `0xe41170`, not by a recovered runtime traversal callback. `State::cSwimRiver` and `State::cDriftRiver` are referenced only by initializer `0x585c80` in the indexed string-reference table. State names alone do not prove a swim/drift reader or water traversal.

River-related query branches are tool-action paths: `0xe49f90` calls `0x7bccf0` at `0xe4a078`, and `0xe4a500` calls it at `0xe4a654`; the callers are `0xde5d84` and `0xde5f84`. Their state/action labels are `PlayerRiverMakerDig/FallDig` and `PlayerRiverMakerBury/FallBury`. They support query-gated terraform checks, not river crossing. Bridge evidence remains at the EventFlow placement/progression level: the prior traversal review found no bridge endpoints, crossing action, or physical crossing result. No bridge traversal reader is joined to the ground query.

## Bounded search and limits

The current native index has 663,262 direct-call rows, 60,515 `functions` rows, and 149,425 `native_functions` rows. The recognized pointer index contains 18,348 sequences and 192,637 entries. The exact incoming-call scan finds one direct callsite to `0x1978a0`, zero to `0x8445d0`, five to `0x172740`, 223 to `0x7bccf0`, and the traversal callsites listed above. The raw writer scan covers aligned AArch64 text words and immediate-offset stores over main, `rtld`, `subsdk0`, and `sdk`; the report/JSON hash is recorded below. These bounds exclude neither computed-address stores nor runtime-built or unrecognized indirect dispatch.

The Npad poll method `0x1968b80`, `ControllerMgr` update `0x19a4ab0`, and the scheduler task tree remain separate from these movement/traversal readers. The registered controller task callback does not call the poller, the controller-manager update, the player state readers, or the query helpers. No sampled Npad field is joined to the player state at `+0x2b4`, tool dispatcher case `0x10`, or movement vector/velocity writer.

The canonical terrain writer and grid accessor both use 52-byte runtime records, but no loader/editor edge converts the 14-byte LandMaking source cells into this grid. The event-flow bridge recipe/placement sequence, water terraform checks, NPC route flags, and prepared native fixtures cannot substitute for a live player traversal result.

Status: **ROOT-TO-GRID SETUP EDGE PROVEN STATIC; ROOT READINESS WRITER OPEN; GRID CALLBACK/MOVEMENT BRANCHES PROVEN STATIC; LIVE QUERY AND PLAYER TRAVERSAL OPEN.**

### Source identity

- Main ELF SHA-256: `5bf707c3dc5dac0ad9635af7d336ec580f81c3f7876d0f55400d1900e3415d74`; supplied main NSO: `f8d248109ff72999b4600ae3749f8c7397fb960f7ad3ab8dee3018ae9e14e900`; decompressed main text: `9c9b45d8e7a58706ca59e7244b3aebac2325ef98faa205e007974eeeb2f758e9`.
- Native index SHA-256: `a78c7af27d37b8fd931bba8bc611623dacf7685cb6e8b4f827effa0765340aad`; recognized code-pointer sequences: `64d474068ca289f9146f7f32e6647a16a05e8f5be8e635615a478744b62ef822`.
- The companion JSON records function-slice hashes, relocation and pointer-table evidence, bounded query counts, and hashes of the prior reports used here.
