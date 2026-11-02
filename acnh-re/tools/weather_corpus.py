#!/usr/bin/env python3
"""Compare local weather tables with pinned MeteoNook literals, without execution."""
import ast
import calendar
import hashlib
import json
from pathlib import Path
import re

from reverse_corpus import dump

ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/'output'
REFERENCE=ROOT/'tools/external/MeteoNook/data.rs'
COMMIT='a7ea07aa9b3db8859b0f476c549a1a2245ad1b07'
WEATHER=['快晴','晴れ','曇り','雨雲','雨','大雨']
WIND=['凪','陸弱','陸中','陸強','海弱','海中','海強']


def rust_array(text,name,aliases=None):
    """Accept nested integer literals only after exact alias substitution."""
    text=re.sub(r'//[^\n]*','',text)
    match=re.search(r'pub static '+re.escape(name)+r'\s*:[^=]+?=\s*\[',text)
    if not match:raise ValueError(('missing reference array',name))
    start=match.end()-1;depth=0
    for end in range(start,len(text)):
        if text[end]=='[':depth+=1
        elif text[end]==']':
            depth-=1
            if depth==0:break
    else:raise ValueError('unterminated reference array')
    literal=text[start:end+1]
    if aliases:
        literal=re.sub(r'\b[A-Za-z_][A-Za-z_0-9]*\b',lambda m:str(aliases[m.group()]),literal)
    if re.search(r'[^\[\]\d,\s]',literal):raise ValueError('nonliteral reference array')
    return ast.literal_eval(literal)


