#!/usr/bin/env python3
"""Probe the native HHA rank classifier at its house-level score boundaries.

The original 0x7b3ff0 NSO instructions sum the twelve score categories and set
the per-player result ordinal at record +8. Save-node and player-validity
accessors are controlled stubs; the score sum, house-level dispatch, threshold
comparisons, and result stores execute natively.
"""
from pathlib import Path
import hashlib
import json
import re
import sqlite3
import struct
import sys

TOOLS = Path(__file__).resolve().parent
REPO = TOOLS.parent
DATA = Path('/workspace/acnh-re')
NSO = DATA / 'inputs/additional_exefs/main'
DB = DATA / 'output/index.sqlite'
DECOMP = DATA / 'output/binary/analysis_decomp'
POINTER_ARRAYS = DATA / 'output/binary/code_pointer_arrays.json'
MESSAGES = DATA / 'output/additional_romfs/messages/USen/String.json'
MAIL_MESSAGES = DATA / 'output/additional_romfs/messages/USen/Mail.json'
NATIVE_FLAGS = DATA / 'output/gameplay/native_flag_refs.json'
FLAG_INDEX = DATA / 'output/gameplay/flag_index.json'
EVENT_HANDLERS = DATA / 'output/binary/event_handlers_resolved.json'
OUT = REPO / 'output/gameplay/house_hha_followup/hha_rank_threshold_native.json'

NSO_SHA256 = 'f8d248109ff72999b4600ae3749f8c7397fb960f7ad3ab8dee3018ae9e14e900'
FUNCTION = 0x7B3FF0
EVALUATOR = 0x7B1FE0
CALL_PC = 0x7B29B4
LEVEL_TABLE = 0x29F7AAA
LEVEL_TABLE_BYTES = bytes.fromhex('0009121b242d3b')
REPORT_CANDIDATE_FUNCTION = 0x7B4FC0
REPORT_LABEL_FUNCTION = 0x7B6470
REPORT_DISPATCH_PC = 0x7B52B0
REPORT_DISPATCH_TABLE = 0x29F7ACA
REPORT_DISPATCH_TABLE_BYTES = bytes.fromhex('2c000306090c0f98161a1e2124272a')
REPORT_DISPATCH_BASE = 0x7B64C8
REPORT_ORDINAL_TARGETS = [0x7B6578, 0x7B64C8, 0x7B64D4]
RANK_ROW_OFFSETS = [0x24 + 4 * i for i in range(12)]

# Each native comparison is against (threshold - 1), with signed <= on the
# first boundary and signed > on the second. The labels below are subsequently
# cross-checked against the original instruction immediates.
LEVEL_THRESHOLDS = [
    {'house_level_raw': 2, 'b_max': 9_999, 'a_max': 14_999},
    {'house_level_raw': 3, 'b_max': 16_999, 'a_max': 22_999},
    {'house_level_raw': 4, 'b_max': 24_999, 'a_max': 34_999},
    {'house_level_raw': 5, 'b_max': 37_999, 'a_max': 46_999},
    {'house_level_raw': 6, 'b_max': 49_999, 'a_max': 59_999},
    {'house_level_raw': 7, 'b_max': 63_999, 'a_max': 74_999},
    {'house_level_raw': 8, 'b_max': 79_999, 'a_max': 89_999},
]
COMPARE_IMMEDIATE_VAS = {
    2: (0x7B41E4, 0x7B41F0),
    3: (0x7B4208, 0x7B4214),
    4: (0x7B422C, 0x7B4238),
    5: (0x7B4250, 0x7B425C),
    6: (0x7B4274, 0x7B4280),
    7: (0x7B4298, 0x7B42A4),
    8: (0x7B42D0, 0x7B42F8),
}
RANK_LABELS = {0: ('001', 'S'), 1: ('002', 'A'), 2: ('003', 'B')}

if (DATA / '.deps').is_dir():
    sys.path.insert(0, str(DATA / '.deps'))
sys.path.insert(0, str(TOOLS))
from capstone import Cs, CS_ARCH_ARM64, CS_MODE_ARM  # noqa: E402
from exefs_modules import NsoModule  # noqa: E402
from nso_sandbox import Sandbox  # noqa: E402


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def disassemble(nso, start, size):
    decoder = Cs(CS_ARCH_ARM64, CS_MODE_ARM)
    return {ins.address: ins for ins in decoder.disasm(nso.read(start, size), start)}


def immediate(ins):
    match = re.fullmatch(r'w\d+, #0x([0-9a-f]+)', ins.op_str)
    if ins.mnemonic != 'mov' or not match:
        raise AssertionError({'expected_mov_imm32': (hex(ins.address), ins.mnemonic, ins.op_str)})
    return int(match.group(1), 16)


