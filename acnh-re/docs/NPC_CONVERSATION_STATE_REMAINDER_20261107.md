# NPC conversation-state remainder (ACNH 1.0.0)

This follow-up executes one registered host/guest conversation callback body:
the `NpcAIActivityState::cConversationGuest` entry at `0xc0c9e0` (registered
state index 61). The case uses a controlled owner object and paired actor
contexts. It does not launch a live villager or the EventFlow/scheduler.

The native entry body returned successfully. The observed writes to its
synthetic owner were limited to:

| Owner offset | Before | After | Operation visible in the original body |
|---|---:|---:|---|
| `+0xab40` (`u64`) | `0x41` | `0x1041` | Read the qword, OR `0x1000`, write it back. The changed byte was `+0xab41: 0x00 → 0x10`. |
| `+0x103dc` (`u32`) | `0` | `0x1357` | Copy the dword at `+0x7834` (`0x1357`) to `+0x103dc`. The changed bytes were `00 00 → 57 13`. |

These offsets are left unnamed: the callback and fixture prove the read/write
operations but do not recover the field names or the bit-12 meaning.

## Controlled pair path

The harness supplied these objects and values:

- owner `0x80000000`, with its context pointer at `owner+8`, a runtime-context
  pointer at `owner+0x10`, and a demo-context pointer at `owner+0x18`;
- owner context resident slot `4` at `context+0x448`, and actor pointer at
  `context+0x68`;
- paired context actor pointer at `paired_context+0x68`;
- actor position records at each actor pointer `+0x278`, with X/Z values
  `[1.25, -2.5]` and `[5.0, 7.5]`;
- `owner+0x7d1c = 0x2468` and `owner+0x7834 = 0x1357`.

Original `0xc0c9e0` passed `owner+0x7d1c` to `0x3fe00`. The adapter supplied the
paired-context pointer and set temporary bytes `+8` and `+0xa` to 1, selecting
the callback's paired-context branch. The body then read the resident slot and
called `0xd1cb80` with `(4, 1)`; that controlled helper returned null, so the
subsequent `0xd1eaf0` branch did not run. It obtained the two actor position
addresses through the prepared contexts and passed them to `0x1c780`. The
position helper was captured and stubbed, so no distance/comparison result is
claimed.

The body next called `0xbf78f0` and `0xc8c920`. The recorded `0xc8c920`
arguments were `x0=owner+0x18`, `x1=0`, `x2=0x2468` (the dword at
`owner+0x7d1c`), `x3=0x34ca2e8`, `x4=0`. That service was stopped at entry. The
callback then ORed the `owner+0xab40` bitfield, called `0xceb7d0` with
`(owner+0xa8f0, 1)`, copied the word from `owner+0x7834` to `owner+0x103dc`,
and returned through a controlled temporary-object destructor at `0x40040`.
These helper bodies were not executed.

## Reproduction and scope

From the checkout root; point the sandbox to the local main NSO and include its dependency path:

```bash
ACNH_RE_NSO=/workspace/acnh-re/inputs/additional_exefs/main \
PYTHONPATH=/workspace/acnh-re/.deps \
python3 acnh-re/output/gameplay/npc_conversation_state_remainder_20261107/repro_guest_entry_native.py
```

The harness verified the pinned main NSO SHA-256
`f8d248109ff72999b4600ae3749f8c7397fb960f7ad3ab8dee3018ae9e14e900`, ran one
case with zero mismatches, and found exactly the two owner write ranges above.
The structured result and captured helper arguments are in
[guest_entry_native.json](../output/gameplay/npc_conversation_state_remainder_20261107/guest_entry_native.json); the reproducer is
[repro_guest_entry_native.py](../output/gameplay/npc_conversation_state_remainder_20261107/repro_guest_entry_native.py).

The callback instructions themselves were original NSO code. The owner,
resident slot, paired context, actors, positions, and copied word were prepared
inputs. The harness replaced `0x3fe00` pair resolution, `0xd1cb80` helper,
`0x1c780` position comparison, `0xbf78f0` context helper,
`0xc8c920` native service, `0xceb7d0`, and `0x40040`. It therefore establishes
the guest entry's operations on this branch, not the real pair-resolution rule
or downstream effects.

## Remaining conversation boundary

The full state/talk path remains open. The guest entry was called directly;
this test did not invoke the state manager or prove when state 61 is selected.
The host callback bodies at `0xc0b510`, `0xc0bd20`, and `0xc0c280`, plus guest
update/exit at `0xc0cb20` and `0xc0cc70`, remain unexecuted. In particular,
`0xc8c920` is the next unverified service boundary for this entry, and no
host/guest handoff or multiplayer synchronization was observed.

The story/scheduler gap from
[NPC_STORY_REMAINDER_20261107.md](NPC_STORY_REMAINDER_20261107.md) remains:
resolve how queue entry `0xb17ae0` relates to NPC update cadence, capture the
runtime conditions that choose host and guest, and connect `0xf4dbd0`'s
counter-selected index to an actual topic/message/EventFlow lookup. The
`0xc30930` motion/animation interpretation remains static evidence. None of
these paths was exercised by this fixture.

Reference state registration and prior conversation limits:
`output/mechanics/npc_state_registry_native.json`,
`output/mechanics/focus7/npc_native_state_labels.json`,
`docs/NPC_SOCIAL_FOLLOWUP.md`, and `docs/VILLAGER_SOCIAL_FOLLOWUP.md`. The
queue and previously written NPC files remain unchanged.
