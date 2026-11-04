# Skenario gameplay lengkap ACNH 1.0.0

Tanggal: 4 November 2026. Dokumen ini melengkapi [GAMEPLAY_FLOW](GAMEPLAY_FLOW.md), yang membahas urutan progres cerita. Di sini skenario disusun menurut skala waktu (satu hari, satu minggu, satu tahun), ditambah siklus villager, pengunjung khusus, dan timeline progres dalam hitungan pergantian hari.

Label bukti sama dengan GAMEPLAY_FLOW: **[EF]** EventFlow, **[NATIVE]** belum dibaca, **[PSEUDO]** pseudocode otomatis yang belum dieksekusi, **[TXT]** teks dialog. Ada satu label tambahan:

| Label | Arti |
|---|---|
| **[TBL]** | Nilai langsung dari tabel BCSV (`output/tables_resolved/`) |

Data mesin untuk dokumen ini: [`output/gameplay/native_flag_refs.json`](../output/gameplay/native_flag_refs.json) (pipeline pergantian hari dan bacaan pseudocode), [`flag_index.json`](../output/gameplay/flag_index.json), dan [`trees/`](../output/gameplay/trees/).

## 1. Model state

### Layout save

**Terbukti native (emulasi).** `tools/save_layout_native.py` menjalankan konstruktor layout save `0xf32fa0` langsung dari NSO lewat `tools/nso_sandbox.py`, lalu menulis `output/gameplay/save_layout.json`. JSON itu memuat 88 member yang dipilih sampai kedalaman 2 atau bernama, serta sensus penuh 43.292 node: 151 alamat vtable unik dan 76 ukuran data. Ukuran setiap tipe terbukti lewat slot vtable 3; nama kelas C++-nya belum ditemukan. Pemindaian string ExeFS `main` juga tidak menemukan anchor RTTI standar `__ZTI`/`__ZTS` atau `_ZTI`/`_ZTS`, jadi label kelas tidak dapat dipulihkan dari nama RTTI yang tertanam di biner.

- **Struktur node** (0x38 byte): `+0x00` vtable (tipe), `+0x10` offset data, `+0x18` anak pertama, `+0x20` saudara. Ukuran data dikembalikan oleh slot vtable 3.
- **Offset `base + OFF`** di pseudocode (`F_ee9350`) adalah offset node (`node`), bukan offset data.
- **Data save utama** berukuran `0x4fa0d8` byte.
- **Ukuran yang cocok dengan bacaan [PSEUDO] sebelumnya:** member villager `0xa8` = `0x1d6d48`, jadwal pengunjung `0x20a210` = `0x78`, skor pulau `0x24fdb0` = `0x250`.

### Bacaan yang sudah terbukti native

`tools/gameplay_native.py` menjalankan fungsi asli dari NSO lewat `tools/nso_sandbox.py` (unicorn). Hasilnya ditulis ke `output/gameplay/gameplay_native.json`. Stub yang dipakai: RNG, flag, dan pencarian baris kalender. `nn::time` dilayani dengan `datetime` Python.

| Fungsi | Yang dicek | Hasil |
|---|---|---|
| `0xd34a20` | level keakraban < 30/60/100/150/200 → 1–6 (§5.1) | lulus |
| `0x15c6910`…`0x15c69a0`, `0x15c4db0` | bobot kategori skor pulau dan denda duplikat (GAMEPLAY_FLOW §10.1) | lulus |
| `0xfc6d00` | 3000 minggu harga lobak, RNG sama: 12 harga, pola, dan awal puncak identik dengan model Python di harness (§3.7) | lulus |
| `0xf0330` | NormalLive: Sabtu; `Before` mundur; `Skip` batal; `Same` tetap (§3.6) | lulus |
| `0xfdafa0` | Daisy Mae: Minggu dan state toko ≥ 2 (§3.5) | lulus |
| `0xfdc020` | kode pengunjung hari ini = `codes[hari]`, kode ≥ 10 → 0 (§3.2) | lulus |
| `0xf7d7e0` | tamu campsite: 0/5/10/15/20% untuk ≤2/3/4/5/≥6 hari (§2.1) | lulus |
| `0xfcc300` | Able Sisters: kit ada → +1 hari `TailorConstruction1` = 1 → +2 hari state 2 (`TailorBuilt`, `TailorBuiltToday`); 2 hari terlewat sekaligus → langsung buka tanpa `Today`; tanpa kit tetap state 1 | lulus |
| `0xf77050` | tenda museum dan upgrade: kit → state 2; `MuseumGrowupEnable1` + satu hari → hitungan 1; hari berikutnya → state 3 dan `Museum2Built`. Flag `*Today` hanya pada tepat satu hari berlalu | lulus |
| `0xf26330` | campsite: kit → state 2, `CampSiteBuilt`, `CeremonyBuildCampSite`, `CampSiteBuiltToday`; tanpa kit tetap state 1 | lulus |

