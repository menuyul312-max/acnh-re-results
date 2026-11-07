# Tindak lanjut transaksi crafting

**Tanggal:** 2026-11-06

**Cakupan tahap ini:** jalur akuisisi cache cold-cache sampai cek kecukupan bahan, memakai resep nyata `RecipeCraftParam.UniqueID=56` (`FtrFruitbasket`). Tahap ini tidak menyatakan DIY selesai.

## Bukti yang dieksekusi

**[TBL]** Baris 56 menghasilkan item 975 dengan satu Apple (`2213`), Pear (`2285`), Cherry (`2287`), Orange (`2214`), dan Peach (`2286`). Slot keenam kosong. Blob tabel hasil resolve dan `romfs/Bcsv/RecipeCraftParam.bcsv` sama-sama ber-hash SHA-256 `97fe6d73e183dab43dad7358627a0a1a43f5764f0a18fa044a63a9ecf56ba919`.

**[NATIVE]** Harness membaca enam pasangan bahan/jumlah melalui getter asli `0xedac50`, lalu memanggil `0xee0be0` untuk keenam slot. Cache dimulai dengan byte siap (`cache+8`) nol. Handle pemain 0 yang direkonstruksi membuat helper mengambil tiga member dari konteks player dan meneruskan masing-masing ke loader native `0xeda040`, `0xeda160`, dan `0xeda280`. Vtable tiap komponen menunjuk ke producer asli `0xee72b0`, `0xee7550`, dan `0xee7800`. Setelah producer mengisi penghitung, helper menyetel byte cache menjadi 1 dan memeriksa bahan.

Fixture menyimpan Apple dan Pear pada sumber A, Cherry dan Orange pada B, serta Peach pada C. Dengan opsi C aktif, kelima slot lolos. Dengan sumber yang sama tetapi opsi C mati, slot Peach gagal. Run ketiga menghilangkan Peach dari member C dan juga gagal pada slot itu. Ketiga cek mempertahankan penghitung cache setelah proses producer. Call graph pada `/workspace/acnh-re/output/index.sqlite` mencatat enam call dari `0xedc240` ke `0xee0be0`; pseudocode di `output/binary/analysis_decomp/edc240.c` meneruskan slot 0–5.

## Label dan batas bukti

`[NATIVE]` berlaku untuk instruksi asli ELF pada getter, helper, loader, dan producer yang disebut di atas. `[TBL]` berlaku untuk resep. A/B/C adalah tiga kelompok struktur cache; nama member save gameplay-nya belum dibuktikan.

**[PSEUDO: fixture direkonstruksi]** Tidak ada save pemain asli yang diberikan. Konteks player, descriptor member, dan record 8-byte dibuat dari bentuk data yang dikonsumsi loader. Jadi hasil membuktikan bahwa jalur cold-cache native bisa dijalankan dari tiga member yang dibentuk sesuai layout sumber, bukan bahwa byte ini berasal dari save tertentu. Satu-satunya dependency stub adalah impor SDK `memset`: NSO SDK tidak ada pada input worktree ini, maka callback meniru kontrak byte-fill dan mencatat tiga pemanggilan 30.000 byte. Fungsi game tetap berjalan sebagai instruksi ELF asli.

**Belum dieksekusi:** pengurangan bahan, pemberian item hasil, cancel/rollback, pemeriksaan atau penulisan state learned-recipe, interaksi halaman `WorkCraftBgPage` (`0x1596020`), dan operasi remake/customization. EventFlow `Ftr_Working` sebelumnya menunjukkan aksi `PlayerWorkbenchMaking`/`PlayerWorkbenchGetDemo` dan query/set/reset resep, tetapi bukti EventFlow itu belum menghubungkan efek transaksi ke save melalui native run. Nama sumber unlock juga belum dibuktikan. Tahap ini hanya menyelesaikan satu jalur akuisisi dan pemeriksaan bahan.

## Reproduksi

Dari root worktree:

```sh
python3 acnh-re/tools/crafting_transaction_followup_native.py
python3 -m unittest -v acnh-re.tests.test_crafting_transaction_followup_native
```

Runner memakai main ELF yang hash-nya `5bf707c3dc5dac0ad9635af7d336ec580f81c3f7876d0f55400d1900e3415d74`, NSO `inputs/additional_exefs/main` dengan hash `f8d248109ff72999b4600ae3749f8c7397fb960f7ad3ab8dee3018ae9e14e900`, RomFS tambahan, tabel bersama di `/workspace/acnh-re/output`, dan index read-only di `/workspace/acnh-re/output/index.sqlite`. Ringkasan seluruh state, call count, hash, stub, dan batas klaim ada di [crafting_transaction_followup_native.json](../output/gameplay/crafting_transaction_followup/crafting_transaction_followup_native.json).

## Tahap 2: resep, transaksi, workbench, dan remake

Tahap ini menelusuri handler native dan EventFlow secara statik. Label **[NATIVE STATIC]** berarti pseudocode decompiler dan call-site index cocok; fungsi transaksi belum dijalankan dengan konteks pemain nyata.

### Belajar resep

**[EVENTFLOW]** Dalam `Ftr_Working:RcoDIYtrialOngoing`, cabang tutorial memanggil `PlayerSetCraftRecipe` untuk `DIYtutorial1` (#22) dan kemudian `DIYtutorial2` (#30). `Ftr_Working:ChkCraftWoodBridge` dan `ChkCraftCampKit` memanggil query `PlayerHasCraftRecipe` untuk ID 7211 dan 5166, lalu menguji `PlayerIsMadeCraftRecipe` dan memanggil `PlayerResetCraftRecipe` pada grup WoodBridge/CampSite. Ini bukti pemakaian dan urutan EventFlow, belum bukti hasil pada save tertentu.

**[NATIVE STATIC]** `PlayerSetCraftRecipe` terdaftar pada constructor `0x32dc50`, dengan behavior di `0x32dd30`. Handler mencocokkan `UnlockType` dengan enum 46 nama; indeks `DIYtutorial1/2` adalah 12/13. Jalur grup memanggil helper `0xede0f0` dan enumerator `0xedf590`, sedangkan item spesifik melewati `0xedef00`. Helper save `0xedf0e0` menulis bit terindeks ke struktur save pemain. Query `PlayerHasCraftRecipe` di `0x42ac80` menggunakan helper `0xee1ec0` dan `0xee1f80` untuk memeriksa state. Perilaku ini belum dijalankan terhadap save nyata, sehingga nilai kembalian query dan perubahan bit untuk ID tutorial masih open.

### Cek bahan, konsumsi, dan hasil craft

**[EVENTFLOW]** Jalur `Workbench_Cmn_DIYdemo` memilih `SaveSetFromUIResult SaveType=cWorkCraft` (#212), lalu `PlayerWorkbenchMaking IsRemake=false` (#208) dan `PlayerWorkbenchGetDemo IsRemake=false` (#217). Handler `SaveSetFromUIResult` memetakan `cWorkCraft` ke case 9 dan helper `0x3358c0`.

**[NATIVE STATIC]** Helper `0x3358c0` menyiapkan hasil UI melalui `0xedf8e0` dan memanggil `0xee1420`. Fungsi transaksi memiliki enam call-site menuju `0xeff060`. Pada satu cabang kondisional, ia melewatkan kuantitas bahan bertanda negatif untuk enam slot; `0xeff060` meneruskan delta ke `0xf9e410`, yang mengurangi jumlah item yang cocok dan membatasi hasil negatif ke nol. Cabang lain memproses enam slot lewat `0xee1060`. Setelah pemrosesan bahan, jalur hasil memanggil `0xefab90` → `0xefac20` → `0xf987c0`.

Pemeriksaan assembly memperjelas jalur pocket-full tambahan `0xee1420` → `0xefbd30` → `0xf99270`. `0xefa9a0` memeriksa adanya slot kosong pada member pocket pemain (`+0x70`, tampilan `0x17c` byte); bila tidak ada, `0xee0ed0` berjalan dengan objek output sementara dan menelusuri enam material descriptor pada offset `0x2c` dengan stride `0x14`. Helper `0xeda620` menghitung total unit dan jumlah slot yang cocok. Pada kondisi hitungan stack tertentu, cabang hidup di `0xee104c` menyalin descriptor bahan saat ini ke objek sementara. Setelah enam slot diproses, `0xda4020` dan pemeriksaan descriptor `0xf58d00` harus sama-sama lolos sebelum `0xefbd30` meneruskan descriptor ke `0xf99270`; `0xefb090` menyusul sebagai helper update/notifikasi member. Helper slot-placement yang sama dipanggil jalur penambahan item umum `0xefac20` → `0xf987c0`, jadi pemakaian `0xf99270` di sini adalah primitive inventori bersama, bukan fungsi rollback khusus. Bukti statik menetapkan sumber objek sementara sebagai salah satu `RecipeCraftParam.MaterialN`, tetapi belum menentukan mengapa crafting memasukkan descriptor itu—kompaksi, pemulihan bahan, atau rollback. Rincian ada di `crafting_recipe_flow_native.json` bagian `craft_full_pocket_precheck`.

**Belum dieksekusi end-to-end:** precheck inventori pada helper transaksi (`0xee0ed0`), perubahan kuantitas bahan di save pemain, penambahan hasil, identitas objek sementara yang menuju `0xefbd30`, dan urutan/rollback saat interupsi. Bukti ini berbeda dari cold-cache check tahap 1: `0xee0be0` menguji cache bahan yang direkonstruksi, sedangkan `0xee1420` memakai jalur transaksi pemain.

### Workbench dan customization

**[NATIVE STATIC]** String `WorkCraftBgPage` menunjuk ke initializer `0x1596020`, yang mengatur object halaman dan manager UI. Fungsi ini tidak membuktikan commit transaksi. `WorkCraftInfoPage` dan `WorkCraftListPage` mempunyai initializer terpisah di `0x1597b90` dan `0x159cbc0`.

**[EVENTFLOW + TBL]** Jalur remake memilih item dengan filter `cWorkBenchRemake`, menjalankan `UIWorkingHandling cRemakeSelect`, lalu `SaveSetFromUIResult cWorkRemake` (#182), `PlayerWorkbenchMaking IsRemake=true` (#184), dan `PlayerWorkbenchGetDemo IsRemake=true` (#185). Dalam tutorial remake, event memberi 50 item 2513 sebelum memilih item 3436. Tabel `ItemParam` mengenali 2513 sebagai `CraftRemake` bernama リメイクキット dan 3436 sebagai もくせいクロゼット. Baris `ItemRemake.UniqueID=168` untuk item 3436 menetapkan `RemakeKitNum=2`.

**[NATIVE STATIC]** `cWorkRemake` berada di case 10 `SaveSetFromUIResult`, menuju `0x335d10`. Disassembly menunjukkan handler membuat ID kit `0x9d1` (2513), memuat jumlah dari `context+0x14`, lalu meneruskan ID dan jumlah itu ke `0xefbdf0`. Helper tersebut meneruskan argumen jumlah ke `0xf99b10`, yang mengubah inventory. Pemetaan row `ItemRemake.RemakeKitNum` ke jumlah itu pada jalur bit-4-clear sudah dibuktikan di [CRAFTING_REMAKE_COST_STATIC.md](CRAFTING_REMAKE_COST_STATIC.md). Jalur tutorial memakai `cRemakeSelectTutorial`; probe native terbaru di artifact tahap 3 memetakan kode `0x38` ke `CraftPhoneCase` dan menguji objek item 3436 secara langsung.

### Status dan batas

| Bagian | Status | Batas klaim |
| --- | --- | --- |
| Cold-cache dan cukup bahan | **Proven, dieksekusi native** | Save member A/B/C adalah fixture rekonstruksi. |
| Unlock/query resep | **Proven, EventFlow + native statik** | Mutasi dan query tidak dijalankan terhadap save nyata. |
| Pengurangan bahan dan tambah hasil | **Proven, native statik** | Call path terlihat; transaksi tidak dijalankan end-to-end. |
| WorkCraftBgPage | **Proven, initializer halaman** | Interaksi UI/commit tidak dijalankan. |
| Remake tutorial dan pengurangan kit | **Proven statik + native predicate** | Tutorial memberi 50 kit dan memilih item 3436; cost 2 mengalir ke kuantitas inventori pada jalur bit-4-clear. Predicate native `0x15806f0` menghasilkan false untuk ItemParam 3436 (`Ftr`) dan true untuk kontrol 8760 (`CraftPhoneCase`). Builder UI penuh belum dijalankan. |
| Cancel sebelum handler | **Proven di EventFlow untuk entry Remake biasa** | Batal dari pemilih hasil keluar/ulang sebelum `Workbench_Cmn_DIYdemo`; nilai tombol yang diterjemahkan UI dan pembatalan internal tutorial belum dibuktikan. |
| Rollback/refund setelah handler | **Open, sumber objek tambahan terpetakan** | Pocket-full precheck dapat menyalin descriptor `RecipeCraftParam.MaterialN` ke helper insertion. Tujuan gameplay dan efeknya pada saldo item belum dieksekusi; handler remake tidak punya refund kit eksplisit. Interupsi dan atomicity penuh belum dijalankan. |
| Persistensi inventory | **Request SaveProc terbukti secara statik** | `System_SaveGameClose#1` memakai `Process=cAll`; handler `SaveSimpleSave` tail-dispatch ke `0x338080` lalu `0xfb3160 → 0xfaf180`, dan jalur update memeriksa completion. Serializer serta write/flush durable setelah `SaveProc` belum ditemukan. Jalur `cWorkCraft` tidak memanggil SaveProc secara langsung. |

Harness pemeriksa statik menyimpan call graph, enum, nilai tabel, provenance, dan status di [crafting_transaction_followup_static.json](../output/gameplay/crafting_transaction_followup/crafting_transaction_followup_static.json). Ia mengindeks 12 pemakaian `SaveSimpleSave`, dispatch `0x338080 → 0xfb3160 → 0xfaf180`, dan jalur pemeriksaan completion; flush durable setelah `SaveProc` belum ditemukan. Harness membaca index, tabel, decompilation dan output tahap 1; tidak menyalin sumber besar.

Reproduksi tahap 2 dari root worktree:

```sh
python3 acnh-re/tools/crafting_transaction_followup_static.py
python3 -m unittest -v acnh-re.tests.test_crafting_transaction_followup_static
python3 acnh-re/tools/gameplay_flow.py --output-root /workspace/acnh-re/output tree Ftr_Working --entry RcoDIYtrialOngoing
python3 acnh-re/tools/gameplay_flow.py --output-root /workspace/acnh-re/output tree Ftr_Working --entry Workbench_Cmn_DIYdemo
python3 acnh-re/tools/gameplay_flow.py --output-root /workspace/acnh-re/output tree Ftr_Working --entry RcoRemakeTrialOngoing
```

## Tahap 3: skema resep, status belajar, dan pengurangan bahan

Tahap ini menambah join tabel yang menyeluruh, transisi belajar/reset resep, dan dua probe native kecil. Hasil terstruktur ada di [crafting_recipe_flow_native.json](../output/gameplay/crafting_transaction_followup/crafting_recipe_flow_native.json). Harness membaca index bersama dalam mode SQLite `mode=ro`; semua native fixture dibuat di memori.

### `RecipeCraftParam` dan kunci silang

**[TBL]** Tabel berisi 552 baris dengan row size 52. Kunci `UniqueID` adalah `u16` pada offset `0x30`; rentangnya 6–672 dan memiliki 115 celah. `Item` (`u16`, offset `0x2c`) menunjuk ke `ItemParam.UniqueID`. Enam slot bahan adalah pasangan `MaterialN`/`AmountN`, keduanya `u16`; sentinelnya `MaterialN=65534` dengan jumlah 0. Offset fisik pasangan tidak berurutan di BCSV dan dicatat satu per satu dalam artifact.

Join lengkap pada dump 1.0.0 menghasilkan 552/552 output unik yang cocok dengan `ItemParam.UniqueID`; baris output yang sama memiliki `ItemParam.DiyRecipeID == RecipeCraftParam.UniqueID`. Semua 1.020 slot bahan berisi item ID yang juga ada pada `ItemParam.UniqueID`. Dengan demikian `ItemParam.DiyRecipeID` adalah kunci silang balik untuk output resep, sedangkan material slot tetap menyimpan ID item langsung.

Contoh `UniqueID=56`: item hasil 975, `ItemParam.DiyRecipeID=56`, dan lima buah masing-masing jumlah 1: Apple 2213, Pear 2285, Cherry 2287, Orange 2214, Peach 2286. `UniqueID=458` menghasilkan item 7211 (`CraftUnlock=WoodBridge`); `UniqueID=461` menghasilkan 5166 (`CraftUnlock=CampSite`). Baris ini menghubungkan angka di EventFlow dengan ID resep yang dipakai bitmap.

### Perubahan state resep

**[EVENTFLOW + NATIVE STATIC]** Aksi `PlayerSetCraftRecipe` berada pada constructor `0x32dc50` dan handler `0x32dd30`. Handler memetakan string `UnlockType` lewat enum 46 nilai. `ItemUniqueId=65534` pada tutorial mengarahkan aksi ke grup `CraftUnlock`; enumerator `0xede0f0` membuat daftar recipe ID yang cocok dan `0xedf590` menerapkan setter untuk tiap resep. Jalur `ItemUniqueId` yang valid memakai `0xedef00`.

Event tutorial #22 memberi grup `DIYtutorial1` (satu baris tabel), kemudian #30 memberi `DIYtutorial2` (dua baris). Pada alur jembatan, query `PlayerHasCraftRecipe` meminta output item 7211; tabel menghubungkan ID itu ke resep 458/`WoodBridge`. Alur perkemahan memakai output 5166 dan resep 461/`CampSite`. Setelah `PlayerIsMadeCraftRecipe` cocok, aksi reset grup berjalan (#70 dan #75). Handler reset `0x32cff0` mengulang pemilihan berdasarkan `CraftUnlock`, lalu `0xedf6e0` mengirim setiap ID ke `0xedf830`, yang menghapus bit melalui `0xf290b0`.

Writer `0xedf0e0` menggunakan bitmap resep dengan ID 0–2047. Alamat bit yang ditulis adalah `save+0x8e920 + selector*0x100 + (recipe_id >> 3)`, dengan mask `1 << (recipe_id & 7)`; selector di luar 0–7 kembali ke grup 0. Query native `0xee1ec0` mengambil `ItemParam.DiyRecipeID`, lalu memeriksa bit melalui `0xf28fd0`. Probe native memanggil langsung helper bit test/set/clear atas array 256-byte sintetis: ID 458 dan 461 berubah 0→1→0; ID 2047 diterima; ID 2048 diabaikan. Ini memverifikasi helper bit, bukan writer penuh atau save pemain. Query EventFlow `PlayerHasCraftRecipe` memiliki tambahan logika grup, dan nilai/polaritas akhirnya belum dijalankan terhadap save.

`PlayerIsMadeCraftRecipe` menyimpan state terpisah dari resep yang dipelajari. Pemetaan key kini terbukti statik, dengan leaf bitmap diverifikasi native. Saat `0xedf8e0` membentuk hasil, `0xfdc240` menaruh `RecipeCraftParam.UniqueID` pada u16 pertama payload; `0xee1420` meneruskan field itu ke `0xee17e0`, lalu `0xf29080` menulisnya pada lane kedua bitmap di offset member `+0x100`. Getter `0xf29010` memakai lane yang sama. Batas `0x800` berlaku pada ID resep.

Query `PlayerIsMadeCraftRecipe` (`0x42d3b0`) memanggil `0xedbd00` untuk masing-masing delapan slot `MadeItemID`. Helper itu memakai `0xab4f60`/`0xab78e0` untuk mengubah `ItemParam.UniqueID` menjadi `ItemParam.DiyRecipeID`, lalu membaca bit lewat `0xf29010`. Jalur konversi memakai record umum `ItemParam.UniqueID=0x16a2` yang bertipe `DIYRecipe` (ItemKind row `0x55`); nilai `DiyRecipeID` dari item input yang menjadi key. Audit seluruh index EventFlow menemukan dua query saja: `MadeItemID=7211` (HousingKitBridge) dipetakan ke resep 458/`WoodBridge`, dan `MadeItemID=5166` (HousingKit) ke resep 461/`CampSite`; keduanya `cAND` dengan satu slot populated dan tujuh sentinel. ID item di atas `0x7ff` tidak memerlukan bitmap terpisah.

`tools/crafting_recipe_flow_native.py` menjalankan pasangan leaf `0xf29080`/`0xf29010` pada key resep 56, 458, 461, 2047, dan 2048; hasil cocok dengan domain dan mask byte. Ini menguji operasi bitmap dan menggabungkannya dengan jejak native statik serta join tabel untuk dua `MadeItemID` tinggi. Wrapper query lengkap dan polaritas `cAND`/`cOR` pada campuran input belum dijalankan terhadap save-player fixture.

### Bahan dan titik commit workbench

**[NATIVE]** Tahap material sebelumnya sudah menjalankan getter `0xedac50` dan cek cold-cache `0xee0be0` memakai lima slot asli resep 56 serta record A/B/C yang direkonstruksi. Probe baru menjalankan helper kuantitas bertanda `0xf9e410` pada pocket fixture berisi item Apple 2213: 9 dikurangi 3 menjadi 6, 2 dikurangi 3 menjadi 0, dan 9 dikurangi 9 menjadi 0. Hanya field jumlah `u16` di `+0x100` yang berubah; slot item tetap terisi di fixture ini, jadi hasil tersebut tidak menetapkan aturan kompaksi atau penghapusan slot.

Probe ini memaksa `0xaac730` bernilai benar karena konteks manager penuh untuk predikat item itu belum dibangun. Selebihnya, pencarian slot, `0xf9e840`, alur `0xf9e410`, dan tulis jumlah berjalan sebagai instruksi ELF asli. Kasus permintaan lebih besar dari jumlah sengaja melewati gate kecukupan transaksi; hasil clamp ke nol bukan bukti bahwa craft penuh menerima bahan kurang. Gate `0xee0ed0` pada transaksi tetap belum dieksekusi sebagai jalur lengkap.

**[NATIVE STATIC + EVENTFLOW]** `Workbench_Cmn_DIYdemo` mengirim `SaveSetFromUIResult cWorkCraft` (#212), lalu `PlayerWorkbenchMaking` (#208), `PlayerWorkbenchGetDemo` (#217), dan putaway (#221). Case 9 di handler SaveSet (`0x3358c0`) menyiapkan hasil lewat `0xedf8e0` dan masuk ke transaksi `0xee1420` sebelum aksi Making/Demo berikutnya. Transaksi memeriksa flag bahan melalui `0xee0ed0`; satu cabang berisi enam delta negatif melalui `0xeff060 → 0xf9e410`, diikuti jalur tambah hasil `0xefab90 → 0xefac20 → 0xf987c0` dan marker. `WorkCraftBgPage` `0x1596020` tetap merupakan initializer UI, bukan titik commit yang terbukti.

`0xeff060` membuka member pocket pemain dan mengubah record yang ada di memori. `SaveSimpleSave` merupakan request terpisah: index menemukan 12 aksi tersebut, termasuk `System_SaveGameClose#1` dengan `Process=cAll`. Handler aksinya tail-dispatch ke `0x338080`, yang menjalankan `0xfb3160 → 0xfaf180` untuk memasukkan operasi `SaveProc`; jalur update memeriksa penyelesaiannya. Handler `cWorkCraft` dan `0xee1420` tidak memanggil jalur request itu secara langsung. Ini menetapkan batas antara mutasi inventory di memori dan request save eksplisit. Serializer serta write/flush ke file setelah `SaveProc` belum teridentifikasi, dan transaksi craft tetap belum diuji untuk atomicity/interupsi.

### Batas lanjutan SaveProc dan uji fixture parsial

**[NATIVE STATIC]** Caller inisialisasi `0x96ef0` mendaftarkan worker bernama `SaveProc` melalui `0xfb4150 → 0xd4240`. Operasi yang dikirim `0xfb3160 → 0xfaf180` masuk ke queue berrecord 0x38 byte. Poller `0xfaf210` mengambil record dan mencapai thunk `0xfb41c0 → 0xd45c0`. Dispatcher umum `0xfaf360` memanggil `0xfaf4e0`, lalu memilih callback tidak langsung dari object queue pada offset `+0x10` atau `+0x30`; `0xd45c0` meneruskan data task ke `0x2201820`. Pointer callback yang dipakai untuk `SaveProc` belum diidentifikasi, jadi call chain ini belum membuktikan serializer.

Audit import menemukan `nn::fs::OpenFile`, `WriteFile`, `FlushFile`, dan `Commit` masing-masing cocok unik dengan export di modul terpisah `sdk`. Tidak ada call langsung ke wrapper filesystem itu dari fungsi request/queue/dispatch yang terindeks. Callback dinamis masih dapat memanggilnya. Sandbox native saat ini memetakan `main.elf` saja dan tidak menjalankan implementasi SDK atau filesystem, sehingga flush durable tidak dapat disimpulkan dari probe yang ada.

**[UJI NATIVE PARSIAL; TIDAK MENCAPAI INSERTION]** Fixture `0xee1420` memakai ID bahan aktual resep 56, tetapi tidak membangun semua manager/cache dunia. Instruksi asli mencapai mutator pertama `0xeff060`, lalu gagal pada read `0xab941c`: jalur `0xa9e440 → 0xa774c0 → 0xab9400` menerima pointer manager/table null dari GOT `0x32f3f78` dan mendereferensikan pointer hasil yang tidak valid. Nama/semantik manager itu belum ditetapkan. Probe langsung `0xefbd30` mencapai resolver pemain `0xe670b0`, tetapi berhenti karena service dunia/player di GOT `0x32d3d78` bernilai null; `0xf99270` tidak dipanggil. Kedua percobaan tidak membuktikan item descriptor yang dipindah, tujuan refund, atau perilaku saat interupsi. Detail argumen, PC, dan batas fixture ada di [crafting_transaction_fixture_attempt.json](../output/gameplay/crafting_transaction_followup/crafting_transaction_fixture_attempt.json); jalankan `tools/crafting_transaction_fixture_attempt.py` untuk mengulanginya.

Pemeriksa statik kini mencatat worker task dan import SDK di [crafting_transaction_followup_static.json](../output/gameplay/crafting_transaction_followup/crafting_transaction_followup_static.json). Status runtime tetap terbuka sampai manager item/cache dan service pemain dari inisialisasi dunia penuh direkonstruksi; setelah itu barulah identity descriptor dan jalur batalkan/interupsi dapat diuji.

Reproduksi tahap 3 (argumen `--output-root` menunjuk ke index/tabel bersama yang valid dan dibuka read-only):

```sh
python3 acnh-re/tools/crafting_recipe_flow_native.py --output-root /workspace/acnh-re/output
```
