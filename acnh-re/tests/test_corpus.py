import hashlib
import json
from pathlib import Path
import sqlite3
import struct
import sys
import unittest
import zipfile
import zlib

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'output'
SOURCE = Path('/workspace/downloads/ACNH_island_RE/ACNH_island_RE')
sys.path.insert(0, str(ROOT / 'tools'))
from conditions import read_condition, normalized, parse_text
from reverse_corpus import yaz0


class CorpusTests(unittest.TestCase):
    def test_input_and_container_coverage(self):
        m = json.loads((OUT / 'manifest.json').read_text())['entries']
        self.assertEqual(sum(e['parent_id'] is None for e in m), 1171)
        self.assertEqual(len(m), 2986)
        self.assertFalse([e for e in m if e['status'] not in ('structure_decoded', 'container_validated')])
        seen = set()
        for e in m:
            self.assertEqual(e['id'], m[e['id']]['id'])
            p = OUT / e['raw']['$blob']
            self.assertTrue(p.is_file(), e['source'])
            if e['sha256'] not in seen:
                b = p.read_bytes()
                self.assertEqual(hashlib.sha256(b).hexdigest(), e['sha256'])
                self.assertEqual(len(b), e['size'])
                seen.add(e['sha256'])
            if e.get('decoded'):
                self.assertEqual(json.loads((OUT / e['decoded']).read_text())['source_sha256'], e['sha256'])

    def test_data_relationships(self):
        s = json.loads((OUT / 'semantic_summary.json').read_text())
        self.assertEqual(s['bcsv_values_checked_against_prior_export'], 1116909)
        self.assertEqual(s['bcsv_export_mismatches'], 0)
        self.assertEqual(s['prior_binary_reference_errors'], 0)
        self.assertEqual(s['prior_binary_references_checked'], 5052)
        self.assertEqual(s['supplementary_byml_exports'], 58)
        self.assertEqual(s['terrain_records_checked'], 1032192)
        self.assertEqual(s['terrain_mismatches'], 0)
        self.assertEqual(s['bgm_missing_destinations'], 0)
        i = json.loads((OUT / 'index_summary.json').read_text())
        self.assertEqual(i['event_flag_labels_resolved'], i['event_flag_references'])
        self.assertEqual(i['subflow_targets_missing'], 0)
        self.assertEqual(i['subflow_entries_missing'], 0)

    def test_all_audio_condition_blobs(self):
        records = json.loads((OUT / 'audio/condition_bytecode.json').read_text())['conditions']
        self.assertEqual(len(records), 2644)
        mismatches = []
        for r in records:
            raw = (OUT / r['raw']['$blob']).read_bytes()
            actual = read_condition(raw)
            self.assertEqual(actual, r['decoded'])
            if normalized(actual['ast']) != normalized(parse_text(r['text'])):
                mismatches.append(r)
        # Preserve this observed text/bytecode discrepancy; do not "fix" original data.
        self.assertEqual(len(mismatches), 1)
        self.assertIn('$29!=59 || $28!=23', mismatches[0]['text'])

    def test_condition_rejects_cycles_and_truncation(self):
        valid = bytes.fromhex('433118000800010f0601020009010f000b0004000000803f')
        self.assertEqual(read_condition(valid)['ast'], ['==', ['var', 15], ['number', 1.0]])
        for i in range(len(valid)):
            with self.assertRaises((ValueError, struct.error)):
                read_condition(valid[:i])
        cyclic = bytearray(valid)
        cyclic[9] = 0
        with self.assertRaisesRegex(ValueError, 'cyclic'):
            read_condition(bytes(cyclic))

    def test_yaz0_rejects_invalid_backreference(self):
        data = b'Yaz0' + struct.pack('>I', 3) + b'\0' * 8 + b'\0\x10\0'
        with self.assertRaisesRegex(ValueError, 'back-reference'):
            yaz0(data)

    def test_query_index(self):
        db = sqlite3.connect(OUT / 'index.sqlite')
        self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0], 'ok')
        self.assertEqual(db.execute('SELECT count(*) FROM files').fetchone()[0], 2986)
        self.assertEqual(db.execute('SELECT count(*) FROM columns').fetchone()[0], 2048)
        self.assertEqual(db.execute('SELECT count(*) FROM decomp').fetchone()[0], 6402)
        self.assertGreater(db.execute('SELECT count(*) FROM hash_refs').fetchone()[0], 2352)
        db.close()

    def test_original_archive_files_unchanged(self):
        archive = SOURCE.parent.parent / 'ACNH_island_RE.zip'
        with zipfile.ZipFile(archive) as z:
            for entry in z.infolist():
                if entry.is_dir():
                    continue
                p = SOURCE.parent / entry.filename
                self.assertEqual(zlib.crc32(p.read_bytes()) & 0xffffffff, entry.CRC, entry.filename)

    def test_resolved_schema_descriptors_and_enum_labels(self):
        named, columns, enum_values = 0, 0, 0
        for p in (OUT / 'tables_resolved').glob('*.json'):
            table = json.loads(p.read_text())
            columns += len(table['columns'])
            for c in table['columns']:
                if c['descriptor']:
                    self.assertEqual(zlib.crc32(c['descriptor'].encode()), int(c['hash'],16))
                    named += 1
                self.assertLessEqual(c['offset']+c['width'], table['row_size'])
                if c['enum_values']:
                    for h, labels in c['enum_values'].items():
                        label = labels[1] if table['enum_language']=='Japanese' else labels[0]
                        self.assertEqual(zlib.crc32(label.encode()), int(h,16))
                        enum_values += 1
            self.assertEqual(len(table['rows']), table['row_count'])
        self.assertEqual((named,columns),(1957,2048))
        self.assertGreater(enum_values, 1000)

    def test_native_evidence_and_dispatch_bounds(self):
        from native_image import Image
        im = Image()
        expected = hashlib.sha256(im.data).hexdigest()
        verification = json.loads((OUT/'native_verification.json').read_text())
        curves = json.loads((OUT/'environment/curves.json').read_text())
        builtin = json.loads((OUT/'binary/exit_flowchart_verification.json').read_text())
        for doc in [verification,curves,builtin]:
            self.assertEqual(doc['native_elf_sha256'],expected)
        self.assertFalse(verification['terrain']['mismatches'])
        self.assertEqual(verification['c1']['native_comparisons'],6580)
        self.assertFalse(verification['c1']['mismatches'])
        self.assertEqual((curves['record_count'],curves['comparisons']),(360,25253))
        self.assertFalse(curves['mismatches'])
        self.assertEqual(builtin['mismatches'],0)
        handlers = json.loads((OUT/'binary/event_handlers_resolved.json').read_text())
        self.assertEqual(handlers['counts']['native_factories'],1056)
        self.assertEqual(handlers['counts']['with_vtable'],1056)
        self.assertEqual(handlers['counts']['unique_native_factories'],904)
        self.assertEqual(handlers['counts']['constructors_traced'],904)
        self.assertEqual(handlers['counts']['slot_spans_hitting_limit'],0)
        self.assertFalse(handlers['unresolved'])
        for rec in handlers['entries'].values():
            if rec['kind']=='queries':self.assertGreaterEqual(len(rec.get('slots',[])),7)
            for i,raw_target in enumerate(rec.get('slots_raw',[])):
                self.assertEqual(int(raw_target,16),im.ptr(int(rec['vtable'],16)+8*i))
            for target in rec.get('slots',[]):
                va = int(target,16)
                self.assertEqual(va%4,0)
                self.assertTrue(any(s['p_flags']&1 and s['p_vaddr']<=va<s['p_vaddr']+s['p_filesz'] for s in im.segments))

    def test_constructor_trace_excludes_embedded_string_vptr(self):
        from native_image import Image
        from vptr_trace import trace
        im=Image()
        vtable,stores=trace(im,0x43b3b0)
        self.assertEqual(vtable,0x3058da8)
        self.assertEqual(stores[-1]['pc'],'0x43b3f4')
        self.assertNotEqual(vtable,0x301c1f0)
        self.assertEqual(trace(im,0x34de30)[0],0x304da48)

    def test_corrected_terrain_against_every_raw_record(self):
        atlas = json.loads((OUT/'relations/terrain_native.json').read_text())
        self.assertFalse(atlas['unknown_unit_ids'])
        self.assertFalse(atlas['out_of_range_variants'])
        disagreements, records = 0, 0
        for rec in atlas['presets']:
            data = json.loads((OUT/rec['json']).read_text())
            raw = (OUT/data['raw']['$blob']).read_bytes()
            for i, cell in enumerate(data['cells']):
                a,av,ar,b,bv,br,h = cell
                self.assertEqual((a,av,ar),struct.unpack_from('<HHB',raw,i*14))
                self.assertEqual((b,bv,br),struct.unpack_from('<HHB',raw,i*14+6))
                self.assertEqual(h,raw[i*14+12])
                if av != atlas['models'][str(a)]['max_variation']:disagreements+=1
                records+=1
        self.assertEqual(records,1032192)
        self.assertEqual(disagreements,54820)

    def test_dds_payloads_and_mip_dimensions(self):
        textures=json.loads((OUT/'environment/textures.json').read_text())
        self.assertEqual(sum(len(t['mips']) for t in textures),13)
        for t in textures:
            raw=(OUT/t['dds']).read_bytes()
            self.assertEqual(hashlib.sha256(raw).hexdigest(),t['sha256'])
            self.assertEqual(raw[:4],b'DDS ')
            self.assertEqual(struct.unpack_from('<I',raw,4)[0],124)
            self.assertEqual(raw[84:88],b'DX10')
            self.assertEqual(struct.unpack_from('<I',raw,128)[0],80)
            pos=148
            for mip in t['mips']:
                n=((mip['width']+3)//4)*((mip['height']+3)//4)*8
                self.assertEqual(n,mip['linear_bytes'])
                self.assertEqual(hashlib.sha256(raw[pos:pos+n]).hexdigest(),mip['linear_sha256'])
                pos+=n
            self.assertEqual(pos,len(raw))

    def test_independent_typed_byml_coverage(self):
        from typed_byml import decode
        summary=json.loads((OUT/'byml_typed/summary.json').read_text())
        self.assertEqual(summary['independent_tree_matches'],2313)
        self.assertEqual(summary['duplicate_dictionary_keys'],0)
        self.assertEqual(summary['tag_counts']['s64'],9397)
        # Independent parser preserves signed 64-bit wire bits and does not
        # silently turn an int64 into a JSON floating-point number.
        raw=bytearray(40)
        raw[:16]=b'YB'+struct.pack('<HIII',3,0,0,16)
        raw[16:20]=bytes([0xc0,1,0,0])
        raw[20]=0xd4
        struct.pack_into('<I',raw,24,32)
        struct.pack_into('<q',raw,32,-(2**63)+123)
        graph,flat=decode(bytes(raw))
        self.assertEqual(flat,[-(2**63)+123])
        self.assertEqual(graph['nodes'][0]['entries'][0]['decimal'],str(flat[0]))
        self.assertEqual(len(graph['integers_outside_json_safe_range']),1)

    def test_native_inventory_and_fallback_provenance(self):
        from native_image import Image
        im=Image()
        summary=json.loads((OUT/'binary/decompilation_summary.json').read_text())
        self.assertEqual(summary['targeted_with_pseudocode']+len(summary['missing']),summary['targeted_addresses'])
        self.assertEqual(summary['targeted_addresses'],64475)
        for missing in summary['missing']:
            raw=(OUT/missing['raw_region']).read_bytes()
            self.assertEqual(raw,im.read(int(missing['va'],16),missing['bytes_requested']))
            self.assertEqual(hashlib.sha256(raw).hexdigest(),missing['raw_sha256'])
            self.assertEqual(missing['bytes_represented'],len(raw))
        evidence=json.loads((OUT/'binary/critical_evidence.json').read_text())
        for region in evidence['regions'].values():
            raw=im.read(int(region['start_va'],16),region['bytes_requested'])
            self.assertEqual(hashlib.sha256(raw).hexdigest(),region['raw_sha256'])
        inventory=json.loads((OUT/'source_inventory.json').read_text())
        self.assertEqual(inventory['count'],15564)


if __name__ == '__main__':
    unittest.main()