Bacaan lain tetap [PSEUDO] sampai ada kasus emulasinya.

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
| 4 | `0x4ae640` | doa bintang (`PrayStarToday` → `StarPieceGrowCount`, lalu reset); batu uang (flag pemain `OccurrenceCoinStone`); botol pesan bila `MessageBottleAvailable`: per pemain tanpa `IsGetMessageBottle`, dan botol pertama (`PickedUpMessageBottle` = 0) berisi item DIY `0x227a` atau `0x1be1` (lempar koin RNG harian `0xf53500`). Pemilihan memakai bitset/kandidat sel bidang 0x8000 dan query penempatan umum `0x4ad1f0`; alamat sel pantai atau mask pantai khusus belum terbukti. |
| 5 | `0xd21110`, `0xf8ab90`, `0xfbd830` | rumah NPC: `0xd21110` memuat `Param/NpcHouse/<spesies><nn>.byml` untuk villager yang menetap (hanya membaca `AbandonedHouse`); jadwal DIY NPC; sapaan pertama |
| 6 | `0xf8b460`, `0xf8bf40` | jenis hari. Pada hari biasa dengan `BuiltTownOffice`, `EarlyOrLate` semua villager direset: 2 → 3, selain itu → 0. Lalu dua undian `rand100 < min(10 × villager, 80)`, masing-masing memilih villager berbobot `ContinuousNormalDay` (≥2); pilihan pertama diberi 1, pilihan kedua 2 |
| 7 | `0xd22440` | NPC untuk Countdown, Fishing Tourney, Bug-Off |
| 8 | `0xd257d0` | obrolan sapaan villager (`AppFirstTalk`, `AppWelcomeMigrantsTalk`, …) |
| 9 | `0xbdfd40` | aktivitas kelompok villager: per pemain, flag `ReservedNpcGroupActivity{Morning,Noon,Evening,Nignt}` diisi acak (25% per slot) dari `NpcLife`/`NpcInterest` sesuai level pulau; dilewati pada hari K.K. atau event |
| 10 | `0xfd0700` | `DailyQuestFirstFivePointToday` (Nook Miles+ ×5) |
| 11 | `0xfd9d10`, `0xfda740` | pengunjung khusus (§6) dan posisi spawn pengunjung hari ini (§3) |
| 12 | `0xf535e0` | `PlayReportDaily` |

Dispatcher `0xf545f0` sendiri memanggil, berurutan:
1. `0xf234f0` (papan pengumuman);
2. `0x6601a0` (papan toko, Gyroid plaza, `VillageDaysCount`);
3. `0xf6130` (event global: `GlobalEventReady` → `GlobalEventAvailable`, tanda turnamen terlewat `InsectFesFinished`/`FishFesFinished`, `TodayGlobalEventId`, jadwal ulang tahun per pemain `0xf920f0`);
4. `0xfc4560`, `0xf77050`, `0xf7d4c0` (tamu campsite: pasti bila `CampFirstCamperVisit`, selain itu 5/10/15/20% untuk 3/4/5/≥6 hari sejak tamu terakhir), `0xf26330`, `0xf6a730`, `0xfd8920` (K.K., pembuat jadwal pengunjung mingguan `0xfd8a80`, validasi `0xfd9620`; §3), `0xfc1b80` (rumor: `RumorPFavoriteProgressDays` += hari), `0xf8f190` (member `+0x20d310` = 2), `0x10c26e0` (struktur);
5. `0xf91b90` (hari main, Wisp, `MarketBuiltMyVillage`), `0xf84320` (pindah keluar dan masuk villager, §5.1–5.2), `0xf40e0` (papan event dan ulang tahun).

