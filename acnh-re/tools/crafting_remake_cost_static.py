"""Trace remake-kit table cost into the cWorkRemake save-result field.

This is a read-only cross-check over the supplied main ELF, native call index,
EventFlow index and resolved ItemParam/ItemRemake tables. It does not execute a
game save transaction.
"""
from pathlib import Path
import hashlib
import json
import sqlite3
import sys

TOOLS = Path(__file__).resolve().parent
REPO = TOOLS.parent
SHARED = Path('/workspace/acnh-re')
DB = SHARED / 'output' / 'index.sqlite'
TABLES = SHARED / 'output' / 'tables_resolved'
MANIFEST = SHARED / 'output' / 'manifest.json'
OUT = REPO / 'output' / 'gameplay' / 'crafting_transaction_remainder'

sys.path.insert(0, str(SHARED / '.deps'))
sys.path.insert(0, str(TOOLS))
# This checkout omits generated outputs, so native_image must use the shared
# read-only manifest and ELF tree while the report is still written locally.
sys.path.insert(0, str(SHARED / 'tools'))
from native_image import Image  # noqa: E402
from gameplay_flow import render_tree  # noqa: E402


def sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def table(name):
    return json.loads((TABLES / f'{name}.json').read_text())


def row_by(data, key, value):
    index = next(i for i, column in enumerate(data['columns'])
                 if column['name'] == key)
    return next(row for row in data['rows'] if row[index] == value)


def value(data, row, key):
    index = next(i for i, column in enumerate(data['columns'])
                 if column['name'] == key)
    return row[index]


def raw_table_hash(data):
    return sha256(SHARED / 'output' / data['raw']['$blob'])


