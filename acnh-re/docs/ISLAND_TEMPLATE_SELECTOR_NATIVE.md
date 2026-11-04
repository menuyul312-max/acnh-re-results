# Pemilihan template pulau: bukti native dan status poin 1–4

Tanggal: 4 November 2026 (Asia/Jakarta). Build mengikuti SHA256 ELF pada JSON hasil, bukan perkiraan versi dari nama berkas.

## Hasil baru

Fungsi selector **ELF 0x552bb0** berhasil dijalankan hingga return menggunakan instruksi asli, helper asli, dan RNG asli, tanpa mengganti instruksi atau dependensi dengan stub. **528 kasus lulus** terhadap perhitungan pembanding independen. Ini adalah bukti selector dalam context rekonstruksi, bukan eksekusi world game lengkap.

Input yang dipakai selector mencakup kategori u32 di W1 dan pointer state RNG di X2. Jalur asli membaca registry tabel dari singleton dan cache kategori u16 berdasarkan indeks baris. Fixture menyediakan registry/cache itu, serta BCSV FieldOutsideTemplate dari sumber pengguna. Tujuh skenario mempertahankan ID asli; empat skenario tambahan mengganti ID untuk menguji empat word bitset, penolakan ID >=128, dan ID duplikat. Semua keadaan rekonstruksi dicatat di tool.

Aturan yang teruji:

1. Kategori cache lebih besar dari 2 diperlakukan sebagai 0.
2. Baris yang kategorinya sama dengan input menyumbangkan UniqueID ke bitset 128-bit. ID di atas 127 tidak disertakan. ID duplikat dihitung satu kali.
3. Untuk N bit aktif, selector mengambil satu draw u32, lalu memilih peringkat `floor(draw * N / 2^32)` dalam daftar ID aktif yang diurutkan naik.
4. Kandidat kosong mengembalikan 0 tanpa mengubah RNG. Kandidat tidak kosong mengonsumsi tepat satu draw. Nilai 0 sendiri bukan penanda kegagalan yang unik karena ID 0 juga bisa valid.

Literal pada ELF **0x2933de2** adalah `3B_S2,3B_SE,3B_SW,`. Initializer `0x50ea00` dan converter hash `0x50dff0` mendukung urutan indeks 0, 1, 2 secara statis. CRC32 nama Inggris cocok dengan hash TemplateKind asli pada tabel. Dengan demikian hubungan 0→3B_S2, 1→3B_SE, 2→3B_SW memiliki bukti kode/literal, lebih kuat daripada pola awalan nama sebelumnya. Initializer cache asli belum dijalankan; cache pada emulasi tetap direkonstruksi.

Koreksi alamat: nama Ghidra `FUN_00652bb0` berarti ELF **0x552bb0**, bukan 0x652bb0. Catatan kandidat sebelumnya sudah diperbaiki. Semua alamat di laporan ini adalah ELF VA.

## Status poin 1–4

