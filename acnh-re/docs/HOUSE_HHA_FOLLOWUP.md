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

Di `0x7b1fe0`, ketika jalur item berada pada `iVar24 == 0` dan predicate native `0xaa7f80` lolos, blok `0x7b2694` meminta dua extent dari record objek: `0x52c270` menghasilkan `maxX + 1 - minX` dari offset `+0x10/+0x20`, sedangkan `0x52c290` menghasilkan `maxZ + 1 - minZ` dari `+0x14/+0x24`. Instruksi `MADD/STR` kemudian menambah `width × depth` ke `+0x150` pada record evaluasi pemain. Jadi `+0x150` menerima jumlah luas bounding-rectangle yang lolos guard itu. Evaluator juga memakai bitmap 0x400 sel pada konteks `+0xee8` untuk menandai grid index selama scan, tetapi bitmap tersebut tidak tampak dipakai oleh blok `MADD/STR` untuk mengurangi luas yang sudah tercatat. Arti predicate `0xaa7f80` dan apakah ia menolak item yang bertumpang tindih belum terpetakan; bukti ini tidak menetapkan koreksi overlap atau ruang kosong di dalam bounding rectangle.

Native harness menjalankan dua extent helper, `MADD`, dan store asli pada lima pasangan batas koordinat, termasuk koordinat negatif dan accumulator awal nonnol. Hasil: 5 kasus, 0 mismatch. Harness sengaja mulai sesudah eligibility guard dan tidak menjalankan item lookup atau predicate `0xaa7f80`.

Artefak dan reproducer:

- `output/gameplay/house_hha_followup/hha_coverage_accumulator_native.json`
- `tools/hha_floor_coverage_accumulator_native.py`

### Penyebut luas rumah +0x14c — produsen switch terbukti; selector belum bernama

`0x7b1dd0` memeriksa slot pemain 0–7 melalui `0x1205870(index)` dan meneruskan slot aktif ke evaluator `0x7b1fe0(index)`. Stride `0x160` pada tabel internal adalah record evaluasi per slot pemain/rumah; pemindaian delapan ruang berlangsung di dalam evaluator. Nama field save yang menghasilkan selector luas rumah belum ditemukan.

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

Pola luas itu cocok dengan pertumbuhan denah rumah. `PlayerHouseLevel` pada EventFlow dan `SaveLand.PlayerHouseList.HouseList[0].HouseLevel` pada schema save eksternal adalah kandidat nama yang cocok, tetapi belum ada cross-reference native lokal dari selector ke salah satu label itu; selector tetap tidak bernama. Native harness menjalankan dispatch dan store asli untuk ketujuh selector dengan 0 mismatch; ia mulai setelah lookup/flag-setter dan berhenti sebelum helper `0x7b7c30`.

Artefak dan reproducer:

- `output/gameplay/house_hha_followup/hha_house_area_denominator_native.json`
- `tools/hha_house_area_denominator_native.py`

Jalankan dari root worktree:

```bash
PYTHONPATH=/workspace/acnh-re/.deps python acnh-re/tools/hha_house_area_denominator_native.py
```

### Skor item menuju akumulator HHA — terbukti terbatas; kait ke bucket masih terbuka

Evaluator `0x7b1fe0` memproses item untuk satu slot pemain dan memanggil `0x7b36b0` untuk item yang lolos pemeriksaan. Instruksi native `0x7b36b0` memanggil helper item `0xab9050` di PC `0x7b37b8`, lalu menambahkan nilai baliknya ke record evaluasi pemain pada `param1 + 0xb10`, offset `+0x24`. Pseudocode helper `0xab9050` mencari hash field `0xd62525d0`; hash ini sama persis dengan kolom `ItemFrom:HHABaseScore` pada schema resolved (offset 6, lebar 2 byte). Reproducer menjalankan instruksi asli `0x7b36b0` dengan nilai balik helper terkontrol 0, 200, dan 499; ketiganya menambahkan nilai yang sama ke `+0x24`, sementara `+0x150` tetap pada sentinel uji. Ada 3 kasus dan 0 mismatch. Identitas sumber skor dibuktikan lewat kesamaan hash schema; harness tidak menjalankan lookup tabel item sebenarnya.

