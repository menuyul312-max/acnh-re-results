# Reverse engineering UI dan HUD ACNH

Pemetaan ini memakai dump RomFS dan ExeFS ACNH 1.0.0 yang tersedia di mesin lokal. Cakupan ini khusus aset, struktur, binding, dan referensi native UI/HUD. Proyek Godot hanya dibaca; tidak ada file Godot yang diubah dan tidak ada perubahan yang di-push ke GitHub.

## Kesimpulan

Struktur statis utama UI sekarang terhubung: 523 BFLYT, pane dan sublayout, group, data kontrol, userData, material, tekstur, font, target animasi, serta 15 animasi extended user data. Parser mengidentifikasi seluruh ID properti animasi yang teramati dan tidak menyisakan error pada section yang diaudit. Struktur `grs1/gre1` dan properti BND1/SCR1 juga sudah dipetakan. Analisis pseudocode native tambahan kini menegaskan jalur pemintaan resource `.bflyt`, tabel aksi fokus/key/touch, beberapa updater HUD, serta pembacaan userData efek oleh renderer.

Ini memberi dasar yang cukup kuat untuk membuat importer dan scene UI Godot. Ini belum membuktikan kapan setiap layar tampil, bagaimana input perangkat dipetakan ke kontrol, archive mana yang menang pada 35 referensi part ganda, atau apakah hasil render sama dengan game. Belum ada konversi UI di proyek Godot maupun capture pembanding.

## Pemetaan aset dan struktur

- RomFS `Layout/` berisi 524 arsip: 519 `.zs` dan 5 `.szs`. Sebanyak 523 member BFLYT terindeks; arsip tambahan MultiFilter berisi enam `.baglmf`, bukan layar yang belum terbaca. Katalog menyimpan nama, member, ukuran desain, pane, animasi, dan hash layout.
- Katalog memuat 10.882 pane. MainScreen berukuran desain 1920×1080 dan memiliki 32 pane, termasuk 29 slot PRT1. Slot bernama mencakup delapan `L_ItemBalloon`, dua belas `L_MsgBalloon`, `LClock`, `LTimerBell`, `LTimer`, `LRoomGuide`, `LTimerCounterSet`, `LRoadUseBtn`, `LStickBalloon`, `LMealEf`, dan `LShareGuide`. Nama serta posisi slot tidak membuktikan state tampilnya.
- MainScreenSmartPhone memiliki 24 pane dan lima grup animasi: Loop (60 frame), In (8), Out (6), State (2), dan Flash (36). Target, track, key, dan pane statis sudah terindeks; controller, pemicu, dan jadwal update runtime belum diketahui.
- Ada 2.075 record `grp1`. Sebanyak 457 pasang `grs1`/`gre1` berukuran 8 byte membatasi 1.552 record `grp1`; seluruh isi di antara marker adalah `grp1`. Sebanyak 523 record lain berada di luar batas itu dan semuanya bernama `RootGroup`. Tidak ada marker yang tidak berpasangan atau error struktur. Hubungan ini dicatat sebagai batas grup, tanpa menyimpulkan perilaku visibilitas runtime.
- Seluruh 356 CNT1 terbaca: 711 referensi pane beserta nama aksi, 2.049 nama animasi, dan 51 nama animasi unik. Nama seperti `Select`, `Decide`, `Cancel`, `FocusKey`, dan `FocusTouch` memberi label state/aksi yang tersimpan; callback dan mapping tombol masih perlu native/runtime.
- Seluruh 2.164 USD1 dan 3.518 entri terbaca: 978 string, 852 int32, dan 885 float32. Sebanyak 803 record `ui2dsys` dipetakan ke 453 `AnimTagName` dan 350 `ProceduralShape`. Ada 2.093 deklarasi nama tag dengan 375 nama unik; dua dari 2.095 animasi memiliki nama tag kosong. Field ProceduralShape disimpan beserta flag, warna, radius, gradation, dan parameter shadow; efek renderer-nya belum diuji.
- Seluruh 1.715 PRT1 terbaca, termasuk 4.026 record properti, 653 override pane, 254 blok userData, dan 2.257 blok `panelInfo`. Tidak ada offset userData yang gagal dipahami secara struktural. Makna flag penggunaan belum dikonfirmasi ke renderer.
- Seluruh 550 WND1 mencatat inflation, ukuran frame, warna, material, UV, frame, dan mode flip. Distribusi frame: 446 satu frame, 51 dua frame, dan 53 empat frame. Ada 2.846 PIC1; setiap pane menyatakan quad standar dan memiliki satu sampai tiga layer UV. Data mendukung konversi nine-patch, tetapi aturan render perlu dibandingkan dengan game.
- Sebanyak 158 BND1 dan 2 SCR1 sudah dibaca sebagai common pane block: ukuran section 84 byte, terdiri dari header section 8 byte dan blok pane 76 byte, tanpa byte extension pada seluruh sampel. Referensi format menamai keduanya BoundingPane dan ScissorPane. Efek hit-test/bounds dan clipping dalam game belum tervalidasi.
- Seluruh 6.076 material terbaca tanpa byte sisa atau bit flag tak dikenal. Ada 6.475 tautan material-ke-tekstur dan semuanya memiliki kandidat BNTX dalam arsip yang sama; 2.795 nama tekstur cocok unik ke BNTX; 3.727 pane merujuk material. Sebanyak 132 material memiliki nama shader GLSL yang cocok unik. Field integer `0x08040200` muncul pada semua material, tetapi arti semantik dan pilihan BNSH/pass runtime belum terbukti.
- Seluruh 276 referensi font cocok dengan delapan alias FontInfo: tiga BFFNT dan lima FCPX. Locale aktif, fallback glyph, metrik, dan rasterisasi runtime belum diverifikasi.

