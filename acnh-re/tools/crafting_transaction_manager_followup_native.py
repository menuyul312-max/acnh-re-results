"""Bounded native follow-up for recipe 56 material dispatch and manager gates.

The supplied ItemParam, ItemKind, and ItemOutfitInfo BCSV tables are installed
in a Unicorn memory sandbox. Original helper code runs against synthetic player
and pocket records; no live save or game process is read or written.
"""
from pathlib import Path
import os
import hashlib
import json
import struct
import sys

TOOLS = Path(__file__).resolve().parent
REPO = TOOLS.parent
REPOSITORY_ROOT = REPO.parent
SOURCE_ROOT = Path(os.environ.get('ACNH_SOURCE_ROOT', REPOSITORY_ROOT.parent / 'acnh-re')).resolve()
if not (SOURCE_ROOT / 'output' / 'tables_resolved' / 'ItemParam.json').is_file() and 'ACNH_SOURCE_ROOT' not in os.environ:
    SOURCE_ROOT = REPO
if not (SOURCE_ROOT / 'output' / 'tables_resolved' / 'ItemParam.json').is_file():
    raise FileNotFoundError(
        'Resolved source tables are missing; set ACNH_SOURCE_ROOT to the local ACNH RE source dataset'
    )
DEPS = Path(os.environ.get('ACNH_DEPS_PATH', SOURCE_ROOT / '.deps')).resolve()
OUT = REPO / 'output' / 'gameplay' / 'crafting_transaction_manager_followup_20261107.json'

sys.path.insert(0, str(DEPS))
sys.path.insert(0, str(TOOLS))

from unicorn import UC_HOOK_CODE, UC_HOOK_MEM_READ_UNMAPPED, UC_HOOK_MEM_WRITE, UC_HOOK_MEM_WRITE_UNMAPPED  # noqa: E402
from native_emulator import Sandbox, regs  # noqa: E402
import inventory_requirements_native as item_tables  # noqa: E402
import crafting_pocket_manager_probe as pocket_probe  # noqa: E402

item_tables.ROOT = SOURCE_ROOT
DATA = SOURCE_ROOT / 'output'
SENTINEL = 0xfffe


def sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def load_table(name):
    table = json.loads((DATA / 'tables_resolved' / f'{name}.json').read_text())
    manifest = json.loads((DATA / 'manifest.json').read_text())
    entry = manifest['entries'][table['source_id']]
    decoded = json.loads((DATA / entry['decoded']).read_text())['data']
    raw = (DATA / table['raw']['$blob']).read_bytes()
    return table, decoded, raw


