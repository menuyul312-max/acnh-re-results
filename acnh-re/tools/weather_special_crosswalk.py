#!/usr/bin/env python3
"""Crosswalk EnvSpecialWeather query results to the supplied 1.0.0 EventFlow/MSBT.

This records only message IDs and topic labels derived from local USen message
text. It does not infer weather scheduling or render/actor activation.
"""
import argparse
import hashlib
import json
import re
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ROMFS = Path('/workspace/downloads/acnh_additional_romfs_2026-11-02/romfs')
DEFAULT_ANALYSIS_ROOT = Path('/workspace/acnh-re/output')
DEFAULT_OUT = ROOT / 'output/gameplay/ecology_weather_followup/weather_special_crosswalk.json'
ELF_SHA256 = '5bf707c3dc5dac0ad9635af7d336ec580f81c3f7876d0f55400d1900e3415d74'
QUERY_NAME = 'EventFlowQueryEnvSpecialWeather'


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _message_lookup(out_root):
    result = {}
    msg_root = out_root / 'additional_romfs/messages/USen'
    for archive in ('TalkNNpc', 'TalkSNpc'):
        path = msg_root / f'{archive}.json'
        doc = json.loads(path.read_text())
        for member, data in doc['members'].items():
            member_key = member.removesuffix('.msbt')
            for row in data.get('messages', []):
                for label in row.get('labels', []):
                    result[f'{archive}/{member_key}:{label}'] = row.get('text') or ''
    return result


def _message_tags(text):
    # Strip control tags before topic classification. No message body is copied
    # to the output artifact.
    plain = re.sub(r'\[/?tag[^\]]*\]', '', text)
    plain = re.sub(r'\s+', ' ', plain).strip().lower()
    tags = []
    if re.search(r'meteor|shooting star|meteors', plain):
        tags.append('meteor_or_stargazing')
    if 'rainbow' in plain:
        tags.append('double_rainbow' if 'double' in plain else 'rainbow')
    if 'aurora' in plain:
        tags.append('aurora')
    if re.search(r'\bfog\b|hazy|haze|hard to see', plain):
        tags.append('low_visibility')
    if re.search(r'thunder|\bstorm\b|lightning', plain):
        tags.append('explicit_storm_or_thunder')
    if 'loud' in plain and 'flashy' in plain:
        tags.append('loud_and_flashy_weather')
    return tags


def _case_messages(flowchart, start, max_steps=64):
    """Walk deterministic action/join links until first split or termination."""
    events, actors = flowchart['events'], flowchart['actors']
    seen, ids = set(), []
    current = start
    for _ in range(max_steps):
        if current is None or current in seen or current >= len(events):
            break
        seen.add(current)
        event = events[current]
        if event['type'] == 'action':
            actor = actors[event['actor']]
            action = actor['actions'][event['action']]
            if action == 'EventFlowActionOpenMessageWindow':
                mid = (event.get('params') or {}).get('MessageID')
                if isinstance(mid, str):
                    ids.append(mid)
                    break
            current = event.get('next')
            continue
        if event['type'] == 'join':
            current = event.get('next')
            continue
        break
    return ids


