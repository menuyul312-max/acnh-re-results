# Follow-up rumah dan HHA

Tanggal: 6 November 2026. Cakupan dokumen ini mengikuti bukti per subbagian. Fungsi native tunggal tidak cukup untuk menyimpulkan seluruh evaluasi HHA.

## 1. Dispatcher enam mission HHA — terbukti terbatas

`0x7b4330` membaca enam bit rendah pada `state + 0x140`. Urutannya berkaitan langsung dengan referensi native `cPlayer:HappyHomeMission1` sampai `cPlayer:HappyHomeMission6` di `/workspace/acnh-re/output/index.sqlite` dan definisi Jepang di `output/gameplay/flag_index.json`. Semua flag bernilai Bool (`default=0`, `max=1`) dan tidak memiliki penulis EventFlow yang terindeks.

Reproducer menjalankan instruksi asli AArch64 `0x7b4330` dari NSO bersama, sambil mengontrol status hasil baca flag. Untuk setiap pasangan mask enam bit (`active_mask`, `completed_mask`), ia memeriksa urutan pembacaan, ordinal pertama yang belum selesai, argumen pada pemanggil mission `0x7b5540`, pemanggilan setter flag `0xf4b0d0`, dan nilai balik. Ada 4.096 pasangan, ditambah satu kasus yang hanya menyalakan bit di atas enam. Hasil: 0 mismatch; 3.367 kasus dispatch menghasilkan ordinal 0–5, sedangkan 729 kasus tanpa flag aktif yang belum selesai kembali 0. `param2` diteruskan ke `0x7b5540` sebagai nilai 32-bit rendah.

Native yang dijalankan adalah dispatcher `0x7b4330`. Stub hanya dipasang pada tiga batas: getter flag `0xf4aff0` mengembalikan status terkontrol, setter flag `0xf4b0d0` mencatat nama dan nilai yang diminta, dan penerima `0x7b5540` mencatat argumen tanpa efek game. Karena getter/setter tidak berjalan ke penyimpanan save asli dan penerima tidak dijalankan, bukti ini memverifikasi cabang, urutan, serta argumen dispatcher saja. Ini tidak mengungkap syarat yang menyalakan keenam bit mission.

Artefak rinci dan reproducer:

- `output/gameplay/house_hha_followup/hha_mission_dispatch_native.json`
- `tools/hha_mission_dispatch_native.py`

Jalankan dari root worktree dengan dependency cache bersama:

```bash
PYTHONPATH=/workspace/acnh-re/.deps python acnh-re/tools/hha_mission_dispatch_native.py
```

Sumber native: ExeFS `main` SHA-256 `f8d248109ff72999b4600ae3749f8c7397fb960f7ad3ab8dee3018ae9e14e900`; ELF `A_logic/main.elf` SHA-256 `5bf707c3dc5dac0ad9635af7d336ec580f81c3f7876d0f55400d1900e3415d74`. Metadata fungsi, panggilan langsung, dan nama flag dibaca dari indeks SQLite bersama secara read-only. RomFS tambahan tidak dipakai untuk dispatcher ini.

## 2. Pesanan upgrade dan nominal pinjaman — terbukti di EventFlow

`SNPC_rco_10_Common_UpgradeMyhome:RcoCmnProcessUpgradeMyhome` memasang `HouseOrder1`–`HouseOrder7` menurut `PlayerHouseLevel` 1–7. Nama flag di `EventFlagsHouseParam` menjelaskan urutan bentuk rumah: tenda→6×6, 6×6→8×8, penambahan ruang belakang, ruang kiri, ruang kanan, lantai dua, lalu basement.

Setelah itu, `SNPC_rco_03_ChkAfterRemodel:Root` hanya masuk bila `cPlayer:RcoAfterHouseRemodel` ON, lalu memilih nominal melalui `PlayerHouseLevel`:

| Level yang dibaca flow | Bells pada `PlayerSetLoan` |
|---:|---:|
| 2 | 98.000 |
| 3 | 198.000 |
| 4 | 348.000 |
| 5 | 548.000 |
| 6 | 758.000 |
| 7 | 1.248.000 |
| 8 | 2.498.000 |

Ini membuktikan nominal yang dikirim EventFlow setelah cabang remodel, bukan nilai saldo save sesudah action berjalan. Registration EventFlow menyatakan `PlayerSetLoan` menerima `Bells:int`. Kode native kandidat di vtable slot action mengarah melalui `0xeff7f0` ke `0xeaf1c0`, dan `0xeaf1c0` merujuk `SetLoan`, `CurLoan`, `RepayMoney`, serta `IsRepayByDeposit`. Slot masih berstatus peran belum terurai dan storage save tidak diemulasikan, sehingga hubungan native ini dicatat sebagai static linkage.

Alur bayar juga terlihat di EventFlow: ATM memeriksa `PlayerLoanRepaying`, lalu cabang `PlayerHasLoan` case 1 dapat memesan demo `Player_GetDemo_Once:Get_FinishLoan`. Demo itu mematikan `PlayerLoanRepaying`, menyalakan `PlayerLoanFinish1st`, dan menambah achievement `RepayLoan`. Obrolan `SNPC_rco_04_ChkFinishLoan` kemudian menandai selesai sepenuhnya dengan `PcHousingLoanFinish` saat `PlayerHouseLevel` 8. Arti hasil native `PlayerHasLoan` case 1 belum diperiksa.

