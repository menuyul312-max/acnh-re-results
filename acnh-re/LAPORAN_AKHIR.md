# Laporan rekayasa balik paket ACNH

**Status: seluruh berkas mentah B_data yang tersedia sudah dipetakan secara struktural. Rekayasa balik seluruh semantik game belum selesai 100%.** Pemetaan alamat, JSON hasil baca, atau keberadaan pseudocode tidak disamakan dengan pemahaman perilaku lengkap. Bagian yang belum terbukti dicatat eksplisit.

Proyek Godot hanya menjadi referensi dan tidak diubah. Hasil baru berada di `/workspace/acnh-re`, untuk menjadi sumber konversi berikutnya tanpa ketergantungan engine.

**Fokus terbaru sesuai arahan pengguna:** [tujuh sistem mekanik](docs/FOCUS7_MECHANICS.md), meliputi fisika/collision, gerakan, terrain, ground dinamis, posisi, NPC/navigasi, dan item/alat/crafting. Peta mencakup 69 tabel, 194 parameter PlayerActor, 98 NpcActivityParam dan 55 graf AI. [Lanjutan terbaru](docs/NPC_NAVIGATION_KERNEL.md) menambah 2.083 kasus: kernel A* dengan callback biaya/heuristik asli, extractor rute, pool node, handoff dan pemilihan target. Total helper/blok terbaru **1.134.009**. Kernel diuji pada grid rekonstruksi, termasuk perbandingan Dijkstra; world menjadi grid, worker async, steering, solver collision dan seluruh tujuh sistem belum selesai dipahami. Angka tahap lama adalah snapshot historis.

**Tahap mekanik:** [audit collision dan ledger seluruh sistem](docs/MECHANICS_RE.md) menambah 262.164 perbandingan blok native, pemetaan mode collision pada 235 state pemain, parameter terrain dan 465 fungsi titik masuk riset lintas sistem. Jumlah helper/blok kumulatif menjadi 1.042.503; angka lama pada uraian tahap sebelumnya adalah snapshot historis. Model/sound selanjutnya memakai katalog sebagai referensi, sesuai arahan pengguna. Seluruh perilaku game tetap belum selesai dipahami.

**Tambahan 2 November 2026:** arsip RomFS baru berisi 25.597 berkas, termasuk seluruh 1.171 B_data awal yang identik. Audit tambahan memetakan 965.426 pesan dalam 14 varian bahasa, 888.034 label BDLI, 83 state machine animasi dan metadata UI/shader. [Laporan tambahan dan batasnya](docs/ADDITIONAL_ROMFS.md). Angka cakupan tabel/BYML di bagian lama tetap merujuk korpus awal; shader/VFX kini tersedia sebagian, sementara direktori Model dan Sound/Resource tetap tidak tersedia. Ini belum menyelesaikan perilaku seluruh game.

Perubahan terhadap laporan sebelumnya: [progress_since_previous.json](output/progress_since_previous.json). Tahap ini menambah validasi pembaca BYML asli, nama array bertipe, registry/record Stage, view byte BCSV, predicate flag, RNG, dan pemilih cuaca hari biasa. Nama key BYML yang pulih bertambah dari 2.910 menjadi 2.979; nama asli kolom BCSV tetap 1.957, dengan empat view baca native baru untuk kolom unresolved.

## Sumber dan batas input

- Paket asli: 15.564 berkas, 235.591.766 byte. [Inventaris seluruh berkas dan SHA-256](output/source_inventory.json).
- `A_logic` paket awal menyertakan `main.elf` dan `main.npdm`. ELF SHA-256: `5bf707c3dc5dac0ad9635af7d336ec580f81c3f7876d0f55400d1900e3415d74`. Alamat native dalam laporan adalah VA ELF; pseudocode memakai image base tambahan `0x100000`.
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
| Nama field BYML | 2.979/3.410 key hash/ID; 99.452% kemunculan memiliki descriptor pulih | [Kamus dan bukti nama](output/schemas/byml_names.json) |
| Item dan penempatan | 46.034 word item; seluruhnya cocok definisi/sentinel; 44.443 penempatan berkoordinat | [Katalog per sumber](output/items/catalogue.json) |
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

Sebanyak **437.114/439.521 kemunculan key (99.452%)** memiliki nama yang pulih. Angka ini adalah cakupan nama key BYML, bukan persentase RE seluruh game. Semua 2.313 tampilan bernama dapat dibalik ke tree key asli. Kandidat ambigu, hash tanpa nol depan, dan tipe wire asli tetap dipertahankan. [Tampilan JSON bernama](output/byml_resolved/catalogue.json).

Copy native `0xf589b0`/`0xf589e0` mengonfirmasi layout `<u16 ID, u8 SystemParam, u8 AdditionalParam, u32 FreeParam>`. Reset `0x1a6560` menghasilkan word `0xfffe`. Helper `0xf58a90` memetakan AdditionalParam ke ID dummy pembungkus dan mempertahankan MessageBottle `0x16a1`; helper `0xf59f70` membaca koordinat extension dari byte 6/7 jika ID `0xfffd`. **9.747 perbandingan native tanpa mismatch** mencakup seluruh word unik korpus, seluruh 256 AdditionalParam sintetis pada ID batas, copy/guard bytes, reset, koordinat extension, tabel kertas, dan CRC32 descriptor. Tidak ada dependensi yang di-stub dalam uji tahap ini.

Semua 46.034 kemunculan terhubung: 7.471 ke `ItemParam`, 38.172 ke `FgMainParam`, dan 391 sentinel kosong. Semuanya menyimpan word mentah, pointer sumber, dan referensi baris tabel. AdditionalParam seluruh korpus nol; cabang wrapping diuji secara sintetis. FreeParam tetap union bergantung jenis item; belum dipaksakan sebagai jumlah atau remake. Khusus keluarga bunga, byte terendah FreeParam kini terbukti membawa gen melalui caller pembentukan item anakan, dijelaskan pada bagian genetika. Interpretasi rotation/buried/dropped dari NHSE masih rujukan eksternal. Skala koordinat dan transformasi Godot belum disimpulkan. [Kamus item](output/items/words.json), [hasil uji asli](output/items/native_verification.json).

