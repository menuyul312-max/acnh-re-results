# Terrain runtime, bitset area dan evaluator NPC

Tahap setelah commit `5309d6f` menambahkan **1.568 kasus native tanpa mismatch**.
Total helper/blok menjadi **1.135.577**, dari 1.134.009. Pemeriksaan BYML tetap
2.546.185 dan terpisah. Angka ini volume validasi konteks terkontrol, bukan
persentase penyelesaian seluruh game.

Temuan utama: record terrain runtime kini terhubung melalui instruksi asli ke
word flag, node navigasi dan A*. Flood-fill/bitset serta beberapa jalur lengkap
evaluator NPC juga berjalan. Input world, height records dan actor state tetap
rekonstruksi. Loader preset, world lengkap, worker async dan steering belum selesai.

Godot dan sumber pengguna tidak diubah. Model/sound tetap referensi katalog.
Alamat adalah VA ELF ACNH 1.0.0, SHA-256:
`5bf707c3dc5dac0ad9635af7d336ec580f81c3f7876d0f55400d1900e3415d74`.

| Area | Sebelumnya | Tambahan tahap ini | Kasus |
|---|---|---|---:|
| Terrain menuju navigasi | Grid A* dengan flags/weights yang disiapkan | Writer ketinggian runtime, decoder word, callback node, reset biaya dan classifier | 1.199 |
| Bitset area | Input bitset buatan pada lookahead | Flood/wrapper asli dibandingkan queue traversal, repair sumber dan consumer bitset | 194 |
| Evaluator NPC | Setup berhenti sebelum evaluator | Jalur arrival/promotion/resume/wait lengkap dan setup hingga batas FSM | 175 |

## Record runtime memuat 12 sampel float ketinggian

`0x180d20` membaca 48 byte awal record 52 byte sebagai 12 float. Empat byte pada
+48..51 tetap atribut sektor. Fungsi membandingkan sampel antar sektor dan
record tetangga, lalu menulis flag 32-bit per sel pada array terpisah:

| Field world | Peran yang dikonsumsi |
|---|---|
| +0x30/+0x34 | Width/height |
| +0x40/+0x48 | Jumlah/pointer record base52 byte |
| +0x50/+0x58 | Jumlah/pointer overlay |
| +0x60/+0x68 | Jumlah/pointer word flag 32-bit |

Ini memperjelas **runtime record**. Isi48 byte awal PBC asli, serta constructor
yang menghubungkan preset14 byte ke runtime52 byte, tetap belum terbukti.
Kesamaan stride tidak dipakai untuk mengklaim loader tersebut sudah dipahami.

Pengujian writer memakai atribut sektor 0 dan threshold spread world yang
disiapkan. Nilai0 dapat dirujuk ke ColGroundAttributeParam pada katalog; tabel
tersebut menjadi referensi semantik, bukan getter BCSV yang dieksekusi di uji ini.
Surface type lain dan seluruh kombinasi threshold/overlay belum diperiksa.

Pada context yang diuji:

- Selisih internal antar sektor memakai batas **1,25 inklusif**. Bit12 menyala
  bila seluruh sambungan internal lolos. Dua pola pasangan berlawanan menghasilkan
  bit 13 atau bit 14.
- Bit0 word input melewati pemeriksaan slope internal. Pemeriksaan tinggi antar
  sel tetap berjalan pada kasus yang diuji.
- Tetangga dengan ketinggian konstan tersambung bila delta berada pada
  `[-1,25,+1,25]` dan bit 6 word tetangga tidak menghambatnya.
- Bagian word di luar bit 8..14 dipertahankan oleh writer pada pengujian ini.

Ada 336 kasus batas ketinggian tetangga dan 312 pola internal, termasuk one-hot
pada seluruh12 sampel serta pola acak deterministik. Buffer record sumber dan
guard tetap identik. Delapan rantai menjalankan writer → callback node → A*
asli. Patch datar menghasilkan rute; barrier tinggi5 pada contoh ini menghalangi
rute, termasuk contoh celah satu sel yang diuji. Ini hasil pada konfigurasi uji,
bukan aturan lengkap semua celah atau bentuk pulau.