Penulis native `RcoAfterHouseRemodel` kini terpetakan. Jalur pembaruan rumah `0xf545f0` memanggil `0xf96960`; fungsi itu mengunjungi delapan blok state berjarak `0x26400` dan meneruskan tiap blok ke `0xf949c0`. Fungsi terakhir menyimpan level awal, menjalankan helper remodel sesuai level, lalu membandingkan level awal dan hasilnya. Jika berubah, ia memanggil setter `0xf4b0d0` untuk `RcoAfterHouseRemodel` menggunakan byte state pada `param1 + 0x263d0`, dan juga memperbarui `ExtendMyHome`. Pemanggil `0xf545f0` adalah `0xf53a70`, jalur pembaruan harian yang juga memproses flag seperti `TodayCreateVillage` dan `PlayToday`. Ini membuktikan sinyal flag saat perubahan level terdeteksi oleh updater; kode yang ditelusuri tidak memuat hitung mundur atau angka jumlah hari renovasi. Gate EventFlow tetap mematikan flag setelah dialog.

Artefak: `output/gameplay/house_hha_followup/house_loan_eventflow.json`. Reproducer statisnya:

```bash
python acnh-re/tools/house_loan_evidence.py
```

Untuk melihat graf langsung dari data decode bersama, jalankan:

```bash
python acnh-re/tools/gameplay_flow.py --output-root /workspace/acnh-re/output tree SNPC_rco_03_ChkAfterRemodel --entry Root
```

## 3. Evaluasi grade, skor, tema, dan surat HHA

### Cabang bucket skor — terbukti terbatas

`0x7b29d0` memanggil `0x7b4fc0` pada PC `0x7b2bec`. Cabang native `0x7b4fc0` membaca record pada `param1 + 0xb10`. Untuk input nonnegatif yang diuji, field `+0x150` dibagi empat dengan `>> 2`, dibagi field `+0x14c`, lalu dikali 100. Native memilih bit kategori internal 5 untuk rasio di bawah 20, bit 4 untuk 20 sampai kurang dari 50, dan bit 3 untuk 50 ke atas. Nama bucket ini belum dapat dipetakan ke grade yang ditampilkan.

Reproducer menjalankan instruksi asli `0x7b4fc0` dengan record terkontrol. Pada baseline field lain yang disetel ke keadaan netral, sembilan probe melintasi ambang 20 dan 50, masing-masing dengan flag `cPlayer:HappyHomeMission1` ON/OFF pada batas relevan. Hasil mask yang diamati: bucket 5 menghasilkan `0x7822` baik flag ON maupun OFF; bucket 4 menghasilkan `0x7812` saat ON dan `0x7802` saat OFF; bucket 3 menghasilkan `0x780a` saat ON dan `0x7802` saat OFF. Jadi bit 3 dan 4 ditekan ketika getter mission mengembalikan false, sedangkan bit 5 tetap ada. Ada 9 kasus dan 0 mismatch.

Getter `0xf4aff0` dikontrol oleh harness untuk mengembalikan nilai flag yang diminta; receiver `0x7b6470` hanya mencatat mask lalu menghentikan pemrosesan berikutnya. Helper lain di jalur ini juga distub agar mask native diteruskan ke receiver. Aritmetika rasio dan pemilihan bit di `0x7b4fc0` berjalan sebagai instruksi NSO asli. Uji memakai `param2=0`, sehingga lookup `GetSRankonHHA` pada cabang `param2` nonnol tidak dijalankan. Bukti ini tidak menentukan skor penuh per ruangan, bobot tema, atau nama grade.

Artefak dan reproducer:

- `output/gameplay/house_hha_followup/hha_score_bucket_native.json`
- `tools/hha_score_bucket_native.py`

Jalankan dari root worktree:

```bash
PYTHONPATH=/workspace/acnh-re/.deps python acnh-re/tools/hha_score_bucket_native.py
```

### Pembilang luas +0x150 — footprint objek terbukti terbatas

Di `0x7b1fe0`, ketika jalur item berada pada `iVar24 == 0` dan predicate native `0xaa7f80` lolos, blok `0x7b2694` meminta dua extent dari record objek: `0x52c270` menghasilkan `maxX + 1 - minX` dari offset `+0x10/+0x20`, sedangkan `0x52c290` menghasilkan `maxZ + 1 - minZ` dari `+0x14/+0x24`. Instruksi `MADD/STR` kemudian menambah `width × depth` penuh ke `+0x150` pada record evaluasi pemain. Scan 0x400 sel berjalan x-dahulu di setiap baris lalu menaikkan z; indeks bitmap adalah `x_offset + z_offset × width`. Sebelum resolver dipanggil, scan melewati anchor yang bitnya sudah terpasang. Untuk descriptor objek valid, penambahan skor saja yang dibatasi `iVar24 == 0` dan predicate `0xaa7f80`; sesudah blok itu, evaluator tetap menandai seluruh footprint objek di bitmap meskipun predicate skor gagal. Karena itu, objek valid yang ditemukan lebih awal dapat menutupi anchor objek berikutnya bila anchor tersebut berada di footprint-nya. Jika kedua anchor tidak saling tertutupi, setiap objek yang lolos predicate menambah persegi panjang penuh dan irisan footprint tidak dikurangi dari akumulator. Sentinel kosong/lookup tambahan yang gagal hanya menandai anchor.

