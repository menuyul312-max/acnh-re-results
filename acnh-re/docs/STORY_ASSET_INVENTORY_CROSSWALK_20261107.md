# Inventaris sumber dan konversi untuk crosswalk cerita

**Tanggal: 7 November 2026.** Laporan ini mengaudit kelas aset dan batas importer yang dapat mendukung crosswalk cerita utama. Angka bersumber dari [ADDITIONAL_ROMFS.md](ADDITIONAL_ROMFS.md), `output/coverage.json`, dan kode di `tools/reference/acnh_rip`. Rincian yang bisa dibaca mesin ada di [asset_inventory.json](../output/gameplay/story_asset_parts/asset_inventory.json).

## Cakupan aset

| Kelas | Tersedia / jumlah yang diketahui | Jalur konversi atau pemakaian | Batas untuk pemetaan cerita |
|---|---|---|---|
| Data gameplay | B_data: 1.171 file, 2.986 entri; termasuk 164 BCSV, 2.313 BYML, 47 AAMP, 456 EventFlow | Typed/indexed JSON; tautkan flow, table row, item/structure ID, flag dan stage dengan key mentah tetap utuh | 91 descriptor BCSV dan 431 hash key BYML unresolved; data yang terdecode belum membuktikan handler native |
| Teks/dialog | 965.426 pesan/label pada 14 bahasa dari MSBT/BDLI | MSBT→JSON, simpan label, bahasa, tag, archive dan rujukan node EventFlow | Pemilih label runtime, substitusi, sinkronisasi animasi dan voice playback belum sepenuhnya terhubung |
| UI | 523 BFLYT, 2.095 BFLAN, 431 BNTX container, 3.336 texture record; 356 `cnt1` dan 2.164 `usd1` belum semantik | BFLYT→pane-tree JSON; BFLAN→summary/raw sections; BNTX→PNG; ikat UIName/page factory/input ke flow | Belum seluruh page binding, focus, modal lifecycle, input, renderer parity atau capture live |
| Animasi | 83 ASB, 55 AnimationInfo BYML, 1.159 node, 10.001 transisi, 1.297 warp, 1.895 kasus parameter; BFLAN memuat animasi UI | ASB→state/transition graph; BFRES skeletal clip dapat disample menjadi JSON bila model/rig sumber tersedia; BFLAN ditangani terpisah | Syarat transisi ASB, pemilihan clip actor, rig binding, timing/blend dan root motion masih parsial; BFRES model source tidak tersedia |
| Model | Katalog 37.459 baris (5.627 menandai GLB+PNG dan 31.832 PNG saja); 7.668 ResName ItemParam cocok exact dengan Asset_ID katalog | Dengan raw source: Yaz0/SARC→BFRES→GLB; BNTX→PNG/HDR; animasi→JSON; `.phive` disimpan raw | `Model/` tidak ada. Katalog adalah nama/metadata, bukan mesh atau hasil ekspor terverifikasi; current exporter hanya LOD0 dan slot material terbatas |
| Audio | Katalog 17.410 baris (860 BGM, 16.550 SFX) | Dengan raw source: BARS/AMTA→BWAV offsets; BWAV→PCM WAV→OGG; indeks mempertahankan rate/channel/sample/loop | `Sound/Resource/` tidak ada. Tidak ada waveform yang dapat divalidasi; katalog tidak membuktikan file, consumer, loop atau timing konser/prolog |
| Tekstur/material/shader | BNTX UI tersedia; dua BFSHA archive, 5 shading-model records, 1.889 program slots, 133 GLSL members (30 hash unik), 256 BNSH | Decode texture ke PNG/HDR; pertahankan shader bytes/options dan ikat ke material/model/actor lewat consumer | Model textures dan banyak binding material tidak tersedia; slot/options bukan implementasi shader lengkap |
| Efek | Dua VFXB/PTCL, ELink2DB.belnk, SLink2DB.bslnk | Pertahankan bytes/hash; hubungkan emitter, timing, material, actor dan trigger sebelum mapping runtime | Semantik PTCL/XLNK dan consumer story belum lengkap |
| Font | Importer mengenali BFTTF/BFOTF dan BFFNT; FontInfo dapat dipakai bila sumber ada | Scalable BFTTF/BFOTF→TTF/OTF; BFFNT disimpan raw bila belum terbaca | Page-to-font dan pemakaian spesifik prolog/dialog masih harus dicocokkan |
| World/collision | FieldPreset/item/structure records, terrain-unit/PBC references, native collision consumers; `.phive` diharapkan ada dalam model archive | Pertahankan grid/source IDs; transform hanya dipromosikan setelah loader/consumer terbukti; simpan `.phive` raw sampai decode tervalidasi | Full seed→world loader/placement belum selesai; model archive tidak ada; solver, mask, friction dan actor→collider binding parsial |

## Prinsip pemakaian untuk tiap beat

Setiap beat prolog sampai Island Designer harus menunjuk atau secara eksplisit menandai `OPEN`/`CAT` untuk UI, animasi, model, audio, teks, texture, material/shader, effects, font, world data, dan collision. Inilah cara memastikan kategori aset tidak hilang dari mapping. Ini **bukan** berarti semua 37.459 model atau 17.410 audio katalog digunakan di cerita utama; crosswalk hanya mengaitkan kandidat yang mempunyai hubungan sumber ke flow/actor/item/structure.

Satu asset link baru dapat dinaikkan dari `CAT` bila sumber/path/file atau row ID ditemukan dan hubungannya ke consumer story ditunjukkan. Link baru dapat disebut terkonversi bila importer menghasilkan output dengan provenance/hash. Link baru dapat disebut akurat bila output diuji terhadap consumer game atau data referensi native yang relevan. Katalog tidak dapat menaikkan status tersebut.

## Urutan konversi yang dicatat

1. BCSV/BYML/AAMP/EventFlow dibaca ke JSON typed dengan source IDs dan integer raw dipertahankan.
2. MSBT/BDLI diekspor dengan label dan tag; kaitkan label ke EventFlow path sebelum menentukan dialog per beat.
3. BFLYT, BFLAN, BNTX, ASB, font dan UI shader diproses oleh importer referensi yang tersedia; validasi key/layout/texture dan catat konten raw untuk bagian yang belum dimengerti.
4. Model: hanya saat Model/SARC/BFRES/BNTX tersedia, decode ke GLB/PNG/HDR/animation JSON sambil mempertahankan sumbu/unit, material extras dan LOD limit. `.phive` tidak dianggap terdecode.
5. Audio: hanya saat BWAV/BARS tersedia, baca metadata/loop dari BWAV, konversi WAV→OGG dan bandingkan loop offset serta consumer. Audio katalog tetap `CAT`.
6. World placement/collision dipetakan dari preset → grid/cell → structure/item instance → transform → model/collider/actor; setiap transform yang belum dibuktikan ditinggalkan `OPEN`.

Inventaris mesin tersedia di [story_asset_crosswalk.json](../output/gameplay/story_asset_crosswalk.json) bersama part per urutan cerita. Pass struktural sudah lengkap: 28 beat, empat part cerita valid, dan 11 keluarga aset pada setiap beat. Manifest mencatat 381 rujukan aset untuk 308 slot minimum: 235 `OPEN`, 73 `CAT`, 35 `EF`, 13 `PSEUDO`, 18 `STRUCT`, dan 7 `TBL`. Ini menutup kelengkapan kategori pada crosswalk, bukan seluruh pemakaian semantik. Consumer cerita, transform dunia, binding UI/animasi, serta aset mentah model dan audio masih belum terbukti; model/audio hanya punya kandidat katalog.
