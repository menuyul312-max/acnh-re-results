"""Bounded NPC navigation request plumbing, not a route-search simulation.

Original request writers, result predicates and polling instructions execute.
The lower controller is explicitly inactive; no pathfinder result is fabricated
by a replacement function. Grid admission is stopped at its branch boundary.
"""
from collections import Counter
from pathlib import Path
import hashlib
import itertools
import json
import struct
from native_emulator import Sandbox, regs
from unicorn import UC_HOOK_CODE

ROOT = Path(__file__).resolve().parent.parent


def main():
    s = Sandbox(); u = s.uc; im = s.image
    npc, child, owner, actor, target, parameters = [s.HEAP+n for n in
                                                 (0xa0000, 0xc0000, 0xd0000, 0xe0000, 0xf0000, 0xf1000)]
    request = npc+0x8838
    def q(p, v): u.mem_write(p, struct.pack('<Q', v))
    def d(p, v): u.mem_write(p, struct.pack('<I', v & 0xffffffff))
    def rd(p): return struct.unpack('<I', u.mem_read(p, 4))[0]
    def byte(p): return bytes(u.mem_read(p, 1))[0]
    def vec(p, value): u.mem_write(p, struct.pack('<3f', *value))
    groups = {'request_record_writers': 0, 'native_status_predicates': 0,
              'inactive_child_polling': 0, 'grid_admission_boundary_blocks': 0,
              'full_distance_rejections': 0, 'escape_state_result_dispatch_blocks': 0}
    u.mem_write(npc, bytes(0xb000)); u.mem_write(child, bytes(0x200))
    # Modes0/1 take a position; mode2 takes an actor/target integer. Parameters
    # are32 opaque bytes. The native mode2 default is separate from0/1.
    writer_samples = []
    mode2_default = bytes((7*i+13) & 255 for i in range(32))
    # This default object is in BSS and its startup initializer is not run.
    # A distinctive prepared value tests the copy source without inventing
    # original gameplay parameter values.
    u.mem_write(0x357ba08, mode2_default)
    for mode, position, use_explicit in itertools.product(range(3),
            [(0., 0., 0.), (1.25, -7.5, 23.75), (-100., 16., -5.)], [False, True]):
        u.mem_write(request, b'\xa5'*0x2100)
        default = bytes((3*i+7) & 255 for i in range(32))
        explicit = bytes((5*i+11) & 255 for i in range(32))
        u.mem_write(request+0x208c, default); u.mem_write(parameters, explicit)
        vec(target, position)
        if mode == 2: d(target, 0x345678)
        source_before = bytes(u.mem_read(target, 12))
        s.call([0xcb5150, 0xcb51c0, 0xcb5240][mode],
               (request, target, parameters if use_explicit else 0))
        wanted_params = explicit if use_explicit else default if mode < 2 else mode2_default
        assert bytes(u.mem_read(request+0x206c, 32)) == wanted_params
        assert rd(request+0x2068) == mode and byte(request+0x20ac) == 0
        if mode < 2:
            assert bytes(u.mem_read(request+0x2058, 12)) == source_before
            assert rd(request+0x2064) == 0
        else:
            assert bytes(u.mem_read(request+0x2058, 12)) == im.read(im.ptr(0x32d06b0), 12)
            assert rd(request+0x2064) == 0x345678
        assert bytes(u.mem_read(target, 12)) == source_before
        groups['request_record_writers'] += 1
        if len(writer_samples) < 3:
            writer_samples.append({'mode': mode, 'explicit_parameters': use_explicit,
                                   'native_parameter_hex': bytes(u.mem_read(request+0x206c, 32)).hex()})
    for enabled, state, status in itertools.product([0, 1, 2], [-1, 0, 1, 2], [0, 3, 4, 5]):
        u.mem_write(child+0x121, bytes([enabled])); d(child+0x58, state); d(child+0x9c, status)
        assert s.call(0xc86cc0, (child,)) == int(not enabled or state == 1 and status == 4)
        assert s.call(0xc86d00, (child,)) == int(status == 3)
        groups['native_status_predicates'] += 2
    def prepare_poll(mode, flags, enabled, status):
        u.mem_write(request, bytes(0x2100)); q(request+0x20, child)
        d(request+0x2068, mode); u.mem_write(request+0x20ac, bytes([flags]))
        u.mem_write(child, bytes(0x200)); d(child+0x58, -1)
        u.mem_write(child+0x121, bytes([enabled])); d(child+0x9c, status)
    poll_outcomes = Counter()
    for mode, flags, enabled, status in itertools.product([1, 2],
            [1, 3, 9, 0x11, 0x41, 0x81], [0, 1], [0, 3, 4]):
        prepare_poll(mode, flags, enabled, status)
        blocked = bool(flags & (0x12 if mode == 1 else 2))
        wanted = flags
        if not blocked:
            if mode == 1 and enabled == 0: wanted |= 0x10
            elif status == 3: wanted |= 2
        s.call(0xcb5370, (request,), limit=10000)
        assert byte(request+0x20ac) == wanted
        assert rd(child+0x5c) == (0 if blocked else 1)
        assert rd(child+0x58) == 0xffffffff
        poll_outcomes[f'mode{mode}:0x{wanted:02x}'] += 1
        groups['inactive_child_polling'] += 1
    # Admission gate: both coordinate conversions execute, then stop before
    # either the reject assignment or accepted-request state mutation.
    q(child, owner); q(owner+0x68, actor)
    observed = {}; gate_hook = {'stop': True}
    def trace(uc, pc, size, data):
        if pc == 0xc864d0: observed['branch'] = 'reject'
        elif pc == 0xc864d8: observed['branch'] = 'admit'
        if gate_hook['stop']: uc.emu_stop()
    hooks = [u.hook_add(UC_HOOK_CODE, trace, begin=p, end=p) for p in [0xc864d0, 0xc864d8]]
    admission = Counter(); admission_samples = []
    # All chosen points avoid the legacy coordinate conversion's negative
    # exact-multiple edge. The native-converted coordinate is checked too.
    for origin, dx, dz in itertools.product([(0, 0), (-10, 7), (12, -8)],
            [-25, -24, 0, 24, 25], [-21, -20, 0, 20, 21]):
        ax, az = origin; tx, tz = ax+dx, az+dz
        vec(actor+0x278, (5.*ax, 3., 5.*az))
        vec(target, (5.*tx+1.25, -999., 5.*tz+1.25))
        #15c0a60 returns unsigned16 lanes; even negative probes must follow
        # that actual representation before predicting the stopping branch.
        packed_actor = (ax & 0xffff, az & 0xffff)
        expected = 'admit' if abs(packed_actor[0]-tx) <= 24 and abs(packed_actor[1]-tz) <= 20 else 'reject'
        observed.clear()
        u.reg_write(regs.UC_ARM64_REG_SP, s.STACK+0x1ff000)
        u.reg_write(regs.UC_ARM64_REG_X0, child)
        u.reg_write(regs.UC_ARM64_REG_X1, target)
        u.reg_write(regs.UC_ARM64_REG_X2, 0)
        u.reg_write(regs.UC_ARM64_REG_LR, s.STOP)
        stop = 0xc864d8 if expected == 'admit' else 0xc864d0
        u.emu_start(0xc86440, s.STOP, timeout=5_000_000, count=2000)
        assert u.reg_read(regs.UC_ARM64_REG_PC) == stop, (origin, dx, dz, expected,
                hex(u.reg_read(regs.UC_ARM64_REG_PC)),
                bytes(u.mem_read(u.reg_read(regs.UC_ARM64_REG_SP), 32)).hex())
        sp = u.reg_read(regs.UC_ARM64_REG_SP)
        native_target = struct.unpack('<2i', u.mem_read(sp+8, 8))
        native_actor = struct.unpack('<2i', u.mem_read(sp+0x18, 8))
        assert native_target == (tx, tz) and native_actor == packed_actor
        # Actor coordinate is packed into unsigned16 lanes by15c0a60.
        native_delta = (native_actor[0]-native_target[0], native_actor[1]-native_target[1])
        actual_expected = 'admit' if abs(native_delta[0]) <= 24 and abs(native_delta[1]) <= 20 else 'reject'
        # Negative actor cells are wrapped by the packed coordinate helper;
        # this is a boundary test, not a valid-island coordinate assumption.
        assert actual_expected == expected
        admission[actual_expected] += 1
        groups['grid_admission_boundary_blocks'] += 1
        if actual_expected == 'reject':
            # This rejection path is also executable to its actual return.
            gate_hook['stop'] = False
            assert s.call(0xc86440, (child, target, 0), limit=10000) == 0
            gate_hook['stop'] = True
            groups['full_distance_rejections'] += 1
        if len(admission_samples) < 8:
            admission_samples.append({'world_actor': [5.*ax, 3., 5.*az],
                                      'actor_grid_native': native_actor, 'target_grid_native': native_target,
                                      'branch': actual_expected})
    for hook in hooks: u.hook_del(hook)
    # Real high-level EscapeHighCostArea update calls the request poller and
    # tests its flags. Stop before the fallback/state-change routine executes.
    escape_outcomes = Counter()
    for enabled, status in itertools.product([0, 1], [0, 3, 4]):
        prepare_poll(1, 1, enabled, status)
        fallback = enabled == 0 or status == 3
        stop = 0xc1e2c0 if fallback else s.STOP
        u.reg_write(regs.UC_ARM64_REG_SP, s.STACK+0x1ff000)
        u.reg_write(regs.UC_ARM64_REG_X0, npc)
        u.reg_write(regs.UC_ARM64_REG_LR, s.STOP)
        u.emu_start(0xc31e20, stop, timeout=5_000_000, count=3000)
        assert u.reg_read(regs.UC_ARM64_REG_PC) == stop
        if fallback:
            assert u.reg_read(regs.UC_ARM64_REG_X0) == npc
            assert u.reg_read(regs.UC_ARM64_REG_W1) == 0
            assert u.reg_read(regs.UC_ARM64_REG_X2) == im.ptr(0x32d1d60)
        escape_outcomes['fallback_dispatch' if fallback else 'remain'] += 1
        groups['escape_state_result_dispatch_blocks'] += 1
    result = {'groups': groups, 'cases': sum(groups.values()), 'mismatches': [],
              'poll_outcomes': dict(poll_outcomes), 'admission_outcomes': dict(admission),
              'escape_outcomes': dict(escape_outcomes), 'writer_samples': writer_samples,
              'admission_samples': admission_samples,
              'native_functions': {'request_writers': ['0xcb5150', '0xcb51c0', '0xcb5240'],
                                   'poll': '0xcb5370', 'child_step': '0xc86cb0',
                                   'child_fsm_step': '0x1f06900',
                                   'completion_predicate': '0xc86cc0', 'failure_predicate': '0xc86d00',
                                   'grid_request': '0xc86440', 'escape_update': '0xc31e20'},
              'layout': {'npc_request_offset': '0x8838', 'request_target_vec3': '0x2058',
                         'request_target_id': '0x2064', 'request_mode': '0x2068',
                         'request_parameters_opaque32': '0x206c', 'request_flags': '0x20ac',
                         'request_child_pointer': '0x20', 'child_state': '0x58',
                         'child_status': '0x9c', 'child_completion_enable_byte': '0x121'},
              'rules': ['Mode0/1 store a world vec3, mode2 stores an integer target; mode0/1 null parameter uses request+0x208c, mode2 uses native default32 bytes at0x357ba08.',
                        'For an already-started mode1 request, flags0x12 suppress polling; otherwise completion adds0x10, failure adds2. Mode2 suppresses on2 and only adds failure2.',
                        'Completion is true when child+0x121 is zero, or current state1 and status4. Failure is exactly status3.',
                        'The grid request compares absolute X/Z cell differences against24/20 inclusively; actor uses world+2.5 -> packed16 coordinates, target uses direct world conversion. Actor Y and target Y are not compared in this gate.',
                        'EscapeHighCostArea update dispatches0xc1e2c0 on request flags0x12; dispatch arguments checked, destination routine not executed.'],
              'scope': 'Native request data and result propagation, with a deliberately inactive lower FSM and a bounded admission block.',
              'limits': ['No route search, obstacle tests, path costs, movement integration, active child-state handler, scheduler or async navigation worker executes.',
                         'Already-started polling is tested. First-start initialization and async route collection remain open.',
                         'Admission stops before accepted-request mutation; only distance rejection cases execute the complete request function.',
                         'Parameter32 bytes remain opaque; both request-local and BSS default parameter values are prepared patterns, not recovered gameplay defaults. Startup initializers are not run.',
                         'Input coordinates and child statuses are reconstructed, not observed in a running game.',
                         'Grid threshold values are cells for this request gate, not a proven global pathfinder radius.'],
              'source_reference': 'mechanics/npc_state_registry_native.json#/states/32',
              'dependencies_stubbed': [], 'elf_sha256': hashlib.sha256(im.data).hexdigest()}
    (ROOT/'output/mechanics/npc_navigation_request_native.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({'groups': groups, 'cases': result['cases'], 'admission': dict(admission), 'mismatches': 0}), flush=True)


if __name__ == '__main__': main()
