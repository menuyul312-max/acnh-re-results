"""Extract house-loan EventFlow and static native-link evidence from shared data."""
from pathlib import Path
import hashlib
import json
import sqlite3
import sys

REPO = Path(__file__).resolve().parent.parent
DATA = Path('/workspace/acnh-re')
ROMFS = Path('/workspace/downloads/acnh_additional_romfs_2026-11-02/romfs')
ELF = Path('/workspace/downloads/ACNH_island_RE/ACNH_island_RE/A_logic/main.elf')
DB = DATA / 'output' / 'index.sqlite'
OUT = REPO / 'output' / 'gameplay' / 'house_hha_followup' / 'house_loan_eventflow.json'
FLOWS = {
    'SNPC_rco_03_ChkAfterRemodel': 'Root',
    'SNPC_rco_10_Common_UpgradeMyhome': 'RcoCmnProcessUpgradeMyhome',
    'SNPC_rco_04_ChkFinishLoan': 'Root',
    'Player_GetDemo_Once': 'Get_FinishLoan',
    'Obj_RcoMachine': 'RcoMachineATM',
}
EXPECTED_LOANS = {2: 98000, 3: 198000, 4: 348000, 5: 548000,
                  6: 758000, 7: 1248000, 8: 2498000}


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def manifest_entry(source_id):
    manifest = json.loads((DATA / 'output' / 'manifest.json').read_text())
    return manifest['entries'][source_id]


def load_flow(flow_name):
    flow_index = json.loads((REPO / 'output' / 'gameplay' / 'flow_index.json').read_text())['data']
    indexed = flow_index[flow_name]
    entry = manifest_entry(indexed['source_id'])
    source = ROMFS / indexed['source'].removeprefix('B_data/')
    assert sha256(source) == entry['sha256'] == entry['raw']['sha256']
    decoded_path = DATA / 'output' / entry['decoded']
    decoded = json.loads(decoded_path.read_text())
    charts = decoded['data']['flowcharts']
    chart = next(chart for chart in charts if chart['name'] == flow_name)
    return indexed, entry, source, chart


def walk_entry(chart, entry_name):
    """Return actions and path conditions from the decoded BFEVFL graph."""
    actors, events = chart['actors'], chart['events']
    start = chart['entry_points'][entry_name]['main_event']
    pending = [(start, [])]
    seen = set()
    actions = []
    while pending:
        event_index, conditions = pending.pop()
        if event_index is None:
            continue
        condition_key = json.dumps(conditions, sort_keys=True, ensure_ascii=False)
        key = (event_index, condition_key)
        if key in seen:
            continue
        seen.add(key)
        event = events[event_index]
        if event['type'] == 'action':
            actor = actors[event['actor']]
            name = actor['actions'][event['action']]
            if name in {
                'EventFlowActionPlayerSetLoan',
                'EventFlowActionEventFlagSystemOn',
                'EventFlowActionEventFlagSystemOff',
                'EventFlowActionReservePlayerMutterDemo',
                'EventFlowActionEventFlagSystemAdd',
            }:
                actions.append({'event_index': event_index, 'action': name,
                                'params': event.get('params') or {},
                                'conditions': conditions})
            pending.append((event.get('next'), conditions))
        elif event['type'] == 'switch':
            actor = actors[event['actor']]
            query = actor['queries'][event['query']]
            params = event.get('params') or {}
            for case in reversed(event.get('cases') or []):
                condition = {'query': query, 'params': params,
                             'case': case.get('value')}
                pending.append((case.get('event'), conditions + [condition]))
    return actions


def selected_conditions(actions, query):
    return [action for action in actions
            if any(c['query'].endswith(query) for c in action['conditions'])]