Urutan scan ini menentukan objek anchor berbeda mana yang sempat diperiksa, tetapi belum menentukan pemenang bila dua record menempati koordinat yang sama. Resolver `0xb13fe0 → 0x52f220 → 0x52d640` mengambil satu nilai sel; nilai sentinel `-3` memicu satu lookup fallback pada grid lain, bukan enumerasi semua objek pada koordinat itu. Writer generik `0x52df00` memang mengganti satu nilai sel dan updater persegi `0x52e360` memanggilnya, tetapi xref statis hanya mengaitkan writer itu dengan `0x52d980`/`0x52e360`; urutan pemuatan furniture ke grid rumah tidak tersambung ke jalur ini. Pemenang same-cell tetap memerlukan bukti urutan population grid atau capture runtime.

Guard `0xaa7f80` memeriksa field item nonnol, dua hasil lookup properti, dan bit 5 byte item `+0x0a`; arti properti dan bit itu di sini masih belum terpetakan.

Native harness menjalankan dua extent helper, `MADD`, dan store asli pada lima pasangan batas koordinat, termasuk koordinat negatif dan accumulator awal nonnol. Hasil: 5 kasus, 0 mismatch. Harness sengaja mulai sesudah eligibility guard dan tidak menjalankan item lookup atau predicate `0xaa7f80`.

Artefak dan reproducer:

- `output/gameplay/house_hha_followup/hha_coverage_accumulator_native.json`
- `tools/hha_floor_coverage_accumulator_native.py`

### Penyebut luas rumah +0x14c — sumber semantik `PlayerHouseLevel` terbukti; label lokal belum ada

`0x7b1dd0` memeriksa slot pemain 0–7 melalui `0x1205870(index)` dan meneruskan slot aktif ke evaluator `0x7b1fe0(index)`. Stride `0x160` pada tabel internal adalah record evaluasi per slot pemain/rumah; pemindaian delapan ruang berlangsung di dalam evaluator. Evaluator membaca selector `u32` dari node save yang diakses lewat global `0x33dc730` dan mengganti nilai di atas 8 dengan 0. Sumber lokalnya adalah descriptor empat byte `0x17cd80` (8 instance; sample data `0x2dbaa0`), pada awal record rumah pemain.

Makna selector kini terikat ke query terdaftar `EventFlowQueryPlayerHouseLevel`: slot getter 6 di vtable `0x3058150` menuju `0x42bfb0`, yang membaca melalui global accessor `0x33dc730` yang sama dengan evaluator HHA. Getter itu menormalkan raw 1–8 menjadi level 0–7, dan nilai nol/tidak valid menjadi 0. Ini membuktikan bahwa descriptor yang dibaca evaluator adalah sumber nilai semantik `PlayerHouseLevel`, bukan hanya dugaan dari geometri. Crosswalk offset/ukuran terhadap file schema eksternal `save_schema_111_103` memberi kandidat tepat `SaveLand.PlayerHouseList.HouseList[0].HouseLevel`; label descriptor lokal tetap tidak ditemukan, karena layout 1.0.0 menyimpan tipe dan ukuran tanpa nama RTTI.

Di `0x7b1fe0`, setelah lookup state dan setter `HHAGradeMailFlag`, selector 2–8 menjalankan switch native di `0x7b2144–0x7b2248`. Switch menulis denominator `+0x14c` dan count `+0x154` pada record pemain:

| Selector | `+0x14c` | `+0x154` | Interpretasi geometri yang cocok |
|---:|---:|---:|---|
| 2 | 36 | 1 | 6×6 |
| 3 | 64 | 1 | 8×8 |
| 4 | 100 | 2 | 8×8 + 6×6 |
| 5 | 136 | 3 | 8×8 + 2×(6×6) |
| 6 | 172 | 4 | 8×8 + 3×(6×6) |
| 7 | 232 | 5 | 8×8 + 3×(6×6) + 10×6 |
| 8 | 292 | 6 | 8×8 + 3×(6×6) + 2×(10×6) |

Pola luas itu cocok dengan pertumbuhan denah rumah dan konsisten dengan nilai `PlayerHouseLevel` yang dibaca getter terdaftar. Label descriptor lokal tetap tidak diketahui meskipun semantiknya terbukti. Native harness menjalankan dispatch dan store asli untuk ketujuh selector dengan 0 mismatch; ia mulai setelah lookup/flag-setter dan berhenti sebelum helper `0x7b7c30`.

Artefak dan reproducer:

- `output/gameplay/house_hha_followup/hha_house_area_denominator_native.json`
- `tools/hha_house_area_denominator_native.py`

Jalankan dari root worktree:

```bash
PYTHONPATH=/workspace/acnh-re/.deps python acnh-re/tools/hha_house_area_denominator_native.py
```

### Skor item menuju akumulator HHA — terbukti terbatas; kait ke bucket masih terbuka

Evaluator `0x7b1fe0` memproses item untuk satu slot pemain dan memanggil `0x7b36b0` untuk item yang lolos pemeriksaan. Instruksi native `0x7b36b0` memanggil helper item `0xab9050` di PC `0x7b37b8`, lalu menambahkan nilai baliknya ke record evaluasi pemain pada `param1 + 0xb10`, offset `+0x24`. Pseudocode helper `0xab9050` mencari hash field `0xd62525d0`; hash ini sama persis dengan kolom `ItemFrom:HHABaseScore` pada schema resolved (offset 6, lebar 2 byte). Reproducer menjalankan instruksi asli `0x7b36b0` dengan nilai balik helper terkontrol 0, 200, dan 499; ketiganya menambahkan nilai yang sama ke `+0x24`, sementara `+0x150` tetap pada sentinel uji. Ada 3 kasus dan 0 mismatch. Identitas sumber skor dibuktikan lewat kesamaan hash schema; harness tidak menjalankan lookup tabel item sebenarnya.

