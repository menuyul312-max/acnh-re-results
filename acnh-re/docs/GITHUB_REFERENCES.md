# Rujukan GitHub untuk melengkapi RE ACNH

Sumber publik dipakai sebagai pembanding dengan commit tetap. Tahap lanjutan sudah memeriksa layout item terhadap instruksi native, menguji helper asli, dan membandingkan kamus save dengan hash lokal. Kode recompiler/runtime tidak dijalankan; hasil terverifikasi serta kandidat tetap dibedakan.

## Temuan versi

ACNHRecomp pada commit `b0c357c13b22cc6419c6ae6ca9711de55c6d08fe` memetakan build ID `7FC1BAFF976AECA414520CB89F4616CB` ke ACNH **1.0.0**. Bytes ID tersebut ditemukan pada ELF lokal di offset file 50.444.884. Lihat [versions.txt](https://github.com/Nycolazs/ACNHRecomp/blob/b0c357c13b22cc6419c6ae6ca9711de55c6d08fe/games/acnh/versions.txt) dan [hooks 1.0.0](https://github.com/Nycolazs/ACNHRecomp/blob/b0c357c13b22cc6419c6ae6ca9711de55c6d08fe/games/acnh/hooks-1.0.0.txt).

Kecocokan ID membantu memilih alamat versi yang tepat. Ini tidak membuktikan seluruh implementasi runtime proyek lain sudah sesuai dengan game asli.

## Yang dapat diperoleh

| Proyek | Referensi yang tersedia | Penggunaan pada pekerjaan ini |
|---|---|---|
| [Treeki/CylindricalEarth](https://github.com/Treeki/CylindricalEarth) | Skema BCSV, enum, EventFlow, RTTI, save schema, kamus field, pembaca PBC | Sebagian skema sudah dipakai untuk pemulihan nama kolom sebelumnya. Kamus save dan hierarki tipe masih dapat menjadi pembanding lanjutan. |
| [Nycolazs/ACNHRecomp](https://github.com/Nycolazs/ACNHRecomp) | Recompiler AArch64, runtime HLE, translasi NVN/Vulkan, hooks dan diagnosis | Referensi untuk ABI/fungsi impor, alur file/waktu/input, shader dan validasi instruksi. |
| [kwsch/NHSE](https://github.com/kwsch/NHSE) | Struktur item, map, villager, flower genes dan offset save berbagai versi | Kandidat interpretasi bit-field item delapan byte dan struktur save. |
| [Slattz/LibACNH](https://github.com/Slattz/LibACNH) | Parser BCSV/BYML/MSBT/SARC, hash, EncryptedInt, SaveCrypto, sead Random | Pembanding algoritme dan pembaca independen. |
| [Treeki/MeteoNook](https://github.com/Treeki/MeteoNook) | Riset prediksi cuaca dan core Rust | Snapshot dipin; tabel lokal dibandingkan, RNG dan pemilih hari biasa diuji native. Empat perbedaan cuaca lokal dipertahankan. |
| [Turnip Prophet](https://github.com/mikebryant/ac-nh-turnip-prices) | Prediksi pola dan probabilitas harga turnip | Kandidat untuk pendalaman ekonomi; implementasi/lisensi belum diperiksa. |

## Contoh konkret yang baru diperiksa

- NHSE `Item.cs`, commit `cb0745415945776f73375bf0a434a8babf059307`, mendefinisikan item delapan byte: ItemId u16 di offset 0, SystemParam u8 di 2, AdditionalParam u8 di 3, dan FreeParam s32 di 4. Layout tersebut kini cocok dengan dua helper copy asli. Reset kosong, lookup wrapping, dan pembacaan koordinat extension diuji melalui emulasi tanpa stub. Interpretasi rotation/buried/dropped, flower genes, serta seluruh union FreeParam tetap memerlukan bukti tersendiri.
- Ada perbedaan versi: helper lookup lokal 1.0.0 melewati MessageBottle 0x16a1 dan memakai aturan dummy sesuai dua bit mode. Pengecualian Egg/Festive dari NHSE terbaru tidak langsung diterapkan. Seluruh item korpus punya AdditionalParam nol; uji wrapping memakai data sintetis.
- `save_keys.json` CylindricalEarth mempunyai 1.101 pasangan yang cocok Murmur3 seed 0. Satu pasangan bernama `AdditionalAudioInfoV` gagal dan ditolak. Kandidat `UIList` menambah pembanding pada 12 kemunculan. Nama dari kamus saja tidak menggantikan key secara otomatis.
- Pemulihan field parameter menemukan aturan berbeda dari save: CRC32 `nama.tipe` dan `nama[]`, dikonfirmasi pada formatter native. Nama/tipe/koordinat baru beserta provenance tersedia di [kamus BYML](../output/schemas/byml_names.json) dan [hasil item](../output/items/summary.json).
- ACNHRecomp menyediakan `hle_time.cpp` dan `hle_fs.cpp`, termasuk representasi waktu/kalender dan pemetaan filesystem. HLE adalah implementasi pengganti; fungsi stub tidak menjadi bukti perilaku SDK asli.
- README CylindricalEarth menyebut alamat vtable EventFlow versi 1.1.4 dan save schema yang berubah antarversi. Alamat tersebut tidak boleh langsung diterapkan pada biner 1.0.0.

## Yang tetap belum tersedia dari sumber publik yang diperiksa

MeteoNook commit `a7ea07aa9b3db8859b0f476c549a1a2245ad1b07` (AGPL-3.0) kini diperiksa pada `src/data.rs` dan `src/lib.rs`. Semua 40 tabel bobot, kalender, dan angin cocok; empat nilai cuaca per jam berbeda. RNG state nol juga mempunyai perilaku API yang berbeda. [Kontrak, bukti dan batas](NATIVE_STAGE_WEATHER.md). Pemilih hari biasa teruji pada data lokal; event khusus, rollback tanggal SDK dan seluruh visual cuaca belum terverifikasi.

HeavenTool commit `e3ddf830a4ae360657917d3d598c79170273d056` diperiksa sebagai kandidat nama. CRC32 cocok pada sepuluh kemunculan kolom, tetapi tujuh descriptor melebihi span lokal. Nama yang lebarnya cocok juga belum mempunyai bukti peran. Nol nama dipromosikan; kode/daftar lengkap tidak disertakan. [Audit](../output/schemas/public_descriptor_audit.json). Ini contoh bahwa kecocokan hash saja belum cukup untuk mengubah skema kanonis.

ACNHRecomp secara eksplisit menyatakan tidak menyertakan aset game, executable game/SDK, atau kode game hasil translasi. Dump, generated C++, dan hasil build ditempatkan pada direktori `private/` yang diabaikan Git. Dokumentasi format dan parser dari proyek lain tidak mengisi bytes mesh, tekstur, animasi, audio atau modul SDK yang tidak ada dalam input lokal.

## Urutan pemanfaatan

1. Pilih metadata/hook ACNHRecomp untuk build 1.0.0 yang cocok.
2. Cocokkan skema, kamus nama, dan struktur NHSE/Treeki terhadap hash, offset, serta pembaca native lokal.
3. Cocokkan algoritme cuaca/ekonomi dengan konstanta dan perilaku biner yang tersedia.
4. Rekam sumber, commit, lisensi, status kandidat dan hasil verifikasi. Pemetaan kanonis hanya diperbarui jika bukti lokal mendukungnya.

Proyek Godot tetap tidak diubah. Hasil tahap lanjutan dibangun melalui pipeline data, dan ikut paket ZIP hasil terbaru. Snapshot rujukan, URL, checksum, serta batas pemakaian tercatat di [PINNED_SOURCES.json](../tools/external/PINNED_SOURCES.json).

Katalog pemeriksaan: [github_sources.json](../research/github_sources.json).

