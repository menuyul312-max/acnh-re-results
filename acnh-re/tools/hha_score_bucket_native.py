"""Exercise one native HHA category-bucket branch with controlled inputs.

The original NSO instructions at 0x7b4fc0 compute a bucket from fields in the
HHA room record. Only accessor/receiver boundaries are stubbed. This is not the
full furniture-score, grade, theme, or mail calculation.
"""
from pathlib import Path
import hashlib
import json
import sqlite3
import struct
import sys

TOOLS = Path(__file__).resolve().parent
REPO = TOOLS.parent
DATA = Path('/workspace/acnh-re')
NSO = DATA / 'inputs' / 'additional_exefs' / 'main'
DB = DATA / 'output' / 'index.sqlite'
ROMFS = Path('/workspace/downloads/acnh_additional_romfs_2026-11-02/romfs')
BDLI_INDEX = DATA / 'output' / 'additional_romfs' / 'bdli' / 'USen' / 'String.json'
OUT = REPO / 'output' / 'gameplay' / 'house_hha_followup' / 'hha_score_bucket_native.json'
NSO_SHA256 = 'f8d248109ff72999b4600ae3749f8c7397fb960f7ad3ab8dee3018ae9e14e900'

FUNCTION = 0x7b4fc0
CALLER = 0x7b29d0
CALLER_PC = 0x7b2bec
OUTPUT_RECEIVER = 0x7b6470
FLAG_GET = 0xf4aff0
FLAG_KEY = 'HappyHomeMission1'
FLAG_FULL_KEY = 'cPlayer:HappyHomeMission1'
FLAG_PREP = 0x7b1fe0
FLAG_SET = 0xf4b0d0
MAIL_FLAG = 'cPlayer:HHAGradeMailFlag'

if (DATA / '.deps').is_dir():
    sys.path.insert(0, str(DATA / '.deps'))
sys.path.insert(0, str(TOOLS))
from nso_sandbox import Sandbox  # noqa: E402


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def read_flag_key(sb, pointer):
    name_pointer = sb.u64(pointer + 8)
    return sb.read(name_pointer, 128).split(b'\0', 1)[0].decode('ascii')