Di evaluator `0x7b1fe0`, setelah pemindaian, native membentuk `+0x136c` sebagai jumlah 12 akumulator kategori pada `+0x24` sampai `+0x50`. Cabang bucket `0x7b4fc0` membaca field berbeda: `+0x150` sebagai pembilang dan `+0x14c` sebagai penyebut. Untuk pembilang nonnegatif, ia membulatkan luas ke atas per empat sel lewat `(+0x150 + 3) >> 2`, membagi hasilnya dengan `+0x14c`, lalu mengalikan 100. Ambang internal yang terlihat adalah 20 dan 50; konstanta float 100.0 dan 50.0 berada di `0x29d6408` dan `0x29d62ac`. Harness bucket lama menguji scalar `+0x150` langsung dengan instruksi `0x7b4fc0`.

Pembacaan silang dekompilasi memberi jembatan tambahan dari akumulator barang ke mask report. Evaluator `0x7b1fe0` memanggil akumulator item `0x7b36b0` di PC `0x7b265c`; akumulator itu memanggil `0xab9050` di PC `0x7b37b8` dan menambah nilai baliknya ke field kategori saat ini. Setelah `0x7b39c0`, evaluator menyimpan total lama dari konteks pada `+0x136c`, menghitung ulang jumlah 12 field kategori `+0x24..+0x50`, lalu menulis selisih total baru dan lama ke record evaluasi pada `+0xd8 + 4*min(indeks_area,5)`. Bucket `0x7b4fc0` memindai nilai `+0xd8` sebanyak jumlah pada `+0x154`, memilih indeks nilai maksimum/minimum ke `+0x155/+0x156`, lalu menyalakan mask `0x100/0x200`. Receiver `0x7b6470` mengubah bit itu menjadi record kode `0x33/0x34`, yang kemudian dibangun dan dimasukkan ke antrean bersama.

Ini membuktikan jalur statis terbatas `HHABaseScore → akumulator kategori → total sementara +0x136c → delta per area +0xd8 → dua rincian mask report`. Nilai `+0x136c` sendiri tidak dipetakan ke threshold rank yang ditampilkan; report memakai perubahan skor per area dan indeks area tertinggi/terendah. Penelusuran tersebut belum dijalankan sebagai satu harness native end-to-end.

Karena akumulator item `+0x24..+0x50`/total `+0x136c` dan pembilang bucket `+0x150` merupakan field berbeda, bukti yang ada belum menghubungkan nilai helper item ke scalar bucket. Formula luas yang terbukti menghitung footprint persegi panjang yang diterima, bukan union sel untuk objek yang overlap; pengaruh overlap nyata tetap perlu diuji pada ruangan tersinkron. Bobot tema, hubungan total `+0x136c` dengan classifier rank, dan pengikatan ordinal classifier ke objek grade UI tetap **terbuka**; cutoff numerik native per level terbukti pada subseksi berikutnya.

Reproducer dan hasil untuk akumulator item:

- `output/gameplay/house_hha_followup/hha_item_score_accumulator_native.json`
- `tools/hha_item_score_accumulator_native.py`

Jalankan dengan dependency cache bersama:

```bash
PYTHONPATH=/workspace/acnh-re/.deps python acnh-re/tools/hha_item_score_accumulator_native.py
```

### Ambang rank terbukti; formula skor item dan surat masih terbuka

**Ambang grade S/A/B per level rumah kini terbukti pada instruksi native.** Evaluator `0x7b1fe0` memanggil classifier `0x7b3ff0` pada PC `0x7b29b4` setelah memindai kategori barang. Classifier menjumlahkan dua belas nilai kategori pada record `+0x24..+0x50` menjadi total signed-i32 `+0x110`, lalu memilih ordinal hasil di `+0x08` menurut raw `PlayerHouseLevel` 2–8. Nilai selector lain keluar tanpa mengganti ordinal. Tabel branch native tujuh entri memetakan level rumah ke dua batas skor berikut:

| Raw `PlayerHouseLevel` | B: `+0x110` | A: `+0x110` | S: `+0x110` |
|---:|---:|---:|---:|
| 2 | 0–9.999 | 10.000–14.999 | ≥15.000 |
| 3 | 0–16.999 | 17.000–22.999 | ≥23.000 |
| 4 | 0–24.999 | 25.000–34.999 | ≥35.000 |
| 5 | 0–37.999 | 38.000–46.999 | ≥47.000 |
| 6 | 0–49.999 | 50.000–59.999 | ≥60.000 |
| 7 | 0–63.999 | 64.000–74.999 | ≥75.000 |
| 8 | 0–79.999 | 80.000–89.999 | ≥90.000 |

Di output native, ordinal `2` dipakai sampai batas B, `1` untuk rentang A, dan `0` di atas batas A. Jalur `0x7b4a20` memeriksa `record +0x08 == 0` dan memperbarui achievement native `GetSRankonHHA`, sehingga ordinal 0 terikat langsung ke S. Dua helper UI `0xac2e30` dan `0xac3360` menggunakan ordinal zero-based `+1` untuk resource `STR_HHA_Rank`; pesan US English memetakan label `001/002/003` ke `S/A/B`. Reproducer menjalankan classifier asli dengan 33 kasus batas/level: tanpa mismatch. Artefak: `output/gameplay/house_hha_followup/hha_rank_threshold_native.json`; jalankan `PYTHONPATH=/workspace/acnh-re/.deps python acnh-re/tools/hha_rank_threshold_native.py`.

