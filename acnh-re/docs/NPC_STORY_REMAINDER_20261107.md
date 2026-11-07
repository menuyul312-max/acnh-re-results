# NPC story remainder audit (ACNH 1.0.0)

This note checks the prologue-to-K.K. story route and the general villager talk
path against the decoded EventFlow graphs, the native handler/state registries,
and the existing native fixtures. It is a bounded audit, not a playthrough
trace. The pinned `main` NSO is SHA-256
`f8d248109ff72999b4600ae3749f8c7397fb960f7ad3ab8dee3018ae9e14e900`.

Evidence labels used here:

| Label | What it proves |
|---|---|
| **EF** | A decoded EventFlow contains the action, query, flag write, or subflow call and its configured parameters. |
| **REG** | `focus7/native_event_handlers.json` connects a registered EventFlow name to a native factory, constructor, vtable, and code pointers. The row alone does not identify each slot's role or execute its body. |
| **BODY** | Original NSO instructions ran in a bounded harness. Any controlled reads, prepared objects, or stop-at-entry boundary are stated. |
| **PSEUDO** | Static disassembly/decompilation/call references support the interpretation; the path was not executed as a whole. |
| **NAME** | The EventFlow node is present, but the inspected handler inventory and focused native fixtures do not establish its handler semantics. This does not mean that no native handler exists. |

## Story-path audit

| Story beat | Graph path and native evidence | Boundary |
|---|---|---|
| Prologue fruit for the campfire | **EF:** `Tutorials_Prologue_Rco:Root` calls `TownFruitTypeChk`; that subflow queries `LandFruit`, checks `HasTargetItem`, removes six matching fruit, and sets `HaveTownFruit4CampFire`. `HasTargetItem`, `DeleteTargetItem`, `SetDeliveryItemAtRandom`, and `EventFlagSystemOn` have **REG** entries. `LandFruit` is **PSEUDO**: `GAMEPLAY_FLOW.md` links query `0x4145e0` to `SaveFg.SpecialityFruit` and maps the five local fruit IDs. | The fruit accessor was not run against a save. The focused inventory has no row for `LandFruit`, `NpcDelivery`, `GeneralTalkChoice2`, or the delivery/transition actions around the campfire. Their graph position is known; their live handler inputs and effects are not. |
| Day-two orientation with Tom Nook | **EF:** `SNPC_rco_00_StartMainGame:Root` calls `Rco_GetSmartPhone` and `Rco_TutorialGetBill`; `Rco_OrientationEnd` turns on prologue flags and reserves `Player_GetDemo_Once:Get_MainGame`. `SetDeliveryItemAtRandom`, `EventFlagSystemOn`, and `NpcAISetting` have **REG** code-pointer evidence. | The prologue does not have a native end-to-end EventFlow run. `SmartPhone`, `NpcDelivery`, `ReservePlayerMutterDemo`, and several UI/demo actions have no handler-body evidence in the focused inventory. `NpcAISetting` registration is not proof of the settings applied by this event. |
| Museum donation | **EF:** `SNPC_rco_01_Tent_1_Entries:RcoTentFishInsect` executes the `OwlIsDonation` query, `OwlDonationDone`, then `MuseumDonationNumCheck Border=5` before calling `SNPC_rco_51_DonationReward`. **BODY:** the native save writer `0xf780e0 → 0xf78130` ran seven controlled cases and the donation precondition/predicate ran five cases; all recorded zero mismatches. | The writer uses a synthetic `SaveMuseum` block, controlled item-kind/validity results, controlled marker bytes, and controlled adapters. Its statically identified caller `FUN_003c2410` was not emulated. `MuseumDonationNumCheck` and the live EventFlow selection-to-donor mapping remain open; writer evidence does not prove the whole Blathers interaction. |
| Three plots and resident services | **EF:** `SNPC_rco_53_MigrantsQuest` gives recipes/kits and uses `NpcHouseNum`; `Demo_PublicAnnouncement_Process` uses `IsSettlerQuestOutsideComplete`, `CompleteSettlerQuestSubject`, and `DecideSettlerNpc`. The focused handler inventory has **REG** evidence for `NpcHouseNum`, including query code pointer `0x419690`; `GAMEPLAY_FLOW.md` interprets its case polarity from pseudocode. | `NpcHouseNum` has not been run in a native fixture. The outside-completion query, completion action, and villager chooser have only graph-level evidence in this audit. The native resident selection and `ImmQ_*` transition writers remain outside the executed boundary. |
| Isabelle rating and first K.K. concert | **EF:** `System_IslandEvaluationCheck` supplies the rating result consumed by `SNPC_sza_50_IslandEvaluation`; the prologue route later reserves `cMainFieldFirstLive`, calls `SNPC_tkk_Live`, and Tom Nook returns in `SNPC_rco_55_TkkFirstLive`. The inventory has **REG** rows for some shared gates (`EventFlagSystemBool`, `NpcHouseNum`, `ShopLevel`, `MuseumLevel`) but not for the score query family or `TkkLive` stage actions. | Score and unlock descriptions in `GAMEPLAY_FLOW.md` are **PSEUDO/EF**, not a native run of Isabelle's EventFlow. `NpcAIActivityState::cTotakekeLive` is registered, but its activity callback and the first-live stage handoff were not executed. |
| AI-selected villager conversation | **EF:** `AI_NPC_Rco` uses `NpcCheckStateSelectTiming`, `NpcChangeAIState`, `SetNpcSpeakFlow`, and `NpcChangeConversationPretenseState`. **REG:** the latter three names map to native factory/constructor/vtable records in `focus7/native_event_handlers.json`; `NpcChangeConversationPretenseState` resolves through the registered `NpcChangeAIState` action binding. The state registry registers 43 common states and 24 activity states, including `cConversationHost` (60) and `cConversationGuest` (61). | The action rows expose native code pointers but no executed AI-state action body. The state-registry test reaches callback entry only. No scheduler tick, host/guest admission, state transition, or selected talk EventFlow was run. |

