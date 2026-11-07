# Post-rating chain follow-up: K.K. first-live gate, credits, and Island Designer

Audit date: 7 November 2026. Scope: ACNH 1.0.0 static RE from Isabelle's K.K. readiness flag through the first-live announcement, stage/NPC handoff, credits evidence, and the post-live Nook/license flows. Source artifacts are in the repository’s `acnh-re/` directory; paths in the hash table are relative to that directory. This report and its JSON are stored in the same repository. The cited native instructions are disassembly of the ExeFS `main`, not execution in the game.

Machine-readable proof graph: [`core_story_post_rating_chain_followup_20261107.json`](../output/gameplay/core_story_post_rating_chain_followup_20261107.json).

The earlier uncertainty about the second flag argument in `0xfd8920` is resolved. Raw AArch64 shows that the query is `TkkFirstLive`, and the function writes `TkkFirstLiveEnable=1` only when elapsed days are at least one, `IslandEvaluationClearTkkLive` is ON, and `TkkFirstLive` is OFF. A separate day-change block in `0xf545f0` clears `TkkFirstLiveReserved`, reads `TotakekeLiveCount`, and when the count is at least one writes `TkkFirstLive=1` and clears `TkkFirstLiveEnable`. Both findings are static native evidence; no main-story save was executed end to end.

## Proof graph

```mermaid
flowchart LR
    R[Isabelle: IslandEvaluationClearTkkLive ON\nEventFlow #52, source 622]
    G[Day change 0xfd8920\nelapsed >= 1 AND flag ON\nAND TkkFirstLive OFF -> Enable ON]
    A[Public announcement\nreserve first live; request cMainFieldFirstLive]
    S[Stage / AI actor handoff]
    L[SNPC_tkk_Live:Tkk_LandFirstLive\ndemo + after-live flags/count]
    D[Day-change 0xf545f0\nTotakekeLiveCount >= 1 -> TkkFirstLive ON; Enable OFF]
    V[StandByRcoVisitMyHomeAfterTkkFirstLive ON]
    P[Daily processor queues phone standby flags]
    I[SNPC_rco_55_TkkFirstLive:InvitePlayerHouse]
    C[MainmenuConstructLicense ON\nUIMenuDeviceAppear(cConstructLicense)]
    X[StaffCredit assets]
    R --> G --> A
    A -. "OPEN: no stage/AI-to-entry caller" .-> S
    S -. "OPEN: entry callsite absent" .-> L
    L --> D
    L --> V --> P
    P -. "OPEN: no direct visit-flow join" .-> I
    I --> C
    L -. "OPEN: trigger not identified" .-> X
```

| Transition or claim | Evidence status | What the source proves |
|---|---|---|
| Readiness flag to first-live enable | **STATIC_NATIVE_CONFIRMED** | Exact flag names and branch polarity are visible in `0xfd8920` disassembly. This closes the old missing-argument issue, but does not show a story save running through the condition. |
| Enable to reserved announcement and stage request | **EF_LOCAL; runtime join open** | `Demo_PublicAnnouncement:Root_Init` (ID 279) checks `TkkFirstLiveEnable` and writes `TkkFirstLiveReserved`; `PAnnounceSza` event #41 requests `cMainFieldFirstLive`. |
| `cMainFieldFirstLive` to `Tkk_LandFirstLive` | **OPEN_JOIN** | The destination stage, dedicated NPC entry, and native stage/AI actor construction are present. `SNPC_tkk_Live`, `AI_NPC_Tkk_FirstLive`, and the actor-builder have no indexed direct caller tying the stage to that entry. |
| First-live completion to `TkkFirstLive` native state | **EF_LOCAL + STATIC_NATIVE_CONFIRMED; not executed together** | `Tkk_LiveAfter_Flag` adds `TotakekeLiveCount` and sets the Nook standby flag. The day-change block reads that count and updates `TkkFirstLive`/Enable. |
| Standby Nook visit to `InvitePlayerHouse` | **OPEN_JOIN** | The daily processor consumes the standby flag and queues phone-call flags. `InvitePlayerHouse` clears the visit standby flag but does not read it; its license branch tests `TkkFirstLiveReserved` and bag capacity. No direct EventFlow caller connects the two. |
| `InvitePlayerHouse` to Island Designer | **EF_LOCAL** | Its event #16 sets `MainmenuConstructLicense`; #17 installs `cConstructLicense`. This proves the local unlock action, not the upstream visit scheduling. |
| First live to credits | **OPEN_JOIN** | Staff-credit layout/string paths and a generic native `StaffCredit` reference exist. No credit event, EventFlow caller, or identified native/stage trigger ties them to the first live. |

