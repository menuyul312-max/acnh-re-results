# Terrain option-to-save/preset follow-up (ACNH 1.0.0)

This isolated follow-up closes the static relationship from the four registration terrain options to a candidate FieldMainFieldParam UniqueID and then to the SaveMainField fields written by the selected-entry consumer. It does not claim a fixed option-slot-to-preset table, a durable save commit, or an observed map load. No game/save was run or modified; no Godot work, commit, or push was performed.

## Result

**Proven:** the four option entries are generated dynamically from the field-parameter row set. Each entry carries a u16 candidate ID at entry+0x0c and an outside-template UniqueID at entry+0x0e. The UI result stores a slot index in the cVillage result field; the native consumer bounds-checks that slot, selects entry[slot], writes its +0x0c ID to SaveMainField.MainFieldParamUniqueID, and copies its +0x10 payload plus +0x0e value into SaveMainField.OutsideField.

The row-ID relationship has three native/data links: generation calls the ID-indexed row accessor 0x54e190; the same generator reads the row's OutsideTemplateKind with its known hash; and the native row iterator reads hash 0x54706054, which the decoded FieldMainFieldParam table identifies as UniqueID (u16). FieldData in that table supplies the existing filename-stem join to <FieldData>_LandMaking.byml.

**Not proven:** a stable mapping such as slot 0 to a particular UniqueID or preset. The four IDs are sampled dynamically, with a de-duplication mask. The writer/loader that populates the context ID range and pointer array is not identified in the available generated decompilation. Nor is the later native edge from this write to terrain generation/map loading or a durable save commit.

## Evidence labels and address convention

- **NATIVE** — raw AArch64 code/relocation or generated direct-call index for the supplied 1.0.0 main.
- **PSEUDO** — control/data-flow interpretation from generated decompilation, constrained by the native PCs listed.
- **TBL** — decoded table metadata or row-to-file data join.
- **STRUCT** — external save-schema crosswalk aligned to local save-layout offsets and sizes. It is cross-version corroboration, not local RTTI.
- **OPEN** — edge not established by this bounded static analysis.

PCs below are raw ELF VAs and offsets into segment file work/exefs_modules/main/0.bin. The hash-identified source build is listed in the companion JSON ledger. Generated FUN_006... pseudonames carry a +0x100000 display bias; cited PCs do not.

## Four-entry producer and row identity

**NATIVE — setup and four slots.** 0x5651b0 calls 0x529860 at PC 0x5651ec. When its status/feature guard passes, 0x529860 enters 0x529910 at PC 0x5298b4. The producer allocates an option pointer array and writes count 4 at PC 0x529964. It constructs slots 0–3. Their calls to 0x54e190 (ID-indexed row lookup) are at 0x5299f4, 0x529b04, 0x529c14, and 0x529d24; calls to 0x54e330 (OutsideTemplateKind column lookup) are at 0x5299fc, 0x529b0c, 0x529c1c, and 0x529d2c; calls to 0x552bb0 (outside-template selection) are at 0x529a0c, 0x529b1c, 0x529c2c, and 0x529d3c; per-entry builder calls to 0x528bf0 are at 0x529a80, 0x529b90, 0x529ca0, and 0x529db0. Entry stride is 0xe0.

**PSEUDO — candidate ID stored in each entry.** 0x529910 builds the helper arguments with the selected candidate u16, OutsideTemplateKind-derived u16, and slot ordinal. 0x528bf0 writes the candidate ID at entry+0x0c, outside-template value at +0x0e, and ordinal at +0xb8. The entry retains a +0x10 payload and a resource/object at +0xa0. Thus UI index i selects generated entry i; the ordinal is not itself the table UniqueID.

**NATIVE/TBL — the row lookup is a FieldMainFieldParam candidate.** 0x54e190 computes candidateID minus the u16 at context+0x1128, bounds-checks against the u32 at +0x1108, then loads an eight-byte pointer from the array at +0x1110. Separately, 0x54e930 walks IDs beginning at +0x1128 through the +0x112a terminal bound, resolves rows through that same range/array, and scans row hash 0x54706054. Decoded metadata for B_data/Bcsv/FieldMainFieldParam.bcsv identifies 0x54706054 as UniqueID/u16 at row offset 4, 0x6e1ac981 as FieldData/string32 at offset 6, and 0x948eb946 as OutsideTemplateKind/u8 at offset 38. The generator's 0x54e330 call uses that last hash on the row returned by 0x54e190. Together these links identify the candidate as a FieldMainFieldParam.UniqueID value.

**NATIVE — iterator feeding the generator.** 0x529910 calls wrapper 0x54edf0 at PC 0x529940; that wrapper calls iterator 0x54e930 at PC 0x54ee0c. The iterator reads the same UniqueID range and uses hash 0x54706054 to resolve each row through +0x1110. This proves the candidate pool is drawn from the ID-indexed row set. The initializer or resource loader that fills the array and range members remains OPEN.

