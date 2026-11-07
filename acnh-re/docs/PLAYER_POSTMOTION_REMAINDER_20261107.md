# Sisa gerak post-motion: cabang `0xdac780`

Fungsi asli `0xdac780` memiliki dua jalur yang berujung pada `0xda86b0` dan
satu sink yang menulis float ke Y aktor. Uji di bawah membuktikan beberapa
potongan kontrol dan sink secara native; hasil query serta input state yang
mendahuluinya belum dijalankan.

## Jalur statis dari instruksi

Fungsi mulai dengan memanggil `0xdc80b0`, yang mengembalikan satu bila u32
`player+0x178` sama dengan `1`. Jika hasilnya nol dan `player+0xa0` null,
fungsi kembali tanpa menulis. Jika hasilnya satu, fungsi menyalin
`actor+0x27c` ke `player+0x1304`, lalu memeriksa bit nol pada `player+0xefd`.

Dengan bit tersebut mati, hasil `0xdacc40` diuji sebagai satu-hot index.
Kondisi `(1 << result) & 0x66 != 0` (hasil 1, 2, 5, atau 6) langsung menuju
panggilan `0xda86b0` di `0xdac9e4`. Hasil 0 mengubah record packed pada
`player+0x1001` melalui `0xe99510`, lalu memanggil `0x7c5570` dengan
`actor+0x284`, `actor+0x278`, dan record posisi tersebut. Hasil state lain
menuju `0x7bccf0`.

Dengan bit `player+0xefd` aktif, fungsi juga memanggil `0x7bccf0` pada
`actor+0x278`. Jalur query memilih hasil itu langsung jika `player+0xf40 == 1`;
jika tidak, kode memilih nilai yang lebih tinggi antara query dan
`actor+0x27c` untuk input finite. Kedua jalur query dan jalur khusus state nol
bertemu pada sink `0xdac9d0..0xdac9dc`: vtable slot aktor `+0xf8` menunjuk
getter asli `0xdb4fb0`, yang mengembalikan `actor+0x278`, lalu instruksi
`str s8, [x0,#4]` menulis Y di `actor+0x27c`. Sesudahnya fungsi memanggil
`0xda86b0` di `0xdac9e4`. Jalur lain juga tail-branch ke `0xda86b0` di
`0xdac9a4` setelah memulihkan stack.

Jika predicate awal `0xdc80b0` bernilai nol tetapi collider ada, jalur lain
memperbarui collider byte `+0x4f41`, menghaluskan float `player+0x12f8` menuju
nilai dari `0xe6fb50`, menyimpan dua word collider di `+0x2ac/+0x2b0`, lalu
memeriksa lagi `0xdacc40`. Beberapa hasil state memperbarui collider
`+0x178`/byte `+0x5074` dan kembali; hasil lainnya menyalin Y aktor ke
`player+0x1304`, memperbarui collider, lalu memanggil `0xda86b0`. Bagian ini
belum dieksekusi.

## Fixture native

Unicorn menjalankan tiga batas yang sempit:

- Tiga kasus menjalankan seluruh fungsi pada jalur `player+0x178 != 1` dengan
  collider null. `0xdc80b0` berjalan asli dan fungsi kembali tanpa perubahan
  player atau aktor.
- Empat kasus mulai pada `0xdac7bc`, tepat sesudah pemanggilan `0xdacc40`.
  Hasil W0 `1, 2, 5, 6` masing-masing mencapai `0xdac9e0`, tepat sebelum
  panggilan `0xda86b0`.
- Lima kasus menjalankan sink `0xdac9d0..0xdac9e0`. Nilai S8 disuplai sebagai
  hasil query yang belum dibuktikan; getter vtable asli `0xdb4fb0` berjalan,
  dan hanya `actor+0x27c` yang berubah.

Seluruh 12 kasus lolos bit-per-bit tanpa mismatch atau dependency stub. Nilai
W0 dan S8 tersebut adalah fixture input: uji ini tidak membuktikan producer
state `0xdacc40`, hasil `0x7bccf0`/`0x7c5570`, atau kondisi live yang memilih
masing-masing cabang.

Harness menggunakan `native_emulator.Sandbox` pada ELF yang checksum-nya
dipatok di bawah: segmen kode/data ELF serta relocation dipetakan apa adanya,
dengan stack `0x40000000..0x401fffff`, heap `0x50000000..0x501fffff`, dan
sentinel `0x60000000`; FP/SIMD diaktifkan. Fixture meletakkan player di
`HEAP+0x10000` dan actor di `HEAP+0x20000`, memakai stack pointer
`STACK+0x1ff000`, dan mengisi area penjaga di sekitar keduanya. Uji sink
memasang vtable actor yang slot `+0xf8`-nya menunjuk kode asli `0xdb4fb0`, lalu
posisi awal `(13,-7,29)`. Uji edge memulai emulasi pada `0xdac7bc` dengan
player di `X19`, hasil state di `W0`, dan berhenti di `0xdac9e0`; uji sink
memulai di `0xdac9d0` dengan actor di `X0` dan nilai scalar terpilih di `S8`,
lalu juga berhenti di `0xdac9e0`. Tiga panggilan penuh early-return memakai
`Sandbox.call(0xdac780, (player,))`; tidak ada alamat callee yang dipatch atau
diganti dengan stub. Kode yang tidak dieksekusi dalam fixture tetap hanya
didukung oleh inspeksi statis.

Alamat caller masuk juga belum terikat. Pemindaian instruksi ELF tidak
menemukan `B`/`BL` langsung ke `0xdac780`; set relocation dan daftar pointer
kode yang tersedia juga tidak memberi entry untuk alamat itu. Karena itu
jalur masuk/frame scheduler tetap terbuka. Jalur keluar yang dibuktikan secara
statis adalah `0xdac780 -> 0xda86b0` pada dua situs di atas.

ELF ACNH 1.0.0 memiliki SHA-256
`5bf707c3dc5dac0ad9635af7d336ec580f81c3f7876d0f55400d1900e3415d74`.
Input `additional_exefs/main` SHA-256
`f8d248109ff72999b4600ae3749f8c7397fb960f7ad3ab8dee3018ae9e14e900` cocok
dengan segmen kode `main` menurut audit `ADDITIONAL_EXEFS.md`.

Reproduksi dari checkout ini:

```bash
PYTHONPATH=/workspace/acnh-re/.deps python \
  /workspace/acnh-re-github/acnh-re/output/mechanics/player_postmotion_remainder_20261107/dac780_postmotion_native.py
```

Hasil detail, sampel, dan hash instruksi ada di
[`dac780_postmotion_native.json`](../output/mechanics/player_postmotion_remainder_20261107/dac780_postmotion_native.json).
Sumber harness ada di
[`dac780_postmotion_native.py`](../output/mechanics/player_postmotion_remainder_20261107/dac780_postmotion_native.py).

Uji ini tidak menjalankan penuh query collider, koreksi geometris, `0xda86b0`,
atau satu frame pemain. Penulisan actor Y pada sink sudah dibuktikan dengan
input S8 yang disuplai; hubungan nilainya dengan hasil query runtime dan
landing tetap terbuka.
