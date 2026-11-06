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

Waktu kalender upgrade masih **terbuka**. Flag `RcoAfterHouseRemodel` menjadi gate EventFlow dan flow mematikannya setelah percakapan, tetapi tidak ada penulis EventFlow yang menyalakannya. Sumber yang diperiksa belum menunjukkan native event yang menetapkan flag tersebut atau jumlah hari renovasi.

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

### Skor total, grade yang ditampilkan, dan tema — terbuka

Skema resolved `ItemParam` memuat `ItemHHATheme`, `ItemHHACategory`, `ItemHHASet`, `ItemHHASituation1/2`, `ItemHHAPart`, `ItemHHASeason`, dan `ItemHHADirection`; `ItemFrom` memuat `HHABaseScore`. Indeks BDLI US English memuat 3 record `STR_HHA_Rank`, 25 `STR_HHA_Theme`, 19 `STR_HHA_Set`, dan 24 `STR_HHA_Situation`. Bukti yang dikumpulkan belum menghubungkan nilai field barang tersebut dengan bobot poin atau mask bucket yang diuji. Flag `cLifeSupportAchievement:GetSRankonHHA` bernama Jepang “mendapat S di HHA” dan direferensikan oleh beberapa fungsi native, tetapi threshold serta kaitnya dengan bit bucket 3/4/5 belum terbukti.

### Flag surat grade — jalur setter terbukti; pengiriman terbuka

Flag `cPlayer:HHAGradeMailFlag` memiliki label Jepang “HHA | kirim surat evaluasi ON?” dan tidak memiliki penulis EventFlow yang terindeks. Fungsi native `0x7b1fe0` merujuk string `HHAGradeMailFlag` dan memiliki satu panggilan setter flag `0xf4b0d0`. Ini membuktikan jalur native yang memperbarui flag tersebut, bukan bahwa surat benar-benar dibuat atau dikirim, kondisi grade yang memicunya, maupun waktunya.

**Blocker bukti saat ini:** harness bucket mengontrol accessor flag dan menghentikan receiver laporan. Belum ada reproduksi penyimpanan flag atau jalur pengiriman surat yang menghubungkan hasil bucket ke surat pemain. Karena itu formula HHA lengkap, pemetaan grade, bonus tema, dan jadwal surat masih terbuka.
