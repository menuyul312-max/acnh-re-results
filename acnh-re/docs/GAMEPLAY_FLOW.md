# Alur gameplay ACNH 1.0.0 dari data

Tanggal: 4 November 2026. Sumber: 456 EventFlow (BFEVFL) yang sudah di-decode, 1.555 definisi flag dari 11 tabel `EventFlags*`, dan teks USen. Tidak ada langkah yang diambil dari ingatan tentang game. Setiap langkah menyebut flow, entry point, flag, atau label pesan yang bisa dicek ulang.

## Cara membaca dokumen ini

Setiap langkah diberi label bukti:

| Label | Arti |
|---|---|
| **[EF]** | Terlihat langsung di graf EventFlow: aksi, query, cabang, atau subflow. |
| **[NATIVE]** | Flag progres ini tidak punya penulis di 456 EventFlow, dan pada umumnya tabelnya menandai `FlagsFlowAccess=EnableReadOnly`. Pemicunya ada di kode native dan belum di-RE. |
| **[TXT]** | Angka atau keterangan yang hanya ada di teks dialog. |

Aturan cabang query flag Bool: **case 0 = ON, case 1 = OFF**. Buktinya ada dua contoh langsung (`Tutorials_Prologue_Rco` event 9 dan `SNPC_rco_01_Tent_1_Entries` event 17). Uji statistik di `output/gameplay/summary.json` juga mendukungnya: 466 dari 474 penulisan flag yang dijaga flag yang sama konsisten (98,3%).

Query lain punya konvensinya sendiri, yang disimpulkan dari struktur grafnya:
- `VillageScoreCheck*`: case 1 = skor ≥ batas. Tangga peringkat hanya masuk akal dengan arti ini.
- `NpcHouseNum`: case 0 = jumlah ≥ `Num`. Cabang case 1 memanggil `NotEnoughNNpc`.

Arti tiap query native belum dibuktikan dengan eksekusi.

Untuk verifikasi, jalankan `python tools/gameplay_flow.py tree <Flow>`. Pohon flow progres utama tersimpan di [`output/gameplay/trees/`](../output/gameplay/trees/). Penulis dan pembaca setiap flag ada di [`output/gameplay/flag_index.json`](../output/gameplay/flag_index.json).

## Peta NPC dan flow

Kode diambil dari label `SpNpcParam` dan nama flow; nama tampilan diambil dari teks dialog.

| Kode | NPC | Flow utama |
|---|---|---|
| `rco` | Tom Nook | `AI_NPC_Rco`, `SNPC_rco_*` |
| `rcm`, `rct` | Timmy, Tommy | `SNPC_rcm_*`, `SNPC_rct` |
| `owl` | Blathers | `SNPC_owl_*` |
| `sza` | Isabelle | `SNPC_sza_*` |
| `tkk` | K.K. Slider | `SNPC_tkk*`, `AI_NPC_Tkk*` |
| `hgh`, `hgs`, `hgc` | Mabel, Sable, Label | `SNPC_hgh_*`, `SNPC_hgs`, `SNPC_hgc_*` |
| `dod`, `doc` | Orville, Wilbur | `SNPC_dod_*`, `SNPC_doc_*` |
| `gul`, `gst`, `boc`, `bey`, `chy`, `cml`, `skk`, `spn`, `ows` | Gulliver, Wisp, Daisy Mae, C.J., Flick, Saharah, Kicks, Harvey, Celeste | `SNPC_<kode>*` |

Villager biasa (`NNPC_*`) dibagi menurut 8 kode kepribadian: AN, BO, FU, GE, HA, KO, OT, ZK.

## 0. Boot dan siklus sistem

