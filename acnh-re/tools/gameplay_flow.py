#!/usr/bin/env python3
"""Index gameplay progression evidence from decoded EventFlow, flag tables and messages.

Inputs (all produced by the existing pipeline / ZIP bundles, nothing is inferred):
  output/manifest.json                 BFEVFL entries and their decoded JSON
  output/decoded/*.json                decoded flowcharts (actors, events, entry points)
  output/tables_resolved/EventFlags*   flag definitions (Key, Japanese Name, access policy)
  output/additional_romfs/messages/USen/*.json   message text (optional)

Outputs (output/gameplay/):
  flag_index.json      every flag: table row, EventFlow writers (with path conditions) and readers
  flow_index.json      every flowchart/entry point: subflow calls, flag reads/writes, notable actions
  milestones.json      the progression flags listed in MILESTONES with resolved evidence
  trees/*.txt          readable trees of the progression flows in KEY_FLOWS
  summary.json         counts and the bool-case self check

Usage:
  python tools/gameplay_flow.py [--output-root DIR] [--with-text] build
  python tools/gameplay_flow.py [--output-root DIR] [--with-text] tree SNPC_rco_53_MigrantsQuest [--entry Root]

Committed outputs keep MessageIDs only. --with-text adds USen text from your own extraction.

Path conditions come from a bounded walk of each entry point. Only switch branches that test
game state are kept (flags, facility levels, environment, items). Player dialogue choices,
random choices and subflow results are not conditions and are dropped. Subflows are recorded
as calls, not inlined, so conditions of the caller are not propagated into the callee.
"""
import argparse
import collections
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

FLAG_TABLES = {
    'cLand': 'EventFlagsLandParam', 'cLandTemp': 'EventFlagsLandTempParam',
    'cPlayer': 'EventFlagsPlayerParam', 'cPlayerTemp': 'EventFlagsPlayerTempParam',
    'cPlayerVisit': 'EventFlagsPlayerVisitParam', 'cNpcSave': 'EventFlagsNpcSaveParam',
    'cNpcTemp': 'EventFlagsNpcTempParam', 'cNpcMemory': 'EventFlagsNpcMemoryParam',
    'cHouse': 'EventFlagsHouseParam',
    'cLifeSupportAchievement': 'EventFlagsLifeSupportAchievementParam',
    'cLifeSupportDaily': 'EventFlagsLifeSupportDailyParam',
}
WRITE_OPS = {
    'EventFlowActionEventFlagSystemOn': 'on', 'EventFlowActionEventFlagSystemOff': 'off',
    'EventFlowActionEventFlagSystemSet': 'set', 'EventFlowActionEventFlagSystemAdd': 'add',
    'EventFlowActionEventFlagNpcOn': 'on', 'EventFlowActionEventFlagNpcOff': 'off',
    'EventFlowActionEventFlagNpcSet': 'set', 'EventFlowActionEventFlagNpcAdd': 'add',
}
READ_QUERIES = {
    'EventFlowQueryEventFlagSystemBool', 'EventFlowQueryEventFlagSystemInt',
    'EventFlowQueryEventFlagNpcBool', 'EventFlowQueryEventFlagNpcInt',
}
# Interactive or random branches: they select dialogue, they are not prerequisites.
NON_CONDITION = re.compile(r'EventFlowQuery(GeneralTalkChoice|RandomChoice|PercentChoice|'
                           r'SubflowResultChoice|UIResult|IsSamePhrase|CheckEntryVariable|'
                           r'UIPocketMenu|UICheck|NpcSelect)')
NOTABLE_ACTIONS = re.compile(r'(RequestChangeStage|MailSend|SmartPhone$|SetCraftRecipe|SetItemToPocket|'
                             r'Structure|Build|Ceremony|Unlock|Museum|Loan|Money|Demo|Movie|'
                             r'Quest|Npc(MoveIn|MoveOut|Delivery)|SetRewardRecipe|PublicAnnouncement)')

