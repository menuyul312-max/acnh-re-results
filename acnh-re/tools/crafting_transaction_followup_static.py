"""Extract native/EventFlow evidence around DIY craft and remake transactions.

This is a read-only evidence extractor over the shared decoded source database,
tables, and decompiler output. It does not emulate a player transaction.
"""
from pathlib import Path
import hashlib
import json
import sqlite3
import sys

REPO = Path(__file__).resolve().parents[1]
SHARED = Path('/workspace/acnh-re')
OUTPUT = REPO / 'output' / 'gameplay' / 'crafting_transaction_followup'
DB = SHARED / 'output' / 'index.sqlite'
DECOMP = SHARED / 'output' / 'binary' / 'analysis_decomp'
TABLES = SHARED / 'output' / 'tables_resolved'
MANIFEST = SHARED / 'output' / 'manifest.json'
HANDLERS = SHARED / 'output' / 'binary' / 'event_handlers_resolved.json'
PREVIOUS = OUTPUT / 'crafting_transaction_followup_native.json'
ELF = REPO / 'inputs' / 'additional_exefs' / 'main'


def sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def table(name):
    return json.loads((TABLES / f'{name}.json').read_text())


def table_blob_hash(name, manifest):
    decoded = table(name)
    source_id = str(decoded['source_id'])
    entries = manifest['entries']
    entry = entries[int(source_id)] if isinstance(entries, list) else entries[source_id]
    blob = SHARED / 'output' / entry['decoded']
    # The resolved table points at the original BCSV blob. Resolve it from the
    # manifest-backed source record without copying any source file.
    blob_path = decoded['raw']['$blob']
    path = SHARED / 'output' / blob_path
    return sha256(path)


def table_row(data, key, value):
    col = next(i for i, column in enumerate(data['columns']) if column['name'] == key)
    return next(row for row in data['rows'] if row[col] == value)


def column_value(data, row, key):
    col = next(i for i, column in enumerate(data['columns']) if column['name'] == key)
    return row[col]


def enum_values(text):
    return [value.strip() for value in text.rstrip(',').split(',')]


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def function_span(db, va):
    row = db.execute('SELECT size FROM native_functions WHERE va=?', (va,)).fetchone()
    if row is None:
        row = db.execute('SELECT size FROM functions WHERE va=?', (va,)).fetchone()
    require(row is not None, f'missing function span for {va:#x}')
    return row[0]


def direct_calls(db, va):
    size = function_span(db, va)
    return [
        {'pc': f'0x{pc:x}', 'target': f'0x{target:x}'}
        for pc, target in db.execute(
            'SELECT pc,target_va FROM direct_calls WHERE pc>=? AND pc<? ORDER BY pc',
            (va, va + size))
    ]


def calls_to(db, va, target):
    return [call for call in direct_calls(db, va) if int(call['target'], 16) == target]


def event(db, flow, index):
    row = db.execute(
        'SELECT actor,kind,name,params_json FROM event_calls '
        'WHERE flow=? AND event_index=?', (flow, index)).fetchone()
    require(row is not None, f'missing EventFlow row {flow}#{index}')
    return {'flow': flow, 'index': index, 'actor': row[0], 'kind': row[1],
            'name': row[2], 'params': json.loads(row[3])}


def string_for_function(db, function_va, needle):
    rows = db.execute(
        'SELECT text FROM string_refs WHERE function_va=? AND instr(text,?)>0 '
        'ORDER BY string_va', (function_va, needle)).fetchall()
    require(rows, f'missing enum/string {needle} from function {function_va:#x}')
    return rows[0][0]


def decomp(name):
    path = DECOMP / f'{name}.c'
    return path, path.read_text()


def disassemble(source_elf, addresses):
    sys.path.insert(0, str(SHARED / '.deps'))
    sys.path.insert(0, str(REPO / 'tools'))
    from native_image import Image  # noqa: E402

    image = Image(source_elf)
    result = {}
    for address in addresses:
        instructions = image.disasm(address, 4)
        require(instructions, f'no instruction at {address:#x}')
        instruction = instructions[0]
        result[f'0x{address:x}'] = f'{instruction.mnemonic} {instruction.op_str}'.strip()
    return result


