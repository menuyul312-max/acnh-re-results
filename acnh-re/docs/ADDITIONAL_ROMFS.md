# Audit RomFS dan katalog tambahan — 2 November 2026

Arsip tambahan berhasil diunduh dan diekstrak terpisah dari sumber awal. Ini
memperluas data yang dapat dianalisis, tetapi belum melengkapi seluruh aset dan
perilaku ACNH. Proyek Godot tidak dibuka atau diubah.

## Input dan kecocokan

| Input | Ukuran byte | SHA-256 |
|---|---:|---|
| extracted_romfs.tar.gz | 218358853 | d7016babade54714ad8fca65f5deeac2cb317f65365f63a7c84d1682c7e26e8b |
| KATALOG_MODEL_ACNH.csv | 11664619 | 358e39168dfa584cbc45e8582ffd9e2b492af7a2626e79e1f310b2c6b37ece58 |
| KATALOG_AUDIO_ACNH.csv | 5798832 | ca137ebac9cd3f56b6c6b30f0ec49237ea35530a3deb636e2570208a664a8d50 |

Arsip berisi 25.597 berkas biasa, total 278.419.280 byte. Tidak ada symlink atau
entri khusus. Seluruh 1.171 jalur B_data lama tersedia dan SHA-256 masing-masing
identik; 24.426 jalur lainnya baru terhadap B_data awal. Ini membuktikan
kecocokan subset lama dengan basis RE ACNH 1.0.0. Versi seluruh tambahan belum
dibuktikan secara independen melalui metadata build masing-masing.

Gzip dibaca sampai EOF untuk memeriksa CRC dan ukuran trailer. Tar terurai
berukuran 298.150.912 byte, termasuk header dan padding. Sumber awal dipertahankan.

## Hasil pembacaan baru

| Bagian | Hasil | Batas |
|---|---|---|
| Pesan | 154 arsip bahasa, 27.538 anggota MSBT, 965.426 pesan/label | 14 varian bahasa, masing-masing 68.959 pesan; bukan 965.426 pesan gameplay unik |
| BDLI | 23.310 berkas, 888.034 record LBLI | Semua hash CRC32 cocok unik ke label MSBT dalam konteks berkasnya; bukan pembuktian resolver runtime |
| Payload BDLI | 37.687.120 record berukuran 20 byte | Seluruh batas, cakupan tanpa gap/overlap, offset dan hash terperiksa; makna field payload belum ditentukan |
| AnimationSequence | 83 ASB, 1.159 node, 10.001 transisi, 1.297 warp, 1.895 kasus parameter | Struktur dan string dibaca; interpretasi kondisi dan ruang indeks transisi masih parsial |
| BYML tambahan | 55 AnimationInfo dan Param/Sound/SysSoundMgr.byml | Menambah sumber mentah yang sebelumnya hanya sebagian tersedia sebagai ekspor; belum diaudit native pada tahap ini |
| UI | 523 BFLYT dibaca | Pohon pane, material dan referensi tersedia; bukan UI yang sudah berfungsi di engine |
| Tekstur | 431 kontainer BNTX, 3.336 record tekstur | Metadata UI/font; angka dapat mencakup duplikasi antarkontainer; belum dikonversi seluruhnya ke gambar |
| GLSL UI | 133 anggota sumber, 30 konten unik menurut SHA-256 | Sumber yang memang tersimpan dalam kontainer; bukan dekompilasi seluruh shader game |
| BFSHA | Dua arsip, lima shading model, 1.889 slot program yang dinyatakan metadata | Opsi dan pilihan dibaca; tabel program/key/BNSH belum direkonstruksi lengkap |
| Kontainer tambahan | 1.076 SARC, 4.792 anggota | Hitungan ini untuk jalur baru di luar arsip Message dan kontainer lama yang sudah dianalisis |

Pembacaan format yang ditangani selesai tanpa error tercatat. Batas SARC dan
hash nama anggotanya diperiksa; batas MSBT dan indeks label/teks juga diperiksa.
Tag kontrol dan atribut pesan tetap disimpan; perilaku rendering dan substitusi
tag belum divalidasi melalui runtime game.

Header BDLI terukur: magic BDLI, versi u16=2, count u16 di +6, array LBLI pada
offset 20. Tiap LBLI berukuran 16 byte: magic, count payload u32, offset payload
u32 relatif ke awal record LBLI, lalu CRC32 label. Awal area payload = 20+16*count.
Hasil ini adalah bukti struktur korpus, belum penelusuran fungsi konsumen native.

## Hubungan ke hasil RE lama

