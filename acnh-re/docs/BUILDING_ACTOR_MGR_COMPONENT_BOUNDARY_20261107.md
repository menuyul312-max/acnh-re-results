# Building component search: actor-manager boundary

This follow-up checks whether the registered `NpcActorMgr` path can explain the
`NpcActor` object's `+0x68` component consumed by the building-coordinate
callback. It does not find that attachment. The main result is a firm type and
dispatch separation: `NpcActorMgr` is a large actor manager that constructs
actor-request records, while the `NpcActor` instance has its own smaller
registration and outer vptr. The manager path must not be used as the missing
`actor+0x68` setter.

## Two distinct registered objects

`_INIT_2780` at `0xbecc50` registers the class name `NpcActor` with allocation
size `0x618` and factory/constructor address `0xbe5e40`. Its base-init chain
`0xbe5e40 → 0x7bbe20 → 0x27c70` clears offsets `+0x68/+0x70`; its outer vptr
address point is `0x30d58a0`. The previously published
[`BUILDING_SITE_COMPONENT_VPTR_LIFECYCLE_BOUNDARY_20261107.md`](BUILDING_SITE_COMPONENT_VPTR_LIFECYCLE_BOUNDARY_20261107.md)
records the exact PCs, relocations, and coordinate-call boundary.

`_INIT_2810` at `0xc71bf0` separately registers `NpcActorMgr` with size
`0x10780` and factory `0xc67fa0`. The factory allocates that manager object
and calls constructor `0xc67ff0`; this constructor calls the common base
initializer and installs the distinct outer table at `0x30d9a50`. The manager
table entry at `0x30d9a88` (`+0x38`) targets `0xc685a0`, which calls
`0xc70da0`. That builder assembles first-live actor data (`E_FirstLive_NPC_0`,
`AI_NPC_Tkk_FirstLive`) and submits actor requests through `0xc6c210`.

The stage actor registry also lists `NpcActorMgr` as a separate registered
actor kind (index 5). This evidence identifies a manager/actor-request path;
it does not show an instance of the `NpcActor` class receiving a component.

## Bounded writer check

The checked `NpcActorMgr` constructor pseudocode has no explicit post-base
assignment to its receiver `+0x68`. The `0xc70da0` builder and its
`0xc6c210` request-submission routine contain no explicit receiver `+0x68`
store. These are bounded decompilation observations, not proof about every
indirect runtime factory. They also concern the manager object and its request
payload, not the `NpcActor` receiver used by `0xbe6340/0xbe6480`.

The `NpcActor` constructor/base initializer still only proves that its own
`+0x68` starts null. The later writer, concrete inner vptr, `+0x128` target,
final transform, footprint/terrain validator, preview-to-built actor binding,
and persistence edge remain **OPEN**. No physical placement or runtime object
was executed.

## Reproducibility

Source file hashes, object sizes, registrations, table entries, and bounded
checks are recorded in
[`building_actor_mgr_component_boundary_20261107.json`](../output/gameplay/building_actor_mgr_component_boundary_20261107.json).
All VAs are raw `main.elf` addresses. The `main.elf` SHA-256 is
`5bf707c3dc5dac0ad9635af7d336ec580f81c3f7876d0f55400d1900e3415d74`.
