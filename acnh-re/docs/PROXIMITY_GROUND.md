# Kedekatan objek dan pembaca izin ground

Tahap ini menelusuri mask ke konsumen dan memperluas pemeriksaan terrain.
Model/sound tetap memakai katalog. Tidak ada perubahan proyek Godot.

## Helper kedekatan XZ

Fungsi ELF `0x7c94f0` menerima pointer dua float[3] di X0/X1, parameter R0/R1
di S0/S1, lalu mengembalikan boolean di W0. Nama R0/R1 hanya penamaan kontrak
matematis; satuan koordinat dan semua asal parameternya belum dibuktikan.

Fungsi menghitung jarak XZ dengan operasi f32 terpisah, bukan fused multiply-add:

```
dx = f32(A.x - B.x)
dz = f32(A.z - B.z)
d2 = f32(f32(dx*dx) + f32(dz*dz))
distance = f32(sqrt(d2))
threshold = f32(R0 + f32(R1 * scale))
result = distance < threshold
```

Konstanta asli pada `0x29d5fb8` adalah f32 0.9800000190734863, bukan literal
double 0.98. Komponen Y tidak dibaca. Pengujian mencakup Y nol, +/-10000,
NaN dan infinity, dengan XZ/R0/R1 finite terbatas. Buffer sumber dan guard
tetap identik. Jalur fallback SDK sqrtf untuk hasil NaN tidak diuji.

Sebanyak 1.339 kasus menjalankan helper lengkap, termasuk titik batas dan
tetangga representasi f32. Hasil seluruhnya cocok dengan model operasi f32.

## Cabang pemanggil dengan mask dan tinggi

Fragment `0x7f6b10` menjalankan getter mask asli `0x33de0`, lalu helper jarak
asli `0x7c94f0`. Cabang ini menerima kandidat hanya bila:

```
mask == 0x201
AND helper_XZ(A, B, R0, R1)
AND (height_limit <= 0 OR abs(A.y - B.y) < height_limit)
```

Ada 600 kasus kombinasi mask, jarak, selisih Y dan batas tinggi. Keputusan
accept/reject dicocokkan pada alamat `0x7f6c9c`/`0x7f6b64`. Seluruh hasil cocok;
51 kombinasi diterima. Equal-at-threshold tidak diterima oleh pembanding ketat.
Tanda negatif maupun nol pada batas tinggi melewati uji tinggi untuk domain
finite yang diperiksa.

Tidak ada stub. Pointer actor/transform, posisi, mask dan register disiapkan
secara eksplisit. Pengujian dimulai setelah filter actor/type sebelumnya dan
berhenti sebelum cleanup serta penulisan ID hasil. Pengumpulan kandidat,
registry actor dan keseluruhan fungsi query `0x7f6910` belum dijalankan.
Jangan memperluas aturan mask cabang ini ke semua jenis collision.

Caller helper yang terindeks: `0x7f6b34`, `0x7f6c28`, dan `0xe667fc`.
Deteksi kedekatan belum merupakan respons penetrasi, dorongan, gravitasi,
pergerakan atau pathfinding lengkap.

## Empat pembaca izin ground

| Field | Fungsi ELF |
|---|---|
| WaterCheck | 0x18ef20 |
| CanBury | 0x18f1c0 |
| PlayerNoEntry | 0x18f5b0 |
| NpcNoEntry | 0x18f700 |

Keempat fungsi lengkap dijalankan bersama helper lookup asli `0x18f070`.
Input memakai seluruh 63 row mentah ColGroundAttributeParam. Lookup array
pointer dan cache offset metadata direkonstruksi; constructor tabel dan proses
penemuan metadata tidak dijalankan.

Aturan baca terverifikasi: byte nol menghasilkan false; semua byte nonzero
menghasilkan true. Index di luar lookup atau cache field bertanda missing
menghasilkan false. Jumlah kasus:

- 252 pembacaan row sumber, termasuk pemeriksaan sumber tidak berubah;
- 1.024 probe, seluruh 256 byte pada masing-masing field;
- 16 index di luar batas;
- empat kondisi cache missing.

Total 1.296 kasus cocok. Makna field mengikuti descriptor yang sudah pulih;
ini belum membuktikan seluruh syarat menggali, mengubur, berjalan, berenang,
AI atau penempatan item pada caller. Field FtrPlace dan field tanpa nama
tidak dipromosikan sebagai aturan native yang sudah teruji pada tahap ini.

## Hasil dan pekerjaan berikutnya

- `output/mechanics/proximity_native.json`
- `output/mechanics/ground_permissions_native.json`
- `tools/proximity_native.py`
- `tools/ground_permissions_native.py`

Reproduksi dengan menjalankan dua tool tersebut pada korpus yang sama.
Total tahap ini 3.235 kasus; kumulatif helper/blok 1.108.440. Angka adalah
volume pemeriksaan, bukan cakupan seluruh game.

Penelusuran berikutnya: pengumpulan kandidat dan filter actor pada query penuh;
konsumen mask di 0xe715b0/0xe76270; caller empat izin ground; lalu pemisahan
deteksi, respons penetrasi, gerak/gravitasi dan navigasi. Seluruh sistem lainnya
tetap terbuka dalam ledger riset, termasuk save/network, AI dan ekonomi.
