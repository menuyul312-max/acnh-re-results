"""Record runtime terrain/navigation producers and active-evaluator boundaries."""
from pathlib import Path
import json
import sqlite3

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT/'output'
PROOFS = ['terrain_nav_flags_native', 'npc_route_evaluator_native', 'npc_reachable_mask_native']


def write(path, data): path.write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n')


def main():
    coverage = json.loads((OUT/'coverage.json').read_text())
    previous = json.loads((OUT/'mechanics/npc_navigation_progress.json').read_text())
    before = previous['native_helper_cases_after']; assert before == 1134009
    added = {}; results = {}
    for name in PROOFS:
        result = json.loads((OUT/f'mechanics/{name}.json').read_text())
        assert result['cases'] == sum(result['groups'].values())
        assert result['mismatches'] == [] and result['dependencies_stubbed'] == []
        assert result['elf_sha256'] == previous['source_elf_sha256']
        results[name] = result; added[name] = result['cases']
        coverage['native_helper_checks'][name] = result['cases']
        coverage['mechanics_research'][name] = f'mechanics/{name}.json'
    after = before+sum(added.values()); assert after == 1135577
    assert sum(coverage['native_helper_checks'].values()) >= after
    progress = {'native_helper_cases_before': before, 'new_native_case_groups': added,
                'new_game_mechanics_and_block_cases': sum(added.values()), 'new_support_cases': 0,
                'new_native_cases': sum(added.values()), 'native_helper_cases_after': after,
                'native_byml_structural_comparisons_separate': coverage['native_byml_reader']['comparisons'],
                'mismatches': [], 'full_game_semantics_complete': False,
                'source_elf_sha256': previous['source_elf_sha256'], 'report': '../docs/WORLD_NAV_BRIDGE.md',
                'scope': 'Original bounded routines on declared runtime contexts; no percentage of full-game completion.'}
    write(OUT/'mechanics/world_nav_bridge_progress.json', progress)
    db = sqlite3.connect(OUT/'index.sqlite')
    def ref(address):
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
            functions.append({'role': role, **ref(address), 'proof_json': f'mechanics/{name}.json',
                              'scope': result['scope']})
    mapping = {'complete': False, 'source_elf_sha256': previous['source_elf_sha256'],
               'addresses': 'ELF VA; Ghidra base is ELF+0x100000', 'functions': functions,
               'runtime_layout': results['terrain_nav_flags_native']['runtime_layout'],
               'word_decode': results['terrain_nav_flags_native']['word_decode'],
               'native_reset_cost_weights': results['terrain_nav_flags_native']['native_default_cost_weights'],
               'evaluator_pairs': results['npc_route_evaluator_native']['next_state_status_pairs'],
               'layers': [{'name': '14-byte preset to runtime52-byte records', 'status': 'Unproven constructor/loader'},
                          {'name': 'Runtime12 heights to word flags', 'status': 'Verified tested attribute0 geometry; other surface classes remain open'},
                          {'name': 'Word to node flags/directions', 'status': 'Complete native callbacks execute; direct low nibble/mode/mask bounds checked; full resulting bytes recorded'},
                          {'name': 'Cost initialization/classification', 'status': 'Original reset and tested classifier priority; actor predicate registry empty'},
                          {'name': 'Reachable mask', 'status': 'Original flood/wrapper versus queue oracle on declared graphs; null predicate'},
                          {'name': 'Active evaluator', 'status': 'Selected complete arrival/promotion/resume/wait paths and setup-to-FSM boundary'},
                          {'name': 'Live async/steering/physics', 'status': 'Unexecuted full lifecycle, all steering helpers and collision response'}],
               'source_data_references': {'terrain_presets_and_models_catalogue': 'relations/terrain_native.json',
                                          'ground_attribute_table': 'tables_resolved/ColGroundAttributeParam.json',
                                          'npc_parameter_bindings': 'mechanics/npc_activity_bindings.json',
                                          'npc_state_registry': 'mechanics/npc_state_registry_native.json',
                                          'previous_kernel_map': 'mechanics/npc_navigation_kernel_map.json'},
               'source_data_limit': 'Ground table is a semantic reference for numeric attribute0. These reconstructed runtime tests do not load source presets/PBC or establish all parameter-table bindings.'}
    write(OUT/'mechanics/world_nav_bridge_map.json', mapping)
    frontier = json.loads((OUT/'mechanics/continuation_frontier.json').read_text())
    terrain = frontier['areas']['terrain']
    terrain['verified_reference'] = list(dict.fromkeys(terrain['verified_reference']+['mechanics/terrain_nav_flags_native.json']))
    terrain['verified_boundary'] = 'Original runtime12-float height writer0x180d20, world word reader0x185e70 and node transform, on reconstructed attribute0 records and tested height patterns. Eight original height->word->node->A* chains.'
    terrain['remaining'] = ['14-byte preset ->52-byte runtime constructor and source loader',
                            'Other surface attributes, all height/spread thresholds and overlay-height branches',
                            'Live terraform mutation and all placement restrictions']
    terrain['status_this_continuation'] = 'New runtime height/flag producer proof; no preset loader or live edit execution.'
    terrain['next_functions'] = ['0x180d20', '0x174070', '0x558f40']
    npc = frontier['areas']['npc_navigation']
    npc['verified_reference'] = list(dict.fromkeys(npc['verified_reference']+[f'mechanics/{name}.json' for name in PROOFS]+['mechanics/world_nav_bridge_map.json']))
    npc['verified_boundary'] = 'Prior A*/route consumers plus runtime terrain/word/node callbacks, native reset weights and classifier, flood/wrapper with queue oracle, selected complete active evaluator paths and setup/evaluator to FSM handoff. Context remains reconstructed.'
    npc['remaining'] = ['Full world producer and nonempty actor/constraint predicates; other terrain surface classes and dynamic sources',
                        'Async request submission, lifecycle, cancellation and result publication',
                        'Remaining active evaluator branches, nonexpired wait predicates and steering geometry helpers0xc88310/0xc88660',
                        'Position/physics integration, scheduler, social/interest decisions and all transitions',
                        'All parameter meanings/units and proof of original constructor bindings']
    npc['next_functions'] = ['0x15c1690', '0x15c3190', '0x15c3390', '0xc88310', '0xc88660', '0xc88b80', '0xc21310']
    npc['next_function_scope'] = 'Remaining world producer, async lifecycle and steering/interruption paths; some enclosing functions now have selected path proofs.'
    for area in [terrain, npc]:
        area['function_references'] = [{**ref(address), 'evidence': 'Original address index; proposed next target, not a full semantic claim.'} for address in area['next_functions']]
    db.close()
    latest = {'report': '../docs/WORLD_NAV_BRIDGE.md', 'progress': 'mechanics/world_nav_bridge_progress.json',
              'new_native_cases': sum(added.values()), 'native_helper_cases_total': after}
    frontier['latest_phase'] = latest; write(OUT/'mechanics/continuation_frontier.json', frontier)
    coverage['full_user_goal_completed'] = False
    coverage['mechanics_research'].update({'world_nav_bridge_report': '../docs/WORLD_NAV_BRIDGE.md',
                                          'world_nav_bridge_progress': 'mechanics/world_nav_bridge_progress.json',
                                          'world_nav_bridge_map': 'mechanics/world_nav_bridge_map.json'})
    write(OUT/'coverage.json', coverage)
    p = OUT/'mechanics/focus7/summary.json'; focus = json.loads(p.read_text())
    focus['world_nav_bridge_followup'] = latest; write(p, focus)
    p = OUT/'mechanics/npc_navigation_kernel_map.json'; old = json.loads(p.read_text())
    old['later_phase'] = {'map': 'mechanics/world_nav_bridge_map.json', 'report': '../docs/WORLD_NAV_BRIDGE.md'}
    write(p, old)
    print(json.dumps(progress), flush=True)


if __name__ == '__main__': main()
