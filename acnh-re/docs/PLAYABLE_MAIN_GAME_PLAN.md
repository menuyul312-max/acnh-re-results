# Rencana membangun gameplay utama ACNH yang bisa dimainkan

Status dokumen: rencana kerja, belum mengubah kode Godot. Target sumber adalah
Animal Crossing: New Horizons versi dasar 1.0.0 yang sudah dipetakan di repo RE.
Proyek Godot yang dibaca untuk audit berada di
`/workspace/analysis/acnh/project`; sesuai arahan, proyek itu tidak diubah.

## Sasaran

Tujuan jangka panjangnya adalah satu game single-player yang bisa dimainkan
dari New Game sampai loop pulau setelah cerita utama, dengan urutan progres dan
gerbang yang mengikuti ACNH. Batas pertama yang bisa dinyatakan selesai adalah
pemain memulai pulau, menyelesaikan alur pemukiman, mencapai konser K.K. pertama,
membuka Island Designer, lalu dapat melanjutkan bermain dan menyimpan pulau.

Pekerjaan sampingan—koleksi museum lengkap, seluruh dialog dan aktivitas
villager, kalender event lengkap, belanja katalog, multiplayer, dan paritas
visual semua aset—dikerjakan sesudah atau berdampingan hanya bila tidak
menghambat jalur utama. Fitur dari update 2.0 dan Happy Home Paradise berada di
luar target build berbasis dump 1.0.0 ini.

Reverse engineering memberi spesifikasi dan bukti; itu belum berarti mekanik
sudah menjadi gameplay Godot. Setiap sistem perlu dipasang ke satu state game,
diuji sebagai alur utuh, dan disimpan agar progres bertahan setelah game ditutup.

## Kondisi awal yang ditemukan

| Bagian | Yang sudah ada | Yang membuatnya belum menjadi game utuh |
|---|---|---|
| Proyek Godot | Scene pulau, pemain, NPC, inventory, crafting, UI, sistem ikan/serangga, loader data, dan EventFlow tersedia sebagai prototipe. | Main scene yang disetel adalah `IslandViewer.tscn`, yaitu viewer pulau/kamera; belum ada jalur New Game → bermain → save/load. |
| Sumber data | Tabel, preset, EventFlow, pesan, katalog aset, dan bukti fungsi native tersedia di repo RE. | `DataManager.gd` lama membaca `res://data/*.json` yang tidak tersedia, sementara beberapa subsistem memakai `generated/data`; belum ada satu kontrak loader yang menjadi sumber kebenaran semua gameplay. |
| Cerita | Alur dari prolog sampai konser K.K. dan Island Designer telah dipetakan dari EventFlow dan kode native. | Runner Godot masih memiliki banyak action/query yang tidak ditangani; sebuah flow yang termuat belum tentu dapat dijalankan sampai selesai. |
| Pemain dan dunia | Ada controller, generator/viewer pulau, object scene, dan beberapa helper terrain/navigation yang telah diuji secara terpisah. | Nilai gerak, spawn, interaksi, dan dunia di controller lama masih memakai konstanta/aturan sementara; collision scene lama juga membatasi jumlah instance. Belum ada integrasi physics, terrain, water, dan placement dalam satu runtime. |
| Item dan crafting | JSON/table joins, item payload, resep, dan beberapa helper native terverifikasi. Ada UI inventory/crafting. | Starter inventory dan sebagian transaksi ditulis tetap; pengurangan bahan → hasil craft → penuh inventory → rollback/save belum bekerja sebagai satu transaksi yang konsisten. Tool durability dan penggunaan target juga belum menyelesaikan seluruh jalur. |
| Waktu dan progres | Urutan pergantian hari serta syarat banyak fasilitas sudah dipetakan. | Godot memakai jam sistem langsung; belum ada clock game yang terkendali, batas hari 05:00, pemrosesan harian yang mengubah fasilitas, atau penyimpanan progres. |
| NPC dan dialog | Ada scene NPC, AI dasar, EventFlow JSON, serta rujukan pesan. | Wander dan dialog di beberapa scene masih contoh buatan; jadwal, event, kondisi cerita, interaksi, dan resident state belum disambungkan ke runtime yang sama. |
| Aset | Katalog nama, batas ukuran, material, UI, animasi, dan audio tersedia. | Model/tekstur/audio hasil konversi tidak berada di proyek yang diaudit; log pemeriksaan sebelumnya mencatat banyak resource hilang. Katalog metadata sendiri tidak menggantikan file visual/audio. |

