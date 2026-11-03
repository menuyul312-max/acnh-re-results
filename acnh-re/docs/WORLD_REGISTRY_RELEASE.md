# Pelepasan entry registry wilayah

Lanjutan setelah `be22654`: **126 kasus native lolos tanpa mismatch**.
Total helper/blok menjadi **1.136.083**; keseluruhan game tetap parsial.
Alamat adalah VA ELF build yang sama; checksum disimpan di JSON. Godot dan
input sumber tidak diubah. List, entry dan tiga world runtime disiapkan eksplisit.

Fungsi lengkap `0x165240` kini dijalankan melalui unlink asli `0x1967c60`,
helper entry dan mutator wilayah `0x181ae0`. Kandidat yang sebelumnya hanya
dibaca statis kini memiliki bukti eksekusi untuk konteks ini.

Perilaku yang teruji:

- Entry null atau enabled byte dengan bit rendah clear tidak dilepas.
- Entry yang diterima dilepas dari linked list dan counter owner+0xf18 dikurangi.
- Jenis1/2/3 memilih world pada owner+0x60/+0x68/+0x70, lalu menghapus word bit6
  pada rectangle entry. Tiga array word yang berbeda membuktikan pemilihannya.
- Jenis0/4 yang diuji tetap melepas entry dan mengurangi counter, tetapi tidak
  mengubah world. Pemeriksaan jenis terjadi setelah pelepasan.
- Helper langsung tidak menghapus enabled byte. Wrapper `0x168140` mengambil
  owner melalui singleton world dan menghapus byte itu setelah pemanggilan.
- Dua pemanggilan langsung pada fixture mengurangi counter dua kali; dua
  pemanggilan wrapper hanya sekali karena flag sudah clear. Ini kontrak lifecycle
  helper, bukan bukti bug gameplay yang dapat dicapai.

Pengujian mencakup posisi awal/tengah/akhir pada list tiga entry, lima nilai
flag aktif, jenis valid/invalid, reciprocal links, counter dan semua sel pada
ketiga world. Link offset diambil dari owner+0xf1c; fixture memakai0x48, yang
belum diklaim sebagai satu-satunya layout asli.

Rincian:75 kasus removal,48 wrapper,1 null guard dan2 kontrak panggilan berulang.
[JSON bukti](../output/mechanics/world_registry_release_native.json),
[progress](../output/mechanics/world_registry_progress.json),
[frontier](../output/mechanics/continuation_frontier.json).

Yang masih terbuka: alokasi dan pendaftaran entry, constructor owner asli,
seluruh identitas/filter registry aktor, pemanggil keputusan placement, custom
link offsets dan kondisi list invalid. Loader preset/PBC, terraform hidup,
async worker, steering, physics dan transaksi item juga belum selesai.

Reproduksi dengan ELF/SDK serta baseline yang sama:

```bash
python tools/world_registry_release_native.py
python tools/world_registry_followup.py
```

Jalankan generator ini setelah generator historis jika membangun ulang semua
ringkasan. Tidak ada fungsi atau instruksi native diganti stub.