1. **[EF]** `System_BootSequence`: memuat save (`SaveSimpleLoad`), cek bahasa, lalu `CreateStaticField`.
2. **[EF]** `System_Title`: `UITitleHandling`, lalu stage `cGrowUp`, `cCharacterOrder`, atau `cDateCheck`.
3. **[EF]** `System_GrowUp` punya entry `NewGame`, `Continue`, `InGame`, `AfterNet`, dan `PlayerSwitch`. Setiap entry menjalankan `DateCheck`, lalu `System_GrowUp_GameProcess:Root` dan `System_GrowUp_WeatherControl`, lalu `Save`, lalu pindah stage.
   - `NewGame` memanggil `FirstDay` dan masuk ke `cMainFieldDemoLanding`.
   - `Continue` masuk ke `cMainFieldPlayerHouse`, atau ke `cGrowUpTalk` bila ada obrolan pagi.
4. **[EF]** Proses pergantian hari ada di `System_GrowUp_GameProcess:Root`:
   - `FirstCamperCheck`;
   - `ChkwithIslandEvaluation`: rating pulau, penghitung lily, peluang jamur, peluang kontrak rumah NPC;
   - `BuildMoveEndChk`.
5. **[EF]** Pengumuman pagi `Demo_PublicAnnouncement:Root` menjalankan `Demo_PublicAnnouncement_Process`:
   - `Process_Daily`: sekali per hari per pemain, dijaga `PAnnouceProcessDoneToday`;
   - `Process_Anytime`;
   - `Process_Only_PAnnounce`.

   Banyak pemicu progres ada di proses ini. Rinciannya di bagian 7 dan 8.

## 1. Hari 1: prolog

1. **[EF]** `Tutorials_Prologue1_Areacheck`: pemain memilih belahan bumi (`EnvWeatherArea` North/South). Ada cabang per wilayah: Japan, NorthAmerica, EU, Asia, Oceania, SouthAmerica, Africa.
2. **[EF]** `Tutorials_Prologue1_Charactermaking`:
   - nama (`UISoftwareKeyboardHandling cName`);
   - ulang tahun (`UIDateHandling cOpeningBirthday`);
   - pembuatan karakter (`UICharactermakingHandling cFirstTime`);
   - pilihan peta pulau (`UIMapSelectHandling`);
   - pendaftaran pemain (`EntryPlayerVillager`).

   Lalu flag `DoneCharacterCreation` ON dan stage berganti ke `cOpeningMovie`.
3. **[EF]** `System_GrowUp:NewGame` → `cMainFieldDemoLanding`, lalu `Tutorials_Prologue2_Arrival` dan `Tutorials_Prologue3_Orientation1`. Di orientasi ini pemain menerima:
   - item `tent` (2750);
   - NookPhone (`Orientation1:Root` memanggil `SNPC_rco_00_StartMainGame:Rco_GetSmartPhone`);
   - app Map dan app ensiklopedia.

   Orientasi ditutup dengan `SNPC_rco_00_StartMainGame:Rco_OrientationEnd` (`FinishiPC1Prologue` ON).
4. **[EF]** `Tutorials_Prologue4_Orientation2_*` dan `Player_Demo_HousingFinish`: tenda pemain dipasang (`Prologue4BuiltPlayer`), begitu juga tenda villager AN dan HA.
5. **[EF]** `Tutorials_Prologue_Rco`: Tom Nook meminta 10 `tree branch` (2500) untuk api unggun (`PrologueForCampfire1`). Setelah itu ia meminta 6 buah khas pulau, dicek lewat `LandFruit`:

   | `LandFruit` | Buah | ID |
   |---|---|---|
   | 0 | cherry | 2287 |
   | 1 | orange | 2214 |
   | 2 | pear | 2285 |
   | 3 | peach | 2286 |
   | 4 | apple | 2213 |

   Hasilnya `HaveTownFruit4CampFire`, lalu `PrologueStartedCampfire`.
6. **[EF]** `Tutorials_Prologue5_Campfire`: pesta api unggun. Setelah itu tidur di tempat tidur kemah, `Ftr_Campbed` → stage `cDreamTkk`, dan mimpi K.K. (`Tutorials_Prologue_Tkk`, `PrologueFinishTkkDream`).

## 2. Hari 2: game utama dimulai

