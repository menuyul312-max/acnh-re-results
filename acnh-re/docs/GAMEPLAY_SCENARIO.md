# Skenario gameplay lengkap ACNH 1.0.0

Tanggal: 4 November 2026. Dokumen ini melengkapi [GAMEPLAY_FLOW](GAMEPLAY_FLOW.md), yang membahas urutan progres cerita. Di sini skenario disusun menurut skala waktu (satu hari, satu minggu, satu tahun), ditambah siklus villager, pengunjung khusus, dan timeline progres dalam hitungan pergantian hari.

Label bukti sama dengan GAMEPLAY_FLOW: **[EF]** EventFlow, **[NATIVE]** belum dibaca, **[PSEUDO]** pseudocode otomatis yang belum dieksekusi, **[TXT]** teks dialog. Ada satu label tambahan:

| Label | Arti |
|---|---|
| **[TBL]** | Nilai langsung dari tabel BCSV (`output/tables_resolved/`) |

Data mesin untuk dokumen ini: [`output/gameplay/native_flag_refs.json`](../output/gameplay/native_flag_refs.json) (pipeline pergantian hari dan bacaan pseudocode), [`flag_index.json`](../output/gameplay/flag_index.json), dan [`trees/`](../output/gameplay/trees/).

## 1. Model state

### Layout save

