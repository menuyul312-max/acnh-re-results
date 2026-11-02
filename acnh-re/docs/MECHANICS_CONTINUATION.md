# Lanjutan RE: pemeriksaan bahan, posisi pemain dan gerbang ground

Seluruh alamat di sini adalah VA ELF ACNH 1.0.0 dengan SHA-256
`5bf707c3dc5dac0ad9635af7d336ec580f81c3f7876d0f55400d1900e3415d74`.
Pseudocode Ghidra memakai tambahan base `0x100000`; signature otomatis tetap
harus diperiksa terhadap instruksi. Seluruh tujuh sistem belum selesai dipahami.
Godot tidak diubah; model/sound tetap memakai katalog sesuai arahan pengguna.

Tahap ini menambah **6.828 kasus native tanpa mismatch**. Total helper/blok
menjadi **1.123.294**; 2.546.185 pemeriksaan struktural BYML dihitung terpisah.
Jumlah kasus adalah volume validasi, bukan persentase penyelesaian game.

| Bagian | Sebelum | Hasil tahap ini | Kasus baru |
|---|---|---|---:|
| Crafting | Getter enam slot bahan | Pemeriksa kecukupan pada cache yang sudah terisi | 2.167 |
| Gerakan | Getter gravitasi dan pembentuk parameter | Pembaruan posisi utuh pada cabang tanpa kontribusi animasi | 3.205 |
| Gerakan dari hasil animasi | Consumer belum dieksekusi | Translasi/rotasi, pemilihan flag dan fallback dalam updater asli | 1.344 |
| Ground aktif | Lookup sektor map teruji | Gerbang task Stage, kesiapan world dan selector dengan item kosong | 112 |

## Pemeriksaan bahan: kecukupan tidak berarti bahan sudah dikurangi

Fungsi lengkap `0xee0be0` dijalankan dengan definisi ItemParam dan ItemKind
asli. Cache metadata, lookup dense dan enum direkonstruksi; instruksi fungsi
dan seluruh dependency yang tercapai tetap asli, tanpa stub. Cache counter
sudah ditandai initialized pada `cache+8`, sehingga pengumpulan inventory dari
save tidak dijalankan.

Record requirement memiliki flag kecukupan pada `+0x25`. Enam entry dimulai
pada `+0x2c`, stride 20 byte:

| Offset dalam entry | Isi yang dibaca/ditulis |
|---|---|
| +0 | Item delapan byte |
| +8 | Jumlah yang diperlukan, u16 |
| +10 | Counter C bila opsi bit0 aktif, selain itu nol |
| +12 | Counter A |
| +14 | Counter B |
| +16 | Field cabang alternatif yang belum divalidasi |

Untuk item normal yang diuji, A berada di `cache+0x308+2*itemID`, B di
`cache+0x7b30+2*itemID`, C di `cache+0x23020+2*itemID`. Penjumlahan A+B
dipersempit menjadi u16; jika opsi bit0 aktif, penambahan C juga dipersempit
menjadi u16. Jadi 65.535+1 menjadi nol pada jalur ini.

Jumlah kebutuhan nol melewati pengecekan. Kekurangan bahan menghapus flag
kecukupan. Kelebihan/cukup bahan **tidak menaikkan flag yang sudah nol**.
Pemeriksaan enam slot berurutan membuktikan kegagalan satu slot tetap tersimpan
sampai slot terakhir. Seluruh counter sumber tetap sama setelah fungsi kembali.

Ada 2.160 kasus kombinasi dan tujuh skenario enam bahan berurutan. Item yang
dipilih berasal dari bahan resep asli: 2511, 2768, 5983, 2769, 2502 dan 2767.
Seluruh 552 baris resep juga diperiksa secara statis; tidak ada pengulangan
material ID dalam satu resep. Pemeriksaan ini bukan transaksi crafting penuh.

Temuan penting untuk binding: `ItemParam.ItemKind` cocok dengan CRC32
`ItemKind.Label` dalam **urutan literal enum native yang berisi 120 nama**.
Kolom `Name` adalah deskripsi Jepang, dan `UniqueID` bukan ordinal enum.
Contohnya Ftr memiliki UniqueID 5 tetapi ordinal native 0. Mengurutkan menurut
UniqueID akan menghubungkan item ke aturan kind yang salah.

Counter A/B/C belum diberi nama pocket/storage karena producer-nya belum
dibuktikan. Cold cache, item remake/wrapped, cabang SaveCountMaxNum alternatif,
pengurangan bahan, pemberian hasil dan rollback transaksi masih terbuka.

Data: [inventory_requirements_native.json](../output/mechanics/inventory_requirements_native.json).
JSON memuat rujukan tabel sumber, blob, source ID dan SHA-256.

