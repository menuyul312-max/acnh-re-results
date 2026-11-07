# Water dan terraforming: jejak release region dan batas aksi

Tanggal: 7 November 2026. Tahap ini membaca data aksi air/terraform, mengulang satu rantai native sampai mutasi flag region, lalu mencatat link yang belum dapat dibuktikan. Tidak ada file lama, antrean, README, atau area Godot yang diubah.

## Temuan

`FieldLandMakingActionParam` berisi 17 baris. Dua baris air terjun yang relevan adalah indeks sumber 9 (`FallActionType=MakeFall`, `FallToRiver=0`) dan 10 (`FallActionType=BreakFall`, `FallToRiver=1`); keduanya menggunakan rentang 3×3 dan layer No0. Nilai itu membuktikan konfigurasi [TBL], tetapi belum mengidentifikasi handler pemain yang memilih baris atau menulis perubahan LandMaking.

Rantai mutasi region yang benar-benar dijalankan adalah `0x168140 → 0x165240 → 0x181ae0`. Wrapper melepas entry yang aktif dari list; fungsi release menurunkan count, memilih salah satu world berdasarkan kind entry, lalu menjalankan mutator rectangle `0x181ae0`. Pada fixture kind 1, kode native membersihkan bit `0x40` di rectangle inklusif x=1..3, z=2..4, melepas satu node, menurunkan count 3→2, dan wrapper mengosongkan byte enabled. Semua sel lain dan dua world fixture lain tetap sama. Ini membuktikan kontrak jalur release/mutasi native pada fixture.

Validasi tinggi wilayah `0x181fa0` mempunyai caller langsung `0x163740` dan `0x164e90`. Mutator `0x181ae0` hanya mempunyai caller langsung `0x165240`, dan release itu hanya dipanggil langsung oleh wrapper `0x168140`. Daftar caller wrapper saat ini adalah `0x156970`, `0x15f4e0`, dan `0x160940`. Indeks direct-call karenanya mengikat validasi dan pelepasan ke cabang terpisah; ia belum menghubungkan baris `MakeFall`/`BreakFall` atau predicate `0x181fa0` ke mutasi `0x181ae0`. Dispatch tidak langsung masih mungkin, jadi temuan ini menetapkan link yang hilang dari bukti yang tersedia, bukan membuktikan jalur gameplay tidak ada.

## Reproduksi, input, dan batas fixture

Jalankan dari akar checkout:

```sh
python3 -m py_compile acnh-re/output/ui_island/water_terraform_remainder_20261107/reproduce.py
PYTHONPATH=/workspace/acnh-re/.deps python3 acnh-re/output/ui_island/water_terraform_remainder_20261107/reproduce.py
```

Kedua perintah lulus. `PYTHONPATH` menunjuk paket read-only di bundle dependency shared agar Unicorn, Capstone, dan pyelftools tersedia; skrip juga menambahkan path tersebut sebelum mengimpor harness. Skrip memakai `A_logic/main.elf` dari `output/manifest.json` dan memastikan SHA256 `5bf707c3dc5dac0ad9635af7d336ec580f81c3f7876d0f55400d1900e3415d74`. Query call graph memakai `/workspace/acnh-re/output/index.sqlite` yang berukuran 63,946,752 byte; salinan `acnh-re/output/index.sqlite` di delivery checkout berukuran 0 byte dan tidak dibuka. Raw `FieldLandMakingActionParam.bcsv` berukuran 804 byte dan SHA256-nya `fe3f06ae6fb26c95631e842cd043a52348ba2c7399fc5d6085ff13dcfed0af9a`. Input tambahan, checksum dekompilasi, edge per callsite, dan hash file output ada di JSON hasil.

Harness mengimpor `WorldHarness`, tetapi tidak mengganti fungsi native dengan stub. Ia memetakan fixture sintetis untuk owner/list, enabled byte, rectangle, singleton pointer dan tiga world record; link offset `0x48` hanya konfigurasi fixture. `main` ExeFS NSO dicatat untuk kelengkapan sumber namun tidak dipakai eksekusi ini. Bukti native sebelumnya untuk predicate `0x181fa0` ada di `water_terraform_followup/native/terrain_region_check_native.json` (216 kasus); tahap ini tidak menafsirkan predicate itu sebagai validator Island Designer.

Artefak baru di [`output/ui_island/water_terraform_remainder_20261107/`](../output/ui_island/water_terraform_remainder_20261107/) menyimpan potongan tabel, trace native, dan reproducer. Jalur yang masih terbuka adalah pemanggil aksi pemain yang memilih `FieldLandMakingActionParam`, validasi sebelum MakeFall/BreakFall, mutasi record 14-byte atau grid terrain hidup, undo/commit/save, dan refresh water mesh/flow/shoreline. Karena jalur itu belum diikat, item water/terraform tetap open; hasil ini tidak menutup simulasi air atau Island Designer.
