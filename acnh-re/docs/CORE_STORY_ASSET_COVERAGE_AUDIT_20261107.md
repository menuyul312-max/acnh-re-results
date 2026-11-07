# Audit cakupan penggunaan aset untuk gameplay inti ACNH

**Tanggal:** 7 November 2026  
**Cakupan:** audit silang independen atas 28 beat dari pendaftaran pemain sampai konser K.K. pertama dan pembukaan Island Designer. Ini memeriksa ledger/crosswalk, data UI, parameter, pesan, stage, dan katalog yang sudah ada; tidak mengubah proyek Godot dan tidak menyalin aset model/audio mentah.

Ledger mesin: [core_story_asset_coverage_audit_20261107.json](../output/gameplay/core_story_asset_coverage_audit_20261107.json). Sumber utamanya [story_asset_crosswalk.json](../output/gameplay/story_asset_crosswalk.json), inventaris kelas aset [asset_inventory.json](../output/gameplay/story_asset_parts/asset_inventory.json), [page_layout_method_bindings.json](../output/ui_hud/page_layout_method_bindings.json), [animation_semantics.json](../output/ui_hud/animation_semantics.json), dan manifest data ACNH 1.0.0.

## Hasil audit

Struktur crosswalk mencakup 28 beat dan 11 keluarga aset dengan 381 rujukan. Setelah integrasi bukti UI prolog, hitungannya **235 OPEN**, **73 CAT**, dan **73 EF/PSEUDO/STRUCT/TBL**; `full_semantic_coverage_proven=false`. Jadi 19,2% rujukan berstatus bukti sumber selain katalog/placeholder (`73/381`), sedangkan 80,8% masih terbuka atau katalog saja (`308/381`). Persentase tersebut mengukur rujukan crosswalk, bukan persen reverse engineering seluruh game.

| Keluarga | Rujukan non-OPEN / katalog | OPEN | Makna praktis |
|---|---:|---:|---|
| UI | 25 (5 EF, 9 PSEUDO, 11 CAT) | 19 | Sejumlah handler dan nama layout tercatat; halaman aktual untuk banyak dialog, recipe, rating, dan placement belum ditautkan. |
| Animasi | 21 (3 EF, 10 STRUCT, 2 TBL, 6 CAT) | 20 | BFLAN/ASB dan perintah aksi sebagian ada; `ActionIdx` ke native state index 26/27/19 terbukti statis untuk nilai 1–3, tetapi state index ke clip/ASB node dan timing runtime belum terbukti. |
| Model | 34 CAT | 18 | Semua yang tertaut ke cerita masih kandidat katalog; model mentah tidak tersedia. |
| Audio | 23 (2 EF, 1 TBL, 20 CAT) | 21 | Musik api unggun punya sambungan numerik sampai tabel audio; kandidat lain belum menjadi pemutaran yang terbukti. |
| Teks | 25 EF | 6 | EventFlow menyebut label/pesan; subset terpilih sudah diverifikasi ke MSBT/BDLI pada 14 locale, tetapi teks tidak membuktikan layar, substitusi, atau voice cue. |
| Tekstur | 3 STRUCT | 25 | Tiga beat prolog kini merujuk pane/material/BNTX structural; screen runtime dan consumer pada beat lain belum terikat. |
| Material/shader | 3 STRUCT | 25 | Tiga beat prolog mempunyai material/pane; enam material-to-GLSL join ada di UI keyboard/message candidate. Pipeline/runtime dan beat lain belum terpetakan. |
| Efek | 0 | 28 | VFX/PTCL tersedia pada inventaris global, tetapi pemicu/actor/material per adegan belum dihubungkan. |
| Font | 2 STRUCT | 26 | Dua beat prolog mendeklarasikan alias ke konfigurasi FCPX; locale yang dipakai runtime dan font per beat lain belum dikunci. |
| Data dunia | 8 (4 PSEUDO, 4 TBL) | 20 | Preset/template dan beberapa consumer telah dipetakan; kartu pulau ke preset/save serta transform cerita masih terbuka. |
| Collision | 2 CAT | 27 | Katalog/kelas collider belum terhubung ke instance bangunan, actor, atau hasil validasi/query. |

Efek masih `OPEN` pada seluruh 28 beat. Tekstur, material/shader, dan font masih mayoritas `OPEN`; beberapa slot prolog sekarang `STRUCT`. Ini terutama **kekosongan relasi beat→consumer/runtime**, bukan bukti bahwa arsipnya tidak ada: inventaris global mencatat 431 kontainer BNTX, dua arsip BFSHA, dua VFXB/PTCL, serta importer font. Karena itu, angka slot wajib yang terisi sebaiknya dibaca sebagai disiplin pencatatan kategori, bukan cakupan semantik.

