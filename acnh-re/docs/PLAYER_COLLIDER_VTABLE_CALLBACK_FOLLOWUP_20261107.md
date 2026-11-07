# ACNH 1.0.0 query-candidate vtable callback follow-up

The `+0x30` callbacks for the two candidate vtables initialized by `0x1711d0` and `0x171bc0` resolve exactly from the ACNH 1.0.0 ELF relocations: `0x171450` and `0x171d40`, respectively. They are byte-identical 16-byte functions. Both load a pointer from `0x32d6d70`, return its first float in `s0`, and ignore the candidate, position, status pointer and final argument. The pointer resolves to `0x29ee40c`, whose first float is `-500.0`.

This closes the pointer-target question. In `0x157270`, the query accumulator also starts at `-500.0`; its loop only replaces the accumulator and status when a callback returns a greater value. Thus, for this query, these two callbacks contribute the default/no-hit scalar and do not change the result or status. Calling that value a “no-hit sentinel” is a caller-context interpretation; no source string or function name provides that semantic label.

The spatial-index object is a separate vtable class. Constructor `0x172090` installs the table rooted at relocation target `0x3037698`; its slot `+0x30` resolves to `0x172740`, the grid accessor used by `0x1577a0`. This matches the list construction traced in [the candidate-producer follow-up](PLAYER_COLLIDER_QUERY_CANDIDATE_PRODUCER_FOLLOWUP_20261107.md): the list can contain a terrain-grid index and volume-shaped candidate nodes with distinct callbacks.

## Relocation trace

The main image hash is `f8d248109ff72999b4600ae3749f8c7397fb960f7ad3ab8dee3018ae9e14e900`; the gameplay ELF hash is `5bf707c3dc5dac0ad9635af7d336ec580f81c3f7876d0f55400d1900e3415d74`. The `.rela.dyn` table begins at `0x2212040`, has 24-byte entries, and contains `R_AARCH64_RELATIVE` entries (`r_info = 0x403`, type `1027`). The `main` module base is zero, so the addends below are the relocated pointer values. The NSO stores zero at each relocated pointer word; those zero bytes are placeholders, not null function pointers.

| Constructor / class table | Constructor’s global slot and relocation | Object vptr | Callback word for slot `+0x30` | Resolved target |
|---|---|---|---|---|
| `0x1711d0` candidate | Global `0x32d7148`, relocation addend `0x30375a0` | `0x30375b0` | `0x30375e0`, raw word zero, relocation type 1027, addend `0x171450` | `0x171450` |
| `0x171bc0` candidate | Global `0x32d7168`, relocation addend `0x3037628` | `0x3037638` | `0x3037668`, raw word zero, relocation type 1027, addend `0x171d40` | `0x171d40` |
| `0x172090` spatial index | Global `0x32d7180`, relocation addend `0x3037698` | `0x30376a8` | `0x30376d8`, raw word zero, relocation type 1027, addend `0x172740` | `0x172740` |

The constructors store each relocated table address plus `0x10` as the object vptr. The list iterator’s indirect branch loads the callback from `[vptr+0x30]`; the addresses above therefore follow both the constructor adjustment and the call-site offset. The same relocated targets appear in [code_pointer_arrays.json](../../../acnh-re/output/binary/code_pointer_arrays.json), while the constructors independently establish which table each object uses. The pointer-array artifact cautions that a pointer sequence alone is not enough to call something a vtable.

## Callback behavior and limits

The two resolved candidate callbacks have identical bytes and digest:

```asm
adrp x8, #0x32d6000
ldr  x8, [x8, #0xd70]
ldr  s0, [x8]
ret
```

The relocation at global slot `0x32d6d70` points to `0x29ee40c`. The file bytes there begin `00 00 fa c3`, the little-endian `f32(-500.0)`. The iterator `0x157270` loads its initial scalar from `0x29d5cd4`, also `-500.0`; after calling a candidate it compares the current scalar in `s8` with the candidate result in `s0` and updates only when `s0` is greater. Equality follows the keep-current branch. This proves the two resolved callbacks cannot improve the query value or replace its status in this loop.

Constructor and caller metadata support these assignments:

- `0x1711d0` is called by `0x56e830`, `0x5fb520`, `0xc74610` and `0xc74970`. The candidate-producer trace shows the latter two register nodes built by this constructor; `0x56eb80` can also register the embedded object constructed at `+0x58`.
- `0x171bc0` is called by `0x56e830` and `0xd57470`; `0x56eb80` can register the embedded alternate object at `+0x240`.
- `0x172090` is called by `0x156d70`, `0x156e30` and `0x162a30`; its table slot `+0x30` resolves to `0x172740`, also called directly from `0x1577a0`, `0x164ed0` and `0x164fa0`.
- The call index reports no direct callers or string references for `0x171450` and `0x171d40`, as expected for functions reached through vtable dispatch. Their 16-byte bodies have no decompilation file; the raw disassembly is sufficient to establish the returned value, but not a developer-facing semantic name.

The exact callbacks are now mapped, but the live query remains OPEN. No existing native fixture supplies the real root, live grid, readiness state, populated query list or its relocated object vtables. This work made no synthetic fixture and did not rerun `0x7bccf0` or `0x7c5570`; the earlier `0x172780` sandbox fault remains an emulator initialization boundary, not a gameplay claim. Statuses: **EF** (executable identity/relocation bytes), **STRUCT** (vptr/slot offsets), **PSEUDO** (constructors and iterator), **NATIVE** (previous isolated grid fixtures only), **CAT** (default/no-hit interpretation from caller context), **OPEN** (live query/list and broader gameplay semantics). The ledger is [vtable_callback_relocation_followup_20261107.json](../output/mechanics/player_collider_query_remainder_20261107/vtable_callback_relocation_followup_20261107.json).
