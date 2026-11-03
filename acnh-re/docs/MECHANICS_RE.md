# RE mekanik: collision, terrain dan jalur seluruh sistem

Status: pekerjaan berlanjut; seluruh mekanik game belum selesai dipahami.
Model dan sound memakai katalog sebagai referensi sesuai arahan pengguna.
Proyek Godot tidak dikerjakan. Ketiadaan mesh/waveform tidak menjadi syarat
untuk meneruskan analisis mekanik executable yang tersedia.

## Hasil native baru

Pembaca field `BgCheckType` berada di ELF VA `0xe8dbf0`, dengan hash descriptor
`4045796c`. Pembaca `ObjCheckType` berada di `0xe8d830`, hash `c5567172`.
Rujukan instruksi dan pseudocode dicocokkan; pseudocode memakai base +0x100000.

Literal enum BG asli pada `0x2965b0c` memuat tujuh nama dalam urutan:

1. Normal
2. OnlyWallNoGravity
3. OnlyWall
4. OnlyFloor
5. OnlyOriginalFloor
6. NoBgCheckNoGravity
7. NoBgCheckUseGravity

Seluruh hash BG pada 235 baris PlayerStateParam cocok CRC32 salah satu nama ini.
Distribusinya: Normal 151, NoBgCheckNoGravity 66, OnlyFloor 14,
NoBgCheckUseGravity 2, OnlyWallNoGravity 2. Dua mode lainnya tidak digunakan
oleh tabel yang tersedia. Nama tambahan dari referensi enum eksternal tidak
otomatis diperlakukan sebagai mode yang didukung build lokal.

Mode objek pada tabel: Heavy 223, None 6, Normal 6. Ini adalah nama konfigurasi;
respons benturan fisik masing-masing mode belum diverifikasi.

Empat blok compare/select asli diperiksa melalui emulasi:

| Blok ELF VA | Batas unsigned |
|---|---:|
| 0xe8dd20..0xe8dd28 | 7 |
| 0xe8dd74..0xe8dd7c | 7 |
| 0xe8d960..0xe8d968 | 3 |
| 0xe8d9b4..0xe8d9bc | 3 |

Masing-masing diperiksa pada 65.536 nilai rendah u32 ditambah lima nilai batas
tinggi. Total **262.164 perbandingan**, tanpa mismatch atau stub. Aturannya:
nilai unsigned di bawah batas dipertahankan, lainnya menjadi nol. Pengujian
dimulai setelah pemanggilan konversi enum dan berhenti sebelum store berikutnya.
Tidak ada klaim eksekusi pembaca tabel lengkap, resolver enum lengkap, solver
collision atau layanan OS. Ini bukan 262.164 aturan gameplay yang berbeda.

Hasil data mencakup semua state pemain dengan mode BG, mode objek, ObjCheckRate,
StopAutoSave dan EnableStageChange. Nama state dan nilai flag berasal dari tabel;
efek lengkap flag belum diuji melalui runtime game.

## Terrain dan batas interaksi

Disediakan JSON terhubung untuk 63 baris ColGroundAttributeParam, 17 baris
FieldLandMakingActionParam dan 12 baris FieldLandMakingError. Metadata menyimpan
offset/tipe kolom serta kandidat instruksi pembaca hash dari indeks native.
Data mencakup larangan masuk player/NPC, kelayakan penempatan/bury, atribut
suara/efek, aksi perubahan terrain, dan label error. Keberadaan flag tidak
membuktikan seluruh pengecekan yang dijalankan pemanggilnya. Kolom tanpa nama
asli tetap dipertahankan sebagai hash.

## Ledger penelusuran seluruh sistem

Ledger membagi bukti string dan fungsi ke collision/fisika, terrain, AI/navigasi,
inventory/crafting, save, multiplayer, tanaman, cuaca/kalender, animasi/efek/audio,
serta ekonomi/progres. Tiap target menyimpan alamat ELF, path pseudocode bila
tersedia dan caller langsung yang diketahui.

Ini kumpulan titik masuk berdasarkan bukti string pada indeks yang tersedia,
bukan inventaris lengkap seluruh fungsi suatu sistem. Fungsi dapat masuk lebih
dari satu domain. Kecocokan kata kunci dan caller tidak membuktikan semantik.

