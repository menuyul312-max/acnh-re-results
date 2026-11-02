# Kontrak data untuk konversi berikutnya

Kontrak ini mendeskripsikan sumber RE yang tidak bergantung pada engine. Tidak ada scene Godot atau logika gameplay baru yang dihasilkan.

## Identitas dan provenance

`output/manifest.json` adalah indeks utama. Setiap entri mempunyai `id`, `source`, `parent_id`, `format`, ukuran, SHA-256, referensi `raw`, status, dan lokasi `decoded` bila format memiliki pembaca. Notasi `!` pada sumber menunjukkan rantai keanggotaan kontainer, bukan jalur filesystem yang perlu dieksekusi.

`raw.$blob` selalu relatif terhadap `output/`. Isinya bytes asli atau isi anggota arsip setelah pembungkus dibuka, dengan SHA-256 dan ukuran. Deduplicasi berdasarkan isi tidak menghapus hubungan ke sumber.

Setiap dokumen `decoded` menggunakan pembungkus `schema`, `source_id`, `source`, `source_sha256`, `format`, dan `data`. Jangan memakai nama berkas numerik sebagai identitas aset permanen; gunakan sumber dan hash. Nomor adalah indeks hasil build ini.

## BCSV

`data.columns` diurutkan berdasarkan offset pada record. `data.rows` adalah array nilai yang mengikuti urutan kolom itu. Kolom memiliki hash, offset, lebar, nama terverifikasi atau null, tipe, dan status bukti.

`type_evidence=name_hash` berarti CRC32 dari `nama + spasi + tipe` cocok; `reference_inference` berarti tipe berasal dari inferensi pembaca terdahulu dan tetap tentatif. Angka enum mentah dipertahankan. Label yang muncul pada ekspor terdahulu diperiksa dengan CRC32 sebelum dianggap setara.

Untuk referensi konversi terbaru, gunakan `output/tables_resolved/` dan indeks `output/schemas/catalogue.json`. Sebanyak 1.957 descriptor kolom diverifikasi. Descriptor scalar berbentuk `Name u16` atau tipe scalar lain, string berbentuk `Name string32` dengan kapasitas eksplisit, dan enum berbentuk `Name.hshCstringRef`. `type_evidence=crc32_exact_descriptor` berasal dari kecocokan descriptor lengkap. Tipe pada 91 kolom tanpa descriptor tetap tentatif. Semua kolom tetap mempunyai hash dan offset.

Enum ditulis sebagai `{hash, labels}`. `labels` adalah pasangan `[English, Japanese]` dari domain rujukan yang hash-nya cocok dengan pilihan bahasa header lokal. Nilai tanpa label domain tetap memiliki hash asli; kandidat tambahan ada di `schemas/enum_label_candidates.json`. Kandidat lintas domain tidak otomatis menjadi anggota domain yang terkonfirmasi.

u16 dapat berada dalam rentang kolom empat byte karena padding. Byte record sumber tetap otoritatif. Nilai tidak valid sebagai UTF-8 disimpan sebagai `{"$bytes_hex":"..."}`, bukan dikira string teks.

## BYML

Tree mempertahankan key yang tersimpan dalam berkas, termasuk key hash berbentuk heksadesimal. Kandidat nama terpisah dalam `hash_names.json`; tidak ada penggantian key ambigu secara diam-diam. Blob menjadi objek `$blob`, ukuran, dan SHA-256.

Pembaca tree JSON tidak mengekspresikan seluruh perbedaan tag numerik BYML. Gunakan sumber raw bila perlu membedakan tag signed/unsigned atau melakukan rekonstruksi biner persis. Ekspor tambahan yang tidak memiliki BYML mentah ditandai `prior_json_export; original_BYML_not_supplied`.

Pembaca independen di `tools/typed_byml.py` kini menyediakan `output/byml_typed/catalogue.json` untuk seluruh 2.313 BYML mentah. Graph mempertahankan offset kontainer, tag setiap nilai, key/string table, raw word, pointer data, dan bits f32/s64. s64/u64 memakai `decimal` berbentuk string dan bytes hex untuk menghindari konversi melalui JSON double. Pada input ini terdapat 9.397 nilai s64; tidak ada yang melampaui rentang integer aman JSON, dan tidak ada u64/f64 yang dijumpai. Seluruh tree pembaca independen cocok dengan pembaca dasar; tidak ada key dictionary duplikat. Untuk kode yang perlu tipe persis, gunakan graph bertipe ini dan blob raw sebagai rujukan.

