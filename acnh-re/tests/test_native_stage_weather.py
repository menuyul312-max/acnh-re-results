"""Integration checks against raw pointers, native tables and independent views."""
import collections
import hashlib
import json
from pathlib import Path
import struct
import sys
import unittest
import zlib

ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/'output'
sys.path.insert(0,str(ROOT/'tools'))
sys.path.insert(0,str(ROOT/'tools/reference'))
from acnh_rip.re.immscan import murmur3
from native_image import Image
from weather_corpus import rust_array
from weather_native import predict


def read(path):return json.loads((OUT/path).read_text())


class NativeStageWeatherTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.image=Image();cls.sha=hashlib.sha256(cls.image.data).hexdigest()
        cls.manifest=read('manifest.json')['entries']

    def test_original_byml_reader_covers_every_physical_entry(self):
        doc=read('byml_typed/native_verification.json')
        self.assertEqual(doc['native_elf_sha256'],self.sha)
        self.assertEqual((doc['files'],doc['constructors_accepted']),(2313,2313))
        self.assertEqual((doc['physical_dictionary_entries'],doc['physical_array_entries']),(443204,319774))
        self.assertEqual(doc['comparisons'],sum(doc['groups'].values()))
        self.assertEqual(doc['comparisons'],2546185);self.assertFalse(doc['mismatches'])
        self.assertEqual(doc['substituted_dependency']['name'],'strcmp')
        self.assertIn('not index bounds',doc['dictionary_index_contract']['behavior'])
        for file in doc['file_results']:
            entry=self.manifest[file['source_id']]
            self.assertEqual(file['source_sha256'],entry['sha256'])
            graph=read(file['json']);counts=collections.Counter()
            for node in graph['nodes']:counts[node['type']]+=len(node['entries'])
            self.assertEqual(file.get('dict_entries',0),counts['dict'])
            self.assertEqual(file.get('array_entries',0),counts['array'])

    def test_typed_arrays_and_native_stage_key_roles(self):
        doc=read('schemas/byml_names.json')
        names={r['selected']['descriptor']:r['selected']for r in doc['keys'].values()if r['selected']}
        for name in ['mValueBuffer[].bool','mWeatherType[].Enum','mWindType[].Enum','mRate[].s8']:
            self.assertIn(name,names)
            self.assertTrue(names[name]['declared_type'].startswith('array<'))
        self.assertEqual(len(doc['native_array_types']),11)
        for field in json.loads((ROOT/'tools/knowledge/stage_key_roles.json').read_text())['fields']:
            selected=doc['keys'][field['hash']]['selected']
            self.assertEqual(selected['descriptor'],field['name'])
            self.assertEqual(selected['algorithm'],'Murmur3_32_seed0')
            self.assertEqual(selected['native_role_evidence'],field)
        for record in doc['keys'].values():
            for candidate in record['candidates']:
                if candidate['algorithm']=='CRC32':self.assertNotIn('native_reader_role',candidate['sources'])

    def test_actor_registry_and_stage_records_match_source(self):
        registry=read('stage/actor_type_registry.json');by_hash={}
        pairs={h:i for h,i in struct.iter_unpack('<II',self.image.read(0x29d775c,158*8))}
        self.assertEqual(len(registry['entries']),158)
        for r in registry['entries']:
            self.assertEqual(self.image.cstring(int(r['name_string_va'],16)),r['name'])
            self.assertEqual(murmur3(r['name'].encode()),r['murmur_hash_u32'])
            self.assertEqual(pairs[r['murmur_hash_u32']],r['index']);by_hash[r['murmur_hash_u32']]=r
        actors=transitions=unknown=0
        for rec in read('stage/catalogue.json'):
            if 'json'not in rec:continue
            doc=read(rec['json']);entry=self.manifest[doc['source_id']]
            source=read(entry['decoded'])['data']['root']
            self.assertEqual(doc['source_sha256'],entry['sha256'])
            for kind,key in [('actors','3cbaa541'),('transitions','5cf34787')]:
                self.assertEqual(len(doc[kind]),len(source.get(key,[])))
                for i,record in enumerate(doc[kind]):
                    self.assertEqual(record['raw_record'],source[key][i])
                    self.assertEqual(record['source_pointer'],f'/{key}/{i}')
                    if kind=='actors':
                        found=by_hash.get(record['actor_kind_hash']);actors+=1
                        self.assertEqual(record['native_actor_kind_index'],found['index']if found else 0xffffffff)
                        unknown+=not bool(found)
                    else:transitions+=1
        self.assertEqual((actors,transitions,unknown),(311,142,18))
        doc=read('stage/native_summary.json');self.assertEqual(doc['native_elf_sha256'],self.sha)
        self.assertEqual((doc['native_projection_checks'],doc['native_trig_checks']),(284,265))
        self.assertFalse(doc['mismatches']);self.assertEqual(doc['unregistered_actor_hashes'],3)
        for case in read('stage/trig_verification.json')['cases']:self.assertEqual(case['native_hex'],case['expected_hex'])

    def test_native_byte_views_and_public_crc_candidates(self):
        doc=read('schemas/native_read_views.json');self.assertEqual(doc['native_elf_sha256'],self.sha)
        self.assertEqual((doc['native_byte_view_count'],doc['raw_rows_checked']),(4,1172))
        self.assertEqual((doc['byte_load_comparisons'],doc['animation_fallback_comparisons']),(1024,1024))
        self.assertFalse(doc['mismatches']);self.assertEqual(doc['dependencies_stubbed'],[])
        for f in doc['fields']:
            self.assertEqual(bytes.fromhex(f['load_raw_hex']),self.image.read(int(f['value_load_pc'],16),4))
            table=read('tables_resolved/'+f['table']+'.json')
            col=next(c for c in table['columns']if c['hash']==f['hash'])
            self.assertIsNone(col['descriptor']);self.assertEqual(col['type'],f['type'])
        human=read('tables_resolved/HumanAnimParam.json');i=next(i for i,c in enumerate(human['columns'])if c['hash']=='d5217761')
        self.assertEqual(sum(r[i]==-1 for r in human['rows']),445)
        audit=read('schemas/public_descriptor_audit.json')
        self.assertEqual((audit['matching_columns'],audit['width_rejections'],audit['promoted']),(10,7,0))
        for c in audit['columns']:
            self.assertEqual(zlib.crc32(c['candidate']['descriptor'].encode()),int(c['column_hash'],16))
            self.assertFalse(c['promoted'])

    def test_native_flag_policy_and_integer_rng(self):
        flags=read('flags/reset_policy_native.json');rng=read('random/native_rng.json')
        for doc in [flags,rng]:
            self.assertEqual(doc['native_elf_sha256'],self.sha);self.assertFalse(doc['mismatches'])
            self.assertEqual(doc['dependencies_stubbed'],[])
        self.assertEqual((flags['comparisons'],flags['table_count'],flags['row_count']),(8910,5,884))
        self.assertIsNone(flags['original_field_name'])
        policies=collections.Counter()
        for table in flags['tables']:
            raw=read('tables_resolved/'+table['table']+'.json')
            i=next(i for i,c in enumerate(raw['columns'])if c['hash']=='5140e4b4')
            for row in table['rows']:
                self.assertEqual(row['raw_policy'],raw['rows'][row['row_index']][i]);policies[str(row['raw_policy'])]+=1
        self.assertEqual(dict(policies),flags['observed_policy_counts'])
        self.assertEqual(rng['comparisons'],35567);self.assertEqual(rng['comparisons'],sum(rng['groups'].values()))
        self.assertEqual(rng['zero_explicit_state_fallback'],[1,0x6c078967,0x714acb41,0x48077044])

    def test_weather_preserves_reference_differences_and_native_prediction(self):
        weather=read('weather/summary.json');native=read('weather/native_verification.json')
        self.assertEqual((weather['pattern_count'],weather['rate_table_count'],weather['total_comparisons']),(34,40,6398))
        self.assertEqual(len(weather['reference_differences']),4);self.assertFalse(weather['unexpected_differences'])
        self.assertEqual(native['native_elf_sha256'],self.sha);self.assertFalse(native['mismatches'])
        self.assertEqual(native['dependencies_stubbed'],[])
        self.assertEqual((native['calendar_comparisons'],native['weighted_selection_comparisons']),(732,4000))
        self.assertGreater(native['prediction_comparisons'],6800)
        self.assertEqual(native['prediction_comparisons'],native['draw_state_comparisons'])
        self.assertEqual(native['comparisons'],sum(native[k]for k in ['calendar_comparisons','weighted_selection_comparisons','prediction_comparisons','draw_state_comparisons']))
        patterns=read('weather/patterns.json')['patterns'];manifest=self.manifest
        e=next(e for e in manifest if e['source'].endswith('/WeatherPattern.byml'))
        original=read(f"byml_resolved/{e['id']:05d}.json")['root']['@WeatherPattern']['@mParams']
        for pattern in patterns:
            source=original['@cWeatherPattern_'+str(pattern['index'])]
            self.assertEqual(pattern['weather_labels'],source['@mWeatherType[].Enum'])
            self.assertEqual(pattern['wind_labels'],source['@mWindType[].Enum'])
        rates=read('weather/rates.json')['rates']
        for sample in native['samples']:
            predicted,_,slot,table=predict(sample['stored_seed'],*sample['date'],rates[sample['hemisphere']]['tables'])
            self.assertEqual((predicted,slot,table),(sample['pattern_index'],sample['roll'],sample['rate_index']))
        self.assertEqual(rust_array('pub static TEST: [[u8;2];1] = [[1,2]];','TEST'),[[1,2]])
        with self.assertRaises(ValueError):rust_array('pub static TEST: [u8;1] = [1+1];','TEST')


if __name__=='__main__':unittest.main()