## Animasi dan userData

Ada 2.095 BFLAN dengan 16.147 track kurva dan 91.933 keyframe. Hitungan terdahulu 16.162 track dan 92.038 key keliru karena 15 record FLEU dibaca sebagai kurva biasa; FLEU sekarang dipisahkan sesuai struktur khususnya. Jadi jumlah payload animasi yang dipetakan adalah 16.147 kurva ditambah 15 record FLEU.

Semua 52 kombinasi jenis-section dan ID properti yang teramati punya label dari referensi format; jumlah ID properti unresolved adalah nol. Contohnya FLCT 0/1 adalah `EvalTimeOffset`/`EvalTimeWidth`, FLIM 0–2 adalah rotate/scale-U/scale-V, dan ID FLPS yang dipakai ACNH terpetakan sebagai `ExpLeftTop` dan `RadiusLeftTop`. Kurva Step (2.440) dan Hermite (13.707) serta encoding key-nya tersimpan.

Target kurva Pane (6.729) dan Material (1.787) cocok unik dengan sumber pada arsip yang sama. Semua 15 target User terhubung secara statis ke pane unik dan key userData USD1 bernama sama. Parser FLEU menyimpan seluruh 15 record dari enam arsip, raw header, key, hash, dan tiga array float per record (315 nilai; jumlah `base_count` 105). Arti runtime ketiga array serta pemanggil yang menerapkannya belum dibuktikan.

## Referensi part ganda

Ada 35 pemakaian dengan dua kandidat BFLYT bernama sama, mencakup tiga nama part. Setiap pasangan mempunyai hash berbeda. Pada semua 35 pemakaian, tepat satu kandidat memiliki ekstensi arsip yang sama dengan arsip host (`.zs` atau `.szs`); ini korelasi 35/35 yang layak dipakai sebagai prioritas pencarian. Namun, itu belum membuktikan aturan loader. Ukuran desain root semua kandidat sama-sama 1920×1080 sehingga tidak membedakan kandidat. Kedua kandidat tetap disimpan dan statusnya tetap unresolved sampai urutan lookup native/runtime ditemukan.

## Bukti native dan batas perilaku

ExeFS `main` mencatat 31 pendaftaran halaman dan tiga helper registrasi. Korelasi yang sudah ada mencakup prompt item/MainScreen (`0x1214110`), ConfirmedFruit (`0x132e050`), entri anak MenuMapFull (`0x12330c0`), keluarga dialog umum/telepon (`0x11e6d70`), serta keyboard chat (`0x151ec70`).