| Poin | Bukti saat ini | Celah yang tetap terbuka |
|---|---|---|
| 1. Loader terrain | Jalur native 0x528bf0→0x558f40 memetakan transfer sel 14-byte dan semua 96 preset 112×96. PBC tersedia untuk 13/13 unit terrain terpakai; footprint 2×2 sel ×5 unit cocok dengan satu sel LandMaking 10-unit. Penulis tinggi native 0x180d20 juga memproses awalan 12-float dari 208 rekaman PBC terurai dan menghasilkan flag sesuai profil lokal. | Join waktu-muat dari record preset 14-byte ke PBC/runtime 52-byte belum dieksekusi bersama. Uji seam tidak mendukung satu offset elevasi seragam; transform vertikal, alokasi/chunk, dan perubahan terrain live masih terbuka. Model Cliff8 tidak ada PBC, tetapi ID itu tak dipakai preset; ada satu PBC jalan tambahan di luar tabel. |
| 2. Pemilihan template luar | Selector 0x552bb0 teruji 528 kasus. Urutan enum memiliki dukungan literal/initializer. Fungsi generator 0x529910 secara statis memanggil pembaca kategori 0x54e330 dan selector empat kali, lalu mengirim hasil ke setup 0x528bf0. Semua 96 preset kini dipetakan ke pool 12 template sesuai enum kategori. | Bootstrap cache dan generator belum dijalankan native end-to-end; UID yang akhirnya terpilih bergantung pada RNG/runtime. |
| 3. Perakitan part | Rangkaian asli `0x4de810→0x4dea40→0x4deeb0→0x4dfcb0→0x4e0c90` dijalankan pada 36 template. Semua 792 ID slot pantai cocok dengan pool sumber; 1.036 ID perimeter cocok sebagai OutsideSea; 2.592 record cocok tanpa mismatch. Ada 44 perimeter kosong yang ditelusuri ke target `S_concavity` tanpa kandidat OutsideSea. PBC tersedia untuk semua 136 nama bagian. | BCSV loader/cache bootstrap dan waktu tick gameplay asli belum dijalankan. Parent/world transform, rotasi per bagian, keberhasilan render/load, weld seam dan respons collision saat runtime masih belum terbukti. |
| 4. Sungai/air | Kelima tabel sumber yang dipakai cocok nilai-per-nilai dengan korpus lokal; semua 1.032.192 sel di 96 preset juga cocok. Seluruh 96 preset menempatkan mask River terdekat di segmen slot yang diharapkan. PBC River/Fall, pantai dan 50 varian RoomFloor memberi material/tinggi aktual; 4.088.832 sisi segitiga WaterCheck dapat dibandingkan. | Kandidat rotasi CCW memberi hasil terbaik tetapi menyisakan 1,271952% mismatch. Origin/transform fisik darat-pantai, seam runtime, water surface/flow/efek, serta semantik tinggi tetap belum terbukti. PBC memetakan atribut ground statis, bukan simulasi air. |

## PBC yang baru tersedia di arsip manifest

Arsip lanjutan yang diberikan pengguna memiliki SHA256
`8995d65b09a5cb84b181907c78991806f6da325bc82d35ea24ae6ecf1e263f3a` dan lulus
CRC ZIP. Ia memuat 783 PBC JSON terurai; manifest collision mencatat 783 PBC
berhasil dan tidak ada kegagalan. Nilai kelima tabel lokal cocok seluruhnya:
246 unit terrain, 136 part pantai, 36 template, 63 material ground, dan 173
RoomFloorParam. Semua 1.032.192 sel grid 112×96 cocok tepat pada tujuh field.

Konsistensi skala memberi batas yang lebih rapat: setiap PBC unit terrain adalah
2×2 ×5 unit, sementara satu sel LandMaking berukuran 10 unit dari spacing pantai
160 unit per segmen 16 sel. Grid ground 5-unit 224×192 menjadi ukuran kandidat
bersyarat jika loader memperluas satu PBC ke tiap sel LandMaking. Uji tinggi
statis pada orientasi CCW menunjukkan 107.364 endpoint cocok tanpa offset,
62.936 cocok pada offset uji 15 unit per tingkat, dan 428 cocok pada keduanya;
karena itu offset vertikal tunggal belum terbukti. Rincian tersimpan di
`pbc_water_seam_comparisons.*.elevation_offset_diagnostic` pada audit manifest.

Kecocokan aset pentingnya:

- 13/13 UniqueID unit terrain yang dipakai seluruh 96 preset memiliki PBC
  2×2 dengan cell size 5.0. River menggunakan material WaterCheck index 1;
  tiga Fall yang dipakai menyimpan tinggi lokal -27 sampai -12. Ini membuktikan
  geometri drop statis ada di payload, bukan aliran waterfall aktif.
- 136/136 model `FieldOutsideParts` memiliki PBC 32×32 dengan cell size 5.0.
  Coast River memperlihatkan material Brackish index 12 dan Sea index 5;
  `FieldLandMaking` River/Fall memakai index 1. Index itu dicrosswalk ke baris
  `ColGroundAttributeParam`, bukan disamakan dengan `UniqueID` tabel.
- Seluruh 14 lantai `HasJmp` memiliki semua 50 file PBC varian yang diizinkan
  oleh `Rotatable`. Setelah payload JSON diserialisasi kembali ke record PBC
  header 20-byte + record 52-byte, reader ground asli dijalankan dalam 2.278
  kasus dan cocok tanpa mismatch, termasuk 252 query consumer ground. Pemetaan
  file/fs dan resource async tetap direkonstruksi.
