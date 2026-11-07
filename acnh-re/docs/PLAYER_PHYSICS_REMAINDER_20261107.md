# Sisa bukti gerak pemain: konsumen velocity X/Z

Tahap ini menghubungkan keluaran velocity dari blok asli dalam `0xe17cb0`
dengan satu operasi posisi berikutnya pada fungsi yang sama. Bukti berlaku
hanya untuk dua rentang instruksi yang dijalankan terpisah; rentang di antaranya
direkonstruksi oleh harness dan tidak dijalankan.

## Bukti native

Rentang `0xe17e0c..0xe17e94` membaca pasangan record waktu pada `SP+0x38`,
target XYZ pada `SP+0x40`, dan posisi awal dari aktor pada `player+0x68`.
Fungsi asli memilih waktu akhir primer (`record+0x18`) kecuali nilainya negatif,
lalu memakai waktu akhir fallback (`fallback+0x0c`). Selisih terhadap waktu
awal primer (`record+0x14`) dikonversi menjadi u32; nol menjadi durasi satu.
Getter parameter, solver ballistic `0x1d280`, dan pembentuk triplet gerak
`0xdb17f0` berjalan sebagai kode asli. Velocity XYZ disimpan pada
`player+0x574`.

Rentang `0xe17ff8..0xe18038` memuat ulang aktor dari `player+0x68`, mengambil
getter posisi virtual melalui slot vtable `+0xf8`, lalu memperbarui posisi X
dengan `player+0x574` dan posisi Z dengan `player+0x57c`. Getter asli
`0xdb4fb0` mengembalikan alamat `actor+0x278`. Rentang ini tidak menulis
komponen Y pada vektor tersebut; itu hanya menyatakan batas fragment ini dan
tidak meniadakan koreksi Y di jalur lain dalam fungsi.

Delapan fixture finite lolos tanpa mismatch. Cakupannya meliputi perpindahan
positif dan negatif, interval satu/3/4/5, fallback ketika endpoint primer
negatif, endpoint `-0.0`, truncation interval pecahan, serta velocity X/Z nol.
Perbandingan posisi dan guard dilakukan bit-per-bit. Contoh tiga langkah dari
`[0,0,0]` menuju target `[10,5,-5]` menghasilkan velocity
`[3.3333333,2.1666667,-1.6666666]`; rentang konsumen mengubah posisi menjadi
`[3.3333333,0,-1.6666666]`.

Harness memakai Unicorn 2.1.4 dan menjalankan instruksi ELF ACNH 1.0.0 dengan
SHA-256 `5bf707c3dc5dac0ad9635af7d336ec580f81c3f7876d0f55400d1900e3415d74`.
Input NSO `additional_exefs/main` memiliki SHA-256
`f8d248109ff72999b4600ae3749f8c7397fb960f7ad3ab8dee3018ae9e14e900`; audit
`ADDITIONAL_EXEFS.md` mencatat kesamaan segmen kode `main`.

Harness merekonstruksi memori player/aktor, pasangan record waktu, target,
registry parameter dan nilai sumber `PlayerActor.mDefaultGravity.f32 = -0.25`.
Pointer vtable aktor memakai nilai asli `0x30e38f8`, dan semua dependency
native yang dipanggil berjalan tanpa stub. Celah `0xe17e94..0xe17ff8` tidak
dijalankan, sehingga hasil ini bukan simulasi update penuh.

Reproduksi dari checkout ini:

```bash
PYTHONPATH=/workspace/acnh-re/.deps python \
  /workspace/acnh-re-github/acnh-re/output/mechanics/player_physics_remainder_20261107/player_xz_position_native.py
```

Hasil terperinci, fixture, hash byte dan batas harness ada di
[`player_xz_position_native.json`](../output/mechanics/player_physics_remainder_20261107/player_xz_position_native.json).
Sumber reproduksi ada di
[`player_xz_position_native.py`](../output/mechanics/player_physics_remainder_20261107/player_xz_position_native.py).

## Batas yang masih terbuka

Uji ini tidak menjalankan query target/ground di celah tadi, seluruh fungsi
`0xe17cb0`, koreksi landing, respons penetration, solver geometri collision,
atau penjadwalan traversal. Record dan target disuplai harness, jadi asalnya
dari input dan state gameplay belum dibuktikan. Satuan durasi dan hubungan
durasi dengan frame juga tetap belum diketahui. Hasil ini memperluas bukti
konsumen velocity X/Z saja; movement/physics belum lengkap.
