# Terrain canonical field-grid and collision join follow-up, ACNH 1.0.0

Tanggal: 7 November 2026. Lanjutan ini mengikuti loader preset LandMaking 112×96,
query ground, scratch editor, mutator grid 52-byte, overlay collision, dan jalur
save yang sudah terindeks. Temuan baru mengikat satu handler world-context ke
writer base-grid; hubungan dari loader/editor LandMaking ke writer tersebut dan
ke serializer save tetap **OPEN**.

## Temuan

Format sumber LandMaking tetap kisi 112×96 row-major dengan stride 14 byte.
`0x558f40`, yang dipanggil oleh `0x528bf0` (dan oleh pemulih UID preset
`0x558ef0`), memindahkan dua komponen layer dan byte tinggi ke cell accessor
tujuan. Ini bukan ekspansi ke record ground/collision 52-byte. Semua 96 BYML
yang tercatat dalam index tersedia di sumber lokal; SHA-256 setiap file
diverifikasi terhadap bytes mentah dan dicantumkan dalam JSON.

Grid runtime ground memakai ukuran object `0x118`, dimensi pada `+0x30/+0x34`,
base count/pointer pada `+0x40/+0x48`, overlay count/pointer pada `+0x50/+0x58`,
dan flag count/pointer pada `+0x60/+0x68`. Tiap record berukuran `0x34` byte:
12 float di `+0x00..+0x2f` dan empat atribut byte di `+0x30..+0x33`.
`0x172740` memilih record/atribut untuk query koordinat; `0x1577a0` memanggilnya
dengan mode base, sedangkan jalur daftar `0x157270` mengagregasi callback
spatial-index. Ini adalah consumer grid, tetapi bukan consumer dari output
Island Designer yang saat ini terpetakan.

Ada jalur writer base-grid yang sebelumnya belum tersambung ke rangkuman editor.
Native body `0x8445d0` (span `0x8445d0..0x8449db`, 1.036 byte) melewati cabang
ketika getter state di `0x878b60` bernilai 2 atau 3 dan predicate `0x84fdf0`
lulus. Handler membangun dua endpoint dari field `+0x978` dan `+0x988`, lalu
`0x52bc00` membentuk batas rectangle min/max. Pada PCs `0x8446fc` dan
`0x844710`, handler memanggil:

- `0x163780(owner, rect, 6)` → `0x185960`, yang menulis byte `6` ke keempat
  atribut base record (`+0x30..+0x33`) untuk cell dalam region yang lolos
  batas grid.
- `0x163760(owner, rect, 0.0f)` → `0x185800`, yang menulis `0.0f` ke 12 float
  base record (`+0x00..+0x2f`) untuk cell dalam region yang sama.

Kedua wrapper mengambil pointer dari `owner+0x78`. Handler menyiapkan `owner`
sebagai konteks pada offset `+0x28` dari pointer yang baru dimuat dari singleton
slot `0x32d0de8`; jadi ekspresi target yang terlihat pada instruksi adalah
`[pointer-konteks + 0xa0]`. Offset `+0x78` cocok dengan slot grid yang dipakai
jalur query/inisialisasi terindeks lain. Identitas objek singleton/pointer ini
dengan object yang dibangun oleh `0x156e30` belum dibuktikan, sehingga kecocokan
offset ini tidak diperlakukan sebagai identitas live grid. Pencarian pointer
menemukan satu entry ke `0x8445d0` pada `0x308ce60` di sequence
`0x308ce28` (31 entry); generator menandainya hanya sebagai relocated code
pointer sequence, bukan bukti tipe vtable atau caller yang ter-resolve.

Writer collision overlay juga terpetakan secara terpisah. Wrapper `0x163790`
meneruskan rectangle ke `0x185ab0`, yang menyalin 12 float dari base record ke
overlay record dan mengisi empat atribut overlay dengan byte argumen.
Pemanggil yang terindeks adalah `0x1712c0`, `0x171350`, raw span `0x1713b0`,
`0x171670`, dan `0x18bd00`. Dalam cabang transformasi `0x171670`, rectangle
dibentuk dari transform object sebelum dipakai bersama mutator bit-region
`0x1637b0 → 0x185c80`. Ini menunjukkan mutasi overlay/flag dan consumer query
grid; caller-caller itu belum tersambung ke LandMaking action-param atau patch
editor.