- Untuk susunan River, mask `InnerType0` CCW cocok ke segmen slot laut di 96/96
  preset: 30 `3B_S2`, 33 `3B_SW`, dan 33 `3B_SE`. Pada perbandingan sisi PBC,
  CCW memberi 52.008 mismatch dari 4.088.832 (1,271952%), lebih rendah dari
  no-rotation 2,458110% dan clockwise 2,458208%. Sekitar 95,4% residu CCW
  berasal dari batas pasangan River5B↔Base. Ini konsistensi aset/data, bukan
  konfirmasi transform renderer.

Laporan lengkap dengan daftar varian, material, rentang tinggi, bbox air pantai,
dan statistik tiap preset ada di
[`manifests_pbc_audit.json`](../output/ui_island/manifests_pbc_audit.json).
File mentah tidak disalin ke repo; skrip audit hanya membaca ZIP dan menulis
metadata turunan.

Poin 1–4 sudah jauh lebih terpetakan, tetapi belum setara dengan build gameplay lengkap. Payload arsip mengonfirmasi struktur record PBC dan atribut/material di data build ini; hubungan loader 14-byte ke runtime, transform parent, origin vertikal, dan seam fisik masih belum dijalankan end-to-end. Generator template/RNG penuh juga belum direproduksi. Model dan sound tetap sebatas katalog sesuai arahan pengguna.

## Artefak dan reproduksi

- `output/ui_island/island_template_selector_native.json`: fixture, hasil, batas bukti dan checksum instruksi.
- `output/ui_island/island_template_selector.asm`: disassembly 992 byte selector lengkap.
- `output/ui_island/island_native_call_candidates.json`: relasi pemanggil statis, dengan koreksi alamat.
- `output/ui_island/preset_template_candidate_pools.json`: join seluruh preset ke 12 template kandidat dari `OutsideTemplateKind` dan `TemplateKind`.
- `output/ui_island/island_terrain_loader_native.json`, `island_terrain_loader.asm`, `island_terrain_wrapper_buffer.asm`, dan `island_terrain_wrapper_accessor.asm`: transfer sel 14-byte, vtable slot pembaca backing payload, buffer sementara pada 0x559690, serta checksum instruksi ELF.
- `output/ui_island/terrain_unit_pbc_catalog.json` dan `terrain_unit_pbc_loader.asm`: 246 baris unit, 242 nama model unik, 12 nama grup PBC native dan blok instruksi pembentuk `<ModelName>_pbc`.
- `output/ui_island/coast_part_assembly_native.json` dan `coast_part_assembly_native.asm`: jalur perakitan pantai native, 36 template, 22 slot per template, kandidat FieldOutsideParts, aturan perimeter laut, kisi 9×8, record koordinat serta checksum instruksi.
- `output/ui_island/coast_template_grid_native.json` dan `tools/coast_template_grid_native.py`: rangkaian coast-slot/cincin/perapian grid/serializer asli untuk semua template; tabel/cache direkonstruksi, tick sistem deterministik, rincian sel kosong dicatat.
- `output/ui_island/coast_parts_selector_native.json` dan `tools/coast_parts_selector_native.py`: uji native kumpul kandidat untuk 24 slot pantai dan 22 kelas ReefType, serta 368 hasil seleksi UID dengan fixture tick deterministik.
- `output/ui_island/coast_grid_serializer_native.json` dan `tools/coast_grid_serializer_native.py`: uji native clear `0x4de810` dan serializer `0x4e0c90` untuk 36 fixture template, 2.592 record tanpa mismatch. UID slot memakai kandidat pertama dari tabel dan UID laut diulang; selektor RNG/reef-aware bukan bagian dari uji ini.
- `output/ui_island/coast_part_instantiation_native.json` dan `coast_part_instantiation_native.asm`: consumer grid 9×8, resolver UniqueID, rumus pusat sel dengan spacing terukur 160.0, cabang OutsideSea dan static dispatch ke object factory; transformasi parent dan keberhasilan runtime tetap terbuka.
- `output/ui_island/river_inner_grid_topology.json`: join mask `InnerType0` 4×4 dengan seluruh preset, kontribusi unit River/Fall, statistik seam, ranking handedness rotasi dan batas inferensinya.
- `output/ui_island/external_pbc_format_reference.json`: perbandingan format PBC 52-byte dari parser komunitas dengan record runtime lokal; hanya sumber kode rujukan, bukan asset dump atau bukti jalur konversi.
- `tools/island_template_selector_native.py`: menjalankan selector dari main.elf sumber pengguna dan membandingkan hasil serta state RNG.
- `tools/island_loader_native.py`: memvalidasi 96 grid sumber dan membuat artefak pemetaan loader. Set `ACNH_RESEARCH_ROOT` bila tabel/grid sumber berada di checkout penelitian terpisah.
- `output/ui_island/pbc_ground_attribute_crosswalk.json` dan `tools/pbc_ground_attribute_crosswalk.py`: pemetaan 63 indeks baris material PBC ke `UniqueID`, nama debug, WaterCheck, dan izin masuk; nilai yang benar-benar dipakai payload ada di audit manifest.
- `output/ui_island/manifests_pbc_audit.json` dan `tools/audit_manifest_pbc.py`: kecocokan lima tabel, seluruh 96 grid, cakupan 783 PBC, material/tinggi per aset, 96 outlet, serta pembandingan seam. Jalankan `python tools/audit_manifest_pbc.py /path/manifests.zip --research-root /path/acnh-re`.
- `output/mechanics/terrain_pbc_native_consumers.json` dan `tools/terrain_pbc_native_consumers.py`: 208 awalan 12-float PBC terurai ke penulis tinggi native `0x180d20`; konteks tetangga 8×8 diulang dari pola PBC 2×2 dan bukan loader pulau asli.
- `tools/resident_floor_map_native.py`: dapat menerima `--manifest-zip /path/manifests.zip` untuk menjalankan reader resident-ground memakai PBC JSON terurai, bukan byte map sintetis. Jalankan pada checkout penelitian yang memiliki ELF dan tabel sumber.
- `tools/terrain_pbc_catalog.py`: menghubungkan kolom ModelName dan grup arsip PBC native ke katalog terrain; cakupan payload yang tersedia dibuktikan terpisah oleh audit manifest.
- `tools/river_inner_grid_topology.py`: mereproduksi join mask air per unit dan uji konsistensi rotasi pada 96 preset tanpa mengasumsikan geometri PBC.
- `tools/coast_part_instantiation_native.py`: merekam jalur consumer grid dan factory dari instruksi native serta checksum ELF.

