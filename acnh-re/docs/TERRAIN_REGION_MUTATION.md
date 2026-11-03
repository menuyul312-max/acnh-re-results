# Mutasi flag wilayah dan wrapper world

Tahap setelah `88ad5a9` menambah **164 kasus native tanpa mismatch**; total
helper/blok menjadi **1.135.957**. Ketujuh sistem masih parsial. Context world
rekonstruksi; Godot dan input sumber tidak diubah.

Fungsi asli yang kini diuji lengkap:

- `0x181ae0`: set/clear word bit6 pada sel dalam rectangle.
- `0x185c80`: set/clear word bit2 pada sel dalam rectangle.
- `0x1637b0`: wrapper mutasi bit2 melalui owner+0x78; world null dilewati.
- `0x163740` dan `0x164e90`: meneruskan predicate tinggi melalui owner+0x78
  dan owner+0x60. Keduanya mengembalikan boolean native; signature void pada
  pseudocode tidak menangkap kontrak return tersebut.

Iterator rectangle asli memakai batas inklusif dan hanya mengubah irisan dengan
world. Mode memakai bit rendah; mode2/3 sesuai mode0/1. Bit lain, record tinggi,
rectangle dan guard di luar array dipertahankan. Pengujian mencakup wilayah
utuh, terpotong, seluruhnya di luar dan satu sel, serta word awal0/0xffffffff/0x1f00.
Dua grid allowed/denied yang berbeda membuktikan pemilihan member wrapper.

Empat kasus menjalankan mutasi bit6 lalu decoder `0x185e70` asli. Dengan word
bit12 aktif, bit6 menentukan apakah navigation-byte bit4 diteruskan: source
0x1f00 menghasilkan31, sedangkan0x1f40 menghasilkan15. Ini menghubungkan
penulisan flag wilayah ke consumer navigasi, tanpa mengganti fungsi native.

Rincian:120 kasus setter,16 forwarder,4 wrapper-null,20 wrapper aktif dan4
integrasi decoder. [JSON bukti](../output/mechanics/terrain_region_mutation_native.json)
dan [progress](../output/mechanics/terrain_mutation_progress.json) memuat scope,
alamat ELF, checksum dan batas pengujian.

Arti gameplay seluruh bit, pengumpulan aktor dan caller keputusan placement
belum terbukti. `0x165240` teridentifikasi sebagai kandidat pelepasan registry
melalui pembacaan pseudocode; fungsi tersebut belum dieksekusi. Loader preset/PBC,
live terraform, steering, worker async, physics dan transaksi crafting tetap
terbuka sesuai [frontier](../output/mechanics/continuation_frontier.json).

Reproduksi dengan ELF/SDK dan baseline yang sama:

```bash
python tools/terrain_region_mutation_native.py
python tools/terrain_mutation_followup.py
```

Jalankan generator fase ini setelah generator historis saat membangun ulang
seluruh ringkasan. Jumlah kasus bukan persentase penyelesaian game.