The evidence therefore supports the story graphs and several native leaf
contracts, but not an NPC's complete interaction in a live schedule. In
particular, the event node named in a graph should not be read as proof that the
named handler's behavior has been reconstructed: the `focus7` registry has 221
entries, and a factory/vtable record is a registration fact, not a runtime
result. Names absent from that focused inventory are marked **NAME** above only
for that inventory scope.

## Native talk-selector boundary closed here

The earlier talk-selector fixture exercised six cases at `0xf4dbd0`. This
follow-up extends that fixture to every per-resident slot. The original selector
and native key formatter `0x47360` ran for slots 0 through 9, plus the gate
mismatch and all-slots-miss cases: **12 cases, zero mismatches**. With controlled
counter reads, the function checks `TalkNpc0Count` as an initial gate, formats
the slot keys, stops on the first matching slot, and returns that resident
index; otherwise it returns `-1`.

This closes the selector's first-match mechanics: it returns the first resident
counter slot whose stored value matches the query argument. The
persisted-counter lookup `0xf4d560` and query-context helper `0xf4da70` were
controlled, so this is not a live-save result. The callers `0x395bc0`,
`0x395e50`, and `0x3960d0` were not executed. The selected resident index has
not been joined to a conversation topic, message label, `NpcInterest`/`NpcLife`
row, or EventFlow entry.

Reproduce from the checkout root; point `ACNH_RE_NSO` at the local main NSO and `PYTHONPATH` at the installed native dependencies:

```bash
ACNH_RE_NSO=/workspace/acnh-re/inputs/additional_exefs/main \
PYTHONPATH=/workspace/acnh-re/.deps \
python3 acnh-re/output/gameplay/npc_story_remainder_20261107/repro_talk_index_selector.py
```

The test writes [talk_index_selector_native.json](../output/gameplay/npc_story_remainder_20261107/talk_index_selector_native.json). It reuses one sandbox for all 12 cases, checks the original NSO checksum, and asserts every returned value and formatted key. The existing counter wrapper, friendship-action callback, and talk-streak reset evidence remains documented in [VILLAGER_SOCIAL_FOLLOWUP.md](VILLAGER_SOCIAL_FOLLOWUP.md); those fixtures separately use controlled resolver/writer boundaries.

## Exact remaining runtime work

The following edges keep the `villager-ai-talk` queue item open:

- Resolve the runtime role and callers of queue entry point `0xb17ae0`, then establish whether and when it participates in NPC scheduling. Capture the live path that evaluates `NpcCheckStateSelectTiming`, `SetNpcSpeakFlow`, and state requests; current **REG** evidence stops at action/state pointers and gives no dispatch cadence.
- Execute the `cConversationHost` and `cConversationGuest` entry/update/exit bodies (`0xc0b510`/`0xc0bd20`/`0xc0c280` and `0xc0c9e0`/`0xc0cb20`/`0xc0cc70`) with the runtime pair, event context, and actor dependencies they read. Existing state dispatch reaches these handler addresses, then stops before execution.
- Run `0xc30930` from each real conversation mode and correlate its action/animation request with the subsequent state change. Its current `NpcConversationTalk`, nodding, and `NpcTalk*` interpretation is **PSEUDO** and describes motion/expression requests, not topic selection.
- Trace the returned `0xf4dbd0` index through its callers to the actual topic/message/flow lookup; load the related `NpcInterest`/`NpcLife` data and capture its runtime selector inputs.
- Execute `0xc84240` through its talk counter and friendship effects against a controlled but complete player/resident save fixture. Current friendship-delta evidence starts downstream of that caller; `NpcAddFriendship` action tests cover configured EventFlow deltas but do not run the AI conversation path.
- Separately, run the story graph edges that still rely on **PSEUDO** or **NAME** evidence: `LandFruit`, `MuseumDonationNumCheck`, `NpcHouseNum`, `IsSettlerQuestOutsideComplete`, `DecideSettlerNpc`, island-score queries, and the K.K. stage handoff. Those need their query/action bodies plus the same live save/clock/structure context to establish story timing and branch results.

Sources inspected: [GAMEPLAY_FLOW.md](GAMEPLAY_FLOW.md),
[NPC_SOCIAL_FOLLOWUP.md](NPC_SOCIAL_FOLLOWUP.md),
[VILLAGER_SOCIAL_FOLLOWUP.md](VILLAGER_SOCIAL_FOLLOWUP.md),
`output/mechanics/focus7/native_event_handlers.json`,
`output/mechanics/npc_state_registry_native.json`,
`output/mechanics/focus7/npc_native_state_labels.json`, and the story trees
under `output/gameplay/trees/`. `docs/re_queue.json` remains unchanged; its
`villager-ai-talk` item still has priority 7 and names scheduler, state
transitions, and topic selection as the completion target.
