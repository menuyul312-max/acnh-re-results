# Crafting material removal remainder

**Date:** 2026-11-07
**Scope:** One bounded original-ELF material-removal attempt for RecipeCraftParam row 56. This does not exercise the full craft transaction.

## Interpretation update

> The initial fixture result below is historical and its row-pointer explanation is superseded by [CRAFTING_TRANSACTION_MANAGER_FOLLOWUP_20261107.md](CRAFTING_TRANSACTION_MANAGER_FOLLOWUP_20261107.md). A clean ItemParam/ItemKind manager proves Apple pointer `0x5103c9d8` converts to dense index `495`. The zero predicate belongs to `SaveCountMaxNum` in the alternate `0xeff060 → 0xf9e410` path and does not establish an in-game rejection. The original default material helper `0xee1060` returns 1 in five bounded cases, but the fixture lacks real inventory count caches and makes no consumption claim.

## Result

**Historical observation, superseded as a gameplay interpretation:** this original Apple fixture reached `0xeff060` and `0xf9e410`, then the native gate returned zero before a count update. The call sequence was `0xf9e410 → 0xf9e840 → 0xaac910 → 0xaac730`; the bounded run therefore observed the zero branch and unchanged synthetic pocket bytes. The later manager follow-up below maps the Apple pointer to dense index 495 and shows that `SaveCountMaxNum=0` came from the alternate signed-count route. Do not read this older fixture as an Apple rejection or a valid live inventory count test.

The inventory fixture started with Apple item `2213` and count `9`. It ends with the same item ID and count; no inventory bytes changed, and the pocket view remained unchanged. There was no unmapped access or emulator exception. `consumption_verified` is false. This run does not verify material removal.

**Historical fixture diagnosis, superseded:** that earlier setup placed `0x51007078` in record `+0x10`, where this accessor expected an ItemParam index. Its old manager arrangement was incomplete. The clean follow-up installation separately establishes that Apple row pointer `0x5103c9d8` converts to dense index `495`, and that the alternate route reads the Fruit row's `SaveCountMaxNum=0`. The outstanding cache gap is now the player's native A/B/C item-count context, not pointer-to-index reconstruction.

## Fixture and limits

RecipeCraftParam row 56 names result item `975` and Material1 Apple `2213`, amount `1`. The probe uses a controlled synthetic player/session, inventory member, and view. It installs a 32-slot member view at the native `0xee9350` boundary after original `0xf8f400` resolves the player view; slot 0 holds Apple `2213` with count `9`. The call arguments at `0xeff060` are that view's inventory pointer, an eight-byte Apple descriptor, and signed delta `-1`.

`0xaac730`, `0xf9e840`, `0xf9e410`, and `0xeff060` execute from the original analysis ELF. The predicate bytes are identical before and after (`fb0f1af8fa6701a9`); no predicate return value is replaced. ItemParam/ItemKind row data and the minimal manager arrays are reconstructed by `inventory_requirements_native.install_item_tables`; the complete runtime table-manager graph is absent. The player records are synthetic. The fixture helper lays down success-return virtual-method stubs at `0x501b5000` and `0x501b5010`, but this run sets the active member service pointer to null at `0xee9350`, so native `0xee94f0` takes its no-provider path and those stubs are not called. No live game process or real save participates.

**Historical run plan, superseded:** the initial attempt did not run the five-material case. The follow-up now calls default helper `0xee1060` on all five Recipe-56 fruit rows, which return `1` without pocket writes. A faithful retry still needs the real count caches and their A/B/C source-record producers, followed by a full transaction trace; this report's original run did not test insufficient material or live acceptance.

## Provenance and reproduction

The probe pins the original analysis ELF SHA-256 to `5bf707c3dc5dac0ad9635af7d336ec580f81c3f7876d0f55400d1900e3415d74`, the matching main NSO to `f8d248109ff72999b4600ae3749f8c7397fb960f7ad3ab8dee3018ae9e14e900`, and the read-only shared index to `a78c7af27d37b8fd931bba8bc611623dacf7685cb6e8b4f827effa0765340aad`. Table and call-site provenance, observed arguments/returns, branch instructions, and before/after bytes are in [eff060_apple_probe.json](../output/gameplay/crafting_material_removal_remainder_20261107/eff060_apple_probe.json).

From the worktree root, rerun:

```sh
python3 acnh-re/output/gameplay/crafting_material_removal_remainder_20261107/probe_eff060_apple.py
```

The script reads the shared dump and index, runs the original ELF in the bounded emulator, and writes only `eff060_apple_probe.json` beside itself.

Full transaction dispatch, the other materials, insufficient-material behavior, rollback/atomicity, and durable save remain open. This evidence does not establish complete crafting.