1. **[EF]** `SNPC_rco_00_StartMainGame:Root` me-reset jadwal NPC (`ResetNpcSchedule`, `NpcInitializeActivity`) dan memesan demo `Player_GetDemo_Once:Get_MainGame`. Demo ini menjalankan `Demo_PublicAnnouncement_Process:Root`. Jalur `Get_MainGame_Continue` (dan `...2P`) memanggil `StartMainGameBitSet`, yang menyalakan `PcMaingameStart`.
2. **[EF]** Pengumuman pertama `Demo_PublicAnnouncement_03_Rco_Once:TownNews_OnThe2ndDay`: bandara dibuka. Bila tenda museum dipasang hari itu, ada pengumuman tambahan.
3. **[EF]** Workshop DIY (`Ftr_Working`, `SNPC_rco_01_Tent_1_Entries:RcoTentAskDIYtrial`): butuh 5 tree branch. Setelah resep `DIYtutorial1` dan `DIYtutorial2` didapat:
   - app resep terbuka (`MainmenuRecipe`);
   - balon mulai muncul (`FlightBalloonEnable`);
   - botol pesan mulai muncul (`MessageBottleAvailable`).

## 3. Tenda Tom Nook dan museum

1. **[EF]** Biaya pindah: `RcoTentAboutMyhome` mensyaratkan `HasLifeSupportPoint Point=5000`, yaitu saldo Nook Miles 5.000. Setelah itu `RcoPaid1stCharge` ON dan pencapaian `PayImmigrationCost` +1.
2. **[EF]** Donasi makhluk ke Tom Nook (`RcoTentFishInsect`): batasnya `MuseumDonationNumCheck Border=5`, lalu `RcoTentDonation` dan `SNPC_rco_51_DonationReward`. App ensiklopedia terbuka lewat `SNPC_rco_52_DonationRewardEntries` (`MainmenuEncyclopedia`).
3. **[EF]** Pemain memasang kit tenda Blathers (`Player_Demo_HousingFinish:HousingFinish_OwlTent_Built` → `DecidedMuseumTentPlace`). **[NATIVE]** Tenda baru berdiri lewat `MuseumBuilt` dan `MuseumTentBuiltToday`.
4. **[EF]** Di tenda, Blathers menghitung donasi sampai `MuseumDonationNumCheck Border=20`. Penghitung sisa `DonationAmountForMuseum` (maks 15) berkurang 1 setiap donasi. Setelah tercapai, `MuseumGrowupEnable1` ON.
5. **[NATIVE]** Pembangunan gedung museum: `MuseumConstruction1` → `Museum2Built`.
6. **[EF]** `Demo_PublicAnnouncement_Process:MuseumGrouUpChk` membuka penjualan resep shovel dan vaulting pole di toko (`MarketSellRecipeScoopStick`).

## 4. Rumah dan pinjaman

1. **[TXT]** Pinjaman berurutan dari `SP_rco_02_Loan` dan `SP_rco_00_Common`: 98.000 (rumah) → 198.000 → 348.000 → 548.000 → 758.000 → 1.248.000 (lantai 2) → 2.498.000 Bells (basement).
2. **[EF]** Query `PlayerHouseLevel` bernilai 0–8. `StructureHouseShapeParam` berisi Tent dan `Level00`–`Level04`.
3. **[EF]** Proses pinjaman ada di `SNPC_rco_10_Common_UpgradeMyhome`, `SNPC_rco_03_ChkAfterRemodel`, dan `SNPC_rco_04_ChkFinishLoan`. Saat semuanya lunas, `PcHousingLoanFinish` ON dan Tom Nook mengucapkan "debt-free and set for life".

## 5. Nook's Cranny

