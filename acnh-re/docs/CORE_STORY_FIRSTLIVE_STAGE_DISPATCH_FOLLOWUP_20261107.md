# First-live stage dispatch follow-up (ACNH 1.0.0)

Static-only follow-up for the `PAnnounceSza` → first-live stage → K.K. actor → talk → return/credits path. No game execution, save mutation, or Godot changes were made.

The stage request is now traced one step farther than the earlier owner report. `EventFlowActionSystemRequestChangeStage` is registered with a `TargetStage` parameter; its method at `0x304f80` compares the target against a native 30-label table at `0x306c80`. `cMainFieldFirstLive` is entry 26, and the matching switch branch calls `0x306910` at `0x305adc`. That proves label recognition and dispatch to a first-live-specific native branch. It does **not** prove the next stage manager/event-queue edge.

The generic stage pipeline is independently visible. `0xfef090` calls the `Stage/Game/%s.byml` loader `0xfea5a0` at `0xfef1c0`; `0xfea5a0` calls path builder/resource reader `0xfe8420` at `0xfea710`, then the stage-list/include reader `0xfea760` at `0xfea740`. The latter recursively resolves `Stage/%s.byml` resources. The actor-list path has a separate recursive loader: `0xfeaa40` calls `0xfeabc0` at `0xfeab90`, and `0xfeabc0` calls row processors `0xfeb390` and `0xfeb5e0` at `0xfeac94` and `0xfeac9c`.

The strongest resource candidate is `B_data/Stage/Game/MainFieldDemoFirstLive.byml` (source 2909). Its include array contains `commonOutdoor` (source 2984). That resource's `ActorList[2]` has `ActorName` hash `0xc2701e0b`, which resolves to native actor type index 5, `NpcActorMgr`. The same name/hash is registered natively with factory `0xc67fa0`; that factory constructs the manager whose vtable includes method `0xc685a0`. The manager method calls `0xc70da0` at `0xc686ac` (`BL`, bytes `bd210094`); the builder creates `E_FirstLive_NPC_0`, binds `AI_NPC_Tkk_FirstLive`, and submits it through `0xc6c210`.

This gives a strong stage-to-manager **candidate**, but not an exact alias or a proven row-to-factory call. `Stage/StageList.byml` contains base labels such as `MainField`, not the `cMainFieldFirstLive` → `MainFieldDemoFirstLive` mapping. Also, the actor parser resolves the type hash and consumes actor rows, but the extracted call graph does not resolve its indirect factory dispatch to `0xc67fa0`. The candidate BYML's `commonOutdoor` include and matching registered manager type are evidence of consistency, not by themselves proof that this particular request instantiated that factory.

The EventFlow endpoints remain separated at the talk boundary. `AI_NPC_Tkk_FirstLive:Root` calls `AI_NPC_Common:ContinueSpeak`; the indexed caller list for that root is empty. `SNPC_tkk_Live:Tkk_LandFirstLive` also has an empty indexed caller list. Its own flow content is mapped: it calls `Tkk_1stLIveMC`, `Tkk_LiveDemo`, and `Tkk_LiveAfter_Flag`, then requests `cMainFieldPlayerHouse`. Thus the return target is present in the story data, but no static AI/native edge from the spawned actor to this talk entry was found.

The `State::cPlay` → `StaffCredit` callback is still not a demonstrated “credits after first live” trigger. The callback is registered under `State::cPlay`, then reaches a generic helper containing the `StaffCredit` resource key. No first-live/story caller edge joins that callback, and the 456 extracted EventFlow JSON files contain no literal `StaffCredit` or `StaffList` token. The indexed Flow graph omits message text, so this negative applies to explicit Flow/action names and subflow edges only.

| Edge | Result |
|---|---|
| `PAnnounceSza` target label → native ChangeStage case | **Confirmed to branch boundary**: label index 26 → `0x306910` at `0x305adc`. |
| `cMainFieldFirstLive` → exact `Stage/Game` filename | **Open**: `MainFieldDemoFirstLive.byml` is the unique semantic candidate; `StageList.byml` does not map the alias. |
| Candidate stage → `commonOutdoor` include | **Confirmed in candidate resource**; runtime selection of the candidate remains conditional on the open alias. |
| `commonOutdoor` actor row → registered `NpcActorMgr` type | **Confirmed by matching name/hash/type index**. |
| Actor-list row → `NpcActorMgr` factory invocation | **Open**: indirect dispatch target not resolved to `0xc67fa0`. |
| `NpcActorMgr` method → first-live actor + AI resource | **Confirmed statically**: `0xc685a0` → `0xc70da0`; actor and AI strings are embedded in the builder. |
| `AI_NPC_Tkk_FirstLive` → `Tkk_LandFirstLive` | **Open**: no indexed subflow/caller edge; the AI root only calls `ContinueSpeak`. |
| `Tkk_LandFirstLive` → return to `cMainFieldPlayerHouse` | **Confirmed in EventFlow data**; native label table also contains that return label at index 17. |
| First-live → `StaffCredit` | **Open**: generic `State::cPlay` callback exists, but no story trigger join. |

## Bounded negative results

- `flow_index.json` covers 456 EventFlow files and indexes explicit entries/subflow calls; it excludes message text and cannot expose engine-side dynamic talk selection.
- `direct_calls` proves direct `BL` edges only. The action→stage-loader continuation, actor row→factory dispatch, and AI→talk selection may use indirect/global dispatch and remain unresolved here.
- `StageList.byml` was checked as the stage-label catalogue; its base-stage list is not a complete alias table for `cMainField*` runtime labels.
- The `Stage/Game/MainFieldDemoFirstLive.byml` filename is a well-matched candidate, not an asserted mapping from the EventFlow label.

Machine-readable detail and source hashes are in [the accompanying JSON](../output/gameplay/core_story_firstlive_stage_dispatch_followup_20261107.json).
