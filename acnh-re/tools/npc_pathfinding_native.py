"""Execute the original grid A* kernel and its original cost/heuristic callbacks.

Grid cells, cost classes and weights are reconstructed inputs. World obstacle
production, async scheduling and movement are outside this kernel experiment.
"""
from pathlib import Path
from collections import Counter
import hashlib
import heapq
import json
import math
import random
import struct

from native_emulator import Sandbox, regs
from unicorn import UC_HOOK_CODE

ROOT = Path(__file__).resolve().parent.parent
STEPS = [(-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, 1), (1, -1), (-1, 1)]
WEIGHTS = [1., 1.25, 2., 3., 5., 8., 13., 21.]


def f32(x): return struct.unpack('<f', struct.pack('<f', x))[0]
def packed(p): return ((p[1] & 0xffff) << 16) | (p[0] & 0xffff)


class RouteHarness:
    def __init__(self, sandbox=None):
        self.s = sandbox or Sandbox(); self.u = self.s.uc; self.im = self.s.image
        self.graph = self.im.ptr(0x3311420)
        self.nodes, self.functor = self.s.HEAP+0x80000, self.s.HEAP+0x90000
        self.cost_grid, self.cost_weights = self.im.ptr(0x3311428), self.im.ptr(0x3311440)
        self.u.mem_write(self.cost_grid, bytes(0x48000))
        self.u.mem_write(self.cost_weights, struct.pack('<8f', *WEIGHTS))
        self.u.mem_write(self.functor, bytes(24))
        self.q(self.functor, self.im.ptr(0x3311460)+16)
        assert self.im.ptr(self.im.ptr(0x3311460)+16) == 0x15c38a0
        assert self.im.ptr(self.im.ptr(0x3311460)+24) == 0x15c1610

    def q(self, p, value): self.u.mem_write(p, struct.pack('<Q', value))
    def d(self, p, value): self.u.mem_write(p, struct.pack('<I', value & 0xffffffff))
    def rq(self, p): return struct.unpack('<Q', self.u.mem_read(p, 8))[0]
    def rd(self, p): return struct.unpack('<I', self.u.mem_read(p, 4))[0]

    def prepare(self, width, height, origin=(0, 0), blocked=(), flags=None, classes=None):
        assert 0 < width <= 32 and 0 < height <= 32
        self.width, self.height, self.origin = width, height, origin
        self.cells = {(origin[0]+x, origin[1]+z) for x in range(width) for z in range(height)}
        self.blocked, self.flags, self.classes = set(blocked), flags or {}, classes or {}
        self.u.mem_write(self.graph, bytes(0x50))
        self.u.mem_write(self.graph, struct.pack('<2H', *origin))
        self.d(self.graph+0xc, width); self.d(self.graph+0x10, height)
        self.q(self.graph+0x18, width*height); self.q(self.graph+0x20, self.nodes)
        self.u.mem_write(self.nodes-16, b'\xa5'*16+bytes(40*width*height)+b'\xa5'*16)
        self.s.call(0x15bc0c0, (self.graph,), limit=100000)
        for point in self.cells:
            node = self.node(point)
            assert struct.unpack('<2H', self.u.mem_read(node, 4)) == point
            # Native initialization uses first-edge/else-last-edge branches.
            # A one-cell dimension therefore retains outward bits; expansion
            # still checks coordinate bounds before reading a neighbor.
            expected_mask = 0x6e if point[0] == origin[0] else 0x9d if point[0] == origin[0]+width-1 else 0xff
            if point[1] == origin[1]: expected_mask &= 0xab
            elif point[1] == origin[1]+height-1: expected_mask &= 0x57
            assert bytes(self.u.mem_read(node+4, 3)) == bytes([expected_mask, 0, 0])
            if point in self.blocked: self.u.mem_write(node+6, b'\x03')
            self.u.mem_write(node+5, bytes([self.flags.get(point, 0)]))
            self.d(self.cost_grid+4*(point[0]+288*point[1]), self.classes.get(point, 0))
        self.u.mem_write(self.functor+8, b'\0'); self.q(self.functor+16, 0)

    def node(self, point):
        return self.nodes+40*((point[0]-self.origin[0])+self.width*(point[1]-self.origin[1]))

    def path(self):
        pointer = self.rq(self.graph+0x38); seen = set(); path = []
        while pointer:
            assert pointer not in seen and self.nodes <= pointer < self.nodes+40*self.width*self.height
            seen.add(pointer); point = struct.unpack('<2H', self.u.mem_read(pointer, 4))
            assert pointer == self.node(point)
            path.append(point); pointer = self.rq(pointer+24)
        return path

    def oracle(self, start, goal):
        if start not in self.cells or goal not in self.cells: return 1, None
        distances = {start: 0.}; queue = [(0., start)]
        while queue:
            distance, point = heapq.heappop(queue)
            if distance != distances[point]: continue
            if point == goal: return 2, distance
            for dx, dz in STEPS:
                other = point[0]+dx, point[1]+dz
                if other not in self.cells: continue
                if other != goal and (other in self.blocked or self.flags.get(other, 0) & 0xf5): continue
                category = self.classes.get(other, 0)
                weight = WEIGHTS[category] if 0 <= category < 8 else WEIGHTS[0]
                edge = f32(f32(math.sqrt(dx*dx+dz*dz))*weight)
                candidate = f32(distance+edge)
                if candidate < distances.get(other, math.inf):
                    distances[other] = candidate; heapq.heappush(queue, (candidate, other))
        return 0, None

    def check_search(self, start, goal):
        wanted, optimal = self.oracle(start, goal)
        result = self.s.call(0x15bd700, (self.graph, packed(start), packed(goal), self.functor), limit=3_000_000)
        assert result == wanted, (start, goal, result, wanted)
        path = self.path()
        if result == 2:
            assert path[0] == start and path[-1] == goal
            accumulated = 0.
            for a, b in zip(path, path[1:]):
                delta = b[0]-a[0], b[1]-a[1]
                assert delta in STEPS
                assert b == goal or b not in self.blocked and not self.flags.get(b, 0) & 0xf5
                category = self.classes.get(b, 0); weight = WEIGHTS[category] if 0 <= category < 8 else WEIGHTS[0]
                accumulated = f32(accumulated+f32(f32(math.sqrt(delta[0]**2+delta[1]**2))*weight))
            native_cost = struct.unpack('<f', self.u.mem_read(self.node(goal)+8, 4))[0]
            assert native_cost == accumulated
            assert math.isclose(native_cost, optimal, rel_tol=2e-6, abs_tol=2e-5), (native_cost, optimal, path)
        else:
            assert not path
            native_cost = None
        assert bytes(self.u.mem_read(self.nodes-16, 16)) == b'\xa5'*16
        assert bytes(self.u.mem_read(self.nodes+40*self.width*self.height, 16)) == b'\xa5'*16
        return {'result': result, 'path': path, 'goal_cost': native_cost, 'dijkstra_optimal_cost': optimal}