## Decoder word dan callback node kini terhubung

Reader `0x185e70` mengubah word runtime menjadi byte antara:

| Bit word | Bit byte hasil |
|---:|---:|
| 8 | 2 |
| 9 | 3 |
| 10 | 0 |
| 11 | 1 |
| 12 | 4, hanya ketika bit 6 word clear |
| 13 | 5 |
| 14 | 6 |

Seluruh 256 kombinasi bit yang relevan dan enam koordinat invalid diperiksa.
Callback lengkap `0x15c24a0` kemudian menjalankan `0x15c26b0` pada 256 kombinasi
lain dengan registry constraint kosong dan crop range nonaktif.

Byte antara bit 4,5,6 memiliki prioritas berurutan. Jalurnya membentuk flag arah,
mode node 0/1/2 serta perubahan mask melalui fungsi rekonsiliasi tetangga asli.
Pengujian memeriksa nibble flag langsung, state/mode, batas mask langsung serta
integritas source. **Seluruh byte/mask hasil disimpan**, tetapi semua high bit
tambahan dari rekonsiliasi tetangga belum diberi arti gameplay.

### Bobot biaya berasal dari reset native

Fungsi lengkap `0x15c2ce0` mengisi kategori default 3 dan bobot:

```text
kategori: 0  1  2  3      4  5  6  7
bobot:    1  1  1  1  99999  6  3  2
```

Ini hasil reset asli dengan konstanta ELF, menggantikan kebutuhan memakai bobot
uji untuk mengetahui default jalur ini. Nilainya tidak otomatis membuktikan
semua perubahan konfigurasi selama game berjalan.

`0x15c2910` diuji pada 24 kombinasi. Dengan registry predicate biaya kosong:
node state 3 memilih kategori 4; bit eligibility memilih5; class byte 0 mempertahankan
kategori sebelumnya; class byte 1 memilih7; byte nonzero lain memilih6. Producer
class byte dan seluruh predicate actor belum dijalankan. Array class byte serta
eligibility pada pengujian classifier masih disiapkan eksplisit.

Data: [terrain_nav_flags_native.json](../output/mechanics/terrain_nav_flags_native.json).

## Flood-fill membentuk bitset yang berbeda dari uji passability A*

`0x15bf150` menelusuri direction mask, memakai bitset clear/set asli dan SDK
memset asli. Queue traversal independen memeriksa seluruh bit, jumlah bit dan
guard. Ada 31 skenario: empat bentuk dasar,24 pola blocker deterministik dan tiga
graf dari producer terrain tahap ini. Masing-masing memakai tiga start dan dua
mode, menghasilkan186 perbandingan, ditambah delapan consumer lookahead.
Sebanyak18 perbandingan merupakan subset graf terrain dan tidak dihitung ulang.

Start di luar batas di-clamp oleh flood. Start state 3 menghasilkan bitset kosong.
Flood biasa mengikuti mask arah; ia tidak memakai tes destination `flags&0xf5`
dari A*. Karena itu bitset ini belum diberi nama universal sebagai seluruh area
yang dapat dilalui pemain/NPC.

Wrapper `0x15bf840` melakukan dua hal tambahan:

1. Mencoba repair sumber dengan mask nol melalui `0x15bf8a0`, memakai koordinat
   request **sebelum clamping**. Edge timbal balik dapat dipulihkan ke tetangga
   yang memenuhi state, mask dan flag reciprocal.
2. Mengaktifkan predicate ekspansi setelah node pertama: direction bit 4, atau
   kedua koordinat berbeda dari origin dan node flag 4 clear. Byte enable kembali
   nol setelah fungsi selesai.

Model queue mencakup repair tersebut dan cocok dengan mask/bitset native.
Delapan kasus juga memasukkan bitset native ke filtered lookahead `0xc86970`.
Binding controller ke objek bitset disiapkan eksplisit; wiring constructor world
asli belum diklaim pulih dari komposisi ini.

