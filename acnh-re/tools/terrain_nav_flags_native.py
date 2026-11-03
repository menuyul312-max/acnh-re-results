"""Run original runtime terrain-height -> word flags -> navigation-node paths.

The52-byte runtime records and world context are reconstructed. This does not
recover a preset/PBC loader or prove every ground-type branch of the writer.
"""
from collections import Counter
from pathlib import Path
import hashlib
import itertools
import json
import random
import struct
from npc_pathfinding_native import RouteHarness, packed

ROOT = Path(__file__).resolve().parent.parent
CARDINAL = [(0, -1), (-1, 0), (0, 1), (1, 0)]


def decoded_word(word):
    return ((4 if word & 0x100 else 0) | (8 if word & 0x200 else 0) |
            (1 if word & 0x400 else 0) | (2 if word & 0x800 else 0) |
            (16 if word & 0x1000 and not word & 0x40 else 0) |
            (32 if word & 0x2000 else 0) | (64 if word & 0x4000 else 0))


class WorldHarness(RouteHarness):
    def __init__(self, sandbox=None):
        super().__init__(sandbox)
        self.world, self.words, self.overlay, self.base = [self.s.HEAP+n for n in (0xc0000, 0xd0000, 0xe0000, 0xf0000)]
        self.context, self.coord, self.output = [self.s.HEAP+n for n in (0x110000, 0x112000, 0x112100)]

    def reset(self):
        self.prepare(8, 8)
        self.u.mem_write(self.world, bytes(0x100))
        self.d(self.world+0x30, 8); self.d(self.world+0x34, 8)
        self.d(self.world+0x40, 64); self.q(self.world+0x48, self.base)
        self.d(self.world+0x60, 64); self.q(self.world+0x68, self.words)
        self.u.mem_write(self.world+0x28, struct.pack('<f', 2.5))
        self.u.mem_write(self.base-16, b'\xa5'*16+bytes(52*64)+b'\xa5'*16)
        self.u.mem_write(self.words-16, b'\xa5'*16+bytes(4*64)+b'\xa5'*16)
        self.u.mem_write(self.context, struct.pack('<3Q', self.im.ptr(0x3311450)+16, 0, self.world))
        # Empty native range disables cropping; empty constraint registries
        # select the original terrain callback instead of actor predicates.
        self.u.mem_write(self.im.ptr(0x3311410), bytes(0x28))
        self.d(self.im.ptr(0x3311418), 0); self.d(self.im.ptr(0x3311430), 0)
        self.set_coord((3, 3))

    def set_coord(self, point): self.u.mem_write(self.coord, bytes(8)+struct.pack('<2i', *point))
    def tile(self, point): return self.base+52*(point[0]+8*point[1])
    def word_address(self, point): return self.words+4*(point[0]+8*point[1])

    def write_heights(self, point=(3, 3), incoming=0):
        self.set_coord(point); self.d(self.word_address(point), incoming)
        source = bytes(self.u.mem_read(self.base, 52*64))
        self.s.call(0x180d20, (self.world, self.coord, self.word_address(point), self.tile(point)), limit=300000)
        assert bytes(self.u.mem_read(self.base, 52*64)) == source
        for address, size in [(self.base, 52*64), (self.words, 4*64)]:
            assert bytes(self.u.mem_read(address-16, 16)) == b'\xa5'*16
            assert bytes(self.u.mem_read(address+size, 16)) == b'\xa5'*16
        return self.rd(self.word_address(point))


