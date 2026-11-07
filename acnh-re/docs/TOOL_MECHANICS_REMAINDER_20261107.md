# Tool mechanics remainder (2026-11-07)

This pass follows the open break selector and the remaining family wear routes in the game 1.0.0 indexed main NSO. It closes a bounded native state-request boundary, but it does not prove that zero remaining durability selects `PlayerToolBreak`.

## Selector boundary

The newly traced route is:

```text
action/state caller -> 0xdd6ba0 -> 0xe37760
                                  -> 0xe375d0 predicate
                                  -> 0xdb01e0 -> 0xe89360 -> 0xaa7700 (ToolDamage read)
                                  -> 0xdd5c40(state 0xb8), if the predicate succeeds
```

`0xe37760` requests state ordinal `0xb8` only when its local `+0xf04` bit-2 guard is clear and `0xe375d0` returns true. The state registration audit maps ordinal `0xb8` to `State::cToolBreakDemo`. A bounded Unicorn run of the original `0xe37760` body confirmed the request with a controlled true predicate result; a false result and a set guard bit produced no request. The state registration uses a relocated callback pointer sequence; the indexed evidence does not establish a C++ vtable or bind this request to a live selected callback.

The predicate starts with `0xdb01e0`. That helper reads the held item's current `ToolDamage` through `0xe89360 -> 0xaa7700` and also checks item/state helpers. The traced slice has no direct `BreakDamage - ToolDamage` read through `0xaa7ce0`, and it does not directly call the wear commit wrappers. The known `0xaa7ce0` caller remains the DIY-list builder. Consequently, the new route does not establish that the selector becomes true at `remaining == 0`, nor that the requested state dispatches the `PlayerToolBreak` EventFlow entry.

The neighboring action-region function `0xe589a0` calls `0xdd6ba0`, which gives one watering-region caller a path into this predicate and state request. The named string references `CommonWatering` and `CommonWateringUpperLevel` attach to `0xe585c0`; `0xe589a0` has no direct string references in the index, so this note leaves its precise family label open. The named `0xe585c0` function calls `0xdb01e0` and reaches the current-wear reader, but has no direct wear-commit call.

## Wear routes by family

The direct-call inventory supports these boundaries:

| Family | Indexed route | Remaining gap |
| --- | --- | --- |
| Axe | `0xe36ec0` is the axe hit-tree anchor; it has no direct call to the indexed wear wrappers. | Which successful axe result reaches the wear commit and break-state selector. |
| Shovel | `0xe541a0 -> 0xdb0140 -> 0xe893c0 -> 0xe895a0` is a known get-demo route with `+1` wear. | Dig/bury result handling and the zero-wear transition. |
| Net | `0xe45b80 -> 0xdb00f0 -> 0xe895a0` applies `+1`; the action also calls `0xdb01e0`. | Catch result eligibility and how an exhausted tool selects the break state. |
| Fishing rod | `0xe4e730 -> 0xdb00f0 -> 0xe895a0` applies `+1` or `+2` under the previously recorded rod/item condition; the action also calls `0xdb01e0`. | Family-specific wear cadence and the exhausted-tool transition. |
| Slingshot | `0xe564b0` reaches the launch helper `0x803690`; no direct indexed wear-wrapper edge appears in this anchor. | The later result path that commits wear and selects break presentation. |
| Watering | `0xe585c0 -> 0xdb01e0 -> 0xe89360 -> 0xaa7700` reads current wear. The adjacent `0xe589a0 -> 0xdd6ba0` route can enter the predicate/state request path above. | The family-specific wear commit and whether remaining durability selects the state. |

The direct wear-wrapper callers remain `0xe893c0` from `0x4c0190`, `0xda4560`, and `0xdb0140`, and `0xe895a0` from `0xe893c0` and `0xdb00f0`. The generic helper `0xdd6ba0` also serves other get-demo/state flows, including fish, insect, and shovel contexts; its presence alone does not prove a tool break. This keeps the family cadence incomplete where there is no direct wrapper edge.

## Evidence and reproduction