**Batas bukti member `+0x20d310`:** `0xf8f190` menulis nilai `2` setiap pergantian hari. Pemindaian konstanta di indeks dan bacaan pseudocode saat ini tidak menemukan pembaca. Member tetangga `+0x20d3b8` adalah payload papan pengumuman, tetapi kedekatan offset tidak membuktikan hubungan makna; fungsi `+0x20d310` tetap belum diketahui.

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
- Hari dipilih seragam acak: popcount `0x198b590`, bit ke-n `0x198b630`, dan xorshift128 `0x19aa0e0` dengan state dari slot TLS. **[PSEUDO]** Slot TLS (`0x32d2b68`) berisi konteks thread `+0x60` → `+0xd4`, yaitu `sead::Random` milik thread. RNG ini di-seed sekali saat thread dibuat (`0x19a2d10` → `0x19a9fe0`) dari `nn::os::GetSystemTick`. Jadi jadwal **tidak** ditentukan oleh tanggal, berbeda dari RNG harian `0x35e9510`.

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
- **[TBL]** Konser K.K. biasa (`NormalLive`, `EventBegin=16`) dan konser ulang tahun (`BirthdayLive`, `EventBegin=12`) tidak menyimpan tanggal di `CalendarEventParam`. Tanggalnya dihitung native (lihat 3.6).
- **[EF]** Hari jual lobak Daisy Mae tidak ada di EventFlow; aturan native-nya ada di `0xfdafa0` (atas). Harga lobak ada di 3.7.

### 3.6 Tanggal konser K.K.

**[PSEUDO]** Pencarian event (`0xf2a30` → `0xf2aa0` → `0xf1e20` → `0xf1360`) membandingkan label event dengan lima string global (`0xfe390`), lalu memanggil fungsi tanggal khusus:

| Label | Fungsi | Aturan |
|---|---|---|
| `PlayerBirthday` | `0xefe10` | ulang tahun salah satu pemain (member pemain `+0x16a08`) |
| `NpcBirthday` | `0xf01e0` | ulang tahun villager |
| `NormalLive` | `0xf0330` | lihat di bawah |
| `BirthdayLive` | `0xf11b0` | lihat di bawah |
| `FirstLive` | `0xffbc90` | dipesan lewat `TkkFirstLiveReserved` (GAMEPLAY_FLOW §10) |

Enum `EventType` di rodata `0x29b9f72` = `Global, Region, Other, Totakeke, None`; baris `None` dilewati. Enum `TkkSkip*` di `0x298d19c` = `Before`(0), `Skip`(1), `Same`(2).

**NormalLive** (`0xf0330`), hanya bila `TkkFirstLive` ON:

1. Kandidat = hari Sabtu dari minggu Minggu–Sabtu tanggal itu (`tanggal + (6 − hari)`, hari dari `0x1fbd50`, 0 = Minggu).
2. Bila kandidat tidak punya event kalender (`0xf0790`), konser jatuh di hari itu.
3. Bila ada event, kolom `TkkSkipNormal` event itu menentukan:
   - `Same` → konser tetap di hari itu;
   - `Skip` → tidak ada konser minggu itu;
   - `Before` → mundur satu hari dan ulangi, paling jauh sampai Senin. Bila Senin pun `Before`, tidak ada konser.
4. Di tabel, `Before` dipakai turnamen memancing, turnamen serangga, dan Countdown. Event lain `Same`, dan tidak ada yang `Skip`.

**BirthdayLive:**

- **Penjadwal** (`0xf920f0`, per pemain dari `0xf6130` saat pergantian hari): mulai dari hari ini + 21 lalu mundur hari demi hari sampai hari ini. Hari pertama yang sama dengan ulang tahun pemain (member `+0x11478`, `0xefc70`) menjadi kandidat.
- **Konflik event:** bila kandidat punya event kalender, `TkkSkipBirthday` (`0xf6090`) menentukan hasilnya:
  - `Same` → tetap;
  - `Skip` → tidak ada tanggal;
  - `Before` → mundur ke hari sebelumnya.