def build():
    manifest=json.loads((OUT/'manifest.json').read_text())['entries']
    sources={Path(e['source']).stem:e for e in manifest if e['format']=='BYML'and '/Weather/'in e['source']}
    text=REFERENCE.read_text()
    reference={name:rust_array(text,name,aliases)for name,aliases in [
        ('PATTERNS',dict(F=0,C=1,O=2,RC=3,R=4,HR=5)),
        ('WINDS',dict(WC=0,WL0=1,WL1=2,WL2=3,WS0=4,WS1=5,WS2=6)),
        ('RATE_MAPS',None),('RATE_LOOKUP_N',None),('RATE_LOOKUP_S',None)]}
    def load(name):
        entry=sources[name];doc=json.loads((OUT/f"byml_resolved/{entry['id']:05d}.json").read_text())
        return doc['root']['@'+name]
    failures=[];checks=dict(weather_hours=0,wind_hours=0,rate_slots=0,calendar_dates=0,pattern_labels=0)
    def compare(kind,actual,expected,where):
        checks[kind]+=1
        if actual!=expected:failures.append(dict(kind=kind,where=where,actual=actual,expected=expected))
    pattern_enum=dict((m.group(1),int(m.group(2)))for m in re.finditer(r'^\s*(\w+) = (\d+),',text[text.index('pub enum Pattern {'):text.index('pub enum PatternKind {')],re.M))
    patterns=[]
    for key,record in sorted(load('WeatherPattern')['@mParams'].items(),key=lambda p:int(p[0].rsplit('_',1)[-1])):
        index=int(key.rsplit('_',1)[-1]);label=record['@mLabel.Str']
        compare('pattern_labels',index,pattern_enum[label],label)
        weather=[WEATHER.index(x)for x in record['@mWeatherType[].Enum']]
        winds=[WIND.index(x)for x in record['@mWindType[].Enum']]
        if len(weather)!=24 or len(winds)!=24:raise ValueError('weather hour count')
        for hour in range(24):
            compare('weather_hours',weather[hour],reference['PATTERNS'][index][hour],[index,hour])
            compare('wind_hours',winds[hour],reference['WINDS'][index][hour],[index,hour])
        patterns.append(dict(index=index,label=label,report=record['@mReport.Enum'],source_pointer=f'/@WeatherPattern/@mParams/{key}',
            weather=weather,wind=winds,weather_labels=record['@mWeatherType[].Enum'],wind_labels=record['@mWindType[].Enum']))
    rates=[];lookups={}
    for hemi,offset in [('North',0),('South',20)]:
        tables=[]
        for key,record in sorted(load('WeatherRate_'+hemi)['@mParams'].items(),key=lambda p:int(p[0].rsplit('_',1)[-1])):
            index=int(key.rsplit('_',1)[-1]);weights=record['@mRate[].s8']
            if len(weights)!=34 or sum(weights)!=100 or min(weights)<0:raise ValueError('invalid local weather weights')
            expanded=[p for p,w in enumerate(weights)for _ in range(w)]
            for slot,pattern in enumerate(expanded):compare('rate_slots',pattern,reference['RATE_MAPS'][offset+index][slot],[hemi,index,slot])
            tables.append(dict(index=index,reference_index=offset+index,end_month=record['@mEndMonth.s8'],end_day=record['@mEndDay.s8'],
                weights=weights,roll_0_to_99=expanded,source_pointer=f'/@WeatherRate_{hemi}/@mParams/{key}'))
        # Interpret declared end dates inclusively and verify against independent
        # public calendar tables on every valid date of a leap year.
        dates=[]
        ordered=sorted(tables,key=lambda r:(r['end_month'],r['end_day']))
        for month in range(1,13):
            month_dates=[]
            for day in range(1,calendar.monthrange(2024,month)[1]+1):
                selected=next(r for r in ordered if (month,day)<=(r['end_month'],r['end_day']))
                compare('calendar_dates',selected['reference_index'],reference['RATE_LOOKUP_'+hemi[0]][month-1][day-1],[hemi,month,day])
                month_dates.append(selected['index'])
            dates.append(month_dates)
        rates.append(dict(hemisphere=hemi,tables=tables));lookups[hemi]=dates
    source_refs=[dict(source_id=e['id'],source=e['source'],sha256=e['sha256'],raw=e['raw'],
        named_json=f"byml_resolved/{e['id']:05d}.json",typed_json=f"byml_typed/{e['id']:05d}.json")for e in sorted(sources.values(),key=lambda e:e['id'])]
    dump(OUT/'weather/patterns.json',dict(weather_codes=WEATHER,wind_codes=WIND,patterns=patterns))
    dump(OUT/'weather/rates.json',dict(rates=rates,calendar_valid_dates=lookups,
        calendar_contract='Month arrays contain valid dates only, including February 29. Inclusive end-date interpretation independently matches the pinned reference.'))
    dump(OUT/'weather/render_parameters.json',{name:load(name)for name in ['RainDrawParam','SnowDrawParam']})
    # These are observed differences in the supplied 1.0.0 data, not parser
    # failures. Preserve local values rather than replacing them with a newer
    # reference's values. Any additional difference fails the reproducible build.
    observed=[dict(kind='weather_hours',where=[2,18],actual=1,expected=2),
        dict(kind='weather_hours',where=[2,19],actual=2,expected=1),
        dict(kind='weather_hours',where=[6,17],actual=1,expected=2),
        dict(kind='weather_hours',where=[6,19],actual=2,expected=1)]
    unexpected=[d for d in failures if d not in observed]
    if failures!=observed:unexpected.append(dict(kind='observed_difference_set_changed'))
    result=dict(pattern_count=len(patterns),hours_per_pattern=24,rate_table_count=sum(len(h['tables'])for h in rates),
        sources=source_refs,comparisons=checks,total_comparisons=sum(checks.values()),reference_differences=failures,
        unexpected_differences=unexpected,local_values_preserved=True,
        difference_scope='Fine02 hours 18/19 and Fine06 hours 17/19 differ from the pinned public table. The raw source and both independent and original native readers establish the local values; no claim about the reason or version of the public table.',
        reference=dict(repository='Treeki/MeteoNook',commit=COMMIT,url=f'https://github.com/Treeki/MeteoNook/blob/{COMMIT}/src/data.rs',
            sha256=hashlib.sha256(REFERENCE.read_bytes()).hexdigest(),license='AGPL-3.0',execution='Not executed; restricted literal parsing only'),
        native_validation='Native ordinary-day selector, calendar lookup, weighted loop and exact RNG state are verified separately in weather/native_verification.json. The additional native_linked_verification.json exercises the 05:00 boundary through the original SDK; no complete weather runtime claimed.',
        remaining=['Special-event overrides and version-specific unlock flags','Snow conversion',
            'Cloud, fog, rainbow, aurora, stars and visual runtime behavior'])
    dump(OUT/'weather/summary.json',result)
    print(json.dumps({k:v for k,v in result.items()if k not in ['sources']},indent=2))
    if unexpected:raise ValueError(('unexpected weather reference differences',unexpected[:10]))


if __name__=='__main__':build()
