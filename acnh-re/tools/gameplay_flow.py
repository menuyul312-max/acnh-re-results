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
  native_flag_refs.json  flags without an EventFlow writer -> native functions that reference the
                       flag name string (output/index.sqlite string_refs), membership in the
                       day-change dispatcher 0xf545f0, and manual pseudocode readings
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
import sqlite3
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


# Native day-change driver and facility dispatcher (ELF VA). Callee order comes from index.sqlite direct_calls.
DAY_CHANGE_DRIVER = 0xf53a70
DAY_CHANGE_DISPATCHER = 0xf545f0
# Readings of automated pseudocode (binary/analysis_decomp/<va>.c, Ghidra base ELF+0x100000) with
# string operands resolved. Not executed; flag accessors 0xf44d90 (get bool), 0xf44ad0 (get int),
# 0xf44e70 (set), 0xf45380 (increment) are inferred from their use with flag-name strings.
VISITOR_CODES = {'0': 'non', '1': 'gul', '2': 'hgc', '3': 'cml', '4': 'gst', '5': 'hgh', '6': 'bey', '7': 'chy', '8': 'skk', '9': 'ows',
                 'source': "rodata list 'non,gul,hgc,cml,gstA,hgh,bey,chy,skk,ows' (0xfdcf60); 0xc6f1a0 spawns 1-3 and 5-8"}