- **Simpanan:** tanggal disimpan di `+0x34942` (`0xf41fd0`). Pada hari itu villager mengirim pesan ulang tahun (`BDayMsgSenderNNpcUniqueID0/1`).
- **Pemeriksa** (`0xf11b0`): konser terjadi bila `TkkFirstLive` ON dan ada pemain yang:
  - punya `TotakekeLiveCount > 0` (pernah menonton K.K.);
  - tanggal di member pemain `+0x17370` (deskriptor `0x33d5868`) sama persis (tahun, bulan, hari) dengan hari ini.

  **Terbukti native (layout):** emulasi konstruktor rekaman pemain `0xf8f580` menunjukkan node `0x17370` → data `+0x34942`, ukuran 4. Jadi BirthdayLive memeriksa tanggal yang dijadwalkan `0xf920f0`. Ulang tahun pemain (node `0x16a08`) berada di data `+0x11478`, ukuran 2.

**Jam** (`0xfdb150`): pada hari konser, fungsi ini mengembalikan 1 bila jam < `EventBegin` event itu (`NormalLive` 16, `BirthdayLive` 12) dan 2 bila sudah lewat. Nilai 3 dipakai untuk `FirstLive`, atau bila jam sekarang < 5. `0x1fbf00` memindahkan waktu sebelum 05:00 ke hari permainan sebelumnya, jadi dini hari sesudah hari konser masih dihitung malam konser.

Jadwal pengunjung (§3.3–3.4) menghindari hari-hari ini karena `0xfda940`, `0xfdad10`, `0xfdae20`, dan `0xfd9620` memanggil `0xf2a30` dengan label yang sama.

### 3.7 Harga lobak dan stok toko

**[PSEUDO]** Harga lobak dibuat oleh `0xfc6d00`, dipanggil `0xfc7b40` dari prosesor toko `0xfc4560`.

**Kapan dibuat ulang:** saat pertama kali jalan, atau saat hari Minggu minggu berjalan (tanggal − hari) berbeda dari minggu permainan sebelumnya. Saat pertama kali, pola awal diambil acak 0–3.

**Struktur** (u32):

| Offset | Isi |
|---|---|
| `+0x00` | harga dasar = acak(21) + 90, jadi 90–110 |
| `+0x04`, `+0x08` | Minggu pagi/sore, diisi lalu dinolkan |
| `+0x0c`…`+0x38` | Senin pagi s.d. Sabtu sore, 12 harga |
| `+0x3c` | pola |
| `+0x40` | awal puncak |

Harga = `int(rate × dasar + 0.99999)`, dengan u = acak [0, 1).

**Pola minggu depan** dari pola sekarang (r = acak 0–99):

| Pola sekarang | → 0 | → 1 | → 2 | → 3 |
|---|---|---|---|---|
| 0 | r < 20 | 20–49 | 50–64 | ≥ 65 |
| 1 | < 50 | 50–54 | 55–74 | ≥ 75 |
| 2 | < 25 | 25–69 | 70–74 | ≥ 75 |
| 3 | < 45 | 45–69 | 70–84 | ≥ 85 |

Bila `FirstKabuBuy` ON dan `FirstKabuPattern` masih OFF, `FirstKabuPattern` dinyalakan dan pola dipaksa 3. Artinya minggu sesudah pembelian lobak pertama selalu memakai pola 3.

**Bentuk tiap pola** (rate per setengah hari, Senin pagi = indeks 2):

- **Pola 0:** naik dan turun bergantian, 12 slot total:
  - fase tinggi 1: acak(7) slot, rate 0.9–1.4;
  - fase turun 1: 2 atau 3 slot, mulai 0.6–0.8, tiap slot turun 0.04–0.10;
  - fase tinggi 2;
  - fase turun 2: 5 − panjang fase turun 1;
  - fase tinggi 3. Panjang fase tinggi 2 + 3 = 7 − fase tinggi 1, dan fase tinggi 3 = acak(itu).
- **Pola 1:** puncak dimulai di indeks acak(7)+3, yaitu Senin sore s.d. Kamis sore.
  - Sebelum puncak: mulai 0.85–0.9, tiap slot turun 0.03–0.05.
  - Lima slot puncak: 0.9–1.4, 1.4–2.0, **2.0–6.0**, 1.4–2.0, 0.9–1.4.
  - Sesudahnya: 0.4–0.9.
- **Pola 2:** turun terus dari 0.85–0.9, tiap slot turun 0.03–0.05.
- **Pola 3:** puncak dimulai di indeks acak(8)+2.
  - Sebelum puncak: mulai 0.4–0.9, tiap slot turun 0.03–0.05.
  - Puncak: 0.9–1.4, 0.9–1.4, lalu r₁ − 1, r, r₁ − 1, dengan r = 1.4–2.0 dan r₁ = acak(1.4, r) × dasar.
  - Sesudahnya: mulai 0.4–0.9, tiap slot turun 0.03–0.05.