def install_outfit_info_manager(s, item_table):
    """Bind the field manager/cache consumed by 0xa9e440 -> 0xa774c0/0xab9400."""
    u = s.uc
    ip, _ip_decoded, _ip_raw = load_table('ItemParam')
    outfit, decoded, raw = load_table('ItemOutfitInfo')
    ic = {column['name']: index for index, column in enumerate(ip['columns'])}
    oc = {column['name']: index for index, column in enumerate(outfit['columns'])}

    base = 0x51f00000
    manager = 0x51602000
    row_array = 0x51740000
    item_outfit_index = 0x51750000
    item_outfit_meta = 0x500e0000
    u.mem_write(base, raw)
    u.mem_write(manager + 0x1b0, struct.pack('<I', len(outfit['rows'])))
    u.mem_write(manager + 0x1c0, struct.pack('<I', len(outfit['rows'])))
    u.mem_write(manager + 0x1b8, struct.pack('<Q', row_array))
    for index in range(len(outfit['rows'])):
        row_pointer = base + decoded['data_start'] + index * outfit['row_size']
        u.mem_write(row_array + index * 8, struct.pack('<Q', row_pointer))

    outfit_index_by_label = {
        row[oc['Label']]: index for index, row in enumerate(outfit['rows'])
    }
    item_to_outfit_indices = []
    unresolved = []
    for row_index, row in enumerate(ip['rows']):
        reference = row[ic['ItemOutfitInfo']]
        labels = reference.get('labels', []) if isinstance(reference, dict) else []
        matches = [outfit_index_by_label[label]
                   for label in labels if label in outfit_index_by_label]
        if len(matches) != 1:
            unresolved.append({'itemparam_row_index': row_index,
                               'item_id': row[ic['UniqueID']],
                               'item_label': row[ic['Label']],
                               'reference': reference,
                               'match_count': len(matches)})
            item_to_outfit_indices.append(0)
        else:
            item_to_outfit_indices.append(matches[0])

    u.mem_write(item_outfit_meta, struct.pack('<I', len(ip['rows'])))
    u.mem_write(item_outfit_meta + 8, struct.pack('<Q', item_outfit_index))
    for index, value in enumerate(item_to_outfit_indices):
        u.mem_write(item_outfit_index + index * 2, struct.pack('<H', value))

    recipe_table, _recipe_row, recipe_materials = recipe56_materials()
    item_by_uid = {row[ic['UniqueID']]: (index, row)
                   for index, row in enumerate(ip['rows'])}
    material_references = []
    for material in recipe_materials:
        if material['item_id'] == SENTINEL:
            continue
        item_index, item_row = item_by_uid[material['item_id']]
        outfit_index = item_to_outfit_indices[item_index]
        material_references.append({
            'item_id': material['item_id'],
            'item_label': item_row[ic['Label']],
            'ItemParam_row_index': item_index,
            'ItemParam_ItemOutfitInfo': item_row[ic['ItemOutfitInfo']],
            'ItemOutfitInfo_row_index': outfit_index,
            'ItemOutfitInfo_label': outfit['rows'][outfit_index][oc['Label']],
            'Storage_raw_u16': outfit['rows'][outfit_index][oc['Storage']],
        })

    # These globals are separate from the ItemParam/ItemKind tables installed
    # by inventory_requirements_native.install_item_tables.
    u.mem_write(s.image.ptr(0x32f3f78), struct.pack('<Q', manager))
    u.mem_write(s.image.ptr(0x32f0a98), struct.pack('<Q', item_outfit_meta))
    u.mem_write(s.image.ptr(0x32f0530), b'\x01')
    offsets = s.image.ptr(0x32f0538)
    for index, column in enumerate(outfit['columns']):
        u.mem_write(offsets + index * 4, struct.pack('<I', column['offset']))

    return {
        'ItemOutfitInfo_raw_sha256': hashlib.sha256(raw).hexdigest(),
        'manager_va': hex(manager),
        'manager_row_order': 'ItemOutfitInfo source row order; ItemParam.ItemOutfitInfo labels are converted to these row ordinals',
        'manager_count_at_plus_0x1b0_and_plus_0x1c0': len(outfit['rows']),
        'ItemParam_to_ItemOutfitInfo_cache_count': len(item_to_outfit_indices),
        'ItemParam_to_ItemOutfitInfo_unresolved_refs': len(unresolved),
        'itemoutfitinfo_field_hash': '0xc89fb7af',
        'itemoutfitinfo_field_name_type_offset': 'Storage raw data u16 at offset 142',
        'itemoutfitinfo_offset_cache_global': '0x32f0538',
        'ItemParam_ItemOutfitInfo_index_cache_global': '0x32f0a98',
        'manager_global': '0x32f3f78',
        'apple_reference': {
            'ItemParam_ItemOutfitInfo': ip['rows'][next(
                i for i, row in enumerate(ip['rows'])
                if row[ic['UniqueID']] == 2213)][ic['ItemOutfitInfo']],
            'ItemOutfitInfo_row_index': item_to_outfit_indices[next(
                i for i, row in enumerate(ip['rows'])
                if row[ic['UniqueID']] == 2213)],
            'ItemOutfitInfo_label': outfit['rows'][item_to_outfit_indices[next(
                i for i, row in enumerate(ip['rows'])
                if row[ic['UniqueID']] == 2213)]][oc['Label']],
            'Storage_value': outfit['rows'][item_to_outfit_indices[next(
                i for i, row in enumerate(ip['rows'])
                if row[ic['UniqueID']] == 2213)]][oc['Storage']],
        },
        'recipe56_material_references': material_references,
        'unresolved_samples': unresolved[:4],
    }


