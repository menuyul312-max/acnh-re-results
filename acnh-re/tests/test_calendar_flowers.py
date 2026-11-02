"""Verify new native findings against dates, raw tables and independent invariants."""
import collections
import datetime as dt
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
from calendar_native import packed,effective_day
from native_image import Image


def read(path):return json.loads((OUT/path).read_text())


class CalendarFlowerTests(unittest.TestCase):
    def test_original_sdk_calendar_cycle_and_day_boundary(self):
        d=read('calendar/native_verification.json')
        self.assertEqual(d['gregorian_cycle']['dates'],146097)
        self.assertEqual(d['comparisons'],314757);self.assertEqual(d['comparisons'],sum(d['groups'].values()))
        self.assertFalse(d['mismatches']);self.assertEqual(d['dependencies_stubbed'],[]);self.assertEqual(d['unsupported_os_calls'],[])
        self.assertEqual(d['groups']['main_day_normalization_and_guard'],16268)
        for sample in d['samples']:
            value=dt.datetime.fromisoformat(sample['input']);expected=effective_day(value)
            self.assertEqual(dt.datetime.fromisoformat(sample['output']),expected)
            self.assertEqual(bytes.fromhex(sample['native_hex']),packed(expected))
        link=read('native_modules/relocation_verification.json')
        self.assertEqual(link['pointer_checks'],355478);self.assertEqual(link['pointer_mismatches'],0)
        self.assertEqual(link['pointer_checks'],sum(sum(counts.values())for counts in link['relocations_applied'].values()))
        self.assertFalse(link['initializers_executed']);self.assertFalse(link['tls_initialized'])
        self.assertEqual(link['unsupported_os_calls'],[]);self.assertEqual(link['dependencies_stubbed'],[])

    def test_linked_weather_uses_previous_date_before_five(self):
        d=read('weather/native_linked_verification.json')
        self.assertTrue(d['day_boundary_verified']);self.assertEqual(d['comparisons'],59756)
        self.assertEqual((d['prediction_comparisons'],d['draw_state_comparisons']),(27512,27512))
        self.assertFalse(d['mismatches']);self.assertEqual(d['dependencies_stubbed'],[]);self.assertEqual(d['unsupported_os_calls'],[])
        for sample in d['samples']:
            value=dt.datetime(*sample['date'],*sample['time']);expected=value.date()-dt.timedelta(days=int(value.hour<5))
            self.assertEqual(sample['effective_date'],[expected.year,expected.month,expected.day])
        self.assertTrue(any(s['date'][0]!=s['effective_date'][0]for s in d['samples']))

    def test_native_flower_results_and_source_genotype_links(self):
        d=read('flowers/native_verification.json');self.assertFalse(d['mismatches']);self.assertEqual(d['dependencies_stubbed'],[])
        self.assertEqual(d['parent_byte_pairs_exhaustive'],65536)
        self.assertEqual(d['comparisons'],sum(d['groups'].values()));self.assertEqual(d['groups']['offspring_gene'],66560)
        self.assertEqual(d['groups']['conditional_rng_draw_order'],66560)
        self.assertEqual((d['genotype_rows'],d['probability_parent_pairs']),(270,6561))
        self.assertEqual(sum(d['species_counts'].values()),270);self.assertEqual(d['species_counts']['FlwRose'],81)
        source=read('tables_resolved/FgFlowerHeredity.json');fields={c['name']:i for i,c in enumerate(source['columns'])}
        fg=read('tables_resolved/FgMainParam.json');fi={c['name']:i for i,c in enumerate(fg['columns'])};defs={r[fi['UniqueID']]:r for r in fg['rows']}
        genotypes=read('flowers/genotypes.json');im=Image();enum=genotypes['native_kind_enum'];literal=im.cstring(int(enum['va'],16))
        self.assertEqual(literal,enum['literal']);self.assertEqual(hashlib.sha256(literal.encode()).hexdigest(),enum['sha256'])
        kinds=literal.rstrip(',').split(',')
        for entry in genotypes['genotype_rows']:
            row=source['rows'][entry['source_row_index']]
            self.assertEqual(zlib.crc32(entry['kind'].encode()),int(row[fields['Kind']]['hash'],16))
            self.assertEqual(kinds[entry['native_kind_index']],entry['kind'])
            self.assertEqual(entry['allele_dosages'],[row[fields['Heredity'+l]]for l in 'ABCD'])
            self.assertEqual([(entry['canonical_gene_byte']>>(2*i)&3).bit_count()for i in range(4)],entry['allele_dosages'])
            for key,col in [('primary','Name'),('alternate_zero_growth','h_753336dd')]:
                value=row[fields[col]]
                if value==65534:self.assertIsNone(entry[key]);continue
                self.assertEqual(entry[key]['id'],value);self.assertEqual(entry[key]['label'],defs[value][fi['Label']])
            if entry['alternate_zero_growth']:self.assertEqual(entry['alternate_zero_growth']['grow'],0)

    def test_flower_probability_model_normalizes_and_is_parent_symmetric(self):
        d=read('flowers/inheritance_probabilities.json');self.assertEqual((d['denominator'],d['pair_count']),(256,6561))
        pairs={(p['parent_a'],p['parent_b']):{c['gene']:c['weight']for c in p['children']}for p in d['pairs']}
        self.assertEqual(len(pairs),81**2);self.assertEqual(sum(len(v)for v in pairs.values()),15**4)
        for (a,b),children in pairs.items():
            self.assertEqual(sum(children.values()),256);self.assertEqual(children,pairs[b,a])
            self.assertTrue(all(g in d['canonical_genotypes']for g in children))
        self.assertEqual(pairs[0,255],{85:256})
        self.assertEqual(pairs[0,0],{0:256});self.assertEqual(pairs[255,255],{255:256})

    def test_black_cosmos_cycle_is_preserved_and_bounded(self):
        d=read('flowers/growth_cycles.json');self.assertEqual(len(d['cases']),24)
        self.assertTrue(d['source_values_preserved']);self.assertEqual(d['resource_ids'],[60151,60153,60155])
        source=read('tables_resolved/FgMainParam.json');fields={c['name']:i for i,c in enumerate(source['columns'])}
        rows={r[fields['UniqueID']]:r for r in source['rows']}
        self.assertEqual([rows[v][fields['Grow']]for v in d['resource_ids']],[2,3,0])
        self.assertEqual([rows[v][fields['GrowupFg']]if rows[v][fields['GrowupFg']]!=65534 else rows[v][fields['ChangeFg']]for v in d['resource_ids']],[60153,60155,60151])
        for case in d['cases']:
            self.assertFalse(case['returned']);self.assertEqual(case['instruction_limit'],20000)
            self.assertEqual(case['observed_first_ids'][:6],[60151,60153,60155]*2)

    def test_default_flower_genes_prefer_flag_else_last_matching_row(self):
        doc=read('flowers/default_genes.json');source=read('tables_resolved/FgFlowerHeredity.json');fields={c['name']:i for i,c in enumerate(source['columns'])}
        for entry in doc['entries']:
            row=source['rows'][entry['source_genotype_row']]
            candidates=[(i,r)for i,r in enumerate(source['rows'])if r[fields['Kind']]['hash']==row[fields['Kind']]['hash']and r[fields['Name']]==entry['normalized_bud_id']]
            selected=next((i for i,r in candidates if r[fields['DefaultHeredity']]),candidates[-1][0])
            self.assertEqual(selected,entry['source_genotype_row'])
            expected=sum([0,1,3][row[fields['Heredity'+l]]]<<(i*2)for i,l in enumerate('ABCD'))
            self.assertEqual(expected,entry['native_gene_byte'])
        by_id={r['resource_id']:r for r in doc['entries']}
        self.assertEqual(by_id[60261]['native_gene_byte'],16)
        self.assertEqual(by_id[60264]['native_gene_byte'],67)
        self.assertEqual(by_id[60267]['native_gene_byte'],12)

    def test_complete_flower_item_caller_and_freeparam_gene_byte(self):
        d=read('flowers/native_verification.json');items=read('flowers/offspring_items.json')
        self.assertEqual(d['offspring_item_parent_pairs'],11664);self.assertEqual(d['item_gene_offset'],4)
        for group in ['complete_offspring_item_and_guard','offspring_item_rng_state','parent_items_unchanged']:
            self.assertEqual(d['groups'][group],11664)
        self.assertEqual(items['same_species_canonical_parent_pairs'],11664)
        self.assertEqual(items['native_function'],'0x4d5e50')
        for example in items['samples']:
            item=bytes.fromhex(example['offspring_item_hex']);self.assertEqual(len(item),8)
            ident,system,additional,free=struct.unpack('<HBBI',item)
            self.assertEqual(ident,example['offspring_resource_id'])
            self.assertEqual((system,additional,free),(0,0,example['offspring_gene']))
            self.assertEqual(bytes.fromhex(example['parent_item_a_hex'])[4],example['parent_gene_a'])
            self.assertEqual(bytes.fromhex(example['parent_item_b_hex'])[4],example['parent_gene_b'])


if __name__=='__main__':unittest.main()