def build_report():
    require(DB.is_file() and ELF.is_file(), 'shared index or main ELF is unavailable')
    db = sqlite3.connect(DB)
    db.row_factory = sqlite3.Row
    manifest = json.loads(MANIFEST.read_text())
    analysis_elf = Path(manifest['source_root']) / 'A_logic' / 'main.elf'
    require(analysis_elf.is_file(), f'missing source ELF: {analysis_elf}')
    handlers = json.loads(HANDLERS.read_text())
    previous = json.loads(PREVIOUS.read_text())
    require(sha256(analysis_elf) == previous['provenance']['analysis_elf_sha256'],
            'source ELF checksum differs from the executed cache stage')

    set_recipe_handler = handlers['entries']['EventFlowSystemActor.EventFlowActionPlayerSetCraftRecipe']
    has_recipe_query = handlers['entries']['EventFlowSystemActor.EventFlowQueryPlayerHasCraftRecipe']
    workbench_make = handlers['entries']['Player.EventFlowActionPlayerWorkbenchMaking']
    require(set_recipe_handler['constructor'] == '0x32dc50', 'unexpected set-recipe registration')
    require(has_recipe_query['constructor'] == '0x42aba0', 'unexpected has-recipe registration')

    unlock_text = string_for_function(db, 0x2baa20, 'DIYtutorial1')
    unlock_types = enum_values(unlock_text)
    save_type_text = string_for_function(db, 0x3362f0, 'cWorkCraft')
    save_types = enum_values(save_type_text)
    save_type_dispatch_path, save_type_dispatch = decomp('334650')
    require(unlock_types[12:14] == ['DIYtutorial1', 'DIYtutorial2'],
            'unlock enum no longer maps the tutorial group names at indices 12 and 13')
    require(save_types[9:11] == ['cWorkCraft', 'cWorkRemake'],
            'save-type enum no longer maps craft/remake at indices 9 and 10')
    require('case 9:' in save_type_dispatch and 'FUN_004358c0' in save_type_dispatch
            and 'case 10:' in save_type_dispatch and 'FUN_00435d10' in save_type_dispatch,
            'SaveSetFromUIResult no longer dispatches craft/remake to the mapped native handlers')

    learning_events = [event(db, 'Ftr_Working', i) for i in (22, 30, 69, 70, 72, 74, 75, 77)]
    require(learning_events[0]['params'] == {'UnlockType': 'DIYtutorial1', 'ItemUniqueId': 65534},
            'tutorial 1 unlock action changed')
    require(learning_events[1]['params'] == {'UnlockType': 'DIYtutorial2', 'ItemUniqueId': 65534},
            'tutorial 2 unlock action changed')

    set_recipe_calls = direct_calls(db, 0x32dd30)
    has_recipe_calls = direct_calls(db, 0x42ac80)
    set_decomp_path, set_decomp = decomp('32dd30')
    has_decomp_path, has_decomp = decomp('42ac80')
    save_decomp_path, save_decomp = decomp('edf0e0')
    require('FUN_00fde0f0' in set_decomp and 'FUN_00fdf590' in set_decomp
            and 'FUN_00fdef00' in set_decomp,
            'set-recipe handler no longer routes group and single-recipe helpers')
    require('FUN_00fe1ec0' in has_decomp and 'FUN_00fe1f80' in has_decomp,
            'has-recipe query no longer routes save-state checks')
    require('param_1 + 0x8e920' in save_decomp and 'param_2 >> 3' in save_decomp
            and '1 << (ulong)(param_2 & 7)' in save_decomp,
            'recipe save helper no longer exposes indexed bit writes')

    craft_events = [event(db, 'Ftr_Working', i) for i in (10, 208, 212, 217, 221)]
    require(craft_events[2]['params'] == {'SaveType': 'cWorkCraft'}, 'craft SaveType changed')
    make_handler = handlers['entries']['Player.EventFlowActionPlayerWorkbenchMaking']
    require(make_handler['constructor'] == '0x2e2a70', 'unexpected workbench-make registration')

    craft_save_calls = direct_calls(db, 0x3358c0)
    craft_transaction_calls = direct_calls(db, 0xee1420)
    mutation_calls = direct_calls(db, 0xeff060)
    award_calls = direct_calls(db, 0xefab90)
    award_impl_calls = direct_calls(db, 0xefac20)
    craft_decomp_path, craft_decomp = decomp('ee1420')
    mutation_decomp_path, mutation_decomp = decomp('eff060')
    inventory_decomp_path, inventory_decomp = decomp('f9e410')
    item_add_decomp_path, item_add_decomp = decomp('efac20')
    craft_marker_decomp_path, craft_marker_decomp = decomp('ee17e0')
    require(any(int(c['target'], 16) == 0xedf8e0 for c in craft_save_calls),
            'cWorkCraft handler no longer prepares UI result through 0xedf8e0')
    require(any(int(c['target'], 16) == 0xee1420 for c in craft_save_calls),
            'cWorkCraft handler no longer routes through 0xee1420')
    require(len(calls_to(db, 0xee1420, 0xeff060)) == 6,
            'native craft transaction should contain six material mutator call sites')
    require('-(uint)(ushort)param_2[0x1a]' in craft_decomp
            and 'FUN_00fff060(param_3' in craft_decomp,
            'craft transaction no longer passes signed negative ingredient quantities')
    require('FUN_0109e410' in mutation_decomp and 'param_3 < 0' in inventory_decomp,
            'inventory delta helper no longer exposes signed-count subtraction path')
    require(any(int(c['target'], 16) == 0xefac20 for c in award_calls),
            'craft result path no longer reaches general item-add helper')
    require(any(int(c['target'], 16) == 0xf987c0 for c in award_impl_calls),
            'item-add helper no longer routes through inventory insertion routine')
    require('FUN_01029080' in craft_marker_decomp,
            'post-craft marker helper no longer sets its bounded bitmap')

    remake_item_table = table('ItemParam')
    remake_table = table('ItemRemake')
    kit_row = table_row(remake_item_table, 'UniqueID', 2513)
    closet_row = table_row(remake_item_table, 'UniqueID', 3436)
    remake_id = column_value(remake_item_table, closet_row, 'RemakeID')
    remake_record = table_row(remake_table, 'UniqueID', remake_id)
    require(column_value(remake_table, remake_record, 'ItemUniqueID') == 3436,
            'item-remake record no longer selects tutorial closet 3436')
    require(column_value(remake_table, remake_record, 'RemakeKitNum') == 2,
            'tutorial closet remake-kit table cost changed')

    remake_events = [event(db, 'Ftr_Working', i) for i in (37, 11, 182, 184, 185, 94, 98, 100, 104)]
    require(remake_events[2]['params'] == {'SaveType': 'cWorkRemake'}, 'remake SaveType changed')
    require(remake_events[6]['params'] == {'ItemUniqueId': 2513, 'SetNum': 50},
            'remake tutorial kit award changed')
    remake_save_calls = direct_calls(db, 0x335d10)
    remake_update_path, remake_update = decomp('f99b10')
    remake_kit_arg_disasm = disassemble(
        analysis_elf, (0x335d54, 0x335d64, 0x335d78, 0x335d7c,
              0xefbe04, 0xefbe08, 0xefbe0c, 0xefbe84, 0xefbe88, 0xefbe8c))
    require(any(int(c['target'], 16) == 0xefbdf0 for c in remake_save_calls)
            and any(int(c['target'], 16) == 0xefbad0 for c in remake_save_calls),
            'cWorkRemake handler no longer routes into remake/inventory helpers')
    require(remake_kit_arg_disasm['0x335d64'] == 'mov w1, #0x9d1'
            and remake_kit_arg_disasm['0x335d78'] == 'mov w2, w21'
            and '0xefbdf0' in remake_kit_arg_disasm['0x335d7c']
            and remake_kit_arg_disasm['0xefbe88'] == 'mov w2, w19'
            and '0xf99b10' in remake_kit_arg_disasm['0xefbe8c'],
            'remake kit ID/quantity argument flow changed')
    require('FUN_01099b10' in decomp('efbdf0')[1]
            and 'FUN_01098650' in remake_update,
            'remake update helper route changed')

    page_refs = db.execute(
        "SELECT string_va,function_va,text FROM string_refs "
        "WHERE text IN ('WorkCraftBgPage','WorkCraftInfoPage','WorkCraftListPage') "
        'ORDER BY function_va,string_va').fetchall()
    page_functions = {row['text']: row['function_va'] for row in page_refs}
    require(page_functions.get('WorkCraftBgPage') == 0x1596020,
            'WorkCraftBgPage reference moved')
    bg_calls = direct_calls(db, 0x1596020)
    bg_decomp_path, bg_decomp = decomp('1596020')
    require('0x570' in bg_decomp and 'FUN_01ea8210' in bg_decomp
            and 'FUN_01244600' in bg_decomp,
            'WorkCraftBgPage initializer signature changed')

    result = {
        'scope': 'Static follow-up from cache check through recipe learning, craft inventory mutation, workbench UI and remake/customization source paths.',
        'labels': {
            'previous cold-cache material check': '[EXECUTED NATIVE; fixture reconstructed]',
            'Ftr_Working progression': '[EVENTFLOW]',
            'RecipeCraftParam/ItemParam/ItemRemake values': '[TBL]',
            'handler bodies and call chain': '[NATIVE STATIC: decompiler + direct-call index]',
            'unexecuted native paths and inferred semantics': '[OPEN / NOT EXECUTED]'
        },
        'provenance': {
            'analysis_elf_sha256': sha256(analysis_elf),
            'index_path': str(DB),
            'main_nso_sha256': previous['provenance']['main_nso_sha256'],
            'table_blob_sha256': {
                'RecipeCraftParam': previous['provenance']['recipe_table_raw_sha256'],
                'ItemParam': previous['provenance']['itemparam_raw_sha256'],
                'ItemKind': previous['provenance']['itemkind_raw_sha256'],
                'ItemRemake': table_blob_hash('ItemRemake', manifest)
            }
        },
        'previous_executed_slice': {
            'artifact': 'crafting_transaction_followup_native.json',
            'recipe_unique_id': 56,
            'output_item_id': 975,
            'cold_cache_scenarios': len(previous['scenarios']),
            'native_check': '0xee0be0 plus A/B/C loaders and producers',
            'limits': 'A/B/C source records were reconstructed fixtures; this did not run the UI transaction.'
        },
        'recipe_learning': {
            'status': 'EVENTFLOW_AND_NATIVE_STATIC_PROVEN; not executed against a real save',
            'unlock_type_enum': unlock_types,
            'tutorial_unlock_indices': {'DIYtutorial1': unlock_types.index('DIYtutorial1'),
                                        'DIYtutorial2': unlock_types.index('DIYtutorial2')},
            'events': learning_events,
            'handler': {
                'name': 'EventFlowActionPlayerSetCraftRecipe',
                'constructor': set_recipe_handler['constructor'],
                'behavior_va': '0x32dd30',
                'decomp': str(set_decomp_path),
                'direct_calls': set_recipe_calls,
                'claim': 'The action maps UnlockType against the native 46-entry enum, routes a group through 0xede0f0/0xedf590, and a valid ItemUniqueId through 0xedef00. The save helper 0xedf0e0 writes an indexed bit in the player save structure.'
            },
            'query': {
                'name': 'EventFlowQueryPlayerHasCraftRecipe',
                'constructor': has_recipe_query['constructor'],
                'behavior_va': '0x42ac80',
                'decomp': str(has_decomp_path),
                'direct_calls': has_recipe_calls,
                'claim': 'The query checks the requested item and UnlockType through save-state helpers; return polarity and a real save result were not dynamically verified.'
            }
        },
        'craft_transaction': {
            'status': 'NATIVE_STATIC_CHAIN_PROVEN; full transaction not executed',
            'save_type_enum': save_types,
            'events': craft_events,
            'save_set_handler': {
                'behavior_va': '0x334650',
                'cWorkCraft_case': save_types.index('cWorkCraft'),
                'helper_va': '0x3358c0',
                'calls': craft_save_calls
            },
            'transaction_helper': {
                'va': '0xee1420',
                'decomp': str(craft_decomp_path),
                'material_mutator_call_sites': calls_to(db, 0xee1420, 0xeff060),
                'inventory_delta_helper': {'va': '0xeff060', 'decomp': str(mutation_decomp_path),
                                           'calls': mutation_calls},
                'signed_quantity_helper': {'va': '0xf9e410', 'decomp': str(inventory_decomp_path),
                                           'behavior': 'negative delta subtracts from the matching item count and clamps below zero to zero'},
                'result_award_route': {
                    'calls_from_transaction': [c for c in craft_transaction_calls
                                               if int(c['target'], 16) in (0xefab90, 0xee17e0)],
                    'general_add': {'va': '0xefac20', 'decomp': str(item_add_decomp_path),
                                    'calls': [c for c in award_impl_calls if int(c['target'], 16) == 0xf987c0],
                                    'add_impl_va': '0xf987c0'},
                    'post_add_marker': {'va': '0xee17e0', 'decomp': str(craft_marker_decomp_path),
                                        'calls': [c for c in direct_calls(db, 0xee17e0)
                                                  if int(c['target'], 16) == 0xf29080],
                                        'semantic_mapping': 'bounded bit marker observed; equivalence to EventFlow MadeItemID was not proved'}
                },
            'claim': 'One conditional native branch contains six per-slot calls that pass negative material quantities to an inventory mutator, followed by a general item-add route and a bounded post-craft bit marker.'
            }
        },
        'workbench_page_and_remake': {
            'page_refs': {name: f'0x{va:x}' for name, va in page_functions.items()},
            'workcraft_bg_page': {
                'function_va': '0x1596020',
                'decomp': str(bg_decomp_path),
                'calls': bg_calls,
                'claim': 'This is a page-initialization path: it creates/configures the page and manager state. It does not establish transaction effects.'
            },
            'remake_item': {
                'tutorial_item_unique_id': 3436,
                'item_name_jp': column_value(remake_item_table, closet_row, 'ItemName'),
                'remake_id': remake_id,
                'kit_item_unique_id': 2513,
                'kit_item_name_jp': column_value(remake_item_table, kit_row, 'ItemName'),
                'kit_item_kind': column_value(remake_item_table, kit_row, 'ItemKind')['labels'][0],
                'table_cost': column_value(remake_table, remake_record, 'RemakeKitNum'),
                'remake_record_unique_id': column_value(remake_table, remake_record, 'UniqueID')
            },
            'events': remake_events,
            'save_set_handler': {
                'cWorkRemake_case': save_types.index('cWorkRemake'),
                'helper_va': '0x335d10',
                'calls': remake_save_calls,
                'dispatch_decomp': str(save_type_dispatch_path),
                'inventory_update_decomp': str(remake_update_path),
                'kit_quantity_argument_disassembly': remake_kit_arg_disasm,
                'claim': 'The tutorial grants 50 Remake Kits and selects Remake for item 3436. SaveSetFromUIResult builds item 2513 and passes a quantity loaded from context+0x14 through 0xefbdf0 to 0xf99b10, whose native code changes inventory quantity. The ItemRemake row says item 3436 costs two kits, but this row-to-context mapping was not run in the game.'
            }
        },
        'status_by_slice': {
            'cold_cache_and_required_material_check': 'PROVEN EXECUTED NATIVE on reconstructed fixture',
            'tutorial_recipe_unlock_and_query': 'PROVEN EVENTFLOW + NATIVE STATIC; save mutation not executed',
            'pocket material gate in transaction helper': 'PROVEN STATIC; not same execution as cold-cache helper',
            'ingredient consumption and result add': 'PROVEN NATIVE STATIC call chain; not executed end to end',
            'workbench UI page': 'PROVEN PAGE INITIALIZER; user interaction not executed',
            'customization/remake': 'PROVEN EVENTFLOW + TABLE COST + NATIVE KIT INVENTORY UPDATE; row-to-quantity mapping open',
            'cancel_or_rollback': 'OPEN; no rollback behavior established'
        },
        'open_limits': [
            'The previous cache fixture is reconstructed; it is not a supplied player save.',
            'No real save/player/UI runtime was available, so recipe learn state, pocket precheck, material subtraction, result item insertion, and remake were not executed end to end.',
            'The native craft call order is visible in decompilation; atomicity and rollback on interruption/failure remain unproved.',
            'The WorkCraftBgPage function is a page initializer, not proof that the page itself commits a transaction.',
            'The remake handler passes a context-derived quantity for item 2513 into an inventory update, but the mapping from ItemRemake.RemakeKitNum=2 for item 3436 to that quantity was not executed in the game.',
            'The post-craft bitmap helper accepts only keys below 0x800; its relation to EventFlow MadeItemID values such as 7211 was not established.'
        ]
    }
    db.close()
    return result


def main():
    report = build_report()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    path = OUTPUT / 'crafting_transaction_followup_static.json'
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n')
    print(path)


if __name__ == '__main__':
    main()
