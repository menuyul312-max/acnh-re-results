# Tindak lanjut sistem progression

**Tanggal:** 2026-11-06

**Fokus:** ketersediaan bahan resep crafting, satu irisan yang terukur.

Item terbuka pertama dalam cakupan tugas di `re_queue.json` adalah `crafting-diy` (prioritas 4). Tujuan besarnya juga mencakup belajar resep, konsumsi bahan, alur workbench penuh, dan remake. Bukti sebelumnya sudah menguji getter bahan resep dan helper persyaratan pada warm-cache secara terpisah. Iterasi ini menghubungkan dua fungsi native itu pada satu baris resep nyata, lalu berhenti pada hasil cukup/tidak cukup.

## Bukti dan hasil

**[TBL]** `RecipeCraftParam` memiliki 552 baris berukuran 52 byte dan enam pasang `MaterialN`/`AmountN`. Baris `UniqueID=56` membuat item `975` (`FtrFruitbasket`) dari masing-masing satu Apple (`2213`), Pear (`2285`), Cherry (`2287`), Orange (`2214`), dan Peach (`2286`). Hash SHA-256 tabel hasil resolve sama dengan `romfs/Bcsv/RecipeCraftParam.bcsv`: `97fe6d73e183dab43dad7358627a0a1a43f5764f0a18fa044a63a9ecf56ba919`.

**[NATIVE]** Getter `0xedac50` mengeluarkan enam slot bahan dan kuantitas byte-rendah dari baris itu: lima slot terisi, lalu slot kosong yang tidak ditulis. Helper persyaratan warm-cache `0xee0be0` memeriksa keenam slot yang sama. Dengan satu bahan masing-masing di cache sintetis, byte kecukupan tetap `1`. Saat Pear dihilangkan, pemeriksaan slot Pear mengubahnya menjadi `0`; slot sesudahnya mempertahankan nilai gagal itu. Pada kedua skenario helper tidak mengubah penghitung cache. Call graph dalam index mencatat enam panggilan dari `0xedc240` ke `0xee0be0`; dekompilasi statis `[PSEUDO]` menunjukkan argumen slot 0 sampai 5.

**[EF]** `Ftr_Working.bfevfl` pada RomFS tambahan memuat mode UI crafting/remake (`cCraft`, `cRemakeSelect`, `cCraftTutorial`), aksi `PlayerWorkbenchMaking` dan `PlayerWorkbenchGetDemo` untuk kedua nilai `IsRemake`, serta query/aksi resep seperti `PlayerHasCraftRecipe`, `PlayerIsMadeCraftRecipe`, dan `PlayerSetCraftRecipe`. Ini membuktikan isi flow, tetapi belum membuktikan urutan event penuh atau transaksi native di balik aksinya.

**[PSEUDO]** Masukan ketersediaan berupa penghitung warm-cache sintetis. Eksperimen ini tidak memuat save pemain, menjalankan producer cache A/B/C, mengonsumsi bahan, memberikan item hasil, menguji gerbang resep yang sudah dipelajari, atau mengeksekusi `WorkCraftBgPage` (`0x1596020`). `inventory_cache_native.json` dan `inventory_requirements_native.json` yang sudah ada merupakan bukti native terkait, tetapi hasil ini tidak mengklaim dua harness terpisah itu sebagai satu run dari save sampai crafting. Remake dan aturan sumber unlock tetap terbuka.

## Cara mengulang dan asal data

Jalankan dari root worktree:

```sh
python3 acnh-re/tools/progression_followup_native.py
```

Harness menjalankan `A_logic/main.elf` asli dengan SHA-256 `5bf707c3dc5dac0ad9635af7d336ec580f81c3f7876d0f55400d1900e3415d74`. Hash NSO `main` yang disediakan juga diverifikasi (`f8d248109ff72999b4600ae3749f8c7397fb960f7ad3ab8dee3018ae9e14e900`), tetapi emulator memakai ELF tersebut, bukan memuat NSO secara langsung. Harness hanya membaca RomFS tambahan dan `/workspace/acnh-re/output/index.sqlite`. Hasil per slot, bukti panggilan EventFlow, dan hash sumber ada di [crafting_material_availability_native.json](../output/gameplay/progression_followup/crafting_material_availability_native.json).

**Verifikasi:** satu baris resep; 6 panggilan getter native; 12 panggilan helper persyaratan native untuk keadaan cukup dan kurang satu bahan; 6 titik panggilan langsung pada index; 0 ketidakcocokan. Hasil hanya ditulis ke `output/gameplay/progression_followup/`.
