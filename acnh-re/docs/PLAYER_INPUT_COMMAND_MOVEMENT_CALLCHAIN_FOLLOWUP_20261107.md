# ACNH 1.0.0 Npad-to-player command and movement call-chain follow-up

This pass continues the Npad/HID trace through scheduler dispatch and the controller-manager virtual update, then checks for a reader that turns sampled state into player actions and movement. It uses the supplied ExeFS modules, existing relocation/import records, function index, pointer sequences, and raw main-module disassembly. No Ghidra rebuild or game execution was done.

## Finding

The static scheduler route is now better bounded: the update-like method at `0x1c70310` calls `0x1977840`; that routine calls the `0x197ce80` thunk, which branches to task-manager update body `0x197cb30`. That body invokes the scheduler-group walker at `0x197a1d0`, which recursively dispatches enabled task nodes. Startup registers the callback `0x14ceed0` in the `SysCalc_Controller` group.

This still does **not** connect the sampled Npad records to player commands. The registered callback `0x14ceed0` only copies a field from its controller-manager subobject and checks a flag. The separate `sead::ControllerMgr` method at `0x19a4ab0` walks registered devices and calls their virtual slot `+0x20`; that slot is compatible with the Npad poller `0x1968b80`, but this pass did not establish that this manager method is invoked or that the polled device record is read by a player controller. Movement helpers, action names, ground-query branches, and controller samples therefore remain separate evidence groups.

## Proven static edges

| Edge | Evidence | Limit |
|---|---|---|
| HID API → Npad sample record | At `0x1968b80`, style query `0x1968bd4` selects one of five `GetNpadStates` imports at `0x1968c14`, `0x1968c2c`, `0x1968c44`, `0x1968c5c`, or `0x1968c74`. Each passes count `0x10` and an Npad ID. The output pointer is the per-device record `device + 0xe98*id + 0x58`, with the handheld/sentinel path using the record at `device + 0x58`. | Confirms raw HID state is written to the Npad object. The record's button/axis fields have not been traced to a game-side reader. |
| ControllerMgr → device update slot | `0x19a4ab0` walks the device list at manager `+0x170/+0x178` and invokes each device vptr slot `+0x20` with `BLR x8` at `0x19a4af0`. The relocated pointer sequence at `0x31a6cc8` contains this manager method at `0x31a6d78`, offset `+0xb0`. | Static virtual dispatch shape only. The list's runtime membership and a caller of `0x19a4ab0` are not established. |
| Device update slot → Npad poller | The sequence beginning at `0x31a4020` contains `0x1968b80` at `0x31a4040`, offset `+0x20`, matching the slot loaded by `0x19a4ab0`. The Npad constructor path at `0x1968a60` installs a vptr derived from its relocated table pointer. | The recognized pointer sequence is not, by itself, proof of C++ vtable type or that this instance is in the manager's list. |
| Startup → controller task registration | Startup `0x1535ad0` calls scheduler setup `0x15369c0`, task registration `0x14cef10`, and HID initialization `0x14ced30`. The named task record is linked into scheduler object `+0x5a0`; its callback field resolves to `0x14ceed0`. The group name is `SysCalc_Controller`. | Registration is not equivalent to a successful runtime task invocation. |
| Task/frame-like route → task-tree dispatch | `0x1c70310` calls `0x1977840` at `0x1c7034c`. The pointer sequence at `0x31c26e8` contains `0x1c70310` at `0x31c27c8`; another sequence at `0x31a4dd8` contains `0x1977840` at `0x31a4eb8`. `0x1977840` calls thunk `0x197ce80` at `0x197789c`; the thunk branches to `0x197cb30`, which calls scheduler walker `0x197a1d0` with its embedded group. The walker calls recursive node traversal `0x197a220`; enabled nodes dispatch through a node vptr at `0x197a244`. | This gives a static update-to-task-tree route. The top-level caller/cadence of `0x1c70310` is unresolved. Pointer sequences alone are not typed vtables. |
| Registered task adapter → callback | Registration stores owner/callback/context fields in the task descriptor. The adapter target at `0x14cf150` reaches `BR x1` at `0x14cf178`, using the descriptor callback pointer. The stored callback is `0x14ceed0`. | This dispatches the registered callback, not the Npad poller or the `0x19a4ab0` manager update. |