`byml_resolved/catalogue.json` menyediakan tampilan bernama untuk seluruh BYML. Key berawalan `@` adalah descriptor yang pulih, misalnya `@mHalfUnitX.s32`; key literal asli tidak diubah. `schemas/byml_names.json` menyimpan hash asli, seluruh kandidat, asal nama, algoritme, tipe deklarasi, keluarga nilai aktual, dan referensi string native. Penggantian hanya untuk kecocokan unik yang cocok keluarga nilai dan mempunyai sumber string native/data lokal. Kandidat yang hanya berasal dari kamus publik tetap terpisah. Uji membalik seluruh key ke bentuk sumber tanpa kehilangan informasi.

Parameter scalar/vector native memakai CRC32 `nama.tipe`, array memakai CRC32 `nama[]`, dan beberapa kelompok memakai nama polos. Data stage tertentu memakai kandidat Murmur3 seed 0 nama polos; algoritme disimpan per key dan tidak dicampur dengan CRC32. Hash heksadesimal dapat tidak menyertakan nol di depan. Tipe deklarasi bukan tag wire: `mItemNameParam.u64` dapat ditulis sebagai s32/s64 dalam BYML, sehingga selalu gunakan graph bertipe untuk representasi biner. Pemulihan descriptor tidak sama dengan pembuktian perilaku gameplay.

## Word item dan penempatan

`items/words.json` menyimpan nilai item unik sebagai string desimal u64, hex 16 digit, delapan byte little endian, ID tersimpan, SystemParam, AdditionalParam, serta FreeParam dalam tampilan signed/unsigned. `items/catalogue.json` menunjuk kemunculan per sumber beserta JSON Pointer ke key mentah. Definisi item mengacu ke baris `ItemParam` atau `FgMainParam`; sentinel kosong 65534 dipisahkan. Semua 46.034 kemunculan mempunyai definisi atau sentinel yang dikenali.

Layout native delapan byte adalah `<u16 ID, u8 SystemParam, u8 AdditionalParam, u32 FreeParam>`. `native_lookup_item_id` adalah hasil helper `0xf58a90`, disimpan terpisah dari ID tersimpan: mode AdditionalParam rendah dua bit dapat memilih dummy wrapping/present/cardboard. Pada versi 1.0.0, MessageBottle 0x16a1 melewati penggantian ini. Semua AdditionalParam pada korpus bernilai nol; cabang wrapping diperiksa dengan kasus sintetis, tidak diklaim teramati pada preset.

Sebanyak 44.443 penempatan memiliki koordinat bernama: preset lapangan memakai `mHalfUnitX.s32`, `mHalfUnitZ.s32`, `mItemLayerID.u8`; ruangan memakai `mUnitX.u8`, `mUnitZ.u8`, `mLayer.u8`. Nilai native dipertahankan tanpa menyimpulkan skala, orientasi sumbu, atau transformasi Godot. FreeParam merupakan union bergantung jenis item, bukan selalu stack count. Interpretasi NHSE atas rotation/buried/dropped belum dijadikan bukti native lokal. Hasil emulasi tanpa stub tersedia di `items/native_verification.json`.

## AAMP

Struktur mempertahankan list, object, parameter, hash nama, kandidat nama, tipe, offset descriptor, offset data, dan pointer word. Hitungan struktur dicocokkan dengan header. Float diekspor dengan nilai pembacaan f32, tanpa pembulatan enam desimal.

Kurva pada decode dasar dipertahankan sebagai record 128 byte, dua word header, dan 30 f32 payload. Interpretasi terverifikasi berada di `output/environment/curves.json`: word pertama adalah jumlah float aktif, word kedua jenis kurva. Jenis 7 dan 10 memakai titik `(x,y,tangent)`; jenis 10 mengalikan tangent dengan panjang segmen, jenis 7 memakai tangent lokal. Seluruh 360 record diuji terhadap fungsi native. Payload setelah jumlah aktif tetap disimpan sebagai `unused_tail`. Satu urutan x tidak monoton dipertahankan sesuai input, tanpa diurutkan ulang.

