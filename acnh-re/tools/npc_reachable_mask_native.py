"""Original reachable-bitset flood and wrapper on reconstructed native graphs.

An independent queue traversal checks the produced bitset. Terrain inputs,
header/pool state and the controller-to-bitset binding are explicitly prepared.
"""
from collections import Counter
from pathlib import Path
import hashlib
import itertools
import json
import random
import struct
from native_emulator import regs
from native_sdk_memory import install_sdk_memory
from npc_pathfinding_native import STEPS
from npc_route_handoff_native import HandoffHarness
from terrain_nav_flags_native import WorldHarness

ROOT = Path(__file__).resolve().parent.parent


def main():
    h = WorldHarness(); s, u, im = h.s, h.u, h.im
    sdk = install_sdk_memory(s)
    bit_object, bit_data = s.HEAP+0x150000, s.HEAP+0x151000
    groups = {'native_flood_against_queue': 0, 'native_wrapper_against_queue': 0,
              'terrain_producer_to_flood': 0, 'native_mask_to_lookahead': 0}
    rng = random.Random(0x15bf150); scenarios = []
    scenarios.append({'name': 'open', 'blocked': set()})
    scenarios.append({'name': 'full_wall', 'blocked': {(4, z) for z in range(8)}})
    scenarios.append({'name': 'wall_gap', 'blocked': {(4, z) for z in range(8) if z != 6}})
    scenarios.append({'name': 'blocked_start', 'blocked': {(3, 3)}})
    for i in range(24):
        scenarios.append({'name': f'random_{i}', 'blocked': {(x, z) for x in range(8) for z in range(8) if rng.random() < .25}})
    scenarios += [{'name': 'terrain_'+name, 'blocked': set(), 'terrain': True, 'barrier': barrier, 'gap': gap}
                  for name, barrier, gap in [('flat', False, False), ('wall', True, False), ('gap', True, True)]]
    samples = []; selector_samples = []; outcomes = Counter()
    for scenario in scenarios:
        h.reset()
        for point in sorted(scenario['blocked']):
            s.call(0x15bc2e0, (h.graph, *point, 0), limit=100000)
        if scenario.get('terrain'):
            for point in sorted(h.cells):
                height = 5. if scenario['barrier'] and point[0] == 4 and not (scenario['gap'] and point[1] == 6) else 0.
                u.mem_write(h.tile(point), struct.pack('<12f', *([height]*12)))
            for point in sorted(h.cells): h.write_heights(point)
            s.call(0x15bc200, (h.graph, h.context), limit=2_000_000)
        source_nodes = bytes(u.mem_read(h.nodes, 40*64))
        source_fields = {point: tuple(source_nodes[40*(point[0]+8*point[1])+i] for i in [4,5,6]) for point in h.cells}
        for wrapped, requested in itertools.product([False, True], [(-1, -1), (3, 3), (10, 10)]):
            u.mem_write(h.nodes, source_nodes)
            h.q(h.graph+0x40, bit_object); u.mem_write(h.graph+0x48, b'\0')
            u.mem_write(bit_object, bytes(0x30)); h.d(bit_object+0xc, 2)
            h.q(bit_object+0x10, bit_data); h.d(bit_object+0x1c, 8)
            u.mem_write(bit_data-16, b'\xa5'*16+b'\xff'*8+b'\xa5'*16)
            start = tuple(max(0, min(7, value)) for value in requested)
            masks = {point: value[0] for point, value in source_fields.items()}
            # Repair uses the raw requested coordinate. Clamping happens only
            # later inside the flood, so an outside request is not repaired.
            if wrapped and requested in h.cells and masks[start] == 0:
                reciprocal = [1, 0, 3, 2, 5, 4, 7, 6]
                for i, (dx, dz) in enumerate(STEPS):
                    other = start[0]+dx, start[1]+dz
                    if other in h.cells and source_fields[other][2] != 3 and masks[other] and not source_fields[other][1] & (1 << reciprocal[i]):
                        masks[start] |= 1 << i
                        masks[other] |= 1 << reciprocal[i]
            expected = set(); queued = {start}; todo = [start]
            if source_fields[start][2] == 3: todo = []
            while todo:
                point = todo.pop(); _, flags, state = source_fields[point]; mask = masks[point]
                permitted = (point == start or not wrapped or bool(mask & 0x10) or
                             point[0] != 0 and point[1] != 0 and not flags & 0x10)
                if not permitted: continue
                expected.add(point)
                for i, (dx, dz) in enumerate(STEPS):
                    other = point[0]+dx, point[1]+dz
                    if mask & (1 << i) and other in h.cells and other not in queued:
                        queued.add(other); todo.append(other)
            s.call(0x15bf840 if wrapped else 0x15bf150,
                   (h.graph, requested[0] & 0xffffffff, requested[1] & 0xffffffff, 0), limit=1_000_000)
            wanted_bits = sum(1 << (x+8*z) for x, z in expected)
            actual_bits = struct.unpack('<Q', u.mem_read(bit_data, 8))[0]
            assert actual_bits == wanted_bits, (scenario['name'], wrapped, requested, hex(actual_bits), hex(wanted_bits))
            assert h.rd(bit_object+0x18) == len(expected)
            for point in h.cells:
                actual_fields = bytes(u.mem_read(h.node(point)+4, 2))
                assert actual_fields == bytes([masks[point], source_fields[point][1]]), (scenario['name'], wrapped, requested, point, actual_fields.hex(), masks[point], source_fields[point])
            assert bytes(u.mem_read(bit_data-16, 8+32)) == b'\xa5'*16+struct.pack('<Q', wanted_bits)+b'\xa5'*16
            assert bytes(u.mem_read(h.graph+0x48, 1)) == b'\0'
            groups['native_wrapper_against_queue' if wrapped else 'native_flood_against_queue'] += 1
            if scenario.get('terrain'): groups['terrain_producer_to_flood'] += 1
            outcomes[f'{"wrapped" if wrapped else "plain"}:{len(expected)}'] += 1
            if not scenario['name'].startswith('random_'):
                samples.append({'scenario': scenario['name'], 'wrapped': wrapped, 'requested_start': requested,
                                'clamped_start': start, 'reachable_count': len(expected), 'bitset_hex': f'{wanted_bits:016x}'})
            if scenario['name'] in ['open', 'full_wall', 'wall_gap', 'terrain_wall'] and requested == (3, 3):
                # Configure the documented controller/grid binding explicitly.
                # The eligibility bits themselves come from the original flood.
                route = HandoffHarness(s); route.prepare(7, 8)
                points = [(i, 3) for i in range(8)]
                for i, point in enumerate(points): u.mem_write(route.source+32*i, struct.pack('<2H', *point))
                route.source_snapshot = None
                s.call(0x15c3570, (route.worker, route.list, route.output, route.token))
                child, iterator = route.child, s.HEAP+0x62000
                u.mem_write(child, bytes(0x200)); route.q(child+0x10, h.graph); route.q(child+0xd0, route.list)
                route.q(iterator, route.rq(route.list)-16)
                candidates = points[1:]
                selected = next((point for i, point in enumerate(candidates) if i >= 2 and point in expected), None)
                if selected is None: selected = next((point for point in reversed(candidates) if point in expected), None)
                wanted_xyz = (5.*selected[0], 0., 5.*selected[1]) if selected else (0., 0., 0.)
                s.call(0xc86970, (child, iterator, 3, 1), limit=20000)
                actual_xyz = tuple(struct.unpack('<f', struct.pack('<I', u.reg_read(getattr(regs, 'UC_ARM64_REG_S'+str(i)))))[0] for i in range(3))
                assert actual_xyz == wanted_xyz
                selector_samples.append({'scenario': scenario['name'], 'wrapped': wrapped,
                                         'selected_world_xyz': actual_xyz, 'reachable_count': len(expected)})
                groups['native_mask_to_lookahead'] += 1
    # terrain_producer_to_flood labels a subset of the comparisons above and
    # must not be added twice to the case total.
    subset_cases = groups.pop('terrain_producer_to_flood')
    result = {'cases': sum(groups.values()), 'groups': groups, 'mismatches': [],
              'terrain_originated_comparisons_subset': subset_cases,
              'samples': samples, 'lookahead_samples': selector_samples, 'outcomes': dict(outcomes),
              'native_functions': {'flood': '0x15bf150', 'source_repair_wrapper': '0x15bf840',
                                   'source_repair': '0x15bf8a0', 'bitset_clear': '0x166aad0',
                                   'bitset_set': '0x166ac00', 'lookahead': '0xc86970'},
              'oracle': 'Independent queue traversal using source direction masks and the wrapper expansion predicate; compare every bit, popcount and guards.',
              'rules': ['Out-of-range start coordinates are clamped to the grid. A start node in state3 produces an empty bitset after clearing.',
                        'Plain flood marks and expands nodes reached through direction-mask bits, without using the A* destination flag0xf5 test.',
                        'The wrapper first attempts zero-mask repair at the raw requested coordinate, before flood clamping. It restores reciprocal edges to nonblocked neighbors with nonzero masks and permissive reciprocal flags. It enables a special expansion condition after the first node: direction bit4, or both coordinates differ from the origin and node flag4 is clear. It resets its enable byte before return.',
                        'Original SDK memset clears the bitset. Original bit-set helper increments the count only on a newly set bit.',
                        'Explicitly wired controller tests consume the native-produced bitset with the original filtered lookahead; original world constructor wiring is not claimed.'],
              'scope': 'Complete original flood/wrapper on declared graphs, including terrain-produced graphs and a composed mask-to-lookahead boundary.',
              'limits': ['Constraint predicate argument is null. Nonempty actor predicates and every live-world eligibility use remain open.',
                         'Wrapper repair is modeled and compared on these scenarios; one-cell dimensions, wrapped coordinate ranges and arbitrary callback predicates are not covered.',
                         'Prepared headers, pools and controller binding are not a full worker/world constructor. No async scheduling or steering executes.',
                         'Reachability bitsets and A* passability differ; this test does not assign a universal walkable/obstacle name to the bitset.'],
              'source_reference': ['mechanics/terrain_nav_flags_native.json', 'mechanics/npc_route_target_native.json'],
              'sdk': sdk, 'dependencies_stubbed': [], 'elf_sha256': hashlib.sha256(im.data).hexdigest()}
    (ROOT/'output/mechanics/npc_reachable_mask_native.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({'cases': result['cases'], 'groups': groups, 'terrain_subset': subset_cases, 'mismatches': 0}), flush=True)


if __name__ == '__main__': main()