Konstanta float dibaca dari rodata (`0x29d5e8c` = 0.9, `0x29d5d94` = 1.4, `0x29d5e28` = 0.6, …). RNG yang dipakai adalah `0x19aa0e0` dengan state TLS (`0x33d2b68`), sama seperti pembuat jadwal pengunjung. Seed-nya berasal dari tick sistem, bukan tanggal (§3.3), jadi pola tidak bisa dihitung ulang hanya dari tanggal.

**Stok harian.** Semua toko memakai pola yang sama:

1. himpunan item yang sedang musim untuk tanggal itu (`0xab33e0`, dari `ItemSeasonalityParam` utara/selatan);
2. ∩ `ItemKind` tertentu (`0xa0fd00`);
3. ∩ `ItemFrom` tertentu (`0x276fb0`/`0xa0fd40`);
4. ambil acak (`0xa120c0`, RNG `0x19aa040` di-seed dari RNG TLS).

Enum `ItemFrom` ada di rodata `0x29b535d`.

Untuk Nook's Cranny, `0xfd0630` memilih pembuat stok dari state toko: state 0–1 → `0xfce9e0`, state 2 → `0xfceb90`, dan state 3 → `0xfcf660`. Ketiga pembuat stok menyusun komponen mask musim ∩ `ItemKind` `{Ftr, DoorDeco, Tambourine}`; pembuat state 2–3 menggabungkannya dengan filter tambahan. Nilai `ItemFrom` yang terlihat pada filter mencakup `ShopDefault`/`ShopMiscGoods` untuk state awal; `ShopLv1`/`ShopLv2` serta filter payung/kertas bungkus pada state 2; dan tambahan `ShopSeasonSale`, `ShopLargeGoods`, serta `ShopHighClass` pada state 3. Filter dua pilihan pertama state 0–1 sudah dipastikan. Tiga filter tambahan `0xfcdfe0` kini terpetakan sebagai sumber `ItemFrom` yang mengikuti bulan; pengelompokan filter lain ke tiap ambilan state 2–3 masih terbuka.

**Filter state awal dan sumber dinamis yang terbukti dari pseudocode, disassembly, dan tabel.** Pada `0xfce9e0`, dua pilihan pertama dibuat dari irisan mask item musim, `ItemKind` `{0, 77, 32}`, dan `ItemFrom` `{1}`. Daftar enum `ItemKind` memberi label `Ftr`, `DoorDeco`, dan `Tambourine`; baris `ItemFrom` bernilai 1 adalah `ShopDefault`. Dari 23 baris `ItemParam` dengan `ItemFrom=ShopDefault`, semuanya berjenis `Ftr` sebelum filter musim. Ketiga pembuat state toko juga menyusun komponen mask musim ∩ `ItemKind` `{0, 77, 32}`; state 2–3 menambahkan filter lain yang belum dapat dipasangkan dengan tiap ambilan.

`0xfcdfe0` membuat tiga filter `ItemFrom`. Byte `+0x925` dan `+0x924` pada data node save `+0x20d0e0` adalah indeks 0–7 ke tabel sumber; pemilih `0xf50ad0` menggunakan bulan argumen toko `+10`, menggeser bulan enam posisi dalam mode hemisphere alternatif (`+0x651fc`), mengecualikan dua indeks tersimpan, lalu memilih sumber lain yang mask bulannya cocok. `0xf50f50`/`0xf51040` mengubah indeks tersimpan menjadi nilai `ItemFrom`; `0xf50e40` mengubah pilihan baru. `ItemFrom` dibuktikan karena ketiganya masuk ke konstruktor predikat `0xb0fd40` yang sama dengan filter statis di `0xfce9e0`, `0xfc8760`, dan `0xfca870`. Label ordinal dibaca dari enum native berbentuk daftar koma di rodata `0x29b535d`; ordinal `ShopDefault=1` dan `ShoesBagShop=0x34` cocok dengan konstanta filter Nook/Kicks. Mask memakai bit 0 untuk bulan 1 sesudah penyesuaian hemisphere.

