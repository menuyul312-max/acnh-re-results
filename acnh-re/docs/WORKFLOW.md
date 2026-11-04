# Workflow penggunaan data RE

Panduan ini untuk siapa pun (orang atau agen) yang memakai atau melanjutkan hasil RE ACNH 1.0.0 di repo ini. Isinya: cara menyiapkan data, mencari jawaban, melanjutkan RE, dan mencatat hasil tanpa merusak bukti yang sudah ada.

## 1. Prinsip

- **Bukti dulu, kesimpulan kemudian.** Setiap klaim menyebut sumbernya: berkas, alamat ELF, flow/entry, flag, atau label pesan. Hasil yang belum terbukti diberi status terbuka, bukan ditebak.
- **Tingkat bukti** yang dipakai di repo:

  | Label | Arti | Dipakai di |
  |---|---|---|
  | `S` | Struktur sumber ter-decode | `component_coverage.json` |
  | `L` | Rujukan statis terhubung | `component_coverage.json` |
  | `C` | Kandidat native saja | `component_coverage.json` |
  | `U` | Belum terbukti | `component_coverage.json` |
  | `[EF]` | Terlihat langsung di EventFlow | `docs/GAMEPLAY_FLOW.md` |
  | `[NATIVE]` | Flag tanpa penulis EventFlow; pemicunya di kode native | `docs/GAMEPLAY_FLOW.md` |
  | `[TXT]` | Hanya dari teks dialog | `docs/GAMEPLAY_FLOW.md` |

  Uji native selalu menyebut SHA-256 ELF, jumlah kasus, mismatch, dan stub.
- **Alamat** adalah ELF VA. Pseudocode Ghidra memakai image base ELF+0x100000. Contohnya `FUN_0026e6d0` adalah ELF `0x16e6d0`.
- **Sumber asli tidak disimpan di repo:** executable, RomFS mentah, dan dump. Simpan di `acnh-re/inputs/` (sudah di-ignore) sesuai [kontrak input](ADDITIONAL_EXEFS.md). Jangan meng-commit aset game mentah (model, audio, tekstur) ke repo publik ini.

## 2. Isi repo dan isi ZIP

| Lokasi | Isi | Ada di git? |
|---|---|---|
| `acnh-re/docs/` | Laporan per tahap, kontrak data, workflow | ya |
| `acnh-re/tools/` | Pipeline Python (decode, uji native, indeks) | ya |
| `acnh-re/tests/` | Uji integrasi `unittest` | ya |
| `acnh-re/output/mechanics/`, `ui_island/`, `gameplay/`, ringkasan `*.json` | Hasil tahap terbaru | ya |
| `acnh-re/output/manifest.json`, `decoded/`, `tables_resolved/`, `byml_resolved/`, `byml_typed/`, `items/`, `stage/`, `relations/`, `binary/`, `blobs/`, `index.sqlite` | Hasil baseline | **hanya di 5 ZIP** `downloads/ACNH_RE_bagian_0X_dari_05.zip` |
| `acnh-re/output/additional_romfs/messages/`, `bdli/`, `ui/`, `animation_sequences/` | Pesan 14 bahasa, label BDLI, UI, ASB | **hanya di 3 ZIP** `downloads/additional_romfs/` |

## 3. Persiapan

```bash
git clone https://github.com/menuyul312-max/acnh-re-results.git
```

```bash
cd acnh-re-results
```

Ekstrak kedelapan ZIP ke root repo. Gunakan `-n` (jangan menimpa): ZIP baseline berisi versi lama `acnh-re/README.md`, `acnh-re/LAPORAN_AKHIR.md`, dan `acnh-re/output/coverage.json`, sedangkan versi di git lebih baru.

```bash
for z in downloads/*.zip downloads/additional_romfs/*.zip; do unzip -n -q "$z" -d .; done
```

Cek hasilnya. Total output sekitar 1 GB. File yang dibutuhkan minimal:

