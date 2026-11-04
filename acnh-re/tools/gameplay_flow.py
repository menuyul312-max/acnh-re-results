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
# Villager move-out / move-in state, from 0xf84320, 0xf847f0, 0xf87670, 0xf84f10 and the action handler 0x298c10.
VILLAGER_MOVES = {
    'member': {'descriptor': '0x33d97d8', 'size': '0x1d6d48', 'processor': '0xf84320 (dispatcher 0xf545f0)'},
    'slots': '10 villagers x 0x12ab0 bytes from +0; NpcSave flags at slot +0x11efc; slot state byte +0x11efa (2 = packing, set by 0xf05d00)',
    'fields': {'0xbaae0': 'u32[35] bitset of villagers already picked (index = id byte 0, bit = id byte 1)',
               '0xcca68': '4 more NPC structures (stride 0x12ab0); state byte 3 = waiting to move in (0xf8cea0)',
               '0x1d6d3d': 'i8 move-out candidate slot or -1', '0x1d6d3e': 'i8 cooldown, 15 after a move-out, minus elapsed days',
               '0x1d6d3f': 'i8 days since the last move-out talk, max 30', '0x1d6d40': 'u8 move confirmed by a player',
               '0x1d6d41': 'i8 slot of the last villager that moved in', '0x1d6d42': 'i8 slot of the last villager talked out of moving'},
    'move_out_roll': 'cooldown <= 0, settled >= 6, days_since_talk >= 5, then rand100(day RNG) < 5*settled + days_since_talk',
    'move_out_weight': 'floor((300 - floor(sum Friendship / players)) * 0.1) - players with friendship level 6',
    'move_in_roll': 'villagers < 5: always; 5..7: (10 - n + NNpcContractProbablityAddPoint + free plots) * 10%; >= 8: (10 - n + free plots) * 10%',
    'move_in_pick': 'personality (id byte 2, 0..7) least present on the island, then uniform pick excluding the bitset',
    'evidence': '[PSEUDO] pseudocode + disassembly, not executed',
}
# Island evaluation score (VillageScoreMgr 0x15c4xxx-0x15c6xxx, actor ASysVillageScoreMgr 0xd4c30-0xd5160).
# Enum indices are checked against the comma lists in rodata: ItemKind 0x29336c2, FgMainParam Kind 0x293f104,
# ItemSize 0x29568b7, ItemPriorityPlace 0x296542f, structure type 0x2955748.
ISLAND_SCORE = {
    'save_member': {'offset': '0x24fdb0', 'descriptor': '0x33d5320', 'data_size': '0x250', 'writer': '0x15c68c0 (actor 0xd4df0)'},
    'save_fields': {'0x000': 'u16[18][16]: category 10 half-unit count per 8x8-unit block (VillageScoreVeryMessy)',
                    '0x240': 'f32 Natural (VillageScoreCheckNatural)', '0x244': 'f32 Life (VillageScoreCheckLife)',
                    '0x248': 'i32 category 9 count (VillageScorePutUnitIconNum)', '0x24c': 'i32 category 5 count (VillageScoreCheckTreeNum)'},
    'grid': 'blocks of 8 units; ceil(144/8) x ceil(128/8) = 18 x 16 blocks of 0x228 bytes; items read on a half-unit grid (16 x 16 per block), item layers 0 and 1',
    'categories': {
        '0': 'ItemParam item shown as furniture (ItemKind.CanFtr, item flag bit 5 off) with a DiyRecipeID, ItemSize not 3_0x*; origin cell only',
        '1': 'same, without DiyRecipeID',
        '2': 'DIY furniture with ItemSize 3_0x1_0 / 3_0x2_0 / 3_0x3_0',
        '3': 'non-DIY furniture with ItemSize 3_0x*',
        '4': 'FgMainParam Kind Fence',
        '5': 'FgMainParam Nature bit 4 on and bit 0 off (table: trees with Nature 18 or 22)',
        '6': 'category 5 with Kind TreePalm',
        '7': 'Kind FlwCosmos..FlwSuzuran with Nature bit 0 off',
        '8': 'Kind WeedSpr..WeedWin1',
        '9': 'dropped item shown as a unit icon (ItemUnitIcon set, not shown as furniture, item flag bit 2 off), except item 0x9c4, 0x9c6 and ItemKind Mushroom/StarPiece/ShellDrift',
        '10': 'layer 0, every half-unit cell: Fg with Nature bit 1 on except Kind Hole/Stone (table: trees and stumps), or furniture passing 0xaa8310'},
    'block_value': 'C[c] = sum over blocks of counter[c]; for c = 0, 1 minus a per-block duplicate penalty: dup = counter - distinct (item, variant); dup 5..9 -> 0.5*dup, dup >= 10 -> 0.75*dup',
    'natural': '0.25*C0 + C2 + min(C5, 190) + C7',
    'life': 'C0 + C1 + 4*C2 + 4*C3 + 0.2*C4 + price bonus + 15*(max(bridges - 1, 0) + slopes) + 15 per facility (shop state >= 3, museum state >= 3, tailor built; none under construction)',
    'price_bonus': 'per furniture item at its origin cell: Price * stack >= 20000 -> +2, >= 2000 -> +1; ItemPriorityPlace DirectionOutdoor -> +0.5',
    'zero_weight': 'categories 6, 8, 9, 10 and two per-block terrain counters (0x714060, 0x18af40) do not enter Natural or Life',
    'structures': 'bridges = structure type 26 (Bridge), slopes = 27 (Slope); helpers 0x1089590/0x10895c0 require type 0x1a/0x1b and flag byte +8 bit 0 off, while callbacks 0x110ab50/0x110ad60 also require bit 1 off when include=0 (the score caller 0x15c5ef0 passes 0); symbolic names for both bits remain unknown',
    'item_flag_bits': 'item byte +2 bit 5 clear gates the furniture-classification path; bit 2 clear gates dropped-item category 9 (unit icon); behavior is proven by 0x15c4590, but symbolic flag labels are absent',
    'recalculation': 'edits mark 8x8 blocks dirty (0x15c5fc0, from 0x4ad290, 0x4be720, 0x5fc4c0, 0x61cd80, 0x721b90); the actor recounts one dirty block (0x15c61c0), sums (0x15c61f0) and writes the save member; day change (0xf545f0) and 0xbc82d0() >= 2 force a full recount (+0x58)',
    'eventflow': 'System_IslandEvaluationCheck: Natural 200/270/350/450, Life 80/160/400/650, TreeNum > 220, PutUnitIconNum >= 15, VeryMessy >= 1 block with >= 180 half-units; DeltaBeforeDay compares int(score) with SzaIslandEvaluationBefore{Natural,Life} (5 / 10 points)',
    'evidence': '[PSEUDO] disassembly + table enums, not executed',
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
                             'random picks: popcount 0x198b590, n-th set bit 0x198b630, xorshift128 0x19aa0e0 with state from the TLS slot 0x32d2b68 = per-thread sead::Random (thread context +0x60 -> +0xd4) seeded from nn::os::GetSystemTick at thread creation (0x19a2d10 -> 0x19a9fe0); not the date-seeded day RNG']},
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
    '0xf8b460': {'role': 'day type and early/late villagers at day change',
                 'reading': ['checks calendar events by name in order FishingConvention, InsectConvention, PlayerBirthday, NpcBirthday, Countdown, NewYear; any of them -> nothing else',
                             'normal day with BuiltTownOffice on: p = min(10 * villagers present, 80); two rolls r1, r2 = rand100 (day RNG when 0x35ee058 == 1, else TLS RNG)',
                             'each villager: NPC flag ContinuousNormalDay += 1 (0xf49b20); weight = ContinuousNormalDay when >= 2',
                             'r1 < p and r2 < p each pick one villager by cumulative weight; EarlyOrLate (NPC flag) is written for each slot (0xf497c0); exact values per pick not resolved']},
    '0xfd9d10': {'role': 'special visitors at day change',
                 'reading': ['Gulliver (Johnny*) and Wisp (GstQuest*) quest flags reset/advance',
                             'SpnVisitMainField=1 when a 0-8 value (likely player house level) >=2, ImmQ_A/B/C_Complete on, CommuneIslandAvailable off and VisitedCommune off',
                             'HgcVisitFlagForTailor = (7-slot array[day index] == 2): a weekly slot table, value 2 = Label']},
    '0x419690': {'role': 'EventFlowQueryNpcHouseNum evaluate slot', 'reading': ['returns count < Num, so case 1 = fewer, case 0 = at least Num']},
    '0x3e0b80': {'role': 'EventFlowQueryVillageScoreCheckNatural evaluate slot',
                 'reading': ['returns BorderValue <= score, so case 1 = score at least the border; score is the f32 at +0x240 of save member +0x24fdb0 (Life: +0x244, 0x3df930)']},
    '0x3e4510': {'role': 'EventFlowQueryVillageScoreVeryMessy evaluate slot',
                 'reading': ['counts blocks of the u16[18][16] grid (+0x000) with value >= BorderHalfUnit (+0xd0); returns count >= BorderBlockNum (+0xf8)']},
    '0x3e1470': {'role': 'EventFlowQueryVillageScoreCheckNaturalDeltaBeforeDay evaluate slot',
                 'reading': ['DeltaPoint <= int(Natural) - SzaIslandEvaluationBeforeNatural; 0x2d68c0 (NaturalReflectLandSave) stores int(Natural) in that flag; Life: 0x3e0220 / 0x2d60a0 with SzaIslandEvaluationBeforeLife']},
    '0x15c4590': {'role': 'island score item classifier (disassembly; pseudocode loses return values)',
                  'reading': ['returns a category bitmask, a class byte (0 = category 0, 1 = category 1, else 0xff) and a float bonus',
                              'item byte +2 bit 5 must be clear for furniture classification; bit 2 must be clear for category 9 unit-icon counting; bit names are not exposed',
                              'ItemParam item (0xf58d00) shown as furniture (0xaa7f80): DiyRecipeID (0xaa8690/0xaa8780) and ItemSize 3..5 (0xaab060) pick bit 0/1/2/3; Price*stack (0xaaaa80) > 19999 -> +2.0, >= 2000 -> +1.0; ItemPriorityPlace (0xaa9590) == 1 DirectionOutdoor -> +0.5',
                              'field item (0xf58f20): FgMainParam Kind (0x4cbd20) and Nature bits (0x4cbc20): bit 0x20 tree, 0x40 palm, 0x80 flower, 0x10 fence, 0x100 weed',
                              '0x200 unit-icon items (0xf59370) at the origin cell, except items 0x9c4/0x9c6 and ItemKind 0x2f/0x3f/0x42; 0x400 only on layer 0']},
    '0x15c4240': {'role': 'count one half-unit cell into a block (layer 0; 0x15c48b0 is layer 1 without bit 0x400)',
                  'reading': ['each set bit adds to the u16 counter[bit] (+0x00..+0x14); bonus float added to +0x1c',
                              'class 0/1 items go to a 128-entry (item, variant | class << 4, count) list at +0x20 used by the duplicate penalty 0x15c4db0']},
    '0x15c4db0': {'role': 'duplicate penalty for categories 0 and 1', 'reading': ['dup = counter - distinct entries of that class; dup < 5 -> 0; dup <= 9 -> dup * 0.5; else dup * 0.75']},
    '0x15c5ef0': {'role': 'island score building inputs',
                  'reading': ['+0x8 = bridge count (0x11074d0, structure type 0x1a), +0xc = slope count (0x11076a0, type 0x1b)',
                              '+0x14 shop kind 0 present, state (0x11025d0) >= 3, not under construction (0x1106df0); +0x15 museum kind 2, state (0x11030c0) >= 3, not under construction; +0x16 tailor kind 5 present, not under construction']},
    '0x15c61f0': {'role': 'island score sum (called by the actor at 0xd50d4)',
                  'reading': ['per category 0..10: count (functor 0x3149e08) to +0x24+4c; value = sum of counter - penalty (functor 0x3149e58); Natural (+0x18) += table[c].nat(value), Life (+0x1c) += table[c].life(value)',
                              'weight table 0x3149d28 (pairs life, nat): c0 1/0.25, c1 1/0, c2 4/1, c3 4/0, c4 0.2/0, c5 0/min(x,190), c7 0/1, others 0',
                              'two terrain counters (functor 0x3149e30) have zero weights (0x3149dd8)',
                              'Life += sum of block bonus floats + 15 * (max(bridges - 1, 0) + slopes) + 15 per facility flag +0x14/+0x15/+0x16; +0x10 = distinct furniture (item, variant) pairs, not saved']},
    '0x15c68c0': {'role': 'copy island score to the save member', 'reading': ['+0x000 grid (0x15c5870), +0x240 = Natural, +0x244 = Life, +0x248 = count[9], +0x24c = count[5]']},
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
    '0xf84320': {'role': 'villager move-out and move-in at day change (dispatcher, NPC member 0x33d97d8 / 0x1d6d48 bytes)',
                 'reading': ['elapsed days > 0: 0xf847f0 (move-out) fills a bitmask of slots emptied today',
                             'then 0xf84f10 (fill an empty slot); per slot with MoveInCompletion: 0xf12aa0, 0xd1cb80, 0xd1e740']},
    '0xf847f0': {'role': 'move-out processor',
                 'reading': ['candidate (+0x1d6d3d) with AbandonedHouse != 0 -> slot cleared, candidate -1, cooldown (+0x1d6d3e) = 15',
                             'first slot with ForceMoveOut -> removed now (0xf8a410 kind 2), index kept at +0x2c674 of the 0xd1fcf0 object for the move-in step',
                             'confirmed candidate (+0x1d6d40): slot state +0x11efa != 2 -> set 2 (0xf05d00); next day change -> removed (0xf8a410 kind 1), cooldown 15',
                             'else cooldown -= days (min 0), days_since_talk (+0x1d6d3f) += days (max 30); cooldown > 0 or settled (0xf855c0) < 6 or days_since_talk <= 4 -> candidate -1',
                             'otherwise r = 0xf53420(100) (day RNG); r < 5*settled + days_since_talk -> 0xf87670; a failed roll keeps the old candidate']},
    '0xf855c0': {'role': 'settled villager count (with flag 1)', 'reading': ['slots present with AbandonedHouse < 2 and MoveInCompletion on']},
    '0xf53420': {'role': 'day RNG draw', 'reading': ['xorshift128 0x19aa0e0 on the global state 0x35e9510 (seeded by 0xf53a70); returns u32 * n >> 32']},
    '0xf87670': {'role': 'pick the villager who wants to move out',
                 'reading': ['excluded: empty slots, the index saved by StructureMoveSaveIndex (member +0x4750, 0x33dceb0), the last villager that moved in (+0x1d6d41), the last one talked out of moving (+0x1d6d42), birthday (NmlNpcParam BirthMonth/BirthMDay) 0..7 days away',
                             'weight = int((300 - int(sum of Friendship over the 8 player memories / player count)) * 0.1) - players with level 0xd34a20 > 5',
                             'r = 0xf53420(sum of weights); cumulative pick in slot order; candidate stored, +0x1d6d40 = 0, IsMovingConsultationToPlayer = 0; 0xf05b80 resets per-player memory (0xf48c40 refers to ChokeOffMoveOut)']},
    '0xd34a20': {'role': 'friendship level', 'reading': ['<30 -> 1, <60 -> 2, <100 -> 3, <150 -> 4, <200 -> 5, else 6']},
    '0x298c10': {'role': 'EventFlowActionSetNpcMoveoutStopInfo execute slot',
                 'reading': ['MoveOutStatus 0 (NNPC_ApproachD MoveCancel): ChokeOffMoveOut on in the player memory, +0x1d6d42 = this villager, +0x1d6d40 = 0',
                             'MoveOutStatus 1 (MoveConfirm): +0x1d6d40 = 1', 'both: days_since_talk +0x1d6d3f = 0']},
    '0xf84f10': {'role': 'fill an empty villager slot at day change',
                 'reading': ['counts villagers and their personality (0xcd3cb0 = id byte 2, 0..7); target = first empty slot not emptied today',
                             'target: 0xf8c540 (plot/contract path) first; then 0xf8d210 (MoveInOrder), with 0xf8cea0 for a ForceMoveOut index',
                             'needs a free house plot (0xef44c0 x10; 0xf8d640 counts them and picks one with the day RNG); 0xf8cea0 moves in a waiting NPC (state 3) if any',
                             'else roll rand100: villagers < 5 always; 5..7: < (10 - n + NNpcContractProbablityAddPoint + free plots) * 10; >= 8: < (10 - n + free plots) * 10',
                             'pick: personality bitmask 0x35ee084 = least-present personalities (ties kept), filter 0xf8d7d0, uniform pick 0xf8d860, mark bitset +0xbaae0, house from Param/NpcHouse (0xf826c0, 0xf814c0); IsNpcIncreased/Is3rdNpc']},
    '0xf8d7d0': {'role': 'move-in personality filter (disassembly)', 'reading': ['same u16 cache as 0xf8de30 (<=7, else 0); passes when its bit is set in 0x35ee084']},
    '0xf8cea0': {'role': 'move in a waiting NPC',
                 'reading': ['looks for state byte 3 in the 4 NPC structures at +0xcca68 (stride 0x12ab0); sets MoveInCompletion, builds the house on the given plot']},
    '0xf1360': {'role': 'calendar event date match by label',
                'reading': ['compares the event label with globals set in 0xfe390: PlayerBirthday -> 0xefe10, NpcBirthday -> 0xf01e0, NormalLive -> 0xf0330, BirthdayLive -> 0xf11b0, FirstLive -> 0xffbc90 + TkkFirstLiveReserved',
                            'EventType enum (rodata 0x29b9f72) Global, Region, Other, Totakeke, None; None rows are skipped (0xf1e20, 0xf2c20)']},
    '0xf0330': {'role': 'NormalLive date rule',
                'reading': ['needs TkkFirstLive; candidate = Saturday of the Sunday..Saturday week (date + 6 - weekday, 0x1fbd50)',
                            'no calendar event that day (0xf0790) -> live that day; else TkkSkipNormal (array 0x32d5848, enum 0x298d19c Before/Skip/Same): Same -> that day, Skip -> no live this week, Before -> one day earlier and retry, down to Monday']},
    '0xf11b0': {'role': 'BirthdayLive date rule',
                'reading': ['needs TkkFirstLive; any of 8 players with TotakekeLiveCount > 0 whose date at player member +0x17370 (descriptor 0x33d5868) equals today (year, month, day; 0xf420c0)']},
    '0xf920f0': {'role': 'per-player birthday event date at day change (from 0xf6130)',
                 'reading': ['scans from today + 21 days back to today for the player birthday (member +0x11478, 0xefc70); a calendar event on that day uses TkkSkipBirthday (0xf6090): Same keeps, Skip clears, Before moves one day earlier',
                             'stores the date at +0x34942 (0xf41fd0); on that day villager birthday messages are set (BDayMsgSenderNNpcUniqueID0/1)']},
    '0xfc7b40': {'role': 'weekly turnip price trigger (from shop day change 0xfc4560)',
                 'reading': ['first run: pattern = rand u32 >> 30 (0..3), then 0xfc6d00; otherwise regenerates when the Sunday of the current week differs from the one of the previous play time']},
    '0xfc6d00': {'role': 'turnip price generator (TLS RNG 0x19aa0e0)',
                 'reading': ['u32[17]: +0 base = rand(21) + 90; +4/+8 Sunday (zeroed at the end); +0xc..+0x38 Monday AM .. Saturday PM; +0x3c pattern; +0x40 peak start',
                             'next pattern from r = rand(100): from 0: <20 ->0, <50 ->1, <65 ->2, else 3; from 1: <50 ->0, <55 ->1, <75 ->2, else 3; from 2: <25 ->0, <70 ->1, <75 ->2, else 3; from 3: <45 ->0, <70 ->1, <85 ->2, else 3; FirstKabuBuy on and FirstKabuPattern off -> set FirstKabuPattern, pattern 3',
                             'price = int(rate * base + 0.99999); pattern 0: high (0.9-1.4) / falling (0.6-0.8, -0.04..-0.10) phases totalling 12 slots; pattern 1: peak at rand(7)+3 with 0.9-1.4, 1.4-2.0, 2.0-6.0, 1.4-2.0, 0.9-1.4, then 0.4-0.9; pattern 2: falling from 0.85-0.9 by 0.03-0.05; pattern 3: peak at rand(8)+2 with 0.9-1.4, 0.9-1.4, r1-1, r, r1-1 (r 1.4-2.0, r1 = rand(1.4, r) * base)']},
    '0x3cca80': {'role': 'EventFlowQueryBoaCanSetKabu evaluate slot (NSO VA 0x3cca80; Ghidra FUN_004cca80)',
                 'reading': ['resolves node +0x208ed0 and reads base price at data +0x00; compares requested quantity-scaled amount against it; returns 1 below price, otherwise 0 when the quantity setter accepts it, or 2 when no quantity is set / setter rejects it',
                             'registered as EventFlowQueryBoaCanSetKabu (factory 0x45a7f0, constructor 0x3cca20, vtable 0x3053ac0 slot 6); its sole indexed EventFlow use is SNPC_boc Event32: result 0 -> Event30, 1 -> Event33, 2 -> Event47',
                             'native emulation with controlled save/input/setter accessors confirms all three return codes; this verifies the query branch logic, not a direct UI-page binding',
                             'this proves the Daisy Mae dialogue consumer; KabuBuyPage string at 0x1215c30 is not directly linked to this query']},
    '0xfc7c70': {'role': 'read a turnip price for a weekday and AM/PM slot',
                 'reading': ['clamps weekday to 0..6 and selects u32 at data +0x04 + 4*(2*weekday + pm); called by 0xaab8c0 for the turnip sale-price path']},
    '0xfc56c0': {'role': 'Saharah daily stock',
                 'reading': ['in-season items (0xab33e0) x ItemKind Rug x ItemFrom RugL / RugM / RugS, then RoomWall and RoomFloor x LaurentWallFloor; one random pick each (0xa120c0)']},
    '0xfd0630': {'role': 'Nook\'s Cranny stock (calls 0xfce9e0, 0xfceb90, 0xfcf660)',
                 'reading': ['shop state <2 -> 0xfce9e0, state 2 -> 0xfceb90, state 3 -> 0xfcf660',
                             'state <2 first pick: in-season mask AND ItemKind values {0,77,32} (Ftr, DoorDeco, Tambourine) AND ItemFrom value 1 (ShopDefault), then sample 2; 0xfcdfe0 performs the extra pick(s) from source values read from save node +0x20d0e0',
                             'state 2 and 3 builders also construct the seasonal mask intersected with ItemKind {0,77,32}; this is one component of their filters, not a complete per-pick rule',
                             'NSO VA 0xa0fd80 (Ghidra FUN_00b0fd80) constructs a distinct derived-class predicate: raw vtable 0x30c6348 (Ghidra 0x31c6348) slot 0 reaches raw 0xaa82d0 (Ghidra FUN_00ba82d0), which compares the selector with raw 0xaa8ce0 (Ghidra FUN_00ba8ce0); that helper uses ItemKind-indexed lookups and in one branch resolves ItemParam.DragSE (+0x9c)',
                             'state 2 constructs selector sets {5,6} and {0..5}; state 3 constructs {5,6} and {3,4}. In the DragSE branch these values mean HeavyWheel/Floated, the 0..5 values include Light/Normal/Heavy/VeryHeavy/LightWheel/HeavyWheel; other branches can return a different derived class, so these names do not cover all candidates',
                             'candidate ItemFrom tags seen across all three states: ShopDefault, ShopMiscGoods, ShopLv1/2, ShopLargeGoods, ShopHighClass, ShopSeasonSale, ShopUmbrellaLv1/2, ShopWrappingPaper; builder sets are now identified, but exact assignment to each final output slot remains unresolved']},
    '0xfcdfe0': {'role': 'additional Nook stock picks',
                 'reading': ['builds three filter values and calls 0xce170 once for each with the requested count (1 for state <2, 2 for state 2, -1 for state 3); the first two are mapped from bytes +0x925/+0x924 of save node +0x20d0e0, and the third is mapped from shop argument byte +10',
                             'bytes +0x925/+0x924 are indices into an eight-entry table; helper 0xf50ad0 selects another table index whose month mask includes the current month (shifted by six for the alternate hemisphere mode) and which is not among the saved choices',
                             'table index -> ItemFrom numeric value / name / month mask: 0 -> 0x57 ShopSeed_Anemone / 0x81f; 1 -> 0x55 ShopSeed_Hyacinth / 0x00e; 2 -> 0x58 ShopSeed_Tulip / 0x03c; 3 -> 0x56 ShopSeed_Rose / 0xe70; 4 -> 0x54 ShopSeed_Cosmos / 0x7c0; 5 -> 0x53 ShopSeed_Lily / 0x1e0; 6 -> 0x52 ShopSeed_Chrysanthemum / 0xf81; 7 -> 0x59 ShopSeed_Pansy / 0xc0f',
                             '0xf50f50/0xf51040 map saved indices to ItemFrom numeric values; 0xf50e40 maps the selected index to a value. Labels come from the native comma-separated ItemFrom enum at rodata 0x29b535d; ordinal anchors ShopDefault=1 and ShoesBagShop=0x34 match static Nook/Kicks filters; all three resulting filters use the same 0xb0fd40 ItemFrom predicate']},
    '0xf50ad0': {'role': 'select an additional seasonal Nook ItemFrom source',
                 'reading': ['builds eligible table indices 0..7 from month masks; excludes the two saved indices +0x925/+0x924 and an optional third index; switches the month by six for the alternate hemisphere mode; selects from remaining candidates through day-RNG helper 0xf53420']},
    '0xf50e40': {'role': 'map a season-eligible Nook source index to ItemFrom',
                 'reading': ['calls 0xf50ad0 with the current month from shop argument +10 and saved exclusions +0x925/+0x924; indexes the source table using the returned index and writes its ItemFrom value']},
    '0xf50f50': {'role': 'map saved Nook source index at +0x925',
                 'reading': ['returns the ItemFrom numeric value for the table index in save member +0x20d0e0 data +0x925']},
    '0xf51040': {'role': 'map saved Nook source index at +0x924',
                 'reading': ['returns the ItemFrom numeric value for the table index in save member +0x20d0e0 data +0x924']},
    '0xfc6300': {'role': 'Nook\'s Cranny 64-entry catalog buffer',
                 'reading': ['clears 64 slots at shop block +0x2b14; samples ItemKind Ftr (0) x2, Tops (6) x2, Bottoms (9), Cap (12), Accessory (14), Shoes (11), Music (72) x1 each via 0xfc5d60',
                             '0xfc61e0 marks Shop.Catalog.%s for selected IDs; eligibility helper chain 0xfc5fd0/0xfc60b0 still needs full filter semantics']},
    '0xfca870': {'role': 'Able Sisters / Label stock',
                 'reading': ['ItemFrom Tailor, TailorMarketOnly, HgcQuestReward x ItemKind Tops, Bottoms, OnePiece, Cap, Helmet, Accessory, Socks, Shoes; HgcVisitFlagForTailor']},
    '0xfc8760': {'role': 'Kicks stock', 'reading': ['clears 32 slots; ItemFrom ShoesBagShop x ItemKind Shoes, Socks, Bag']},
    '0xf8f190': {'role': 'day-change reset of member +0x20d310', 'reading': ['writes u32 2 to save member +0x20d310 (4 bytes, descriptor GOT 0x32ff640) every day change; no other reader found by constant scan']},
    '0xf7d4c0': {'role': 'campsite visitor at day change (member +0x20d578, 0x114 bytes)',
                 'reading': ['elapsed days > 0 and no Countdown-type event today (0xf7d5c0): clears an invalid camper id',
                             'new camper when 0xf7d7e0: campsite state (member +0x20d4d0) == 2; CampFirstCamperVisit on -> always; else days since the last camper (date at +0x10c) d: d <= 2 -> no, d = 3/4/5 -> 5/10/15 %, d >= 6 -> 20 % (table 0x29fa1d0, 0.2 at 0x29d6328, day RNG 0xf53490)',
                             'camper picked by 0xd418b0 (excludes villagers on the island), stored with 0xf7d990 (also mirrored into the NPC member via 0xf86300)']},
    '0xfc1b80': {'role': 'per-player rumor counter', 'reading': ['for players 0..7 present (0xef7530): flag RumorPFavoriteProgressDays += elapsed days (0xf4b680)']},
    '0xbdfd40': {'role': 'daily villager group activities (from driver 0xf53a70)',
                 'reading': ['skipped on NormalLive/BirthdayLive days and calendar or global event days',
                             'per activity slot: 25 % roll; candidates from NpcLife/NpcInterest rows whose VillageDevelopmentLevel <= the island level (+0x208)',
                             'per player with ValidatePlayerSaveFlag: player flags ReservedNpcGroupActivityMorning/Noon/Evening/Nignt (+2 unused slots, table 0x3567c30) = random candidate or 0']},
    '0xf6130': {'role': 'calendar day change',
                'reading': ['GlobalEventReady -> GlobalEventAvailable; EventPlazaBuilt -> GlobalEventReady',
                            'skipped days: InsectConvention1-4 date passed -> InsectFesFinished; FishingConventionSpring..Winter -> FishFesFinished; any calendar event -> AnyGlobalEventFinished',
                            'per player 0xf920f0 (birthday event date); TodayGlobalEventId / TodayRegionEventId = UniqueID of today event or 0xffff']},
    '0x4ae640': {'role': 'daily field items: star pieces, money rock, message bottle (from driver)',
                 'reading': ['per player PrayStarToday -> StarPieceGrowCount; PrayStarToday and VisitorPrayStarToday reset',
                             'OccurrenceCoinStone (money rock) placement and MessageBottleAvailable / IsGetMessageBottle / PickedUpMessageBottle operate over a 0x8000-cell field item grid; selected cells use generic field query 0x4ad1f0',
                             'decomp does not establish a fixed beach coordinate or beach-specific cell mask; PcMaingameStart gate']},
    '0xf889e0': {'role': 'conditional AbandonedHouse reset (villager move-out state)',
                 'reading': ['iterates 10 villager slots; resets AbandonedHouse and InducementAtMovingDay through shared flag helper when its state predicates match',
                             'direct callers 0xbc0190 and 0xbc0430 have no recovered direct callers; callback context and local-vs-network origin unresolved']},
    '0xd21110': {'role': 'villager house interiors (also called from 0xbbe5a0, 0xbbf3e0, 0xbc0430)',
                 'reading': ['for each of 10 slots with AbandonedHouse < 2 and MoveInCompletion on: count it (+0x63b0) and load Param/NpcHouse/<species><nn>.byml; reads AbandonedHouse, does not write it']},
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
        'query_handler_readings': {k: PSEUDOCODE_READINGS[k] for k in ('0x419690', '0x3e0b80', '0x3e4510', '0x3e1470', '0x3cca80')},
        'all_readings': PSEUDOCODE_READINGS,
        'visitor_codes': VISITOR_CODES,
        'visitor_schedule': VISITOR_SCHEDULE,
        'villager_moves': VILLAGER_MOVES,
        'island_score': ISLAND_SCORE,
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
