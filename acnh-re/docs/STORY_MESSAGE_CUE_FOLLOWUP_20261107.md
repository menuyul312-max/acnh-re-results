# Story message and cue follow-up — ACNH 1.0.0 EventFlow baseline

This follow-up rechecks the story message joins and animation/audio/UI consumer edges from the earlier story actor proof. It corrects a stale status in the generated binding index and records the exact source joins in [the JSON ledger](../output/gameplay/story_message_cue_followup_20261107.json). Dialogue text is not copied into this report or ledger.

## Message labels resolve in the supplied supplemental archive

The earlier `eventflow_message_bindings.json` carries `resolution=message_archive_not_supplied` for the selected refs, but it also contains per-language member and text-index entries. That status is inherited from the initial EventFlow-only corpus index: `link_additional_romfs.py` adds locale lookups without replacing the earlier resolution string. Direct verification against every indexed message disproves the missing-archive result for these story flows.

I revalidated 460 EventFlow message events across 17 referenced EventFlow files (16 contain message refs), representing 425 unique qualified keys, in all 14 supplied locale directories. Every `(flow, event index, MessageID, locale)` pair points to an existing archive family, MSBT member, text index, and exact label. The same label/index also joins to exactly one BDLI label record in each locale. This is 6,440 exact MSBT checks and 6,440 exact BDLI label/index checks, with no missing key among the selected flows.

| EventFlow key example | EventFlow source | Supplemental archive member and label | Result |
|---|---|---|---|
| `Tutorials/Tutorials_Prologue2_Arrival:001` | `B_data/EventFlow/Tutorials_Prologue2_Arrival.bfevfl`, flowchart `Tutorials_Prologue2_Arrival`, event #0 (`EventFlowActionOpenMessageWindow`) | `Message/Tutorials_{locale}.sarc.zs` → `Tutorials_Prologue2_Arrival.msbt`, label `001` | Exact MSBT index and BDLI label/index match in all 14 locales |
| `Tutorials/Tutorials_Prologue4_Orientation3:045_02` | `B_data/EventFlow/Tutorials_Prologue5_Campfire.bfevfl`, flowchart `Tutorials_Prologue5_Campfire`, event #109 (`EventFlowActionOpenMessageWindow`) | `Message/Tutorials_{locale}.sarc.zs` → `Tutorials_Prologue4_Orientation3.msbt`, label `045_02` | Exact MSBT index and BDLI label/index match in all 14 locales |
| `TalkSNpc/tkk/SP_tkk_dream:001` | `B_data/EventFlow/Tutorials_Prologue_Tkk.bfevfl`, flowchart `Tutorials_Prologue_Tkk`, event #5 (`EventFlowActionOpenMessageWindow`) | `Message/TalkSNpc_{locale}.sarc.zs` → `tkk/SP_tkk_dream.msbt`, label `001` | Exact MSBT index and BDLI label/index match in all 14 locales |
| `TalkSNpc/owl/SP_owl_00_Common:104` | `B_data/EventFlow/SNPC_owl_01_Museum_Donation.bfevfl`, flowchart `SNPC_owl_01_Museum_Donation`, event #2 (`EventFlowActionOpenMessageWindow`) | `Message/TalkSNpc_{locale}.sarc.zs` → `owl/SP_owl_00_Common.msbt`, label `104` | Exact MSBT index and BDLI label/index match in all 14 locales |

The ledger records every key and EventFlow call site with BFEVFL source path, flowchart, event index/type, action name, and `MessageID`, MSBT `text_index`, source member hashes, and per-locale labels/text hashes. Some `MessageID` values are parameters on reaction/dialogue action nodes rather than standalone `MSG` nodes, so the direct BFEVFL event records are used for source citations. It omits message bodies. BDLI record offsets, counts, hashes, and CRC32 label candidates are included for traceability; their payload semantics are not inferred as page counts or layout behavior.

The EventFlow source exports are from the ACNH 1.0.0 baseline. Supplemental Message, BDLI, and ASB records are classified `STRUCT`: the members are present and parsed, but each is marked `new_path` in `extracted_manifest.json`, so exact game patch/build is not independently established. Locale identity is supported by the locale directory and `Message/{domain}_{locale}.sarc.zs` basename. The exact label joins are proven for the supplied archive, but their language text is not version-authenticated to 1.0.0.

## Animation command names join to parsed ASB nodes

Ten distinct `AsCommand` values used by the cited story trees match node names in `AnimationSequence/CharaCommon.root.asb`, including `NpcCheers`, `NpcSpRhythm`, `NpcSpTambourineSound`, `NpcSpDrinking`, `NpcSpTyping`, `NpcSpArrangeShort`, `TkkAGuitarPlayEnd`, and three Isabelle news commands. The JSON ledger gives the exact EventFlow tree, entry, event index and command value alongside ASB node index and first transition. This is a direct static command-name join; no native dispatcher or runtime animation playback was tested. Numeric `NpcRequestAction.ActionIdx` values still have no direct clip-name mapping in the cited sources.

The ASB archive member itself is an additional `new_path`, so its build version is unproven. The follow-up ledger carries the exact `rco`/`tkkA` stage-to-`SpNpcParam.ResName` joins from the earlier proof. Their model catalogue entries and generated paths remain CAT references. No raw `Model/` payload or runtime model load is claimed.

## Audio and UI consumer boundaries

Campfire EventFlow `Tutorials_Prologue5_Campfire` event #140 passes `MusicName=4318`. That numeric value joins `ItemParam` row index 1732 / UniqueID 4318 (`ResName=FtrMjkMainTheme`) and `SoundAudioMusic` row index 94 / UniqueID 103 (`RefItemUniqueID=4318`, `AudioMusicID=95`, label `Minnaatsumare`). This is an exact source-table consumer chain. The audio catalogue contains the name `BGM_Live_095_Minnaatsumare` as a CAT candidate, but it is a string-name match rather than an exact numeric consumer key. A scan of all 164 resolved BCSV JSON tables found no separate `AudioMusicID`-to-catalogue key table. The raw Sound/Resource archive is absent, so the waveform and exact runtime cue file remain unresolved.

The selected story flows contain 27 UI action nodes. None has a serialized BFLYT, Layout, ARC, SARC, or BRLYT resource key in its parameters. The parsed village-name keyboard, character-creation, and MenuDevice layouts remain source candidates; no action-to-page mapping is proven. This absence is checked in the exact UI nodes listed in the JSON rather than inferred from layout names.

The raw archive audit records zero catalogue audio source-path matches and marks generated catalogue paths as references only. The report does not upgrade model, audio, or UI catalogues to runtime-loaded assets. No Godot project or build was used.

## Conversion and verification

Decoded baseline BFEVFL event nodes were matched to the supplemental `eventflow_message_bindings.json`; each locale lookup was independently re-opened in `messages/{locale}/{domain}.json` and checked against the member, index, and exact label. BDLI `message_member`, CRC32 candidate, and text index were checked in `bdli/{locale}/{domain}.json`. Parsed ASB node names were compared by exact equality with story `AsCommand` values. Audio references were followed through the named BCSV columns. Source archive and member hashes are retained in the ledger.

Validation: JSON parsed successfully; all 6,440 selected locale-message pairs and all 6,440 BDLI label/index pairs passed; all selected keys have exact EventFlow call-site evidence. The remaining version, runtime dispatch, exact UI page, numeric animation-action, and raw audio/model limits are recorded explicitly.
