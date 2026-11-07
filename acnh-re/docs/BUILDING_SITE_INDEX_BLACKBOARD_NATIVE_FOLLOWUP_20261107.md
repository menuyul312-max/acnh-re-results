# BuildingSiteIndex and selected-site native follow-up

**Date:** 2026-11-07  
**Scope:** ACNH 1.0.0 static reverse engineering of the native `BuildStructure` site-selection method and its relation to the EventFlow NPC blackboard. This corrects the unresolved-key conclusion in [the placement-handler follow-up](BUILDING_PLACEMENT_NATIVE_HANDLER_FOLLOWUP_20261107.md). No game, save, Godot, or build execution was performed.

## Result

The previous report left `UNK_02a80082` unresolved because the displayed pseudocode address was searched as though it were an ELF virtual address. The decompiler display adds `0x100000` to database ELF VAs. After normalizing that display bias, the exact string at ELF VA `0x2980082` is `BuildingSiteIndex\0`. The native `BuildStructure` method writes its selected site index under that key in the actor's hash-backed AI blackboard. The registered EventFlow `NpcQueryBlackBoard` handler reads from the same actor member and hash-table layout, so the native assignment and EventFlow query are joined by key and storage shape.

The code also builds a six-entry availability bitset from a structure-like site list, chooses one available index, parses that entry into a two-component pair, stores the index, and passes the parsed pair into native actor-context handling. The follow-up [coordinate conversion trace](BUILDING_SITE_WORLD_POSITION_TRANSFORM_FOLLOWUP_20261107.md) now proves the pair becomes an X/Z vector using `10*n+5` before a dynamic component vcall; the final world frame/transform and durable save remain open. The story building for each index and the runtime preset instance are also unresolved.

## Address correction and raw string evidence

The analysis DB records `0x369d50` as the ELF VA for the `BuildStructure` slot candidate, while its pseudocode names the function `FUN_00469d50`. Likewise, the pseudocode label `UNK_02a80082` is normalized to ELF VA `0x2980082`. The read-only ELF metadata gives segment 1 a VA start of `0x2212000`; therefore:

```text
ELF VA         = 0x2980082
segment offset = 0x2980082 - 0x2212000 = 0x76e082
```

At that offset in the decompressed segment, the bytes are the exact NUL-terminated ASCII string `BuildingSiteIndex`. The raw ExeFS `main` NSO SHA-256 is `f8d248109ff72999b4600ae3749f8c7397fb960f7ad3ab8dee3018ae9e14e900`; decompressed segment 1 SHA-256 is `ed2a3e8fff6192db71f758150488cde6581c8963ddd355e9f0f10041e469c6ef`. This direct byte check supersedes the earlier zero-result `string_refs` search for this key; it does not imply the indexed string-reference table is complete.

## Native blackboard key insert, set, and query

The full resolved handler registry (`event_handlers_resolved.json`, SHA-256 `dfc298dfcb1b288b8fda9cd6a49c728fdad903b41f8fc1c9288df7d732ec92a5`; bound from `BindInfo.byml`, manifest ID 307) maps these names to native factories and constructors. Slot roles remain static candidates, but the relevant candidate bodies perform the matching operations:

| EventFlow operation | Handler / candidate | Native behavior |
|---|---|---|
| Register key/value | `MainNpc.EventFlowActionNpcRegistAIBlackBoard`; vtable candidate `0x25b560` | Calls ELF VA `0xc754a0` to insert the key and initial value into the actor's sorted hash table. |
| Set key/value | `MainNpc.EventFlowActionNpcSetAIBlackBoard`; vtable candidate `0x25bdf0` | Calls ELF VA `0xc756a0` to hash the key, find the matching table entry, and overwrite its value. |
| Query key/border | `MainNpc.EventFlowQueryNpcBlackBoard`; vtable candidate `0x386470` | Calls ELF VA `0xc75850` to find/read the key's value, then compares it with the configured `Border`. |

The register, set, and query bodies all reach the actor's table through the same shape: pointer at actor field `+0x2f8`, then table data at `+0x20`. The native hash helper at ELF VA `0x1bf0` hashes the NUL-terminated key with seed 0. The register helper inserts the value and key hash into a record and sorts the entries; the setter and getter search those hash entries. The prologue EventFlow evidence in the existing ledger shows `AI_NPC_Prologue_AN` and `AI_NPC_Prologue_HA` registering `BuildingSiteIndex=-1`, `AI_NPC_Prologue_Common` querying it with `Border=0`, and the orientation flows setting it back to `-1` (raw flow IDs and hashes are in the companion ledger).

