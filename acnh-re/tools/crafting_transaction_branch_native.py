"""Bounded native probes for the 0xee1420 full-pocket craft branches.

The transaction, pocket-full predicate/precheck, pocket restoration helper,
slot compactor and result award wrappers execute from the supplied ELF. The
item mutators, SaveSet event/log block, and made-recipe writer are explicitly
stubbed at their boundary; this is not a complete player transaction.
"""
from collections import Counter
import hashlib
import json
from pathlib import Path
import sqlite3
import struct
import sys

TOOLS = Path(__file__).resolve().parent
REPO = TOOLS.parent
SHARED = Path('/workspace/acnh-re')
OUT = REPO / 'output' / 'gameplay' / 'crafting_transaction_followup'
DB = SHARED / 'output' / 'index.sqlite'
sys.path.insert(0, str(SHARED / '.deps'))
sys.path.insert(0, str(TOOLS))

from unicorn import UC_HOOK_CODE, UC_HOOK_MEM_READ_UNMAPPED, UC_HOOK_MEM_WRITE_UNMAPPED  # noqa: E402
from native_emulator import Sandbox, regs  # noqa: E402
import inventory_requirements_native as item_tables  # noqa: E402
import crafting_pocket_manager_probe as pocket_probe  # noqa: E402

item_tables.ROOT = SHARED

OBSERVE = {
    0xee1420, 0xee0ed0, 0xefa9a0, 0xee147c, 0xefbd30, 0xf99270,
    0xf98650, 0xefab90, 0xefac20, 0xf987c0,
}
RESULT_TRACE_POINTS = {
    0xefac98, 0xefac9c, 0xefaca0, 0xefaca4, 0xefaca8,
    0xefacac, 0xefacb0, 0xefacb4, 0xefacb8, 0xefacbc,
    0xefad2c, 0xefad30, 0xefad54, 0xefad5c, 0xf987c0,
}
DIRTY_HELPERS = {0xf98650, 0xf98fc0, 0xf9a060, 0xf9a0c0}
SAVEPROC_FUNCTIONS = {
    0x96ef0, 0x337f00, 0x338080, 0x338120, 0xfb3160, 0xfaf180,
    0xfaf210, 0xfb4150, 0xd4240, 0xd45c0, 0xfaf360, 0xfaf4e0,
    0x2201820,
}


def sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def unpack_slot(record, index):
    start = 0xb8 + index * 8
    return list(struct.unpack('<HHI', record[start:start + 8]))


def result_route_static_audit():
    with sqlite3.connect(f'file:{DB}?mode=ro', uri=True) as db:
        def edges(owner, target):
            return [f'0x{pc:x}' for (pc,) in db.execute(
                'SELECT pc FROM direct_calls WHERE owner_va=? AND target_va=? ORDER BY pc',
                (owner, target))]

        other_insert_callers = sorted({owner for (owner,) in db.execute(
            'SELECT DISTINCT owner_va FROM direct_calls WHERE target_va=? AND owner_va IS NOT NULL',
            (0xf987c0,)) if owner != 0xefac20})
    return {
        'recipe_entry_result_path_direct_edges': [
            {'caller': '0xee1420', 'callee': '0xefab90',
             'call_sites': edges(0xee1420, 0xefab90)},
            {'caller': '0xefab90', 'callee': '0xefac20',
             'call_sites': edges(0xefab90, 0xefac20)},
            {'caller': '0xefac20', 'callee': '0xf987c0',
             'call_sites': edges(0xefac20, 0xf987c0)},
        ],
        'other_direct_f987c0_callers': [f'0x{owner:x}'
                                        for owner in other_insert_callers],
        'interpretation': 'The indexed recipe entry has one direct result-award chain through 0xefab90 -> 0xefac20 -> 0xf987c0. Other direct callers of the shared insert helper exist, but no alternate result-specific handler is called from 0xee1420.',
    }