def main():
    loaded = {name: load_flow(name) for name in FLOWS}
    chart_evidence = {}
    actions_by_flow = {}
    for name, entry_name in FLOWS.items():
        indexed, entry, source, chart = loaded[name]
        actions = walk_entry(chart, entry_name)
        actions_by_flow[name] = actions
        chart_evidence[name] = {
            'entry': entry_name,
            'source': indexed['source'],
            'sha256': entry['sha256'],
            'bytes': entry['size'],
            'actions_observed': len(actions),
        }

    loan_actions = [a for a in actions_by_flow['SNPC_rco_03_ChkAfterRemodel']
                    if a['action'] == 'EventFlowActionPlayerSetLoan']
    loan_by_level = {}
    for action in loan_actions:
        level = next(c['case'] for c in action['conditions']
                     if c['query'].endswith('PlayerHouseLevel'))
        loan_by_level[level] = action['params']['Bells']
    assert loan_by_level == EXPECTED_LOANS, loan_by_level

    order_actions = actions_by_flow['SNPC_rco_10_Common_UpgradeMyhome']
    house_order = {}
    flag_index = json.loads((REPO / 'output' / 'gameplay' / 'flag_index.json').read_text())['data']
    for action in order_actions:
        if action['action'] != 'EventFlowActionEventFlagSystemOn':
            continue
        flag = action['params'].get('AccessKey', '')
        if flag.startswith('cHouse:HouseOrder'):
            level = next(c['case'] for c in action['conditions']
                         if c['query'].endswith('PlayerHouseLevel'))
            house_order[level] = {
                'flag': flag,
                'name_ja': flag_index[flag]['definition']['name_ja'],
            }
    assert set(house_order) == set(range(1, 8))

    rco_flag = flag_index['cPlayer:RcoAfterHouseRemodel']
    rco_on_writers = [w for w in rco_flag['eventflow_writers'] if w['op'] == 'on']
    assert not rco_on_writers
    finish_writes = [a for a in actions_by_flow['SNPC_rco_04_ChkFinishLoan']
                     if a['action'] == 'EventFlowActionEventFlagSystemOff'
                     and a['params'].get('AccessKey') == 'cPlayer:PlayerLoanFinish1st']
    final_loan_flag = [a for a in actions_by_flow['SNPC_rco_04_ChkFinishLoan']
                       if a['action'] == 'EventFlowActionEventFlagSystemOn'
                       and a['params'].get('AccessKey') == 'cPlayer:PcHousingLoanFinish']
    demo_actions = actions_by_flow['Player_GetDemo_Once']
    atm_demo = [a for a in actions_by_flow['Obj_RcoMachine']
                if a['action'] == 'EventFlowActionReservePlayerMutterDemo'
                and a['params'].get('EntryPointName') == 'Get_FinishLoan']

    handlers = json.loads((DATA / 'output' / 'binary' / 'event_handlers_resolved.json').read_text())
    handler = handlers['entries']['EventFlowSystemActor.EventFlowActionPlayerSetLoan']
    assert handler['parameters'] == {'Bells': 'int'}
    method_va = int(handler['slots'][11], 16)
    assert method_va == 0x32e2f0

    db = sqlite3.connect(f'file:{DB}?mode=ro', uri=True)
    db.row_factory = sqlite3.Row
    def calls(owner, target):
        return [{'pc': f'0x{r["pc"]:x}', 'target': f'0x{r["target_va"]:x}',
                 'instruction': r['instruction']}
                for r in db.execute('SELECT pc,target_va,instruction FROM direct_calls '
                                    'WHERE owner_va=? AND target_va=? ORDER BY pc',
                                    (owner, target))]
    set_action_to_generic = [
        {'pc': f'0x{r["pc"]:x}', 'target': f'0x{r["target_va"]:x}',
         'instruction': r['instruction'], 'owner_va': None}
        for r in db.execute('SELECT pc,target_va,instruction FROM direct_calls '
                            'WHERE pc=? AND target_va=?', (0x32e328, 0xeff7f0))
    ]
    generic_to_set_loan = calls(0xeff7f0, 0xeaf1c0)
    set_loan_refs = [{'string_va': f'0x{r["string_va"]:x}', 'text': r['text']}
                     for r in db.execute('SELECT DISTINCT string_va,text FROM string_refs '
                                          'WHERE function_va=? ORDER BY string_va', (0xeaf1c0,))]
    db.close()
    assert len(set_action_to_generic) == 1 and len(generic_to_set_loan) == 1
    assert {r['text'] for r in set_loan_refs} == {
        'SetLoan', 'CurLoan', 'RepayMoney', 'IsRepayByDeposit'}

    result = {
        'scope': 'Player house upgrade request levels, loan amounts set in the after-remodel flow, and repayment/finish flow hooks.',
        'status_by_subtopic': {
            'loan_amount_by_house_level': 'proven in EventFlow',
            'upgrade_request_order_by_house_level': 'proven in EventFlow',
            'repayment_demo_and_finish_flags': 'proven as EventFlow sequence; PlayerHasLoan result meaning not decoded here',
            'calendar_day_or_elapsed_time_for_upgrade': 'open',
            'native_setloan_handler': 'static chain linked to the registered PlayerSetLoan vtable; not dynamically emulated',
        },
        'sources': {
            'eventflows': chart_evidence,
            'elf': {'path': str(ELF), 'sha256': sha256(ELF)},
            'index_sqlite': {'path': str(DB), 'sha256': sha256(DB), 'read_only': True},
        },
        'upgrade_requests_by_current_player_house_level': {
            str(level): house_order[level] for level in sorted(house_order)
        },
        'loan_actions_by_player_house_level_in_after_remodel_root': {
            str(level): {
                'bells': amount,
                'event_index': next(a['event_index'] for a in loan_actions
                                    if next(c['case'] for c in a['conditions']
                                            if c['query'].endswith('PlayerHouseLevel')) == level),
                'conditions': next(a['conditions'] for a in loan_actions
                                   if next(c['case'] for c in a['conditions']
                                           if c['query'].endswith('PlayerHouseLevel')) == level),
            } for level, amount in sorted(loan_by_level.items())
        },
        'native_binding': {
            'event_action': 'EventFlowSystemActor.EventFlowActionPlayerSetLoan',
            'parameters': handler['parameters'],
            'vtable_method_candidate': f'0x{method_va:x}',
            'vtable_method_slot_index': 11,
            'slot_role_status': 'unresolved in event_handlers_resolved.json',
            'direct_call_chain': set_action_to_generic + generic_to_set_loan,
            '0xeaf1c0_string_refs': set_loan_refs,
            'interpretation_limit': 'String references show loan-related property names; helper internals and save writes were not executed in this stage.',
        },
        'repayment_flow': {
            'atm_reserves_get_finish_loan_demo': atm_demo,
            'finish_demo_writes': [a for a in demo_actions if a['action'] in {
                'EventFlowActionEventFlagSystemOn', 'EventFlowActionEventFlagSystemOff',
                'EventFlowActionEventFlagSystemAdd'}],
            'finish_talk_clears_playerloanfinish1st': len(finish_writes) > 0,
            'finish_talk_sets_pchousingloanfinish': len(final_loan_flag) > 0,
            'note': 'The flow contains PlayerLoanRepaying and PlayerHasLoan gates; branch result semantics for PlayerHasLoan are not asserted.',
        },
        'timing_limit': {
            'after_remodel_gate': 'SNPC_rco_03_ChkAfterRemodel:Root reads cPlayer:RcoAfterHouseRemodel ON before PlayerHouseLevel and loan branches.',
            'on_writer_in_eventflow': False,
            'open': 'The extracted flows show the request flag and after-remodel dialogue, but not which calendar day the native house rebuild sets RcoAfterHouseRemodel.',
        },
        'rules': [
            'PlayerHouseLevel 1..7 selects cHouse:HouseOrder1..7 when the player orders an upgrade.',
            'In SNPC_rco_03_ChkAfterRemodel:Root, PlayerHouseLevel 2..8 selects PlayerSetLoan Bells 98,000; 198,000; 348,000; 548,000; 758,000; 1,248,000; 2,498,000, respectively.',
            'The PlayerSetLoan action registration declares Bells as an int. Static native calls from its registered vtable method candidate reach 0xeff7f0 then 0xeaf1c0; 0xeaf1c0 references SetLoan, CurLoan, RepayMoney, IsRepayByDeposit.',
        ],
        'limits': [
            'Amounts are the Bell values supplied by EventFlow; this stage did not execute the EventFlow action or verify persistent save storage.',
            'RcoAfterHouseRemodel has EventFlow OFF writers but no EventFlow ON writer, so the calendar rebuild completion trigger remains open.',
            'The PlayerHasLoan query branch is preserved as a flow condition; its native result mapping is not established here.',
        ],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'artifact': str(OUT), 'loan_levels': len(loan_by_level),
                      'upgrade_orders': len(house_order),
                      'romfs_flow_hashes': {k: v['sha256'] for k, v in chart_evidence.items()},
                      'main_elf_sha256': result['sources']['elf']['sha256']}, indent=2))


if __name__ == '__main__':
    main()