Di evaluator `0x7b1fe0`, setelah pemindaian, native membentuk `+0x136c` sebagai jumlah 12 akumulator kategori pada `+0x24` sampai `+0x50`. Cabang bucket `0x7b4fc0` membaca field berbeda: `+0x150` sebagai pembilang dan `+0x14c` sebagai penyebut. Untuk pembilang nonnegatif, ia menggeser `+0x150` empat bit ke kanan, membagi hasilnya dengan `+0x14c`, lalu mengalikan 100. Ambang internal yang terlihat adalah 20 dan 50; konstanta float 100.0 dan 50.0 berada di `0x29d6408` dan `0x29d62ac`. Harness bucket lama menguji scalar `+0x150` langsung dengan instruksi `0x7b4fc0`.

Pembacaan silang dekompilasi memberi jembatan tambahan dari akumulator barang ke mask report. Evaluator `0x7b1fe0` memanggil akumulator item `0x7b36b0` di PC `0x7b265c`; akumulator itu memanggil `0xab9050` di PC `0x7b37b8` dan menambah nilai baliknya ke field kategori saat ini. Setelah `0x7b39c0`, evaluator menyimpan total lama dari konteks pada `+0x136c`, menghitung ulang jumlah 12 field kategori `+0x24..+0x50`, lalu menulis selisih total baru dan lama ke record evaluasi pada `+0xd8 + 4*min(indeks_area,5)`. Bucket `0x7b4fc0` memindai nilai `+0xd8` sebanyak jumlah pada `+0x154`, memilih indeks nilai maksimum/minimum ke `+0x155/+0x156`, lalu menyalakan mask `0x100/0x200`. Receiver `0x7b6470` mengubah bit itu menjadi record kode `0x33/0x34`, yang kemudian dibangun dan dimasukkan ke antrean bersama.

Ini membuktikan jalur statis terbatas `HHABaseScore → akumulator kategori → total sementara +0x136c → delta per area +0xd8 → dua rincian mask report`. Nilai `+0x136c` sendiri tidak dipetakan ke threshold rank yang ditampilkan; report memakai perubahan skor per area dan indeks area tertinggi/terendah. Penelusuran tersebut belum dijalankan sebagai satu harness native end-to-end.

Karena akumulator item `+0x24..+0x50`/total `+0x136c` dan pembilang bucket `+0x150` merupakan field berbeda, bukti yang ada belum menghubungkan nilai helper item ke scalar bucket. Penanganan overlap/area kosong pada pembilang bounding-footprint, bobot tema, ambang grade yang ditampilkan, dan hubungan total `+0x136c` dengan grade tetap **terbuka**.

Reproducer dan hasil untuk akumulator item:

- `output/gameplay/house_hha_followup/hha_item_score_accumulator_native.json`
- `tools/hha_item_score_accumulator_native.py`

Jalankan dengan dependency cache bersama:

```bash
PYTHONPATH=/workspace/acnh-re/.deps python acnh-re/tools/hha_item_score_accumulator_native.py
```

### Skor total hingga grade yang ditampilkan dan tema — terbuka

Skema resolved `ItemParam` memuat `ItemHHATheme`, `ItemHHACategory`, `ItemHHASet`, `ItemHHASituation1/2`, `ItemHHAPart`, `ItemHHASeason`, dan `ItemHHADirection`; `ItemFrom` memuat `HHABaseScore`. Indeks BDLI US English memuat 3 record `STR_HHA_Rank`, 25 `STR_HHA_Theme`, 19 `STR_HHA_Set`, dan 24 `STR_HHA_Situation`. Bukti yang dikumpulkan belum menghubungkan nilai field barang tersebut dengan bobot poin, bonus tema, atau rank akhir. Flag `cLifeSupportAchievement:GetSRankonHHA` bernama Jepang “mendapat S di HHA” dan direferensikan oleh beberapa fungsi native, tetapi threshold serta kaitnya dengan bit bucket 3/4/5 belum terbukti. Jembatan `+0x136c → +0xd8 → mask report` di atas memberi hubungan terbatas ke rincian laporan; pembaca downstream yang mengubah report menjadi grade tetap belum diketahui.

### Jalur report internal — antrean terbukti, UI/surat belum terpetakan

