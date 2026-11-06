# Follow-up rumah dan HHA

Tanggal: 6 November 2026. Cakupan dokumen ini mengikuti bukti per subbagian. Fungsi native tunggal tidak cukup untuk menyimpulkan seluruh evaluasi HHA.

## 1. Dispatcher enam mission HHA — terbukti terbatas

`0x7b4330` membaca enam bit rendah pada `state + 0x140`. Urutannya berkaitan langsung dengan referensi native `cPlayer:HappyHomeMission1` sampai `cPlayer:HappyHomeMission6` di `/workspace/acnh-re/output/index.sqlite` dan definisi Jepang di `output/gameplay/flag_index.json`. Semua flag bernilai Bool (`default=0`, `max=1`) dan tidak memiliki penulis EventFlow yang terindeks.

Reproducer menjalankan instruksi asli AArch64 `0x7b4330` dari NSO bersama, sambil mengontrol status hasil baca flag. Untuk setiap pasangan mask enam bit (`active_mask`, `completed_mask`), ia memeriksa urutan pembacaan, ordinal pertama yang belum selesai, argumen pada pemanggil mission `0x7b5540`, pemanggilan setter flag `0xf4b0d0`, dan nilai balik. Ada 4.096 pasangan, ditambah satu kasus yang hanya menyalakan bit di atas enam. Hasil: 0 mismatch; 3.367 kasus dispatch menghasilkan ordinal 0–5, sedangkan 729 kasus tanpa flag aktif yang belum selesai kembali 0. `param2` diteruskan ke `0x7b5540` sebagai nilai 32-bit rendah.

Native yang dijalankan adalah dispatcher `0x7b4330`. Stub hanya dipasang pada tiga batas: getter flag `0xf4aff0` mengembalikan status terkontrol, setter flag `0xf4b0d0` mencatat nama dan nilai yang diminta, dan penerima `0x7b5540` mencatat argumen tanpa efek game. Karena getter/setter tidak berjalan ke penyimpanan save asli dan penerima tidak dijalankan, bukti ini memverifikasi cabang, urutan, serta argumen dispatcher saja. Ini tidak mengungkap syarat yang menyalakan keenam bit mission.

Artefak rinci dan reproducer:

- `output/gameplay/house_hha_followup/hha_mission_dispatch_native.json`
- `tools/hha_mission_dispatch_native.py`

Jalankan dari root worktree dengan dependency cache bersama:

```bash
PYTHONPATH=/workspace/acnh-re/.deps python acnh-re/tools/hha_mission_dispatch_native.py
```

Sumber native: ExeFS `main` SHA-256 `f8d248109ff72999b4600ae3749f8c7397fb960f7ad3ab8dee3018ae9e14e900`; ELF `A_logic/main.elf` SHA-256 `5bf707c3dc5dac0ad9635af7d336ec580f81c3f7876d0f55400d1900e3415d74`. Metadata fungsi, panggilan langsung, dan nama flag dibaca dari indeks SQLite bersama secara read-only. RomFS tambahan tidak dipakai untuk dispatcher ini.

## 2. Pinjaman rumah dan grade HHA

**Terbuka pada tahap ini.** Bagian dispatcher di atas tidak membuktikan nominal pinjaman, waktu peningkatan rumah, penghitungan skor HHA, threshold grade, tema, atau jadwal surat. Perlu bukti terpisah dari EventFlow rumah, tabel RomFS terkait, dan fungsi native yang membaca atau menulis grade sebelum aturan itu dirangkum.