# Progression flags whose evidence is resolved into milestones.json. The list only selects
# which rows to summarise; every statement in the output comes from the data.
MILESTONES = [
    ('prolog', ['cPlayer:DoneCharacterCreation', 'cLand:Prologue4BuiltPlayer', 'cLand:Prologue4BuiltNpcAN',
                'cLand:Prologue4BuiltNpcHA', 'cPlayer:PrologueForCampfire1', 'cPlayer:PrologueForCampfire2',
                'cPlayer:HaveTownFruit4CampFire', 'cPlayer:PrologueStartedCampfire', 'cLandTemp:PrologueStartedCampfire',
                'cPlayer:PrologueFinishTkkDream', 'cLand:FinishiPC1Prologue', 'cPlayer:PcMaingameStart']),
    ('awal_game', ['cPlayer:RcoTentEnableDIYtrial', 'cPlayer:RcoFinishMakingAxe', 'cPlayer:RcoPaid1stCharge',
                   'cPlayer:RcoTentDonation', 'cPlayer:EnableBuildMuseumTent', 'cPlayer:RcoTookRequestMuseum',
                   'cPlayer:DecidedMuseumTentPlace', 'cLand:MuseumBuilt', 'cLand:OwlTentExplainFor1P',
                   'cPlayer:MainmenuRecipe', 'cPlayer:MainmenuEncyclopedia', 'cPlayer:MainmenuMap']),
    ('rumah', ['cPlayer:RcoOrderedHouseBuilt', 'cPlayer:PlayerLoanRepaying', 'cPlayer:PlayerLoanFinish1st',
               'cPlayer:RcoHeardRemodel1', 'cPlayer:PcHousingLoanFinish']),
    ('toko', ['cPlayer:RcmTookQuestReq', 'cLand:RcmShopMaterial_Wood', 'cLand:RcmShopMaterial_HardWood',
              'cLand:RcmShopMaterial_SoftWood', 'cLand:RcmShopMaterial_Iron', 'cLand:RcmShopMaterialComplete',
              'cLand:EnableMarketBuild', 'cPlayer:RcmTookReqMarket', 'cLand:MarketConstruction1', 'cLand:MarketBuilt',
              'cLand:MarketRemodelingFlag1', 'cLand:MarketOpen1stDay1', 'cLand:MarketRemodelingFlag2',
              'cLand:MarketConstruction2', 'cLand:Market2Built']),
    ('museum', ['cLand:DonationAmountForMuseum', 'cLand:MuseumGrowupEnable1', 'cLand:MuseumConstruction1',
                'cLand:Museum2Built', 'cLand:DoneMuseumConstruction', 'cLand:MuseumFossilComplete']),
    ('penjahit', ['cLand:EnableHghStayField', 'cLand:CountTailorBuild', 'cLand:EnableTailorBuild',
                  'cLand:TailorGetHousingkit', 'cLand:TailorReserved', 'cLand:TailorConstruction1', 'cLand:TailorBuilt']),
    ('rumah_villager_baru', ['cLand:RcmImmQuestOpen', 'cLand:RcmImmQuestRunning', 'cLand:ImmQ_SetBridge',
                             'cLand:ImmQ_A_GetHousing', 'cLand:ImmQ_A_SetHousing', 'cLand:ImmQ_A_Interior1Donate',
                             'cLand:ImmQ_A_Outdoor1Set', 'cLand:ImmQ_A_Complete', 'cLand:ImmQ_A_Invited',
                             'cLand:RcmImmQuestComplete', 'cPlayer:ImmQGetQuestPrize']),
    ('resident_services', ['cLand:EnableBuildTownOffice', 'cLand:StartBuildingTownOffice', 'cLand:RcoNoticeBuildInfomationOffice',
                           'cLand:OfficeConstruction1', 'cLand:BuiltTownOffice', 'cPlayer:SzaTaled1stTime']),
    ('pengembangan_pulau', ['cLand:IslandDevQuestRunning', 'cLand:RcoBuildCampsiteOngoing', 'cLand:RcoBuildCampsiteComplete',
                            'cLand:CampSiteBuilt', 'cLand:RcoMeetFirstVisitorRequest', 'cLand:RcoMeetFirstVisitorComplete',
                            'cLand:RcoBuildFirstVisitorsHousingKitComplete', 'cLand:IslandDevQuestComplete',
                            'cLand:CeremonyBuildBridge', 'cLand:CeremonyBuildSlope', 'cLand:BridgeBuilt', 'cLand:SlopeBuilt']),
    ('penilaian_dan_kk', ['cLand:IslandEvaluationUnlock', 'cPlayer:IslandEvaluationUnlockMyself',
                          'cLand:IslandEvaluationClearTkkLive', 'cLand:TkkFirstLiveEnable', 'cLand:TkkFirstLiveReserved',
                          'cLand:TkkFirstLive', 'cLand:TkkFirstLiveSubPlayer', 'cPlayer:MainmenuConstructLicense', 'cPlayer:PcTownmakeLv']),
]