def read_mov32(insns, address):
    value = immediate(insns[address])
    next_ins = insns.get(address + 4)
    if next_ins and next_ins.mnemonic == 'movk' and 'lsl #16' in next_ins.op_str:
        match = re.fullmatch(r'w\d+, #(0x[0-9a-f]+|\d+), lsl #16', next_ins.op_str)
        if not match:
            raise AssertionError({'unexpected_movk': (hex(next_ins.address), next_ins.op_str)})
        part = match.group(1)
        value |= int(part, 16 if part.startswith('0x') else 10) << 16
    return value


def load_static_evidence():
    nso = NsoModule(NSO.read_bytes())
    assert sha256(NSO) == NSO_SHA256
    assert nso.read(LEVEL_TABLE, len(LEVEL_TABLE_BYTES)) == LEVEL_TABLE_BYTES
    insns = disassemble(nso, FUNCTION, 0x330)

    table_offsets = list(nso.read(LEVEL_TABLE, len(LEVEL_TABLE_BYTES)))
    table_targets = [0x7B41DC + 4 * offset for offset in table_offsets]
    expected_targets = [0x7B41DC, 0x7B4200, 0x7B4224, 0x7B4248,
                        0x7B426C, 0x7B4290, 0x7B42C8]
    if table_targets != expected_targets:
        raise AssertionError({'level_branch_table': [hex(x) for x in table_targets]})

    immediate_crosswalk = {}
    for level, (low_va, high_va) in COMPARE_IMMEDIATE_VAS.items():
        low, high = read_mov32(insns, low_va), read_mov32(insns, high_va)
        row = next(x for x in LEVEL_THRESHOLDS if x['house_level_raw'] == level)
        if (low, high) != (row['b_max'], row['a_max']):
            raise AssertionError({'level': level, 'expected': (row['b_max'], row['a_max']),
                                  'actual': (low, high)})
        immediate_crosswalk[str(level)] = {
            'b_max_compare_pc': hex(low_va), 'b_max_immediate': low,
            'a_max_compare_pc': hex(high_va), 'a_max_immediate': high,
        }

    db = sqlite3.connect(f'file:{DB}?mode=ro', uri=True)
    db.row_factory = sqlite3.Row
    calls = [dict(r) for r in db.execute(
        'SELECT pc,target_va,instruction FROM direct_calls WHERE target_va=? ORDER BY pc',
        (FUNCTION,))]
    matching_calls = [r for r in calls if r['pc'] == CALL_PC]
    if len(matching_calls) != 1:
        raise AssertionError({'expected_evaluator_call': calls})
    owner = db.execute(
        'SELECT va,name,span_end_va,evidence FROM native_functions '
        'WHERE va<=? AND span_end_va>? ORDER BY (span_end_va-va),va',
        (CALL_PC, CALL_PC)).fetchone()
    if not owner or owner['va'] != EVALUATOR:
        raise AssertionError({'unexpected_call_owner': dict(owner) if owner else None})

    flag_refs = [r['text'] for r in db.execute(
        'SELECT text FROM string_refs WHERE function_va=? ORDER BY text', (0x7B4A20,))]
    rank_ui_refs = {
        hex(function): [r['text'] for r in db.execute(
            'SELECT text FROM string_refs WHERE function_va=? ORDER BY text', (function,))]
        for function in (0xAC2E30, 0xAC3360)
    }
    if 'GetSRankonHHA' not in flag_refs:
        raise AssertionError({'missing_s_rank_flag_ref': flag_refs})
    if any('STR_HHA_Rank' not in refs for refs in rank_ui_refs.values()):
        raise AssertionError({'missing_rank_ui_resource_ref': rank_ui_refs})

    # The report bucket carries the evaluator's rank ordinal into a candidate
    # bitmask, randomly chooses one of the set report candidates, and maps bit
    # positions 0/1/2 to the Grade package's numeric label codes 040/041/042.
    report_bucket = (DECOMP / '7b4fc0.c').read_text()
    report_labeler = (DECOMP / '7b6470.c').read_text()
    if 'uStack_40 = *(uint *)(lVar7 + 8);' not in report_bucket:
        raise AssertionError('0x7b4fc0 no longer reads result ordinal at row +8')
    if 'uVar11 = 1 << (ulong)(uStack_40 & 0x1f);' not in report_bucket:
        raise AssertionError('0x7b4fc0 no longer inserts rank ordinal into candidate mask')
    if 'uVar5 = (ulong)(uVar11 | 0x7800);' not in report_bucket:
        raise AssertionError('0x7b4fc0 candidate report-mask composition changed')
    if 'FUN_01053450(0,uVar5 & 0xffffffff);' not in report_bucket:
        raise AssertionError('0x7b4fc0 no longer chooses a candidate index from the mask population')
    if 'FUN_01a8b630(uVar5,iVar10 + 1);' not in report_bucket:
        raise AssertionError('0x7b4fc0 no longer resolves the selected set-bit index')
    if 'uVar8 = 0x28;' not in report_labeler or 'uVar8 = 0x29;' not in report_labeler or 'uVar8 = 0x2a;' not in report_labeler:
        raise AssertionError('0x7b6470 rank candidate labels 40/41/42 changed')

    report_table = nso.read(REPORT_DISPATCH_TABLE, len(REPORT_DISPATCH_TABLE_BYTES))
    if report_table != REPORT_DISPATCH_TABLE_BYTES:
        raise AssertionError({'report_candidate_switch_table': report_table.hex()})
    report_targets = [REPORT_DISPATCH_BASE + 4 * value for value in report_table]
    if report_targets[:3] != REPORT_ORDINAL_TARGETS:
        raise AssertionError({'report_candidate_switch_targets': [hex(x) for x in report_targets[:3]]})
    report_insns = disassemble(nso, REPORT_LABEL_FUNCTION, 0x2D0)
    report_codes = {
        0: immediate(report_insns[0x7B64C0]),
        1: immediate(report_insns[0x7B64CC]),
        2: immediate(report_insns[0x7B64D8]),
    }
    if report_codes != {0: 40, 1: 41, 2: 42}:
        raise AssertionError({'rank_ordinal_to_grade_candidate': report_codes})

    report_choice_insns = disassemble(nso, REPORT_CANDIDATE_FUNCTION, 0x320)
    expected_choice_insns = {
        0x7B5288: ('bl', '#0x198b590'),
        0x7B528C: ('mov', 'w1, w0'),
        0x7B5290: ('mov', 'w0, wzr'),
        0x7B5294: ('bl', '#0xf53450'),
        0x7B5298: ('add', 'w1, w0, #1'),
        0x7B529C: ('mov', 'w0, w20'),
        0x7B52A0: ('bl', '#0x198b630'),
        0x7B52A8: ('mov', 'w2, w0'),
        REPORT_DISPATCH_PC: ('bl', '#0x7b6470'),
    }
    choice_sequence = {}
    for address, expected in expected_choice_insns.items():
        ins = report_choice_insns[address]
        actual = (ins.mnemonic, ins.op_str)
        if actual != expected:
            raise AssertionError({'candidate_choice_instruction': hex(address),
                                  'expected': expected, 'actual': actual})
        choice_sequence[hex(address)] = {'mnemonic': ins.mnemonic, 'op_str': ins.op_str}

    report_calls = [dict(r) for r in db.execute(
        'SELECT pc,owner_va,target_va,instruction FROM direct_calls '
        'WHERE (pc=? AND target_va=?) OR (pc=? AND target_va=?) OR (pc=? AND target_va=?)',
        (0x7B5294, 0xF53450, 0x7B52A0, 0x198B630, REPORT_DISPATCH_PC, REPORT_LABEL_FUNCTION))]
    expected_report_edges = {
        (0x7B5294, 0xF53450), (0x7B52A0, 0x198B630),
        (REPORT_DISPATCH_PC, REPORT_LABEL_FUNCTION),
    }
    if {(r['pc'], r['target_va']) for r in report_calls} != expected_report_edges:
        raise AssertionError({'report_candidate_call_edges': report_calls})
    setbit_decomp = (DECOMP / '198b630.c').read_text()
    popcount_decomp = (DECOMP / '198b590.c').read_text()
    bounded_rng_decomp = (DECOMP / 'f53450.c').read_text()
    rng_step_decomp = (DECOMP / '19aa0e0.c').read_text()
    if 'uVar1 = (param_1 & -param_1) - 1;' not in setbit_decomp or 'return uVar1 + (uVar1 >> 0x10)' not in setbit_decomp:
        raise AssertionError('0x198b630 no longer selects the requested set bit')
    if '0x55555555' not in popcount_decomp:
        raise AssertionError('0x198b590 no longer computes the report-mask population')
    if 'uVar1 = 0x36e9510;' not in bounded_rng_decomp or 'FUN_01aaa0e0(0x36e9510);' not in bounded_rng_decomp:
        raise AssertionError('0xf53450 no longer draws from the shared four-word PRNG state')
    if 'return (int)((uVar1 & 0xffffffff) *' not in bounded_rng_decomp or '(param_2 - param_1) >> 0x20) + param_1;' not in bounded_rng_decomp:
        raise AssertionError('0xf53450 bounded PRNG scaling changed')
    if '*param_1 ^ *param_1 << 0xb' not in rng_step_decomp or 'uVar2 >> 0x13' not in rng_step_decomp:
        raise AssertionError('0x1aaa0e0 four-word xorshift step changed')

    mail_messages = json.loads(MAIL_MESSAGES.read_text())['members']
    grade_mail = mail_messages['Sp/HHA/MAIL_SP_HHA_Grade.msbt']['messages']
    grade_mail_rows = {row['labels'][0]: row.get('text', '') for row in grade_mail if row.get('labels')}
    for label in ('040', '041', '042', '140', '141', '142'):
        if label not in grade_mail_rows:
            raise AssertionError({'missing_grade_mail_label': label})
    body_rank_crosswalk = {
        '140': 'S', '141': 'A', '142': 'B',
    }
    for label, rank in body_rank_crosswalk.items():
        if rank + ' rank' not in grade_mail_rows[label]:
            raise AssertionError({'grade_mail_body_rank_mismatch': (label, rank)})

    # The HHA queue's type-3 consumer formats its localized record and hands
    # the result to the same generic save-backed message collection used by
    # the registered EventFlow SystemMailSend action. The two possible content
    # classes insert into 100 or 40 slots; static evidence does not tell which
    # class a live HHA output takes or when it becomes a visible mailbox item.
    insertion_decomp = {
        name: (DECOMP / f'{name}.c').read_text()
        for name in ('ac0a60', 'abfb40', 'ac1ff0', 'ac8840', 'ac87c0',
                     'fadfc0', 'fae7b0', 'f6f040', 'f73900', 'f6b700', 'f6b840')
    }
    for name, token in {
        'ac0a60': '0x2633d0',
        'abfb40': 'FUN_00bc1ff0',
        'ac1ff0': 'FUN_00bc8840',
        'ac8840': 'FUN_010adfc0',
        'ac87c0': 'FUN_010ae7b0',
        'fadfc0': '0xe2900',
        'fae7b0': '0x180880',
        'f6f040': 'memcpy(param_1 + 0x372,param_2 + 0x372,0x2003)',
        'f73900': 'FUN_0106d6d0(param_1,param_2)',
        'f6b700': 'FUN_0106f040(param_1,param_2)',
        'f6b840': 'FUN_01073900(param_1,param_2)',
    }.items():
        if token not in insertion_decomp[name]:
            raise AssertionError({'message_insert_path_check_failed': (name, token)})

    system_mail_binding = json.loads(EVENT_HANDLERS.read_text())['entries'][
        'EventFlowSystemActor.EventFlowActionSystemMailSend']
    if system_mail_binding['constructor'] != '0x345640' or '0x345890' not in system_mail_binding['slots']:
        raise AssertionError({'unexpected_system_mail_action_binding': system_mail_binding})
    mail_action_function = next(r for r in json.loads(POINTER_ARRAYS.read_text())
                                if r.get('start_va') == system_mail_binding['vtable'])
    if not any(entry.get('target_va') == '0x345890' for entry in mail_action_function.get('entries', [])):
        raise AssertionError('SystemMailSend method 0x345890 missing from its relocated code pointer sequence')
    system_mail_edges = [dict(r) for r in db.execute(
        'SELECT pc,owner_va,target_va,instruction FROM direct_calls '
        'WHERE pc IN (0x345f84,0x345f94,0x346048,0x346058) ORDER BY pc')]
    system_mail_expected = {
        (0x345F84, 0xAC77A0), (0x345F94, 0x346A50),
        (0x346048, 0xAC77A0), (0x346058, 0x346A50),
    }
    if {(r['pc'], r['target_va']) for r in system_mail_edges} != system_mail_expected:
        raise AssertionError({'system_mail_record_and_dispatch_edges': system_mail_edges})
    system_mail_route_decomp = (DECOMP / '346a50.c').read_text()
    if 'FUN_00bc1ff0(param_1,lVar1 + lVar6,&uStack_68' not in system_mail_route_decomp:
        raise AssertionError('SystemMailSend route no longer reaches the shared generic record handler')
    hha_route_decomp = (DECOMP / 'ac1ff0.c').read_text()
    if 'FUN_00bc8840' not in hha_route_decomp or 'FUN_00bc87c0' not in hha_route_decomp:
        raise AssertionError('HHA formatter output no longer dispatches to either save-backed message collection')
    mail_flow_rows = [dict(r) for r in db.execute(
        "SELECT flow,event_index,actor,kind,name,params_json FROM event_calls "
        "WHERE params_json LIKE '%MAIL_SP_HHA%' OR params_json LIKE '%cHHA%' "
        "ORDER BY flow,event_index")]
    grade_event_rows = [r for r in mail_flow_rows if 'MAIL_SP_HHA_Grade' in r['params_json']
                        or 'HHAGradeMailFlag' in r['params_json']]
    if grade_event_rows:
        raise AssertionError({'unexpected_grade_eventflow_action': grade_event_rows})
    build_mail_rows = [r for r in mail_flow_rows if 'MAIL_SP_HHA_BuildCelebration' in r['params_json']]
    if len(build_mail_rows) != 1:
        raise AssertionError({'hha_eventflow_mail_actions': mail_flow_rows})
    grade_flag_flow_rows = [dict(r) for r in db.execute(
        "SELECT flow,event_index,actor,kind,name,params_json FROM event_calls "
        "WHERE params_json LIKE '%HHAGradeMailFlag%' ORDER BY flow,event_index")]
    db.close()
    if grade_flag_flow_rows:
        raise AssertionError({'unexpected_hha_grade_flag_eventflow_access': grade_flag_flow_rows})

    decomp_7b4a20 = (DECOMP / '7b4a20.c').read_text()
    if '*(int *)(*(long *)(param_1 + 0xb10) + 8) == 0' not in decomp_7b4a20:
        raise AssertionError('0x7b4a20 no longer shows the rank-code-zero branch')
    if 'FUN_01062fb0(&iStack_38,&lStack_58,1)' not in decomp_7b4a20:
        raise AssertionError('0x7b4a20 no longer shows the GetSRankonHHA update call')
    rank_ui_decomps = {}
    for function in (0xAC2E30, 0xAC3360):
        path = DECOMP / f'{function:x}.c'
        source = path.read_text()
        if '*param_1 + 1' not in source:
            raise AssertionError({'rank_ui_mapping_missing': hex(function)})
        rank_ui_decomps[hex(function)] = {
            'path': str(path), 'sha256': sha256(path),
            'uses_zero_based_rank_value_plus_one_for_STR_HHA_Rank': True,
        }

    messages = json.loads(MESSAGES.read_text())['members']
    rank_resource = messages['Sp/HHA/STR_HHA_Rank.msbt']['messages']
    rank_labels = {row['labels'][0]: row.get('text') for row in rank_resource}
    if rank_labels != {'001': 'S', '002': 'A', '003': 'B'}:
        raise AssertionError({'unexpected_rank_labels': rank_labels})

    pointers = json.loads(POINTER_ARRAYS.read_text())
    rank_vtable_slots = []
    for array in pointers:
        for entry in array.get('entries', []):
            if entry.get('target_va') in ('0x7b8270', '0x7b8420'):
                rank_vtable_slots.append({
                    'array_start': array['start_va'],
                    'pointer_va': entry['pointer_va'],
                    'target_va': entry['target_va'],
                    'byte_slot_from_address_point': int(entry['pointer_va'], 16)
                    - int(array['start_va'], 16),
                })
    if not rank_vtable_slots:
        raise AssertionError('rank UI string-builder trampolines absent from pointer sequences')

    native_flags = json.loads(NATIVE_FLAGS.read_text())['data']['flags']
    s_rank_refs = native_flags['cLifeSupportAchievement:GetSRankonHHA']
    if '0x7b4a20' not in s_rank_refs['referencing_functions']:
        raise AssertionError({'unexpected_s_rank_native_refs': s_rank_refs})
    grade_mail_flag_native = native_flags['cPlayer:HHAGradeMailFlag']
    if grade_mail_flag_native['referencing_functions'] != ['0x7b1fe0'] or grade_mail_flag_native['pseudocode_readings']:
        raise AssertionError({'unexpected_grade_mail_flag_native_refs': grade_mail_flag_native})
    grade_mail_flag_flow = json.loads(FLAG_INDEX.read_text())['data']['cPlayer:HHAGradeMailFlag']
    if grade_mail_flag_flow['eventflow_readers'] or grade_mail_flag_flow['eventflow_writers']:
        raise AssertionError({'unexpected_grade_mail_flag_eventflow_refs': grade_mail_flag_flow})
    evaluator_decomp = (DECOMP / '7b1fe0.c').read_text()
    if 'FUN_0104b0d0(*plVar1 + 0x158,&lStack_1400,1);' not in evaluator_decomp:
        raise AssertionError('HHA evaluator no longer contains the grade-mail native flag setter')
    if '(*(int *)(*plVar1 + 0x158) != -1) && (1 < (int)auStack_1428[0])' not in evaluator_decomp:
        raise AssertionError('grade-mail setter guard (cached byte and raw level) changed')
    return {
        'main_nso_sha256': NSO_SHA256,
        'evaluator_call': {
            'pc': hex(CALL_PC), 'target': hex(FUNCTION),
            'owner': hex(owner['va']), 'owner_name': owner['name'],
            'instruction': matching_calls[0]['instruction'],
        },
        'classifier_disassembly': {
            'function': hex(FUNCTION),
            'category_score_offsets': [hex(x) for x in RANK_ROW_OFFSETS],
            'total_score_output_offset': '0x110',
            'result_rank_ordinal_offset': '0x8',
            'house_level_table_va': hex(LEVEL_TABLE),
            'house_level_table_bytes': LEVEL_TABLE_BYTES.hex(),
            'branch_targets_for_raw_levels_2_to_8': [hex(x) for x in table_targets],
            'comparison_immediates': immediate_crosswalk,
            'rank_result_stores': {
                'ordinal_2_below_or_at_b_max': '0x7b42e0',
                'ordinal_1_above_b_max_through_a_max': '0x7b4308',
                'ordinal_0_above_a_max': '0x7b42b4',
            },
        },
        'rank_ordinal_crosswalk': {
            'code_zero_is_s_rank': {
                'evidence': '0x7b4a20 branches when evaluator row +8 == 0 and updates native flag GetSRankonHHA',
                'native_flag_referencing_function': '0x7b4a20',
            },
            'rank_ui_labels': rank_labels,
            'rank_ui_functions': rank_ui_decomps,
            'hha_vtable_trampolines': rank_vtable_slots,
            'grade_report_candidate': {
                'evaluator_result_offset': '0x8',
                'candidate_mask': '0x7b4fc0 includes bit (1 << evaluator row +0x08) plus report-condition bits',
                'candidate_choice': {
                    'random_range': 'bounded xorshift-derived selection in [0, popcount(mask)) via 0xf53450; state at 0x36e9510 is advanced by 0x1aaa0e0',
                    'native_instruction_sequence': choice_sequence,
                    'set_bit_resolver': '0x198b630 maps the random ordinal to the corresponding set-bit index',
                    'dispatch_call': {'pc': hex(REPORT_DISPATCH_PC), 'target': hex(REPORT_LABEL_FUNCTION)},
                },
                'rank_ordinal_to_grade_record_label_code': {
                    str(key): value for key, value in report_codes.items()
                },
                'grade_package_selector': 11,
                'grade_archive_labels_present': ['040', '041', '042', '140', '141', '142'],
                'archive_body_rank_crosswalk': body_rank_crosswalk,
                'limits': [
                    'The S/A/B record candidate is one member of a randomly chosen report-candidate mask; it is not selected on every evaluation.',
                    'Native record label codes 40/41/42 are passed as the +0x38 input to the Grade package formatter. The matching 140/141/142 archive bodies explicitly name S/A/B, but this pass did not prove the formatter expands base label N to body label N+100.',
                ],
            },
            'save_backed_message_insertion': {
                'hha_queue_path': ['0x7b6470', '0xabf610', '0xac0a60', '0xabfb40', '0xac1ff0'],
                'save_data_offset': '0x2633d0',
                'formatted_output_dispatch': {
                    '100_slot_collection': {'handler': '0xac8840', 'append': '0xfadfc0', 'slot_count': 100, 'entry_stride': '0x2440'},
                    '40_slot_collection': {'handler': '0xac87c0', 'append': '0xfae7b0', 'slot_count': 40, 'entry_stride': '0x99d0'},
                    'state_mark': 2,
                },
                'system_mail_action': {
                    'registration_hash': system_mail_binding['registration_hash'],
                    'vtable': system_mail_binding['vtable'],
                    'method_va': '0x345890',
                    'record_builder_edges': ['0x345f84 -> 0xac77a0', '0x346048 -> 0xac77a0'],
                    'route_dispatch_edges': ['0x345f94 -> 0x346a50', '0x346058 -> 0x346a50'],
                    'shared_handler': '0xac1ff0',
                },
                'indexed_hha_eventflow_actions': mail_flow_rows,
                'grade_eventflow_actions': [],
                'grade_mail_flag': {
                    'definition': grade_mail_flag_flow['definition'],
                    'eventflow_readers': grade_mail_flag_flow['eventflow_readers'],
                    'eventflow_writers': grade_mail_flag_flow['eventflow_writers'],
                    'native_name_xrefs': grade_mail_flag_native['referencing_functions'],
                    'native_setter_function': '0x7b1fe0',
                    'native_setter_guard': 'player slot nonzero; raw house selector > 1; cached signed byte at SavePlayerHouse + 0x263d0 != -1',
                    'reads_or_clearers': [],
                    'limits': 'Native string/xref and decompilation evidence identifies the setter only. No reader/clearer was found in the indexed native pseudocode or EventFlow; another consumer may remain unindexed or require runtime observation.',
                },
                'scope': 'Static code proves HHA text output reaches a save-backed message collection through the shared record handler also used by the SystemMailSend action. The HHA formatter can dispatch to either 100-slot or 40-slot collection depending on output markers. No runtime capture ties the HHA output to a visible mailbox entry or delivery date.',
            },
            'limits': [
                'The evaluator rank ordinal, the S-rank achievement branch, and rank string labels agree on the 0/1/2 ordering; the indexed direct call graph does not contain a complete evaluator-result-to-UI object construction edge.',
                'Rank thresholds use native total +0x110, which is the sum of twelve category fields. This does not resolve the remaining theme/situation bonus weights or the source of each per-item category score.',
            ],
        },
        'queue_and_mail_scope': {
            'hha_grade_record_formatter': '0xac7a00 formats a record through the localized text builder; type-3 dispatch then stores formatted output in a save-backed 100-slot or 40-slot message collection through 0xac8840/0xac87c0.',
            'system_mail_comparison': 'The EventFlow SystemMailSend action method 0x345890 uses record builder 0xac77a0 and route dispatcher 0x346a50. Its cFastToday/cFastTomorrow branches dispatch through record virtual slot +0x30 to 0xac7070 and write to route-specific save-side record arrays; only the cSlowRetry TagType=cNone branch attempts the shared handler 0xac1ff0 before its fallback. HHA grade output is a separate native producer/queue path, not an indexed EventFlow SystemMailSend action.',
            'grade_mail_flag': 'The indexed literal flag reference remains only in 0x7b1fe0, with no EventFlow readers/writers; no reader/clear or delivery timing was found.',
            'scope': 'The save-backed message-list insertion path is statically resolved, but visible mailbox arrival, HHA flag consumption, and delivery timing still require runtime capture.',
        },
    }


