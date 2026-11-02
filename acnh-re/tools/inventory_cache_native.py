"""Build all three material-counter groups with original native producers.

Record inputs and pools are reconstructed; real item definitions and original
SDK memset execute. Save-wrapper acquisition and item consumption are separate.
"""
from pathlib import Path
from collections import Counter
import hashlib
import itertools
import json
import struct
import zlib
from native_emulator import Sandbox, regs
from inventory_requirements_native import install_item_tables
from native_sdk_memory import install_sdk_memory

ROOT = Path(__file__).resolve().parent.parent
COMPONENTS = {
    'A': {'offset': 0x10, 'loader': 0xeda040, 'vtable_got': 0x32fe530,
          'producer': 0xee72b0, 'slots_copied': 20, 'limit': 20, 'count': 0xb0,
          'normal': 0x2d0, 'counters': 0x2f8, 'list': 0xd0, 'size': 0x7828},
    'B': {'offset': 0x7838, 'loader': 0xeda160, 'vtable_got': 0x32fe528,
          'producer': 0xee7550, 'slots_copied': 20, 'limit': 20, 'count': 0xb0,
          'normal': 0x2d0, 'counters': 0x2f8, 'list': 0xd0, 'size': 0x7828},
    'C': {'offset': 0xf060, 'loader': 0xeda280, 'vtable_got': 0x32fe520,
          'producer': 0xee7800, 'slots_copied': 5000, 'limit': 1600, 'count': 0x9c50,
          'normal': 0x13340, 'counters': 0x13fc0, 'list': 0x9d20, 'size': 0x1b4f0}}