Indeks statis report memberi kaitan terpisah antara ordinal dan kandidat surat. `0x7b4fc0` memasukkan bit `1 << (record +0x08)` bersama bit kondisi report. Native memanggil `0xf53450(0,popcount(mask))`; helper ini mengambil state empat kata pada `0x36e9510`, memajukannya lewat langkah xorshift `0x1aaa0e0`, lalu memetakannya ke rentang kandidat. Hasilnya diteruskan sebagai ordinal bit ke `0x198b630`, yang mengambil bit ke-n. Hanya jika kandidat rank terpilih, dispatcher `0x7b6470` memetakan indeks `0/1/2` ke kode record Grade `40/41/42`. Arsip `MAIL_SP_HHA_Grade` memuat label `040–042` dan body `140–142`; body tersebut menyebut S/A/B. Bukti ini mengikat ordinal ke kode kandidat, tetapi tidak membuktikan bahwa setiap evaluasi membuat surat rank atau bahwa formatter mengubah label dasar `040–042` menjadi body `140–142`.

Yang masih terbuka ialah rumus penuh yang membentuk dua belas nilai kategori dari item, bonus tema/situasi, dan kait hasil classifier ke grade yang benar-benar tampil pada UI/mail. Klasifikasi rank kini diketahui; harness hanya memasok total kategori terkontrol dan level rumah, bukan evaluasi ruangan/save yang hidup.

Skema resolved `ItemParam` memuat `ItemHHATheme`, `ItemHHACategory`, `ItemHHASet`, `ItemHHASituation1/2`, `ItemHHAPart`, `ItemHHASeason`, dan `ItemHHADirection`; `ItemFrom` memuat `HHABaseScore`. Archive US English berisi 3 label `STR_HHA_Rank`, 25 tema, 19 set, 24 situation, dan 7 lokasi ruang. Fungsi `0xac2e30` memakai ID string Rank/RoomLocation/Set/Situation/Theme, dan `0xac3360` memakai Rank; trampolines ke keduanya muncul dalam dua code-pointer array yang juga memuat fungsi UI lain. Ini membuktikan sumber teks lokal UI, bukan kait langsung dari record evaluator ke objek layar. Rank thresholds sudah dipetakan dari classifier native, tetapi bobot yang mengubah field item menjadi dua belas kategori masih terbuka. Flag `cLifeSupportAchievement:GetSRankonHHA` bernama Jepang “mendapat S di HHA”; cabang `record +0x08 == 0` pada `0x7b4a20` memperbarui flag itu, mengaitkan ordinal nol classifier dengan S. Bit internal 3/4/5 di report bucket adalah kategori report lain; tidak terbukti sebagai grade S/A/B. Jembatan `+0x136c → +0xd8 → mask report` di atas memberi hubungan terbatas ke rincian laporan; pembaca downstream yang mengubah report ke layar tetap belum diketahui.

### Ambang progres poin HHA — terbukti terbatas; bukan ambang rank

Fungsi `0x7b4720` memeriksa nilai signed-i32 pada record evaluasi `+0x110` terhadap ambang 10.000, 20.000, 30.000, 50.000, 70.000, 100.000, dan 150.000. Jika indeks progres tersimpan pada member berukuran 0x23c byte masih di bawah band yang telah dicapai, ia menaikkan indeks itu dan memanggil `0x7b52d0` untuk membangun record HHA. Archive juga memuat resource `MAIL_SP_HHA_GradeFixedPoints` (21 label), tetapi tidak ditemukan edge native dari record tersebut ke pengiriman resource itu. Ini milestone progres terpisah; classifier S/A/B yang memakai `0x7b3ff0` dan batas per level dijelaskan pada subseksi sebelumnya.

### Jalur report internal — antrean dan formatter HHA terbukti; pengiriman surat terbuka

Setelah `0x7b29d0` memanggil bucket `0x7b4fc0`, fungsi itu meneruskan mask ke `0x7b6470`. Fungsi tersebut memetakan bit ke kode record (`0x28–0x39`), membentuk record lewat `0xac77a0`, lalu memanggil helper antrean `0xabf610`. Builder menyimpan field umum pada `+0x08`, `+0x0c`, `+0x10`, `+0x28`, dan `+0x34–+0x38`; khususnya, `param_5` disimpan ke `+0x34` dan byte `param_6` ke `+0x38`. Field `+0x28` berasal dari `*param_3`, bukan dari kode yang menjadi label kandidat. `0xabf610` menambahkan record ke koleksi `0x33d4ff8` bila virtual eligibility method lolos.

Pola builder+antrean yang sama dipakai cabang HHA lain: `0x7b53b0`, `0x7b55e0`, `0x7b5e60`, dan `0x7b61e0`; updater rumah `0xf95620` juga memasukkan record code `0x19`. Lifecycle generik terlihat di `0xac0a60` (pump/flush), `0xabfb40` (handler tipe 3), dan `0xac1ff0` (virtual record handler), di samping helper filter/remove `0xac13f0/0xabfa00`. Vtable record HHA dapat diselesaikan dari RELATIVE relocation `0x32e8cb0 → 0x3088400`; address point-nya `0x3088410`. Slot yang dipanggil `0xac1ff0` menunjuk ke `0xac78f0` (`+0x28`), `0xac7350` (`+0x38`), dan `0x348250` (`+0x40`). Karena builder mengisi sentinel `+0x10 = -1`, metode `0xac7350` mengambil jalur negatif dan memanggil metode `+0x48`, yaitu `0xac7a00`.