def run_native_cases():
    sb = Sandbox(NSO)
    evaluator = sb.alloc(0xC00)
    row = sb.alloc(0x160)
    view = sb.alloc(0x20)
    level_storage = sb.alloc(4)
    sb.uc.mem_write(evaluator + 0xB10, struct.pack('<Q', row))
    sb.uc.mem_write(view + 8, struct.pack('<Q', 0))
    sb.uc.mem_write(view + 16, struct.pack('<Q', level_storage))
    stub_calls = {'player_validity': 0, 'save_accessor_open': 0, 'save_accessor_close': 0}

    def player_validity(sandbox):
        stub_calls['player_validity'] += 1
        return 1

    def open_level_view(sandbox):
        stub_calls['save_accessor_open'] += 1
        out = sandbox.reg('x0')
        sandbox.uc.mem_write(out + 8, struct.pack('<Q', view))
        return None

    def close_level_view(_sandbox):
        stub_calls['save_accessor_close'] += 1
        return None

    sb.stub(0xEF8260, player_validity)
    sb.stub(0xEE9350, open_level_view)
    sb.stub(0xEE93D0, close_level_view)

    cases = []

    def run_case(case_id, level, score, expected_ordinal, category_scores=None):
        sb.uc.mem_write(row, bytes(0x160))
        scores = category_scores or [score] + [0] * 11
        if len(scores) != 12 or sum(scores) != score:
            raise AssertionError({'invalid_category_fixture': (case_id, scores, score)})
        for offset, value in zip(RANK_ROW_OFFSETS, scores):
            sb.uc.mem_write(row + offset, struct.pack('<i', value))
        sb.uc.mem_write(row + 8, struct.pack('<I', 0xDEADBEEF))
        sb.uc.mem_write(level_storage, struct.pack('<I', level))
        sb.call(FUNCTION, (evaluator, 0))
        total = sb.u32(row + 0x110)
        ordinal = sb.u32(row + 8)
        if total != max(score, 0) or ordinal != expected_ordinal:
            raise AssertionError({'case': case_id, 'level': level, 'score': score,
                                  'expected_ordinal': expected_ordinal,
                                  'observed_ordinal': ordinal, 'observed_total': total})
        cases.append({
            'case_id': case_id, 'raw_house_level': level,
            'category_scores': scores, 'score_total': total,
            'result_ordinal': ordinal,
            'localized_rank_label': RANK_LABELS[ordinal][0],
            'rank_label_text': RANK_LABELS[ordinal][1],
        })

    for item in LEVEL_THRESHOLDS:
        level = item['house_level_raw']
        b_max, a_max = item['b_max'], item['a_max']
        cases_for_level = [
            (b_max, 2, 'b_max'),
            (b_max + 1, 1, 'first_a'),
            (a_max, 1, 'a_max'),
            (a_max + 1, 0, 'first_s'),
        ]
        for score, ordinal, edge in cases_for_level:
            run_case(f'level_{level}_{edge}', level, score, ordinal)

    # Confirm the output total sums all twelve category values, not just the
    # first field, and keep a mixture that crosses level-2 to S.
    run_case('level_2_mixed_category_sum', 2, 15_000, 0,
             category_scores=[1_000, 2_000, 3_000, 4_000, 5_000] + [0] * 7)

    invalid_level_cases = []
    for level in (0, 1, 9, 0xFFFFFFFF):
        sb.uc.mem_write(row, bytes(0x160))
        sb.uc.mem_write(row + 0x24, struct.pack('<i', 50_000))
        sb.uc.mem_write(row + 8, struct.pack('<I', 0xDEADBEEF))
        sb.uc.mem_write(level_storage, struct.pack('<I', level))
        sb.call(FUNCTION, (evaluator, 0))
        total = sb.u32(row + 0x110)
        ordinal = sb.u32(row + 8)
        if total != 50_000 or ordinal != 0xDEADBEEF:
            raise AssertionError({'invalid_level': level,
                                  'total': total, 'ordinal': hex(ordinal)})
        invalid_level_cases.append({
            'raw_house_level': level, 'score_total': total,
            'rank_ordinal_preserved': hex(ordinal),
        })

    return {
        'cases': len(cases) + len(invalid_level_cases),
        'threshold_cases': len(cases),
        'invalid_level_cases': len(invalid_level_cases),
        'mismatches': 0,
        'boundary_policy': {
            'score_at_b_max': 'ordinal 2 (B)',
            'score_at_b_max_plus_one': 'ordinal 1 (A)',
            'score_at_a_max': 'ordinal 1 (A)',
            'score_at_a_max_plus_one': 'ordinal 0 (S)',
        },
        'stub_responsibilities': {
            '0xef8260': 'returns a controlled valid-player result',
            '0xee9350': 'places a synthetic descriptor view for a known PlayerHouseLevel value',
            '0xee93d0': 'closes the controlled descriptor view without save side effects',
        },
        'native_behavior_left_unreplaced': [
            '12-category score summation into record +0x110',
            'raw level 2..8 dispatch through the original 7-entry branch table',
            'per-level lower/upper rank comparisons',
            'rank ordinal store to record +8',
        ],
        'stub_calls': stub_calls,
        'results': cases,
        'invalid_level_results': invalid_level_cases,
    }