def load(p):
    return json.loads(Path(p).read_text())


def label(v):
    if isinstance(v, dict) and 'labels' in v:
        return v['labels'][0]
    return v


def flag_definitions(out):
    defs = {}
    for prefix, table in FLAG_TABLES.items():
        p = out/'tables_resolved'/f'{table}.json'
        if not p.exists():
            continue
        t = load(p)
        cols = [c['name'] or 'h_'+c['hash'] for c in t['columns']]
        for row in t['rows']:
            r = dict(zip(cols, row))
            key = r.get('Key')
            if not isinstance(key, str):
                continue
            defs[f'{prefix}:{key}'] = {
                'table': table, 'source_id': t.get('source_id'), 'name_ja': r.get('Name'),
                'max': r.get('MaxValue') if 'MaxValue' in r else r.get('MaxValue1'),
                'default': r.get('DefaultValue'),
                'flow_access': label(r.get('FlagsFlowAccess')),
                'net_access': label(r.get('FlagsNetAccess')),
                'reset_policy_raw': {k: label(v) for k, v in r.items() if k in ('h_fdb1f290', 'h_5140e4b4', 'h_3c7fb88f', 'h_bed25a86')},
            }
    return defs


class Messages:
    TAG = re.compile(r'\[/?tag[^\]]*\]')

    def __init__(self, root, enabled=True):
        self.text = {}
        if not enabled or not root.exists():
            return
        for f in root.glob('*.json'):
            arch = f.stem
            for member, m in load(f)['members'].items():
                base = member[:-5] if member.endswith('.msbt') else member
                for msg in m.get('messages', []):
                    for lab in msg.get('labels') or []:
                        self.text[f'{arch}/{base}:{lab}'] = msg.get('text') or ''

    def get(self, mid):
        t = self.text.get(mid)
        if t is None:
            return None
        return re.sub(r'\s+', ' ', self.TAG.sub('', t)).strip()


def describe_switch(actor, e):
    q = actor['queries'][e['query']]
    p = e.get('params') or {}
    return q, p


def walk_entry(fc, start, max_states=40000, max_sets=4):
    """Bounded DFS. Returns per-event list of distinct condition tuples and the last message seen."""
    events = fc['events']
    seen = set()
    reach = collections.defaultdict(list)
    stack = [(start, (), None)]
    states = 0
    truncated = False
    while stack:
        idx, conds, last_msg = stack.pop()
        if idx is None or idx < 0 or idx >= len(events):
            continue
        key = (idx, conds)
        if key in seen:
            continue
        seen.add(key)
        states += 1
        if states > max_states:
            truncated = True
            break
        if len(reach[idx]) < max_sets and all(c != conds for c, _ in reach[idx]):
            reach[idx].append((conds, last_msg))
        e = events[idx]
        t = e['type']
        if t == 'action':
            p = e.get('params') or {}
            stack.append((e.get('next'), conds, p.get('MessageID', last_msg)))
        elif t == 'switch':
            actor = fc['actors'][e['actor']]
            q, p = describe_switch(actor, e)
            for case in e.get('cases') or []:
                if NON_CONDITION.match(q):
                    nc = conds
                else:
                    c = (q.replace('EventFlowQuery', ''), json.dumps(p, sort_keys=True, ensure_ascii=False), case['value'])
                    nc = tuple(sorted(set(conds) | {c}))
                    if len(nc) > 12:
                        nc = conds
                stack.append((case['event'], nc, last_msg))
        elif t in ('subflow', 'join'):
            stack.append((e.get('next'), conds, last_msg))
        elif t == 'fork':
            for f in e.get('forks') or []:
                stack.append((f, conds, last_msg))
            stack.append((e.get('join'), conds, last_msg))
    return reach, truncated


