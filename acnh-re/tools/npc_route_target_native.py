"""Original route lookahead/target selection and bounded controller setup.

Matched actor-reference context, routes and eligibility bitsets are prepared.
The eligible-bit meaning in a live island is not inferred from these tests.
"""
from collections import Counter
from pathlib import Path
import hashlib
import itertools
import json
import struct
from native_emulator import Sandbox, regs
from npc_pathfinding_native import RouteHarness
from npc_route_handoff_native import HandoffHarness
from unicorn import UC_HOOK_CODE

ROOT = Path(__file__).resolve().parent.parent


def main():
    s = Sandbox(); h = HandoffHarness(s); u, im = s.uc, s.image
    child, output, iterator, grid, bits_obj, bits = [s.HEAP+n for n in
                                                 (0x60000, 0x61000, 0x62000, 0xa0000, 0xa1000, 0xa2000)]
    params, endpoint_pointer = s.HEAP+0xa3000, s.HEAP+0xa3100
    source_ref = bytes(u.mem_read(im.ptr(0x32d1d60), 1))
    source_id = bytes(u.mem_read(im.ptr(0x32d1c88), 4))
    groups = {'full_default_target_selector': 0, 'full_route_lookahead_unfiltered': 0,
              'full_route_lookahead_bitset_filter': 0, 'controller_setup_blocks': 0,
              'native_search_extraction_target_chain': 0}
    outcomes = Counter(); samples = []
    def floats():
        return tuple(struct.unpack('<f', struct.pack('<I', u.reg_read(getattr(regs, 'UC_ARM64_REG_S'+str(i)))))[0] for i in range(3))
    def prepare_linear(n, target):
        h.prepare(n, max(n, 1))
        h.points = [(4+i, 5) for i in range(n+1)]
        for i, point in enumerate(h.points): u.mem_write(h.source+32*i, struct.pack('<2H', *point))
        h.source_snapshot = (h.source-16, bytes(u.mem_read(h.source-16, 32*(n+1)+32)))
        s.call(0x15c3570, (h.worker, h.list, h.output, h.token))
        route = list(reversed(h.list_state()))
        u.mem_write(child, bytes(0x200)); h.q(child+0xd0, h.list)
        u.mem_write(child+0xa0, source_ref); u.mem_write(child+0xa4, source_id)
        u.mem_write(child+0xec, struct.pack('<3f', *target))
        return route
    def world(point): return float(5*point[0]), 0., float(5*point[1])
    for n, target, direct, with_output in itertools.product([0, 1, 2, 9, 10, 11, 31],
            [(0., 0., 0.), (400., 7.5, 600.)], [False, True], [False, True]):
        route = prepare_linear(n, target); u.mem_write(child+0x121, bytes([direct]))
        u.mem_write(output, b'\xa5'*8)
        if direct: expected = target
        elif n >= 10: expected = world(route[9])
        elif any(target): expected = target
        else: expected = world(route[-1]) if route else (0., 0., 0.)
        before = bytes(u.mem_read(h.list, 0x30))+bytes(u.mem_read(h.pool, 48*h.capacity))
        s.call(0xc86650, (child, output if with_output else 0), limit=20000)
        assert floats() == expected, (n, target, direct, floats(), expected)
        assert bytes(u.mem_read(output, 4)) == (source_id if with_output else b'\xa5'*4)
        assert bytes(u.mem_read(output+4, 4)) == b'\xa5'*4
        assert before == bytes(u.mem_read(h.list, 0x30))+bytes(u.mem_read(h.pool, 48*h.capacity))
        groups['full_default_target_selector'] += 1
        if n in [9, 10, 11] and not direct and with_output and any(target):
            samples.append({'selector': '0xc86650', 'route_nodes': n, 'explicit_target': target, 'selected_world_xyz': expected})
    for n, budget, target in itertools.product([0, 1, 2, 9, 10, 11, 31],
            [0, 1, 2, 9, 10, 11, 31], [(0., 0., 0.), (400., 7.5, 600.)]):
        route = prepare_linear(n, target)
        patterns = {'unfiltered': set(range(n)), 'all': set(range(n)), 'none': set(),
                    'odd': {i for i in range(n) if i % 2 == 0}, 'last': {n-1} if n else set()}
        for pattern, eligible in patterns.items():
            filtered = pattern != 'unfiltered'
            u.mem_write(grid, bytes(0x50)); u.mem_write(grid, struct.pack('<2H', 4, 5))
            h.d(grid+0xc, n+1); h.d(grid+0x10, 1); h.q(grid+0x40, bits_obj)
            u.mem_write(bits_obj, bytes(0x30)); h.q(bits_obj+0x10, bits); h.d(bits_obj+0x1c, n+1)
            bitmap = sum(1 << (i+1) for i in eligible)
            u.mem_write(bits, struct.pack('<Q', bitmap)); h.q(child+0x10, grid)
            first = h.rq(h.list)-16; h.q(iterator, first)
            index = next((i for i in range(n) if i >= max(0, budget-1) and (not filtered or i in eligible)), None)
            if index is not None:
                expected = world(route[index])
                selected_iterator = h.pool+48*(n-1-index)
            else:
                last = next((i for i in reversed(range(n)) if not filtered or i in eligible), None)
                expected = target if any(target) else world(route[last]) if last is not None else (0., 0., 0.)
                selected_iterator = h.list-16
            before = bytes(u.mem_read(h.list, 0x30))+bytes(u.mem_read(h.pool, 48*h.capacity))
            s.call(0xc86970, (child, iterator, budget, int(filtered)), limit=30000)
            assert floats() == expected, (n, budget, pattern, floats(), expected)
            # Node pool allocation is sequential in the original extractor;
            # nearest-start is the final allocated node.
            assert h.rq(iterator) == selected_iterator
            assert before == bytes(u.mem_read(h.list, 0x30))+bytes(u.mem_read(h.pool, 48*h.capacity))
            groups['full_route_lookahead_bitset_filter' if filtered else 'full_route_lookahead_unfiltered'] += 1
            outcomes[pattern] += 1
            if n == 11 and budget == 10 and not any(target):
                samples.append({'selector': '0xc86970', 'route_nodes': n, 'budget': budget,
                                'eligibility': pattern, 'selected_world_xyz': expected})
    # Run controller setup from its real entry until it calls its route-state
    # evaluator. No state evaluator or movement/FSM callback is replaced.
    def stop_setup(uc, pc, size, data): uc.emu_stop()
    hook = u.hook_add(UC_HOOK_CODE, stop_setup, begin=0xc87710, end=0xc87710)
    setup_samples = []
    values = (0.5, 10., -1., -1., -1., 1.25, 2.5, -3.75)
    u.mem_write(params, struct.pack('<8f', *values))
    for n, target, explicit in itertools.product([0, 1, 11], [(0., 0., 0.), (400., 7.5, 600.)], [False, True]):
        prepare_linear(n, target); u.mem_write(endpoint_pointer, struct.pack('<3f', *target))
        u.reg_write(regs.UC_ARM64_REG_SP, s.STACK+0x1ff000)
        for i, value in enumerate([child, h.list, params if explicit else 0, endpoint_pointer]):
            u.reg_write(getattr(regs, 'UC_ARM64_REG_X'+str(i)), value)
        u.reg_write(regs.UC_ARM64_REG_LR, s.STOP)
        u.emu_start(0xc862b0, s.STOP, timeout=5_000_000, count=10000)
        assert u.reg_read(regs.UC_ARM64_REG_PC) == 0xc87710
        assert h.rq(child+0xd0) == h.list
        assert bytes(u.mem_read(child+0xec, 12)) == struct.pack('<3f', *target)
        assert bytes(u.mem_read(child+0x120, 4)) == bytes([explicit, bool(any(target)), 0, 0])
        assert bytes(u.mem_read(child+0x11e, 2)) == b'\x01\x00'
        assert h.rd(child+0x108) == 60
        effective = values[:5] if explicit else (16., 25., -1., -1., -1.)
        assert bytes(u.mem_read(child+0x18, 20)) == struct.pack('<5f', *effective)
        if explicit: assert bytes(u.mem_read(child+0x2c, 32)) == struct.pack('<8f', *values)
        groups['controller_setup_blocks'] += 1
        if n == 11:
            setup_samples.append({'route_nodes': n, 'explicit_parameter_argument': explicit,
                                  'target_enabled': bool(any(target)), 'effective_first_five_floats': effective})
    u.hook_del(hook)
    # Native search -> original extractor -> original unfiltered lookahead,
    # with no synthetic path replacement between these stages.
    search = RouteHarness(s); integration = []
    for width, height, start, goal in [(8, 8, (0, 0), (7, 7)), (32, 32, (0, 0), (31, 31)),
                                     (32, 32, (31, 31), (0, 0)), (4, 4, (2, 2), (2, 2))]:
        search.prepare(width, height); native = search.check_search(start, goal); path = native['path']
        h.prepare(len(path)-1, 64, native_path=path)
        s.call(0x15c3570, (h.worker, h.list, h.output, h.token))
        u.mem_write(child, bytes(0x200)); h.q(child+0xd0, h.list)
        target = world(goal); u.mem_write(child+0xec, struct.pack('<3f', *target))
        h.q(iterator, h.rq(h.list)-16)
        s.call(0xc86970, (child, iterator, 10, 0))
        expected = world(path[10]) if len(path) > 10 else target
        assert floats() == expected
        integration.append({'start': start, 'goal': goal, 'native_path_steps': len(path)-1,
                            'lookahead_budget': 10, 'selected_world_xyz': expected})
        groups['native_search_extraction_target_chain'] += 1
    result = {'cases': sum(groups.values()), 'groups': groups, 'mismatches': [],
              'samples': samples, 'setup_samples': setup_samples, 'native_pipeline_samples': integration,
              'eligibility_patterns_tested': dict(outcomes),
              'native_functions': {'default_target_selector': '0xc86650', 'route_lookahead': '0xc86970',
                                   'bitset_test': '0x166ab50', 'grid_to_world': '0x52b4c0',
                                   'controller_setup_entry': '0xc862b0', 'setup_stop_before': '0xc87710'},
              'rules': ['For matched target-reference context,0xc86650 returns explicit target if byte+0x121 is set. Otherwise it selects the10th route node; a shorter exhausted route uses the nonzero explicit endpoint or the last converted node.',
                        'Route coordinates map to X/Z*5.0; Y stays at the native zero-vector value on route-node conversion. An explicit endpoint preserves its Y.',
                        '0xc86970 unfiltered mode selects max(1,budget)-th node. Filtered mode returns the first eligible node at or after that position; the budget counts visited nodes, including ineligible ones.',
                        'Eligibility mode uses a bounded grid coordinate check and a real native bitset lookup. Its live-world bit meaning is not assigned here.',
                        'Selection updates the iterator but does not unlink route nodes. On exhaustion, an explicit nonzero endpoint takes precedence over the last eligible converted node.',
                        'Controller setup copies32 parameter bytes when provided; effective first five float defaults on the null-argument path are16,25,-1,-1,-1; list/target and flags are set before calling0xc87710.'],
              'scope': 'Complete original target/lookahead functions on matched-reference routes and prepared eligibility grids, plus a bounded controller setup block and four native search/extraction/lookahead chains.',
              'limits': ['Other actor-reference resolution branches in0xc86650 are not executed.',
                         'Eligibility mask generation from terrain/collision is not run; this does not prove obstacle avoidance, line of sight or a steering solver.',
                         'Controller setup stops before0xc87710; active state decisions, steering and position integration remain unproven.',
                         'Parameter copy/default values are instruction-derived; all eight parameter meanings, units and reachable gameplay values are not assigned.'],
              'source_reference': ['mechanics/npc_pathfinding_native.json', 'mechanics/npc_route_handoff_native.json'],
              'dependencies_stubbed': [], 'elf_sha256': hashlib.sha256(im.data).hexdigest()}
    (ROOT/'output/mechanics/npc_route_target_native.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({'cases': result['cases'], 'groups': groups, 'mismatches': 0}), flush=True)


if __name__ == '__main__': main()