def main():
    if not NSO.is_file() or not DB.is_file() or not MESSAGES.is_file() or not MAIL_MESSAGES.is_file():
        raise FileNotFoundError('required NSO/index/String/Mail message extraction missing')
    static = load_static_evidence()
    native = run_native_cases()
    result = {
        'schema': 'hha_rank_threshold_native_v1',
        'scope': 'Bounded native reproduction of the per-house-level HHA rank classifier plus static ordinal-to-grade-report candidate crosswalk; not a live save, overlap resolver, mailbox capture, or delivery-time test.',
        'source': {'main_nso': {'path': str(NSO), 'sha256': sha256(NSO)},
                   'index_sqlite': {'path': str(DB), 'sha256': sha256(DB)},
                   'us_en_rank_resource': str(MESSAGES)},
        'thresholds': [
            {
                'raw_house_level_selector': row['house_level_raw'],
                'rank_order': [
                    {'rank': 'B', 'score_min': 0, 'score_max': row['b_max'], 'ordinal': 2},
                    {'rank': 'A', 'score_min': row['b_max'] + 1,
                     'score_max': row['a_max'], 'ordinal': 1},
                    {'rank': 'S', 'score_min': row['a_max'] + 1,
                     'score_max': None, 'ordinal': 0},
                ],
                'b_max_compare_immediate': row['b_max'],
                'a_max_compare_immediate': row['a_max'],
            }
            for row in LEVEL_THRESHOLDS
        ],
        'static_evidence': static,
        'native_execution': native,
        'limits': [
            'Player validity, PlayerHouseLevel descriptor lookup, and descriptor close are controlled stubs; no live save or game process is used.',
            'Native thresholds apply to HHA score total +0x110 (the sum of twelve category accumulators), but the full item eligibility/bonus formula and live overlap resolver are not reproduced.',
            'The native ordinal zero is confirmed as S by the GetSRankonHHA update branch; A/B labels are a string-resource ordinal crosswalk. An end-to-end live UI/mail capture remains absent.',
            'Static code establishes a save-backed formatted-message collection insertion route for HHA output; which of the two message collections a live HHA output takes and when that output becomes a visible mailbox entry remain unproven.',
            'The native ordinal-to-label code 40/41/42 mapping is direct. The matching Grade archive body labels 140/141/142 name S/A/B, but formatter arithmetic connecting a base label to its body label remains unproven.',
            'No HHAGradeMailFlag reader/clear or delivery timing is established.',
        ],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(f'PASS {native["cases"]} native cases; 0 mismatches; wrote {OUT}')


if __name__ == '__main__':
    main()
