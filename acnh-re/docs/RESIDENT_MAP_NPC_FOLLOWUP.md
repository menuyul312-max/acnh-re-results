# Lanjutan: resident PBC, arsip asli dan callback NPC

Tahap setelah commit `73a79a0` menambahkan **4.706 kasus native tanpa mismatch**:
2.881 kasus mekanik/blok dan 1.825 pendukung arsip. Total helper/blok menjadi
**1.131.926**, dari 1.127.220. Pemeriksaan struktural BYML tetap 2.546.185 dan
dihitung terpisah. Angka ini volume validasi konteks terkontrol, bukan persentase
RE seluruh game. Ketujuh sistem tetap berstatus parsial.

Semua alamat adalah VA ELF ACNH 1.0.0, bukan alamat Ghidra yang memiliki
tambahan base 0x100000. SHA-256 main.elf:
`5bf707c3dc5dac0ad9635af7d336ec580f81c3f7876d0f55400d1900e3415d74`.
Godot dan sumber pengguna tidak diubah; model/sound tetap referensi katalog.

| Area | Sebelumnya | Bukti tambahan | Kasus |
|---|---|---|---:|
| Resident ground | Fallback Floorboards saat resident map kosong | Pemilihan file, handle/type checks, transform posisi, map reader dan consumer ground | 2.278 |
| Registry NPC | 67 nama state statis | Indeks, descriptor, pemilik dan 201 target callback asli | 270 |
| Permintaan navigasi NPC | Nama/kandidat fungsi | Penulis request, predicate status, polling serta blok batas grid dan state escape | 333 |
| Pendukung SARC | Parser hasil ekstraksi | Constructor/parser/lookup native pada tiga kontainer sumber dan seluruh 1.813 member | 1.825 |

## Resident map memakai ekstensi `.pbc`

Field `RoomFloorParam.HasJmp` tidak membuktikan ekstensi `.jmp`. Resolver asli
`0x16e6d0` membentuk nama:

```text
RoomFloorParam.ResourceName + "_" + variasi + ".pbc"
variasi = 6x6, 8x8, 10x6, 10x6_R
```

Literal variasi berasal dari `0x293eabb`, ekstensi dari `0x2929873`.
Sebanyak 14 lantai HasJmp pada tabel sumber diuji dengan empat file map per
arsip resident yang direkonstruksi. SARC little/big endian dipakai bergantian.
**Berkas PBC asli tidak ditemukan pada korpus yang tersedia.** Isi map pengujian
dibentuk untuk membedakan sektor/variasi; bukan hasil ekstraksi lantai game.

Rangkaian asli berjalan dari `0x18b570` melalui selector, pencarian floor ID,
handle resident, kesiapan unit, pemeriksaan tipe resource, wrapper SARC, lookup
filename, transform posisi hingga reader `0x18adf0`. Constructor/parser SARC dan
memcpy/strcmp SDK yang dipakai adalah instruksi asli, tanpa pengganti fungsi.
State ready, RTTI yang telah terinisialisasi dan wrapper disiapkan secara
eksplisit; constructor wrapper serta loader async tidak dijalankan.

Aturan yang dibedakan melalui eksekusi:

- Kurangi posisi dunia dengan vec3 origin Stage pada `stageManager+0x968`.
- Variasi 0/1 memutar XZ menjadi `(localZ,-localX)` ketika
  `Horizon XOR orientation_bit6` bernilai true. Variasi 2/3 tidak memakai
  transform tambahan ini.
- Variasi 3 hanya boleh memakai map bila `RoomFloorParam.Rotatable` true.
  Bila false, resolver menolak sebelum lookup filename dan memakai Floorboards.
- Resident tidak siap, ID/file tidak ditemukan atau tipe resource tidak cocok
  memakai fallback Floorboards.
- **Map yang ditemukan tetapi menghasilkan atribut7 tidak memakai fallback
  Floorboards.** Consumer ground selanjutnya mempertahankan terrain base untuk7,
  termasuk ketika posisi berada di luar batas map.

Ada 2.016 kombinasi pemilihan/transform, sepuluh kegagalan resource/file, dan
252 pemanggilan lengkap query ground. Pengujian memasukkan posisi Stage
nonzero, orientasi, tiga kelas context, empat sektor dan titik di luar map.
Map sumber pengujian, guard bytes dan BCSV asli tetap identik setelah eksekusi.