def load_static_evidence():
    db = sqlite3.connect(f'file:{DB}?mode=ro', uri=True)
    db.row_factory = sqlite3.Row

    def function(va):
        row = db.execute('SELECT va,size,ghidra_name FROM functions WHERE va=?',
                         (va,)).fetchone()
        dec = db.execute('SELECT path,sha256,bytes,has_warning,bad_instruction_warning '
                         'FROM decomp_new WHERE va=?', (va,)).fetchone()
        assert row and dec
        return {
            'va': f'0x{row["va"]:x}',
            'size': row['size'],
            'ghidra_name': row['ghidra_name'],
            'decompilation': {k: dec[k] for k in dec.keys()},
        }

    fn = function(FUNCTION)
    caller_calls = [r for r in db.execute(
        'SELECT pc,target_va,instruction FROM direct_calls '
        'WHERE owner_va=? AND target_va=? ORDER BY pc', (CALLER, FUNCTION))]
    assert len(caller_calls) == 1 and caller_calls[0]['pc'] == CALLER_PC
    call_counts = {f'0x{r["target_va"]:x}': r['n'] for r in db.execute(
        'SELECT target_va,COUNT(*) AS n FROM direct_calls WHERE owner_va=? '
        'GROUP BY target_va ORDER BY target_va', (FUNCTION,))}
    strings = [{'string_va': f'0x{r["string_va"]:x}', 'text': r['text']}
               for r in db.execute('SELECT DISTINCT string_va,text FROM string_refs '
                                   'WHERE function_va=? ORDER BY string_va', (FUNCTION,))]
    mail_setter_calls = [{'pc': f'0x{r["pc"]:x}', 'target': f'0x{r["target_va"]:x}',
                          'instruction': r['instruction']}
                         for r in db.execute('SELECT pc,target_va,instruction FROM direct_calls '
                                             'WHERE owner_va=? AND target_va=? ORDER BY pc',
                                             (FLAG_PREP, FLAG_SET))]
    mail_strings = [{'string_va': f'0x{r["string_va"]:x}', 'text': r['text']}
                    for r in db.execute('SELECT DISTINCT string_va,text FROM string_refs '
                                        'WHERE function_va=? ORDER BY string_va', (FLAG_PREP,))]

    item_hha_columns = {}
    for table, where in (('ItemParam', "name LIKE 'ItemHHA%'"),
                         ('ItemFrom', "name='HHABaseScore'")):
        rows = db.execute(f'SELECT name,type,offset,width,evidence FROM columns_resolved '
                          f'WHERE table_name=? AND {where} ORDER BY offset', (table,)).fetchall()
        item_hha_columns[table] = [dict(r) for r in rows]
    db.close()

    assert set(r['text'] for r in strings) == {'GetSRankonHHA', FLAG_KEY}
    assert len(mail_setter_calls) == 1 and mail_setter_calls[0]['target'] == f'0x{FLAG_SET:x}'
    assert any(r['text'] == 'HHAGradeMailFlag' for r in mail_strings)
    assert {r['name'] for r in item_hha_columns['ItemFrom']} == {'HHABaseScore'}
    assert {'ItemHHATheme', 'ItemHHACategory', 'ItemHHASet', 'ItemHHASituation1',
            'ItemHHASituation2', 'ItemHHAPart', 'ItemHHASeason', 'ItemHHADirection'} == {
                r['name'] for r in item_hha_columns['ItemParam']}

    flag_index = json.loads((REPO / 'output' / 'gameplay' / 'flag_index.json').read_text())['data']
    native_flags = json.loads((REPO / 'output' / 'gameplay' / 'native_flag_refs.json').read_text())['data']['flags']
    mission = flag_index[FLAG_FULL_KEY]
    mail_flag = flag_index[MAIL_FLAG]
    rank_flag = flag_index['cLifeSupportAchievement:GetSRankonHHA']
    assert mission['eventflow_writers'] == []
    assert mail_flag['eventflow_writers'] == []
    assert FLAG_FULL_KEY in native_flags and f'0x{FUNCTION:x}' in native_flags[FLAG_FULL_KEY]['referencing_functions']
    assert MAIL_FLAG in native_flags and f'0x{FLAG_PREP:x}' in native_flags[MAIL_FLAG]['referencing_functions']

    bdli_index = json.loads(BDLI_INDEX.read_text())['files']
    bdli = {}
    for name in ('STR_HHA_Rank', 'STR_HHA_Theme', 'STR_HHA_Set', 'STR_HHA_Situation'):
        relative = f'BDLI/String/USen/{name}.bdli.zs'
        entry = bdli_index[relative]
        source = ROMFS / relative
        compressed_sha256 = sha256(source)
        bdli[name] = {
            'source': str(source),
            'compressed_file_sha256': compressed_sha256,
            'compressed_file_bytes': source.stat().st_size,
            'index_sha256': entry['sha256'],
            'index_bytes': entry['bytes'],
            'record_count': len(entry['records']),
            'message_member': entry['message_member'],
            'payload_semantics': 'unproven; compressed-file hash and indexed payload hash are kept distinct',
        }
    assert {name: bdli[name]['record_count'] for name in bdli} == {
        'STR_HHA_Rank': 3, 'STR_HHA_Theme': 25,
        'STR_HHA_Set': 19, 'STR_HHA_Situation': 24}

    return {
        'function': fn,
        'caller': {'va': f'0x{CALLER:x}', 'pc': f'0x{CALLER_PC:x}',
                   'instruction': caller_calls[0]['instruction']},
        'direct_call_counts': call_counts,
        'string_refs': strings,
        'mission_flag': {
            'key': FLAG_FULL_KEY,
            'name_ja': mission['definition']['name_ja'],
            'default': mission['definition']['default'],
            'max': mission['definition']['max'],
            'flow_access': mission['definition']['flow_access'],
            'eventflow_writers': mission['eventflow_writers'],
            'native_referencing_functions': native_flags[FLAG_FULL_KEY]['referencing_functions'],
        },
        'grade_mail_flag': {
            'key': MAIL_FLAG,
            'name_ja': mail_flag['definition']['name_ja'],
            'flow_access': mail_flag['definition']['flow_access'],
            'eventflow_writers': mail_flag['eventflow_writers'],
            'native_referencing_functions': native_flags[MAIL_FLAG]['referencing_functions'],
            'setter_call_from_0x7b1fe0': mail_setter_calls,
            'native_string_refs_from_0x7b1fe0': mail_strings,
            'interpretation_limit': 'The reference and setter call establish a native flag update path; they do not establish that a letter is sent or when it is sent.',
        },
        's_rank_achievement_flag': {
            'key': 'cLifeSupportAchievement:GetSRankonHHA',
            'name_ja': rank_flag['definition']['name_ja'],
            'eventflow_writers': rank_flag['eventflow_writers'],
            'native_referencing_functions': native_flags['cLifeSupportAchievement:GetSRankonHHA']['referencing_functions'],
        },
        'item_hha_columns_resolved': item_hha_columns,
        'us_english_hha_bdli_inventory': bdli,
    }