Jalankan `python tools/island_template_selector_native.py` dari akar proyek penelitian dengan dependensi dan sumber lokal yang sama. `island_loader_native.py` membaca 96 JSON LandMaking, lalu menulis bukti turunan dari ELF yang sama; `ACNH_RESEARCH_ROOT=/path/ke/acnh-re` mendukung checkout delivery terpisah. Selector teruji 528 kasus pada laporan mandiri; generator ringkasan mekanik historis belum diperbarui dan total lamanya tidak digunakan untuk mengklaim cakupan baru.

## Tambahan: perakitan template pantai dan laut

Rantai `0x528bf0 → 0x4de9b0` sekarang dipetakan dari instruksi native. Wrapper mengosongkan 72 nilai u16, memilih part untuk 22 koordinat pantai dari kolom kategori template, mengisi perimeter laut, membersihkan interior 5×4, lalu menyalin kisi. Kisi berukuran 9×8: pantai menempati koordinat x=1..7 pada z=1 dan z=6 serta x=1 dan x=7 pada z=2..5. Cincin luar berisi 30 sel; bagian tengahnya 20 sel kosong. Seluruh 72 posisi terklasifikasi tanpa tumpang tindih.

`0x4dfeb0` mempertahankan urutan baris tabel saat membentuk kandidat `FieldOutsideParts` menurut `PartsKind`, lalu memakai satu draw u32 untuk memilih indeks `floor(draw*N/2^32)`. Semua 792 slot (36 template × 22) memiliki kandidat; buffer kapasitas 32 cukup karena pool terbesar di slot pantai berisi 7 opsi. Untuk laut, 27 posisi tepi memakai ReefType dari part pantai di sebelahnya. Empat sudut masing-masing mengisi sel diagonal dengan ReefType sudut yang sama dan dua sel sisi dengan orientasi laut yang disesuaikan ke kelas convexity/flat/concavity. Total ada 39 pemanggilan selector laut; kandidat terbesar per ReefType berisi 6 opsi. Seluruh 22 kelas ReefType pada data part punya kandidat.

