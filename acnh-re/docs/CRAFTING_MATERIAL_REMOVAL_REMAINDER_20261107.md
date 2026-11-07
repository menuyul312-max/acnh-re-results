# Crafting material removal remainder

**Date:** 2026-11-07
**Scope:** One bounded original-ELF material-removal attempt for RecipeCraftParam row 56. This does not exercise the full craft transaction.

## Result

The controlled Apple fixture reaches original `0xeff060` and `0xf9e410`, but the native gate returns zero before a count update. `0xf9e410` calls `0xf9e840` at `0xf9e430`; `0xf9e840` calls `0xaac910`, which calls the unmodified `0xaac730`. At `0xaac91c`, `0xaac730` returns W0=0. `0xaac910` returns zero at `0xf9e878`, and `0xf9e840` takes its reject branch at `0xf9ebf8`. The zero test at `0xf9e434` then reaches `0xf9e410`'s no-change epilogue at `0xf9e4f4`.

The inventory fixture started with Apple item `2213` and count `9`. It ends with the same item ID and count; no inventory bytes changed, and the pocket view remained unchanged. There was no unmapped access or emulator exception. `consumption_verified` is false. This run does not verify material removal.

The trace also identifies why this fixture is not a valid runtime item-data context. At entry to native `0xaac730`, its record `+0x10` contains `0x51007078`, a raw ItemParam row pointer supplied by the reconstructed table manager. The original code bounds that value as an index against the 8,208-entry ItemParam lookup cache; this pointer is out of range, so the native conversion takes its index-zero fallback. The remainder of the ItemParam/ItemKind cache representation is not reconstructed. The resolved dump independently maps Apple `2213` to ItemKind `Fruit` (`0x61cafd93`), whose `SaveCountMaxNum` is zero, but this probe does not establish that native lookup reached Apple's Fruit row.

## Fixture and limits

RecipeCraftParam row 56 names result item `975` and Material1 Apple `2213`, amount `1`. The probe uses a controlled synthetic player/session, inventory member, and view. It installs a 32-slot member view at the native `0xee9350` boundary after original `0xf8f400` resolves the player view; slot 0 holds Apple `2213` with count `9`. The call arguments at `0xeff060` are that view's inventory pointer, an eight-byte Apple descriptor, and signed delta `-1`.

`0xaac730`, `0xf9e840`, `0xf9e410`, and `0xeff060` execute from the original analysis ELF. The predicate bytes are identical before and after (`fb0f1af8fa6701a9`); no predicate return value is replaced. ItemParam/ItemKind row data and the minimal manager arrays are reconstructed by `inventory_requirements_native.install_item_tables`; the complete runtime table-manager graph is absent. The player records are synthetic. The fixture helper lays down success-return virtual-method stubs at `0x501b5000` and `0x501b5010`, but this run sets the active member service pointer to null at `0xee9350`, so native `0xee94f0` takes its no-provider path and those stubs are not called. No live game process or real save participates.

Because the first Apple attempt is rejected by this incomplete lookup context, the five-material and insufficient-material cases were not run. The next useful boundary is to recover the runtime ItemParam lookup/index representation (and validate its player/view source), then repeat this single Apple case until the native gate accepts and the inventory count changes. Only then should the remaining recipe materials be added.

## Provenance and reproduction

The probe pins the original analysis ELF SHA-256 to `5bf707c3dc5dac0ad9635af7d336ec580f81c3f7876d0f55400d1900e3415d74`, the matching main NSO to `f8d248109ff72999b4600ae3749f8c7397fb960f7ad3ab8dee3018ae9e14e900`, and the read-only shared index to `a78c7af27d37b8fd931bba8bc611623dacf7685cb6e8b4f827effa0765340aad`. Table and call-site provenance, observed arguments/returns, branch instructions, and before/after bytes are in [eff060_apple_probe.json](../output/gameplay/crafting_material_removal_remainder_20261107/eff060_apple_probe.json).

From the worktree root, rerun:

```sh
python3 acnh-re/output/gameplay/crafting_material_removal_remainder_20261107/probe_eff060_apple.py
```

The script reads the shared dump and index, runs the original ELF in the bounded emulator, and writes only `eff060_apple_probe.json` beside itself.

Full transaction dispatch, the other materials, insufficient-material behavior, rollback/atomicity, and durable save remain open. This evidence does not establish complete crafting.