def main():
    assert DB.is_file(), f'missing native index: {DB}'
    assert (TABLES / 'ItemParam.json').is_file()
    assert (TABLES / 'ItemRemake.json').is_file()
    image = Image()
    db = sqlite3.connect(f'file:{DB}?mode=ro', uri=True)
    db.row_factory = sqlite3.Row

    def ins(address):
        found = image.disasm(address, 4)
        assert found and found[0].address == address, f'missing instruction {address:#x}'
        return found[0]

    def target(address):
        item = ins(address)
        assert item.mnemonic == 'bl', (hex(address), item.mnemonic, item.op_str)
        return item.operands[0].imm

    item_param = table('ItemParam')
    item_remake = table('ItemRemake')
    item_kind = table('ItemKind')
    item = row_by(item_param, 'UniqueID', 3436)
    remake_id = value(item_param, item, 'RemakeID')
    remake = row_by(item_remake, 'UniqueID', remake_id)
    kit_count = value(item_remake, remake, 'RemakeKitNum')
    kit_item = row_by(item_param, 'UniqueID', 2513)
    phone_case_kind = row_by(item_kind, 'Label', 'CraftPhoneCase')
    phone_case_kind_ordinal = item_kind['rows'].index(phone_case_kind)
    target_item_kind = value(item_param, item, 'ItemKind')
    remake_field = next(column for column in item_remake['columns']
                        if column['name'] == 'RemakeKitNum')
    remake_values = [value(item_remake, row, 'RemakeKitNum')
                     for row in item_remake['rows']]

    # Native RemakeKitNum row resolver: literal hash, then a byte load from the
    # resolved table field. The table schema stores a u16; this build's 654
    # values all fit in that low byte.
    assert ins(0xab2400).mnemonic == 'mov' and ins(0xab2400).operands[1].imm == 0xb129
    assert ins(0xab2404).mnemonic == 'movk' and ins(0xab2404).operands[1].imm == 0x29ec
    assert ins(0xab24e4).mnemonic == 'ldrb'
    assert ins(0xab24e4).op_str == 'w0, [x8]'

    # The workbench state builder calls the native row reader and saves its
    # return into state+0x1928. Its result publisher copies that field into the
    # shared UI-result structure's +0x14 field (manager +0x5c).
    assert target(0x15ad2cc) == 0xab2330
    assert ins(0x15ad2d4).mnemonic == 'str'
    assert ins(0x15ad2d4).op_str == 'w0, [x19]'
    assert ins(0x15ad088).op_str == 'w8, #0x1928'
    assert ins(0x15ad08c).op_str == 'x22, x0, x8'
    assert ins(0x15ad0a4).mnemonic == 'bl'
    assert target(0x15ad2ac) == 0x15806f0
    assert ins(0x15ad2b8).mnemonic == 'orr'
    assert ins(0x15ad2b8).operands[2].imm == 0x10
    assert ins(0x15ad2c8).op_str == 'w8, [x19, #0x1c]'
    assert ins(0x15806f0).op_str == 'w1, #0x38'
    assert ins(0x15806f4).mnemonic == 'b'
    assert ins(0x15806f4).operands[0].imm == 0xa9cb60
    assert ins(0x15ae9b8).mnemonic == 'tbnz'
    assert ins(0x15ae9b8).operands[1].imm == 4
    assert ins(0x15aeacc).mnemonic == 'tbnz'
    assert ins(0x15aeacc).operands[1].imm == 4
    assert target(0x15aeaf4) == 0x154a640
    assert target(0x15aea7c) == 0x154a670
    assert ins(0x15aeab4).op_str == 'x8, [x20, #0x14]'
    assert ins(0x15aeaf0).op_str == 'w8, [sp, #0x14]'
    assert ins(0x15aeae0).op_str == 'w8, wzr'

    # Native setter copies payload+0x14 into manager+0x5c. The getter returns
    # manager+0x48, so its +0x14 read is the same word.
    assert ins(0x154a668).mnemonic == 'b'
    assert ins(0x154a668).operands[0].imm == 0x1546070
    assert ins(0x154a690).mnemonic == 'b'
    assert ins(0x154a690).operands[0].imm == 0x1546020
    assert ins(0x1546070 + 0xa0).mnemonic == 'ldr'
    assert ins(0x1546070 + 0xa0).op_str == 'w8, [x19, #0x14]'
    assert ins(0x1546070 + 0xa4).op_str == 'w8, [x20, #0x5c]'
    assert ins(0x1546020 + 0x44).op_str == 'x0, x19'
    assert ins(0x1546020 + 0x14).op_str == 'x19, x0, #0x48'

    # SaveSetFromUIResult's remake case reads that same +0x14 word and passes
    # it as the quantity for item 2513 into the inventory update helper.
    assert target(0x335d34) == 0x154a670
    assert ins(0x335d54).op_str == 'w21, [x19, #0x14]'
    assert ins(0x335d5c).op_str == 'w21, #1'
    assert ins(0x335d64).op_str == 'w1, #0x9d1'
    assert ins(0x335d78).op_str == 'w2, w21'
    assert target(0x335d7c) == 0xefbdf0
    assert ins(0x335d80).mnemonic == 'mov'
    assert ins(0x335d80).op_str == 'w0, #1'
    assert ins(0x335dd4).op_str == 'w8, [x19, #0x18]'
    assert ins(0x335dd8).op_str == 'w8, #1'
    assert ins(0x335ddc).mnemonic == 'b.ne'
    assert ins(0x335ddc).operands[0].imm == 0x335f00
    assert target(0x335f14) == 0xefb1f0
    assert ins(0x335efc).mnemonic == 'b'
    assert ins(0x335efc).operands[0].imm == 0x335f18
    assert target(0x33603c) == 0x154a640
    assert target(0xefbe8c) == 0xf99b10

    span = db.execute('SELECT size FROM native_functions WHERE va=?', (0x335d10,)).fetchone()
    assert span is not None
    call_targets = [target for (target,) in db.execute(
        'SELECT target_va FROM direct_calls WHERE pc>=? AND pc<? ORDER BY pc',
        (0x335d10, 0x335d10 + span['size']))]
    assert call_targets.count(0xefbdf0) == 1
    assert call_targets.count(0xefb1f0) == 1

    # Preserve the selected-item result path and the explicit normal-remake
    # cancel/retry gates from the decoded EventFlow.
    flow_tree = render_tree(SHARED / 'output', 'Ftr_Working',
                            ['Workbench_Cmn_DIYdemo'])
    for marker in (
            '#182 SaveSetFromUIResult {"SaveType": "cWorkRemake"}',
            '#184 PlayerWorkbenchMaking {"IsRemake": true}',
            '#201 IF SubflowResultChoice2 {"SetIndex": 1}',
            '#185 PlayerWorkbenchGetDemo',
            '#197 PlayerWorkbenchGetDemo'):
        assert marker in flow_tree, f'missing remake outcome marker: {marker}'
    remake_tree = render_tree(SHARED / 'output', 'Ftr_Working', ['Remake'])
    for marker in (
            '#9 IF UIResultMenuDecide',
            '#11 UIWorkingHandling {"DisplayType": "cRemakeSelect"}',
            '#8 IF UIResultMenuDecide',
            '#6 CALL Ftr_Working:Remake'):
        assert marker in remake_tree, f'missing remake selection/cancel marker: {marker}'
    tutorial_tree = render_tree(SHARED / 'output', 'Ftr_Working',
                                ['RcoRemakeTrialOngoing'])
    for marker in (
            '#97 UIItemSelectWindowHandling',
            '"Mode": "cItemSelectRemakeTutorial"',
            '#100 UIWorkingHandling {"DisplayType": "cRemakeSelectTutorial"}',
            '#195 CALL Ftr_Working:Workbench_Cmn_DIYdemo'):
        assert marker in tutorial_tree, f'missing tutorial remake marker: {marker}'

    event_rows = {}
    for index in (97, 100, 182, 184, 185):
        row = db.execute('SELECT kind,name,params_json FROM event_calls '
                         'WHERE flow=? AND event_index=?',
                         ('Ftr_Working', index)).fetchone()
        assert row is not None, f'missing EventFlow event Ftr_Working#{index}'
        event_rows[str(index)] = {
            'kind': row['kind'], 'name': row['name'],
            'params': json.loads(row['params_json'])}
    assert event_rows['100']['name'] == 'EventFlowActionUIWorkingHandling'
    assert event_rows['100']['params'] == {'DisplayType': 'cRemakeSelectTutorial'}
    assert event_rows['97']['name'] == 'EventFlowActionUIItemSelectWindowHandling'
    assert event_rows['97']['params']['Mode'] == 'cItemSelectRemakeTutorial'
    assert event_rows['182']['name'] == 'EventFlowActionSaveSetFromUIResult'
    assert event_rows['182']['params'] == {'SaveType': 'cWorkRemake'}
    assert event_rows['184']['params'] == {'IsRemake': True}
    assert event_rows['185']['params']['IsRemake'] is True

    manifest = json.loads(MANIFEST.read_text())
    analysis_elf = Path(manifest['source_root']) / 'A_logic' / 'main.elf'
    report = {
        'schema': 'acnh.crafting_remake_cost_static.v1',
        'provenance': {
            'elf_sha256': sha256(analysis_elf),
            'itemparam_raw_sha256': raw_table_hash(item_param),
            'itemremake_raw_sha256': raw_table_hash(item_remake),
            'index': 'shared /workspace/acnh-re/output/index.sqlite opened read-only'},
        'table_case': {
            'ItemParam.UniqueID': 3436,
            'ItemParam.RemakeID': remake_id,
            'ItemRemake.UniqueID': value(item_remake, remake, 'UniqueID'),
            'ItemRemake.RemakeKitNum': kit_count,
            'RemakeKit.ItemParam.UniqueID': value(item_param, kit_item, 'UniqueID'),
            'ItemRemake.RemakeKitNum_column': {
                'hash': remake_field['hash'], 'offset': remake_field['offset'],
                'width': remake_field['width'], 'type': remake_field['type']},
            'all_ItemRemake_rows': len(remake_values),
            'RemakeKitNum_range_all_rows': [min(remake_values), max(remake_values)],
            'values_over_255': sum(number > 255 for number in remake_values),
            'tutorial_target_ItemKind': target_item_kind,
            'ItemKind_CraftPhoneCase_candidate': {
                'ordinal': phone_case_kind_ordinal,
                'UniqueID': value(item_kind, phone_case_kind, 'UniqueID'),
                'Label': value(item_kind, phone_case_kind, 'Label'),
                'native_code_match': '0x38 equals ordinal 56; enum-to-row bridge is not directly proven'}},
        'static_native_chain': [
            {'step': 1, 'at': '0xab2330',
             'evidence': 'resolver embeds field hash 0x29ecb129 and returns the byte at the resolved RemakeKitNum offset'},
            {'step': 2, 'at': '0x15ad1c0 via 0x15ad070',
             'evidence': 'call 0xab2330; store returned value at workbench state +0x1928'},
            {'step': 3, 'at': '0x15ae950',
             'evidence': 'for flag bit4=0, copy state +0x1928 to UI-result payload +0x14 and publish through 0x154a640'},
            {'step': 4, 'at': '0x1546070 / 0x1546020',
             'evidence': 'setter maps payload +0x14 to manager +0x5c; getter returns manager +0x48, whose +0x14 is manager +0x5c'},
            {'step': 5, 'at': '0x335d10',
             'evidence': 'read UI-result +0x14; when >=1, pass it with item ID 2513 to 0xefbdf0 -> 0xf99b10'},
            {'step': 6, 'at': '0x15ad1c0 / 0x15806f0 / 0xa9cb60',
             'evidence': 'state bit4 comes from a selected-item predicate with type code 0x38; it is not read from DisplayType'},
            {'step': 7, 'at': '0x15ae950',
             'evidence': 'bit4 set writes quantity 0 and result flag 1; bit4 clear copies state +0x1928 to payload +0x14'}],
        'eventflow': event_rows,
        'eventflow_branches': {
            'ordinary_remake': remake_tree,
            'tutorial_remake': tutorial_tree,
            'normal_remake_cancel_behavior': 'UIResultMenuDecide case 1 after cRemakeSelect retries Remake; case 1 after item selection exits before Workbench_Cmn_DIYdemo and cWorkRemake.',
            'tutorial_cancel_behavior': 'No EventFlow result/cancel query follows cRemakeSelectTutorial; page-internal cancellation is unresolved.'},
        'tutorial_bit4': {
            'selected_target': 3436,
            'selected_target_ItemKind': target_item_kind,
            'RemakeKitNum': kit_count,
            'bit4_builder': '0x15ad1c0 sets state +0x1c bit 4 from 0x15806f0',
            'predicate': '0x15806f0 tail-branches to 0xa9cb60 with code 0x38',
            'DisplayType_direct_dependency': False,
            'runtime_result_for_target': 'UNRESOLVED; code-to-ItemKind crosswalk is a candidate only'},
        'ui_preflight_hint': {
            'helper': '0x1580580 returns true for type code 0x38; otherwise compares RemakeKitNum with the supplied count after its state gates.',
            'caller': '0x136d9d0 uses the result to select a UI property value of 1.0 or 2.0.',
            'meaning': 'The property meaning and whether it disables selection are unresolved.'},
        'claims': {
            'normal_remake_cost_row_to_inventory_quantity': 'PROVEN_STATIC',
            '3436_cost_value_on_flag_bit4_clear_path': '2',
            'tutorial_displaytype_to_flag_bit4_mapping': 'NO_DIRECT_DEPENDENCY_FOUND; bit4 is set from selected-item type predicate 0x38',
            'tutorial_item_runtime_bit4': 'UNRESOLVED_STATIC_CROSSWALK',
            'ordinary_remake_cancel_before_handler': 'PROVEN_EVENTFLOW_BRANCH',
            'tutorial_internal_cancel': 'UNRESOLVED',
            'save_transaction_executed_with_real_player_data': False,
            'rollback_or_refund_on_interruption': 'NO_EXPLICIT_HANDLER_REFUND; FULL_ATOMICITY_UNRESOLVED',
            'inventory_persistence_flush_boundary': 'PLAYER_SAVE_MEMBER_MUTATION_PROVEN; DURABLE_FLUSH_UNRESOLVED'},
        'rollback_boundary': {
            'kit_update_call_sites_in_0x335d10': 1,
            'return_value_checked_immediately_after_call': False,
            'return_flow': {
                'after_kit_call': '0xefbdf0 returns to 0x335d80, which overwrites W0 with constant 1 before continuing; no immediate branch consumes the helper result.',
                'post_consume_split': '0x335dd4 reads result+0x18; the non-1 path branches to 0x335f00 and calls 0xefb1f0, while the 1 path completes a separate object-state path and branches to 0x335f18.',
                'join_and_publish': 'both visible paths rejoin at 0x335f18 and later publish a UI result via 0x154a640 at 0x33603c'},
            'explicit_kit_refund_calls_in_handler': 0,
            'kit_return_status': '0xefbdf0 returns the f99b10 status, but 0x335d80 immediately writes w0=1; no failure branch consumes the status.',
            'meaning': 'At the decoded handler/helper boundary, no explicit kit compensation appears. The post-consume helpers update the remake result; this does not rule out rollback in other event flows or save-system code.'},
        'persistent_save_boundary': {
            'player_context_accessor': '0xf8f400(player, 0)',
            'member_offset_in_player_record': '+0x70',
            'member_view_length_parameter': '0x17c',
            'inventory_mutator': '0xf99b10',
            'evidence': '0xefbdf0 obtains a player-associated member view and passes its memory to f99b10; no serializer or durable flush is identified in the handler chain.',
            'durability': 'UNRESOLVED'},
        'transaction_order': {
            'eventflow_tree': flow_tree,
            'native_handler': {
                'entry': '0x335d10 (cWorkRemake SaveSetFromUIResult case)',
                'ordered_calls': [
                    {'pc': '0x335d7c', 'target': '0xefbdf0', 'purpose': 'kit inventory update (item 2513, context quantity)'},
                    {'pc': '0x335dc0', 'target': '0xefcfc0', 'purpose': 'derive post-remake value from the selected UI result'},
                    {'pc': '0x335dd0', 'target': '0xefbad0', 'purpose': 'post-remake item helper'},
                    {'pc': '0x335f14', 'target': '0xefb1f0', 'purpose': 'alternate post-consume helper on result+0x18 != 1'},
                    {'pc': '0x33603c', 'target': '0x154a640', 'purpose': 'publish the handler UI result'}],
                'scope': 'static direct-call/control-flow reconstruction; nested helper semantics are not all resolved'}},
        'limits': [
            'Static disassembly, EventFlow and table evidence do not execute a full cWorkRemake interaction.',
            'The table field is u16 in the BCSV schema; the native accessor loads its low byte. All 654 current table values are 1..50, so this build has no truncation case.',
            'Ftr_Working#100 uses cRemakeSelectTutorial, but bit4 is derived from a selected-item type check; the exact runtime code-to-ItemKind bridge and tutorial cancel behavior remain untested.',
            'Ordinary Remake cancel branches are mapped in EventFlow, but UIResultMenuDecide case-to-button mapping is inferred from the branch shape.',
            'Inventory mutation is shown inside a player-associated save member; the durable save flush boundary and full transaction rollback are not identified.']}

    OUT.mkdir(parents=True, exist_ok=True)
    out_path = OUT / 'crafting_remake_cost_static.json'
    out_path.write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'result': 'pass', 'normal_cost': kit_count,
                      'rows': len(remake_values), 'values_over_255': 0,
                      'ui_to_inventory_chain': 'static verified',
                      'output': str(out_path)}))


if __name__ == '__main__':
    main()