Rantai resource native yang kini dipetakan: startup `0x98b70` memanggil `0x1541580`, yang membaca daftar nama dan membentuk `Layout/%s.Nin_NX_NVN.zs`. Manager layout (`0x14c3cf0` → `0x14c49e0` → `0x14bfe60` → `0x14bebd0`) membuka arsip `.zs`, meminta member `%s.arc`, lalu mendaftarkan accessor. Loader layout meminta `%s.bflyt` melalui accessor (`0x14c77a0` → `0x191c8d0`). Jalur sublayout PRT1 (`0x1cf1230` → `0x1cf0de0` → `0x1ceb3e0`) membangun key `EuiAllocator:<locale><layout-name>` dan meminta child `.bflyt`. Ini membuktikan format permintaan dan sebuah jalur archive `.zs`, tetapi belum memperlihatkan aturan yang memilih di antara kandidat `.zs`/`.szs` untuk setiap part ganda.

Untuk MainScreen, `0x1315ac0` membandingkan tanggal/waktu dan memperbarui sejumlah text resource yang mencakup `STR_Week`; `0x1315f90` menulis empat text resource indexed lain; `0x14797c0` menyegarkan sebelas entri `STR_KeyIcon`; dan `0x1347c50` mengikat child `/L_Clock_00`. `0x125e3e0` membaca `MainUiClockEnable` dan menjalankan helper update clock/state untuk `MenuDevice`. Nama pane pada sebagian data indexed belum berhasil diurai, dan ini belum menjelaskan controller `MainScreenSmartPhone`.

Helper kontrol `0x1485c20` menyimpan 13 nama aksi berurutan: `FocusKey`, `FocusTouch`, `UnFocusKey`, `UnFocusTouch`, `DecideKey`, `DecideTouch`, `Invalid`, `Check`, `Uncheck`, `RepeatKey`, `RepeatTouch`, `Active`, dan `Inactive`. `0x14845a0` memilih aksi dari indeks dan meneruskannya ke pohon aksi/animasi (`0x14855f0` dan `0x14bd...`). `0x14885b0` mencari pane terkait cursor dengan fallback `P_BtnFocusKey`, `C_Cursor`, dan `B_Hit`. Ini menunjukkan sistem animasi/state untuk kontrol, tetapi belum menghubungkan indeks tersebut ke input pad/touch atau seluruh alur fokus kembali dan modal.

Keluarga dialog umum juga memiliki controller nyata: `0x11e6d70` memilih layout `CmnDialogSmartPhone` atau `CmnDialog`, lalu membuat `CommonDialogPage` dan `CommonDialogBGPage`. `0x11e8960` memperbarui beberapa state dialog, sedangkan `0x11e9210` menyegarkan `STR_KeyIcon`/`KeyGuide`; `0x11e96a0` mengakses delapan slot anak dan state animasinya. Ini memetakan komponen dialog, tetapi belum membuktikan modal stack global, urutan open/close/back, kembalinya fokus, atau teardown.

Consumer userData renderer juga lebih jelas. `0x1930000` mencari record berdasarkan nama. Rangkaian `0x14ca2b0` dan helper-nya membaca field border, color overlay, gradation empat warna, drop shadow, inner shadow, dan gradation mask menjadi parameter shape. Saat menyiapkan layout, `0x1cf0fa0` menelusuri pane dan memanggil handler untuk `EffectLinkOn`, `AdjustToTextOn`, `CaptureUseName/Index`, serta `DynamicCaptureUseName/Index`. Native juga membuat tipe `ScissorPane` (`0x14c89c0`) dan `0x14c8d00` menyimpan enable byte beserta empat nilai 32-bit pada objek itu; jalur ke perintah NVN final dan aturan koordinat/clip bersarang belum tertaut. Sistem `UISysBoundingUseCursor` membuat binding cursor, sementara dispatch `ui2dsys` membedakan 15 keluarga seperti `LpSelector`, `LpScrollBar`, `UISysBounding`, dan `UISysScrollSign`. `UISysBounding` bukan bukti langsung perilaku BND1. Beberapa key native tumpang tindih dengan FLEU, namun updater yang menerapkan tiga array FLEU pada userData dan timing keyframe belum tersambung.

