#!/usr/bin/env python3
"""Inventory binary references and direct writer edges for Friendship.

The index and resolved BCSV table are read-only inputs.  This script records
what the existing static/native traces establish about Friendship sources and
keeps candidate source attribution separate from verified native execution.
"""
import argparse
import hashlib
import json
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

    def hexes(values):
        return [hex(value) for value in values]

    table = json.loads((analysis/'tables_resolved/EventFlagsNpcMemoryParam.json').read_text())
    columns = [c['name'] for c in table['columns']]
    friendship_row = next(row for row in table['rows']
                          if len(row) > 4 and row[4] == 'Friendship')
    friendship = dict(zip(columns, friendship_row))

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
            'villager_generated_mail_eventflows': {
                'action_use_count': sum(len(x) for x in npc_mail_sends.values()),
                'flows': npc_mail_sends,
                'interpretation': 'These NNPC EventFlows send mail from a villager to the player (birthday, quest, life-start, and overflow paths); they are separate from player-to-villager post-office letters. Their action configurations do not add Friendship by themselves.',
            },
            'finding': 'The recipient-side daily mail processor reads Friendship to choose reply mail, but the visible processor has no direct Friendship writer edge. This does not rule out effects inside untraced mail UI/action handlers or attached-present handling.',
        },
        'save_and_runtime_descriptor': {
            'table_row': friendship,
            'local_save_member': {
                'node': npc_villager_node,
                'local_layout_member': next(x for x in save_layout['members'] if x['node'] == '0xa8'),
                'interpretation': 'The native-selected save tree contains the large SaveLand.Npc.NpcVillager candidate region; the external schema name is cross-version corroboration, and neither source names the Friendship byte locally.',
            },
            'record_selection_fixture': json.loads(NATIVE_WRITER_ARTIFACT.read_text())['record_formulas'],
            'runtime_descriptor_limit': 'The native 0xef2c70/0xf48840 setter test uses a synthetic save root and controlled hash/field-index/max descriptor. It proves record-slot arithmetic and writer behavior after those lookups, not the live Friendship descriptor mapping or a player save write.',
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
                        'operation': 'Pseudocode decrements +0xacac once when this actor-update method reaches its timer branch; one call is one decrement, independent of Timer parameter scaling.',
                        'invocation_frequency': 'Not established: runtime dispatch cadence/frame interval is absent from the available static call/pointer-array evidence.',
                    },
                    'flag_offset_caveat': 'NpcIsHitByNet 0x389c50 reads byte +0xacb0; NpcClearHitParam clears adjacent byte +0xacb1. These are distinct offsets and the evidence does not equate them.',
                    'counter_increment_search': 'The available decomp and analysis_decomp corpus exposes the +0xaca8 clear and NpcHitNum read, but no counter increment write. This bounded corpus search is not proof that no indirect or un-decompiled writer exists.',
                    'limit': 'The native test proves Timer*30 storage in a synthetic context; static update pseudocode bounds countdown to one unit per eligible method invocation. The real update dispatch rate and the hit-counter incrementer remain unknown, so exact seconds, hits-per-window, and hits-per-day are not established.',
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
                        'First conditional return stores -3 after an opaque date/task helper result check.',
                        'Second conditional return stores -3 if any of six opaque key/property lookups (0x3a, 0x62, 0x65, 0x5f, 0x31, 0x2a) reports the guarded condition.',
                    ],
                    'other_caller_caveat': '0xac0200 also has direct caller 0xabfcf0; that function has no indexed direct caller, so the writer is not proven to be day-change-exclusive.',
                    'bounded_native_run_attempt': {
                        'status': 'blocked_before_candidate_branch',
                        'setup': 'Executed 0xab9dc0 from the matching main.nso with synthetic output/input buffers and controlled date conversion/range helpers.',
                        'stop': 'The path reached an uninitialized manager/task object access at PC 0x22019d8 before either -3 assignment.',
                        'interpretation': 'No candidate branch was exercised; this is not negative evidence about the -3 result.',
                    },
                    'status': 'Static candidate only. No controlled execution with live manager/save/table dependencies and no ordinary-day occurrence evidence.',
                    'finding': 'This candidate is separate from the net-hit EventFlow and quest-timeout penalties; it cannot yet be labelled normal daily decay.',
                },
                'aggregate_cap_evidence': 'The full indexed EventFlow action inventory contains 72 configured AddFriendship values, all forwarded unchanged at 0xd34cb0; the generic writer clamps an individual value against its supplied descriptor but has no visible daily accumulator/gate. The Friendship table row sets DefaultValue=25 and MaxValue=255. No aggregate day-total field or writer-side daily cap is identified in this direct-call/string-reference inventory.',
                'finding': 'The evidence supports a per-source first-talk limit of one reward/day and a byte ceiling of 255, but does not establish a universal daily point cap. No-talk streak loss is documented separately from Friendship decay. The negative result is bounded to indexed direct writers and EventFlows in this 1.0.0 main build; indirect writes, dynamic keys, and absent modules remain possible.',
            }
        },
        'open': [
            'Run the day-change 0xab9dc0 -3 candidate with the real manager/save/table dependencies and establish ordinary-day reachability; its two return guards are still opaque.',
            'Trace delivery/receipt of cToNpc mail and its attached-present handler through a Friendship write; sender-side item serialization and return-to-baggage paths are now mapped, but recipient effect is unproved.',
            'Execute with the real runtime save root and Friendship descriptor table; current setter fixtures control both descriptor lookup and field offset.',
            'Find the +0xaca8 hit-counter incrementer and runtime dispatch rate of indexed actor-update method 0xc1e2e0 to establish exact net-hit cadence.',
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