Follow-up khusus lima layar prolog dan layout pendukung menemukan 195 entri texture-list dengan kandidat BNTX exact-name dalam archive yang sama, 193 jalur pane→material→texture→BNTX, deklarasi font `SystemB_00`/`Normal_00` ke index FCPX, dan enam material→GLSL bernama. Delapan referensi struktur ini telah dimasukkan ke beat title/registration, opening landing, dan campfire. Dua PTCL dan link database efek ditemukan secara global, tetapi belum ada event/actor prolog yang terhubung ke effect key. Ini adalah bukti `CONSUMER_JOINED` di struktur archive UI supplemental, bukan bukti seluruh 28 beat membuka halaman itu: archive bertanda `new_path`, trigger runtime/page handoff belum tersambung, dan gambar empat map-card `P_Capture_00` masih belum memiliki producer.

## Jalur aset yang sudah memiliki bukti terkuat

**Pendaftaran/UI.** `REGISTRATION_TERRAIN_PROOF_20261107.md` dan flow source 661 (`Tutorials_Prologue1_Charactermaking.bfevfl`, SHA-256 `cbf8fc7e4f5df544398f8dfd4b401f558bf386862af1abac72b8ab57c1d8688d`) mengikat name, birthday, avatar, weather-area, dan `UIMapSelectHandling → cVillage`. Analisis NSO statis di `page_layout_method_bindings.json` mengembalikan string layout yang tepat dari method slot 46 untuk `TitlePage` VA `0x156cde0`→`Title`, `CharaMakePage` `0x11959c0`→`CharaMake`, `DateInputPage` `0x11e1cc0`→`DateInput`, `MapSelectPage` `0x1241910`→`CharaMakeMap`, dan `PrologueBGPage` `0x140efd0`→`WipePrologue`. Hash BFLYT serta child `arc!blyt/...` ada di ledger.

Ini membuktikan kecocokan identifier/layout dalam data supplemental, **bukan** bahwa handler EventFlow membuat page itu. Pemindaian 135 page method menemukan 134 kecocokan nama layout, tetapi tidak menemukan site instruksi B/BL langsung ke getter; indirect call belum dikaitkan ke receiver/page tertentu. Empat kartu `CharaMakeMap` (`L_Btn_00`…`L_Btn_03`) juga belum menunjuk sumber gambar preview atau data preset. Sambungan `cVillage → preset/seed → record save → spawn` tetap `OPEN`.

**Animasi UI dan actor.** `animation_semantics.json` memetakan section/target BFLAN secara struktural; prolog memiliki resource seperti `CharaMake_In/Out`, `CharaMakeMap_In/Out`, `DateInput_In/Out`, dan `WipePrologue_In/Out`. Itu cukup untuk mengetahui nama, layout, target pane, dan kurva terurai, tetapi pemanggil animasi dan timing perpindahan masih terbuka. Pada actor, EventFlow memberi aksi seperti `NpcCheers`, `NpcSpRhythm`, `TkkAGuitarPlayEnd`; sebagian nama cocok dengan node ASB yang diparse. Follow-up native memetakan `NpcRequestAction.ActionIdx=1/2/3` ke internal state index `26/27/19` dan nilai `0` ke global yang belum diketahui, tetapi tidak ada join dari angka itu ke nama AnimationInfo/ASB; clip skeletal juga tidak bisa divalidasi ke rig karena arsip model tidak tersedia.

**Teks dan musik.** [STORY_MESSAGE_CUE_FOLLOWUP_20261107.md](STORY_MESSAGE_CUE_FOLLOWUP_20261107.md) memverifikasi 460 referensi pesan dari 17 flow (16 flow berisi pesan), 425 key unik, pada 14 locale: 6.440 pasangan label/index MSBT dan 6.440 pasangan BDLI cocok tepat. Body dialog tidak disalin; versi arsip supplemental belum terautentikasi ke 1.0.0. Untuk api unggun, EventFlow `Tutorials_Prologue5_Campfire` event #140 memberi `MusicName=4318`; `ItemParam` row 1732 / `UniqueID=4318` adalah `FtrMjkMainTheme`, dan `SoundAudioMusic` row 94 / `UniqueID=103` menghubungkannya ke `AudioMusicID=95`, label `Minnaatsumare`. Itu join tabel yang tepat, bukan bukti waveform atau cue dimainkan. Katalog audio hanya mengandung kandidat nama.

**Model/NPC dan fasilitas.** `SpNpcParam` menghubungkan kode actor seperti `rco` dan `tkkA` ke `ResName` `NpcSpRco` dan `NpcSpTkk`; untuk objek inventaris, 7.668 `ItemParam.ResName` punya exact-name match di katalog model. Model tetap `CAT`: inventaris menyebut 37.459 baris katalog, sementara arsip `Model/` tidak tersedia. Katalog tidak membuktikan mesh, rig, pemilihan runtime, atau transform. Untuk bangunan, flow sudah menyebut kelas `cPlayerHouse`, `cMuseum`, `cMarket`, `cBridge`, `cReserveNpcHouse`, `cCampSite`, item/recipe dan flag lifecycle. Tetapi enam cell `StructurePresetA00` yang tercatat belum diberi role cerita; tidak ada cell→posisi dunia→instance/model/PBC/collider yang terbukti.

