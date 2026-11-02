"""Aggregate the verified continuation results and preserve an explicit frontier.

Idempotent: existing proof groups are replaced by name, never added repeatedly.
This tool aggregates evidence; it does not execute additional native cases.
"""
from pathlib import Path
import json
import sqlite3

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT/'output'
PROOFS = ['inventory_requirements_native', 'player_position_native',
          'player_root_motion_native', 'ground_context_gate_native']
ELF_SHA256 = '5bf707c3dc5dac0ad9635af7d336ec580f81c3f7876d0f55400d1900e3415d74'


def write(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False)+'\n')


def main():
    coverage = json.loads((OUT/'coverage.json').read_text())
    checks = coverage['native_helper_checks']
    # Historical baseline for this phase. Later proof groups must not change
    # its snapshot totals or make this historical aggregator fail on rerun.
    before = 1116466
    added = {}; results = {}
    for name in PROOFS:
        value = json.loads((OUT/f'mechanics/{name}.json').read_text())
        assert not value['mismatches'] and not value.get('dependencies_stubbed', [])
        assert value['cases'] == sum(value['groups'].values())
        if 'elf_sha256' in value: assert value['elf_sha256'] == ELF_SHA256
        checks[name] = value['cases']; added[name] = value['cases']; results[name] = value
    after = before+sum(added.values())
    assert sum(checks.values()) >= after
    progress = {
        'native_helper_cases_before': before, 'new_native_case_groups': added,
        'new_native_cases': sum(added.values()), 'native_helper_cases_after': after,
        'native_byml_structural_comparisons_separate': coverage['native_byml_reader']['comparisons'],
        'mismatches': [], 'complete_game_semantics': False,
        'source_elf_sha256': ELF_SHA256,
        'comparison_scope': 'Native/helper case volumes, not independent gameplay rules or a percentage of game completion.',
        'report': '../docs/MECHANICS_CONTINUATION.md'
    }
    write(OUT/'mechanics/continuation_progress.json', progress)
    frontier = {
        'complete': False, 'addresses': 'ELF VA; Ghidra base is ELF+0x100000',
        'source_elf_sha256': ELF_SHA256,
        'model_sound_policy': 'Catalogue references only; Godot untouched.',
        'areas': {
            'physics_collision': {
                'verified_reference': ['mechanics/collision_response_native.json'],
                'remaining': ['Geometric penetration response', 'Friction/moving-body solver', 'All collision mask meanings'],
                'next_functions': ['0xda86b0'],
                'next_function_scope': 'Static contact-related candidate; not executed by this continuation.'},
            'player_movement': {
                'verified_reference': ['mechanics/player_position_native.json', 'mechanics/player_root_motion_native.json'],
                'verified_boundary': 'Complete0xdac550 with existing context and original actor vtable, finite local inputs and supplied animation-result buffers.',
                'remaining': ['Input/state to velocity/gravity producer', 'Post-motion collision and landing correction',
                              'Full traversal/state transition scheduling', 'Animation sample production', 'Timestep/units'],
                'next_functions': ['0xdac780', '0xda86b0', '0xdd7df0']},
            'terrain': {
                'verified_reference': ['mechanics/terrain_native.json', 'mechanics/dynamic_ground_native.json'],
                'remaining': ['14-byte preset ->52-byte runtime constructor', 'Live terraform mutation', 'All placement restrictions'],
                'status_this_continuation': 'No new terrain-loader execution.'},
            'dynamic_ground': {
                'verified_reference': ['mechanics/ground_context_gate_native.json', 'mechanics/dynamic_ground_native.json'],
                'verified_boundary': 'Stage task hash/status and world readiness dispatch; selector0x157ab0 only empty-item path. Sector map lookup verified separately.',
                'remaining': ['Nonempty context item -> template/variant lookup', 'Actual map selection and fallback', 'Context transform/rotation consumers'],
                'next_functions': ['0x157ab0', '0x856270', '0x16e6d0', '0x855fa0', '0x880680', '0x881e50'],
                'address_note': 'FUN_0026e6d0 is ELF0x16e6d0, not0x26e6d0.'},
            'position_checks': {
                'verified_reference': ['mechanics/proximity_native.json', 'mechanics/terrain_native.json'],
                'remaining': ['Candidate collection', 'Actor registry and all type/filter predicates', 'Full placement queries'],
                'status_this_continuation': 'No new spatial-query execution.'},
            'npc_navigation': {
                'verified_reference': ['mechanics/focus7/npc_ai_flow_graphs.json', 'mechanics/npc_activity_bindings.json'],
                'remaining': ['C++ scheduler and priorities', 'Routes/pathfinder/obstacle avoidance', 'All native AI state transitions'],
                'candidate_ledger': 'mechanics/systems_research_ledger.json#/domains/npc_ai_navigation',
                'status_this_continuation': 'Previous static graphs/bindings remain static; no new NPC runtime proof.'},
            'items_tools_crafting': {
                'verified_reference': ['mechanics/inventory_requirements_native.json', 'mechanics/crafting_materials_native.json'],
                'verified_boundary': 'Complete0xee0be0 on initialized-cache path for six source normal material IDs; A/B/C producers not assigned gameplay names.',
                'remaining': ['Cold-cache gathering and real save context', 'Counter A/B/C producer semantics',
                              'Wrapped/remade/special-count branches', 'Atomic ingredient removal/result award/rollback',
                              'Recipe unlocks', 'Tool durability and all use/remake actions'],
                'next_functions': ['0xedc240', '0xeda040', '0xeff110', '0xf9ec10'],
                'abi_note': '0xedc240 has hidden X8 output; do not call it as a simple scalar-return method.'}
        },
        'scope': 'Concrete proof boundaries and selected next targets; neither all unknown functions nor a complete game specification.'
    }
    db = sqlite3.connect(OUT/'index.sqlite')
    for area in frontier['areas'].values():
        for text in area.get('next_functions', []):
            va = int(text, 16)
            path = None
            for table, field in [('decomp_new', 'path'), ('decomp', 'path')]:
                row = db.execute(f'SELECT {field} FROM {table} WHERE va=?', (va,)).fetchone()
                if row: path = row[0]; break
            if path: assert (OUT/path).exists(), path
            area.setdefault('function_references', []).append({'va': text, 'pseudocode': path,
                                                            'evidence': 'Existing native address index; semantic role must be checked against instructions.'})
    db.close()
    write(OUT/'mechanics/continuation_frontier.json', frontier)
    coverage['full_user_goal_completed'] = False
    research = coverage['mechanics_research']
    for name in PROOFS: research[name] = f'mechanics/{name}.json'
    research.update({'continuation_report': '../docs/MECHANICS_CONTINUATION.md',
                     'continuation_progress': 'mechanics/continuation_progress.json',
                     'continuation_frontier': 'mechanics/continuation_frontier.json'})
    write(OUT/'coverage.json', coverage)
    focus_path = OUT/'mechanics/focus7/summary.json'
    focus = json.loads(focus_path.read_text())
    focus['continuation'] = {'report': '../docs/MECHANICS_CONTINUATION.md',
                             'progress': 'mechanics/continuation_progress.json',
                             'frontier': 'mechanics/continuation_frontier.json',
                             'new_native_cases': sum(added.values()), 'native_helper_cases_total': after}
    write(focus_path, focus)
    print(json.dumps(progress), flush=True)


if __name__ == '__main__': main()