### Stage, pembaca BYML asli, flag, RNG, dan cuaca

Registry actor berisi **158 nama yang dibaca dari tabel native**, masing-masing cocok Murmur3 dan indeks hasil lookup `0x628b0`. Seluruh 108 resource Stage kini mempunyai katalog hubungan, actor, hash parent, environment, dan target perpindahan. Ada 311 kemunculan actor; **18 kemunculan dari tiga hash** tidak terdaftar dan dilewati pembaca `0xfeb390`. `Parent` mengacu pada jenis actor, bukan ID instance unik. Hash yang belum dikenal tetap dipertahankan. [Registry](output/stage/actor_type_registry.json).

Seluruh **142 record volume/perpindahan** cocok dengan proyeksi native `0xfeeeb0` pada dua mode (284 pemeriksaan); 265 kasus tambahan menguji arah/interpolasi trigonometri `0x1cb70` secara bit-exact f32. Nama field Stage `ActorName`, `ActorList`, `UIList`, dan `UIName` mempunyai kecocokan Murmur3 serta bukti indeks key dan fungsi konsumen. Formula dan batas initializer/stub dicatat di [Stage](output/stage/native_summary.json), [kontrak native](docs/NATIVE_STAGE_WEATHER.md).

Pembaca BYML asli menerima semua 2.313 sumber. **443.204 entry dictionary dan 319.774 entry array** cocok tag dan word dalam **2.546.185 pemeriksaan tanpa mismatch**. Audit awal memakai pengganti `strcmp` SDK; audit dengan SDK unggahan berikutnya menjalankan seluruh pemeriksaan kembali menggunakan implementasi asli (lihat bagian ExeFS). ABI output terdiri dari word ternormalisasi u32 dan tag u8, lalu padding tiga byte. Temuan batas penting: helper dictionary by-index langsung `0x1ef63d0` hanya memeriksa count tidak nol, bukan batas indeks; caller wajib memvalidasi indeks. Pemeriksaan ini membuktikan pembacaan struktur, bukan jutaan aturan gameplay.

Empat view kolom tanpa nama diperbaiki berdasarkan instruksi byte asli: `HumanAnimParam:d5217761` dan `FieldLandMakingError:0b3be609` dibaca signed s8; `EventFlagsLandTempParam:3c7fb88f` serta `ItemRemake:d4f43b0b` dibaca u8. Ada 445 nilai HumanAnim 0xff yang kini menjadi -1; blok native memilih fallback caller untuk byte negatif. Sebanyak 1.172 baris diperiksa dan 2.048 perbandingan instruksi/blok cocok. Nama asli empat kolom tetap belum diketahui. [Bukti tipe](output/schemas/native_read_views.json).

Kolom hash `5140e4b4` muncul pada lima tabel EventFlags (884 baris). Predicate `0xf54530` terbukti: selector 0/lainnya=false; 1=counter!=0; 2=counter!=0 atau byte tambahan!=0; 3=true; 4=counter>0. Counter adalah s64 pada context+0, byte tambahan pada +0x1a. Makna context tingkat gameplay belum terbukti. **8.910 kasus native cocok**, tanpa stub. [Kebijakan reset](output/flags/reset_policy_native.json).

RNG integer (seed, state eksplisit, u32/u64, ekspor state) cocok dalam **35.567 perbandingan tanpa stub**. State eksplisit semua nol mempunyai fallback native ke state hasil seed 0; ini berbeda dari `Random::with_state` MeteoNook. [RNG](output/random/native_rng.json).

Cuaca menyediakan 34 pola × 24 jam untuk cuaca dan angin, serta 20 tabel peluang per hemisphere. **6.398 perbandingan** terhadap MeteoNook yang dipin menemukan **empat nilai cuaca per jam berbeda**: Fine02 jam 18/19 dan Fine06 jam 17/19. Nilai paket lokal dipertahankan; seluruh bobot, kalender, dan angin cocok. Perbedaan tidak dianggap error parse atau diperbaiki dengan menyalin tabel publik.

Pemilih cuaca hari biasa `0xfdd9b0` kini dijalankan memakai object parameter yang diisi data lokal dan accessor native asli: seed dicampur dengan `(year*512 + month*32 + day)*65536` modulo u32; dua draw dilewati; draw ketiga memilih roll 0–99 melalui perkalian high-word, lalu akumulasi bobot s8 memilih pola. **59.756 pemeriksaan tanpa mismatch/stub** mencakup 732 tanggal kalender, seluruh 4.000 slot peluang, 27.512 prediksi, dan state RNG akhirnya. Jalur sebelum 05.00 sekarang memakai SDK asli dan sudah diuji; tanggal efektif mundur sehari. Flag event khusus dan visual/cloud/fog/aurora/stars tetap belum diuji. Ini bukan eksekusi seluruh runtime cuaca. [Audit awal](output/weather/native_verification.json), [verifikasi SDK dan batas hari](output/weather/native_linked_verification.json).

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

Nama string BCSV memakai kapasitas dalam descriptor, misalnya `Name string32`; enum memakai `Name.hshCstringRef`. Aturan tersebut memulihkan 1.957 nama kolom. Label domain enum yang cocok lokal berjumlah 401.293 dari 429.511 nilai. Nilai tanpa label domain dan sembilan string yang tidak valid/terpotong sebagai UTF-8 tetap mempertahankan hash atau bytes. Kandidat label tambahan tidak dipromosikan otomatis menjadi makna terkonfirmasi.

Pembaca BYML independen mencocokkan seluruh 2.313 tree dengan hasil pembaca dasar, sekaligus mempertahankan tag scalar, offset, key/string table, dan bits mentah. Terdapat 9.397 nilai s64; semuanya dalam rentang integer aman JSON pada korpus ini. Graph tetap menyimpannya sebagai string desimal plus hex agar konversi masa depan tidak kehilangan bit. Tidak ditemukan key dictionary duplikat.

Pembaca RE EventFlow kini mempertahankan f32 tanpa pembulatan enam desimal. Perubahan salinan tool dicatat dalam provenance; sumber pengguna tetap utuh.

