# Audit komponen UI dan penataan pulau — 3 November 2026

Fokus terbaru adalah UI dan penataan pulau. Hasil tahap ini memperluas pembacaan struktur dan hubungan referensi; **belum membuktikan seluruh UI dan sistem penataan pulau selesai di-reverse**. Model/sound menggunakan katalog. Godot dan sumber asli tidak diubah.

## Temuan yang sudah dapat diperiksa

| Komponen | Hasil | Batas bukti |
|---|---|---|
| Layout UI | 523 layout, 10.882 pane; parent, transform, ukuran, teks, indeks material/font, grup dan section sumber | Parser struktur, belum kesetaraan hasil render |
| Pane | 4.730 pan1, 1.715 prt1, 2.846 pic1, 881 txt1, 550 wnd1, 158 bnd1, 2 scr1 | wnd1/bnd1/scr1 mempertahankan payload tambahan yang belum ditafsirkan |
| Subkomponen | 1.680 dari 1.715 referensi memiliki satu kandidat; 35 memiliki dua kandidat dengan isi berbeda | Kedua kandidat disimpan; prioritas pemuatan belum terbukti |
| Animasi UI | Seluruh 2.095 FLAN: 16.162 track, 92.038 keyframe | Offset/encoding terbaca; property ID, interpolasi engine, trigger dan lifecycle belum diuji runtime |
| Target animasi | 8.531 content target memiliki kecocokan nama pane/material dalam container yang sama | Kecocokan nama statis, bukan bukti handler |
| Kandidat kode UI | 62 nama layout cocok persis dengan string yang dirujuk fungsi native | Alamat fungsi kandidat, belum penetapan controller/input handler |
| Referensi tekstur/font | 2.795/2.795 referensi tekstur memiliki kandidat metadata; 14/276 referensi font cocok nama resource | Nama resource statis, belum binding renderer; 262 font belum terhubung dengan pencarian nama persis |
| Pantai luar | 36 template × 22 slot = 792 slot; seluruh slot cocok dengan kandidat dari 136 part berdasarkan hash PartsKind | Belum pemilihan varian, transform, seam atau collision |
| Preset pulau | 96 baris FieldMainFieldParam terhubung ke LandMaking, EventPlaza, StructurePreset dan ItemPreset | Filename-stem join; urutan loader dan penerapan runtime belum terbukti |
| Terrain | Referensi skema 14-byte, dua layer, variasi, rotasi dan tinggi yang sudah diteliti sebelumnya | Bukan tambahan bukti native pada tahap ini |

Parser animasi sebelumnya hanya menyediakan ringkasan header. Tahap ini membaca pat1/pai1, nama target, tipe target numerik, daftar info/track serta keyframe dengan encoding f32/f32/f32 dan f32/u16/u16. Lima belas content target tipe 2 memakai header tambahan dengan offset tabel dan nama target tambahan; bentuk ini kini ditangani. ID numerik tetap dipertahankan agar arti properti tidak ditebak.

Pemindaian section juga mencatat **356 cnt1** dan **2.164 usd1**. Keduanya belum ditafsirkan semantiknya. Material yang terbaca masih parsial; menghitung pane dan memvalidasi indeks tidak membuktikan shader, clipping, blend atau hasil gambar.

## Hubungan data pulau

`FieldMainFieldParam.FieldData` mengarah berdasarkan nama dasar ke dua sumber: `<FieldData>_LandMaking.byml` dan `<FieldData>_EventPlaza.byml`. StructureData dan ItemData cocok dengan masing-masing sumber BYML. Semua 96 bundel memiliki keempat sumber tersebut.

Kolom Label berisi nama VillagePreset; tidak ada kecocokan nama file persis pada katalog BYML ini. **Hal tersebut tidak membuktikan ada file yang hilang:** peran Label sebagai nama file belum terbukti. Demikian juga, angka OutsideTemplateKind tidak dipaksakan menjadi UniqueID FieldOutsideTemplate; jalur pemilihan template masih terbuka.

Setiap slot pantai menyimpan PartsKind. Join menggunakan hash enum yang sama dengan FieldOutsideParts, mempertahankan seluruh kandidat, ReefType, UniqueID dan ModelName. Ini memungkinkan penelusuran pantai, batu utara, muara sungai, tanjung, dermaga dan bandara tanpa memilih varian secara sembarang. Koordinat dunia, ukuran part dan aturan menyambung part belum diturunkan di sini.

StructurePreset berisi daftar site UnitX/UnitZ; daftar koordinat ini belum mengidentifikasi jenis bangunan. ItemPreset menyimpan HalfUnitX/HalfUnitZ, layer dan mItemNameParam.u64; nilai u64 tetap packed dan tidak dianggap ID item langsung. Satuan koordinat asli dipertahankan. Referensi model River/Fall bukan bukti geometri air, arah arus, foam, kedalaman atau collision.

## Yang belum terbukti

- UI: cnt1/usd1, properti override prt1, seluruh parameter material/window, localization substitution, target-property animation, focus/controller/gamepad, callback tombol, modal, lifecycle dan hubungan aksi dengan gameplay/save.
- Pulau: pemilihan template/varian pantai, transform part dan sambungan; loader preset menuju world runtime; identitas site bangunan; footprint dan validasi penempatan; preview/konfirmasi/pembatalan; transaksi edit terrain dan penyimpanan.
- Air: pembentukan geometri sungai/air terjun/laut, batas air dan pantai, visual arus/foam/ripple, hubungan navigasi/collision serta perubahan sesudah terraforming.

Pemeriksaan ground, flag wilayah dan navigasi dari tahap sebelumnya tetap berlaku hanya pada scope yang tercatat dalam laporan native masing-masing. Tahap ini menambah **0 kasus native**; total sebelumnya 1.136.083 tidak dinaikkan oleh hitungan file, track atau keyframe.

## Berkas dan reproduksi

- [Ringkasan](../output/ui_island/summary.json), [cakupan per komponen](../output/ui_island/component_coverage.json), [verifikasi](../output/ui_island/verification.json).
- [Seluruh layout/pane dan relasi](../output/ui_island/layouts.json).
- [Indeks animasi](../output/ui_island/animations.json); setiap entry menunjuk JSON rinci di `output/ui_island/animations/` dengan offset track dan keyframe.
- [Template/part dan bundel preset pulau](../output/ui_island/island.json).
- [Kandidat fungsi UI](../output/ui_island/native_candidates.json), [anggota layout lainnya](../output/ui_island/other_layout_members.json).

Jalankan dari akar proyek dengan sumber pengguna tersedia di lokasi yang dikonfigurasi dalam `audit_additional_romfs.py`:

```sh
python tools/ui_island_audit.py
python tools/verify_ui_island.py
```

Verifikasi memeriksa census sumber lengkap, SHA256 terhadap inventory sebelumnya, batas section, parent pane, indeks material/font/texture dan grup, join pantai/preset, serta merekonstruksi byte **seluruh 92.038 keyframe** dan membandingkannya dengan sumber. Pemeriksaan ini menguji kesetiaan struktur, bukan perilaku game. Data asli tidak disertakan dalam pembaruan GitHub.
