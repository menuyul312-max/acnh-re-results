"""Verify Stage-task dispatch and guarded entry into dynamic-ground selection."""
from pathlib import Path
import hashlib
import itertools
import json
import struct
from native_emulator import Sandbox
from unicorn import UC_HOOK_CODE

ROOT = Path(__file__).resolve().parent.parent


def main():
    s = Sandbox(); u = s.uc
    task_manager, task_context, stage_manager, registry, world, position = [
        s.HEAP + n for n in (0x10000, 0x20000, 0x30000, 0x40000, 0x50000, 0x60000)]
    def q(p, v): u.mem_write(p, struct.pack('<Q', v))
    def d(p, v): u.mem_write(p, struct.pack('<I', v))
    vtable = s.image.ptr(0x32d0838) + 16
    assert vtable == 0x301c990
    q(registry, vtable)
    q(s.image.ptr(0x32d08d8), registry)
    count = s.call(s.image.ptr(vtable+0x10), (registry,))
    assert count == 2
    entries = []
    for index in range(count):
        record = s.call(s.image.ptr(vtable+0x18), (registry, index))
        name = s.image.cstring(s.image.ptr(record))
        entries.append({'index': index, 'descriptor_va': hex(record),
                        'name_va': hex(s.image.ptr(record)), 'name': name})
    assert [r['name'] for r in entries] == ['SceneBoot', 'Stage']
    observed = set()
    watched = {0x157ab0, 0x880ff0, 0x18adf0}
    def trace(uc, address, size, data):
        if address in watched: observed.add(address)
    hook = u.hook_add(UC_HOOK_CODE, trace)
    groups = {'stage_gate_chain': 0, 'dynamic_dispatch_guards': 0}
    for index, exists, context_exists, stage_exists, state in itertools.product(
            [0, 1], [False, True], [False, True], [False, True], [0, 1, 256, 0xffffffff]):
        q(s.image.ptr(0x32d0c88), task_manager if exists else 0)
        q(task_manager+0x330, task_context if context_exists else 0)
        d(task_manager+0x338, index); d(task_context+0x244, state)
        q(s.image.ptr(0x32d71a0), stage_manager if stage_exists else 0)
        expected = state if exists and context_exists and index == 1 else 0
        assert s.call(0xfef6b0, limit=10000) == expected
        assert s.call(0x880740, limit=12000) == int(stage_exists and expected != 0)
        groups['stage_gate_chain'] += 1
    q(s.image.ptr(0x32d0c88), task_manager); q(task_manager+0x330, task_context)
    q(s.image.ptr(0x32d71a0), stage_manager)
    # A real empty item word selects the native early-return path inside the
    # active selector. No replacement of that function is installed.
    u.mem_write(stage_manager+0xa58, struct.pack('<Q', 0xfffe))
    original_buffers = {}
    for index, state, has_world, has_inner, disabled in itertools.product(
            [0, 1], [0, 1], [False, True], [False, True], [0, 1, 255]):
        d(task_manager+0x338, index); d(task_context+0x244, state)
        q(s.image.ptr(0x32d0de8), world if has_world else 0)
        q(world+0xa0, world+0x2000 if has_inner else 0)
        u.mem_write(world+0xf60, bytes([disabled]))
        original_buffers = {p: bytes(u.mem_read(p, size)) for p, size in
                            [(task_manager, 0x400), (task_context, 0x300),
                             (stage_manager, 0xc00), (world, 0x1000), (position, 12)]}
        observed.clear()
        assert s.call(0x18b570, (position,), limit=30000) == 7
        should_enter = index == 1 and state != 0 and has_world and has_inner and disabled == 0
        assert (0x157ab0 in observed) == should_enter
        assert (0x880ff0 in observed) == should_enter
        assert 0x18adf0 not in observed
        for p, before in original_buffers.items(): assert bytes(u.mem_read(p, len(before))) == before
        groups['dynamic_dispatch_guards'] += 1
    u.hook_del(hook)
    result = {
        'native_functions': ['0xfef6b0', '0x880740', '0x18b570'],
        'callees_executed': ['0x1f027b0', '0x1f02870', '0xa8a0', '0x1bf0',
                             '0x157ab0 (empty-item branch)', '0x880ff0', '0x878230'],
        'groups': groups, 'cases': sum(groups.values()), 'mismatches': [],
        'task_registry': {'vtable': hex(vtable), 'entries': entries,
                          'evidence': 'Root vtable 0x301c5b8 includes initializer 0x5ca0; slot+0x38 is 0x5950, which installs *(0x32d0838)+16. Initializer stores that result through GOT 0x32d08d8 at0x5f54.',
                          'count_getter': '0xa890', 'entry_getter': '0xa8a0',
                          'entry_contract': 'Readonly base0x301c950 + signed(index)*24. Getter itself does not check bounds.'},
        'stage_hash': '758f7eaf', 'hash_algorithm': 'Murmur3_32_seed0 (original0x1bf0)',
        'rules': [
            '0xfef6b0 returns context+0x244 u32 only when the current task name hashes to Stage; otherwise0.',
            '0x880740 additionally requires a non-null stage-manager global and converts that u32 to boolean.',
            '0x18b570 returns7 unless this gate succeeds, the world pointer and world+0xa0 pointer exist, and world+0xf60 byte is0.',
            'When those guards pass it enters original0x157ab0. Empty context item0xfffe returns7 inside that selector.'
        ],
        'reconstructed_state': ['Task-manager/context, Stage-manager and world memory',
                                'Original registry vtable on its8-byte instance; original readonly task descriptors unchanged'],
        'dependencies_stubbed': [], 'code_hooks': 'Observation of function entry only; no register or instruction changes.',
        'limits': ['Positive selector path with nonempty context item, actual template/map choice and fallback attributes not executed.',
                   'Task scheduler, constructors, allocation and lifecycle transitions not executed.',
                   'Only the two valid task indices were dereferenced.'],
        'elf_sha256': hashlib.sha256(s.image.data).hexdigest()
    }
    (ROOT/'output/mechanics/ground_context_gate_native.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({'groups': groups, 'cases': result['cases'], 'mismatches': 0}), flush=True)


if __name__ == '__main__': main()