## Pemetaan biner dan batas hasil dekompilasi

- Snapshot asal: 60.515 fungsi, 663.262 rekaman cabang langsung, dan 33.487 referensi string. Sebanyak 6.402 pseudocode asal tetap tersedia.
- Inventaris Ghidra baru memuat 148.316 kandidat fungsi executable. [Inventaris gabungan](output/binary/function_inventory.json) mempertahankan asal setiap entry; batas fungsi hasil analisis otomatis tidak dianggap source asli.
- Ekspor baru: **64.466 berkas pseudocode executable**, mencakup 64.466/64.475 alamat target tahap ini. Ada 9 target tanpa pseudocode; fallback disassembly dan statusnya tercatat di [ringkasan dekompilasi](output/binary/decompilation_summary.json).
- 4.747 pseudocode memiliki peringatan; 5 memuat tanda masalah instruksi. Inferensi signature bisa salah dan dapat menghilangkan pemakaian return value. Keberadaan pseudocode tidak berarti perilaku fungsi sudah terbukti.
- 197.845 pointer relative ke kode, 95.230 alamat target unik, dan 18.348 deret pointer dicatat untuk penelusuran panggilan tidak langsung. Deret tersebut tidak otomatis dianggap vtable.
- ELF awal mempunyai **910 simbol impor undefined**. Unggahan ExeFS tambahan kini menyediakan kecocokan ekspor untuk 898 simbol tersebut; rincian dan batasnya pada bagian ExeFS di bawah. [Simbol awal](output/binary/symbols.json), [resolusi lintas modul](output/native_modules/import_resolution.json).
- [SQLite](output/index.sqlite) mempertahankan indeks asal dan menambah `columns_resolved`, `native_functions`, serta `decomp_new` untuk sumber terbaru.

## Unggahan ExeFS tambahan dan pemetaan suara NPC

Lima berkas tambahan (`main.npdm`, `rtld`, `main`, `subsdk0`, `sdk`) disimpan terpisah di `inputs/additional_exefs/`; paket sumber awal dan Godot tetap utuh. Semua empat executable adalah NSO0 yang dapat dibuka dengan LZ4. **12 hash segmen** cocok dengan header masing-masing. Ketiga segmen `main` cocok byte demi byte dengan `main.elf` lama, termasuk build ID 1.0.0. Alamat RE sebelumnya tetap berlaku untuk `main` ini. Alamat SDK/subsdk0 relatif ke modul masing-masing. [Katalog dan hash](output/native_modules/summary.json).

NPDM tambahan memiliki Title ID `01006f8002326000`. Sebanyak 510 byte berbeda dari NPDM lama, seluruhnya dalam region signature ACID dan kunci publik. Header, ACI0 dan isi descriptor di luar region tersebut identik; verifikasi signature kriptografis tidak dilakukan. Kedua NPDM dipertahankan sebagai sumber berbeda. [Perbandingan](output/native_modules/npdm_comparison.json).

**37.517 simbol dinamis** kini diindeks pada empat modul. Dari 910 impor `main`, **898 mempunyai kecocokan ekspor unik**: 880 pada `sdk`, 18 pada `subsdk0`. Dua belas sisanya memakai binding `STB_WEAK`: empat marker `__rel_*` dan delapan `glslc*`. Perilaku saat simbol weak tidak tersedia masih memerlukan pemeriksaan caller. Kecocokan ekspor merupakan resolusi statis; load order, relocation lengkap, TLS, constructor dan syscall OS belum menjadi runtime lengkap. [Peta impor beserta lokasi relocation](output/native_modules/import_resolution.json).

SDK sudah dipakai pada uji nyata. `strcmp` pada VA SDK `0x4d7900` ditautkan ke GOT `main` di `0x32cede0` melalui `R_AARCH64_JUMP_SLOT`; instruksi PLT/main/SDK tetap asli. **67.714 kasus strcmp** cocok, termasuk seluruh pasangan byte dan alignment berbeda. Seluruh **2.546.185 pemeriksaan BYML** dijalankan kembali, menghasilkan **84.560 panggilan strcmp asli dan nol stub**, tanpa mismatch. Pemetaan emulasi hanya membutuhkan text SDK untuk fungsi mandiri tersebut; initializer atau syscall SDK lain belum dieksekusi. [Uji strcmp](output/native_modules/strcmp_native_verification.json), [BYML dengan SDK asli](output/native_modules/linked_byml_verification.json). Cakupan BYML ini sama dengan audit sebelumnya dan tidak dijumlahkan sebagai entry baru.

Enam kolom tanpa nama pada `NmlNpcParam` (397 baris) dan `SpNpcParam` (62 baris) kini mempunyai binding native: hash `21c5bbd6`, `42f255d5`, `e52f0037` ditransfer sebagai u8 ke konfigurasi suara+44/+45/+46, yakni object+0x83c/+0x83d/+0x83e. Fallback masing-masing 5/4/1 bila metadata field tidak ditemukan. Blok asli `0x160aff0` setelah pemilihan NPC membaca metadata BCSV, mencari hash, mengisi cache offset, lalu menulis ketiga byte. **995 pemeriksaan** mencakup 459 baris asli, seluruh nilai byte sintetis, seluruh kombinasi field hilang, dan guard bytes. Tidak ada dependensi yang diganti. Nama asli serta makna akustik seperti pitch/timbre/speed belum disimpulkan. [JSON dan bukti](output/npc/voice_configuration_native.json).

ExeFS tambahan mengatasi kekurangan kode modul SDK/multimedia dari audit awal. Mesh, animasi, audio waveform, VFX, shader dan Havok yang tidak ada pada subset RomFS tetap tidak diperoleh dari modul executable ini. [Kontrak input baru](docs/ADDITIONAL_EXEFS.md), [perubahan dari laporan terakhir](output/progress_additional_exefs.json).

## Kalender SDK, batas hari, dan genetika bunga