Belum ada xref native bernama persis untuk MainScreenSmartPhone pada kumpulan 62 kandidat nama layout yang diperiksa. Arti flag registrasi, open/close/back, routing key/touch, modal stack, fokus kembali, teardown, dan jadwal update HUD memerlukan trace call path yang lebih lengkap atau observasi runtime. Nama CNT1 maupun animasi tidak cukup untuk membuktikan aksi yang menjalankannya.

## Yang masih belum terbukti

1. **Pemilihan part:** korelasi suffix cocok pada 35/35 contoh dan call path meminta child lewat key resource plus nama `.bflyt`, tetapi belum ada bukti archive lookup memilih kandidat `.zs` atau `.szs` tertentu.
2. **Dispatch UI:** tabel aksi fokus/key/touch dan jalur aksi kontrol ditemukan, tetapi pemetaan input perangkat, callback CNT1, state/lifecycle layar, controller smartphone, dialog/modal, close/back, restore focus, dan teardown belum ditelusuri sampai lengkap.
3. **Animasi khusus:** native membaca banyak field userData efek, tetapi updater FLEU, semantik ketiga array, timing, dan consumer `C_Id` belum terbukti.
4. **Renderer:** setter `ScissorPane` dan cursor-bound helper ditemukan, tetapi BND1 hit-test, jalur setter ke NVN scissor, origin/skala viewport, ProceduralShape parity, BNSH/shader pass, sampler/blend, warna, fallback font/locale, clipping bersarang, serta hasil pixel belum dibandingkan dengan capture game.
5. **Konversi dan paritas Godot:** scene/importer UI belum dibuat. Preview lokal hanya alat inspeksi; tekstur BNTX asli ditampilkan dengan shader dan glyph ZL sederhana, bukan render ACNH.

## Catatan konversi ke Godot untuk hasil akurat

Belum ada implementasi konversi yang diklaim. Gunakan indeks dan dump statis ini sebagai data sumber, lalu validasi per layar/state/frame.

1. Pertahankan pane tree, urutan gambar, nama, parent, transform, pivot/origin, visibility, alpha, skala, ukuran desain, material index, UV, warna vertex, teks, dan font. Jangan meratakan layout menjadi satu gambar.
2. Jadikan setiap PRT1 instance sublayout tersendiri dan terapkan magnification, property override, embedded userData, `panelInfo`, dan grup pane pada instance yang tepat. Untuk 35 referensi ganda, simpan kandidat sampai bukti loader tersedia.
3. Pertahankan `RootGroup` dan rentang grup yang dibatasi `grs1/gre1`; jangan melebur group pane karena nama mirip. Simpan CNT1 pane/action dan daftar animasi untuk nanti dihubungkan ke kontrol runtime. Simpan pula nama tipe `ui2dsys` dan tabel aksi kontrol (`FocusKey`, `FocusTouch`, `UnFocusKey`, `UnFocusTouch`, `DecideKey`, `DecideTouch`, `Invalid`, `Check`, `Uncheck`, `RepeatKey`, `RepeatTouch`, `Active`, `Inactive`) sebagai data dispatch; jangan menganggapnya pemetaan tombol fisik sebelum input controller terbukti.
4. Simpan koordinat sumber dan ukuran desain 1920×1080 tanpa transformasi lossy. Jika viewport Godot 1280×720 dipakai, skala seragam 2/3 adalah titik awal. Rumus `x = 960 + x_bflyt`, `y = 540 - y_bflyt` hanya hipotesis jika origin pusat dan sumbu Y sumber ke atas; pastikan dengan capture.
5. Implementasikan PIC1 sebagai quad dengan seluruh UV layer dan warna vertex. Implementasikan WND1 sebagai nine-patch yang menghormati inflation, border, frame, UV, flip, material, dan warna. Decode channel/swizzle/alpha/mipmap BNTX dan samakan sampler/blend/shader; nama GLSL bukan bukti shader pass yang dipilih saat runtime.
6. Untuk txt1, gunakan font BFFNT/FCPX yang terikat lewat FontInfo dan pertahankan metrik, alignment, spacing, wrapping, locale, glyph fallback, dan glyph private-use. Jangan mengubah teks dinamis menjadi string final sebelum substitusi dan localization diketahui.
7. Konversi 16.147 kurva ke track Godot atau pemutar custom dengan Step/Hermite, nilai, slope, target, dan frame tetap. Simpan 15 FLEU sebagai track data kustom berisi tiga array float dan nama key; jangan anggap array-nya key/value biasa sebelum runtime consumer dipahami. Pemanggilan/timing harus datang dari state machine/controller yang dibuktikan.
8. Tambahkan node khusus untuk `ProceduralShape`, BND1, dan SCR1 sambil mempertahankan field mentah serta transformnya. Native membaca userData `S_*` untuk border, overlay, gradation, shadow, dan gradation mask; pertahankan field-field tersebut dan indeks warna sampai shader/warna cocok. `ScissorPane` menyimpan enable byte dan empat nilai mentah, sementara hubungan ke clipping GPU belum terbukti. Implementasikan batas/cursor `UISysBounding` sebagai sistem terpisah dari section BND1. Bandingkan render pada resolusi sumber dan viewport target sebelum menandai hasil akurat.