1. **[EF]** Tawaran Timmy (`SNPC_rcm_01_Tent_1_Entries:Request`) dipanggil dari `SNPC_rcm:Root` bila semua syarat ini terpenuhi:
   - pulau sendiri (`IsMyVillage`);
   - `ShopLevel` case 0 (toko masih tenda);
   - `RcmTalked1stAfterPrologue` ON;
   - `PlayerHouseLevel` case 2;
   - pemain adalah perwakilan pulau;
   - `RcmTookQuestReq` OFF.

   Dialognya diawali "Congratulations on your new home!", lalu `RcmTookQuestReq` ON.
2. **[EF]** `SNPC_rcm_21`–`24` memeriksa 30 `wood` (2768), 30 `softwood` (2767), 30 `hardwood` (2769), dan 30 `iron nugget` (2511). Flag `RcmShopMaterial_*` menjadi ON satu per satu, lalu `RcmShopMaterialComplete` dan pemain menerima kit toko.
3. **[EF]** Kit dipasang (`Prologue4BuiltShop`). Timmy berkata "open by tomorrow". **[NATIVE]** Toko berdiri lewat `MarketConstruction1` → `MarketBuilt` → `MarketOpen1stDay1`.
4. **[EF]** Pada pagi toko pertama kali buka, `Demo_PublicAnnouncement_21_CmnEvChk:ChkMarket` men-set result 13=1. Akibatnya `Demo_PublicAnnouncement_00_Cmn` memanggil `TownNews_Rco_HouseBuild`, yang menyalakan **`RcmImmQuestOpen`**: quest 3 rumah dibuka pada hari Nook's Cranny dibuka.
5. **[EF]** Upgrade kedua toko: `ShopLevel=2` → `Market2Built`. **[NATIVE]** Syarat `MarketRemodelingFlag2` dan `MarketConstruction2`.

## 6. Able Sisters

1. **[EF]** Mabel datang sebagai pedagang keliling (`SNPC_hgh_00_Peddler`). `CountTailorBuild` bertambah 1 pada jalur kunjungan.
2. **[EF]** `Demo_PublicAnnouncement_Process:EnableTailorBuild`: bila `CountTailorBuild` diuji terhadap batas 3, `MakeVillagePlayerFlag` ON, dan `KinuyoTalkBoforeFlag` ON, maka `EnableTailorBuild` ON.
3. **[EF]** Mabel memberi kit (`TailorGetHousingkit`), lalu kit dipasang (`TailorReserved`). **[NATIVE]** Toko berdiri lewat `TailorConstruction1` → `TailorBuilt`.

## 7. Quest 3 rumah villager baru

1. **[EF]** `AI_NPC_Rco:AI_Rco_ChkForceImmQ` memaksa obrolan intro (`RcoTentImmQuestIntro_*`), lalu `RcmImmQuestRunning` ON.
2. **[EF]** `SNPC_rco_53_MigrantsQuest`: pemain menerima resep `bridge construction kit` (7211) dan `ladder` (2615). Jembatan dipasang (`ImmQ_SetBridge`). Setelah itu pemain menerima `plot 1/2/3 housing kit` (5827–5829) dan memasangnya (`ImmQ_*_SetHousing`).
3. **[EF]** Untuk setiap plot:
   - 3 furnitur dalam diserahkan ke kotak (`Obj_ReservedPlaceBox`, `ImmQ_*_Interior1-3Donate`);
   - furnitur luar dicek lewat `IsSettlerQuestOutsideComplete`.
4. **[EF]** Pengumuman pagi menjalankan `ImmQFtrChkA/B/C`: bila ketiga furnitur dalam dan furnitur luar lengkap, aksi `CompleteSettlerQuestSubject` dan `DecideSettlerNpc` dijalankan. **[NATIVE]** Pemilihan villager dan flag `ImmQ_*_Complete`. Flag `ImmQ_*_Invited` tidak punya penulis di EventFlow.
5. **[EF]** `ImmQEndChk`: bila A, B, dan C selesai, `RcmImmQuestComplete` ON dan `ImmQClearNextDay` ON. Hadiahnya 50 `simple wooden fence` (11711). Keesokan harinya workshop remake tersedia (`RemakeUnlock`).