Harness sekarang memetakan main, SDK, subsdk0 dan rtld serta menerapkan relocation yang didukung. **355.478 pointer relocation** diperiksa, terpisah dari jumlah uji perilaku. Resolusi undefined dengan satu ekspor strong memakai ekspor itu; definisi lokal tetap relatif ke modulnya. Init module, TLS dan layanan OS tidak disimulasikan. Semua helper yang diterbitkan berjalan tanpa stub dan tanpa mencapai syscall OS.

Kalender SDK diperiksa pada seluruh **146.097 tanggal dalam siklus Gregorian 400 tahun**, ditambah tanggal batas dan sampel tahun 1–9999. **314.757 perbandingan** mencakup konversi kalender/Posix, 16.268 kasus normalisasi hari beserta guard, serta 4.151 kasus offset hari s32. Fungsi game `0x1fbc00` mengurangi satu tanggal bila jam <05, lalu menulis 05:00:00. Tepat 05:00 tetap memakai tanggal yang sama. Perkalian nanodetik s64 pada helper offset tetap mempertahankan overflow aslinya. Ini aritmetika kalender UTC; pembacaan jam host atau inisialisasi timezone OS belum dibuktikan. [Kalender](output/calendar/native_verification.json).

Uji cuaca lengkap kini mencakup **27.512 prediksi** pada 00:00:00, 04:59:59, 05:00:00 dan 23:59:59, dengan tanggal efektif, pola dan state akhir RNG yang cocok. Fungsi asli berjalan melalui GOT/PLT ke SDK asli. Flag override tetap 0; event khusus belum tercakup. [Cuaca lintas modul](output/weather/native_linked_verification.json).

Pewarisan bunga `0x4cd070` teruji pada **seluruh 65.536 pasangan byte gen induk** dan 1.024 pasangan u32 tambahan. Empat lokus memakai dua bit per lokus; 01 dan 10 sama-sama dosage 1. Induk heterozigot saja yang mengambil RNG; urutan lokus A→D, masing-masing induk A lalu B. Hasil kanonis memakai kode 0/1/3. Gen anak, state akhir RNG dan guard cocok.

Seluruh **270 baris genotipe dari delapan jenis bunga** kini terhubung ke resource FgMainParam dan stage pertumbuhan. Rose mempunyai 81 kombinasi, tujuh jenis lain masing-masing 27. Lookup genotipe/growth `0x4cc4d0` diuji pada seluruh byte gen dan enam input stage, memakai raw BCSV serta cache/array yang direkonstruksi dari data asli dan literal enum native. Constructor/file loader tidak dijalankan dalam harness ini. **247.172 pemeriksaan bunga** mencakup lookup resource, RNG, default gen dan kasus batas. [Genotipe JSON](output/flowers/genotypes.json), [hasil native](output/flowers/native_verification.json).

`DefaultHeredity` kini terverifikasi pada **180 resource**: normalisasi ke bud Grow=2, berhenti pada baris matching yang DefaultHeredity-nya aktif, atau memakai **baris matching terakhir** bila tidak ada penanda. Field hash `753336dd` dipakai sebagai awal lookup alternatif bila terisi; seluruh nilai alternatif dalam sumber mengarah ke Grow=0. Nama aslinya tetap belum diketahui. [Gen default](output/flowers/default_genes.json).

Caller `0x4d5e50` juga diuji pada **11.664 pasangan induk dalam jenis yang sama**, sampai menghasilkan item delapan byte: ID bud, gen pada byte terendah FreeParam (item+4), state RNG dan guard cocok. Pointer hasil object C++ memakai register X8 tersembunyi; argumen eksplisit X0/X1 adalah object Fg dan item induk lain. Signature otomatis yang menampilkan hasil sebagai argumen biasa tidak dianggap ABI otoritatif. [Item anakan](output/flowers/offspring_items.json).

Ada kasus data Black Cosmos yang perlu dipertahankan: ID 60151→60153→60155→60151 mempunyai Grow 2→3→0, sehingga permintaan Grow=1 tidak tercapai. Pada **24 input sintetis**, kode asli mengulang dua putaran yang sama dan belum kembali dalam batas 20.000 instruksi. Kasus ini dicatat sebagai eksekusi berbatas, bukan dipaksa sukses atau diganti sentinel. Caller item anakan yang diuji selalu meminta Grow=2 dan tidak memicu kasus itu. Belum dibuktikan bahwa workflow game lain mengirim permintaan Grow=1 tersebut; ini belum dinyatakan sebagai bug gameplay. [Siklus dan trace](output/flowers/growth_cycles.json).

Model probabilitas Mendelian mencakup 6.561 pasangan genotipe kanonis dengan bobot rasional per 256. Model mengasumsikan pemilihan alel adil dan independen. Pemilihan pasangan tanaman, posisi spawn, kelayakan breeding, bonus penyiraman/pengunjung, serta aturan golden rose tetap pekerjaan lanjutan. [Probabilitas](output/flowers/inheritance_probabilities.json), [kontrak dan batas](docs/CALENDAR_FLOWERS.md), [perbandingan tahap terakhir](output/progress_calendar_flowers.json).

## Yang belum terpetakan secara semantik

1. **91 kemunculan kolom BCSV** belum memiliki nama asli yang terverifikasi; sebagian kini mempunyai tipe baca atau peran fungsional yang teruji. Setiap kolom tetap mempunyai hash, offset, tipe, contoh nilai, dan kandidat fungsi pembaca: [daftar bukti](output/schemas/unresolved_evidence.json).
2. BYML primer masih memiliki 431 key hash/ID tanpa descriptor unik yang dipilih, mencakup 2.407 kemunculan. [Daftar tersisa](output/schemas/byml_names_unresolved.json). Indeks kandidat lama lintas format tetap disimpan di `hash_names_expanded.json`; hitungannya bukan cakupan pemulihan BYML terbaru. Banyak key merupakan ID dinamis; pemulihan nama tidak otomatis menentukan perilaku.
3. Perilaku lengkap seluruh handler, penjadwalan event, AI, ekonomi, pertumbuhan, fisika, save, dan sinkronisasi belum mempunyai spesifikasi dan uji menyeluruh. Pemetaan fungsi menyediakan jalur penelusuran, bukan pengganti pekerjaan tersebut.
4. Geometry model, animasi skeletal, audio gelombang dan Havok yang tidak ikut sumber tetap tidak dapat dipulihkan dari katalog saja. Tambahan RomFS menyediakan state machine ASB, UI/font, sebagian shader dan dua VFXB/PTCL serta database XLNK, tetapi pemahaman runtime format-format tersebut masih parsial. Dua tekstur lingkungan dari paket awal sudah dipulihkan; tekstur UI tambahan baru diinventarisasi metadatanya.
5. Uji native memakai emulasi helper terisolasi, bukan menjalankan game lengkap. Integrasi runtime dan konversi Godot tidak dikerjakan sesuai batas tugas.