Pratinjau [HUD_layout_preview.png](../work/ui_hud_preview/HUD_layout_preview.png) memakai tekstur BNTX hasil decode dan anchor MainScreen, tetapi merangkum efek shader/font dan memakai teks “ZL” sebagai pengganti glyph. Gunakan hanya untuk inspeksi komposisi.

## Artefak

- [Katalog layout dan animasi](../output/ui_hud/screen_catalog.json)
- [Pemetaan MainScreen dan smartphone](../output/ui_hud/hud_mapping.json)
- [Pendaftaran dan korelasi native](../output/ui_hud/native_bindings.json)
- [Rantai resource, HUD, fokus, dan consumer userData native](../output/ui_hud/native_ui_traces.json)
- [Struktur section, userData, CNT1, WND1, BND1, dan SCR1](../output/ui_hud/section_semantics.json)
- [Batas group `grs1/gre1` dan `grp1`](../output/ui_hud/group_structure.json)
- [35 referensi part ganda dan kandidat hash](../output/ui_hud/part_reference_ambiguities.json)
- [Binding material, tekstur, dan shader](../output/ui_hud/resource_bindings.json)
- [Target, track, key, tag, dan peta properti animasi](../output/ui_hud/animation_semantics.json)
- [15 record FLEU beserta binding userData](../output/ui_hud/extended_user_data.json)
- [Binding font](../output/ui_hud/font_bindings.json)
- [Generator audit](../tools/ui_hud_audit.py)
- [Rencana sisa kerja](UI_HUD_RE_PLAN.md)

Jalankan ulang dari root repo dengan `python3 acnh-re/tools/ui_hud_audit.py`; lokasi RomFS dapat diatur dengan `ACNH_ROMFS`. Semua output dan preview tetap lokal.

Referensi format: [nnbfl BFLYT/BFLAN hexpat](https://github.com/crackheadakira/nnbfl/blob/af30eaf9a92324bfe7ecc2af8df9c8dbf8848a79/hexpats/bflyt_bflan_bffnt.900.hexpat), [nnbfl target animation properties](https://github.com/crackheadakira/nnbfl/blob/af30eaf9a92324bfe7ecc2af8df9c8dbf8848a79/nnbfl/src/bflan/targets.rs), [nnbfl FLEU structure](https://github.com/crackheadakira/nnbfl/blob/af30eaf9a92324bfe7ecc2af8df9c8dbf8848a79/nnbfl/src/bflan/anim_info.rs), [LayoutExporterU BFLAN property names](https://github.com/aboood40091/LayoutExporterU/blob/8c644cfad606ead47e6ce9eae2d315a5e70afe61/bflan.py), dan [nnbfl pane definitions](https://github.com/crackheadakira/nnbfl/blob/af30eaf9a92324bfe7ecc2af8df9c8dbf8848a79/nnbfl/src/bflyt/pane.rs). Label format publik dicocokkan dengan payload ACNH lokal; perilaku runtime tidak disimpulkan dari referensi format.