def run_native_cases():
    # For these nonnegative probes, the native code divides the +0x150 field
    # by four with an arithmetic shift. With denominator 1000, these pairs
    # straddle the observed 20% and 50% edges.
    cases = [
        {'id': '19_9_percent_mission_off', 'field_150': 796, 'mission1': False,
         'effective_numerator': 199, 'bucket_bit_index': 5, 'expected_mask': 0x7822},
        {'id': '19_9_percent_mission_on', 'field_150': 796, 'mission1': True,
         'effective_numerator': 199, 'bucket_bit_index': 5, 'expected_mask': 0x7822},
        {'id': '20_percent_mission_off', 'field_150': 800, 'mission1': False,
         'effective_numerator': 200, 'bucket_bit_index': 4, 'expected_mask': 0x7802},
        {'id': '20_percent_mission_on', 'field_150': 800, 'mission1': True,
         'effective_numerator': 200, 'bucket_bit_index': 4, 'expected_mask': 0x7812},
        {'id': '49_9_percent_mission_off', 'field_150': 1996, 'mission1': False,
         'effective_numerator': 499, 'bucket_bit_index': 4, 'expected_mask': 0x7802},
        {'id': '49_9_percent_mission_on', 'field_150': 1996, 'mission1': True,
         'effective_numerator': 499, 'bucket_bit_index': 4, 'expected_mask': 0x7812},
        {'id': '50_percent_mission_off', 'field_150': 2000, 'mission1': False,
         'effective_numerator': 500, 'bucket_bit_index': 3, 'expected_mask': 0x7802},
        {'id': '50_percent_mission_on', 'field_150': 2000, 'mission1': True,
         'effective_numerator': 500, 'bucket_bit_index': 3, 'expected_mask': 0x780a},
        {'id': '50_1_percent_mission_on', 'field_150': 2004, 'mission1': True,
         'effective_numerator': 501, 'bucket_bit_index': 3, 'expected_mask': 0x780a},
    ]
    sb = Sandbox(NSO)
    obj = sb.alloc(0xc00)
    state_ptr = sb.alloc(0x200)
    sb.uc.mem_write(obj + 0xb10, struct.pack('<Q', state_ptr))
    state = {'mission1': False, 'flag_reads': [], 'receiver_calls': []}

    def get_flag(sandbox):
        key = read_flag_key(sandbox, sandbox.reg('x1'))
        if key != FLAG_KEY:
            raise AssertionError(f'unexpected flag getter key {key!r}')
        state['flag_reads'].append(key)
        return int(state['mission1'])

    def preserve_mask(sandbox):
        # 0x198b630 is a conversion/bitset helper on this path; returning x0
        # preserves the native mask for the receiver stub below.
        return sandbox.reg('x0')

    def receive_result(sandbox):
        state['receiver_calls'].append({
            'mask': sandbox.reg('x2') & 0xffffffff,
            'score_arg': sandbox.reg('x1') & 0xffffffff,
        })
        return 0

    for address, callback in (
        (0xef8260, None),
        (FLAG_GET, get_flag),
        (0x198b590, None),
        (0xf53450, None),
        (0x198b630, preserve_mask),
        (OUTPUT_RECEIVER, receive_result),
    ):
        sb.stub(address, callback)

    for case in cases:
        state['mission1'] = case['mission1']
        state['flag_reads'].clear()
        state['receiver_calls'].clear()
        sb.uc.mem_write(state_ptr, bytes(0x200))
        fields = ((0x08, '<I', 1), (0x130, '<h', -2), (0x138, '<h', -2),
                  (0x14c, '<i', 1000), (0x150, '<i', case['field_150']),
                  (0x154, '<b', 0))
        for offset, fmt, value in fields:
            sb.uc.mem_write(state_ptr + offset, struct.pack(fmt, value))
        return_value = sb.call(FUNCTION, (obj, 0))
        observed = state['receiver_calls']
        if (return_value != 0 or state['flag_reads'] != [FLAG_KEY] or
                len(observed) != 1 or observed[0]['mask'] != case['expected_mask']):
            raise AssertionError({'case': case, 'return': return_value,
                                  'flag_reads': state['flag_reads'],
                                  'receiver_calls': observed})
        case['observed_mask'] = f'0x{observed[0]["mask"]:04x}'
        case['native_return'] = return_value

    return {
        'instruction_source': 'original AArch64 instructions at 0x7b4fc0 in ExeFS main NSO',
        'cases': len(cases),
        'mismatches': 0,
        'native_bucket_branch': [
            {'ratio_condition': 'ratio < 20.0', 'category_bit_index': 5,
             'boundary_probe': '19.9'},
            {'ratio_condition': '20.0 <= ratio < 50.0', 'category_bit_index': 4,
             'boundary_probes': ['20.0', '49.9']},
            {'ratio_condition': 'ratio >= 50.0', 'category_bit_index': 3,
             'boundary_probes': ['50.0', '50.1']},
        ],
        'mission_flag_gate': 'With cPlayer:HappyHomeMission1 false, native output suppresses category bits 3 and 4; category bit 5 remains in the observed mask.',
        'controlled_record_fields': {
            'record_pointer': 'param1 + 0xb10',
            '+0x8': 1,
            '+0x130': -2,
            '+0x138': -2,
            '+0x14c': 1000,
            '+0x150': 'case field; for nonnegative probes native uses field>>2',
            '+0x154': 0,
            'param2': 0,
        },
        'results': cases,
        'stub_responsibilities': {
            '0xef8260': 'no-op global/helper boundary',
            '0xf4aff0': 'returns controlled cPlayer:HappyHomeMission1 value after verifying accessor key',
            '0x198b590': 'no-op conversion/helper boundary',
            '0xf53450': 'no-op conversion/helper boundary',
            '0x198b630': 'returns x0 unchanged so the generated bit mask reaches the receiver',
            '0x7b6470': 'captures x1/x2 and suppresses downstream report/message processing',
        },
        'unreplaced_behavior': 'The ratio arithmetic, tier-bit selection, and mission-dependent bit suppression in 0x7b4fc0 execute as native NSO instructions.',
    }