def recipe56_materials():
    recipe, _decoded, _raw = load_table('RecipeCraftParam')
    columns = {column['name']: index for index, column in enumerate(recipe['columns'])}
    row = next(row for row in recipe['rows'] if row[columns['UniqueID']] == 56)
    materials = [{'slot': slot, 'item_id': row[columns[f'Material{slot + 1}']],
                  'amount': row[columns[f'Amount{slot + 1}']]}
                 for slot in range(6)]
    return recipe, row, materials


def run_case(material_slot):
    s = Sandbox()
    u = s.uc
    item_info = item_tables.install_item_tables(s)
    outfit_info = install_outfit_info_manager(s, item_info)
    fixture = pocket_probe.initialize_manager_fixture(s, None, 2213)
    addresses = fixture['_addresses']
    context = addresses['mode_context']
    pocket = addresses['pocket_record']
    recipe_table, recipe_row, materials = recipe56_materials()
    selected = materials[material_slot]
    if selected['item_id'] == SENTINEL:
        raise ValueError('the probe slot must contain a real recipe-56 material')

    payload = s.HEAP + 0x1c0000
    u.mem_write(payload, bytes(0x120))
    u.mem_write(payload, struct.pack('<H', 56))
    u.mem_write(payload + 8, struct.pack('<HHI', recipe_row[
        next(i for i, column in enumerate(recipe_table['columns'])
             if column['name'] == 'Item')], 0, 0))
    u.mem_write(payload + 0x25, b'\x01')
    for material in materials:
        entry = payload + 0x2c + material['slot'] * 0x14
        u.mem_write(entry, struct.pack('<HHI', material['item_id'], 0, 0))
        u.mem_write(entry + 8, struct.pack('<H', material['amount']))

    # One synthetic pocket word per required material. FreeParam is zero, but
    # its unit-count meaning is not assumed: the native counter groups/cache
    # that feed material counts are not installed by this fixture.
    empty = struct.pack('<HHI', SENTINEL, 0, 0)
    pocket_items = [struct.pack('<HHI', material['item_id'], 0, 0)
                    if material['amount'] else empty for material in materials]
    pocket_items += [empty] * (20 - len(pocket_items))
    u.mem_write(pocket + 0xb8, b''.join(pocket_items))
    u.mem_write(pocket + 0x158, struct.pack('<I', sum(
        bool(material['amount']) for material in materials)))
    u.mem_write(pocket + 0x15c, bytes(20))

    scratch = context + 0x2a550
    pointer_array = s.HEAP + 0x1d0000
    node_array = s.HEAP + 0x1d1000
    u.mem_write(scratch, struct.pack('<IIQQ', 0, 20, pointer_array, node_array))
    for index in range(20):
        next_node = node_array + (index + 1) * 8 if index + 1 < 20 else 0
        u.mem_write(node_array + index * 8, struct.pack('<Q', next_node))

    watched = {
        0xee1060, 0xe89170, 0xa9f140, 0xa9e440, 0xa774c0, 0xab9400,
        0xf97da0, 0xefc2f0, 0xefbec0, 0xefbf80, 0xefe340,
        0xf98570, 0xaa7ce0,
        0xf99fe0, 0xf99e40, 0xf98650, 0xee1880,
        0xeda900, 0xf97d50, 0xf97d60,
        0xee1100, 0xee1104, 0xee1140, 0xee1148, 0xee114c,
        0xee12d8, 0xee12e8, 0xee138c, 0xee1390, 0xee1398,
        0xee13a0, 0xee13a4, 0xee13a8, 0xee13ac, 0xee13b0,
    }
    trace = []
    branch_trace = []
    helper_returns = []
    pending_returns = {}
    faults = []
    writes = []
    last_pcs = []

    def code_hook(uc, address, _size, _user_data):
        last_pcs.append(f'0x{address:x}')
        if len(last_pcs) > 100:
            del last_pcs[0]
        if 0xee12c0 <= address <= 0xee13f0:
            branch_trace.append({
                'va': f'0x{address:x}',
                'x0_x5': [f'0x{uc.reg_read(getattr(regs, f"UC_ARM64_REG_X{i}")):x}'
                          for i in range(6)],
            })
        for pending in pending_returns.get(address, []):
            if 'return_x0' not in pending:
                pending['return_x0'] = f'0x{uc.reg_read(regs.UC_ARM64_REG_X0):x}'
        if address in watched:
            trace.append({
                'va': f'0x{address:x}',
                'x0_x5': [f'0x{uc.reg_read(getattr(regs, f"UC_ARM64_REG_X{i}")):x}'
                          for i in range(6)],
            })
            if address in {0xa9f140, 0xeda900, 0xf97d50, 0xf97d60}:
                pending = {
                    'helper_va': f'0x{address:x}',
                    'return_va': f'0x{uc.reg_read(regs.UC_ARM64_REG_X30):x}',
                }
                helper_returns.append(pending)
                pending_returns.setdefault(
                    int(pending['return_va'], 16), []).append(pending)

    def unmapped_hook(uc, _access, address, size, _value, _user_data):
        faults.append({
            'pc': f'0x{uc.reg_read(regs.UC_ARM64_REG_PC):x}',
            'address': f'0x{address:x}', 'size': size,
            'recent_pcs': last_pcs[-20:],
        })
        return False

    def write_hook(uc, _access, address, size, value, _user_data):
        if pocket <= address < pocket + 0x17c:
            writes.append({
                'pc': f'0x{uc.reg_read(regs.UC_ARM64_REG_PC):x}',
                'offset': f'0x{address - pocket:x}',
                'size': size, 'value': f'0x{value:x}',
            })

    u.hook_add(UC_HOOK_CODE, code_hook)
    u.hook_add(UC_HOOK_MEM_READ_UNMAPPED, unmapped_hook)
    u.hook_add(UC_HOOK_MEM_WRITE_UNMAPPED, unmapped_hook)
    u.hook_add(UC_HOOK_MEM_WRITE, write_hook)
    before = bytes(u.mem_read(pocket, 0x17c))
    error = None
    native_return = None
    try:
        native_return = s.call(0xee1060,
                               (context, payload, context, material_slot, 0, 0),
                               limit=3_000_000)
    except Exception as exc:
        error = f'{type(exc).__name__}: {exc}'
    after = bytes(u.mem_read(pocket, 0x17c))
    outfit_reference = next(
        reference for reference in outfit_info['recipe56_material_references']
        if reference['item_id'] == selected['item_id'])
    storage_predicate = next((row.get('return_x0') for row in helper_returns
                              if row['helper_va'] == '0xa9f140'), None)

    return {
        'entry': '0xee1060',
        'material': selected,
        'pocket_before_first_six': [
            list(struct.unpack('<HHI', before[0xb8 + i * 8:0xc0 + i * 8]))
            for i in range(6)],
        'pocket_after_first_eight': [
            list(struct.unpack('<HHI', after[0xb8 + i * 8:0xc0 + i * 8]))
            for i in range(8)],
        'dirty_marker_bytes_before': list(before[0x15c:0x170]),
        'dirty_marker_bytes_after': list(after[0x15c:0x170]),
        'changed_pocket_offsets': [f'0x{index:x}' for index, (old, new)
                                   in enumerate(zip(before, after)) if old != new],
        'pocket_write_events': writes,
        'native_return': native_return,
        'native_error': error,
        'native_0xa9f140_Storage_query_return': storage_predicate,
        'ItemOutfitInfo_material_reference': outfit_reference,
        'unmapped_accesses': faults,
        'trace': trace,
        'branch_trace': branch_trace,
        'helper_return_values': helper_returns,
        'table_setup': {
            'ItemParam_raw_sha256': item_info['item_raw_sha256'],
            'ItemKind_raw_sha256': item_info['kind_raw_sha256'],
            'ItemOutfitInfo_raw_sha256': outfit_info['ItemOutfitInfo_raw_sha256'],
            'ItemParam_to_ItemOutfitInfo_for_recipe56_materials':
                outfit_info['recipe56_material_references'],
        },
        'fixture_limits': fixture['limits'],
    }