Layout PBC yang dikonsumsi reader: header 20 byte, width/height pada +4/+8,
origin X/Z s32 pada +12/+16, record 52 byte dengan atribut sektor pada +48..51.
**Makna empat byte awal header dan 48 byte awal tiap record belum terbukti.**
Karena itu hasil ini belum menjadi spesifikasi collision geometry lengkap.

Data: [resident_floor_map_native.json](../output/mechanics/resident_floor_map_native.json).
Rujukan tabel ItemParam, ItemKind, RoomFloorParam dan ColGroundAttributeParam
beserta source ID/blob/checksum dipertahankan.

## Arsip sumber cocok dengan reader game

Constructor SARC `0x199a580`, parser `0x199a610`, filename wrapper `0x1c84e50`
dan lookup typed `0x1f05d90` berjalan memakai vtable asli `0x31a63c8`.

| Kontainer sumber terindeks | Member yang dicocokkan |
|---|---:|
| GameEnv.szs setelah dekompresi sumber | 1 |
| GameEnv.genvb | 48 |
| StaticParam.pack | 1.764 |

Seluruh offset, ukuran dan SHA-256 member cocok dengan manifest ekstraksi.
Tambahan mencakup filename hilang, arsip sintetis little/big endian dan member
berukuran nol. Tidak ada klaim dekompresor, filesystem atau pemuat async sudah
berjalan. Validasi ini dihitung sebagai pendukung arsip, terpisah dari mekanik.

Data: [native_archive_verification.json](../output/mechanics/native_archive_verification.json).

## Dari 67 label NPC menjadi indeks dan target callback

Blok asli `0xc1acb8` hingga sebelum `0xc1bb08` mendaftarkan 43 state umum,
memanggil extension virtual `0xbfee00` untuk 24 state aktivitas, lalu menyimpan
state awal0. Pemilik memakai vtable asli `0x30d5f28`; getter count mengembalikan67.
Manager berada pada owner+0x7760. Record descriptor 64 byte dan name16 byte
disiapkan lebih dulu; allocator prefix dan constructor penuh tidak dijalankan.

Semua 67 label serta alamat string cocok dengan bukti statis sebelumnya.
Nama yang didaftarkan menghilangkan namespace `NpcAIState::` atau
`NpcAIActivityState::`. Descriptor menyimpan owner serta tiga member pointer.

Consumer FSM asli memberi bukti peran callback: slot 0 dipakai saat masuk state
oleh `0x1f06750`, slot 8 saat update oleh `0x1f06900`, slot 0x10 saat keluar oleh
`0x1f067b0`. Penetapan peran ini memakai pembacaan instruksi consumer; simulator
seluruh FSM tidak dijalankan.

Seluruh **201 dispatcher callback** dieksekusi sampai alamat handler tujuan:
156 direct dan 45 virtual. **Eksekusi berhenti sebelum badan handler berjalan.**
Ini membuktikan binding, receiver dan resolusi member pointer, bukan seluruh
keputusan AI dari callback tersebut.

| Indeks | State native | Entry | Update | Exit |
|---:|---|---|---|---|
| 13 | cEscapeFromPlayer | 0xc2e620 | 0xc2e680 | 0xc2e690 |
| 32 | cEscapeHighCostArea | 0xc31c40 | 0xc31e20 | 0xc31e80 |
| 43 | cMoveFacility | 0xc0f480 | 0xc0f880 | 0xc0f9c0 |
| 44 | cMoveVillage | 0xc0f9d0 | 0xc0fbc0 | 0xc0fcb0 |
| 51 | cMoveSpotOut | 0xc178d0 | 0xc178f0 | 0xc18430 |

Data lengkap: [npc_state_registry_native.json](../output/mechanics/npc_state_registry_native.json).
Daftar ini berlaku untuk vtable pemilik yang diuji, bukan klaim seluruh subclass
NPC game hanya memiliki67 state.

## Wrapper navigasi kini punya batas perilaku yang teruji

Request pada NPC+0x8838 memakai tiga mode. Penulis asli `0xcb5150`/`0xcb51c0`
menyalin vec3 target untuk mode 0/1. `0xcb5240` menyimpan ID integer untuk mode 2.
Ketiganya menyalin parameter 32 byte dan menghapus flag request. Isi parameter
masih opaque; pola default lokal/global direkonstruksi untuk menguji asal copy,
bukan diklaim sebagai nilai default gameplay yang pulih.

