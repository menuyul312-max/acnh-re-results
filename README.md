# Hasil RE ACNH 1.0.0

Paket hasil reverse engineering untuk menjadi referensi konversi ke Godot. Proyek Godot dan sumber pengguna tidak diubah. Status semantik masih parsial.

## Fokus terbaru: tujuh sistem mekanik

Lanjutan terbaru: [mutasi flag wilayah dan wrapper world](acnh-re/docs/TERRAIN_REGION_MUTATION.md), **164 kasus tambahan**, total **1.135.957** helper/blok. Set/clear flag wilayah dan pengaruh bit6 terhadap decoder navigasi teruji pada grid rekonstruksi. Placement lengkap tetap terbuka.

Tahap sebelumnya: [pemeriksaan wilayah terrain](acnh-re/docs/TERRAIN_REGION_CHECK.md),216 kasus tambahan; total **1.135.793** helper/blok. Mode base/overlay, flag dan batas rentang tinggi sekitar0,11 teruji pada context rekonstruksi. Sistem game lengkap tetap parsial.

[Laporan fokus](acnh-re/docs/FOCUS7_MECHANICS.md) · [Peta JSON tujuh area](acnh-re/output/mechanics/focus7/summary.json)

Fokus: fisika/collision, pergerakan pemain, terrain, ground dinamis, pemeriksaan posisi, NPC/navigasi, serta item/alat/crafting. Peta mencakup 69 tabel, 55 graf AI dan binding statis 292 parameter. [Tahap sebelumnya](acnh-re/docs/WORLD_NAV_BRIDGE.md) menambah **1.568 kasus**: 12 sampel tinggi runtime, word/flag/node navigasi, biaya default, flood-fill/bitset dan beberapa jalur evaluator NPC hingga return. Total setelah tahap itu **1.135.577**. Context tetap rekonstruksi; loader preset/PBC, world lengkap, worker async, steering dan physics belum terbukti penuh. Model/sound memakai katalog. Seluruh mekanik belum selesai; [frontier JSON](acnh-re/output/mechanics/continuation_frontier.json) mencatat yang terbukti dan yang masih terbuka. Pembaruan tersedia langsung di repo; ZIP lama tetap snapshot historis.

Pembaruan mekanik: [collision, terrain dan ledger seluruh sistem](acnh-re/docs/MECHANICS_RE.md). Data baru tersedia langsung dalam [output/mechanics](acnh-re/output/mechanics), terpisah dari ZIP snapshot sebelumnya. Tahap ini menambah 262.164 perbandingan blok native dan memetakan konfigurasi 235 state pemain. Model dan sound memakai katalog sebagai referensi.

## Pembaruan RomFS tambahan — 2 November 2026

[Laporan tambahan](acnh-re/docs/ADDITIONAL_ROMFS.md) · [Unduh tiga ZIP tambahan](downloads/additional_romfs/) · [Ringkasan JSON](acnh-re/output/additional_romfs/summary.json)

Tambahan ini memetakan 965.426 pesan dalam 14 varian bahasa, 888.034 label BDLI, 83 state machine animasi, 523 layout UI dan metadata 3.336 record tekstur. Sebanyak 8.030/8.093 rujukan pesan EventFlow serta nama tampilan 8.074/8.208 baris item terhubung ke teks yang tersedia. Katalog model/audio tetap referensi; folder Model dan Sound/Resource tidak ikut arsip tambahan.

Unduh dan ekstrak **ketiga ZIP tambahan** ke folder yang sama dengan hasil baseline. Kelima ZIP baseline di bawah tetap tersedia dan isinya tidak berubah. Jika menggunakan Code → Download ZIP, ekstrak seluruh ZIP baseline dan tambahan dari folder downloads ke folder repo yang sama. Arsip sumber RomFS dan executable asli tidak disertakan.

## Unduh hasil baseline