## Posisi pemain: consumer gerakan sudah berjalan utuh

Fungsi `0xdac550` kini berjalan dari entry sampai return, memakai pointer
context yang sudah tersedia serta vtable actor asli `0x30e38f8`. Constructor
`0xdb4e70` memasang vtable tersebut; constructor tidak dijalankan dalam uji.
Slot `+0xf8` menuju getter posisi `0xdb4fb0`, yang mengembalikan actor+0x278.
Slot `+0x140` menuju getter sudut `0x26250`, yang mengembalikan actor+0x2b0.

Tanpa flag kontribusi animasi, input lokal adalah `[0, player+0xf58,
player+0xf50]`. Vektor diputar dengan packed yaw pada `player+0xf48`, lalu
dikalikan float `context+0xd30` melalui getter asli `0x7d1f00`. Signature
pseudocode yang memperlakukan S0 sebagai parameter skala tidak sesuai ABI
aslinya. Satuan skala dan frekuensi pemanggilan belum terbukti sebagai timestep.

Fungsi menambahkan delta XYZ ke posisi actor dan menyalinnya ke actor+0x294.
Salinan pada player+0x12dc hanya memakai delta X/Z, dengan komponen tengah Y
ditulis nol. Actor+0x2c8 juga ditulis nol. Nilai actor+0x2dc dimasukkan ke buffer
30 entri pada player+0x16c8; indeks unsigned >=30 direset ke0 sebelum penulisan,
kemudian disimpan sebagai indeks berikutnya 1..30. Makna gameplay nilai
actor+0x2dc belum diberi nama. Actor null membuat fungsi kembali tanpa perubahan
field pemain pada context yang diuji.

Uji mencakup sudut reguler dan sudut di antara entry lookup, skala 0/0,5/1/2,
arah gerak positif/negatif, indeks buffer 0/29/30/31/0xffffffff, serta flag lain
yang tidak mengaktifkan kontribusi animasi. Seluruh buffer actor/player dan
guard dicocokkan; context dipastikan tidak berubah.

### Rotasi native memiliki aproksimasi yang perlu dipertahankan

`0x1cbd0` memakai interpolasi tabel pada **setengah sudut** untuk membentuk
quaternion. Untuk vektor lokal tanpa komponen X, koefisien X adalah `2*qs*qc`
dan Z adalah `1-2*qs*qs`, dengan pembulatan f32 sesuai instruksi. Quaternion
tidak dinormalisasi ulang. Mengganti langkah ini dengan sin/cos sudut penuh
dapat memberi delta sedikit berbeda.

Seluruh 3.200 kasus cabang gerak cocok **tanpa selisih numerik** dengan referensi
quaternion dari tabel asli. Perbandingan geometri sin/cos independen memakai
toleransi eksplisit; selisih absolut maksimum yang teramati 0,00251218 pada
grid uji. Ditambah lima kasus actor null, jumlahnya 3.205. Klaim selisih nol
tersebut berlaku pada grid uji ini, bukan seluruh kemungkinan float/angle32.

Data: [player_position_native.json](../output/mechanics/player_position_native.json).

## Kontribusi animasi: translasi, rotasi dan flag

Tambahan 1.344 kasus menjalankan updater yang sama dengan model/controller,
descriptor channel0 serta buffer hasil animasi yang direkonstruksi. Pembaca
`0x46f70`/`0x46fa0`, validasi `0x1f280c0`, getter vektor `0x1f27e80` dan
`0x1f27fa0`, konversi sudut dan getter virtual actor semuanya tetap asli.
Mesin pembentuk sampel, playback dan blending animasi tidak dijalankan.

Flag berada pada player+0xefc:

| Kondisi | Perilaku consumer yang terbukti |
|---|---|
| Bit1 | Tambahkan translasi sampel dikali float player+0x12d8 sebelum rotasi/skala |
| Bit1 dan bit5 | Gunakan panjang XZ sampel pada arah lokal Z; Y sampel diabaikan |
| Bit2 | Konversi rotasi float sampel lalu akumulasikan ke tiga sudut actor |
| Bit2 tanpa bit5 | Akumulasikan juga tiga sudut pemain, dengan wrap u32 |
| Bit2 dan bit5 | Ganti yaw pemain dengan player+0x1308; sudut X/Z pemain dipertahankan |

Konversi sudut memakai konstanta f32 `683565248.0`, sesuai skala
`2^32/(2*pi)`, perkalian f32, truncation integer lalu penyimpanan 32 bit.
Sudut actor tetap diakumulasi ketika yaw pemain memakai override.