def run_save_count_gate():
    s = Sandbox()
    u = s.uc
    tables = item_tables.install_item_tables(s)
    ip = tables['item_table']
    ic = tables['item_cols']
    kind = tables['kind_table']
    kc = tables['kind_cols']
    item = next(row for row in ip['rows'] if row[ic['UniqueID']] == 2213)
    item_row_index = next(index for index, row in enumerate(ip['rows'])
                          if row[ic['UniqueID']] == 2213)
    descriptor = s.HEAP + 0x10000
    item_object = s.HEAP + 0x11000
    slots = s.HEAP + 0x12000
    u.mem_write(descriptor, struct.pack('<HHI', 2213, 0, 0))
    u.mem_write(item_object, bytes(0x40))
    s.call(0xa9c290, (item_object, descriptor), limit=50_000)
    row_pointer = struct.unpack('<Q', u.mem_read(item_object + 0x10, 8))[0]
    row_index = s.call(0x1665ea0, (row_pointer,), limit=20_000)
    field_value = s.call(0xaac730, (item_object,), limit=100_000)
    predicate = s.call(0xaac910, (item_object,), limit=100_000)
    u.mem_write(slots, b''.join(struct.pack('<HHI', 2213 if i == 0 else SENTINEL, 0, 0)
                                for i in range(32)))
    before = bytes(u.mem_read(slots, 0x110))
    s.call(0xf9e410, (slots, descriptor, -1), limit=300_000)
    after = bytes(u.mem_read(slots, 0x110))
    kind_row = next(row for row in kind['rows']
                    if row[kc['UniqueID']] == 51 and row[kc['Label']] == 'Fruit')
    return {
        'ItemParam_Apple_row_index': item_row_index,
        'ItemParam_Apple_row_pointer_in_item_object_plus_0x10': hex(row_pointer),
        'native_0x1665ea0_dense_index': row_index,
        'native_0xaac730_SaveCountMaxNum_value': field_value,
        'native_0xaac910_nonzero_predicate': predicate,
        'ItemKind_Fruit': {
            'UniqueID': kind_row[kc['UniqueID']],
            'Label': kind_row[kc['Label']],
            'MultiHoldMaxNum': kind_row[kc['MultiHoldMaxNum']],
            'SaveCountMaxNum': kind_row[kc['SaveCountMaxNum']],
        },
        'field_source': {
            'schema': 'CylindricalEarth/specs_100.py ItemKind.SaveCountMaxNum',
            'hash': '0x0ce69142', 'type': 'u16', 'offset': 26,
            'raw_table': 'B_data/Bcsv/ItemKind.bcsv',
            'raw_sha256': tables['kind_raw_sha256'],
        },
        'native_callsite_contract': {
            '0xaac730_reads_ItemParam_object_plus_0x10_and_calls_0x1665ea0': True,
            '0xaac730_uses_dense_index_to_ItemParam_to_ItemKind_ordinal_cache': True,
            '0xaac910_returns_one_when_0xaac730_nonzero': True,
            '0xf9e840_callsite': '0xf9e874 then tbz w0,#0 to return 0 at 0xf9ebf8 when the predicate is zero',
            '0xf9e410_callsite': '0xf9e430; the return-zero branch at 0xf9e434 skips all slot scans/count writes',
            'tested_f9e410_delta': -1,
            'f9e410_pocket_fixture_bytes_unchanged': before == after,
        },
        'scope_limit': 'This proves only the SaveCountMaxNum predicate and early return in the generic signed count-update helper for this reconstructed Apple object. It does not prove Apple crafting is rejected or that this is the recipe-56 default path.',
    }


