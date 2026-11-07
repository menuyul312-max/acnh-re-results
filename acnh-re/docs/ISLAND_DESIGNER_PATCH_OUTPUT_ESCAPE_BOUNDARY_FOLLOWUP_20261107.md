# Island Designer 3×3 patch output escape boundary, ACNH 1.0.0

The 3×3 copy at `0x54dc70` is written into the stack frame owned by its caller, `0x531ad0`. The raw AArch64 instructions correct the earlier report's phrase “caller-provided output object”: at `0x531b4c–0x531b54`, `0x531ad0` passes `x19` as the source and `x22 + 0x80` as the destination, where `x22` was set to its current stack pointer. The destination is therefore a local temporary in `0x531ad0`, not an output pointer passed through to `0x531790`, `0x5318e0`, or `0x531ba0`.

On the success branch, `0x54dc70` copies a bounded 3×3 block using 14-byte record spacing. Its helper `0x543000` copies the 11 payload bytes at record offsets `0–4`, `6–10`, and `12`. After the copy, `0x531ad0` sets a boolean result, runs temporary-context cleanup, returns that result, and restores its stack. The inspected return path has no explicit read of the `sp+0x80` destination and returns no pointer to it. The direct-call index shows `0x54dc70` has exactly one caller (`0x531ad0` at `0x531b54`). No consumer of this stack-local block is identified in this chain.

The existing candidate validator at `0x540a10` remains unjoined to an active input caller. It has no function entry in the native function index; the bounded direct-call index has no incoming call targeting `0x540a10`, and the precomputed code-pointer-array corpus has no entry targeting it. The same pointer-array scan finds no target entries for `0x531ad0` or `0x54dc70`. These are static, bounded negative results, not proof against dynamic dispatch or code paths outside the inspected indexes.

This closes only the ownership/escape question for the 3×3 copy. It does not identify a canonical 112×96 map setter, a terrain refresh, undo/apply transaction, or save path. The temporary 12×12 work-grid mutation and patch copy remain separate from proven persistent world-state mutation.

## Evidence and reproducibility

Addresses below are native ELF VAs. The supplied `main` NSO decompressed text segment is byte-identical to the indexed main text (`VA 0`, size `0x2211a60`). Analysis used the existing `index.sqlite`, `code_pointer_arrays.json`, and raw bytes; no Ghidra rebuild or index/crosswalk edit was made.

| Evidence | Result |
|---|---|
| `0x531ad0` | At `0x531aec`, saves incoming source pointer in `x19`; at `0x531b20`, saves its current `sp` in `x22`; at `0x531b4c–0x531b54`, calls `0x54dc70(x19, x22+0x80)`. |
| `0x54dc70` | Single indexed direct caller: `0x531ad0` at `0x531b54`. It treats `x0` as source and `x1` as destination. |
| `0x543000` | Called by `0x54dc70` at `0x54de14`; two `0x543260` calls copy 5 bytes each at six-byte spacing, then one byte at offset 12. |
| `0x531ad0` return | After `0x54dc70`, sets status, calls cleanup helpers, moves the status to `w0`, restores stack, and returns. No output pointer is returned. |
| `0x531ad0` direct callers | `0x531790` at `0x531830` and `0x5318b4`; `0x5318e0` at `0x531950` and `0x531a50`; `0x531ba0` at `0x531bf4` and `0x531c40`. |
| `0x540a10` | No function entry and no incoming target in the indexed direct-call or code-pointer-array scans. |
| Pointer-array scan | 18,348 sequences / 192,637 entries; no target entry for `0x540a10`, `0x531ad0`, or `0x54dc70`. |

Source and function-slice hashes, scan counts, caller edges, and the exact buffer/register evidence are recorded in the [machine-readable ledger](../output/ui_island/island_designer_patch_output_escape_boundary_followup_20261107.json).