Tujuh kondisi diuji, masing-masing 192 kasus: sampel valid, model tidak ada,
model disabled, model blocked, controller tidak ada, data tidak ada, dan mask
bit2 controller aktif. Seluruh fallback meniadakan kontribusi sampel melalui
instruksi asli. Rotasi integer dan batas penulisan memori cocok persis;
perbandingan geometri independen memiliki error maksimum 0,0000878024 pada
grid ini.

Ini membuktikan cara updater **mengonsumsi** hasil animasi. Input tombol,
perubahan velocity/gravitasi, collision solver, traversal dan penjadwalan frame
belum dirangkai menjadi simulasi pemain lengkap.

Data: [player_root_motion_native.json](../output/mechanics/player_root_motion_native.json).

## Ground dinamis: task Stage dan world readiness

Registry task asli ditemukan melalui vtable root yang memuat initializer
`0x5ca0`. Slot root+0x38 menjalankan `0x5950`, yang memasang vtable registry
`0x301c990`; initializer menyimpan pointer instance melalui GOT `0x32d08d8`.
Getter count asli mengembalikan 2. Getter entry `0xa8a0` mengembalikan record
24 byte dari alamat `0x301c950`, dengan dua nama asli: `SceneBoot` dan `Stage`.
Getter entry sendiri tidak memiliki pemeriksaan batas indeks.

Rantai native yang dijalankan:

```
0x18b570
  -> 0x880740: stage-manager ada dan hasil pemeriksa Stage nonzero
     -> 0xfef6b0
        -> context task ada
        -> registry task[index].name -> Murmur3 asli 0x1bf0
        -> hash 758f7eaf (Stage) -> baca u32 context+0x244
  -> world ada, pointer world+0xa0 ada, byte world+0xf60 nol
  -> 0x157ab0
```

`0xfef6b0` mengembalikan **nilai u32**, bukan pointer context; wrapper berikutnya
mengubahnya menjadi boolean. Pada 64 kombinasi task/context/status, hasil cocok.
Ada 48 kombinasi world/task/status tambahan. Hook hanya mengamati entry fungsi
untuk memastikan `0x157ab0` benar-benar tercapai ketika seluruh guard lolos.
Selector memakai item context kosong `0xfffe` sehingga mengembalikan sentinel7.
Task/context/world dan posisi sumber dipastikan tidak berubah.

Jalur positif dengan item context terisi masih membutuhkan validasi pemilihan
template, variasi, map dan fallback. Titik lanjutnya `0x157ab0`, lookup template
`0x856270`, resolver map **0x16e6d0**, serta fallback `0x855fa0`. Pseudocode
resolver bernama FUN_0026e6d0; itu bukan alamat ELF 0x26e6d0. Lookup sektor
`0x18adf0` tetap teruji pada tahap sebelumnya, terpisah dari pemilihan map ini.

Data: [ground_context_gate_native.json](../output/mechanics/ground_context_gate_native.json).

## Bagian yang tetap terbuka

| Area | Yang belum terbukti penuh |
|---|---|
| Fisika/collision | Penetration response, gesekan, body bergerak dan makna seluruh mask |
| Gerakan pemain | Producer input/velocity/gravity, full frame, traversal dan timestep |
| Terrain | Konversi preset14 byte ke record52 byte, edit terrain aktif dan semua syarat placement |
| Ground dinamis | Item context terisi menuju template/map aktif, transform dan fallback lengkap |
| Pemeriksaan posisi | Pengumpulan kandidat, registry actor serta seluruh filter/type/placement |
| NPC/navigasi | Scheduler C++, route/pathfinder, obstacle avoidance serta seluruh transisi AI |
| Item/alat/crafting | Pengumpulan inventory asli, transaksi/pengurangan bahan, unlock, durability dan seluruh aksi |

NPC dan terrain tidak memperoleh pembuktian runtime tambahan pada tahap ini.
Peta statis sebelumnya tetap tersedia dan tidak dinaikkan statusnya menjadi
semantik lengkap. [Frontier JSON](../output/mechanics/continuation_frontier.json)
menyimpan batas uji dan titik lanjut agar penelusuran berikutnya tidak mengulang
klaim yang sama.

## Reproduksi

Jalankan dari direktori RE dengan ELF, manifest, blob dan tabel baseline yang
sama. Original executable dan arsip sumber tidak disertakan dalam repo publik.

```bash
python tools/inventory_requirements_native.py
python tools/player_position_native.py
python tools/player_root_motion_native.py
python tools/ground_context_gate_native.py
python tools/focus7_catalogue.py
python tools/mechanics_continuation.py
```

Hasil dan tool terbaru tersedia langsung di tree Git. ZIP unduhan sebelumnya
tetap snapshot historis dan belum berisi tahap ini.
