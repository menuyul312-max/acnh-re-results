"""Probe the native HHA per-item score accumulator in ExeFS main.

This isolates 0x7b36b0. It replaces the item lookup/score helper and unrelated
container/report helpers, while the code that adds the returned score into the
room record remains original AArch64 NSO instructions. It does not emulate the
full room scan or connect the item accumulator to the separate bucket input.
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
HELPER_DECOMP = DATA / 'output' / 'binary' / 'analysis_decomp' / 'ab9050.c'
OUT = REPO / 'output' / 'gameplay' / 'house_hha_followup' / 'hha_item_score_accumulator_native.json'
NSO_SHA256 = 'f8d248109ff72999b4600ae3749f8c7397fb960f7ad3ab8dee3018ae9e14e900'
ITEMFROM_HHA_BASE_SCORE_HASH = 0xd62525d0

FUNCTION = 0x7b36b0
SCORE_HELPER = 0xab9050
ROOM_PTR_FIELD = 0xb10
ROOM_CATEGORY_SCORE = 0x24
BUCKET_INPUT = 0x150

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


def run_native_cases():
    cases = []
    for score in (0, 200, 499):
        sb = Sandbox(NSO)
        evaluator = sb.alloc(0xc00)
        room = sb.alloc(0x160)
        scratch = sb.alloc(0x1400)
        item_gate = sb.alloc(4)
        item_ref = sb.alloc(0x20)
        layout_a = sb.alloc(0x20)
        layout_b = sb.alloc(0x20)
        baseline = 17
        bucket_sentinel = 777

        sb.uc.mem_write(evaluator + ROOM_PTR_FIELD, struct.pack('<Q', room))
        sb.uc.mem_write(evaluator + ROOM_PTR_FIELD + 8, struct.pack('<Q', scratch))
        sb.uc.mem_write(item_gate, struct.pack('<I', 1))
        sb.uc.mem_write(room, bytes(0x160))
        sb.uc.mem_write(room + ROOM_CATEGORY_SCORE, struct.pack('<I', baseline))
        sb.uc.mem_write(room + BUCKET_INPUT, struct.pack('<I', bucket_sentinel))
        helper_calls = []

        def score_helper(sandbox):
            helper_calls.append({'input_pointer': hex(sandbox.reg('x0')),
                                 'controlled_return': score})
            return score

        def controlled_gate(sandbox, *, enabled=False):
            return int(enabled)

        # These accessors and later report/mission helpers are boundaries around
        # the item scoring step; the score-helper call site and +0x24 addition
        # execute natively. No item data or save state is changed on disk.
        stubs = {
            0xf58d00: lambda s: controlled_gate(s, enabled=True),
            0xa9c290: None,
            0xaa7f80: lambda s: controlled_gate(s, enabled=True),
            0xa9cb60: None,
            0xaafdc0: None,
            SCORE_HELPER: score_helper,
            0x7b6770: None,
            0xf589b0: None,
            0xf589e0: None,
            0xa0f440: None,
            0xab8fb0: None,
            0xab8dd0: None,
            0x7b6ff0: None,
            0x7b69e0: None,
            0x7b6b60: None,
            0x7b6d50: None,
            0xa0f510: None,
            0x7b76d0: None,
        }
        for address, callback in stubs.items():
            sb.stub(address, callback)

        native_return = sb.call(FUNCTION,
                                (evaluator, item_ref, layout_a, layout_b, item_gate, 2))
        observed = sb.u32(room + ROOM_CATEGORY_SCORE)
        bucket_after = sb.u32(room + BUCKET_INPUT)
        if (native_return != 0 or len(helper_calls) != 1 or
                observed != baseline + score or bucket_after != bucket_sentinel):
            raise AssertionError({'score': score, 'native_return': native_return,
                                  'helper_calls': helper_calls,
                                  'category_score': observed,
                                  'bucket_input': bucket_after})
        cases.append({
            'controlled_score_helper_return': score,
            'category_field_before': baseline,
            'category_field_after': observed,
            'bucket_field_before': bucket_sentinel,
            'bucket_field_after': bucket_after,
            'score_helper_calls': helper_calls,
        })
    return {'cases': len(cases), 'mismatches': 0, 'results': cases}


def load_score_source_evidence():
    db = sqlite3.connect(f'file:{DB}?mode=ro', uri=True)
    row = db.execute('SELECT hash,offset,width,evidence FROM columns_resolved '
                     'WHERE table_name=? AND name=?',
                     ('ItemFrom', 'HHABaseScore')).fetchone()
    db.close()
    assert row and row[0] == ITEMFROM_HHA_BASE_SCORE_HASH
    decomp = HELPER_DECOMP.read_text()
    assert '-0x29dada30' in decomp
    assert (-0x29dada30 & 0xffffffff) == ITEMFROM_HHA_BASE_SCORE_HASH
    return {
        'helper_va': f'0x{SCORE_HELPER:x}',
        'helper_decomp': {'path': str(HELPER_DECOMP), 'sha256': sha256(HELPER_DECOMP)},
        'native_helper_key': '0xd62525d0',
        'native_decomp_literal': '-0x29dada30',
        'ItemFrom_column': {
            'name': 'HHABaseScore',
            'hash': f'0x{row[0]:08x}',
            'offset': row[1],
            'width': row[2],
            'evidence': row[3],
        },
        'identity_basis': 'the native helper searches for key 0xd62525d0; this exactly equals ItemFrom:HHABaseScore resolved column hash',
    }


def main():
    assert NSO.is_file() and DB.is_file() and HELPER_DECOMP.is_file()
    assert sha256(NSO) == NSO_SHA256
    result = {
        'scope': 'Controlled native probe of item-score helper return into one HHA room category accumulator.',
        'source': {
            'main_nso': {'path': str(NSO), 'sha256': NSO_SHA256},
            'index_sqlite': {'path': str(DB), 'sha256': sha256(DB)},
        },
        'native_path': {
            'function': '0x7b36b0',
            'score_helper_call_pc': '0x7b37b8',
            'score_helper_target': '0xab9050',
            'room_record_pointer': 'evaluator + 0xb10',
            'category_accumulator_offset': '0x24',
            'bucket_input_offset': '0x150',
            'observed_operation': 'room[0x24] += score_helper_return',
        },
        'score_source_identity': load_score_source_evidence(),
        'native_execution': run_native_cases(),
        'limits': [
            'The runtime harness stubs 0xab9050; its identity as ItemFrom:HHABaseScore is established by the exact native lookup hash and resolved column-hash match, not by running the table lookup against a live item.',
            'The native item-score contribution updates +0x24. It does not update +0x150 in this function.',
            'The evaluator later sums room offsets +0x24..+0x50 into +0x136c, while 0x7b4fc0 reads +0x150/+0x14c. No path connecting those values is established here.',
            'No displayed HHA grade, theme bonus, mail creation, or mail delivery is emulated.',
        ],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(f"PASS {result['native_execution']['cases']} native item-score cases; 0 mismatches; wrote {OUT}")


if __name__ == '__main__':
    main()