def main():
    assert NSO.is_file() and DB.is_file() and ROMFS.is_dir() and BDLI_INDEX.is_file()
    assert sha256(NSO) == NSO_SHA256
    static = load_static_evidence()
    native = run_native_cases()
    result = {
        'scope': 'Bounded native reproduction of one HHA score-category branch; not a full score, grade, theme, or mail formula.',
        'source': {'main_nso': {'path': str(NSO), 'sha256': NSO_SHA256},
                   'index_sqlite': {'path': str(DB), 'sha256': sha256(DB)},
                   'additional_romfs': str(ROMFS)},
        'static_evidence': static,
        'native_execution': native,
        'subsection_status': {
            'ratio_bucket_branch': 'proven for the tested controlled record values; internal bucket bit IDs only',
            'total_hha_points_and_player_facing_grade': 'open',
            'theme_or_situation_bonus_weights': 'open; item schema/catalogue evidence does not define native scoring weights',
            'grade_mail_flag_write_path': 'proven as a native key reference and setter call in 0x7b1fe0',
            'grade_mail_trigger_and_delivery_timing': 'open; not established by this function, the flag index, or the examined EventFlow references',
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(f'PASS {native["cases"]} native cases; 0 mismatches; wrote {OUT}')


if __name__ == '__main__':
    main()