Karena bagian ini masih ada, laporan **tidak menyatakan seluruh ACNH selesai direkayasa balik**. Syarat pengguna “semuanya terpetakan” pada tingkat perilaku belum terpenuhi; `output/coverage.json` menandainya eksplisit dengan `full_user_goal_completed=false`.

## Validasi dan penggunaan hasil

Pemeriksaan helper/blok native berjumlah **780.339 kasus/perbandingan**, mencakup terrain, C1, kurva, ExitFlowchart, item/CRC, Stage, byte BCSV, flag, RNG, dan cuaca. Rincian dihitung di `output/coverage.json`. **2.546.185 pemeriksaan pembaca BYML dicatat terpisah** agar volume validasi struktur tidak disamakan dengan cakupan perilaku game. Hasil, checksum ELF, serta batas stub/toleransi disimpan bersama output. Untile tekstur memeriksa 353.623 blok dan kesetaraan retile pada blok yang digunakan.

Pemeriksaan integrasi membandingkan setiap sel terrain dengan raw, descriptor dan label enum dengan CRC, batas slot native, header/payload DDS, seluruh blob manifest, integritas SQLite, serta CRC seluruh berkas arsip asal. Log terakhir: [verification.log](output/verification.log).

Mulai konversi berikutnya dari [manifest](output/manifest.json), [katalog tabel resolved](output/schemas/catalogue.json), [BYML bernama](output/byml_resolved/catalogue.json), [item](output/items/catalogue.json), [katalog aset JSON](output/assets/catalogue.json), dan [kontrak data](docs/DATA_CONTRACT.md). Gunakan `tables_resolved/` untuk nama dan tipe terbaru; `decoded/` tetap menjadi pembacaan struktur yang dekat ke sumber. Metadata model lapangan yang tersedia tidak mencakup resource furnitur/tree yang disebut tabel item; nama resource dipertahankan sebagai referensi, tanpa menganggap mesh sudah tersedia. Jangan memakai kandidat atau pseudocode otomatis sebagai aturan gameplay terkonfirmasi.

```bash
python /workspace/acnh-re/tools/build_all.py /workspace/downloads/ACNH_island_RE/ACNH_island_RE
python -m unittest discover -s /workspace/acnh-re/tests -v
```

Pembacaan format memakai Python 3.11+. Pemeriksaan/disassembly native memerlukan dependensi pada `requirements-native.txt` yang sudah terpasang di `.deps`. Ekspor pseudocode merupakan tahap Ghidra tersendiri dengan JDK 21; script ada pada `ghidra_scripts/`. Pipeline data tidak membuka editor Godot dan tidak memerlukan kunci konsol. Rujukan eksternal beserta lisensi ada pada [NOTICE](tools/external/NOTICE.md).

## Lampiran: seluruh tabel BCSV menurut domain

Pengelompokan domain mengikuti nama tabel dan ditandai sebagai klasifikasi. Semua 164 tabel tetap dirujuk ke JSON dengan hash/offset sumber; kategori ini bukan pembuktian perilaku native.

### audio

| Tabel | Baris | Kolom bernama/total |
|---|---:|---:|
| [BgmPropertyControlParam](output/tables_resolved/BgmPropertyControlParam.json) | 79 | 4/4 |
| [BgmPropertyParam](output/tables_resolved/BgmPropertyParam.json) | 22 | 2/2 |
| [DuckingParam](output/tables_resolved/DuckingParam.json) | 21 | 2/2 |
| [RadioCM](output/tables_resolved/RadioCM.json) | 10 | 7/7 |
| [RadioJingle](output/tables_resolved/RadioJingle.json) | 18 | 7/7 |
| [SoundAttributeForGround](output/tables_resolved/SoundAttributeForGround.json) | 18 | 2/2 |
| [SoundAttributeForPlacement](output/tables_resolved/SoundAttributeForPlacement.json) | 12 | 2/2 |
| [SoundAudioMusic](output/tables_resolved/SoundAudioMusic.json) | 98 | 5/5 |
| [SoundInstruments](output/tables_resolved/SoundInstruments.json) | 23 | 5/5 |
| [SoundMaterialType](output/tables_resolved/SoundMaterialType.json) | 3 | 3/3 |
| [TVProgram](output/tables_resolved/TVProgram.json) | 23 | 56/57 |
| [TVProgramFriday](output/tables_resolved/TVProgramFriday.json) | 77 | 3/3 |
| [TVProgramMonday](output/tables_resolved/TVProgramMonday.json) | 80 | 3/3 |
| [TVProgramSaturday](output/tables_resolved/TVProgramSaturday.json) | 66 | 3/3 |
| [TVProgramSunday](output/tables_resolved/TVProgramSunday.json) | 69 | 3/3 |
| [TVProgramThursday](output/tables_resolved/TVProgramThursday.json) | 79 | 3/3 |
| [TVProgramTuesday](output/tables_resolved/TVProgramTuesday.json) | 75 | 3/3 |
| [TVProgramWednesday](output/tables_resolved/TVProgramWednesday.json) | 79 | 3/3 |

### calendar_and_seasons

| Tabel | Baris | Kolom bernama/total |
|---|---:|---:|
| [CalendarEventParam](output/tables_resolved/CalendarEventParam.json) | 17 | 157/157 |
| [ReleaseVersionParam](output/tables_resolved/ReleaseVersionParam.json) | 3 | 4/4 |
| [SeasonCalendar](output/tables_resolved/SeasonCalendar.json) | 53 | 20/20 |

