"""Aggregate the next RE phase without re-counting historical native proofs."""
from pathlib import Path
import json
import sqlite3

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT/'output'
PROOFS = ['room_floor_ground_native', 'inventory_cache_native', 'ballistic_velocity_native', 'sdk_memory_native']


def write(path, value): path.write_text(json.dumps(value, indent=2, ensure_ascii=False)+'\n')


def main():
    coverage = json.loads((OUT/'coverage.json').read_text())
    previous = json.loads((OUT/'mechanics/continuation_progress.json').read_text())
    before = previous['native_helper_cases_after']
    assert before == 1123294
    added = {}
    for name in PROOFS:
        result = json.loads((OUT/f'mechanics/{name}.json').read_text())
        assert result['mismatches'] == [] and result['dependencies_stubbed'] == []
        assert result['cases'] == sum(result['groups'].values())
        assert result['elf_sha256'] == previous['source_elf_sha256']
        coverage['native_helper_checks'][name] = result['cases']; added[name] = result['cases']
    after = before+sum(added.values())
    assert sum(coverage['native_helper_checks'].values()) >= after
    progress = {'native_helper_cases_before': before, 'new_native_case_groups': added,
                'new_game_mechanics_cases': sum(added[n] for n in PROOFS if n != 'sdk_memory_native'),
                'new_sdk_support_cases': added['sdk_memory_native'],
                'new_native_cases': sum(added.values()), 'native_helper_cases_after': after,
                'native_byml_structural_comparisons_separate': coverage['native_byml_reader']['comparisons'],
                'mismatches': [], 'full_game_semantics_complete': False,
                'source_elf_sha256': previous['source_elf_sha256'],
                'report': '../docs/ACTIVE_CONTEXT_FOLLOWUP.md',
                'scope': 'Volumes of bounded helper/block verification; support tests are separate from gameplay cases. No percentage of full-game completion is inferred.'}
    write(OUT/'mechanics/active_context_progress.json', progress)
    frontier = json.loads((OUT/'mechanics/continuation_frontier.json').read_text())
    areas = frontier['areas']
    movement = areas['player_movement']
    movement['verified_reference'] = list(dict.fromkeys(movement['verified_reference']+['mechanics/ballistic_velocity_native.json']))
    movement['verified_boundary'] = 'Complete position/root-motion consumer0xdac550 on reconstructed context; complete ballistic helper0x1d280; bounded player block0xe17e54..before0xe17e94.'
    movement['remaining'] = ['Input/state -> real runtime velocity/gravity integration', 'Post-motion collision and landing correction',
                             'Full traversal/state scheduling', 'Animation sample/timing production', 'Duration units and frame scheduling']
    movement['next_functions'] = ['0xe17cb0', '0xe42b30', '0xdac780', '0xda86b0']
    dynamic = areas['dynamic_ground']
    dynamic['verified_reference'] = list(dict.fromkeys(dynamic['verified_reference']+['mechanics/room_floor_ground_native.json']))
    dynamic['verified_boundary'] = 'Real RoomFloor items,173 source floor rows, native HasJmp/Horizon discovery, variant dispatch, no-resident-map fallback and active ground-permission consumers with paired inactive controls.'
    dynamic['remaining'] = ['Resident JMP resource/container lookup and actual map selection',
                            'Position transform/rotation with an actual resident map', 'All loader and non-RoomFloor override sources']
    dynamic['next_functions'] = ['0x16e6d0', '0xc69e0', '0x1c84e50', '0x880680']
    crafting = areas['items_tools_crafting']
    crafting['verified_reference'] = list(dict.fromkeys(crafting['verified_reference']+['mechanics/inventory_cache_native.json']))
    crafting['verified_boundary'] = 'All three source-record loaders and original counter producers, normal-item stack rules, marked-slot producer lists, u16 wrap and producer->requirement chain. Parent save-wrapper acquisition remains unexecuted.'
    crafting['remaining'] = ['Actual save-wrapper acquisition and full parent cold-cache path',
                            'A/B/C bindings to named save members', 'Wrapped/remade/special-count item paths',
                            'Atomic ingredient removal/result award/rollback', 'Recipe unlocks', 'Tool durability and all use/remake actions']
    crafting['next_functions'] = ['0xee0be0', '0xedc240', '0xed9c20', '0xee9350', '0xf8f540']
    frontier['latest_phase'] = {'report': '../docs/ACTIVE_CONTEXT_FOLLOWUP.md', 'progress': 'mechanics/active_context_progress.json',
                                'new_native_cases': sum(added.values()), 'native_helper_cases_total': after}
    db = sqlite3.connect(OUT/'index.sqlite')
    for area in [movement, dynamic, crafting]:
        area['function_references'] = []
        for address in area['next_functions']:
            va = int(address, 16); path = None
            for table in ['decomp_new', 'decomp']:
                row = db.execute(f'SELECT path FROM {table} WHERE va=?', (va,)).fetchone()
                if row: path = row[0]; break
            if path: assert (OUT/path).exists()
            area['function_references'].append({'va': address, 'pseudocode': path,
                                                'evidence': 'Existing native index. Proposed next target; full semantics not inferred from its pseudocode.'})
    db.close(); write(OUT/'mechanics/continuation_frontier.json', frontier)
    coverage['full_user_goal_completed'] = False
    for name in PROOFS: coverage['mechanics_research'][name] = f'mechanics/{name}.json'
    coverage['mechanics_research'].update({'active_context_report': '../docs/ACTIVE_CONTEXT_FOLLOWUP.md',
                                          'active_context_progress': 'mechanics/active_context_progress.json'})
    write(OUT/'coverage.json', coverage)
    p = OUT/'mechanics/focus7/summary.json'; focus = json.loads(p.read_text())
    focus['active_context_followup'] = frontier['latest_phase']
    write(p, focus)
    print(json.dumps(progress), flush=True)


if __name__ == '__main__': main()
