"""Connect newly supplied text/catalogues to existing RE evidence; verify raw gzip."""
from collections import Counter, defaultdict
from pathlib import Path
import gzip
import json
import re

from audit_additional_romfs import OUT, ROMFS, inflate, sarc_members, dump, sha


def main():
    original = Path('/workspace/acnh-re/output')
    refs = json.loads((original/'relations/eventflow.json').read_text())['message_references']
    items = json.loads((original/'tables_resolved/ItemParam.json').read_text())
    cols = {c['name']:i for i,c in enumerate(items['columns']) if c.get('name')}
    uidcol, rescol = cols['UniqueID'], cols['ResName']
    bindings = [{**r,'languages':{}} for r in refs]
    translations = defaultdict(dict)
    by_language = {}
    item_name_stats = {}
    for lang_dir in sorted((OUT/'messages').iterdir()):
        if not lang_dir.is_dir():continue
        lookup = {}
        names = defaultdict(list)
        for file in sorted(lang_dir.glob('*.json')):
            domain = file.stem
            data = json.loads(file.read_text())
            for member, msg in data['members'].items():
                stem = member.removesuffix('.msbt')
                for row in msg['messages']:
                    for label in row['labels']:
                        key = f'{domain}/{stem}:{label}'
                        if key in lookup:
                            raise ValueError('Duplicate qualified message label')
                        lookup[key] = {'member':member,'text_index':row['index'],
                                       'json':str(file.relative_to(OUT))}
                        if domain=='String' and member.startswith('Item/STR_ItemName_'):
                            m=re.search(r'_(\d+)$',label)
                            if m:
                                names[int(m[1])].append({'label':label,'text':row['text'],
                                    'member':member,'text_index':row['index'],
                                    'matching_rule':'Exact item UniqueID in item-name label suffix.'})
            if domain == 'String':
                group_names = {}
                for member,msg in data['members'].items():
                    prefix='Outfit/GroupName/STR_OutfitGroupName_'
                    if member.startswith(prefix):
                        category=member[len(prefix):].removesuffix('.msbt')
                        for row in msg['messages']:
                            for label in row['labels']:
                                group_names[category,label]={'member':member,'label':label,
                                    'text':row['text'],'text_index':row['index']}
                for member,msg in data['members'].items():
                    prefix='Outfit/GroupColor/STR_OutfitGroupColor_'
                    if not member.startswith(prefix):continue
                    category=member[len(prefix):].removesuffix('.msbt')
                    for row in msg['messages']:
                        for label in row['labels']:
                            m=re.fullmatch(r'(\d+)_(.+)_(\d+)',label)
                            if not m or m[2]!=category:continue
                            group=group_names.get((category,m[1]))
                            if group:
                                names[int(m[3])].append({**group,'color':row['text'],
                                    'color_member':member,'color_label':label,
                                    'color_text_index':row['index'],
                                    'matching_rule':'Exact UniqueID in outfit color label; exact category/group key links group name.'})
        stats=Counter()
        for row in bindings:
            found=lookup.get(row['id'])
            row['languages'][lang_dir.name] = found
            stats['matched' if found else 'missing']+=1
        by_language[lang_dir.name] = dict(stats)
        item_stats=Counter()
        for row in items['rows']:
            uid=row[uidcol]
            candidates=names.get(uid,[])
            if candidates:
                translations[uid][lang_dir.name]=candidates
            item_stats['named_rows' if candidates else 'unnamed_rows']+=1
            item_stats['ambiguous_name_rows']+=len(candidates)>1
        item_name_stats[lang_dir.name]=dict(item_stats)
        print(json.dumps({'linked_language':lang_dir.name,'event_messages':dict(stats),
                          'item_names':dict(item_stats)}),flush=True)
    dump(OUT/'eventflow_message_bindings.json',{'languages':by_language,'references':bindings,
         'scope':'Qualified label lookup; does not validate control flow, rendering or placeholder expansion.'})
    models=json.loads((OUT/'catalogues/model.json').read_text())['entries']
    catalog_by_id=defaultdict(list)
    for i,row in enumerate(models):catalog_by_id[row['Asset_ID']].append(i)
    item_rows=[]
    model_stats=Counter()
    for index,row in enumerate(items['rows']):
        uid,resname=row[uidcol],row[rescol]
        candidates=catalog_by_id.get(resname,[])
        model_stats['exact_resource_name_catalogue_matches' if candidates else 'no_exact_resource_name_catalogue_match']+=1
        item_rows.append({'source_table_row':index,'unique_id':uid,'resource_name':resname,
                          'display_name_candidates_by_language':translations.get(uid,{}),
                          'model_catalogue_candidate_rows':candidates,
                          'model_matching_rule':'Exact ResName == Asset_ID; no fuzzy matching.'})
    dump(OUT/'item_localization_and_catalogue_links.json',{'source_table':'tables_resolved/ItemParam.json',
         'row_count':len(item_rows),'language_counts':item_name_stats,
         'model_match_counts':dict(model_stats),'items':item_rows})
    # Extract already-present UI GLSL text, retaining parent-container provenance.
    resources=json.loads((OUT/'resource_inventory.json').read_text())['resources']
    wanted=defaultdict(list)
    for r in resources:
        if r['member'].endswith('.glsl'):wanted[r['source']].append(r)
    shader_index=[]
    for source,entries in wanted.items():
        cache={'':inflate((ROMFS/source).read_bytes())}
        for record in entries:
            parts=record['member'].split('!');parent=''
            for part in parts:
                key=parent+'!'+part if parent else part
                if key not in cache:
                    children={n:b for n,o,b in sarc_members(cache[parent])}
                    cache[key]=inflate(children[part])
                parent=key
            content=cache[parent]
            if sha(content)!=record['sha256']:raise ValueError('Shader member SHA mismatch')
            record={**record,'text':content.decode('utf-8-sig')}
            name=sha((source+'!'+parent).encode())+'.json'
            dump(OUT/'shaders/glsl'/name,record)
            shader_index.append({'source':source,'member':parent,'sha256':record['sha256'],'json':'shaders/glsl/'+name})
    dump(OUT/'shaders/glsl/index.json',{'entries':shader_index,'scope':'Existing UI shader sources only; no complete shader conversion.'})
    # Drain gzip through EOF so its trailer CRC and original size are checked.
    archive=Path('/workspace/downloads/acnh_additional_romfs_2026-11-02/extracted_romfs.tar.gz')
    total=0
    with gzip.open(archive,'rb') as f:
        while chunk:=f.read(8*1024*1024):total+=len(chunk)
    checks={'gzip_crc_and_size':'passed','uncompressed_tar_bytes':total,
            'event_message_references':len(bindings),'event_bindings_by_language':by_language,
            'item_rows':len(item_rows),'item_names_by_language':item_name_stats,
            'model_match_counts':dict(model_stats),'ui_glsl_source_members':len(shader_index),
            'ui_glsl_unique_sources':len({x['sha256'] for x in shader_index}),
            'event_references_missing_in_all_languages':sum(all(v is None for v in r['languages'].values()) for r in bindings)}
    dump(OUT/'link_verification.json',checks)
    print(json.dumps(checks),flush=True)


if __name__=='__main__':main()