### event_flags

| Tabel | Baris | Kolom bernama/total |
|---|---:|---:|
| [EventFlagsHouseParam](output/tables_resolved/EventFlagsHouseParam.json) | 10 | 6/7 |
| [EventFlagsLandParam](output/tables_resolved/EventFlagsLandParam.json) | 244 | 8/9 |
| [EventFlagsLandTempParam](output/tables_resolved/EventFlagsLandTempParam.json) | 51 | 7/9 |
| [EventFlagsLifeSupportAchievementParam](output/tables_resolved/EventFlagsLifeSupportAchievementParam.json) | 81 | 20/20 |
| [EventFlagsLifeSupportDailyParam](output/tables_resolved/EventFlagsLifeSupportDailyParam.json) | 188 | 16/17 |
| [EventFlagsNpcMemoryParam](output/tables_resolved/EventFlagsNpcMemoryParam.json) | 116 | 6/9 |
| [EventFlagsNpcSaveParam](output/tables_resolved/EventFlagsNpcSaveParam.json) | 34 | 6/7 |
| [EventFlagsNpcTempParam](output/tables_resolved/EventFlagsNpcTempParam.json) | 47 | 6/8 |
| [EventFlagsPlayerActivityParam](output/tables_resolved/EventFlagsPlayerActivityParam.json) | 60 | 8/8 |
| [EventFlagsPlayerParam](output/tables_resolved/EventFlagsPlayerParam.json) | 673 | 7/9 |
| [EventFlagsPlayerTempParam](output/tables_resolved/EventFlagsPlayerTempParam.json) | 69 | 6/7 |
| [EventFlagsPlayerVisitParam](output/tables_resolved/EventFlagsPlayerVisitParam.json) | 42 | 6/6 |

### fish

| Tabel | Baris | Kolom bernama/total |
|---|---:|---:|
| [FishAppearRiverParam](output/tables_resolved/FishAppearRiverParam.json) | 100 | 38/38 |
| [FishAppearSeaParam](output/tables_resolved/FishAppearSeaParam.json) | 76 | 38/38 |
| [FishBeyQuestParam](output/tables_resolved/FishBeyQuestParam.json) | 24 | 4/4 |
| [FishStatusParam](output/tables_resolved/FishStatusParam.json) | 84 | 17/19 |

### insects

| Tabel | Baris | Kolom bernama/total |
|---|---:|---:|
| [InsectAppearParam](output/tables_resolved/InsectAppearParam.json) | 166 | 75/75 |
| [InsectBattleParam](output/tables_resolved/InsectBattleParam.json) | 4 | 3/3 |
| [InsectStatusParam](output/tables_resolved/InsectStatusParam.json) | 85 | 16/16 |

### interiors_and_museum

| Tabel | Baris | Kolom bernama/total |
|---|---:|---:|
| [IndoorIdrParam](output/tables_resolved/IndoorIdrParam.json) | 20 | 4/4 |
| [IndoorPhotoStudioItemParam](output/tables_resolved/IndoorPhotoStudioItemParam.json) | 20 | 8/8 |
| [MuseumFossilDonateInfo](output/tables_resolved/MuseumFossilDonateInfo.json) | 73 | 5/5 |
| [MuseumNPCLayoutInfo](output/tables_resolved/MuseumNPCLayoutInfo.json) | 83 | 7/7 |
| [MuseumNPCSilhouette](output/tables_resolved/MuseumNPCSilhouette.json) | 17 | 6/6 |
| [MuseumNPCSpotTalk](output/tables_resolved/MuseumNPCSpotTalk.json) | 9 | 5/5 |
| [MuseumNameboardInfo](output/tables_resolved/MuseumNameboardInfo.json) | 67 | 12/12 |
| [MuseumWatchPoint](output/tables_resolved/MuseumWatchPoint.json) | 86 | 13/14 |
| [RoomArchParam](output/tables_resolved/RoomArchParam.json) | 9 | 2/2 |
| [RoomCeilingParam](output/tables_resolved/RoomCeilingParam.json) | 6 | 2/2 |
| [RoomCurtainParam](output/tables_resolved/RoomCurtainParam.json) | 4 | 3/3 |
| [RoomCurtainTexParam](output/tables_resolved/RoomCurtainTexParam.json) | 18 | 3/3 |
| [RoomFloorParam](output/tables_resolved/RoomFloorParam.json) | 173 | 14/14 |
| [RoomLandingParam](output/tables_resolved/RoomLandingParam.json) | 2 | 4/4 |
| [RoomWallParam](output/tables_resolved/RoomWallParam.json) | 243 | 15/15 |
| [RoomWindowParam](output/tables_resolved/RoomWindowParam.json) | 24 | 5/5 |

### items_and_crafting

