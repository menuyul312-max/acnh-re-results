# Building placement validator chain — ACNH 1.0.0

**Scope:** static AArch64 callsite tracing from `EventFlowQueryCanBuildHere` and `EventFlowActionBuildStructure` into the native structure-type strategy manager, then through the selected site-coordinate parser and actor-context handoff. This pass did not rebuild Ghidra, run the game, edit indexes/crosswalks, or search the `NpcActor+0x68` component writer.

## Result

The query and build action candidates both call the same raw ELF wrapper at `0x10dfea0`, which dispatches through a structure-type-indexed manager. The manager has five concrete strategy handlers installed at indices 1–5. Each handler exposes a setup method at vtable slot `+0x20` and a result/query method at `+0x28`; the dispatcher invokes both. The strategy methods write status bits, so this is a direct placement-query chain rather than only a name-based candidate.

One strategy contains an explicit eight-iteration cell loop. It derives a rotated X/Z position for every cell and routes each through shared regional checks. That is direct footprint-like geometry evidence for strategy index 5. Another strategy converts X/Z to the five-unit field grid and probes directional/neighbor cells. These establish grid and multi-cell checks, while the precise structure labels, water/terrain rule meanings, and status-to-message mapping remain unresolved.

The `BuildStructure` action runs the strategy query before it parses its selected saved site-list record. The record parser later converts the adjusted integer pair to X/Z using `10*n + 5`, leaves Y unchanged, then passes the vector into an actor-context handler. The current trace does **not** prove that the selected saved pair itself is an input to the earlier strategy validation. The pose descriptor and saved site pair remain two separate data paths until a further join is established.

## Proven dispatch chain

The `BindInfo` registry maps `EventFlowQueryCanBuildHere` to registered handler candidate `0x408cd0` and `EventFlowActionBuildStructure` to candidate `0x369d50`. The EventFlow uses `StructureType`, `StructureBuildPosType`, and `StructureBuildTiming`; `Player_HousingKit` contains query uses for `cBridge`, `cPlayerHouse`, `cReserveNpcHouse`, `cMuseum`, `cMarket`, `cNormalNpcHouse`, `cTailor`, `cSlope`, and `cCampSite`. `System_Structure_Common` calls the preview/build action handlers. Registry evidence identifies these as static handler candidates; runtime execution was not tested.

At raw ELF PCs, the query candidate calls the shared pose builder at `0x408e5c` and the strategy wrapper at `0x408e84`. The build action calls the pose builder at `0x369ef0` and the same wrapper at `0x369f18`. The wrapper tail-branches from `0x10dfebc` to manager dispatcher `0x10d85a0`. That dispatcher loads a handler from its table using descriptor type at `+8`, calls the object's `vtable+0x20` method at `0x10d8604`, then tail-calls `vtable+0x28` at `0x10d8628` with the result object and descriptor.

The manager constructor at `0x10d8360` installs five child handlers. Their relocated vtable address points and exact slot targets are:

| Strategy index | Manager offset | `+0x20` setup | `+0x28` result/query |
|---:|---:|---:|---:|
| 1 | `+0x10` | `0x10e3790` | `0x10e38d0` |
| 2 | `+0x18` | `0x10e2200` | `0x10e2490` |
| 3 | `+0x20` | `0x10de640` | `0x10de670` |
| 4 | `+0x28` | `0x10da7c0` | `0x10da7d0` |
| 5 | `+0x30` | `0x10e5100` | `0x10e5110` |

The numeric `StructureType` ordinal is mapped into these strategy indices by `0x376eb0`: cases `0→1`, `1→2`, `2→3`, `3→3`, and `4→2`; cases 5 and 6 can route to indices 4 and 5 after successful secondary lookups, while their fallback is index 3; cases 7 and 8 route to index 3. The ordinal-to-label join is not recovered, so the EventFlow names must not yet be assigned to particular strategy rows. The constructor initializes indices 1–5; it does not construct entries 0 or 6. A null selected entry produces status `0x15` in the dispatcher.

The result object is a bit mask. `0x10e4eb0` clears it; `0x10e4ef0` records one of up to 22 status bits. `0x408cd0` returns whether the result field at `+8` is nonzero. I leave the user-facing truth polarity and each bit's message meaning open rather than inferring them from the query name.

## Geometry and validation evidence

