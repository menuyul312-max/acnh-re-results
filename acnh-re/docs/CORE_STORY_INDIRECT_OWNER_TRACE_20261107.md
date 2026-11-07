# ACNH 1.0.0 RE: indirect owner trace for first-live and StaffCredit

This follow-up resolves both function-pointer owners as far as the static binary permits. `0xc685a0` is a method in the `NpcActorMgr` function-pointer table: the class is registered by `_INIT_2810`, its factory is `0xc67fa0`, and its constructor installs the table containing `0xc685a0`. That method directly calls `0xc70da0`, whose pseudocode references `E_FirstLive_NPC_0` and `AI_NPC_Tkk_FirstLive`. `0x146f2c0` is read by a state-registration routine and passed under the key `State::cPlay`; it then calls a generic helper that references `StaffCredit`.

The two dispatch structures are now attributed, but neither supplies the missing story-time caller. The EventFlow request for `cMainFieldFirstLive` is proven, as are the native method and actor-builder path. The stage projection does not contain a `NpcActorMgr` actor row, and the indexed EventFlow graph has no caller for `SNPC_tkk_Live:Tkk_LandFirstLive` or `AI_NPC_Tkk_FirstLive`. The `State::cPlay`/`StaffCredit` path has no indexed EventFlow bridge from the K.K. first-live sequence. Those joins remain **OPEN**.

## Relocation correction and exact rows

The earlier follow-up described `0x2479bf0` and `0x25a3fe8` as static pointer slots. They are instead the `r_addend` fields inside `.rela.dyn` records. The relocated pointer storage locations are the records' `r_offset` values, shown below. `r_info=0x403` encodes `R_AARCH64_RELATIVE` (type 1027, symbol 0). Bytes are raw little-endian `.rela.dyn` row bytes from `A_logic/main.elf`.

| `.rela.dyn` row VA / file offset | `r_offset` (relocated pointer location) | `r_addend` (pointer value) | Exact row bytes |
|---|---:|---:|---|
| `0x2479be0` / `0x2479ec8` | `0x30d9a88` | `0xc685a0` | `889a0d03000000000304000000000000a085c60000000000` |
| `0x2479988` / `0x2479c70` | `0x32f9148` | `0x30d9a40` | `48912f03000000000304000000000000409a0d0300000000` |
| `0x2479aa8` / `0x2479d90` | `0x32f91a8` | `0xc67fa0` | `a8912f03000000000304000000000000a07fc60000000000` |
| `0x25a3f60` / `0x25a4248` | `0x330daf8` | `0x3135370` | `f8da30030000000003040000000000007053130300000000` |
| `0x25a3f78` / `0x25a4260` | `0x330db00` | `0x3135580` | `00db30030000000003040000000000008055130300000000` |
| `0x25a3fd8` / `0x25a42c0` | `0x330db20` | `0x146f2c0` | `20db3003000000000304000000000000c0f2460100000000` |

## `NpcActorMgr` and `0xc685a0`

The `_INIT_2810` initializer at `0xc71bf0` loads the factory pointer from `0x32f91a8`, supplies the allocation size `0x10780`, and calls registration helper `0x61ab0` at `0xc7236c` (`d1bdcf97`, `BL #0x61ab0`). Its arguments include the two strings at `0x29ab7c6` (`"NpcActorMgr"`) and `0x29b9e0d` (`NpcActorMgr`). The helper at `0x61ab0` stores the factory and size in the class registration record and links that record into its registry. This is static registration evidence, not an initializer execution trace.

The registered factory `0xc67fa0` allocates `0x10780` bytes and calls constructor `0xc67ff0` at `0xc67fd0` (`08000094`, `BL #0xc67ff0`). The constructor installs a function-pointer table on the object: at `0xc68020` it forms the page for `0x32f9000` (`883401b0`), at `0xc68024` loads `[x8,#0x148]` (`08a540f9`, relocated value `0x30d9a40`), adds `0x10` at `0xc68028` (`08410091`), and stores the result as the object's first pointer at `0xc68030` (`880200f9`). The resulting table base is `0x30d9a50`.

