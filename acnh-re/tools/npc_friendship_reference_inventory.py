#!/usr/bin/env python3
"""Inventory binary references and direct writer edges for Friendship.

The index and resolved BCSV table are read-only inputs.  This script records
what the existing static/native traces establish about Friendship sources and
keeps candidate source attribution separate from verified native execution.
"""
import argparse
from collections import defaultdict, deque
import hashlib
import json
import re
import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
ELF_SHA256 = '5bf707c3dc5dac0ad9635af7d336ec580f81c3f7876d0f55400d1900e3415d74'
NSO_SHA256 = 'f8d248109ff72999b4600ae3749f8c7397fb960f7ad3ab8dee3018a9e14e900'
EVENTFLOW_ARTIFACT = ROOT / 'output/gameplay/villager_social_followup/eventflow_friendship_action_native.json'
NATIVE_WRITER_ARTIFACT = ROOT / 'output/gameplay/villager_social_followup/friendship_save_writer_native.json'
NATIVE_DELTA_ARTIFACT = ROOT / 'output/gameplay/villager_social_followup/friendship_delta_native.json'
SAVE_LAYOUT_ARTIFACT = ROOT / 'output/gameplay/save_layout.json'
SAVE_LAYOUT_CROSSWALK_ARTIFACT = ROOT / 'output/gameplay/save_layout_external_crosswalk.json'
HIT_TIMER_ARTIFACT = ROOT / 'output/gameplay/villager_social_followup/hit_timer_native.json'


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--analysis-root', type=Path, default=ROOT/'output',
                    help='read-only analysis corpus containing index.sqlite and tables_resolved')
    ap.add_argument('--output', type=Path,
                    default=ROOT/'output/gameplay/villager_social_followup/friendship_reference_inventory.json')
    args = ap.parse_args()
    analysis = args.analysis_root
    db = sqlite3.connect(f'file:{analysis / "index.sqlite"}?mode=ro', uri=True)

    def refs(text):
        return sorted({row[0] for row in db.execute(
            'SELECT function_va FROM string_refs WHERE text=? AND function_va IS NOT NULL', (text,))})

    def callers(va):
        return sorted({row[0] for row in db.execute(
            'SELECT owner_va FROM direct_calls WHERE target_va=? AND owner_va IS NOT NULL', (va,))})

    def calls(va):
        return list(dict.fromkeys(row[0] for row in db.execute(
            'SELECT target_va FROM direct_calls WHERE owner_va=? ORDER BY pc', (va,))))

    def direct_callee_closure(start_va):
        """Return the indexed direct-call closure for one native function."""
        graph = defaultdict(list)
        for owner_va, target_va in db.execute(
                'SELECT owner_va,target_va FROM direct_calls '
                'WHERE owner_va IS NOT NULL ORDER BY pc'):
            graph[owner_va].append(target_va)
        seen = {start_va}
        pending = deque([start_va])
        while pending:
            owner_va = pending.popleft()
            for target_va in graph.get(owner_va, ()):
                if target_va not in seen:
                    seen.add(target_va)
                    pending.append(target_va)
        return seen

    def unowned_direct_call_sites(target_va):
        """Resolve call-site owners omitted by the decomp-only direct-call index."""
        result = []
        for pc, owner_va in db.execute(
                'SELECT pc, owner_va FROM direct_calls WHERE target_va=? ORDER BY pc',
                (target_va,)):
            owner = owner_va
            method_name = None
            evidence = 'direct_calls.owner_va'
            if owner is None:
                row = db.execute(
                    'SELECT va,name,size FROM native_functions '
                    'WHERE va<=? AND span_end_va>? ORDER BY size LIMIT 1',
                    (pc, pc)).fetchone()
                if row:
                    owner, method_name, size = row
                    evidence = 'pc contained in native_functions span'
                else:
                    size = None
            else:
                row = db.execute(
                    'SELECT name,size FROM native_functions WHERE va=?',
                    (owner,)).fetchone()
                if row:
                    method_name, size = row
                else:
                    size = None
            result.append({
                'callsite_pc': hex(pc),
                'owner_va': hex(owner) if owner is not None else None,
                'owner_name': method_name,
                'owner_size': hex(size) if size is not None else None,
                'owner_resolution': evidence,
            })
        return result

    def hexes(values):
        return [hex(value) for value in values]

    table = json.loads((analysis/'tables_resolved/EventFlagsNpcMemoryParam.json').read_text())
    columns = [c['name'] for c in table['columns']]
    friendship_row = next(row for row in table['rows']
                          if len(row) > 4 and row[4] == 'Friendship')
    friendship = dict(zip(columns, friendship_row))

    # The six negative-result constants in FUN_00bb9dc0 are ItemKind enum
    # ordinals. FUN_00b25280 reads ItemParam.ItemKind and writes its converted
    # ordinal into a u16 map; FUN_00b9cb60 reads that map with the item ID at
    # descriptor+0x10.
    item_param = json.loads((analysis/'tables_resolved/ItemParam.json').read_text())
    item_kind_table = json.loads((analysis/'tables_resolved/ItemKind.json').read_text())
    item_kind_col = next(c for c in item_param['columns'] if c['name'] == 'ItemKind')
    item_kind_columns = [c['name'] for c in item_kind_table['columns']]
    minus_three_kind_codes = [0x3a, 0x62, 0x65, 0x5f, 0x31, 0x2a]
    item_kind_category_crosswalk = []
    for code in minus_three_kind_codes:
        fields = dict(zip(item_kind_columns, item_kind_table['rows'][code]))
        item_kind_category_crosswalk.append({
            'comparison_code_hex': hex(code),
            'comparison_code_decimal': code,
            'ItemParam_ItemKind_ordinal': code,
            'ItemKind_bcsv_row_index': code,
            'ItemKind_Label': fields['Label'],
            'ItemKind_Name': fields['Name'],
            'ItemKind_UniqueID': fields['UniqueID'],
            'CanGift': fields['CanGift'],
            'CanNpcPresent': fields['CanNpcPresent'],
            'CanNpcBirthdayPresent': fields['CanNpcBirthdayPresent'],
        })
    if any(row['ItemKind_UniqueID'] == row['comparison_code_decimal']
           for row in item_kind_category_crosswalk):
        raise ValueError('ItemKind row UniqueID unexpectedly equals a -3 category ordinal')
    item_kind_mapping_evidence = {
        'itemparam_source': item_param['source'],
        'itemparam_row_count': item_param['row_count'],
        'itemparam_itemkind_field': {
            'hash': item_kind_col['hash'],
            'offset': item_kind_col['offset'],
            'descriptor': item_kind_col.get('descriptor'),
            'reference': item_kind_col.get('name_reference'),
        },
        'itemkind_table_source': item_kind_table['source'],
        'itemkind_row_count': item_kind_table['row_count'],
        'native_mapping': [
            'FUN_00b25280 reads ItemParam field hash 0x5270eb75 (ItemKind), converts the enum value to an ordinal 0..0x77, and writes the u16 ordinal into the item-ID category map.',
            'FUN_00b9cb60 reads descriptor+0x10 as the item lookup key, loads that category-map entry, and compares the resulting ordinal to the supplied code.',
        ],
        'crosswalk_basis': 'The resolved ItemKind.bcsv row at index N supplies the English Label, Japanese Name, UniqueID, and NPC-present/gift flag values for ItemParam.ItemKind ordinal N. ItemKind ordinal and ItemKind UniqueID are separate domains.',
        'categories': item_kind_category_crosswalk,
        'public_schema_crosscheck': {
            'repository': 'Treeki/CylindricalEarth',
            'commit': 'bb09c0ee71a4aa6011de088b88ea55fdee0bf6e9',
            'source_file': 'specs_100.py:4027-4130, enum_f5a85f4bb42c_b173422234a3',
            'url': 'https://github.com/Treeki/CylindricalEarth/blob/bb09c0ee71a4aa6011de088b88ea55fdee0bf6e9/specs_100.py#L4027',
            'finding': 'The public 1.0.0 enum sequence agrees with the local ItemKind.bcsv row labels at all six ordinals.',
            'scope_limit': 'Schema corroboration only; it does not establish runtime occurrence of either -3 guard.',
        },
    }

    flow = json.loads(EVENTFLOW_ARTIFACT.read_text())
    gift_flows = {}
    for sample in flow['eventflow_samples']:
        name = sample['flow']
        if name.startswith('NNPC_Select_') or any(
                token in name for token in ('Gift', 'Delivery', 'Birthday')):
            gift_flows.setdefault(name, []).append(sample['AddValue'])
    gift_flows = {name: {'action_count': len(values), 'AddValue': sorted(values)}
                  for name, values in sorted(gift_flows.items())}

    # Read decoded BFEVFL sources for bounded negative claims such as the
    # player-to-villager post-office flow. No game text is loaded or emitted.
    flow_index = json.loads((analysis/'gameplay/flow_index.json').read_text())['data']
    native_handlers = json.loads(
        (analysis/'binary/event_handlers_resolved.json').read_text())['entries']

    def flow_actions(flow_name):
        meta = flow_index[flow_name]
        decoded_path = analysis/'decoded'/f"{meta['source_id']:05d}.json"
        decoded = json.loads(decoded_path.read_text())
        flowchart = next(fc for fc in decoded['data']['flowcharts']
                         if fc['name'] == flow_name)
        records = []
        for event in flowchart['events']:
            if event.get('type') != 'action':
                continue
            actor = flowchart['actors'][event['actor']]
            action = actor['actions'][event['action']]
            records.append({'event_index': int(event['name'][5:]),
                            'action': action,
                            'params': event.get('params') or {}})
        return records

    def event_calls(flow_name):
        return [
            {'event_index': event_index, 'kind': kind, 'name': name,
             'params': json.loads(params) if params else {}}
            for event_index, kind, name, params in db.execute(
                'SELECT event_index, kind, name, params_json FROM event_calls '
                'WHERE flow=? ORDER BY event_index', (flow_name,))
        ]

    def flow_nodes(flow_name, wanted):
        """Return matching query/action nodes with their actual EventFlow indexes."""
        meta = flow_index[flow_name]
        decoded_path = analysis/'decoded'/f"{meta['source_id']:05d}.json"
        decoded = json.loads(decoded_path.read_text())
        flowchart = next(fc for fc in decoded['data']['flowcharts']
                         if fc['name'] == flow_name)
        records = []
        for event in flowchart['events']:
            event_index = int(event['name'][5:])
            if event.get('type') == 'switch':
                actor = flowchart['actors'][event['actor']]
                query = actor['queries'][event['query']]
                if query in wanted:
                    records.append({
                        'event_index': event_index, 'kind': 'query',
                        'name': query, 'params': event.get('params') or {},
                        'cases': event.get('cases') or [],
                    })
            elif event.get('type') == 'action':
                actor = flowchart['actors'][event['actor']]
                action = actor['actions'][event['action']]
                if action in wanted:
                    records.append({
                        'event_index': event_index, 'kind': 'action',
                        'name': action, 'params': event.get('params') or {},
                        'next': event.get('next'),
                    })
        return records

    def native_handler(name):
        entry = native_handlers[f'EventFlowSystemActor.{name}']
        return {
            'registration_va': entry.get('registration_va'),
            'factory': entry.get('factory'),
            'constructor': entry.get('constructor'),
            'object_size': entry.get('object_size'),
            'vtable': entry.get('vtable'),
            'execution_slot': entry.get('slots', [])[-1],
            'slot_evidence': entry.get('slot_span_evidence'),
        }

    letter_flow = 'Obj_MessageCardRack_01_SendVillage'
    letter_actions = flow_actions(letter_flow)
    letter_friendship_actions = [x for x in letter_actions
                                 if x['action'] == 'EventFlowActionNpcAddFriendship']
    letter_events = event_calls(letter_flow)
    letter_delivery_events = [x for x in letter_events if x['name'] in {
        'EventFlowActionDropIntoPostOffice', 'EventFlowActionBellCountDown',
        'EventFlowQueryHasFreeInPostOffice', 'EventFlowQueryHasAttachedPresent',
        'EventFlowActionNpcAddFriendship'}]
    attached_present_names = {
        'EventFlowQueryHasAttachedPresent',
        'EventFlowActionReturnAttachedPresentToBaggage',
        'EventFlowActionDropIntoPostOffice',
        'EventFlowActionUIMsgCardAdrHandling',
        'EventFlowActionUIMsgCardEditTextHandling',
        'EventFlowActionSaveSetFromUIResult',
    }
    attached_flow_nodes = {
        flow_name: flow_nodes(flow_name, attached_present_names)
        for flow_name in (
            'Obj_MessageCardRack',
            'Obj_MessageCardRack_05_EditingCardResume',
            'Obj_MessageCardRack_01_SendVillage',
        )
    }
    attached_event_calls = {
        flow_name: [event for event in event_calls(flow_name)
                    if event['name'] in attached_present_names]
        for flow_name in (
            'Obj_MessageCardRack',
            'Obj_MessageCardRack_05_EditingCardResume',
            'Obj_MessageCardRack_01_SendVillage',
        )
    }
    mail_serializer_keys = sorted({row[0] for row in db.execute(
        'SELECT text FROM string_refs WHERE function_va=? AND text IS NOT NULL',
        (0xec5500,))})
    npc_mail_sends = {}
    for flow_name, event_index, name, params in db.execute(
            "SELECT flow,event_index,name,params_json FROM event_calls "
            "WHERE flow LIKE 'NNPC_%' AND name IN "
            "('EventFlowActionNpcMailSend','EventFlowActionNpcMailSendRandom') "
            "ORDER BY flow,event_index"):
        npc_mail_sends.setdefault(flow_name, []).append({
            'event_index': event_index, 'action': name,
            'params': json.loads(params) if params else {},
        })
    mail_related_rows = db.execute(
        "SELECT flow,actor,kind,name,count(*) FROM event_calls "
        "WHERE lower(name) LIKE '%mail%' OR lower(name) LIKE '%letter%' "
        "OR lower(name) LIKE '%present%' OR lower(name) LIKE '%attach%' "
        "OR lower(name) LIKE '%receive%' "
        "GROUP BY flow,actor,kind,name ORDER BY flow,actor,kind,name").fetchall()
    mail_related_flows = {}
    mail_related_usage = {}
    for flow_name, actor, kind, name, count in mail_related_rows:
        mail_related_flows.setdefault(flow_name, []).append({
            'actor': actor, 'kind': kind, 'name': name, 'event_count': count,
        })
        mail_related_usage[name] = mail_related_usage.get(name, 0) + count
    mail_related_flow_inventory = {
        flow_name: {
            'mail_present_related_nodes': nodes,
            'npc_add_friendship_event_count': db.execute(
                "SELECT count(*) FROM event_calls WHERE flow=? "
                "AND name='EventFlowActionNpcAddFriendship'", (flow_name,)
            ).fetchone()[0],
        }
        for flow_name, nodes in sorted(mail_related_flows.items())
    }
    mailbox_receive_action = native_handlers[
        'EventFlowSystemActor.EventFlowActionUIWaitReceivingMailAppear']
    mailbox_helper_closure = direct_callee_closure(0x367c20)
    friendship_literal_functions = set(refs('Friendship'))
    mailbox_friendship_literal_functions = sorted(
        mailbox_helper_closure & friendship_literal_functions)
    mailbox_flow_meta = flow_index['Ftr_MailBox']
    mailbox_flow_decoded = json.loads(
        (analysis/'decoded'/f"{mailbox_flow_meta['source_id']:05d}.json").read_text())
    mailbox_flowchart = next(
        fc for fc in mailbox_flow_decoded['data']['flowcharts']
        if fc['name'] == 'Ftr_MailBox')
    mailbox_flow_nodes = flow_nodes('Ftr_MailBox', {
        'EventFlowActionUIWaitReceivingMailAppear',
        'EventFlowActionUIPostHandling',
        'EventFlowActionCheckFreeCommunication',
        'EventFlowActionUIPostCreate',
        'EventFlowQueryUIResultMenuDecide',
        'EventFlowQueryIsMyVillage',
        'EventFlowQueryIsMyPost',
        'EventFlowActionNetFriendMailCheck',
        'EventFlowActionOpenMessageWindow',
    })
    mailbox_native_action_trace = {
        'registration_va': mailbox_receive_action.get('registration_va'),
        'factory': mailbox_receive_action.get('factory'),
        'constructor': mailbox_receive_action.get('constructor'),
        'object_size': mailbox_receive_action.get('object_size'),
        'vtable': mailbox_receive_action.get('vtable'),
        'slots': mailbox_receive_action.get('slots'),
        'specific_method_call': unowned_direct_call_sites(0x367c20),
        'specific_method_direct_callees': hexes(calls(0x367c20)),
        'specific_method_direct_writer_edges': {
            'calls_f48840': 0xf48840 in calls(0x367c20),
            'calls_ef2c70': 0xef2c70 in calls(0x367c20),
        },
        'specific_method_direct_callee_closure_count': len(mailbox_helper_closure),
        'specific_method_closure_writer_edges': {
            'reaches_f486c0': 0xf486c0 in mailbox_helper_closure,
            'reaches_ef2c70': 0xef2c70 in mailbox_helper_closure,
            'reaches_f48840': 0xf48840 in mailbox_helper_closure,
            'reaches_friendship_literal_functions': [
                hex(x) for x in mailbox_friendship_literal_functions],
        },
        'execution_method_pseudocode': 'Action method 0x367bd0 calls helper 0x367c20, returns while helper-context state at +0xc8 is nonzero, otherwise writes completion state 1 to action object+0xb0. The helper manages an indexed UI/message queue and calls generic UI services; its 212-function owner-resolved direct-call closure has no Friendship literal, getter, generic-key writer, or field-writer edge.',
        'limit': 'This is a negative result for the indexed direct-call closure of the UI wait action. It cannot exclude virtual callbacks, deferred save processing, another unindexed module, or later recipient/attachment handlers.',
    }
    net_receive_mail_handler = native_handlers[
        'EventFlowSystemActor.EventFlowActionNetReceiveMail']
    grow_up_meta = flow_index['System_GrowUp']
    grow_up_decoded = json.loads(
        (analysis/'decoded'/f"{grow_up_meta['source_id']:05d}.json").read_text())
    grow_up_flowchart = next(
        fc for fc in grow_up_decoded['data']['flowcharts']
        if fc['name'] == 'System_GrowUp')

    def flow_event_at(flowchart, array_index):
        """Describe a decoded EventFlow node by its array index and label."""
        event = flowchart['events'][array_index]
        node = {
            'array_index': array_index,
            'event_label': event['name'],
            'type': event.get('type'),
            'next_array_index': event.get('next'),
        }
        if event.get('type') == 'action':
            actor = flowchart['actors'][event['actor']]
            node['name'] = actor['actions'][event['action']]
            node['params'] = event.get('params') or {}
        elif event.get('type') == 'switch':
            actor = flowchart['actors'][event['actor']]
            node['name'] = actor['queries'][event['query']]
            node['params'] = event.get('params') or {}
            node['cases'] = event.get('cases') or []
        elif event.get('type') == 'subflow':
            node['flowchart'] = event.get('flowchart') or None
            node['entry_point'] = event.get('entry_point')
        return node

    # These are actual EventFlow array indexes; labels such as Event28 are
    # separate source identifiers and must not be treated as the array index.
    net_receive_mail_routes = [
        {
            'entry_point': 'ContinueCommon',
            'route_array_indices': [4, 66, 44, 13],
            'route': [flow_event_at(grow_up_flowchart, i)
                      for i in [4, 66, 44, 13]],
            'conditions': [],
            'context': 'The top-level Continue entrypoint also schedules local subflow event index 5, which calls ContinueCommon.',
        },
        {
            'entry_point': 'InGame',
            'route_array_indices': [22, 61, 82, 6, 67, 45, 26],
            'route': [flow_event_at(grow_up_flowchart, i)
                      for i in [22, 61, 82, 6, 67, 45, 26]],
            'conditions': [{'event_array_index': 82, 'query': 'EventFlowQueryPassDaysSincePreviousGrowUp',
                            'case_value': 1}],
            'context': 'The local path reaches NetReceiveMail only on the case-1 branch of PassDaysSincePreviousGrowUp.',
        },
        {
            'entry_point': 'AfterNet',
            'route_array_indices': [23, 62, 85, 8, 68, 27],
            'route': [flow_event_at(grow_up_flowchart, i)
                      for i in [23, 62, 85, 8, 68, 27]],
            'conditions': [{'event_array_index': 85, 'query': 'EventFlowQueryPassDaysSincePreviousGrowUp',
                            'case_value': 1}],
            'context': 'The local path reaches NetReceiveMail only on the case-1 branch of PassDaysSincePreviousGrowUp.',
        },
        {
            'entry_point': 'PostPlayerSwitch',
            'route_array_indices': [48, 28, 69, 46, 47, 34],
            'route': [flow_event_at(grow_up_flowchart, i)
                      for i in [48, 28, 69, 46, 47, 34]],
            'conditions': [
                {'event_array_index': 48, 'query': 'EventFlowQueryIsSharePlay',
                 'params': {'TargetMode': 0}, 'case_value': 0},
                {'event_array_index': 46, 'query': 'EventFlowQueryIsSharePlay',
                 'params': {'TargetMode': 0}, 'case_value': 1},
            ],
            'context': 'After the initial IsSharePlay case 0 path, SaveGrowUp(cInGame), and TimeLock(cUnlock), a second IsSharePlay query routes case 1 through NetUpdateFriendList to NetReceiveMail.',
        },
    ]
    net_receive_mail_native_trace = {
        'registration_va': net_receive_mail_handler.get('registration_va'),
        'factory': net_receive_mail_handler.get('factory'),
        'constructor': net_receive_mail_handler.get('constructor'),
        'object_size': net_receive_mail_handler.get('object_size'),
        'vtable': net_receive_mail_handler.get('vtable'),
        'slots': net_receive_mail_handler.get('slots'),
        'explicit_eventflow_parameters': net_receive_mail_handler.get('parameters'),
        'execution_slot_index': 8,
        'execution_slot_va': '0x326b60',
        'execution_slot_body': 'No-op native body.',
        'completion_slot_index': 9,
        'completion_slot_va': '0x326b70',
        'completion_slot_body': 'Stores 1 to action object+0xb0.',
        'friendship_writer_edges': {
            'execution_slot_direct_callees': hexes(calls(0x326b60)),
            'completion_slot_direct_callees': hexes(calls(0x326b70)),
            'execution_slot_calls_f486c0': 0xf486c0 in calls(0x326b60),
            'execution_slot_calls_ef2c70': 0xef2c70 in calls(0x326b60),
            'execution_slot_calls_f48840': 0xf48840 in calls(0x326b60),
            'completion_slot_calls_f486c0': 0xf486c0 in calls(0x326b70),
            'completion_slot_calls_ef2c70': 0xef2c70 in calls(0x326b70),
            'completion_slot_calls_f48840': 0xf48840 in calls(0x326b70),
        },
        'interpretation': 'The four System_GrowUp actions have no explicit EventFlow parameters or attached-present input. Their registered execution method is a no-op, followed by a completion-state setter; this does not reveal the external network receipt/payload processing that may occur elsewhere.',
        'limit': 'This is a bounded negative result for the decoded local 1.0.0 action and these two native methods. It cannot exclude framework side effects, indirect callbacks, deferred network/mail processing, or a missing module.',
    }
    mail_processor_edges = {
        '0xf53a70': [hex(x) for x in calls(0xf53a70)
                     if x in (0xaba970, 0xabff90)],
        '0xaba970': [hex(x) for x in calls(0xaba970) if x == 0xaba9d0],
        '0xaba9d0': [hex(x) for x in calls(0xaba9d0)
                     if x in (0xabaa80, 0xabb250)],
        '0xabb250': [hex(x) for x in calls(0xabb250)
                     if x in (0xabbf00, 0xabb3f0, 0xabba50)],
        '0xabbf00': [hex(x) for x in calls(0xabbf00)
                     if x in (0xabc820, 0xabcbe0, 0xf48840, 0xef2c70)],
    }
    save_layout = json.loads(SAVE_LAYOUT_ARTIFACT.read_text())
    save_crosswalk = json.loads(SAVE_LAYOUT_CROSSWALK_ARTIFACT.read_text())
    npc_villager_node = next(
        x for x in save_crosswalk['member_crosswalk'] if x['node'] == '0xa8')
    talk_force_samples = [x for x in flow['eventflow_samples']
                          if x['flow'] == 'NNPC_Talk_Force']
    hit_entry_event_indices = [21, 32, 33]
    hit_entry_samples = [x for x in talk_force_samples
                         if x['event_index'] in hit_entry_event_indices]
    talk_force_negative_samples = [x for x in talk_force_samples
                                   if x['AddValue'] < 0]
    talk_force_actions = [x for x in flow_actions('NNPC_Talk_Force')
                          if x['action'] == 'EventFlowActionNpcAddFriendship']
    present_flows = {name: values for name, values in gift_flows.items()
                     if name.startswith('NNPC_Select_')}
    birthday_flows = {name: values for name, values in gift_flows.items()
                      if 'Birthday' in name}

    # Exact actor-context counter access scan. The native code writes this
    # field through a pointer-array index (0x1595 * 8 == 0xaca8), so scan both
    # the explicit offset and the decompiler's indexed form.
    binary_root = analysis/'binary'
    context_counter_accesses = []
    counter_corpus_counts = {}
    counter_access_pattern = re.compile(
        r'0xaca8\b|(?:\[|\+)\s*0x1595\b')
    for corpus_name, suffix in (
            ('analysis_decomp', '.c'), ('decomp', '.c'),
            ('new_decomp', '.c'), ('disassembly_fallback', '.asm')):
        corpus_path = binary_root/corpus_name
        source_paths = sorted(corpus_path.glob(f'*{suffix}'))
        counter_corpus_counts[corpus_name] = {
            'files_scanned': len(source_paths),
            'extension': suffix,
        }
        for source_path in source_paths:
            for line_number, line in enumerate(
                    source_path.read_text(errors='ignore').splitlines(), 1):
                if counter_access_pattern.search(line.lower()):
                    context_counter_accesses.append({
                        'corpus': corpus_name,
                        'file': source_path.name,
                        'line': line_number,
                        'text': line.strip(),
                    })

    timer_call_sites = unowned_direct_call_sites(0xc1e2e0)
    pointer_arrays_path = analysis/'binary/code_pointer_arrays.json'
    timer_owner_array = None
    timer_owner_members = {}
    if pointer_arrays_path.exists():
        for pointer_array in json.loads(pointer_arrays_path.read_text()):
            for slot_index, entry in enumerate(pointer_array['entries']):
                if entry.get('target_va') in {
                        '0xbe6270', '0xbe98a0', '0xbec1f0', '0xbec810'}:
                    timer_owner_members[entry['target_va']] = {
                        'pointer_va': entry['pointer_va'],
                        'slot_index': slot_index,
                    }
                if entry.get('target_va') == '0xbec1f0':
                    timer_owner_array = {
                        'start_va': pointer_array['start_va'],
                        'pointer_va': entry['pointer_va'],
                        'target_va': entry['target_va'],
                        'slot_index': slot_index,
                        'sequence_status': pointer_array.get('status'),
                    }
            if timer_owner_array:
                timer_owner_array['related_owner_methods'] = timer_owner_members
                break

    npc_ai_state_names = sorted({row[0] for row in db.execute(
        'SELECT DISTINCT text FROM string_refs WHERE function_va=? '
        "AND text LIKE 'NpcAIState::%' ORDER BY text", (0xc1ac50,))})

    refs_friendship = refs('Friendship')
    callsite_notes = {
        0xabaA80: 'Reads Friendship in resident/player iteration and feeds the value through level conversion; no direct field writer in this function.',
        0xabbf00: 'Daily player-to-villager mail processor (0xaba970 -> 0xaba9d0 -> 0xabb250) reads Friendship, converts it to a level, and uses it to select a reply-mail branch; no direct Friendship writer call.',
        0xac0200: 'Direct daily-candidate writer: reads Friendship, invokes candidate calculator 0xab9dc0, then passes Friendship plus candidate delta to 0xf48840.',
        0xca6c40: 'Reads friendship/acquaintance values and level-converts them while selecting/scoring NPC candidates; no direct Friendship writer call.',
        0xd1cfc0: 'Reads Friendship as one input to a returned calculation; no direct Friendship writer call.',
        0xd24d20: 'Reads Friendship in a move-in/abandoned-house path; no direct Friendship writer call.',
        0xd34a70: 'Reads Friendship and returns the 1–6 point band.',
        0xd34c20: 'Reads Friendship; no direct field writer call.',
        0xd34cb0: 'Friendship delta wrapper: reads old value, applies 0xd34f80, and transitions the friendship-level flag when crossing its condition.',
        0xd34f80: 'Friendship delta/floor calculation; passes Friendship value to 0xef2c70.',
        0xed4460: 'Reads Friendship to populate NNPCFriendship/NNPCFavor values; no direct Friendship writer call.',
        0xf87670: 'Reads Friendship while populating a multi-resident synchronization/update structure; no direct Friendship writer call.',
        0xfb60a0: 'Reads Friendship and level-converts it for a threshold/random branch; no direct Friendship writer call.',
    }
    refs_inventory = []
    for va in refs_friendship:
        direct = calls(va)
        refs_inventory.append({
            'function_va': hex(va),
            'callers': hexes(callers(va)),
            'directly_calls_f486c0': 0xf486c0 in direct,
            'directly_calls_f48840': 0xf48840 in direct,
            'directly_calls_ef2c70': 0xef2c70 in direct,
            'note': callsite_notes.get(va, 'Friendship literal reference; this caller needs additional semantic tracing.'),
        })

    writer_callers = callers(0xf48840)
    wrapper_callers = callers(0xef2c70)
    result = {
        'evidence_basis': {
            'analysis_root': str(analysis),
            'index': 'index.sqlite string_refs and direct_calls; queried read-only',
            'elf_sha256': ELF_SHA256,
            'nso_sha256': NSO_SHA256,
        },
        'save_table_row': {
            'table': table['source'],
            'row_count': table['row_count'],
            'fields': friendship,
            'interpretation': 'The resolved table labels Friendship as a u8 value, initial/default 25, max 255. This describes table metadata, not execution of the runtime descriptor-map loader.',
        },
        'string_reference_inventory': {
            'key': 'Friendship',
            'function_count': len(refs_inventory),
            'functions': refs_inventory,
        },
        'known_writer_paths': [
            {
                'path': ['0xc84240', '0xd34cb0', '0xd34f80', '0xef2c70', '0xf48840'],
                'basis': 'Native talk/delta and setter fixtures plus direct-call graph.',
                'caller_edges': {
                    '0xd34cb0': hexes(callers(0xd34cb0)),
                    '0xd34f80': hexes(callers(0xd34f80)),
                    '0xef2c70': hexes(wrapper_callers),
                },
                'scope': 'First-talk reward and EventFlow AddFriendship values; the EventFlow inventory proves all 72 configured AddValue arguments reach 0xd34cb0 unchanged.',
            },
            {
                'path': ['0xf53a70', '0xabff90', '0xac0200', '0xab9dc0', '0xf48840'],
                'basis': 'Static caller edges and pseudocode only.',
                'caller_edges': {
                    '0xac0200': hexes(callers(0xac0200)),
                    '0xab9dc0': hexes(callers(0xab9dc0)),
                },
                'scope': 'Candidate day-change Friendship adjustment; the -3 branch and ordinary-play reachability remain unexecuted.',
            },
        ],
        'direct_writer_inventory': {
            'field_writer': '0xf48840',
            'direct_callers': hexes(writer_callers),
            'Friendship_literal_direct_writer': '0xac0200',
            'Friendship_literal_direct_writer_callers': hexes(callers(0xac0200)),
            'generic_key_writer': '0xef2c70',
            'generic_key_writer_callers': hexes(wrapper_callers),
            'wrapper_key_check': {
                '0xd34f80': 'Friendship',
                '0xf12fe0': ['SameLand'],
                '0xfba210': ['SickQuestGossip', 'TalkedDuringSick'],
            },
            'limits': 'Inventory is based on direct calls and indexed string references in this main.nso build; it cannot rule out indirect writes, dynamic field names, unindexed strings, or code in absent modules.',
        },
        'mail_processing': {
            'day_change_path': ['0xf53a70', '0xaba970', '0xaba9d0', '0xabb250', '0xabbf00'],
            'direct_call_targets': mail_processor_edges,
            'friendship_read': '0xabbf00 reads Friendship with 0xf486c0, converts it with 0xd34a20, and uses the band when selecting response-mail branches. It references MAIL_XX_ReMax and calls 0xabc820/0xabcbe0 to create mail; it directly calls neither 0xf48840 nor 0xef2c70.',
            'player_send_eventflow': {
                'flow': letter_flow,
                'events': letter_delivery_events,
                'finding': 'The flow selects a cNpc address, edits the card, checks 200 Bells, deducts them, then invokes DropIntoPostOffice with cSaveMailUserInfo. It contains no NpcAddFriendship action and no explicit HasAttachedPresent query.',
                'limit': 'The flow has no friendship action, but attached-item serialization can be traced through the native post-office action. Recipient-side Friendship effects remain open.',
            },
            'attached_present_native_trace': {
                'eventflow_nodes': attached_flow_nodes,
                'eventflow_calls': attached_event_calls,
                'handler_registry': {
                    'EventFlowQueryHasAttachedPresent': native_handler(
                        'EventFlowQueryHasAttachedPresent'),
                    'EventFlowActionReturnAttachedPresentToBaggage': native_handler(
                        'EventFlowActionReturnAttachedPresentToBaggage'),
                    'EventFlowActionDropIntoPostOffice': native_handler(
                        'EventFlowActionDropIntoPostOffice'),
                    'EventFlowActionUIMsgCardAdrHandling': native_handler(
                        'EventFlowActionUIMsgCardAdrHandling'),
                    'EventFlowActionUIMsgCardEditTextHandling': native_handler(
                        'EventFlowActionUIMsgCardEditTextHandling'),
                    'EventFlowActionSaveSetFromUIResult': native_handler(
                        'EventFlowActionSaveSetFromUIResult'),
                },
                'query_and_return_action': {
                    'has_present_execution_va': '0x433bc0',
                    'has_present_body_calls': ['0x1589cf0', '0x158a280'],
                    'has_present_descriptor_address': '0x3245218',
                    'return_present_execution_va': '0x33ff10',
                    'return_present_body_calls': ['0x1589cf0', '0x158a2d0'],
                    'return_present_descriptor_address': '0x3245240',
                    'interpretation': 'Both handlers build a generic property view and dispatch through a virtual method. The query returns a boolean written by that dispatch; the underlying attached-item field and the return action side effect are not named in the available static evidence.',
                },
                'post_office_native_path': {
                    'event_action_execution_va': '0x33d550',
                    'send_helper_va': '0x33d7a0',
                    'direct_helper_chain': ['0xec5410', '0xec5500', '0xec5480',
                                            '0xf62e90', '0xf73ea0'],
                    'serializer_va': '0xec5500',
                    'serializer_string_keys': mail_serializer_keys,
                    'item_sentinel': -2,
                    'item_serialization': 'The serializer writes HasItem from (item != -2); when present, it writes ItemUniqueID. It also writes CardDesignID; ToNpcUniqueID is in the record-type-1 branch.',
                    'input_binding': 'The EventFlow passes TmpMailInstance=cSaveMailUserInfo to DropIntoPostOffice; its native helper passes the current temporary record at context+0x658 to the serializer.',
                    'writer_edges': {
                        '0x33d7a0_calls_f48840': 0xf48840 in calls(0x33d7a0),
                        '0x33d7a0_calls_ef2c70': 0xef2c70 in calls(0x33d7a0),
                        '0xf62e90_calls_f48840': 0xf48840 in calls(0xf62e90),
                        '0xf62e90_calls_ef2c70': 0xef2c70 in calls(0xf62e90),
                    },
                    'limit': 'The sender serializer confirms an optional item is included in the post-office mail record. It does not prove that receipt awards or changes Friendship, and the live save descriptor for the attachment is unresolved.',
                },
                'finding': 'The save/edit flows query for an attached present and can return it to baggage. The send-to-villager flow posts cSaveMailUserInfo through a native serializer that can include an item. No recipient-side Friendship write has been found in the traced path.',
            },
            'mail_present_eventflow_inventory': {
                'source': 'Complete indexed event_calls table from decoded BFEVFLs in this build.',
                'distinct_flow_count': len(mail_related_flow_inventory),
                'action_query_use_count': sum(mail_related_usage.values()),
                'action_query_usage_counts': mail_related_usage,
                'flows': mail_related_flow_inventory,
                'receiver_paths': {
                    'Ftr_MailBox': {
                        'source': flow_index['Ftr_MailBox']['source'],
                        'entrypoint_root_event_index': mailbox_flowchart['entry_points']['Root']['main_event'],
                        'nodes': mailbox_flow_nodes,
                        'finding': 'In this local 1.0.0 flow, Root branches on Ftr.IsMyPost; the post-office UI path runs CheckFreeCommunication -> UIWaitReceivingMailAppear -> UIPostHandling -> UIResultMenuDecide. The flow has no NpcAddFriendship action. The wait action is UI handling, not proof of recipient mail deserialization.',
                        'native_handler': mailbox_native_action_trace,
                    },
                    'System_GrowUp': {
                        'source': grow_up_meta['source'],
                        'array_index_note': 'event_calls.event_index is the EventFlow event-array index; EventXX is a separate source label.',
                        'event_indices': [event_array_index for event_array_index, event in enumerate(
                            grow_up_flowchart['events'])
                            if event.get('type') == 'action'
                            and grow_up_flowchart['actors'][event['actor']]['actions'][event['action']]
                            == 'EventFlowActionNetReceiveMail'],
                        'routes': net_receive_mail_routes,
                        'native_handler': net_receive_mail_native_trace,
                        'finding': 'Four parameterless EventFlowActionNetReceiveMail nodes occur in online/network startup routes, separate from the local Ftr_MailBox UI wait and player-to-villager post-office flow. ContinueCommon follows SaveGrowUp(cStart), time unlock, and NetUpdateFriendList; InGame/AfterNet reach receipt only on PassDaysSincePreviousGrowUp case 1; PostPlayerSwitch traverses the two IsSharePlay(TargetMode=0) switch cases recorded per route. The registered action execution body is a no-op and its completion method only sets action state; neither has a direct Friendship writer edge or explicit attachment parameter.',
                        'attachment_limit': 'A network mail payload may still be processed by framework/network code outside this action. These nodes do not prove that a received attachment is a villager present or that it changes Friendship.',
                    },
                    'Obj_MessageCardRack_02_SendFuture': 'Only future-mail reservation/edit/delete/return-present actions and queries; it is not a recipient delivery flow and has no NpcAddFriendship action.',
                },
                'same_flow_caveat': 'Some villager-to-player outgoing mail EventFlows also contain friendship actions for gifts or quests. Co-location in a flow does not show that sending or receiving mail caused those separate deltas.',
                'limit': 'This exhausts decoded EventFlow action/query names containing mail, letter, present, attachment, or receive. Native indirect callbacks, omitted modules, and later save processing remain outside the inventory.',
            },
            'villager_generated_mail_eventflows': {
                'action_use_count': sum(len(x) for x in npc_mail_sends.values()),
                'flows': npc_mail_sends,
                'interpretation': 'These NNPC EventFlows send mail from a villager to the player (birthday, quest, life-start, and overflow paths); they are separate from player-to-villager post-office letters. Their action configurations do not add Friendship by themselves.',
            },
            'finding': 'The recipient-side daily mail processor reads Friendship to choose reply mail, but the visible processor has no direct Friendship writer edge. This does not rule out effects inside untraced mail UI/action handlers or attached-present handling.',
        },
        'minus_three_guard_category_mapping': item_kind_mapping_evidence,
        'public_source_review': {
            'CylindricalEarth_ItemKind': item_kind_mapping_evidence['public_schema_crosscheck'],
            'ACNH_Resources_Ftr_MailBox': {
                'url': 'https://github.com/969981/ACNH_Resources/blob/3.0.3_Unpack/UnPack/1/EventFlow/Ftr_MailBox.json',
                'finding': 'The public newer-build flow confirms the mailbox UI wait and post handling sequence, and adds NetFriendMailCheck and movement/tutorial gates absent from the local 1.0.0 graph. It has no native Friendship writer information.',
                'version_limit': 'Newer public EventFlow reference; used only to compare flow structure, not to prove local 1.0.0 runtime behavior.',
            },
            'Rafacasari_acnh_eventflows': {
                'url': 'https://github.com/Rafacasari/acnh-eventflows/blob/78cbc66da4cfb7cb365be77651ed6acdc0b799e4/Ftr_MailBox.evfl.txt',
                'finding': 'Readable EventFlow rendering likewise shows mailbox/post-office UI and message branches, not a Friendship writer.',
                'version_limit': 'Public flow text does not identify native action implementations or save effects.',
            },
            'ACNHRecomp': {
                'url': 'https://github.com/Nycolazs/ACNHRecomp',
                'searches': ['NpcHitNum', 'ItemKind', 'Ftr_MailBox'],
                'finding': 'GitHub code searches exposed no matching game-native function bodies for NpcHitNum, ItemKind, or Ftr_MailBox. A separate Friendship search request failed and is not counted as a negative result.',
                'limit': 'A public-repository search is not a proof of absence; this project does not provide a matching 1.0.0 native body for the unresolved call edges.',
            },
        },
        'static_source_coverage_and_live_capture': {
            'indexed_binary': {
                'module': 'ExeFS main NSO',
                'sha256': NSO_SHA256,
                'analysis_decomp_c_files': counter_corpus_counts['analysis_decomp']['files_scanned'],
                'decomp_c_files': counter_corpus_counts['decomp']['files_scanned'],
                'new_decomp_c_files': counter_corpus_counts['new_decomp']['files_scanned'],
                'disassembly_fallback_asm_files': counter_corpus_counts['disassembly_fallback']['files_scanned'],
                'module_boundary': 'The current index and native call graph are for main NSO. Other supplied ExeFS modules rtld, sdk, and subsdk0 are present as inputs but are not represented in this indexed direct-call graph.',
            },
            'eventflow_scope': {
                'source': 'Decoded local-build BFEVFL corpus and event_calls table',
                'mail_present_receive_action_query_uses': sum(mail_related_usage.values()),
                'distinct_flows': len(mail_related_flow_inventory),
                'Ftr_MailBox_local_flow_node_count': len(mailbox_flow_nodes),
                'System_GrowUp_NetReceiveMail_event_count': 4,
                'limit': 'No live EventFlow execution was recorded; direct-call closures do not include virtual callback semantics or later persistence processors.',
            },
            'source_table_scope': {
                'ItemParam_rows': item_param['row_count'],
                'ItemKind_rows': item_kind_table['row_count'],
                'Friendship_descriptor_table': table['source'],
            },
            'live_capture_blocker': 'The indexed 1.0.0 static corpus and public references reviewed add no further evidence for these specific questions. Remaining proof requires an instrumented process running the matching 1.0.0 build plus a cloned save with real runtime table/save managers; no game process or live save was supplied.',
            'capture_plan': [
                'At 0xab9dc0 entry/return, log caller/backtrace, ushort item ID, descriptor+0x10 key, mapped ItemParam.ItemKind ordinal, async wrapper status at +0x50, result at +0x20, and output delta. Observe calls from both 0xabff90 and 0xabfcf0 on an ordinary day and after day-change; compare -2, ordinary category, and one item per six mapped categories.',
                'At 0xac0200 and 0xf48840, snapshot Friendship before/after each candidate to establish whether either -3 guard is reached and written during normal play.',
                'At owner constructor 0xbe5e40, population method 0xbe98a0, and indirect factory load/call at 0xbeab28/0xbeab30, record the selected registry row/key, resolved target, returned child pointer/vptr, owner+0x2f8 store, and setup call 0xc1ac50. Watch +0x2f8 through slot-18 clear 0xbec810 and destructor 0xbe6270 to identify all runtime lifecycle transitions and the concrete child type.',
                'Place a write watchpoint on NPC actor+0xaca8 and log every write PC/backtrace/object base; hook clear 0x258b10 and read 0x388660. Trace the actual indirect dispatch into owner vtable slot 13 at 0xbec1f0 (entry 0x30d5908, byte offset 0x68) and count its entries and child calls to 0xc1e2e0 at 0xbec314 against frame numbers and elapsed time; this identifies the incrementer and actual update cadence.',
                'On a cloned save, send and receive controlled player letters with no attachment, an ordinary attachment, and representative attachments from each mapped ItemKind. Capture execution of each System_GrowUp NetReceiveMail route and the external network payload/recipient processor; trace Ftr_MailBox UI separately, then log Friendship getter/writer sites and saved-state diff. Break at NetReceiveMail native execution 0x326b60 and completion 0x326b70, while recognizing their local bodies alone do not expose payload processing.',
                'During local and network Friendship writes, capture the live Key="Friendship" descriptor returned through 0xdc5e20, its UniqueID/MaxValue, typed view address selected by 0xef2c70, save root, and resulting raw bytes. Compare with local formula save_base+resident*0x10798+player*0xa8+0x39f8 and network formula save_base+resident*0x10798+player*0x700+0x1c0; then observe save flush/persistence.',
            ],
        },
        'save_and_runtime_descriptor': {
            'table_row': friendship,
            'native_field_mapping': {
                'key_to_table_row': {
                    'function': '0xdc5e20',
                    'key_field_hash': '0x45f320f2',
                    'meaning': 'The generic native descriptor lookup selects a row by Key; the Friendship table row joins by literal Key="Friendship".',
                },
                'field_selector': {
                    'function': '0xf48190',
                    'field_hash': '0x54706054',
                    'field_name': 'UniqueID',
                    'Friendship_table_value': friendship['UniqueID'],
                    'interpretation': 'The native setter uses the selected descriptor UniqueID as its selector in the requested field view; a controlled fixture now tests the extracted value 10.',
                },
                'value_ceiling': {
                    'function': '0xf48840',
                    'field_hash': '0xbd7682f5',
                    'field_name': 'MaxValue',
                    'Friendship_table_value': friendship['MaxValue'],
                    'interpretation': 'The writer reads the selected descriptor MaxValue for clamping; fixture metadata is seeded with the table value 255.',
                },
                'view_request': {
                    'function': '0xef2c70 -> typed-view virtual slot',
                    'requested_size': '0x100',
                    'crosswalk_candidate': 'SaveEventFlagNpcMemory has external size 0x100 and a Flags.ValueArray member.',
                },
                'local_native_type_candidate': {
                    'vtable': '0x30e8680',
                    'size': '0x100',
                    'sample_node': '0x1c0',
                    'sample_data': '0x44',
                    'instances': 2352,
                    'crosswalk_status': 'multiple_struct_type_candidates',
                    'type_candidates': ['::Game::SaveEventFlagNpcMemory', 's_33a3f71b'],
                    'external_candidate_path': 'SaveLand.Npc.NpcVillager.Animal[0].Memory[0].EventFlag.Flags.ValueArray[0]',
                    'version_limit': 'Crosswalk source is the public save_schema_111_103 schema; local executable is 1.0.0.',
                },
                'evidence_limit': 'Table row selection and the native table-manager lookup remain controlled by the fixture; the tested +0x0a is relative to a synthetic 0x100-byte view, not a proven absolute player-save byte offset.',
            },
            'local_save_member': {
                'node': npc_villager_node,
                'local_layout_member': next(x for x in save_layout['members'] if x['node'] == '0xa8'),
                'interpretation': 'The native-selected save tree contains the large SaveLand.Npc.NpcVillager candidate region; the external schema name is cross-version corroboration, and neither source names the Friendship byte locally.',
            },
            'record_selection_fixture': json.loads(NATIVE_WRITER_ARTIFACT.read_text())['record_formulas'],
            'runtime_descriptor_limit': 'The native 0xef2c70/0xf48840 setter test uses a synthetic save root and controlled hash-to-row lookup; the selector and ceiling are seeded from the exact Friendship table row (UniqueID=10, MaxValue=255). It proves record-slot arithmetic and mutation at synthetic view+0x0a, not the live descriptor-manager lookup or absolute player-save offset.',
        },
        'eventflow_gift_related_actions': {
            'source_artifact': 'eventflow_friendship_action_native.json',
            'flow_actions': gift_flows,
            'claim_limit': 'These are configured action deltas and native callback forwarding. They do not establish every item-quality formula or that each conditional action occurs in a playthrough.',
        },
        'behavior_source_review': {
            'gift_selection': {
                'flow_action_deltas': present_flows,
                'birthday_gift_deltas': birthday_flows,
                'interpretation': 'NNPC_Select_Present dispatches by selected item kind into creature, equipment, furniture, tool, and other item subflows. NNPC_Select_Sell_Gift is the villager buying a selected player item; CheckNpcFavorLevel selects configured +1/+2/+3 friendship branches, and the overflow branch sends MAIL_XX_OverFlow by NpcMailSendRandom after those deltas. These are different flows from player letters.',
            },
            'player_letter': {
                'flow': letter_flow,
                'source': flow_index[letter_flow]['source'],
                'actions': letter_actions,
                'npc_add_friendship_action_count': len(letter_friendship_actions),
                'finding': 'The local player-to-villager post-office flow edits and posts a message card after a 200-Bell check; it contains no NpcAddFriendship action. The indexed exact-key friendship writer inventory also identifies no letter-sender callsite.',
                'limit': 'This does not rule out a later Friendship change when a delivered letter or attached present is processed.',
            },
            'net_hits': {
                'ai_flow_edges': [
                    {'flow': 'AI_NPC_Normal', 'entry': 'End_Hit',
                     'checks': ['NpcIsHitByNet', 'NpcHitNum(Border=3)'],
                     'route': 'NNPC_Talk_Force:Hit'},
                    {'flow': 'AI_NPC_Outdoor', 'entry': 'Hit',
                     'checks': ['NpcIsHitByNet', 'NpcHitNum(Border=3)',
                                'HasAcquaintanceship'],
                     'route': 'NNPC_Talk_Force:Hit'},
                ],
                'query_pseudocode': {
                    'NpcHitNum': '0x388660 returns case 0 when configured Border <= the NPC hit counter; AI_NPC_Normal and AI_NPC_Outdoor use Border=3.',
                    'NpcIsHitByNet': '0x389c50 returns case 0 when the NPC hit-by-net byte is nonzero.',
                },
                'timer_and_clear_pseudocode': {
                    'NpcSetHitTimer': 'Action handler 0x25c650 stores Timer * 30 at context offset +0xacac; Timer=60 is configured on the below-threshold return path.',
                    'NpcClearHitParam': 'Action handler 0x258b10 zeros the u32 at context offset +0xaca8 (the counter read by 0x388660) and byte +0xacb1.',
                    'native_controlled_test': json.loads(HIT_TIMER_ARTIFACT.read_text()),
                    'countdown_method': {
                        'indexed_va': '0xc1e2e0',
                        'decompiler_symbol': '0xd1e2e0',
                        'operation': 'Pseudocode decrements +0xabe8 once when positive near method entry, then decrements the separate +0xacac timer once only if the later state guards allow the timer branch. Each decrement is per method invocation, independent of Timer parameter scaling.',
                        'invocation_frequency': 'Not established: runtime dispatch cadence/frame interval is absent from the available static call/pointer-array evidence.',
                    },
                    'flag_offset_caveat': 'NpcIsHitByNet 0x389c50 reads byte +0xacb0; NpcClearHitParam clears adjacent byte +0xacb1. These are distinct offsets and the evidence does not equate them.',
                    'counter_increment_search': 'Exact +0xaca8 / indexed +0x1595 search over analysis_decomp, decomp, new_decomp, and selected disassembly_fallback snippets finds the generic subobject setup, clear, and read only; there is no increment in those scanned sources. Computed-pointer writes or unindexed code remain possible.',
                    'counter_access_scan': {
                        'analysis_decomp_c_files_scanned': counter_corpus_counts['analysis_decomp']['files_scanned'],
                        'corpora_scanned': counter_corpus_counts,
                        'offset_equivalence': '0xaca8 == 0x1595 * sizeof(u64); scan covers both explicit offset and pointer-array-index forms.',
                        'accesses': context_counter_accesses,
                        'finding': 'The only exact source hits are generic subobject construction, NpcClearHitParam zeroing the field, and NpcHitNum reading it; the second decomp tree repeats the clear/read, while new_decomp and the selected fallback assembly snippets have no exact hit. No increment or other nonzero writer appears in these scanned corpora.',
                    },
                    'timer_update_call_owner': {
                        'decrementer_method': '0xc1e2e0',
                        'direct_call_sites': timer_call_sites,
                        'pointer_sequence_membership': timer_owner_array,
                        'owner_object_subobject_lifecycle': {
                            'field_offset': '0x2f8',
                            'semantic_candidate': 'NPC AI-state/controller subobject; the native RTTI/class name is not recovered, but setup method 0xc1ac50 references 43 NpcAIState::... names.',
                            'owner_class_evidence': {
                                'constructor_va': '0xbe5e40',
                                'constructor_native_span': '0xbe5e40..0xbe5f5b',
                                'constructor_behavior': 'Raw disassembly allocates 0x618 bytes, stores the vptr from *(0x32f7a18)+0x10, and zeros owner offsets +0x2f0, +0x2f8, +0x300, +0x308, +0x310, and +0x318 before later initialization.',
                                'pointer_sequence_methods': timer_owner_members,
                                'global_vptr_handle': {
                                    'global_va': '0x32f7a18',
                                    'relocated_value': '0x30d5890',
                                    'constructor_addend': '0x10',
                                    'constructor_store_va': '0xbe5e98',
                                    'resolved_vtable_va': '0x30d58a0',
                                    'evidence': 'The main NSO R_AARCH64_RELATIVE relocation resolves *(0x32f7a18) to 0x30d5890; constructor 0xbe5e70..0xbe5e98 loads it, adds 0x10, and stores the resulting 0x30d58a0 to the new owner object. This equals the sequence start and confirms this sequence is the owner vtable.',
                                },
                                'classification': 'Confirmed owner vtable at 0x30d58a0: slot 0 is the destructor, slot 7 populates +0x2f8, slot 13 performs the owner update, and slot 18 tears the child down.',
                            },
                            'population_method': {
                                'va': '0xbe98a0',
                                'vtable_slot': 7,
                                'factory_indirect_callsite': '0xbeab30',
                                'pointer_store_pc': '0xbeab34',
                                'null_check_pc': '0xbeab38',
                                'setup_callsite': '0xbeab40',
                                'setup_method': '0xc1ac50',
                                'behavior': 'The selected indirect factory returns a child pointer in x0; the method stores it at owner+0x2f8, skips setup when null, and otherwise calls 0xc1ac50(child, original_method_arg2). 0xc1ac50 registers 43 statically named NpcAIState entries, including cIdle, cWander, cTalk, cHit, and cConversationPretense.',
                                'direct_callers_of_population_method': hexes(callers(0xbe98a0)),
                                'factory_dispatch': 'The R_AARCH64_RELATIVE relocation at global 0x32d3e20 resolves to BSS object 0x356b3f0. At 0xbeaa68..0xbeaa6c, the method loads the runtime registry object pointer from that BSS object; at 0xbeaa8c..0xbeaa94 it reads the count at registry+8 and records pointer at registry+0x10. It searches 0x20-byte records using the computed w0 key against record+0x18. On a match, 0xbeab28 loads the record qword at +0 and 0xbeab30 calls it indirectly; 0xbeab34 stores the returned child at owner+0x2f8. The registry object pointer/table contents are runtime-populated in BSS, so the selected row and target cannot be recovered from this dump alone.',
                                'factory_identity': 'Unresolved statically: the factory comes from a runtime-populated BSS registry and is loaded indirectly at 0xbeab28. Capture its target and selected row/key at runtime.',
                                'factory_registry': {
                                    'global_va': '0x32d3e20',
                                    'global_relocated_value': '0x356b3f0',
                                    'registry_pointer_field_offset': '0x0',
                                    'count_field_offset': '0x8',
                                    'records_pointer_field_offset': '0x10',
                                    'record_size': '0x20',
                                    'record_factory_pointer_offset': '0x0',
                                    'factory_pointer_load_pc': '0xbeab28',
                                    'factory_indirect_call_pc': '0xbeab30',
                                    'record_selector_key_offset': '0x18',
                                    'selector_key_source': 'Return value in w0 from helper 0x1bf0 at 0xbeaa80, called with owner+0x360 and w1=0.',
                                    'status': 'The global resolves to a BSS storage object, but its registry pointer/count/record contents are runtime-populated and absent from the static file image.',
                                },
                                'npc_ai_state_registration_names': npc_ai_state_names,
                            },
                            'update_method': {
                                'va': '0xbec1f0',
                                'vtable_slot': 13,
                            'direct_callers': hexes(callers(0xbec1f0)),
                                'indirect_membership': 'pointer_sequence_membership above',
                                'callsite_to_child_update': '0xbec314',
                                'condition': 'At 0xbec30c the owner loads owner+0x2f8 into x0; 0xbec310 skips the call if null; otherwise 0xbec314 calls 0xc1e2e0 with the child as this.',
                            },
                            'clear_method': {
                                'va': '0xbec810',
                                'vtable_slot': 18,
                                'behavior': 'If owner+0x2f8 is non-null, calls child cleanup 0xc1eab0, calls child virtual release slot +0x18, then stores null at owner+0x2f8.',
                            },
                            'destructor': {
                                'va': '0xbe6270',
                                'vtable_slot': 0,
                                'behavior': 'Replaces the current vptr with the global-base vptr, releases child owner+0x2f8 through its virtual slot +0x18, then clears the pointer.',
                            },
                            'name_limit': 'Static evidence identifies the child by its AI-state registration strings and lifecycle. No native RTTI symbol, public exact 1.0.0 class name, or selected dynamic factory target identifies the concrete child type.',
                        },
                        'owner_disassembly': {
                            'source': 'Raw local main NSO AArch64 disassembly, same SHA-256 as evidence_basis.nso_sha256; owner C body is absent from both decomp trees.',
                            'callsite': '0xbec314',
                            'call_condition': 'Owner loads pointer from owner_object+0x2f8 at 0xbec30c, branches around the call if it is null at 0xbec310, and calls 0xc1e2e0 at 0xbec314 otherwise.',
                        },
                        'interpretation': 'The decrementer is called from owner update method 0xbec1f0 in slot 13 of a strong vtable candidate; the parent constructor, +0x2f8 AI-state population, and teardown are now mapped. The indexed direct-call graph has zero callers of 0xbec1f0; slot membership supplies an indirect-dispatch candidate but does not identify or prove the external dispatcher or cadence.',
                    },
                    'limit': 'The native test proves Timer*30 storage in a synthetic context; static update pseudocode bounds the +0xacac countdown to one unit per eligible method invocation. The real update dispatch rate and +0xaca8 hit-counter incrementer remain unknown, so exact seconds, hits-per-window, and hits-per-day are not established.',
                },
                'hit_entry_friendship_action_event_indices': hit_entry_event_indices,
                'hit_entry_friendship_action_values': [x['AddValue'] for x in hit_entry_samples],
                'all_flow_negative_friendship_action_event_indices': [
                    x['event_index'] for x in talk_force_negative_samples],
                'all_flow_negative_friendship_action_values': [
                    x['AddValue'] for x in talk_force_negative_samples],
                'all_flow_negative_friendship_action_count': len(talk_force_negative_samples),
                'flow_friendship_action_count': len(talk_force_actions),
                'finding': 'The net-hit path requires the hit-by-net query to pass and the hit counter to reach 3; the below-threshold path arms the 60-timer action and returns to the normal AI route. Outdoor additionally requires HitMainPlayer and HasAcquaintanceship before entering cHit/Hit. NNPC_Talk_Force:Hit then chooses one of three mutually exclusive random branches; only action sites 21, 32, or 33 can subtract -3, and each is reached through CheckNpcLook case 0 and NoAcquaintance_Chk. The helper exits when HasAcquaintanceship is OFF. Thus one Hit-entry invocation can execute at most one of these three -3 actions, while a later thresholded hit sequence may repeat it after hit state is reset. The same flow has four other -3 actions in Push and +5 in Flea; these are separate entries. All configured callback values are forwarded unchanged in the 72/72 native action test.',
                'limits': ['The AI transition bodies are not exercised as an end-to-end native hit simulation.', 'The timer handler is tested natively with synthetic context; update cadence and the counter incrementer remain unknown.', 'A net hit alone does not prove a Friendship loss: the threshold, AI route, acquaintance/look checks, and selected dialogue branch all matter.'],
            },
            'neglect_and_caps': {
                'first_talk_of_day': '0xc84240 increments TalkCountToday and awards Friendship only when its resulting value is 1; the delta is min(ContinuousTalkDays, 3), as pseudocode evidence.',
                'missed_talk': 'The day-change reset helpers clear ContinuousTalkDays when the prior TalkCountToday is zero in the applicable mode. This removes the streak bonus; no direct Friendship decrement is shown on that path.',
                'field_table': 'EventFlagsNpcMemoryParam sets Friendship default 25/max 255 and ContinuousTalkDays default 0/max 7. These are field bounds, not an aggregate daily Friendship cap.',
                'milestone_flag': 'NNPC_Talk_General:PresentAvailable_Chk uses FriendshipBecomeAcqHToday and FriendshipBecomeAcqH to gate ReceivedFirstPresent; these flags are not a writer-level point cap.',
                'quest_timeout': 'NNPC_Quest_Delivery_TimeOver configures -1, -2, or -3 according to HasDeliveryItem and HasOpenedDeliveryItem query branches; this is a quest timeout penalty, not passive neglect decay.',
                'daily_candidate': {
                    'route': ['0xf53a70', '0xabff90', '0xac0200', '0xab9dc0', '0xf48840'],
                    'indexed_edges': {
                        '0xf53a70_to_0xabff90': 0xabff90 in calls(0xf53a70),
                        '0xabff90_callers': hexes(callers(0xabff90)),
                        '0xac0200_callers': hexes(callers(0xac0200)),
                        '0xab9dc0_callers': hexes(callers(0xab9dc0)),
                    },
                    'calc_minus_three_branches': [
                        'First conditional return stores -3 when an async task result is greater than 2. The task result lives at wrapper+0x20 and is read only once its status at +0x50 equals 2; the task/worker result enum is not named.',
                        'Second conditional return stores -3 when any of six descriptor category checks matches ItemKind ordinal codes 0x3a=Trash, 0x62=LostQuestDust, 0x65=TreasureQuestDust, 0x5f=JohnnyQuestDust, 0x31=TurnipExpired, or 0x2a=Weed. Helper 0xb9cb60 maps descriptor+0x10 through the ItemParam.ItemKind u16 category map before comparison; these codes are not ItemKind row UniqueIDs or EventFlags UniqueIDs.',
                    ],
                    'other_caller_caveat': '0xac0200 also has direct caller 0xabfcf0; that function has no indexed direct caller, so the writer is not proven to be day-change-exclusive.',
                    'bounded_native_run_attempt': {
                        'status': 'blocked_before_candidate_branch',
                        'setup': 'Executed 0xab9dc0 from the matching main.nso with synthetic output/input buffers and controlled date conversion/range helpers.',
                        'stop': 'The path reached an uninitialized task/manager object access at PC 0x22019d8 before the async result or six category comparisons could be controlled.',
                        'interpretation': 'No candidate branch was exercised; static mapping now names the second guard categories, but neither runtime condition nor normal-day occurrence is verified and the async worker result remains unnamed.',
                    },
                    'status': 'Static candidate only. The six item-category ordinals are mapped, but there is no controlled execution with live manager/save/table dependencies and no ordinary-day occurrence evidence.',
                    'finding': 'This candidate is separate from the net-hit EventFlow and quest-timeout penalties; it cannot yet be labelled normal daily decay.',
                },
                'aggregate_cap_evidence': 'The full indexed EventFlow action inventory contains 72 configured AddFriendship values, all forwarded unchanged at 0xd34cb0; the generic writer clamps an individual value against its supplied descriptor but has no visible daily accumulator/gate. The Friendship table row sets DefaultValue=25 and MaxValue=255. No aggregate day-total field or writer-side daily cap is identified in this direct-call/string-reference inventory.',
                'finding': 'The evidence supports a per-source first-talk limit of one reward/day and a byte ceiling of 255, but does not establish a universal daily point cap. No-talk streak loss is documented separately from Friendship decay. The negative result is bounded to indexed direct writers and EventFlows in this 1.0.0 main build; indirect writes, dynamic keys, and absent modules remain possible.',
            }
        },
        'open': [
            'Run the day-change 0xab9dc0 -3 candidate with the real task/manager/save/table dependencies and establish ordinary-day reachability; the six category names are mapped, but the async worker result and guard occurrence remain unresolved.',
            'Trace delivery/receipt of cToNpc mail and its attached-present handler through a Friendship write; sender-side item serialization and return-to-baggage paths are now mapped, but recipient effect is unproved.',
            'Execute with the real runtime save root and Friendship descriptor table; current setter fixtures control both descriptor lookup and field offset.',
            'Resolve the runtime factory row/child type for owner+0x2f8, identify the runtime dispatcher invoking owner vtable slot 13 (0xbec1f0), and measure its cadence; find the +0xaca8 hit-counter incrementer to establish exact net-hit timing.',
            'Determine host/guest state-transition conditions and prove whether 0x395bc0/0x395e50/0x3960d0 result indexes are dialog topics, messages, or another conversation selector.',
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps({'friendship_reference_functions': len(refs_inventory),
                      'direct_f48840_callers': len(writer_callers),
                      'generic_ef2c70_callers': len(wrapper_callers),
                      'gift_related_flows': list(gift_flows),
                      'artifact': str(args.output)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