| Tabel | Baris | Kolom bernama/total |
|---|---:|---:|
| [ItemAct](output/tables_resolved/ItemAct.json) | 55 | 6/6 |
| [ItemClothGroup](output/tables_resolved/ItemClothGroup.json) | 1.106 | 17/18 |
| [ItemColor](output/tables_resolved/ItemColor.json) | 15 | 3/3 |
| [ItemFilter](output/tables_resolved/ItemFilter.json) | 7 | 19/19 |
| [ItemFrom](output/tables_resolved/ItemFrom.json) | 119 | 4/4 |
| [ItemKind](output/tables_resolved/ItemKind.json) | 120 | 28/28 |
| [ItemMailAttachCategoryGroup](output/tables_resolved/ItemMailAttachCategoryGroup.json) | 3 | 3/4 |
| [ItemMenuIcon](output/tables_resolved/ItemMenuIcon.json) | 470 | 4/4 |
| [ItemNpcFtrActionParam](output/tables_resolved/ItemNpcFtrActionParam.json) | 17 | 7/7 |
| [ItemNpcOutfitInfo](output/tables_resolved/ItemNpcOutfitInfo.json) | 20 | 4/5 |
| [ItemNpcRoomReplaceCategory](output/tables_resolved/ItemNpcRoomReplaceCategory.json) | 21 | 10/10 |
| [ItemNpcTopsForm](output/tables_resolved/ItemNpcTopsForm.json) | 35 | 31/31 |
| [ItemOutfitCategory](output/tables_resolved/ItemOutfitCategory.json) | 65 | 12/12 |
| [ItemOutfitInfo](output/tables_resolved/ItemOutfitInfo.json) | 108 | 16/16 |
| [ItemParam](output/tables_resolved/ItemParam.json) | 8.208 | 88/94 |
| [ItemPlayerInitialOutfitBoyAWParam](output/tables_resolved/ItemPlayerInitialOutfitBoyAWParam.json) | 8 | 9/9 |
| [ItemPlayerInitialOutfitBoySSParam](output/tables_resolved/ItemPlayerInitialOutfitBoySSParam.json) | 8 | 9/9 |
| [ItemPlayerInitialOutfitGirlAWParam](output/tables_resolved/ItemPlayerInitialOutfitGirlAWParam.json) | 8 | 9/9 |
| [ItemPlayerInitialOutfitGirlSSParam](output/tables_resolved/ItemPlayerInitialOutfitGirlSSParam.json) | 8 | 9/9 |
| [ItemPlayerTopsForm](output/tables_resolved/ItemPlayerTopsForm.json) | 75 | 11/11 |
| [ItemRemake](output/tables_resolved/ItemRemake.json) | 654 | 55/56 |
| [ItemRemakeCommonPattern](output/tables_resolved/ItemRemakeCommonPattern.json) | 200 | 7/7 |
| [ItemRemakeCommonPatternCategory](output/tables_resolved/ItemRemakeCommonPatternCategory.json) | 11 | 3/3 |
| [ItemSeasonalityParam](output/tables_resolved/ItemSeasonalityParam.json) | 5 | 9/9 |
| [ItemShareTexture](output/tables_resolved/ItemShareTexture.json) | 2 | 2/2 |
| [ItemSize](output/tables_resolved/ItemSize.json) | 25 | 8/8 |
| [ItemStrSort](output/tables_resolved/ItemStrSort.json) | 8.208 | 15/15 |
| [ItemUIContextMenu](output/tables_resolved/ItemUIContextMenu.json) | 54 | 6/6 |
| [ItemUnitIcon](output/tables_resolved/ItemUnitIcon.json) | 159 | 8/8 |
| [MannequinCoodinate](output/tables_resolved/MannequinCoodinate.json) | 116 | 10/10 |
| [MaterialType](output/tables_resolved/MaterialType.json) | 6 | 3/3 |
| [RecipeCraftParam](output/tables_resolved/RecipeCraftParam.json) | 552 | 19/19 |

### messages_and_localization

| Tabel | Baris | Kolom bernama/total |
|---|---:|---:|
| [LocalizeNameConvertParam](output/tables_resolved/LocalizeNameConvertParam.json) | 19 | 19/19 |
| [MessageCardBoardDesignParam](output/tables_resolved/MessageCardBoardDesignParam.json) | 6 | 12/13 |
| [MessageCardColorParam](output/tables_resolved/MessageCardColorParam.json) | 278 | 2/2 |
| [MessageCardDesignParam](output/tables_resolved/MessageCardDesignParam.json) | 66 | 19/21 |
| [MessageCardSelectDesign](output/tables_resolved/MessageCardSelectDesign.json) | 170 | 12/13 |
| [MessageCardSelectDesignSp](output/tables_resolved/MessageCardSelectDesignSp.json) | 48 | 12/13 |
| [MessageCardSelectPresent](output/tables_resolved/MessageCardSelectPresent.json) | 84 | 3/5 |
| [MessageCardSelectPresentSp](output/tables_resolved/MessageCardSelectPresentSp.json) | 19 | 3/5 |

### npc

| Tabel | Baris | Kolom bernama/total |
|---|---:|---:|
| [AITag](output/tables_resolved/AITag.json) | 31 | 4/4 |
| [AmiiboData](output/tables_resolved/AmiiboData.json) | 473 | 9/9 |
| [NmlNpcParam](output/tables_resolved/NmlNpcParam.json) | 397 | 31/39 |
| [NmlNpcRaceParam](output/tables_resolved/NmlNpcRaceParam.json) | 35 | 15/15 |
| [NpcCastLabelData](output/tables_resolved/NpcCastLabelData.json) | 29 | 4/4 |
| [NpcCastScheduleData](output/tables_resolved/NpcCastScheduleData.json) | 29 | 10/11 |
| [NpcEquipRule](output/tables_resolved/NpcEquipRule.json) | 19 | 20/20 |
| [NpcInterest](output/tables_resolved/NpcInterest.json) | 18 | 27/27 |
| [NpcLife](output/tables_resolved/NpcLife.json) | 47 | 40/40 |
| [NpcLooksParam](output/tables_resolved/NpcLooksParam.json) | 8 | 35/35 |
| [NpcMoveRoomTemplate](output/tables_resolved/NpcMoveRoomTemplate.json) | 28 | 6/6 |
| [NpcMsgBullfestParam](output/tables_resolved/NpcMsgBullfestParam.json) | 21 | 24/24 |
| [NpcRoomTemplate](output/tables_resolved/NpcRoomTemplate.json) | 342 | 6/6 |
| [NpcSpClothSetParam](output/tables_resolved/NpcSpClothSetParam.json) | 17 | 10/10 |
| [NpcSpModelScale](output/tables_resolved/NpcSpModelScale.json) | 4 | 19/19 |
| [NpcSpServiceMotionRandom](output/tables_resolved/NpcSpServiceMotionRandom.json) | 53 | 8/8 |
| [NpcSpServiceMotionWork](output/tables_resolved/NpcSpServiceMotionWork.json) | 8 | 18/18 |
| [NpcSpServiceMotionWorkSp](output/tables_resolved/NpcSpServiceMotionWorkSp.json) | 3 | 5/5 |
| [SpNpcParam](output/tables_resolved/SpNpcParam.json) | 62 | 19/22 |
| [VMMultistepNPC](output/tables_resolved/VMMultistepNPC.json) | 3 | 2/2 |

### other

