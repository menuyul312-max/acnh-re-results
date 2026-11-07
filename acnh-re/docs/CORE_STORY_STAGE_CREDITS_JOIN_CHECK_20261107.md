# Remaining first-live stage and credits joins

Audit date: 7 November 2026. This is a narrow follow-up on the open `cMainFieldFirstLive` → `Tkk_LandFirstLive` and first-live → credits edges. Source hashes are relative to the sibling RE dataset `/workspace/acnh-re`. Machine-readable evidence is in [`core_story_stage_credits_join_check_20261107.json`](../output/gameplay/core_story_stage_credits_join_check_20261107.json).

The native index adds one useful link: function `0xc685a0` directly calls the first-live actor builder `0xc70da0` at `0xc686ac` (`BL`, bytes `bd210094`). The direct-call row has `owner_va=NULL`; the supplemental native span inventory places the PC inside `FUN_00d685a0`, start `0xc685a0`, size `0x248`. Inside the builder's positive type-predicate branch, it constructs an actor named `E_FirstLive_NPC_0`, assigns the AI resource `AI_NPC_Tkk_FirstLive`, and submits the actor through `0xc6c210`. This confirms a native dynamic actor-construction route. It still does not prove that `Demo_PublicAnnouncement`'s `cMainFieldFirstLive` request reaches `0xc685a0`, or that the AI talk path invokes `SNPC_tkk_Live:Tkk_LandFirstLive`.

The stage candidate `B_data/Stage/Game/MainFieldDemoFirstLive.byml` (source ID 2909) contains nine generic stage actors; its decoded actor list has no named `E_FirstLive_NPC_0` row. It contains `ActorEventStartDemo` and one unresolved actor-kind hash. The native actor builder is therefore consistent with dynamic insertion, but there is no indexed map from EventFlow stage string `cMainFieldFirstLive` to that BYML resource or to the builder's caller. Also, `SNPC_tkk_Live`, `AI_NPC_Tkk_FirstLive`, and `AI_NPC_Rco_FirstLiveInvite` still have empty EventFlow `called_from` lists; the K.K. AI only calls `AI_NPC_Common:ContinueSpeak`.

There is also a native name-key registration that is relevant to the Nook visit. Static initializer `_INIT_2865` at `0xcec550` stores `TkkFirstLiveInviteRco` (string VA `0x2925c66`) in its `NNPC_Talk_Sequence` record and calls generic name-hash routine `0x1bf0` at `0xcec970`. That is registration of a name/hash, not a resolved pointer to `AI_NPC_Rco_FirstLiveInvite` or `SNPC_rco_55_TkkFirstLive:InvitePlayerHouse`. The AI flow remains a generic `VisitSpeak` call, and the Nook EventFlow entry has no indexed direct caller.

For credits, the static index does contain a direct generic caller: code at `0x146f34c` in native function `0x146f2c0` calls `0x1470e90` (`StaffCredit` string-ref site; `BL`, bytes `d1060094`). The callee's switch has case 8 that passes the generic name `StaffCredit` to the asset/layout helper. The function-pointer sequence inventory also contains `0x146f2c0` at slot `0x330db20`, in a sequence starting at `0x330db08`; the sequence has no resolved owner or dispatch meaning. The native function inventory has no direct `BL` caller for `0x146f2c0`, and the flow index has no `StaffCredit` or `StaffList` event. The extracted ROMFS paths prove that the layout and staff-list assets exist; they do not prove that the first-live stage invokes the loader or starts credits.

