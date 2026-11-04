# Skenario gameplay lengkap ACNH 1.0.0

Tanggal: 4 November 2026. Dokumen ini melengkapi [GAMEPLAY_FLOW](GAMEPLAY_FLOW.md), yang membahas urutan progres cerita. Di sini skenario disusun menurut skala waktu (satu hari, satu minggu, satu tahun), ditambah siklus villager, pengunjung khusus, dan timeline progres dalam hitungan pergantian hari.

Label bukti sama dengan GAMEPLAY_FLOW: **[EF]** EventFlow, **[NATIVE]** belum dibaca, **[PSEUDO]** pseudocode otomatis yang belum dieksekusi, **[TXT]** teks dialog. Ada satu label tambahan:

| Label | Arti |
|---|---|
| **[TBL]** | Nilai langsung dari tabel BCSV (`output/tables_resolved/`) |

Data mesin untuk dokumen ini: [`output/gameplay/native_flag_refs.json`](../output/gameplay/native_flag_refs.json) (pipeline pergantian hari dan bacaan pseudocode), [`flag_index.json`](../output/gameplay/flag_index.json), dan [`trees/`](../output/gameplay/trees/).

## 1. Model state

### Flag

**[TBL]** Ada 1.555 flag di 11 tabel `EventFlags*`. Kolom kebijakan reset (`h_fdb1f290` di Land; `h_5140e4b4` di tabel lain) menentukan kapan sebuah flag di-reset. Predikat reset sudah terbukti native (`0xf54530`, lihat [NATIVE_STAGE_WEATHER](NATIVE_STAGE_WEATHER.md)), dan pembacanya `0xf46200` dipanggil di pergantian hari.

| Tabel | Cakupan | Flag | Punya penulis EventFlow |
|---|---|---|---|
| `Land` | pulau, permanen | 244 | 133 |
| `LandTemp` | pulau, sementara | 51 | 30 |
| `Player` | per pemain, permanen | 673 | 460 |
| `PlayerTemp` | per pemain, sementara | 69 | 48 |
| `PlayerVisit` | saat berkunjung | 42 | 37 |
| `NpcSave` / `NpcTemp` / `NpcMemory` | per villager | 34 / 47 / 116 | 13 / 25 / 95 |
| `House` | rumah | 10 | 7 |
| `LifeSupportAchievement` / `LifeSupportDaily` | Nook Miles | 81 / 188 | 13 / 1 |

Kebijakan reset di tabel Land: `None` 200 flag, `Pre` 41 flag, `Plus` 2, `Start` 1. Komentar Jepang untuk `Pre` menyebut flag di-reset sebelum proses pertumbuhan pergantian hari bila jumlah hari yang lewat tidak 0.

### State fasilitas

**[PSEUDO]** Setiap fasilitas punya state integer di save. State naik di pergantian hari bila struktur kit-nya sudah ada:

| Fasilitas | Fungsi | State | Jenis struktur | Lama |
|---|---|---|---|---|
| Nook's Cranny | `0xfc4560` | 0–3 | 0 | kit → buka: 1 pergantian hari; upgrade: 2 |
| Museum | `0xf77050` | 0–4 | 2 | kit → tenda: 1; tenda → gedung: 2 |
| Able Sisters | `0xfcc300` | 0–2 | 5 | kit → buka: 2 |
| Campsite | `0xf26330` | 0–3 | 6 | kit → jadi: 1 |
| Resident Services | `0x10c2ad0` | – | 1 | tergantung struktur jenis 1 |

"Jenis struktur" adalah argumen pemeriksa struktur (`0x1071bd0`, `0x1106cb0`); nama enum aslinya belum dipetakan. Bila beberapa hari terlewat sekaligus (`elapsed ≥ 2`), konstruksi dua tahap bisa selesai dalam satu pergantian hari.

### Rating pulau

**[EF]** Ambang dan tabel bintang ada di GAMEPLAY_FLOW §10.

**[PSEUDO]** Rumusnya ada di GAMEPLAY_FLOW §10.1. Natural dan Life adalah float di member save `+0x24fdb0`, offset `+0x240`/`+0x244`, yang diperbarui `VillageScoreMgr` setiap ada blok 8×8 yang berubah.

- **Natural** = 0.25 × furnitur DIY kecil + furnitur DIY lebar 3 + min(pohon dewasa, 190) + bunga.
- **Life** = furnitur, dengan bobot 4 untuk furnitur lebar 3, ditambah:
  - 0.2 × pagar;
  - bonus harga (+1/+2, dan +0.5 untuk `DirectionOutdoor`);
  - 15 per jembatan (kecuali yang pertama) dan per tanjakan;
  - 15 per fasilitas: toko state 3, museum state 3, penjahit.

## 2. Satu hari