## Exact native gate and writer

The audited native image is `inputs/additional_exefs/main`, SHA-256 `f8d248109ff72999b4600ae3749f8c7397fb960f7ad3ab8dee3018ae9e14e900`. The instruction listing below was independently decoded from its AArch64 bytes; little-endian byte strings are shown for the conditional instructions. Pseudocode and static references are corroboration, not runtime proof.

### `0xfd8920`: readiness flag → enable flag

Direct caller: `0xf545f0`, call instruction at `0xf54fdc`. SQLite direct-call index has no other caller. `0xf545f0` is itself called from day-change driver `0xf53a70` at `0xf53e4c`.

| PC | Instruction / encoding | Reading |
|---|---|---|
| `0xfd8934` | `ldr x8, [x1]` | Load the elapsed-day argument. |
| `0xfd8940` | `cmp x8, #1` (`1f0500f1`) | Compare against one day. |
| `0xfd8944` | `b.lt #92` (`eb020054`) | Skip unlock block for values below one; continue for elapsed days ≥ 1. |
| `0xfd8950`–`0xfd8954` | `adrp x8, #27041792`; `add x8, x8, #361` | Resolves to string VA `0x29a2169`, `IslandEvaluationClearTkkLive`. |
| `0xfd8964` | `bl 0xf44d90` | Read that flag. |
| `0xfd8968` | `tbz w0, #0, #56` (`c0010036`) | Skip if bit 0 is clear; readiness flag must be ON. |
| `0xfd896c`–`0xfd8970` | `adrp x8, #27115520`; `add x8, x8, #3955` | Resolves to string VA `0x29b4f73`, `TkkFirstLive`. |
| `0xfd897c` | `bl 0xf44d90` | Read `TkkFirstLive`. |
| `0xfd8980` | `tbnz w0, #0, #32` (`00010037`) | Skip the writer when bit 0 is set; `TkkFirstLive` must be OFF. |
| `0xfd8984`–`0xfd8988` | `adrp x8, #27000832`; `add x8, x8, #1267` | Resolves to `0x29984f3`, `TkkFirstLiveEnable`. |
| `0xfd8994` / `0xfd899c` | `mov w1, #1` (`e1030032`); `bl 0xf44e70` (`35b1fd97`) | Write `TkkFirstLiveEnable=1`. |

After the gate, `0xfd8920` calls `0xfd8a80` at `0xfd89a8` to build the weekly visitor schedule and `0xfd9620` at `0xfd89b4` to validate today's entry. The static function summary is also in `native_flag_refs.json:data.flags.cLand:TkkFirstLiveEnable` and `data.day_change_dispatcher_pipeline`.

### `0xf545f0`: completed-live count → first-live occurred

Direct caller: `0xf53a70`, call instruction at `0xf53e4c`. The function calls `0xfd8920` at `0xf54fdc`. The following block is conditional on an earlier scheduler-result bit, a non-null result from `0xf2d310`, and a nonzero pointed-to context/day value; it is not an unconditional daily write.