The relocated sequence at `0x30d9a50` contains `0xc685a0` at pointer slot `0x30d9a88`, offset `+0x38` from the installed base. This gives a concrete owner path from the registered `NpcActorMgr` object to the method. `0xc685a0` directly calls `0xc70da0` at `0xc686ac` (`bd210094`, `BL #0xc70da0`). The `0xc70da0` decompilation references the actor name `E_FirstLive_NPC_0` and behavior path `%s/AIC:Special/AIF:AI_NPC_Tkk_FirstLive`; its pseudocode also submits the built actor through the native actor path. Static code establishes the manager method → first-live actor builder link.

## `State::cPlay` and `0x146f2c0`

The neighboring object constructor `0x146e010` loads the pointer at `0x330daf8` (`0x3135370`), adds `0x10`, and stores `0x3135380` as the object table at `0x146e038`. That table contains `0x146f040` at `0x3135558` (`+0x1d8`). The table owner is a constructed native object, but this scan did not recover a semantic class name or a direct caller for `0x146f040`.

Inside `0x146f040`, the callback-table read is explicit: `0x146f144`/`0x146f14c` load the function pointer at `0x330db20` (`e9f400d0`, `adrp x9,#0x330d000`; `299145f9`, `ldr x9,[x9,#0xb20]`), yielding `0x146f2c0`. The adjacent slot `0x330db28` loads `0x146f380` at `0x146f150`/`0x146f154` (`eaf400d0`; `4a9545f9`). The routine constructs the string `State::cPlay` at `0x29570e1` (`0x146f168`/`0x146f16c`: `49a70090`; `29850391`), sets the state argument to `3` at `0x146f170` (`e1070032`), then calls helper `0x1f064b0` at `0x146f17c` (`cd5c2a94`). Thus the table entry is registered through the `State::cPlay` state setup. This is a static callback-registration path; the generic helper's recovered name is not a story-state label.

The target `0x146f2c0` calls `0x1470e90` at `0x146f34c` (`d1060094`, `BL #0x1470e90`). The helper references the string `StaffCredit` at `0x298a2f5` in its case-8 path and passes it through generic helper operations. A neighboring function, `0x146ee10`, references `StaffCreditPage` at `0x292ff31`; no direct call joins it to `0x146f2c0`. The containing object type and the story trigger for entering the `StaffCredit` case remain unresolved.

## Story bridge and OPEN joins

The indexed EventFlow action `Demo_PublicAnnouncement:PAnnounceSza`, event 41 (source ID 279), requests `SystemRequestChangeStage(TargetStage="cMainFieldFirstLive")`. Its stage resource is source ID 2909, `B_data/Stage/Game/MainFieldDemoFirstLive.byml`. The generated stage projection contains nine actor records and no `NpcActorMgr` row. Separately, the native actor-type registry has a registered `NpcActorMgr` entry at index 5. A global native actor-manager registration is therefore proven; a stage-resource instantiation edge is not.

The flow index identifies `SNPC_tkk_Live:Tkk_LandFirstLive` (source ID 625) and `AI_NPC_Tkk_FirstLive:Root` (source ID 272), but both flowcharts have empty `called_from` lists. The K.K. live flow contains local transitions from `Tkk_LandFirstLive` to `Tkk_LiveDemo` and `Tkk_LiveAfter_Flag`, then requests a return to `cMainFieldPlayerHouse`; it does not show that the first-live actor builder dispatches that entry. The flow index includes 456 EventFlows and has no `StaffCredit`, `StaffRoll`, or `cStaffRoll` token in its indexed data. Its metadata excludes message text, so that search only constrains indexed flow/action structure.

| Join | Status | Boundary |
|---|---|---|
| `_INIT_2810` → registered `NpcActorMgr` factory → constructor-installed table → `0xc685a0` → `0xc70da0` | **STATIC_CONFIRMED** | Exact registration, relocation, vptr write, table slot, and direct `BL` are in the main ELF. Runtime execution was not performed. |
| `Demo_PublicAnnouncement:PAnnounceSza[41]` → `cMainFieldFirstLive` | **FLOW_CONFIRMED** | Explicit source-ID 279 action. |
| Stage load → `NpcActorMgr` instantiation / method dispatch | **OPEN** | Stage projection has no `NpcActorMgr` actor row; no native or EventFlow caller in the indexed joins identifies the runtime stage dispatch. |
| `0xc70da0` / `AI_NPC_Tkk_FirstLive` → `SNPC_tkk_Live:Tkk_LandFirstLive` | **OPEN** | Actor behavior name is static evidence; EventFlow `called_from` is empty and no stage-to-entry bridge is indexed. |
| K.K. first-live / credits flow → `State::cPlay` callback → `StaffCredit` | **OPEN** | Callback-table owner/setup is attributed, but there is no indexed EventFlow trigger or native caller tying the state to this story sequence. |