Join table juga menunjukkan setiap template memiliki tepat dua slot pantai berkategori River. Dua belas `3B_S2` menempatkan slot itu di `S0Parts` dan `S4Parts` (dua outlet selatan); dua belas `3B_SW` memakai `W1Parts` dan `S3Parts`; dua belas `3B_SE` memakai `E1Parts` dan `S1Parts`. ModelName kandidatnya `FldOutSRiver00..02`, `FldOutWRiver00..01`, atau `FldOutERiver00..01`. Arsip manifest sekarang menyediakan PBC untuk seluruh 136 nama part, termasuk seluruh varian muara. Ini memetakan geometri/material statis yang tersedia, tetapi kandidat yang terpilih dan transform mesh yang dipakai di runtime belum terbukti. Ringkasan slot ada di properti `river_coast_slot_summary` pada JSON coast assembly; daftar payload ada di `manifests_pbc_audit.json`.

`0x4e0c90` menulis header dimensi 9×8 dan membuat 72 record berukuran 0x18 byte dengan UniqueID di offset +8 serta indeks grid x/z pada +12/+16. Jalur downstream kini terbukti: update object `0x529de0→0x528e60` memanggil loop `0x4dd4d0` pada cabang state tertentu. Loop 8×9 itu melewati sel UID=0, mencari row berdasarkan UniqueID (`0x551bf0`), membentuk descriptor posisi x=`160·gridX+80`, y=0, z=`160·gridZ+80`, lalu memanggil object factory. Nilai 160.0 berasal dari dua pointer global yang menunjuk konstanta float identik; vektor dasar yang dipakai memiliki XYZ nol. Dengan demikian pusat dan jarak kisi lokal terbukti; komposisi transformasi parent/world, rotasi, dan semantik flag option tetap belum diketahui. Perbandingan dimensi lintas sumber menunjukkan daratan 112×96 dan outline pantai 7×6, tepat 16 sel LandMaking per segmen pantai di tiap sumbu. PBC terrain 2×2 ×5 unit dan pantai 32×32 ×5 unit cocok dengan jarak sel terrain 10 dan spacing pantai 160. Itu mendukung skala bersama, tetapi origin/parent transform tetap belum dibuktikan instruksi native. Uji grid native menghasilkan 50–52 sel nonzero per template: 22 slot pantai serta 28–30 bagian laut. Loop factory melewati UID nol, jadi dispatch teramati pada fixture berjumlah 50–52 per template; keberhasilan load/render belum diuji. `0x551d20` memeriksa apakah row adalah `OutsideSea` dan memilih descriptor option 0 atau 2, tetapi makna option tersebut belum terbaca. PBC statis untuk semua 136 bagian kini ada; pemuatan/render/collision di runtime tetap belum diuji. Detail dan checksum tersimpan di `output/ui_island/coast_part_instantiation_native.json`/`.asm`; bukti assembly PBC ada di `manifests_pbc_audit.json`.

Uji consumer grid mengeksekusi `0x4de810` dan `0x4e0c90` pada 36 pola template dari tabel sumber. Untuk setiap pola, seluruh 72 ID dan koordinat `(x,z)` pada record native cocok, termasuk 22 ID slot pantai, 30 sel perimeter fixture, dan 20 sel interior kosong; total 2.592 record tanpa mismatch. Ini menguatkan pemetaan kisi integer ke record native. Uji tersebut sengaja memberi ID fixture deterministik sehingga belum membuktikan hasil pilihan RNG `0x4dfeb0` atau pengisian laut sesuai ReefType oleh `0x4deeb0`.

Selektor `0x4dfeb0` juga dijalankan sampai tepat sebelum RNG untuk seluruh 24 `PartsKind` yang dipakai template: 78 UID kandidat cocok dengan daftar sumber. Selector `0x4e01d0` mengumpulkan 52 UID untuk 22 kelas ReefType OutsideSea, juga tanpa mismatch. Lalu kedua selector dijalankan sampai return pada delapan tick deterministik per pool (368 kasus), dengan seed expander dan langkah RNG native asli. Harness mengganti hanya import `nn::os::GetSystemTick` di PLT `0x220e420`; cache typed, row wrapper, serta cache UniqueID direkonstruksi dari data tabel terurai. Jadi rumus pilihan UID sekarang teruji di kode native pada input terkendali, tetapi loader/cache bootstrap asli, nilai tick aktual, pemanggil generator `0x529910`, dan urutan draw gameplay tetap terbuka. Rincian ada di `output/ui_island/coast_parts_selector_native.json`.