| PC | Instruction / encoding | Reading |
|---|---|---|
| `0xf54790`–`0xf54794` | `adrp/add` to `0x2969cbd` | `TkkFirstLiveReserved` address in the register later passed to the flag writer. |
| `0xf54798`–`0xf5479c` | `adrp/add` to `0x29b4f73` | `TkkFirstLive` address. |
| `0xf547a0`–`0xf547a4` | `adrp/add` to `0x29984f3` | `TkkFirstLiveEnable` address. |
| `0xf54824` / `0xf54828` | `stp` reserved-flag key; `bl 0xf44e70` with `w1=0` | Clear `TkkFirstLiveReserved`. |
| `0xf5482c`–`0xf54838` | Set up `TotakekeLiveCount`; `bl 0xf4aff0` | Read the player count flag (`EventFlagsPlayerParam`, source ID 26). |
| `0xf5483c` | `cmp w0, #1` (`1f040071`) | Compare count to one. |
| `0xf54840` | `b.lt #48` (`8b010054`) | Skip writes for count < 1; proceed for count ≥ 1. |
| `0xf54854`–`0xf5485c` | `mov w1,#1`; key `TkkFirstLive`; `bl 0xf44e70` | Set `TkkFirstLive=1`. |
| `0xf54864`–`0xf5486c` | `mov w1,#0`; key `TkkFirstLiveEnable`; `bl 0xf44e70` | Clear `TkkFirstLiveEnable`. |