BOOL_CASE_EVIDENCE = ('Tutorials_Prologue_Rco event 9: case 1 explains the 10 branches and then turns '
                      'PrologueForCampfire1 on, case 0 moves on to PrologueForCampfire2; '
                      'SNPC_rco_01_Tent_1_Entries event 17: case 0 (fee paid) calls SNPC_rco_10_Common_AboutMyHome. '
                      'bool_case_self_check in summary.json repeats the test for every writer.')


def cond_json(conds):
    out = []
    for q, p, v in conds:
        p = json.loads(p)
        if q.startswith('EventFlag') and 'AccessKey' in p:
            c = {'flag': p['AccessKey'], 'query': q, 'case': v}
            if q.endswith('Bool'):
                # Case 0 is the ON branch, case 1 the OFF branch (see BOOL_CASE_EVIDENCE).
                c['state'] = {0: 'on', 1: 'off'}.get(v, v)
            else:
                c['value'] = v
            out.append(c)
        else:
            out.append({'query': q, 'params': p, 'value': v})
    return out


def build(out, with_text=False):
    manifest = load(out/'manifest.json')['entries']
    defs = flag_definitions(out)
    msgs = Messages(out/'additional_romfs/messages/USen', with_text)
    flags = collections.defaultdict(lambda: {'writers': [], 'readers': []})
    flows = {}
    truncated_entries = []
    for ent in manifest:
        if ent['format'] != 'BFEVFL':
            continue
        doc = load(out/ent['decoded'])['data']
        for fc in doc['flowcharts']:
            name = fc['name']
            finfo = {'source': ent['source'], 'source_id': ent['id'], 'entries': {}}
            for ep_name, ep in fc['entry_points'].items():
                reach, truncated = walk_entry(fc, ep['main_event'])
                if truncated:
                    truncated_entries.append(f'{name}:{ep_name}')
                einfo = {'subflow_calls': [], 'flag_writes': [], 'flag_reads': [], 'notable_actions': [],
                         'first_messages': [], 'walk_truncated': truncated}
                for idx in sorted(reach):
                    e = fc['events'][idx]
                    variants = reach[idx]
                    conds0, last_msg = variants[0]
                    p = e.get('params') or {}
                    if e['type'] == 'subflow':
                        einfo['subflow_calls'].append({'event': idx, 'flowchart': e.get('flowchart') or name,
                                                       'entry_point': e.get('entry_point')})
                    elif e['type'] == 'action':
                        a = fc['actors'][e['actor']]['actions'][e['action']]
                        if 'MessageID' in p and len(einfo['first_messages']) < 3:
                            einfo['first_messages'].append({'id': p['MessageID'], 'text_USen': msgs.get(p['MessageID'])})
                        if a in WRITE_OPS and 'AccessKey' in p:
                            op = WRITE_OPS[a]
                            val = 1 if op == 'on' else 0 if op == 'off' else p.get('SetNum', p.get('AddNum', p.get('Value')))
                            ordered = sorted(variants, key=lambda v: len(v[0]))
                            w = {'flow': name, 'entry': ep_name, 'event': idx, 'op': op, 'value': val,
                                 'conditions': [cond_json(c) for c, _ in ordered],
                                 'preceding_message': last_msg, 'preceding_text_USen': msgs.get(last_msg) if last_msg else None}
                            flags[p['AccessKey']]['writers'].append(w)
                            einfo['flag_writes'].append({'flag': p['AccessKey'], 'op': op, 'value': val, 'event': idx})
                        elif NOTABLE_ACTIONS.search(a.replace('EventFlowAction', '')):
                            einfo['notable_actions'].append({'event': idx, 'action': a.replace('EventFlowAction', ''),
                                                             'params': {k: v for k, v in p.items() if k not in ('IsCloseMessageWindow',)}})
                    elif e['type'] == 'switch':
                        q = fc['actors'][e['actor']]['queries'][e['query']]
                        if q in READ_QUERIES and 'AccessKey' in p:
                            flags[p['AccessKey']]['readers'].append({'flow': name, 'entry': ep_name, 'event': idx,
                                                                     'cases': [c['value'] for c in e.get('cases') or []]})
                            einfo['flag_reads'].append(p['AccessKey'])
                einfo['flag_reads'] = sorted(set(einfo['flag_reads']))
                finfo['entries'][ep_name] = einfo
            flows[name] = finfo
    # callers of each flow
    callers = collections.defaultdict(set)
    for name, f in flows.items():
        for ep, e in f['entries'].items():
            for c in e['subflow_calls']:
                if c['flowchart'] != name:
                    callers[c['flowchart']].add(f'{name}:{ep}')
    for name in flows:
        flows[name]['called_from'] = sorted(callers.get(name, ()))
    flag_index = {}
    for key in sorted(set(defs) | set(flags)):
        f = flags.get(key, {'writers': [], 'readers': []})
        d = defs.get(key)
        flag_index[key] = {
            'definition': d,
            'eventflow_writers': f['writers'],
            'eventflow_readers': sorted({f"{r['flow']}:{r['entry']}" for r in f['readers']}),
            'writer_status': ('eventflow' if f['writers'] else
                              'no_eventflow_writer; written by native code or never written in 1.0.0 (unproven)'),
        }
    return flows, flag_index, defs, truncated_entries