| Waktu / pemicu | Yang terjadi | Bukti |
|---|---|---|
| 05:00 | Batas hari game: jam <05 dianggap hari sebelumnya | Native terbukti (`0x1fbc00`, [CALENDAR_FLOWERS](CALENDAR_FLOWERS.md)) |
| Game dibuka / lewat 05:00 | `System_GrowUp` (`NewGame`/`Continue`/`InGame`/`AfterNet`) → `DateCheck` → proses pertumbuhan → cuaca → `Save` → stage | [EF] |
| Proses pertumbuhan native | Driver `0xf53a70` (urutan di §2.1) | [PSEUDO] |
| Proses pertumbuhan EventFlow | `System_GrowUp_GameProcess`: campsite pertama, rating pulau, lily, jamur, peluang kontrak rumah NPC | [EF] |
| Pengumuman pagi | `Demo_PublicAnnouncement`: Tom Nook sebelum Resident Services, Isabelle sesudahnya. `Process_Daily` sekali per pemain per hari, `Process_Only_PAnnounce` untuk pemicu progres | [EF] |
| Siang–malam | Villager mengikuti jadwal *cast* (§2.2), pengunjung khusus, event (§4) | [TBL]/[EF] |

### 2.1 Pipeline pergantian hari native

**[PSEUDO]** Driver `0xf53a70` memanggil fungsi berikut. Urutannya dari `index.sqlite` `direct_calls`; peran disimpulkan dari string yang dirujuk tiap fungsi.

| # | Fungsi | Peran (dari string) |
|---|---|---|
| 1 | `0xf56c30`, `0xf56cb0` | set/get `SaveGrowUpRandomFactor` (faktor acak pertumbuhan). Driver lalu men-seed RNG global `0x35e9510` dengan `tahun×365 + bulan + hari + GrowUpRandomFactor + 0x1934` dan membuang 8 angka pertama |
| 2 | `0xf545f0` | dispatcher fasilitas (§1) dan event global (`0xf6130`) |
| 3 | `0x6608a0`, `0x660280` | `VillageExtensionLevel2`, `AllowNpcGroupActivity` |
| 4 | `0x4ae640` | botol pesan, batu uang, doa bintang, bintang jatuh |
| 5 | `0xd21110`, `0xf8ab90`, `0xfbd830` | rumah NPC: `MoveInCompletion`, `AbandonedHouse`, jadwal DIY NPC, sapaan pertama |
| 6 | `0xf8b460`, `0xf8bf40` | jenis hari: event kalender, `ContinuousNormalDay`, `EarlyOrLate` |
| 7 | `0xd22440` | NPC untuk Countdown, Fishing Tourney, Bug-Off |
| 8 | `0xd257d0` | obrolan sapaan villager (`AppFirstTalk`, `AppWelcomeMigrantsTalk`, …) |
| 9 | `0xbdfd40` | jenis konser K.K. (`NormalLive`/`BirthdayLive`) |
| 10 | `0xfd0700` | `DailyQuestFirstFivePointToday` (Nook Miles+ ×5) |
| 11 | `0xfd9d10`, `0xfda740` | pengunjung khusus (§6) dan posisi spawn pengunjung hari ini (§3) |
| 12 | `0xf535e0` | `PlayReportDaily` |

Dispatcher `0xf545f0` sendiri memanggil, berurutan:
1. `0xf234f0` (papan pengumuman);
2. `0x6601a0` (papan toko, Gyroid plaza, `VillageDaysCount`);
3. `0xf6130` (event global, `GlobalEventAvailable/Ready`);
4. `0xfc4560`, `0xf77050`, `0xf7d4c0` (campsite pertama), `0xf26330`, `0xf6a730`, `0xfd8920` (K.K., pembuat jadwal pengunjung mingguan `0xfd8a80`, validasi `0xfd9620`; §3), `0xfc1b80` (rumor), `0x10c26e0` (struktur);
5. `0xf91b90` (hari main, Wisp, `MarketBuiltMyVillage`), `0xf84320` (pindah keluar dan masuk villager, §5.1–5.2), `0xf40e0` (papan event dan ulang tahun).

### 2.2 Jadwal aktif NPC

**[TBL]** `NpcCastScheduleData` (29 baris) memakai jam 5–29, yaitu 05:00 sampai 05:00 esok hari:

| Jenis | Baris (`CastLabel`) | Jam |
|---|---|---|
| Hari biasa (`NotEvent`) | 0–7, 14–28 | 5–29; label 14 dan 15 sampai jam 24 |
| `FishingConvention` | 8 | 9–18 |
| `InsectConvention` | 9 | 9–18 |
| `Countdown` | 10–13 | 23–24 dan 24–29 |

Kolom `NeglectSleep`, `UseRainGoods`, `ApplyNeedActivity`, dan `CanDoze` per baris mengatur tidur, payung saat hujan, kebutuhan aktivitas, dan tertidur. `NpcCastLabelData` memetakan label ke flow AI: `AI_NPC_Outdoor/Indoor`, `AI_NPC_Facility`, `AI_NPC_Quest_TreasureHunt`, `AI_NPC_Quest_VisitP/VisitN`.

