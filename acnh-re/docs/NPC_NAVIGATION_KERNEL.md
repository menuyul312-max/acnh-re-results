# Kernel navigasi NPC: A*, pemindahan rute dan pemilihan target

Snapshot ini dilanjutkan oleh [terrain runtime dan evaluator aktif](WORLD_NAV_BRIDGE.md).
Sebagian jalur world-height/flag, flood-fill, bobot default dan evaluator kini
memiliki bukti native tambahan; steering dan lifecycle async tetap terbuka.

Tahap setelah commit `c22e342` menambahkan **2.083 kasus native tanpa mismatch**.
Total helper/blok menjadi **1.134.009**, dari 1.131.926. Pemeriksaan BYML tetap
2.546.185 dan dihitung terpisah. Ini volume validasi konteks terkontrol, bukan
persentase RE seluruh game. Ketujuh sistem tetap parsial.

Kemajuan utamanya: **kernel A* asli sudah dieksekusi**, bersama callback biaya
dan heuristik aslinya, lalu hasil rute dihubungkan ke extractor dan pemilih
target native. Grid uji, status worker, pool node, biaya dan bitset disiapkan
secara eksplisit. Pembentukan grid dari pulau yang sedang berjalan, lifecycle
worker async dan gerakan NPC penuh belum dijalankan.

Semua alamat adalah VA ELF build ACNH 1.0.0. SHA-256 sumber:
`5bf707c3dc5dac0ad9635af7d336ec580f81c3f7876d0f55400d1900e3415d74`.
Godot dan input pengguna tidak diubah; model/sound tetap referensi katalog.

| Area | Sebelumnya | Bukti tahap ini | Kasus |
|---|---|---|---:|
| Pencari jalur | Callback NPC, wrapper request dan batas grid | Inisialisasi node, A*, biaya/heuristik asli, pembandingan Dijkstra dan blok worker | 1.269 |
| Hasil rute | Target fungsi pengambil hasil | Extractor lengkap, recycling pool, batas 256 node, handoff dan integrasi A* | 252 |
| Target gerakan | Kandidat controller | Selector target/lookahead lengkap pada context yang diuji, bitset, setup controller terbatas dan integrasi | 562 |

## A* memakai delapan arah dan antrean terbuka berupa linked list

`0x15bd700` menjalankan pencarian, `0x15bda30` memperluas tetangga.
Antrean terbuka diurutkan berdasarkan `f = g + h`; parent pointer dibentuk
menjadi rantai hasil dari start ke goal ketika target ditemukan. Struktur ini
cocok dengan A*, bukan sekadar inferensi dari nama state NPC.

Callback memakai vtable asli `0x3149c68`:

- `0x15c38a0`: jarak Euclidean antar sel dikalikan bobot kategori sel tujuan.
- `0x15c15a0`: jarak dasar antar dua koordinat sel.
- `0x15c1610`: heuristik jarak Euclidean ke goal.

Kategori biaya dibaca dari array global dengan stride 288. Kategori unsigned
0..7 memilih delapan bobot; nilai negatif atau di luar rentang memakai bobot0.
Byte functor+8 nonzero menghasilkan biaya edge nol. Pointer region opsional
pada functor tidak diaktifkan dalam pengujian tahap ini.

Bobot uji `[1,1.25,2,3,5,8,13,21]` adalah input rekonstruksi yang sengaja berbeda.
**Nilai ini bukan default gameplay yang berhasil dipulihkan.** Seluruh bobot
minimal 1 agar heuristik Euclidean tetap sesuai untuk pembandingan optimum.
Tidak ada klaim optimalitas pada mode biaya nol, bobot kurang dari 1 atau
callback lain.

Return yang dibedakan pada context ini: `1` untuk endpoint di luar batas,
`0` untuk pencarian yang habis tanpa rute, dan `2` untuk hasil rute terbentuk.
Start sama dengan goal menghasilkan satu node start/goal.

### Perbandingan independen dan pengecualian target

Ada **619 pencarian**: 107 skenario utama/acak deterministik, ditambah 512
variasi seluruh byte flag pada sel antara dan sel tujuan. Masing-masing juga
menjalankan inisialisasi grid native, sehingga ada 619 kasus initializer
terpisah. Dua puluh tiga kasus memeriksa callback biaya/heuristik, dan delapan
kasus memeriksa blok worker yang memanggil kernel serta menyimpan hasilnya.

