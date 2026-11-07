# Island loader remainder: reproducibility boundary

Tanggal: 7 November 2026. Cakupan tetap pada jalur generator/loader pulau. Tidak ada perubahan pada `re_queue.json`, README, atau artefak lama.

## Hasil

Reproduksi terbatas dari tindak lanjut 6 November lulus lagi pada input yang tersedia. Ini mempertahankan bukti statis bahwa `0x529910` mempunyai empat call site selector `0x552bb0` dan empat setup `0x528bf0`, setup memanggil transfer preset `0x558f40` hanya setelah pointer template dan grid lolos null-check, serta helper RNG asli melewati seed tetap dan delapan draw tanpa mismatch. Reproduksi ini **tidak** menjalankan generator `0x529910`, setup `0x528bf0`, atau pemuatan resource/game world lengkap.

Pemeriksaan baru memperjelas batas aset: input yang tersedia sekarang mencakup ELF yang cocok tepat dengan checksum audit sebelumnya, raw BCSV/BYML tambahan, indeks lokal, arsip sumber pulau, dan arsip RomFS tambahan lengkap. Tidak ada nama file PBC pada dua arsip sumber tersebut maupun direktori ekstrak pulau. Metadata audit lama memang mencatat `acnh_manifests_drive.zip` (SHA256 `8995d65b09a5cb84b181907c78991806f6da325bc82d35ea24ae6ecf1e263f3a`, 783 payload PBC), tetapi pemeriksaan tidak menemukan nama arsip itu di `/workspace` dan checksumnya tidak cocok dengan arsip sumber pulau/RomFS yang tersedia. JSON audit yang tersimpan berisi ringkasan turunan, bukan payload yang dapat digunakan ulang untuk join record.

Karena itu bukti terdahulu tentang isi PBC dapat dikutip sebagai hasil audit yang sudah tercatat, tetapi tidak dapat direproduksi dari input lokal pada giliran ini. Batas ini menghalangi pemeriksaan baru atas pemetaan cell LandMaking 14-byte ke cell ground/PBC 52-byte, subcell, rotasi, origin, dan tinggi runtime. Jalur runtime tetap terbuka; item end-to-end belum selesai.

## Input dan checksum

Rincian lengkap—ukuran, path, SHA256, checksum masing-masing dari 96 BYML preset, jumlah member ZIP, hasil pencarian nama PBC, dan checksum dokumen/artefak yang dipakai untuk cross-check—ada di [`source_inventory.json`](../output/ui_island/island_loader_remainder_20261107/source_inventory.json). Kumpulan utama yang dibaca:

| Input | SHA256 | Peran |
|---|---|---|
| `A_logic/main.elf` pada `/workspace/downloads/ACNH_island_RE/ACNH_island_RE/` | `5bf707c3dc5dac0ad9635af7d336ec580f81c3f7876d0f55400d1900e3415d74` | ELF persis yang dipakai `native_image.Image` dan Sandbox terbatas. |
| `/workspace/acnh-re/output/index.sqlite` | Tercatat di inventory | Call graph, ukuran fungsi, skema BCSV. Replay membaca indeks shared ini (63,946,752 byte); file `acnh-re/output/index.sqlite` di checkout delivery berukuran 0 byte dan tidak dipakai. |
| RomFS tambahan terurai di `/workspace/downloads/acnh_additional_romfs_2026-11-02/romfs` | Tiga hash tabel ada di inventory | BCSV `FieldMainFieldParam`, `FieldOutsideTemplate`, `FieldLandMakingUnitModelParam` dan 96 preset LandMaking BYML. |
| `/workspace/acnh-re-additional-romfs.zip` | `2acdf4a5b69f1f4a08078a6b8e35516997a740670a98de22dea308b6f79328e3` | Arsip RomFS tambahan gabungan; tidak ada nama member PBC. |
| `/workspace/downloads/ACNH_island_RE.zip` | Tercatat di inventory | Arsip sumber pulau; mencakup ELF yang dipakai dan tabel mentah; tidak ada nama member PBC. |
| `acnh-re/inputs/additional_exefs/main` | Tercatat di inventory | NSO ExeFS yang tersedia, checksumnya berbeda karena ini file/format terpisah dari `A_logic/main.elf`. Replay ini menggunakan ELF, bukan NSO. |

File split tambahan RomFS yang tersedia dan checksum per bagiannya ikut dicatat. Klaim pencarian ini terbatas pada nama path/member yang memuat string `pbc` tanpa membedakan huruf besar/kecil; tidak menyatakan bahwa tidak ada data geometri terenkripsi atau bernama lain di luar sumber yang diperiksa.

## Reproduksi dan hasil

Dari akar checkout `/workspace/acnh-re-github`:

```sh
python3 -m py_compile acnh-re/output/ui_island/island_loader_remainder_20261107/reproduce.py
python3 acnh-re/output/ui_island/island_loader_remainder_20261107/reproduce.py
```

Kedua perintah lulus pada 7 November 2026. Skrip replay hasil terbatas yang sudah ada di `output/ui_island/island_loader_followup/reproduce.py`, mengalihkan output ke direktori baru ini, lalu menambahkan inventory sumber dan pemeriksaan ketersediaan arsip. Tujuh assertion reproduksi lama lulus: row BCSV `96/36/246`, 96 UID preset unik dan kategori `30/33/33`, 96 grid LandMaking, kecocokan call site ELF dengan index, field transfer 14-byte versus ground/PBC 52-byte, tidak adanya member bernama PBC pada sumber RomFS terindeks, dan delapan draw RNG cocok dengan kalkulasi independen.

Harness hanya mengeksekusi instruksi ELF asli `0x19aa040` dan `0x19aa0e0`. Tidak ada call internal ke dua leaf RNG itu yang diganti stub. Harness menyediakan seed/state sintetis, stack/heap terpetakan, dan return sentinel. Ia tidak membuat singleton registry/cache/resource manager, tidak menjalankan konstruktor RNG `0x19a9fe0` yang memakai system tick, dan tidak memanggil `0x529910`, `0x528bf0`, atau loader resource. Karena itu seed tetap menguji transisi helper, bukan stream gameplay atau hasil empat slot.

Output baru: `result.json`, `source_inventory.json`, dan skrip reproduksi berada di [`output/ui_island/island_loader_remainder_20261107/`](../output/ui_island/island_loader_remainder_20261107/). Skrip merekam SHA256 input dan sumber reproducer agar pemeriksaan batas aset bisa diulang.

## Yang masih terbuka

- Eksekusi native empat slot `0x529910 → 0x552bb0/0x528bf0`, dengan state tick, registry, cache, resource template, dan destination grid asli atau fixture yang setara.
- Eksekusi resource loader `0x558f40` dengan grid tujuan dan resource objek yang sebenarnya, bukan sekadar interpretasi dataflow.
- Payload arsip PBC yang dirujuk audit sebelumnya agar join 14-byte ke 52-byte bisa diuji ulang dan transform per-subcell/rotasi/origin/tinggi dapat dipastikan.
- Pembentukan ground, collision, shore/water, dan world runtime dari input preset.

Status yang layak dicatat tetap **open** untuk gate `island-loader-end-to-end`. Hasil ini mengulang bukti bounded dan menetapkan input spesifik yang masih diperlukan; ia tidak menutup gate tersebut.