Metode formatter `0xac7a00` membaca selector resource dari `record +0x34`, mengambilnya dari registry native yang dimulai di `0x29501df`, lalu memakai byte `record +0x38` sebagai input label untuk pembangun teks `0xf71be0 → 0xf71cd0`. Caller report HHA memberi selector `0x0b` (`11`); entri registry indeks 11 adalah `MAIL_SP_HHA_Grade`. Archive US English memuat resource itu dengan 127 label. Archive juga memuat `GradeFixedPoints` (21), `GradeMission` (15), `Mission` (15), dan `BuildCelebration` (21). Dengan demikian rute queue yang tersedia membuktikan pemilihan paket Grade dan penerusan label ke formatter. Ini belum membuktikan record masuk ke mailbox atau surat terkirim.

`0x7b5b00` memberi formatter code `1, 2, 5, 10, 11, 12, 15, 20, 25, 30`; `0x7b6470` memberi `40, 41, 42, 44, 45, 46, 48, 51, 52, 53, 54, 55, 56, 57`; `0x7b61e0` memetakan ordinal 0–10 ke `70–78, 80, 81`. Semua 35 code cocok dengan label tiga digit pada `MAIL_SP_HHA_Grade.msbt`, dan record formatter membacanya dari `+0x38`. Bukti statis kini menyambungkan producer → antrean tipe 3 → virtual consumer HHA → selector paket Grade → input label formatter.

Jalur sesudah formatter juga terpetakan sebagian. Pump `0xac0a60` mengambil state dari save data pada `+0x2633d0`; consumer tipe 3 meneruskan record ke `0xac1ff0`, yang memilih handler berdasarkan marker objek. Kedua handler berujung pada penyisipan record terformat ke koleksi di dalam data save: `0xfadfc0` mengelola 100 slot dengan stride `0x2440`, sedangkan `0xfae7b0` mengelola 40 slot dengan stride `0x99d0`; masing-masing menandai state `2`. Dalam cabang `TagType=cNone`, `SystemMailSend` memakai builder `0xac77a0` dan dispatcher `0x346a50`; route `cFastToday`/`cFastTomorrow` menjalankan metode virtual `0xac7070` untuk memasukkan record ke koleksi save khusus, sedangkan `cSlowRetry` mencoba handler umum `0xac1ff0` sebelum fallback. Kedua producer ini berbagi format record, bukan bukti bahwa output grade HHA dikirim melalui action tersebut. Belum ada capture yang mengaitkan report HHA ke salah satu slot save itu, ke entri mailbox yang terlihat, atau ke waktu pengiriman.

Pencarian seluruh `event_calls` yang terindeks untuk `MAIL_SP_HHA`/`cHHA` hanya menemukan satu action: `SNPC_rco_10_Common_UpgradeMyhome`, event 45, mengirim `MAIL_SP_HHA_BuildCelebration` dengan route `cFastTomorrow`. Tidak ditemukan action grade HHA. Xref native exact-name untuk `HHAGradeMailFlag` hanya satu, yaitu jalur setter di `0x7b1fe0`; indeks tidak menunjukkan pembaca/pengosong native yang bernama sama maupun reader/writer EventFlow. **Batasnya:** tidak ada call langsung dari producer formatter grade ke action `EventFlowSystemMailSend`; consumer flag, pilihan koleksi untuk report HHA, syarat mailbox, dan delivery masih terbuka. Generator memverifikasi relocation, selector paket, dan kecocokan label di `output/gameplay/house_hha_followup/hha_report_queue_static.json`; runner ambang memvalidasi silang bukti kandidat dan penyisipan di `output/gameplay/house_hha_followup/hha_rank_threshold_native.json`.

### `SystemMailSend` — record masuk koleksi save; inbox/delivery tidak terbukti

Action terdaftar sebagai `EventFlowSystemActor.EventFlowActionSystemMailSend`; method `0x345890` membangun record dengan `0xac77a0`, memetakan string route ke ordinal melalui `0x27ccd0`, lalu memanggil dispatcher `0x346a50` bersama ordinal `TagType`. Daftar route native di `0x29ba1da` berurutan `cFastToday`, `cFastTomorrow`, `cSlowRetry`, sehingga ordinalnya 0, 1, 2.

Untuk `TagType=cNone`, route `cFastToday` memanggil `0xabf6a0 → 0xac1eb0(record, 1, context)`. Route `cFastTomorrow` memanggil `0xabf730 → 0xac1eb0(record, 2, context)`. Fungsi virtual `0xac1eb0` memanggil slot `+0x30`; dua array pointer record yang diindeks (`0x30883a8` dan `0x3088410`) sama-sama mengarahkan slot tersebut ke `0xac7070`. Hubungan tepat antara global constructor `0x33f4288` dan salah satu address point belum dipastikan, tetapi kedua kandidat memberi implementasi slot yang sama. Metode `0xac7070` memformat record lalu memilih jalur berdasarkan mode. Mode 1 memeriksa empat slot record pada offset `+0x7c58`, `+0x7f10`, `+0x81c8`, `+0x8480`, memilih yang tersedia melalui `0xfad540`, lalu menyalin data lewat `0xfaabf0`. Mode 2 memeriksa 16 slot pada member save key `0x9610`, berjarak `0x2b4` mulai `+0x5118` hingga `+0x79a4` melalui `0xfad340`, kemudian mengisi slot pilihan lewat `0xfaa3f0`; tindak lanjut menghitung slot valid dan memperbarui save state. Ini membuktikan bahwa action `cFastTomorrow` menulis record ke koleksi save-backed ber-slot saat handler EventFlow berjalan, bila pemeriksaan validitas lolos dan ada slot kosong.

