"""Check new ExeFS provenance, symbol matches and bounded NPC/SDK execution."""
import hashlib
import json
from pathlib import Path
import struct
import sys
import unittest

ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/'output'
sys.path.insert(0,str(ROOT/'tools'))
from exefs_modules import NsoModule,DEFAULT_INPUT,npdm_info
from native_image import Image


def read(path):return json.loads((OUT/path).read_text())


class AdditionalExefsTests(unittest.TestCase):
    def test_uploaded_main_and_npdm_match_previous_effective_content(self):
        doc=read('native_modules/summary.json')
        self.assertEqual(doc['segment_hashes_verified'],12)
        self.assertTrue(doc['main_matches_previous_elf']);self.assertTrue(doc['npdm_program_id_match'])
        self.assertEqual(doc['symbols_all_modules'],37517)
        for segment in doc['main_segment_comparison']:
            self.assertTrue(segment['exact_match']);self.assertEqual(segment['nso_sha256'],segment['previous_elf_sha256'])
        comparison=read('native_modules/npdm_comparison.json')
        self.assertFalse(comparison['exact_match']);self.assertEqual(comparison['differing_byte_count'],510)
        self.assertTrue(comparison['remaining_bytes_identical'])
        self.assertTrue(comparison['changes_confined_to_acid_signature_and_public_key'])
        self.assertEqual(comparison['uploaded']['program_id'],'01006f8002326000')
        if not (DEFAULT_INPUT/'main').exists():self.skipTest('Original uploaded executables must be provided separately')
        im=Image();raw=(DEFAULT_INPUT/'main').read_bytes();module=NsoModule(raw)
        for segment in module.segments:self.assertEqual(segment['data'],im.read(segment['va'],segment['size']))
        corrupted=bytearray(raw);corrupted[0xa0]^=1
        with self.assertRaisesRegex(ValueError,'SHA-256'):NsoModule(bytes(corrupted))
        for bad in [b'',b'NSO0'+bytes(251)]:
            with self.assertRaises(ValueError):NsoModule(bad)
        with self.assertRaises(ValueError):module.read(0xffffffffffffffff,1)
        self.assertEqual(npdm_info((DEFAULT_INPUT/'main.npdm').read_bytes()),comparison['uploaded'])

    def test_static_import_candidates_exist_in_the_actual_export_tables(self):
        docs={name:read(f'native_modules/{name}.json')for name in ['rtld','main','subsdk0','sdk']}
        resolution=read('native_modules/import_resolution.json')
        self.assertEqual((resolution['main']['imports'],resolution['main']['with_export_candidate']),(910,898))
        exports={(module,s['index']):s for module,doc in docs.items()for s in doc['symbols']if s['section']}
        for module,record in resolution.items():
            for binding in record['bindings']:
                self.assertEqual(binding['symbol'],docs[module]['symbols'][binding['symbol']['index']])
                for candidate in binding['export_candidates']:
                    actual=exports[candidate['module'],candidate['index']]
                    self.assertEqual(actual['name'],binding['symbol']['name'])
                    self.assertEqual(actual['va'],candidate['va'])
        unresolved=resolution['main']['unresolved'];self.assertEqual(len(unresolved),12)
        self.assertTrue(all(b['symbol']['binding']==2 for b in unresolved))
        self.assertEqual(sum(b['symbol']['name'].startswith('glslc')for b in unresolved),8)
        self.assertEqual(sum(b['symbol']['name'].startswith('__rel_')for b in unresolved),4)
        sdk=docs['sdk'];self.assertEqual(sdk['soname'],'nnSdk.nss')
        for doc in docs.values():
            for segment in doc['segments']:self.assertTrue(segment['header_hash_verified'])
            path=Path(doc['input_file'])
            if path.exists():self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),doc['input_sha256'])

    def test_original_sdk_strcmp_and_cross_module_byml_are_stub_free(self):
        cmp=read('native_modules/strcmp_native_verification.json');byml=read('native_modules/linked_byml_verification.json')
        self.assertEqual(cmp['comparisons'],67714);self.assertFalse(cmp['mismatches'])
        self.assertEqual(cmp['dependencies_stubbed'],[]);self.assertEqual(byml['dependencies_stubbed'],[])
        self.assertIsNone(byml['substituted_dependency']);self.assertFalse(byml['mismatches'])
        self.assertEqual(byml['strcmp_calls'],84560);self.assertEqual(byml['comparisons'],2546185)
        old=read('byml_typed/native_verification.json')
        for key in ['constructors_accepted','physical_dictionary_entries','physical_array_entries','groups']:
            self.assertEqual(byml[key],old[key])
        self.assertEqual(byml['linked_module']['strcmp_module_va'],'0x4d7900')
        self.assertEqual(byml['linked_module']['main_got_relocation_site'],'0x32cede0')
        self.assertEqual(byml['linked_module']['module_sha256'],read('native_modules/sdk.json')['input_sha256'])

    def test_npc_columns_retain_hashes_and_match_every_raw_voice_byte(self):
        doc=read('npc/voice_configuration_native.json')
        self.assertEqual((doc['source_rows_checked'],doc['column_bindings'],doc['comparisons']),(459,6,995))
        self.assertEqual(doc['comparisons'],sum(doc['groups'].values()))
        self.assertEqual(doc['dependencies_stubbed'],[]);self.assertFalse(doc['mismatches'])
        self.assertEqual(doc['original_names_recovered'],0)
        manifest=read('manifest.json')['entries']
        for table in doc['tables']:
            source=manifest[table['source_id']];self.assertEqual(source['sha256'],table['source_sha256'])
            resolved=read('tables_resolved/'+table['table']+'.json')
            raw=(OUT/table['raw']['$blob']).read_bytes()
            indices=[next(i for i,c in enumerate(resolved['columns'])if c['hash']==f['hash'])for f in table['fields']]
            for f in table['fields']:self.assertIsNone(f['original_name'])
            for row in table['rows']:
                values=[raw[o]for o in row['source_byte_offsets']]
                self.assertEqual(values,row['config_bytes_44_45_46'])
                self.assertEqual(values,[resolved['rows'][row['row_index']][i]for i in indices])
        self.assertEqual(len(doc['missing_field_cases']),16)


if __name__=='__main__':unittest.main()