## Yang belum terbukti untuk gameplay inti

1. **Pendaftaran ke pulau yang dimainkan:** gambar empat map card, ID card terpilih, `cVillage` ke field preset/seed, writer save pertama, stage handoff dan spawn pemain.
2. **Aset UI yang benar-benar dibuka:** handler/page controller ke instance, layout dan BFLAN; banyak UI recipe, donation, placement, rating, public announcement, camper dan Island Designer masih `OPEN`.
3. **Animasi actor:** internal native state index untuk `ActionIdx` 1–3 sudah ditemukan; join index 26/27/19 ke resource, clip/ASB state, rig, waktu, dan perubahan stage tetap belum terbukti. Nama command ke node ASB saja belum menyelesaikan ini.
4. **Instance dunia:** keenam site-cell ke jenis bangunan/plot; cell-to-world origin/axis/unit/rotation/height; validator; model dan collider yang dimuat; mutasi instance dan save/day-change.
5. **Model/audio sebagai katalog:** kandidat harus dihubungkan secara ID ke actor/parameter/consumer per beat. Sesuai kebijakan proyek, katalog cukup menjadi referensi; tanpa raw payload tidak boleh dinaikkan menjadi hasil konversi atau bukti pemutaran.
6. **Tekstur, shader, efek dan font:** beberapa layar prolog memiliki join deklaratif pane→BNTX, font alias→FCPX, dan material→GLSL; sisa pekerjaan adalah mengikat page tersebut ke handler/instance runtime, melacak effect key ke actor/flow, serta mengulang peta per beat pada seluruh cerita atau menandai `not_applicable` bila kategori memang tidak dipakai.
7. **Alur end-to-end:** belum ada satu rantai yang membuktikan input pemain → world query/interaksi → inventory/craft atau placement → save/day-change → gate cerita → UI/actor/stage berikutnya.

## Urutan pemeriksaan yang paling memperkecil gap

1. Tautkan page handler ke factory/constructor/vtable dan page registry; mulai dari `UIMapSelectHandling`, `UICharactermakingHandling`, `UIDateHandling`, `MenuDevice`/`cConstructLicense`, recipe, dan structure preview. Simpan sumber handler, target VA, argumen, dan batas indirect dispatch.
2. Ikat `CharaMakeMap` child panes dan texture/image refs ke empat preview record; ikuti ID hasil `cVillage` ke map/preset/seed/save memakai data 1.0.0, bukan kesamaan nama katalog.
3. Ikuti actor request dari state index `ActionIdx` sampai pemetaan bernama ke `AnimationInfo`/ASB. Tandai kebutuhan rig/model mentah sebagai blocker bila tidak ada.
4. Selesaikan join placement cell/selector/pose/world coordinates, lalu struktur ID ke catalog candidate dan PBC/collider consumer. Jangan menyimpulkan role dari urutan enam cell.
5. Buat tabel cue suara per EventFlow parameter dan table ID. Kasus 4318→95 menjadi pola untuk mencari BGM lain; hasil katalog tanpa numeric/resource consumer tetap `CAT`.
6. Untuk tiap keluarga tekstur/shader/effect/font, gunakan consumer UI/actor yang sudah diikat dahulu, lalu cari key exact dalam archive/container; jangan mempromosikan kemiripan nama.
7. Perbarui crosswalk untuk memisahkan `resource exists`, `candidate`, `consumer joined`, `conversion verified`, dan `runtime verified`; tandai `not_applicable` bila kategori tidak digunakan pada beat agar placeholder `OPEN` tidak disalahartikan sebagai aset hilang.

## Batas dan validasi

Data B_data dan EventFlow beracuan build 1.0.0 dengan hash dalam manifest. UI/MSBT/ASB supplemental archive berisi path/member yang telah diparse, tetapi identitas patch-nya belum dipastikan; kecocokan tidak boleh menghapus batas versi tersebut. Repositori resource publik yang diperiksa sebelumnya berlabel 3.0.3, sehingga bukan pengganti sumber 1.0.0. Model/audio tetap katalog saja sesuai kebijakan proyek.

JSON audit diproduksi dari crosswalk aktual dan memuat hitungan per keluarga, batas bukti, contoh join, serta urutan gap. Validasi yang dijalankan: parse JSON untuk sumber audit, pemeriksaan status/count terhadap `story_asset_crosswalk.json`, cek file sumber terkait, dan `git diff --check`. Tidak ada file crosswalk utama, Godot, atau aset model/audio mentah yang diubah.
