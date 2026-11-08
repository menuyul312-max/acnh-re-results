# Building site-pair to BCSV row binding follow-up — ACNH 1.0.0

**Scope:** Static trace of the six-entry mSiteList consumer, StructureType-to-strategy dispatch, placement-validator inputs, and candidate joins to StructureInfoParam / StructureFacilityModel and HousingKit story calls. This pass reads the existing SQLite index and prior placement reports. It does not run the game, modify indexes, inspect model/PBC payloads, change Godot, or reproduce the 19 ModelName catalogue.

## Finding

The native path proves two separate joins:

- BuildStructure selects an available index from a six-entry structure list, writes that index to the actor blackboard key BuildingSiteIndex, parses the selected pair, then passes the adjusted coordinates to actor-context handling.
- The StructureType enum ordinal enters a type-indexed strategy dispatcher. The EventFlow labels and their strategy routes are statically recoverable.

The two paths do not meet at the validator call in the same BuildStructure activation. BuildStructure dispatches validation at raw ELF PC 0x369f18, checks its result, and only afterward selects a site index and parses its pair at PC 0x36a37c. The newly selected pair is therefore absent from that validator invocation's arguments. No direct key joins the six mSiteList indices or pairs to a StructureType, a StructureInfoParam UID, or a StructureFacilityModel row.

The table-to-table foreign-key join is proven: all 19 StructureFacilityModel rows join to StructureInfoParam through StructureInfoUniqueID → UniqueID. That resolves the facility table family, but does not assign any of those rows to a site-list index or a StructureType label. The complete 19-key model catalogue remains in the prior preview asset report.

## Native chain and exact callsites

The SQLite index and the existing decompilation agree on the relevant EventFlow and native calls. Raw addresses below are ELF VAs; Ghidra pseudocode display labels carry a +0x100000 bias.

| Edge | Raw PC | Target | What the call establishes |
|---|---:|---:|---|
| EventFlowQueryCanBuildHere | 0x408e5c | 0x3771d0 | Builds the pose/type descriptor from the action/query parameters. |
| EventFlowQueryCanBuildHere | 0x408e84 | 0x10dfea0 | Sends the descriptor to the structure strategy dispatcher. |
| BuildStructure | 0x369ef0 | 0x3771d0 | Builds the descriptor from its StructureType, position-type, and timing parameters. |
| BuildStructure | 0x369f18 | 0x10dfea0 | Runs strategy validation before entering the site-list selection path. |
| Strategy descriptor | 0x37721c | 0x376eb0 | Passes the parsed StructureType ordinal into the strategy-index switch; the result is stored at descriptor +8. |
| Dispatcher wrapper | 0x10dfebc | 0x10d85a0 | Tail-branches to the world structure-query manager. |
| Strategy manager | 0x10d8604 / 0x10d8628 | vtable +0x20 / +0x28 | Calls the selected strategy setup and result methods. |
| BuildStructure selector | 0x36a14c–0x36a19c | 0x4e1d80 | Checks site-list indices 0 through 5 and builds an availability set. |
| BuildStructure selector | 0x36a33c | 0x166ab70 | Selects an available set-bit index. The caller passes actor +0x288 as the rank input; the decompilation uses its low 32 bits. |
| BuildStructure blackboard write | 0x36a36c | 0xc756a0 | Writes the selected index (0..5) under BuildingSiteIndex. |
| BuildStructure pair parse | 0x36a37c | 0x4e1670 | Parses the selected list entry into a pair. This is after validation and selection. |
| Pair parser conversion | 0x4e1758 | 0x568360 | Converts adjusted pair components to X/Z lanes using 10*n+5; leaves the caller's Y lane unchanged. |
| BuildStructure actor handoff | 0x36a3ac | 0xbe6480 | Passes the parsed pair and a separate scalar to actor-context handling. |

The ordered pseudocode path is explicit: BuildStructure calls 0x3771d0 and then 0x10dfea0; its validation-result check gates the later six-slot loop. The selector and pair parser occur after that check. Thus the parser's output cannot be an argument to that earlier call in this handler activation. A previously selected pair held in actor or global state, a separate validator invocation, and indirect consumers remain outside this local result.

The six cells in StructurePresetA00.mSiteList are (61,66), (78,77), (49,79), (88,80), (97,84), and (69,90). The loader chain associates a six-child descriptor with mSiteList: 0x55dfd0 names the descriptor, 0x4e1db0 enumerates six children, and 0x5651b0 passes member +0x3a50 to that loader from a ValidateVillageSave-associated path. BuildStructure reads a structure-like object with the same +0x3a50 / +0x3a58 / +0x3a60 layout. The source asset and native object share count and layout, while the exact runtime preset instance remains open.

## StructureType and strategy routing

The enum at ELF VA 0x2969f28 supplies the list-position ordinals. The type-to-strategy route is established by 0x3771d0 passing the ordinal to 0x376eb0 and that switch storing the selected strategy index in the descriptor.

| Ordinal | EventFlow StructureType | Native strategy route |
|---:|---|---|
| 0 | cPlayerHouse | 1 |
| 1 | cNormalNpcHouse | 2 |
| 2 | cMuseum | 3, subtype 2 |
| 3 | cMarket | 3, subtype 0 |
| 4 | cReserveNpcHouse | 2 |
| 5 | cBridge | 4 when its secondary lookup succeeds; otherwise the switch can fall through the case-6 path to strategy 5 or strategy 3 / subtype 2 |
| 6 | cSlope | 5 when its secondary lookup succeeds; otherwise strategy 3 / subtype 2 |
| 7 | cTailor | 3, subtype 5 |
| 8 | cCampSite | 3, subtype 6 |