Audit proyek Godot yang tersedia menyebut empat tes logika ikan/serangga lulus,
tetapi tes tersebut tidak membuktikan jalur cerita atau game loop. Viewer dapat
mulai secara headless, namun pemeriksaan yang sama mencatat permintaan model dan
audio yang hilang. Angka lulus helper di RE juga bukan persentase game selesai.

## Arsitektur minimum sebelum menambah banyak fitur

Satukan semua subsistem di bawah satu runtime dan satu state tersimpan:

1. `GameState`: pemain, pulau, tanggal/jam, mata uang, inventory, resep yang
   dipelajari, penduduk, fasilitas, struktur, dan EventFlag dengan AccessKey ACNH.
2. `GameClock`: waktu simulasi yang bisa diuji secara deterministik, termasuk
   pergantian hari pukul 05:00. Sinkronisasi jam nyata dapat menjadi mode normal,
   sedangkan debug/test memakai tanggal dan percepatan yang dapat dikendalikan.
3. `DataCatalog`: satu loader untuk ItemParam, recipe, ItemKind, preset, teks,
   NPC, dan parameter yang dipakai gameplay. Setiap record tetap membawa ID dan
   provenance tabel/field; data wajib yang hilang harus menghasilkan laporan
   jelas, bukan nilai default diam-diam.
4. `WorldRuntime`: membangun pulau dari preset yang dipilih, menghubungkan mesh,
   terrain, air, collision, structure, item, spawn, dan batas navigasi.
5. `Interaction/Inventory/Crafting`: satu kontrak item 8-byte dan transaksi
   inventory yang atomik. Tool action harus mengubah target dunia dan durability
   sesuai data/kode yang sudah dibuktikan.
6. `StoryRuntime`: gunakan EventFlowRunner/flags yang ada, tetapi aktifkan hanya
   flow yang terjangkau jalur utama terlebih dahulu. Setiap action/query utama
   harus punya implementasi atau status unsupported yang menghentikan tes;
   jangan membiarkan handler kosong dianggap sukses.
7. `SaveService`: format save Godot berversi, tulis dengan aman, dan uji
   round-trip. Untuk target pertama tidak perlu mengimpor/menulis format save
   Switch; yang penting state permainan Godot konsisten dan dapat dilanjutkan.
8. UI inti: HUD, dialog/pilihan, inventory, resep, objective/hint, telepon,
   kalender dan evaluasi pulau. Layout hasil ekstraksi menjadi acuan; implementasi
   awal boleh sederhana asalkan aksi dan state benar.

## Urutan tahap dan gerbang selesai