def run_case(material_marker, occupied_slots, actor_view_link=False):
    s = Sandbox()
    u = s.uc
    table_info = item_tables.install_item_tables(s)
    fixture = pocket_probe.initialize_manager_fixture(s, None, 2213)
    addresses = fixture.pop('_addresses')
    manager = int(fixture['world_player_manager_va'], 16)
    view = struct.unpack('<Q', u.mem_read(manager + 0x118, 8))[0]
    pocket = addresses['pocket_record']

    # Reconstruct a full or one-free-slot view. Slot payloads are raw 8-byte
    # records; their last u32 meaning is deliberately not asserted here.
    u.mem_write(pocket + 0xac, struct.pack('<I', occupied_slots))
    u.mem_write(pocket + 0x158, struct.pack('<I', 20))
    empty = struct.pack('<HHI', 0xfffe, 0, 0)
    occupied = struct.pack('<HHI', 2213, 0, 1)
    u.mem_write(pocket + 0xb8,
                b''.join(occupied if i < occupied_slots else empty
                         for i in range(20)))

    recipe = s.HEAP + 0x1c0000
    context = addresses['mode_context']
    if actor_view_link:
        # Controlled accessor experiment: arrange context+0x173e0 to alias the
        # already reconstructed active view expected by 0xf8f400.
        context = view - 0x173e0
        u.mem_write(context, b'\x00')
    u.mem_write(recipe, bytes(0x120))
    u.mem_write(recipe, struct.pack('<H', 56))
    u.mem_write(recipe + 8, struct.pack('<HHI', 975, 0, 0))
    u.mem_write(recipe + 0x25, b'\x01')
    materials = [(2213, 1), (2285, 1), (2287, 1),
                 (2214, 1), (2286, 1), (0xfffe, 0)]
    for index, (item_id, amount) in enumerate(materials):
        entry = recipe + 0x2c + index * 0x14
        u.mem_write(entry, struct.pack('<HHI', item_id, 0, 0))
        u.mem_write(entry + 8, struct.pack('<H', amount))

    # This synthetic non-marker payload halfword satisfies the entry guard;
    # +0x3c then selects the first material's per-record mutation branch.
    u.mem_write(recipe + 0x38, struct.pack('<H', 1))
    u.mem_write(recipe + 0x3c, struct.pack('<H', material_marker))
    u.mem_write(context, b'\x00')

    events = []
    mutators = []
    slot_writes = []
    faults = []
    result_trace = []
    before = bytes(u.mem_read(pocket, 0x17c))

    def record_call(address):
        x = [u.reg_read(getattr(regs, f'UC_ARM64_REG_X{i}'))
             for i in range(4)]
        row = {'va': f'0x{address:x}',
               'x0_x3': [f'0x{value:x}' for value in x]}
        if address in (0xefbd30, 0xefab90, 0xefac20):
            pointer = x[1]
            row['descriptor_va'] = f'0x{pointer:x}'
            row['descriptor_bytes'] = bytes(u.mem_read(pointer, 8)).hex()
            row['descriptor_item_id'] = struct.unpack(
                '<H', u.mem_read(pointer, 2))[0]
        events.append(row)

    def code_hook(uc, address, _size, _user_data):
        if address in OBSERVE:
            record_call(address)
        if address in RESULT_TRACE_POINTS and len(result_trace) < 64:
            result_trace.append({
                'pc': f'0x{address:x}',
                'x0_x4': [f'0x{uc.reg_read(getattr(regs, f"UC_ARM64_REG_X{i}")):x}'
                          for i in range(5)],
                'x19_x22': [f'0x{uc.reg_read(getattr(regs, f"UC_ARM64_REG_X{i}")):x}'
                            for i in range(19, 23)],
            })
        if address == 0xf8f540:
            # The player-view resolver is the sole extra world-service stub.
            uc.reg_write(regs.UC_ARM64_REG_X0, view)
            uc.reg_write(regs.UC_ARM64_REG_PC,
                         uc.reg_read(regs.UC_ARM64_REG_X30))
        elif address == 0xef6700 and actor_view_link:
            # Supply only the unresolved player/actor context selection. The
            # returned context's +0x173e0 is the synthetic active-view object.
            uc.reg_write(regs.UC_ARM64_REG_X0, context)
            uc.reg_write(regs.UC_ARM64_REG_PC,
                         uc.reg_read(regs.UC_ARM64_REG_X30))
        elif address == 0xe66950 and actor_view_link:
            # Bound the unresolved actor registry to an explicit no-match result
            # so the subsequent pocket insertion leaf can be tested separately.
            uc.reg_write(regs.UC_ARM64_REG_X0, 0)
            uc.reg_write(regs.UC_ARM64_REG_PC,
                         uc.reg_read(regs.UC_ARM64_REG_X30))
        elif address == 0xeff060:
            pointer = uc.reg_read(regs.UC_ARM64_REG_X1)
            mutators.append({
                'helper': '0xeff060',
                'descriptor_bytes': bytes(uc.mem_read(pointer, 8)).hex(),
                'item_id': struct.unpack('<H', uc.mem_read(pointer, 2))[0],
                'delta_u32': uc.reg_read(regs.UC_ARM64_REG_X2) & 0xffffffff,
            })
            uc.reg_write(regs.UC_ARM64_REG_X0, 0)
            uc.reg_write(regs.UC_ARM64_REG_PC,
                         uc.reg_read(regs.UC_ARM64_REG_X30))
        elif address == 0xee1060:
            param = uc.reg_read(regs.UC_ARM64_REG_X1)
            index = uc.reg_read(regs.UC_ARM64_REG_X3) & 0xff
            pointer = param + 0x2c + index * 0x14
            mutators.append({
                'helper': '0xee1060', 'material_index': index,
                'descriptor_bytes': bytes(uc.mem_read(pointer, 8)).hex(),
                'item_id': struct.unpack('<H', uc.mem_read(pointer, 2))[0],
                'amount_u16': struct.unpack('<H', uc.mem_read(pointer + 8, 2))[0],
            })
            uc.reg_write(regs.UC_ARM64_REG_X0, 0)
            uc.reg_write(regs.UC_ARM64_REG_PC,
                         uc.reg_read(regs.UC_ARM64_REG_X30))
        elif address == 0xf98650:
            index = uc.reg_read(regs.UC_ARM64_REG_X1)
            pointer = uc.reg_read(regs.UC_ARM64_REG_X2)
            slot_writes.append({
                'slot_index': index,
                'descriptor_bytes': bytes(uc.mem_read(pointer, 8)).hex(),
            })
        elif address == 0xee147c:
            sp = uc.reg_read(regs.UC_ARM64_REG_SP)
            row = {'va': '0xee147c', 'precheck_output_bytes':
                   bytes(uc.mem_read(sp + 0x48, 8)).hex()}
            row['precheck_output_item_id'] = struct.unpack(
                '<H', uc.mem_read(sp + 0x48, 2))[0]
            events.append(row)
        elif address == 0xee1698:
            # Copy the exact result descriptor source (x22 = param2 + 8), then
            # skip the dynamic UI/event-log setup and resume at award setup.
            sp = uc.reg_read(regs.UC_ARM64_REG_SP)
            source = uc.reg_read(regs.UC_ARM64_REG_X22)
            descriptor = bytes(uc.mem_read(source, 8))
            uc.mem_write(sp + 0x30, descriptor)
            events.append({
                'va': '0xee1698',
                'synthetic_event_block_bypass': True,
                'seeded_result_descriptor_bytes': descriptor.hex(),
                'resume_va': '0xee17a8',
            })
            uc.reg_write(regs.UC_ARM64_REG_PC, 0xee17a8)
        elif address == 0xee17e0:
            # Keep made-recipe persistence outside this transaction fixture.
            uc.reg_write(regs.UC_ARM64_REG_X0, 0)
            uc.reg_write(regs.UC_ARM64_REG_PC,
                         uc.reg_read(regs.UC_ARM64_REG_X30))

    def unmapped_hook(uc, _access, address, size, _value, _user_data):
        fault_row = {'pc': f'0x{uc.reg_read(regs.UC_ARM64_REG_PC):x}',
                     'address': f'0x{address:x}', 'size': size,
                     'registers': {f'x{i}': f'0x{uc.reg_read(getattr(regs, f"UC_ARM64_REG_X{i}")):x}'
                                   for i in range(9)},
                     'sp': f'0x{uc.reg_read(regs.UC_ARM64_REG_SP):x}',
                     'lr': f'0x{uc.reg_read(regs.UC_ARM64_REG_LR):x}'}
        faults.append(fault_row)
        return False

    u.hook_add(UC_HOOK_CODE, code_hook)
    u.hook_add(UC_HOOK_MEM_READ_UNMAPPED, unmapped_hook)
    u.hook_add(UC_HOOK_MEM_WRITE_UNMAPPED, unmapped_hook)
    error = None
    native_return = None
    try:
        native_return = s.call(0xee1420, (context, recipe, context),
                               limit=2_000_000)
    except Exception as exc:  # preserve bounded-fixture failures in the artifact
        error = f'{type(exc).__name__}: {exc}'

    after = bytes(u.mem_read(pocket, 0x17c))
    count = Counter(row['helper'] for row in mutators)
    by_va = Counter(row['va'] for row in events if 'x0_x3' in row)
    result_slots_after = [
        {'slot_index': index, 'raw_record': unpack_slot(after, index)}
        for index in range(20) if unpack_slot(after, index)[0] == 975]
    compare_trace = next((row for row in result_trace
                          if row['pc'] == '0xefac98'), None)
    branch_trace = [row['pc'] for row in result_trace
                    if row['pc'] in ('0xefac9c', '0xefaca0', '0xefacb0',
                                     '0xefad2c', '0xefad30')]
    route_diagnostic = {
        'f987c0_reached': any(row['va'] == '0xf987c0'
                              for row in events if 'x0_x3' in row),
        'compare_at_0xefac98': compare_trace,
        'early_return_sequence_pcs': branch_trace,
        'result_item_slots_after': result_slots_after,
    }
    if not route_diagnostic['f987c0_reached'] and compare_trace:
        x0 = int(compare_trace['x0_x4'][0], 16)
        x19 = int(compare_trace['x19_x22'][0], 16)
        route_diagnostic.update({
            'compare_x0_equals_x19': x0 == x19,
            'route_stop_reason': ('0xefac20 takes its equality early-return branch before the pocket accessor/insertion helper; this partial actor-registry fixture resolves both operands to the same synthetic member-array pointer.'
                                  if x0 == x19 else
                                  'The route stops before 0xf987c0 for a reason not captured by the 0xefac98 equality comparison.'),
        })
    elif route_diagnostic['f987c0_reached']:
        route_diagnostic['route_stop_reason'] = '0xf987c0 executes and the pocket bytes show whether the result descriptor was inserted; the later native error, if any, occurs after this pocket mutation.'
    return {
        'case': {'material_marker_at_plus_0x3c': material_marker,
                 'occupied_pocket_slots': occupied_slots},
        'native_return': native_return,
        'native_error': error,
        'first_unmapped_accesses': faults,
        'native_entry_counts': dict(sorted(by_va.items())),
        'result_award_path_trace': result_trace,
        'result_route_diagnostic': route_diagnostic,
        'material_mutator_calls': mutators,
        'material_mutator_call_counts': dict(sorted(count.items())),
        'precheck_descriptor': next((row for row in events
                                     if row.get('precheck_output_bytes')), None),
        'pocket_restore_descriptor': next((row for row in events
                                           if row.get('va') == '0xefbd30'), None),
        'result_award_descriptor': next((row for row in events
                                         if row.get('va') == '0xefab90'), None),
        'result_slot_helper_descriptor': next((row for row in events
                                               if row.get('va') == '0xefac20'), None),
        'result_route_reached': {
            va: any(row.get('va') == va for row in events)
            for va in ('0xefab90', '0xefac20', '0xf987c0')
        },
        'pocket_slot_record_before_first_six': [
            unpack_slot(before, index) for index in range(6)],
        'pocket_slot_record_after_first_six': [
            unpack_slot(after, index) for index in range(6)],
        'result_item_slots_after': result_slots_after,
        'dirty_slot_bytes_before': list(before[0x15c:0x170]),
        'dirty_slot_bytes_after': list(after[0x15c:0x170]),
        'native_f98650_calls': len(slot_writes),
        'native_f98650_slot_indices': [row['slot_index'] for row in slot_writes],
        'changed_pocket_offsets': [f'0x{index:x}'
                                   for index, (old, new) in enumerate(zip(before, after))
                                   if old != new],
        'event_block_bypass': next((row for row in events
                                    if row.get('synthetic_event_block_bypass')), None),
        'fixture': {
            'recipe_id': 56, 'recipe_result_item_id': 975,
            'material_rows': [{'item_id': item, 'amount': amount}
                              for item, amount in materials],
            'pocket_item_id': 2213,
            'raw_record_u32_fixture_value': 1,
            'pocket_capacity': 20, 'occupied_slots': occupied_slots,
            'actor_view_link_experiment': actor_view_link,
            'transaction_context': f'0x{context:x}',
            'context_first_byte': 0,
            'synthetic_gate_halfword_offset': '0x38',
            'synthetic_gate_halfword_value': 1,
            'world_manager': fixture['world_player_manager_va'],
            'active_view': f'0x{view:x}', 'pocket_record': f'0x{pocket:x}',
            'item_table_sha256': {
                'ItemParam': table_info['item_raw_sha256'],
                'ItemKind': table_info['kind_raw_sha256'],
            },
        },
        'stubs_and_limits': [
            '0xf8f540 returns the synthetic active-view pointer; the remaining view methods execute through the two bounded method stubs in the shared fixture.',
            '0xeff060 and 0xee1060 are no-op stubs. The branch is tested, but material removal is not.',
            'At 0xee1698, the result descriptor is copied from x22 (param2+8) and execution resumes at 0xee17a8, bypassing dynamic UI/event-log setup.',
            '0xee17e0 is stubbed; made-recipe marker persistence is not tested.',
            'The player/session/save manager is partial. Result insertion is only proven to reach 0xefab90/0xefac20 when those calls appear; final inventory insertion is not assumed.',
        ],
    }