| Indeks | Nilai `ItemFrom` | Mask bulan |
|---:|---|---:|
| 0 | `ShopSeed_Anemone` (`0x57`) | `0x81f` |
| 1 | `ShopSeed_Hyacinth` (`0x55`) | `0x00e` |
| 2 | `ShopSeed_Tulip` (`0x58`) | `0x03c` |
| 3 | `ShopSeed_Rose` (`0x56`) | `0xe70` |
| 4 | `ShopSeed_Cosmos` (`0x54`) | `0x7c0` |
| 5 | `ShopSeed_Lily` (`0x53`) | `0x1e0` |
| 6 | `ShopSeed_Chrysanthemum` (`0x52`) | `0xf81` |
| 7 | `ShopSeed_Pansy` (`0x59`) | `0xc0f` |

Nilai sumber ketiga bergantung pada bulan dan indeks yang sudah tersimpan; jumlah kandidat yang diambil dari tiap filter (`1` pada state <2, `2` pada state 2, semua pada state 3). Filter per ambilan lain pada state 2 dan 3 tetap belum dapat dipasangkan satu per satu.

**Pembaca harga dasar lobak.** Generator `0xfc6d00` menulis harga dasar pada kata pertama blok. Query native `0x4cca80` mengambil node save `+0x208ed0`, membaca `u32` pada `data +0x00`, lalu memakai nilainya pada perbandingan jumlah pembelian yang dikalikan kuantitas. Pembaca harga jual harian terpisah: `0xaab8c0` memanggil `0xfc7c70`, yang memilih slot di `data +0x04 + 4 × (2 × hari + pagi/sore)`. Hubungan langsung query `0x4cca80` dengan halaman UI `KabuBuyPage` belum ditemukan.

| Fungsi | Toko | Pool |
|---|---|---|
| `0xfd0630` → `0xfce9e0`, `0xfceb90`, `0xfcf660` | Nook's Cranny | Pool filter berubah menurut state toko; enum `ItemFrom` yang ditemukan: `ShopDefault`, `ShopMiscGoods`, `ShopLv1/2`, `ShopLargeGoods`, `ShopHighClass`, `ShopSeasonSale`, `ShopUmbrellaLv1/2`, `ShopWrappingPaper` |
| `0xfc56c0` | Saharah (`LaurentWallFloor`) | 5 slot: `Rug` × `RugL`, `RugM`, `RugS`; `RoomWall` dan `RoomFloor` × `LaurentWallFloor` |
| `0xfc8760` | Kicks | `ShoesBagShop` × `Shoes`/`Socks`/`Bag`; 32 slot (`+0x00`…`+0xf8`) dikosongkan dulu |
| `0xfca870` | Able Sisters / Label | `Tailor`, `TailorMarketOnly`, `HgcQuestReward` × `Tops`, `Bottoms`, `OnePiece`, `Cap`, `Helmet`, `Accessory`, `Socks`, `Shoes` (flag `HgcVisitFlagForTailor`) |
| `0xfc6300` → `0xfc5d60` | pengisi katalog Nook's Cranny | Mengosongkan 64 slot di blok `+0x2b14`, lalu mengambil 2 `Ftr`, 2 `Tops`, dan masing-masing 1 `Bottoms`, `Cap`, `Accessory`, `Shoes`, `Music`; indeks `ItemKind` = 0, 6, 9, 12, 14, 11, 72. Tiap kandidat melewati filter musim/katalog; aturan tepat pemilihan sumber masih terbuka. |

**Jumlah ambilan Nook's Cranny** (`0xfd0630`, argumen n dari `0xfce170(himpunan, n)`; array stok dikosongkan dulu oleh `0xfcdc10`):

| State toko | Fungsi | Ambilan |
|---|---|---|
| < 2 | `0xfce9e0` | 2, plus 1 dari himpunan pulau (member `0x20d0e0`) |
| 2 | `0xfceb90` | 4, 4, 1, 1, plus ambilan helper `0xfcf580`/`0xfce710` dan 2 dari member `0x20d0e0` |
| 3 | `0xfcf660` | 8, 8, 2, 2, 1, 1, 1, 1, 1, plus helper |

**Blok toko** (node `0x1f3e98`, lihat `save_layout.json`):