# Layout of the 0x78-byte special-visitor schedule member (descriptor 0x33d50a8, save +0x20a210), from 0xfd8a80/0xfda740/0xfdbf60.
VISITOR_SCHEDULE = {
    'member': {'descriptor': '0x33d50a8', 'save_offset': '0x20a210', 'size': '0x78'},
    'fields': {'0x00': 'u32 codes[7], index = nn::time day of week (0 Sunday .. 6 Saturday)',
               '0x1c': 'f32[3] spawn position of today\'s visitor (0xfda740)', '0x28': 'f32[3] second spawn spot (0xfda740)',
               '0x44': 'u32 copy[7] of codes as generated', '0x60': 'u8 carry_over[14], indexed by code',
               '0x70': 'i32 wisp_extra_day or -1', '0x74': 'i32 celeste_day or -1'},
    'writer': '0xfd8a80 (via 0xfd8920 from dispatcher 0xf545f0)', 'validator': '0xfd9620',
    'week': 'Monday 05:00 to Monday 05:00',
    'order': ['Mabel (tailor < 2): Sat, Sun, 1 weekday', 'Saharah: 1 weekday', 'Kicks (tailor >= 2): 1 weekday',
              'pool, carry-over first: Label (tailor >= 2), C.J./Flick (BuiltTownOffice), Gulliver (museum >= 2)',
              'Celeste day (museum > 2): Fine00 day, else Fine02/04/06', 'Wisp: remaining weekdays (max 5), else extra day; then Sat/Sun if free'],
    'evidence': '[PSEUDO] pseudocode + disassembly, not executed',
}
PSEUDOCODE_READINGS = {
    '0xf77050': {'role': 'museum facility state at day change (states 0-4, param_2 = elapsed days)',
                 'reading': ['state 1 + structure kind 2 present -> state 2; MuseumBuilt=1; MuseumTentBuiltToday=1 if exactly 1 day',
                             'state 2: MuseumGrowupEnable1 on -> cleared and construction starts; otherwise needs MuseumConstruction1>=1',
                             'MuseumConstruction1 + elapsed days < 2 -> increment (value 1 sets MuseumConstructionToday)',
                             'otherwise state 3; MuseumConstruction1=0; Museum2Built=1; Museum2BuiltToday=1 if exactly 1 day']},
    '0xfcc300': {'role': 'tailor facility state at day change',
                 'reading': ['state 1: TailorConstruction1 off -> needs structure kind 5 present; else needs TailorConstruction1>=1',
                             'TailorConstruction1 + elapsed days < 2 -> increment',
                             'otherwise state 2; TailorConstruction1=0; TailorBuilt=1; TailorBuiltToday=1 if exactly 1 day']},
    '0xfc4560': {'role': 'shop facility state at day change (calls 0xfcc300)',
                 'reading': ['state 1 + structure kind 0 present -> state 2; MarketBuilt=1; MarketOpen1stDay1=1 if exactly 1 day',
                             'state 2: second remodel path uses MarketRemodelingFlag2/MarketConstruction2, CountMarket1AfterBuild>30 and an unidentified value >=200000 ((x>>6)>0xc34)',
                             'MarketConstruction2 + elapsed days >= 2 -> state 3; MarketOpen1stDay2=1 if exactly 1 day']},
    '0xf26330': {'role': 'campsite facility state at day change',
                 'reading': ['state 1 + structure kind 6 present -> state 2; CampSiteBuilt=1; CeremonyBuildCampSite=1; CampSiteBuiltToday=1 if exactly 1 day']},
    '0x10c2ad0': {'role': 'Resident Services at day change (called from 0x10c26e0)',
                  'reading': ['OfficeConstruction1 accumulates elapsed days while BuiltTownOffice is off (reset to 0 above 1)',
                              'structure kind 1 present and BuiltTownOffice off -> BuiltTownOffice=1, GlobalEventReady=1, EventPlazaBuilt=1; BuiltTownOfficeToday=1 if exactly 1 day']},
    '0xfd8920': {'role': 'K.K. unlock, weekly visitor schedule and daily resets at day change (dispatcher passes the schedule member)',
                 'reading': ['elapsed days >=1 and IslandEvaluationClearTkkLive on and a second flag off (TkkFirstLive is the other flag string in this function; the call argument is lost in decompilation) -> TkkFirstLiveEnable=1',
                             'then 0xfd8a80 (build the weekly schedule) and 0xfd9620 (validate today\'s entry)',
                             'RctInTent set from the current hour (5..19 -> off)', 'JohnnyRequirePartsNum=5 on day change']},
    '0xfd8a80': {'role': 'weekly special-visitor schedule generator (writer of the 0x78-byte member)',
                 'reading': ['week = Monday 05:00 to Monday 05:00 (0x1fbe10: before 05:00 counts as the previous day; Sunday goes back 6 days). Rebuilds only when the Monday of the previous play time differs from the current one (0x1fbfa0), or when day-change info +0x18 is set (no stored last-play time, i.e. first run)',
                             'clears codes[0..6], copy[0..6] (+0x44) and sets wisp_extra_day (+0x70) and celeste_day (+0x74) to -1',
                             'tailor state (member +0x1f40c8, 0x33d9ea0, clamp 0..2) < 2: Mabel (5) on Saturday (0xfdad10), Sunday (0xfdae20) and one random weekday (0xfda940)',
                             'Saharah (3): one random weekday, always. Tailor state >= 2: Kicks (8) one random weekday',
                             'pool: Label (2) if tailor >= 2; C.J. (6) and Flick (7) if BuiltTownOffice; Gulliver (1) if museum state (member +0x20a168, 0x33d8a08, 0xf77050 states) >= 2. Codes whose carry-over byte +0x60+code is set are placed first, then the rest, each in random order; stops when no weekday is free',
                             'codes that did not fit set their carry-over byte for next week (bytes +0x60..+0x6d are cleared first)',
                             'museum state > 2: celeste_day = random day of this week (Mon..Sun) whose weather pattern name is Fine00; if none, one with Fine02/Fine04/Fine06; days with a calendar event, NormalLive or BirthdayLive are skipped',
                             'Wisp (4): up to 5 more random weekdays; if none fits, wisp_extra_day = a random Mon..Fri that already has a visitor; then Wisp also on Saturday and Sunday when free',
                             'copy[i] = codes[i] (clamped 0..9) at +0x44',
                             'random picks: popcount 0x198b590, n-th set bit 0x198b630, xorshift128 0x19aa0e0 with state from a TLS slot (link to the day seed of 0xf53a70 not checked)']},
    '0xfda940': {'role': 'place a visitor code on a random free weekday',
                 'reading': ['candidates Monday..Friday only (bits 1..5); a day is free when codes[day]==0, no calendar event (0xf0790), not a NormalLive or BirthdayLive day, and day != celeste_day',
                             'uniform pick among free days; writes codes[day]=code; returns 0 when no day is free']},
    '0xfdad10': {'role': 'place a visitor code on Saturday', 'reading': ['codes[6] free, no calendar event or K.K. live that day, celeste_day != 6']},
    '0xfdae20': {'role': 'place a visitor code on Sunday', 'reading': ['codes[0] free, no calendar event or K.K. live that day, celeste_day != 0']},
    '0xfd9620': {'role': 'validate today\'s schedule entry at day change',
                 'reading': ['valid: Gulliver and Wisp always; Saharah needs one of 8 players with value >= 2 (0xef8520, member +0x17cd48 + i*0xe3b8, 0x33dc730, 0..8; same value Harvey uses, likely house level); Mabel needs EnableHghStayField on, tailor state != 2 and no K.K. live; others need no K.K. live (NormalLive/BirthdayLive)',
                             'calendar event or K.K. live (FirstLive/NormalLive/BirthdayLive) today -> code 0',
                             'otherwise an invalid entry is replaced: JohnnyTalkAnyPlayerFlag on -> Wisp (4) for codes 2,3,5,6,7,8,9; flag off and not (shop state >= 2 on Sunday) and museum >= 2 and code != 4 -> Gulliver (1); else 0',
                             'wisp_extra_day or celeste_day == today with a calendar event or K.K. live -> -1']},
    '0xfdbf60': {'role': 'Wisp present today', 'reading': ['no K.K. live today and (codes[today] == 4 or wisp_extra_day == today)']},
    '0xfda740': {'role': 'today visitor spawn position (driver)',
                 'reading': ['1 Gulliver: 0x7ad880; 2/5/8 Label/Mabel/Kicks: offset (+15, 0, +20) from a fixed point; 3/7 Saharah/Flick: random spot 0x7ad9e0; 6 C.J.: 0x7acda0, no spot -> codes[today]=0',
                             'position in floats +0x1c..+0x24, a second spot (0x7ad9e0) in +0x28..+0x30']},
    '0xfdc080': {'role': 'cancel today\'s visitor', 'reading': ['codes[today]=0; wisp_extra_day/celeste_day == today -> -1; SpnVisitMainField=0']},
    '0xfdcf60': {'role': 'visitor code -> label table', 'reading': ["rodata 'non,gul,hgc,cml,gstA,hgh,bey,chy,skk,ows' (0x488ff0 uses the same list with gst)"]},
    '0xf8b460': {'role': 'day type at day change',
                 'reading': ['checks calendar events by name in order FishingConvention, InsectConvention, PlayerBirthday, NpcBirthday, Countdown, NewYear',
                             'normal day with BuiltTownOffice on: per-player ContinuousNormalDay/EarlyOrLate counters and RNG rolls 0-99; purpose not yet identified']},
    '0xfd9d10': {'role': 'special visitors at day change',
                 'reading': ['Gulliver (Johnny*) and Wisp (GstQuest*) quest flags reset/advance',
                             'SpnVisitMainField=1 when a 0-8 value (likely player house level) >=2, ImmQ_A/B/C_Complete on, CommuneIslandAvailable off and VisitedCommune off',
                             'HgcVisitFlagForTailor = (7-slot array[day index] == 2): a weekly slot table, value 2 = Label']},
    '0x419690': {'role': 'EventFlowQueryNpcHouseNum evaluate slot', 'reading': ['returns count < Num, so case 1 = fewer, case 0 = at least Num']},
    '0x3e0b80': {'role': 'EventFlowQueryVillageScoreCheckNatural evaluate slot',
                 'reading': ['returns BorderValue <= score, so case 1 = score at least the border; score is a float at +0x240 of a save object']},
    '0xf53a70': {'role': 'day-change driver',
                 'reading': ['seeds the global RNG 0x35e9510 (Ghidra 0x36e9510) with year*365 + month + day + GrowUpRandomFactor + 0x1934 '
                             '(calendar layout <s16 year,u8 month,u8 day>; GrowUpRandomFactor via 0xf56cb0), discards 8 u32 draws, then runs 0xf545f0',
                             'passes the 0x78-byte special-NPC schedule save member (descriptor 0x33d50a8, save offset +0x20a210) to 0xfd9d10 and 0xfda740 (0xfd0700 gets member +0x1f67f0 instead)',
                             'day-change info: +0 elapsed days, +8 current time, +0x10 previous play time, +0x18 set when no last-play time is stored']},
    '0xc698d0': {'role': 'daily special-NPC spawner (vtable-called)',
                 'reading': ['calls 0xc6eb80 (calendar-event NPCs), 0xc6f1a0 (scheduled visitor, Daisy Mae, K.K.), 0xc6f5d0 (announcement), '
                             '0xc6f990 (Tommy), 0xc6fbb0 (Harvey), 0xc6fd70 (Celeste), 0xc70060 (Wisp)']},
    '0xc6eb80': {'role': 'calendar-event NPC spawner',
                 'reading': ['today event via 0xf4db0/0xf4cb0, spawns up to 10 E_%s_NPC_%d with AI_NPC_%s / AI_NPC_Rco_%s / AI_NPC_Sza_%s flows']},
    '0xc6f1a0': {'role': 'scheduled visitor + Daisy Mae + K.K. spawn',
                 'reading': ['code = 0xfdc020(schedule): 1 gul, 2 hgc, 3 cml, 5 hgh, 6 bey, 7 chy, 8 skk (labels read from rodata); 0/4/9 spawn nothing here (4 Wisp via 0xc70060, Celeste via 0xc6fd70)',
                             'spawn via 0xc728b0(label, flag): flag 1 for hgh/bey/chy, 0 otherwise',
                             'then boc (Daisy Mae) when 0xfdafa0 is true; then tkkA when 0xfdbae0 is true']},
    '0xfdc020': {'role': 'today visitor code', 'reading': ['schedule[weekday index from 0x1fbd50], index clamped 0..6, value clamped 0..9']},
    '0xfdafa0': {'role': 'Daisy Mae today', 'reading': ['a save value (member +0x1f3e98, descriptor 0x33d8a20, likely shop state) >= 2 and weekday index == 0']},
    '0xfdb300': {'role': 'special NPC may appear now',
                 'reading': ['gst (Wisp) and ows (Celeste): only when (hour - 5) > 14, i.e. 20:00-04:59; other labels have other checks']},
    '0xfdb060': {'role': 'K.K. live type today',
                 'reading': ['0 unless TkkFirstLive on; then calendar event FirstLive -> 3, BirthdayLive -> 2, NormalLive -> 1']},
    '0xfdbae0': {'role': 'K.K. performs today', 'reading': ['0xfdb060 non-zero and TkkReturn off']},
    '0xfdb6e0': {'role': 'is special NPC <label> present today (used by 0xcf9cf0 over 7 entries)',
                 'reading': ['ows: not a K.K. day and schedule int +0x74 == weekday index', 'tkk: K.K. day and TkkReturn off',
                             'spn: not a K.K. day, no global event, SpnVisitMainField on', 'gst: 0xfdbf60; boc: further helpers']},
    '0x33c660': {'role': 'EventFlowActionDecideSettlerNpc execute slot',
                 'reading': ['settler save member 0xc0 bytes = 3 entries x 0x3c (plots A/B/C); empty entry -> 0xf8dd70(SettlerType) and 3-byte NPC id stored']},
    '0xf8dd70': {'role': 'pick settler for plot',
                 'reading': ['SettlerType < 3: filter value table 0x29fa1dc = [0, 5, 4]; candidate bitset 0xcd29a0, filter 0xf8de30, pick 0xf8d860']},
    '0xf8de30': {'role': 'settler filter (from disassembly)',
                 'reading': ['row = 0x1665ea0(npc); u16 cache[row] (<=7, else 0) == global 0x35ee080 (the plot value)',
                             'the only 8-value enum in NmlNpcParam is NpcLooks: 0 Boy_normal, 5 Girl_active, 4 Girl_normal (inference)']},
    '0xf8d860': {'role': 'random villager pick (shared by 0xf8dd70, 0xf84f10, 0xf8c540)',
                 'reading': ['removes villagers whose bit is set in the save bitset +0xbaae0 (35 words = 1120 bits)',
                             'popcount candidates (0x198b590), uniform pick with RNG 0x19aa0e0 (u32 * n >> 32), bit lookup 0x198b630']},
    '0xf32fa0': {'role': 'save layout constructor', 'reading': ['builds the accessor tree of save members with their offsets; entry point for save-format RE']},
    '0x10c26e0': {'role': 'structure counters at day change',
                  'reading': ['reads BridgeBuilt/SlopeBuilt and Count*AfterBuild counters for tailor, museum, shop, office, campsite']},
}