def save_dirty_marker_audit():
    with sqlite3.connect(f'file:{DB}?mode=ro', uri=True) as db:
        paths = dict(db.execute('SELECT va, path FROM decomp_new'))
        caller_rows = db.execute(
            'SELECT owner_va, target_va, pc FROM direct_calls '
            'WHERE target_va IN (?, ?, ?, ?) ORDER BY target_va, owner_va, pc',
            tuple(DIRTY_HELPERS)).fetchall()
        direct_dirty_callers = {
            f'0x{target:x}': sorted({f'0x{owner:x}' for owner, target2, _pc
                                    in caller_rows if target2 == target})
            for target in DIRTY_HELPERS
        }
        known_save = []
        for va in sorted(SAVEPROC_FUNCTIONS):
            rel = paths.get(va)
            source = (SHARED / 'output' / rel).read_text(errors='ignore') if rel else ''
            references = [line.strip() for line in source.splitlines()
                          if '0x15c' in line.lower()]
            known_save.append({
                'va': f'0x{va:x}', 'decomp_path': rel,
                'has_indexed_decomp': bool(rel),
                'direct_plus_0x15c_lines': references,
            })

    helper_roles = {
        '0xf98650': 'writes 0xff to the affected primary/secondary slot marker after slot placement',
        '0xf98fc0': 'reads the marker for a primary/secondary slot index',
        '0xf9a060': 'stores the caller-supplied marker byte',
        '0xf9a0c0': 'scans marker bytes to find a requested state',
        '0xf99270': 'compaction/move helper; calls 0xf98650 while rewriting slot records',
    }
    return {
        'pocket_dirty_marker_layout': {
            'primary_base_offset': '0x15c', 'bytes': 20,
            'secondary_base_offset': '0xa4',
            'interpretation_limit': 'Per-slot inventory/member-view marker behavior is established; durable-save semantics are not.',
        },
        'known_native_helpers': helper_roles,
        'saveproc_static_functions_checked': known_save,
        'direct_dirty_helper_callers': direct_dirty_callers,
        'direct_dirty_helper_calls_from_saveproc_functions': [
            {'owner': f'0x{owner:x}', 'target': f'0x{target:x}', 'pc': f'0x{pc:x}'}
            for owner, target, pc in caller_rows
            if owner in SAVEPROC_FUNCTIONS
        ],
        'saveproc_worker_callback_factory_unresolved': True,
        'serializer_or_flush_relation': 'UNRESOLVED: the indexed SaveProc path reaches generic worker/task objects with unresolved indirect callbacks; no direct pocket +0x15c read or call to a dirty-marker helper appears in the known SaveProc request/queue/dispatch functions.',
        'caveat': 'A callback can inspect or serialize the member through runtime-bound code without a direct +0x15c reference in the current indexed function set. Absence of a direct edge does not prove the byte is excluded from a durable snapshot.',
    }


