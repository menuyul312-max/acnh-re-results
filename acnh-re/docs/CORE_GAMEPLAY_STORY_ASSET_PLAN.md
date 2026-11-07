# Rencana crosswalk cerita, gameplay inti, penempatan dunia, dan aset

**Tanggal: 7 November 2026.** Dokumen ini merencanakan RE yang menghubungkan alur cerita utama ACNH 1.0.0 dengan actor, interaksi, posisi di pulau, UI, animasi, model, teks, dan audio. Targetnya adalah spesifikasi yang cukup lengkap untuk kelak menjadi dasar gameplay; dokumen ini tidak membangun game atau mengubah proyek Godot.

Manifest gabungan ada di [`output/gameplay/story_asset_crosswalk.json`](../output/gameplay/story_asset_crosswalk.json): 28 beat dari prolog sampai Island Designer sudah digabung dari empat part cerita dan satu inventaris aset. Pass struktural valid; 381 rujukan aset mengisi 308 slot minimum untuk 11 keluarga per beat. Rinciannya 235 `OPEN`, 73 `CAT`, dan 73 `EF/PSEUDO/STRUCT/TBL` (35 `EF`, 13 `PSEUDO`, 18 `STRUCT`, 7 `TBL`). Jadi setiap kategori sudah tercakup, tetapi hubungan visual/runtime belum tuntas. Model/audio hanya kandidat katalog karena arsip sumber mentahnya tidak tersedia.

Inventaris jumlah sumber, kelas aset, importer, dan batas konversi ada di [STORY_ASSET_INVENTORY_CROSSWALK_20261107.md](STORY_ASSET_INVENTORY_CROSSWALK_20261107.md).

Temuan dari proof lanjutan per loop dirangkum pada [CORE_GAMEPLAY_PROOF_INDEX_20261107.md](CORE_GAMEPLAY_PROOF_INDEX_20261107.md); tiap ledger terpisah menjaga detail source/hash dan gap native/UI/world tanpa mengubah status kandidat menjadi klaim runtime.

## Sasaran dan batas bukti

Jalur prioritas dimulai dari boot/New Game, prolog kedatangan, api unggun dan mimpi K.K., tutorial hari kedua, biaya pindah dan rumah, Nook's Cranny, quest tiga plot, Resident Services, campsite/camper pertama, rating pulau, konser K.K. pertama, lalu pembukaan Island Designer. Ini mengikuti urutan yang tercatat di [GAMEPLAY_FLOW.md](GAMEPLAY_FLOW.md) §§0–11. Fasilitas dan sistem sampingan dimasukkan hanya bila menjadi prasyarat atau memengaruhi gate cerita.

Flow yang menyebut sebuah stage, actor, item, atau aksi adalah bukti **bahwa referensi itu ada di graf**, bukan bukti bahwa model, animasi, transform dunia, renderer, atau handler native-nya sudah terhubung. Tiap hubungan di crosswalk harus diberi salah satu status: `EF` (graf), `TBL` (tabel), `NATIVE` (body native benar-benar dijalankan dengan konteks yang dicatat), `PSEUDO`, `CAT` (katalog saja), atau `OPEN`. Nama kandidat tidak boleh dianggap kecocokan aset final.

## Peta beat cerita ke bukti dan aset

Kolom penempatan menjelaskan apa yang harus dilacak, bukan koordinat yang sudah diketahui. Lokasi spesifik, anchor kamera, transform actor, dan kecocokan visual tetap `OPEN` sampai ditautkan ke data atau consumer runtime yang tepat.

