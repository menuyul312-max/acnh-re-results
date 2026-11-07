# Sisa verifikasi skor pulau: classifier dan fixture sintetis

Tanggal: 7 November 2026. Build native yang dipakai adalah ExeFS `main` dengan SHA-256
`f8d248109ff72999b4600ae3749f8c7397fb960f7ad3ab8dee3018ae9e14e900`.

## Hasil

Item `island-score-native` di `re_queue.json` tetap **open**. Jalur native yang lebih kecil kini teruji: `0x15c4590` mengklasifikasikan item, `0x15c4240`/`0x15c48b0` menghitung satu sel ke blok sintetis, dan `0x15c68c0` menyalin skor serta grid kategori 10 ke member save sintetis. Pemanggil penggabung `0x15c61f0` belum dijalankan.

Sebelum fixture ini, `tools/gameplay_native.py` sudah menguji 70 sampel sepuluh leaf bobot `0x15c6910`–`0x15c69a0` dan 48 sampel `0x15c4db0`, tercatat lulus di `output/gameplay/gameplay_native.json`. Namun classifier, penghitung sel, dan penjumlahan penuh masih berstatus `[PSEUDO]` di `GAMEPLAY_FLOW` §10.1; laporan ini menambahkan pengujian classifier dan penghitung sel native.

Runner baru menjalankan 14 kasus kategori, lima pengecualian unit-icon, lima batas bonus harga, dan uji kategori 10 pada layer 0 serta layer 1. Semua lulus. Kasus meliputi kategori 0–10, furniture bertabrakan, pohon/palm dengan bit kategori 10, fence, bunga, weed, item ikon, serta pengecualian `Hole`/`Stone` dan lima item/kind yang tidak dihitung sebagai ikon. Harga `1999`, `2000`, `19999`, dan `20000` mengonfirmasi batas bonus `+0.5` outdoor, `+1` mulai 2000, dan `+2` mulai 20000; bonus outdoor tetap ditambahkan pada rentang harga yang lebih tinggi. Bit kategori 10 muncul pada helper layer 0 dan tidak pada helper layer 1.

Pemeriksaan duplicate memakai item dan varian yang benar-benar dimasukkan oleh helper blok native. Untuk kategori 0 dan 1, pengulangan 5/6/10/11 kali menghasilkan denda `0/2.5/4.5/7.5`. Sepuluh item dengan satu ID dan dua varian menghasilkan dua pasangan distinct dan denda `4.0`. Fixture dua blok dengan empat salinan per blok tetap tanpa denda; ini mengonfirmasi denda diterapkan per blok.

Empat pulau sintetis kemudian diringkas memakai counter native per blok, denda native, dan fungsi bobot asli `0x15c6910`–`0x15c69a0`. Natural dan Life dari fungsi bobot cocok dengan rumus §10.1:

| Fixture | Counter utama | Natural | Life |
|---|---|---:|---:|
| `balanced_categories` | C0..C10 = `[2,1,1,1,1,2,1,1,1,1,3]`; bonus harga 4.0 | 4.5 | 15.2 |
| `duplicate_penalty_thresholds` | C0=6, C1=11; nilai setelah denda masing-masing 3.5 | 0.875 | 7.0 |
| `duplicate_penalty_is_per_block` | C0=4 pada masing-masing dari dua blok | 2.0 | 8.0 |
| `natural_tree_cap_190` | C5=191 | 190.0 | 0.0 |

Poin kategori 10 juga dipindahkan melalui writer native ke save fixture. Tiga blok sintetis dengan 179, 180, dan 181 half-unit menghasilkan nilai yang sama di grid save; dua blok memenuhi ambang statis 180. Query EventFlow `VillageScoreVeryMessy` sendiri belum dijalankan.

## Batas fixture

Classifier, penghitung blok, denda duplicate, fungsi bobot, dan writer save berjalan dari instruksi ELF asli. Stub hanya mengganti batas data/accessor: lookup ItemParam dan FgMainParam, field furnitur/jenis medan/ikon/ukuran/harga/varian, serta konstruktor tampilan sementara. `0xf58a90` membaca ID u16 dari item sintetis. Satu pemanggilan penghitung mewakili satu sel asal yang diterima; fixture tidak mensimulasikan ukuran/overlap objek atau validasi posisi. Hasil membuktikan cara classifier native memakai nilai accessor yang diberikan, tetapi belum menguji lookup tabel asli untuk UID tertentu atau bit flag item dari save live.

Rumus Natural/Life dalam tabel di atas tidak datang dari eksekusi `0x15c61f0`: runner menjumlahkan hasil bobot native atas counter/denda native dan membandingkannya dengan rumus terdokumentasi secara independen. Jembatan, tanjakan, fasilitas, terrain counters, aktor yang memproses blok kotor, query EventFlow, serta siklus perubahan pulau→evaluasi→unlock belum menjadi bagian fixture. Karena itu bukti ini menutup cabang classifier/cell counter dan validasi komponen skor sintetis; ia belum menutup syarat queue “end-to-end native island score”.

## Reproduksi dan artefak

Jalankan dari root checkout:

```bash
python3 acnh-re/output/gameplay/island_score_remainder_20261107/island_score_remainder_native.py
```

Runner memakai `tools/nso_sandbox.py`, ExeFS `main` lokal, dan dependensi native yang tersedia melalui `ACNH_RE_DEPS` atau `/workspace/acnh-re/.deps`.

- [Runner dan fixture](../output/gameplay/island_score_remainder_20261107/island_score_remainder_native.py)
- [Hasil native JSON](../output/gameplay/island_score_remainder_20261107/island_score_remainder_native.json)

Hasil terakhir: semua 14 classifier/cell-counter cases, lima pengecualian ikon, lima batas harga, dua kasus layer, sembilan uji duplicate, empat pulau sintetis, proyeksi grid clutter, dan penyalinan save lulus. `0x15c61f0` tetap belum dieksekusi, sehingga status `island-score-native` perlu tetap **open**.
