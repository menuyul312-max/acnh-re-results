# NPC host-state remainder (ACNH 1.0.0)

This probe executes the registered `NpcAIActivityState::cConversationHost`
entry at `0xc0b510` (state index 60) in the pinned main NSO. The original host
callback, conversion/view helpers, and the host's early-return helper chain
ran in the native sandbox. No function VAs were replaced. A synthetic empty
callback registry and a controlled nested runtime object make the branch
bounded; this does not start an NPC or its scheduler.

The host entry read `owner+8` as its context, then read the actor pointer at
`context+0x68` and scalar `0x77` at `context+0x230`. It passed
`actor+0x278`, the address of a two-float fixture vector, and mode 0 to
`0xd355f0`. After that original helper returned scalar 0, the host called the
original `0x3fa40` view initializer. Its 16-byte output was all zero, so the
entry followed its null-view branch at `0xc0b56c` to `0xc0b84c`.

On that branch the host called `0xbf7850` with `x0=owner+0x10` and `x1=6`.
The original helper called `0xbf7670`, which completed and wrote four values in
the supplied runtime context. The raw before/after values were:

| Runtime context offset | Before bytes | After bytes | Raw interpretation |
|---|---|---|---|
| `+0x380` | `00 00 00 00` | `00 00 80 bf` | `u32 0xbf800000`; bits also decode as `f32 -1.0` |
| `+0x384` | `00 00 00 00` | `00 00 00 40` | `u32 0x40000000`; bits also decode as `f32 2.0` |
| `+0x394` | `00 00 00 00` | `06 00 00 00` | `u32 6` |
| `+0x400` | `00 00 00 00 00 00 00 00` | `fe ff 00 00 00 00 00 00` | `u64 0xfffe` |

The callback did not change any byte in the `0x11000`-byte owner object, the
owner-context object, the actor, or the nested fixture object. These offsets
are left unnamed because this branch demonstrates writes, not the field names
or their game meaning. The return register after the callback was a temporary
stack address used by the final `0x3fcc0` return routine; it is not treated as
a callback result.

## Fixture boundary and failed access

With the sandbox's original static singleton pointer left null, the native
`0xca4370` callback dispatcher interpreted bytes at address zero as its list
header. It read `0xd100c3ff` from `x0+0xb70` as a signed count and attempted an
invalid list read at `0xca4394` (`ldr x1, [x20], #8`, with `x20=0x910083fda9027bfd`).
The reproducer records this initial `UC_ERR_READ_UNMAPPED` access. This count
is code bytes reached through a null pointer, not a meaningful registry size.

For the successful case, the fixture placed a synthetic manager pointer in
the singleton pointer cell at `0x357aec0` and set its `+0xb70` callback count
to zero. The original `0xca4370` body then ran its empty-list path. The view
initializer's original global path returned null because its inner pointer at
`0x33441f8` was zero in the sandbox image, leading to the early return above.
To let the original `0xbf7670` helper run through, the fixture also supplied a
nested object at `runtime_context+0x350`, a vtable at nested-object `+0x320`,
and a vtable slot at `+0x18` pointing to the existing one-instruction native
`ret` at `0x3fcc0`. The runtime context's `+0x3b0` pointer matched the static
sentinel `0x29d4e28`, selecting the helper's bounded equality branch. Those
objects and branch inputs are synthetic fixture data, not a reconstructed
live-game context.

The original code entries observed include `0xc0b510`, `0xd355f0`, `0xca4370`,
`0x3fa40`, `0xbf7850`, `0xbf7670`, `0xf58890`, `0xf5ae70`, `0xf57780`,
`0xf57e10`, `0x1990780`, `0x1990820`, and `0x3fcc0`. No function address was
stubbed and the sandbox reported no unresolved imports. The controlled empty
registry means no registry callback ran; the nested vtable's method target was
the native `ret` instruction, not an ACNH method implementation.

## Reproduction and remaining conversation gap

From the checkout root:

```bash
PYTHONPATH=/workspace/acnh-re/.deps \
python3 acnh-re/output/gameplay/npc_host_state_remainder_20261107/repro_host_entry_native.py
```

The harness checks the pinned main NSO SHA-256
`f8d248109ff72999b4600ae3749f8c7397fb960f7ad3ab8dee3018ae9e14e900`, asserts
the owner/context/actor/nested-object diffs and the four runtime-context
changes, and writes its observations to
[host_entry_native.json](../output/gameplay/npc_host_state_remainder_20261107/host_entry_native.json).
The reproducer is
[repro_host_entry_native.py](../output/gameplay/npc_host_state_remainder_20261107/repro_host_entry_native.py).

This establishes one direct host-entry early-return branch and the raw writes
made by its `0xbf7850`/`0xbf7670` helper path. It does not show when state 60 is
selected, whether a real pair is admitted, or how the host hands off to state
61. The NPC scheduler cadence, host/guest selection, conversation topic and
message lookup, EventFlow selection, and network synchronization remain open.
The guest-entry evidence and selector audit in
[NPC_CONVERSATION_STATE_REMAINDER_20261107.md](NPC_CONVERSATION_STATE_REMAINDER_20261107.md)
and [NPC_STORY_REMAINDER_20261107.md](NPC_STORY_REMAINDER_20261107.md) remain
bounded to their recorded branches as well.
