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

**[EF]** Ambang dan tabel bintang ada di GAMEPLAY_FLOW §10. **[PSEUDO]** Handler `VillageScoreCheckNatural` (`0x3e0b80`) membandingkan ambang dengan float di objek save offset `+0x240`. Jadi skornya disimpan, lalu dibandingkan. Penghitung skornya (string `VillageScoreMgr`/`ASysVillageScoreMgr`) belum dibaca.

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
| 11 | `0xfd9d10` | pengunjung khusus (§6) |
| 12 | `0xf535e0` | `PlayReportDaily` |

Dispatcher `0xf545f0` sendiri memanggil, berurutan:
1. `0xf234f0` (papan pengumuman);
2. `0x6601a0` (papan toko, Gyroid plaza, `VillageDaysCount`);
3. `0xf6130` (event global, `GlobalEventAvailable/Ready`);
4. `0xfc4560`, `0xf77050`, `0xf7d4c0` (campsite pertama), `0xf26330`, `0xf6a730`, `0xfd8920` (K.K.), `0xfc1b80` (rumor), `0x10c26e0` (struktur);
5. `0xf91b90` (hari main, Wisp, `MarketBuiltMyVillage`), `0xf84320` (`MoveInCompletion`), `0xf40e0` (papan event dan ulang tahun).

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

- **[PSEUDO] Jadwal pengunjung mingguan.** Bentuknya member save `0x78` byte (descriptor `0x33d50a8`, offset save `+0x20a210`) dengan 7 kode pengunjung, satu per indeks hari (`0x1fbd50`, 0–6). Kode hari ini diambil `0xfdc020`, lalu spawner harian `0xc698d0` → `0xc6f1a0` men-spawn label sesuai kode:

  | Kode | 1 | 2 | 3 | 5 | 6 | 7 | 8 | 0/4/9 |
  |---|---|---|---|---|---|---|---|---|
  | NPC | `gul` Gulliver | `hgc` Label | `cml` Saharah | `hgh` Mabel | `bey` C.J. | `chy` Flick | `skk` Kicks | tidak ada |

  Label diambil dari rodata `main` (`re_helpers.py rodata`). Kode 2 = Label cocok dengan `HgcVisitFlagForTailor` di `0xfd9d10`.