def main():
    recipe, row, materials = recipe56_materials()
    recipe_cols = {column['name']: index for index, column in enumerate(recipe['columns'])}
    item_table, _decoded, _raw = load_table('ItemParam')
    item_cols = {column['name']: index for index, column in enumerate(item_table['columns'])}
    kind_table, _kind_decoded, _kind_raw = load_table('ItemKind')
    kind_cols = {column['name']: index for index, column in enumerate(kind_table['columns'])}
    kind_by_label = {entry[kind_cols['Label']]: entry for entry in kind_table['rows']}
    material_item_kinds = []
    for material in materials:
        if material['item_id'] == SENTINEL:
            continue
        item_row = next(entry for entry in item_table['rows']
                        if entry[item_cols['UniqueID']] == material['item_id'])
        kind_label = item_row[item_cols['ItemKind']]['labels'][0]
        kind_row = kind_by_label[kind_label]
        material_item_kinds.append({
            'item_id': material['item_id'], 'item_label': item_row[item_cols['Label']],
            'item_kind': kind_label, 'multi_hold_max_num': kind_row[kind_cols['MultiHoldMaxNum']],
            'save_count_max_num': kind_row[kind_cols['SaveCountMaxNum']],
            'required_amount': material['amount'], 'fixture_free_param': 0,
            'fixture_pocket_records': 1,
            'fixture_count_context': 'not initialized; no native unit-count value inferred',
        })
    cases = [run_case(slot) for slot, material in enumerate(materials)
             if material['item_id'] != SENTINEL]
    manifest = json.loads((DATA / 'manifest.json').read_text())
    elf = Path(manifest['source_root']) / 'A_logic' / 'main.elf'
    result = {
        'schema': 'acnh.crafting_transaction_manager_followup_native.v1',
        'evidence_status': 'BOUNDED_NATIVE_EXECUTION_WITH_RECONSTRUCTED_TABLE_AND_PLAYER_FIXTURES',
        'provenance': {
            'analysis_elf_sha256': sha256(elf),
            'main_nso_sha256': sha256(REPO / 'inputs' / 'additional_exefs' / 'main'),
            'recipe_table_raw_sha256': recipe['raw']['sha256'],
            'recipe_id': 56,
            'recipe_result_item_id': row[recipe_cols['Item']],
            'recipe_materials': materials,
        },
        'correction_to_earlier_row_pointer_hypothesis': {
            'supersedes': 'CRAFTING_TRANSACTION_REMAINDER_20261107.md claim that 0xaac730 compared the raw ItemParam row pointer against the dense row count',
            'correct_flow': '0xa9c290 stores the ItemParam BCSV row pointer at ItemParam-object+0x10; 0xaac730 passes that pointer through 0x1665ea0, receives dense ItemParam row index 495 for Apple, then indexes the ItemParam->ItemKind ordinal cache.',
            'clean_install_setup': 'inventory_requirements_native.install_item_tables installs the raw ItemParam and ItemKind BCSV blobs, ItemParam UniqueID dense-pointer array, ItemKind row-pointer array, kind-ordinal mapping, metadata offsets, and native table-manager globals.',
            'native_result': run_save_count_gate(),
        },
        'source_item_count_semantics': {
            'Fruit_ItemKind_row': 'UniqueID=51, Label=Fruit',
            'MultiHoldMaxNum': 's16 offset 24; source value 10 for Fruit and the stack-limit field used by the separately proven inventory counter producer.',
            'SaveCountMaxNum': 'u16 offset 26, descriptor hash 0x0ce69142; source value 0 for Fruit. This is the field read by 0xaac730 in the specific 0xf9e840/0xf9e410 count-update path, not the Fruit stack-limit field.',
            'Apple_ItemParam_ItemOutfitInfo': 'None -> ItemOutfitInfo row ordinal 30 (source Storage raw data u16=0); the source schema does not assign a stronger Storage interpretation. This separate row manager is required by 0xa9e440/0xa9f140.',
            'ItemOutfitInfo_Storage_scope': 'The native 0xa9f140 lookup is reached by 0xee1060 and reads this distinct field; no source or test here equates it with stack count, SaveCountMaxNum, or ingredient rejection.',
        },
        'native_default_material_branch': {
            '0xee1420_default_selector': 'param2+0x3c == 0 -> calls 0xee1060 for slots 0..5 with param5=0 and param6=null.',
            'alternate_selector': 'param2+0x3c != 0 selects six per-material 0xeff060 branches only for slots whose amount is nonzero; each material record +0x10 marker also controls whether that slot is routed to 0xeff060.',
            'verified_branch_context': 'The previous 0xee1420 branch probe used a synthetic +0x38 guard and varied +0x3c to select the two paths. Its material mutators were stubbed; it did not establish the payload builder’s real marker values. This follow-up calls original 0xee1060 directly with its default-mode argument tuple and the reconstructed ItemOutfitInfo manager; it returns 1, while the synthetic pocket bytes remain unchanged.',
        },
        'itemoutfit_manager_setup': install_outfit_info_manager_metadata(),
        'direct_ee1060_recipe56_material_cases': cases,
        'material_item_kinds_and_true_counts': material_item_kinds,
        'transaction_and_save_limits': [
            '0xee1060 was called directly per actual RecipeCraftParam.UniqueID=56 material, with one native-form item record for each fruit stack; this is not the full 0xee1420 transaction or the UI payload builder.',
            'The partial player/pocket resolver uses synthetic manager/member records and two success-return virtual view stubs from crafting_pocket_manager_probe.initialize_manager_fixture. One item word per source material is present, but the native A/B/C inventory counter/cache context and its source-record producers are not initialized, so this is not a true count fixture.',
            'No real save was loaded, changed, serialized, or flushed. Recipe-56 result insertion, cancellation, rollback/refund, and durable SaveProc effects remain open.',
            'A successful 0xee1060 return alone is not treated as proof of material consumption; only changed synthetic pocket bytes would establish fixture mutation.',
            'The 0xeff060 SaveCountMaxNum probe is an alternate helper branch and cannot be generalized to in-game Apple material rejection.',
        ],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps({'output': str(OUT), 'material_cases': len(cases),
                      'apple_dense_index': result['correction_to_earlier_row_pointer_hypothesis']['native_result']['native_0x1665ea0_dense_index'],
                      'mutation_cases': sum(bool(case['changed_pocket_offsets']) for case in cases),
                      'native_errors': [case['native_error'] for case in cases if case['native_error']]}, indent=2))