Urutan penelusuran lanjutan: konsumen mode collision dan integrasi gerak pemain;
pemeriksaan larangan terrain dan aksi terraforming; scheduler/interaksi actor;
AI/pathfinding; transaksi item dan ekonomi; save/network; kemudian hubungan
animasi, XLNK dan VFX dengan pemicu gameplay. Sistem lainnya tetap tercatat
sebagai pekerjaan terbuka, bukan dianggap selesai karena sudah ada pseudocode.

## Berkas hasil

- output/mechanics/collision_states.json
- output/mechanics/collision_native_verification.json
- output/mechanics/terrain_collision_parameters.json
- output/mechanics/systems_research_ledger.json
- tools/mechanics_atlas.py

Reproduksi: `python /workspace/acnh-re/tools/mechanics_atlas.py` dengan input ELF,
indeks SQLite dan tabel baseline yang sama. Jumlah perbandingan helper/blok
kumulatif menjadi 1.042.503; pemeriksaan BYML 2.546.185 tetap dihitung terpisah.
Jumlah tersebut adalah volume validasi, bukan persentase selesainya seluruh game.

Tahap konsumen mode: lihat [kebijakan mask dan perubahan scalar](COLLISION_RESPONSE.md), yang menambah 62.702 kasus dan menjalankan predicate asli. Total terbaru 1.105.205; angka di uraian awal adalah snapshot tahap sebelumnya.

Tahap kedekatan dan izin ground: lihat [PROXIMITY_GROUND.md](PROXIMITY_GROUND.md). Tambahan 3.235 kasus teruji; total terbaru 1.108.440. Solver gerak dan collision lengkap masih terbuka.

Tahap runtime terrain: [koordinat, overlay dan rangkaian ground](TERRAIN_RUNTIME.md), 1.791 kasus tambahan, termasuk tiga pemanggil yang dijalankan utuh pada konteks terkontrol. Total terbaru 1.110.231; override dinamis dan runtime lengkap tetap terbuka.

Fokus tujuh sistem: [peta bukti, ground dinamis, parameter gerak/NPC dan getter crafting](FOCUS7_MECHANICS.md). Tambahan 6.235 kasus native dan pemetaan statis 292 parameter; total terbaru 1.116.466. Seluruh tujuh sistem belum dinyatakan selesai.

Lanjutan: [pemeriksaan bahan, posisi/root motion dan gerbang Stage/world](MECHANICS_CONTINUATION.md).
Tambahan 6.828 kasus tanpa mismatch; total helper/blok terbaru **1.123.294**.
Consumer posisi dan hasil animasi kini berjalan utuh pada context terkontrol;
producer input/gravity, collision solver, pathfinding dan transaksi inventory
masih terbuka. Frontier JSON mencatat titik lanjut dan batas setiap pembuktian.

Lanjutan terbaru: [terrain runtime, bitset dan evaluator aktif](WORLD_NAV_BRIDGE.md)
menambah 1.568 kasus menjadi **1.135.577**. Ini mencakup 12 sampel tinggi runtime,
flag/node navigasi, bobot default, flood-fill dan sebagian jalur evaluator;
loader, live world, worker async dan steering tetap terbuka.

Tahap kernel: [kernel A*, extractor rute dan pemilihan target NPC](NPC_NAVIGATION_KERNEL.md)
menambah 2.083 kasus menjadi **1.134.009**. Kernel dan consumer dijalankan dengan
instruksi asli pada input yang dinyatakan; world-grid producer, async worker,
steering dan collision penuh belum terbukti.

Tahap resident: [resident PBC, arsip asli dan callback NPC](RESIDENT_MAP_NPC_FOLLOWUP.md)
menambah 4.706 kasus menjadi **1.131.926**. Ini mencakup resident ground pada map
rekonstruksi, registry 67 state/201 target callback, request navigasi terkontrol
dan dukungan reader SARC. Pathfinder/solver lengkap tetap terbuka.

Tahap context terisi: [override RoomFloor, producer counter dan pembentuk velocity](ACTIVE_CONTEXT_FOLLOWUP.md).
Tambahan 3.926 kasus (3.422 mekanik dan 504 pendukung SDK), total terbaru
**1.127.220**. Ground tanpa resident map, producer record ke requirement dan
blok solver pemain teruji; resource map aktif, save-wrapper, transaksi,
collision solver dan navigasi NPC tetap terbuka.
