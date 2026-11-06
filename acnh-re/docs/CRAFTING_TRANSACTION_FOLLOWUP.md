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