def bool_self_check(flag_index):
    """An 'on' write guarded by a test of the same flag should sit on the OFF branch."""
    tally = collections.Counter()
    for key, f in flag_index.items():
        for w in f['eventflow_writers']:
            if w['op'] not in ('on', 'off'):
                continue
            states = {c.get('state') for conds in w['conditions'][:1] for c in conds if c.get('flag') == key}
            if len(states) == 1:
                tally[f"write_{w['op']}_guarded_by_{states.pop()}"] += 1
    return dict(tally)


def milestones(flag_index):
    result = []
    for phase, keys in MILESTONES:
        rows = []
        for k in keys:
            f = flag_index.get(k)
            if not f:
                rows.append({'flag': k, 'status': 'flag_not_found'})
                continue
            d = f['definition'] or {}
            rows.append({
                'flag': k, 'name_ja': d.get('name_ja'), 'flow_access': d.get('flow_access'), 'max': d.get('max'),
                'writer_status': f['writer_status'],
                'writers': [{'flow': w['flow'], 'entry': w['entry'], 'op': w['op'], 'value': w['value'],
                             'conditions': w['conditions'][:2], 'preceding_message': w['preceding_message'],
                             'preceding_text_USen': w['preceding_text_USen']}
                            for w in f['eventflow_writers'][:6]],
                'writer_count': len(f['eventflow_writers']),
                'readers': f['eventflow_readers'][:12], 'reader_count': len(f['eventflow_readers']),
            })
        result.append({'phase': phase, 'flags': rows})
    return result