This is static RE evidence only; native routines were disassembled/decompiled but not executed. No model, audio, or rendered cutscene evidence was used, so audiovisual behavior is unverified. The EventFlow index omits dialogue text.

## Evidence sources and hashes

Hashes are SHA-256. Generated analysis artifacts are under `/workspace/acnh-re`, mirrored in the delivery checkout at `../../../acnh-re`. The source ELF path is resolved from `output/manifest.json`'s `source_root` (`/workspace/downloads/ACNH_island_RE/ACNH_island_RE`); the raw NSO is in the analysis checkout.

| Source | SHA-256 |
|---|---|
| `inputs/additional_exefs/main` (NSO input) | `f8d248109ff72999b4600ae3749f8c7397fb960f7ad3ab8dee3018ae9e14e900` |
| `A_logic/main.elf` / `output/binary/elf.json` main ELF digest | `5bf707c3dc5dac0ad9635af7d336ec580f81c3f7876d0f55400d1900e3415d74` |
| `output/manifest.json` (source-root mapping) | `eb8d114129e01e6c3284a7a2613c3f451d649c0708a58a1a08cd757c5f3840a8` |
| `output/index.sqlite` | `a78c7af27d37b8fd931bba8bc611623dacf7685cb6e8b4f827effa0765340aad` |
| `output/binary/code_pointer_arrays.json` | `64d474068ca289f9146f7f32e6647a16a05e8f5be8e635615a478744b62ef822` |
| `output/binary/analysis_decomp/c71bf0.c` | `df0143f8def558ee26a80fdba2ec7f81be9787bb62833f43d0502ec00687272a` |
| `output/binary/analysis_decomp/61ab0.c` | `b17784caa07cb61a87c2dc004a1ea3c217bf572a7edc533a109fb3d82179f9ae` |
| `output/binary/analysis_decomp/c67ff0.c` | `14c396b819c682273f129d53aeaa09f12fc40f5412ab1230a0187f82a106b6ef` |
| `output/binary/analysis_decomp/c70da0.c` | `b2253dd8192f615ce55cb57d7ff4de45a22ae14d4186edf61a4e57bb8f0b5588` |
| `output/binary/analysis_decomp/1470e90.c` | `c37c9542db23aa8d74105a101da693608282c529acbee2c33ab4bc50da873425` |
| `output/binary/analysis_decomp/146ee10.c` | `6daa5f72fbd20df37941db811b316e9ff7046f58878a244903591b7e6fa3c3b6` |
| `output/binary/analysis_decomp/1f064b0.c` | `64acfe2527e8e11d1201a313cdf1c65ebcd87413a2a992146d54eb767c8a9a75` |
| `output/gameplay/flow_index.json` | `359f3a21a17a116902b0c8e1110c3892814b6fccbeb50b71d573c8ab3e1c68c5` |
| `output/stage/by_source/02909.json` | `2b003d9744649e7668585ff93df4dd17d0844e92ce86e5a06f7b094f1428bd28` |
| `output/stage/actor_type_registry.json` | `67439173a460ad49bb6cbc0086047eb192581f0cad36f4c936c4078a39d959be` |
| Raw source ID 279 `Demo_PublicAnnouncement.bfevfl` | `7ec0d30107a1d40169b4455932f0f6853beb9ef7b7cf69ca2ee2f77958a12602` |
| Raw source ID 272 `AI_NPC_Tkk_FirstLive.bfevfl` | `5f7c36dba971c8c30f434b92085a8bb7e8bd677df39bcd008d0aa8950e02a9f8` |
| Raw source ID 625 `SNPC_tkk_Live.bfevfl` | `d1a9d0253d4ae6c1ed46e87d007f8924f4cba637589a3d0750ca07295794d316` |
| Raw source ID 2909 `MainFieldDemoFirstLive.byml` | `0cf0898403df0b2eb8a47fae804a373ca6a7dcc8eb9680aac64360847b16bd12` |

The machine-readable graph and exact relocation/instruction records are in [`core_story_indirect_owner_trace_20261107.json`](../output/gameplay/core_story_indirect_owner_trace_20261107.json).
