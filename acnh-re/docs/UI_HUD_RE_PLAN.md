# Rencana sisa reverse engineering UI/HUD

Status diperbarui 6 November 2026. Fokus hanya UI/HUD ACNH 1.0.0. Analisis RomFS/ExeFS yang tersedia tetap lokal; Godot hanya dibaca dan tidak ada push.

## Status

| Area | Status | Bukti / batas berikutnya |
|---|---|---|
| Inventaris layout | Selesai untuk dump yang tersedia | 524 arsip Layout direkonsiliasi dengan 523 member BFLYT dan 10.882 pane. Tidak ada klaim bahwa ini memuat semua perilaku/game state. |
| HUD utama dan smartphone | Struktur terpetakan; controller layout belum terikat | MainScreen 32 pane/29 slot sublayout; MainScreenSmartPhone 24 pane/5 animasi. Factory terpisah `SmartPhoneIconPage` ditemukan, tetapi hubungannya dengan BFLYT ini belum terbukti. Pemicu dan state bersamaan masih terbuka. |
| Section BFLYT | Struktur terpetakan, consumer runtime sebagian | CNT1, USD1/ui2dsys, PRT1, WND1, BND1/SCR1, serta rentang group `grs1/gre1` tervalidasi. Jalur viewport menghitung rectangle dan membuat/memperbarui ScissorPane; pemanggilan NVN akhir, aturan clip bersarang, dan BND1 hit-test belum terbukti. |
| Resource/material/font | Binding statis selesai | 6.076 material, 6.475 texture links, 276 referensi font terikat. Pilihan BNSH/pass, sampler/blend runtime, locale/fallback, dan pixel parity masih terbuka. |
| Part ganda | Jalur permintaan ditemukan, pilihan archive belum terpecahkan | Native meminta child sebagai resource bernama `EuiAllocator:<locale><layout-name>` dan meminta member `.bflyt`; jalur manager lain membuka `Layout/%s.Nin_NX_NVN.zs` lalu `%s.arc`. Belum ada cabang yang memilih antara kandidat `.zs` dan `.szs` pada 35 referensi. |
| Animasi | Format dan sebagian pemicu terpetakan | 16.147 kurva/91.933 key, semua 52 kombinasi section/property dikenal; 15 FLEU terurai dan tertaut ke userData pane unik. Native memiliki tabel aksi kontrol dan jalur aksi animasi, tetapi timing dan updater FLEU belum terbukti. |
| Native UI | Jalur dispatch komponen dan state kontrol bertambah; lifecycle belum selesai | Terpetakan update tanggal/HUD, 11 icon key MainScreen, child clock, tabel 13 aksi kontrol, state machine 18-state/29 trigger, kecocokan nama pada 91 `LpUniteButton` CNT1, dua tahap dispatch tipe UI beserta slot vtable, factory `AppUniteBtnCtrl`/`UniteBtnCtrl`, lima jenis kontrol bernama, tag UserButton, dan emitter 8 jenis aksi. Target virtual, input perangkat, controller smartphone, modal stack, restore focus, dan teardown belum lengkap. |
| Konversi Godot | Belum dilakukan | Ada resep konversi dan preview inspeksi. Belum ada importer/scene UI atau capture pembanding dengan game. |

## Temuan yang sudah ditutup secara statis

- Rekonsiliasi seluruh archive/member BFLYT dan indeks layar, pane, group, part reference, material, tekstur, font, serta animasi.
- Decode seluruh section CNT1/USD1/PRT1/WND1 yang ditemukan; 356 CNT1, 2.164 USD1, 1.715 PRT1, dan 550 WND1 tanpa error parser.
- Pemetaan 803 `ui2dsys` records: 453 `AnimTagName` dan 350 `ProceduralShape`; field shape disimpan, tetapi efek renderer belum dikonfirmasi.
- Pemetaan 160 BND1/SCR1 common pane records serta 457 blok group yang dibatasi marker. Semua 1.552 group di dalam blok hanya mencakup section `grp1`; 523 `RootGroup` berada di luar blok.
- Enumerasi semua 52 jenis-section/ID properti animasi yang teramati; 0 properti unresolved. Memisahkan 15 FLEU dari 16.147 kurva dan mengikat semua target User ke key USD1 unik pada pane terkait.
- Memperbarui hitungan animasi lama. FLEU sebelumnya keliru dihitung sebagai track/curve key; angka kanonik sekarang 16.147 kurva + 15 record FLEU.
- Memetakan enum state kontrol `0..17`, 29 trigger transisi key/touch/inverse/validity pada `0x1dd0c20`, konfigurasi `*Cursor`/`Draggable`, dan binding tag `UB_Select`, `UB_Unselect`, `UB_Decide`, `UB_DispValid`. Ini bukti state machine kontrol statis, bukan bukti routing input platform.
- Menghubungkan emitter native ke `DecideKey`, `Invalid`, `Check`/`Uncheck`, `RepeatKey`/`RepeatTouch`, dan `Active`/`Inactive`; `FocusKey`, `FocusTouch`, UnFocus*, serta `DecideTouch` masih belum punya produsen lengkap.
- Memetakan tipe kontrol native `ButtonNormal`, `ButtonCheck`, `ButtonRepeat`, `ButtonFocusActive`, dan `ButtonSelBox` ke mode ID `1..5`, serta resolusi `Inherit` melalui rekaman induk.
- Mengorelasikan state machine tersebut dengan CNT1: 91 `LpUniteButton` memiliki 18 nama animasi yang selaras dengan state/trigger native; profil `ButtonNormal` (12), `ButtonCheck` (3), dan `ButtonRepeat` (4) cocok dengan action table dan emitter bertipe.
- Memetakan dua tahap dispatch tipe komponen UI: `0x1db2140` memilih slot setup per tipe (termasuk `LpUniteButton` pada `+0x18`), lalu `0x1672890` memilih slot follow-up (`LpUniteButton` pada `+0xb0`). Tiga builder memanggil keduanya berurutan. Factory `AppUniteBtnCtrl` dan `UniteBtnCtrl` juga terhubung ke setup state machine bersama; target virtual dan binding record spesifik masih terbuka.
- Menghasilkan preview HUD sebagai alat inspeksi, bukan hasil render final.

