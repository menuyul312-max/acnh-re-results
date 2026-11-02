#!/usr/bin/env python3
"""Verify flower inheritance and genotype/growth lookup against original code."""
import collections
import hashlib
import itertools
import json
from pathlib import Path
import random
import struct
import zlib

from native_byml_verify import ReaderSandbox
from native_rng import initialize,roll
from reverse_corpus import dump
from native_emulator import regs
from unicorn import UC_HOOK_CODE

ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/'output'
RNG_VA=0x35e9510
DOSAGE=[0,1,1,2]
ENCODE=[0,1,3]


def breed(a,b,state):
    state=list(state);child=0;draws=0
    for locus in range(4):
        total=0
        for parent in [a,b]:
            dosage=DOSAGE[(parent>>(2*locus))&3]
            if dosage==2:total+=1
            elif dosage==1:
                value,state=roll(state);draws+=1
                total+=int(((value*2)>>32)==0)
        child|=ENCODE[total]<<(2*locus)
    return child,state,draws


def distribution(a,b):
    outcomes={0:1}
    for locus in range(4):
        counts=collections.Counter()
        da=DOSAGE[(a>>(2*locus))&3];db=DOSAGE[(b>>(2*locus))&3]
        for ca in ([0,0]if da==0 else[0,1]if da==1 else[1,1]):
            for cb in ([0,0]if db==0 else[0,1]if db==1 else[1,1]):counts[ENCODE[ca+cb]]+=1
        outcomes={old|(gene<<(2*locus)):weight*count for old,weight in outcomes.items()for gene,count in counts.items()}
    return outcomes


def native_kinds(image):
    start=image.data.find(b'All,TreeOak,TreeOakStump,TreeCedar,')
    if start<0:raise ValueError('native Fg kind enum literal missing')
    end=image.data.index(0,start);literal=image.data[start:end].decode()
    names=literal.rstrip(',').split(',')
    if len(names)!=30 or names[21]!='FlwRose':raise ValueError('native Fg kind order changed')
    va=next(s['p_vaddr']+start-s['p_offset']for s in image.segments if s['p_offset']<=start<s['p_offset']+s['p_filesz'])
    return names,dict(va=hex(va),literal=literal,sha256=hashlib.sha256(image.data[start:end]).hexdigest())


def load_tables(s):
    manifest=json.loads((OUT/'manifest.json').read_text())['entries'];result={}
    for name in ['FgMainParam','FgFlowerHeredity']:
        table=json.loads((OUT/f'tables_resolved/{name}.json').read_text());source=manifest[table['source_id']]
        original=json.loads((OUT/source['decoded']).read_text())['data']
        result[name]=dict(table=table,source=source,original=original,raw=(OUT/table['raw']['$blob']).read_bytes())
    return result


def install_lookup_tables(s,tables,kinds):
    manager=s.HEAP+0x80000
    def q(at,value):s.uc.mem_write(at,struct.pack('<Q',value))
    def d(at,value):s.uc.mem_write(at,struct.pack('<I',value))
    q(s.image.ptr(0x32e2648),manager)
    for index,name in enumerate(['FgMainParam','FgFlowerHeredity']):
        item=tables[name];table=item['table'];original=item['original'];raw=item['raw'];base=s.HEAP+0x10000+index*0x20000
        s.uc.mem_write(base,raw);item['emulated_raw_base']=base
        obj=manager+index*0x200;holder=s.HEAP+0x90000+index*32;array=s.HEAP+0x91000+index*0x1000
        q(obj+0xb0,holder);q(holder+8,base);d(obj+0x1b0,table['row_count']);d(obj+0x1c0,table['row_count']);q(obj+0x1b8,array)
        for i in range(table['row_count']):q(array+i*8,base+original['data_start']+i*table['row_size'])
        fields={c['name']:i for i,c in enumerate(table['columns'])}
        if index==0:
            dense=s.HEAP+0x95000;minimum=min(r[fields['UniqueID']]for r in table['rows']);maximum=max(r[fields['UniqueID']]for r in table['rows'])
            d(manager+0x1d8,maximum-minimum+1);q(manager+0x1e0,dense);s.uc.mem_write(manager+0x1f8,struct.pack('<H',minimum))
            for i,row in enumerate(table['rows']):q(dense+(row[fields['UniqueID']]-minimum)*8,base+original['data_start']+i*table['row_size'])
            enum=s.image.ptr(0x32e26c8);d(enum,table['row_count']);target=s.HEAP+0x99000;q(enum+8,target)
            for i,row in enumerate(table['rows']):
                matches=[j for j,name in enumerate(kinds)if zlib.crc32(name.encode())==int(row[fields['Kind']]['hash'],16)]
                if len(matches)!=1:raise ValueError('native main-Fg kind/BCSV CRC mismatch')
                s.uc.mem_write(target+i*2,struct.pack('<H',matches[0]))
        else:
            enum=s.image.ptr(0x32e26c0);d(enum,table['row_count']);target=s.HEAP+0x97000;q(enum+8,target)
            for i,row in enumerate(table['rows']):
                matches=[j for j,name in enumerate(kinds)if zlib.crc32(name.encode())==int(row[fields['Kind']]['hash'],16)]
                if len(matches)!=1:raise ValueError('native kind/BCSV CRC mismatch')
                s.uc.mem_write(target+i*2,struct.pack('<H',matches[0]))
    return manager