| Edge | Result |
|---|---|
| EventFlow request → stage asset | **OPEN_JOIN**: exact request `cMainFieldFirstLive` (flow 279, #41) and candidate `MainFieldDemoFirstLive.byml` (source 2909) are present, but no name-to-resource mapping is indexed. |
| Native stage helper → dynamic K.K. actor | **PARTLY CONFIRMED**: `0xc685a0` call at `0xc686ac` reaches `0xc70da0`; that builder creates `E_FirstLive_NPC_0` with `AI_NPC_Tkk_FirstLive` under its positive predicate branch. A static function-pointer sequence contains `0xc685a0` at slot `0x30d9a88`, but no incoming direct call or resolved dispatch record into `0xc685a0` is identified. |
| Dynamic AI actor → `Tkk_LandFirstLive` | **OPEN_JOIN**: AI flow and talk EventFlow both exist, but there is no direct caller/entry mapping. |
| Credits loader → post-concert credits | **OPEN_JOIN**: `0x146f2c0` → `0x1470e90` generic native call and asset paths exist; a pointer sequence contains `0x146f2c0` at `0x330db20`, but its owner/dispatch semantics are unresolved. No incoming direct `BL` caller to `0x146f2c0`, EventFlow credit action, or first-live link is indexed. |
| Nook visit key → `InvitePlayerHouse` | **OPEN_JOIN**: `TkkFirstLiveInviteRco` is registered as a name/hash; the registration does not resolve to the Nook AI or talk EventFlow. |

The native caller index is a static direct-call scan. For the call into `0xc70da0`, `direct_calls` records PC `0xc686ac` with a null `owner_va`; the supplemental `native_functions` span inventory places that PC inside `FUN_00d685a0` (`0xc685a0`, size `0x248`). The function-pointer sequence inventory contains `0xc685a0` at `0x30d9a88` in a sequence beginning at `0x30d9a50`; its owner/dispatch semantics are unresolved. The address also appears in a static data slot at VA `0x2479bf0`, likewise with no identified dispatcher/owner. Similarly, the `StaffCredit` call at `0x146f34c` is an unowned direct-call row whose PC lies within native function `0x146f2c0`; a function-pointer sequence contains it at `0x330db20` in a sequence beginning at `0x330db08`, but its owner/dispatch semantics are unresolved. The address also appears in a static data slot at `0x25a3fe8`. These findings establish the caller bodies locally while leaving the initiating stage/credit events open. The direct-call index covers direct branch instructions; it does not identify indirect function-pointer dispatch.

No model, audio, raw movie, or rendered scene was used. All native findings are static RE, not execution in a progressed save. No build or commit was performed.

## Source hashes

| Source | SHA-256 |
|---|---|
| ExeFS `main` | `f8d248109ff72999b4600ae3749f8c7397fb960f7ad3ab8dee3018ae9e14e900` |
| `output/index.sqlite` | `a78c7af27d37b8fd931bba8bc611623dacf7685cb6e8b4f827effa0765340aad` |
| `output/gameplay/flow_index.json` | `359f3a21a17a116902b0c8e1110c3892814b6fccbeb50b71d573c8ab3e1c68c5` |
| `output/stage/by_source/02909.json` | `2b003d9744649e7668585ff93df4dd17d0844e92ce86e5a06f7b094f1428bd28` |
| `output/stage/actor_type_registry.json` | `67439173a460ad49bb6cbc0086047eb192581f0cad36f4c936c4078a39d959be` |
| `output/stage/native_summary.json` | `396383658321f378b256acdfb80a20faac22b4f84a6faad45dd23db45b3ce4f7` |
| `output/binary/code_pointer_arrays.json` | `64d474068ca289f9146f7f32e6647a16a05e8f5be8e635615a478744b62ef822` |
| `output/binary/analysis_decomp/c70da0.c` | `b2253dd8192f615ce55cb57d7ff4de45a22ae14d4186edf61a4e57bb8f0b5588` |
| `output/binary/analysis_decomp/cec550.c` | `e63314596b25521adbfb5bf71dec074dcbcd37d19de67eadbefa9680f0147290` |
| `output/binary/analysis_decomp/1470e90.c` | `c37c9542db23aa8d74105a101da693608282c529acbee2c33ab4bc50da873425` |
| `output/additional_romfs/extracted_manifest.json` | `5e2327bc81c0a526cbcf878e9d899f47536b5b8f5a9fdf8b4a776413f75b64b8` |

First-live stage source ID 2909 is `B_data/Stage/Game/MainFieldDemoFirstLive.byml`, source SHA-256 `0cf0898403df0b2eb8a47fae804a373ca6a7dcc8eb9680aac64360847b16bd12`. The EventFlow source hashes and exact call/registration PCs are recorded in the JSON graph.