# Flows whose readable trees are written to output/gameplay/trees/ by `build`.
KEY_FLOWS = [
    'System_BootSequence', 'System_Title', 'System_GrowUp', 'System_GrowUp_GameProcess',
    'Tutorials_Prologue1_Areacheck', 'Tutorials_Prologue1_Charactermaking', 'Tutorials_Prologue2_Arrival',
    'Tutorials_Prologue3_Orientation1', 'Tutorials_Prologue4_Orientation2_RcmRct', 'Tutorials_Prologue4_Orientation3',
    'Tutorials_Prologue5_Campfire', 'Tutorials_Prologue_Rco', 'Tutorials_Prologue_Tkk', 'SNPC_rco_00_StartMainGame',
    'AI_NPC_Rco', 'SNPC_rco', 'SNPC_rco_01_Tent_1_Entries', 'SNPC_rco_51_DonationReward', 'SNPC_rco_52_DonationRewardEntries',
    'SNPC_owl_11_Tent_Entries', 'SNPC_owl_12_Tent_FirstTimeTalk', 'SNPC_rcm_01_Tent_1_Entries', 'SNPC_rcm_21_MaterialCollecting',
    'SNPC_rcm_24_MaterialGiveProcess', 'SNPC_rcm_03_RenualOpen', 'SNPC_hgh_00_Peddler', 'Player_Demo_HousingFinish',
    'Demo_PublicAnnouncement', 'Demo_PublicAnnouncement_00_Cmn', 'Demo_PublicAnnouncement_03_Rco_Once',
    'Demo_PublicAnnouncement_13_Sza_Once', 'Demo_PublicAnnouncement_21_CmnEvChk', 'Demo_PublicAnnouncement_Process',
    'SNPC_rco_53_MigrantsQuest', 'Obj_ReservedPlaceBox', 'System_MigrantsQuestProcess', 'SNPC_rco_01_Office_1_Entries',
    'SNPC_rco_54_IslandDevelopment', 'SNPC_rco_05_ChkCeremony', 'SNPC_sza_50_IslandEvaluation', 'System_IslandEvaluationCheck',
    'SNPC_tkk_Live', 'SNPC_rco_55_TkkFirstLive', 'SNPC_rco_02_SelRoofColor', 'SNPC_rco_10_Common_UpgradeMyhome',
    'SNPC_rco_04_ChkFinishLoan', 'SNPC_owl_01_Museum_Donation', 'Player_GetDemo_Once', 'Player_ToolBreak', 'SNPC_gul',
    'NNPC_GEvent_CatchFishFes', 'NNPC_GEvent_CatchInsectFes', 'NNPC_GEvent_Countdown', 'SNPC_doc_50_MysteryTour',
]
QUIET_ACTIONS = {'TurnNeck', 'TurnBody', 'WaitFrame', 'SetDefaultWaitAs', 'CharacterEmoticonAction', 'SoundTriggerEmit',
                 'SmartPhoneSE', 'SoundDuckingOn', 'SoundDuckingOff', 'SwapSpeaker', 'NpcChangeHeadCtrlMode'}


def flow_paths(out):
    return {Path(x['source']).stem: out/x['decoded'] for x in load(out/'manifest.json')['entries'] if x['format'] == 'BFEVFL'}


def render_tree(out, flow, entries=None, msgs=None, max_lines=20000, with_text=False):
    """Readable indented rendering of one flowchart. Bool flag cases are shown as ON/OFF.

    Message lines show the MessageID; with_text adds the USen text from a local extraction."""
    msgs = msgs or Messages(out/'additional_romfs/messages/USen', with_text)
    fc = load(flow_paths(out)[flow])['data']['flowcharts'][0]
    ev = fc['events']
    lines = [f'# {flow} (source: decoded EventFlow; bool flag case 0 = ON, case 1 = OFF; #N = event index)']

    def emit(text):
        if len(lines) >= max_lines:
            raise StopIteration
        lines.append(text)

    def show(j, ind, seen):
        while j is not None:
            if j in seen:
                emit(f'{ind}-> (#{j})')
                return
            seen.add(j)
            x = ev[j]
            t = x['type']
            pr = x.get('params') or {}
            if t == 'action':
                a = fc['actors'][x['actor']]['actions'][x['action']].replace('EventFlowAction', '')
                if a not in QUIET_ACTIONS:
                    if 'MessageID' in pr:
                        text = msgs.get(pr['MessageID'])
                        emit(f'{ind}#{j} MSG {pr["MessageID"]}' + (f' "{text[:160]}"' if text else ''))
                    else:
                        emit(f'{ind}#{j} {a} {json.dumps(pr, ensure_ascii=False)}')
                j = x.get('next')
            elif t == 'switch':
                q = fc['actors'][x['actor']]['queries'][x['query']].replace('EventFlowQuery', '')
                emit(f'{ind}#{j} IF {q} {json.dumps(pr, ensure_ascii=False)}')
                for c in x.get('cases') or []:
                    lab = c['value']
                    if q.startswith('EventFlag') and q.endswith('Bool'):
                        lab = {0: 'ON', 1: 'OFF'}.get(lab, lab)
                    emit(f'{ind}  case {lab}:')
                    show(c['event'], ind + '    ', seen)
                return
            elif t == 'subflow':
                emit(f'{ind}#{j} CALL {x.get("flowchart") or flow}:{x.get("entry_point")}' + (f' {json.dumps(pr, ensure_ascii=False)}' if pr else ''))
                j = x.get('next')
            elif t == 'fork':
                emit(f'{ind}#{j} FORK')
                for f in x.get('forks') or []:
                    show(f, ind + '  || ', seen)
                j = x.get('join')
            else:
                j = x.get('next')

    try:
        for name, ep in fc['entry_points'].items():
            if entries and name not in entries:
                continue
            emit(f'== ENTRY {name}')
            show(ep['main_event'], '  ', set())
    except StopIteration:
        lines.append('... (truncated)')
    return '\n'.join(lines) + '\n'