| Beat utama | Flow dan keadaan yang sudah tercatat | Penempatan dan interaksi dunia yang harus dipetakan | Crosswalk aset yang harus dibuktikan |
|---|---|---|---|
| Boot, title, New Game, pembuatan karakter | `System_BootSequence`, `System_Title`, `System_GrowUp:NewGame`; pemilihan wilayah, nama, ulang tahun, karakter, peta pulau, pendaftaran pemain; stage `cOpeningMovie`. **EF**. | Hubungkan title → input character creation → hasil player record → pilihan peta/seed → stage opening. Petakan actor/cutscene yang memulai perjalanan; jangan menyimpulkan layout/shot dari nama stage. | `UICharactermakingHandling`, `UIMapSelectHandling`, `UIDateHandling`, pane/BFLAN/BNTX yang dipakai, pesan MSBT; karakter/player model dan rig; animasi/cutscene; suara UI dan musik. Page binding dan model/audio final belum terbukti. |
| Pesawat dan kedatangan | `Tutorials_Prologue2_Arrival`, `Tutorials_Prologue3_Orientation1`, `cMainFieldDemoLanding`; Tom Nook memberikan tenda, NookPhone, Map dan ensiklopedia. **EF**. | Cari spawn point pemain, pesawat/landing actor, jalur ke plaza, Tom Nook dan villager awal; kaitkan stage/camera transition ke koordinat atau landmark dari loader. Penempatan dan urutan visual aktor belum dibuktikan oleh flow saja. | Model actor/player/pesawat/plaza, rig dan ASB state; animasi kedatangan, berdiri, percakapan, ekspresi; layout phone/Map/ensiklopedia, label MSBT, UI SFX/BGM. Semua model/audio hanya **CAT** pada dump ini; exact `UIName`/clip/path-to-beat masih perlu crosswalk. |
| Orientasi, tenda awal, dan dua villager | `Tutorials_Prologue4_Orientation2_*`, `Player_Demo_HousingFinish`; flag pemasangan tenda pemain dan villager awal AN/HA. **EF**. | Petakan struktur kit ke instance rumah/tenda, kepemilikan, cell grid, rotasi, validasi jarak, dan spawn villager. Cocokkan event penyelesaian placement dengan save flag `Prologue4BuiltPlayer` dan perpindahan tutorial. | Model tenda, NPC dan furnishing; animasi penempatan kit, construction/transition dan interaksi; HUD placement preview/confirm/cancel; bunyi konfirmasi. ID struktur diketahui dari flow/parameter yang terkait, tetapi asset path dan transform final belum diikat. |
| Ranting, buah, api unggun, dan mimpi K.K. | `Tutorials_Prologue_Rco`, `Tutorials_Prologue5_Campfire`, `Tutorials_Prologue_Tkk`; 10 ranting, 6 buah khas, `Ftr_Campbed`, stage `cDreamTkk`, dan flag prolog. Buah `LandFruit`→ItemID sudah tercatat. **EF/TBL/PSEUDO** untuk sebagian query. | Sambungkan gerak/interaksi → pickup ranting/buah → inventory → penyerahan ke Tom Nook → pemunculan api unggun → kerumunan/party → penggunaan campbed → dream stage. Petakan posisi prop, area trigger, kamera, dan actor sekitar tiap aksi. | Model ranting/buah/api unggun/campbed/NPC/player; clip pickup, handover, campfire reaction, sleep/dream; label dialog MSBT; musik/suara acara dan dream. Asset katalog memberi nama saja. Konsumsi item, trigger posisi, transisi animasi, dan audio consumer per node perlu ditutup. |
| Hari kedua, DIY, alat, dan biaya pindah | `SNPC_rco_00_StartMainGame`, pengumuman bandara, workshop `Ftr_Working`, resep tutorial, app Recipe; biaya 5.000 Nook Miles. **EF**; transaksi DIY/save masih terbuka. | Hubungkan dialog workshop → meja kerja → pilihan resep → cek bahan → animasi craft → hasil ke pocket → pengumuman/reward. Ikat biaya pindah ke currency mutation, pembayaran, receipt, dan upgrade house kit. | Model/pose workbench, tool/material/hasil, UI recipe/craft/pocket, BFLAN feedback, tutorial text, craft SFX. Animasi ASB belum disambungkan ke action-state; pengurangan bahan/atomicity dan wrapper save belum terbukti. |
| Donasi dan pembangunan museum | Tom Nook meminta 5 makhluk; Blathers/tenda dan ambang donasi 20; museum naik lewat processor harian. **EF/PSEUDO**, dengan batas native pada audit museum terkait. | Hubungkan makhluk hasil catch → item → dialog/serah-terima → donor marker → tenda pada lokasi pilihan → pergantian hari → gedung museum dan announcement. Tentukan posisi NPC/entrance serta aturan placement tanpa mengarang koordinat. | Model makhluk, tenda/gedung museum, Blathers, donation UI, podium/display; dialog/animasi donasi dan construction; label MSBT dan bunyi. Row donor dan live save trace masih terbuka; raw model/audio tidak ada. |
| Rumah pertama, toko, dan quest tiga plot | Upgrade rumah membuka toko; material toko 4×30, kit, hari buka; bridge/ladder dan tiga plot berisi furnitur interior/eksterior. **EF**, sebagian processor dan native item/fasilitas masih parsial. | Kaitkan kit toko/rumah/bridge/ladder/plot ke jenis struktur, placement grid, slope/river/shore validation, furnishing requirement, villager house-slot, dan day-change completion. Tempatkan langkah ini pada world map hanya setelah world origin/transform dan loader terbukti. | Model tiap fasilitas, bridge/slope, plot kit, furnitur dan villager; preview/placement UI; build/done animation, NPC reactions, construction FX; resep/item IDs dan pesan quest. Asset source path, placement transform, transaksi furnish/serah-terima dan perubahan save end-to-end masih open. |
| Resident Services, Isabelle, campsite, camper | Renovasi kantor dan plaza; intro Isabelle; campsite kit, camper pertama dan house kit. **EF/PSEUDO**. | Hubungkan jenis struktur 1/6 dan perubahan tenda→gedung ke plaza, lokasi spawn, ceremony markers, visitor schedule, camper dialogue, dan house placement; buktikan urutan processor→announcement→stage. | Model kantor dua tahap, plaza, campsite, Isabelle/camper, ceremony props; announcement/HUD, stage animation, dialog, BGM change, visitor SFX. Spatial anchors, office mesh swap, NPC schedule-to-scene binding, dan dialog topic masih terbuka. |
| Rating pulau, konser K.K., credits, Island Designer | Rumus Nature/Life/penalti dan ambang cerita terbaca; sebagian leaf score lulus native fixture, aggregator/unlock penuh belum. EventFlow memiliki `cMainFieldFirstLive`, konser, staff-credit references, lalu app Island Designer. **EF/PSEUDO/NATIVE parsial**. | Hubungkan placed items/trees/flowers/facilities/bridges → score cache → Isabelle evaluation → day-change scheduler → K.K. stage/arrival/performance → credits → license. Setelah unlock, petakan preview/edit/validate/commit/rollback dan save untuk terrain/water. | K.K./stage/model/rig dan perform clip, music track/event timing, reaction/crowd, rating UI, license UI/BFLAN, credits layout/MSBT. Audio hanya katalog; playback, renderer, staff-roll native trigger, score aggregator→unlock dan terraforming transaction belum terbukti end-to-end. |

