# Handoff: melanjutkan RE gameplay di sesi lain

Baca file ini dulu; tidak perlu membaca seluruh repo. Antrian kerja yang bisa dibaca mesin ada di [`re_queue.json`](re_queue.json).

## Status singkat (4 November 2026)

| Area | Status | Baca bila perlu |
|---|---|---|
| Format data (BCSV, BYML, EventFlow, pesan, UI) | Lengkap secara struktural | [DATA_CONTRACT](DATA_CONTRACT.md) |
| Alur progres prolog → konser K.K. → Island Designer | Terpetakan dari EventFlow; penyelesaian bangunan dan pembuka K.K. dibaca dari pseudocode | [GAMEPLAY_FLOW](GAMEPLAY_FLOW.md) §1–11 |
| Skenario hari, minggu, tahun, villager, pengunjung | Terpetakan; beberapa algoritma masih terbuka | [GAMEPLAY_SCENARIO](GAMEPLAY_SCENARIO.md) |
| Pipeline pergantian hari native | Urutan dan peran prosesor terpetakan (`0xf53a70`, `0xf545f0`) | `output/gameplay/native_flag_refs.json` |
| Jadwal pengunjung mingguan | Terbaca utuh: pembuat `0xfd8a80`, penempatan, validasi harian `0xfd9620`, layout member, kode 0–9 | GAMEPLAY_SCENARIO §3; `native_flag_refs.json` → `data.visitor_schedule` |
| Pemilihan penghuni plot | Terbaca: filter kepribadian [0,5,4] dan pemilih acak dengan bitset eksklusi | GAMEPLAY_SCENARIO §5 |
| Pindah keluar dan pengisian slot villager | Terbaca: undian harian, bobot keakraban, pengecualian, peluang pindah masuk, pilihan kepribadian | GAMEPLAY_SCENARIO §5.1–5.2; `native_flag_refs.json` → `data.villager_moves` |
| Rumus skor pulau | Terbaca: 11 kategori item, bobot Natural/Life, bonus harga/jembatan/fasilitas, poin minus | GAMEPLAY_FLOW §10.1; `native_flag_refs.json` → `data.island_score` |
| Tanggal konser K.K. | Terbaca: NormalLive = Sabtu (geser sesuai `TkkSkipNormal`), BirthdayLive dari jadwal ulang tahun per pemain | GAMEPLAY_SCENARIO §3.6 |
| Lobak/stok toko | Belum | `re_queue.json` item 1 |
| Mekanik (collision, terrain, NPC nav, …) dan pembentukan pulau | Dikerjakan agen lain; jangan disentuh tanpa koordinasi | README root "Fokus terbaru" |

Level bukti: **[EF]** EventFlow, **[TBL]** tabel, **[PSEUDO]** pseudocode/disassembly yang belum dieksekusi, **[NATIVE]** belum dibaca, ditambah "terbukti native" untuk hasil emulasi. Jangan menaikkan status tanpa bukti.

## Menyiapkan data (±10 menit)

1. Clone repo, lalu ekstrak 8 ZIP tanpa menimpa file git:

   ```bash
   for z in downloads/*.zip downloads/additional_romfs/*.zip; do unzip -n -q "$z" -d .; done
   ```

   Alternatifnya, ekstrak ke folder lain dan pakai `--output-root <folder>/acnh-re/output` di setiap tool.
2. Untuk `rodata` dan `disasm`, letakkan ExeFS `main` (NSO0) di `acnh-re/inputs/additional_exefs/main`. Folder ini di-ignore git. Sumbernya file `extracted_exefs.zip` milik pemilik repo, `main` SHA-256 `f8d248109ff72999b4600ae3749f8c7397fb960f7ad3ab8dee3018ae9e14e900`; minta ke pemilik repo, jangan di-commit.
3. Pasang `capstone` lewat `pip install -r acnh-re/requirements-native.txt`, atau `pip install capstone` saja untuk `disasm`.
4. Cek: `python3 -m unittest discover -s acnh-re/tests -p 'test_gameplay_flow.py'`. Dengan data terekstrak dan `main` di tempatnya, hasilnya 16 OK. Tanpa `main`, 6 tes NSO di-skip.

## Alat yang dipakai