## 8. Resident Services dan Isabelle

1. **[EF]** `Enable_BuildOfficeIntroduction`: bila `RcmImmQuestComplete` ON dan `NpcHouseNum cConstructed ≥5`, maka `RcoNoticeBuildInfomationOffice` ON.
2. **[EF]** `ChkOfficeNews` men-set result 13=3, lalu pengumuman `TownNews_Rco_OfficeRenual` menyalakan `EnableBuildTownOffice`.
3. **[NATIVE]** Pembangunan: `OfficeConstruction1` → `BuiltTownOffice` dan `BuiltTownOfficeToday`.
4. **[EF]** Pada hari gedung selesai, `TownNews_Rco_OfficeOpen` memperkenalkan Isabelle; itu siaran terakhir Tom Nook. Sesudahnya `Demo_PublicAnnouncement:Root` memanggil `PAnnounceSza`, karena `BuiltTownOffice` ON dan bukan hari pertama. Musik 24 jam juga berganti (`BGMChangeCheck`).
5. **[EF]** Upacara peresmian ada di `SNPC_rco_05_ChkCeremony`, dengan stage `cMainFieldCeremonyMarket/Museum/Office/Tailor/CampSite/Bridge/Slope`.

## 9. Pengembangan pulau

1. **[EF]** `SNPC_rco_01_Office_1_Entries:OfficeOpening*` menyalakan `IslandDevQuestRunning`.
2. **[EF]** Campsite (`SNPC_rco_54_IslandDevelopment:CampSiteRequest`): resep `campsite construction kit` (5166) diberikan, lalu kit dipasang (`RcoBuildCampsiteComplete`). **[NATIVE]** Campsite berdiri lewat `CampSiteBuilt`.
3. **[EF]** Saat pergantian hari, `FirstCamperCheck` menyalakan `RcoMeetFirstVisitorRequest` dan `CampFirstCamperVisit`. Pemain menemui pengunjung pertama (`NNPC_Spot_Camp:Flow_FirstCamper*`) dan menerima `housing kit` (3349) untuk rumahnya (`RcoBuildFirstVisitorsHousingKitComplete`). Sesudah itu panggilan amiibo ke campsite terbuka (`TanuportAmiiboCampUnlock`).
4. **[EF]** Bila `NpcHouseNum cConstructed ≥6`, `Root3IslandEvaluation` → `IslandEvaluationStartForce/Running` menyalakan **`IslandEvaluationUnlock`**. Kit rumah tambahan bisa dibeli sejak `FirstCamperHouseComplete` menyalakan `RcoEnableBuyHousingKit`, sampai `NpcHouseNum cExist` 10 (`SNPC_rco_01_Office_1_Entries:ChkGetHousing` memeriksa 7, 8, 9, 10).
5. **[EF]** Jembatan dan tanjakan dipesan lewat Tom Nook (`SNPC_rco_10_Common_BuildBridgeSlope`) dan diresmikan dengan upacara. Flag `BridgeBuilt` dan `SlopeBuilt` tidak punya penulis di EventFlow **[NATIVE]**.

## 10. Rating pulau dan konser pertama K.K.

**[EF]** Rating dihitung di `System_IslandEvaluationCheck:IslandEvaluationChk`. Fungsi ini dijalankan saat pergantian hari (`ChkwithIslandEvaluation`) dan saat berbicara dengan Isabelle.

| Komponen | Ambang (query) | Peringkat |
|---|---|---|
| Nature (`VillageScoreCheckNatural`) | 200 / 270 / 350 / 450 | N = 0–4 |
| Life (`VillageScoreCheckLife`) | 80 / 160 / 400 / 650 | L = 0–4 |
| Minus (`ChkMinusPoint`) | `VillageScoreVeryMessy` (180 half-unit, 1 blok) / pohon `>220` / ikon unit `15` | 0 = tidak ada, 1 = berantakan, 2 = pohon, 3 = ikon |