def native_refs(out, flag_index):
    db_path = out/'index.sqlite'
    if not db_path.exists():
        return None
    db = sqlite3.connect(db_path)
    callees = [t for (t,) in db.execute('SELECT target_va FROM direct_calls WHERE owner_va=? ORDER BY pc', (DAY_CHANGE_DISPATCHER,))]
    order = list(dict.fromkeys(callees))
    second = {t for c in order for (t,) in db.execute('SELECT target_va FROM direct_calls WHERE owner_va=?', (c,))}
    rows = {}
    for key, f in flag_index.items():
        if f['eventflow_writers'] or not f['definition']:
            continue
        name = key.split(':', 1)[1]
        refs = db.execute('SELECT string_va, function_va FROM string_refs WHERE text=?', (name,)).fetchall()
        funcs = sorted({fn for _, fn in refs if fn})
        rows[key] = {
            'name_ja': f['definition']['name_ja'], 'flow_access': f['definition']['flow_access'],
            'string_va': sorted({hex(s) for s, _ in refs}),
            'referencing_functions': [hex(fn) for fn in funcs],
            'day_change': [hex(fn) for fn in funcs if fn in order or fn in second or fn == DAY_CHANGE_DISPATCHER],
            'pseudocode_readings': {hex(fn): PSEUDOCODE_READINGS[hex(fn)] for fn in funcs if hex(fn) in PSEUDOCODE_READINGS},
        }
    fanin = dict(db.execute('SELECT target_va, COUNT(DISTINCT owner_va) FROM direct_calls GROUP BY target_va').fetchall())

    def pipeline(root):
        out = []
        for t in dict.fromkeys(t for (t,) in db.execute('SELECT target_va FROM direct_calls WHERE owner_va=? ORDER BY pc', (root,))):
            names = sorted({x for (x,) in db.execute('SELECT text FROM string_refs WHERE function_va=?', (t,))})
            if names or hex(t) in PSEUDOCODE_READINGS:
                out.append({'function': hex(t), 'callers': fanin.get(t, 0), 'strings': names[:40],
                            'reading': PSEUDOCODE_READINGS.get(hex(t))})
        return out
    return {
        'status': 'string cross-references are static evidence; readings are from automated pseudocode, not native execution',
        'day_change_driver': hex(DAY_CHANGE_DRIVER),
        'day_change_driver_pipeline': pipeline(DAY_CHANGE_DRIVER),
        'day_change_dispatcher': hex(DAY_CHANGE_DISPATCHER),
        'day_change_dispatcher_pipeline': pipeline(DAY_CHANGE_DISPATCHER),
        'query_handler_readings': {k: PSEUDOCODE_READINGS[k] for k in ('0x419690', '0x3e0b80')},
        'all_readings': PSEUDOCODE_READINGS,
        'visitor_codes': VISITOR_CODES,
        'visitor_schedule': VISITOR_SCHEDULE,
        'day_change_callees_in_order': [hex(t) for t in order],
        'flags': rows,
        'counts': {'flags_without_eventflow_writer': len(rows),
                   'with_string_reference': sum(1 for r in rows.values() if r['referencing_functions']),
                   'referenced_from_day_change': sum(1 for r in rows.values() if r['day_change'])},
    }


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
    nref = native_refs(out, flag_index)
    if nref is not None:
        (dest/'native_flag_refs.json').write_text(json.dumps({'meta': meta, 'data': nref}, ensure_ascii=False, indent=1) + '\n')
    summary = {
        'native_flag_refs': nref['counts'] if nref else 'output/index.sqlite not extracted',
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