Able Sisters dan fasilitas lain tetap dicatat sebagai cabang cerita atau dukungan rating, tetapi tidak boleh disisipkan ke rantai wajib New Game→konser tanpa bukti bahwa gate utama mensyaratkannya. Tiap tabel akan menyimpan prasyaratnya sebagai conditional branch.

## Bentuk crosswalk yang akan dibuat

Satu record untuk setiap beat/action kritis akan menyimpan:

- `game_version`, `flow`, `node/event`, stage masuk/keluar, actor code, precondition dan flag/save delta;
- aksi pemain, item/structure ID, lokasi/zone, koordinat/rotation hanya bila sumber membuktikannya, dan consumer native yang memakai data tersebut;
- `UIName`/pane/BFLAN/BNTX, label MSBT dan bahasa, model `Asset_ID`/`ResName`, ASB state/clip, audio katalog/path, serta evidence class untuk setiap join;
- sumber file + SHA-256, offset atau table row ID, tool/versi/parameter konversi, output hash, validasi, dan gap yang tersisa.

Part manifest menggunakan [story_asset_crosswalk.schema.json](../output/gameplay/story_asset_crosswalk.schema.json). Schema mewajibkan field terpisah untuk UI, animasi, model, audio, teks, tekstur, shader/material, efek, font, data dunia dan collision. Setiap kategori harus mempunyai minimal satu referensi atau placeholder `OPEN`/`CAT`, sehingga tidak bisa terlewat saat digabung.

Jika satu hubungan belum diketahui, record tetap dibuat dengan `status=OPEN` dan alasan eksplisit. Data hasil konversi harus mempertahankan raw source, key/ID game, provenance, unit, axis, byte/bit asli dan batas fidelity. File yang hanya ada di katalog diberi `CAT`; tidak boleh diberi status converted atau runtime-verified.

Contoh record awal yang boleh dibuat dari bukti flow yang sudah ada:

```json
{
  "beat_id": "prologue.orientation1",
  "game_version": "1.0.0",
  "flow": {"name": "Tutorials_Prologue3_Orientation1", "evidence": "EF"},
  "stage": {"name": "cMainFieldDemoLanding", "evidence": "EF"},
  "actor": {"code": "rco", "role": "Tom Nook", "evidence": "EF"},
  "items": [{"id": 2750, "role": "player tent", "evidence": "EF"}],
  "unlocks": ["NookPhone", "Map app", "encyclopedia app"],
  "assets": {
    "ui_page_binding": "OPEN",
    "model_asset_path": "CAT lookup required; source model absent",
    "animation_state_or_clip": "OPEN",
    "message_labels": "resolve from EventFlow message refs",
    "audio_asset": "CAT lookup only; source audio absent",
    "world_anchor_and_transform": "OPEN"
  }
}
```

