# Pemeriksaan wilayah terrain

Lanjutan setelah commit `1ced9d9`: **216 kasus native lolos tanpa mismatch**.
Total helper/blok menjadi **1.135.793**. Angka ini volume validasi, bukan
persentase penyelesaian game. Godot dan input pengguna tidak diubah.

Fungsi asli `0x181fa0` kini berjalan lengkap bersama iterator persegi panjang
aslinya, pada grid runtime rekonstruksi. Alamat adalah VA ELF build yang sama;
checksum executable dicatat di JSON.

Temuan yang teruji:

- Rentang sel persegi panjang inklusif; sel di luar world dilewati. Wilayah
  sepenuhnya di luar world menghasilkan true pada konteks ini.
- Mode0 mensyaratkan word bit0 dan membaca base atau overlay yang tersedia.
  Overlay dipakai jika byte atribut pertamanya bukan sentinel7.
- Mode1 mensyaratkan word bit1 dan membaca base, meskipun overlay tersedia.
- Selisih maksimum-minimum **float pertama record** harus tidak melebihi
  `0.10999999940395355` (sekitar0,11). Kesamaan dengan threshold diterima.
- Record, word flags dan rectangle input dipastikan tidak berubah.

Kombinasi mencakup kedua mode, rentang di dalam/sebagian di luar/seluruhnya di
luar grid, overlay kosong/aktif/inherit, tinggi0/threshold/di atas threshold,
dan empat kombinasi flag. Oracle independen menghitung izin serta rentang tinggi.
Hasil:130 true dan86 false, sesuai native pada seluruh216 kasus.

Batas0,11 ini terpisah dari batas slope1,25 pada writer terrain sebelumnya.
Predicate ini hanya memeriksa float0; ia belum membuktikan semua12 sampel,
collision geometry atau aturan placement lengkap. Constructor preset/PBC,
caller placement hidup, rectangle terbalik dan tinggi NaN/infinite belum diuji.
Async worker, steering, physics dan sistem lain yang tercatat pada frontier
masih parsial.

Data: [bukti native](../output/mechanics/terrain_region_check_native.json),
[perbandingan tahap](../output/mechanics/terrain_region_progress.json),
[frontier](../output/mechanics/continuation_frontier.json).

Reproduksi dengan ELF dan baseline yang sama:

```bash
python tools/terrain_region_check_native.py
python tools/terrain_region_followup.py
```

Generator fase ini dijalankan setelah generator fase terdahulu bila seluruh
ringkasan dibangun ulang. Tidak ada pengganti fungsi atau instruksi native.
