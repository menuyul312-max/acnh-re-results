#!/usr/bin/env python3
"""Index the final evidence set and report structural and semantic scope separately."""
import collections
import csv
import hashlib
import json
from pathlib import Path
import sqlite3

from native_image import Image
from reverse_corpus import dump

ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/'output'


def read(name):return json.loads((OUT/name).read_text())
def number(n):return f'{n:,}'.replace(',','.')


def build():
    manifest=read('manifest.json');source=Path(manifest['source_root'])
    structural=read('summary.json');schema=read('schemas/summary.json')
    handlers=read('binary/event_handlers_resolved.json');native=read('native_verification.json')
    curves=read('environment/curves.json');terrain=read('relations/terrain_native.json')
    semantic=read('semantic_summary.json');baseline=read('index_summary.json')
    atlas=read('binary/native_atlas_summary.json');textures=read('environment/textures.json')
    builtin=read('binary/exit_flowchart_verification.json');hashes=read('schemas/hash_candidates_summary.json')
    typed=read('byml_typed/summary.json')
    byml_names=read('schemas/byml_names_summary.json');items=read('items/summary.json')
    byml_native=read('byml_typed/native_verification.json');stage=read('stage/native_summary.json')
    byte_views=read('schemas/native_read_views.json');public_audit=read('schemas/public_descriptor_audit.json')
    flag_policy=read('flags/reset_policy_native.json');rng=read('random/native_rng.json')
    weather=read('weather/summary.json');weather_native=read('weather/native_verification.json')
    weather_linked=(OUT/'weather/native_linked_verification.json').exists()
    if weather_linked:weather_native=read('weather/native_linked_verification.json')
    calendar_native=read('calendar/native_verification.json')if (OUT/'calendar/native_verification.json').exists()else None
    flowers=read('flowers/native_verification.json')if (OUT/'flowers/native_verification.json').exists()else None
    relocation=read('native_modules/relocation_verification.json')if (OUT/'native_modules/relocation_verification.json').exists()else None
    npc_voice=read('npc/voice_configuration_native.json')
    modules=read('native_modules/summary.json')if (OUT/'native_modules/summary.json').exists()else None
    linked_byml=read('native_modules/linked_byml_verification.json')if (OUT/'native_modules/linked_byml_verification.json').exists()else None
    sdk_cmp=read('native_modules/strcmp_native_verification.json')if (OUT/'native_modules/strcmp_native_verification.json').exists()else None
    im=Image()
    def executable(v):return v%4==0 and any(s['p_flags']&1 and s['p_vaddr']<=v<s['p_vaddr']+s['p_filesz'] for s in im.segments)
    target_file=OUT/'binary/targeted_addresses.txt'
    seed=ROOT/'work/all_native_targets.txt'
    if seed.exists():target_file.write_text(seed.read_text())
    targets={int(x,16) for x in target_file.read_text().splitlines()} if target_file.exists() else set()
    functions={}
    for va,size,name in csv.reader((source/'C_reverse/generated/re/functions.tsv').open(),delimiter='\t'):
        v=int(va,16)-0x100000
        functions[v]={'va':v,'size':int(size),'span_end_va':v+int(size)-1,
                      'name':name,'evidence':'supplied_function_snapshot'}
    inv=OUT/'binary/analyzed_functions.tsv'
    if inv.exists():
        for r in csv.DictReader(inv.open(),delimiter='\t'):
            v=int(r['elf_va'],16)
            functions[v]={'va':v,'size':int(r['body_bytes']),'span_end_va':int(r['end_va'],16),
                'name':r['name'],'inferred_return_type':r['return_type'],'evidence':'new_Ghidra_inventory'}
    docs=[];rejected=[]
    for p in sorted((OUT/'binary/analysis_decomp').glob('*.c')):
        va=int(p.stem,16)
        if not executable(va):
            rejected.append({'va':hex(va),'path':str(p.relative_to(OUT)),
                             'reason':'non-executable or unaligned; rejected as function pseudocode'})
            continue
        text=p.read_text()
        docs.append({'va':va,'path':str(p.relative_to(OUT)),'size':p.stat().st_size,
            'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'warning': 'WARNING' in text,
            'bad_instruction_warning':any(t in text for t in ['halt_baddata','Bad instruction','Unable to resolve constructor'])})
        functions.setdefault(va,{'va':va,'size':None,'name':f'FUN_{va+0x100000:08x}',
                                 'span_end_va':None,
                                 'evidence':'targeted_disassembly; boundary_not_exported'})
    completed={d['va'] for d in docs}
    missing=[]
    im.disassembler.skipdata=True
    for va in sorted(targets-completed):
        rec={'va':hex(va),'status':'pseudocode_unavailable; raw ELF remains authoritative',
             'snapshot_function':functions.get(va)}
        if executable(va):
            end=(functions.get(va) or {}).get('span_end_va')
            n=end-va+1 if end is not None else 256
            p=OUT/'binary/disassembly_fallback'/f'{va:x}.asm';p.parent.mkdir(parents=True,exist_ok=True)
            instructions=im.disasm(va,n)
            p.write_text('\n'.join(f'{i.address:08x} {i.bytes.hex():8s} {i.mnemonic:8s} {i.op_str}' for i in instructions)+'\n')
            raw=im.read(va,n);rawpath=p.with_suffix('.bin');rawpath.write_bytes(raw)
            rec.update(disassembly=str(p.relative_to(OUT)),bytes_requested=n,instructions=len(instructions),
                bytes_represented=sum(i.size for i in instructions),raw_region=str(rawpath.relative_to(OUT)),
                raw_sha256=hashlib.sha256(raw).hexdigest(),
                region_note='Ghidra candidate span, including gaps; skip-data pseudo instructions preserve undecoded bytes')
        missing.append(rec)
    im.disassembler.skipdata=False
    decomp={'targeted_addresses':len(targets),'targeted_with_pseudocode':len(targets&completed),
        'valid_pseudocode_files':len(docs),'with_warnings':sum(d['warning'] for d in docs),
        'with_bad_instruction_warnings':sum(d['bad_instruction_warning'] for d in docs),
        'missing':missing,'rejected_noncode_candidates':rejected,
        'semantic_status':'automated pseudocode; not a claim of fully understood behavior'}
    dump(OUT/'binary/decompilation_summary.json',decomp)
    dump(OUT/'binary/decompilation_index.json',docs)
    dump(OUT/'binary/function_inventory.json',sorted(functions.values(),key=lambda r:r['va']))
    db=sqlite3.connect(OUT/'index.sqlite')
    db.execute('DROP TABLE IF EXISTS decomp_new')
    db.execute('CREATE TABLE decomp_new(va INTEGER PRIMARY KEY,path TEXT,sha256 TEXT,bytes INTEGER,has_warning INTEGER,bad_instruction_warning INTEGER)')
    db.executemany('INSERT INTO decomp_new VALUES(?,?,?,?,?,?)',[(r['va'],r['path'],r['sha256'],r['size'],r['warning'],r['bad_instruction_warning']) for r in docs])
    db.execute('DROP TABLE IF EXISTS native_functions')
    db.execute('CREATE TABLE native_functions(va INTEGER PRIMARY KEY,size INTEGER,span_end_va INTEGER,name TEXT,evidence TEXT)')
    db.executemany('INSERT INTO native_functions VALUES(?,?,?,?,?)',[(r['va'],r['size'],r.get('span_end_va'),r['name'],r['evidence']) for r in functions.values()])
    db.commit();db.close()
    source_files=[]
    for p in sorted(source.rglob('*')):
        if p.is_file():
            rel=p.relative_to(source).as_posix()
            source_files.append({'path':rel,'size':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),
                'role':'native_input' if rel.startswith('A_logic/') else 'raw_data_input' if rel.startswith('B_data/') else 'supplied_reference_readonly'})
    dump(OUT/'source_inventory.json',{'root':str(source),'files':source_files,'count':len(source_files),
        'note':'Cataloguing a reference file is distinct from manually understanding its complete contents.'})
    domains=read('domains.json')
    for rows in domains['domains'].values():
        for r in rows:
            table=read(f"tables_resolved/{r['table']}.json")
            r.update(named_columns=sum(bool(c['descriptor']) for c in table['columns']),schema=f"tables_resolved/{r['table']}.json")
    dump(OUT/'domains_resolved.json',domains)
    remaining={
        'unnamed_bcsv_columns':schema['unresolved_columns'],
        'bcsv_evidence':'schemas/unresolved_evidence.json',
        'hash_keys_without_candidate':hashes['distinct_observed_keys']-hashes['keys_with_candidates'],
        'hash_key_note':'Includes numeric IDs; candidate equality is not a semantic proof.',
        'unresolved_primary_byml_keys':byml_names['unresolved_keys'],
        'unresolved_primary_byml_key_occurrences':byml_names['unresolved_key_occurrences'],
        'byml_name_evidence':'schemas/byml_names_unresolved.json',
        'stage_unregistered_actor_kinds':stage['unregistered_actor_hashes'],
        'weather_unverified_paths':weather_native['remaining'],
        'flowers_unverified_paths':flowers['remaining']if flowers else'Flower algorithms not independently verified',
        'native_behavior':'Complete game behavior, AI, scheduler, economy, save and networking are not fully specified by these results.',
        'external_implementations':('Additional ExeFS now supplies SDK/multimedia export implementations for 898/910 main imports; 12 weak symbols lack export matches. Cross-module loader/TLS/initialization/syscalls and complete runtime remain partial.'if modules else'910 undefined symbols; multimedia.nss and nnSdk.nss implementations are not supplied.'),
        'missing_raw_formats':'The B_data subset does not supply full model geometry, animation/audio/VFX/shader/Havok archives mentioned by older tools.',
        'runtime_validation':'Isolated helpers emulated; complete game runtime and end-to-end engine conversion not exercised.'}
    coverage={'status':'structural_mapping_complete; semantic_reverse_engineering_partial',
        'full_user_goal_completed':False,'scope':'all supplied raw B_data, native address indexes, and supplied JSON references; Godot unchanged',
        'structural':structural,'typed_byml':typed,'byml_names':byml_names,'items':items,
        'native_byml_reader':{k:v for k,v in byml_native.items()if k!='file_results'},
        'stage':{k:v for k,v in stage.items()if k not in ['key_registry','registry_call_sites']},
        'native_bcsv_views':{k:v for k,v in byte_views.items()if k!='fields'},
        'public_descriptor_audit':{k:v for k,v in public_audit.items()if k!='columns'},
        'flag_policy':{k:v for k,v in flag_policy.items()if k!='tables'},
        'rng':rng,'weather':weather,'weather_native':weather_native,
        'npc_voice':{k:v for k,v in npc_voice.items()if k not in ['tables','missing_field_cases']},
        'additional_exefs':modules,
        'calendar':calendar_native,
        'flowers':flowers,
        'module_relocation':relocation,
        'native_byml_linked_sdk':{k:v for k,v in linked_byml.items()if k!='file_results'}if linked_byml else None,
        'schemas':schema['counts'],'dispatch':handlers['counts'],
        'native_helper_checks':{'terrain':native['terrain']['cases'],'C1':native['c1']['native_comparisons'],
            'curves':curves['comparisons'],'ExitFlowchart':len(builtin['predicate_checks'])+1,
            'items_and_parameter_crc32':items['native_comparisons'],
            'stage_projection_and_trig':stage['native_projection_checks']+stage['native_trig_checks'],
            'bcsv_byte_loads_and_animation_block':byte_views['byte_load_comparisons']+byte_views['animation_fallback_comparisons'],
            'flag_policy':flag_policy['comparisons'],'RNG':rng['comparisons'],
            'weather_ordinary_day':weather_native['comparisons'],
            'npc_voice_byte_bindings':npc_voice['comparisons'],
            'actual_sdk_strcmp':sdk_cmp['comparisons']if sdk_cmp else 0,
            'sdk_calendar_and_game_day':calendar_native['comparisons']if calendar_native else 0,
            'flower_genes_and_resource_lookup':flowers['comparisons']if flowers else 0},
        'new_decompilation':{k:v for k,v in decomp.items() if k not in ('missing','rejected_noncode_candidates')},
        'pseudocode_missing_targets':len(missing),'native_atlas':atlas,'remaining':remaining,
        'semantic_validation':semantic,'baseline_native_index':baseline}
    dump(OUT/'coverage.json',coverage)
    total_checks=sum(coverage['native_helper_checks'].values())
    prior_path=ROOT/'research/phase4_baseline/coverage.json'
    if prior_path.exists():
        prior=json.loads(prior_path.read_text())
        progress={'comparison':'Current evidence against the saved report before the Stage/BYML-native/weather phase.',
            'byml_recovered_keys':{'before':prior['byml_names']['unique_recovered_keys'],'after':byml_names['unique_recovered_keys']},
            'byml_recovered_occurrences':{'before':prior['byml_names']['recovered_key_occurrences'],'after':byml_names['recovered_key_occurrences']},
            'byml_unresolved_keys':{'before':prior['byml_names']['unresolved_keys'],'after':byml_names['unresolved_keys']},
            'native_helper_comparisons':{'before':sum(prior['native_helper_checks'].values()),'after':total_checks},
            'native_byml_structural_comparisons_added':byml_native['comparisons'],
            'native_bcsv_views_added':byte_views['native_byte_view_count'],
            'new_pseudocode_files':{'before':prior['new_decompilation']['valid_pseudocode_files'],'after':decomp['valid_pseudocode_files']},
            'bcsv_named_columns':{'before':prior['schemas']['named_columns'],'after':schema['counts']['named_columns']},
            'new_domains':['Stage scene records and actor registry','Flag-reset predicate','Integer RNG','Ordinary-day weather selection'],
            'input_policy':'Original archive files verified unchanged; Godot remains read-only.',
            'semantic_completion':False}
        dump(OUT/'progress_since_previous.json',progress)
    phase5_path=ROOT/'research/phase5_baseline/coverage.json'
    if phase5_path.exists():
        prior=json.loads(phase5_path.read_text())
        dump(OUT/'progress_additional_exefs.json',dict(
            comparison='Against the report immediately before the five additional ExeFS uploads.',
            native_helper_comparisons=dict(before=sum(prior['native_helper_checks'].values()),after=total_checks),
            main_imports_with_implementations=dict(before=0,after=modules['main_imports_with_export_candidate']if modules else 0),
            sdk_substitution_in_byml=dict(before='strcmp substitute',after='original SDK implementation'if linked_byml else'unchanged'),
            npc_voice_columns_bound=6,source_rows_native_checked=npc_voice['source_rows_checked'],
            original_bcsv_names_added=0,full_game_semantics_complete=False))
    phase6_path=ROOT/'research/phase6_baseline/coverage.json'
    if phase6_path.exists()and calendar_native and flowers:
        prior=json.loads(phase6_path.read_text())
        dump(OUT/'progress_calendar_flowers.json',dict(comparison='Against the report after the five additional ExeFS uploads.',
            native_helper_comparisons=dict(before=sum(prior['native_helper_checks'].values()),after=total_checks),
            module_relocation_pointer_checks=relocation['pointer_checks'],
            game_day_boundary=dict(before='Before-05:00 branch unverified',after='Original SDK/game normalizer verified; complete Gregorian cycle'),
            weather_predictions=dict(before=prior['weather_native']['prediction_comparisons'],after=weather_native['prediction_comparisons']),
            flower_genotype_rows=flowers['genotype_rows'],flower_default_resources=flowers['default_gene_resources'],
            bounded_flower_growth_cycles=flowers['cyclic_growth_requests'],
            byml_names=dict(before=prior['byml_names']['unique_recovered_keys'],after=byml_names['unique_recovered_keys']),
            original_bcsv_names_added=0,full_game_semantics_complete=False))
    report=f'''# Laporan rekayasa balik paket ACNH

**Status: seluruh berkas mentah B_data yang tersedia sudah dipetakan secara struktural. Rekayasa balik seluruh semantik game belum selesai 100%.** Pemetaan alamat, JSON hasil baca, atau keberadaan pseudocode tidak disamakan dengan pemahaman perilaku lengkap. Bagian yang belum terbukti dicatat eksplisit.

Proyek Godot hanya menjadi referensi dan tidak diubah. Hasil baru berada di `/workspace/acnh-re`, untuk menjadi sumber konversi berikutnya tanpa ketergantungan engine.

Perubahan terhadap laporan sebelumnya: [progress_since_previous.json](output/progress_since_previous.json). Tahap ini menambah validasi pembaca BYML asli, nama array bertipe, registry/record Stage, view byte BCSV, predicate flag, RNG, dan pemilih cuaca hari biasa. Nama key BYML yang pulih bertambah dari 2.910 menjadi {number(byml_names['unique_recovered_keys'])}; nama asli kolom BCSV tetap 1.957, dengan empat view baca native baru untuk kolom unresolved.

## Sumber dan batas input

- Paket asli: {number(len(source_files))} berkas, {number(sum(r['size'] for r in source_files))} byte. [Inventaris seluruh berkas dan SHA-256](output/source_inventory.json).
- `A_logic` paket awal menyertakan `main.elf` dan `main.npdm`. ELF SHA-256: `{atlas['elf_sha256']}`. Alamat native dalam laporan adalah VA ELF; pseudocode memakai image base tambahan `0x100000`.
- Build ID `7FC1BAFF976AECA414520CB89F4616CB` cocok dengan **ACNH 1.0.0** pada daftar versi ACNHRecomp yang dipin. [Audit rujukan publik dan batas versi](docs/GITHUB_REFERENCES.md).
- `B_data` menyertakan 1.171 berkas, bukan keseluruhan RomFS rilis ACNH. Keberadaan parser pada paket tidak membuktikan berkas format itu ikut tersedia.
- Ekspor aset JSON menjadi referensi: [156 entri arsip/model dan 925 material](output/assets/catalogue.json), termasuk AABB, nama shader, sampler, tekstur, dan parameter. Metadata ini tidak mengandung kembali seluruh vertex/index mesh sumber.
- Ada 58 ekspor BYML tambahan tanpa BYML mentah: 55 konfigurasi animasi NPC dan tiga konfigurasi suara. Seluruh 5.052 referensi blob ekspor lama diperiksa dan tersedia.

## Pemetaan data yang berhasil

| Bagian | Hasil | Referensi |
|---|---|---|
| Berkas dan isi kontainer | 2.986 entri; tanpa error parse atau format tak terklasifikasi | [Manifest](output/manifest.json) |
| BCSV | 164 tabel, 29.836 baris, 2.048 kolom | [Katalog JSON](output/schemas/catalogue.json) |
| Nama kolom | 1.957 descriptor cocok CRC32; 91 belum bernama | [Skema dan hitungan](output/schemas/summary.json) |
| BYML | 2.313: 549 langsung dan 1.764 anggota StaticParam.pack | Manifest dan decoded JSON |
| Validasi BYML independen | Seluruh 2.313 tree cocok; tag numerik dan offset dipertahankan | [Katalog graph bertipe](output/byml_typed/catalogue.json) |
| Nama field BYML | {number(byml_names['unique_recovered_keys'])}/{number(byml_names['hashed_keys'])} key hash/ID; {byml_names['recovered_occurrence_percent']}% kemunculan memiliki descriptor pulih | [Kamus dan bukti nama](output/schemas/byml_names.json) |
| Item dan penempatan | {number(items['item_word_occurrences'])} word item; seluruhnya cocok definisi/sentinel; {number(items['placements_with_named_coordinates'])} penempatan berkoordinat | [Katalog per sumber](output/items/catalogue.json) |
| Pembaca BYML asli | 443.204 entry dictionary dan 319.774 entry array cocok tag/word; 2.546.185 pemeriksaan | [Validasi native](output/byml_typed/native_verification.json) |
| Stage dan actor | 108 resource; 311 actor; 158 jenis terdaftar; 142 record volume/perpindahan | [Stage JSON](output/stage/catalogue.json) |
| Cuaca | 34 pola × 24 jam, 40 tabel peluang; pemilih hari biasa teruji native | [Cuaca](output/weather/summary.json), [native](output/weather/native_verification.json) |
| Lingkungan | 47 AAMP; seluruh jenis parameter yang muncul ditangani | [Kurva](output/environment/curves.json) |
| EventFlow | 456 berkas; 3.561 subflow memiliki file dan entry target | [Hubungan](output/relations/eventflow.json) |
| Flag event | 3.661 referensi cocok dengan label tabel | Hubungan EventFlow |
| Dispatch native | 1.056 nama terhubung ke 904 factory/vtable unik; satu operasi runner | [Peta dispatch](output/binary/event_handlers_resolved.json) |
| Terrain | 1.032.192 sel, 96 preset, kedua layer, tanpa ID atau variasi di luar tabel | [Layout dan model lookup](output/relations/terrain_native.json) |
| Resep | Enam slot material/jumlah untuk 552 resep, urutan dikonfirmasi native | [Resep native](output/relations/recipe_materials_native.json) |
| Grafik BGM | 503 grafik, 2.291 node, 2.139 transisi; target tersedia | [Pemeriksaan semantik](output/semantic_summary.json) |
| Kondisi BGM | 2.644 referensi, 940 program unik, evaluator native teridentifikasi | [Bytecode dan AST](output/audio/condition_bytecode.json) |
| Tekstur | Dua BC4_UNORM, seluruh 13 mip, DDS tanpa kompresi ulang | [Referensi tekstur JSON](output/environment/textures.json) |

## Temuan native yang memengaruhi konversi

### Descriptor BYML dan item delapan byte

Formatter parameter `0x67770` memakai `%s.%s` di `0x292423b` dengan nama anggota dan nama tipe dari slot vtable `0xe8`. Array struct memakai `%s[]`, misalnya `mFtrList[]`; array bertipe memakai `%s[].%s` di `0x29b9f57`, misalnya `mWeatherType[].Enum` dan `mValueBuffer[].bool`. Jalur `0x1c87110` menghitung hash descriptor melalui CRC32 `0x19ab050`. Sebanyak 21 nama tipe scalar/parameter dan 11 tipe elemen array dipulihkan dari vtable.

Ini memulihkan nama koordinat lapangan `mHalfUnitX.s32`, `mHalfUnitZ.s32`, `mItemLayerID.u8`, koordinat ruangan `mUnitX.u8`, `mUnitZ.u8`, `mLayer.u8`, serta field `mItemNameParam.u64`. Nama dinamis juga dibandingkan dengan string BCSV/BYML lokal dan nama berkas; misalnya root `ham00` cocok CRC32 nama NPC tersebut. Sebagian data stage memakai kecocokan Murmur3 nama polos; algoritme dicatat per key. Kecocokan ini memulihkan descriptor, belum membuktikan seluruh makna atau satuan gameplay.

Pemeriksaan literal UTF-8 juga memulihkan root `GMO調整` pada 494 konfigurasi GMO. Kamus mempertahankan nama Jepang asli dan tidak membatasi field hanya pada string ASCII.

Sebanyak **{number(byml_names['recovered_key_occurrences'])}/{number(byml_names['hashed_key_occurrences'])} kemunculan key ({byml_names['recovered_occurrence_percent']}%)** memiliki nama yang pulih. Angka ini adalah cakupan nama key BYML, bukan persentase RE seluruh game. Semua 2.313 tampilan bernama dapat dibalik ke tree key asli. Kandidat ambigu, hash tanpa nol depan, dan tipe wire asli tetap dipertahankan. [Tampilan JSON bernama](output/byml_resolved/catalogue.json).

Copy native `0xf589b0`/`0xf589e0` mengonfirmasi layout `<u16 ID, u8 SystemParam, u8 AdditionalParam, u32 FreeParam>`. Reset `0x1a6560` menghasilkan word `0xfffe`. Helper `0xf58a90` memetakan AdditionalParam ke ID dummy pembungkus dan mempertahankan MessageBottle `0x16a1`; helper `0xf59f70` membaca koordinat extension dari byte 6/7 jika ID `0xfffd`. **{number(items['native_comparisons'])} perbandingan native tanpa mismatch** mencakup seluruh word unik korpus, seluruh 256 AdditionalParam sintetis pada ID batas, copy/guard bytes, reset, koordinat extension, tabel kertas, dan CRC32 descriptor. Tidak ada dependensi yang di-stub dalam uji tahap ini.

Semua {number(items['item_word_occurrences'])} kemunculan terhubung: 7.471 ke `ItemParam`, 38.172 ke `FgMainParam`, dan 391 sentinel kosong. Semuanya menyimpan word mentah, pointer sumber, dan referensi baris tabel. AdditionalParam seluruh korpus nol; cabang wrapping diuji secara sintetis. FreeParam tetap union bergantung jenis item; belum dipaksakan sebagai jumlah atau remake. Khusus keluarga bunga, byte terendah FreeParam kini terbukti membawa gen melalui caller pembentukan item anakan, dijelaskan pada bagian genetika. Interpretasi rotation/buried/dropped dari NHSE masih rujukan eksternal. Skala koordinat dan transformasi Godot belum disimpulkan. [Kamus item](output/items/words.json), [hasil uji asli](output/items/native_verification.json).

### Stage, pembaca BYML asli, flag, RNG, dan cuaca

Registry actor berisi **158 nama yang dibaca dari tabel native**, masing-masing cocok Murmur3 dan indeks hasil lookup `0x628b0`. Seluruh 108 resource Stage kini mempunyai katalog hubungan, actor, hash parent, environment, dan target perpindahan. Ada 311 kemunculan actor; **18 kemunculan dari tiga hash** tidak terdaftar dan dilewati pembaca `0xfeb390`. `Parent` mengacu pada jenis actor, bukan ID instance unik. Hash yang belum dikenal tetap dipertahankan. [Registry](output/stage/actor_type_registry.json).

Seluruh **142 record volume/perpindahan** cocok dengan proyeksi native `0xfeeeb0` pada dua mode (284 pemeriksaan); 265 kasus tambahan menguji arah/interpolasi trigonometri `0x1cb70` secara bit-exact f32. Nama field Stage `ActorName`, `ActorList`, `UIList`, dan `UIName` mempunyai kecocokan Murmur3 serta bukti indeks key dan fungsi konsumen. Formula dan batas initializer/stub dicatat di [Stage](output/stage/native_summary.json), [kontrak native](docs/NATIVE_STAGE_WEATHER.md).

Pembaca BYML asli menerima semua 2.313 sumber. **{number(byml_native['physical_dictionary_entries'])} entry dictionary dan {number(byml_native['physical_array_entries'])} entry array** cocok tag dan word dalam **{number(byml_native['comparisons'])} pemeriksaan tanpa mismatch**. Audit awal memakai pengganti `strcmp` SDK; audit dengan SDK unggahan berikutnya menjalankan seluruh pemeriksaan kembali menggunakan implementasi asli (lihat bagian ExeFS). ABI output terdiri dari word ternormalisasi u32 dan tag u8, lalu padding tiga byte. Temuan batas penting: helper dictionary by-index langsung `0x1ef63d0` hanya memeriksa count tidak nol, bukan batas indeks; caller wajib memvalidasi indeks. Pemeriksaan ini membuktikan pembacaan struktur, bukan jutaan aturan gameplay.

Empat view kolom tanpa nama diperbaiki berdasarkan instruksi byte asli: `HumanAnimParam:d5217761` dan `FieldLandMakingError:0b3be609` dibaca signed s8; `EventFlagsLandTempParam:3c7fb88f` serta `ItemRemake:d4f43b0b` dibaca u8. Ada 445 nilai HumanAnim 0xff yang kini menjadi -1; blok native memilih fallback caller untuk byte negatif. Sebanyak 1.172 baris diperiksa dan 2.048 perbandingan instruksi/blok cocok. Nama asli empat kolom tetap belum diketahui. [Bukti tipe](output/schemas/native_read_views.json).

Kolom hash `5140e4b4` muncul pada lima tabel EventFlags (884 baris). Predicate `0xf54530` terbukti: selector 0/lainnya=false; 1=counter!=0; 2=counter!=0 atau byte tambahan!=0; 3=true; 4=counter>0. Counter adalah s64 pada context+0, byte tambahan pada +0x1a. Makna context tingkat gameplay belum terbukti. **{number(flag_policy['comparisons'])} kasus native cocok**, tanpa stub. [Kebijakan reset](output/flags/reset_policy_native.json).

RNG integer (seed, state eksplisit, u32/u64, ekspor state) cocok dalam **{number(rng['comparisons'])} perbandingan tanpa stub**. State eksplisit semua nol mempunyai fallback native ke state hasil seed 0; ini berbeda dari `Random::with_state` MeteoNook. [RNG](output/random/native_rng.json).

Cuaca menyediakan 34 pola × 24 jam untuk cuaca dan angin, serta 20 tabel peluang per hemisphere. **{number(weather['total_comparisons'])} perbandingan** terhadap MeteoNook yang dipin menemukan **empat nilai cuaca per jam berbeda**: Fine02 jam 18/19 dan Fine06 jam 17/19. Nilai paket lokal dipertahankan; seluruh bobot, kalender, dan angin cocok. Perbedaan tidak dianggap error parse atau diperbaiki dengan menyalin tabel publik.

Pemilih cuaca hari biasa `0xfdd9b0` kini dijalankan memakai object parameter yang diisi data lokal dan accessor native asli: seed dicampur dengan `(year*512 + month*32 + day)*65536` modulo u32; dua draw dilewati; draw ketiga memilih roll 0–99 melalui perkalian high-word, lalu akumulasi bobot s8 memilih pola. **{number(weather_native['comparisons'])} pemeriksaan tanpa mismatch/stub** mencakup 732 tanggal kalender, seluruh 4.000 slot peluang, {number(weather_native['prediction_comparisons'])} prediksi, dan state RNG akhirnya. {'Jalur sebelum 05.00 sekarang memakai SDK asli dan sudah diuji; tanggal efektif mundur sehari. Flag event khusus dan visual/cloud/fog/aurora/stars tetap belum diuji.'if weather_linked else'Rollback sebelum 05.00, flag event khusus dan visual/cloud/fog/aurora/stars belum diuji.'} Ini bukan eksekusi seluruh runtime cuaca. [Audit awal](output/weather/native_verification.json), [verifikasi SDK dan batas hari](output/weather/native_linked_verification.json).

Audit HeavenTool menemukan sepuluh kemunculan kolom yang cocok CRC32, tetapi tujuh kandidat descriptor melebihi span kolom lokal. **Tidak ada nama dari daftar tersebut dipromosikan.** Kandidat yang lebarnya cocok juga masih memerlukan bukti nama/peran. [Audit publik](output/schemas/public_descriptor_audit.json).

### Terrain: dua layer dan variasi aktual

Record 14 byte berisi dua komponen enam byte `(u16 unit_id, u16 variation_index, u8 rotation, padding)`, lalu satu byte height dan padding. Copy native `0x542db0` tidak membaca padding offset 5, 11, dan 13. Getter height `0xf52860` mempertahankan 0–5; nilai >=6 menjadi 4. Uji mencakup seluruh 256 nilai byte, sehingga nilai batas 5 tetap terwakili.

Loader preset `0x558f40` membaca kedua layer dan memakai getter batas variasi `0x547520`, dengan fallback 0 jika indeks melebihi batas. Nilai `Variation` pada tabel unit adalah batas maksimum; indeks aktual berada di offset 2/8 record. Formatter `0x543340` memakai `%s_%d` dengan indeks yang dimuat dari komponen+2. Pemilihan model pada ekspor lama berbeda pada **54.820 sel layer pertama** karena memakai batas maksimum tersebut. JSON baru di `output/world/` memakai indeks record. Godot asal tidak diubah. [Instruksi dan checksum bukti utama](output/binary/critical_evidence.json).

### EventFlow: alias berasal dari data game

`EventFlow/Info/BindInfo.byml` menjelaskan 72 alias yang dipakai oleh registry korpus. Canonical name dicocokkan ke hash Murmur3 seed 0 dan pointer registrasi ELF; seluruh 1.056 nama dispatch yang memakai factory terhubung ke constructor dan vtable. Ada 904 factory/vtable unik karena alias dan kategori actor dapat memakai implementasi yang sama. Slot yang dipublikasikan disaring agar menunjuk alamat executable yang sejajar empat byte.

Pelacakan statis pada seluruh 904 constructor mempertahankan offset object dan merekam instruksi store vptr utama. Ini memperbaiki satu vtable query yang sebelumnya tertukar dengan vtable SafeString di dalam object, serta satu constructor yang tidak terbaca pemindai lama. Pointer slot asli dan hasil pengikutan thunk disimpan terpisah. Span pointer diteruskan sampai batas nol/non-executable; guard 256 slot tidak tercapai. Peran class-specific slot dan seluruh jalur constructor belum dibuktikan secara dinamis.

`ExitFlowchart` diperiksa tersendiri. Initializer `0x446800` menyimpan nama khusus tersebut, predicate `0x4474e0` membedakannya dari nama lain, dan jalur start `0x447060` menetapkan completion byte pada object+0x50 lalu mengembalikan sukses. Uji memakai callback terminator SafeString berbentuk RET stub dengan semua string sudah diterminasi; batas stub ini dicatat pada [hasil uji](output/binary/exit_flowchart_verification.json).

Pemetaan dispatch menentukan fungsi yang dituju. Ini belum merupakan spesifikasi lengkap perilaku semua action/query.

### Kurva lingkungan dan kondisi BGM

Seluruh 114 parameter kurva terdiri dari 360 record sead berukuran 128 byte. Word pertama adalah jumlah float aktif, word kedua jenis kurva. Jenis 7 `Hermit2D` memakai tangent lokal; jenis 10 `Hermit2DSmooth` menskalakan tangent dengan panjang segmen. Fungsi native berada di `0x19ab390` dan `0x19ab540`. Sebanyak **25.253 perbandingan** cocok dalam toleransi f32. Satu record mempunyai urutan x tidak monoton; input tetap dipertahankan tanpa diurutkan ulang.

Evaluator C1 ditemukan di `0x21e21e0`/`0x21e21f0`. Seluruh 940 program unik diperiksa dalam tujuh keadaan properti: **6.580 perbandingan tanpa mismatch**. Satu pasangan teks kondisi memiliki pengelompokan operator yang berbeda; native mengikuti AST bytecode. Pada `WorldHour=22, WorldMinute=29, WorldSecond=55`, bytecode bernilai false, sedangkan pembacaan teks dengan prioritas boolean biasa bernilai true. Lihat [spesifikasi C1](docs/C1_CONDITIONS.md).

Indeks properti C1 memakai urutan `GlobalProperty`, bukan `BgmPropertyParam.UniqueID`. Contohnya indeks 15 adalah `FacilityMusicNumber`, sedangkan ID tabel 15 adalah `NetDemoState`.

### Resep, tipe tabel, dan presisi

Switch slot 0–5 pada `0xedac50` mengonfirmasi enam pasangan material/jumlah dan urutannya. Sentinel material kosong adalah 65534; output jumlah native dibaca sebagai u8. Ini memverifikasi pembacaan bahan, belum seluruh transaksi crafting.

Nama string BCSV memakai kapasitas dalam descriptor, misalnya `Name string32`; enum memakai `Name.hshCstringRef`. Aturan tersebut memulihkan 1.957 nama kolom. Label domain enum yang cocok lokal berjumlah {number(schema['counts']['enum_values_resolved'])} dari {number(schema['counts']['enum_values'])} nilai. Nilai tanpa label domain dan sembilan string yang tidak valid/terpotong sebagai UTF-8 tetap mempertahankan hash atau bytes. Kandidat label tambahan tidak dipromosikan otomatis menjadi makna terkonfirmasi.

Pembaca BYML independen mencocokkan seluruh 2.313 tree dengan hasil pembaca dasar, sekaligus mempertahankan tag scalar, offset, key/string table, dan bits mentah. Terdapat 9.397 nilai s64; semuanya dalam rentang integer aman JSON pada korpus ini. Graph tetap menyimpannya sebagai string desimal plus hex agar konversi masa depan tidak kehilangan bit. Tidak ditemukan key dictionary duplikat.

Pembaca RE EventFlow kini mempertahankan f32 tanpa pembulatan enam desimal. Perubahan salinan tool dicatat dalam provenance; sumber pengguna tetap utuh.

## Pemetaan biner dan batas hasil dekompilasi

- Snapshot asal: {number(baseline['functions_indexed'])} fungsi, {number(baseline['direct_branch_records'])} rekaman cabang langsung, dan {number(baseline['string_references'])} referensi string. Sebanyak 6.402 pseudocode asal tetap tersedia.
- Inventaris Ghidra baru memuat {number(sum(r['evidence']=='new_Ghidra_inventory' for r in functions.values()))} kandidat fungsi executable. [Inventaris gabungan](output/binary/function_inventory.json) mempertahankan asal setiap entry; batas fungsi hasil analisis otomatis tidak dianggap source asli.
- Ekspor baru: **{number(decomp['valid_pseudocode_files'])} berkas pseudocode executable**, mencakup {number(decomp['targeted_with_pseudocode'])}/{number(decomp['targeted_addresses'])} alamat target tahap ini. Ada {number(len(missing))} target tanpa pseudocode; fallback disassembly dan statusnya tercatat di [ringkasan dekompilasi](output/binary/decompilation_summary.json).
- {number(decomp['with_warnings'])} pseudocode memiliki peringatan; {number(decomp['with_bad_instruction_warnings'])} memuat tanda masalah instruksi. Inferensi signature bisa salah dan dapat menghilangkan pemakaian return value. Keberadaan pseudocode tidak berarti perilaku fungsi sudah terbukti.
- {number(atlas['relocated_code_pointers'])} pointer relative ke kode, {number(atlas['distinct_relocated_code_targets'])} alamat target unik, dan {number(atlas['code_pointer_arrays'])} deret pointer dicatat untuk penelusuran panggilan tidak langsung. Deret tersebut tidak otomatis dianggap vtable.
- ELF awal mempunyai **{number(atlas['undefined_symbols'])} simbol impor undefined**. Unggahan ExeFS tambahan kini menyediakan kecocokan ekspor untuk 898 simbol tersebut; rincian dan batasnya pada bagian ExeFS di bawah. [Simbol awal](output/binary/symbols.json), [resolusi lintas modul](output/native_modules/import_resolution.json).
- [SQLite](output/index.sqlite) mempertahankan indeks asal dan menambah `columns_resolved`, `native_functions`, serta `decomp_new` untuk sumber terbaru.

## Yang belum terpetakan secara semantik

1. **91 kemunculan kolom BCSV** belum memiliki nama asli yang terverifikasi; sebagian kini mempunyai tipe baca atau peran fungsional yang teruji. Setiap kolom tetap mempunyai hash, offset, tipe, contoh nilai, dan kandidat fungsi pembaca: [daftar bukti](output/schemas/unresolved_evidence.json).
2. BYML primer masih memiliki {number(byml_names['unresolved_keys'])} key hash/ID tanpa descriptor unik yang dipilih, mencakup {number(byml_names['unresolved_key_occurrences'])} kemunculan. [Daftar tersisa](output/schemas/byml_names_unresolved.json). Indeks kandidat lama lintas format tetap disimpan di `hash_names_expanded.json`; hitungannya bukan cakupan pemulihan BYML terbaru. Banyak key merupakan ID dinamis; pemulihan nama tidak otomatis menentukan perilaku.
3. Perilaku lengkap seluruh handler, penjadwalan event, AI, ekonomi, pertumbuhan, fisika, save, dan sinkronisasi belum mempunyai spesifikasi dan uji menyeluruh. Pemetaan fungsi menyediakan jalur penelusuran, bukan pengganti pekerjaan tersebut.
4. Geometry, animasi, audio gelombang, VFX, shader, dan Havok yang hanya disebut tool lama tidak dapat dipulihkan dari metadata JSON saja jika sumber biner tidak ikut paket. Dua tekstur lingkungan yang memang tersedia sudah dipulihkan.
5. Uji native memakai emulasi helper terisolasi, bukan menjalankan game lengkap. Integrasi runtime dan konversi Godot tidak dikerjakan sesuai batas tugas.

Karena bagian ini masih ada, laporan **tidak menyatakan seluruh ACNH selesai direkayasa balik**. Syarat pengguna “semuanya terpetakan” pada tingkat perilaku belum terpenuhi; `output/coverage.json` menandainya eksplisit dengan `full_user_goal_completed=false`.

## Validasi dan penggunaan hasil

Pemeriksaan helper/blok native berjumlah **{number(total_checks)} kasus/perbandingan**, mencakup terrain, C1, kurva, ExitFlowchart, item/CRC, Stage, byte BCSV, flag, RNG, dan cuaca. Rincian dihitung di `output/coverage.json`. **{number(byml_native['comparisons'])} pemeriksaan pembaca BYML dicatat terpisah** agar volume validasi struktur tidak disamakan dengan cakupan perilaku game. Hasil, checksum ELF, serta batas stub/toleransi disimpan bersama output. Untile tekstur memeriksa {number(sum(m['tile_blocks_checked'] for t in textures for m in t['mips']))} blok dan kesetaraan retile pada blok yang digunakan.

Pemeriksaan integrasi membandingkan setiap sel terrain dengan raw, descriptor dan label enum dengan CRC, batas slot native, header/payload DDS, seluruh blob manifest, integritas SQLite, serta CRC seluruh berkas arsip asal. Log terakhir: [verification.log](output/verification.log).

Mulai konversi berikutnya dari [manifest](output/manifest.json), [katalog tabel resolved](output/schemas/catalogue.json), [BYML bernama](output/byml_resolved/catalogue.json), [item](output/items/catalogue.json), [katalog aset JSON](output/assets/catalogue.json), dan [kontrak data](docs/DATA_CONTRACT.md). Gunakan `tables_resolved/` untuk nama dan tipe terbaru; `decoded/` tetap menjadi pembacaan struktur yang dekat ke sumber. Metadata model lapangan yang tersedia tidak mencakup resource furnitur/tree yang disebut tabel item; nama resource dipertahankan sebagai referensi, tanpa menganggap mesh sudah tersedia. Jangan memakai kandidat atau pseudocode otomatis sebagai aturan gameplay terkonfirmasi.

```bash
python /workspace/acnh-re/tools/build_all.py /workspace/downloads/ACNH_island_RE/ACNH_island_RE
python -m unittest discover -s /workspace/acnh-re/tests -v
```

Pembacaan format memakai Python 3.11+. Pemeriksaan/disassembly native memerlukan dependensi pada `requirements-native.txt` yang sudah terpasang di `.deps`. Ekspor pseudocode merupakan tahap Ghidra tersendiri dengan JDK 21; script ada pada `ghidra_scripts/`. Pipeline data tidak membuka editor Godot dan tidak memerlukan kunci konsol. Rujukan eksternal beserta lisensi ada pada [NOTICE](tools/external/NOTICE.md).

## Lampiran: seluruh tabel BCSV menurut domain

Pengelompokan domain mengikuti nama tabel dan ditandai sebagai klasifikasi. Semua 164 tabel tetap dirujuk ke JSON dengan hash/offset sumber; kategori ini bukan pembuktian perilaku native.

'''
    if modules:
        extra=f'''## Unggahan ExeFS tambahan dan pemetaan suara NPC

Lima berkas tambahan (`main.npdm`, `rtld`, `main`, `subsdk0`, `sdk`) disimpan terpisah di `inputs/additional_exefs/`; paket sumber awal dan Godot tetap utuh. Semua empat executable adalah NSO0 yang dapat dibuka dengan LZ4. **12 hash segmen** cocok dengan header masing-masing. Ketiga segmen `main` cocok byte demi byte dengan `main.elf` lama, termasuk build ID 1.0.0. Alamat RE sebelumnya tetap berlaku untuk `main` ini. Alamat SDK/subsdk0 relatif ke modul masing-masing. [Katalog dan hash](output/native_modules/summary.json).

NPDM tambahan memiliki Title ID `01006f8002326000`. Sebanyak 510 byte berbeda dari NPDM lama, seluruhnya dalam region signature ACID dan kunci publik. Header, ACI0 dan isi descriptor di luar region tersebut identik; verifikasi signature kriptografis tidak dilakukan. Kedua NPDM dipertahankan sebagai sumber berbeda. [Perbandingan](output/native_modules/npdm_comparison.json).

**37.517 simbol dinamis** kini diindeks pada empat modul. Dari 910 impor `main`, **898 mempunyai kecocokan ekspor unik**: 880 pada `sdk`, 18 pada `subsdk0`. Dua belas sisanya memakai binding `STB_WEAK`: empat marker `__rel_*` dan delapan `glslc*`. Perilaku saat simbol weak tidak tersedia masih memerlukan pemeriksaan caller. Kecocokan ekspor merupakan resolusi statis; load order, relocation lengkap, TLS, constructor dan syscall OS belum menjadi runtime lengkap. [Peta impor beserta lokasi relocation](output/native_modules/import_resolution.json).

SDK sudah dipakai pada uji nyata. `strcmp` pada VA SDK `0x4d7900` ditautkan ke GOT `main` di `0x32cede0` melalui `R_AARCH64_JUMP_SLOT`; instruksi PLT/main/SDK tetap asli. **67.714 kasus strcmp** cocok, termasuk seluruh pasangan byte dan alignment berbeda. Seluruh **2.546.185 pemeriksaan BYML** dijalankan kembali, menghasilkan **84.560 panggilan strcmp asli dan nol stub**, tanpa mismatch. Pemetaan emulasi hanya membutuhkan text SDK untuk fungsi mandiri tersebut; initializer atau syscall SDK lain belum dieksekusi. [Uji strcmp](output/native_modules/strcmp_native_verification.json), [BYML dengan SDK asli](output/native_modules/linked_byml_verification.json). Cakupan BYML ini sama dengan audit sebelumnya dan tidak dijumlahkan sebagai entry baru.

Enam kolom tanpa nama pada `NmlNpcParam` (397 baris) dan `SpNpcParam` (62 baris) kini mempunyai binding native: hash `21c5bbd6`, `42f255d5`, `e52f0037` ditransfer sebagai u8 ke konfigurasi suara+44/+45/+46, yakni object+0x83c/+0x83d/+0x83e. Fallback masing-masing 5/4/1 bila metadata field tidak ditemukan. Blok asli `0x160aff0` setelah pemilihan NPC membaca metadata BCSV, mencari hash, mengisi cache offset, lalu menulis ketiga byte. **995 pemeriksaan** mencakup 459 baris asli, seluruh nilai byte sintetis, seluruh kombinasi field hilang, dan guard bytes. Tidak ada dependensi yang diganti. Nama asli serta makna akustik seperti pitch/timbre/speed belum disimpulkan. [JSON dan bukti](output/npc/voice_configuration_native.json).

ExeFS tambahan mengatasi kekurangan kode modul SDK/multimedia dari audit awal. Mesh, animasi, audio waveform, VFX, shader dan Havok yang tidak ada pada subset RomFS tetap tidak diperoleh dari modul executable ini. [Kontrak input baru](docs/ADDITIONAL_EXEFS.md), [perubahan dari laporan terakhir](output/progress_additional_exefs.json).

'''
        report=report.replace('## Yang belum terpetakan secara semantik\n',extra+'## Yang belum terpetakan secara semantik\n',1)
    if calendar_native and flowers:
        extra=f'''## Kalender SDK, batas hari, dan genetika bunga

Harness sekarang memetakan main, SDK, subsdk0 dan rtld serta menerapkan relocation yang didukung. **{number(relocation['pointer_checks'])} pointer relocation** diperiksa, terpisah dari jumlah uji perilaku. Resolusi undefined dengan satu ekspor strong memakai ekspor itu; definisi lokal tetap relatif ke modulnya. Init module, TLS dan layanan OS tidak disimulasikan. Semua helper yang diterbitkan berjalan tanpa stub dan tanpa mencapai syscall OS.

Kalender SDK diperiksa pada seluruh **146.097 tanggal dalam siklus Gregorian 400 tahun**, ditambah tanggal batas dan sampel tahun 1–9999. **{number(calendar_native['comparisons'])} perbandingan** mencakup konversi kalender/Posix, 16.268 kasus normalisasi hari beserta guard, serta 4.151 kasus offset hari s32. Fungsi game `0x1fbc00` mengurangi satu tanggal bila jam <05, lalu menulis 05:00:00. Tepat 05:00 tetap memakai tanggal yang sama. Perkalian nanodetik s64 pada helper offset tetap mempertahankan overflow aslinya. Ini aritmetika kalender UTC; pembacaan jam host atau inisialisasi timezone OS belum dibuktikan. [Kalender](output/calendar/native_verification.json).

Uji cuaca lengkap kini mencakup **27.512 prediksi** pada 00:00:00, 04:59:59, 05:00:00 dan 23:59:59, dengan tanggal efektif, pola dan state akhir RNG yang cocok. Fungsi asli berjalan melalui GOT/PLT ke SDK asli. Flag override tetap 0; event khusus belum tercakup. [Cuaca lintas modul](output/weather/native_linked_verification.json).

Pewarisan bunga `0x4cd070` teruji pada **seluruh 65.536 pasangan byte gen induk** dan 1.024 pasangan u32 tambahan. Empat lokus memakai dua bit per lokus; 01 dan 10 sama-sama dosage 1. Induk heterozigot saja yang mengambil RNG; urutan lokus A→D, masing-masing induk A lalu B. Hasil kanonis memakai kode 0/1/3. Gen anak, state akhir RNG dan guard cocok.

Seluruh **270 baris genotipe dari delapan jenis bunga** kini terhubung ke resource FgMainParam dan stage pertumbuhan. Rose mempunyai 81 kombinasi, tujuh jenis lain masing-masing 27. Lookup genotipe/growth `0x4cc4d0` diuji pada seluruh byte gen dan enam input stage, memakai raw BCSV serta cache/array yang direkonstruksi dari data asli dan literal enum native. Constructor/file loader tidak dijalankan dalam harness ini. **{number(flowers['comparisons'])} pemeriksaan bunga** mencakup lookup resource, RNG, default gen dan kasus batas. [Genotipe JSON](output/flowers/genotypes.json), [hasil native](output/flowers/native_verification.json).

`DefaultHeredity` kini terverifikasi pada **{number(flowers['default_gene_resources'])} resource**: normalisasi ke bud Grow=2, berhenti pada baris matching yang DefaultHeredity-nya aktif, atau memakai **baris matching terakhir** bila tidak ada penanda. Field hash `753336dd` dipakai sebagai awal lookup alternatif bila terisi; seluruh nilai alternatif dalam sumber mengarah ke Grow=0. Nama aslinya tetap belum diketahui. [Gen default](output/flowers/default_genes.json).

Caller `0x4d5e50` juga diuji pada **11.664 pasangan induk dalam jenis yang sama**, sampai menghasilkan item delapan byte: ID bud, gen pada byte terendah FreeParam (item+4), state RNG dan guard cocok. Pointer hasil object C++ memakai register X8 tersembunyi; argumen eksplisit X0/X1 adalah object Fg dan item induk lain. Signature otomatis yang menampilkan hasil sebagai argumen biasa tidak dianggap ABI otoritatif. [Item anakan](output/flowers/offspring_items.json).

Ada kasus data Black Cosmos yang perlu dipertahankan: ID 60151→60153→60155→60151 mempunyai Grow 2→3→0, sehingga permintaan Grow=1 tidak tercapai. Pada **24 input sintetis**, kode asli mengulang dua putaran yang sama dan belum kembali dalam batas 20.000 instruksi. Kasus ini dicatat sebagai eksekusi berbatas, bukan dipaksa sukses atau diganti sentinel. Caller item anakan yang diuji selalu meminta Grow=2 dan tidak memicu kasus itu. Belum dibuktikan bahwa workflow game lain mengirim permintaan Grow=1 tersebut; ini belum dinyatakan sebagai bug gameplay. [Siklus dan trace](output/flowers/growth_cycles.json).

Model probabilitas Mendelian mencakup 6.561 pasangan genotipe kanonis dengan bobot rasional per 256. Model mengasumsikan pemilihan alel adil dan independen. Pemilihan pasangan tanaman, posisi spawn, kelayakan breeding, bonus penyiraman/pengunjung, serta aturan golden rose tetap pekerjaan lanjutan. [Probabilitas](output/flowers/inheritance_probabilities.json), [kontrak dan batas](docs/CALENDAR_FLOWERS.md), [perbandingan tahap terakhir](output/progress_calendar_flowers.json).

'''
        report=report.replace('## Yang belum terpetakan secara semantik\n',extra+'## Yang belum terpetakan secara semantik\n',1)
    for domain,rows in sorted(domains['domains'].items()):
        report+=f'### {domain}\n\n| Tabel | Baris | Kolom bernama/total |\n|---|---:|---:|\n'
        for r in rows:
            report+=f"| [{r['table']}](output/{r['schema']}) | {number(r['rows'])} | {r['named_columns']}/{r['columns']} |\n"
        report+='\n'
    (ROOT/'LAPORAN_AKHIR.md').write_text(report)
    (ROOT/'README.md').write_text('''# ACNH: sumber rekayasa balik untuk konversi berikutnya

Seluruh B_data yang tersedia sudah dibaca secara struktural. Semantik seluruh game belum terpetakan 100%; batas dan field yang belum diketahui dicatat, tanpa mengubah proyek Godot asal.

- [Laporan temuan, keberhasilan, validasi, dan batas cakupan](LAPORAN_AKHIR.md).
- [Manifest sumber](output/manifest.json), [inventaris seluruh paket](output/source_inventory.json), [cakupan yang dapat dibaca mesin](output/coverage.json).
- [Perubahan dari laporan sebelumnya](output/progress_since_previous.json).
- [Katalog tabel JSON terbaru](output/schemas/catalogue.json), [katalog aset JSON](output/assets/catalogue.json), [kontrak data](docs/DATA_CONTRACT.md).
- [BYML dengan nama field pulih](output/byml_resolved/catalogue.json), [kamus descriptor](output/schemas/byml_names.json), [word item dan penempatan](output/items/catalogue.json), [uji native item](output/items/native_verification.json).
- [Dispatch native](output/binary/event_handlers_resolved.json), [terrain](output/relations/terrain_native.json), [resep](output/relations/recipe_materials_native.json), [kurva](output/environment/curves.json), [tekstur](output/environment/textures.json).
- [Stage dan actor](output/stage/catalogue.json), [cuaca dan validasi native](output/weather/native_verification.json), [RNG](output/random/native_rng.json), [predicate flag](output/flags/reset_policy_native.json), [kontrak dan batas](docs/NATIVE_STAGE_WEATHER.md).
- [ExeFS tambahan dan simbol SDK](output/native_modules/summary.json), [BYML tanpa stub SDK](output/native_modules/linked_byml_verification.json), [konfigurasi suara NPC](output/npc/voice_configuration_native.json), [kontrak input](docs/ADDITIONAL_EXEFS.md).
- [Kalender dan batas hari](output/calendar/native_verification.json), [cuaca lintas SDK](output/weather/native_linked_verification.json), [genotipe bunga](output/flowers/genotypes.json), [gen default](output/flowers/default_genes.json), [kasus siklus](output/flowers/growth_cycles.json), [kontrak](docs/CALENDAR_FLOWERS.md).
- [Field belum bernama beserta bukti](output/schemas/unresolved_evidence.json), [indeks SQLite](output/index.sqlite), [status dekompilasi](output/binary/decompilation_summary.json).

Nilai raw dan provenance tetap otoritatif. Nama/hash kandidat, pseudocode otomatis, dan struktur yang valid dibedakan dari perilaku yang sudah diverifikasi native.
''')
    print(json.dumps({'source_files':len(source_files),'native_functions_catalogued':len(functions),
        'new_pseudocode':len(docs),'targets_without_pseudocode':len(missing),
        'native_comparisons':total_checks,'semantic_completion':False},indent=2))


if __name__=='__main__':build()
