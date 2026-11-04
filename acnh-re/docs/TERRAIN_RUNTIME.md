# Runtime terrain: koordinat, overlay dan gabungan izin ground

Seluruh fungsi yang disebut teruji utuh pada konteks/buffer yang direkonstruksi.
Ini melanjutkan pembaca izin ground ke pemanggilnya, bukan menjalankan game
lengkap. Tidak ada perubahan instruksi, stub, atau pengganti hasil panggilan.

## Koordinat dan batas negatif

`0x52b5a0` membaca dua s32 di source+8/+12 dan menulis X/Z float pada output+0/+8.
Operasinya adalah konversi s32 ke f32, multiply f32 dengan 5, lalu add f32 2.5.
Y dan byte di luar dua field output tidak berubah. Output null adalah no-op.

`0x52b280` membentuk object index dari posisi. Untuk domain finite terbatas:

```
index(v) = trunc(f32(f32(trunc(v)) / 5.0)) - int(v < 0)
```

Jangan menggantinya dengan floor(v/5). Contoh native: -10 -> -3, -5 -> -2,
0 -> 0, 5 -> 1, 10 -> 2. Nilai negatif tepat pada kelipatan lima masuk index
sebelumnya. Ini aturan fungsi asli, bukan kesalahan parser yang diperbaiki.
NaN, infinity dan saturasi konversi di luar domain s32 belum diuji.

Uji converter: 562 kasus dengan batas s32 dan guard; constructor balik: 452
kasus; roundtrip pusat sel: 128 pasangan index pada rentang -1000..1000.
Unit terhadap Godot serta seluruh kelas koordinat lain belum disimpulkan.

## Grid runtime dan overlay

Helper `0x181cd0` memakai index linear x+width*z. Record runtime berukuran 52 byte;
empat byte atribut ada pada offset 48..51. Masing-masing byte overlay menggantikan
atribut base, kecuali nilainya 7. Nilai 7 berarti mewarisi byte base yang sesuai.
Overlay null atau index di luar jumlah record overlay memakai base.

Layout record ini sekarang dicocokkan dengan 783 PBC JSON terurai dalam arsip
manifest pengguna. Header menyimpan ukuran dan origin; setiap record 52 byte
memuat 12 float32 pada byte 0..47 dan empat atribut pada 48..51. HeavenTool
menamai empat grup tinggi Top/Left/Bottom/Right, masing-masing tinggi pusat dan
dua sudut; atribut memakai urutan arah yang sama. Reader lokal `0x180d20`
mengonsumsi 12 float, sedangkan `0x181cd0` mengambil empat atribut. Ini
memvalidasi bentuk dan penggunaan data payload; skala world-space, interpolasi
dan konversi LandMaking ke record masih perlu jalur loader.
Referensi dan hasil audit ada di [`external_pbc_format_reference.json`](../output/ui_island/external_pbc_format_reference.json)
dan [`manifests_pbc_audit.json`](../output/ui_island/manifests_pbc_audit.json).

Ada 576 kasus yang memeriksa semua 16 kombinasi inheritance empat byte, overlay
null/present, jumlah overlay parsial, dan enam sel grid. Enam kasus batas negatif
atau di luar width/height menghasilkan false dan tidak menulis output.

Record runtime 52 byte berbeda dari record preset mentah 14 byte. Tahap ini belum
menjalankan konversi preset menjadi buffer runtime. Payload PBC nyata mengisi
rentang tinggi lokal, tetapi hubungan nilainya ke byte elevasi dan world-space,
serta interpolasi height di native, belum diukur. Buffer base yang valid tetap
diperlukan dalam konteks uji.

## Skala LandMaking dan PBC

Arsip PBC menutup satu bagian skala spasial. Peta LandMaking berukuran 112×96;
grid pantai membagi peta itu menjadi 7×6 segmen, masing-masing 16×16 sel.
Jarak native antarpusat segmen pantai adalah 160 unit, sehingga satu sel
LandMaking berukuran 10 unit pada perbandingan lintas grid. Semua PBC untuk 13
unit terrain yang dipakai memiliki grid 2×2 dengan cell size 5, yaitu footprint
10×10 unit. Pembaca koordinat native juga menempatkan pusat sel pada
`5*i + 2.5`. Jadi dimensi dan skala saling cocok: secara kondisional, satu sel
LandMaking setara dengan 2×2 sampel ground 5-unit, dan grid rapat seluruh pulau
akan berukuran 224×192.

