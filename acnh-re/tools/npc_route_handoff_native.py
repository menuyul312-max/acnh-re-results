"""Execute original route extraction/list recycling and the parent handoff block.

Worker identity/status and fixed node pools are reconstructed. Six integration
cases feed the original A* result chain directly into the original extractor.
The parent block stops BEFORE child controller initialization executes.
"""
from collections import Counter
from pathlib import Path
import hashlib
import itertools
import json
import struct

from npc_pathfinding_native import RouteHarness, packed
from native_emulator import Sandbox, regs
from unicorn import UC_HOOK_CODE

ROOT = Path(__file__).resolve().parent.parent


class HandoffHarness:
    def __init__(self, sandbox=None):
        self.s = sandbox or Sandbox(); self.u = self.s.uc; self.im = self.s.image
        self.worker, self.list, self.output, self.token, self.source, self.pool, self.child = [self.s.HEAP+n for n in
                (0x10000, 0x20000, 0x30000, 0x30100, 0x40000, 0x50000, 0x60000)]
        self.request = self.list-0x28
        self.graph = self.im.ptr(0x3311420)
        self.coord_vt = self.im.ptr(0x32d1598)+16
        assert self.im.ptr(self.coord_vt) == 0x25730

    def q(self, p, v): self.u.mem_write(p, struct.pack('<Q', v))
    def d(self, p, v): self.u.mem_write(p, struct.pack('<I', v & 0xffffffff))
    def rq(self, p): return struct.unpack('<Q', self.u.mem_read(p, 8))[0]
    def rd(self, p): return struct.unpack('<I', self.u.mem_read(p, 4))[0]

    def prepare(self, n, capacity, old_count=0, result=2, state=2, matches=True, native_path=None):
        assert 0 <= old_count <= capacity <= 512
        self.capacity = capacity
        self.u.mem_write(self.worker, bytes(0xb0)); self.d(self.worker, 0x12345678)
        self.d(self.worker+8, state); self.d(self.worker+0x30, result)
        self.d(self.token, 0x12345678 if matches else 0x12345679)
        self.u.mem_write(self.output, b'\xa5'*8)
        self.u.mem_write(self.request, bytes(0x2200))
        self.q(self.list, self.list); self.q(self.list+8, self.list)
        self.d(self.list+0x10, old_count); self.d(self.list+0x28, capacity)
        self.u.mem_write(self.pool-16, b'\xa5'*16+bytes(48*capacity)+b'\xa5'*16)
        self.old_nodes = []
        for i in range(capacity):
            node = self.pool+48*i
            if i < old_count:
                self.old_nodes.append(node); self.q(node, self.coord_vt)
                self.u.mem_write(node+8, struct.pack('<2I', 60000+i, 61000+i))
                link = node+16
                self.q(link, self.list if i == 0 else self.pool+48*(i-1)+16)
                self.q(link+8, self.list if i == old_count-1 else self.pool+48*(i+1)+16)
            else: self.q(node, node+48 if i < capacity-1 else 0)
        if old_count:
            self.q(self.list, self.pool+48*(old_count-1)+16); self.q(self.list+8, self.pool+16)
        self.q(self.list+0x18, self.pool+48*old_count if old_count < capacity else 0)
        if native_path is None:
            self.points = [((17*i+3) & 0xffff, (65535-13*i) & 0xffff) for i in range(n+1)]
            raw = bytearray(32*(n+1))
            for i, point in enumerate(self.points):
                struct.pack_into('<2H', raw, 32*i, *point)
                struct.pack_into('<Q', raw, 32*i+24, self.source+32*(i+1) if i < n else 0)
            self.u.mem_write(self.source-16, b'\xa5'*16+raw+b'\xa5'*16)
            self.q(self.graph+0x38, self.source)
            self.source_snapshot = (self.source-16, bytes(self.u.mem_read(self.source-16, len(raw)+32)))
        else:
            self.points = native_path
            n = max(0, len(native_path)-1)
            self.source_snapshot = None
        self.n = n; self.head_before = self.rq(self.graph+0x38)

    def list_state(self):
        points, active, links = [], [], []
        pointer = self.rq(self.list+8); previous = self.list
        while pointer != self.list:
            node = pointer-16
            assert node not in active and self.pool <= node < self.pool+48*self.capacity
            assert (node-self.pool) % 48 == 0 and self.rq(node) == self.coord_vt
            assert self.rq(pointer) == previous
            active.append(node); links.append(pointer)
            points.append(struct.unpack('<2I', self.u.mem_read(node+8, 8)))
            previous = pointer; pointer = self.rq(pointer+8)
        assert self.rq(self.list) == previous
        assert len(active) == self.rd(self.list+0x10)
        free = []; pointer = self.rq(self.list+0x18)
        while pointer:
            assert pointer not in free and pointer not in active
            assert self.pool <= pointer < self.pool+48*self.capacity and (pointer-self.pool) % 48 == 0
            free.append(pointer); pointer = self.rq(pointer)
        assert len(active)+len(free) == self.capacity
        assert bytes(self.u.mem_read(self.pool-16, 16)) == b'\xa5'*16
        assert bytes(self.u.mem_read(self.pool+48*self.capacity, 16)) == b'\xa5'*16
        if self.source_snapshot:
            p, value = self.source_snapshot; assert bytes(self.u.mem_read(p, len(value))) == value
        return points

    def verify_consumed(self, status=2):
        assert self.rd(self.worker) == 0 and self.rd(self.worker+8) == 0
        expected = list(reversed(self.points[1:257]))[:self.capacity] if status == 2 and self.n else []
        assert self.list_state() == expected, (self.n, self.capacity, self.list_state(), expected)
        if status == 2 and self.n:
            assert self.rq(self.graph+0x38) == self.rq(self.head_before+24)
        else: assert self.rq(self.graph+0x38) == self.head_before
        return expected


