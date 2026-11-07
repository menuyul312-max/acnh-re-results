# First-live AI-to-talk parameter binding follow-up (ACNH 1.0.0)

This static follow-up checks the EventFlow arguments that the earlier caller index did not carry through. It closes the source-graph edge from the first-live AI root to the dedicated K.K. talk entry. It does not establish that the candidate stage, actor manager, or AI root executes in a live game. No game or save was run, and no Godot work was done.

## Confirmed EventFlow edge

`AI_NPC_Tkk_FirstLive:Root` starts at event-array index 5 (`Event5`). That event is a subflow to `AI_NPC_Common:ContinueSpeak` with the explicit arguments `FlowName=SNPC_tkk_Live` and `EntryName=Tkk_LandFirstLive`.

The common continuation consumes those same argument names. Its event-array index 2 first invokes `EventFlowActionNpcChangeAIState` with `StateName=cContinueSpeak`; event-array index 3 then invokes `EventFlowActionSetNpcSpeakFlow` with `FlowName=$arg(FlowName)` and `EntryName=$arg(EntryName)`. Together, the caller values and callee argument references statically select `SNPC_tkk_Live:Tkk_LandFirstLive` for this AI resource. This is a source-graph binding, conditional on the AI root being entered; it is not a runtime trace of the native NPC state.

The action registry in the native handler inventory recognizes `EventFlowActionSetNpcSpeakFlow` (registration hash `0x878212f7`, registration cell `0x305aba8`, factory `0x450a70`, constructor `0x25eab0`, vtable `0x303f518`) and lists `FlowName` and `EntryName` as its string parameters. `EventFlowActionNpcChangeAIState` is separately registered at `0x305aeb8` with factory `0x4516b0` and constructor `0x252f30`. This ties both source-graph action names to the supplied main binary's native action registry. The action method's precise storage/dispatch behavior and its live execution are not established here.

The selected target entry, `SNPC_tkk_Live:Tkk_LandFirstLive`, contains the first-live master-of-ceremonies subflow, the live-demo subflow, and the after-live flag subflow. Its static graph includes `SystemRequestChangeStage(TargetStage=cMainFieldPlayerHouse)` at event-array index 94. The prior flow trace records the after-live branch's writes to `TkkFirstLiveJoined`, `TkkLiveToday`, `TkkTalkToday`, `StandByRcoVisitMyHomeAfterTkkFirstLive`, and `TotakekeLiveCount`. The day-change routine later reads that count and sets `TkkFirstLive`. These are authored flow/native relationships; they do not demonstrate one continuous playthrough.

## Why the earlier flow index missed this edge

The [`flow_index.json`](../output/gameplay/flow_index.json) graph records `AI_NPC_Tkk_FirstLive:Root → AI_NPC_Common:ContinueSpeak`, but shows no caller for `SNPC_tkk_Live:Tkk_LandFirstLive`. Its caller builder only records literal `flowchart`/`entry_point` subflow fields. The target flow and entry are instead passed as arguments to the intermediate `SetNpcSpeakFlow` action. The empty `called_from` result is therefore a limitation of that index for parameterized flow selection, not evidence that the source flow omits the target.

There is a separate similarly named path: `AI_NPC_Rco_FirstLiveInvite:Root` passes `SNPC_rco_55_TkkFirstLive:InvitePlayerHouse` through `AI_NPC_Common:VisitSpeak`. That flow handles the invitation/visit-home follow-up and includes a `Player_GetDemo_Once:Finish_1stKkLive` request. It is not the K.K. concert's `SNPC_tkk_Live:Tkk_LandFirstLive` entry and should not be used as its actor-to-talk join.

## End-to-end boundary and remaining gaps

The [prior stage trace](CORE_STORY_FIRSTLIVE_STAGE_DISPATCH_FOLLOWUP_20261107.md) and native builder evidence, combined with this EventFlow follow-up, establish the static candidate chain:

`NpcActorMgr` builder candidate → `AI_NPC_Tkk_FirstLive` resource name → `AI_NPC_Tkk_FirstLive:Root` arguments → `AI_NPC_Common:ContinueSpeak` → `SetNpcSpeakFlow(SNPC_tkk_Live, Tkk_LandFirstLive)` → first-live talk-flow content → authored request back to `cMainFieldPlayerHouse`.

The stage alias-to-file mapping and actor-row indirect factory dispatch remain conditional. The prior native trace found `cMainFieldFirstLive`'s dedicated branch and a matching `MainFieldDemoFirstLive.byml` / `commonOutdoor` / `NpcActorMgr` candidate; it did not prove those resource and factory joins. The builder's construction of `E_FirstLive_NPC_0` with `AI_NPC_Tkk_FirstLive` is static, but its runtime activation from this stage remains open.

The native `State::cPlay` callback containing the `StaffCredit` resource key is a separate path ([callback trace](CORE_STORY_INDIRECT_OWNER_TRACE_20261107.md)). A bounded search of the extracted EventFlow JSON and the indexed EventFlow graph found no `StaffCredit` or `StaffList` token, and no edge from `Tkk_LandFirstLive` or its return stage into that callback. The credits trigger therefore remains **OPEN**. The first-live flag/day-change relation is detailed in the [villager continuity follow-up](VILLAGER_PLOT_FIRSTLIVE_CONTINUITY_FOLLOWUP_20261107.md). Model and sound payloads remain catalogue-only under the existing evidence policy.

| Join | Status |
|---|---|
| `AI_NPC_Tkk_FirstLive:Root` → `AI_NPC_Common:ContinueSpeak` with target arguments | **Confirmed in EventFlow source data** |
| `ContinueSpeak` → `cContinueSpeak` state action → parameterized `SetNpcSpeakFlow` | **Confirmed in EventFlow source data; native action registrations identified** |
| `NpcActorMgr` stage record → first-live builder at runtime | **Open**; stage alias and indirect factory dispatch are not closed |
| `Tkk_LandFirstLive` → authored return to `cMainFieldPlayerHouse` | **Confirmed in EventFlow data**, conditional on the flow path executing |
| First-live completion → `State::cPlay` / `StaffCredit` trigger | **Open** |

## Evidence identity and limits

The main executable identity is SHA-256 `5bf707c3dc5dac0ad9635af7d336ec580f81c3f7876d0f55400d1900e3415d74`. The raw EventFlow source hashes, parsed EventFlow JSON hashes, native action-registry hash, flow-index hash, and prior stage-dispatch proof hashes are recorded in the companion JSON. The raw EventFlow files have pinned hashes; their version label is inherited from the supplied 1.0.0 analysis corpus rather than an embedded version field in BFEVFL.

The extracted tree and flow index are static. EventFlow action names and arguments prove authored graph intent, not that the engine loaded this stage, instantiated this actor, or ran the selected entry. The actor-model and music/audio resource conversions are outside this proof and remain catalogue references.