The callback body `0x14ceed0` loads its subobject at manager `+0x210`, calls `0x14cf380` (copying subobject `+0x60` to `+0xdc`), checks manager byte `+0x208`, and otherwise returns. It does not call `0x19a4ab0`, `0x1968b80`, an Npad state reader, or the mapped movement/query helpers. This is an important separation: the scheduler group contains a task named `sys::ControllerManager::update()`, but its recovered callback is not the path that polls Npad state.

## Command and movement join: still open

No sampled-state-to-command decode was recovered. The poll method writes the opaque SDK state structures into per-controller records, but no indexed direct caller reads those records, and the movement-side fields are supplied independently in existing native checks. The controller poller and `0x19a4ab0` each have zero indexed immediate-call callers; their known edges are through relocated code-pointer sequences and virtual dispatch candidates.

The existing movement map establishes fragments, not the producer of their inputs: `0xe17cb0` writes velocity at player `+0x574` and movement components at `+0xf58` from supplied time/target values; `0xdac550` consumes movement components and updates actor position at `+0x278`; `0xe42b30`, `0xdac780`, and `0xda86b0` reach ground-query helper `0x7bccf0` on selected branches. Those native tests use prepared fields and do not show an Npad-originating command. The ground-query results and landing/collision consequences also remain unproven in an authentic live world.

There are plausible names near the control and motion code, including `StickInputRate` and `StickInputGapDegree` (string references around `0xdb1e20`), `PlayerMoveTurn` / `PlayerMoveSpeed` (around `0xe1b580` and `0xe1b870`), and player states such as `cMove` / `cTurn`. These are parameter/state labels, not a def-use chain from the Npad record, so they are recorded as candidates only.

## Bounded search and conclusion

The indexed direct-call query found no direct callsite for `0x1968b80`, `0x19a4ab0`, `0x14ceed0`, or `0x1c70310`. The recognized relocated code-pointer index contains the poller and manager update only at the table slots described above; relocation/import records resolve the five Npad state imports uniquely to SDK exports. The all-module immediate-store/import scan in [the ExeFS-wide follow-up](PLAYER_WORLD_READY_MULTIMODULE_RAW_SCAN_FOLLOWUP_20261107.md) covers `main`, `rtld`, `subsdk0`, and `sdk`, and likewise leaves the input-to-player join open. These bounds do not exclude runtime-built pointers, unrecognized tables, computed-address readers, or indirect calls through objects whose dynamic identity is unknown.

Current chain status:

`SDK Npad state API → per-device sample record` **PROVEN STATIC** → `player command/action decoder` **OPEN** → `player movement fields and movement update` **PARTIALLY MAPPED, INPUT PRODUCER OPEN** → `live ground/collision result` **OPEN**.

The scheduler route is more concrete than before, but it does not close the player-control path. To close that path, evidence is still needed for (1) invocation of `ControllerMgr::update` on the Npad manager/device list, (2) the reader and decoder of the per-device sampled state, (3) the command/state writer that supplies the movement helper inputs, and (4) a live/faithful ground-query result. The companion [machine-readable ledger](../output/mechanics/player_collider_query_remainder_20261107/player_input_command_movement_callchain_followup_20261107.json) records the exact PCs, searches, source hashes, and status boundaries.

## Source identity

- Main ELF inventory hash: `5bf707c3dc5dac0ad9635af7d336ec580f81c3f7876d0f55400d1900e3415d74`.
- Main NSO: `f8d248109ff72999b4600ae3749f8c7397fb960f7ad3ab8dee3018ae9e14e900`; decompressed main text: `9c9b45d8e7a58706ca59e7244b3aebac2325ef98faa205e007974eeeb2f758e9`.
- `rtld`, `subsdk0`, and `sdk` NSO hashes and import/export evidence are listed in the companion JSON.
- Recognized pointer-sequence index: `64d474068ca289f9146f7f32e6647a16a05e8f5be8e635615a478744b62ef822`.
- Existing native index: `a78c7af27d37b8fd931bba8bc611623dacf7685cb6e8b4f827effa0765340aad`.