Setelah `0x7b29d0` memanggil bucket `0x7b4fc0`, fungsi itu meneruskan mask ke `0x7b6470`. Fungsi tersebut memetakan bit ke kode record internal (`0x28–0x39`), membentuk record lewat `0xac77a0` (label Ghidra `FUN_00bc77a0`), lalu memanggil helper antrean `0xabf610` (label Ghidra `FUN_00bbf610`). Builder menulis field pada offset `+0x08`, `+0x0c`, `+0x10`, `+0x28`, dan `+0x34–+0x38`; helper antrean memiliki cabang yang menambahkan entri nonnull ke koleksi global. Kedua call ini bukan API pengiriman surat; arti record dan konsumen antrean sesudahnya belum diketahui.

Pola builder+antrean yang sama dipakai cabang HHA lain: `0x7b53b0` (kelompok kode `0x0c`), `0x7b55e0` (`0x0e`), `0x7b5e60` (`0x0d`), dan `0x7b61e0` (`0x0b`, kode `0x46–0x51`). Caller yang terlihat adalah `0x7b52d0`, `0x7b5540`, `0x7b29d0`, dan `0x7b4d00`. Dalam receiver `0x7b6470`, indeks mask 8 dan 9 memakai nilai maksimum/minimum dari `+0x155/+0x156`, lalu menjadi record code `0x33/0x34`. `0xabf610` menambahkan record nonnull ke antrean native generik; builder dan append tidak menunjukkan layar, label bahasa, atau action surat. Fungsi HHA yang mengonsumsi entri itu serta pemetaan record code ke UI/mail belum ditemukan.

Daftar callsite, hash pseudocode, dan pencarian EventFlow terindeks disimpan di `output/gameplay/house_hha_followup/hha_report_queue_static.json`. Regenerator statisnya `tools/hha_report_queue_static.py`:

```bash
python acnh-re/tools/hha_report_queue_static.py
```

### Flag surat grade — syarat setter parsial terbukti; pengiriman terbuka

Flag `cPlayer:HHAGradeMailFlag` memiliki label Jepang “HHA | kirim surat evaluasi ON?” dan tidak memiliki penulis maupun pembaca EventFlow yang terindeks. Manager `0x7b1dd0`, yang dipanggil dari `0xf53a70`, memeriksa slot pemain 0–7 melalui `0x1205870(index)`; bila slot tersedia dan `0x7b1fe0` berhasil, ia melanjutkan ke `0x7b29d0`. Di awal `0x7b1fe0`, setter `0xf4b0d0` berjalan sebelum pemindaian furniture bila indeks pemain bukan nol, selector yang dibaca lebih besar dari 1, dan field state record `+0x158` bukan `-1`. Setter menerima nilai dari field itu; initializer record `0x7b1a50` mengisi `+0x158 = -1`. Manager memanggil `0x7b29d0` hanya setelah evaluator berhasil, sehingga penulisan flag pasti mendahului scan skor dan bucket pada pass yang sama. Ini membuktikan flag tidak dihitung dari hasil scan baru pada pass itu; sumber field state, kait ke grade pass sebelumnya, dan pembacanya setelah setter belum diketahui.

Dalam indeks EventFlow lengkap untuk dump yang tersedia, pencarian `HHAGradeMailFlag` menghasilkan nol akses. Pencarian mail dengan `FromType=cHHA` atau `MAIL_SP_HHA` menghasilkan satu action: `SNPC_rco_10_Common_UpgradeMyhome` event 45 mengirim `MAIL_SP_HHA_BuildCelebration` melalui `cFastTomorrow`. Ini surat perayaan pembangunan rumah, bukan hasil evaluasi. Jalur pengiriman grade mail tetap **belum terbukti**; blocker yang tersisa ialah konsumen antrean report native dan titik yang membaca atau mengosongkan `HHAGradeMailFlag`.

**Batas bukti saat ini:** harness item mengontrol nilai balik lookup `HHABaseScore`; harness footprint menguji aritmetika bounding rectangle; harness bucket mengontrol record `+0x150`, accessor mission, dan menghentikan receiver laporan. Ketiganya menjalankan jalur native terpisah. Belum ada reproduksi save yang menghubungkan field item, total `+0x136c`, pembilang/penyebut bucket, `HHAGradeMailFlag`, dan konsumen antrean report. Karena itu formula HHA lengkap, pemetaan grade, bonus tema, serta syarat dan jadwal surat tetap terbuka.