## Urutan pekerjaan yang tersisa

1. **Tutup pemilihan part bila bukti tersedia.** Call path native kini menegaskan pembentukan key resource child dan permintaan member `.bflyt`, tetapi tidak memperlihatkan archive precedence. Langkah berikutnya memerlukan pencarian allocator/resource index lebih dalam atau trace runtime; simpan dua kandidat hingga hasil itu diperoleh.
2. **Lanjutkan controller dan dispatch UI.** Type-to-slot dispatch dan factory kontrol kini tercatat, tetapi target virtual belum dipecahkan. Berikutnya hubungkan event platform ke aksi kontrol/CNT1, lalu ikuti MainScreenSmartPhone, open/close/back, modal push/pop, restore focus, dan teardown.
3. **Tutup konsumen khusus.** Native membaca userData untuk border, color overlay, gradation, drop/inner shadow, gradation mask, effect link, text adjustment, serta capture statis/dinamis. Berikutnya hubungkan pembaruan FLEU ke field itu, petakan `C_Id`, CNT1 callbacks dan flag PRT1, lalu uji BND1/SCR1/ProceduralShape terhadap renderer.
4. **Uji renderer dengan referensi sinkron.** Bandingkan source capture dan hasil render untuk viewport, origin, material, BNTX channel/swizzle, sampler/blend, font locale/fallback, WND1, clipping, shader pass, dan keyframe. Catat layar, state, frame, resolusi, dan perbedaan. Dump aset saja tidak cukup untuk memastikan pixel parity.
5. **Bangun konverter Godot setelah bukti cukup.** Pertahankan pane tree, sublayout instance, overrides, group ranges, material, font, track, dan data FLEU. Buat fixture per jenis pane dan satu layar lengkap; jangan menandai visual parity sebelum cocok pada capture game.

## Kondisi selesai dan blocker

Pemetaan statis format berhenti pada titik bahwa seluruh section yang teramati memiliki parsing terstruktur atau tersimpan sebagai raw/hash, semua properti animasi teramati diberi label, dan referensi resource ambigu ditulis bersama kandidat. Pemetaan perilaku belum selesai sampai call path/controller/runtime menjawab input, lifecycle, pembaruan FLEU, dan pemilihan resource. Perbandingan render memerlukan capture game yang sinkron; bila tidak tersedia, parity harus tetap dilabeli belum terbukti. Bukti tambahan dan rantai fungsi native tercatat di `acnh-re/output/ui_hud/native_ui_traces.json`.

Belum ada blocker yang mengharuskan perubahan Godot atau push. Blocker aktual untuk klaim perilaku adalah tidak adanya trace/runtime yang membuktikan urutan loader dan state UI dari aset statis saja.

## Artefak lokal

Hasil terbaru ada di `acnh-re/output/ui_hud/`, khususnya `screen_catalog.json`, `group_structure.json`, `part_reference_ambiguities.json`, `section_semantics.json`, `animation_semantics.json`, `extended_user_data.json`, `resource_bindings.json`, `font_bindings.json`, `native_bindings.json`, `native_ui_traces.json`, dan `hud_mapping.json`. Generator: `acnh-re/tools/ui_hud_audit.py`. Laporan temuan: [UI_HUD_REVERSE_ENGINEERING.md](UI_HUD_REVERSE_ENGINEERING.md).
