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
| 1. Loader world | Pseudocode 0x528bf0 memanggil 0x558f40 secara bersyarat. Loader mengiterasi 112×96 sel dan dua komponen berukuran 6 byte dalam record 14 byte; schema/variasi model telah diperiksa pada tahap sebelumnya. | I/O BYML, virtual callback penulis, alokasi/lifetime dan rantai record 14-byte ke grid tinggi/collision 52-byte belum dijalankan lengkap. |
| 2. Pemilihan pantai | Selector 0x552bb0 teruji 528 kasus. Urutan enum memiliki dukungan literal/initializer. Pemanggil 0x529910 dan 0x5662e0 merujuk jalur pembaca OutsideTemplateKind lalu selector. | Bootstrap cache dan integrasi pemanggil belum teruji; pemilihan varian individual FieldOutsideParts masih terbuka. |
| 3. Perakitan part | 792 slot dari 36 template terhubung ke kandidat PartsKind; fungsi setup 0x508560 memanggil helper slot. | Origin, transform, orientasi, ukuran, seam dan collision pantai belum terbukti. 0x532070 merupakan kandidat jalur model unit berdasarkan pemanggilan formatter; bukan bukti susunan pantai. |
| 4. Sungai/air | Unit River/Fall dan arsip terkait terhubung dalam metadata. Slot muara terpetakan pada seluruh template. String RiverObject/WaterfallMapObject memberikan kandidat factory. | Konektivitas interior ke muara, geometri, water level/flow, shader/foam/ripple dan collision belum terbukti penuh. Factory objek bukan bukti algoritme air. |

Poin 1–4 belum dinyatakan selesai. Hasil baru ini menutup aturan pemilihan dari cache yang sudah tersedia, bukan seluruh pipeline. Ketiadaan PBC asli dalam korpus yang diaudit membatasi verifikasi isi collision, tetapi bukan alasan menghentikan pembacaan kode yang masih tersedia. Mesh/audio tetap referensi katalog sesuai permintaan pengguna.

## Artefak dan reproduksi

- `output/ui_island/island_template_selector_native.json`: fixture, hasil, batas bukti dan checksum instruksi.
- `output/ui_island/island_template_selector.asm`: disassembly 992 byte selector lengkap.
- `output/ui_island/island_native_call_candidates.json`: relasi pemanggil statis, dengan koreksi alamat.
- `tools/island_template_selector_native.py`: menjalankan selector dari main.elf sumber pengguna dan membandingkan hasil serta state RNG.

Jalankan `python tools/island_template_selector_native.py` dari akar proyek penelitian dengan dependensi dan sumber lokal yang sama. Bukti baru ini dihitung sebagai 528 kasus pada laporan mandiri; generator ringkasan mekanik historis belum diperbarui dan total lamanya tidak digunakan untuk mengklaim cakupan baru.
