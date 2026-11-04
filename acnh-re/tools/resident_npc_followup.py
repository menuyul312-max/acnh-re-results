"""Record resident-map/NPC proof boundaries and totals as a reproducible phase."""
from pathlib import Path
import json
import sqlite3

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT/'output'
PROOFS = {'resident_floor_map_native': 'mechanics',
          'npc_state_registry_native': 'mechanics',
          'npc_navigation_request_native': 'mechanics',
          'native_archive_verification': 'archive_support'}


def write(path, data): path.write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n')


def main():
    coverage = json.loads((OUT/'coverage.json').read_text())
    previous = json.loads((OUT/'mechanics/active_context_progress.json').read_text())
    before = previous['native_helper_cases_after']; assert before == 1127220
    added = {}; totals = {'mechanics': 0, 'archive_support': 0}
    for name, category in PROOFS.items():
        result = json.loads((OUT/f'mechanics/{name}.json').read_text())
        assert result['mismatches'] == [] and result['dependencies_stubbed'] == []
        assert result['cases'] == sum(result['groups'].values())
        assert result['elf_sha256'] == previous['source_elf_sha256']
        coverage['native_helper_checks'][name] = result['cases']
        coverage['mechanics_research'][name] = f'mechanics/{name}.json'
        added[name] = result['cases']; totals[category] += result['cases']
    after = before+sum(added.values())
    # This phase is a historical snapshot when later native groups exist.
    assert sum(coverage['native_helper_checks'].values()) >= after
    progress = {'native_helper_cases_before': before, 'new_native_case_groups': added,
                'new_game_mechanics_cases': totals['mechanics'],
                'new_archive_support_cases': totals['archive_support'],
                'new_native_cases': sum(added.values()), 'native_helper_cases_after': after,
                'native_byml_structural_comparisons_separate': coverage['native_byml_reader']['comparisons'],
                'mismatches': [], 'full_game_semantics_complete': False,
                'source_elf_sha256': previous['source_elf_sha256'],
                'report': '../docs/RESIDENT_MAP_NPC_FOLLOWUP.md',
                'scope': 'Bounded original instruction checks on declared contexts; no full-game completion percentage.'}
    write(OUT/'mechanics/resident_npc_progress.json', progress)
    frontier = json.loads((OUT/'mechanics/continuation_frontier.json').read_text())
    dynamic = frontier['areas']['dynamic_ground']
    dynamic['verified_reference'] = list(dict.fromkeys(dynamic['verified_reference']+['mechanics/resident_floor_map_native.json', 'mechanics/native_archive_verification.json', 'ui_island/manifests_pbc_audit.json']))
    dynamic['verified_boundary'] = 'Complete resident RoomFloor selector, ready-handle checks, typed SARC lookup, position transform, PBC attribute reader and ground consumers on 50 matched extracted RoomFloor PBC variants, with original source floor/item tables; 2,278 cases match.'
    dynamic['remaining'] = ['PBC JSON payload values are available, but raw PBC file/container bytes and unconsumed height geometry/world-scale are not proven',
                            'Filesystem loading, decompression, async jobs and resource allocation/lifetime',
                            'Non-RoomFloor dynamic sources and live-scene reachability']
    dynamic['next_functions'] = ['0x16e6d0', '0x1c84e50', '0x18adf0']
    dynamic['next_function_scope'] = 'Trace the filesystem/async loader and geometry consumers of PBC height fields; the RoomFloor attribute reader and ground consumers now use extracted PBC payload values.'
    npc = frontier['areas']['npc_navigation']
    npc['verified_reference'] = list(dict.fromkeys(npc['verified_reference']+['mechanics/npc_state_registry_native.json', 'mechanics/npc_navigation_request_native.json']))
    npc['verified_boundary'] = 'Original registration for67 states,201 original callback-target dispatches, three request writers/status predicates, inactive-child polling and bounded grid-admission/EscapeHighCostArea update blocks. AI callback bodies are not generally executed.'
    npc['remaining'] = ['Active native AI state handlers and all state-transition decisions',
                        'Routes/pathfinder, costs, obstacle avoidance and async route worker',
                        'Accepted request initialization, route node collection and movement integration',
                        'C++ scheduler, priorities and social/interest decisions',
                        'Opaque request32-byte parameter semantics and default initializer']
    npc['next_functions'] = ['0xcb5470', '0xcb5840', '0xc86440', '0xc862b0', '0x15c3570', '0xc31c40', '0xc0f9d0']
    npc['next_function_scope'] = 'Concrete handlers/route handoff targets recovered from original registrations and direct calls; not proof their algorithms are understood.'
    npc.pop('status_this_continuation', None)
    db = sqlite3.connect(OUT/'index.sqlite')
    for area in [dynamic, npc]:
        area['function_references'] = []
        for address in area['next_functions']:
            va = int(address, 16); path = None
            indexed = db.execute('SELECT size,name FROM native_functions WHERE va=?', (va,)).fetchone()
            for table in ['decomp_new', 'decomp']:
                row = db.execute(f'SELECT path FROM {table} WHERE va=?', (va,)).fetchone()
                if row: path = row[0]; break
            if path: assert (OUT/path).exists()
            area['function_references'].append({'va': address, 'pseudocode': path,
                                                'indexed_function_size': indexed[0] if indexed else None,
                                                'evidence': 'Original ELF VA and existing native index; proposed next target, not a completed semantic claim.'})
    db.close()
    frontier['latest_phase'] = {'report': '../docs/RESIDENT_MAP_NPC_FOLLOWUP.md',
                                'progress': 'mechanics/resident_npc_progress.json',
                                'new_native_cases': sum(added.values()), 'native_helper_cases_total': after}
    write(OUT/'mechanics/continuation_frontier.json', frontier)
    coverage['full_user_goal_completed'] = False
    coverage['mechanics_research'].update({'resident_npc_report': '../docs/RESIDENT_MAP_NPC_FOLLOWUP.md',
                                          'resident_npc_progress': 'mechanics/resident_npc_progress.json'})
    write(OUT/'coverage.json', coverage)
    p = OUT/'mechanics/focus7/summary.json'; focus = json.loads(p.read_text())
    focus['resident_npc_followup'] = frontier['latest_phase']; write(p, focus)
    print(json.dumps(progress), flush=True)


if __name__ == '__main__': main()