Setelah cache pantai dan cache bagian direkonstruksi bersama, rangkaian native `0x4de810→0x4dea40→0x4deeb0→0x4dfcb0→0x4e0c90` berjalan pada seluruh 36 template. Semua 792 UID slot pantai cocok dengan kategori `PartsKind` sumber, dan semua 1.036 UID perimeter yang tidak nol adalah `OutsideSea`; setiap grid menghasilkan 72 record berkoordinat benar. Dari 1.404 panggilan selector perimeter, 44 mengembalikan UID 0 pada ReefType ordinal 14 (`S_concavity`), yang tidak memiliki row bagian laut di tabel. Akibatnya tiap template mengisi 28–30 dari 30 sel perimeter; sel kosong selalu berada di `[1,7]` (18 template) atau `[7,7]` (26 template), ketika side target meminta `S_concavity`. `NE_concavity` juga tidak memiliki row sumber, tetapi tidak muncul sebagai target perimeter pada 36 template yang diuji. Ini adalah hasil runtime-native dengan row wrappers/cache rekonstruksi serta tick deterministik; loader BCSV asli, waktu tick dan transform world tetap belum dijalankan. Laporan per template ada di `output/ui_island/coast_template_grid_native.json`.

## Tambahan: konektivitas unit sungai pada preset terrain

Pemeriksaan grid atas seluruh 96 preset LandMaking mengelompokkan layer0 unit ID yang metadata native petakan sebagai River0A..River8A/B/C. Ditemukan 84.759 sel River pada 96 preset; flood fill 4-arah menghasilkan 576 komponen (setiap preset lebih dari satu komponen pada klasifikasi semua tipe River). Tidak ada sel River pada layer1. Tidak ada komponen River yang menyentuh tepi grid daratan. Relasi tetangga terbanyak mencakup unit 17↔21 (24.622 sisi bersama) dan 20↔21 (23.148 sisi bersama); hitungan adalah sisi sel, bukan aliran air.

Hasil ini menunjukkan sel River preset merupakan jaringan internal yang terpisah dari edge grid. Semua 36 template memiliki dua slot pantai berkategori River pada pola selatan-selatan, barat-selatan, atau timur-selatan. Dengan mask CCW, outlet terdekat tiap preset tepat jatuh pada segmen slot yang ditetapkan template: 96/96 cocok. Ini menghubungkan pola mask dan slot pada tingkat data; belum membuktikan unit River terminal, transformasi world atau sambungan mesh pada runtime. File topology: `output/ui_island/river_grid_topology.json`; slot: `river_coast_slot_summary` dalam `output/ui_island/coast_part_assembly_native.json`; validasi outlet/PBC: `output/ui_island/manifests_pbc_audit.json`.

### Mask air `InnerType` per unit

Join `FieldLandMakingUnitModelParam` ke seluruh preset menemukan 13 UniqueID yang benar-benar dipakai; 5 bertipe River dan 3 bertipe Fall memiliki sampel air pada pola `InnerType0` 4×4. Tiga model Fall yang dipakai (`Fall300`, `Fall200`, `Fall400`) menyumbang masing-masing 9, 9, dan 12 sampel berkode River. Jadi jaringan air data-level juga melewati unit Fall, bukan hanya sel yang `ModelType`-nya River.

Untuk tiap preset, 4×4 mask unit dirakit memakai field rotasi sumber lalu diperiksa pada 8.177.664 pasangan sampel di seam antar-sel. Arah rotasi counterclockwise menghasilkan ketidakcocokan batas terendah: 244.810 (2,993642%) dan 413.422 pasangan air–air. Namun, 159.202 mismatch (65,0%) terjadi antara dua unit bertipe River; 64.058 mismatch berasal dari pasangan River5B (ID 17) dengan ID yang sama. Ini menunjukkan residu tidak dapat dijelaskan hanya oleh pasangan Fall, dan mask literal tidak boleh diperlakukan sebagai bukti sambungan mesh. Raster 448×384 hasilnya memiliki 849 komponen 4-arah untuk 96 preset, median 9 dan rentang 6–13. Kandidat tanpa rotasi menghasilkan 5.167 komponen; kandidat clockwise 7.419. Tidak satu pun raster menyentuh tepi grid luar pada ketiga kandidat. Pada kandidat counterclockwise, sampel air terdekat selalu 48 sub-sampel dari baris grid paling bawah untuk seluruh 96 preset; gap ke baris atas 56–88, sisi kiri 48–132, dan kanan 48–124.