def build(romfs, out_root):
    sys.path.insert(0, str(ROOT / 'tools'))
    from reference.acnh_rip.formats.bfevfl import read_bfevfl, validate

    messages = _message_lookup(out_root)
    rows, file_sources = [], []
    eventflow_dir = romfs / 'EventFlow'
    for path in sorted(eventflow_dir.glob('*.bfevfl')):
        raw = path.read_bytes()
        flow = read_bfevfl(raw)
        problems = validate(flow)
        if problems:
            raise ValueError(f'{path.name}: BFEVFL validation errors: {problems[:4]}')
        uses = []
        for fc in flow['flowcharts']:
            for event_index, event in enumerate(fc['events']):
                if event['type'] != 'switch':
                    continue
                actor = fc['actors'][event['actor']]
                query = actor['queries'][event['query']]
                if query != QUERY_NAME:
                    continue
                cases = []
                for case in event.get('cases', []):
                    message_ids = _case_messages(fc, case['event'])
                    message_rows = []
                    for mid in message_ids:
                        text = messages.get(mid)
                        message_rows.append({
                            'message_id': mid,
                            'text_sha256': hashlib.sha256((text or '').encode()).hexdigest() if text is not None else None,
                            'topic_tags': _message_tags(text or '') if text is not None else [],
                            'message_found_in_usen': text is not None,
                        })
                    cases.append({'value': case['value'], 'event_index': case['event'], 'messages': message_rows})
                uses.append({
                    'flowchart': fc['name'], 'event_index': event_index, 'event_name': event['name'],
                    'cases': cases,
                })
        if uses:
            rows.extend(uses)
            file_sources.append({'file': f'EventFlow/{path.name}', 'sha256': _sha(path), 'query_uses': len(uses)})

    query_decomp = out_root / 'binary/analysis_decomp/3f62f0.c'
    query_text = query_decomp.read_text()
    return_values = {int(n) for n in re.findall(r'\breturn\s+(\d+);', query_text)}
    return_values.update(int(n) for n in re.findall(r'\buVar5\s*=\s*(\d+);', query_text))
    db = sqlite3.connect(out_root / 'index.sqlite')
    enum_texts = [row[0] for row in db.execute(
        'SELECT DISTINCT text FROM string_refs WHERE function_va=?', (0x26b9c0,))]
    db.close()
    enum_text = next((t for t in enum_texts if t.startswith('cNotSet, ')), '')
    enum_values = enum_text.split(', ') if enum_text else []

    by_value = {}
    for use in rows:
        for case in use['cases']:
            rec = by_value.setdefault(str(case['value']), {'value': case['value'], 'evidence': []})
            rec['evidence'].append({
                'flowchart': use['flowchart'], 'event_index': use['event_index'],
                'event_name': use['event_name'], 'messages': case['messages'],
            })
    if sorted(int(k) for k in by_value) != list(range(10)):
        raise ValueError(f'EventFlow values do not cover 0..9: {sorted(int(k) for k in by_value)}')
    if sorted(return_values) != list(range(10)):
        raise ValueError(f'native query decomp values do not cover 0..9: {sorted(return_values)}')
    if sum(1 for r in rows if r['flowchart'] == 'NNPC_FreeB') != 1:
        raise ValueError('expected one audited NNPC_FreeB weather query')
    freeb = next(r for r in rows if r['flowchart'] == 'NNPC_FreeB')
    if {c['value'] for c in freeb['cases']} != set(range(1, 10)):
        raise ValueError('NNPC_FreeB values 1..9 changed')
    if any(not m['message_found_in_usen'] for u in rows for c in u['cases'] for m in c['messages']):
        raise ValueError('one or more weather query branches lack a resolved USen message')
    result = {
        'artifact': 'weather_special_crosswalk',
        'game_version': 'ACNH 1.0.0',
        'native_elf_sha256': ELF_SHA256,
        'sources': {
            'eventflow_files': file_sources,
            'message_archives': {
                name: {'path': f'output/additional_romfs/messages/USen/{name}.json',
                       'sha256': _sha(out_root / 'additional_romfs/messages/USen' / f'{name}.json')}
                for name in ('TalkNNpc', 'TalkSNpc')
            },
            'message_text_policy': 'Only SHA-256 and conservative topic tags are emitted; message bodies are not copied.',
        },
        'native_query': {
            'eventflow_handler': QUERY_NAME,
            'registry': {'factory': '0x456770', 'evaluate_slot': '0x3f62f0', 'vtable': '0x30559c8'},
            'decomp_numeric_return_values': sorted(return_values),
            'decomp_path': 'output/binary/analysis_decomp/3f62f0.c',
            'decomp_sha256': _sha(query_decomp),
            'scope': 'Static pseudocode return paths; no native runtime state fixture was supplied for this query.',
        },
        'related_weather_condition_enum': {
            'function': '0x26b9c0',
            'values': enum_values,
            'string_source': 'index.sqlite:string_refs',
            'limit': 'The enum vocabulary is recovered, but its ordinal values are not equated with EnvSpecialWeather query results.',
        },
        'uses': rows,
        'cases_by_value': [by_value[k] for k in sorted(by_value, key=int)],
        'interpretation_limits': [
            'A message topic identifies the dialogue branch selected for that query value; it does not prove when the query value is produced.',
            'The weather-condition strings cBeforeMeteor/cMeteorShower/cRainbow/cWRainbow/cBeforeAurora/cAurora at 0x26b9c0 are not equated numerically with EnvSpecialWeather query values here.',
            'The artifact does not resolve the calendar/flag scheduler, weather actor spawn, renderer inputs, or visual duration.',
        ],
    }
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--romfs', type=Path, default=DEFAULT_ROMFS)
    parser.add_argument('--output-root', type=Path, default=DEFAULT_ANALYSIS_ROOT)
    parser.add_argument('--output', type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    result = build(args.romfs, args.output_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    summary = {
        'query_uses': len(result['uses']),
        'case_values': [r['value'] for r in result['cases_by_value']],
        'unresolved_message_ids': sum(not m['message_found_in_usen'] for u in result['uses'] for c in u['cases'] for m in c['messages']),
        'output': str(args.output),
    }
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
