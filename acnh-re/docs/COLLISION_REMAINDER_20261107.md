# Sisa collision: jalur setter vertikal di `0xda86b0`

Tahap ini membuktikan beberapa cabang terpilih pada fungsi asli `0xda86b0`.
Harness mulai tepat setelah pemanggilan state helper `0xdacc40`: nilai u32
hasil helper disuplai di W0 pada `0xda86e4`. Gerbang collider sebelum titik ini
dan producer nilai W0 tidak dijalankan.

## Aturan yang dibuktikan

Instruksi pada `0xda86e4..0xda8774` menyimpan W0 ke stack, membatasi nilainya
terhadap 6, lalu menguji bit `1 << W0` terhadap mask `0x62` dan `0x18`.

- Hasil W0 `1`, `5`, atau `6` masuk jalur langsung yang mengambil float dari
  `player+0x1304` dan meneruskannya ke setter virtual aktor.
- Hasil W0 `2` membaca `player+0xf58`. Jika nilainya positif, setter menerima
  `f32(player+0xf58 + actor+0x288)`. Jika nol atau negatif, cabang ini tidak
  menulis nilai Y.
- Nilai lain pada fixture masuk ke alamat `0xda8734`, tepat sebelum instruksi
  berikutnya memanggil query `0x7bccf0`. Harness berhenti sebelum query itu.

Vtable aktor asli adalah `0x30e38f8`; slot `+0x110` menunjuk `0xdb4f90`, yang
bercabang ke setter `0x2eac0`. Setter tersebut menjalankan
`str s0, [x0, #0x27c]`, jadi bukti ini mengikat cabang ke penulisan float
`actor+0x27c`. Nama gameplay untuk field, hasil state helper, dan kondisi
runtime yang memilihnya belum ditetapkan.

Sebelas fixture native cocok bit-per-bit tanpa mismatch: tiga jalur target
langsung, satu penjumlahan, dua cabang tanpa penulisan, dan lima jalur yang
berhenti sebelum query helper. Buffer player dan actor selain field Y yang
ditulis tetap sama. Harness memakai Unicorn 2.1.4; tidak ada dependency yang
diganti dengan stub. Nilai W0 dan object disusun sebagai input fixture.

Input ELF ACNH 1.0.0 memiliki SHA-256
`5bf707c3dc5dac0ad9635af7d336ec580f81c3f7876d0f55400d1900e3415d74`.
Input `additional_exefs/main` memiliki SHA-256
`f8d248109ff72999b4600ae3749f8c7397fb960f7ad3ab8dee3018ae9e14e900`; audit
`ADDITIONAL_EXEFS.md` mencatat kesamaan segmen kode `main`.

Reproduksi dari checkout ini:

```bash
PYTHONPATH=/workspace/acnh-re/.deps python \
  /workspace/acnh-re-github/acnh-re/output/mechanics/collision_remainder_20261107/da86b0_vertical_branch_native.py
```

Fixture, input branch, checksum instruksi, dan hasil rinci tersedia di
[`da86b0_vertical_branch_native.json`](../output/mechanics/collision_remainder_20261107/da86b0_vertical_branch_native.json).
Sumber harness ada di
[`da86b0_vertical_branch_native.py`](../output/mechanics/collision_remainder_20261107/da86b0_vertical_branch_native.py).

## Batas bukti

Ini hanya jalur setter vertikal yang dipilih dari `0xda86b0`, bukan bukti
landing lengkap. Gerbang collider sebelumnya, producer `0xdacc40`, query
`0x7bccf0`, sisa fungsi, dan koreksi setelah query belum diuji. Respons
penetration geometris, arti collision mask, solver gesekan, state runtime,
integrasi gerak, dan penjadwalan frame tetap terbuka.
