"""Bounded native checks for the NPC route-grid producer.

The original grid wrapper executes through its world-bound-aware region setup
and both endpoint bounds checks. Accepted cases stop immediately before the
first grid-array initialization; rejected cases run to the original return.
"""
from collections import Counter
from pathlib import Path
import hashlib
import json
import struct

from native_emulator import Sandbox, regs
from unicorn import UC_HOOK_CODE

ROOT = Path(__file__).resolve().parent.parent
ELF_SHA256 = '5bf707c3dc5dac0ad9635af7d336ec580f81c3f7876d0f55400d1900e3415d74'
GRID_PRODUCER = 0xc88310
REGION_UPDATE = 0xc88b80
ACCEPT_STOP = 0xc884c8
GRAPH_WIDTH_OFFSET = 0x0c
GRAPH_HEIGHT_OFFSET = 0x10


class Harness:
    def __init__(self):
        self.s = Sandbox()
        self.u = self.s.uc
        self.im = self.s.image
        self.ctx, self.graph, self.p2, self.p3, self.option = [
            self.s.HEAP + offset for offset in
            (0x50000, 0x60000, 0x70000, 0x71000, 0x72000)]
        self.singleton_cell, self.region_manager, self.world_bounds = [
            self.s.HEAP + offset for offset in (0x7f000, 0x80000, 0x81000)]
        self.u.mem_write(self.singleton_cell, bytes(0x10))
        self.u.mem_write(self.region_manager, bytes(0x400))
        self.u.mem_write(self.world_bounds, bytes(0x100))

        # c88b80 obtains a region-bounds record through this native accessor
        # chain. Only its input state is prepared; no native code is replaced.
        self.q(self.singleton_cell, self.region_manager)
        self.q(self.region_manager + 0x1c0, self.world_bounds)
        self.q(0x32d1ba8, self.singleton_cell)
        for offset, value in zip((0x20, 0x24, 0x30, 0x34), (0, 0, 100, 100)):
            self.d(self.world_bounds + offset, value)

        self.accept_seen = False

        def stop_after_admission(uc, pc, _size, _data):
            if pc == ACCEPT_STOP:
                self.accept_seen = True
                uc.emu_stop()

        self.hook = self.u.hook_add(UC_HOOK_CODE, stop_after_admission)

    def q(self, address, value):
        self.u.mem_write(address, struct.pack('<Q', value))

    def d(self, address, value):
        self.u.mem_write(address, struct.pack('<I', value & 0xffffffff))

    def vec_from_cells(self, address, xz):
        x, z = xz
        self.u.mem_write(address, struct.pack('<3f', x * 5.0, 0.0, z * 5.0))

    def prepare(self, case):
        self.u.mem_write(self.ctx, bytes(0x300))
        self.u.mem_write(self.graph, bytes(0x6000))
        self.q(self.ctx + 0x10, self.graph)
        self.u.mem_write(self.ctx + 0x125, bytes([int(case['fixed_origin'])]))
        self.u.mem_write(self.graph, struct.pack('<HH', *case['initial_origin']) +
                         bytes(8) + struct.pack('<II', 25, 21))
        self.vec_from_cells(self.p2, case['from_cell'])
        self.vec_from_cells(self.p3, case['to_cell'])
        self.d(self.option, 0)
        self.accept_seen = False

    def invoke(self, accepted_prefix):
        if not accepted_prefix:
            result = self.s.call(GRID_PRODUCER,
                                 (self.ctx, self.p2, self.p3, self.option),
                                 limit=100000)
            return {'pc': self.u.reg_read(regs.UC_ARM64_REG_PC), 'return': result}

        self.u.reg_write(regs.UC_ARM64_REG_SP, self.s.STACK + 0x1ff000)
        for index, value in enumerate((self.ctx, self.p2, self.p3, self.option)):
            self.u.reg_write(getattr(regs, f'UC_ARM64_REG_X{index}'), value)
        self.u.reg_write(regs.UC_ARM64_REG_X30, self.s.STOP)
        self.u.emu_start(GRID_PRODUCER, self.s.STOP, timeout=5_000_000, count=100000)
        pc = self.u.reg_read(regs.UC_ARM64_REG_PC)
        assert pc == ACCEPT_STOP and self.accept_seen, hex(pc)
        return {'pc': pc, 'return': None}

    def graph_snapshot(self):
        raw = bytes(self.u.mem_read(self.graph, 0x14))
        origin = struct.unpack_from('<2H', raw, 0)
        region = struct.unpack_from('<4H', raw, 4)
        width, height = struct.unpack_from('<2I', raw, 0x0c)
        return {'origin_xz': list(origin),
                'region_start_xz': list(region[:2]),
                'region_end_exclusive_xz': list(region[2:]),
                'width_height': [width, height]}


