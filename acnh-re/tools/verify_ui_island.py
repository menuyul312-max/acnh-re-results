"""Check source census, references and exact keyframe byte reconstruction.

These checks validate structural fidelity, not animation playback or handlers.
"""
from collections import Counter
import hashlib
import json
import struct
from ui_island_audit import ROOT, OUT, ROMFS, inflate, sarc_members


def main():
    raw = {}
    def scan(source, member, b):
        b = inflate(b)
        if b[:4] == b'SARC':
            for name, _, data in sarc_members(b):
                scan(source, member+'!'+name if member else name, data)
        elif b[:4] in (b'FLYT',b'FLAN'):
            raw[(source,member)] = b
    for p in sorted((ROMFS/'Layout').iterdir()):
        scan(str(p.relative_to(ROMFS)), '', p.read_bytes())
    layouts = json.loads((OUT/'layouts.json').read_text())['layouts']
    anims = json.loads((OUT/'animations.json').read_text())['animations']
    assert len(layouts)==523 and len(anims)==2095
    assert {(x['source'],x['member']) for x in layouts+anims} == set(raw)
    inventory = json.loads((ROOT/'output/additional_romfs/resource_inventory.json').read_text())['resources']
    inv = {(x['source'],x['member']):x for x in inventory}
    counts = Counter()
    for x in layouts+anims:
        b=raw[(x['source'],x['member'])]
        assert hashlib.sha256(b).hexdigest()==x['sha256']==inv[(x['source'],x['member'])]['sha256']
        assert len(b)==x['bytes']
    for a in anims:
        d=json.loads((ROOT/'output'/a['json']).read_text())
        b=raw[(a['source'],a['member'])]
        for content in d['contents']:
            for info in content['infos']:
                for t in info['targets']:
                    fmt='<fff' if t['curve_type_id']==2 else '<fHH'
                    recovered=b''.join(struct.pack(fmt,*key) for key in t['keys'])
                    start=t['key_data_offset']
                    assert b[start:start+len(recovered)]==recovered
                    assert len(t['keys'])==t['key_count']
                    counts['keyframe_byte_roundtrips']+=len(t['keys'])
                    counts['tracks']+=1
        for t in a['targets']:
            assert t['same_container_name_candidates']
            counts['animation_target_name_links']+=1
    for layout in layouts:
        ids={c['id'] for c in layout['components']}
        assert ids==set(range(len(ids)))
        for c in layout['components']:
            assert c['parent_id'] is None or 0<=c['parent_id']<c['id']
            if 'material' in c: assert 0<=c['material']<len(layout['materials'])
            if 'font' in c: assert 0<=c['font']<len(layout['fonts'])
            counts['panes']+=1
        assert all(not g['unmatched_panes'] for g in layout['groups'])
    island=json.loads((OUT/'island.json').read_text())
    assert len(island['coast_templates'])==36 and len(island['parts'])==136
    for t in island['coast_templates']:
        assert len(t['slots'])==22
        for s in t['slots']:
            assert s['candidate_parts']
            assert all(p['PartsKind']['hash']==s['kind']['hash'] for p in s['candidate_parts'])
            counts['coast_slot_joins']+=1
    assert len(island['preset_bindings'])==96
    for p in island['preset_bindings']:
        links=p['links']
        assert all(len(links['FieldData'][suffix])==1 for suffix in ('LandMaking','EventPlaza'))
        assert len(links['StructureData'])==len(links['ItemData'])==1
        counts['preset_source_bundles']+=1
    summary=json.loads((OUT/'summary.json').read_text())
    assert not summary['errors']
    assert counts['tracks']==16162 and counts['keyframe_byte_roundtrips']==92038
    report={'passed':True,'source_members':len(raw),'checks':dict(counts),
            'native_cases_added':0,
            'scope':'Structural source fidelity and reference integrity; not game/UI execution.'}
    (OUT/'verification.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    main()