```bash
ls acnh-re/output/manifest.json acnh-re/output/decoded acnh-re/output/tables_resolved acnh-re/output/additional_romfs/messages/USen
```

Kebutuhan software:
- Python 3.11+ untuk pembaca format dan indeks.
- Untuk uji native: paket pada `acnh-re/requirements-native.txt` dan executable asli di `acnh-re/inputs/` (lihat [ADDITIONAL_EXEFS.md](ADDITIONAL_EXEFS.md)).
- Ekspor pseudocode baru: Ghidra dengan JDK 21 dan skrip `acnh-re/ghidra_scripts/`.

## 4. Mencari jawaban: file mana untuk apa

| Pertanyaan | Mulai dari |
|---|---|
| Berkas sumber apa saja yang ada, hash, formatnya | `output/manifest.json` (field `decoded` menunjuk JSON hasil baca) |
| Isi tabel BCSV dengan nama kolom | `output/tables_resolved/<Tabel>.json`, indeks `output/schemas/catalogue.json` |
| Isi BYML dengan nama key | `output/byml_resolved/`; tipe persis di `output/byml_typed/` |
| Alur cerita/progres: siapa memicu apa | [GAMEPLAY_FLOW.md](GAMEPLAY_FLOW.md), `output/gameplay/flag_index.json`, `output/gameplay/trees/` |
| Graf satu EventFlow | `python acnh-re/tools/gameplay_flow.py tree <Flow>` |
| Teks dialog/nama item | `output/additional_romfs/messages/<bahasa>/*.json`; label pesan dari `MessageID` EventFlow |
| Item, penempatan, word 8 byte | `output/items/catalogue.json`, [DATA_CONTRACT.md](DATA_CONTRACT.md) |
| Rumus yang sudah terbukti native (RNG, cuaca, kalender, bunga, collision, terrain, …) | `output/coverage.json`, `output/mechanics/*.json`, docs per tahap |
| Apa yang belum selesai dan target berikutnya | `output/mechanics/continuation_frontier.json`, `output/ui_island/component_coverage.json`, bagian 12 [GAMEPLAY_FLOW.md](GAMEPLAY_FLOW.md) |
| Fungsi native: pseudocode, rujukan string/hash | `output/binary/analysis_decomp/<va>.c`, tabel di `output/index.sqlite` |
| Dispatch aksi/query EventFlow ke kode native | `output/binary/event_handlers_resolved.json` |

Contoh: mencari siapa yang menyalakan flag progres.

```bash
python3 -c "import json;f=json.load(open('acnh-re/output/gameplay/flag_index.json'))['data']['cLand:RcmImmQuestOpen'];print(f['definition']['name_ja']);[print(w['flow'],w['entry'],w['op']) for w in f['eventflow_writers']]"
```

Contoh: melihat graf flow beserta teks dialog lokal. Teks hanya dibaca dari ekstraksi milikmu; output yang di-commit cukup menyimpan `MessageID`.

```bash
python3 acnh-re/tools/gameplay_flow.py --with-text tree SNPC_rco_53_MigrantsQuest --entry GetHousingKit
```

## 5. Melanjutkan RE: siklus satu tahap

1. **Pilih target** dari `continuation_frontier.json`, `component_coverage.json`, atau daftar `[NATIVE]` di `gameplay/flag_index.json` (`writer_status` = `no_eventflow_writer...`). Jangan mengambil area yang sedang dikerjakan agen lain; lihat commit terakhir dan bagian "Fokus terbaru" di README.
2. **Kumpulkan bukti:**
   - string atau hash di `index.sqlite`;
   - pseudocode di `binary/analysis_decomp`;
   - handler di `event_handlers_resolved.json`;
   - graf EventFlow.
