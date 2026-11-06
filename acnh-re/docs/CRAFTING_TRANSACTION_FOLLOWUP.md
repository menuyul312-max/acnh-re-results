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

**[NATIVE STATIC]** Helper `0x3358c0` menyiapkan hasil UI melalui `0xedf8e0` dan memanggil `0xee1420`. Fungsi transaksi memiliki enam call-site menuju `0xeff060`. Pada satu cabang kondisional, ia melewatkan kuantitas bahan bertanda negatif untuk enam slot; `0xeff060` meneruskan delta ke `0xf9e410`, yang mengurangi jumlah item yang cocok dan membatasi hasil negatif ke nol. Setelah pemrosesan bahan, jalur hasil memanggil `0xefab90` → `0xefac20` → `0xf987c0`, helper penambahan item umum. Jalur lain memanggil `0xee17e0` → `0xf29080`, yang menulis bit untuk key di bawah `0x800`; hubungan marker terbatas ini dengan `MadeItemID` seperti 7211 belum terbukti.

**Belum dieksekusi end-to-end:** precheck inventori pada helper transaksi (`0xee0ed0`), perubahan kuantitas bahan di save pemain, penambahan hasil, dan urutan/rollback saat interupsi. Bukti ini berbeda dari cold-cache check tahap 1: `0xee0be0` menguji cache bahan yang direkonstruksi, sedangkan `0xee1420` memakai jalur transaksi pemain.

### Workbench dan customization

**[NATIVE STATIC]** String `WorkCraftBgPage` menunjuk ke initializer `0x1596020`, yang mengatur object halaman dan manager UI. Fungsi ini tidak membuktikan commit transaksi. `WorkCraftInfoPage` dan `WorkCraftListPage` mempunyai initializer terpisah di `0x1597b90` dan `0x159cbc0`.

**[EVENTFLOW + TBL]** Jalur remake memilih item dengan filter `cWorkBenchRemake`, menjalankan `UIWorkingHandling cRemakeSelect`, lalu `SaveSetFromUIResult cWorkRemake` (#182), `PlayerWorkbenchMaking IsRemake=true` (#184), dan `PlayerWorkbenchGetDemo IsRemake=true` (#185). Dalam tutorial remake, event memberi 50 item 2513 sebelum memilih item 3436. Tabel `ItemParam` mengenali 2513 sebagai `CraftRemake` bernama リメイクキット dan 3436 sebagai もくせいクロゼット. Baris `ItemRemake.UniqueID=168` untuk item 3436 menetapkan `RemakeKitNum=2`.

**[NATIVE STATIC]** `cWorkRemake` berada di case 10 `SaveSetFromUIResult`, menuju `0x335d10`. Disassembly menunjukkan handler membuat ID kit `0x9d1` (2513), memuat jumlah dari `context+0x14`, lalu meneruskan ID dan jumlah itu ke `0xefbdf0`. Helper tersebut meneruskan argumen jumlah ke `0xf99b10`, yang mengubah inventory. Pemetaan row `ItemRemake.RemakeKitNum` ke jumlah itu pada jalur bit-4-clear sudah dibuktikan di [CRAFTING_REMAKE_COST_STATIC.md](CRAFTING_REMAKE_COST_STATIC.md). Jalur tutorial memakai `cRemakeSelectTutorial`; sumber bit 4 adalah predikat tipe item, dan crosswalk kode `0x38` ke `CraftPhoneCase` masih berstatus kandidat.

### Status dan batas

| Bagian | Status | Batas klaim |
| --- | --- | --- |
| Cold-cache dan cukup bahan | **Proven, dieksekusi native** | Save member A/B/C adalah fixture rekonstruksi. |
| Unlock/query resep | **Proven, EventFlow + native statik** | Mutasi dan query tidak dijalankan terhadap save nyata. |
| Pengurangan bahan dan tambah hasil | **Proven, native statik** | Call path terlihat; transaksi tidak dijalankan end-to-end. |
| WorkCraftBgPage | **Proven, initializer halaman** | Interaksi UI/commit tidak dijalankan. |
| Remake tutorial dan pengurangan kit | **Proven statik untuk bit-4-clear** | Tutorial memberi 50 kit dan memilih item 3436; cost 2 mengalir ke kuantitas inventori pada jalur normal. Bit 4 diturunkan dari predikat tipe item `0x38`; nilai runtime untuk item tutorial belum diuji. |
| Cancel sebelum handler | **Proven di EventFlow untuk entry Remake biasa** | Batal dari pemilih hasil keluar/ulang sebelum `Workbench_Cmn_DIYdemo`; nilai tombol yang diterjemahkan UI dan pembatalan internal tutorial belum dibuktikan. |
| Rollback/refund setelah handler | **Open** | Caller mengabaikan status pengurangan kit dan tidak menunjukkan refund eksplisit; nested rollback lain dan interupsi transaksi lengkap belum dijalankan. |
| Persistensi inventory | **Mutasi record pemain terbukti statik** | `0xefbdf0` membuka member `player+0x70`, tetapi batas flush/durabilitas ke file save belum ditemukan. |

Harness pemeriksa statik menyimpan call graph, enum, nilai tabel, provenance, dan status di [crafting_transaction_followup_static.json](../output/gameplay/crafting_transaction_followup/crafting_transaction_followup_static.json). Ia hanya membaca index, tabel, decompilation dan output tahap 1; tidak menyalin sumber besar.

Reproduksi tahap 2 dari root worktree:

```sh
python3 acnh-re/tools/crafting_transaction_followup_static.py
python3 -m unittest -v acnh-re.tests.test_crafting_transaction_followup_static
python3 acnh-re/tools/gameplay_flow.py --output-root /workspace/acnh-re/output tree Ftr_Working --entry RcoDIYtrialOngoing
python3 acnh-re/tools/gameplay_flow.py --output-root /workspace/acnh-re/output tree Ftr_Working --entry Workbench_Cmn_DIYdemo
python3 acnh-re/tools/gameplay_flow.py --output-root /workspace/acnh-re/output tree Ftr_Working --entry RcoRemakeTrialOngoing
```