### 2.3 Detail harian lain

- **[PSEUDO]** `0xfd8920`: `RctInTent` OFF pada jam 5–19, ON di luar jam itu. `JohnnyRequirePartsNum` di-set 5 di setiap pergantian hari.
- **[EF]** `Process_Daily`: keakraban Sable +1 bila diizinkan, hitungan beli lobak Daisy Mae, penghitung login Nook Stop (di-reset menurut `PlayerPastDaysFromLastPlay` dengan batas 2), resep zodiak Celeste, dan hadiah maskapai.

## 3. Satu minggu

Semua isi bagian ini **[PSEUDO]** (pseudocode dan disassembly yang belum dieksekusi), kecuali yang diberi label lain. Ringkasan mesinnya ada di `output/gameplay/native_flag_refs.json` → `data.visitor_schedule`.

### 3.1 Batas minggu dan member jadwal

- **Minggu** berjalan dari Senin 05:00 sampai Senin 05:00 berikutnya. `0x1fbe10` menghitung hari sebelum 05:00 sebagai hari sebelumnya, lalu mundur ke Senin (dari Minggu mundur 6 hari).
- **Indeks hari** memakai `nn::time::GetDayOfWeek` (`0x1fbd50`): 0 = Minggu, 1 = Senin, …, 6 = Sabtu.
- **Member jadwal** berukuran `0x78` byte (descriptor `0x33d50a8`, offset save `+0x20a210`):

  | Offset | Isi |
  |---|---|
  | `+0x00` | `u32 codes[7]`, kode pengunjung per indeks hari |
  | `+0x1c` | `f32[3]` posisi spawn pengunjung hari ini (`0xfda740`) |
  | `+0x28` | `f32[3]` titik spawn kedua (`0xfda740`) |
  | `+0x44` | `u32 copy[7]`, salinan kode saat jadwal dibuat |
  | `+0x60` | `u8 carry_over[14]` per kode: tertunda minggu lalu, didahulukan |
  | `+0x70` | `i32` hari tambahan Wisp, atau −1 |
  | `+0x74` | `i32` hari Celeste, atau −1 |

### 3.2 Kode pengunjung

Daftar label dibaca dari rodata `main` (`0xfdcf60`, string `non,gul,hgc,cml,gstA,hgh,bey,chy,skk,ows`):

| Kode | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 |
|---|---|---|---|---|---|---|---|---|---|---|
| Label | `non` | `gul` | `hgc` | `cml` | `gst` | `hgh` | `bey` | `chy` | `skk` | `ows` |
| NPC | – | Gulliver | Label | Saharah | Wisp | Mabel | C.J. | Flick | Kicks | Celeste |

- Spawner harian `0xc698d0` → `0xc6f1a0` men-spawn kode 1–3 dan 5–8 dari `0xfdc020` (kode hari ini).
- Kode 9 ada di tabel, tetapi tidak pernah ditulis pembuat jadwal; hari Celeste disimpan di `+0x74`.
- Wisp di-spawn `0xc70060`. Ia hadir bila hari itu bukan hari K.K. dan `codes[hari] == 4` atau hari tambahan Wisp = hari ini (`0xfdbf60`).
- Celeste di-spawn `0xc6fd70`. Ia hadir bila hari itu bukan hari K.K. dan `+0x74` = hari ini (`0xfdb6e0`).
- Wisp dan Celeste hanya tampil 20:00–04:59 (`0xfdb300`: `jam−5 > 14`).

### 3.3 Pembuatan jadwal (`0xfd8a80`)

Fungsi ini dipanggil `0xfd8920` dari dispatcher pergantian hari. Jadwal dibuat ulang bila Senin dari waktu main terakhir berbeda dengan Senin sekarang (`0x1fbfa0`), atau bila belum ada waktu main tersimpan (info pergantian hari `+0x18`, yakni main pertama). Langkahnya berurutan:

1. **Kosongkan.** `codes` dan `copy` diisi 0; `+0x70` dan `+0x74` diisi −1.
2. **Mabel**, bila state penjahit < 2 (penjahit belum berdiri; member `+0x1f40c8`, descriptor `0x33d9ea0`): Sabtu (`0xfdad10`), Minggu (`0xfdae20`), dan satu hari kerja acak.
3. **Saharah**: satu hari kerja acak, setiap minggu.
4. **Kicks**, bila state penjahit ≥ 2: satu hari kerja acak.
5. **Kolam acak**:
   - Label, bila penjahit ≥ 2;
   - C.J. dan Flick, bila `BuiltTownOffice` ON;
   - Gulliver, bila state museum ≥ 2 (tenda Blathers; member `+0x20a168`, state `0xf77050`).

   Kode yang tertunda minggu lalu (`carry_over`) ditempatkan dulu, lalu sisanya. Keduanya dalam urutan acak, dan berhenti begitu tidak ada hari kerja kosong. Kode kolam yang tidak kebagian hari menyalakan `carry_over`-nya untuk minggu depan.