Polling asli `0xcb5370` memperlihatkan:

- Mode 1 yang sudah dimulai melewati polling bila flag 0x12 terisi. Bila masih
  berjalan, predicate selesai menambahkan0x10; predicate gagal menambahkan2.
- Mode 2 melewati polling pada flag 2 dan hanya memakai predicate gagal.
- Predicate `0xc86cc0` true bila child+0x121 nol, atau child state 1/status 4.
  Predicate `0xc86d00` true tepat ketika status 3.

Pengujian memakai FSM child yang sengaja tidak aktif (`current=-1`, enable0).
Step FSM asli tetap berjalan dan counter-nya diperiksa, tetapi handler child
aktif serta pathfinder tidak dieksekusi. Status disiapkan sebagai input untuk
membuktikan propagasi hasil, bukan sebagai hasil pencarian rute nyata.

Blok admission `0xc86440` mengubah posisi aktor/target menjadi koordinat sel dan
memeriksa perbedaan absolut X/Z terhadap batas **24 dan 20**, inklusif. Aktor
memakai world+2,5 dan koordinat packed16; target memakai konversi langsung.
Y tidak dibandingkan di gerbang ini. Uji batas mencakup sel negatif untuk
menunjukkan wrapping packed16, tanpa menganggapnya posisi pulau yang sah.
Sebanyak 75 kasus berhenti sebelum blok reject/admit; 66 yang ditolak juga
dijalankan sampai return asli0. Cabang penerimaan belum dijalankan penuh.
Batas24/20 ini belum berarti radius global pathfinder.

Enam kasus tambahan menjalankan update `cEscapeHighCostArea` di `0xc31e20`
melalui poller asli. Flag0x12 mengarahkan ke `0xc1e2c0` dengan argumen yang
diverifikasi. Eksekusi berhenti sebelum fungsi tujuan mengubah state. Ini
menghubungkan satu callback state ke wrapper navigasi tanpa mengklaim proses
escape atau route planning lengkap.

Data: [npc_navigation_request_native.json](../output/mechanics/npc_navigation_request_native.json).

## Yang tetap belum terbukti

| Fokus | Bagian terbuka |
|---|---|
| Fisika/collision | Respons penetrasi geometry, friksi, moving body, seluruh arti mask |
| Gerakan pemain | Input sampai satu frame runtime, integrator gravitasi, koreksi collision dan landing, penjadwalan animasi |
| Terrain | Constructor preset14 byte menjadi record 52 byte, mutasi terraforming dan seluruh batas placement |
| Ground dinamis | Isi PBC asli, field yang belum dikonsumsi, loader/async/lifetime, sumber override selain RoomFloor |
| Pemeriksaan posisi | Pengumpulan kandidat, registry/filter aktor, seluruh placement query |
| NPC/navigasi | Handler child aktif, request diterima, worker pencari jalur, route node/cost/obstacle avoidance, scheduler dan keputusan AI |
| Item/alat/crafting | Akuisisi save-wrapper, nama A/B/C, item khusus, transaksi konsumsi/hasil/rollback, unlock dan durability |

Tidak diperlukan model/sound mentah untuk melanjutkan analisis algoritme ini.
Sebagian pekerjaan tetap dapat dilanjutkan dari fungsi native yang sudah ada;
isi PBC yang tidak tersedia tidak dapat diklaim pulih hanya dari pengujian map
rekonstruksi. [Frontier JSON](../output/mechanics/continuation_frontier.json)
menyimpan target lanjutan dan batas pembuktian tiap area.

## Reproduksi

Dengan input ELF/SDK serta hasil ekstraksi baseline sesuai kontrak proyek:

```bash
python tools/native_archive.py
python tools/resident_floor_map_native.py
python tools/npc_state_registry_native.py
python tools/npc_navigation_request_native.py
python tools/focus7_catalogue.py
python tools/mechanics_continuation.py
python tools/active_context_followup.py
python tools/resident_npc_followup.py
```

Generator fase historis dijalankan sebelum generator terbaru agar frontier
menunjuk tahap ini. Tools tidak mengganti instruksi atau fungsi native dengan
stub; konteks rekonstruksi dan batas blok dicatat pada JSON. Runtime emulator
tetap lingkungan terkontrol, bukan bukti observasi seluruh game yang berjalan.