This combines a static caller trace with a bounded native probe of `0xe37760`; it is not a live player action or EventFlow execution. The native probe uses a synthetic state/context allocation, stubs `0xe375d0` to supply true/false outcomes, and captures the call to the generic state helper `0xdd5c40`. It does not execute the predicate or state manager. The static trace uses the indexed direct-call database at `/workspace/acnh-re/output/index.sqlite`, decomp snapshots under `/workspace/acnh-re/output/binary/analysis_decomp`, the state-registration disassembly `dd9a60.asm`, and `code_pointer_arrays.json`. The main NSO SHA-256 is `f8d248109ff72999b4600ae3749f8c7397fb960f7ad3ab8dee3018ae9e14e900`. The per-function snapshot hashes, fixture stubs, and checked call edges are recorded in [tool_break_state_selector_static.json](../output/gameplay/tool_mechanics_remainder_20261107/tool_break_state_selector_static.json).

The checks were rerun against the read-only index and passed: `0xe37760` calls both `0xe375d0` and `0xdd5c40`; its decomp requests ordinal `0xb8`; the registry names that ordinal `State::cToolBreakDemo`; `0xdb01e0` reaches the current-wear getter; and the watering-region edges `0xe589a0 -> 0xdd6ba0 -> 0xe37760` are present. The static checks can be reproduced with:

```sh
python3 - <<'PY'
import sqlite3, sys
from pathlib import Path
sys.path.insert(0, "/workspace/acnh-re-github/acnh-re/tools")
import tool_durability_residual_static as audit
db = sqlite3.connect("file:/workspace/acnh-re/output/index.sqlite?mode=ro", uri=True)
def targets(start, end):
    return {target for (target,) in db.execute(
        "SELECT target_va FROM direct_calls WHERE pc>=? AND pc<?", (start, end))}
def end(va):
    return db.execute("SELECT span_end_va FROM native_functions WHERE va=?", (va,)).fetchone()[0]
state = audit.player_state_callback_audit(db, Path("/workspace/acnh-re/output"))
assert 0xe375d0 in targets(0xe37760, end(0xe37760))
assert 0xdd5c40 in targets(0xe37760, end(0xe37760))
assert "FUN_00ed5c40(param_1,0xb8,uVar1)" in Path(
    "/workspace/acnh-re/output/binary/analysis_decomp/e37760.c").read_text()
assert state["adjacent_state_registrations"][0xb8]["state_name"] == "State::cToolBreakDemo"
assert 0xdd6ba0 in targets(0xe589a0, end(0xe589a0))
assert 0xe37760 in targets(0xdd6ba0, end(0xdd6ba0))
print("tool break selector and watering-region static checks passed")
PY
```

The native request boundary can be reproduced with:

```sh
PYTHONPATH=/workspace/acnh-re/.deps:/workspace/acnh-re-github/acnh-re/tools python3 - <<'PY'
import struct
from pathlib import Path
from nso_sandbox import Sandbox

sb = Sandbox(Path("/workspace/acnh-re-github/acnh-re/inputs/additional_exefs/main"))
state, ctx, arg = sb.alloc(0x1200), sb.alloc(0x400), sb.alloc(0x20)
sb.uc.mem_write(state + 0x68, struct.pack("<Q", ctx))
sb.uc.mem_write(arg + 0xc, struct.pack("<I", 0x7f))
predicate, calls, requests = {"value": 1}, [], []
sb.stub(0xe375d0, lambda _sb: (calls.append(1) or predicate["value"]))
for va in (0xdd7c40, 0xe5a880, 0x15bbbf0, 0x15bbc10, 0x7c9560):
    sb.stub(va, lambda _sb: 0)
sb.stub(0xdd5c40, lambda s: (requests.append(s.reg("x1")) or 1))
for guard, result, expected in ((0, 1, [0xb8]), (0, 0, []), (4, 1, [])):
    predicate["value"] = result
    calls.clear()
    requests.clear()
    sb.uc.mem_write(state + 0xf04, bytes([guard]))
    sb.call(0xe37760, (state, arg))
    assert requests == expected, (guard, result, requests)
    assert len(calls) == (0 if guard & 4 else 1)
assert not sb.unknown_imports
print("original e37760 state-request probe passed: 3 cases, 0 mismatches")
PY
```

The unresolved threshold condition, live state selection, remaining axe/slingshot/watering wear paths, and durable save serialization stay open.
