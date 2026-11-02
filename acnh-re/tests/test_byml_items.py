"""Cross-check the named views against independent raw/source representations."""
import collections
import hashlib
import json
from pathlib import Path
import struct
import sys
import unittest
import zlib

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT/'output'
sys.path.insert(0,str(ROOT/'tools'))
from byml_names import rename_tree
from item_words import decode_word
from acnh_rip.re.immscan import murmur3


class NamedBymlItemTests(unittest.TestCase):
    def test_named_byml_is_reversible_and_names_match_hash_algorithm(self):
        dictionary=json.loads((OUT/'schemas/byml_names.json').read_text())
        inverse={};algorithms=collections.Counter()
        for key,record in dictionary['keys'].items():
            selected=record['selected']
            if not selected:continue
            descriptor=selected['descriptor'];algorithm=selected['algorithm']
            hashed=zlib.crc32(descriptor.encode()) if algorithm=='CRC32' else murmur3(descriptor.encode())
            self.assertEqual(hashed,int(key,16),descriptor)
            self.assertTrue(selected['wire_family_compatible'])
            self.assertTrue(set(selected['sources']) & {'native_exact_string','native_referenced_string',
                'native_terminated_suffix','native_comma_list_member','native_utf8_string',
                'local_source_filename','local_BYML_string','local_BCSV_string','local_BCSV_field_name','native_reader_role'})
            inverse['@'+descriptor]=key;algorithms[algorithm]+=record['occurrences']
        self.assertEqual(dict(algorithms),dictionary['summary']['recovered_occurrences_by_algorithm'])
        catalogue=json.loads((OUT/'byml_resolved/catalogue.json').read_text())
        manifest=json.loads((OUT/'manifest.json').read_text())['entries']
        self.assertEqual({p.relative_to(OUT).as_posix() for p in (OUT/'decoded').glob('*.json')},
                         {entry['decoded'] for entry in manifest if entry.get('decoded')})
        self.assertEqual(len(catalogue),2313)
        for rec in catalogue:
            named=json.loads((OUT/rec['json']).read_text())
            entry=manifest[rec['source_id']]
            original=json.loads((OUT/entry['decoded']).read_text())['data']['root']
            self.assertEqual(named['source_sha256'],entry['sha256'])
            self.assertEqual(rename_tree(named['root'],inverse),original,entry['source'])
        # Leading-zero omission and scalar/container naming are distinct.
        self.assertEqual(dictionary['keys']['1c37a23']['selected']['descriptor'],'mWall.u16')
        self.assertEqual(dictionary['keys']['3503db35']['selected']['descriptor'],'mWall')
        self.assertEqual(dictionary['keys']['b3a97a50']['selected']['descriptor'],'mFtrList[]')
        self.assertEqual(dictionary['keys']['b4e54d00']['selected']['descriptor'],'GMO調整')

    def test_every_item_pointer_and_definition_against_primary_data(self):
        docs=json.loads((OUT/'items/catalogue.json').read_text())
        words=json.loads((OUT/'items/words.json').read_text())
        by_hex={r['hex_u64']:r for r in words['words']}
        actual=collections.Counter();positions=0
        manifest=json.loads((OUT/'manifest.json').read_text())['entries']
        table_cache={}
        for rec in docs:
            source=manifest[rec['source_id']]
            root=json.loads((OUT/source['decoded']).read_text())['data']['root']
            data=json.loads((OUT/rec['json']).read_text())
            self.assertEqual(data['source_sha256'],source['sha256'])
            for row in data['items']:
                value=root
                for component in row['source_pointer'].split('/')[1:]:
                    value=value[int(component)] if isinstance(value,list) else value[component]
                r=by_hex[row['word_hex']];actual[row['word_hex']]+=1
                self.assertEqual(value,int(r['decimal']))
                raw=bytes.fromhex(r['bytes_le'])
                self.assertEqual(int.from_bytes(raw,'little'),value)
                item,system,additional,free=struct.unpack('<HBBI',raw)
                self.assertEqual((item,system,additional,free),
                    (r['stored_item_id'],r['system_param'],r['additional_param'],r['free_param_u32']))
                if 'coordinates' in row:positions+=1
        self.assertEqual(sum(actual.values()),46034)
        self.assertEqual(positions,44443)
        for r in words['words']:
            self.assertEqual(actual[r['hex_u64']],r['occurrences'])
            definition=r['definition']
            if definition:
                name=definition['table']
                if name not in table_cache:table_cache[name]=json.loads((OUT/f'tables_resolved/{name}.json').read_text())
                table=table_cache[name];idx=next(i for i,c in enumerate(table['columns']) if c['name']=='UniqueID')
                self.assertEqual(table['rows'][definition['row_index']][idx],r['stored_item_id'])
            else:self.assertEqual(r['stored_item_id'],65534)
        self.assertEqual(words['summary']['definition_occurrences'],{'ItemParam':7471,'FgMainParam':38172,'empty':391})
        for invalid in [-1,1<<64,3.5]:
            with self.assertRaises(ValueError):decode_word(invalid)

    def test_native_item_evidence_and_reference_snapshots(self):
        v=json.loads((OUT/'items/native_verification.json').read_text())
        self.assertFalse(v['mismatches']);self.assertEqual(v['dependencies_stubbed'],[])
        self.assertGreater(v['comparisons'],9000)
        self.assertEqual(v['comparisons'],sum(v['groups'].values()))
        source=Path(json.loads((OUT/'manifest.json').read_text())['source_root'])
        raw=(source/'A_logic/main.elf').read_bytes()
        self.assertEqual(v['native_elf_sha256'],hashlib.sha256(raw).hexdigest())
        self.assertEqual(raw[50444884:50444884+16].hex(),'7fc1baff976aeca414520cb89f4616cb')
        references=ROOT/'tools/external'
        for rec in json.loads((references/'PINNED_SOURCES.json').read_text())['files']:
            self.assertEqual(hashlib.sha256((references/rec['local']).read_bytes()).hexdigest(),rec['sha256'])
        names=json.loads((OUT/'schemas/byml_names_summary.json').read_text())
        self.assertEqual(names['external_save_dictionary']['verified_murmur_entries'],1101)
        self.assertEqual(names['external_save_dictionary']['rejected_entries'][0]['name'],'AdditionalAudioInfoV')


if __name__=='__main__':unittest.main()