## Batas Island Designer dan persistence

Rantai editor masih berhenti sebelum canonical field grid. `0x531790` membaca
ActionParam dan membentuk validasi titik/3×3; `0x531ad0 → 0x53e4f0` membuat
scratch grid empat layer 12×12. `0x54dc70` menyalin blok 3×3, stride 14 byte,
ke `0x531ad0` stack local pada `sp+0x80`. Caller `0x531ad0` hanya menerima
status; tidak ada pointer output yang keluar. Direct-call index mencatat satu
caller `0x54dc70` (`0x531ad0@0x531b54`), enam caller `0x531ad0`, dan tidak ada
incoming edge terindeks untuk `0x540a10`. Corpus pointer sequence juga tidak
memuat target `0x531ad0`, `0x54dc70`, `0x540a10`, atau writer base/overlay
`0x163760/0x163780/0x163790`.

Pencarian direct-call bounded lima hop dari sepuluh entry editor/scratch
mencapai 218 node owner terindeks dan tidak mencapai query `0x157270/0x1577a0`,
ground callback `0x172740`, mutator `0x163760/0x163780/0x163790/0x1637b0`,
writer `0x185800/0x185960/0x185ab0/0x185c80`, validator region, atau consumer
preset/save `0x529ea0/0x565e30`. Ini batas call graph statis; dispatch tidak
langsung, consumer yang tidak tercakup index, dan perubahan lewat subsystem
lain tetap mungkin.

Jalur save yang dikenali memilih **UID preset**, bukan menyimpan grid terrain:
consumer `0x529ea0` menulis UID kandidat ke `SaveMainField+0xcfa2a`, sedangkan
`0x565e30 → 0x558ef0 → 0x558f40` membaca UID untuk merekonstruksi data preset.
Pemeriksaan `save_layout.json` (88 member pada keluaran yang dibatasi depth 2,
19 bernama) tidak menemukan key `LandMakingMap`, `CliffLevel`, `Terrain`, atau
`Ground`. Literal pencarian pada `main.elf` juga tidak menemukan
`LandMakingMap` atau `SaveFieldLandMakingMapData`; pencarian nama ini hanya
negatif terbatas dan tidak menutup field yang disimpan sebagai data biner atau
hash. Tidak ditemukan serializer grid, transaksi apply, undo snapshot, atau
refresh mesh/collision yang dapat dihubungkan ke hasil editor.

## OPEN yang tepat

1. **Loader → canonical ground:** tidak ada static join dari tujuh field sel
   14-byte `0x558f40` ke record runtime `0x34` byte yang dibaca `0x172740`.
   Audit PBC sebelumnya memberi struktur aset, tetapi payload PBC mentah tidak
   tersedia pada input lokal untuk menjalankan ulang konversi 14→52 byte.
2. **Editor → world mutation:** output `0x54dc70` masih lokal ke stack
   `0x531ad0`; tidak ada static edge ke writer base-grid, overlay, atau query
   refresh yang sudah dikenal.
3. **Apply/save:** UID preset `+0xcfa2a` terbukti tersimpan dalam object SaveMainField,
   tetapi bukan record grid. Tidak ada writer/serializer terrain map atau edge
   apply/undo yang ditutup oleh pencarian ini.
4. **Caller runtime writer:** `0x8445d0` menunjukkan mutasi base grid saat
   cabang state tertentu, tetapi direct-call owner tidak tersedia; entry pointer
   `0x308ce60` belum ditelusuri ke dispatcher atau keadaan gameplay.

## Batas pemeriksaan

Call graph berasal dari `/workspace/acnh-re/output/index.sqlite`; pointer
sequence dari `code_pointer_arrays.json`; byte native dari `A_logic/main.elf`.
Hash sumber, hash function-slice, daftar checksum semua preset, callsite mentah,
dan hasil bounded scan ada di [JSON ledger](../output/mechanics/terrain_canonical_grid_collision_join_followup_20261107.json).
Laporan yang dibaca mencakup loader terrain, pemilihan/persistensi UID,
Island Designer edit/apply/action-param/output escape, water/terraform, grid
ground/movement, query ground, dan region/collision mutation; nama file dan
hash-nya dicatat di ledger.

Ini analisis statis saja. Tidak ada game execution, save mutation, perubahan
Godot, perubahan index/crosswalk, staging, commit, atau push.
