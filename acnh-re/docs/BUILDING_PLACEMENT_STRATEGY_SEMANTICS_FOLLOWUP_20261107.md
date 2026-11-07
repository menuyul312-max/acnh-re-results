# Building placement StrategyType and message status mapping

**Result.** The nine StructureType enum ordinals are now tied to the five installed strategy entries through direct parser and switch evidence. The result bitset is also tied to the `BuildStructureErrorMsg` switch and its US English TalkSys message labels. Specific BCSV row joins remain open.

## Direct enum proof

The `EventFlowQueryCanBuildHere` constructor stores the native property key `StructureType` before the value parsed at object offset `+0xd0`; the next keys are `StructureBuildPosType` and `StructureBuildTiming`. Its body calls the enum converter for the `StructureType` value, then passes the numeric output through `0x3771d0` into the switch at `0x376eb0`. The generated enum extraction code explicitly defines list position as the enum value. The source list at ELF VA `0x2969f28` is:

| Ordinal | EventFlow name | Strategy route |
|---:|---|---|
| 0 | `cPlayerHouse` | 1 |
| 1 | `cNormalNpcHouse` | 2 |
| 2 | `cMuseum` | 3 / subtype 2 |
| 3 | `cMarket` | 3 / subtype 0 |
| 4 | `cReserveNpcHouse` | 2 |
| 5 | `cBridge` | 4 if its secondary lookup succeeds; otherwise dispatch falls through case 6 and can route to 5 or 3/subtype 2 |
| 6 | `cSlope` | 5 if its secondary lookup succeeds; otherwise 3/subtype 2 |
| 7 | `cTailor` | 3 / subtype 5 |
| 8 | `cCampSite` | 3 / subtype 6 |

`cBridge` (5) and `cSlope` (6) use secondary lookups in the dispatch switch. The switch may route them to indexes 4/5, or fall back to strategy 3/subtype 2. No BCSV row is assigned from name similarity.

## Result code to message proof

The result setter at `0x10e4ef0` accepts codes 0–21. It checks only the low 32-bit word before setting the requested bit, so it does not prove a global first-write-only rule for codes 8–21. Getter `0x10e4e40` scans bit positions 0–21 and returns the lowest set index, or 21 when none is set. The registered `EventFlowActionBuildStructureErrorMsg` body calls the same strategy dispatch, reads that code, maps it in a switch, and formats `TalkSys/SYS_Player:<message-id>` with an optional suffix. The USen labels resolve to:

| Status | TalkSys label | Message category shown by the source text |
|---:|---|---|
| 0 | `911` | I'm too close to the water. I need more room. |
| 1 | `911_01` | The ground isn't stable near these rocks, so I shouldn't try to build anything here. |
| 2 | `912` | I'm too close to the water. I need more room. |
| 3 | `913` | I'm too close to a cliff. I need more room. |
| 4 | `914` | I'm too close to the ledge. I need more room. |
| 5 | `914_01` | Everyone gathers in this plaza, so you should choose a different place. |
| 6 | `915` | If I place buildings too close to each other, it'll block the flow of traffic. Better choose another place! |
| 7 | `916` | If it's too close to a bridge like this, it'll block the flow of traffic. Better choose another place! |
| 8 | `917` | If it's too close to an incline like this, it'll block the flow of traffic. Better choose another place! |
| 9 | `918` | This is too close to the plaza. I don't want anything to get in the way here. Better choose another place! |
| 10 | `919` | This is fairly close to someone's mailbox, so this isn't a good spot. Better choose another place! |
| 11 | `919_01` | I'll need to move the [tag group=0 type=3 data=0100]mailbox[tag group=0 type=3 data=ffff] first. |
| 12 | `921` | There's no river near here that I can place a bridge over! |
| 13 | `926` | To place a bridge, you need the river to be just the right width. And the land on either side should be even. |
| 14 | `926_01` | It'd be hard to use a bridge here with the water so close. |
| 15 | `926_02` | It'd be hard to use a bridge here with the cliff so close. |
| 16 | `926_03` | I don't think it'd be a good idea to build a bridge on the sand here. |
| 17 | `921` | There's no river near here that I can place a bridge over! |
| 18 | `927` | I don't see an even stretch of cliffs here where an incline could go. |
| 19 | `928` | If I put an incline here, the end of it will bump up against a cliff. |
| 20 | `928_01` | This is a little too high. I don't think I'll build an incline up here. |
| 21 | `910` | There isn't enough space here. |

Status 21 takes the switch default, label `910` (“There isn’t enough space here.”); the switch also sends any other unhandled code to that default. The `StructureInfoParam` table contains broad `House`, `Facility`, `Bridge`, and `Slope` categories, but this trace did not find a direct join from each of the nine EventFlow ordinals to a particular BCSV row.

## Saved site pair boundary

In the BuildStructure body, validation at `0x369f18` and its result check occur before the handler selects and parses the saved `mSiteList` pair at `0x36a37c`. The pair is passed later to actor-context handling at `0x36a3ac`; it is absent from the earlier strategy call arguments. This rules out the newly selected pair feeding that validator call in the same handler activation. An earlier hidden selection stored elsewhere remains unproven.

## Evidence sources

Primary native source: ACNH 1.0.0 `main.elf`, SHA-256 `5bf707c3dc5dac0ad9635af7d336ec580f81c3f7876d0f55400d1900e3415d74`. The JSON sidecar records hashes and exact paths for the generated enum, constructor/query/dispatch/error-action decompilations, handler registry, EventFlow source, and USen TalkSys messages. No Ghidra rebuild, BCSV crosswalk change, index edit, or repository push was performed.