6. **Hari Celeste**, bila state museum > 2 (gedung museum): hari acak dalam minggu itu (Senin–Minggu) yang pola cuacanya `Fine00`. Bila tidak ada, dipilih dari hari `Fine02`, `Fine04`, atau `Fine06`. Hari dengan event kalender, `NormalLive`, atau `BirthdayLive` dilewati. Nama pola ini sama dengan pola cuaca di `output/weather/patterns.json`.
7. **Wisp**: sampai 5 hari kerja kosong lagi. Bila tidak satu pun kebagian, `+0x70` = satu hari Senin–Jumat acak yang sudah berisi pengunjung. Setelah itu Wisp juga mengisi Sabtu dan Minggu bila kosong dan bukan hari Celeste.
8. **Salin** `codes` ke `copy`.

**Penempatan hari kerja** (`0xfda940`):
- Hanya Senin–Jumat (bit 1–5).
- Hari dianggap kosong bila `codes[hari] == 0`, tidak ada event kalender (`0xf0790`), bukan hari `NormalLive`/`BirthdayLive`, dan bukan hari Celeste.
- Hari dipilih seragam acak: popcount `0x198b590`, bit ke-n `0x198b630`, dan xorshift128 `0x19aa0e0` dengan state dari slot TLS. Kaitannya dengan seed harian `0xf53a70` belum dicek.

Akibat langsung dari urutan di atas:
- Sabtu dan Minggu hanya bisa berisi Mabel (sebelum penjahit) atau Wisp.
- Saat semua syarat terbuka, ada 6 pengunjung untuk 5 hari kerja (Saharah, Kicks, Label, C.J., Flick, Gulliver). Satu dari empat anggota kolam pasti tertunda ke minggu berikutnya, dan Wisp mendapat hari tambahan bersama pengunjung lain.

### 3.4 Validasi harian (`0xfd9620`)

Setiap pergantian hari, entri hari ini dicek.

**Syarat sah per kode:**
- Gulliver dan Wisp selalu sah.
- Saharah sah bila ada pemain dengan nilai ≥ 2. Nilainya dibaca `0xef8520` dari member pemain `+0x17cd48`, descriptor `0x33dc730`, rentang 0–8. Nilai yang sama dipakai syarat Harvey, kemungkinan level rumah.
- Mabel sah bila `EnableHghStayField` ON, penjahit belum berdiri, dan bukan hari K.K. **[EF]** Flag itu ("Mabel boleh dipilih sebagai NPC pengunjung") dinyalakan `SNPC_rcm_03_RenualOpen:Rcm_RenualOpen1_ConvHgh` dan dimatikan `Player_Demo_HousingFinish:HousingFinish_Tailor_Built`.
- Kode lain sah bila bukan hari `NormalLive` atau `BirthdayLive`.

**Bila tidak sah:**
- Hari dengan event kalender atau konser K.K. (`FirstLive`, `NormalLive`, `BirthdayLive`) → kode 0.
- Selain itu, entri diganti:
  - bila `JohnnyTalkAnyPlayerFlag` ON ("ada yang sudah bicara dengan Gulliver"; **[EF]** dinyalakan `SNPC_gul:GulTalkChk`), kode 2, 3, 5, 6, 7, 8, dan 9 menjadi Wisp (4);
  - bila flag itu OFF, bukan Minggu dengan toko sudah buka, museum ≥ 2, dan kodenya bukan 4, entri menjadi Gulliver (1);
  - selain itu menjadi 0.

Hari tambahan Wisp dan hari Celeste yang jatuh pada hari event atau konser K.K. diubah menjadi −1.

**Pembatalan lain:**
- Posisi spawn (`0xfda740`): C.J. dibatalkan bila `0x7acda0` tidak menemukan titik spawn.
- `0xfdc080` (eksekusi `CancelTodayVisitorNpc` lewat `0x2b2ac0`) mengosongkan pengunjung hari ini dan mematikan `SpnVisitMainField`.

### 3.5 Pengunjung lain dan K.K.

- Daisy Mae (`boc`, `0xfdafa0`): indeks hari 0 (Minggu) **dan** state toko ≥ 2 (member `+0x1f3e98`, prosesor `0xfc4560`).
- Harvey: `SpnVisitMainField`, tetapi tidak pada hari K.K. atau event global.
- **Jenis konser K.K. hari ini** (`0xfdb060`): 0 bila `TkkFirstLive` OFF; selain itu dicek lewat event kalender, `FirstLive` → 3, `BirthdayLive` → 2, `NormalLive` → 1. K.K. tampil bila nilainya bukan 0 dan `TkkReturn` OFF (`0xfdbae0`).
- **[TBL]** Konser K.K. biasa (`NormalLive`, `EventBegin=16`) dan konser ulang tahun (`BirthdayLive`, `EventBegin=12`) tidak menyimpan hari dalam minggu di `CalendarEventParam`. Penentu tanggal event `NormalLive` ada di sistem kalender native (`0xf2a30`, dipanggil `0xfdb060`) dan belum dibaca.
- **[EF]** Hari jual lobak Daisy Mae tidak ada di EventFlow. Harga lobak juga belum di-RE.

