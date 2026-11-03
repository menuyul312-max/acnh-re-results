"""Execute selected complete paths in the original active NPC route evaluator.

Native route extraction/lookahead, RNG and evaluator instructions execute.
World/actor state is prepared. Steering/geometry branches remain unexecuted.
"""
from collections import Counter
from pathlib import Path
import hashlib
import itertools
import json
import math
import random
import struct
from native_emulator import Sandbox, regs
from npc_route_handoff_native import HandoffHarness
from unicorn import UC_HOOK_CODE

ROOT = Path(__file__).resolve().parent.parent


def roll(state):
    a, b, c, d = state; n = (a ^ (a << 11)) & 0xffffffff
    value = (n ^ (n >> 8) ^ d ^ (d >> 19)) & 0xffffffff
    return value, [b, c, d, value]


def main():
    s = Sandbox(); h = HandoffHarness(s); u, im = s.uc, s.image
    child, owner, actor, metadata, model, status_obj, params, endpoint_ptr = [s.HEAP+n for n in
                   (0x60000, 0x70000, 0x71000, 0x72000, 0x73000, 0x74000, 0xa0000, 0xa1000)]
    groups = {'zero_target_failure': 0, 'endpoint_reached_priority': 0,
              'strict_distance_boundary': 0, 'last_waypoint_promotion': 0,
              'explicit_endpoint_resume': 0, 'expired_wait_rng': 0,
              'setup_evaluator_to_fsm_blocks': 0}
    samples = []; jitter = Counter(); result_pairs = Counter()
    def vec(p, values): u.mem_write(p, struct.pack('<3f', *values))
    def readvec(p): return tuple(struct.unpack('<3f', u.mem_read(p, 12)))
    def prepare(n, endpoint, position=(1., 7., 1.), waypoint=(7, 8)):
        h.prepare(n, max(n, 2))
        for i in range(n+1): u.mem_write(h.source+32*i, struct.pack('<2H', (waypoint[0]+i-1) & 0xffff, waypoint[1]))
        h.source_snapshot = None
        s.call(0x15c3570, (h.worker, h.list, h.output, h.token))
        u.mem_write(child-16, b'\xa5'*16+bytes(0x200)+b'\xa5'*16)
        for p, size in [(owner, 0x400), (actor, 0x400), (metadata, 0x100), (model, 0x500), (status_obj, 0x6000)]:
            u.mem_write(p, bytes(size))
        h.q(child, owner); h.q(owner+0x68, actor)
        h.q(owner+0x2f0, model); h.q(owner+0x2f8, status_obj)
        h.q(child+0x10, metadata); h.q(child+0xd0, h.list)
        vec(actor+0x278, position); vec(child+0xec, endpoint)
        u.mem_write(child+0x121, b'\x01')
        u.mem_write(child+0x18, struct.pack('<2f', .5, 25.))
        h.d(child+0x108, 60)
    def evaluate():
        list_before = bytes(u.mem_read(h.list, 0x30))+bytes(u.mem_read(h.pool, 48*h.capacity))
        value = s.call(0xc87710, (child,), limit=200000)
        status = h.rd(child+0x9c); result_pairs[f'{value}/{status}'] += 1
        assert list_before == bytes(u.mem_read(h.list, 0x30))+bytes(u.mem_read(h.pool, 48*h.capacity))
        assert bytes(u.mem_read(child-16, 16)) == b'\xa5'*16
        assert bytes(u.mem_read(child+0x200, 16)) == b'\xa5'*16
        return value, status
    for y in [-3., 0., 9.]:
        prepare(0, (0., 0., 0.), (1., y, 1.))
        assert evaluate() == (1, 3)
        groups['zero_target_failure'] += 1
    for n, (dx, dz), y in itertools.product([0, 1, 31], [(0., 0.), (3., 4.), (6., 8.)], [-100., 0., 100.]):
        endpoint = 1.+dx, y, 1.+dz; distance = math.hypot(dx, dz)
        prepare(n, endpoint); u.mem_write(child+0x18, struct.pack('<f', distance+.25))
        assert evaluate() == (1, 4)
        assert struct.unpack('<f', u.mem_read(child+0x110, 4))[0] == distance
        groups['endpoint_reached_priority'] += 1
    for (dx, dz), y, threshold_delta in itertools.product([(3., 4.), (6., 8.)], [-100., 0., 100.], [-.25, 0.]):
        endpoint = 1.+dx, y, 1.+dz; distance = math.hypot(dx, dz)
        prepare(1, endpoint); u.mem_write(child+0x18, struct.pack('<f', distance+threshold_delta))
        assert evaluate() == (4, 1)
        assert readvec(child+0xe0) == (35., 7., 40.)
        assert bytes(u.mem_read(child+0x121, 2)) == b'\x01\x01'
        groups['strict_distance_boundary'] += 1
        if y == 100.:
            samples.append({'case': 'strict_endpoint_boundary', 'xz_distance': distance,
                            'threshold': distance+threshold_delta, 'endpoint_y': y,
                            'next_state': 4, 'status': 1, 'promoted_waypoint_xyz': readvec(child+0xe0)})
    for direct, y, waypoint in itertools.product([False, True], [-3., 0., 9.], [(7, 8), (0, 0), (20, 30)]):
        prepare(1, (200., 100., 200.), (1., y, 1.), waypoint)
        u.mem_write(child+0x121, bytes([direct]))
        assert evaluate() == (4, 1)
        assert readvec(child+0xe0) == (5.*waypoint[0], y, 5.*waypoint[1])
        assert bytes(u.mem_read(child+0x121, 2)) == b'\x01\x01'
        groups['last_waypoint_promotion'] += 1
    for n, y in itertools.product([1, 2, 31], [-3., 0., 9.]):
        endpoint = (200., 123., 200.)
        prepare(n, endpoint, (1., y, 1.)); u.mem_write(child+0x122, b'\x01')
        assert evaluate() == (4, 1)
        assert readvec(child+0xe0) == endpoint
        groups['explicit_endpoint_resume'] += 1
    rng = random.Random(0xc87710)
    states = [[1, 2, 3, 4], [0xffffffff]*4]+[[rng.getrandbits(32) for _ in range(4)] for _ in range(48)]
    for i, state in enumerate(states):
        for pending in [False, True]:
            prepare(31, (0., 0., 0.)); u.mem_write(child+0x121, b'\0')
            u.mem_write(child+0x122, bytes([pending])); h.d(child+0x58, 4)
            limit = [1, 5, 60, 100][i % 4]
            h.d(child+0x104, limit-1); h.d(child+0x108, limit)
            u.mem_write(owner+0x288, struct.pack('<4I', *state))
            wanted, next_state = roll(state); delay = 90+30*((wanted*5) >> 32)
            assert evaluate() == (3, 2)
            assert h.rd(child+0x104) == 0 and h.rd(child+0x10c) == delay
            assert list(struct.unpack('<4I', u.mem_read(owner+0x288, 16))) == next_state
            assert readvec(child+0xe0) == readvec(actor+0x278)
            assert bytes(u.mem_read(child+0x122, 1)) == b'\0'
            jitter[str(delay)] += 1; groups['expired_wait_rng'] += 1
    # Full controller setup calls the real evaluator; stop before the generic
    # FSM transition executes. This is a larger boundary than the prior phase.
    observed = {}
    def trace(uc, pc, size, data):
        if pc == 0xc87710: observed['evaluator_calls'] = observed.get('evaluator_calls', 0)+1
        else:
            observed['manager'] = uc.reg_read(regs.UC_ARM64_REG_X0)
            observed['next'] = uc.reg_read(regs.UC_ARM64_REG_W1)
            uc.emu_stop()
    hooks = [u.hook_add(UC_HOOK_CODE, trace, begin=p, end=p) for p in [0xc87710, 0x1f067b0]]
    # The evaluator was executed above. Refresh its translated block so the
    # newly installed observation hook is emitted; original bytes stay intact.
    u.ctl_remove_cache(0xc87710, 0xc87714)
    setup_samples = []
    for name, n, endpoint, wanted_next, wanted_status in [
            ('near', 1, (1.25, 100., 1.25), 1, 4),
            ('empty', 0, (0., 0., 0.), 1, 3),
            ('last_waypoint', 1, (200., 100., 200.), 4, 1)]:
        for explicit in [False, True]:
            prepare(n, endpoint); vec(endpoint_ptr, endpoint)
            u.mem_write(params, struct.pack('<8f', .5, 25., -1., -1., -1., 0., 0., 0.))
            observed.clear(); u.reg_write(regs.UC_ARM64_REG_SP, s.STACK+0x1ff000)
            for i, value in enumerate([child, h.list, params if explicit else 0, endpoint_ptr]):
                u.reg_write(getattr(regs, 'UC_ARM64_REG_X'+str(i)), value)
            u.reg_write(regs.UC_ARM64_REG_LR, s.STOP)
            u.emu_start(0xc862b0, s.STOP, timeout=5_000_000, count=200000)
            assert u.reg_read(regs.UC_ARM64_REG_PC) == 0x1f067b0
            assert observed == {'evaluator_calls': 1, 'manager': child+0x50, 'next': wanted_next}, (name, explicit, observed)
            assert h.rd(child+0x9c) == wanted_status
            setup_samples.append({'case': name, 'explicit_parameter': explicit, 'fsm_next': wanted_next, 'status': wanted_status})
            groups['setup_evaluator_to_fsm_blocks'] += 1
    for hook in hooks: u.hook_del(hook)
    result = {'cases': sum(groups.values()), 'groups': groups, 'mismatches': [],
              'samples': samples, 'next_state_status_pairs': dict(result_pairs),
              'expired_wait_delays': dict(jitter), 'setup_samples': setup_samples,
              'native_functions': {'evaluator': '0xc87710', 'lookahead': '0xc86970',
                                   'waypoint_peek': '0x1967d30', 'rng_u32': '0x19aa0e0',
                                   'setup_entry': '0xc862b0', 'setup_stop_before': '0x1f067b0'},
              'rules': ['A zero selected vec3 returns next-state1/status3. An enabled explicit endpoint with XZ distance strictly below child+0x18 returns next-state1/status4; endpoint Y is ignored by that distance.',
                        'For the tested final-waypoint context, the evaluator promotes the remaining grid point to child+0xe0 using X/Z*5 and actor Y, sets bytes+0x121/+0x122 to1, and returns next-state4/status1.',
                        'An enabled pending explicit endpoint resumes it at child+0xe0 and returns next-state4/status1 in the tested far-target context.',
                        'Expired wait-state4 increments the counter, resets it, draws the original RNG and stores90+30*floor(u32_draw*5/2^32). It returns next-state3/status2, records actor position and clears the pending byte.',
                        'The original setup/evaluator chain reaches the generic FSM transition with checked manager and next-state arguments; transition callbacks are not run.'],
              'scope': 'Selected complete paths of the original active route evaluator, plus bounded setup through evaluator to FSM handoff.',
              'limits': ['This is not full branch coverage of0xc87710. Steering/geometry helpers0xc88310/0xc88660, nonexpired waits, interruption predicates and all state transitions remain open.',
                         'Owner, actor, controller and route state are reconstructed. No live scheduler, async worker or position/physics integration runs.',
                         'Numeric next-state indices and statuses are verified; names of all child FSM states and timer time units remain unassigned.',
                         'No completion/arrival claim is made for the full NPC game system from these bounded contexts.'],
              'source_reference': ['mechanics/npc_route_target_native.json', 'mechanics/npc_route_handoff_native.json', 'random/native_rng.json'],
              'dependencies_stubbed': [], 'elf_sha256': hashlib.sha256(im.data).hexdigest()}
    (ROOT/'output/mechanics/npc_route_evaluator_native.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({'cases': result['cases'], 'groups': groups, 'expired_wait_delays': dict(jitter), 'mismatches': 0}), flush=True)


if __name__ == '__main__': main()