**PSEUDO — selection is run-dependent.** The four slots use a random selection path and de-duplication bitset. There is no constant slot-to-ID table in the generator. Exact slot contents require a runtime/RNG fixture or a recovered deterministic seed and initial state.

## Result index, selected entry, and SaveMainField destination

The preceding cVillage-context report proves the option index is stored in the UI result child and then written by SaveSetFromUIResult case 5 to the field-system context subobject+0x20 (whole-context+0x45f0). This follow-up closes the consumer step:

- **NATIVE/PSEUDO — selected-entry consumer.** 0x565300 calls cleanup 0x529e50 at PC 0x565368. 0x529e50 reads the result index from subobject+0x20 and tail-branches at raw PC 0x529e94 to 0x529ea0. That consumer bounds-checks against count+0x10 and selects entry[index] from the pointer array at +0x18. Raw bytes at 0x529e84 are 61 22 40 b9; at 0x529e94 they are 03 00 00 14, encoding a branch to 0x529ea0. 0x529ea0 is an interior entry in the indexed 0x529e50 function span, not a separately indexed function start.
- **NATIVE — MainFieldParamUniqueID write.** The selected entry u16 at +0x0c is loaded at PC 0x529f34 (bytes a9 1a 40 79) and stored at PC 0x529f44 (bytes 09 69 2a 78) through save descriptor key 0xda2ac, at SaveMainField-relative offset +0xcfa2a.
- **NATIVE — OutsideField copy.** The consumer resolves descriptor key 0x92 at PCs 0x529f80–0x529f88, loads entry+0x0e at 0x529f90, passes entry+0x10 at 0x529f94, and calls 0xf8f2a0 at 0x529f9c. The helper copies exactly 0x90 bytes and writes the u16 argument at destination+0x90. The destination is the resolved OutsideField object.
- **STRUCT — destination names and offsets.** The checked save crosswalk maps the SaveLand child node of size 0xda2ac to SaveLand.MainField / ::Game::SaveMainField. Its MainFieldParamUniqueID primitive is two bytes at SaveLand data offset 0x2d121e, equivalent to MainField-relative +0xcfa2a. Its OutsideField child is 0x92 bytes at SaveLand data offset 0x2d118c, or MainField-relative +0xcf998. This aligns with the native descriptor lookups and the helper's 0x90-byte block plus two-byte value. Key 0x92 equals the crosswalk child size; that numeric equality is corroboration, not a standalone assertion that descriptor keys universally encode sizes.
- **PSEUDO — runtime-state boundary.** These writes go through the native save-object accessor into in-memory SaveLand.MainField. No serialization, save-file commit, or disk write is called in the recovered selected-entry consumer.

An independent creation routine at 0x5662e0 also resolves key 0xda2ac and writes a u16 candidate to +0xcfa2a, resolves key 0x92, and calls the same copy helper. This corroborates the destination route only; it is not used to infer the cVillage index relationship. Its indexed direct caller is 0xfc3b00 at PC 0xfc3b08.

## Relation to FieldData, LandMaking, and world setup

The table metadata joins each candidate UniqueID to its row's FieldData and OutsideTemplateKind. Existing data work joins a FieldMainFieldParam.FieldData stem such as FieldPresetA00 to FieldPresetA00_LandMaking.byml (source 2442). This establishes which data file corresponds to a row when its UniqueID is known.

It does **not** establish a stable option-slot-to-UniqueID mapping or prove that the 0x529ea0 consumer opens/applies that LandMaking file. No seed or spawn field is written in this selected-entry consumer. A separate creator path writes MainFieldParamUniqueID, DistantViewUniqueID, and OutsideField before world initialization, but the matching field names do not prove that this UI option path reaches the same generation/load routine. Later map application, terrain generation order, spawn selection, seed association, and durable save timing remain OPEN.

## Bounded search and limits

- The generated direct-call index records nine 0x54e190 calls: four from 0x529910, plus 0x4e1e34, 0x558f84, 0x5598f0, 0x559ba8, and 0x566370. The readback path in 0x4e1db0 calls 0x54e190 at PC 0x4e1e34 and a row accessor at 0x4e1e90, proving a saved ID can be re-resolved to a row; the later map-application edge is not identified.
- The generated decompilation references context offsets +0x1108, +0x1110, and +0x1128 as range/count/pointer-array reads in 0x54e190 and 0x54e930. A bounded fixed-offset search found no clear writer for these exact members. The table population/loading path remains OPEN.
- The cVillage write and cleanup consumer access the same context member (+0x45f0), but no direct call edge from SaveSetFromUIResult to 0x565300 is established. This is a static field/dataflow join.
- The save names come from a versioned external schema aligned to local native offsets/sizes, not local symbols.

Validation: the companion JSON parses with python -m json.tool; source hashes were checked against the files listed there. No earlier report or another agent's artifact was edited.