| Offset | Isi |
|---|---|
| `+0x4` | Saharah (5 × 8 byte) |
| `+0x2c` | Able Sisters |
| `+0x1300` | Kicks (32 × 8) |
| `+0x1400` | stok Nook's Cranny |
| `+0x2ad0` | rekaman lobak (`0x44` byte) |
| `+0x2b14` | buffer 64 item untuk katalog Nook's Cranny (`0xfc6300` → `0xfc5d60`); helper menandai `Shop.Catalog.%s` setelah kandidat dipilih |

**Harga jual** (`0xaab8c0`):
- **Lobak:** `rekaman[1 + 2 × hari + (jam > 11)] × ItemParam.Price` (`0xfc7c70`). Karena slot Minggu bernilai 0, lobak tidak bisa dijual hari Minggu.
- **Item lain:** `Price × tumpukan / 4`.

Pembaca harga dasar `+0x00`, yang diduga menjadi harga beli Daisy Mae, belum terisolasi. `0xfc6d00` menulisnya dan memakai nilai itu untuk membuat 12 harga; `0xfc7c70` memakai harga slot harian untuk harga jual lobak. Rujukan UI `KabuBuyPage` dan `HowmuchBuyItem`/`HowmuchSellKabu` ditemukan, tetapi aliran nilainya menuju harga dasar belum terbukti.

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

**[PSEUDO] Rincian yang dulu terbuka:**

- **`0xf8c540`** adalah jalur plot dan undangan (`FromSettlerQuest`, `InducementFlag`, `HasAcquaintanceship`). Selama quest 3 rumah, villager dipilih dengan filter pemukim `0xf8de30` dan dipindahkan masuk oleh `0xf8de90`. Fungsi ini juga mengisi `IsNpcIncreased`/`Is3rdNpc` dan membangun rumah (`0xf826c0`, `0xf814c0`).
- **`0xf8d210`** memindahkan masuk slot dengan `MoveInOrder` terkecil di antara slot yang `MoveInCompletion`-nya masih OFF, lalu memajukan `MoveInOrder` slot lain.
- **`AbandonedHouse`:** `0xd36400` hanya *membaca* flag ini (`0xf49540`). Penulisnya ada tiga:
  - `0xcb7550`: nilai 1. Villager lalu dikeluarkan (`0xf8a410` jenis 1) dan `InducementAtMovingDay` dinyalakan.
  - `0xcc5a40`: nilai 2.
  - `0xf889e0`: reset ke 0.

  `0xf889e0` juga dipanggil oleh `0xbc0190` dan `0xbc0430`; keduanya tidak memiliki caller langsung di indeks dan konteks callback-nya belum teridentifikasi, jadi jalur lokal non-jaringan belum terbukti. Jalur lain yang ditemukan adalah dispatcher `0xc7ea00` (← `0xbcef20` ← … ← `0xb65410` `NetConfig`), yang konsisten dengan sinkronisasi multipemain. Fungsi `0xf855c0` hanya menghitung villager yang menetap dengan membaca `AbandonedHouse` dan `MoveInCompletion`; ia bukan penulis flag.

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

Pertanyaan yang dulu terbuka di jadwal ini sudah terjawab **[PSEUDO]**:
- **RNG TLS** `0xfd8a80` adalah RNG thread yang di-seed dari tick sistem, bukan RNG harian (§3.3).
- **Nilai pemain 0–8** (`0xef8520`, deskriptor `0x33dc730`, node `0x17cd48 + i × 0xe3b8`) adalah level rumah: play report `0xec4060` melaporkannya sebagai `HouseLevel`. Saharah dan Harvey butuh level rumah ≥ 2.
- **Titik tetap `0x469680`** = `(*0x33d6f98) + 0x40` adalah posisi plaza event. `0x135440` mengembalikannya untuk tempat bernama `EventPlaza`, jadi Label, Mabel, dan Kicks berdiri di plaza + (15, 0, 20).

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
| 1 | Menaikkan [PSEUDO] lain menjadi terbukti | tambah kasus di `tools/gameplay_native.py`: toko `0xfc4560`, gedung museum (tahap 2 `0xf77050`), undian pindah (`0xf847f0`), jadwal pengunjung (`0xfd8a80`), penjumlah skor (`0x15c61f0`) |

Antrian yang sama, dalam bentuk yang bisa dibaca mesin dan ditandai statusnya, ada di [re_queue.json](re_queue.json).
