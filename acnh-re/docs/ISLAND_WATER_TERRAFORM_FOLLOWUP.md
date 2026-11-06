# Lanjutan air pulau dan terraforming: region terrain

Catatan ini menutup satu irisan terbatas pada pemeriksaan dan pelepasan region
terrain. Hasilnya membantu memetakan prasyarat penempatan dan siklus hidup region;
belum melacak satu aksi Island Designer dari input pemain sampai perubahan peta
dan save.

## Fakta statis dari data

Preset `FieldPreset*_LandMaking.byml` membentuk grid 112×96 dengan record sel
14-byte. Audit 96 preset menemukan 84.759 sel yang memakai unit River pada
layer 0; tidak ada unit River pada layer 1. Kelima unit River dan tiga unit
Fall yang dipakai preset memiliki PBC. PBC terrain River membawa atribut ground
index 1, sementara model Fall yang dipakai menyimpan tinggi lokal −27 sampai
−12. PBC bagian pantai memuat atribut air payau (Brackish water) index 12 dan
Sea index 5. Angka atribut itu adalah indeks baris `ColGroundAttributeParam`,
bukan ID permukaan render.

Ini membuktikan payload geometri/ground statis tersedia dan dapat dicocokkan
dengan preset. PBC tidak membuktikan permukaan air, ombak, aliran, buih, atau
cara sambungan sungai dan air terjun dirender. Detail data tetap ada di
[`ISLAND_TEMPLATE_SELECTOR_NATIVE.md`](ISLAND_TEMPLATE_SELECTOR_NATIVE.md) dan
`output/ui_island/manifests_pbc_audit.json`.

## Pseudocode dan jalur pemanggil

`0x181fa0` memeriksa persegi panjang sel pada grid terrain. Forwarder
`0x164e90` memilih world di `owner+0x60`; helper ground `0x18ce50` memanggil
forwarder ini sebagai bagian dari predikat “tanah polos”. Forwarder kedua,
`0x163740`, memilih `owner+0x78` dan dipakai oleh beberapa pemeriksa terrain.
Jalur ini menghubungkan predicate region ke aturan placement terrain umum,
tetapi belum menghubungkannya ke aksi RiverMaker atau CliffMaker.

Pelepasan region mengikuti jalur terpisah: `0x168140 → 0x165240 → 0x181ae0`.
`0x165240` menghapus entry dari list, menurunkan count, lalu untuk kind 1–3
memilih world masing-masing di `owner+0x60/+0x68/+0x70` dan memutasi flag
rectangle. `0x168140` adalah wrapper yang mengambil owner dari singleton lalu
membersihkan byte enabled entry. Pseudocode tiga pemanggil wrapper
(`0x156970`, `0x15f4e0`, `0x160940`) menunjukkan iterasi list menurut kind.
Ini membuktikan jalur pembersihan region; nama aksi gameplay dan jalur pendaftaran
entry belum ditautkan.

Aturan predicate yang dibaca dari pseudocode dan dikonfirmasi pada fixture:

- Batas rectangle inklusif; sel di luar grid dilewati.
- Mode 0 mensyaratkan word bit 0 dan memilih overlay bila tersedia serta byte
  atribut pertamanya bukan sentinel 7. Mode 1 mensyaratkan bit 1 dan memakai
  record base.
- Rentang `record.float[0]` maksimum−minimum harus ≤
  `0.10999999940395355`. Predicate ini hanya membaca float pertama dari record
  52-byte.
- Mutator `0x181ae0` menulis bit 6 (`0x40`); pada jalur pelepasan, bit tersebut
  dibersihkan untuk rectangle entry yang diterima.

## Native yang dijalankan

Fungsi native asli dijalankan di Unicorn atas ELF dari source root dengan checksum
`5bf707c3dc5dac0ad9635af7d336ec580f81c3f7876d0f55400d1900e3415d74`; NSO
pasangan pada input lokal memiliki SHA-256
`f8d248109ff72999b4600ae3749f8c7397fb960f7ad3ab8dee3018ae9e14e900`. Dependensi
yang dipatok untuk eksekusi ini: Unicorn 2.1.4, pyelftools 0.33, Capstone 5.0.9.
Tidak ada dependensi native yang diganti stub. Harness merekonstruksi grid,
pointer world, rectangle, serta list region; game lengkap tidak dijalankan.

- `terrain_region_check_native.json`: 216 kasus pada `0x181fa0`; 130 true,
  86 false, tanpa mismatch.
- `terrain_region_mutation_native.json`: 164 kasus pada mutator, dua forwarder,
  wrapper mutasi, dan decoder navigasi; tanpa mismatch.
- `world_registry_release_native.json`: 126 kasus pada `0x165240` dan
  `0x168140`; tanpa mismatch. Fixture list menetapkan link offset `0x48`.
  Dua pemanggilan langsung atas entry yang sama menurunkan count dua kali,
  sedangkan wrapper membersihkan byte enabled dan menahan penghapusan kedua.
  Ini kontrak helper pada fixture, bukan bukti bug ketika game berjalan.

Output lengkap berada di
[`output/ui_island/water_terraform_followup/native/`](../output/ui_island/water_terraform_followup/native/);
`summary.json` menyimpan checksum executable, versi dependensi, tautan panggilan
statis dan jumlah kasus.

## Gap yang tersisa

Belum ada bukti native untuk pendaftaran region, pemanggilan helper ini dari
state RiverMaker/CliffMaker, validasi alat, mutasi record LandMaking,
preview/undo/commit, serialisasi perubahan ke save, atau refresh mesh dan
collision setelah edit. Loader preset 14-byte menuju record ground/PBC 52-byte
juga belum dijalankan hingga selesai. Jadi hasil ini menetapkan aturan region yang
dipakai predicate placement umum serta pelepasan entry; ia belum menetapkan
perilaku lengkap sungai, air terjun, pantai, maupun Island Designer.
