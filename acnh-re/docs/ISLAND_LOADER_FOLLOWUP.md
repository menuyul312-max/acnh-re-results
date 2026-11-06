# Island loader dan generator: follow-up terbatas

Tanggal: 6 November 2026. Alamat di sini adalah ELF VA; nama Ghidra `FUN_00629910` mengacu ke ELF `0x529910`.

## Temuan yang didukung

**[NATIVE]** Fungsi `0x529910` punya empat slot yang berulang. Indeks baris `FieldMainFieldParam` dipilih dari bitset tanpa pengulangan: draw u32 native dikalikan jumlah bit aktif, hasil perkalian high-word menjadi peringkat, `0x52a110` mengambil bit ke-n, lalu generator menghapus bit tersebut. Pembaca `0x54e190` membuka row yang dipilih; `0x54e330` membaca `OutsideTemplateKind`; `0x552bb0` memilih `UniqueID` template dengan state RNG yang sama; generator mengemas UID preset, UID template, dan nomor slot dalam parameter 0xe0-byte lalu memanggil `0x528bf0`.

**[NATIVE]** Keempat pemanggilan `0x552bb0` dan keempat pemanggilan `0x528bf0` terverifikasi di `index.sqlite` dan cocok dengan instruksi ELF. `0x528bf0` memanggil `0x558f40` hanya jika resource template dan grid tujuan tidak null. Harness terbatas menjalankan seed expansion `0x19aa040` dan delapan draw `0x19aa0e0` pada instruksi asli dengan seed tetap; semua state dan hasil cocok dengan rumus pembanding. Constructor generator `0x19a9fe0` memakai `nn::os::GetSystemTick`, jadi uji seed ini mengesahkan algoritme RNG, bukan stream tick asli atau urutan lengkap generator.

**[TBL]** Tiga tabel mentah dari additional RomFS cocok dengan skema kolom di indeks lokal: `FieldMainFieldParam` 96 row dan 96 UID unik, `FieldOutsideTemplate` 36 row, dan `FieldLandMakingUnitModelParam` 246 row. Kind template untuk 96 preset berjumlah 30/33/33 pada enum 0/1/2. Additional RomFS ini berisi 96 file `FieldPreset*_LandMaking.byml`; ringkasan terkomit di artefak loader mengidentifikasi 112×96 sel dan record sumber 14 byte per sel.

**[NATIVE]** Pada `0x558f40`, record sumber mempunyai stride 14. Untuk tiap koordinat, dua layer dibaca dari byte offset 0 dan 6, tinggi dari offset 12. Loader menulis tujuh field ke cell accessor tujuan pada offset `0, 2, 4, 6, 8, 10, 12`; koordinat yang di luar grid dilewati. ID unit sentinel diganti default; indeks variation dibandingkan dengan batas `Variation` dari cache FieldUnitParam (hash kolom `0xc733aa77`) dan nilai di atas batas direset ke nol. Byte tinggi ditransfer apa adanya; accessor berikutnya membatasi nilai di atas 5 menjadi 4. Semua tinggi pada 96 preset yang telah didekode berada pada 0–3.

## Batas join dan transform

**[NATIVE]** Grid ground/collision runtime adalah format berbeda: indeks `x + width*z`, stride 52 byte, berisi 12 float32 pada byte 0–47 serta empat atribut material pada byte 48–51. Fungsi loader `0x558f40` yang ditelusuri di atas menulis field LandMaking, bukan memperluas satu cell 14-byte menjadi record 52-byte.

**[TBL]** Katalog resource mencatat jalur nama `ModelName + "_pbc"` dan grup arsip unit terrain. Ringkasan audit sebelumnya menyebut semua 13 unit yang dipakai preset mempunyai kandidat PBC 2×2 pada cell size 5.0. **[EF]** Payload PBC itu tidak ada dalam additional RomFS yang tersedia, dan `index.sqlite` juga tidak memiliki path bernama PBC. Karena itu byte tinggi/atribut untuk tiap record, transformasi rotasi ke empat subcell, origin, skala tinggi, dan cache resource runtime tidak dapat dijoin atau dibandingkan di sini. Hubungan 16 sel LandMaking per segmen coast 160-unit → 10 unit per sel tetap inferensi bersyarat, bukan transform world yang dibuktikan loader.

**[PSEUDO]** Urutan kontrol empat slot dijabarkan dari instruksi/dekompilasi dan call site, tetapi iterasi ini belum mengeksekusi `0x529910` atau `0x528bf0` bersama registry/cache/resource asli. Jadi UID hasil empat slot untuk seed tertentu dan grid runtime hasilnya belum diklaim.

## Reproduksi dan hasil

Jalankan `python acnh-re/output/ui_island/island_loader_followup/reproduce.py` dari checkout ini. Skrip hanya membaca input, BCSV tambahan, `index.sqlite`, ELF dan artefak ringkasan; output baru ditulis ke `output/ui_island/island_loader_followup/`. Ia memeriksa jumlah row/kategori, empat call site per slot, field offset 14-byte, perbedaan stride 14 vs 52, ketiadaan file PBC, serta delapan langkah native RNG. Hasil lengkap dan checksum sumber ada di [`result.json`](../output/ui_island/island_loader_followup/result.json).

| Jalur | Bukti berhasil | Terbuka |
|---|---|---|
| Generator luar | **[NATIVE]** Empat pasangan selector/setup dan urutan pemilihan tanpa pengulangan terkonfirmasi statis. Delapan draw seed tetap lulus pada fungsi RNG asli. | Bootstrap registry/cache dan eksekusi empat slot `0x529910 → 0x528bf0` belum berjalan end-to-end. |
| Preset 14-byte | **[NATIVE]** Field transfer dan aturan variation/height dipetakan untuk seluruh koleksi 96 preset. | Alokasi internal/accessor grid tujuan dan pemuatan resource asli belum dieksekusi. |
| Ground/PBC 52-byte | **[NATIVE]** Bentuk record dan konsumennya diketahui dari pembaca ground/height asli. | **[EF]** Dump yang tersedia tidak membawa payload PBC; join data dan transform per-cell belum dapat diuji. |