Bintang = result 0 + 1. Dasarnya: result 4 menampilkan "best possible ranking" dan resep golden watering can.

- **Bila rumah NPC (cConstructed) <8:** maksimal 1 bintang. Pengecualiannya: bila ≥7 rumah dan N≥2 serta L≥2, hasilnya 2 bintang (`NotEnoughNNpc`).
- **Bila ≥8 rumah:** nilai awal ditentukan L, lalu dibatasi N.

| L | N=0 | N=1 | N=2 | N=3 | N=4 |
|---|---|---|---|---|---|
| 0 | 2★ | 2★ | 2★ | 2★ | 2★ |
| 1 | 2★ | 2★ | 2★ | 2★ | 2★ |
| 2 | 2★ | 2★ | 3★ | 3★ | 3★ |
| 3 | 2★ | 2★ | 3★ | 4★ | 4★ |
| 4 | 2★ | 2★ | 3★ | 4★ | 5★, atau 4★ bila ada poin minus |

Cara skor Nature dan Life dihitung ada di query native dan belum di-RE.

Alur menuju konser:

1. **[EF]** `SNPC_sza_50_IslandEvaluation:Sza_Evaluation_CmnImpression`: bila `IslandDevQuestComplete` OFF, result 0 bernilai 2, 3, atau 4 (≥3★), dan pemain adalah perwakilan pulau (`MakeVillagePlayerFlag` ON), Isabelle membacakan komentar dari "K.S.", lalu `ClearTkkFirstLiveScore` dijalankan. Akibatnya `IslandEvaluationClearTkkLive` ON, `IslandDevQuestRunning` OFF, dan `IslandDevQuestComplete` ON.
2. **[NATIVE]** `TkkFirstLiveEnable` (EnableReadOnly).
3. **[EF]** Pada pengumuman pagi, bila `TkkFirstLiveEnable` ON, pemain adalah perwakilan pulau, dan `EventBranch AddDay=0` bernilai case 0, `Demo_PublicAnnouncement:Root_Init` menyalakan `TkkFirstLiveReserved` dan `TkkFirstLiveSubPlayer`, lalu membatalkan pengunjung hari itu (`CancelTodayVisitorNpc`). Isabelle mengumumkan konser (`Demo_PublicAnnouncement_13_Sza_Once:TownNews_KK1stLive`). Sesudah pengumuman, `PAnnounceSza` memindahkan stage ke **`cMainFieldFirstLive`** (stage `MainFieldDemoFirstLive`).

   Catatan: `ClearTkkFirstLiveScore` sudah memeriksa `EventBranch AddDay=1` sebelum menyalakan flag. Kapan tepatnya `TkkFirstLiveEnable` menjadi ON ditentukan kode native.
4. **[EF]** Konser `SNPC_tkk_Live` menyalakan `TkkFirstLiveJoined`, menambah `TotakekeLiveCount` dan pencapaian `GotoTotakekeShow`, lalu menyalakan `StandByRcoVisitMyHomeAfterTkkFirstLive`.
5. **Staff roll:** layout `StaffCredit*` dan teks `STR_StaffList` ada di data. **[NATIVE]** Tidak ada aksi EventFlow yang memanggilnya, jadi pemicunya ada di stage atau kode native.
6. **[EF]** Sesudah konser, Tom Nook datang ke rumah (`SNPC_rco_55_TkkFirstLive:InvitePlayerHouse`). Pemain menerima lagu `Welcome Horizons` (4318) dan app **Island Designer** (`MainmenuConstructLicense`, `UIMenuDeviceAppear cConstructLicense`).

Inilah ujung alur cerita utama di data. Sesudahnya tidak ada flag progres baru yang mengunci cerita; yang tersisa adalah loop terbuka di bagian 11.

## 11. Setelah konser: loop terbuka