def build_report():
    manifest = json.loads((SHARED / 'output' / 'manifest.json').read_text())
    analysis_elf = Path(manifest['source_root']) / 'A_logic' / 'main.elf'
    nso = REPO / 'inputs' / 'additional_exefs' / 'main'
    cases = {
        'full_pocket_marker_zero': run_case(0, 20),
        'full_pocket_marker_one': run_case(1, 20),
        'one_free_slot_marker_zero': run_case(0, 19),
        'full_pocket_actor_resolver_stub': run_case(0, 20, True),
        'one_free_slot_actor_resolver_stub': run_case(0, 19, True),
    }
    return {
        'schema': 'acnh.crafting.transaction_branch_native.v1',
        'scope': 'The original 0xee1420 caller, 0xee0ed0 precheck, 0xefbd30 pocket restore, 0xf99270 compactor and 0xefab90/0xefac20 result wrappers execute on bounded synthetic fixtures. This does not establish a complete save-backed craft, material removal, rollback, or durable persistence.',
        'provenance': {
            'analysis_elf_sha256': sha256(analysis_elf),
            'main_nso_sha256': sha256(nso),
            'shared_index': str(DB),
            'recipe_table': 'RecipeCraftParam UniqueID=56, output=975',
        },
        'cases': cases,
        'branch_findings': {
            'full_pocket': '20 occupied slots cause 0xee1420 to call 0xee0ed0 and then 0xefbd30; a 19/20 pocket skips both, including 0xf99270.',
            'material_descriptor': 'In the full fixture, 0xee0ed0 copies Material1 (item 2213) to the temporary output, and 0xefbd30 receives those exact 8 bytes. This is separate from the result descriptor.',
            'per_material_marker': 'At +0x3c (Material1 record +0x10), zero routes all six material rows through 0xee1060. One routes Material1 through 0xeff060 while five unmarked rows still use 0xee1060.',
            'result_descriptor': 'The result ID 975 from param2+8 reaches 0xefab90 then 0xefac20 after the pocket-full path. In the unmodified partial actor-registry fixture, 0xefac20 takes an equality early return at 0xefac98 before pocket lookup; controlled no-match variants subsequently reach 0xf987c0 and mutate a free slot.',
            'result_insert_static_route': result_route_static_audit(),
            'result_insert_fixture_followup': 'With a controlled actor resolver and explicit no-match registry response, the real 0xf987c0 is reached. In the 19/20 case it writes result 975 into slot 19 and sets marker +0x16f to 0xff without calling 0xf98650. In the 20/20 case, preceding native compaction opens slots and 975 appears in slot 4; the marker range was already set by compaction. These synthetic cases prove the insert helper mutation, not a complete live-game award or save.',
            'compaction_observation': 'On the synthetic 20-record fixture (each raw record [2213,0,1]), 0xf99270 rewrote 24 slots through 0xf98650; the first four raw records became [2213,0,9], the remaining slots became [65534,0,0], and all 20 primary dirty bytes became 0xff. The u32 payload field is reported raw; its gameplay count meaning and conservation rule are not established.',
        },
        'dirty_marker_save_audit': save_dirty_marker_audit(),
        'transaction_limits': [
            'The per-material mutators 0xeff060/0xee1060 were stubbed, so no material subtraction or transaction balance is observed.',
            'The entry gate halfword at +0x38 was set synthetically to reach the +0x3c toggle; the payload was not produced by the real UI result builder 0xedf8e0 in this test.',
            'No interruption/cancellation was injected while native transaction instructions were executing. Atomicity and rollback remain open.',
            'The dirty marker is proven to be written during pocket slot rewrites, but its consumption by a real SaveProc serializer/durable flush remains open because the callback target is runtime-bound.',
        ],
    }


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    output = OUT / 'crafting_transaction_branch_native.json'
    output.write_text(json.dumps(build_report(), indent=2, ensure_ascii=False) + '\n')
    print(output)


if __name__ == '__main__':
    main()