Route `cSlowRetry` (ordinal 2) lebih dulu mencoba `0xac1ff0`; bila handler itu gagal, fallback `0xabf740` meneruskan mode 3 ke `0xac7070`, yang kembali memakai empat slot tetapi writer `0xfaaeb0`. Dari 50 pemakaian action EventFlow terindeks, 35 memakai `cFastTomorrow` dan 15 `cFastToday`; tidak ada yang memakai `cSlowRetry`. Contoh HHA satu-satunya ialah `BuildCelebration` event 45 dengan `cFastTomorrow`, bukan report grade.

Keberadaan record di koleksi save route tidak membuktikan ia sudah terlihat di inbox, diterima pemain, atau sampai pada tanggal/clock tertentu. Nama route dan pemilihan cabang memberi maksud Today/Tomorrow, tetapi jadwal aktual dan delivery masih memerlukan capture runtime. Bukti dan pemeriksa statis ada di `output/gameplay/house_hha_followup/hha_overlap_mail_dispatch_static.json` dan `tools/hha_overlap_mail_dispatch_static.py`:

```bash
PYTHONPATH=/workspace/acnh-re/.deps python acnh-re/tools/hha_overlap_mail_dispatch_static.py
```

Ada jalur berdekatan untuk perayaan pembangunan rumah: updater harian `0xf53a70 → 0xaba970 → 0xaba9d0 → 0xabb250 → 0xabb3f0` membaca flag native `cNpcMemory:HHABuildCelebraition`, memanggil helper rumah `0x7b1960`, lalu menambahkan event type-3 generik lewat `0xabf610`. Helper `0x7b1960` hanya beroperasi jika bit 6 state rumah aktif; event builder menguji `(u32 pada row rumah +0x144 & 0xfffffffc) == 4`. Helper itu juga memanggil `0xf95610`, pembaca byte save yang sama dengan evaluator HHA. Jalur EventFlow `MAIL_SP_HHA_BuildCelebration` terpisah dan secara eksplisit menjadwalkan mail `cFastTomorrow`, tetapi bukti statis tidak mengikat event native tersebut ke action itu, ke report queue, atau ke `HHAGradeMailFlag`. Jadi jalur ini menerangkan sebagian pengiriman perayaan remodel, bukan pengiriman grade HHA.

Daftar callsite, hash pseudocode, dan pencarian EventFlow terindeks disimpan di `output/gameplay/house_hha_followup/hha_report_queue_static.json`. Regenerator statisnya `tools/hha_report_queue_static.py`:

```bash
python acnh-re/tools/hha_report_queue_static.py
```

### Flag surat grade — syarat setter parsial terbukti; pengiriman terbuka

Flag `cPlayer:HHAGradeMailFlag` memiliki label Jepang “HHA | kirim surat evaluasi ON?” dan tidak memiliki penulis maupun pembaca EventFlow yang terindeks. Manager `0x7b1dd0`, yang dipanggil dari `0xf53a70`, memeriksa slot pemain 0–7 melalui `0x1205870(index)`; bila slot tersedia dan `0x7b1fe0` berhasil, ia melanjutkan ke `0x7b29d0`. Di awal `0x7b1fe0`, helper `0xf95610` mengambil signed byte dari `SavePlayerHouse + 0x263d0` dan nilainya disimpan pada record evaluasi `+0x158`. Setter `0xf4b0d0` mengirim nilai itu ke `HHAGradeMailFlag` sebelum scan furniture bila indeks pemain bukan nol, selector yang dibaca lebih besar dari 1, dan byte bukan `-1`. Initializer record `0x7b1a50` mengisi `+0x158 = -1`. Jadi setter membawa nilai yang tersimpan sebelum pass skor baru, bukan hasil scan yang baru dihitung.

Nama field byte pada build lokal masih tidak diketahui. Descriptor layout lokal di sample node `0x18b058` berukuran satu byte dan cocok dengan alamat record `+0x263d0`, tetapi tidak punya nama atau kandidat jalur eksternal yang cocok. `0xf949c0` juga memakai byte ini: untuk level rumah 4–6 dan nilai bukan `-1`, helper `0xf95620` membangun record queue code `0x19` lalu set `RcoWallFtrRemoveHouseRemodel` dari nilai yang sama. Fungsi `0xf95ba0` membandingkan kandidat terhadap byte ini dan byte tetangganya `+0x263d1`, sementara `0xf95ca0` memproses keduanya saat tidak sentinel. Itu mempersempit pemakaian, tetapi belum membuktikan bahwa byte tersebut berarti “grade sebelumnya” atau bahwa ia sendiri mengirim mail.

Dalam indeks EventFlow untuk dump tersedia, `HHAGradeMailFlag` tidak memiliki reader/writer; pencarian native exact-name memiliki satu xref setter di `0x7b1fe0`, tanpa pseudocode reader. Action HHA terindeks tetap hanya surat perayaan `BuildCelebration`; route native `cFastTomorrow` kini terbukti menulis record ke array save-backed 16 slot saat action dijalankan, tetapi ini tidak menghubungkan report grade dengan action itu. Consumer/pengosong flag, hubungan producer grade ke koleksi mail, syarat mailbox, dan waktu delivery belum terbukti.