**[Unduh repo beserta lima ZIP hasil](https://github.com/menuyul312-max/acnh-re-results/archive/refs/heads/main.zip)**

[Halaman Release](https://github.com/menuyul312-max/acnh-re-results/releases/tag/hasil-re-2026-11-02) · [Checksum lima ZIP](downloads/SHA256SUMS.txt)

Repo ini publik; hasil tersedia dalam lima ZIP mandiri di direktori downloads. Unduh kelimanya, atau gunakan tautan unduh repo di atas. Ekstrak kelima ZIP ke folder tujuan yang sama.

Gabungan lima ZIP berisi 86.653 entry: hasil JSON, blob yang dirujuk, pseudocode/disassembly, indeks SQLite, tool, tes, dan laporan. Isinya telah diperiksa setara dengan paket ZIP lengkap lokal. Repo Git juga menyimpan tool, laporan, serta ringkasan JSON yang dapat dibaca langsung.

### Cara mengekstrak hasil

Unduh semua lima ZIP pada [downloads/](downloads/). Masing-masing adalah ZIP mandiri. Ekstrak kelimanya ke **folder tujuan yang sama**; tidak perlu perintah penggabungan. Gabungan isinya telah diperiksa setara dengan ZIP lengkap.

Jika memilih **Code → Download ZIP**, ekstrak arsip repo, lalu ekstrak kelima ZIP dalam folder downloads ke folder repo tersebut. Ini melengkapi direktori acnh-re/output dan berkas hasil lainnya.

## Laporan dan hasil yang dapat dibaca

- [Laporan lengkap](acnh-re/LAPORAN_AKHIR.md)
- [Kontrak data](acnh-re/docs/DATA_CONTRACT.md)
- [SDK/ExeFS tambahan](acnh-re/docs/ADDITIONAL_EXEFS.md)
- [Kalender, cuaca dan genetika bunga](acnh-re/docs/CALENDAR_FLOWERS.md)
- [Cakupan dan bagian yang belum diketahui](acnh-re/output/coverage.json)
- [Perbandingan tahap terakhir](acnh-re/output/progress_calendar_flowers.json)
- [Log 34 uji integrasi](acnh-re/output/verification.log)

Tautan laporan ke data terinci yang belum berada di tree Git dapat dibuka setelah kelima ZIP diekstrak.

## Cakupan terkini

- Seluruh subset B_data yang tersedia dipetakan secara struktural: 1.171 berkas, 2.986 entri kontainer/data.
- Nama pulih: 1.957/2.048 kolom BCSV; 2.979/3.410 jenis key BYML. Cakupan kemunculan key BYML 99,452% bukan persentase RE seluruh game.
- 1.135.957 kasus helper/blok native dan 2.546.185 pemeriksaan BYML; 34 uji integrasi baseline sebelumnya lulus. Jumlah kasus bukan persentase penyelesaian game.
- Pemetaan Stage, item, terrain, EventFlow, SDK, cuaca, kalender, suara NPC, gen bunga dan item anakan.
- Perilaku lengkap game belum selesai; batas dan kasus yang belum diketahui dicatat eksplisit.

## Sumber dan reproduksi

Executable unggahan asli (main.elf/NPDM, main, rtld, subsdk0, sdk), instalasi tool besar, dan direktori kerja tidak dimasukkan. Simpan sumber tersebut secara terpisah sesuai kontrak input. Baca [petunjuk ExeFS](acnh-re/docs/ADDITIONAL_EXEFS.md) sebelum menjalankan pemeriksaan native.

Lisensi setiap rujukan tetap berlaku; lihat [NOTICE rujukan](acnh-re/tools/external/NOTICE.md). Tidak ada lisensi umum baru yang diberikan untuk konten game.

SHA-256 ZIP lengkap lokal sebelum pembagian (verifikasi lima berkas unduhan memakai downloads/SHA256SUMS.txt):

```text
52ad5f6ecf1a185b3ca40de5391822ee8109323378eec52cbdb651e003229af1
```

Konsumen collision: [override mode, mask dan perubahan scalar](acnh-re/docs/COLLISION_RESPONSE.md), dengan 62.702 kasus validasi tambahan. JSON dan tool tersedia langsung dalam repo; ZIP snapshot lama tidak diperbarui.

Kedekatan dan terrain: [uji XZ, batas tinggi dan pembaca izin ground](acnh-re/docs/PROXIMITY_GROUND.md), dengan 3.235 kasus tambahan. JSON/tool tersedia langsung di repo, terpisah dari ZIP snapshot sebelumnya.

Runtime terrain: [koordinat, overlay dan tiga pemanggil ground utuh](acnh-re/docs/TERRAIN_RUNTIME.md), 1.791 kasus tambahan pada konteks terkontrol. [Resident RoomFloor terbaru](acnh-re/docs/RESIDENT_MAP_NPC_FOLLOWUP.md) mencakup pemilihan `.pbc`, transform dan consumer pada map rekonstruksi; PBC asli serta loader/async tetap terbuka.