Skenario meliputi grid terbuka, dinding dengan celah, dinding penuh, biaya tinggi
yang membuat jalan memutar lebih murah, origin nonzero, endpoint invalid,
start/goal yang diblokir, dan 96 grid acak kecil. Implementasi Dijkstra terpisah
memakai heap; hasil dibandingkan untuk reachability, legalitas langkah, biaya
f32 yang dijumlahkan dan optimum. Hasil: 362 sukses, 255 tanpa rute, 2 endpoint
invalid, tanpa mismatch.

Node antara ditolak ketika state node bernilai 3 atau `flags & 0xf5` nonzero.
Namun **node tujuan melewati penolakan ini**; start juga dimasukkan langsung.
Arti gameplay setiap bit tersebut belum diberi nama tanpa producer yang terbukti.

Pada direction mask yang dibuat initializer dan dipakai uji, langkah diagonal
memeriksa node tujuan tanpa mewajibkan dua tetangga ortogonal bebas. Ini tidak
membuktikan NPC game dapat menembus sudut objek: producer world dapat menghapus
bit arah atau menambah pembatas lain sebelum kernel dijalankan.

Data: [npc_pathfinding_native.json](../output/mechanics/npc_pathfinding_native.json).

## Layout node dan graf yang dikonsumsi kernel

| Struktur | Field yang terbukti dikonsumsi |
|---|---|
| Header graf | Origin X/Z u16 +0/+2, width s32 +0xc, height s32 +0x10, jumlah node u64 +0x18, array node +0x20, open-list head +0x28, result head +0x38 |
| Node 40 byte | Koordinat u16 +0/+2, direction mask +4, flags +5, search state +6, g f32 +8, f-score f32 +0xc, parent +0x10, link open/result +0x18 |

Initializer asli `0x15bc0c0` mengisi koordinat dan mask batas. Pada dimensi satu
sel, cabang first-edge/else-last-edge dapat mempertahankan bit keluar, tetapi
expander tetap memeriksa batas koordinat sebelum mengakses tetangga.
Ini layout field yang dipakai consumer, bukan klaim seluruh field class selesai.

## Extractor mempunyai kontrak boolean dan status yang berbeda

`0x15c3570` hanya menerima worker state 2 dengan requester ID32-bit yang cocok.
ID tidak cocok atau state lain mempertahankan output/list. Untuk hasil yang
diterima, urutannya adalah:

1. Lepas node list lama dan kembalikan ke free pool memakai instruksi list serta
   destructor koordinat asli.
2. Tulis status ke output, lalu reset ID dan state worker ke 0.
3. Bila status 2 dan terdapat langkah setelah start, lewati node start, ambil
   paling banyak 256 node awal, balik urutannya, lalu isi pool sampai kapasitas.

Urutan maju list hasil bergerak dari ujung prefix menuju dekat start. Membaca
list dari belakang memberi urutan langkah dari dekat start menuju tujuan.

**Boolean tidak menyatakan seluruh node sudah tersalin ke pool.** Satu sampai
256 langkah menghasilkan true meskipun kapasitas pool nol atau terlalu kecil.
Lebih dari 256 langkah menghasilkan false, tetapi prefix terbatas tetap disalin.
Rute tanpa langkah setelah start menghasilkan false dan list kosong.

Blok parent `0xcb5518` membaca **status output2**, mengabaikan boolean extractor,
menambahkan flag 4 dan meneruskan argumen ke `0xc862b0`. Pengujian berhenti sebelum
fungsi inisialisasi child itu berjalan. Jadi empty/oversized route dapat memberi
boolean false namun tetap mencapai handoff dalam context yang disiapkan.
Ini kontrak consumer yang teruji, bukan klaim bug gameplay yang sudah terbukti.

Ada 130 kasus extractor/pool, 80 guard ID/state/status, 36 blok parent dan enam
integrasi. Pada enam integrasi, rantai hasil A* asli dipakai langsung tanpa
diganti path sintetis di antara pencarian, extractor dan handoff.

Data: [npc_route_handoff_native.json](../output/mechanics/npc_route_handoff_native.json).

## Pemilih target memakai lookahead serta bitset eligibility

`0xc86650` dijalankan lengkap pada context reference/ID yang cocok. Bila
child+0x121 nonzero, fungsi mengembalikan endpoint eksplisit. Selain itu, fungsi
memilih hingga node ke-10 pada rute. Rute pendek yang habis memakai endpoint
eksplisit nonzero, atau node terakhir yang dikonversi ketika endpoint nol.
Cabang resolusi actor-reference lain tidak diuji di tahap ini.