## 4. Satu tahun

**[TBL]** `CalendarEventParam` (17 baris). `Week`/`Wday` = minggu ke-N dan hari ke-N dalam minggu. `Wday` 6 adalah Sabtu bila 0 = Minggu; konvensi ini belum diverifikasi native.

| Event | Utara | Selatan | Jam | Lain |
|---|---|---|---|---|
| Fishing Tourney (4×) | minggu 2, `Wday` 6; musim semi/panas/gugur/dingin = bulan 4/7/10/1 | minggu 2, `Wday` 6; bulan 10/1/4/7 | 9–18 | NPC 5–20, `BbsDays` 6 |
| Bug-Off (4×) | minggu 4, `Wday` 6, bulan 6/7/8/9 | minggu 3, `Wday` 6, bulan 11/12/1/2 | 9–18 | NPC 5–20, `BbsDays` 6 |
| Countdown | 31/12 | 31/12 | 23–02 | `BbsDays` 4 |
| Tahun Baru | 1/1 | 1/1 | – | – |
| Imlek | tabel tanggal per tahun 2000–2060 | sama | – | `RegionAsia`=0 |
| Ulang tahun pemain/NPC | tanggal ulang tahun | – | – | `BbsDays` 8 |
| Konser K.K. | biasa / ulang tahun / pertama | – | mulai 16 / 12 / – | `TkkSkip*` = Before/Same |

- **[PSEUDO]** Event global hanya berjalan setelah `GlobalEventReady`, yang menyala bersamaan dengan `BuiltTownOffice` di `0x10c2ad0`. `0xf6130` merujuk `GlobalEventAvailable`, `TodayGlobalEventId`, dan `TodayRegionEventId`.
- **[TBL]** `SeasonCalendar` (53 batas tanggal) memberi indeks musiman per belahan bumi:
  - kolom: `Season`, `Snow`, `Cloud`, `SPWeather`, `Bush`, `Shop`, `Weed`, `Fog`, `Sakura`;
  - polanya, misalnya `Season_N` = 3 untuk Jan–Feb, 0 untuk Mar–Mei, 1 untuk Jun–Agu, 2 untuk Sep–Nov;
  - `Sakura_N` 1→2→3 pada 6–10 April.
- Pemilih cuaca hari biasa sudah terbukti native; lihat [CALENDAR_FLOWERS](CALENDAR_FLOWERS.md) dan [NATIVE_STAGE_WEATHER](NATIVE_STAGE_WEATHER.md).

## 5. Siklus villager

| Tahap | Mekanisme | Bukti |
|---|---|---|
| Awal | 2 villager, kepribadian AN dan HA | [EF] |
| Quest 3 rumah | `DecideSettlerNpc` (slot eksekusi `0x33c660`) → `0xf8dd70(SettlerType)`: filter `0xf8de30` memaksa nilai kepribadian per plot dari tabel rodata `0x29fa1dc` = [0, 5, 4]. Itu `NpcLooks` `Boy_normal` / `Girl_active` / `Girl_normal` bila nilainya indeks enum (inferensi). Pemilih `0xf8d860` mengeluarkan villager di bitset save `+0xbaae0` dan memilih acak seragam dengan RNG `0x19aa0e0` | [EF] aksi; [PSEUDO]/disassembly |
| Pengunjung campsite pertama | Bila diajak, rumahnya dipasang dari `housing kit` 3349 | [EF] |
| Rumah tambahan | Kit dibeli lewat Tom Nook sampai `NpcHouseNum cExist` 10 | [EF] |
| Mengundang di campsite | `NNPC_Spot_Camp_Invite:CheckOffice` → `CheckCanInduceNpc`: 1 = nama sama sudah tinggal, 2 = nama sama sudah pasti pindah, 3 = penghuni maksimal, 4 = tidak ada lahan dijual | [EF] |
| Mengundang di Mystery Tour | `NNPC_Spot_MysteryTour` butuh `RcmImmQuestComplete` dan `CheckNpcMoveIn`; menyalakan `InduceInMysteriTourIslandToday` | [EF] |
| Panggilan amiibo ke campsite | `Obj_RcoMachine_AmiiboCall`; terbuka setelah rumah pengunjung pertama (`TanuportAmiiboCampUnlock`) | [EF] |
| Peluang kontrak lahan | `NNpcContractCounter` (pergantian hari): `NNpcContractProbablityAddPoint` 0–3 menurut jumlah rumah dan peringkat pulau (§5.2) | [EF] |
| Pindah masuk | `MoveInCompletion`, layout rumah dari `Param/NpcHouse/%s.byml` (`0xd21110`) | [PSEUDO] string |
| Konsultasi pindah keluar | `NNPC_ApproachD:MoveConfirm`/`MoveCancel` menyalakan `IsMovingConsultationToPlayer` (§5.1) | [EF] |
| Pengumuman pindah | `Demo_PublicAnnouncement_32_CmnNewsMoveIn`, `_34_CmnNewsMoveOut`, gate `IsExistMoveNpc` | [EF] |
| Rumah kosong | `AbandonedHouse` (`0xd21110`, `0xf8ab90`, …) | [PSEUDO] string |
| Pemilih villager acak yang sama | `0xf8d860` juga dipanggil `0xf84f10` (pengisian slot, §5.2) dan `0xf8c540` | [PSEUDO] |
| Siapa yang ingin pindah, dan kapan | §5.1 | [PSEUDO] |