def cmd_build(out, with_text=False):
    flows, flag_index, defs, truncated = build(out, with_text)
    dest = out/'gameplay'
    dest.mkdir(exist_ok=True)
    meta = {'schema': 'acnh-re/gameplay/1', 'game_version': '1.0.0', 'bool_case_rule': 'case 0 = on, case 1 = off',
            'bool_case_evidence': BOOL_CASE_EVIDENCE,
            'inputs': ['manifest.json', 'decoded/ (BFEVFL)', 'tables_resolved/EventFlags*', 'additional_romfs/messages/USen'],
            'condition_policy': 'switch branches on game state only; dialogue choice/random/subflow-result branches dropped; subflows not inlined',
            'truncated_entry_walks': truncated,
            'message_text_included': with_text}

    def dump(name, data):
        (dest/name).write_text(json.dumps({'meta': meta, 'data': data}, ensure_ascii=False, indent=1) + '\n')
    dump('flow_index.json', flows)
    dump('flag_index.json', flag_index)
    dump('milestones.json', milestones(flag_index))
    trees = dest/'trees'
    trees.mkdir(exist_ok=True)
    msgs = Messages(out/'additional_romfs/messages/USen', with_text)
    paths = flow_paths(out)
    for flow in KEY_FLOWS:
        if flow in paths:
            (trees/f'{flow}.txt').write_text(render_tree(out, flow, msgs=msgs))
    summary = {
        'flowcharts': len(flows),
        'entry_points': sum(len(f['entries']) for f in flows.values()),
        'flag_definitions': len(defs),
        'flags_referenced_by_eventflow': sum(1 for k, f in flag_index.items() if f['eventflow_writers'] or f['eventflow_readers']),
        'flags_with_eventflow_writer': sum(1 for f in flag_index.values() if f['eventflow_writers']),
        'flags_defined_without_eventflow_writer': sum(1 for k, f in flag_index.items() if f['definition'] and not f['eventflow_writers']),
        'flags_referenced_but_undefined': sorted(k for k, f in flag_index.items() if not f['definition']),
        'truncated_entry_walks': len(truncated),
        'bool_case_self_check': bool_self_check(flag_index),
        'trees_written': sorted(f for f in KEY_FLOWS if f in paths),
        'trees_missing': sorted(f for f in KEY_FLOWS if f not in paths),
    }
    (dest/'summary.json').write_text(json.dumps({'meta': meta, 'summary': summary}, ensure_ascii=False, indent=1) + '\n')
    print(json.dumps({k: v for k, v in summary.items() if k != 'trees_written'}, ensure_ascii=False, indent=1))


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--output-root', default=str(ROOT/'output'), help='folder that holds manifest.json and decoded/')
    sub = ap.add_subparsers(dest='cmd')
    ap.add_argument('--with-text', action='store_true',
                    help='include USen message text (local use; committed outputs keep MessageIDs only)')
    sub.add_parser('build', help='write output/gameplay/ (default)')
    t = sub.add_parser('tree', help='print a readable tree of one EventFlow')
    t.add_argument('flow', help='flowchart name, e.g. SNPC_rco_53_MigrantsQuest')
    t.add_argument('--entry', action='append', help='only these entry points (repeatable)')
    args = ap.parse_args()
    out = Path(args.output_root)
    if args.cmd == 'tree':
        print(render_tree(out, args.flow, args.entry, with_text=args.with_text), end='')
    else:
        cmd_build(out, args.with_text)


if __name__ == '__main__':
    main()