**Terbukti native (emulasi).** `tools/save_layout_native.py` menjalankan konstruktor layout save `0xf32fa0` langsung dari NSO lewat `tools/nso_sandbox.py`, lalu menulis `output/gameplay/save_layout.json`. JSON itu memuat 88 member yang dipilih sampai kedalaman 2 atau bernama, serta sensus penuh 43.292 node: 151 alamat vtable unik dan 76 ukuran data. Ukuran setiap tipe terbukti lewat slot vtable 3. Perbandingan eksternal terhadap `SaveLand` pada [skema save 111/103](https://github.com/Treeki/CylindricalEarth/blob/bb09c0ee71a4aa6011de088b88ea55fdee0bf6e9/savefile/save_schema_111_103.json) menemukan kecocokan offset/ukuran untuk 143 dari 151 sampel vtable; pada 88 member terpilih, 85 punya jalur yang cocok setelah kedalaman node disejajarkan. [Crosswalk lengkap](../output/gameplay/save_layout_external_crosswalk.json) mempertahankan kandidat dan ambiguitas. Ini kandidat nama lintas versi, bukan RTTI lokal: executable yang dianalisis adalah 1.0.0, sementara skema publik berlabel 111/103. Pemindaian seluruh empat NSO yang tersedia juga tidak menemukan nama kelas game.

- **Struktur node** (0x38 byte): `+0x00` vtable (tipe), `+0x10` offset data, `+0x18` anak pertama, `+0x20` saudara. Ukuran data dikembalikan oleh slot vtable 3.
- **Offset `base + OFF`** di pseudocode (`F_ee9350`) adalah offset node (`node`), bukan offset data.
- **Data save utama** berukuran `0x4fa0d8` byte.
- **Ukuran yang cocok dengan bacaan [PSEUDO] sebelumnya:** member villager `0xa8` = `0x1d6d48`, jadwal pengunjung `0x20a210` = `0x78`, skor pulau `0x24fdb0` = `0x250`.

### Bacaan yang sudah terbukti native

`tools/gameplay_native.py` menjalankan fungsi asli dari NSO lewat `tools/nso_sandbox.py` (unicorn). Hasilnya ditulis ke `output/gameplay/gameplay_native.json`. Stub yang dipakai meliputi RNG, flag, pencarian baris kalender, serta accessor save/input untuk query lobak. Kasus ikan (`tools/creature_spawn_native.py`) mengontrol accessor baris/kolom tabel (diisi dari tabel asli ekstraksi lokal), gerbang jumlah tangkapan `0x5b8e30`, jam, kode cuaca, mode sesi, dan undian; loop, uji mask, jumlah bobot, transformasi undian, dan pilihan kumulatif berjalan native. Kasus jadwal pengunjung (`tools/visitor_schedule_native.py`) hanya mengontrol flag per nama, hari event kalender, hari konser K.K., indeks pola cuaca per tanggal, dan undian xorshift; lookup layout save, accessor fasilitas/rumah pemain, helper minggu/tanggal, dan pemilihan bit berjalan native. Kasus villager (`tools/villager_move_native.py`) hanya mengontrol flag per nama, penulis efek samping (rumah, memori, histori), rekaman keakraban per pemain, dan tanggal. Kasus pindah masuk memuat `NmlNpcParam.bcsv` asli dari ekstraksi lokal dan membangun tabel NPC dengan inisialisator game sendiri. `nn::time` dilayani dengan `datetime` Python.

| Fungsi | Yang dicek | Hasil |
|---|---|---|
| `0xd34a20` | level keakraban < 30/60/100/150/200 → 1–6 (§5.1) | lulus |
| `0x15c6910`…`0x15c69a0`, `0x15c4db0` | bobot kategori skor pulau dan denda duplikat (GAMEPLAY_FLOW §10.1) | lulus |
| `0xfc6d00` | 3000 minggu harga lobak, RNG sama: 12 harga, pola, dan awal puncak identik dengan model Python di harness (§3.7) | lulus |
| `0x3cca80` | Query harga lobak: jumlah kosong → 2; di bawah harga dasar × jumlah → 1; setter menerima ambang → 0; setter menolak → 2. Akses save/input/setter memakai stub terkontrol (§3.7) | lulus |
| `0xf0330` | NormalLive: Sabtu; `Before` mundur; `Skip` batal; `Same` tetap (§3.6) | lulus |
| `0xfdafa0` | Daisy Mae: Minggu dan state toko ≥ 2 (§3.5) | lulus |
| `0xfdc020` | kode pengunjung hari ini = `codes[hari]`, kode ≥ 10 → 0 (§3.2) | lulus |
| `0xf7d7e0` | tamu campsite: 0/5/10/15/20% untuk ≤2/3/4/5/≥6 hari (§2.1) | lulus |
| `0xfcc300` | Able Sisters: kit ada → +1 hari `TailorConstruction1` = 1 → +2 hari state 2 (`TailorBuilt`, `TailorBuiltToday`); 2 hari terlewat sekaligus → langsung buka tanpa `Today`; tanpa kit tetap state 1 | lulus |
| `0xf77050` | tenda museum dan upgrade: kit → state 2; `MuseumGrowupEnable1` + satu hari → hitungan 1; hari berikutnya → state 3 dan `Museum2Built`. Tes memasok flag upgrade; jalur hidup dari donasi ke flag belum tersambung end-to-end ([follow-up museum](MUSEUM_ART_GYROID_FOLLOWUP.md)) | lulus |
| `0xf26330` | campsite: kit → state 2, `CampSiteBuilt`, `CeremonyBuildCampSite`, `CampSiteBuiltToday`; tanpa kit tetap state 1 | lulus |
| `0xf847f0`, `0xf855c0` | undian pindah keluar: `r < 5 × menetap + penghitung` (hanya bila jeda 0, menetap ≥ 6, penghitung ≥ 5); jeda/penghitung; calon `AbandonedHouse`; `ForceMoveOut` (slot pertama saja); konfirmasi → status 2 → pergi (§5.1) | lulus |
| `0xf87670` | bobot pemilihan calon (float32, 3 pemain, pengurang level 6), seluruh 229 nilai undian; pengecualian slot; jendela ulang tahun pada tiga tanggal (§5.1) | lulus |
| `0xcc8ad0`, `0xcd4050` | tabel runtime dari `NmlNpcParam` asli: kepribadian = indeks enum `NpcLooks` di 397 baris; pool pindah masuk = 391 baris dengan `InitLive` ≠ 0 (§5.2) | lulus |
| `0xfd8a80`, `0xfda940`, `0xfdad10`, `0xfdae20` | 1500 minggu acak (state penjahit/museum, `BuiltTownOffice`, `carry_over`, event, konser, cuaca, minggu sama/berbeda, main pertama): semua field member jadwal dan jumlah undian sama dengan model §3.3. Sabtu/Minggu hanya Mabel atau Wisp; kode 9 tidak pernah ditulis; saat semua syarat terbuka dan hari kerja bebas, tepat satu anggota kolam tertunda (58 minggu) | lulus |
| `0xfd9620` | 3000 hari acak: kode hari ini, hari tambahan Wisp, dan hari Celeste sama dengan model §3.4 | lulus |
| `0xfd8920` | `TkkFirstLiveEnable` (hari berlalu, `IslandEvaluationClearTkkLive` ON, `TkkFirstLive` OFF), urutan pembuat → validasi, `RctInTent` per jam, `JohnnyRequirePartsNum` = 5 (576 sampel) | lulus |
| `0xf84f10`, `0xf8d860` | peluang pindah masuk (n, P, `NNpcContractProbablityAddPoint`); mask kepribadian; pemilihan dua tahap spesies → villager; fallback eksklusi; slot yang dikosongkan hari ini; NPC menunggu (§5.2) | lulus |
| `0x5b9ba0` | undian ikan per posisi: 3888 sampel atas tabel `FishAppear*`/`FishStatusParam`/`ItemParam` asli (2 belahan bumi × 12 bulan × 3 slot × 6 jenis air, cuaca, mode sesi, jumlah tangkapan, undian): hasil sama dengan model float32 §8.1 | lulus |
| `0x5b98b0` | undian ikan persen: 1584 sampel; `r = u × 100 >> 32`, baris sampah ikut, gagal gerbang → `0xfffe` (§8.1) | lulus |
| `0x5b9270` | gerbang ikan: Sirakansu hanya kode cuaca 4/5; mode sesi ≥ 2 membuang Can/Boot/Tire dan `Ore` (§8.1) | lulus |
| `0x5e3570`, `0x5e36b0`, `0x9f1870`, `0x9f1920` | jam → slot ikan (3) dan serangga (6), mask slot untuk rentang jam (576 pasangan) (§8.1, §8.2) | lulus |
| `0x95ebe0` | konstruktor `InsectAppearParam`: entri getter ke-k membaca kolom `Prob<Bulan><Slot>` dengan k = bulan × 6 + slot, dicek lewat hash kolom (§8.2) | lulus |
| `0x957940` | undian serangga pulau: 1008 sampel atas tabel `InsectAppearParam`/`InsectStatusParam` asli (2 belahan bumi × 12 bulan × 6 slot × 7 undian, termasuk 0, `0xffffffff`, `0x80000000`): ItemID sama dengan model §8.2 (bobot u16, `r = u × W >> 32`, pengurangan kumulatif, `0xfffe` bila kosong) | lulus |
| `0x958570` | saringan `AppearFg`: 85 serangga (57 ditolak), setiap bit `AppearFg` tunggal 0–23 menolak kecuali bit 3, plus 7 ID khusus (§8.2) | lulus |
| `0x4d7110` | jenis batu baru: satu undian RNG lapangan `0x344d100`, indeks `u × 5 >> 32` ke tabel StoneA–E; 3000 state acak, state RNG sesudahnya ikut dicek, tanpa stub (§10) | lulus |
| `0x7abd00` | jenis kerang: undian `0xf53420(100)` dari RNG harian asli dan dua tabel ambang musim (musim 0–3, 12.000 sampel); hanya lookup musim `0x2035f0` yang dikontrol (§10) | lulus |
| `0x7a7010` | batas kerang harian/total dari bitset pantai: 3/9, 8/9 (satu sisi), 10/16 (dua sisi); 409 bitset termasuk batas x = 98/100 dan z = 78/80/180/182 (§10) | lulus |
| `0xf50ad0` | pemilih spesies bunga pulau: bulan 0–13 × dua belahan bumi × 63 pola pengecualian × setiap posisi undian (5000 run); mask bulan, geser enam bulan di belahan selatan, pengecualian, dan fallback sama dengan model; hanya `0xf53420` yang dikontrol (§10.4) | lulus |
| `0xf50f50`, `0xf51040` | indeks `SpecialityFlower`/`VillageFlower` 0–7 → grup `ItemFrom` 0x57, 0x55, 0x58, 0x56, 0x54, 0x53, 0x52, 0x59; tanpa stub (§10.4) | lulus |
| `0xf509e0` | buah asli dan buah saudara pulau baru: 3000 state RNG thread; lima buah muncul, buah saudara tidak pernah sama dengan buah asli, byte paksa-apel memberi Apple. Akses save, cek keberadaan item (ID `ItemParam` asli), dua helper parameter item, dan tabel item-per-indeks dikontrol (§10.4) | lulus |
| `0x7ab350` | tempat pohon/kelapa di objek kerja sintetis: 195 kasus satu-fitur (pasir, satu/empat ubin air, set 5/9/10/11/18/19, ubin 1, tinggi ±4,9/±5, tepi lapangan) dan 1200 lapangan acak, kedua nilai `pantai`. Pasir, air, tinggi, `CliffLevel`, dan rect lapangan dikontrol; pemindaian set dan `0x7a2e10` native (§10.5) | lulus |
| `0x7a2e10` | lereng mode 0 dan 1 atas 600 lapangan acak; ambang 5 dan pengecualian `CliffLevel` sama / diagonal sebagian air (§10.5) | lulus |
| `0x4b5cc0` | tetangga bebas: 600 kasus atas set 1/3/20 dan rect lapangan terpotong; urutan tujuh tetangga, utara (0,−2) tidak pernah ditawarkan; `0xf53420` dikontrol (§10.5) | lulus |
| `0x3060b80`, `0x3060cb0` | tabel gulma 7 kode musim × 7 ID (1A, 1B, 1C, 2A, 2B, 2C, 3) dibaca dari memori NSO setelah relokasi; sama dengan urutan `Grow`/`Label` di `FgMainParam` (§10.3) | lulus |
| `0x4b6000` | tumbuh gulma: 120 lapangan sintetis (kepadatan, ubin siram, hari pertama atau bukan, argumen harian dan pulau baru, batas tercapai); urutan undian dan semua tulisan item sama dengan model (§10.3) | lulus |
| `0x4b63e0` | sebar gulma: 120 lapangan (tinggi ±5, ubin terisi, set 2 di luar rect, masker pulau baru, batas 150/1300 tercapai): tulisan anak, jumlah, set 17, set 2, dan penghitung `+0x2e144` sama dengan model. Akses lapisan item, `FgMainParam`, tinggi, dan RNG harian dikontrol (§10.3) | lulus |
| `0x4ba120` | konversi musim gulma: 30 lapangan, tiap kode musim, gulma campuran tujuh musim (§10.3) | lulus |
| `0x3d9b60`, `0xf77e00`, `0xf77f60`, `0xf780e0`, `0xf78130` | predicate pilihan Blathers dan SaveMuseum: 1.024 slot, sentinel `-2`, item 8 byte, tanggal packed `year/month/day` per-slot `+4`, marker `+0x3004`; gate Fossil/Fish/Insect dan duplicate check `0xff` diuji native dengan adapter terkontrol. Producer state marker `+0xb0d` ditelusuri ke `0xe68280`; label/domain nilainya masih terbuka (lihat [museum donation](MUSEUM_DONATION_FOLLOWUP.md) dan [art/gyroid](MUSEUM_ART_GYROID_FOLLOWUP.md)) | lulus dengan adapter |

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

**Batas bukti member `+0x20d310`:** node lokal `0x20d310` disejajarkan dengan `SaveLand.Office`; anaknya `0x20d348` disejajarkan dengan `SaveLand.Office.OfficeLevel` pada data `+0x4159f0`, ukuran 4. Kecocokan memakai offset, ukuran, dan kedalaman pohon pada skema lintas versi; simbol enum lokal belum ada. Inisialisasi root save `0xf5af30` memberi field data `+0x4159f0` nilai `1`; dispatcher `0xf545f0` kemudian memanggil `0xf8f190`, yang menulis `2` saat proses pergantian hari. Peralihan `1 → 2` terbukti lokal; arti enum kedua nilai dan pembaca lokal belum diketahui. Member tetangga `+0x20d3b8` tetap merupakan payload papan pengumuman yang terpisah.

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

- **Terbukti native** `0xfd8920`: `RctInTent` OFF pada jam 5–19, ON di luar jam itu. `JohnnyRequirePartsNum` di-set 5 bila hari berlalu > 0 atau main pertama.
- **[EF]** `Process_Daily`: keakraban Sable +1 bila diizinkan, hitungan beli lobak Daisy Mae, penghitung login Nook Stop (di-reset menurut `PlayerPastDaysFromLastPlay` dengan batas 2), resep zodiak Celeste, dan hadiah maskapai.

## 3. Satu minggu

Pembuatan jadwal (§3.3), validasi harian (§3.4), dan pembungkusnya `0xfd8920` **terbukti native** (emulasi, §1). Isi lain bagian ini **[PSEUDO]** kecuali diberi label lain, termasuk posisi spawn `0xfda740` dan spawner harian. Ringkasan mesinnya ada di `output/gameplay/native_flag_refs.json` → `data.visitor_schedule`.

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

### 3.3 Pembuatan jadwal (`0xfd8a80`) — terbukti native

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

### 3.4 Validasi harian (`0xfd9620`) — terbukti native

Setiap pergantian hari (hari berlalu > 0 atau main pertama), entri hari ini dicek. "Hari ini" = hari dalam minggu dari info pergantian hari `+8`; driver `0xf53a70` sudah menormalkan waktu itu ke 05:00 hari game (`0x1fbc00`), jadi jam 00:00–04:59 tetap memakai entri hari sebelumnya.

**Syarat sah per kode:**
- Gulliver dan Wisp selalu sah.
- Saharah sah bila ada pemain dengan nilai ≥ 2. Nilainya dibaca `0xef8520` dari member pemain `+0x17cd48`, descriptor `0x33dc730`, rentang 0–8. Nilai yang sama dipakai syarat Harvey, kemungkinan level rumah.
- Mabel sah bila `EnableHghStayField` ON, penjahit belum berdiri, dan bukan hari K.K. **[EF]** Flag itu ("Mabel boleh dipilih sebagai NPC pengunjung") dinyalakan `SNPC_rcm_03_RenualOpen:Rcm_RenualOpen1_ConvHgh` dan dimatikan `Player_Demo_HousingFinish:HousingFinish_Tailor_Built`.
- Kode lain sah bila bukan hari `NormalLive` atau `BirthdayLive`. Ini juga berlaku untuk hari kosong (kode 0) dan kode ≥ 10: keduanya tidak diganti Gulliver/Wisp, hanya dikosongkan pada hari event atau konser. Kode ≥ 10 tetap tersimpan; pembacanya `0xfdc020` mengubahnya menjadi 0.

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

Untuk Nook's Cranny, `0xfd0630` memilih pembuat stok dari state toko: state 0–1 → `0xfce9e0`, state 2 → `0xfceb90`, dan state 3 → `0xfcf660`. Ketiga pembuat menyusun komponen mask musim ∩ `ItemKind` `{Ftr, DoorDeco, Tambourine}`. State 2 dan 3 juga membangun filter kelas turunan melalui konstruktor `0xb0fd80`; filter itu berbeda dari predikat `ItemKind` dan `ItemFrom`. Urutan panggilan selektor dan penempatan ke bucket hari kini terbukti; yang belum terurai adalah keanggotaan item tiap bitset gabungan dan ID yang akhirnya terpilih.

**Filter state awal dan sumber dinamis yang terbukti dari pseudocode, disassembly, dan tabel.** Pada `0xfce9e0`, dua pilihan pertama dibuat dari irisan mask item musim, `ItemKind` `{0, 77, 32}`, dan `ItemFrom` `{1}`. Daftar enum `ItemKind` memberi label `Ftr`, `DoorDeco`, dan `Tambourine`; baris `ItemFrom` bernilai 1 adalah `ShopDefault`. Dari 23 baris `ItemParam` dengan `ItemFrom=ShopDefault`, semuanya berjenis `Ftr` sebelum filter musim. Ketiga pembuat state toko juga menyusun komponen mask musim ∩ `ItemKind` `{0, 77, 32}`; state 2–3 menambahkan filter lain yang belum dapat dipasangkan dengan tiap ambilan.

`0xfcdfe0` membuat tiga filter `ItemFrom`. Byte `+0x925` dan `+0x924` pada data node save `+0x20d0e0` adalah indeks 0–7 ke tabel sumber; pemilih `0xf50ad0` menggunakan bulan argumen toko `+10`, menggeser bulan enam posisi dalam mode hemisphere alternatif (`+0x651fc`), mengecualikan dua indeks tersimpan, lalu memilih sumber lain yang mask bulannya cocok. `0xf50f50`/`0xf51040` mengubah indeks tersimpan menjadi nilai `ItemFrom`; `0xf50e40` mengubah pilihan baru. `ItemFrom` dibuktikan karena ketiganya masuk ke konstruktor predikat `0xb0fd40` yang sama dengan filter statis di `0xfce9e0`, `0xfc8760`, dan `0xfca870`. Label ordinal dibaca dari enum native berbentuk daftar koma di rodata `0x29b535d`; ordinal `ShopDefault=1` dan `ShoesBagShop=0x34` cocok dengan konstanta filter Nook/Kicks. Mask memakai bit 0 untuk bulan 1 sesudah penyesuaian hemisphere.

**Filter kelas tambahan Nook.** Alamat pada paragraf ini adalah VA NSO mentah kecuali diberi label Ghidra: konstruktor `0xa0fd80` (Ghidra `FUN_00b0fd80`) menyimpan selector; vtable `0x30c6348` (Ghidra `0x31c6348`) mengarah melalui slot 0 ke predikat `0xaa82d0` (Ghidra `FUN_00ba82d0`), yang membandingkan selector dengan hasil helper `0xaa8ce0` (Ghidra `FUN_00ba8ce0`). Helper mengklasifikasikan item lewat lookup berbasis `ItemKind`; salah satu cabangnya membaca `ItemParam.DragSE` pada offset `+0x9c`. Pada cabang DragSE, ordinal 3–6 berarti `VeryHeavy`, `LightWheel`, `HeavyWheel`, dan `Floated`; ordinal 0–2 berarti `Light`, `Normal`, dan `Heavy`. Helper mempunyai cabang lain yang menghasilkan kelas turunan berbeda, jadi label DragSE hanya berlaku saat jalur itu dipakai. `0xfceb90` membangun selector `{5,6}` dan `{0..5}`; `0xfcf660` membangun `{5,6}` dan `{3,4}`. Himpunan ini digabung dengan filter sumber dan mask umum sebelum `0xfce710`/`0xfce170` memilih stok. Filter kelas terbukti ada, tetapi pemetaan akhir tiap himpunan gabungan ke tiap slot stok belum selesai.

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

Nilai sumber ketiga bergantung pada bulan dan indeks yang sudah tersimpan. `0xfcdfe0` membuat tiga pass terpisah: dua `ItemFrom` dari indeks save `+0x925/+0x924` dan satu sumber baru yang cocok dengan bulan. Masing-masing pass mengambil 1 item per hari pada state <2, 2 pada state 2, dan semua kandidat yang lolos pada state 3.

**Input harga lobak dan flow Daisy Mae.** Generator `0xfc6d00` menulis harga dasar pada kata pertama blok. Query NSO VA `0x3cca80` (Ghidra `FUN_004cca80`) mengambil node save `+0x208ed0`, membaca `u32` pada `data +0x00`, lalu membandingkannya dengan jumlah pembelian yang dikalikan kuantitas. Metadata registrasi mengidentifikasinya sebagai slot 6 `EventFlowQueryBoaCanSetKabu` (factory `0x45a7f0`, constructor `0x3cca20`, vtable `0x3053ac0`). Pada EventFlow lokal `SNPC_boc:boc_Buy`, event 29 menjalankan `EventFlowActionUITenKeyHandling` dengan `Type=cKabu`, event 30 membaca hasil menu, lalu cabang 0 menuju query `BoaCanSetKabu` pada event 36. Hasil query 0/1/2 menuju event 35/37/40. Query mengembalikan 1 bila nilai permintaan di bawah harga dasar × kuantitas; 0 bila setter menerima jumlah; 2 bila jumlah belum diisi atau setter menolak. Emulasi native dengan accessor save/input/setter terkontrol mengonfirmasi tiga kode hasil. Layout lokal `SwkbdTextAreaKaburiba` mempunyai pane input angka dan total. Tabel publik [NookKit 3.0.3](https://github.com/acnhmodding/nookkit/blob/16522dcb71f4b3c4f4d37d9cc6bf6676a5fca0b7/data/pages-3.0.3.tsv) memetakan `KabuBuyPage` ke layout itu, tetapi versinya berbeda dari dump lokal. Jadi urutan input-ke-query lokal terbukti; kaitan persis `Type=cKabu` ke kelas halaman pada build 1.0.0 belum dibuktikan. Rincian bukti ada di [`kabu_ui_binding.json`](../output/gameplay/kabu_ui_binding.json).

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
| < 2 | `0xfce9e0` | 2 dari filter umum; 3 pass sumber `ShopSeed` ×1 (`0xfcdfe0`) |
| 2 | `0xfceb90` | 2 helper ×2; 4, 4, 1, 1 dari filter lain; 3 pass sumber `ShopSeed` ×2 (`0xfcdfe0`) |
| 3 | `0xfcf660` | `fce710` 2; `fce170` 1; `fce710` 2, 1; three `ShopSeed` passes all; `fce170` 8, 8, 2, 2, 1×5 |

**Pemetaan keluaran per hari.** Save member `SaveShopZakka` (node `0x1f67f0`, data `+0x4100e8`) berisi tujuh bucket berjarak `0x200` byte. `0xfd2450` memberi urutan nama Minggu–Sabtu. `0xfce170` menjalankan selector terpisah untuk setiap hari; `0xfce710` memilih satu batch berukuran `jumlah-per-hari × 7`, lalu membagikannya berurutan ke tujuh bucket. Keduanya menulis melalui `0xfce570` ke slot kosong pertama dari 64 entri (stride 8 byte, ID kosong `-2`) dan membentuk label `Shop.Zakka.<hari>.<item>`. Loop selector mencakup ID `0–14999`; mask kandidat berukuran `0x754` byte (469 kata 32-bit, 24 bit valid pada kata terakhir). Ini menetapkan domain seleksi, bukan berarti setiap ID mempunyai baris `ItemParam`. Dengan semua kandidat lolos, state <2 menempati slot 0–1 untuk filter umum dan 2–4 untuk tiga pass `ShopSeed`; state 2 menempati 0–1 dan 2–3 untuk helper awal, 4–9 untuk tiga pass seed, lalu 10–13, 14–17, 18, dan 19 untuk filter berikutnya. Kekurangan kandidat dapat menggeser slot berikutnya; state 3 juga memanggil tiga pass seed dengan jumlah semua kandidat, jadi batas akhir setelah slot 5 bergantung pada isi pool. [Peta call order, domain, dan offset](../output/gameplay/nook_shop_weekly_slot_map.json). ID item per slot tetap ditentukan seleksi acak dan filter gabungan.

**Predicate runtime yang masih tanpa label.** `0xfcf580` memindai ID `0–14999`; untuk bit yang aktif, ia membentuk/membaca record kandidat, memanggil `0xf58d00`, lalu memanggil filter objek dan menghapus bit jika kandidat ditolak. Konstruktor `0xa0fce0` hanya mengisi vtable `0x31c6280` dan nilai selektor. Pemanggil state 2 memberi selektor `0x41` dan `0x02`; state 3 memberi `0x41` pada kedua pemanggilan. Tabel pointer lokal menghubungkan slot 0 vtable itu ke metode `0x1c86550`, tetapi field yang diuji, arti nilai selektor, serta ketergantungan metode pada state runtime belum diberi nama. Karena itu keanggotaan bitset gabungan state 2/3 belum dapat dihitung hanya dari mask musim, `ItemKind`, dan `ItemFrom`.

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

Alur lokal dari input angka `cKabu` ke query Daisy Mae dan bidang UI yang dipakai sudah didukung oleh EventFlow, layout, dan emulasi query. Sisa ketidakpastian sempit: pemetaan native halaman `KabuBuyPage` untuk build lokal 1.0.0; satu-satunya tabel halaman-ke-layout publik yang ditemukan berasal dari versi 3.0.3.

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
| Quest 3 rumah | `DecideSettlerNpc` (slot eksekusi `0x33c660`) → `0xf8dd70(SettlerType)`: filter `0xf8de30` memaksa nilai kepribadian per plot dari tabel rodata `0x29fa1dc` = [0, 5, 4]. Nilai itu adalah indeks enum `NpcLooks`, jadi plotnya untuk `Boy_normal` / `Girl_active` / `Girl_normal` (pemetaan terbukti native, `0xcc8ad0`). Pemilih `0xf8d860` mengeluarkan villager di bitset save `+0xbaae0`, lalu memilih spesies secara acak seragam dan sesudah itu villager di dalam spesies itu (§5.2) | [EF] aksi; filter [PSEUDO]; pemetaan kepribadian dan pemilih terbukti native |
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
| Pemilih villager acak yang sama | `0xf8d860` juga dipanggil `0xf84f10` (pengisian slot, §5.2) dan `0xf8c540` | terbukti native lewat `0xf84f10` |
| Siapa yang ingin pindah, dan kapan | §5.1 | terbukti native |

Aturan §5.1 dan §5.2 **terbukti native**: `0xf847f0`, `0xf87670`, dan `0xf84f10` dijalankan dari `main` lewat emulasi (`tools/villager_move_native.py`, 15 kasus di `gameplay_native.json`; daftar di §1). Pengecualiannya: baris berlabel [EF], dan fungsi yang di-stub dalam emulasi itu, yaitu `0xf8c540` (jalur plot), `0xf8d210` (`MoveInOrder`), `0xf8cea0` (NPC menunggu), serta penulis rumah dan memori. Fungsi-fungsi itu tetap [PSEUDO]. Ringkasan mesinnya ada di `native_flag_refs.json` → `data.villager_moves`.

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
1. Calon dengan `AbandonedHouse` ≠ 0 → slot dikosongkan, jeda = 15. Proses lalu berlanjut ke langkah 4 pada hari yang sama, sehingga jeda langsung berkurang (setelah satu hari: 14).
2. Villager pertama (urut slot) dengan `ForceMoveOut` ON → langsung pindah (`0xf8a410` jenis 2), flag dimatikan, dan slotnya dikosongkan. Villager kedua yang juga ber-`ForceMoveOut` menunggu hari berikutnya. Jeda tidak diubah, kecuali villager itu juga calon.
3. Calon yang sudah dikonfirmasi:
   - pergantian hari pertama → status slot `+0x11efa` = 2 (`0xf05d00`). Fungsi selesai di sini, jadi penghitung tidak bertambah hari itu;
   - pergantian hari berikutnya → pindah (`0xf8a410` jenis 1), slot dikosongkan, jeda = 15.
4. Selain itu jeda dikurangi dan penghitung hari ditambah sejumlah hari yang berlalu. Calon dihapus bila salah satu syarat ini terpenuhi:
   - jeda > 0;
   - villager menetap < 6 (`0xf855c0`: slot terisi, `MoveInCompletion` ON, `AbandonedHouse` < 2);
   - penghitung ≤ 4.

   Bila tidak, `r` = acak 0–99 dari RNG harian `0x35e9510` (`0xf53420`, di-seed `0xf53a70`). Bila `r < 5 × villager menetap + penghitung`, calon baru dipilih (`0xf87670`). Bila undian gagal, calon lama tetap.

   Contoh: 10 villager dan penghitung 30 → 80% per hari; 6 villager dan penghitung 5 → 35%. Penghitung dibatasi 30 (`+ hari berlalu`, lalu min 30). Batas `5n + penghitung` terbukti native untuk n = 6/8/10 dan penghitung 5/12/30; dengan n = 5 atau penghitung 4 tidak ada undian dan calon dihapus.

**Pemilihan calon** (`0xf87670`):
- **Dikecualikan:**
  - slot kosong;
  - indeks yang disimpan aksi `StructureMoveSaveIndex` (member `+0x4750`; dipakai `SNPC_rco_10_Common_MoveHouse` dan `_MoveNpcFacility`, kemungkinan rumah yang sedang dipindah);
  - villager terakhir yang pindah masuk;
  - villager terakhir yang dibujuk tinggal;
  - villager yang ulang tahunnya dekat (`BirthMonth`/`BirthMDay` di `NmlNpcParam`). Rumusnya: d = selisih (pukul 05:00 di hari ulang tahun tahun ini − sekarang) dalam hari, dipotong ke arah nol (`0x1fc070`); bila d < 0, dipakai ulang tahun tahun depan; villager dikecualikan bila d < 8. Secara efektif yang dikecualikan adalah ulang tahun dari hari game ini sampai 8 hari game ke depan, atau 9 hari game total. Contoh: pukul 09:00 pada 10 April, ulang tahun 10–18 April dikecualikan dan 19 April tidak; pukul 04:00 (hari game masih 9 April), 9–17 April dikecualikan. Pergantian tahun ikut teruji.
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

`0xf84f10` jalan setiap pergantian hari sesudah §5.1. Sasarannya slot kosong pertama (ID spesies `0x23`, ditulis `0xf01640`) yang tidak dikosongkan hari itu. Bila satu-satunya slot kosong baru dikosongkan hari ini, tidak ada pindah masuk; jalur plot pun tidak dicoba.

1. **Jalur plot/kontrak** `0xf8c540` (string `FromSettlerQuest`, `InducementFlag`, `ImmQ_%s_*`). Bila berhasil, selesai.
2. **`0xf8d210`** (`MoveInOrder`). Bila ada villager hasil `ForceMoveOut`, `0xf8cea0` juga dipanggil untuk slotnya; perannya di sini belum dibaca rinci.
3. **Plot rumah kosong** wajib ada: `0xef44c0` untuk 10 plot; `0xf8d640` menghitung P = jumlah plot tersedia dan memilih plot ke-r (r acak 0…P−1, RNG harian).
   - Bila ada NPC menunggu (status 3) di salah satu dari 4 struktur NPC tambahan (`+0xcca68 + k×0x12ab0`; kemungkinan villager yang sudah diundang), `0xf8cea0` memindahkannya ke plot itu. Selesai.
   - Selain itu ada undian harian `r` = acak 0–99; pindah masuk terjadi bila `r` < batas. Misalkan n = jumlah slot dengan ID NPC valid dan P = jumlah plot tersedia:

     | n | Peluang pindah masuk |
     |---|---|
     | < 5 | 100% |
     | 5–7 | (10 − n + `NNpcContractProbablityAddPoint` + P) × 10% |
     | ≥ 8 | (10 − n + P) × 10% |
   - **Pemilihan villager baru:**
     - Kepribadian yang dipilih adalah yang paling sedikit di pulau; bila seri, semuanya. Nilainya 0–7, dari byte ke-3 ID NPC (`0xcd3cb0`). Byte itu diisi dari tabel runtime `0xcc8ad0` = indeks enum `NpcLooks`: 0 `Boy_normal`, 1 `Boy_active`, 2 `Boy_pride`, 3 `Boy_snobby`, 4 `Girl_normal`, 5 `Girl_active`, 6 `Girl_pride`, 7 `Girl_big_sis`.
     - Pool kandidat (`0xcd2f40`) adalah baris `NmlNpcParam` dengan `InitLive` ≠ 0, yaitu 391 dari 397. Pool ini disaring `0xf8d7d0` dengan mask kepribadian `0x35ee084`.
     - `0xf8d860` membuang kandidat yang ada di bitset eksklusi `+0xbaae0`; bila sisanya kosong, eksklusi diabaikan. Pemilihannya **dua tahap**: satu spesies diambil acak seragam di antara spesies yang masih punya kandidat, lalu satu villager diambil acak seragam di dalam spesies itu. Akibatnya peluang per villager = 1 / (jumlah spesies × kandidat di spesiesnya), jadi villager dari spesies dengan sedikit kandidat lebih mungkin terpilih. Villager terpilih ditandai di bitset eksklusi.
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

  `0xf889e0` juga dipanggil oleh `0xbc0190` dan `0xbc0430`. Call graph tidak menemukan caller langsung untuk dua fungsi tersebut; pemindaian relokasi/vtable main dan registrasi EventFlow juga tidak memberi nama dispatch. Keduanya memang mencapai penulis yang sama melalui save node `+0x1d6d48`: `0xbc0190` hanya melakukannya bila argumen bit 0 dan root save tersedia, sedangkan `0xbc0430` melakukannya setelah rangkaian setup dunia yang mencakup `0xd21110`. Ini membuktikan dua jalur tambahan ke penulis, tetapi pemicu/callback serta apakah jalur itu lokal atau bagian dari lifecycle jaringan masih belum diketahui. Jalur jaringan yang jelas terpisah adalah dispatcher `0xc7ea00` (← `0xbcef20` ← … ← `0xb65410` `NetConfig`). Fungsi `0xf855c0` hanya menghitung villager yang menetap dengan membaca `AbandonedHouse` dan `MoveInCompletion`; ia bukan penulis flag.

## 6. Pengunjung khusus

| NPC | Yang sudah diketahui | Bukti |
|---|---|---|
| Harvey (`spn`) | `SpnVisitMainField`=1 bila sebuah nilai 0–8 ≥2 (kemungkinan level rumah pemain), quest A/B/C selesai, dan Photopia belum terbuka maupun dikunjungi | [PSEUDO] `0xfd9d10` |
| Label (`hgc`) | Kode 2, kolam acak setelah penjahit berdiri (§3.3); `HgcVisitFlagForTailor`; quest dan keakraban di `KotonoQuest*` | [PSEUDO] / [EF] |
| Saharah (`cml`) | Kode 3, satu hari kerja setiap minggu; sah bila ada pemain dengan nilai ≥2 (§3.4) | jadwal dan validasi terbukti native (§3.3–3.4); spawn [PSEUDO] |
| Kicks (`skk`) | Kode 8, satu hari kerja setiap minggu setelah penjahit berdiri | jadwal dan validasi terbukti native (§3.3–3.4); spawn [PSEUDO] |
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

## 8. Kemunculan ikan dan serangga

Tabel kandidat per jenis air, belahan bumi, bulan, dan slot (hanya ItemID dan bobot) dibangun ulang dengan `python3 tools/creature_spawn_native.py table` ke [`output/gameplay/creature_spawn.json`](../output/gameplay/creature_spawn.json). Bacaan mesin ada di `native_flag_refs.json` → `data.creature_spawn`.

### 8.1 Ikan

**Tabel [TBL].** `FishAppearRiverParam` (100 baris) dan `FishAppearSeaParam` (76 baris) memuat satu baris per ikan per belahan bumi. Nilai `AppearArea` 0 = utara, 1 = selatan; baris selatan bergeser enam bulan. Untuk setiap bulan × slot × belahan bumi, jumlah kolom `Prob*` tepat 100. `FishStatusParam` memberi `AppearType` (enum rodata `River, RiverCliffTop, Pond, BrackishWater, Sea, Anywhere, SeaBeachBridge`), `ShadowType`, `IsCreateBait`, dan `OpenDonatedNum`. Ukuran bayangan adalah `ShadowType` ikan terpilih; nilainya tetap, tidak diundi.

**Belahan bumi dan slot (terbukti native).** Mode belahan bumi dibaca dari root save `+0x651fc` (nilai > 1 dianggap 0) dan memilih tabel 0 atau 1. `0x5e3570`: indeks bulan = bulan − 1; jam 4–8 dan 16–20 → `MorningAndEvening`, 9–15 → `Daytime`, 21–3 → `Night`. `0x5e36b0` membentuk mask slot yang sama untuk rentang jam.

**Undian per posisi (terbukti native).** Vtable lapangan `0x3068a68` slot 43 = `0x59ca80` [PSEUDO] mengklasifikasikan air di posisi:

| Kode terrain `0x157270` | Tabel | Mask `AppearType` |
|---|---|---|
| 12 | sungai | `River` + `BrackishWater` (muara) |
| 5 | laut | `Sea`, ditambah `SeaBeachBridge` bila `0x59cda0(pos, 9)` (dermaga) |
| 1 | sungai | `Pond` bila lookup badan air `0x71cfa0`/`0x71dcd0` tetap vektor default; selain itu `River`, ditambah `RiverCliffTop` bila `0x59cc70(pos, 1)` |

Lalu `0x5b9a00` → `0x5b9ba0` (sungai) atau `0x5ba610` → `0x5ba7b0` (laut) memilih:

1. Kandidat = baris dengan `IsCreateBait` ≠ 0 (Can, Boot, Tire, dan Stone tidak pernah menjadi bayangan), `ItemKind` = `Fish`, bit `AppearType` di mask, lolos gerbang `0x5b9270`, dan `OpenDonatedNum` ≤ jumlah tangkapan.
2. `W` = jumlah `Prob` kandidat (float32); `r = W × (float(0x3f800000 | u >> 9) − 1)`.
3. Kandidat pertama yang jumlah berjalannya > `r` terpilih.
4. Tanpa kandidat [PSEUDO]: sungai → `Funa` (0x148), atau `Medaka` (0x8ae) bila mask memuat `Pond`; laut → `Aji` (0x8d8).

**Undian per jenis.** Vtable yang sama slot 35 = `0x59bc10(field, out, kind)`: kind 0 → `0x5b9380` (sungai), 1 → `0x5b9f80` (laut). Bit 0 byte lapangan `+0x13e1` memilih varian. Bit itu juga memindahkan undian per posisi ke bulan/slot yang tersimpan di objek `0x33d3f78` `+0x210/+0x214` dan ke gerbang `0xb54980`/`0xb548c0`. Objek `0x33d3f78` adalah ketersediaan ikan pulau misteri (tur Nook Miles) yang dibangun `0xb53d20`, pasangan ikan dari `0xb56850` (§8.2). Jadi bit 0 = mode pulau misteri [PSEUDO].
- Bit 0 mati, `0x5b98b0` (terbukti native): `r = u × 100 >> 32`; baris pertama (termasuk sampah) dengan jumlah berjalan > `r`; baris itu harus lolos `0x5b9270` dan `0x5b8e30`, jika tidak hasilnya kosong (`0xfffe`) tanpa undian ulang.
- Bit 0 hidup, `0x5b95b0` [PSEUDO]: baris yang lolos `0x5b9270` dan `0xb548c0` disaring dulu; `r = u × W >> 32`.

**Gerbang.** `0x5b9270` (terbukti native): Sirakansu (0x8ec) hanya bila kode cuaca jam ini 4 atau 5 (hujan, hujan lebat). `0x204480` mengubah 4/5 menjadi 6/7 saat `0x202490` melaporkan salju [PSEUDO], dan kode 6/7 menolak Sirakansu. Mode sesi `0xbc82d0` ≥ 2 membuang Can (0xd8a), Boot (0xd8d), Tire (0xd8e), dan semua `ItemKind` `Ore`. `0x5b8e30` (native dengan accessor field/save terkontrol; lihat `tools/open_donated_native.py`): `OpenDonatedNum` ≤ penghitung `CatchFish` pemain untuk mode 0/1; mode 2/3 memakai `FishNetHostCatchNumResult`. **828** batas nilai untuk seluruh 84 baris `FishStatusParam` lulus tanpa mismatch. Nilai ambang di tabel: 0 (45 ikan), 20 (22), 50 (12), dan 100 (5). Pengambilan tabel BCSV dan nilai save live tetap dikontrol dalam harness.

**Daftar ensiklopedia.** `0x5bb150` → `0x5bbd80` menghitung ketersediaan per item untuk rentang waktu. `AppearType` 0–3 membaca tabel sungai, 4 dan 6 tabel laut, dan 5 (`Anywhere`) keduanya. Hasilnya mask tiga slot.

### 8.2 Serangga

**Tabel [TBL].** `InsectAppearParam` (166 baris): satu baris per serangga per belahan bumi, 72 kolom `Prob` (12 bulan × 6 slot). Jumlah per slot tidak 100. `InsectStatusParam` (85 baris) memberi `AppearWeather`, `Kind`, dan `AppearFg` (3 byte mentah).

**Slot (terbukti native).** `0x9f1870` (jam sekarang) dan `0x9f1920` (waktu diberikan): jam 23–3 → `Midnight`, 4–7 → `Morning`, 8–15 → `Daytime`, 16 → `Evening1`, 17–18 → `Evening2`, 19–22 → `Night`. Getter `Prob` adalah entri bulan × 6 + slot dari array yang diisi konstruktor `0x95ebe0` di `+0x170`; urutannya terbukti native.

**Undian pulau (terbukti native).** `0x957940(manajer *0x33d3eb8)` tidak punya pemanggil langsung (dipanggil lewat pointer fungsi):
1. Bulan/slot dari jam (`0x9f1870`); belahan bumi dari root save `+0x651fc` (nilai > 1 dibaca 0), lalu tabel lewat `0x957bf0`.
2. Kandidat = baris (urutan tabel) dengan `Prob(bulan × 6 + slot)` ≠ 0 yang tidak ditolak `0x958570`.
3. `W = Σ Prob` (u16), `r = rand32 × W >> 32` (RNG TLS `0x19aa0e0`). Dipilih kandidat pertama dengan `r < Prob` setelah dikurangi bobot sebelumnya. Bila W = 0 → `0xfffe`.

**Saringan `0x958570` (terbukti native).** Serangga ditolak dari undian umum bila `AppearFg` punya bit apa pun selain bit 3, atau ID-nya salah satu dari 0x24b Amenbo, 0x250 Ga, 0x252 Gengorou, 0x25c Funkorogashi, 0x268 Konohamushi, 0x28b Yadokari, 0x1425 Tagame. Serangga yang ditolak muncul lewat jalur titik spawn masing-masing. Hasilnya, undian umum berisi serangga terbang/tanah tanpa titik khusus, termasuk empat kupu-kupu umum yang hanya punya bit 3.

**`AppearFg` [TBL] + [PSEUDO].** 18 bit dipakai (bit 3 dilewati). `0x9e8fb0` memetakan bit i lewat tabel manajer `+0x350` (jumlah `+0x348`, default 0x11) ke enum target spawn dan mengembalikan mask enum. Nama enumnya belum dibaca; kelompok menurut anggota tabel:

| Bit | Anggota | Kelompok (disimpulkan) |
|---|---|---|
| 0–4 | kupu-kupu besar, belalang sembah, lebah madu, kepinding, kepik (bit 3: empat kupu-kupu umum) | bunga |
| 5 | Katatsumuri, Dangomushi, Mukade | batu |
| 6–8 | Hae, Ari | benda busuk/sampah |
| 10–12 | tonggeret, kumbang, kumbang tanduk | batang pohon |
| 14–16 | Tamamushi, Baiorinmushi, dua kumbang sungut panjang | tunggul |

**Batas per spesies `0x8ddbd0` [PSEUDO].** Menghitung serangga aktif di daftar lapangan (`+0x290`[`+0x2a0`], entri `+0x18`, jumlah `+0x10`) yang cocok dengan predikat spesies. Spawn diizinkan selama jumlah < batas:

| Batas | Spesies |
|---|---|
| 3 | 0x24b Amenbo, 0x250 Ga, 0x28b Yadokari |
| 2 | 0x24e Dangomushi + 0x274 Mukade (bersama), 0x24f Funamushi, 0x252 Gengorou + 0x1425 Tagame (bersama), 0x268 Konohamushi, 0x27a Okera |
| 1 | 0x255 Hae, 0x25e Ka |
| selalu ditolak | 0x26b Kumo, 0x26e Minomushi (jalur pohon `0x8e0400`) |

Spesies lain: bila `0xb5ac30` (`0xfe8ab0` dengan argumen 0x11) salah, tanpa batas. Pengecualiannya serangga yang mask enum `AppearFg`-nya 0x40 (enum 6): batas 1 per grup itu, dan hanya bila `0x15c67d0(skor, 6, 1)` ≥ 5 (mode sesi < 2) dan `0x4c1310()` ≥ 7. Bila `0xb5ac30` benar: 0x16e3 Sakurapetal dan 0x1cce AutumnLeaf ditolak, lainnya tanpa batas. Arti `0xb5ac30` dan kedua ambang belum dibaca.

**Pulau misteri (tur Nook Miles) [PSEUDO].** Bacaan lama "kandidat disebar ke grup spawn" keliru. `0xb5ac90` memanggil `0xb56850(*0x33d3f70)` lalu `0xb53d20(*0x33d3f78)`:
- `0xb56850`: manajer memuat `MysteryTourInsectParam` (11 baris; `TargetInsect` = mask 85 bit atas indeks baris `InsectStatusParam`). Kandidat = baris `InsectStatusParam` (kecuali 0x279 Nomi) yang bit `AppearWeather`-nya ada di mask cuaca dan `Prob` bulan/slot tur ≠ 0. UniqueID tema diset bila minimal satu anggota menjadi kandidat (UniqueID 9: dua). `0xb56f00` = baris BCSV per indeks, `0xb58c10` = offset kolom `TargetInsect` (hash 0xd086a528).
- Mask cuaca: bit `AlwaysAppear` selalu; `AppearInSnowGroundTerm` pada periode salju (`0x203c90`); kode cuaca 4/5 (`0x204690`) → `AppearInRain`, selain itu `NotAppearInRain` dan, di luar periode salju, `NotAppearInRainAndSnow`; `AppearInCherryBlossomOpenUpTerm` bila `0x203710`; `AppearInAutumnLeavesTerm` bila `0x2039d0`.
- `0x957d70`: undian berbobot yang sama dengan `0x957940` atas kandidat tur, bulan/slot dari `*0x33d3f70 +0x218/+0x21c`.
- `0xb53d20`: pasangan ikan (getter `Prob` ikan `0x5b34f0`, Sirakansu hanya cuaca 4/5). Objek inilah yang dibaca undian ikan saat bit `+0x13e1` aktif (§8.1).

**Kasus khusus [PSEUDO].** Kutu pada villager (`0x959f70`, dari `0xd21890`): `u × 1000 >> 32 < Prob(Nomi) × arg`. Laba-laba Kumo (0x26b) dan Minomushi (0x26e) dari pohon (`0x8e0400`) hanya disiapkan bila `Prob` slot ini ≠ 0. Ketersediaan per rentang waktu (gaya ensiklopedia): `0x9591d0`, `0x959410`.

**Masih terbuka.**
- `0x957940` tidak membaca `AppearWeather`; tempat aturan cuaca diterapkan di pulau utama belum ditemukan.
- Jalur titik spawn per kelompok `AppearFg` (bunga, batu, pohon, tunggul) dan pemanggilnya; nama enum tabel `+0x350`.
- Arti `0xb5ac30`, ambang `0x15c67d0`/`0x4c1310` di batas spesies; batas `0x8ddbd0` belum dijalankan native.

## 9. Celah berikutnya (prioritas)

| # | Celah | Titik masuk |
|---|---|---|
| 1 | ~~Undian serangga~~ undian umum selesai (§8.2); sisa: aturan cuaca pulau utama, jalur titik spawn per kelompok `AppearFg` | `0x957940`, `0x9e8fb0`, `0x8ddbd0` |
| 2 | ~~Regenerasi objek lapangan harian~~ selesai, lihat §10; sisa di `re_queue.json` → `field-daily-regrowth.left_open` | `0x4ae640`, `0x4b6e70`, `0x7a3ef0` |
| 3 | Nook Miles+, pencapaian, skor turnamen | `0xf66020` → `0xf60690`, `0x309ff0`, `0x586bd0`, `0xfa60c0` |
| 4 | Penambah poin keakraban | penulis field yang dibaca `0xd34a20` |
| 5 | Skor pulau end-to-end native | `0x15c68c0`, `0x15c61f0` |
| 6 | Prosesor toko native | `0xfc4560` |
| 7 | Nama simbolik yang belum terbukti (bit flag, vtable save, enum OfficeLevel, binding `KabuBuyPage`, sel pantai) | `left_open` di item selesai `re_queue.json` |

Titik masuk baris 2–3 diambil dari `index.sqlite` (`hash_refs`, `string_refs`, `direct_calls`), jadi masih berupa kandidat; perannya belum dibaca. Cuaca dan genetika bunga sudah ada di baseline (`output/weather`, `output/flowers`) dan tidak perlu diulang. `plants_and_breeding` juga tercatat sebagai target riset agen mechanics, jadi hasil baris 2 hanya ditulis ke `output/gameplay` dan dokumen `GAMEPLAY_*`.

Antrian yang sama, dalam bentuk yang bisa dibaca mesin dan ditandai statusnya, ada di [re_queue.json](re_queue.json).

## 10. Pulau: objek lapangan harian dan isi awal pulau baru

Data mesin: `output/gameplay/native_flag_refs.json` → `data.field_regrowth`. Kasus native: `tools/field_regrowth_native.py`. Genetika bunga tidak diulang di sini (baseline `output/flowers`).

### 10.1 Alur dan objek kerja

**[PSEUDO]** Driver `0xf53a70` membuat objek kerja lapangan berukuran 0x2e150 byte (`0x7a3410`). Lalu `0x7a9760` → `0x7a5c60` mengisinya dari save, `0x4ae640(hari, kerja)` menjalankan semua prosesor, dan `0x7b1dd0` menulis hasilnya kembali. Argumen pertama berisi:

- jumlah hari sejak pertumbuhan terakhir (s64);
- waktu sekarang dan waktu terakhir;
- byte "pertumbuhan pertama", yang menyala bila save belum punya tanggal.

Hari = 0 hanya menjalankan bagian per pemain. Hari < 0 (jam dimundurkan) punya jalur sendiri.

Objek kerja diawali 5 bitset ubin item (0x4008 byte: header 8 byte dan 131.072 bit, bit = `z × 512 + x`) di `+N × 0x4008`, lalu 26 bitset unit sel. Bitset unit ke-N ada di `+0x14028 + N × 0x1008`, terdiri dari header 8 byte dan 32.768 bit; indeks ≥ 26 jatuh ke set 0. Indeks bit = `(z >> 1) × 256 + (x >> 1)`, dengan x dan z dalam ubin item (`0x7b0020` membalikkannya). Satu unit = 2 × 2 ubin item. Catatan koreksi: bacaan sebelumnya menyebut 32 bitset; batas indeks di instruksi adalah 26 (`cmp w8, #0x1a` di `0x7ab350`). Sensus `0x7a3ef0` mengisi set per jenis `FgMainParam.Kind` (tabel lompat `0x29f7a3c`), misalnya 5 = pohon, 6 = pohon dewasa yang bisa membawa barang, 8 = pohon buah, 9 = pohon tumbuh, 10 = kelapa, 11 = bambu, 17 = gulma, 18 = batu, 19 = tunggul. Sensus `0x7a46f0` (barang di tanah) dan `0x7a97e0` (pantai) mengisi penghitung berikut:

| Penghitung | Isi |
|---|---|
| `+0x2e144` bit 2–4 | fosil terkubur (berhenti di 6) |
| `+0x2e144` bit 5–7 | batu |
| `+0x2e144` bit 8–18 | gulma |
| `+0x2e144` bit 19–23 | ranting di tanah (berhenti di 15) |
| `+0x2e144` bit 24–28 | kerang di pantai |
| `+0x2e144` bit 29–31 | pohon dengan sarang tawon |
| `+0x2e148` bit 0–3 / 4–5 | pohon berisi 100 Bell / berisi furnitur |
| `+0x2e148` bit 6 / 8 | `DIYStone` lepas ada / botol pesan di pantai |
| `+0x2e148` bit 14–17 | pecahan bintang di pantai |

Saat sensus, cedar hias `0xec9a`/`0xec97` dikembalikan ke cedar biasa `0xea69` ketika musimnya lewat. Tunggul pohon buah `0xecbc`–`0xecbf` diganti tunggul ek dengan tingkat yang sama.

### 10.2 Aturan harian (hari ≥ 1)

| Objek | Aturan | Bukti |
|---|---|---|
| Batu | Status semua batu di-reset. Batu baru = `min(hari, 6 − batu)`, tiap batu memakai jenis dari `0x4d7110`: StoneA–E seragam dari RNG lapangan `0x344d100` | jenis: terbukti native; jumlah: konstanta instruksi `0x4b0108`/`0x4b0118` [PSEUDO] |
| Batu uang | Tiap pemain dengan `OccurrenceCoinStone` = 0: satu batu acak (set 18 ∩ 20) diberi flag uang; tanpa batu, batu baru berflag ditanam. Setelah itu `OccurrenceCoinStone` = 1 | [PSEUDO] |
| `DIYStone` lepas | Bila belum ada, satu `0x9c6` di sel acak set 1 yang tidak bersebelahan dengan batu (`0x7aa9a0`) | [PSEUDO] |
| Fosil | `min(6 − fosil terkubur, 4 bila hari = 1, selain itu 6)`. Tiap fosil adalah item `ItemKind` Fossil acak (RNG harian, `0x4b5900`), dikubur sebagai `0xa13`; berhenti bila penempatan gagal | [PSEUDO], konstanta `0x4b019c` |
| Pecahan bintang | Hari = 1: `StarPieceGrowCount = PrayStarToday + VisitorPrayStarToday / 5`, lalu `PrayStarToday` = 0; selain itu keduanya 0. Pecahan diletakkan sampai `10 − pecahan di pantai` | [PSEUDO] |
| Kerang | `0x4addc0`: bukan pertumbuhan pertama, flag `+0x1a`, dan sekarang ≥ waktu tersimpan + 30 menit (`0x4ade80`). Kerang ditambah sampai batas harian di sel pantai kosong (set 4) | [PSEUDO] |
| Jenis kerang | `0x7abd00`, `r` = RNG harian 0–99, musim = kolom 5 (`Shop`) `SeasonCalendar`. Musim biasa: Hora 6%, Syako 11%, Sango 11%, Hone 11%, Ebisu 11%, Takara 20%, Sanddollar 30%. Musim 1 (panas): ShellDriftSummer 10%, Hora 6%, Syako 10%, Sango 10%, Hone 10%, Ebisu 10%, Takara 17%, Sanddollar 27% | terbukti native |
| Batas kerang | `0x7a7010`: harian/total 3/9. Menjadi 8/9 bila ada sel pantai pada z 80–180 di satu sisi (x < 100 atau x > 99), dan 10/16 bila kedua sisi punya | terbukti native |
| Botol pesan | Bila `MessageBottleAvailable` dan belum ada botol, pemain pertama tanpa `IsGetMessageBottle` mendapat satu `0x16a1` (aturan resep pertama di §2.1) | [PSEUDO] |
| Titik per pemain | 8 pemain dengan `PcMaingameStart`: status `0xf51390` 0–5 dan sel bebas (set 2 ∩ 20, tidak di samping pohon/bambu/batu/tunggul). Arti status belum dibaca | [PSEUDO] |

### 10.3 Tanaman (`0x4b6e70`)

- **Pohon.** **[PSEUDO]** Semua pohon, kelapa, dan bambu diproses lewat `0x4b99a0`. Pohon dengan `Grow` < 4 tidak tumbuh bila ada ≥ 12 pohon lain di persegi 9×9 unit sekitarnya, atau bila `0x7ab350` menolak tempatnya. Selain itu `0x4d5ca0` mengikuti rantai `FgMainParam.GrowupFg` satu langkah per hari sampai `0xfffe` [TBL rantai]. Bambu yang hari ini mencapai `Grow` 4 menjatuhkan `NutItem`-nya ke sel bebas di sampingnya.
- **Buah.** **[PSEUDO]** Pohon buah menyimpan penghitung tumbuh ulang 2 bit (bit 19–20 word item) yang dikurangi jumlah hari. Bit siram 17–18 dibersihkan.
- **Ranting.** **[PSEUDO]** Bila ranting di tanah < 15, `DIYBranch` `0x9c4` diletakkan di area 6×6 sekitar pohon acak sampai 15.
- **Isi pohon** (`0x4d6e10`). **[PSEUDO]** 0 = 100 Bell `0x839`, 1 = 1000 Bell `0x842`, 2 = sarang tawon `0xcbf`, 3 = furnitur acak. Isi baru tiap hari diberikan ke pohon acak di set 6 ∩ 20:
  - sarang tawon sampai 5;
  - furnitur sampai 2 setelah `VillageExtensionLevel2` = 1 (sebelumnya 1);
  - 100 Bell sampai 15 pohon, cedar hias dilewati.
- **Gulma.** Hari yang disimulasikan = `min(hari, 20)` **[PSEUDO]**. Bila hari > 20, tanggal terakhir lebih dulu dimajukan `hari − 20`; pergantian musim di celah itu mengonversi sekali. Tiap hari:
  - saat kode musim `Weed` (kolom 6, `0x203640`) berganti, `0x4ba120` mengonversi gulma dan langkah tumbuh/sebar hari itu dilewati;
  - di hari lain, `0x4b6000` menumbuhkan lalu `0x4b63e0` menyebarkan gulma (batas 150);
  - selama gulma < 150, gulma acak baru ditambah: 2 bila gulma ≤ 30, selain itu 1.

  Varian gulma baru dipilih `0xf53420(3)` dari tiga ID tahap 1 per kode musim. Batas `SeasonCalendar` belahan utara: 0 = 20 Mar–9 Jun, 1 = 10 Jun–15 Sep, 2 = 16–19 Sep, 3 = 20 Sep–31 Okt, 4 = Nov–15 Des, 5 = 16 Des–24 Feb, 6 = 25 Feb–19 Mar [TBL].

  Aturan di bawah ini **terbukti native** (`tools/island_weed_native.py`), kecuali loop pemanggil dan sumber bitmap siram.

  | Unsur | Aturan |
  |---|---|
  | Tahap | Gulma = `FgMainParam.Kind` WeedSpr…WeedWin1 (`0x4d6620`); tahap = `Grow` 1–3 (`0x4d6650`). Rantai `GrowupFg`: 1A/1B/1C → 2A/2B/2C → 3 [TBL] |
  | Tabel musim | 7 ID per kode musim, urutan 1A, 1B, 1C, 2A, 2B, 2C, 3. Kode 0 (Spr) di `0x3060b80`; kode 1–6 (Smr, Aut1, Aut11, Aut21, Win1, Win11) lewat pointer `0x3060cb0` |
  | Siram | Bitset ubin 3 (`+0xc018`) = bitmap siram `SaveFg` (`0xf515c0`, 144 × 128 unit). Semua bit menyala bila flag save `+0x230` bit 0 aktif (`0x7a5c60`, juga menyalakan bit 0 `+0x2e144`). Hanya dipakai pada hari simulasi pertama |
  | Tumbuh `0x4b6000(kerja, pertama, jumlah, batas, a, b, c, d)` | Tidak berjalan bila jumlah ≥ batas. Tiap unit set 17, urutan pindai z luar lalu x (ubin genap): tahap 1 naik satu langkah bila `rand100` ≤ a (b bila hari pertama dan disiram), tahap 2 bila ≤ c (d). Tahap 3 tidak mengundi |
  | Sebar `0x4b63e0(kerja, musim, pertama, &jumlah, batas, a, b, c, d, masker)` | Memakai salinan set 17, jadi anak hari ini tidak ikut menyebar. Tahap 1 menyebar bila `rand100` ≤ a (b), tahap 2 bila ≤ 10 (c), tahap 3 bila ≤ 80 (d); angka dalam kurung untuk hari pertama di ubin siram. Kandidat = 8 unit tetangga di dalam rect lapangan, di set 2, di masker bila ada, dengan beda tinggi ≤ 5 (`0x7a2da0`). Satu kandidat diundi seragam menurut urutan bit ubin (`0x7afca0`, `0xf53450`). Anak ditulis hanya bila ubin lapisan 0 kosong. Lalu jumlah + 1, penghitung `+0x2e144` + 1 (berhenti di 150, `0x4b2400`), unit keluar dari set 0–4 dan 24 dan masuk set 17. Berhenti saat jumlah = batas |
  | Anak `0x4b6d90` | Selalu tahap 1 dari musim berjalan. Induk tahap 3 → 1A/1B/1C acak (`0xf53420(3)`). Induk huruf A → B atau C, B → A atau C, C → A atau B (`0xf53420(2)`). Induk musim lain dipetakan dulu ke slotnya (`0x4b6c10` → `0x4b2f10`) |
  | Konversi `0x4ba120(musim, kerja)` | Tiap gulma set 17 diganti ID dengan slot yang sama di tabel musim baru. ID yang tidak ada di tabel mana pun ditulis ulang apa adanya |

  Peluang per hari dari argumen pemanggil (`rand100` = `0xf53420(100)`, 0–99, syarat ≤):

  | Pemanggil | Tumbuh tahap 1 / 2 | Sebar tahap 1 / 2 / 3 | Batas |
  |---|---|---|---|
  | Harian `0x4b6e70` | 21 % / 6 % (siram hari pertama: 51 % / 11 %) | 1 % / 11 % / 81 % (siram hari pertama: 6 % / 21 % / 100 %) | 150, tanpa masker |
  | Pulau baru `0x4ae640` | 6 % / 3 % | 21 % / 11 % / 81 % | 1300, masker, ≤ 20 putaran, tanpa gulma acak baru |

  Masker pulau baru **[PSEUDO]**: semua unit, kecuali unit kiri, kanan, dan selatan dari ≤ 10 pohon buah (set 8 ∩ zona 0, diundi `0x7b0f00`) serta persegi 6 × 6 ubin dari (−2, −2) di sekitar ≤ 2 batu (set 18 ∩ zona 0).

  Catatan koreksi: bacaan sebelumnya menyebut ubin 3 menyala penuh "bila argumen 2 `0x7a5c60` menyala". Disassembly `0x7a60d0`–`0x7a6144` menunjukkan sumbernya `0xf51f40` (flag save `+0x230` bit 0). Argumen 2 hanya menjadi bit 7 `+0x2e148`.

- **Bunga.** **[PSEUDO]** Bunga dewasa yang disiram berkembang biak ke sel kosong di sampingnya. Mawar emas `0xeb7d` muncul pada `rand100` < 50 (`0x4c0e30`). Lily: `FlwLilyGrowCounter`/`FlwLilyFirstGrow`.

### 10.4 Isi awal pulau baru

**[PSEUDO]** Jalur ini berjalan pada pertumbuhan pertama selama `VillageExtensionLevel2` ≠ 1. Pulau dibagi tiga zona (`0x7b8b30`, lihat di bawah). Langkah-langkahnya:

1. Cedar zona 2 dibuang sampai 10, dan pohon di persegi plaza 12×6 dibersihkan.
2. Pohon dan kelapa yang ditolak `0x7ab350` dibuang.
3. **Buah.** `SpecialityFruit` dibaca (`0xf50ab0`), lalu `0x4ca460` mencari baris `FgMainParam` ber-Kind `TreeFruit` yang membawa buah itu. Pohon tersebut ditulis ke setiap sel set 8, yaitu penanda pohon apel `60001` dari preset.
4. **Bunga.** `0x4ca690(0x54)` mengambil tiga benih grup `ItemFrom` `ShopSeed_Cosmos`. `0x4ca690(grup SpecialityFlower)` mengambil tiga benih spesies pulau; grupnya diambil dari `0xf50f50`. Keduanya diundi tanpa pengembalian dengan `0xf53420` dan dipetakan ke tanaman `Fg`. Sel set 15 yang berisi tanaman Cosmos ke-k diganti tanaman spesies pulau ke-k, jadi pasangan warna ikut teracak.
5. Isi pohon per zona (`0x4b5540`):
   - zona 0: 2 sarang tawon, 5 × 100 Bell, 1 furnitur;
   - zona 1: 1 sarang tawon, 5 × 100 Bell, 1 furnitur;
   - zona 2: 2 sarang tawon, 5 × 100 Bell.
6. Fosil: zona 1 empat, zona 2 dua. Kerang: zona 0 tiga, zona 1 sisanya sampai batas total.
7. Jenis semua batu preset diundi ulang dengan `0x4d7110`. 20 ranting diletakkan di sekitar pohon, dan `DIYStone` di samping batu.
8. Gulma tidak menyebar ke unit kiri, kanan, dan selatan pohon buah, atau ke persegi 6 × 6 di sekitar batu. Gulma disebar sampai 1300, maksimal 20 putaran `0x4b6000`/`0x4b63e0` (aturan dan peluang di §10.3).

Catatan koreksi: bacaan sebelumnya menyebut langkah 3 memakai `0xf50f50`/`0x4ca690`. Itu salah. Kedua fungsi itu milik langkah bunga; fallback `0x4ca690` adalah `0xa42` `SeedCosmosRed`.

**Zona `0x7b8b30`.** **[PSEUDO]** Ketiga zona adalah bitset sel di objek kerja: `+0`, `+0x1008`, dan `+0x2010`. Bila `VillageExtensionLevel2` = 1, hanya semua bit zona 0 yang dinyalakan.

| Zona | Sel | Isi awal yang memakainya |
|---|---|---|
| 0 | Sel dalam mask "terhubung ke plaza" `*(0x32d1ba8)+0x1608` (`0x51cb60`). Mask kosong bila `cLand:SandBankDisable` ON | 3 kerang, 1 furnitur |
| 1 | Sel lain dengan `CliffLevel` 0 (atau 4) | 4 fosil, sisa kerang, 1 furnitur |
| 2 | Sel lain dengan `CliffLevel` 1, 2 (atau 5). `CliffLevel` 3 tidak masuk zona mana pun | 2 fosil, cedar dibatasi 10 |

- `CliffLevel` adalah byte `+0xc` elemen `LandMakingMap` (112 × 96 × 14 byte), dibaca lewat grid unit `0x54c970`. `0xf52860` membaca nilai > 5 sebagai 4. Nama field berasal dari skema save publik CylindricalEarth `save_schema_111_103`, lintas versi.
- Mask zona 0 dibangun oleh `0x51cc30` (dipanggil `0x56d640`). Fungsi ini melakukan flood fill 8 tetangga di grid dunia 288 × 256 unit item, mulai dari titik plaza event `0x469680`. Pengisian berhenti di sel dengan atribut tanah 1 (sungai), 5 (laut), atau 12 (muara) dari `ColGroundAttributeParam`. Mask atributnya `0x1022`, dicek oleh `0x18c7e0`. Jadi zona 0 adalah daratan yang bisa dicapai dari plaza tanpa menyeberang air.
- `name_ja` flag `SandBankDisable` adalah "中州判定が無効になったか？". Flag ini dinyalakan EventFlow `Player_GetDemo_MileExchange` saat lisensi sungai didapat [EF].

**Pembuatan pulau `0x5662e0`.** **[PSEUDO]** Fungsi ini dipanggil `0xfc3b00`, lalu `0x56d640(1)` berjalan. Langkahnya:

1. Isi `MainFieldParamUniqueID` (`SaveMainField` `+0xcfa2a`) dan `DistantViewUniqueID` (`+0xda2a8`).
2. Tulis `SaveMainField.OutsideField` dari `FieldOutsideTemplate` yang terpilih (`0xf8f2a0`). Isinya `FieldBlockData`, yaitu 9 × 8 ID bagian u16, dan `TemplateUniqueId`.
3. Panggil `0x565e30`. Untuk setiap blok dengan ID bagian ≠ 0 (`0x4de8c0`), `0x55caa0` membuka resource `Field/BlockItemPreset` anggota `BlockItemPreset<ID>` (`"%s%d"`). `0x55cc60` lalu meletakkan `ItemList` di asal blok + offset.

Loader yang sama dipakai pulau Commune (`0x565c90`) dan Mystery Tour (`0x5517e0`). Berkas `BlockItemPreset` tidak ada di manifest romfs 1.0.0 yang tersedia, jadi isinya **[NATIVE]**.

**Sumber tiap jenis objek awal.**

| Objek | Sumber | Bukti |
|---|---|---|
| Ek, cedar, gulma musim semi, StoneA | ItemPreset A/B/C (96 berkas). Word item 64-bit; 16 bit bawah = `FgMainParam.UniqueID` | [TBL] |
| Bunga | ItemPreset: 53–63 Cosmos tahap 3 per preset, yaitu Red `60017`, Yellow `60043`, dan White `60020`. 32 bit atas = byte gen default 3/0x1c/0x10; di sebagian preset nilai yang sama digeser 5 bit. Spesiesnya diganti di langkah 4 | [TBL], penggantian [PSEUDO] |
| Pohon buah | Penanda `60001` di ItemPreset, diganti pohon `SpecialityFruit` di langkah 3 | [TBL] + [PSEUDO] |
| Pohon kelapa dan buah kelapa | Tidak ada di ItemPreset dan tidak ada konstanta ID kelapa (`0xea77`, `0xeabf`–`0xeac2`) di seluruh `.text`. ItemPreset hanya menutupi area dalam (x 28–196, z 28–162 unit item). Satu-satunya jalur item lain di pembuatan pulau adalah `BlockItemPreset` untuk blok luar/pantai. Kelapa adalah `NutItem` (`0x8f0`) pohon kelapa dewasa `0xea77`, bukan objek terpisah | jalur [PSEUDO], isi [NATIVE] |
| Kerang, fosil, isi pohon, ranting, `DIYStone` | Langkah 5–7 | [PSEUDO]; jenis kerang terbukti native |

**Buah dan bunga khas (`SaveFg`).** Blok save `SaveLand +0x4150b4` (0x928 byte) memuat `SpecialityFruit` (`+0x900`), `SisterFruit` (`+0x902`), `VillageFlower` (`+0x924`), dan `SpecialityFlower` (`+0x925`). Nama field berasal dari skema publik. `0xf50950` mereset nilainya ke Apple/Apple dan 4/4.

- **Buah (terbukti native).** `0xf509e0` (dari `0xfc3490`) menulis `SpecialityFruit = 0xab4470(0)`. Nilainya dipaksa Apple `0x8a5` bila byte `(*0x32d0600)+0x52a` ≠ 0; arti byte ini belum dibaca. Lalu `SisterFruit = 0xab4470(1)`.
  - `0xab4470` membentuk himpunan {Apple, Orange, Pear, Peach, Cherry} dan membuang `SpecialityFruit` bila argumennya 1.
  - Satu undian RNG thread (TLS) menjadi seed xorshift lokal. `0xa120c0` memilih kandidat ke-`floor(u × n / 2³²)` dalam urutan ID item.
- **Bunga.** `0xf51150` dipanggil `0x4adbc0` pada pertumbuhan pertama **[PSEUDO]**.
  - Bulan = bulan ulang tahun pemain dari `0xef6440` (member `+0x11478`) bila tanggalnya valid. Bila tidak, bulan = `0xf53420(12) + 1`.
  - `SpecialityFlower = 0xf50ad0(bulan, −1, −1, −1)`.
  - `VillageFlower = 0xf50ad0(bulan sekarang dari 0x1fb9c0, SpecialityFlower, −1, −1)`.
- **Pemilih `0xf50ad0` (terbukti native).** Bila root save `+0x651fc` = 1 (selatan), bulan digeser enam. Kandidat adalah indeks 0–7 yang mask bulannya memuat bit bulan − 1 dan tidak dikecualikan. `0xf53420(jumlah)` memilih satu. Tanpa kandidat, pengecualian terakhir yang bukan −1 dilepas lalu pemilihan diulang; bila semua sudah −1, hasilnya 3. Pemakaian di toko ada di §3.7.

| Indeks | Grup `ItemFrom` | Spesies | Bulan (utara) |
|---|---|---|---|
| 0 | 0x57 | Anemone | 1–5, 12 |
| 1 | 0x55 | Hyacinth | 2–4 |
| 2 | 0x58 | Tulip | 3–6 |
| 3 | 0x56 | Rose | 5–7, 10–12 |
| 4 | 0x54 | Cosmos | 7–11 |
| 5 | 0x53 | Lily | 6–9 |
| 6 | 0x52 | Chrysanthemum | 1, 8–12 |
| 7 | 0x59 | Pansy | 1–4, 11–12 |

Tabel ada di `0x35e9138` (u32 grup, u16 mask). Nama grup berasal dari daftar enum `ItemFrom` di rodata `0x29b535d`.

**Generator lain.** `0x4b3490` adalah pengisi pulau Mystery Tour, bukan pulau utama. Fungsi ini dipanggil `0x5602a0` saat atribut stage 0x11 aktif dan berujung ke `InduceInMysteriTourIslandToday`. Ia memakai ulang `0x4d7110`, `0x4b5900`, `0x4ca460`, `0x4ca690`, `0xf50f50`, dan `0xf51040`.

### 10.5 Aturan penempatan

Data mesin: `data.field_regrowth.placement` dan `data.field_regrowth.work_object` di `native_flag_refs.json`. Kasus native: `tools/island_placement_native.py`.

**Atribut tanah.** **[PSEUDO]** `0x164b20` → `0x181cd0` memberi empat atribut `ColGroundAttributeParam` untuk satu ubin item. Kolom dibaca lewat pencarian baris `0x18f070`. Hash kolom dicocokkan lewat `output/mechanics/focus7/table_field_links.json`.

| Fungsi | Arti |
|---|---|
| `0x18c4b0` | keempat atribut punya `Sand` (`0x18f460`) |
| `0x18cb10(ubin, default)` | salah satu atribut punya `WaterCheck` (`0x18ef20`); `default` bila manajer tanah atau barisnya tidak ada |
| `0x18c400` | salah satu punya `PlayerNoEntry` (`0x18f5b0`) |
| `0x18c610` / `0x18c6c0` | salah satu atribut 41–43 (matras, terpal, lantai MyDesign) / atribut 45 (batu karang tak bisa dimasuki) |
| `0x18ce50(rect)` | semua ubin "tanah polos" (`0x18c990`): lapisan tanah ada (`0x181fa0`), tidak kena `0x182c20`, flag unit `0x56dc00` mati, dan keempat atribut bukan `WaterCheck`, 7 (Null), 43, atau 46 (`0x186b40`) |

**Set sel yang dipakai predikat.** **[PSEUDO]** Sensus `0x7a5c60` → `0x7a5090`, `0x7a3300`, `0x7a3d70`:

| Set | Isi |
|---|---|
| ubin 0 | ubin lapisan 0 tanpa item (−2), ditambah item yang bisa dibuang (`0x4d7bf0`) dan dibersihkan sensus |
| ubin 1 | ubin yang kena objek struktur/terrain (`0x7a26e0` → `0x18cbc0`/`0x18cd40`) |
| ubin 2 | jejak item tanah (luas dari `0xa142b0`) dan batu yang baru diletakkan |
| 1 | daratan bebas: unit di luar bitset pantai `*0x32e2410`, keempat ubin di ubin 0, tanah polos, tidak semuanya `Sand`, tanpa `PlayerNoEntry`, tanpa atribut 41–43/45, dan tidak ada objek di jalur 2×8 di selatannya; lalu disaring mask `0x7a55b0` |
| 2 | set 1 dan `0x7a2a30` (tiap ubin lolos `0x18cf70`, flag unit `0x56d780` mati) |
| 3 | set 1 dan `0x7a28b0` (seperti `0x7a2a30`, dan tidak di persegi plaza event `0x469640`) |
| 4 | unit pantai (`0x7a97e0`) |
| 20 | unit yang bisa dicapai pemain (`0x7a3200` pada keempat ubin): tanpa `PlayerNoEntry`; sebelum `VillageExtensionLevel2` = 1 hanya mask terhubung plaza (zona 0 di §10.4); `Level2` = 1 tanpa `Level3` → `CliffLevel` 0; keduanya = 1 → `CliffLevel` ≠ 3 |
| 21 / 22 | unit `CliffLevel` 2 / 1 |
| 23 | unit yang keempat ubinnya ada di ubin 0 |
| 24 | tempat lily di atas tebing (`0x7a3ca0`: set 23, `0x7a2a30`, `CliffLevel` 1–2, `0x7a3ab0`) |
| 25 | unit berisi item `ItemKind` 0x2f (Mushroom) yang dicek terhadap `0xcd0` (`0x7a46f0`); syarat persisnya belum dibaca |

Setelah penempatan, `0x7aa200` mengeluarkan unit dari set 0–4 dan 24 dan memperbarui set 23.

**Tempat pohon `0x7ab350(kerja, pos, pantai)`.** **Terbukti native.** Fungsi ini dipanggil pertumbuhan pohon `0x4b99a0` dan langkah 2 §10.4 (pantai = 1 untuk kelapa). Hasil 1 bila:

1. Untuk 3×3 unit di sekitar `pos` (dx, dz ∈ {−2, 0, 2} ubin), ubin itu `Sand` tepat bila `pantai` = 1.
2. Tidak ada unit yang keempat ubinnya air. Unit yang sebagian air hanya boleh di empat diagonal.
3. Tidak ada unit tetangga (8) di set 5, 10, atau 11, kecuali yang juga di set 9 (pohon yang sedang tumbuh). Tidak ada tetangga di set 19 (tunggul) atau 18 (batu).
4. Tidak ada tetangga yang seluruhnya di ubin 1 (struktur) atau di luar persegi lapangan.
5. `0x7a2e10(pos, 1)` = 0.

**Lereng `0x7a2e10(pos, mode)`.** **Terbukti native.** Hasil 1 bila salah satu dari 8 unit tetangga beda tinggi (`0x18d4c0`) ≥ 5 dari pusat. Dengan mode 1, tetangga seperti itu diabaikan bila `CliffLevel`-nya sama dengan pusat, atau bila ia diagonal dan sebagian (tidak seluruhnya) air.

**Batu `0x7aa3c0`.** **[PSEUDO]** Kandidat = set 2 ∩ set 20. Kandidat dibuang bila:

- ada tetangga yang seluruhnya di ubin 1 ∪ ubin 2 (`0x7af8a0`);
- ada tetangga (8) yang bukan tanah polos;
- `0x7a2e10(pos, 0)` = 1.

Dari sisanya satu unit diundi seragam (`0x7b0f00`: `0xf53450` di RNG harian `0x35e9510`, lalu bit ke-k). Batu ditulis di lapisan 0 (`0x4ad3b0`), unit ditempati, penghitung batu naik (berhenti di 7), lalu set 18 dan ubin 2 diisi.

**Fosil `0x7ad6e0`.** **[PSEUDO]** Satu unit seragam dari set 3 ∩ set 20. `0x7a28b0` harus masih lolos dan `0xf58d00` menerima item. Lalu `0xa143f0` mengubur item dan unit ditempati. Tidak ada pengulangan; karena itu loop fosil harian berhenti di kegagalan pertama.

**Penempat umum `0x7aadc0(kerja, item, set, keluaran, set20)`.** **[PSEUDO]** Satu unit seragam dari set (∩ set 20 bila diminta). Jejak item (`0xf59e30`) harus 2 × 2 ubin. Item ditulis di lapisan 0 dan unit ditempati. Pemakainya:

| Pembungkus | Objek | Set |
|---|---|---|
| `0x7ad870` | gulma (§10.3) | 2 ∩ 20 |
| `0x7abe80` / `0x7abf30` | kerang / pecahan bintang | 4; ∩ 20 bila argumen flag-nya menyala |
| `0x7abff0` | lily (`0x4b6e70`) | 24 |
| `0x7ad860` | dari `0xfbef40` | 1 ∩ 20 |

**Tetangga bebas `0x4b5cc0(keluaran, kerja, pos, set3, set20)`.** **Terbukti native.** Kandidat = set 3 (atau set 1), ∩ set 20 bila diminta. Hanya tujuh tetangga yang diperiksa, berurutan (−2,−2), (+2,−2), (−2,0), (+2,0), (−2,+2), (0,+2), (+2,+2). Unit tepat di utara (0,−2) tidak pernah ditawarkan. Tetangga di luar persegi lapangan dilewati. `0xf53420(n)` memilih satu. Pemakainya: rebung bambu, ranting, dan isi pohon (§10.3).

**Masih terbuka.** Mask wilayah `0x7a55b0` (set 0 dan saringan set 1–3); bagian dalam `0x181fa0`, `0x182c20`, `0x56dc00`, `0x18cf70`, dan `0x7a26e0`; arti set 16 dan 25.