**Batas bukti dan kebutuhan capture:** harness item mengontrol nilai balik lookup `HHABaseScore`; harness footprint menguji aritmetika bounding rectangle; harness bucket mengontrol record `+0x150`, accessor mission, dan menghentikan receiver laporan. Ketiganya menjalankan jalur native terpisah. Dalam file yang tersedia tidak ada capture runtime yang menyamakan slot pemain, selector save, susunan item/koordinat ruangan, hasil evaluator, isi queue, transisi `HHAGradeMailFlag`, dan surat yang benar-benar masuk.

Untuk menutup celah, diperlukan capture tersinkron pada build yang sama: (1) save + daftar item/posisi pada pass HHA, dengan kasus dua objek pada anchor yang sama serta kasus satu anchor di dalam footprint objek sebelumnya, untuk melihat grid winner dan nilai `+0x150`; (2) total kategori `+0x110`, raw `PlayerHouseLevel`, ordinal `+0x08`, dan rank UI sekitar batas yang sudah diketahui untuk mengikat classifier ke tampilan; (3) byte `+0x263d0`, `HHAGradeMailFlag`, record queue, dan mailbox sebelum/sesudah satu evaluasi untuk menentukan consumer, ID mail, dan jadwal; (4) nilai selector dengan `HouseLevel` yang diketahui untuk mengonfirmasi nama field 1.0.0. Tanpa keterkaitan waktu dan slot yang sama, capture terpisah tidak dapat membuktikan alur end-to-end. Formula category score penuh, bonus tema/situasi, pemenang furniture same-cell, consumer/pengosongan flag grade-mail, serta hubungan report grade dengan koleksi mail dan delivery tetap terbuka.

### Pass lanjutan: aturan tulis pada anchor sama dan alias byte save

Native menetapkan aturan terbatas untuk tabrakan pada satu anchor. Jalur insert room-grid `0xa14320 → 0x52f270 → 0x52d980` memvalidasi descriptor yang masuk lalu, pada sel anchor, langsung memanggil `0x52df00` dengan nilai baru; cabang itu tidak membaca isi lama atau membandingkan skor/prioritas. Maka di antara insert yang lolos, **penulis terakhir menggantikan nilai sebelumnya**. Jalur update `0xa144b0`/`0x63ca90 → 0x52f280 → 0x52e0a0 → 0x52e360` berbeda: sel `-2` dilewati; descriptor lama yang dikenali `0xf58e20` boleh diperbarui, sedangkan nilai `-3` memakai lookup grid alternatif. Sel lain tidak ditulis. Getter HHA masih mengembalikan satu signed short, bukan daftar furniture.

Ini menyelesaikan kebijakan storage untuk write yang terlacak, tetapi belum mengidentifikasi objek mana yang menjadi write terakhir saat kamar pertama kali dimuat. Satu caller room update yang ditemukan, `0x5ff7f0 → 0x63ca90`, mengunjungi baris spasial 0x38-byte yang telah dibentuk untuk update; bukti tidak mengikat daftar itu ke urutan loader furniture dari save. Jadi identitas pemenang aktual untuk dua item satu anchor tetap memerlukan capture grid/write berurutan atau trace loader yang menghubungkan record save ke pemanggil setter.

Pemetaan save menunjukkan node player-house lokal `0x17cd48` berukuran `0x26400`, dengan descriptor satu-byte pada sample node `0x18b058` yang alamat datanya tepat `+0x263d0`. Ada juga descriptor dua-byte `0x18b020` di alamat sama. Crosswalk schema versi lain memberi kandidat field primitif `SaveLand.PlayerHouseList.HouseList[0].PlayerList[0]` untuk rentang dua byte itu, tetapi tidak ada kecocokan path bagi descriptor satu-byte dan candidate lintas-versi tidak membuktikan arti lokal. Native tetap membaca `+0x263d0` dan `+0x263d1` sebagai dua signed byte terpisah. Ini mempersempit alias layout tanpa memberi nama semantik yang pasti.

Pemeriksaan lanjutan menghitung 51 direct callsite generic getter `0xf4aff0`, 145 generic setter `0xf4b0d0`, dan 16 callsite writer tingkat bawah `0xf4b170`. Xref string exact `HHAGradeMailFlag` tetap satu di setter HHA `0x7b1fe0`; daftar reader/writer EventFlow dan pencarian parameter action tetap kosong, kedua hash CRC32 yang diuji tidak punya xref, dan indeks pointer-array tidak memberi target getter/setter tersebut. Generic API memiliki banyak pemakaian flag lain, tetapi tidak ada caller statis yang dapat dipastikan membaca atau mengosongkan key HHA. Consumer tersembunyi melalui key dinamis tetap hanya bisa dibedakan dengan trace runtime.

Artefak pass ini mencatat callsite insert/update, alias descriptor dan batas statis accessor: `output/gameplay/house_hha_followup/hha_same_anchor_flag_successor.json`. Regenerator dan verifikasinya:

```bash
PYTHONPATH=/workspace/acnh-re/.deps python acnh-re/tools/hha_same_anchor_flag_successor.py
```

Capture minimum untuk menutup sisa: pada build yang sama, satu SaveLand/player slot beserta byte `+0x263d0/+0x263d1`; daftar dua furniture valid pada satu anchor dengan urutan insertion dibalik; tiap write berisi VA setter, room, anchor, descriptor masuk, nilai sel sebelum/sesudah, serta nilai resolver HHA `0xa13fe0`; lalu pada pass tersinkron, key+value semua panggilan generic flag, record report queue, slot koleksi mail save-backed, dan keadaan inbox sebelum/sesudah. Snapshot save yang tidak ditautkan ke urutan write, pass evaluator, dan perubahan flag/mail tidak cukup untuk membuktikan hubungan end-to-end.