Counterclockwise menempati peringkat pertama dari tiga konvensi mask; pada InnerType mentah masih ada residual 2,99%. Data PBC nyata juga menurunkan ketidakcocokan material pada seam menjadi 1,271952% dalam 4.088.832 perbandingan sisi segitiga; 95,4% residu terjadi pada River5B↔Base. Uji tinggi endpoint memberi 1,293% mismatch pada seam dengan byte elevasi yang sama, tanpa kalibrasi offset elevasi. Keduanya adalah dukungan konsistensi, bukan validasi renderer atau seam runtime. Native hanya membuktikan byte rotasi dipindahkan; transform world dan hubungan mask 4×4 ke grid pantai belum terbaca. Gap 48 sampel bukan jarak dunia. Data PBC ada dan diringkas di `manifests_pbc_audit.json`; aliran dinamis, efek waterfall, collision runtime dan seam fisik tetap belum terbukti.

## Format record PBC dan validasi payload

Parser PBC publik pada commit `bb09c0e` di `Treeki/CylindricalEarth` memberi header dan stride 0x34; HeavenTool pada commit `e3ddf83` mengisi struktur payloadnya dengan lebih terperinci. Arsip manifest yang diberikan pengguna sekarang memuat payload PBC terurai dengan header, ukuran, origin, cell size, 12 tinggi dan empat atribut per sel. Byte 0–47 berisi empat grup float32 dalam urutan Top, Left, Bottom, Right. Setiap grup adalah tinggi pusat segitiga lalu dua sudut. Byte 48–51 adalah empat atribut material dengan urutan arah yang sama. Bentuk ini cocok dengan kode lokal: 0x180d20 membaca 12 float dan 0x181cd0 mengambil empat atribut; 783 payload memberi validasi langsung pada corpus build ini.

HeavenTool menyatakan material IDs sebagai indeks baris `ColGroundAttributeParam`, dan seluruh nilai byte yang ditemukan di 783 PBC berada dalam rentang lokal 0–62. Ini indeks baris, bukan `UniqueID`: pada corpus PBC index 26 menunjuk `UniqueID=29` (`道:つち`, dirt path). Row WaterCheck yang teramati adalah index 1 River, 5 Sea, 12 Brackish water, dan 54 Museum water. Seluruh 63 baris beserta cakupan pemakaian ada di `pbc_ground_attribute_crosswalk.json` dan `manifests_pbc_audit.json`. Tinggi lokal, konversi elevasi ke world-space, seam transform, dan konversi LandMaking 14-byte ke runtime/PBC 52-byte tetap terbuka. Rujukan kode dan checksum ada di `external_pbc_format_reference.json`.

## Capaian poin 1–4 setelah lanjutan

Status akhir: poin 1–4 memiliki payload asset dan dataflow statis yang jauh lebih lengkap. Yang belum terbukti adalah eksekusi loader/pembangun pulau end-to-end, transformasi global, seam/collision runtime, skala tinggi/elevasi, simulasi air dan perilaku saat terrain berubah. Poin 2 tetap menunggu bootstrap cache/RNG generator utuh. Jadi data sumber sudah terbaca untuk bagian yang dipakai, tetapi hasilnya belum dapat disebut gameplay lengkap.

Field transfer juga menegakkan batas variasi: reader 0x547520 mengambil `Variation` u16 (CRC32 `0xc733aa77`) untuk unit tujuan dan loader mengubah indeks di atas batas menjadi 0. ID unit sentinel diganti ke ID default native; nilai kedua sentinel runtime belum dibaca. Byte tinggi dipindahkan lalu dibatasi oleh accessor terpisah 0xf52860; seluruh preset yang tersedia hanya memakai tinggi 0–3. Semua ini adalah bukti statis instruksi dan data, bukan hasil uji runtime world-builder.
