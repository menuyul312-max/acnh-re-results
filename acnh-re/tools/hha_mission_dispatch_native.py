"""Exhaustively exercise the native HHA mission-flag dispatcher.

The original AArch64 instructions at 0x7b4330 run from the shared ExeFS NSO.
Only the event-flag get/set accessors and the dispatch receiver are controlled
by the harness; their arguments are recorded so the dispatcher itself remains
native. This does not evaluate HHA mission criteria or score/grade thresholds.
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
ELF = Path('/workspace/downloads/ACNH_island_RE/ACNH_island_RE/A_logic/main.elf')
DB = DATA / 'output' / 'index.sqlite'
ROMFS = Path('/workspace/downloads/acnh_additional_romfs_2026-11-02/romfs')
OUT = REPO / 'output' / 'gameplay' / 'house_hha_followup'
NSO_SHA256 = 'f8d248109ff72999b4600ae3749f8c7397fb960f7ad3ab8dee3018ae9e14e900'
ELF_SHA256 = '5bf707c3dc5dac0ad9635af7d336ec580f81c3f7876d0f55400d1900e3415d74'
FUNCTION = 0x7b4330
FLAG_GET = 0xf4aff0
FLAG_SET = 0xf4b0d0
MISSION_DISPATCH = 0x7b5540
MISSION_NAMES = [f'HappyHomeMission{i}' for i in range(1, 7)]
PARAM2 = 0xa5a5123412345678

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


def load_static_evidence():
    db = sqlite3.connect(f'file:{DB}?mode=ro', uri=True)
    db.row_factory = sqlite3.Row
    fn = db.execute('SELECT va,size,ghidra_name FROM functions WHERE va=?',
                    (FUNCTION,)).fetchone()
    decomp = db.execute('SELECT path,sha256 FROM decomp_new WHERE va=?',
                         (FUNCTION,)).fetchone()
    calls = db.execute('SELECT target_va,COUNT(*) AS n FROM direct_calls '
                       'WHERE owner_va=? GROUP BY target_va ORDER BY target_va',
                       (FUNCTION,)).fetchall()
    strings = db.execute('SELECT DISTINCT string_va,text FROM string_refs '
                         'WHERE function_va=? ORDER BY string_va',
                         (FUNCTION,)).fetchall()
    db.close()
    assert fn and decomp
    call_counts = {f'0x{row["target_va"]:x}': row['n'] for row in calls}
    assert call_counts == {'0x7b5540': 1, '0xf4aff0': 6, '0xf4b0d0': 1}, call_counts
    string_by_name = {row['text']: f'0x{row["string_va"]:x}' for row in strings}
    assert set(string_by_name) == set(MISSION_NAMES), string_by_name

    flags = json.loads((REPO / 'output' / 'gameplay' / 'flag_index.json').read_text())
    flags = flags.get('data', flags)
    definitions = []
    for name in MISSION_NAMES:
        key = f'cPlayer:{name}'
        record = flags[key]
        definition = record['definition']
        assert record['eventflow_writers'] == []
        assert definition['default'] == 0 and definition['max'] == 1
        definitions.append({
            'key': key,
            'string_va': string_by_name[name],
            'name_ja': definition['name_ja'],
            'table': definition['table'],
            'default': definition['default'],
            'max': definition['max'],
            'flow_access': definition['flow_access'],
            'eventflow_writers': record['eventflow_writers'],
            'writer_status': record['writer_status'],
        })

    decomp_path = DATA / 'output' / decomp['path']
    assert sha256(decomp_path) == decomp['sha256']
    return {
        'function': {'va': f'0x{FUNCTION:x}', 'size': fn['size'],
                     'ghidra_name': fn['ghidra_name']},
        'decomp': {'path': decomp['path'], 'sha256': decomp['sha256']},
        'direct_call_counts': call_counts,
        'flags_in_native_check_order': definitions,
    }


def key_from_accessor_arg(sb, pointer):
    name_pointer = sb.u64(pointer + 8)
    return sb.read(name_pointer, 96).split(b'\0', 1)[0].decode('ascii')


def main():
    assert NSO.is_file() and ELF.is_file() and DB.is_file()
    assert ROMFS.is_dir()
    assert sha256(NSO) == NSO_SHA256
    assert sha256(ELF) == ELF_SHA256
    static = load_static_evidence()

    sb = Sandbox(NSO)
    obj = sb.alloc(0xc00)
    hha_state = sb.alloc(0x200)
    sb.uc.mem_write(obj + 0xb10, struct.pack('<Q', hha_state))
    state = {'completed': set(), 'reads': [], 'writes': [], 'dispatches': []}

    def get_flag(sandbox):
        name = key_from_accessor_arg(sandbox, sandbox.reg('x1'))
        if name not in MISSION_NAMES:
            raise AssertionError(f'unexpected native flag key: {name}')
        state['reads'].append(name)
        return int(name in state['completed'])

    def set_flag(sandbox):
        name = key_from_accessor_arg(sandbox, sandbox.reg('x1'))
        state['writes'].append({'name': name, 'value': sandbox.reg('x2')})
        state['completed'].add(name)
        return 0

    def dispatch_mission(sandbox):
        state['dispatches'].append({
            'object': sandbox.reg('x0'),
            'param2': sandbox.reg('x1'),
            'ordinal': sandbox.reg('x2'),
        })
        return 0

    sb.stub(FLAG_GET, get_flag)
    sb.stub(FLAG_SET, set_flag)
    sb.stub(MISSION_DISPATCH, dispatch_mission)

    checked_pairs = 0
    getter_calls = 0
    dispatched = [0] * len(MISSION_NAMES)
    mismatch_count = 0
    samples = {}
    for active_mask in range(1 << len(MISSION_NAMES)):
        for completed_mask in range(1 << len(MISSION_NAMES)):
            state['completed'] = {MISSION_NAMES[i] for i in range(6)
                                  if completed_mask & (1 << i)}
            state['reads'].clear()
            state['writes'].clear()
            state['dispatches'].clear()
            sb.uc.mem_write(hha_state + 0x140, struct.pack('<I', active_mask))

            first_pending = None
            expected_reads = []
            for i, name in enumerate(MISSION_NAMES):
                if active_mask & (1 << i):
                    expected_reads.append(name)
                    if not (completed_mask & (1 << i)):
                        first_pending = i
                        break

            result = sb.call(FUNCTION, (obj, PARAM2))
            want_result = int(first_pending is not None)
            want_writes = ([] if first_pending is None else
                           [{'name': MISSION_NAMES[first_pending], 'value': 1}])
            want_dispatches = ([] if first_pending is None else [{
                'object': obj, 'param2': PARAM2 & 0xffffffff,
                'ordinal': first_pending,
            }])
            observed = (result, state['reads'], state['writes'], state['dispatches'])
            expected = (want_result, expected_reads, want_writes, want_dispatches)
            if observed != expected:
                mismatch_count += 1
                raise AssertionError({'active_mask': active_mask,
                                      'completed_mask': completed_mask,
                                      'observed': observed, 'expected': expected})

            checked_pairs += 1
            getter_calls += len(state['reads'])
            if first_pending is not None:
                dispatched[first_pending] += 1
                if first_pending not in samples:
                    samples[first_pending] = {
                        'active_mask': f'0x{active_mask:02x}',
                        'completed_mask': f'0x{completed_mask:02x}',
                        'read_order': list(state['reads']),
                        'dispatch_ordinal': first_pending,
                        'set_key': state['writes'][0]['name'],
                        'return': result,
                    }

    # High bits are outside the six native branches. Keep all six flags complete
    # so any accidental low-bit change would still be visible as a dispatch.
    state['completed'] = set(MISSION_NAMES)
    state['reads'].clear()
    state['writes'].clear()
    state['dispatches'].clear()
    sb.uc.mem_write(hha_state + 0x140, struct.pack('<I', 0xfffffc00))
    high_bits_result = sb.call(FUNCTION, (obj, PARAM2))
    assert high_bits_result == 0 and state['reads'] == []
    assert state['writes'] == [] and state['dispatches'] == []

    assert checked_pairs == 4096
    assert mismatch_count == 0
    assert getter_calls == 6734
    assert sum(dispatched) == 3367
    assert dispatched == [1024, 768, 576, 432, 324, 243], dispatched

    result = {
        'scope': ('Native HHA mission dispatcher 0x7b4330: controlled flag states '
                  'exercise native bit selection, check order, first-pending dispatch, '
                  'flag write, return value, and 32-bit param2 forwarding.'),
        'sources': {
            'main_nso': {'path': str(NSO), 'sha256': NSO_SHA256},
            'main_elf': {'path': str(ELF), 'sha256': ELF_SHA256},
            'index_sqlite': {'path': str(DB), 'sha256': sha256(DB)},
            'additional_romfs': {
                'path': str(ROMFS),
                'used_for_this_native_dispatch_check': False,
                'reason': '0x7b4330 dispatches save flags; this check does not consume RomFS tables.',
            },
        },
        'static_evidence': static,
        'native_execution': {
            'harness': 'tools/nso_sandbox.py (Unicorn ARM64), original NSO instructions at 0x7b4330',
            'cases': {
                'active_mask_x_completed_mask': checked_pairs,
                'high_bits_only': 1,
                'mismatches': mismatch_count,
                'flag_get_calls': getter_calls,
                'mission_dispatch_calls': sum(dispatched),
                'mission_dispatch_by_zero_based_ordinal': dispatched,
                'return_zero': 729,
                'return_one': 3367,
            },
            'samples_first_pending_by_ordinal': {
                str(i): samples[i] for i in range(len(MISSION_NAMES))
            },
            'stubs': {
                '0xf4aff0': 'flag getter: return controlled completed-state by native key; log key',
                '0xf4b0d0': 'flag setter: record native key/value and update controlled state',
                '0x7b5540': 'mission dispatch receiver: record object, param2, ordinal; no game side effects',
            },
        },
        'verified_rules': [
            'The six low bits at HHA-state offset +0x140 gate checks for cPlayer:HappyHomeMission1..6 in numeric order.',
            'For active bits, the native function reads each matching mission flag until the first false flag; later mission bits are not read in that call.',
            'When it finds the first false active flag, it calls 0x7b5540 once with zero-based ordinal 0..5, writes that same flag as 1 through 0xf4b0d0, and returns 1.',
            'When every active mission flag is already true, or no low mission bits are active, it returns 0 without dispatch or write.',
            'The dispatcher forwards param2 as its low 32 bits.',
        ],
        'limits': [
            'The flag accessor, flag writer, and 0x7b5540 receiver were stubbed; their internal game behavior is outside this result.',
            'Controlled flag states do not establish the criteria that set the six mission bits or clear the mission flags.',
            'No HHA point total, grade threshold, grade-mail timing, loan amount, or house-upgrade schedule is proven here.',
            'Flag names and Japanese descriptions identify the six mission slots; flag_index.json still marks native writer status as unproven because it has no EventFlow writer.',
        ],
    }
    OUT.mkdir(parents=True, exist_ok=True)
    destination = OUT / 'hha_mission_dispatch_native.json'
    destination.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({
        'artifact': str(destination),
        'function': f'0x{FUNCTION:x}',
        'cases': checked_pairs + 1,
        'mismatches': mismatch_count,
        'mission_dispatch_calls': sum(dispatched),
        'index_sqlite_sha256': result['sources']['index_sqlite']['sha256'],
    }, indent=2), flush=True)


if __name__ == '__main__':
    main()