| Perintah | Untuk apa |
|---|---|
| `python3 acnh-re/tools/gameplay_flow.py build` | Bangun ulang `output/gameplay/` (indeks flag/flow, pohon flow, `native_flag_refs.json`) |
| `python3 acnh-re/tools/gameplay_flow.py tree <Flow> [--entry E] [--with-text]` | Graf satu EventFlow yang bisa dibaca |
| `python3 acnh-re/tools/re_helpers.py decomp 0xVA [--compact]` | Pseudocode dengan string di-resolve dan alamat diubah ke ELF VA |
| `re_helpers.py calls 0xVA --depth N` | Pohon callee beserta string yang dirujuk |
| `re_helpers.py refs <teks atau %pola%>` / `strings 0xVA` / `callers 0xVA` | Rujukan silang dari `index.sqlite` |
| `re_helpers.py handler <NamaAksi>` | Aksi/query EventFlow → factory, vtable, slot (slot terakhir = execute/evaluate) |
| `re_helpers.py rodata 0xVA --u32 0xVA:N` / `disasm 0xVA` | Baca string pendek/angka dari rodata, dan disassembly fungsi tanpa pseudocode |
| `re_helpers.py table <Tabel>` / `item <ID>` / `msg <regex>` | Tabel BCSV, nama item, pencarian pesan (lokal; teks jangan di-commit) |

## Aturan penting

- **Alamat:** ELF VA. Pseudocode Ghidra = ELF+0x100000 (`FUN_01077050` = `0xf77050`, `UNK_02a9bcb7` = string `0x299bcb7`).
- **Cabang flag Bool:** case 0 = ON, case 1 = OFF. `NpcHouseNum`: case 0 = ≥Num. `VillageScoreCheck*`: case 1 = ≥ambang.
- **Pola fungsi native:** `F_f44d90` get bool, `F_f44ad0` get int, `F_f44e70` set, `F_f45380` increment flag. Pola member save: `F_ee9350(&x, base + OFF, …)` → `F_ee94f0(…, SIZE)` → data = `x[2] + x[1]`; tipe member = `lRam…` tepat sesudahnya. Undian acak pergantian hari: `F_f53420(n)` = acak 0..n−1 dari RNG harian `0x35e9510` (berlaku bila global `0x35ee058` = 1, seperti di dalam `0xf84320`); `F_19aa0e0` dengan state dari TLS adalah RNG lain. Bit acak: popcount `0x198b590`, bit ke-n `0x198b630`. Nilai enum kolom tabel (`ItemKind`, `ItemSize`, `FgMainParam.Kind`, …) adalah indeks di daftar string koma di rodata; cari daftarnya dengan `rodata`, bukan dari urutan `UniqueID`.
- **Repo publik:** jangan meng-commit teks dialog, aset, executable, atau link dump. Output yang di-commit memakai MessageID saja.
- **File besar, jangan dibaca utuh:**
  - `output/gameplay/flag_index.json` dan `flow_index.json` (±2,5 MB);
  - `output/ui_island/*.json`, `output/binary/*`;
  - `LAPORAN_AKHIR.md` (lampiran panjang).

  Query dengan Python atau `re_helpers.py`.
- **Total kasus native** hanya dicatat di `output/mechanics/continuation_frontier.json` (`latest_phase`).

## Cara menutup satu item antrian

1. Ambil item `open` pertama di `re_queue.json` dan pakai `entry_points`-nya.
2. Catat bacaan di `PSEUDOCODE_READINGS` (`tools/gameplay_flow.py`), lalu jalankan `gameplay_flow.py build`.
3. Tulis temuan di GAMEPLAY_SCENARIO atau GAMEPLAY_FLOW dengan label bukti, lalu tambahkan tes bila ada invariant yang bisa dicek.
4. Ubah `status` item menjadi `done` (pindahkan ke `done`), dan tambahkan baris di log di bawah.
5. Commit lalu push ke `main`. Pemilik repo mengizinkan merge langsung.

## Log sesi

| Tanggal | Hasil | Commit |
|---|---|---|
| 2026-11-04 | Alur gameplay dari EventFlow, workflow, README dirapikan | `2c55049` |
| 2026-11-04 | Verifikasi tiga file Drive; rujukan native flag progres | `430e9ba` |
| 2026-11-04 | Pipeline pergantian hari; dokumen skenario | `f388ba3` |
| 2026-11-04 | Jadwal pengunjung (konsumen dan kode), seed RNG harian, pemilihan penghuni plot, `re_helpers.py`, handoff ini | `00669b6` |
| 2026-11-04 | Pembuat jadwal pengunjung mingguan `0xfd8a80` dan validasinya `0xfd9620`; tes NSO | `6d79bcc` |
| 2026-11-04 | Pindah keluar villager (`0xf847f0`, `0xf87670`) dan pengisian slot (`0xf84f10`) | `5993e20` |
| 2026-11-04 | Rumus skor pulau (`VillageScoreMgr` `0x15c4590`, `0x15c61f0`, penulis save `0x15c68c0`) | `59a5b34` |
| 2026-11-04 | Tanggal konser K.K. (`0xf1360`, `0xf0330`, `0xf11b0`, `0xf920f0`) | `7ace148` |