Data: [npc_reachable_mask_native.json](../output/mechanics/npc_reachable_mask_native.json).

## Beberapa jalur evaluator aktif kini dijalankan hingga return

`0xc87710` berjalan lengkap untuk kondisi berikut, memakai route extractor,
lookahead dan RNG asli:

| Kondisi yang diuji | Next-state index | Status |
|---|---:|---:|
| Vec3 target terpilih nol | 1 | 3 |
| Endpoint aktif dengan jarak XZ di bawah threshold | 1 | 4 |
| Promosi waypoint terakhir | 4 | 1 |
| Melanjutkan endpoint eksplisit yang pending | 4 | 1 |
| Counter tunggu pada state 4 kedaluwarsa | 3 | 2 |

Tes kedatangan memakai **strict `<`**, sehingga nilai tepat pada threshold tidak
masuk jalur arrival yang diuji. Jarak hanya memakai X/Z; perubahan endpoint Y
tidak mengubah hasilnya. Promosi waypoint mengalikan grid X/Z dengan5 dan
**mempertahankan Y aktor**. List rute tetap utuh pada jalur-jalur ini.

Seratus kasus state tunggu memeriksa RNG state dan jeda:

```text
delay = 90 + 30 * floor(u32_draw * 5 / 2^32)
```

Nilai90/120/150/180/210 seluruhnya tercapai. Counter direset, posisi aktor disimpan
dan byte pending dihapus. Satuan waktu belum ditetapkan sebagai frame atau detik.

Enam kasus tambahan menjalankan setup `0xc862b0` melalui evaluator asli hingga
sebelum `0x1f067b0`, dengan argumen manager/next-state diperiksa. Generic FSM dan
callback transisinya belum dieksekusi. Hook observasi pada fungsi yang sudah
diterjemahkan emulator memakai refresh cache terjemahan; byte instruksi tidak
diubah dan tidak ada fungsi diganti stub.

Data: [npc_route_evaluator_native.json](../output/mechanics/npc_route_evaluator_native.json).

## Batas yang masih perlu dikerjakan

- Constructor preset14 byte menjadi runtime52 byte, loader PBC asli, live
  terraforming, surface type lain, overlay-height dan seluruh placement rule.
- Producer world lengkap, class byte, actor constraint/predicate yang terisi,
  serta binding parameter/tabel dan wiring constructor asli.
- Pengajuan request async, worker lifecycle, cancellation dan publikasi hasil.
- Sisa cabang evaluator, nonexpired wait/interruption predicate serta steering
  geometry pada `0xc88310`/`0xc88660` dan producer grid lokal `0xc88b80`.
- Integrasi posisi/physics, solver penetrasi/friksi/moving body, seluruh scheduler
  dan keputusan sosial/aktivitas NPC.
- Fokus lain tetap terbuka: koleksi/filter placement, transaksi crafting,
  unlock resep dan durability alat.

[Peta JSON terbaru](../output/mechanics/world_nav_bridge_map.json) menghubungkan
fungsi dan lapisan bukti dengan referensi terrain, ColGroundAttributeParam,
parameter NPC serta registry state. [Frontier tujuh area](../output/mechanics/continuation_frontier.json)
dan [perbandingan tahap](../output/mechanics/world_nav_bridge_progress.json)
mempertahankan status keseluruhan parsial.

## Reproduksi

Dengan ELF/SDK, indeks serta hasil ekstraksi baseline yang sama:

```bash
python tools/terrain_nav_flags_native.py
python tools/npc_reachable_mask_native.py
python tools/npc_route_evaluator_native.py
python tools/focus7_catalogue.py
python tools/mechanics_continuation.py
python tools/active_context_followup.py
python tools/resident_npc_followup.py
python tools/npc_navigation_followup.py
python tools/world_nav_bridge_followup.py
```

Generator historis dijalankan sebelum generator terbaru. Native helper/blok tetap
dibedakan dari simulasi game penuh; seluruh tujuh sistem belum dinyatakan selesai.
