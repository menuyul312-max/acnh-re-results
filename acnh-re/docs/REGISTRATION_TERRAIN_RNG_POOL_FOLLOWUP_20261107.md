# Terrain-option RNG and candidate-pool follow-up (ACNH 1.0.0)

This static follow-up resolves how the four registration entries sample candidate IDs and what makes a row eligible. It also records a bounded negative search for the runtime range/array producer. It does not establish the live range values, durable save behavior, or a map-load edge. No game was run and no save was changed.

## Findings

The four options sample **without replacement** from a 512-bit mask populated by callback-returned IDs. The callback resolves a row's `UniqueID` and sets its bit only when the returned ID is below 512. The random path selects a 1-based ordinal among the currently set bits, maps that ordinal to a bit/ID, clears the selected bit, and repeats for slots 0–3. No fixed slot-to-ID mapping exists.

The decoded local `FieldMainFieldParam.bcsv` has 96 unique IDs, all in 0–119. Thus all 96 fit the mask's `<512` cap. The static row set consists of IDs `0`, `8–24`, `28–81`, `89–100`, and `108–119`; gaps are `1–7`, `25–27`, `82–88`, and `101–107`. `OutsideTemplateKind` is read only after a candidate ID is sampled; the mask callback does not filter by that field. The table has 30 rows of kind 0, 33 of kind 1, and 33 of kind 2.

**Runtime eligibility remains conditional.** `54e930` walks the configured inclusive range `+0x1128..+0x112a`; it uses the span at `+0x1108` and pointer array at `+0x1110`, and has a BCSV lookup path when an indexed pointer is unavailable. The callback's `54e200` helper returns zero when its row pointer is null/empty, and `54ee20` then sets bit 0 because zero is below 512. So the exact proven pool is the distinct callback return values in `[0,511]`; a null callback can reassert bit 0. If the live range covers 0–119 and the 96 rows resolve, all 96 table IDs are eligible and the 24 gaps do not add other IDs (bit 0 is already a real row). The available static evidence does not prove those live bounds or row residency, so “all 96 eligible at runtime” remains **OPEN**.

## Native evidence

Addresses below are raw ELF virtual addresses (PCs), not the generated `FUN_006...` pseudoname addresses.

- **Mask construction.** `529910` calls mask initializer `54eda0` at PC `0x529938` and iterator wrapper `54edf0` at `0x529940`. `54eda0` clears the 64-byte mask payload (16 × u32) and initializes its object header. `54edf0` builds a callback pair using the vtable relocated at `0x30648f8`; that relocation resolves to `54ee20`. The wrapper calls iterator `54e930` at PC `0x54ee0c`.
- **Row-to-bit callback.** `54e930` reads the runtime base at `+0x1128`, terminal at `+0x112a`, span at `+0x1108`, and pointer array at `+0x1110`. It enumerates the ID range and has a BCSV resolution path that searches the `UniqueID` field hash `0x54706054`. Its callback call is at `0x54eb10`. The callback at `54ee20` calls `54e200` on the resolved row (`0x54ee2c–0x54ee34`), masks the returned ID to 16 bits, rejects IDs above `0x1ff` (`0x54ee38–0x54ee40`), and sets `1 << (ID & 31)` in word `ID >> 5` (`0x54ee44–0x54ee5c`). `54e200` performs the `0x54706054` field lookup and returns the row's u16 value.
- **Null-row corner case.** Raw `54e200` returns `w0=0` at `0x54e310` when its row pointer is null or begins with zero. `54ee20` has no nonzero-ID guard before setting the bit, so this path sets/reasserts bit 0. In a full 0–119 range, the table's genuine ID-0 row already contributes the same bit; with narrower live bounds, the effect cannot be resolved without the runtime range and pointer-array contents.
- **Population count and ordinal selection.** `32ba60` visits 16 u32 words and calls `198b590` for each; raw `198b590` is a 32-bit population-count sequence (`0x198b590–0x198b5c0`). The generator initializes the RNG at `0x529970`; for slot 0 it counts the mask at `0x529980/0x52998c`, advances RNG at `0x529998`, multiplies the random u32 by the population count at `0x52999c`, takes the high 32 bits at `0x5299a4`, adds one at `0x5299a8`, then calls nth-set-bit selector `52a110` at `0x5299ac`. The same sequence is repeated for slots 1–3 at calls `0x529abc`, `0x529bcc`, and `0x529cdc` (with the corresponding preceding population-count/RNG instructions).
- **No duplicate candidate.** `52a110` sums the population of preceding words, locates the word containing the requested 1-based ordinal, and calls `198b630` to select that set bit. `198b630` clears lower set bits until it reaches the requested ordinal and returns the bit index. The generator then clears the selected mask bit (`0x5299c4–0x5299e0` for slot 0; repeated for later slots), so the next slot cannot select the same ID.
- **RNG seed and recurrence.** `19a9fe0` calls PLT stub `0x220e420`; `.rela.plt` entry `0x32ce7d8` resolves to imported `_ZN2nn2os13GetSystemTickEv`. It derives four state words with multiplier `0x6c078965` and increments 1–4 (`0x19a9ff0–0x19aa0034`). `19aa0e0` advances those four words with the xorshift recurrence (`0x19aa0e0–0x19aa0108`). The exact runtime option order is therefore seed/run dependent; a deterministic seed fixture would be needed to reproduce actual IDs.