3. **Buat tool** `acnh-re/tools/<nama>.py`:
   - membaca input asli atau hasil decode;
   - menulis `acnh-re/output/<area>/<nama>.json` dengan SHA-256 ELF, input, jumlah kasus, mismatch, dan stub;
   - kalau memakai emulasi, menjalankan instruksi asli, dan setiap state yang direkonstruksi dicatat.
4. **Tambah uji** `acnh-re/tests/test_<nama>.py`. Uji harus `skip` bila input lokal tidak ada, seperti `test_gameplay_flow.py`.
5. **Tulis laporan** `acnh-re/docs/<NAMA>.md`: hasil, aturan yang teruji, batas, dan yang masih terbuka.
6. **Perbarui pencatatan:**
   - `continuation_frontier.json` (`latest_phase`, `remaining`, `next_functions`);
   - progres tahap `output/<area>/*_progress.json`;
   - satu baris di "Fokus terbaru" README root.

   Angka total kasus native hanya dicatat di `continuation_frontier.json` → `latest_phase.native_helper_cases_total`. Dokumen lain cukup merujuk ke sana.
7. **Commit** per tahap dengan pesan yang menyebut hasilnya. Tool, output, uji, dan dokumen masuk satu commit.

## 6. Memakai hasil untuk konversi engine

- **Progres dan state cerita:** pakai flag dari `EventFlags*` (`tables_resolved`) sebagai state; nilai default dan maksimumnya ada di tabel. Urutan dan syaratnya ada di [GAMEPLAY_FLOW.md](GAMEPLAY_FLOW.md) dan `gameplay/milestones.json`. Langkah `[NATIVE]` perlu keputusan desain sendiri sampai RE-nya selesai.
- **Konten:** item, resep, ikan/serangga, NPC, dan musim dari `tables_resolved`. Teks dari `messages`.
- **Rumus:** pakai hanya yang berstatus terverifikasi, misalnya RNG, cuaca hari biasa, batas hari 05:00, genetika bunga, rumus bintang pulau dari EventFlow, dan aturan stack item. Kandidat dan pseudocode otomatis bukan aturan gameplay.
- **Aset:** model dan audio hanya berupa katalog referensi (`additional_romfs/catalogues`). Proyek Godot tidak diubah oleh repo ini.

## 7. Verifikasi

Semua uji:

```bash
python3 -m unittest discover -s acnh-re/tests -v
```

Hasil yang diharapkan:

| Kondisi | Hasil (24 uji) |
|---|---|
| Hanya clone, tanpa ZIP | Banyak error `FileNotFoundError`, karena file baseline ada di ZIP; 6 uji alur gameplay di-skip |
| Setelah ekstrak 8 ZIP | 16 lulus. 8 error masih wajar bila paket native (`capstone`, dari `acnh-re/requirements-native.txt`) belum dipasang dan arsip input asli tidak ada di `/workspace/downloads/` |
| ZIP, paket native, dan input asli lengkap | Semua uji dapat dijalankan |

Uji `test_corpus` membuat `acnh-re/output/index.sqlite` kosong bila indeks belum diekstrak. Hapus file itu sebelum commit.

Uji alur gameplay saja, dengan data di luar repo:

```bash
ACNH_RE_OUTPUT=/path/ke/acnh-re/output python3 -m unittest discover -s acnh-re/tests -p 'test_gameplay_flow.py' -v
```

Membangun ulang indeks alur gameplay:

```bash
python3 acnh-re/tools/gameplay_flow.py build
```

## 8. Kerja bersama beberapa agen

- Satu agen satu area. Kerjakan di branch sendiri bila memungkinkan, lalu merge ke `main`.
- Sebelum mulai, lakukan `git pull`, lalu baca commit terakhir dan "Fokus terbaru" di README.
- Jangan menulis ulang dokumen tahap milik agen lain. Tambahkan tautan atau catatan lanjutan.
- README root hanya berisi ringkasan dan tautan. Rincian masuk `docs/`; angka masuk JSON.