Pointer suatu nilai dapat berada di dalam rentang nilai lain karena penggunaan ulang data; batas data berikutnya tidak otomatis menentukan ukuran record. Pembaca dasar memberi nama layout pada jenis yang sudah diverifikasi; hasil sampling native berada pada berkas kurva terverifikasi di atas.

## EventFlow

Flowchart, actor, action/query, entry point, transisi, parameter, fork, join, dan subflow tersedia sebagai data. Pemeriksaan target memastikan konsistensi struktur, bukan membuktikan perilaku handler atau penjadwalan paralel.

Pembaca RE kini mempertahankan f32 tanpa pembulatan desimal; perubahan pada salinan pembaca referensi dicatat di `tools/reference/PROVENANCE.json`. Ekspor lama yang disertakan pengguna tetap tidak diubah.

Gunakan `binary/event_handlers_resolved.json` untuk factory/constructor/vtable. Alias berasal dari BYML `BindInfo`, kemudian canonical name dicocokkan ke registrasi Murmur3 seed 0 di ELF. Semua slot yang dipublikasikan harus menunjuk alamat executable dan sejajar empat byte. Batas deret pointer tidak ditentukan dari jumlah maksimum slot saja. `ExitFlowchart` merupakan operasi runner, dengan pemeriksaan native terpisah.

Pelacakan constructor baru mempertahankan offset pointer `this`, sehingga penulisan vptr `SafeString` yang tertanam tidak tertukar dengan vptr object utama. Seluruh 904 constructor unik menghasilkan store ke offset object nol yang teridentifikasi. `vptr_stores` memuat instruksi buktinya; ini propagasi statis terbatas, bukan emulasi seluruh jalur constructor. `slots_raw` mempertahankan pointer asli, sedangkan `slots` mengikuti thunk tail branch. Span kandidat diteruskan sampai pointer nol/non-executable, dengan guard 256 slot; guard tersebut tidak tercapai pada korpus ini. Peran slot tambahan tetap belum ditentukan.

## Terrain dan resep

`output/world/FieldPreset*_LandMaking.json` menyimpan tujuh nilai per sel: unit, variasi, rotasi untuk dua layer, lalu height. Layout mentah 14 byte: `<u16 unit0,u16 variation0,u8 rotation0,pad,u16 unit1,u16 variation1,u8 rotation1,pad,u8 height,pad>`. Constructor/copy native tidak membaca tiga byte padding. Getter height `0xf52860` mempertahankan 0–5 dan memakai fallback 4 untuk nilai >=6; JSON mempertahankan nilai sumber, sehingga konsumen dapat menerapkan aturan itu secara eksplisit. Ini bukan operasi min(value,4). Seluruh 256 nilai byte diuji, termasuk nilai batas 5.

`FieldLandMakingUnitModelParam.Variation` adalah batas variasi; pemilihan aktual memakai indeks variasi dalam sel. Model dan arsip diperoleh melalui lookup di `relations/terrain_native.json`. Ini memperbaiki 54.820 pemilihan model pada ekspor lama. Semua 1.032.192 sel dan kedua layer memiliki ID unit serta variasi yang berada dalam tabel/rentang tersedia.

Formatter native `0x543340` memakai string `%s_%d` di `0x2996f6e`; argumen indeksnya dimuat langsung sebagai u16 dari komponen+2. Loader memakai fallback 0 jika indeks melebihi batas tabel. Instruksi penting beserta checksum region tersedia di `binary/critical_evidence.json`.

`relations/recipe_materials_native.json` menyimpan enam pasangan material/jumlah sesuai switch slot 0..5 di fungsi native `0xedac50`. Sentinel material kosong adalah 65534. Status ini memverifikasi pembacaan slot, bukan seluruh aturan transaksi crafting.

## Tekstur

`output/environment/textures.json` adalah referensi JSON untuk dua DDS BC4_UNORM yang dapat dipulihkan dari BNTX. DDS berisi blok linear tanpa kompresi ulang. Seluruh 13 mip dipertahankan; padding tiled tetap ada dalam blob sumber. Channel swizzle BNTX disimpan terpisah: angka 2 berarti R. DDS BC4 tunggal tidak otomatis menerapkan swizzle `[R,R,R,R]` dari game.