## Table evidence and interpretation

`output/tables_resolved/FieldMainFieldParam.json` is source ID 41, decoded from `B_data/Bcsv/FieldMainFieldParam.bcsv`, with 96 rows and row size 136. It identifies hash `0x54706054` as `UniqueID` (`u16`, row offset 4), `0x6e1ac981` as `FieldData` (string32, offset 6), and `0x948eb946` as `OutsideTemplateKind` (`u8`, offset 38). All 96 `UniqueID` values are distinct, between 0 and 119, and therefore pass the callback's `<512` bitset limit. The table contains no rows for the 24 gap IDs listed above.

The callback does not test `OutsideTemplateKind`; the later per-slot `54e330` lookup reads it after the random ID has been selected, and the existing generator then passes that value to `552bb0`. This supports “kind affects the later outside-template branch” but not “kind filters candidate rows.”

## Bounded search for the range/array producer

The producer of `+0x1108`, `+0x1110`, `+0x1128`, and `+0x112a` is still **OPEN**.

The raw executable segment was scanned for the direct global-cell reference pattern to `0x32d1ba8`: 297 exact ADRP/LDR references were found in 264 raw function extents. A local register-flow scan from the relocated global cell through the loaded object found no direct stores to the four target offsets, and no stores through the global pointer-slot alias. A separate aligned scalar unsigned-immediate load/store scan found 167 references to those exact offsets; 102 were STR instructions across 42 function extents. None of the 264 direct-reference owner functions directly BL-call one of those 42 store-owner functions.

This is a bounded negative, not proof that no producer exists. The scan cannot exclude a store through a virtual/helper call, a computed base that is not represented as an immediate offset, initialization in an unprovided imported module, or a cross-function pointer route outside the direct BL edges. Several unrelated classes use the same large offsets, so an offset-only match is not enough to attribute their stores to the candidate-index object. The live `+0x1108/+0x1110/+0x1128/+0x112a` initializer, table-loading caller chain, and durable world-generation consumer remain OPEN.

## Source identity

- Main ELF SHA-256: `5bf707c3dc5dac0ad9635af7d336ec580f81c3f7876d0f55400d1900e3415d74`.
- Raw executable segment `main/0.bin` SHA-256: `9c9b45d8e7a58706ca59e7244b3aebac2325ef98faa205e007974eeeb2f758e9` (35,723,872 bytes, VA base 0).
- ELF metadata ledger SHA-256: `42bfdc3107b4fde9add2459049ef6febd8bca4d999725eedfd3485bf5be8040d`.
- Resolved table JSON SHA-256: `141a6d85166bc8b08eac399389114fbebd5708e0d1c3b54af3be37e116a0e100`.
- `symbols.json` SHA-256: `6e808e4ccdd59a3b9ba186a853deb33385d0f9dc52d820606c60f93307a8aa1a`.
- `function_inventory.json` SHA-256: `ef4200433442a15746c700a3980e2573ee790ca6cee898b8786ec1c0fcd0c9ac`.

The companion JSON lists the raw-PC evidence, table statistics, source hashes, and the negative-search boundaries in machine-readable form. No earlier report, crosswalk, or another agent's file was edited; no commit or push was made.