The exact string addresses are independently present in `output/index.sqlite` (`string_refs`) for function `0xf545f0`. Static pseudocode is `output/binary/analysis_decomp/f545f0.c`. EventFlow `SNPC_tkk_Live:Tkk_LiveAfter_Flag` (source ID 625, events #144/#16 in branches) increments the same `TotakekeLiveCount`; this makes the count read semantically meaningful but does not execute both systems in one save trace.

## Stage, visit, and credits joins

`Demo_PublicAnnouncement:Root_Init` (BFEVFL source ID 279) reads `TkkFirstLiveEnable`; event #83 sets `TkkFirstLiveReserved` under its player/day/building conditions. `PAnnounceSza` event #41 requests `cMainFieldFirstLive`. `SNPC_tkk_Live:Tkk_LandFirstLive` (ID 625) calls `Tkk_1stLIveMC`, `Tkk_LiveDemo`, and `Tkk_LiveAfter_Flag` (#118/#92/#93); event #94 returns to `cMainFieldPlayerHouse`. The after-flag entry sets `TkkFirstLiveJoined`, `TkkLiveToday`, `StandByRcoVisitMyHomeAfterTkkFirstLive`, and increments `TotakekeLiveCount` (#141–146). The source graph does not connect the requested stage to this entry: `called_from=[]` for `SNPC_tkk_Live` and both first-live AI flows; `AI_NPC_Tkk_FirstLive:Root` only calls `AI_NPC_Common:ContinueSpeak`. Native actor builder `0xc70da0` references `E_FirstLive_NPC_0` and `AIF:AI_NPC_Tkk_FirstLive`, but the direct-call index records no direct caller for `0xc70da0`, and no actor-to-`Tkk_LandFirstLive` call is identified.

The post-live daily processor makes a separate branch. `Demo_PublicAnnouncement_Process:ChkStartGamePhoneCall` (ID 295) calls `CheckPhoneCallIslandCreater` at #158. That entry checks `TkkFirstLive`, `MainmenuConstructLicense` OFF, `StandByRcoVisitMyHomeAfterTkkFirstLive`, day branch and `PlayerHouseLevel`; its actions set `StandByPhoneCallIslandCreater` and `StandByGameStartPhoneCall` (#163–166), or clear flags on other schedule cases. It does not call `SNPC_rco_55_TkkFirstLive:InvitePlayerHouse`. That invite entry (ID 606) clears the visit standby flag (#31), checks baggage and `TkkFirstLiveReserved`, then in the grant branch delivers item 4318, sets `MainmenuConstructLicense` (#16), and installs `cConstructLicense` (#17). The phone-call flow `Player_StartGamePhoneCall` (ID 521) separately reads `StandByPhoneCallIslandCreater` in `ChkPhoneCall` and writes the same license in `IslandCreaterTell` / `_Continued` (#145), but its indexed direct callers are empty. These are two confirmed local unlock implementations with an open automatic scheduling/entry join.

The extracted ROMFS inventory contains `Layout/StaffCredit.Nin_NX_NVN.zs` and `BDLI/String/USen/STR_StaffList.bdli.zs`. `0x1470e90` references the generic string `StaffCredit`, but has no direct caller in `index.sqlite`; none of the 456 indexed EventFlows contains `StaffCredit` or `StaffList`. This does not identify the game-over/staff-roll trigger. Layout or string presence alone cannot prove the credits are shown after the concert.

The emulated save layout identifies a generic cLand flag store at node `0x1575b0`, data `0x200ff4`, size `0x800`, and the flag metadata identifies `EventFlagsLandParam` (source ID 18) and `EventFlagsPlayerParam` (source ID 26). The available save-layout evidence does not map these story flag names to individual offsets/bits. No model, audio, raw scene/stage asset, or rendered UI was used to establish the open handoffs or credits trigger.

## Evidence hashes

| Artifact | SHA-256 |
|---|---|
| `inputs/additional_exefs/main` (ExeFS `main`) | `f8d248109ff72999b4600ae3749f8c7397fb960f7ad3ab8dee3018ae9e14e900` |
| `output/index.sqlite` | `a78c7af27d37b8fd931bba8bc611623dacf7685cb6e8b4f827effa0765340aad` |
| `output/gameplay/flow_index.json` | `359f3a21a17a116902b0c8e1110c3892814b6fccbeb50b71d573c8ab3e1c68c5` |
| `output/gameplay/flag_index.json` | `0a27bae4ad2f7dbae70f10d8bc460b2e79ba3c7e9a4eabe38feb501321fb79a6` |
| `output/gameplay/native_flag_refs.json` | `e7b1f581a342a6ec856cc735326823f0721aa81b587fc54f4300b2ab2b25bedc` |
| `output/gameplay/save_layout.json` | `a326c84213faad1921bd7660c3e171a7b3af117ec55e2ca711a871ad637e51dc` |
| `output/additional_romfs/extracted_manifest.json` | `5e2327bc81c0a526cbcf878e9d899f47536b5b8f5a9fdf8b4a776413f75b64b8` |

EventFlow source IDs/hashes: `279` Demo_PublicAnnouncement `7ec0d30107a1d40169b4455932f0f6853beb9ef7b7cf69ca2ee2f77958a12602`; `295` Demo_PublicAnnouncement_Process `7b921fd4ef4b262169b3f9d445bf74437fcf913294607d20f8b29c6b65bb8077`; `514` Player_GetDemo_Once `191b49e0fcb1e2c116068b9e69d40c837031a28b9e579f83f19a1eeca999298b`; `521` Player_StartGamePhoneCall `f14f415f0eb70050a2c7d731b0f38639d65cbd78fee54f45c666d8691241b842`; `606` SNPC_rco_55_TkkFirstLive `b3d6e9d359a19a744561d7b2c7f213b71513c3489ebee2c679b46e1540407905`; `622` SNPC_sza_50_IslandEvaluation `c57c677d2d2f09290c0414f7a43c404bb28e8b8c126b6ce703df61c61ff3281e`; `625` SNPC_tkk_Live `d1a9d0253d4ae6c1ed46e87d007f8924f4cba637589a3d0750ca07295794d316`; `272` AI_NPC_Tkk_FirstLive `5f7c36dba971c8c30f434b92085a8bb7e8bd677df39bcd008d0aa8950e02a9f8`; `258` AI_NPC_Rco_FirstLiveInvite `f0b576c5d5f8b1877609b4a971f32aebed02a612f7aabad8e8c60cb8cd89da2c`.
