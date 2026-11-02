# Hasil RE ACNH 1.0.0

Paket hasil reverse engineering untuk menjadi referensi konversi ke Godot. Proyek Godot dan sumber pengguna tidak diubah. Status semantik masih parsial.

## Unduh hasil lengkap

**[Unduh ZIP lengkap — 117 MB](https://github.com/menuyul312-max/acnh-re-results/releases/download/hasil-re-2026-11-02/acnh-re-results.zip)**

[Halaman Release](https://github.com/menuyul312-max/acnh-re-results/releases/tag/hasil-re-2026-11-02) · [Checksum ZIP](https://github.com/menuyul312-max/acnh-re-results/releases/download/hasil-re-2026-11-02/acnh-re-results.sha256)

Repo ini publik; hasil dapat diunduh melalui halaman Release atau direktori downloads.

ZIP lengkap berisi 86.653 entry: hasil JSON, blob yang dirujuk, pseudocode/disassembly, indeks SQLite, tool, tes, dan laporan. Repo Git menyimpan tool, laporan, ringkasan JSON, dan ZIP cadangan; seluruh keluaran terurai tersedia dalam paket lengkap.

### Jika ZIP lengkap sulit diunduh

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

Tautan laporan ke data terinci yang belum berada di tree Git dapat dibuka setelah paket lengkap diekstrak.

## Cakupan terkini

- Seluruh subset B_data yang tersedia dipetakan secara struktural: 1.171 berkas, 2.986 entri kontainer/data.
- Nama pulih: 1.957/2.048 kolom BCSV; 2.979/3.410 jenis key BYML. Cakupan kemunculan key BYML 99,452% bukan persentase RE seluruh game.
- 780.339 perbandingan helper/blok native, 2.546.185 pemeriksaan BYML, dan 34 uji integrasi lulus.
- Pemetaan Stage, item, terrain, EventFlow, SDK, cuaca, kalender, suara NPC, gen bunga dan item anakan.
- Perilaku lengkap game belum selesai; batas dan kasus yang belum diketahui dicatat eksplisit.

## Sumber dan reproduksi

Executable unggahan asli (main.elf/NPDM, main, rtld, subsdk0, sdk), instalasi tool besar, dan direktori kerja tidak dimasukkan. Simpan sumber tersebut secara terpisah sesuai kontrak input. Baca [petunjuk ExeFS](acnh-re/docs/ADDITIONAL_EXEFS.md) sebelum menjalankan pemeriksaan native.

Lisensi setiap rujukan tetap berlaku; lihat [NOTICE rujukan](acnh-re/tools/external/NOTICE.md). Tidak ada lisensi umum baru yang diberikan untuk konten game.

SHA-256 ZIP lengkap:

```text
52ad5f6ecf1a185b3ca40de5391822ee8109323378eec52cbdb651e003229af1
```