- Dari 8.093 rujukan pesan EventFlow, 8.030 cocok secara exact dengan path dan label
  pada masing-masing dari 14 bahasa. Ada 63 kemunculan tanpa kecocokan exact.
  Ini tidak otomatis berarti teks hilang atau alur rusak: normalisasi nama,
  pemilihan suffix dan keterjangkauan jalur runtime belum dibuktikan.
- Dari 8.208 baris ItemParam, 8.074 memiliki kandidat nama tampilan tunggal pada
  setiap bahasa; 134 belum terhubung. Item biasa memakai suffix UniqueID label.
  Pakaian memakai UniqueID pada label warna, kemudian key kategori/group yang
  sama untuk nama kelompok. Nama kelompok dan warna dipertahankan terpisah.
  Aturan join data ini belum menggantikan audit seluruh fungsi pemilih nama native.
- Sebanyak 7.668 baris item mempunyai ResName yang sama persis dengan Asset_ID
  katalog model; 540 tidak. Kecocokan katalog tidak membuktikan mesh tersedia.
- Nama 91 kolom BCSV dan 431 key BYML yang belum pulih pada korpus awal tetap
  terbuka. Tahap ini belum menghitung ulang cakupan nama seluruh BYML tambahan.
- Jumlah uji native lama tetap 780.339 helper/blok dan 2.546.185 pemeriksaan BYML.
  Audit struktur baru tidak dijumlahkan sebagai tambahan uji perilaku native.

## Apa yang tersedia dan masih kurang

Katalog model memuat 37.459 entri: 5.627 menyatakan GLB+PNG dan 31.832 PNG saja.
Itu adalah keterangan katalog tentang hasil konversi, bukan verifikasi berkasnya.
Katalog audio memuat 17.410 entri: 860 BGM dan 16.550 SFX. Seluruh jalur sumber
RomFS pada katalog audio tidak ditemukan dalam arsip yang diberikan.

Tidak ada direktori Model/ atau Sound/Resource/ dalam arsip. Berkas GLB/PNG/OGG
di jalur acnh_godot/generated yang dirujuk katalog juga tidak ikut dikirim.
Jangan menyimpulkan model, animasi skeletal, waveform dan audio loop telah
dipulihkan hanya dari keberadaan katalog.

Shader dan efek kini tersedia sebagian sebagai biner sumber: dua VFXB/PTCL,
ELink2DB.belnk dan SLink2DB.bslnk (magic XLNK), serta BFSHA dan kontainer shader.
Pernyataan lama bahwa semua sumber VFX/shader tidak tersedia tidak berlaku lagi
untuk tambahan ini. Semantik PTCL dan XLNK masih perlu RE. Ada 2.095 BFLAN,
530 FCPX dan 256 BNSH yang telah diinventarisasi, tetapi belum didekode lengkap.

Sistem AI, scheduler, ekonomi, save/load, jaringan, fisika, breeding lengkap,
event cuaca dan integrasi engine tetap belum selesai. Tidak ada eksekusi game
lengkap atau konversi Godot pada tahap ini.

## Berkas hasil dan reproduksi

Semua keluaran baru berada di output/additional_romfs/:

- summary.json, archive_inventory.json, extracted_manifest.json
- messages/{bahasa}/{arsip}.json dan bdli/{bahasa}/{arsip}.json
- animation_sequences/, new_byml/, ui/, shaders/ dan resource_inventory.json
- catalogues/model.json, catalogues/audio.json
- eventflow_message_bindings.json, item_localization_and_catalogue_links.json
- link_verification.json, audit.log, link.log

Data mentah tambahan berada terpisah di
/workspace/downloads/acnh_additional_romfs_2026-11-02/romfs.
Referensi offset/anggota kontainer dan hash disimpan supaya pembacaan dapat
ditelusuri ke sumber. Payload besar BDLI dirujuk dengan offset, count dan hash,
bukan diperluas menjadi puluhan juta array JSON.

```bash
python /workspace/acnh-re/tools/download_additional_romfs.py
python /workspace/acnh-re/tools/extract_additional_romfs.py
cc -O2 /workspace/acnh-re/tools/reference/acnh_rip/native/yaz0dec.c -o /workspace/acnh-re/work/yaz0dec-additional
python /workspace/acnh-re/tools/audit_additional_romfs.py
python /workspace/acnh-re/tools/link_additional_romfs.py
```

Dependensi tambahan: zstandard. Paket hasil lama tetap menjadi baseline;
keluaran audit tambahan harus dipakai bersama baseline tersebut.