Record ini adalah bentuk pekerjaan, bukan klaim bahwa asetnya sudah ditemukan. Field `assets` baru dapat dinaikkan statusnya setelah path/ID sumber, consumer, dan batas konversinya dicatat.

## Urutan pekerjaan berikutnya

| Urutan | Pekerjaan RE | Status saat ini | Hasil berikutnya / syarat penutupan |
|---|---|---|---|
| 1 | Beat ledger New Game→Island Designer beserta actor, stage, flag, item, interaksi, dialog dan 11 kelas aset. | Selesai secara struktural: 28 beat di empat part; seluruh part lolos schema. | Buktikan tiap hubungan visual dan runtime melalui consumer/handler; jangan menganggap referensi EventFlow sebagai bukti pemutaran aset. |
| 2 | Prolog: layout UI, actor, animasi, suara, item dan prop dari keberangkatan sampai mimpi K.K. | Crosswalk tersedia; layout/BFLAN, ASB/AnimationInfo dan katalog kandidat ditambahkan. Model/audio tetap `CAT`; pemicu halaman, clip actor, dan transform masih `OPEN`. | Hubungkan flow ke page/controller, actor ke state/clip, serta stage ke prop/posisi dengan key atau caller yang bisa diulang. |
| 3 | Graph penempatan world: preset pulau → grid/cell → instance → transform → actor/camera/trigger untuk tenda, plaza, shop, plot, office, campsite, bridge dan slope. | Parsial; laporan loader, water/terraform dan terrain sudah mencatat batas bukti, tetapi rantai transform cerita belum utuh. | Tutup loader dan transform end-to-end untuk sampel; untuk posisi yang tak tersimpan pada sumber biarkan `OPEN`. |
| 4 | Dependency mekanik yang memotong cerita: gerak/interaksi, pickup/inventory, DIY/tools, NPC talk, save/day-change, placement, score/unlock, UI input/focus. | Banyak leaf/helper sudah dipetakan, tetapi belum ada trace tunggal input→state/save→transisi cerita untuk semua loop. | Hubungkan jalur kritis dengan bukti native atau EventFlow caller yang lengkap; catat kondisi test dan batas fixture. |
| 5 | Beat hari kedua→konser pertama, termasuk plot, Resident Services, camper, rating, credits dan Island Designer. | Crosswalk 21 beat tersedia; beberapa stage/koordinat, actor clip, UI trigger dan consumer tetap terbuka. | Pastikan syarat wajib dan urutannya konsisten dengan EventFlow, processor pergantian hari, flag/save, serta perpindahan stage. |
| 6 | Konversi dan provenance per kelas. | Cara konversi dan batas fidelity tercatat di inventaris; data gameplay, teks, UI dan animasi punya hasil statis. Arsip Model/ dan Sound/Resource tidak tersedia. | Validasi decoder terhadap sumber untuk kelas yang tersedia; model/audio tetap `CAT` sampai raw source, consumer, dan hasil konversi dapat diverifikasi. |

Urutan ini menghasilkan spesifikasi RE, bukan build. Sumber visual model/audio yang hilang tidak menghalangi pencatatan nama/path katalog dan relasi ceritanya, tetapi menghalangi verifikasi mesh, waveform, animasi skeletal yang memerlukan rig, serta perbandingan tampilan. Kondisi itu harus terlihat pada tiap record sampai sumber mentah tersedia.

## Kriteria cakupan inti selesai

Peta baru dapat disebut mencakup inti gameplay jika semua bab wajib pada tabel di atas memiliki crosswalk record; jalur perpindahan stage, flags, save/day-change, aksi pemain, NPC, world placement, UI, dialog, animasi, model dan audio mempunyai source/evidence status; dan loop berikut terhubung dari prasyarat ke hasil: bergerak/berinteraksi, mengambil/menyimpan item, crafting/menggunakan alat, menempatkan struktur/furnitur, menyelesaikan quest NPC, menunggu pergantian hari, membangun fasilitas, menilai pulau, membuka serta menjalankan konser pertama. Bagian yang belum dapat dieksekusi harus tetap berstatus terbuka, bukan diisi dengan asumsi.