Isi §5.1 dan §5.2 adalah **[PSEUDO]** (pseudocode, rumus peluang dicocokkan dengan disassembly), kecuali yang diberi label lain. Ringkasan mesinnya ada di `native_flag_refs.json` → `data.villager_moves`.

### 5.1 Pindah keluar

Data villager ada di member NPC (descriptor `0x33d97d8`, `0x1d6d48` byte): 10 slot × `0x12ab0` byte. Flag `cNpcSave` tiap slot ada di `+0x11efc` slot. State pindahnya:

| Offset | Isi |
|---|---|
| `+0x1d6d3d` | slot calon pindah, atau −1 |
| `+0x1d6d3e` | jeda: 15 setelah ada yang pindah, berkurang sejumlah hari yang berlalu |
| `+0x1d6d3f` | hari sejak percakapan pindah terakhir, maksimum 30 |
| `+0x1d6d40` | pindah sudah dikonfirmasi pemain |
| `+0x1d6d41` | slot villager terakhir yang pindah masuk |
| `+0x1d6d42` | slot villager terakhir yang dibujuk tetap tinggal |

**Setiap pergantian hari** (minimal satu hari berlalu), `0xf84320` → `0xf847f0` mengerjakan, berurutan:
1. Calon dengan `AbandonedHouse` ≠ 0 → slot dikosongkan, jeda = 15.
2. Villager pertama (urut slot) dengan `ForceMoveOut` ON → langsung pindah dan slotnya dikosongkan.
3. Calon yang sudah dikonfirmasi:
   - pergantian hari pertama → status slot `+0x11efa` = 2 (`0xf05d00`);
   - pergantian hari berikutnya → pindah, slot dikosongkan, jeda = 15.
4. Selain itu jeda dikurangi dan penghitung hari ditambah sejumlah hari yang berlalu. Calon dihapus bila salah satu syarat ini terpenuhi:
   - jeda > 0;
   - villager menetap < 6 (`0xf855c0`: slot terisi, `MoveInCompletion` ON, `AbandonedHouse` < 2);
   - penghitung ≤ 4.

   Bila tidak, `r` = acak 0–99 dari RNG harian `0x35e9510` (`0xf53420`, di-seed `0xf53a70`). Bila `r < 5 × villager menetap + penghitung`, calon baru dipilih (`0xf87670`). Bila undian gagal, calon lama tetap.

   Contoh: 10 villager dan penghitung 30 → 80% per hari; 6 villager dan penghitung 5 → 35%.

**Pemilihan calon** (`0xf87670`):
- **Dikecualikan:**
  - slot kosong;
  - indeks yang disimpan aksi `StructureMoveSaveIndex` (member `+0x4750`; dipakai `SNPC_rco_10_Common_MoveHouse` dan `_MoveNpcFacility`, kemungkinan rumah yang sedang dipindah);
  - villager terakhir yang pindah masuk;
  - villager terakhir yang dibujuk tinggal;
  - villager yang ulang tahunnya 0–7 hari lagi (`BirthMonth`/`BirthMDay` di `NmlNpcParam`).
- **Bobot** per villager = ⌊(300 − ⌊ΣFriendship ÷ jumlah pemain⌋) × 0.1⌋ − jumlah pemain berlevel keakraban 6.
  - Friendship diambil dari memori villager untuk tiap dari 8 pemain.
  - Level (`0xd34a20`): <30 → 1, <60 → 2, <100 → 3, <150 → 4, <200 → 5, ≥200 → 6.

  Makin rendah rata-rata keakraban, makin besar peluang dipilih.
- **Undian:** `r` = acak 0 sampai Σbobot−1 dari RNG harian; calon dipilih secara kumulatif menurut urutan slot.
- **Setelah terpilih:** konfirmasi dihapus, `IsMovingConsultationToPlayer` OFF, dan memori per pemain direset (`0xf05b80` → `0xf48c40`, yang merujuk `ChokeOffMoveOut`).