The strategy manager has installed handlers at indices 1–5. Strategy 4 probes the five-unit X/Z grid and neighboring cells; strategy 5 has an eight-cell coordinate loop. Those are algorithm properties of the selected strategy entries. They do not supply a BCSV row key. The secondary lookups on ordinal cases 5 and 6 use native helper paths whose concrete BCSV descriptor has not been identified, so they are not promoted to StructureBridgeParam / StructureSlopeParam joins.

## BCSV and story joins tested

The relevant resolved BCSV schemas were checked by field name, row values, and join key:

| Source | Rows | Keys/categories observed | Result for this trace |
|---|---:|---|---|
| StructureInfoParam | 29 | UniqueID; categories House, Facility, Bridge, Slope | Contains no StructureType, site index, or site-pair field. UIDs 0–18 are House, 19–25 and 29 are Facility, 26 is Bridge, and 27 is Slope. |
| StructureFacilityModel | 19 | StructureInfoUniqueID → StructureInfoParam.UniqueID | Exact table join succeeds for all 19 rows; referenced UIDs are 19–25 and 29. It has no StructureType or site-index field. |
| StructureBridgeParam | 54 | BridgeTypeUniqueID, UniqueID | Separate bridge identifiers; no site index or StructureType key. |
| StructureSlopeParam | 9 | UniqueID values 0–5 and 29–31 | Separate slope identifiers; no site index or StructureType key. |

The table categories are broader than the nine-value StructureType enum. Category similarity such as cBridge / Bridge does not create a native key join. Ordinal equality is also not a general mapping: enum ordinal 2 is cMuseum while StructureInfoParam UID 2 is a House row; ordinal 3 is cMarket while UID 3 is also a House row. BCSV UID 26 / 27 identifies the Bridge / Slope categories, but no call or data field connects enum ordinals 5 / 6 or selected site indices to those UIDs.

EventFlow source gives the story-facing type labels. Player_HousingKit has type-specific CanBuildHere queries and preview-guide actions, including three cReserveNpcHouse / cSettlerQuest cases. Its BuildStructure subflow call forwards StructureType, StructurePosType, and BuildTiming as arguments to System_Structure_Common. That common flow forwards those arguments to its three BuildStructure action sites. This proves the story selector → StructureType argument path and its native strategy route. The common flow carries no mSiteList index or StructureInfoParam UID, so it does not assign a story structure to one of the six pairs.

The exact selected index is available to a blackboard consumer as BuildingSiteIndex. The indexed prologue flows initialize the key to -1, query it with Border 0, and reset it to -1; they do not name a site index, pair, or StructureInfoParam row. The current evidence therefore binds the key and the selected numeric index, but not a story-building identity.

## Tested joins and bounded negatives

- **Proven:** StructureType string → enum ordinal → strategy route.
- **Proven:** six-entry native availability set → selected index → BuildingSiteIndex blackboard write.
- **Proven:** selected list index → selected BYML pair → adjusted X/Z pair → actor-context handoff.
- **Proven:** StructureFacilityModel.StructureInfoUniqueID → StructureInfoParam.UniqueID for all 19 model rows.
- **Open:** mSiteList index/pair → StructureType or story building.
- **Open:** StructureType ordinal/label → exact StructureInfoParam / StructureFacilityModel / BridgeParam / SlopeParam row.
- **Open:** selected pair → the validator invocation earlier in BuildStructure; the parser runs later and no pair argument reaches that earlier dispatcher call.
- **Open:** exact runtime list instance, row selection, final transform, preview/final actor resource, collider/PBC binding, and durable structure save.

The SQLite direct-call index contains the listed call PCs and targets, but several EventFlow candidate-body rows have owner_va=0. Caller ownership is therefore checked against the registered handler mapping and the hashed pseudocode snapshots, not inferred from that column. The call-order negative is local to the inspected BuildStructure body and does not rule out indirect dispatch or other validator calls elsewhere.

## Reproducibility

Primary binary: ACNH 1.0.0 main.elf SHA-256 5bf707c3dc5dac0ad9635af7d336ec580f81c3f7876d0f55400d1900e3415d74; input main NSO SHA-256 f8d248109ff72999b4600ae3749f8c7397fb960f7ad3ab8dee3018ae9e14e900. Read-only analysis index output/index.sqlite SHA-256 a78c7af27d37b8fd931bba8bc611623dacf7685cb6e8b4f827effa0765340aad; resolved handler registry SHA-256 dfc298dfcb1b288b8fda9cd6a49c728fdad903b41f8fc1c9288df7d732ec92a5.

Key source hashes: StructurePresetA00.byml 2a0be5f7a0904fe09c5ead536802749696e317bf1261d22327811aafb036436e; Player_HousingKit.bfevfl 6b7e56629772c85053c44b399d9e1a9bdf1d8f147cceb8bb499cc8c8918a0383; System_Structure_Common.bfevfl e64c08ddc898616e354c6951ae891597726d78c4ca2c61e4257264d837033c12; StructureInfoParam.bcsv a16b03ec38869a015faa5dbaddde03ea3865db88c91ea40d32d9c7e2fa6904ef; StructureFacilityModel.bcsv b29acfe910d54b39b90d2f5f6c04b092ef037706cd9e929656f6104aa8adae9d.

The companion JSON ledger contains hashes for the native decompilation snapshots, BCSV resolved views, source flows, and index. JSON syntax and repository diff checks passed. No game, save, or Godot execution was performed.