Strategies 1–3 call the same family of regional helpers. Representative raw calls from strategy 3 are `0x10de7f0 → 0x10e0db0`, `0x10de85c → 0x10e0620`, `0x10de8b4 → 0x10e0b00`, `0x10de908 → 0x10e0fb0`, and `0x10de984 → 0x10e1120`; the other two strategies contain corresponding calls. Their code iterates query ranges, applies field/object predicates, selects category bits, and returns numeric statuses. `0x10e0fb0` is a plausible spatial/overlap candidate because it iterates query objects and invokes geometry/object predicates, but its specific collision semantics are not named or proven.

Strategy 4 (`0x10da7d0`) calls `0x52b280` to quantize X/Z into the five-unit grid, then queries a field/grid object and branches on predicates including `0x187180` and `0x187f00`. It also performs directional and neighbor-cell probing. This proves grid-state and adjacency checks, not a fully identified terrain, cliff, or water rule.

Strategy 5's result method calls `0x10e52f0` at `0x10e5184`. That routine initializes a cell index to zero, calls `0x10e5940` at `0x10e5334`, increments the index, and stops after index 7. `0x10e5940` uses the selected cell offset and structure orientation to update X/Z coordinates, then prepares a field-query record. The loop routes each of its eight cells through shared checks such as `0x10e0db0`, `0x10e0620`, `0x10e0b00`, and `0x10e0fb0`. The loop and coordinate math are direct evidence; “footprint-like” describes the observed shape of the algorithm, not a resolved game class or dimension table.

## Saved site coordinates and actor boundary

In `BuildStructure`, the strategy call at `0x369f18` precedes selected site-record parsing at `0x36a37c`. The parser `0x4e1670` calls `0x568360` at `0x4e1758`; the helper writes the adjusted signed X/Z pair as `10*n+5`, preserving the caller's Y lane. `BuildStructure` passes the vector to `0xbe6480` at `0x36a3ac`. That helper has conditional field-grid branches and a common component handoff, but those branches do not establish a complete footprint validator or the final structure transform.

The registered `StructureStartPreviewGuide` handler candidate calls `0x490f0` at `0x344818`; this helper builds a generic actor request and reaches actor-manager routines. Treat that as a preview-actor creation candidate only: this pass did not resolve its class/resource, model, animation, collider, or final spawn destination. `PreviewStructure` routes through the strategy manager and copies pose/metadata to actor-context state at `+0x288`. No static PBC/collider constructor was found on the checked path, and the final building instantiation and persistence edge remain open.

The BCSV schemas inspected were `StructureInfoParam` (29 rows), `StructureFacilityModel` (19), `StructureBridgeParam` (54), `StructureSlopeParam` (9), and `StructureHouseShapeParam` (15). Their resolved fields cover IDs, model names, floor height, house parts, bridge patterns, slope names, materials, doors, lighting and construction state. None has a resolved, explicitly named footprint-dimension field. Several fields remain unresolved, and these tables are not an exhaustive search of every placement input, so this is a bounded schema finding rather than proof that no dimensions exist elsewhere.

## Still open

- Bind each of the nine `StructureType` strings to its numeric ordinal and strategy index.
- Decode shared helper predicates and status bits into concrete water, cliff/ground, occupancy, overlap, and clearance rules.
- Prove whether the selected `BuildingSiteIndex` pair is validated by these strategy methods or only consumed by the later actor-context path.
- Recover footprint shape, rotation and per-class dimensions for every strategy; only the eight-cell path is established here.
- Join preview/build flow to the concrete actor factory, model/animation and PBC/collider assets, final transform and saved instance.
- Verify behavior dynamically; this report uses static binary, EventFlow and BCSV evidence only.

## Reproducibility

Raw addresses in this report are ELF VAs. The input `main.elf` SHA-256 is `5bf707c3dc5dac0ad9635af7d336ec580f81c3f7876d0f55400d1900e3415d74`. The companion [JSON ledger](../output/gameplay/building_placement_validator_chain_followup_20261107.json) records raw call PCs and encodings, per-function code hashes, relocated vtable targets, BCSV/EventFlow hashes, and bounded open edges. A depth-three direct-`BL` scan across the four EventFlow bodies and all ten strategy entry methods covered 1,029 known function bodies and found no indexed `pbc`, collider/collision, `StructurePreview`/`StructureActor`, `ModelName`, `.bfres`, or `.sarc` strings. Indirect calls and resource-table dispatch remain outside that negative result.