- **[PSEUDO] Pengunjung lain yang tidak lewat kode:**
  - Daisy Mae (`boc`, `0xfdafa0`): indeks hari = 0 **dan** sebuah nilai save ≥2 (kemungkinan state Nook's Cranny).
  - Celeste: indeks hari = int pada `+0x74` di member jadwal (`0xfdb6e0`).
  - Wisp (`gst`) dan Celeste (`ows`) hanya tampil jam 20:00–04:59 (`0xfdb300`: `jam−5 > 14`).
  - Harvey: `SpnVisitMainField`, tetapi tidak pada hari K.K. atau event global.
- **[PSEUDO] Jenis konser K.K. hari ini** (`0xfdb060`): 0 bila `TkkFirstLive` OFF; selain itu dicek lewat event kalender, `FirstLive` → 3, `BirthdayLive` → 2, `NormalLive` → 1. K.K. tampil bila nilainya bukan 0 dan `TkkReturn` OFF (`0xfdbae0`).
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
| Peluang kontrak lahan | `NNpcContractCounter` (pergantian hari): `NNpcContractProbablityAddPoint` 0–3 menurut jumlah rumah (≥8 → 0; 5–7 → menurut peringkat Life/Nature) | [EF] |
| Pindah masuk | `MoveInCompletion`, layout rumah dari `Param/NpcHouse/%s.byml` (`0xd21110`) | [PSEUDO] string |
| Konsultasi pindah keluar | `NNPC_ApproachD:MoveConfirm`/`MoveCancel` menyalakan `IsMovingConsultationToPlayer` | [EF] |
| Pengumuman pindah | `Demo_PublicAnnouncement_32_CmnNewsMoveIn`, `_34_CmnNewsMoveOut`, gate `IsExistMoveNpc` | [EF] |
| Rumah kosong | `AbandonedHouse` (`0xd21110`, `0xf8ab90`, …) | [PSEUDO] string |
| Pemilih villager acak yang sama | `0xf8d860` juga dipanggil `0xf84f10` (kontrak lahan) dan `0xf8c540` | [PSEUDO] |
| Siapa yang ingin pindah, dan kapan | belum dibaca (`0xf87670`) | [NATIVE] |

## 6. Pengunjung khusus

| NPC | Yang sudah diketahui | Bukti |
|---|---|---|
| Harvey (`spn`) | `SpnVisitMainField`=1 bila sebuah nilai 0–8 ≥2 (kemungkinan level rumah pemain), quest A/B/C selesai, dan Photopia belum terbuka maupun dikunjungi | [PSEUDO] `0xfd9d10` |
| Label (`hgc`) | Kode jadwal 2 → spawn dan `HgcVisitFlagForTailor`; quest dan keakraban di `KotonoQuest*` | [PSEUDO] / [EF] |
| Saharah (`cml`), Kicks (`skk`) | Kode jadwal 3 dan 8 | [PSEUDO] |
| C.J. (`bey`), Flick (`chy`) | Kode jadwal 6 dan 7 (spawn dengan flag 1); juga NPC event turnamen | [PSEUDO] / [EF] |
| Mabel (`hgh`) | Kode jadwal 5. Kunjungan pedagang menambah `CountTailorBuild` → toko penjahit; `HghStayMarket` di `0xfc4560` | [PSEUDO] / [EF] |
| Sable (`hgs`) | `HgsCloseness` maks 11, +1 per hari bila diizinkan | [EF] |
| Wisp (`gst`) | Spawn `0xc70060` (`GstAppearField`); hanya 20:00–04:59; flag quest di-reset pada pergantian hari | [PSEUDO] |
| Gulliver (`gul`) | Kode jadwal 1; `JohnnyRequirePartsNum`=5 per pergantian hari; `JohnnyHelpCount` 30 → resep golden shovel | [PSEUDO] / [EF] |
| Daisy Mae (`boc`) | Indeks hari 0 dan nilai save ≥2; `BocBuyCount`, `FirstKabuBuy`, `FirstKabuPattern` | [PSEUDO] / [EF]; harga [NATIVE] |
| Celeste (`ows`) | Indeks hari = `+0x74` di jadwal, malam saja; resep per zodiak (`OwsThisZodiac` 1–12); bintang jatuh (`0x4ae640`) | [PSEUDO] / [EF] |

Yang belum ditemukan **[NATIVE]**: penulis 7 kode dan `+0x74`, yaitu algoritma pembuat jadwal mingguan. Pencariannya lihat §8.

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
| 1 | Pembuat jadwal mingguan (7 kode + `+0x74`) | Sudah disingkirkan: konsumen `0xfdc020`, `0xc6f1a0`, `0xfdb6e0`, `0xcf9cf0`, `0xbe09d0`, `0xf32fa0` (konstruktor layout save). Sisa kandidat yang memakai descriptor `0x33d50a8` lewat vtable (tanpa pemanggil langsung): `0x101400`, `0x260370`, `0xcf420`, `0x2b2ac0` (eksekusi `CancelTodayVisitorNpc`), `0x488980` |
| 2 | Siapa ingin pindah keluar | `0xf87670` (`IsMovingConsultationToPlayer`), pemanggil `0xf8c540` → `0xf8d860` |
| 3 | Rumus skor Nature/Life | penulis float `+0x240`, `VillageScoreMgr` |
| 4 | Hari konser K.K. biasa | fungsi perujuk `NormalLive` (§3) |
| 5 | Harga lobak dan stok toko | belum ada titik masuk string; mulai dari flag `FirstKabuPattern` |
| 6 | Prosesor yang belum dibaca | `0xf8f190`, `0xf7d4c0`, `0xfc1b80`, `0xbdfd40`, `0xf8b460` (tujuan RNG) |
| 7 | Menaikkan [PSEUDO] menjadi terbukti | emulasi fungsi fasilitas seperti tahap mekanik terdahulu |
| 8 | Format save | konstruktor layout save `0xf32fa0` (pemanggil `0xf30220`, `0xf416c0`) |

Antrian yang sama, dalam bentuk yang bisa dibaca mesin dan ditandai statusnya, ada di [re_queue.json](re_queue.json).