| Tahap | Hasil yang dibangun | Syarat untuk lanjut |
|---|---|---|
| 0. Kunci target dan build | Tetapkan Godot 4 yang didukung, build 1.0.0, struktur data runtime, aturan provenance/asumsi, perintah build dan test yang dapat diulang. Inventaris file aset yang tersedia dan yang harus dibuat dari dump lokal. | Project dapat dibuka dari satu perintah; loader menghasilkan laporan valid/missing; tidak ada perubahan pada sumber dump atau Godot di luar workspace pemilik. |
| 1. Vertical slice berjalan | Ubah entry scene menjadi game root; spawn pemain pada satu pulau awal; gerak, kamera, collision terrain, interaksi, pickup/drop, HUD minimum, dan save/load dasar. Pakai placeholder saat aset asli tidak tersedia. | Dari profil kosong pemain bisa berjalan dari tenda ke plaza, tidak menembus pantai/tebing/bangunan, mengambil dan menjatuhkan item, menutup lalu membuka game dan kembali dengan posisi/inventory sama. |
| 2. Hari pertama dan tutorial | New Game, pilihan karakter/belahan bumi/preset, kedatangan, penempatan tenda, NookPhone, dua villager awal, kumpulkan 10 ranting dan 6 buah, api unggun, tidur, lalu masuk ke hari kedua. | Alur prolog dapat diselesaikan tanpa debug flag; urutan dan flag cocok dengan flow sumber; restart tidak mengulang prolog untuk save yang sudah berjalan. |
| 3. Loop item dan DIY | Gather ranting/kayu/buah/batu/besi; pocket/stack/equip/use; resep belajar; workbench; craft tool/furnitur yang diperlukan cerita. Terapkan transaksi bahan-hasil secara atomik dan overflow inventory. | Satu resep cerita dapat dipelajari, gagal dengan bahan kurang tanpa mengubah inventory, sukses mengurangi jumlah tepat dan memberi hasil tepat satu kali; tool target dan durability tersimpan. |
| 4. Pinjaman dan fasilitas awal | Nook Miles yang cukup untuk biaya pindah 5.000, upgrade tenda ke rumah, donasi 5 makhluk dan penempatan tenda museum; jalur donasi sampai 20 dan pembangunan museum berjalan sebagai fasilitas sampingan. | Semua gate cerita berubah melalui interaksi/flag yang benar; pergantian hari membangun fasilitas pada hari yang tepat; pemain tidak dapat melewati pembayaran/syarat dengan memanggil UI saja. |
| 5. Nook's Cranny dan tiga plot | Kumpulkan 30 wood, 30 softwood, 30 hardwood, dan 30 iron; serahkan ke toko dan buka keesokan hari. Jalankan quest jembatan/tangga, tiga plot rumah, daftar furnitur dalam/luar, penyelesaian, dan pindah masuk tiga villager. | Ketiga plot hanya selesai setelah requirement tiap plot terpenuhi; penduduk yang dipilih tetap valid; jumlah rumah dan flag konsisten setelah reload. |
| 6. Resident Services dan campsite | Upgrade Resident Services, hadirkan Isabelle dan upacara; bangun campsite; jalankan pengunjung pertama dan rumahnya; buka pembelian plot tambahan sampai jumlah penduduk cukup untuk evaluasi. | Urutan pergantian hari/fasilitas bisa diuji dari save baru; campsite pertama dan penghuni baru tidak macet atau terduplikasi. |
| 7. Rating, konser K.K., dan tamat cerita utama | Implementasikan skor Nature/Life, minus points, jumlah rumah, evaluasi Isabelle, pembuka konser ≥3 bintang, jadwal konser, performance/credits, dan unlock Island Designer. | Skenario fresh-save mencapai konser K.K. pertama dengan syarat ACNH; pengujian membuktikan kasus tepat di bawah/tepat pada ambang dan reload di tiap gate. Ini menjadi milestone “main story playable”. |
| 8. Free play sesudah cerita | Pulau tetap terbuka sesudah credits; pemain dapat menyimpan, kembali, menempatkan/memindah barang, memakai alat, bermain dengan hari dan spawn dasar, serta memakai fungsi Island Designer minimum yang sudah divalidasi. | Setelah konser pemain tidak masuk dead-end; perubahan dunia, waktu, inventory, fasilitas, dan spawn bertahan setelah save/load. |
| 9. Perluasan game dasar | Tambahkan sistem sampingan bertahap pada state dan kontrak yang sudah stabil: koleksi museum, semua resep, rumah/HHA, toko/katalog/pesanan/surat, jadwal dan hubungan villager, musim/cuaca/event, turnip/Nook Miles/tournament, Mystery Tour, dan terraforming/air penuh. | Tiap kelompok punya uji sistem serta satu uji integrasi yang memainkan fitur melalui UI; status data-only/pseudocode/native/implemented dibedakan. |
| 10. QA dan fidelity | Uji berbagai tanggal/belahan bumi, save lama/migrasi, performa pulau, resource hilang, UI, audio, animasi, dan build ekspor. Bangun aset dari dump lokal melalui pipeline; ukur visual pada scene referensi. | Build bersih dapat memulai/menyelesaikan main story; tidak ada error/softlock/duplikasi item; daftar asumsi dan kegagalan aset terlihat; semua jalur inti punya regression test. |

Tahap 2–7 harus diuji bertahap; jangan menunggu semua 456 flow terimplementasi.
Mulai dari closure flow yang benar-benar dipanggil prolog sampai konser, lalu
tambah flow NPC/fasilitas yang diperlukan. EventFlow yang belum diperlukan tetap
dicatat sebagai unsupported dan masuk antrean side content.

## Pekerjaan RE yang langsung memengaruhi jalur utama

