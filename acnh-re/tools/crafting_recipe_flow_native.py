"""Trace RecipeCraftParam joins and execute isolated recipe/inventory helpers.

The shared decoded corpus is read-only and must be selected explicitly with
--output-root. The SaveSetFromUIResult workbench transaction itself is not
executed; the native runs below cover leaf recipe-bit helpers and the signed
inventory-count helper on reconstructed fixtures.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import sqlite3
import struct
import sys
import zlib

TOOLS = Path(__file__).resolve().parent
REPO = TOOLS.parent
LOCAL_OUTPUT = REPO / 'output'
ARTIFACT = LOCAL_OUTPUT / 'gameplay' / 'crafting_transaction_followup' / 'crafting_recipe_flow_native.json'


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def col_index(table, name):
    return next(i for i, column in enumerate(table['columns']) if column['name'] == name)


def field(table, row, name):
    return row[col_index(table, name)]


def enum_label(value):
    if isinstance(value, dict):
        labels = value.get('labels') or []
        return labels[0] if labels else value.get('hash')
    return value


def load_table(output_root, name):
    path = output_root / 'tables_resolved' / f'{name}.json'
    table = json.loads(path.read_text())
    blob_path = output_root / table['raw']['$blob']
    return table, sha256(blob_path)


def get_event(db, flow, index):
    row = db.execute(
        'SELECT actor,kind,name,params_json FROM event_calls WHERE flow=? AND event_index=?',
        (flow, index)).fetchone()
    require(row is not None, f'missing EventFlow event {flow}#{index}')
    return {'flow': flow, 'index': index, 'actor': row[0], 'kind': row[1],
            'name': row[2], 'params': json.loads(row[3])}


def function_span(db, va):
    row = db.execute('SELECT size FROM native_functions WHERE va=?', (va,)).fetchone()
    if row is None:
        row = db.execute('SELECT size FROM functions WHERE va=?', (va,)).fetchone()
    require(row is not None, f'missing function size at {va:#x}')
    return row[0]


def direct_calls(db, va):
    size = function_span(db, va)
    return [{'pc': f'0x{pc:x}', 'target': f'0x{target:x}'} for pc, target in db.execute(
        'SELECT pc,target_va FROM direct_calls WHERE pc>=? AND pc<? ORDER BY pc',
        (va, va + size))]


def selected_calls(db, va, targets):
    targets = set(targets)
    return [call for call in direct_calls(db, va) if int(call['target'], 16) in targets]


def recipe_join_report(output_root, db):
    recipe, recipe_hash = load_table(output_root, 'RecipeCraftParam')
    items, item_hash = load_table(output_root, 'ItemParam')
    kinds, kind_hash = load_table(output_root, 'ItemKind')
    recipe_ids = {field(recipe, row, 'UniqueID'): row for row in recipe['rows']}
    item_rows = {field(items, row, 'UniqueID'): row for row in items['rows']}
    missing_outputs = []
    output_recipe_mismatches = []
    duplicate_outputs = defaultdict(list)
    ingredient_slots = 0
    missing_ingredients = []
    unlock_counts = Counter()
    npc_unlock_counts = Counter()
    for row in recipe['rows']:
        recipe_id = field(recipe, row, 'UniqueID')
        output_id = field(recipe, row, 'Item')
        duplicate_outputs[output_id].append(recipe_id)
        unlock_counts[str(enum_label(field(recipe, row, 'CraftUnlock')))] += 1
        npc_unlock_counts[str(enum_label(field(recipe, row, 'NPCUnlock')))] += 1
        item = item_rows.get(output_id)
        if item is None:
            missing_outputs.append({'recipe_id': recipe_id, 'item_id': output_id})
        elif field(items, item, 'DiyRecipeID') != recipe_id:
            output_recipe_mismatches.append({
                'recipe_id': recipe_id, 'item_id': output_id,
                'itemparam_diy_recipe_id': field(items, item, 'DiyRecipeID')})
        for slot in range(1, 7):
            material_id = field(recipe, row, f'Material{slot}')
            amount = field(recipe, row, f'Amount{slot}')
            if material_id == 0xfffe:
                require(amount == 0, f'empty material slot has nonzero amount: {recipe_id}:{slot}')
                continue
            ingredient_slots += 1
            if material_id not in item_rows:
                missing_ingredients.append({'recipe_id': recipe_id, 'slot': slot,
                                            'item_id': material_id})
    repeated_outputs = {str(item_id): ids for item_id, ids in duplicate_outputs.items()
                        if len(ids) > 1}
    require(not missing_outputs, 'RecipeCraftParam.Item failed its ItemParam.UniqueID join')
    require(not output_recipe_mismatches,
            'ItemParam.DiyRecipeID no longer matches RecipeCraftParam.UniqueID for output rows')
    require(not repeated_outputs, 'RecipeCraftParam output IDs are no longer one-to-one')
    require(not missing_ingredients, 'one or more ingredient IDs do not join ItemParam.UniqueID')

    schema = [{'name': c['name'], 'offset': c['offset'],
               'descriptor_width': c['width'], 'type': c['type']}
              for c in recipe['columns']]
    sample_ids = (56, 458, 461)
    sample_rows = []
    for recipe_id in sample_ids:
        row = recipe_ids[recipe_id]
        output_id = field(recipe, row, 'Item')
        output_item = item_rows[output_id]
        sample_rows.append({
            'recipe_unique_id': recipe_id,
            'output_item_id': output_id,
            'output_item_diy_recipe_id': field(items, output_item, 'DiyRecipeID'),
            'craft_unlock': enum_label(field(recipe, row, 'CraftUnlock')),
            'npc_unlock': enum_label(field(recipe, row, 'NPCUnlock')),
            'villager_open_num': field(recipe, row, 'VillagerOpenNum'),
            'serial_id': field(recipe, row, 'SerialID'),
            'materials': [{'slot': slot,
                           'item_id': field(recipe, row, f'Material{slot}'),
                           'quantity_table_u16': field(recipe, row, f'Amount{slot}')}
                          for slot in range(1, 7)]})

    relevant_events = [get_event(db, 'Ftr_Working', i)
                       for i in (22, 30, 69, 70, 72, 74, 75, 77, 208, 212, 217, 221)]
    bridge = item_rows[7211]
    camp = item_rows[5166]
    bridge_recipe = recipe_ids[field(items, bridge, 'DiyRecipeID')]
    camp_recipe = recipe_ids[field(items, camp, 'DiyRecipeID')]
    return recipe, items, kinds, {
        'schema': {
            'row_count': len(recipe['rows']), 'row_size_bytes': recipe['row_size'],
            'fields': schema,
            'empty_material_id': 0xfffe,
            'material_and_amount_storage': 'six u16 pairs; native getter 0xedac50 reads each actual pair and writes the low byte of Amount to its output quantity',
            'unique_id_range': [min(recipe_ids), max(recipe_ids)],
            'unique_id_gaps_in_range': max(recipe_ids) - min(recipe_ids) + 1 - len(recipe_ids)},
        'joins': {
            'recipe_item_to_itemparam_unique_id': {
                'join': 'RecipeCraftParam.Item = ItemParam.UniqueID',
                'matched': len(recipe['rows']), 'total': len(recipe['rows']),
                'unique_output_items': len(duplicate_outputs), 'duplicate_output_ids': repeated_outputs},
            'itemparam_backlink_to_recipe': {
                'join': 'ItemParam.DiyRecipeID = RecipeCraftParam.UniqueID',
                'matched_output_rows': len(recipe['rows']), 'total_output_rows': len(recipe['rows']),
                'unmatched_rows': output_recipe_mismatches},
            'ingredient_to_itemparam_unique_id': {
                'join': 'RecipeCraftParam.Material1..6 = ItemParam.UniqueID',
                'matched_populated_slots': ingredient_slots, 'total_populated_slots': ingredient_slots,
                'missing_rows': missing_ingredients}},
        'enum_row_counts': {
            'CraftUnlock': dict(sorted(unlock_counts.items())),
            'NPCUnlock': dict(sorted(npc_unlock_counts.items()))},
        'sample_rows': sample_rows,
        'sequence_examples': {
            'wood_bridge_output_item_id': 7211,
            'wood_bridge_recipe_id': field(items, bridge, 'DiyRecipeID'),
            'wood_bridge_craft_unlock': enum_label(field(recipe, bridge_recipe, 'CraftUnlock')),
            'camp_site_output_item_id': 5166,
            'camp_site_recipe_id': field(items, camp, 'DiyRecipeID'),
            'camp_site_craft_unlock': enum_label(field(recipe, camp_recipe, 'CraftUnlock'))},
        'source_tables': {
            'RecipeCraftParam': {'source_id': recipe['source_id'], 'raw_sha256': recipe_hash},
            'ItemParam': {'source_id': items['source_id'], 'raw_sha256': item_hash},
            'ItemKind': {'source_id': kinds['source_id'], 'raw_sha256': kind_hash}},
        'events': relevant_events}


def native_leaf_probes(output_root, recipe, items):
    # Use the analysis ELF selected by the shared manifest, not the local
    # zero-byte index placeholder or a copy of a large input.
    sys.path.insert(0, str(output_root.parent / '.deps'))
    sys.path.insert(0, str(TOOLS))
    from native_image import Image  # noqa: E402
    from native_emulator import Sandbox  # noqa: E402
    import inventory_requirements_native as inventory_requirements  # noqa: E402

    manifest = json.loads((output_root / 'manifest.json').read_text())
    analysis_elf = Path(manifest['source_root']) / 'A_logic' / 'main.elf'
    require(analysis_elf.is_file(), f'missing analysis ELF: {analysis_elf}')
    image = Image(analysis_elf)
    require(sha256(analysis_elf) == '5bf707c3dc5dac0ad9635af7d336ec580f81c3f7876d0f55400d1900e3415d74',
            'analysis ELF checksum changed; native addresses need revalidation')

    bit_sandbox = Sandbox(image)
    u = bit_sandbox.uc
    bits = bit_sandbox.HEAP + 0x10000
    u.mem_write(bits, bytes(0x100))
    bit_cases = []
    for recipe_id in (458, 461, 2047, 2048):
        before = bit_sandbox.call(0xf28fd0, (bits, recipe_id))
        bit_sandbox.call(0xf29050, (bits, recipe_id))
        after_set = bit_sandbox.call(0xf28fd0, (bits, recipe_id))
        set_bytes = list(u.mem_read(bits, 0x100))
        bit_sandbox.call(0xf290b0, (bits, recipe_id))
        after_clear = bit_sandbox.call(0xf28fd0, (bits, recipe_id))
        cleared_byte = u.mem_read(bits + (recipe_id >> 3 if recipe_id < 2048 else 0), 1)[0]
        require(before == 0 and after_set == int(recipe_id < 2048)
                and after_clear == 0, f'bit helper behavior changed for recipe id {recipe_id}')
        bit_cases.append({
            'recipe_id': recipe_id, 'valid_domain': recipe_id < 2048,
            'before_set_query': before, 'after_set_query': after_set,
            'after_clear_query': after_clear,
            'expected_byte_offset': recipe_id >> 3 if recipe_id < 2048 else None,
            'expected_bit_mask': (1 << (recipe_id & 7)) if recipe_id < 2048 else None,
            'target_byte_after_clear': cleared_byte,
            'array_nonzero_after_set': sum(value != 0 for value in set_bytes)})

    material_id = 2213
    sample_recipe = next(row for row in recipe['rows']
                         if field(recipe, row, 'UniqueID') == 56)
    require(field(recipe, sample_recipe, 'Material1') == material_id
            and field(recipe, sample_recipe, 'Amount1') == 1,
            'Recipe 56 no longer supplies the expected one-Apple fixture')
    material_probe_cases = []
    for index, (available, requested_remove) in enumerate(((9, 3), (2, 3), (9, 9))):
        sandbox = Sandbox(image)
        inventory_requirements.ROOT = output_root.parent
        table_setup = inventory_requirements.install_item_tables(sandbox)
        u = sandbox.uc
        # This helper is an item eligibility predicate backed by game tables
        # and runtime managers not fully initialized in this isolated fixture.
        # The caller/loop and actual signed count mutation remain native.
        stub_va = 0xaac730
        original_stub = image.read(stub_va, 8).hex()
        u.mem_write(stub_va, struct.pack('<II', 0x52800020, 0xd65f03c0))
        pocket = sandbox.HEAP + 0x10000
        item_arg = sandbox.HEAP + 0x12000
        empty_slot = struct.pack('<HHI', 0xfffe, 0, 0)
        pocket_bytes = struct.pack('<HHI', material_id, 0, 0) + empty_slot * 31 + bytes(0x200)
        u.mem_write(pocket, pocket_bytes)
        u.mem_write(pocket + 0x100, struct.pack('<H', available))
        u.mem_write(item_arg, struct.pack('<HHI', material_id, 0, 0))
        before = bytes(u.mem_read(pocket, 0x300))
        preflight = sandbox.call(0xf9e840, (pocket, item_arg), limit=1_000_000)
        result = sandbox.call(0xf9e410, (pocket, item_arg, -requested_remove), limit=1_000_000)
        after = bytes(u.mem_read(pocket, 0x300))
        remaining = struct.unpack('<H', after[0x100:0x102])[0]
        changed = [offset for offset, pair in enumerate(zip(before, after)) if pair[0] != pair[1]]
        expected = max(0, available - requested_remove)
        require(preflight == 1 and result == 1 and remaining == expected and changed == [0x100],
                f'native material count mutation mismatch in case {index}')
        case_name = ('below_request_clamps_zero' if available < requested_remove else
                     'exact_stack_becomes_zero' if available == requested_remove else
                     'partial_removal')
        material_probe_cases.append({
            'case': case_name,
            'item_id': material_id, 'recipe_unique_id': 56,
            'available_count_before': available, 'requested_remove': requested_remove,
            'helper_return': result, 'stack_match_gate_return': preflight,
            'available_count_after': remaining, 'changed_byte_offsets': [hex(x) for x in changed],
            'item_slot_bytes_after': after[:8].hex(),
            'stubbed_boundary': {'va': hex(stub_va), 'original_bytes': original_stub,
                                 'effect': 'force aac730 true; this item predicate stayed false with the installed tables because its full runtime manager context is not reconstructed'},
            'source_table_hashes': {'ItemParam': table_setup['item_raw_sha256'],
                                    'ItemKind': table_setup['kind_raw_sha256']}})
    return {
        'bit_helpers': {
            'set_va': '0xf29050', 'clear_va': '0xf290b0', 'query_va': '0xf28fd0',
            'fixture': 'zeroed 256-byte array; no SaveGame member wrapper or player context',
            'cases': bit_cases,
            'stubbed_boundaries': []},
        'material_consumer': {
            'signed_count_helper_va': '0xf9e410',
            'stack_match_gate_va': '0xf9e840',
            'fixture': '32 eight-byte item slots followed by u16 counts at +0x100; slot 0 is Apple item 2213; requested deltas are negative',
            'cases': material_probe_cases,
            'stubbed_boundary': 'Each case patches 0xaac730 to return true. Item lookup, pocket slot search, 0xf9e840 control flow, 0xf9e410, and the u16 count writes execute from the original ELF.'},
        'analysis_elf_sha256': sha256(analysis_elf)}


def build(output_root):
    db_path = output_root / 'index.sqlite'
    require(db_path.is_file(), f'missing shared read-only index: {db_path}')
    require((output_root / 'manifest.json').is_file(), f'missing shared manifest in {output_root}')
    db = sqlite3.connect(f'file:{db_path}?mode=ro', uri=True)
    try:
        db.row_factory = sqlite3.Row
        recipe, items, kinds, static = recipe_join_report(output_root, db)
        handlers = json.loads((output_root / 'binary' / 'event_handlers_resolved.json').read_text())['entries']
        native = native_leaf_probes(output_root, recipe, items)
        recipe_events = {event['index']: event for event in static['events']}
        require(recipe_events[22]['params'] == {'UnlockType': 'DIYtutorial1', 'ItemUniqueId': 65534}
                and recipe_events[30]['params'] == {'UnlockType': 'DIYtutorial2', 'ItemUniqueId': 65534},
                'tutorial SetCraftRecipe group inputs changed')
        require(handlers['EventFlowSystemActor.EventFlowActionPlayerSetCraftRecipe']['constructor'] == '0x32dc50',
                'set-recipe handler registration changed')
        require(handlers['EventFlowSystemActor.EventFlowActionPlayerResetCraftRecipe']['constructor'] == '0x32cf40',
                'reset-recipe handler registration changed')
        require(handlers['EventFlowSystemActor.EventFlowQueryPlayerHasCraftRecipe']['constructor'] == '0x42aba0',
                'has-recipe query registration changed')
        learn_set_calls = selected_calls(db, 0x32dd30, (0xede0f0, 0xedf590, 0xedef00))
        learn_reset_calls = selected_calls(db, 0x32cff0, (0xede0f0, 0xedf6e0))
        transaction_calls = selected_calls(db, 0xee1420,
                                           (0xee0ed0, 0xeff060, 0xefab90, 0xee17e0))
        save_craft_calls = selected_calls(db, 0x3358c0, (0xedf8e0, 0xee1420))
        inventory_mutator_calls = selected_calls(
            db, 0xeff060, (0xf8f400, 0xee9350, 0xee9490, 0xee94f0, 0xf9e410, 0xee93d0))
        require(len([c for c in transaction_calls if c['target'] == '0xeff060']) == 6,
                'craft transaction no longer has six material delta call sites')
        require({'0xedf8e0', '0xee1420'} <= {c['target'] for c in save_craft_calls},
                'cWorkCraft SaveSet handler no longer prepares and enters the transaction')
        require(any(c['target'] == '0xf9e410' for c in inventory_mutator_calls),
                'inventory member mutator no longer reaches signed count helper')
        result = {
            'schema': 'acnh.crafting_recipe_flow_native.v1',
            'scope': 'Recipe table joins and state consumers, recipe bit leaf helpers, and one signed material inventory helper on controlled fixtures. SaveSetFromUIResult and the UI transaction are static only.',
            'evidence_labels': {
                'table rows and joins': '[TBL: shared resolved tables]',
                'EventFlow': '[EF: indexed Ftr_Working events]',
                'handler routes': '[NATIVE STATIC: call index + pseudocode/disassembly available in shared corpus]',
                'bit leaf helpers': '[EXECUTED NATIVE: synthetic byte-array fixture]',
                'material delta helper': '[EXECUTED NATIVE: reconstructed pocket fixture; one predicate stub]',
                'save durability and rollback': '[OPEN: no full player/UI/save runtime]'},
            'provenance': {
                'output_root': str(output_root),
                'read_only_index': str(db_path),
                'index_mode': 'SQLite URI mode=ro',
                'shared_manifest_sha256': sha256(output_root / 'manifest.json'),
                'analysis_elf_sha256': native['analysis_elf_sha256']},
            'recipe_table_and_joins': static,
            'learn_recipe': {
                'event_actions': [recipe_events[22], recipe_events[30],
                                  recipe_events[70], recipe_events[75]],
                'query_and_made_examples': {
                    'queries': [recipe_events[72], recipe_events[77]],
                    'made_checks': [recipe_events[69], recipe_events[74]],
                    'item_to_recipe_join': [
                        {'item_id': 7211, 'diy_recipe_id': 458, 'craft_unlock': 'WoodBridge'},
                        {'item_id': 5166, 'diy_recipe_id': 461, 'craft_unlock': 'CampSite'}]},
                'handler_registration': {
                    'set': {'constructor': handlers['EventFlowSystemActor.EventFlowActionPlayerSetCraftRecipe']['constructor'],
                            'behavior_va': '0x32dd30'},
                    'reset': {'constructor': handlers['EventFlowSystemActor.EventFlowActionPlayerResetCraftRecipe']['constructor'],
                              'behavior_va': '0x32cff0'},
                    'query': {'constructor': handlers['EventFlowSystemActor.EventFlowQueryPlayerHasCraftRecipe']['constructor'],
                              'behavior_va': '0x42ac80'}},
                'group_and_item_paths': {
                    'set_group_enumerator_calls': learn_set_calls,
                    'reset_group_enumerator_calls': learn_reset_calls,
                    'claims': [
                        'The set handler maps UnlockType strings through the 46-entry native enum. For a group it builds a RecipeCraftParam.CraftUnlock-matching bitset and applies per-recipe learn setters; a valid item-specific request routes through 0xedef00.',
                        'The reset handler uses the same group bitset and routes each recipe ID through 0xedf830, which clears its learned bit with 0xf290b0.',
                        '0xee1ec0 converts the ItemParam row to its DiyRecipeID and checks the bit through 0xf28fd0. The EventFlow query has additional group logic and has not been run against a save; do not infer its result polarity from its display name alone.']},
                'save_bit_layout_static': {
                    'player_save_member_offset': '0x8e920',
                    'selector_stride_bytes': '0x100',
                    'recipe_id_domain': '0..2047',
                    'byte_offset_within_selector': 'recipe_id >> 3',
                    'bit_mask': '1 << (recipe_id & 7)',
                    'selector_above_7': 'falls back to selector group zero in the writer',
                    'direct_bit_helpers': {'test': '0xf28fd0', 'set': '0xf29050', 'clear': '0xf290b0'},
                    'runtime_save_mutation': 'not executed'},
                'native_leaf_probe': native['bit_helpers']},
            'material_and_workbench': {
                'availability': {
                    'cold_cache_native_helper': '0xee0be0',
                    'recipe_material_getter': '0xedac50',
                    'executed_real_row': 56,
                    'status': 'previous native fixture: RecipeCraftParam row 56 reads five real one-count materials; cache source records A/B/C are reconstructed'},
                'consumption_leaf_probe': native['material_consumer'],
                'eventflow_order': [recipe_events[212], recipe_events[208],
                                    recipe_events[217], recipe_events[221]],
                'static_execution_chain': {
                    'save_set_type': 'cWorkCraft (enum index 9)',
                    'save_set_handler': '0x3358c0',
                    'save_set_calls': save_craft_calls,
                    'transaction_helper': '0xee1420',
                    'transaction_calls': transaction_calls,
                    'inventory_record_mutator': {
                        'va': '0xeff060',
                        'player_wrapper_member_offset': '0x1c0',
                        'save_member_access_calls': inventory_mutator_calls,
                        'signed_count_helper': '0xf9e410'},
                    'result_award': '0xee1420 -> 0xefab90 -> 0xefac20 -> 0xf987c0',
                    'post_add_marker': '0xee17e0 -> 0xf29080; the writer ignores IDs >= 0x800',
                    'timing_claim': 'The cWorkCraft SaveSetFromUIResult action prepares the UI result and enters 0xee1420 before the following PlayerWorkbenchMaking/GetDemo EventFlow actions. WorkCraftBgPage is a page initializer, not the transaction.'}},
            'save_and_rollback_boundaries': {
            'mutation_target': 'The six 0xeff060 calls resolve player-wrapper member +0x1c0 and mutate its in-memory count array; result insertion also uses the general item inventory path.',
                'precheck': '0xee1420 consults the transaction material flag before ingredient mutation; insufficient precheck returns before the consumption loop.',
                'rollback': 'No undo/refund branch is visible in the handler after ingredient deltas and result award. Full atomicity, interruption handling, and later manager rollback remain unexecuted.',
                'persistence': 'The traced helper mutates a save member in memory; serializer/flush boundary to durable save file was not identified.',
                'made_marker': '0xf29080 uses a second bitmap lane and accepts only IDs below 0x800. EventFlow MadeItemID values 7211 and 5166 exceed that bound; whether the query uses another path is open.'},
            'residuals': [
                'Execute EventFlowActionPlayerSetCraftRecipe, reset, and PlayerHasCraftRecipe against a real save-member fixture; current bit probe tests the native leaf operations only.',
                'Resolve query return polarity and the exact ItemParam.DiyRecipeID conversion path with a controlled save wrapper.',
                'Run SaveSetFromUIResult cWorkCraft and 0xee1420 with a complete reconstructed player/UI fixture, including output insertion, interruption, and rollback observations.',
                'Identify the serializer/flush boundary and determine whether item IDs above 0x7ff use a separate MadeItemID path.']}
    finally:
        db.close()
    ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'result': 'pass', 'output': str(ARTIFACT),
                      'recipe_rows': len(recipe['rows']),
                      'joined_outputs': result['recipe_table_and_joins']['joins']['recipe_item_to_itemparam_unique_id']['matched'],
                      'bit_cases': len(native['bit_helpers']['cases']),
                      'consumption_cases': len(native['material_consumer']['cases'])}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-root', type=Path, required=True,
                        help='shared output directory containing the read-only index and decoded tables')
    args = parser.parse_args()
    build(args.output_root.resolve())


if __name__ == '__main__':
    main()