**Konsultasi** (**[EF]** `NNPC_ApproachD` + handler `0x298c10`):

| Pilihan | Aksi | Akibat |
|---|---|---|
| `MoveConfirm` | `SetNpcMoveoutStopInfo(MoveOutStatus=1)` | pindah dikonfirmasi: status slot 2 pada pergantian hari berikutnya, pergi pada pergantian hari sesudahnya |
| `MoveCancel` | `SetNpcMoveoutStopInfo(MoveOutStatus=0)` | `ChokeOffMoveOut` ON di memori pemain; villager ini dicatat sebagai "dibujuk tinggal" |

Keduanya mereset penghitung hari ke 0 dan menyalakan `NextMoveOutTalk` serta `IsMovingConsultationToPlayer`. Jadi undian berikutnya baru mungkin 5 hari kemudian.

### 5.2 Mengisi slot kosong

`0xf84f10` jalan setiap pergantian hari sesudah §5.1. Sasarannya slot kosong pertama yang tidak dikosongkan hari itu.

1. **Jalur plot/kontrak** `0xf8c540` (string `FromSettlerQuest`, `InducementFlag`, `ImmQ_%s_*`). Bila berhasil, selesai.
2. **`0xf8d210`** (`MoveInOrder`). Bila ada villager hasil `ForceMoveOut`, `0xf8cea0` juga dipanggil untuk slotnya; perannya di sini belum dibaca rinci.
3. **Plot rumah kosong** wajib ada: `0xef44c0` untuk 10 plot; `0xf8d640` menghitungnya dan memilih satu dengan RNG harian.
   - Bila ada NPC menunggu (status 3) di salah satu dari 4 struktur NPC tambahan (`+0xcca68 + k×0x12ab0`; kemungkinan villager yang sudah diundang), `0xf8cea0` memindahkannya ke plot itu. Selesai.
   - Selain itu ada undian harian. Misalkan n = jumlah villager dan P = jumlah plot kosong:

     | n | Peluang pindah masuk |
     |---|---|
     | < 5 | 100% |
     | 5–7 | (10 − n + `NNpcContractProbablityAddPoint` + P) × 10% |
     | ≥ 8 | (10 − n + P) × 10% |
   - **Pemilihan villager baru:**
     - Kepribadian yang dipilih adalah yang paling sedikit di pulau; bila seri, semuanya. Nilainya 0–7, dari byte ke-3 ID NPC (`0xcd3cb0`).
     - Kandidat disaring `0xf8d7d0` (bitmask `0x35ee084`), lalu dipilih acak seragam oleh `0xf8d860` dengan bitset eksklusi `+0xbaae0`. Villager terpilih ikut ditandai di bitset itu.
     - Rumah dibuat dari `Param/NpcHouse/%s.byml` (`0xf826c0`, `0xf814c0`).

**[EF] `NNpcContractProbablityAddPoint`** (`System_GrowUp_GameProcess:NNpcContractCounter`, dipanggil dari `ChkwithIslandEvaluation`; peringkat dari `System_IslandEvaluationCheck`: SetIndex 2 = Nature, SetIndex 3 = Life):

| Rumah NPC | Life | Nature | Nilai |
|---|---|---|---|
| <5 atau ≥8 | – | – | 0 |
| 5–7 | 0 | – | 0 |
| 5–7 | 1 | 0 / ≥1 | 0 / 1 |
| 5–7 | ≥2 | 0 / 1 / ≥2 | 0 / 1 / 3 |

Yang masih terbuka: penulis `AbandonedHouse` (perujuk `0xd36400`, dipanggil `0x10d39d0`, `0x1102dc0`, …) dan peran `0xf8c540`/`0xf8d210` secara rinci.

## 6. Pengunjung khusus

