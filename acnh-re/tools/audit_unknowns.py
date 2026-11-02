#!/usr/bin/env python3
"""Give every still-unnamed BCSV field a concrete evidence trail."""
import collections
import json
from pathlib import Path
import sqlite3

from reverse_corpus import dump

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT/'output'


def build():
    db = sqlite3.connect(OUT/'index.sqlite')
    fields = json.loads((OUT/'schemas/unresolved_names.json').read_text())
    tables = {}
    result = []
    for field in fields:
        table_name,h = field['table'],field['hash']
        if table_name not in tables:
            tables[table_name] = json.loads((OUT/'tables_resolved'/f'{table_name}.json').read_text())
        table = tables[table_name]
        i = next(i for i,c in enumerate(table['columns']) if c['hash']==h)
        column = table['columns'][i]
        values = [r[i] for r in table['rows']]
        common = collections.Counter(json.dumps(v,ensure_ascii=False,sort_keys=True) for v in values)
        refs = db.execute('SELECT pc,owner_va FROM hash_refs WHERE hash=?',(int(h,16),)).fetchall()
        evidence = []
        for pc,owner in refs:
            p = OUT/'binary/analysis_decomp'/f'{owner:x}.c' if owner else None
            evidence.append({'pc':hex(pc),'function_va':hex(owner) if owner else None,
                'pseudocode':str(p.relative_to(OUT)) if p and p.exists() else None,
                'status':'immediate_candidate; shared hash does not establish table identity'})
        result.append({**field,'source_id':table['source_id'],'raw':table['raw'],
            'decoded_type':column['type'],'type_status':column['type_evidence'],
            'row_count':len(values),'distinct_values':len(common),
            'common_values':[{'value':json.loads(v),'count':n} for v,n in common.most_common(8)],
            'native_candidates':evidence,'meaning_status':'unresolved; original name not recoverable from CRC alone'})
    dump(OUT/'schemas/unresolved_evidence.json',result)
    db.execute('DROP TABLE IF EXISTS columns_resolved')
    db.execute('CREATE TABLE columns_resolved(table_name TEXT, hash INTEGER, name TEXT, descriptor TEXT, type TEXT, offset INTEGER, width INTEGER, evidence TEXT, PRIMARY KEY(table_name,hash))')
    for p in (OUT/'tables_resolved').glob('*.json'):
        t=json.loads(p.read_text())
        db.executemany('INSERT INTO columns_resolved VALUES(?,?,?,?,?,?,?,?)',
            [(p.stem,int(c['hash'],16),c['name'],c['descriptor'],c['type'],c['offset'],c['width'],c['name_evidence']) for c in t['columns']])
    db.commit();db.close()
    print(json.dumps({'unresolved_columns':len(result),'with_native_candidates':sum(bool(r['native_candidates']) for r in result)},indent=2))


if __name__ == '__main__': build()
