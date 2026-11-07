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


def decomp(output_root, name):
    path = output_root / 'binary' / 'analysis_decomp' / f'{name}.c'
    require(path.is_file(), f'missing decompiler source: {path}')
    return path.read_text()


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

    def native_ins(address):
        decoded = image.disasm(address, 4)
        require(decoded and decoded[0].address == address,
                f'missing native instruction at {address:#x}')
        instruction = decoded[0]
        return f'{instruction.mnemonic} {instruction.op_str}'.strip()

    # Inspect the stack-full precheck path as instructions rather than relying
    # on Ghidra's decompilation, which marks several live branches unreachable.
    # The object copied to the later pocket helper is an ItemId descriptor
    # copied from the current recipe material slot, not the craft result item.
    precheck_instructions = {
        hex(address): native_ins(address) for address in (
            0xee144c, 0xee1450, 0xee1468, 0xee1478,
            0xee0f00, 0xee0f3c, 0xee0f48, 0xee0f98, 0xee0f9c, 0xee0fa0,
            0xee0fcc, 0xee0fd0, 0xee0fd4, 0xee0ffc, 0xee1000,
            0xee1030, 0xee1038, 0xee104c, 0xee1050, 0xee1054,
            0xee165c, 0xee1660, 0xee1664, 0xee1668, 0xee166c,
            0xee1670, 0xee1674, 0xee1678, 0xee167c,
            0xee1680, 0xee1684, 0xee1688)}
    require(precheck_instructions['0xee1450'] == 'bl #0xefa9a0'
            and precheck_instructions['0xee1478'] == 'bl #0xee0ed0',
            'craft full-pocket precheck call sequence changed')
    require(precheck_instructions['0xee0f3c'] == 'add x21, x21, #0x2c'
            and precheck_instructions['0xee0f48'] == 'bl #0xf589b0'
            and precheck_instructions['0xee0fa0'] == 'bl #0xeda620'
            and precheck_instructions['0xee1000'] == 'b.lo #0xee1038'
            and precheck_instructions['0xee1030'] == 'cbnz w23, #0xee104c'
            and precheck_instructions['0xee1054'] == 'bl #0xf589e0',
            'craft precheck material-slot copy path changed')
    require(precheck_instructions['0xee1664'] == 'bl #0xf589b0'
            and precheck_instructions['0xee166c'] == 'bl #0xda4020'
            and precheck_instructions['0xee1678'] == 'bl #0xf58d00'
            and precheck_instructions['0xee1688'] == 'bl #0xefbd30',
            'craft post-consumption pocket insertion gate changed')
    sample_material_ids = [
        field(recipe, next(row for row in recipe['rows']
                           if field(recipe, row, 'UniqueID') == 56),
              f'Material{slot}')
        for slot in range(1, 7)]
    sample_material_ids = [item_id for item_id in sample_material_ids if item_id != 0xfffe]
    precheck_temp_item = {
        'status': 'NATIVE_STATIC_ASSEMBLY; not dynamically executed',
        'transaction_helper_va': '0xee1420',
        'precheck_helper_va': '0xee0ed0',
        'initial_free_pocket_test': {
            'helper_va': '0xefa9a0',
            'behavior': 'reads the player-associated +0x70 pocket member and returns whether its 0x17c-byte view has an empty item slot; a false result routes into 0xee0ed0 and marks the temporary output pointer as present'},
        'material_source': {
            'payload_offset_first_slot': '0x2c',
            'slot_stride': '0x14',
            'slot_count': 6,
            'recipe_56_candidate_item_ids': sample_material_ids,
            'identity': '0xee0ed0 scans the six material descriptors, and the live capture branch at 0xee104c copies the current descriptor to its output object'},
        'precheck_counts': {
            'slot_and_total_counter_va': '0xeda620',
            'behavior': 'counts matching pocket slots and their total units for the current material descriptor',
            'native_stack_limit_reader_va': '0xaac450',
            'behavior_detail': 'the helper compares the current matching-slot count with the stack-count requirement before and after subtracting the recipe amount'},
        'capture_conditions_static': [
            'When the computed stack requirement before consumption is below the current matching-slot count and the caller supplied the temp output, branch 0xee1030 reaches the copy at 0xee104c.',
            'When the post-consumption stack requirement is below the current matching-slot count but remains positive, branch 0xee1038 falls through to the same copy; a zero remainder does not capture the descriptor.',
            'The copy is of the current RecipeCraftParam.MaterialN item descriptor, not the recipe output descriptor.'
        ],
        'post_consumption_gate': {
            'transaction_mode_helper_va': '0xda4020',
            'item_descriptor_validity_helper_va': '0xf58d00',
            'pocket_add_helper_va': '0xefbd30',
            'gate': 'after either six-slot processor, the transaction-mode helper and descriptor-validity helper must both return true before 0xefbd30 receives the captured material descriptor'},
        'interpretation_limit': 'This proves the temporary descriptor source and stack-count conditions. It does not establish whether the insertion compacts a stack, restores a material, or implements rollback; the full transaction was not run.'}

    # Resolve the selected item's ItemParam row through the native ItemParam
    # type-index table, then execute the exact type-code predicate used by the
    # remake workbench. The manager and row storage are reconstructed from the
    # real decoded tables; the predicate itself remains original ELF code.
    inventory_requirements.ROOT = output_root.parent
    type_sandbox = Sandbox(image)
    type_tables = inventory_requirements.install_item_tables(type_sandbox)
    item_manifest = json.loads((output_root / 'manifest.json').read_text())
    item_entry = item_manifest['entries'][items['source_id']]
    item_decoded = json.loads((output_root / item_entry['decoded']).read_text())['data']
    item_data_base = 0x51000000
    item_rows = {field(items, row, 'UniqueID'): (index, row)
                 for index, row in enumerate(items['rows'])}
    phone_case_kind_row = next(row for row in type_tables['kind_table']['rows']
                               if field(type_tables['kind_table'], row, 'Label') == 'CraftPhoneCase')
    phone_case_kind_ordinal = type_tables['kind_table']['rows'].index(phone_case_kind_row)
    phone_case_probe_item = next(
        field(items, row, 'UniqueID') for row in items['rows']
        if enum_label(field(items, row, 'ItemKind')) == 'CraftPhoneCase')
    require(phone_case_kind_ordinal == 0x38 and phone_case_probe_item in item_rows,
            'native type-code positive control no longer joins CraftPhoneCase')
    tutorial_type_cases = []
    for item_id in (3436, phone_case_probe_item):
        row_index, item_row = item_rows[item_id]
        row_va = item_data_base + item_decoded['data_start'] + row_index * items['row_size']
        item_object = type_sandbox.HEAP + 0x20000 + len(tutorial_type_cases) * 0x100
        type_sandbox.uc.mem_write(item_object, bytes(0x20))
        type_sandbox.uc.mem_write(item_object + 0x10, struct.pack('<Q', row_va))
        item_param_index = type_sandbox.call(0x1665ea0, (row_va,), limit=100000)
        result = type_sandbox.call(0x15806f0, (item_object,), limit=100000)
        expected = int(item_id == phone_case_probe_item)
        require(result == expected,
                f'remake type-code 0x38 classification changed for ItemParam {item_id}')
        tutorial_type_cases.append({
            'item_id': item_id,
            'itemparam_row_index': row_index,
            'native_row_index_result': item_param_index,
            'item_kind': enum_label(field(items, item_row, 'ItemKind')),
            'type_code': 0x38,
            'predicate_va': '0x15806f0',
            'predicate_result': result,
            'itemparam_raw_row_pointer': hex(row_va)})

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

    # Craft-result markers use a second bitmap lane in the same 0x1400-byte
    # member. The keys are RecipeCraftParam.UniqueID values, even when the
    # EventFlow MadeItemID is a much larger ItemParam.UniqueID.
    made_bits = bit_sandbox.HEAP + 0x30000
    u.mem_write(made_bits, bytes(0x200))
    made_bit_cases = []
    for recipe_id in (56, 458, 461, 2047, 2048):
        before = bit_sandbox.call(0xf29010, (made_bits, recipe_id))
        bit_sandbox.call(0xf29080, (made_bits, recipe_id))
        after = bit_sandbox.call(0xf29010, (made_bits, recipe_id))
        array = bytes(u.mem_read(made_bits, 0x200))
        expected = int(recipe_id < 2048)
        require(before == 0 and after == expected,
                f'made-recipe marker helper mismatch for recipe ID {recipe_id}')
        made_bit_cases.append({
            'recipe_id': recipe_id,
            'valid_domain': recipe_id < 2048,
            'before_set_query': before,
            'after_set_query': after,
            'expected_bitmap_offset': 0x100 + (recipe_id >> 3) if expected else None,
            'expected_bit_mask': (1 << (recipe_id & 7)) if expected else None,
            'nonzero_bytes_after_set': sum(value != 0 for value in array)})

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
        'remake_tutorial_type_code': {
            'predicate_wrapper_va': '0x15806f0',
            'kind_resolver_va': '0xa9cb60',
            'itemparam_row_index_helper_va': '0x1665ea0',
            'compared_code': 0x38,
            'native_kind_ordinal': phone_case_kind_ordinal,
            'positive_control_item_id': phone_case_probe_item,
            'fixture': 'original ItemParam and ItemKind table blobs; native manager/index arrays reconstructed from decoded rows; selected object points at its raw ItemParam row',
            'cases': tutorial_type_cases,
            'stubbed_boundaries': []},
        'bit_helpers': {
            'set_va': '0xf29050', 'clear_va': '0xf290b0', 'query_va': '0xf28fd0',
            'fixture': 'zeroed 256-byte array; no SaveGame member wrapper or player context',
            'cases': bit_cases,
            'stubbed_boundaries': []},
        'made_marker_helpers': {
            'set_va': '0xf29080', 'query_va': '0xf29010',
            'fixture': 'zeroed 0x200-byte memory; helpers use bitmap lane at base + 0x100; no player/save wrapper',
            'cases': made_bit_cases,
            'stubbed_boundaries': []},
        'material_consumer': {
            'signed_count_helper_va': '0xf9e410',
            'stack_match_gate_va': '0xf9e840',
            'fixture': '32 eight-byte item slots followed by u16 counts at +0x100; slot 0 is Apple item 2213; requested deltas are negative',
            'cases': material_probe_cases,
            'stubbed_boundary': 'Each case patches 0xaac730 to return true. Item lookup, pocket slot search, 0xf9e840 control flow, 0xf9e410, and the u16 count writes execute from the original ELF.'},
        'craft_full_pocket_precheck': precheck_temp_item,
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
        recipe_rows = {field(recipe, row, 'UniqueID'): row for row in recipe['rows']}
        item_rows = {field(items, row, 'UniqueID'): row for row in items['rows']}
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
        made_query_handler = handlers['EventFlowSystemActor.EventFlowQueryPlayerIsMadeCraftRecipe']
        require(made_query_handler['constructor'] == '0x42d1c0',
                'made-recipe query registration changed')
        learn_set_calls = selected_calls(db, 0x32dd30, (0xede0f0, 0xedf590, 0xedef00))
        learn_reset_calls = selected_calls(db, 0x32cff0, (0xede0f0, 0xedf6e0))
        transaction_calls = selected_calls(db, 0xee1420,
                                           (0xee0ed0, 0xeff060, 0xefab90, 0xee17e0))
        transaction_pocket_add_calls = selected_calls(db, 0xee1420, (0xefbd30,))
        pocket_add_helper_calls = selected_calls(db, 0xefbd30, (0xf99270, 0xefb090))
        award_item_add_calls = selected_calls(db, 0xefac20, (0xf987c0,))
        generic_pocket_add_calls = selected_calls(db, 0xf987c0, (0xf99270,))
        save_craft_calls = selected_calls(db, 0x3358c0, (0xedf8e0, 0xee1420))
        made_query_calls = selected_calls(db, 0x42d3b0, (0xedbd00,))
        made_query_leaf_calls = selected_calls(db, 0xedbd00, (0xab4f60, 0xab78e0, 0xf29010))
        marker_writer_calls = selected_calls(db, 0xee17e0, (0xf29080,))
        inventory_mutator_calls = selected_calls(
            db, 0xeff060, (0xf8f400, 0xee9350, 0xee9490, 0xee94f0, 0xf9e410, 0xee93d0))
        require(len([c for c in transaction_calls if c['target'] == '0xeff060']) == 6,
                'craft transaction no longer has six material delta call sites')
        require({'0xedf8e0', '0xee1420'} <= {c['target'] for c in save_craft_calls},
                'cWorkCraft SaveSet handler no longer prepares and enters the transaction')
        require(any(c['target'] == '0xf9e410' for c in inventory_mutator_calls),
                'inventory member mutator no longer reaches signed count helper')
        require(len(made_query_calls) == 8,
                'made-recipe query no longer checks all eight MadeItemID parameter slots')
        require({'0xab4f60', '0xab78e0', '0xf29010'} <=
                {c['target'] for c in made_query_leaf_calls},
                'made-recipe query no longer maps item to recipe ID and reads the marker bitmap')
        require(any(c['target'] == '0xf29080' for c in marker_writer_calls),
                'craft-result marker path no longer reaches the native marker setter')

        made_events = [recipe_events[index] for index in (69, 74)]
        require(all(event['params']['CheckMode'] == 'cAND' for event in made_events),
                'wood-bridge/camp-site made-recipe checks changed from cAND')
        all_made_query_events = []
        for flow, index, actor, kind, name, params_json in db.execute(
                "SELECT flow,event_index,actor,kind,name,params_json FROM event_calls "
                "WHERE name='EventFlowQueryPlayerIsMadeCraftRecipe' ORDER BY flow,event_index"):
            params = json.loads(params_json)
            populated = []
            for slot in range(8):
                item_id = params.get(f'MadeItemID{slot}', 0xfffe)
                if item_id in (0xfffe, 0xffff):
                    continue
                item_row = item_rows.get(item_id)
                require(item_row is not None,
                        f'EventFlow made-recipe item {item_id} is missing from ItemParam')
                recipe_id = field(items, item_row, 'DiyRecipeID')
                require(recipe_id in recipe_rows,
                        f'EventFlow made-recipe item {item_id} points outside RecipeCraftParam')
                populated.append({
                    'slot': slot, 'item_id': item_id, 'recipe_id': recipe_id,
                    'recipe_in_bitmap_domain': recipe_id < 2048,
                    'item_id_exceeds_bitmap_domain': item_id >= 2048})
            all_made_query_events.append({
                'flow': flow, 'index': index, 'check_mode': params.get('CheckMode'),
                'populated_slots': populated,
                'sentinel_slots': 8 - len(populated)})
        require(len(all_made_query_events) == 2
                and sum(len(event['populated_slots']) for event in all_made_query_events) == 2,
                'global EventFlow MadeCraftRecipe query inventory changed')
        made_item_rows = []
        for item_id in (975, 7211, 5166):
            item_row = item_rows[item_id]
            recipe_id = field(items, item_row, 'DiyRecipeID')
            require(recipe_id in recipe_rows and field(recipe, recipe_rows[recipe_id], 'Item') == item_id,
                    f'ItemParam.DiyRecipeID no longer joins output item {item_id} to its recipe')
            made_item_rows.append({
                'item_id': item_id,
                'item_kind': enum_label(field(items, item_row, 'ItemKind')),
                'diy_recipe_id': recipe_id,
                'recipe_craft_unlock': enum_label(field(recipe, recipe_rows[recipe_id], 'CraftUnlock'))})
        generic_recipe_item = item_rows[0x16a2]
        require(enum_label(field(items, generic_recipe_item, 'ItemKind')) == 'DIYRecipe',
                'generic DIY recipe item 0x16a2 no longer has ItemKind DIYRecipe')
        recipe_kind_matches = [(index, row) for index, row in enumerate(kinds['rows'])
                               if field(kinds, row, 'Label') == 'DIYRecipe']
        require(len(recipe_kind_matches) == 1 and recipe_kind_matches[0][0] == 0x55
                and field(kinds, recipe_kind_matches[0][1], 'UniqueID') == 238,
                'ItemKind DIYRecipe row changed')
        made_events_static = [get_event(db, 'Ftr_Working', index) for index in (69, 74)]
        made_query_code = decomp(output_root, 'edbd00')
        item_to_recipe_code = decomp(output_root, 'ab4f60')
        recipe_id_return_code = decomp(output_root, 'ab78e0')
        marker_set_code = decomp(output_root, 'ee17e0')
        transaction_code = decomp(output_root, 'ee1420')
        pocket_add_code = decomp(output_root, 'efbd30')
        pocket_add_inventory_code = decomp(output_root, 'f99270')
        result_builder_code = decomp(output_root, 'edf8e0')
        recipe_builder_code = decomp(output_root, 'edc240')
        require('FUN_00bb4f60' in made_query_code and 'FUN_00bb78e0' in made_query_code
                and 'FUN_01029010' in made_query_code,
                'made-recipe query no longer converts item IDs to recipe IDs before bitmap read')
        require('0xbcf5d17a' in item_to_recipe_code and '0x16a2' in item_to_recipe_code
                and '0x55' in item_to_recipe_code,
                'made-recipe converter no longer reads DiyRecipeID and validates the recipe-item type')
        require('0x55' in recipe_id_return_code and 'param_1 + 0xc' in recipe_id_return_code,
                'made-recipe converter no longer returns the recipe ID from the typed recipe record')
        require('FUN_01029080' in marker_set_code
                and 'FUN_00fe17e0(param_1,*param_2,param_3)' in transaction_code,
                'craft transaction no longer forwards its first result-payload field to marker setter')
        require('FUN_00fdc240(&lStack_100,param_1,param_3,param_4,param_5 & 1)' in result_builder_code
                and '*param_2 = lStack_100' in result_builder_code,
                'cWorkCraft result builder no longer copies the recipe row payload into the transaction result')
        require('uStack_130 = (undefined2)param_3' in recipe_builder_code
                and '*param_1 = CONCAT44(iStack_12c,CONCAT22(uStack_12e,uStack_130))' in recipe_builder_code,
                'craft result payload no longer retains RecipeCraftParam.UniqueID in its first u16')
        require('FUN_00ffbd30(param_3,auStack_48)' in transaction_code
                and any(c['target'] == '0xefbd30' for c in transaction_pocket_add_calls),
                'conditional pocket-add path no longer follows the craft material branch')
        require('FUN_01099270' in pocket_add_code
                and {'0xf99270', '0xefb090'} <=
                {c['target'] for c in pocket_add_helper_calls}
                and 'FUN_01098650' in pocket_add_inventory_code,
                'post-material pocket helper no longer reaches item-slot insertion')
        require(any(c['target'] == '0xf987c0' for c in award_item_add_calls)
                and any(c['target'] == '0xf99270' for c in generic_pocket_add_calls),
                'general item-award route no longer shares the pocket insertion helper')
        result = {
            'schema': 'acnh.crafting_recipe_flow_native.v1',
                'scope': 'Recipe table joins and state consumers, learn/made marker bit leaf helpers, and one signed material inventory helper on controlled fixtures. SaveSetFromUIResult and the UI transaction are static only.',
            'evidence_labels': {
                'table rows and joins': '[TBL: shared resolved tables]',
                'EventFlow': '[EF: indexed Ftr_Working events]',
                'handler routes': '[NATIVE STATIC: call index + pseudocode/disassembly available in shared corpus]',
                'bit leaf helpers': '[EXECUTED NATIVE: synthetic byte-array fixture]',
                'made recipe marker mapping': '[NATIVE STATIC + TBL; bitmap leaf pair executed native]',
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
                'craft_full_pocket_precheck': native['craft_full_pocket_precheck'],
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
                    'post_add_marker': '0xee17e0 -> 0xf29080 writes the recipe ID from transaction-result payload field 0, in the second bitmap lane at save-member +0x100',
                    'conditional_pocket_add': {
                        'transaction_call': '0xee1420 -> 0xefbd30',
                        'call_site': transaction_pocket_add_calls,
                        'gate': 'The initial 0xefa9a0 pocket-empty test must be false so 0xee0ed0 runs with a temp-output pointer; after slot processing, 0xda4020 on the transaction context and 0xf58d00 on the captured descriptor must both return true before 0xefbd30 is called. This path is after either slot-processing form.',
                        'helper_chain': pocket_add_helper_calls,
                        'member_offset': '0x70 on the player-associated record',
                        'member_view_length_parameter': '0x17c',
                        'inventory_helper': '0xf99270 searches/updates the pocket-like slot arrays and reaches 0xf98650 to place an item record; 0xefb090 follows as the member notification/update helper.',
                        'shared_generic_add_path': {
                            'award_wrapper_va': '0xefac20',
                            'award_wrapper_calls': award_item_add_calls,
                            'general_inventory_add_va': '0xf987c0',
                            'general_inventory_add_calls': generic_pocket_add_calls,
                            'interpretation': 'The same 0xf99270 slot-placement helper is called by the general item-award insertion path 0xefac20 -> 0xf987c0, so the helper is shared with ordinary pocket item placement.'},
                        'interpretation': 'The temp object is copied from the current RecipeCraftParam.MaterialN descriptor when the precheck stack-count comparison takes a live capture branch. The helper is a shared general pocket insertion path, but why crafting passes this material descriptor into it and whether it represents compaction, restoration, or rollback remain unresolved; transaction atomicity cannot be inferred from this insertion alone.'},
                    'timing_claim': 'The cWorkCraft SaveSetFromUIResult action prepares the UI result and enters 0xee1420 before the following PlayerWorkbenchMaking/GetDemo EventFlow actions. WorkCraftBgPage is a page initializer, not the transaction.'}},
            'made_recipe_marker': {
                'eventflow_checks': made_events_static,
                'eventflow_coverage': {
                    'source': 'all indexed EventFlowQueryPlayerIsMadeCraftRecipe calls in the shared corpus',
                    'query_count': len(all_made_query_events),
                    'populated_item_count': sum(len(event['populated_slots'])
                                                for event in all_made_query_events),
                    'queries': all_made_query_events},
                'handler': {'constructor': made_query_handler['constructor'],
                            'behavior_va': '0x42d3b0',
                            'query_calls_per_item_slot': made_query_calls},
                'query_item_to_recipe_path': {
                    'behavior_va': '0x42d3b0',
                    'per_item_helper_va': '0xedbd00',
                    'field_converter_va': '0xab4f60',
                    'recipe_id_accessor_va': '0xab78e0',
                    'bitmap_query_va': '0xf29010',
                    'calls': made_query_leaf_calls,
                    'field_hash': '0xbcf5d17a',
                    'field_name': 'ItemParam.DiyRecipeID',
                    'generic_recipe_item_id': 0x16a2,
                    'generic_recipe_item_kind': enum_label(field(items, generic_recipe_item, 'ItemKind')),
                    'kind_gate': {'itemkind_row_index': recipe_kind_matches[0][0],
                                  'itemkind_unique_id': field(kinds, recipe_kind_matches[0][1], 'UniqueID'),
                                  'label': 'DIYRecipe',
                                  'behavior': 'the converter returns the row DiyRecipeID as the bitmap key only after validating the typed recipe record'},
                    'examples': made_item_rows},
                'write_path': {
                    'save_set_ui_result_builder': '0xedf8e0',
                    'recipe_payload_builder': '0xfdc240',
                    'transaction_va': '0xee1420',
                    'transaction_marker_calls': [c for c in transaction_calls if c['target'] == '0xee17e0'],
                    'marker_writer_va': '0xee17e0',
                    'marker_bitmap_setter_va': '0xf29080',
                    'marker_writer_calls': marker_writer_calls,
                    'result_payload_key': 'the first u16 copied from the selected RecipeCraftParam.UniqueID into the cWorkCraft result payload',
                    'bitmap_lane_offset': '0x100'},
                'native_leaf_probe': native['made_marker_helpers'],
                'interpretation': 'The 0x800 bound applies to RecipeCraftParam.UniqueID, not ItemParam.UniqueID. The WoodBridge and CampSite EventFlow item IDs 7211 and 5166 map through ItemParam.DiyRecipeID to 458 and 461 before the query reads the marker bit; they therefore use the ordinary in-range marker lane.'},
            'save_and_rollback_boundaries': {
            'mutation_target': 'The six 0xeff060 calls resolve player-wrapper member +0x1c0 and mutate its in-memory count array; result insertion also uses the general item inventory path.',
                'precheck': 'When 0xefa9a0 reports no empty pocket slot, 0xee1420 calls 0xee0ed0 with a temporary descriptor output; the helper counts material slots/units, but its return/status is not used by the caller.',
                'rollback': 'A conditional pocket insertion follows material processing: 0xee1420 -> 0xefbd30 -> 0xf99270 -> 0xefb090. Assembly traces its temporary object to a current RecipeCraftParam.MaterialN descriptor under stack-count conditions; full transaction effects, atomicity, and interruption behavior remain unexecuted.',
                'persistence': 'The traced helper mutates a save member in memory. SaveSimpleSave separately queues SaveProc; the craft handler does not directly call that request path. Serializer/flush boundary to durable save file was not identified.',
                'made_marker': 'The key is RecipeCraftParam.UniqueID; high ItemParam.UniqueID inputs are converted through DiyRecipeID before lookup. The two observed tutorial IDs resolve to in-range recipe IDs 458 and 461.'},
            'residuals': [
                'Execute EventFlowActionPlayerSetCraftRecipe, reset, and PlayerHasCraftRecipe against a reconstructed player-save fixture; current bit probe tests the native leaf operations only.',
                'Execute the PlayerHasCraftRecipe wrapper against a reconstructed player-save fixture to verify return polarity and selector behavior.',
                'Run SaveSetFromUIResult cWorkCraft and 0xee1420 with a complete reconstructed player/UI fixture; determine effects of the captured RecipeCraftParam.MaterialN descriptor, output insertion, interruption, and rollback behavior.',
                'Identify the serializer and durable file write/flush after the separate SaveSimpleSave -> SaveProc request path for recipe and made-recipe members.',
                'Execute the full PlayerIsMadeCraftRecipe wrapper against player-save and eight-item fixtures to verify cAND/cOR polarity and mixed valid/invalid inputs.']}
        result['remake_tutorial_type_code'] = native['remake_tutorial_type_code']
    finally:
        db.close()
    ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'result': 'pass', 'output': str(ARTIFACT),
                      'recipe_rows': len(recipe['rows']),
                      'joined_outputs': result['recipe_table_and_joins']['joins']['recipe_item_to_itemparam_unique_id']['matched'],
                      'bit_cases': len(native['bit_helpers']['cases']),
                      'made_marker_cases': len(native['made_marker_helpers']['cases']),
                      'consumption_cases': len(native['material_consumer']['cases'])}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-root', type=Path, required=True,
                        help='shared output directory containing the read-only index and decoded tables')
    args = parser.parse_args()
    build(args.output_root.resolve())


if __name__ == '__main__':
    main()
