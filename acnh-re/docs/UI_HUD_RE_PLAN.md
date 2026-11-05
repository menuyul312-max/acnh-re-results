# Rencana sisa reverse engineering UI/HUD

Status diperbarui 5 November 2026. Fokus hanya UI/HUD ACNH 1.0.0. Analisis RomFS/ExeFS yang tersedia tetap lokal; Godot hanya dibaca dan tidak ada push.

## Status

| Area | Status | Bukti / batas berikutnya |
|---|---|---|
| Inventaris layout | Selesai untuk dump yang tersedia | 524 arsip Layout direkonsiliasi dengan 523 member BFLYT dan 10.882 pane. Tidak ada klaim bahwa ini memuat semua perilaku/game state. |
| HUD utama dan smartphone | Struktur terpetakan | MainScreen 32 pane/29 slot sublayout; MainScreenSmartPhone 24 pane/5 grup animasi. Pemicu, controller smartphone, dan state bersamaan belum dilacak lengkap. |
| Section BFLYT | Struktur terpetakan | CNT1, USD1/ui2dsys, PRT1, WND1, BND1/SCR1, serta rentang group `grs1/gre1` tervalidasi. Efek hit-test, clipping, shape, dan flag renderer tetap belum terbukti. |
| Resource/material/font | Binding statis selesai | 6.076 material, 6.475 texture links, 276 referensi font terikat. Pilihan BNSH/pass, sampler/blend runtime, locale/fallback, dan pixel parity masih terbuka. |
| Part ganda | Dikorelasikan, belum terpecahkan | 35 referensi memiliki dua kandidat berbeda. Tepat satu kandidat pada tiap kasus berbagi suffix `.zs`/`.szs` dengan host; korelasi kuat tetapi bukan aturan loader yang terkonfirmasi. |
| Animasi | Format dan target statis terpetakan | 16.147 kurva/91.933 key, semua 52 kombinasi section/property dikenal; 15 FLEU terurai dan tertaut ke userData pane unik. Pemanggilan, timing, dan consumer FLEU belum diketahui. |
| Native UI | Sebagian | 31 pendaftaran halaman dan sejumlah jalur kalender, item, peta, device, dialog, serta keyboard berkorelasi. Routing input/focus, lifecycle, dan smartphone controller belum lengkap. |
| Konversi Godot | Belum dilakukan | Ada resep konversi dan preview inspeksi. Belum ada importer/scene UI atau capture pembanding dengan game. |

## Temuan yang sudah ditutup secara statis

- Rekonsiliasi seluruh archive/member BFLYT dan indeks layar, pane, group, part reference, material, tekstur, font, serta animasi.
- Decode seluruh section CNT1/USD1/PRT1/WND1 yang ditemukan; 356 CNT1, 2.164 USD1, 1.715 PRT1, dan 550 WND1 tanpa error parser.
- Pemetaan 803 `ui2dsys` records: 453 `AnimTagName` dan 350 `ProceduralShape`; field shape disimpan, tetapi efek renderer belum dikonfirmasi.
- Pemetaan 160 BND1/SCR1 common pane records serta 457 blok group yang dibatasi marker. Semua 1.552 group di dalam blok hanya mencakup section `grp1`; 523 `RootGroup` berada di luar blok.
- Enumerasi semua 52 jenis-section/ID properti animasi yang teramati; 0 properti unresolved. Memisahkan 15 FLEU dari 16.147 kurva dan mengikat semua target User ke key USD1 unik pada pane terkait.
- Memperbarui hitungan animasi lama. FLEU sebelumnya keliru dihitung sebagai track/curve key; angka kanonik sekarang 16.147 kurva + 15 record FLEU.
- Menghasilkan preview HUD sebagai alat inspeksi, bukan hasil render final.

## Urutan pekerjaan yang tersisa

1. **Cari bukti pemilihan part.** Telusuri resource lookup dari pendaftaran halaman/loader archive sampai pembentukan member BFLYT. Uji hipotesis suffix induk-anak terhadap fungsi native atau capture. Simpan kedua kandidat sampai call path menunjukkan urutan lookup secara eksplisit.
2. **Tutup controller dan dispatch UI.** Prioritaskan MainScreen/MainScreenSmartPhone, inventory/ring, dialog, MenuDevice, peta, dan keyboard. Hubungkan pendaftaran ke konstruktor/vtable, update loop, input, animasi, close/back, fokus kembali, dan teardown. Catat fungsi serta call path untuk tiap klaim.
3. **Pahami konsumen khusus.** Cari pemakai FLEU key/array, CNT1 action table, PRT1 usage flag, BND1/SCR1, dan ProceduralShape pada binary/native reference. Jika symbol/consumer tidak ada di dump ini, simpan raw field dan tandai bukti yang dibutuhkan; jangan memberi nama semantik hanya dari kemiripan nilai.
4. **Uji renderer.** Bandingkan source capture dan hasil render untuk viewport, origin, material, BNTX channel/swizzle, sampler/blend, font locale/fallback, WND1, clipping, shader pass, serta keyframe. Catat layar, state, frame, resolusi, dan perbedaan.
5. **Bangun konverter Godot setelah bukti cukup.** Pertahankan pane tree, sublayout instance, overrides, group ranges, material, font, track, dan data FLEU. Buat fixture per jenis pane dan satu layar lengkap; jangan menandai visual parity sebelum cocok pada capture game.

## Kondisi selesai dan blocker

Pemetaan statis format berhenti pada titik bahwa seluruh section yang teramati memiliki parsing terstruktur atau tersimpan sebagai raw/hash, semua properti animasi teramati diberi label, dan referensi resource ambigu ditulis bersama kandidat. Pemetaan perilaku belum selesai sampai call path/controller/runtime menjawab input, lifecycle, dan pemilihan resource. Perbandingan render memerlukan capture game yang sinkron; bila tidak tersedia, parity harus tetap dilabeli belum terbukti.

Belum ada blocker yang mengharuskan perubahan Godot atau push. Blocker aktual untuk klaim perilaku adalah tidak adanya trace/runtime yang membuktikan urutan loader dan state UI dari aset statis saja.

## Artefak lokal

Hasil terbaru ada di `acnh-re/output/ui_hud/`, khususnya `screen_catalog.json`, `group_structure.json`, `part_reference_ambiguities.json`, `section_semantics.json`, `animation_semantics.json`, `extended_user_data.json`, `resource_bindings.json`, `font_bindings.json`, `native_bindings.json`, dan `hud_mapping.json`. Generator: `acnh-re/tools/ui_hud_audit.py`. Laporan temuan: [UI_HUD_REVERSE_ENGINEERING.md](UI_HUD_REVERSE_ENGINEERING.md).