| Perlu sebelum milestone | Status bukti saat ini | Langkah implementasi/validasi |
|---|---|---|
| Loading preset pulau, terrain, pantai, dan collision | Schema/payload dan beberapa consumer sudah dipetakan; runtime loader, transform, seam, dan collision end-to-end masih terbuka. | Bangun satu preset utuh dahulu; bandingkan posisi unit dengan data; hilangkan batas collision 200 instance dan tes seluruh area berjalan. |
| Gerak dan interaksi pemain | Banyak helper gerak/collision diuji terisolasi; integrator, solver, input, dan placement runtime lengkap belum terbukti. | Sambungkan ke CharacterBody/controller dengan satuan dan timestep eksplisit; validasi fixture/native; jangan pertahankan angka hardcode controller lama tanpa tag asumsi. |
| Crafting dan barang cerita | Output/bahan resep terhubung dan beberapa producer/helper diuji; transaksi penuh, rollback, pocket/storage identity, serta durable save masih terbuka. | Implementasi transaksi yang menjaga bahan dan hasil atomik; verifikasi resep bridge, ladder, plot furniture, dan tool yang dibutuhkan main path. |
| Museum | Jalur donasi, marker, dan ambang dapat ditelusuri; row/key runtime dan real-save → next-day belum terbukti. Museum bukan syarat konser, jadi jangan jadikan ini blocker untuk milestone 7. | Buat adapter museum yang dapat dikoreksi dan label asumsi; lanjutkan RE untuk donor mapping/real save saat side lane museum dimulai. |
| Villager plots dan rumah | Flow plot/settler terbaca, tetapi query `NpcHouseNum`, `IsSettlerQuestOutsideComplete`, keputusan settler dan writer beberapa flag belum semua teruji end-to-end. | Implementasikan query dengan skenario boundary; cek daftar requirement dalam/luar; jalankan seleksi penduduk dengan tabel build yang sama. |
| Rating dan K.K. | Ambang skor dan jalur cerita diketahui dari flow/pseudocode; skor pulau belum diuji native end-to-end dan detail scheduling/performance masih memiliki batas bukti. | Uji scorer dengan pulau sintetis, validasi pembuka K.K., lalu jalankan timeline dari save yang sama sampai konser. |
| Day rollover dan save | Urutan processor harian sebagian besar dipetakan; clock/save gameplay Godot belum menjadi satu pipeline. | Simulasikan hari pada pukul 05:00 dengan prosesor berurutan dan save atomik; tes hari 0/1/2 serta restart di tengah konstruksi. |
| Dialog, HUD, dan aset | Struktur/teks/layout banyak tersedia; visual runtime penuh dan aset model/audio proyek belum tersedia/terhubung lengkap. | Ekspor subset teks/layout yang dibutuhkan main story; gunakan fallback placeholder agar sistem dapat diuji; bangun aset asli lokal bila dump tersedia. |

## Side content yang boleh menyusul

Tidak perlu menutup semua hal berikut sebelum alur K.K. dapat dimainkan:

- koleksi museum 100%, penilaian fosil, seni/gyroid dan semua display;
- HHA lengkap, semua renovasi rumah, katalog belanja, delivery/mailbox;
- friendship, semua topik percakapan, rumor, move-out dan seluruh jadwal villager;
- seluruh ikan/serangga dengan cuaca/waktu/event dan semua turnamen;
- kalender event tahunan, Nook Miles+ harian, Nook Stop, Mystery Tour;
- semua item, outfit, remake, furnishing interior, multiplayer/network;
- air terjun, aliran sungai, seluruh efek pantai dan editor terraforming penuh;
- semua model, animasi, shader, sound, dan pixel-perfect UI.

Sebagian dari ini punya bukti RE yang kuat; sebagian lain masih parsial. Kesiapan
data tidak sama dengan implementasi atau uji gameplay.

## Ukuran keberhasilan

Jangan menilai kemajuan dengan persentase jumlah fungsi native atau EventFlow.
Gunakan tiga gerbang yang bisa dimainkan:

1. **Vertical slice:** bergerak, berinteraksi, mengumpulkan, membuat item, save,
   reload.
2. **Main story playable:** fresh save → prolog → fasilitas/plot → 3 bintang →
   konser K.K. → Island Designer.
3. **Base-game breadth:** side systems masuk satu per satu tanpa merusak gerbang
   1 dan 2; tiap fitur punya uji dan status cakupan yang dapat dibaca.

Tidak ada estimasi durasi yang dapat dipertanggungjawabkan sebelum tahap 1
berhasil. Risiko terbesar bukan kurangnya peta RE, melainkan integrasi banyak
handler, state/save, runtime dunia, dan ketersediaan aset ke dalam satu loop yang
teruji.