## BuildStructure selection and handoff

The registered `EventFlowSystemActor.EventFlowActionBuildStructure` entry (BindInfo hash `202e4467`) has constructor `0x369c10` and a vtable slot candidate at ELF VA `0x369d50`. The exact method-to-runtime invocation remains an EventFlow dispatch boundary, so this section describes its static method body rather than a demonstrated live placement.

1. The method reads a structure-like object at `*0x33d1ba8 + 0x3a50`, with count at `+0x3a58` and entry pointers at `+0x3a60`. The six-slot loader and `mSiteList` descriptor are independently present at ELF VAs `0x4e1db0` and `0x55dfd0`; source association to `ValidateVillageSave` is recorded in the earlier placement report. The runtime object's exact parameter/preset identity is not established.
2. The method checks indices 0–5 through the list accessor at ELF VA `0x4e1d80` and adds valid indices to a six-bit set. The selector at ELF VA `0x166ab70` returns the rank-th set index. Its second input is the address of actor field `+0x288`; the decompilation shows the helper using the low 32 bits of that argument as the rank input, not loading a value from the field. No semantic field name is inferred.
3. If the selected index is in range, the method fetches that list entry, parses it through ELF VA `0x4e1670`, writes `BuildingSiteIndex = selected_index` through the same hash-table setter at ELF VA `0xc756a0`, and removes that index from the availability set. When the method's separate eligibility branch fails, it writes `BuildingSiteIndex = -1` instead.
4. The parser creates a two-component output pair using the observed arithmetic `first + (other_value >> 1), second + 1`. The field names, axes, units, origin, and reason for this adjustment remain unknown.
5. At PC `0x36a3ac`, the method passes the parsed pair to ELF VA `0xbe6480` with a structure-like scalar and flag 0. This callee branches on actor byte `+0x5ad`; it routes the pair through two coordinate-dependent helpers (`0xd3fd30` and `0xd40840`) in special branches, or through ELF VA `0xbe6340` in the common branch. The common branch calls an actor component virtual method at vtable slot `+0x158`, writes the selected scalar at actor `+0x610`, and notifies linked objects. The decompilation of the intervening component call at ELF VA `0x12eae0` uses an additional coordinate argument in a virtual call at `+0x128`, but the caller pseudocode omits that argument; this follow-through is therefore not promoted to a proven world-transform write.
6. At PC `0x36a3c0`, the method separately calls ELF VA `0xbf9520` on the actor's `+0x2f0` subobject with flag 0. That function copies the selected scalar to subobject `+0x4dc` and, when subobject `+0x370 < 31`, to `+0x39c`. Its flag-1 branch can also write `+0x320` and the first words behind pointers at `+0x348` and `+0x340`; the direct `BuildStructure` call uses flag 0.

The paired list record therefore reaches a concrete native actor-context branch, and its selected index reaches the exact EventFlow blackboard key. The code does not name the scalar source behind `*0x33d6180`, nor prove that this is the final terrain/building position or a save record.

## Remaining boundaries

- `cPlayerHouse`, `cBridge`, `cReserveNpcHouse` / plot A/B/C, and other story structure selectors are not mapped to particular indices 0–5.
- The six-cell `StructurePresetA00` source matches the native six-entry loader shape, but the runtime list instance and preset selection are not proven to be that exact asset instance.
- The selected adjusted pair's X/Z conversion is partially resolved as `10*n+5`, with downstream 5-unit field-grid indexing. Global origin/frame, untouched Y, orientation, footprint, and final model transform remain **OPEN**. The preview/build query's full footprint and terrain validators remain **OPEN**.
- The exact scalar copied by `0xbf9520`, selected model resource, `.phive`/PBC consumer, and collision instance remain **OPEN** or **CAT** where only catalog names exist.
- No serialized structure-instance record, durable save write/flush/reload, or day-change completion boundary was traced here.

## Validation

The companion JSON records the source hashes, corrected VAs, direct call PCs, behavior limits, and open joins. Checks confirmed the segment VA/offset calculation, exact raw string bytes, native-decomp source hashes, and JSON structure. No game or save was executed.