def main():
    s = Sandbox(); u = s.uc; tables = install_item_tables(s)
    sdk = install_sdk_memory(s)
    ip, ic = tables['item_table'], tables['item_cols']
    kt, kc = tables['kind_table'], tables['kind_cols']
    kind_by_hash = {zlib.crc32(r[kc['Label']].encode()): r for r in kt['rows']}
    items = {row[ic['UniqueID']]: row for row in ip['rows']}
    def max_stack(uid): return kind_by_hash[int(items[uid][ic['ItemKind']]['hash'], 16)][kc['MultiHoldMaxNum']]
    def quantity(word):
        uid, system, free = struct.unpack('<HHI', word)
        if uid == 0xfffe: return 0
        assert system == 0 and items[uid][ic['RemakeID']] == -1
        limit = max_stack(uid)
        count = ((free & 65535)+1) & 255
        return 1 if limit < 2 or count > limit else count
    def word(uid, free=0): return struct.pack('<HHI', uid, 0, free)
    empty = struct.pack('<Q', 0xfffe)
    selected = [2511, 5983, 2624, 109]
    assert [max_stack(uid) for uid in selected] == [30, 10, 99, 0]
    cache = s.HEAP+0x40000; source = s.HEAP+0xa0000
    requirement = s.HEAP+0xd0000; handle = s.HEAP+0xe0000
    u.mem_write(handle, b'\xff'+bytes(7))
    def d(p, v): u.mem_write(p, struct.pack('<I', v & 0xffffffff))
    def q(p, v): u.mem_write(p, struct.pack('<Q', v))
    def h(p, v): u.mem_write(p, struct.pack('<H', v & 65535))
    groups = {'source_A': 0, 'source_B': 0, 'source_C': 0, 'producer_to_requirement': 0}
    samples = []; list_mask_cases = 0; wrap_samples = []

    def build(name, words, count, mask=0):
        nonlocal list_mask_cases
        spec = COMPONENTS[name]; obj = cache+spec['offset']
        assert len(words) == spec['slots_copied']
        u.mem_write(obj, bytes(spec['size']))
        vt = s.image.ptr(spec['vtable_got'])+16
        assert s.image.ptr(vt+0x40) == spec['producer']
        q(obj, vt)
        # A genuine native vtable uses reconstructed free-list/pointer-array
        # storage. No allocator or producer callback is replaced.
        index = 'ABC'.index(name)
        pointers = 0x51a00000+index*0x20000
        nodes = pointers+0x4000
        list_base = obj+spec['list']; d(list_base, 0); d(list_base+4, spec['limit'])
        q(list_base+8, pointers); q(list_base+16, nodes)
        for i in range(spec['limit']): q(nodes+16*i, nodes+16*(i+1) if i+1 < spec['limit'] else 0)
        u.mem_write(obj+spec['normal'], b'\xcc'*(spec['limit']*2))
        raw = b''.join(words)+struct.pack('<I', count & 0xffffffff)
        if name in ('A', 'B'): raw += bytes(16)+struct.pack('<I', mask)
        before = raw; u.mem_write(source, raw)
        try: s.call(spec['loader'], (obj, source), limit=5000000)
        except Exception as error:
            raise RuntimeError(f'{name=}, {count=}, PC={u.reg_read(regs.UC_ARM64_REG_PC):#x}: {error}') from error
        active = min(count & 0xffffffff, spec['limit'])
        totals = Counter()
        for w in words[:active]:
            uid = struct.unpack_from('<H', w)[0]
            if uid != 0xfffe: totals[uid] += quantity(w)
        expected = bytearray(30000)
        for uid, amount in totals.items(): struct.pack_into('<H', expected, uid*2, amount & 65535)
        assert bytes(u.mem_read(obj+spec['counters'], 30000)) == expected, (name, count, totals)
        actual_normal = bytes(u.mem_read(obj+spec['normal'], 2*spec['limit']))
        expected_normal = b''.join(w[:2] for w in words[:active])+b'\xcc'*(2*(spec['limit']-active))
        assert actual_normal == expected_normal, (name, count, 'normalized')
        assert bytes(u.mem_read(obj+0x10, 8*spec['slots_copied'])) == b''.join(words)
        assert bytes(u.mem_read(source, len(before))) == before
        assert struct.unpack('<I', u.mem_read(list_base, 4))[0] == 0, (name, count, 'loader resets list')
        if name in ('A', 'B'):
            assert struct.unpack('<I', u.mem_read(obj+0xc8, 4))[0] == 0
            assert struct.unpack('<I', u.mem_read(obj+0xc4, 4))[0] == mask
        if mask:
            # The copy loader clears the cache's slot mask. Test its separate
            # marked-slot producer branch after that real initialization.
            memset = int(sdk['bindings']['memset']['emulated_va'], 16)
            s.call(memset, (obj+spec['counters'], 0, 30000), limit=10000)
            d(obj+0xc8, mask)
            s.call(spec['producer'], (obj,), limit=1000000)
            assert bytes(u.mem_read(obj+spec['counters'], 30000)) == expected
        selected_slots = [i for i in range(active) if name in ('A', 'B') and mask & (1 << i)]
        assert struct.unpack('<I', u.mem_read(list_base, 4))[0] == len(selected_slots), (name, count, mask, 'marked list')
        for i, slot in enumerate(selected_slots):
            ptr = struct.unpack('<Q', u.mem_read(pointers+8*i, 8))[0]
            assert struct.unpack('<I', u.mem_read(ptr, 4))[0] == slot
            assert bytes(u.mem_read(ptr+4, 8)) == words[slot]
            assert bytes(u.mem_read(ptr+12, 1)) == b'\0'
        if selected_slots: list_mask_cases += 1
        return totals

    for name, uid in itertools.product(['A', 'B'], selected):
        maximum = max_stack(uid)
        for free, count, mask in itertools.product(list(dict.fromkeys([0, 1, max(0, maximum-1), maximum, 255, 256])),
                                                   [0, 1, 19, 20, 21, 0xffffffff], [0, 0xfffff]):
            words = [empty if i % 5 == 4 else word(uid, free) if i % 3 == 0
                     else word(2511, i % 30) if i % 3 == 1 else word(5983, i % 10)
                     for i in range(20)]
            build(name, words, count, mask); groups['source_'+name] += 1
    for uid in selected:
        maximum = max_stack(uid)
        for free, count in itertools.product(list(dict.fromkeys([0, max(0, maximum-1), maximum, 255])),
                                             [0, 1, 1599, 1600, 1601, 5000, 0xffffffff]):
            words = [word(uid, free)]*5000
            totals = build('C', words, count); groups['source_C'] += 1
            if totals.get(uid, 0) > 65535:
                wrap_samples.append({'item': uid, 'free_param': free, 'source_count': count,
                                     'mathematical_sum': totals[uid], 'u16_counter': totals[uid] & 65535})
    for a, b, c in [(0, 0, 0), (5, 10, 15), (30, 30, 30)]:
        for name, amount in zip('ABC', [a, b, c]):
            spec = COMPONENTS[name]
            words = ([word(2511, amount-1)] if amount else [])
            words += [empty]*(spec['slots_copied']-len(words))
            build(name, words, int(amount != 0))
        u.mem_write(cache+8, b'\x01')
        cache_before = bytes(u.mem_read(cache, 0x2a550))
        for needed, include_c, initial in itertools.product([0, 1, 14, 15, 16, 31, 91, 65535], [0, 1], [0, 1]):
            u.mem_write(requirement, bytes(0xb0)); u.mem_write(requirement+0x25, bytes([initial]))
            entry = requirement+0x2c; u.mem_write(entry, word(2511)); h(entry+8, needed)
            s.call(0xee0be0, (cache, requirement, handle, 0, include_c), limit=30000)
            available = (a+b+(c if include_c else 0)) & 65535
            expected_flag = initial if needed == 0 or available >= needed else 0
            assert bytes(u.mem_read(requirement+0x25, 1)) == bytes([expected_flag])
            if needed:
                assert struct.unpack('<3H', u.mem_read(entry+10, 6)) == (c if include_c else 0, a, b)
            assert bytes(u.mem_read(cache, len(cache_before))) == cache_before
            groups['producer_to_requirement'] += 1
        samples.append({'A': a, 'B': b, 'C': c, 'item': 2511})
    result = {
        'groups': groups, 'cases': sum(groups.values()), 'mismatches': [],
        'native_components': {name: {**spec, 'vtable': hex(s.image.ptr(spec['vtable_got'])+16)} for name, spec in COMPONENTS.items()},
        'source_item_ids': selected,
        'source_item_stack_limits': {str(uid): max_stack(uid) for uid in selected},
        'cases_with_selected_slot_nodes': list_mask_cases, 'u16_wrap_samples': wrap_samples,
        'source_to_requirement_samples': samples,
        'rules': ['A/B copy20 item words and scan min(u32 count,20); C copies5000 and scans min(u32 count,1600).',
                  'Native item validity/normalization and MultiHoldMaxNum/FreeParam stack readers populate 15000 u16 counters per group.',
                  'For the selected unwrapped normal items with stack limit>=2, quantity is((low16 FreeParam+1)&255); above-limit quantity falls back to1. Nonstack items count as1.',
                  'Counter additions wrap modulo65536. Source records are not modified.',
                  'The copy loaders clear the cache slot mask/list. Separately marking A/B cache slots and rebuilding creates a slot/item node list without subtracting them from the counters.',
                  'Counters produced by these loaders feed the original requirement checker0xee0be0, without manually assigning counter totals.'],
        'dependencies_stubbed': [], 'sdk': sdk,
        'reconstructed_state': ['Original cache component vtables from constructor0xed8870',
                                'Source-layout item records/count/metadata and preallocated node pools',
                                'Real original ItemParam/ItemKind blobs, metadata and native enum order'],
        'limits': ['Save-wrapper acquisition and the parent cold-cache path of0xee0be0 are not executed.',
                   'A/B/C are structural names; user-facing pocket/storage names require a validated save-member binding.',
                   'Wrapped/remade items, special save-count branches and all invalid item types are not covered.',
                   'No ingredient removal, result award, rollback, unlock or durability operation is claimed.'],
        'source_tables': {name: {'json': f'tables_resolved/{name}.json', 'source_id': t['source_id'], 'raw': t['raw']}
                          for name, t in [('ItemParam', ip), ('ItemKind', kt)]},
        'elf_sha256': hashlib.sha256(s.image.data).hexdigest()
    }
    (ROOT/'output/mechanics/inventory_cache_native.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({'groups': groups, 'cases': result['cases'], 'mismatches': 0}), flush=True)


if __name__ == '__main__': main()