Ini membuktikan konsistensi skala antar sumber, bukan ekspansi aktual loader.
Origin PBC, rotasi fisik, ukuran alokasi grid runtime, dan satu-ke-satu penempatan
PBC ke setiap sel LandMaking belum terbaca di jalur native.

Uji sambungan tinggi pada orientasi CCW kandidat membandingkan 170.728 endpoint
PBC di batas sel yang byte elevasinya berbeda satu tingkat. Dari angka itu,
107.364 cocok tanpa offset elevasi, 62.936 cocok setelah uji offset 15 unit per
tingkat, dan 428 tidak cocok pada keduanya. Ini menunjukkan tidak ada satu
offset elevasi seragam yang dapat disimpulkan dari PBC statis. Angka tersebut
adalah uji profil lokal, bukan pengukuran transformasi vertikal native; detail
per rotasi dan pasangan unit ada di
[`manifests_pbc_audit.json`](../output/ui_island/manifests_pbc_audit.json).

Awalan tinggi PBC juga telah diberikan kepada penulis native `0x180d20` sebagai
12 float32 pertama dalam record 52-byte (diikuti empat material byte).
Sebanyak 208 kasus mencakup ke-13 model terrain yang dipakai, empat orientasi
kandidat, dan empat sel PBC per model. `River3B` dan `Cliff3B` menghasilkan
delapan pola word saat orientasi/sel berubah; aset Fall menghasilkan dua pola,
dan unit datar tetap datar. Neighbor di grid 8×8 direkonstruksi dengan mengulang
pola PBC 2×2 yang sama. Jadi ini membuktikan konsumen tinggi native membaca
float tinggi dari payload PBC terurai. Uji ini tidak membuktikan pembacaan empat
material byte, loader asli, transformasi pulau, seam antar-model, atau kolisi
mesh. Hasil per kasus ada di
[`terrain_pbc_native_consumers.json`](../output/mechanics/terrain_pbc_native_consumers.json).

## Empat titik dan rangkaian fungsi lengkap

Sampler `0x162dc0` menjalankan helper grid dan converter. Trace panggilan native
untuk index (0,0) merekam posisi XZ ke `0x18b570` sebagai berikut:

1. (2.5, 1.25)
2. (1.25, 2.5)
3. (2.5, 3.75)
4. (3.75, 2.5)

Ini empat titik arah dengan offset 1.25 dari pusat, bukan empat pojok sel.
Nilai sampel 7 mempertahankan atribut yang sebelumnya diperoleh dari grid.

Tiga pemanggil berikut dijalankan utuh bersama seluruh callee pada jalurnya:

| Fungsi ELF | Aturan hasil boolean |
|---|---|
| 0x187420 | Semua empat atribut memenuhi WaterCheck |
| 0x1874f0 | Setidaknya satu atribut memenuhi PlayerNoEntry |
| 0x187610 | Tepat dua atribut memenuhi WaterCheck |

Ke-16 kombinasi true/false diperiksa pada tiap fungsi (48 kasus), memakai row
mentah BCSV yang memang memiliki nilai field true/false. Ada 12 kasus koordinat
invalid dan enam kasus world/grid tidak tersedia; semua mengembalikan false.
Ini hasil predicate, bukan jaminan suatu tindakan gameplay boleh dijalankan.

Konteks yang direkonstruksi: singleton world/ground, buffer grid, array pointer
row BCSV, dan metadata cache yang sebelumnya sudah diperiksa. Manager konteks
pada *ptr(0x32d71a0) sengaja null; fungsi asli `0x880740` mengembalikan false,
sehingga fungsi asli `0x18b570` mengembalikan sentinel 7. Dengan demikian cabang
override ground oleh object dinamis **belum** diuji. Constructor loader, OS dan
semua keadaan world lainnya juga belum dijalankan.

## Validasi dan tindak lanjut

Total tahap ini **1.791 kasus**, tanpa mismatch. File hasil:
`output/mechanics/terrain_native.json`. Tool reproduksi: `tools/terrain_native.py`.
Kumulatif helper/blok kini 1.110.231; jumlah bukan persentase RE seluruh game.

Masih perlu ditelusuri: override atribut dinamis aktif, loader record runtime,
seluruh konsumen predicate ground, solver benturan/pergerakan, dan navigasi.
Model dan sound tetap dipakai melalui katalog sebagai referensi sesuai arahan.