def main():
    h = HandoffHarness(); s, u, im = h.s, h.u, h.im
    groups = {'complete_route_extractor': 0, 'worker_identity_and_status_guards': 0,
              'parent_result_handoff_blocks': 0, 'native_search_to_extractor_to_parent': 0}
    outcomes = Counter(); samples = []
    for n, capacity in itertools.product([0, 1, 2, 3, 7, 31, 255, 256, 257, 300], [0, 1, 2, 8, 64, 256, 300]):
        for old_count in sorted({0, min(2, capacity)}):
            h.prepare(n, capacity, old_count)
            result = s.call(0x15c3570, (h.worker, h.list, h.output, h.token), limit=1_000_000)
            assert result == int(1 <= n <= 256)
            assert h.rd(h.output) == 2
            points = h.verify_consumed()
            assert bytes(u.mem_read(h.output+4, 4)) == b'\xa5'*4
            outcomes[f'return{result}'] += 1; groups['complete_route_extractor'] += 1
            if n in [0, 1, 256, 257, 300] and capacity in [0, 2, 300] and old_count == 0:
                samples.append({'source_steps_after_start': n, 'capacity': capacity,
                                'native_return': result, 'output_status': h.rd(h.output),
                                'output_nodes': len(points), 'front': points[:3], 'back': points[-3:]})
    # A stale identity or non-ready worker leaves all caller outputs/lists intact.
    # A matching ready worker consumes and resets itself even for failure results.
    for state, matches, status, old_count in itertools.product([0, 1, 2, 3], [False, True], [0, 1, 2, 3, 0xffffffff], [0, 2]):
        h.prepare(7, 8, old_count, status, state, matches)
        list_before = bytes(u.mem_read(h.list, 0x30)); pool_before = bytes(u.mem_read(h.pool, 8*48))
        worker_before = bytes(u.mem_read(h.worker, 0xb0))
        result = s.call(0x15c3570, (h.worker, h.list, h.output, h.token), limit=100000)
        accepted = state == 2 and matches
        assert result == int(accepted and status == 2)
        if accepted:
            assert h.rd(h.output) == status; h.verify_consumed(status)
        else:
            assert bytes(u.mem_read(h.output, 8)) == b'\xa5'*8
            assert bytes(u.mem_read(h.list, 0x30)) == list_before
            assert bytes(u.mem_read(h.pool, 8*48)) == pool_before
            assert bytes(u.mem_read(h.worker, 0xb0)) == worker_before
            h.list_state(); assert h.rq(h.graph+0x38) == h.head_before
        groups['worker_identity_and_status_guards'] += 1
    observed = {}
    def parent_hook(uc, pc, size, data):
        if pc == 0xcb5530: observed['extractor_return'] = uc.reg_read(regs.UC_ARM64_REG_W0)
        else:
            observed['stop'] = pc
            observed['args'] = [uc.reg_read(getattr(regs, 'UC_ARM64_REG_X'+str(i))) for i in range(4)]
            uc.emu_stop()
    hooks = [u.hook_add(UC_HOOK_CODE, parent_hook, begin=p, end=p) for p in [0xcb5530, 0xc862b0, 0xcb54a0]]
    def run_parent(status):
        # Entry is the result-collection continuation, after the ready predicate.
        h.d(h.request+8, 0x12345678); h.q(h.request+0x20, h.child)
        u.mem_write(h.request+0x20ac, b'\x21'); observed.clear()
        u.reg_write(regs.UC_ARM64_REG_SP, s.STACK+0x1ff000)
        u.reg_write(regs.UC_ARM64_REG_X19, h.request)
        u.reg_write(regs.UC_ARM64_REG_X20, h.worker)
        u.reg_write(regs.UC_ARM64_REG_X22, h.request+0x20ac)
        u.reg_write(regs.UC_ARM64_REG_LR, s.STOP)
        u.emu_start(0xcb5518, s.STOP, timeout=5_000_000, count=1_000_000)
        assert observed['extractor_return'] == int(status == 2 and 1 <= h.n <= 256)
        if status == 2:
            assert observed['stop'] == 0xc862b0
            assert observed['args'] == [h.child, h.list, h.request+0x206c, h.request+0x2058]
            assert bytes(u.mem_read(h.request+0x20ac, 1)) == b'\x25'
        else:
            assert observed['stop'] == 0xcb54a0
            assert bytes(u.mem_read(h.request+0x20ac, 1)) == b'\x23'
        h.verify_consumed(status)
        return {'extractor_return': observed['extractor_return'], 'parent_handoff': status == 2,
                'parent_flags': bytes(u.mem_read(h.request+0x20ac, 1))[0], 'output_nodes': h.rd(h.list+0x10)}
    parent_samples = []
    for n, capacity, status in itertools.product([0, 1, 255, 256, 257, 300], [0, 2, 300], [2, 3]):
        h.prepare(n, capacity, min(2, capacity), status)
        value = run_parent(status); groups['parent_result_handoff_blocks'] += 1
        if status == 2 and capacity == 300:
            parent_samples.append({'source_steps_after_start': n, **value})
    # The original A* chain, including parent pointers converted to next links,
    # is used directly. No path bytes are copied to a synthetic route chain.
    search = RouteHarness(s); integration_samples = []
    scenarios = [('open', set(), (0, 0), (7, 7)),
                 ('wall_gap', {(3, z) for z in range(7)}, (0, 0), (7, 0)),
                 ('unreachable', {(3, z) for z in range(8)}, (0, 0), (7, 0)),
                 ('start_equals_goal', set(), (2, 2), (2, 2)),
                 ('reverse_direction', set(), (7, 7), (0, 0)),
                 ('limited_pool', set(), (0, 0), (7, 7))]
    for name, blocked, start, goal in scenarios:
        search.prepare(8, 8, blocked=blocked)
        native = search.check_search(start, goal); path = native['path']
        node_before = bytes(u.mem_read(search.nodes, 40*64))
        h.prepare(max(0, len(path)-1), 2 if name == 'limited_pool' else 32, 2,
                  native['result'], native_path=path)
        value = run_parent(native['result'])
        assert bytes(u.mem_read(search.nodes, 40*64)) == node_before
        integration_samples.append({'name': name, 'native_search_result': native['result'],
                                    'native_source_path': path, **value})
        groups['native_search_to_extractor_to_parent'] += 1
    for hook in hooks: u.hook_del(hook)
    result = {'groups': groups, 'cases': sum(groups.values()), 'mismatches': [],
              'extractor_outcomes': dict(outcomes), 'samples': samples, 'parent_samples': parent_samples,
              'native_pipeline_samples': integration_samples,
              'native_functions': {'extractor': '0x15c3570', 'unlink_node': '0x1967c60',
                                   'append_node': '0x1967c40', 'coordinate_destructor': '0x25730',
                                   'parent_block_entry': '0xcb5518', 'parent_handoff_stop_before': '0xc862b0',
                                   'astar': '0x15bd700'},
              'list_layout': {'sentinel': 'list+0', 'size_s32': 'list+0x10', 'free_head': 'list+0x18',
                              'capacity_s32': 'list+0x28', 'node_vtable': 'node+0',
                              'node_xz_u32': 'node+8', 'node_link': 'node+0x10'},
              'rules': ['Only worker state2 with a matching requester32-bit ID consumes the result; guards leave output/list untouched.',
                        'A matching ready result first recycles the old list, writes status, and resets worker ID/state to0. Non-success status then returns false.',
                        'For status2 with at least one step, remove the initial start node from the source chain, select its first min(remaining,256) nodes, reverse order and append until destination capacity is reached.',
                        'Return is true for1..256 source steps even if the destination capacity truncates the list to0. More than256 source steps returns false but still fills the bounded prefix.',
                        'The parent continuation checks output status2, ignoring the extractor boolean. It sets request flag4 and dispatches child initialization even when extraction returned false for an empty/oversized route.',
                        'Six cases connect the native A* result chain directly to extraction and the parent handoff; no synthetic path is substituted in these cases.'],
              'scope': 'Complete original result extraction and node-pool recycling, plus bounded parent result-collection/handoff and a native-search integration chain.',
              'limits': ['Worker request identity, ready state and result publication are prepared; async execution and original worker lifecycle are not proven.',
                         'The parent block starts after its readiness check and stops BEFORE child controller initialization. Movement, collision avoidance and landing are not executed.',
                         'Empty/oversized route behavior is a tested consumer contract, not evidence of a reachable gameplay bug.',
                         'Only fields consumed by these routines are specified. Fixed-pool construction/allocation and full save/world state remain reconstructed.'],
              'source_reference': 'mechanics/npc_pathfinding_native.json',
              'dependencies_stubbed': [], 'elf_sha256': hashlib.sha256(im.data).hexdigest()}
    (ROOT/'output/mechanics/npc_route_handoff_native.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({'groups': groups, 'cases': result['cases'], 'mismatches': 0}), flush=True)


if __name__ == '__main__': main()
