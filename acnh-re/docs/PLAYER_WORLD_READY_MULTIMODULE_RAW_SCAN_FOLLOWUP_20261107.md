# Player world readiness and ExeFS raw-store follow-up (ACNH 1.0.0)

This pass extends the prior root-readiness search with a raw instruction scan of every supplied ExeFS text segment and resolves one nonzero `+0xee8` byte-store candidate to its only indexed direct caller. The candidate is **not** joined to the world-root query context, so the root `+0xf10` writer remains open. It also confirms that the known Npad poll calls resolve to Nintendo SDK exports while the edge from sampled input to player movement remains open.

## Nonzero `+0xee8` candidate

The main text scan finds four unsigned-immediate `STRB` instructions to receiver offset `+0xee8` and none to `+0xf10`:

| Raw VA | Instruction word | Effect |
|---|---|---|
| `0x156938` | `0x393ba27f` | `STRB WZR,[X19,#0xee8]`; clears the known query-context byte during constructor initialization. |
| `0x110c58c` | `0x393ba27f` | `STRB WZR,[X19,#0xee8]`; receiver type is not established by the raw offset alone. |
| `0x11196bc` | `0x393ba268` | `STRB W8,[X19,#0xee8]`; immediately preceded by `MOV W8,#1` at `0x11196b8` (`0x320003e8`). This is a nonzero writer to an unidentified receiver. |
| `0x1c7e4cc` | `0x393ba27f` | `STRB WZR,[X19,#0xee8]`; receiver type is not established by the raw offset alone. |

At `0x1119610`, `X19` is copied from incoming `X0`. `0x1119510` reads `[X0,#0xee8]` at `0x1119520`; when it is zero, its branch at `0x1119528` reaches a tail path through `0x1119608` into `0x1119610`. The callee populates additional fields and stores byte value 1 at `0x11196bc`. This proves a lazy-init-like check/set pattern for some object, but the label is descriptive only.

The raw main-text direct `B`/`BL` scan found only `0x1119608 B 0x1119610` for the setter and one direct caller of `0x1119510`, `0x969f8 BL 0x1119510` inside `FUN_001967e0`. That function is present in the startup pointer sequence at `0x32d3c60`. The call setup reads a pointer through global relocation cell `0x32d29f0` (relative relocation addend `0x361a5f8`), then loads its first word into `X0`. The first word of that BSS location is runtime state and is not identified in the file-backed image.

This is separate from the known root-query chain: root global cell `0x32d0de8` relocates to storage slot `0x33728b0`; its predicate checks `root+0xf10`, equivalent to query-context `+0xee8` because the context is at root `+0x28`. The new writer's only direct caller instead obtains `X0` through the different cell `0x32d29f0` and BSS address `0x361a5f8`. No code-pointer-array entry for `0x1119510` or `0x1119610`, direct branch from the root predicate/initializer, or data-flow equality between these receiver paths was found. Therefore this writer remains a candidate and does **not** prove the root readiness byte is set.

## ExeFS-wide direct-store bounds

I scanned each aligned 4-byte word of the supplied decompressed text segment in `main`, `rtld`, `subsdk0`, and `sdk` for unsigned-immediate `STRB`, `STRH`, `STR W`, and `STR X` stores whose scaled byte displacement is exactly `0xee8` or `0xf10`. The opcode/offset scan produced these counts:

| Module | `STRB` | `STRH` | `STR W` | `STR X` | `STRB` source at `+0xee8/+0xf10` |
|---|---:|---:|---:|---:|---|
| `main` | 4 | 0 | 61 | 56 | 3 `WZR` clears; one `W8=1` candidate at `0x11196bc` |
| `rtld` | 0 | 0 | 0 | 0 | none |
| `subsdk0` | 0 | 0 | 3 | 2 | none |
| `sdk` | 0 | 0 | 7 | 5 | none |

The 32-/64-bit stores can overlap a byte at those offsets, and their object receivers were not exhaustively de-aliased across all functions. The scan also does not cover computed-address writes, atomics, stores through pointers to nested objects, indirect runtime dispatch, or memory writes by an omitted module. It is a bounded raw opcode search, not a complete def-use proof. No non-main module contains a direct byte-width immediate store to either offset, but the available evidence does not establish their runtime object types.

## Closest input-to-world path

The earlier controller trace showed `ControllerMgr` virtual update slot `+0xb0` at `0x19a4ab0` dispatching device slot `+0x20` to the Npad poll method `0x1968b80`. The cross-module import ledger now confirms the five poll calls bind uniquely to `sdk` exports:

| Main call PC | Input state | Main relocation cell → `sdk` export VA |
|---|---|---|
| `0x1968c14` | `NpadHandheldState` | `0x32cf6f0` → `0x3570e0` |
| `0x1968c2c` | `NpadJoyDualState` | `0x32cf6f8` → `0x357a30` |
| `0x1968c44` | `NpadFullKeyState` | `0x32cf700` → `0x356fc0` |
| `0x1968c5c` | `NpadJoyLeftState` | `0x32cf708` → `0x357b50` |
| `0x1968c74` | `NpadJoyRightState` | `0x32cf710` → `0x357c70` |

The poller's style query at `0x1968bd4` likewise resolves through `0x32cf6e8` to `sdk` export `0x355970`. This pins the HID calls to the supplied SDK module. It does not connect the scheduler callback to `ControllerMgr::update`, translate these sampled states into a player command, or join that command to the existing ground/collision/movement query path. Those gameplay edges remain **OPEN**.

## Identity and limits

The companion JSON records all four NSO input hashes and text-segment hashes, the main ELF hash, import-resolution and pointer-index hashes, candidate instruction words/PCs, direct-call bounds, and the unresolved receiver distinction. The direct-store scan operates on the decompressed ExeFS `.bin` text segments (`VA 0` for `main`); SDK-module VAs are module-relative and are not mixed with main ELF VAs.

This work is static. It did not execute the game, inspect runtime BSS values, mutate a save, or construct a gameplay fixture. The candidate `0x11196bc` and SDK import joins refine the search, but neither closes root readiness or end-to-end player control.