def install_outfit_info_manager_metadata():
    table, _decoded, _raw = load_table('ItemOutfitInfo')
    ip, _ip_decoded, _ip_raw = load_table('ItemParam')
    recipe, _recipe_row, materials = recipe56_materials()
    outfit_cols = {column['name']: index for index, column in enumerate(table['columns'])}
    item_cols = {column['name']: index for index, column in enumerate(ip['columns'])}
    outfit_index_by_label = {
        row[outfit_cols['Label']]: index for index, row in enumerate(table['rows'])
    }
    item_by_uid = {row[item_cols['UniqueID']]: row for row in ip['rows']}
    material_refs = []
    for material in materials:
        if material['item_id'] == SENTINEL:
            continue
        item_row = item_by_uid[material['item_id']]
        labels = item_row[item_cols['ItemOutfitInfo']].get('labels', [])
        outfit_index = outfit_index_by_label[labels[0]]
        outfit_row = table['rows'][outfit_index]
        material_refs.append({
            'item_id': material['item_id'],
            'item_label': item_row[item_cols['Label']],
            'ItemParam_ItemOutfitInfo': item_row[item_cols['ItemOutfitInfo']],
            'ItemOutfitInfo_row_index': outfit_index,
            'ItemOutfitInfo_label': outfit_row[outfit_cols['Label']],
            'Storage_raw_u16': outfit_row[outfit_cols['Storage']],
        })
    return {
        'source': table['source'],
        'source_id': table['source_id'],
        'row_count': table['row_count'],
        'row_size': table['row_size'],
        'raw_sha256': table['raw']['sha256'],
        'manager_contract': '0xa9e440 -> 0xa774c0 reads row count +0x1c0 and row-pointer array +0x1b8; 0xab9400 resolves ItemOutfitInfo.Storage by hash 0xc89fb7af.',
        'itemparam_reference_contract': 'ItemParam.ItemOutfitInfo resolves to ItemOutfitInfo.Label row ordinal; dense per-ItemParam-row ordinals are installed at 0x32f0a98.',
        'Storage_field_source': 'CylindricalEarth/specs_100.py declares ItemOutfitInfo.Storage as RawData(hash 0xc89fb7af, width 2); no stronger semantic interpretation is assigned here.',
        'ItemParam_row_count': ip['row_count'],
        'recipe56_material_references': material_refs,
        'dependencies_stubbed_in_material_call': [
            'Two view-service virtual methods in the existing partial player/pocket fixture return success.',
        ],
    }


if __name__ == '__main__':
    main()