## Hubungan ke kode native

Database SQLite memakai VA ELF. Pseudocode Ghidra menulis alamat fungsi dengan tambahan image base `0x100000`. Jangan mencampur kedua ruang alamat.

Tabel `decomp` mencakup semua 6.402 berkas pseudocode yang tersedia, termasuk berkas yang tidak tercantum dalam snapshot `functions`. Pseudocode tetap merupakan hasil analisis terdahulu dengan kemungkinan salah tipe atau batas fungsi; tidak diperlakukan sebagai source asli.

Hasil Ghidra baru berada di `binary/analysis_decomp/` dan indeks SQLite `decomp_new`. Pseudocode otomatis dapat kehilangan nilai return akibat inferensi signature yang salah, mempunyai indirect call yang belum pulih, atau memuat peringatan decompiler. Pemahaman perilaku memerlukan pemeriksaan instruksi dan uji terarah; keberadaan berkas C tidak membuktikan seluruh fungsi sudah dipahami. Daftar kegagalan dan fallback disassembly disimpan terpisah dalam indeks hasil akhir.

`binary/code_pointer_arrays.json` menginventarisasi deret pointer relocatable ke kode. Ini kandidat struktur untuk penelusuran panggilan tidak langsung, bukan klasifikasi otomatis seluruhnya sebagai vtable. `binary/symbols.json` mencatat 910 simbol undefined dan library eksternal yang implementasinya tidak ikut paket.

`hash_refs` adalah hasil pencarian kandidat immediate MOVZ/MOVK. Hash yang sama muncul pada banyak tabel, dan pemindai jendela instruksi tidak membuktikan aliran data. `direct_calls` memuat BL dan kandidat tail branch ke entry fungsi; panggilan virtual tidak seluruhnya terwakili. Keduanya adalah alat penelusuran RE, bukan spesifikasi perilaku otomatis.

## Tingkat bukti

1. Bytes input yang dapat diverifikasi ulang.
2. Struktur yang lolos pemeriksaan ukuran, offset, hitungan, dan hubungan pada korpus ini.
3. Kandidat nama/hash atau hubungan yang cocok dengan data.
4. Makna gameplay yang didukung fungsi native dan dapat diuji.

Konversi harus mempertahankan pembedaan tersebut. Kelulusan pada tingkat struktur tidak otomatis menyelesaikan tingkat perilaku.
## Tambahan tahap native Stage/cuaca

Lihat [NATIVE_STAGE_WEATHER.md](NATIVE_STAGE_WEATHER.md) untuk ABI pembaca BYML, tipe array `%s[].%s`, registry actor, proyeksi f32, empat view byte BCSV, predicate flag, RNG, dan pemilih cuaca hari biasa. Indeks baru: `output/stage/catalogue.json`, `output/weather/patterns.json`, `output/weather/rates.json`, `output/weather/native_verification.json`. Data cuaca lokal tetap otoritatif saat berbeda dari referensi publik. Kolom tanpa nama yang view byte-nya terbukti tetap memakai hash; bukti tipe tidak dipromosikan menjadi nama asli.

Unggahan lima ExeFS berikutnya cocok dengan main lama dan kini menyediakan kode SDK/multimedia untuk penelusuran. [ADDITIONAL_EXEFS.md](ADDITIONAL_EXEFS.md) menjelaskan ruang alamat per modul, 898 kecocokan ekspor, perbedaan NPDM dan uji BYML memakai strcmp asli tanpa stub. `output/npc/voice_configuration_native.json` memetakan enam kolom NPC ke offset konfigurasi, dengan nama asli tetap unresolved.

Tahap [CALENDAR_FLOWERS.md](CALENDAR_FLOWERS.md) memverifikasi batas hari 05.00 lewat SDK, prediksi cuaca sebelum/sesudah batas hari, serta gen bunga, resource pertumbuhan, gen default dan item anakan. Byte terendah FreeParam pada keluarga bunga menyimpan gen; interpretasi ini tidak diperluas ke keluarga item lain. Kasus siklus Black Cosmos dicatat sebagai bounded execution, tanpa mengganti data asli.

