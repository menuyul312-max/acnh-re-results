# Konsumen mode collision: kebijakan mask dan perubahan scalar

Tahap ini mengikuti fungsi ELF `0xda97a0` sesudah pemuatan mode dari tabel.
Ini belum solver geometri atau eksekusi gerak pemain lengkap. Model dan sound
tetap memakai katalog; Godot tidak diubah.

## Aturan pemilihan yang teruji

Fragment asli `0xda9a60..0xda9b30` memakai mode objek tabel yang sudah dimuat
di stack, selector u32 pada player+0x12ec, byte player+0xf03, kondisi dari
bagian lebih awal pada W22, serta field collider+0x178.

- Selector player+0x12ec = 2 mempertahankan mode tabel. Nilai lain menjadi mode
  efektif langsung. Jangan menyamakan selector 2 dengan arti enum mode tabel 2.
- Bila bit 6 pada player+0xf03 aktif dan mode efektif bukan 2, mode menjadi 1.
- Mode 1 menghasilkan mask 0x201.
- Mode 0 menghasilkan mask nol bila bit 0 W22 aktif. Bila tidak, fungsi asli
  `0xdc80a0` dipanggil: ia memeriksa apakah u32 player+0x178 sama dengan nol.
  Hasil true memilih 0x80, false memilih 0x201.
- Mode selain 0/1 menghasilkan mask nol.
- Pada mode 0/1, bit 0 collider+0x178 diisi kebalikan bit 0 W22. Mode lainnya
  membersihkan bit tersebut. Semua bit lain pada word ini tetap dipertahankan.

Player+0x178 dan collider+0x178 adalah field pada object yang berbeda. Nama
gameplay field, byte flag, dan W22 belum ditetapkan. Pengujian merekonstruksi
nilai input fragment, bukan membuktikan seluruh inisialisasi object.

Pemanggilan helper output pada `0xda9b30` menuju `0x33dd0`. Helper ini menulis
mask ke `*(collider+0x278)+0x40`; getter `0x33de0` membacanya. Keduanya dijalankan
sebagai fungsi lengkap dengan pointer object yang direkonstruksi. Makna tiap
bit mask pada solver belum terbukti, sehingga 0x201 tidak otomatis dinamai
solid/active dan 0x80 tidak otomatis dinamai ghost.

Ada caller getter yang membandingkan hasil dengan 0x201 di fungsi 0x7f6910,
0xe715b0 dan 0xe76270. Ini jalur lanjutan untuk memetakan konsumen mask;
pseudocode caller tersebut belum diuji menyeluruh pada tahap ini.

## Perubahan nilai bertahap

Bagian `0xda9844` hingga sebelum call `0xda99bc` memperbarui float pada
player+0x12f0 menuju target. Untuk domain finite nonnegative yang diuji:

```
step = f32(base / 20)
previous < target: next = min(target, f32(previous + step))
previous > target: next = max(target, f32(previous - step))
previous = target: next = previous
```

Pembandingan memakai representasi bit f32, bukan toleransi desimal. Ini bukti
aturan perubahan scalar dalam fungsi collision-policy; satuan, arti fisik base,
asal target, interpretasi timestep dan hubungan dengan input gerak belum dibuktikan.
NaN, infinity dan nilai negatif tidak termasuk domain uji ini.

## Validasi

| Kelompok | Kasus |
|---|---:|
| Setter/getter mask lengkap, termasuk guard bytes | 262 |
| Fragment policy dengan predicate native asli | 61.440 |
| Perubahan scalar f32 | 1.000 |
| Total | 62.702 |

Seluruhnya cocok. Policy mencakup tiga mode tabel, lima selector override,
seluruh 256 nilai byte flag, dua kondisi gate, dua pola word collider dan empat
nilai field predicate. Predicate dijalankan melalui BL asli, tanpa stub atau
penggantian hasil call. Fragment berhenti sebelum helper output; helper output
dan getter diuji terpisah secara lengkap. Seluruh update pemain tidak dijalankan.

Output: `output/mechanics/collision_response_native.json`; reproduksi:
`python /workspace/acnh-re/tools/collision_response_native.py`.
Uji awal yang memakai hasil predicate sebagai input digantikan oleh pengujian
predicate asli; hitungannya tidak dijumlahkan dua kali. Jumlah helper/blok
kumulatif kini 1.105.205. Volume pemeriksaan bukan persentase penyelesaian RE.

Masih terbuka: makna mask dalam solver, bentuk collision, collision response
geometris, integrasi pergerakan dan gravitasi, serta semua state/runtime caller.
