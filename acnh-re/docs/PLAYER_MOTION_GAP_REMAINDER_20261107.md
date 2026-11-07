# Sisa gap gerak pemain: interpolasi scalar pada `0xe17cb0`

Rentang `0xe17e94..0xe17ff8` kini dipetakan dari instruksi ELF; jalur scalar
di ujungnya juga diuji pada kode asli. Bukti ini memperlihatkan perhitungan
interpolasi yang dipengaruhi jarak horizontal, tetapi hasilnya masuk ke field
object properti, bukan langsung ke Y aktor.

## Asal data dan alur statis

`player+0x1018` dan `player+0x1022` adalah dua record posisi packed 10-byte
yang dibaca melalui helper asli `0xe99510`. Helper mengubah X/Z i32 memakai
float di `0x29d6404` (`0.00100000005`) dan Y i16 memakai faktor `0.25`, lalu
mengembalikan tiga float di S0/S1/S2. Di awal gap, kedua posisi dibaca ulang;
`0x1d5e0` menghitung nilai arah u32 dari selisih horizontal X/Z dan menulisnya
ke `SP+0x18`. Fungsi `0xdaa4a0` kemudian meneruskan nilai itu bersama konstanta
stack ke pemanggil virtual aktor dan `0x1c9d0`; makna gameplay argumen tersebut
belum dibuktikan.

Berikutnya `0xe17ef4..0xe17f20` membentuk key dari pointer global
`0x32d00668 + 0x10` dan alamat `0x29ab0b48`, lalu memanggil `0x7d1e60`.
Hasil nol menuju `0xe17f58`. Hasil nonnol memanggil `0x7d6970`; hasil nol di
sana menuju epilog `0xe18084`. Jika nonnol, `0xdc80a0` memilih antara
`0xdd6b40(player,6,1)` dan `0xdaaa50(player,6)`, lalu kedua cabang berakhir
di epilog. Jalur hit ini tidak dijalankan fixture.

Pada jalur no-hit, predicate asli `0xdc80a0` bernilai satu jika u32
`player+0x178` sama dengan nol. Nilai nol melewati scalar path menuju
`0xe17ff8`. Nilai satu masuk perhitungan jarak berikut:

```text
d_actor  = hypot(P0.x - actor.x, P0.z - actor.z)
d_target = hypot(P0.x - P1.x, P0.z - P1.z)
t        = clamp(d_actor / d_target, 0, 1)
scalar   = P0.y + (P1.y - P0.y) * t
```

Untuk input finite tanpa hasil NaN, instruksi native memakai `FSQRT`,
pembagian float, batas atas S12=`1.0`, dan pemilihan nol untuk rasio negatif.
`0xe5a6a0` memilih pointer `player+0x3f8` jika tidak null, selain itu memilih
object global default. Pemanggil `0xdb5050` menyimpan scalar ke
`object+0x2ec` dan mengatur byte `object+0x2e5` menjadi satu. Fragmen ini tidak
menulis `actor+0x27c`; nilai tersebut belum terbukti sebagai field gameplay
tertentu atau diaplikasikan ke aktor setelahnya.

## Uji native berbatas

Harness menjalankan rentang asli `0xe17f58..0xe17ff8`, termasuk predicate
`0xdc80a0`, resolver object `0xe5a6a0`, dan setter `0xdb5050`. Kedua record
packed disuplai pada offset player yang dibaca fungsi; float triplet untuk P0
dan P1 dihasilkan oleh helper asli `0xe99510`. Posisi X/Z aktor, property
object, dan word predicate direkonstruksi. Tidak ada dependency yang diganti
dengan stub.

Tujuh kasus lolos tanpa mismatch: lima interpolasi dengan actor tepat di P0,
setengah jarak, melewati P1, posisi diagonal 3-4-5, dan `d_target=0` dengan
`d_actor>0`; dua word predicate nonnol memastikan scalar store dilewati.
Buffer player, aktor, target stack, dan property object dijaga; satu-satunya
perubahan pada property object adalah field/flag di atas. Kasus NaN tidak
termasuk.

Instruksi ELF ACNH 1.0.0 memiliki SHA-256
`5bf707c3dc5dac0ad9635af7d336ec580f81c3f7876d0f55400d1900e3415d74`.
Input `additional_exefs/main` SHA-256
`f8d248109ff72999b4600ae3749f8c7397fb960f7ad3ab8dee3018ae9e14e900` memiliki
segmen kode yang dicatat identik dalam audit `ADDITIONAL_EXEFS.md`.

Reproduksi dari checkout ini:

```bash
PYTHONPATH=/workspace/acnh-re/.deps python \
  /workspace/acnh-re-github/acnh-re/output/mechanics/player_motion_gap_remainder_20261107/interpolation_target_native.py
```

Hasil, sampel, checksum byte dan batas fixture ada di
[`interpolation_target_native.json`](../output/mechanics/player_motion_gap_remainder_20261107/interpolation_target_native.json).
Sumber harness ada di
[`interpolation_target_native.py`](../output/mechanics/player_motion_gap_remainder_20261107/interpolation_target_native.py).

## Yang masih terbuka

Uji tidak menjalankan lookup `0x7d1e60`, cabang hit `0x7d6970`, pemilih aksi
`0xdd6b40`/`0xdaaa50`, atau seluruh rentang `0xe17e94..0xe17ff8`. Prefix
`0x1d5e0` dan `0xdaa4a0` hanya dipetakan statis. Asal record di runtime,
arti property scalar, penggunaan scalar setelah disimpan, landing correction,
collision geometry, durasi/frame, dan penjadwalan update masih belum
dibuktikan. Ini bukan simulasi movement atau physics lengkap.
