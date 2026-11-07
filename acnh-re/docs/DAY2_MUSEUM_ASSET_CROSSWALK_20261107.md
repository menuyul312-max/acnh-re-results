# Day 2 through museum: story-to-asset crosswalk

**Tanggal: 7 November 2026.** Part mesin ada di [day2_museum.json](../output/gameplay/story_asset_parts/day2_museum.json). Enam beat mencakup start hari kedua/pengumuman bandara, workshop DIY, biaya pindah dan rumah pertama, donasi awal/tenda Blathers, ambang donasi 20/pembangunan museum, lalu pengumuman museum dan pembukaan resep alat.

## Bukti yang tersambung

- EventFlow menyebut `SNPC_rco_00_StartMainGame`, pengumuman `TownNews_OnThe2ndDay`, workshop `Ftr_Working`, resep `DIYtutorial1/2`, item cabang `2500`, app recipe, biaya pindah 5.000 Nook Miles, filter `OwlDonation`, tenda museum dan hadiah/pengumuman terkait. Referensi bab ada di [GAMEPLAY_FLOW.md](GAMEPLAY_FLOW.md) §§2–4.
- Query `MuseumDonationNumCheck Border=5` dan `Border=20` membatasi tahap donasi; `DecidedMuseumTentPlace` mengikat penyelesaian penempatan kit ke flow. Ini bukti graf, bukan bukti model tenda atau koordinat.
- Processor museum `0xf77050` membaca struktur jenis 2 dan flag state 1→2→3 dalam catatan pseudocode. Ini belum dijalankan pada save nyata dari donasi sampai pergantian hari.
- Unlock `MarketSellRecipeScoopStick` dicatat sebagai state/event. Itu tidak membuktikan page toko, ikon resep, atau layout tertentu.

Setiap beat memiliki sebelas field kelas aset wajib: UI, animasi, model, audio, teks, tekstur, material/shader, efek, font, world data, collision. Link yang diketahui merujuk nama flow atau item; family tanpa path/consumer tertentu dicatat `OPEN`. Katalog model/audio tidak dipakai untuk menebak mesh atau sound acara.

Indeks UI memberi binding statik `WorkCraftInfoPage→WorkBenchInfo`, `WorkCraftListPage→WorkBench`, dan `MenuRecipePage→MenuRecipe`; indeks BFLAN memiliki track `WorkBenchInfo_*`, `WorkBenchBG_In/Change/Out`, dan `MenuRecipe_In/Out`. Katalog memberi kandidat model `FtrWorkbench`, `NpcSpRco`, `NpcSpOwl`, `StrcMuseumA00Reserve/Build`, serta audio `Player/Pl_LearningRecipe_00`, `Npc_Diy_Hummer_*`, `UI_WorkCraftInfo/*`, `BGM_Indoor_Museum_Tent`, dan ambience konstruksi. Semua nama katalog tersebut berstatus `CAT`: kandidat bernama/path saja, tanpa file model/audio mentah dan tanpa bukti pemanggil cerita. Static page-to-layout dan BFLAN resource presence juga belum membuktikan page atau animasi dipicu oleh beat tutorial.

## Yang belum tertutup

Transaksi bahan DIY—pemeriksaan, pengurangan, hasil, rollback, interupsi dan flush save—belum terbukti end-to-end. Pembayaran Nook Miles dan upgrade rumah belum ditautkan ke serializer durable. Donasi makhluk belum tersambung dari inventory nyata ke row donor dan ambang museum pada satu save. Cell/rotasi tenda, perubahan mesh ke gedung, actor/camera, page BFLYT, clip ASB/BFLAN, label MSBT dan audio consumer belum memiliki crosswalk final.

Karena `Model/` dan `Sound/Resource/` tidak tersedia, nama yang mungkin ditemukan di katalog tetap **CAT** saja. Part ini tidak mengklaim semua kebutuhan visual museum/workshop sudah dapat dikonversi; ia memastikan gap tiap kelas aset terlihat per beat dan menjadi target RE berikutnya.

Validasi yang dilakukan: parsing JSON dan pemeriksaan dengan [schema crosswalk](../output/gameplay/story_asset_crosswalk.schema.json). Pemeriksaan schema memastikan setiap beat memiliki placement dan semua kelas aset wajib; pemeriksaan itu tidak membuktikan interaksi runtime atau kecocokan visual.