1. **[EF]** Lily of the valley: penghitung `FlwLilyGrowCounter` hanya bertambah bila rating 5★ **dan** `TkkFirstLive` ON (`System_GrowUp_GameProcess:ChkLilyCounter`). Di bawah 5★, penghitung di-reset ke 0.
2. **[EF]** Resep alat emas:

   | Alat | Syarat / sumber |
   |---|---|
   | golden net | `CompleteInsects` (mail museum) |
   | golden rod | `CompleteFish` |
   | golden watering can | 5★ pertama |
   | golden shovel | `JohnnyHelpCount` batas 30 (`SNPC_gul`) |
   | golden axe | `Player_ToolBreak:ToolBreak_Axe` |
   | golden slingshot | tidak ada di EventFlow **[NATIVE]** |

3. **[EF]** Museum lengkap: `SNPC_owl_01_Museum_Donation` menyalakan `MuseumFossilComplete` beserta pesan "collections are, at last, complete".
4. **[EF]** Event kalender ada di `CalendarEventParam` (17 baris): Fishing Tourney 4 musim, Bug-Off 4 kali, Countdown, Tahun Baru, Imlek, ulang tahun pemain dan NPC, serta 3 jenis konser K.K. Flow-nya: `NNPC_GEvent_*`, `SNPC_bey_event`, `SNPC_chy_event`, dan `SNPC_*_GEvent_Countdown`.
5. **[EF]** Loop harian dari `Process_Daily`: keakraban Sable (`HgsCloseness`), hitungan beli lobak (`BocBuyCount`), login Nook Stop, resep Celeste per zodiak (`OwsChkMonthlyFlag`), dan hadiah maskapai.
6. **[EF]** Mystery Tour: `SNPC_dod_01_Airport_NormalSeq` → `cMysteryTourIsland` → `SNPC_doc_50_MysteryTour` → `cFromOutlierToHomeland`.
7. **[EF]** Nook Miles: 81 pencapaian dengan ambang dan hadiah per tingkat di `EventFlagsLifeSupportAchievementParam`, ditambah 188 tugas harian di `EventFlagsLifeSupportDailyParam`.

## 12. Yang belum bisa dibuktikan dari data

- **693 flag tanpa penulis EventFlow.** Daftar lengkapnya dengan filter `writer_status` di `flag_index.json`. Flag progres penting di antaranya:
  - selesainya pembangunan: `MuseumBuilt`, `Museum2Built`, `MarketBuilt`, `TailorBuilt`, `BuiltTownOffice`, `CampSiteBuilt`;
  - `TkkFirstLive`, `TkkFirstLiveEnable`, `ImmQ_*_Complete`, `ImmQ_*_Invited`, `BridgeBuilt`, `SlopeBuilt`.
- **Query native yang angkanya dipakai tetapi caranya belum di-RE:** `VillageScoreCheckNatural/Life` (cara skor dihitung), `NpcHouseNum`, `MuseumDonationNumCheck`, `IsSettlerQuestOutsideComplete`, `EventBranch`, `FacilityOpenPastDays`, serta aksi `DecideSettlerNpc` dan `CompleteSettlerQuestSubject`.
- **Pemilih obrolan oleh AI NPC.** Flow `AI_NPC_*` memilih obrolan lewat `SetNpcSpeakFlow`, `NpcChangeConversationPretenseState`, dan state AI. Kapan state itu dievaluasi (jadwal, jarak, giliran bicara) ditentukan kode native.
- **Staff roll, perpindahan stage setelah demo, dan penyelesaian konstruksi di pagi hari** berjalan di luar EventFlow.
- **Batas walker:** subflow tidak di-inline, dan cabang `SubflowResultChoice` tidak dihitung sebagai syarat. Rantai lewat result (contohnya result 13 pada pengumuman pagi) dibaca manual dari pohon flow di atas.

Status dump dan katalog dari tiga link Google Drive: belum bisa diunduh di sesi ini (host `drive.google.com` diblokir kebijakan jaringan). Setelah tersedia, dump itu akan dipakai untuk menutup celah di bagian ini, misalnya dengan memeriksa data stage, AI, dan aset yang belum ada di paket sekarang.