| NPC | Yang sudah diketahui | Bukti |
|---|---|---|
| Harvey (`spn`) | `SpnVisitMainField`=1 bila sebuah nilai 0–8 ≥2 (kemungkinan level rumah pemain), quest A/B/C selesai, dan Photopia belum terbuka maupun dikunjungi | [PSEUDO] `0xfd9d10` |
| Label (`hgc`) | Kode 2, kolam acak setelah penjahit berdiri (§3.3); `HgcVisitFlagForTailor`; quest dan keakraban di `KotonoQuest*` | [PSEUDO] / [EF] |
| Saharah (`cml`) | Kode 3, satu hari kerja setiap minggu; sah bila ada pemain dengan nilai ≥2 (§3.4) | [PSEUDO] |
| Kicks (`skk`) | Kode 8, satu hari kerja setiap minggu setelah penjahit berdiri | [PSEUDO] |
| C.J. (`bey`), Flick (`chy`) | Kode 6 dan 7, kolam acak bila `BuiltTownOffice` (spawn dengan flag 1); C.J. batal bila tidak ada titik spawn; juga NPC event turnamen | [PSEUDO] / [EF] |
| Mabel (`hgh`) | Kode 5. Sebelum penjahit: Sabtu, Minggu, dan satu hari kerja; sah hanya bila `EnableHghStayField` ON. Kunjungan pedagang menambah `CountTailorBuild` → toko penjahit; `HghStayMarket` di `0xfc4560` | [PSEUDO] / [EF] |
| Sable (`hgs`) | `HgsCloseness` maks 11, +1 per hari bila diizinkan | [EF] |
| Wisp (`gst`) | Kode 4: mengisi hari kosong sisa (maks 5 hari kerja, plus Sabtu/Minggu), atau hari tambahan `+0x70`; pengganti entri gugur bila Gulliver sudah diajak bicara. Spawn `0xc70060` (`GstAppearField`); hanya 20:00–04:59; flag quest di-reset pada pergantian hari | [PSEUDO] |
| Gulliver (`gul`) | Kode 1, kolam acak setelah tenda museum; pengganti entri gugur selama belum diajak bicara (§3.4). `JohnnyRequirePartsNum`=5 per pergantian hari; `JohnnyHelpCount` 30 → resep golden shovel | [PSEUDO] / [EF] |
| Daisy Mae (`boc`) | Indeks hari 0 dan nilai save ≥2; `BocBuyCount`, `FirstKabuBuy`, `FirstKabuPattern` | [PSEUDO] / [EF]; harga [NATIVE] |
| Celeste (`ows`) | Hari = `+0x74`, satu per minggu setelah gedung museum, dipilih dari hari cuaca `Fine00` (cadangan `Fine02/04/06`); malam saja; resep per zodiak (`OwsThisZodiac` 1–12); bintang jatuh (`0x4ae640`) | [PSEUDO] / [EF] |

Yang masih terbuka dari jadwal ini:
- apakah RNG TLS yang dipakai `0xfd8a80` adalah RNG yang di-seed harian oleh `0xf53a70`;
- arti pasti nilai pemain 0–8 (syarat Saharah dan Harvey);
- titik tetap yang menjadi acuan posisi Label, Mabel, dan Kicks (`0x469680`).

## 7. Timeline progres dalam pergantian hari

"+N" = jumlah pergantian hari sesudah syarat terpenuhi, dengan asumsi bermain setiap hari.

| Langkah | Syarat | Hasil |
|---|---|---|
| Buat pulau | prolog hari 1 | tenda pemain, 2 villager |
| Pengumuman hari ke-2 | pergantian hari pertama | bandara buka |
| Tenda museum | 5 makhluk diberikan ke Tom Nook, kit dipasang | +1: tenda Blathers |
| Gedung museum | total donasi mencapai `MuseumDonationNumCheck Border=20` (penghitung sisa `DonationAmountForMuseum` maks 15) | +1: konstruksi; +2: gedung |
| Nook's Cranny | rumah pemain, 30×4 bahan, kit dipasang | +1: toko buka; pada hari itu juga quest 3 rumah diumumkan |
| Quest 3 rumah | jembatan, 3 kit, 3 furnitur dalam + furnitur luar per plot | plot lengkap diproses di pengumuman pagi; ketiganya lengkap → hadiah pagar |
| Resident Services | quest selesai dan ≥5 rumah NPC | pengumuman → konstruksi → gedung (struktur jenis 1); Isabelle; `GlobalEventReady` |
| Campsite | kit campsite dipasang | +1: campsite; pergantian hari berikutnya: pengunjung pertama |
| Penilaian pulau | rumah pengunjung pertama, ≥6 rumah NPC | Isabelle mulai menilai |
| Konser K.K. | ≥8 rumah NPC dan ≥3★ saat bicara dengan Isabelle | +1: `TkkFirstLiveEnable`; pagi itu konser dijadwalkan dan langsung berlangsung |
| Island Designer | setelah konser | app diberikan Tom Nook |
| Lily of the valley | 5★ dan konser pertama sudah terjadi | penghitung +1 per pergantian hari |

## 8. Celah berikutnya (prioritas)

| # | Celah | Titik masuk |
|---|---|---|
| 1 | Hari konser K.K. biasa | penentu tanggal event `NormalLive` di kalender native `0xf2a30` (§3.5) |
| 2 | Harga lobak dan stok toko | belum ada titik masuk string; mulai dari flag `FirstKabuPattern` |
| 3 | Prosesor yang belum dibaca | `0xf8f190`, `0xf7d4c0`, `0xfc1b80`, `0xbdfd40`, `0xf8b460` (tujuan RNG) |
| 4 | Menaikkan [PSEUDO] menjadi terbukti | emulasi fungsi fasilitas dan rumus skor pulau seperti tahap mekanik terdahulu |
| 5 | Format save | konstruktor layout save `0xf32fa0` (pemanggil `0xf30220`, `0xf416c0`) |

Antrian yang sama, dalam bentuk yang bisa dibaca mesin dan ditandai statusnya, ada di [re_queue.json](re_queue.json).