def cell_vec(case, key):
    return [case[key][0] * 5.0, 0.0, case[key][1] * 5.0]


def main():
    cases = [
        {'name': 'fixed_interior', 'mode': 'saved_origin', 'fixed_origin': True,
         'initial_origin': [10, 10], 'from_cell': [10, 15], 'to_cell': [34, 30],
         'expected': 'admitted_prefix'},
        {'name': 'fixed_reverse_interior', 'mode': 'saved_origin', 'fixed_origin': True,
         'initial_origin': [10, 10], 'from_cell': [34, 30], 'to_cell': [10, 15],
         'expected': 'admitted_prefix'},
        {'name': 'fixed_x_lower_exclusive', 'mode': 'saved_origin', 'fixed_origin': True,
         'initial_origin': [10, 10], 'from_cell': [9, 10], 'to_cell': [30, 20],
         'expected': 'rejected_return_0'},
        {'name': 'fixed_x_upper_exclusive', 'mode': 'saved_origin', 'fixed_origin': True,
         'initial_origin': [10, 10], 'from_cell': [10, 10], 'to_cell': [35, 20],
         'expected': 'rejected_return_0'},
        {'name': 'fixed_z_lower_exclusive', 'mode': 'saved_origin', 'fixed_origin': True,
         'initial_origin': [10, 10], 'from_cell': [10, 9], 'to_cell': [20, 30],
         'expected': 'rejected_return_0'},
        {'name': 'fixed_z_upper_exclusive', 'mode': 'saved_origin', 'fixed_origin': True,
         'initial_origin': [10, 10], 'from_cell': [10, 10], 'to_cell': [20, 31],
         'expected': 'rejected_return_0'},
        {'name': 'centered_full_span', 'mode': 'recentered', 'fixed_origin': False,
         'initial_origin': [0, 0], 'from_cell': [0, 0], 'to_cell': [24, 20],
         'expected': 'admitted_prefix', 'expected_origin': [0, 0]},
        {'name': 'centered_exact_width_edge', 'mode': 'recentered', 'fixed_origin': False,
         'initial_origin': [0, 0], 'from_cell': [0, 0], 'to_cell': [25, 20],
         'expected': 'rejected_return_0', 'expected_origin': [0, 0]},
        {'name': 'centered_rounding_inside', 'mode': 'recentered', 'fixed_origin': False,
         'initial_origin': [0, 0], 'from_cell': [2, 0], 'to_cell': [25, 20],
         'expected': 'admitted_prefix', 'expected_origin': [1, 0]},
        {'name': 'centered_rounding_edge', 'mode': 'recentered', 'fixed_origin': False,
         'initial_origin': [0, 0], 'from_cell': [1, 0], 'to_cell': [25, 20],
         'expected': 'rejected_return_0', 'expected_origin': [0, 0]},
        {'name': 'centered_low_clamp', 'mode': 'recentered', 'fixed_origin': False,
         'initial_origin': [0, 0], 'from_cell': [1, 1], 'to_cell': [5, 5],
         'expected': 'admitted_prefix', 'expected_origin': [0, 0]},
        {'name': 'centered_high_clamp', 'mode': 'recentered', 'fixed_origin': False,
         'initial_origin': [0, 0], 'from_cell': [99, 90], 'to_cell': [100, 100],
         'expected': 'admitted_prefix', 'expected_origin': [76, 80]},
    ]

    harness = Harness()
    groups = Counter()
    samples = []
    for case in cases:
        harness.prepare(case)
        admitted = case['expected'] == 'admitted_prefix'
        observed = harness.invoke(admitted)
        graph = harness.graph_snapshot()
        expected_pc = ACCEPT_STOP if admitted else None
        assert (observed['pc'] == expected_pc if admitted else observed['return'] == 0), case['name']
        if 'expected_origin' in case:
            assert graph['origin_xz'] == case['expected_origin'], (case['name'], graph)
        if case['mode'] == 'saved_origin':
            assert graph['origin_xz'] == case['initial_origin'], (case['name'], graph)
        assert graph['width_height'] == [25, 21], (case['name'], graph)
        groups[f"{case['mode']}:{case['expected']}"] += 1
        samples.append({'name': case['name'], 'mode': case['mode'],
                        'from_world': cell_vec(case, 'from_cell'),
                        'to_world': cell_vec(case, 'to_cell'),
                        'from_grid_input': case['from_cell'],
                        'to_grid_input': case['to_cell'],
                        'observed': case['expected'],
                        'stop_pc': hex(observed['pc']),
                        'return_value': observed['return'],
                        'grid': graph})

    harness.u.hook_del(harness.hook)
    assert hashlib.sha256(harness.im.data).hexdigest() == ELF_SHA256
    result = {
        'cases': len(cases), 'groups': dict(groups), 'mismatches': [],
        'samples': samples,
        'native_functions': {
            'grid_producer': '0xc88310', 'region_update': '0xc88b80',
            'world_to_grid_coordinate': '0x15c0a60',
            'region_bounds_accessor': '0x565070',
            'admitted_prefix_stop_before': '0xc884c8',
            'first_grid_array_initialization_call': '0x220e440'},
        'graph_layout': {'origin_xz_u16': 'graph+0x0',
                         'region_start_xz_u16': 'graph+0x4',
                         'region_end_exclusive_xz_u16': 'graph+0x8',
                         'width_s32': 'graph+0xc', 'height_s32': 'graph+0x10'},
        'prepared_context': {
            'grid_dimensions': [25, 21],
            'native_region_global_bounds': {'min_xz': [0, 0], 'max_xz_inclusive': [100, 100]},
            'singleton_holder_and_manager': 'Synthetic object state at heap addresses; native accessor instructions execute.',
            'position_vectors': 'Inputs are cell-index * 5.0 on X/Z, Y=0; conversion to grid coordinates still executes in 0x15c0a60.'},
        'rules': [
            '0xc88310 runs the original region update then tests both converted endpoints against [originX, originX+width) and [originZ, originZ+height).',
            'The fixed-origin cases preserve the prepared origin and admit both endpoints at the lower bound and the last in-range cell; either endpoint at the exclusive upper edge or one cell below the lower edge returns 0.',
            'In recentered cases, the region origin is computed from the midpoint and then clamped by the prepared global region bounds. The tested [2,0] -> [25,20] case admits with origin [1,0]; [1,0] -> [25,20] lands at origin [0,0] and rejects at the exclusive X edge.',
            'Accepted cases stop after both endpoint predicates pass and immediately before the first grid-array initialization. They do not prove the later terrain-to-grid production or route search.'
        ],
        'scope': 'Original 0xc88310/0xc88b80/0x15c0a60 instructions execute on explicit grid and singleton context. Rejected routes run to the original return; accepted routes stop before array initialization.',
        'limits': [
            'The global region bounds and existing grid are prepared test inputs, not recovered live-island state.',
            'The accepted prefix does not execute grid flags, terrain costs, graph initialization, worker submission or A*.',
            'No request scheduler, cancellation or result publication is exercised; no NPC activity/social behavior is inferred.'
        ],
        'dependencies_stubbed': [], 'elf_sha256': ELF_SHA256}

    out = ROOT / 'output/mechanics/npc_social_followup/npc_grid_producer_native.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps({'cases': len(cases), 'groups': dict(groups), 'mismatches': 0,
                      'artifact': str(out.relative_to(ROOT))}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
