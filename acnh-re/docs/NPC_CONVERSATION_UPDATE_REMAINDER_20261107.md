# NPC conversation update/exit remainder (ACNH 1.0.0)

This probe executes the registered `NpcAIActivityState::cConversationHost`
exit body at `0xc0c280` (state index 60) from the pinned main NSO. It selects
the callback's bit-5 cleanup branch and reaches the end of the original body.
The callback and its native helpers ran without function-address stubs.

The fixture supplied an owner with `owner+0xab40 = 0x1020`, so bit 5 selected
`0xc0c420`; the same word also had bit 12 set. The owner context at `owner+8`
contained scalar `0x77` at `context+0x230`, and the callback's second argument
was zero. The fixture initialized `owner+0xab10` to `0xffff`, and the words at
`+0x7d14`, `+0x7d1c`, and `+0x103dc` to `0x55`, `0x66`, and `0x99`.

The original body first cleared bit 12 from `owner+0xab40`, then called
`0xceb7d0` with `(owner+0xa8f0, 0)`. That helper cleared the low ten bits of
the halfword at `owner+0xab10`. The body then called `0xca52a0` with the
context scalar. The fixture supplied a singleton manager whose list-end
pointer at `manager+0x2488` equaled the empty sentinel `manager+0x2480`, so
the original helper returned on its empty-list branch.

With the zero second argument, the exit body took its non-3 branch, called the
original `0x3fa40` view initializer twice using `owner+0x7d14`, and received
null both times because the initializer's inner global pointer was zero. On
that path it zeroed `owner+0x103dc`, copied the zero dword at global-counter
pointer `0x3348650` to `owner+0x7d14` and `owner+0x7d1c`, and cleared bit 5
from `owner+0xab40`.

| Owner field | Before | After | Raw operation evidenced on this branch |
|---|---:|---:|---|
| `+0xab40` (`u64`) | `0x1020` | `0` | Clear bit 12 at `0xc0c420`, then clear bit 5 at `0xc0c408` |
| `+0xab10` (`u16`) | `0xffff` | `0xfc00` | `0xceb7d0` clears bits 0–9 with `w1=0` |
| `+0x7d14` (`u32`) | `0x55` | `0` | Copy the dword at global pointer `0x3348650` |
| `+0x7d1c` (`u32`) | `0x66` | `0` | Copy the same global dword at callback return |
| `+0x103dc` (`u32`) | `0x99` | `0` | Store zero on the null-view branch |

All other bytes in the `0x11000`-byte owner allocation remained unchanged. The
owner-context and synthetic manager objects also had no changed bytes. These
offsets remain unnamed: the test demonstrates this branch's writes, not the
fields' names or gameplay meanings.

## Fixture and limits

The sandbox's pointer cell at `0x357aec0` was initially null. The fixture
placed a synthetic manager there and set its `+0x2488` qword to
`manager+0x2480`; this satisfies `0xca52a0`'s empty-list check without
dispatching any list item. The view initializer global at `0x32d0de0` points
to an image object whose inner pointer is zero, which is why both view
wrappers were 16 zero bytes. The global counter pointer at `0x32d1c88` resolves
to `0x3348650`, whose dword was zero. The original `0x3fa40`, `0x3fcc0`,
`0xceb7d0`, and `0xca52a0` bodies ran; the sandbox reported no unresolved
imports.

From the checkout root, reproduce the case with:

```bash
PYTHONPATH=/workspace/acnh-re/.deps \
python3 acnh-re/output/gameplay/npc_conversation_update_remainder_20261107/repro_host_exit_native.py
```

The harness verifies the pinned NSO SHA-256
`f8d248109ff72999b4600ae3749f8c7397fb960f7ad3ab8dee3018ae9e14e900`, exact
owner/context/manager diffs, and the final raw fields. Its observations are in
[host_exit_native.json](../output/gameplay/npc_conversation_update_remainder_20261107/host_exit_native.json);
the reproducer is
[repro_host_exit_native.py](../output/gameplay/npc_conversation_update_remainder_20261107/repro_host_exit_native.py).

This is a direct exit-body call, not a state-manager transition. The fixture
does not establish when the host state exits, the live runtime manager shape,
pair admission, or a host-to-guest handoff. NPC scheduler cadence, host/guest
selection, dialogue topic/message and EventFlow lookup, and network
synchronization remain open.