`0xc86970`, yang dipanggil evaluator rute `0xc87710`, juga berjalan lengkap:

- Mode tanpa filter memilih node ke-`max(1,budget)` jika tersedia.
- Mode berfilter memilih node eligible pertama pada atau setelah posisi itu.
  Budget menghitung node yang dikunjungi, termasuk node yang tidak eligible.
- Filter memeriksa batas koordinat grid dan bitset melalui `0x166ab50` asli.
- Jika rute habis, endpoint eksplisit nonzero menggantikan kandidat terakhir.
- Iterator berubah, tetapi node tidak dilepas dari list oleh selector ini.

Konversi koordinat menggunakan `0x52b4c0`: X/Z dikalikan5, sedangkan Y tetap
nilai nol pada jalur node yang diuji. Endpoint eksplisit mempertahankan Y-nya.
Makna eligibility dalam world asli belum dipastikan; pengujian ini belum
membuktikan line of sight atau penghindaran collision.

Ada 56 kasus selector default, 98 lookahead tanpa filter, 392 lookahead berfilter,
12 blok setup controller serta empat rantai A* → extractor → selector asli.
Kasus batas mencakup panjang rute9/10/11, budget0/1/2/9/10/11/31, endpoint
kosong/nonzero dan bitset semua/kosong/ganjil/hanya node terakhir.

Setup `0xc862b0` diuji dari entry hingga sebelum `0xc87710`. List, endpoint,
flag dan copy 32 byte parameter terverifikasi. Lima float efektif ketika argumen
parameter null adalah `[16,25,-1,-1,-1]`; dengan argumen terisi, lima float itu
berasal dari parameter yang disalin. Arti seluruh parameter dan satuannya belum
ditetapkan. Evaluator state dan integrator gerakan belum dijalankan.

Data: [npc_route_target_native.json](../output/mechanics/npc_route_target_native.json).

## Yang masih terbuka

NPC/navigasi kini memiliki kernel pencarian dan beberapa consumer yang terbukti.
Sistem penuh masih memerlukan pembuktian:

- Terrain/collision/actor pulau menjadi direction mask, node flags, kategori
  biaya dan eligibility bitset. Belum ada binding nama tabel ke bobot uji.
- Pengajuan request async, lifecycle worker, cancellation dan publikasi hasil.
- Evaluator state aktif, steering, pembaruan posisi dan respons collision.
- Prioritas scheduler, keputusan aktivitas/sosial dan semua transisi AI.
- Cabang reference lain, seluruh makna parameter dan kondisi keterjangkauannya.

Frontier baru memuat target `0x15c3390`, `0x15c24a0`, `0x15c2910`, `0x15bf150`,
`0x15c3190`, `0xc87710` dan `0xc87ea0`. Blok worker/setup yang diuji tidak
menjadi klaim bahwa seluruh fungsi/world worker tersebut telah berjalan.

Bagian fokus lain tetap terbuka: solver penetrasi/friksi/moving body, integrasi
gerak penuh dan landing, constructor/mutasi terrain, PBC asli serta loader,
registry/filter placement, dan transaksi crafting/unlock/durability.
Model/sound tetap cukup memakai katalog untuk kelanjutan riset algoritme ini.

[Peta kernel JSON](../output/mechanics/npc_navigation_kernel_map.json) menghubungkan
fungsi, layout, bukti, registry state, parameter dan graf AI yang sudah tersedia.
[Frontier tujuh area](../output/mechanics/continuation_frontier.json) dan
[perbandingan tahap](../output/mechanics/npc_navigation_progress.json) menyimpan
bagian yang terbukti dan belum terbukti tanpa persentase penyelesaian.

## Reproduksi

Dengan ELF, indeks, input SDK dan hasil ekstraksi baseline yang sama:

```bash
python tools/npc_pathfinding_native.py
python tools/npc_route_handoff_native.py
python tools/npc_route_target_native.py
python tools/focus7_catalogue.py
python tools/mechanics_continuation.py
python tools/active_context_followup.py
python tools/resident_npc_followup.py
python tools/npc_navigation_followup.py
```

Generator historis dijalankan sebelum generator terbaru. Semua fungsi yang
disebut native menggunakan instruksi asli tanpa stub pengganti. Hasil berasal
dari emulator dengan konteks yang dinyatakan, bukan observasi game penuh.