def main():
    h = WorldHarness(); s, u, im = h.s, h.u, h.im
    groups = {'word_decoder_truth_table': 0, 'decoder_invalid_coordinates': 0,
              'complete_node_callback': 0, 'flat_neighbor_height_boundaries': 0,
              'internal_height_connectivity': 0, 'native_cost_reset_defaults': 0,
              'cost_category_producer': 0, 'height_to_node_to_search': 0}
    h.reset(); center = (3, 3); source_samples = []; node_samples = []; internal_samples = []
    for bits, gate in itertools.product(range(128), [False, True]):
        word = (bits << 8) | (0x40 if gate else 0) | 0x80008080
        h.d(h.word_address(center), word); u.mem_write(h.output, b'\xa5'*16)
        s.call(0x185e70, (h.world, h.coord, h.output))
        expected = bytearray(b'\xa5'*16); expected[8] = decoded_word(word)
        assert bytes(u.mem_read(h.output, 16)) == expected
        assert h.rd(h.word_address(center)) == word
        groups['word_decoder_truth_table'] += 1
    for point in [(-1, 0), (0, -1), (8, 0), (0, 8), (0x7fffffff, 0), (-0x80000000, 0)]:
        h.set_coord(point); u.mem_write(h.output, b'\xa5'*16)
        s.call(0x185e70, (h.world, h.coord, h.output))
        expected = bytearray(b'\xa5'*16); expected[8] = 0
        assert bytes(u.mem_read(h.output, 16)) == expected
        groups['decoder_invalid_coordinates'] += 1
    for bits, gate in itertools.product(range(128), [False, True]):
        h.reset(); word = (bits << 8) | (0x40 if gate else 0)
        h.d(h.word_address(center), word)
        s.call(0x15c24a0, (h.context, h.node(center)), limit=100000)
        value = decoded_word(word)
        if value & 16:
            flags = (8 if not value & 1 else 0) | (2 if not value & 2 else 0) | (4 if not value & 4 else 0) | (1 if not value & 8 else 0)
            mode = 0; mask = 255
            for i, clear_mask in enumerate([0x6e, 0x9d, 0xab, 0x57]):
                if flags & (1 << i): mask &= clear_mask
        elif value & 32: flags, mode, mask = 0x89, 1, 0
        elif value & 64: flags, mode, mask = 0x2a, 2, 0
        else: flags, mode, mask = 0, 0, 255
        data = bytes(u.mem_read(h.node(center), 40))
        # Neighbor reconciliation can add high flag bits back to the center.
        # Check the direct low nibble plus topology/mode; retain the full
        # resulting byte in the evidence without inventing its bit names.
        assert (data[5] & 15, data[6], data[32]) == (flags & 15, 0, mode), (word, data.hex(), flags, mode)
        assert data[4] & ~mask == 0, (word, data.hex(), mask)
        assert h.rd(h.word_address(center)) == word
        groups['complete_node_callback'] += 1
        node_samples.append({'runtime_word': hex(word), 'decoded_byte': value,
                             'node_direction_mask': data[4], 'direct_direction_mask_upper_bound': mask, 'node_flags': data[5],
                             'verified_direct_flag_low_nibble': flags & 15, 'node_mode_byte20': mode})
    for center_height, delta, blocked in itertools.product([-5., 0., 3.],
            [-1.5, -1.25, -1., 0., 1., 1.25, 1.5], range(16)):
        h.reset(); u.mem_write(h.tile(center), struct.pack('<12f', *([center_height]*12)))
        for i, (dx, dz) in enumerate(CARDINAL):
            other = center[0]+dx, center[1]+dz
            u.mem_write(h.tile(other), struct.pack('<12f', *([center_height+delta]*12)))
            h.d(h.word_address(other), 0x40 if blocked & (1 << i) else 0)
        word = h.write_heights(incoming=0x80008080)
        expected = 0x80008080 | 0x1000
        if abs(delta) <= 1.25:
            expected |= sum(1 << (8+i) for i in range(4) if not blocked & (1 << i))
        assert word == expected, (center_height, delta, blocked, hex(word), hex(expected))
        groups['flat_neighbor_height_boundaries'] += 1
        if center_height == 0 and blocked == 0:
            source_samples.append({'center_height': center_height, 'neighbor_delta': delta, 'runtime_word': hex(word)})
    rng = random.Random(0x180d20)
    patterns = [[0.]*i+[value]+[0.]*(11-i) for i in range(12) for value in [-2., -1.25, 0., 1.25, 2.]]
    patterns += [[rng.choice([-2., -1.25, 0., 1.25, 2.]) for _ in range(12)] for _ in range(96)]
    for heights, force in itertools.product(patterns, [False, True]):
        h.reset(); u.mem_write(h.tile(center), struct.pack('<12f', *heights))
        incoming = 0x80008080 | int(force)
        bad = [abs(heights[(3*i+3) % 12]-heights[3*i]) > 1.25 or
               abs(heights[(3*i+4) % 12]-heights[(3*i+2) % 12]) > 1.25 for i in range(4)]
        if force: bad = [False]*4
        expected_internal = (0x1000 if not any(bad) else 0) | (0x2000 if bad == [True, False, True, False] else 0) | (0x4000 if bad == [False, True, False, True] else 0)
        word = h.write_heights(incoming=incoming)
        assert word & 0x7000 == expected_internal, (heights, force, bad, hex(word), hex(expected_internal))
        assert word & ~0x7f00 == incoming
        groups['internal_height_connectivity'] += 1
        if len(internal_samples) < 12 and expected_internal != 0x1000 and not force:
            internal_samples.append({'heights12': heights, 'internal_edge_blocked': bad, 'runtime_word': hex(word)})
    # This complete original reset supplies real default weights from ELF
    # constants, replacing the distinct prepared weights used in the prior phase.
    h.reset(); worker = s.HEAP+0x140000; u.mem_write(worker, bytes(0xb0))
    s.call(0x15c2ce0, (worker,), limit=500000)
    native_weights = list(struct.unpack('<8f', u.mem_read(h.cost_weights, 32)))
    assert native_weights == [1., 1., 1., 1., 99999., 6., 3., 2.]
    assert bytes(u.mem_read(h.cost_grid, 0x48000)) == struct.pack('<I', 3)*(0x48000//4)
    groups['native_cost_reset_defaults'] += 1
    cost_samples = []
    bit_object = h.graph+0x2e4498; bit_data = s.HEAP+0x160000
    for state_blocked, eligible, category_byte in itertools.product([False, True], [False, True], [0, 1, 2, 3, 4, 255]):
        h.reset(); point = center
        if state_blocked: u.mem_write(h.node(point)+6, b'\x03')
        h.q(bit_object+0x10, bit_data); h.d(bit_object+0x1c, 8)
        u.mem_write(bit_data, struct.pack('<Q', (1 << 27) if eligible else 0))
        u.mem_write(h.graph+0x2d2498+point[0]+288*point[1], bytes([category_byte]))
        cost_address = h.cost_grid+4*(point[0]+288*point[1]); h.d(cost_address, 3)
        expected = 4 if state_blocked else 5 if eligible else 3 if category_byte == 0 else 7 if category_byte == 1 else 6
        s.call(0x15c2910, (h.context, h.node(point)), limit=10000)
        assert h.rd(cost_address) == expected
        cost_samples.append({'node_state3': state_blocked, 'eligible_bit': eligible,
                             'input_class_byte': category_byte, 'native_cost_category': expected,
                             'default_weight': native_weights[expected]})
        groups['cost_category_producer'] += 1
    # A constant-height island patch versus a tall full barrier. Words and node
    # masks are generated by the original producers, not written as nav inputs.
    pipeline = []
    for barrier, gap, reverse in itertools.product([False, True], [False, True], [False, True]):
        h.reset()
        for x, z in sorted(h.cells):
            height = 5. if barrier and x == 4 and not (gap and z == 6) else 0.
            u.mem_write(h.tile((x, z)), struct.pack('<12f', *([height]*12)))
        for point in sorted(h.cells): h.write_heights(point)
        s.call(0x15bc200, (h.graph, h.context), limit=2_000_000)
        start, goal = ((1, 3), (6, 3)) if not reverse else ((6, 3), (1, 3))
        # Independent graph reachability from the resulting native masks.
        seen = {start}; todo = [start]
        from npc_pathfinding_native import STEPS
        while todo:
            point = todo.pop(); node = bytes(u.mem_read(h.node(point), 40))
            for i, (dx, dz) in enumerate(STEPS):
                other = point[0]+dx, point[1]+dz
                if not node[4] & (1 << i) or other not in h.cells or other in seen: continue
                candidate = bytes(u.mem_read(h.node(other), 40))
                if other != goal and (candidate[6] == 3 or candidate[5] & 0xf5): continue
                seen.add(other); todo.append(other)
        result = s.call(0x15bd700, (h.graph, packed(start), packed(goal), h.functor), limit=2_000_000)
        assert result == (2 if goal in seen else 0)
        path = h.path(); assert bool(path) == (result == 2)
        if path: assert path[0] == start and path[-1] == goal
        pipeline.append({'tall_barrier': barrier, 'gap': gap, 'reverse': reverse, 'native_result': result, 'path': path})
        groups['height_to_node_to_search'] += 1
    result = {'cases': sum(groups.values()), 'groups': groups, 'mismatches': [],
              'height_boundary_samples': source_samples, 'internal_height_samples': internal_samples,
              'node_truth_table': node_samples, 'native_pipeline_samples': pipeline,
              'native_default_cost_weights': native_weights, 'cost_category_samples': cost_samples,
              'native_functions': {'height_to_word': '0x180d20', 'word_decoder': '0x185e70',
                                   'world_node_callback': '0x15c24a0', 'terrain_node_transform': '0x15c26b0',
                                   'iterate_grid': '0x15bc200', 'search': '0x15bd700',
                                   'cost_reset': '0x15c2ce0', 'cost_category_producer': '0x15c2910'},
              'runtime_layout': {'world_width_height': ['0x30', '0x34'], 'base_count_pointer': ['0x40', '0x48'],
                                 'word_count_pointer': ['0x60', '0x68'], 'runtime_record_stride': 52,
                                 'runtime_height_samples_f32': {'offset': 0, 'count': 12}, 'sector_attributes_u8': [48,49,50,51]},
              'word_decode': {'bit8': 'output bit2', 'bit9': 'output bit3', 'bit10': 'output bit0', 'bit11': 'output bit1',
                              'bit12': 'output bit4 only when source bit6 is clear', 'bit13': 'output bit5', 'bit14': 'output bit6'},
              'rules': ['On the tested attribute0 records, internal edge differences use an inclusive1.25 limit. No bad internal edges sets bit12; opposite bad-edge pairs set bit13 or bit14.',
                        'Incoming word bit0 bypasses internal slope comparisons. It does not bypass cross-cell height checks in the tested cases.',
                        'Constant-height neighboring triangles connect across a cell edge when delta is within[-1.25,1.25] and neighbor word bit6 is clear.',
                        'Node transform prioritizes decoded bit4, then bit5, then bit6; these generate directional flags/masks or mode1/2 and zero center direction mask.',
                        'Original reset fills cost categories with3 and weights with[1,1,1,1,99999,6,3,2]. With an empty cost-predicate registry, producer priority is node state3->category4, eligibility->5, class byte0->unchanged, byte1->7, other bytes->6.',
                        'Full original world callbacks run with an empty constraint registry and disabled crop range. Nonempty actor predicates are not substituted.'],
              'scope': 'Original runtime height/flag and terrain-to-navigation consumers, including eight native height->word->node->A* chains on reconstructed terrain. Callback checks cover direct mask upper bounds, flag low nibble, state/mode and source integrity; full resulting masks/flag bytes are recorded.',
              'limits': ['All height-writer geometry tests use sector attribute0. Other surface-type branches, NaN/infinite heights and all threshold/spread conditions remain open.',
                         'Records/world/header state are reconstructed. No14-byte preset loader, live terraform edit or original PBC content is decoded by this test.',
                         'The12-float role applies to consumed runtime records. It is not proof of original PBC first48-byte content without a verified loader/copy chain.',
                         'Actor constraint callbacks, full async worker, steering, physics solver and live island reachability are not executed.'],
              'source_reference': ['mechanics/npc_navigation_kernel_map.json', 'mechanics/terrain_native.json'],
              'dependencies_stubbed': [], 'elf_sha256': hashlib.sha256(im.data).hexdigest()}
    (ROOT/'output/mechanics/terrain_nav_flags_native.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({'cases': result['cases'], 'groups': groups, 'pipeline_results': [p['native_result'] for p in pipeline], 'mismatches': 0}), flush=True)


if __name__ == '__main__': main()