def build():
    s=ReaderSandbox(substitute_strcmp=False);groups=collections.Counter();failures=[];draw_counts=collections.Counter();samples=[]
    if s.image.read(0x29d6398,4)!=bytes(DOSAGE)or s.image.read(0x29f5f82,3)!=bytes(ENCODE):raise ValueError('native flower gene tables changed')
    def check(group,actual,expected,context):
        groups[group]+=1
        if actual!=expected:
            failures.append(dict(group=group,actual=actual,expected=expected,**context))
            if len(failures)>10:raise ValueError(('systematic flower mismatch',failures[:4]))
    def verify_pair(a,b,seed):
        state=initialize(seed);s.uc.mem_write(RNG_VA-8,b'\xa5'*8+struct.pack('<4I',*state)+b'\x5a'*8)
        expected,end_state,draws=breed(a,b,state);actual=s.integer_call(0x4cd070,[a,b])&0xffffffff
        context=dict(parent_a=a,parent_b=b,seed=seed)
        check('offspring_gene',actual,expected,context)
        native_state=list(struct.unpack('<4I',bytes(s.uc.mem_read(RNG_VA,16))))
        check('conditional_rng_draw_order',native_state,end_state,context)
        check('rng_guard_bytes',bytes(s.uc.mem_read(RNG_VA-8,8)+s.uc.mem_read(RNG_VA+16,8)).hex(),(b'\xa5'*8+b'\x5a'*8).hex(),context)
        draw_counts[draws]+=1
        if a in [0,85,255]and b in [0,85,255]:samples.append(dict(**context,child=actual,rng_draws=draws))
    for a in range(256):
        for b in range(256):verify_pair(a,b,(0xac106^(((a<<8)|b)*0x9e3779b9))&0xffffffff)
    rng=random.Random(0xac107)
    for _ in range(1024):verify_pair(rng.getrandbits(32),rng.getrandbits(32),rng.getrandbits(32))
    kinds,kind_evidence=native_kinds(s.image);tables=load_tables(s);install_lookup_tables(s,tables,kinds)
    primary=tables['FgMainParam']['table'];fields={c['name']:i for i,c in enumerate(primary['columns'])}
    definitions={row[fields['UniqueID']]:dict(zip(fields,row))for row in primary['rows']}
    hereditary=tables['FgFlowerHeredity']['table'];hc={c['name']:i for i,c in enumerate(hereditary['columns'])}
    phenotype={};documents=[];species_counts=collections.Counter()
    for i,row in enumerate(hereditary['rows']):
        label=row[hc['Kind']]['labels'][0];kind=kinds.index(label);count=struct.unpack('<I',s.image.read(0x29ef340+(kind-18)*4,4))[0]
        genes=tuple(row[hc['Heredity'+letter]]for letter in 'ABCD');species_counts[label]+=1
        if genes[count:]!=(0,)*(4-count):raise ValueError('inactive flower loci not zero')
        phenotype[kind,genes]=row
        def resource(value):
            if value==65534:return None
            item=definitions[value]
            return dict(id=value,label=item['Label'],resource=item['ResName'],model=item['ModelName'],grow=item['Grow'],color_index=item['ColorIndex'],
                growup_fg=item['GrowupFg'],change_fg=item['ChangeFg'],pick_item=item['PicItem'],dig_item=item['DigItem'])
        documents.append(dict(source_row_index=i,kind=label,native_kind_index=kind,active_loci=count,allele_dosages=list(genes),
            canonical_gene_byte=sum(ENCODE[g]<<(j*2)for j,g in enumerate(genes)),primary=resource(row[hc['Name']]),
            alternate_zero_growth=resource(row[hc['h_753336dd']]),alternate_field_hash='753336dd',original_alternate_field_name=None,
            default_heredity=row[hc['DefaultHeredity']]))
    def expected_lookup(kind,gene,stage):
        if not 18<=kind<26:return 65534
        count=struct.unpack('<I',s.image.read(0x29ef340+(kind-18)*4,4))[0]
        doses=tuple(DOSAGE[(gene>>(j*2))&3]if j<count else 0 for j in range(4));row=phenotype[kind,doses]
        stage=1 if stage==0 else min(stage,3)
        alternate=row[hc['h_753336dd']];value=alternate if alternate!=65534 else row[hc['Name']]
        if alternate==65534 and stage==2:return value
        seen=set()
        while value!=65534 and value not in seen:
            seen.add(value);item=definitions.get(value)
            if not item:return 65534
            if item['Grow']==stage:return value
            value=item['GrowupFg']if item['GrowupFg']!=65534 else item['ChangeFg']
        return None if value in seen else 65534
    cycle_cases=[];tracking=None
    def observe_growth(uc,address,size,user):
        if tracking is not None and len(tracking)<12:tracking.append(uc.reg_read(regs.UC_ARM64_REG_X22)&0xffff)
    s.uc.hook_add(UC_HOOK_CODE,observe_growth,begin=0x4cc944,end=0x4cc944)
    for kind in range(18,26):
        count=struct.unpack('<I',s.image.read(0x29ef340+(kind-18)*4,4))[0]
        if species_counts[kinds[kind]]!=3**count:raise ValueError('incomplete genotype table')
        for gene in range(256):
            for stage in [0,1,2,3,4,255]:
                expected=expected_lookup(kind,gene,stage)
                if expected is None:
                    tracking=[];returned=True
                    try:s.integer_call(0x4cc4d0,[kind,gene,stage],limit=20000)
                    except ValueError:returned=False
                    observed=list(tracking);tracking=None
                    check('cyclic_growth_request_bounded',dict(returned=returned,first_growth_ids=observed[:6]),
                        dict(returned=False,first_growth_ids=[60151,60153,60155]*2),dict(kind=kind,gene=gene,stage=stage))
                    cycle_cases.append(dict(kind=kind,gene=gene,requested_stage=stage,normalized_stage=1,
                        instruction_limit=20000,returned=returned,observed_first_ids=observed,
                        stopped_pc=hex(s.uc.reg_read(regs.UC_ARM64_REG_PC))))
                else:
                    try:actual=s.integer_call(0x4cc4d0,[kind,gene,stage],limit=1000000)&0xffffffff
                    except Exception as error:raise ValueError(('native flower lookup context',kind,gene,stage))from error
                    check('genotype_growth_resource_lookup',actual,expected,dict(kind=kind,gene=gene,stage=stage))
    for kind in [0,17,26,29,0xffffffff]:
        for gene in [0,1,85,170,255]:check('invalid_kind_rejected',s.integer_call(0x4cc4d0,[kind,gene,2])&0xffffffff,65534,dict(kind=kind,gene=gene))
    default_genes=[]
    for value,item in definitions.items():
        kind=kinds.index(item['Kind']['labels'][0])
        if not 18<=kind<26:continue
        current=value;seen=set()
        while current!=65534 and current not in seen:
            seen.add(current);candidate=definitions[current]
            if candidate['Grow']==2:break
            current=candidate['GrowupFg']if candidate['GrowupFg']!=65534 else candidate['ChangeFg']
        else:raise ValueError(('flower default-gene normalization cannot reach buds',value))
        candidates=[(i,row)for i,row in enumerate(hereditary['rows'])if row[hc['Kind']]['hash']==item['Kind']['hash']and row[hc['Name']]==current]
        if not candidates:continue
        selected=next(((i,r)for i,r in candidates if r[hc['DefaultHeredity']]),candidates[-1])
        row_index,row=selected;expected=sum(ENCODE[row[hc['Heredity'+letter]]]<<(j*2)for j,letter in enumerate('ABCD'))
        actual=s.integer_call(0x4cd310,[value],limit=1000000)&0xffffffff
        check('default_gene_lookup',actual,expected,dict(resource_id=value,normalized_buds=current))
        default_genes.append(dict(resource_id=value,label=item['Label'],normalized_bud_id=current,
            source_genotype_row=row_index,default_flag=row[hc['DefaultHeredity']],native_gene_byte=actual))
    for value in [0,1,59999,60613,65534]:check('invalid_default_gene_lookup',s.integer_call(0x4cd310,[value],limit=1000000)&0xffffffff,0,dict(resource_id=value))
    # Execute the caller that reads parental genes from item FreeParam byte 0,
    # breeds, resolves the child's species/resource, and writes an 8-byte item.
    object_a=s.HEAP+0xa0000;item_b=s.HEAP+0xa1000;child_out=s.HEAP+0xa2000;item_examples=[]
    source_rows={row[fields['UniqueID']]:i for i,row in enumerate(primary['rows'])}
    main_table=tables['FgMainParam'];original=main_table['original'];base=main_table['emulated_raw_base']
    for kind in range(18,26):
        options=[r for r in documents if r['native_kind_index']==kind]
        for a in options:
            for b in options:
                ida=a['primary']['id'];idb=b['primary']['id'];ga=a['canonical_gene_byte'];gb=b['canonical_gene_byte']
                state=initialize((kind*0x10000+ga*256+gb)^0xac108);child,state_expected,draws=breed(ga,gb,state)
                expected_id=expected_lookup(kind,child,2)
                s.uc.mem_write(RNG_VA,struct.pack('<4I',*state))
                parent_a=struct.pack('<HBBI',ida,0,0,ga);parent_b=struct.pack('<HBBI',idb,0,0,gb)
                s.uc.mem_write(object_a+8,parent_a)
                s.uc.mem_write(object_a+16,struct.pack('<Q',base+original['data_start']+source_rows[ida]*primary['row_size']))
                s.uc.mem_write(item_b,parent_b);s.uc.mem_write(child_out-8,b'\xa5'*8+b'\xcd'*8+b'\x5a'*8)
                # Nontrivial C++ Item return uses the hidden AArch64 X8 result
                # pointer. Explicit arguments are X0=Fg object, X1=other item.
                s.uc.reg_write(regs.UC_ARM64_REG_X8,child_out)
                s.integer_call(0x4d5e50,[object_a,item_b],limit=1000000)
                context=dict(kind=kind,parent_gene_a=ga,parent_gene_b=gb)
                actual=bytes(s.uc.mem_read(child_out-8,24));expected=b'\xa5'*8+struct.pack('<HBBI',expected_id,0,0,child)+b'\x5a'*8
                check('complete_offspring_item_and_guard',actual.hex(),expected.hex(),context)
                check('offspring_item_rng_state',list(struct.unpack('<4I',bytes(s.uc.mem_read(RNG_VA,16)))),state_expected,context)
                check('parent_items_unchanged',bytes(s.uc.mem_read(object_a+8,8)+s.uc.mem_read(item_b,8)).hex(),(parent_a+parent_b).hex(),context)
                if len(item_examples)<12:item_examples.append(dict(**context,parent_item_a_hex=parent_a.hex(),parent_item_b_hex=parent_b.hex(),
                    offspring_item_hex=actual[8:16].hex(),offspring_gene=child,offspring_resource_id=expected_id,rng_draws=draws))
    for item in tables.values():check('source_table_memory_unchanged',bytes(s.uc.mem_read(item['emulated_raw_base'],len(item['raw']))).hex(),item['raw'].hex(),dict(source=item['source']['source']))
    canonical=[sum(ENCODE[v]<<(j*2)for j,v in enumerate(doses))for doses in itertools.product(range(3),repeat=4)]
    probabilities=[]
    for a in canonical:
        for b in canonical:
            children=distribution(a,b)
            if sum(children.values())!=256:raise ValueError('invalid Mendelian probability mass')
            probabilities.append(dict(parent_a=a,parent_b=b,children=[dict(gene=gene,weight=weight)for gene,weight in sorted(children.items())]))
    dump(OUT/'flowers/genotypes.json',dict(sources=[dict(source_id=t['source']['id'],source=t['source']['source'],sha256=t['source']['sha256'],raw=t['source']['raw'])for t in tables.values()],
        native_kind_enum=kind_evidence,allele_layout='Four 2-bit loci A/B/C/D from least to most significant bits; 01 and 10 both mean dosage 1.',
        genotype_rows=documents))
    dump(OUT/'flowers/inheritance_probabilities.json',dict(denominator=256,pair_count=len(probabilities),canonical_genotypes=canonical,
        scope='Theoretical Mendelian distribution under independent fair parent-allele draws. Actual engine offspring and conditional RNG progression are separately verified; full spawning/watering probability is outside this model.',pairs=probabilities))
    dump(OUT/'flowers/growth_cycles.json',dict(resource_ids=[60151,60153,60155],grow_values=[2,3,0],
        source_scope='FgMainParam entries labelled Black Cosmos, plus two FgFlowerHeredity dosage rows.',
        native_scope='Synthetic requests for normalized Grow=1; original code repeatedly traverses the same three IDs within the instruction bound. Reachability from ordinary gameplay callers is not established.',
        source_values_preserved=True,cases=cycle_cases))
    dump(OUT/'flowers/default_genes.json',dict(native_function='0x4cd310',entries=default_genes,
        contract='Normalize the flower resource to its Grow=2 bud; select matching Kind/Name rows. Stop at a DefaultHeredity!=0 row, otherwise use the last matching row; encode four dosages using [0,1,3].'))
    dump(OUT/'flowers/offspring_items.json',dict(native_function='0x4d5e50',same_species_canonical_parent_pairs=11664,
        abi='X0=Fg parameter object, X1=other parent item; X8=hidden result pointer for the returned nontrivial C++ item object.',
        item_gene_layout='FreeParam low byte at item+4. Caller reads parent A from Fg object+0xc and parent B from item+4; output contains bud-resource ID plus inherited gene byte.',
        scope='Pairs are supplied explicitly. Partner eligibility, species checking by higher callers, watering bonuses and spatial spawning are outside this helper.',samples=item_examples))
    evidence=[]
    for name,va,size in [('inheritance',0x4cd070,0x298),('phenotype_growth',0x4cc4d0,0xa4c),('default_genes',0x4cd310,0xf88),('offspring_item',0x4d5e50,0xb0),('bounded_rng',0xf53420,0x30)]:
        raw=s.image.read(va,size);path=f'flowers/evidence/{name}.asm';target=OUT/path;target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text('\n'.join(f'{i.address:08x} {i.bytes.hex():8s} {i.mnemonic:8s} {i.op_str}'for i in s.image.disasm(va,size))+'\n')
        evidence.append(dict(va=hex(va),size=size,sha256=hashlib.sha256(raw).hexdigest(),assembly=path))
    result=dict(native_elf_sha256=hashlib.sha256(s.image.data).hexdigest(),comparisons=sum(groups.values()),groups=dict(groups),mismatches=failures,
        dependencies_stubbed=[],parent_byte_pairs_exhaustive=65536,additional_full_u32_parent_cases=1024,
        native_inheritance='0x4cd070',native_resource_lookup='0x4cc4d0',global_rng_state='0x35e9510',rng_draw_histogram=dict(draw_counts),
        species_counts=dict(species_counts),genotype_rows=len(documents),probability_parent_pairs=len(probabilities),
        inheritance_contract='At each locus A through D, visit parent A then B. Dosage 0 contributes 0, dosage 2 contributes 1, dosage 1 draws rollMax(2) and contributes 1 iff result==0. Encode child dosage as [0,1,3]. Only heterozygous parents consume RNG draws.',
        lookup_contract='Kind indices 18..25; collapse 2-bit dosage aliases; index supplied genotype table. Prefer nonempty hash_753336dd alternate, otherwise Name. Clamp requested growth to 1..3 (0->1). Traverse GrowupFg, or ChangeFg when no GrowupFg, to requested Grow. Cyclic requests without the target Grow are recorded as bounded nontermination, not forced to a successful return or sentinel.',
        cyclic_growth_requests=len(cycle_cases),
        default_gene_resources=len(default_genes),default_gene_function='0x4cd310',
        offspring_item_parent_pairs=11664,item_gene_offset=4,
        alternate_field_role='Nonempty values resolve to zero-growth records in supplied FgMainParam; native lookup preferentially starts from that alternate. Original descriptor remains unknown.',
        table_initialization='Raw BCSV bytes retained. Table row arrays, shared-buffer holders, dense ID lookup and enum cache are reconstructed from raw headers/rows and native 30-name kind literal. Table file loading, allocation and table constructors are not executed; temporary item constructors reached inside the verified helpers execute natively.',
        evidence=evidence,samples=samples,
        remaining=['Pair selection and watering/visitor bonuses','Spawn-position selection and breeding eligibility','Gold-rose and special-case rules','Original field name for hash 753336dd'])
    dump(OUT/'flowers/native_verification.json',result)
    print(json.dumps({k:v for k,v in result.items()if k not in ['mismatches','samples','evidence']},indent=2))
    if failures:raise ValueError(('native flower mismatch',failures[:5]))


if __name__=='__main__':build()