| Tabel | Baris | Kolom bernama/total |
|---|---:|---:|
| [EventPlazaFtrParam](output/tables_resolved/EventPlazaFtrParam.json) | 21 | 4/4 |
| [EventPlazaGround](output/tables_resolved/EventPlazaGround.json) | 2 | 2/2 |
| [EventPlazaObjModelParam](output/tables_resolved/EventPlazaObjModelParam.json) | 12 | 5/6 |
| [EventPlazaPlacementParam](output/tables_resolved/EventPlazaPlacementParam.json) | 64 | 13/15 |
| [GmoFootprintParam](output/tables_resolved/GmoFootprintParam.json) | 14 | 4/4 |
| [ShopItemRouteFlags](output/tables_resolved/ShopItemRouteFlags.json) | 18 | 5/5 |

### player

| Tabel | Baris | Kolom bernama/total |
|---|---:|---:|
| [CharaMakeCheekTypeParam](output/tables_resolved/CharaMakeCheekTypeParam.json) | 3 | 4/4 |
| [CharaMakeEyeColorParam](output/tables_resolved/CharaMakeEyeColorParam.json) | 6 | 6/6 |
| [CharaMakeEyeTypeParam](output/tables_resolved/CharaMakeEyeTypeParam.json) | 52 | 5/5 |
| [CharaMakeHairColorParam](output/tables_resolved/CharaMakeHairColorParam.json) | 16 | 9/9 |
| [CharaMakeHairStyleParam](output/tables_resolved/CharaMakeHairStyleParam.json) | 31 | 43/43 |
| [CharaMakeMouthTypeParam](output/tables_resolved/CharaMakeMouthTypeParam.json) | 4 | 4/4 |
| [CharaMakeNoseTypeParam](output/tables_resolved/CharaMakeNoseTypeParam.json) | 3 | 4/4 |
| [CharaMakeSkinColorParam](output/tables_resolved/CharaMakeSkinColorParam.json) | 8 | 15/15 |
| [HumanAnimParam](output/tables_resolved/HumanAnimParam.json) | 455 | 10/12 |
| [PlayerStateParam](output/tables_resolved/PlayerStateParam.json) | 235 | 24/36 |

### world_and_terrain

| Tabel | Baris | Kolom bernama/total |
|---|---:|---:|
| [ColEffectAttributeParam](output/tables_resolved/ColEffectAttributeParam.json) | 20 | 2/2 |
| [ColGroundAttributeParam](output/tables_resolved/ColGroundAttributeParam.json) | 63 | 11/14 |
| [ColSoundAttributeParam](output/tables_resolved/ColSoundAttributeParam.json) | 22 | 2/2 |
| [FgFlowerHeredity](output/tables_resolved/FgFlowerHeredity.json) | 270 | 7/8 |
| [FgMainParam](output/tables_resolved/FgMainParam.json) | 328 | 23/23 |
| [FieldCreateParam](output/tables_resolved/FieldCreateParam.json) | 89 | 6/6 |
| [FieldDistantViewParam](output/tables_resolved/FieldDistantViewParam.json) | 3 | 2/2 |
| [FieldLandMakingActionParam](output/tables_resolved/FieldLandMakingActionParam.json) | 17 | 10/12 |
| [FieldLandMakingError](output/tables_resolved/FieldLandMakingError.json) | 12 | 6/7 |
| [FieldLandMakingRoadKindParam](output/tables_resolved/FieldLandMakingRoadKindParam.json) | 9 | 3/3 |
| [FieldLandMakingUnitModelParam](output/tables_resolved/FieldLandMakingUnitModelParam.json) | 246 | 42/42 |
| [FieldMainFieldParam](output/tables_resolved/FieldMainFieldParam.json) | 96 | 6/6 |
| [FieldMysteryTourFieldParam](output/tables_resolved/FieldMysteryTourFieldParam.json) | 3 | 2/2 |
| [FieldMysteryTourItemParam](output/tables_resolved/FieldMysteryTourItemParam.json) | 3 | 1/1 |
| [FieldMysteryTourParam](output/tables_resolved/FieldMysteryTourParam.json) | 3 | 7/7 |
| [FieldOutsideParts](output/tables_resolved/FieldOutsideParts.json) | 136 | 4/4 |
| [FieldOutsideTemplate](output/tables_resolved/FieldOutsideTemplate.json) | 36 | 27/27 |
| [MysteryTourFieldParam](output/tables_resolved/MysteryTourFieldParam.json) | 23 | 2/2 |
| [MysteryTourFishParam](output/tables_resolved/MysteryTourFishParam.json) | 3 | 2/2 |
| [MysteryTourInsectParam](output/tables_resolved/MysteryTourInsectParam.json) | 11 | 2/2 |
| [MysteryTourItemParam](output/tables_resolved/MysteryTourItemParam.json) | 23 | 1/1 |
| [MysteryTourParam](output/tables_resolved/MysteryTourParam.json) | 20 | 13/13 |
| [StructureBridgeParam](output/tables_resolved/StructureBridgeParam.json) | 54 | 4/4 |
| [StructureBridgeTypeParam](output/tables_resolved/StructureBridgeTypeParam.json) | 9 | 4/5 |
| [StructureDoorParam](output/tables_resolved/StructureDoorParam.json) | 35 | 15/28 |
| [StructureFacilityModel](output/tables_resolved/StructureFacilityModel.json) | 19 | 16/18 |
| [StructureHouseDoorParam](output/tables_resolved/StructureHouseDoorParam.json) | 253 | 11/11 |
| [StructureHouseRoofParam](output/tables_resolved/StructureHouseRoofParam.json) | 166 | 7/7 |
| [StructureHouseShapeParam](output/tables_resolved/StructureHouseShapeParam.json) | 15 | 8/8 |
| [StructureHouseWallParam](output/tables_resolved/StructureHouseWallParam.json) | 149 | 8/9 |
| [StructureInfoParam](output/tables_resolved/StructureInfoParam.json) | 29 | 6/7 |
| [StructureSlopeParam](output/tables_resolved/StructureSlopeParam.json) | 9 | 4/4 |