def main():
    h = RouteHarness(); s, u, im = h.s, h.u, h.im
    groups = {'native_grid_initialization': 0, 'search_against_dijkstra': 0,
              'node_flag_and_target_exceptions': 0, 'native_cost_and_heuristic': 0,
              'worker_search_call_blocks': 0}
    outcomes = Counter(); samples = []
    def run(name, width, height, start, goal, origin=(0, 0), blocked=(), flags=None, classes=None, group='search_against_dijkstra'):
        h.prepare(width, height, origin, blocked, flags, classes)
        groups['native_grid_initialization'] += 1
        value = h.check_search(start, goal); groups[group] += 1
        outcomes[str(value['result'])] += 1
        if not name.startswith('random_') or len(samples) < 12:
            samples.append({'name': name, 'width': width, 'height': height, 'origin': origin,
                            'start': start, 'goal': goal, 'blocked': sorted(blocked),
                            'flags': [{'point': k, 'value': v} for k, v in (flags or {}).items()],
                            'classes': [{'point': k, 'value': v} for k, v in (classes or {}).items()], **value})
    run('diagonal_open', 8, 8, (0, 0), (7, 7))
    run('detour_wall_gap', 8, 8, (1, 1), (6, 1), blocked={(3, z) for z in range(7)})
    run('unreachable_wall', 8, 8, (1, 1), (6, 1), blocked={(3, z) for z in range(8)})
    run('weighted_detour', 8, 5, (0, 2), (7, 2), classes={(x, 2): 7 for x in range(1, 7)})
    run('diagonal_destination_only', 2, 2, (0, 0), (1, 1), blocked={(1, 0), (0, 1)})
    run('start_equals_goal', 4, 4, (2, 2), (2, 2))
    run('invalid_start', 4, 4, (65535, 0), (3, 3))
    run('invalid_goal', 4, 4, (0, 0), (4, 0))
    run('nonzero_origin', 7, 5, (15, 20), (21, 24), origin=(15, 20))
    run('blocked_target_exception', 4, 4, (0, 0), (3, 3), blocked={(3, 3)})
    run('blocked_start_exception', 4, 4, (0, 0), (3, 3), blocked={(0, 0)})
    rng = random.Random(0xac0100)
    for i in range(96):
        width, height = rng.randint(4, 12), rng.randint(4, 10)
        origin = (rng.choice([0, 7, 31]), rng.choice([0, 11, 23]))
        cells = [(origin[0]+x, origin[1]+z) for x in range(width) for z in range(height)]
        start, goal = rng.sample(cells, 2)
        blocked = {p for p in cells if rng.random() < .24 and p not in [start, goal]}
        classes = {p: rng.randrange(8) for p in cells} if i % 2 else {}
        run(f'random_{i}', width, height, start, goal, origin, blocked, classes=classes)
    for flag in range(256):
        # A one-cell corridor distinguishes every bit without alternate routes.
        run(f'intermediate_flag_{flag:02x}', 3, 1, (0, 0), (2, 0), flags={(1, 0): flag}, group='node_flag_and_target_exceptions')
        run(f'target_flag_{flag:02x}', 2, 1, (0, 0), (1, 0), flags={(1, 0): flag}, group='node_flag_and_target_exceptions')
    # All eight source cost categories, signed/oversized category fallback and
    # the explicit zero-cost byte use original callbacks and vtable dispatch.
    h.prepare(3, 3)
    a, b = h.node((0, 0)), h.node((1, 1))
    cost_samples = []
    for category in list(range(8))+[-1, 8, 0x7fffffff]:
        h.d(h.cost_grid+4*(1+288), category)
        result = s.call(0x15c38a0, (h.functor, a, b))
        value = s.float_result(); weight = WEIGHTS[category] if 0 <= category < 8 else WEIGHTS[0]
        assert value == f32(f32(math.sqrt(2))*weight)
        s.call(0x15c1610, (h.functor, a, b)); assert s.float_result() == f32(math.sqrt(2))
        groups['native_cost_and_heuristic'] += 2
        cost_samples.append({'category': category, 'edge_cost': value})
    u.mem_write(h.functor+8, b'\x01'); s.call(0x15c38a0, (h.functor, a, b))
    assert s.float_result() == 0.; groups['native_cost_and_heuristic'] += 1
    # The real worker constructs the same functor, calls the kernel and stores
    # its result. Stop before cancellation/state publication or async activity.
    worker = s.HEAP+0xa0000
    def stop_worker(uc, pc, size, data): uc.emu_stop()
    hook = u.hook_add(UC_HOOK_CODE, stop_worker, begin=0x15c3534, end=0x15c3534)
    worker_samples = []
    for i in range(8):
        blocked = {(3, z) for z in range(6)} if i & 1 else set()
        start, goal = (0, 0), (5, 5)
        h.prepare(6, 6, blocked=blocked)
        wanted, _ = h.oracle(start, goal)
        u.mem_write(worker, bytes(0xb0))
        u.reg_write(regs.UC_ARM64_REG_SP, s.STACK+0x1ff000)
        for reg, value in [('X19', worker), ('X21', start[0]), ('X22', start[1]), ('X24', goal[0]), ('X25', goal[1])]:
            u.reg_write(getattr(regs, 'UC_ARM64_REG_'+reg), value)
        u.emu_start(0x15c34f0, s.STOP, timeout=5_000_000, count=1_000_000)
        assert u.reg_read(regs.UC_ARM64_REG_PC) == 0x15c3534
        assert h.rd(worker+0x30) == wanted
        worker_samples.append({'blocked_wall': bool(i & 1), 'native_worker_result': wanted, 'path_nodes': len(h.path())})
        groups['worker_search_call_blocks'] += 1
    u.hook_del(hook)
    result = {'groups': groups, 'cases': sum(groups.values()), 'mismatches': [],
              'search_outcomes': dict(outcomes), 'samples': samples, 'cost_samples': cost_samples,
              'worker_samples': worker_samples, 'oracle': 'Independent heap-based Dijkstra; compare reachability, path legality, accumulated f32 cost and optimum for prepared weights>=1.',
              'native_functions': {'initialize_grid': '0x15bc0c0', 'astar_search': '0x15bd700',
                                   'expand_neighbors': '0x15bda30', 'edge_cost': '0x15c38a0',
                                   'base_edge_distance': '0x15c15a0', 'heuristic': '0x15c1610',
                                   'worker_bounded_entry': '0x15c34f0', 'worker_stop_before': '0x15c3534'},
              'layout': {'grid_origin_u16_xz': '0x0', 'grid_width_s32': '0xc', 'grid_height_s32': '0x10',
                         'node_count_u64': '0x18', 'node_array': '0x20', 'sorted_open_head': '0x28',
                         'path_head': '0x38', 'node_stride': 40,
                         'node_fields': {'u16_xz': '0x0', 'direction_mask': '0x4', 'flags': '0x5',
                                         'search_state': '0x6', 'g_cost_f32': '0x8', 'f_score_f32': '0xc',
                                         'parent': '0x10', 'open_or_path_next': '0x18'}},
              'rules': ['Sorted linked open list ordered by f=g+h, eight direction bits, parent pointers reconstructed into a start-to-goal path.',
                        'Return1 means invalid endpoint in tested bounds checks;0 means search exhausted;2 means a route was reconstructed.',
                        'Intermediate nodes are rejected for state3 or flags&0xf5; target node bypasses this rejection. Start is also admitted directly.',
                        'Cost is Euclidean adjacent-cell distance times destination cost category weight; category outside unsigned0..7 uses weight0. Functor byte+8 nonzero returns zero edge cost.',
                        'Heuristic is Euclidean distance to the goal. No optimality claim is made for weights<1, zero-cost mode or arbitrary caller callbacks.',
                        'On the prepared direction masks, diagonal expansion tests the destination, not both orthogonal neighbors. World mask construction may impose additional restrictions.'],
              'prepared_context': {'weights': WEIGHTS, 'global_cost_grid_stride': 288,
                                   'grid': 'Reconstructed coordinates, masks from original initializer, blocked states/flags and cost categories.',
                                   'functor': 'Original vtable0x3149c68 with optional cost-region pointer null.'},
              'limits': ['No live island collision/terrain-to-grid producer, route postprocessing, async scheduling or NPC movement is executed.',
                         'Blocked-state and flag numeric tests do not assign all original gameplay meanings to those bits.',
                         'Prepared weights are distinct test inputs, not recovered default gameplay values.',
                         'Worker block tests stop before cancellation and result publication; the complete world-dependent worker is not run.'],
              'source_reference': 'mechanics/npc_navigation_request_native.json',
              'dependencies_stubbed': [], 'elf_sha256': hashlib.sha256(im.data).hexdigest()}
    (ROOT/'output/mechanics/npc_pathfinding_native.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({'groups': groups, 'cases': result['cases'], 'search_outcomes': dict(outcomes), 'mismatches': 0}), flush=True)


if __name__ == '__main__': main()
