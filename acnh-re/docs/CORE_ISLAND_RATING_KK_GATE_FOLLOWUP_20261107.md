# Island rating to first K.K. live gate follow-up

ACNH 1.0.0 static RE follow-up, 7 November 2026. This closes two evidence gaps left by the progression and post-rating reports: the native score-manager calculation/save-copy callsites, and the exact score-rank/result values that enter Isabelle's K.K. readiness branch. The machine-readable graph is [core_island_rating_kk_gate_followup_20261107.json](../output/gameplay/core_island_rating_kk_gate_followup_20261107.json).

The native score calculation and save writer are now joined statically to their callers. The EventFlow score result is also mapped to its displayed star count from the US English message member itself, rather than from result names. This remains a static join: `0x15c61f0` and the save writer were not run together, and no progressing game save was executed.

## Resolved path

`SNPC_sza_50_IslandEvaluation:Root` (source 622) calls `System_IslandEvaluationCheck:IslandEvaluationChk` at tree event #35, then `Compare_BeforeEvaluation` at #199. `IslandEvaluationChk` calls the Nature, Life, and minus-point rank entries. The native query implementations read the score save member at `+0x24fdb0`: `0x3e0b80` compares the requested threshold against the saved `f32` at `+0x240` (Nature), and `0x3df930` uses `+0x244` (Life). `0x419690` confirms the constructed-house query's polarity: it returns `count < Num`, so EventFlow case 0 at `Num=8` means at least eight constructed NPC houses.

The native score manager calculates totals in `0x15c61f0`. Its actor wrapper at `0xd50c0` calls that function at `0xd50d4` (`BL`, bytes `47c45394`). The save-copy function is `0x15c68c0`; actor method `0xd4df0` calls it at `0xd4f34` (`BL`, bytes `63c65394`). That method obtains the save member at offset `0x24fdb0`, requests `0x250` bytes, and passes its data pointer to the writer. The writer copies the category-10 grid and then stores Natural, Life, category-9 count, and category-5 count at offsets `+0x000`, `+0x240`, `+0x244`, `+0x248`, and `+0x24c`. The aggregation and save-copy methods use the same manager pointer loaded through global `0x32d3f68`; their callback ordering is not demonstrated by this static evidence.

The rank entries assign five ordinal result values using these comparisons:

| Output | EventFlow rank logic | Score interval for output rank 2 |
|---|---|---:|
| Nature (`SetIndex=2`) | 200, 270, 350, 450 | 270–<350 |
| Life (`SetIndex=3`) | 80, 160, 400, 650 | 160–<400 |

The `VillageScoreCheckNatural` and `VillageScoreCheckLife` native queries return true when `score >= BorderValue`. Following their branches gives rank 2 at Nature `>=270` and Life `>=160` (the table shows the interval where each rank equals 2). The eight-house branch of `IslandEvaluationChk` combines the rank results into overall result `SetIndex=0`. Its lower accepted result is 2 when both Nature and Life ranks are at least 2. With fewer than eight houses, `NotEnoughNNpc` clamps the result below 2; at seven houses it can set result 1 when both Nature and Life ranks are at least 2. Thus the lowest score path accepted by the K.K. branch is eight constructed NPC houses, Nature `>=270`, and Life `>=160`. Minus-point handling only reduces the top result in the high-rank branch; it does not reduce the qualifying result-2 path below 2.

The result-to-display mapping is directly present in `SNPC_sza_50_IslandEvaluation:NormalSeq`: result cases 0–4 call message labels `003_01`–`003_05`. The extracted `sza/SP_sza_50_IslandEvaluation.msbt` member (SHA-256 `1b2a62c50d05f73f4ba945b7d3205192a9b693935960362267921629b241706f`) labels those messages “1 star” through “5 star”; result 2 therefore means the explicit 3-star message. On entry, `Root` computes rating and comparison results, writes `IslandEvaluationUnlockMyself` and `SzaHeardAboutIslandEvaluation`, then selects `FirstSeq` or `NormalSeq` from `SzaHeardAboutEvaluationDetail`; the result presentation itself uses `MSG` nodes, with no dedicated rating-page action in the indexed flow. `Sza_Evaluation_CmnImpression` routes result cases 2, 3, and 4 through its K.K. check when `IslandDevQuestComplete` is OFF. `MakeVillagePlayerFlag` must be ON, and `ClearTkkFirstLiveScore` is called only on that branch. Within the entry, its `EventBranch AddDay=1` case 0 sets `IslandEvaluationClearTkkLive`, clears `IslandDevQuestRunning`, and sets `IslandDevQuestComplete`.

`Compare_BeforeEvaluation` also reads and updates `cPlayer:SzaBeforeIslandEvaluation`, which selects the evaluation-impression message. Its falling-rating branch emits `001_06` (“Our rating has fallen since the last time you checked”), then rejoins the result-specific path; the compare result does not add a separate K.K. score threshold.

After readiness is written, the already traced native gate at `0xfd8920` requires elapsed days `>=1`, `IslandEvaluationClearTkkLive=ON`, and `TkkFirstLive=OFF` before setting `TkkFirstLiveEnable=ON`. `Demo_PublicAnnouncement:Root_Init` requires `MakeVillagePlayerFlag=ON`, `TkkFirstLiveEnable=ON`, an `EventBranch AddDay=0` case 0, and its office/day conditions before setting `TkkFirstLiveReserved` and `TkkFirstLiveSubPlayer`. The exact EventFlow caller requesting the first-live stage is `Demo_PublicAnnouncement:PAnnounceSza`, source 279, event #41, reached from `Root` event #20 when the office is built and not in its build-today branch; #41 requests `SystemRequestChangeStage(TargetStage="cMainFieldFirstLive")` only when `TkkFirstLiveReserved` is ON. The native action handler at `0x304f80` reaches the first-live-specific branch through `0x305adc` (`BL 0x306910`, bytes `8d030094`). This confirms dispatch to that branch; the remaining stage-manager/resource/actor and actor-to-talk joins stay open as recorded in the stage-dispatch follow-up.

## Remaining joins and limits

- Static code proves that the aggregator and save writer operate on the same score-manager object and that the writer targets the score save member. Their runtime callback order and the full recalculation-to-commit path are still unexecuted.
- The UI evidence proves the `MSG` branches and their five explicit star labels. A dedicated rating page or a runtime call into the generic `CmnDialog` page is still not tied to this flow.
- The exact `PAnnounceSza #41` request and native action branch are resolved. The runtime continuation from `0x306910` to a selected stage resource and then to the live EventFlow remains open.
- All score queries, flags, and stage joins here are static. Existing synthetic fixtures cover score components and the K.K. scheduler wrapper, but not full score aggregation, save commitment, Isabelle's flow, and the first-live dispatch in one run.

## Validation

The raw ExeFS `main` SHA-256 matches `f8d248109ff72999b4600ae3749f8c7397fb960f7ad3ab8dee3018ae9e14e900`. Direct-call instructions were checked against its AArch64 bytes. The BFEVFL IDs and hashes, EventFlags table hashes, query function hashes, score-manager function hashes, and message-member hash are listed in the accompanying JSON. No game or save was mutated, and no test harness was run.
