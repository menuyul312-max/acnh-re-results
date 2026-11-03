"""Aggregate the verified NPC navigation kernel phase and explicit frontier."""
from pathlib import Path
import json
import sqlite3

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT/'output'
PROOFS = ['npc_pathfinding_native', 'npc_route_handoff_native', 'npc_route_target_native']


def write(path, data): path.write_text(json.dumps(data, indent=2, ensure_ascii=False)+'\n')


def main():
    coverage = json.loads((OUT/'coverage.json').read_text())
    previous = json.loads((OUT/'mechanics/resident_npc_progress.json').read_text())
    before = previous['native_helper_cases_after']; assert before == 1131926
    added = {}; results = {}
    for name in PROOFS:
        result = json.loads((OUT/f'mechanics/{name}.json').read_text())
        assert result['cases'] == sum(result['groups'].values())
        assert result['mismatches'] == [] and result['dependencies_stubbed'] == []
        assert result['elf_sha256'] == previous['source_elf_sha256']
        results[name] = result; added[name] = result['cases']
        coverage['native_helper_checks'][name] = result['cases']
        coverage['mechanics_research'][name] = f'mechanics/{name}.json'
    after = before+sum(added.values()); assert after == 1134009
    # Preserve this phase's snapshot when later native proofs are present.
    assert sum(coverage['native_helper_checks'].values()) >= after
    progress = {'native_helper_cases_before': before, 'new_native_case_groups': added,
                'new_game_mechanics_and_block_cases': sum(added.values()), 'new_support_cases': 0,
                'new_native_cases': sum(added.values()), 'native_helper_cases_after': after,
                'native_byml_structural_comparisons_separate': coverage['native_byml_reader']['comparisons'],
                'mismatches': [], 'full_game_semantics_complete': False,
                'source_elf_sha256': previous['source_elf_sha256'],
                'report': '../docs/NPC_NAVIGATION_KERNEL.md',
                'scope': 'Bounded native search/route/target checks on declared inputs; not independent game rules or a full-game completion percentage.'}
    write(OUT/'mechanics/npc_navigation_progress.json', progress)
    db = sqlite3.connect(OUT/'index.sqlite')
    def reference(address):
        va = int(address, 16); path = None
        indexed = db.execute('SELECT size,name FROM native_functions WHERE va=?', (va,)).fetchone()
        for table in ['decomp_new', 'decomp']:
            row = db.execute(f'SELECT path FROM {table} WHERE va=?', (va,)).fetchone()
            if row: path = row[0]; break
        if path: assert (OUT/path).exists()
        return {'va': address, 'pseudocode': path, 'indexed_function_size': indexed[0] if indexed else None}
    functions = []
    for name, result in results.items():
        for role, address in result['native_functions'].items():
            functions.append({'role': role, **reference(address), 'proof_json': f'mechanics/{name}.json',
                              'boundary': 'Named entry/stop addresses describe bounded blocks; full-function coverage applies only to the declared contexts in the proof JSON.'})
    mapping = {'source_elf_sha256': previous['source_elf_sha256'], 'addresses': 'ELF VA; Ghidra display base is ELF+0x100000',
               'functions': functions, 'graph_layout': results['npc_pathfinding_native']['layout'],
               'route_list_layout': results['npc_route_handoff_native']['list_layout'],
               'layers': [{'layer': 'A* kernel', 'proof': 'mechanics/npc_pathfinding_native.json', 'status': 'Verified on prepared cell states, costs and original callbacks'},
                          {'layer': 'Result extraction/list reuse', 'proof': 'mechanics/npc_route_handoff_native.json', 'status': 'Complete extractor; parent stops before child initialization'},
                          {'layer': 'Route target/lookahead', 'proof': 'mechanics/npc_route_target_native.json', 'status': 'Complete matched-context selectors; bounded controller setup'},
                          {'layer': 'World/async producer', 'status': 'Unexecuted: live terrain/collision-to-grid, task lifecycle and result publication'},
                          {'layer': 'Movement/avoidance', 'status': 'Unexecuted: active state decisions, steering and collision integration'}],
               'data_references': {'source_parameter_bindings': 'mechanics/npc_activity_bindings.json',
                                   'native_states': 'mechanics/npc_state_registry_native.json',
                                   'eventflow_graphs': 'mechanics/focus7/npc_ai_flow_graphs.json',
                                   'focus_tables': 'mechanics/focus7/table_field_links.json#/tables'},
               'parameter_binding_limit': 'Prepared kernel weights and eligibility bitsets are not assigned to BCSV/BYML fields without a proven producer.',
               'complete': False}
    write(OUT/'mechanics/npc_navigation_kernel_map.json', mapping)
    frontier = json.loads((OUT/'mechanics/continuation_frontier.json').read_text())
    npc = frontier['areas']['npc_navigation']
    npc['verified_reference'] = list(dict.fromkeys(npc['verified_reference']+[f'mechanics/{name}.json' for name in PROOFS]+['mechanics/npc_navigation_kernel_map.json']))
    npc['verified_boundary'] = 'Original A* kernel with original cost/heuristic callbacks, Dijkstra comparison on prepared grids, complete route extraction/list recycling, matched-context target/lookahead functions, bounded worker search/parent handoff/controller setup and ten native search-to-consumer chains.'
    npc['remaining'] = ['Live island terrain/collision/actor data -> node flags, direction masks, cost categories and eligibility bitsets',
                        'Async request submission, worker lifecycle, cancellation and result publication',
                        'Active child-state evaluator0xc87710 and steering/position integration',
                        'All NPC scheduler priorities, social/interest decisions and state-transition logic',
                        'Other actor-reference branches and all request parameter meanings/units']
    npc['next_functions'] = ['0x15c3390', '0x15c24a0', '0x15c2910', '0x15bf150', '0x15c3190', '0xc87710', '0xc87ea0']
    npc['next_function_scope'] = 'World-grid production, async request entry and active movement evaluators; only explicitly bounded worker/controller blocks have run in this phase.'
    npc['function_references'] = [{**reference(address), 'evidence': 'Existing native address index; proposed next target, not completed semantics.'} for address in npc['next_functions']]
    db.close()
    frontier['latest_phase'] = {'report': '../docs/NPC_NAVIGATION_KERNEL.md', 'progress': 'mechanics/npc_navigation_progress.json',
                                'new_native_cases': sum(added.values()), 'native_helper_cases_total': after}
    write(OUT/'mechanics/continuation_frontier.json', frontier)
    coverage['full_user_goal_completed'] = False
    coverage['mechanics_research'].update({'npc_navigation_report': '../docs/NPC_NAVIGATION_KERNEL.md',
                                          'npc_navigation_progress': 'mechanics/npc_navigation_progress.json',
                                          'npc_navigation_kernel_map': 'mechanics/npc_navigation_kernel_map.json'})
    write(OUT/'coverage.json', coverage)
    p = OUT/'mechanics/focus7/summary.json'; focus = json.loads(p.read_text())
    focus['npc_navigation_followup'] = frontier['latest_phase']; write(p, focus)
    print(json.dumps(progress), flush=True)


if __name__ == '__main__': main()
