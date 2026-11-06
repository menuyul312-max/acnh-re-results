# Handoff: melanjutkan RE gameplay di sesi lain

Baca file ini dulu; tidak perlu membaca seluruh repo. Antrian kerja yang bisa dibaca mesin ada di [`re_queue.json`](re_queue.json). Item `open` diurutkan menurut prioritas pemilik; sisa kecil yang belum terjawab ada di `left_open` tiap entri `done` (diaudit 6 November 2026, lihat `done_audit`).

## Status singkat (5 November 2026)

| Area | Status | Baca bila perlu |
|---|---|---|
| Format data (BCSV, BYML, EventFlow, pesan, UI) | Lengkap secara struktural | [DATA_CONTRACT](DATA_CONTRACT.md) |
| Alur progres prolog → konser K.K. → Island Designer | Terpetakan dari EventFlow; penyelesaian bangunan dan pembuka K.K. dibaca dari pseudocode | [GAMEPLAY_FLOW](GAMEPLAY_FLOW.md) §1–11 |
| Skenario hari, minggu, tahun, villager, pengunjung | Terpetakan; beberapa algoritma masih terbuka | [GAMEPLAY_SCENARIO](GAMEPLAY_SCENARIO.md) |
| Pipeline pergantian hari native | Urutan dan peran prosesor terpetakan; semua prosesor punya bacaan (`0xf53a70`, `0xf545f0`) | `output/gameplay/native_flag_refs.json` |
| Jadwal pengunjung mingguan | Terbukti native: pembuat `0xfd8a80` (1500 minggu), validasi harian `0xfd9620` (3000 hari), pembungkus `0xfd8920`; layout member, kode 0–9. Posisi spawn `0xfda740` masih [PSEUDO] | GAMEPLAY_SCENARIO §3; `native_flag_refs.json` → `data.visitor_schedule` |
| Pemilihan penghuni plot | Filter kepribadian [0,5,4] terbaca. Pemetaan kepribadian = indeks enum `NpcLooks` dan pemilih dua tahap (spesies → villager) terbukti native | GAMEPLAY_SCENARIO §5 |
| Pindah keluar dan pengisian slot villager | Terbukti native (15 kasus): undian harian, bobot keakraban, pengecualian dan jendela ulang tahun, peluang pindah masuk, mask kepribadian, pool `InitLive`, pemilihan dua tahap | GAMEPLAY_SCENARIO §5.1–5.2; `native_flag_refs.json` → `data.villager_moves` |
| Verifikasi native | 53 kasus lulus (15 siklus villager dengan `NmlNpcParam` asli, 3 jadwal pengunjung, 7 pemilihan ikan dan slot serangga atas tabel asli, 2 undian serangga: `0x957940`, `0x958570`, 3 objek lapangan: jenis batu `0x4d7110`, jenis kerang `0x7abd00`, batas kerang `0x7a7010`; 3 isi awal pulau: bunga `0xf50ad0`, grup bunga `0xf50f50`/`0xf51040`, buah `0xf509e0`; 3 aturan penempatan: tempat pohon `0x7ab350`, lereng `0x7a2e10`, tetangga bebas `0x4b5cc0`; 4 gulma: tabel musim, tumbuh `0x4b6000`, sebar `0x4b63e0`, konversi `0x4ba120`), termasuk empat cabang query Daisy Mae dengan accessor terkontrol; suite gameplay 40/40 tanpa skip dengan Unicorn/Capstone lokal dan ExeFS `main` | GAMEPLAY_SCENARIO §1 "Bacaan yang sudah terbukti native"; `tests/test_gameplay_flow.py` |
| Layout save | Terbukti native: 88 member terpilih; sensus 43.292 node, 151 vtable, 76 ukuran. Skema publik memberi kandidat lintas versi: 143/151 sampel vtable dan 85/88 member cocok pada offset, ukuran, dan kedalaman; nama lokal belum dibuktikan oleh RTTI | GAMEPLAY_SCENARIO §1; `output/gameplay/save_layout.json`; `output/gameplay/save_layout_external_crosswalk.json` |
| Rumus skor pulau | Terbaca: 11 kategori item, bobot Natural/Life, bonus harga/jembatan/fasilitas, poin minus. Dampak bit item `+2` dan syarat struktur bit `+8` sudah dibuktikan; nama simbolik bit tetap tidak ada | GAMEPLAY_FLOW §10.1; `native_flag_refs.json` → `data.island_score` |
| Tanggal konser K.K. | Terbaca: NormalLive = Sabtu (geser sesuai `TkkSkipNormal`), BirthdayLive dari jadwal ulang tahun per pemain | GAMEPLAY_SCENARIO §3.6 |
| Kemunculan ikan dan serangga | Ikan terbukti native: undian per posisi `0x5b9ba0` (bobot float32, mask `AppearType`, `IsCreateBait`), undian persen `0x5b98b0`, gerbang hujan/mode `0x5b9270`, slot jam. Serangga terbukti native: undian pulau `0x957940` (bobot u16 `Prob`, `r = u × W >> 32`) dan saringan `AppearFg` `0x958570`; batas per spesies `0x8ddbd0` [PSEUDO]. `0xb56850`/`0xb53d20` = ketersediaan pulau misteri (koreksi bacaan lama); bit lapangan `+0x13e1` = mode pulau misteri [PSEUDO]. Terbuka: aturan cuaca serangga di pulau utama, jalur titik spawn per kelompok `AppearFg` | GAMEPLAY_SCENARIO §8; `output/gameplay/creature_spawn.json`; `native_flag_refs.json` → `data.creature_spawn` |
| Lobak dan stok toko | Alur lokal input `cKabu` → query dan layout numerik terpetakan; output Nook, slot bersyarat, domain ID 0–14999, dan mekanisme batch tujuh hari terbukti. Keanggotaan bitset state 2/3, hasil RNG konkret, serta page binding build 1.0.0 tetap terbuka | GAMEPLAY_SCENARIO §3.7; `output/gameplay/kabu_ui_binding.json`; `output/gameplay/nook_shop_weekly_slot_map.json`; `re_queue.json` |
| Objek lapangan pulau | Prosesor harian `0x4ae640` dan tanaman `0x4b6e70` terpetakan: batu, batu uang, fosil, pecahan bintang, kerang, ranting, isi pohon, pertumbuhan pohon/buah, gulma, dan isi awal pulau baru. Jenis batu, jenis kerang, batas kerang, serta tumbuh, sebar, dan konversi musim gulma terbukti native; sisanya [PSEUDO] | GAMEPLAY_SCENARIO §10; `native_flag_refs.json` → `data.field_regrowth` |
| Aturan penempatan | Tempat pohon/kelapa `0x7ab350`, lereng `0x7a2e10`, dan tetangga bebas `0x4b5cc0` terbukti native (akses atribut tanah dikontrol). Batu `0x7aa3c0` (set 2 ∩ 20), fosil `0x7ad6e0` (set 3 ∩ 20), gulma dan penempat umum `0x7aadc0` [PSEUDO]. Objek kerja: 5 bitset ubin + 26 bitset unit; set 20 = area yang bisa dicapai pemain menurut `VillageExtensionLevel2/3` | GAMEPLAY_SCENARIO §10.5; `native_flag_refs.json` → `data.field_regrowth.placement` |
| Isi awal pulau | Zona `0x7b8b30`: 0 = daratan terhubung ke plaza tanpa menyeberang air, 1 = `CliffLevel` 0, 2 = `CliffLevel` 1–2. Buah khas/saudara (`0xf509e0`) dan spesies bunga pulau (`0xf50ad0`, 8 spesies dengan mask bulan) terbukti native. Bunga awal = Cosmos dari ItemPreset yang diganti spesies pulau. Kelapa: jalur `0x5662e0` → `BlockItemPreset<ID bagian>` per blok luar; berkasnya tidak ada di romfs yang tersedia [NATIVE] | GAMEPLAY_SCENARIO §10.4; `native_flag_refs.json` → `data.field_regrowth.new_island` |
| Gulma | Tahap = `Grow` 1–3. Tumbuh, sebar ke 8 tetangga (set 2, beda tinggi ≤ 5, salinan set 17), anak selalu tahap 1 dengan huruf lain, konversi musim per slot, ambang harian dan pulau baru: terbukti native. Ubin siram hanya berlaku pada hari simulasi pertama | GAMEPLAY_SCENARIO §10.3; `native_flag_refs.json` → `data.field_regrowth.plants_0x4b6e70.weed_rules` |
| Berikutnya | Prioritas pemilik (6 Nov): dulu topik yang sudah dimulai tetapi belum selesai — loader pulau end-to-end, air/terraform, cuaca di luar pola harian (undian serangga selesai 6 Nov) — lalu crafting/DIY, donasi museum, rumah/HHA, AI dan percakapan villager, mekanik alat, katalog; sesudahnya 5 item gameplay lama. `left_open` item `done` sudah diaudit (`done_audit`): entri yang terjawab item lain dipindah ke `resolved`, celah yang menyangkut topik prioritas dirujuk lewat `related_left_open` | `re_queue.json` → `items`, `done_audit` |
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
4. Cek: `python3 -m unittest discover -s acnh-re/tests -p 'test_gameplay_flow.py'`. Dengan data terekstrak, `main`, Unicorn, Capstone, dan NumPy tersedia, suite saat ini lulus 40/40 tanpa skip. Tanpa `main`, tes yang membaca instruksi native akan di-skip.

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
| `tools/nso_sandbox.py` (modul) | Emulasi fungsi native langsung dari NSO `main` (unicorn): relokasi MOD0, stub import libc, `Sandbox.call(va, args)`, `stub(va, fn)` |
| `python3 acnh-re/tools/gameplay_native.py` | Verifikasi native (emulasi) bacaan gameplay → `output/gameplay/gameplay_native.json`; tambah kasus baru di sini untuk menaikkan [PSEUDO] |
| `tools/visitor_schedule_native.py` (modul, dipanggil `gameplay_native.py`) | Rig emulasi pembuat jadwal `0xfd8a80`, validasi `0xfd9620`, pembungkus `0xfd8920` di atas layout save asli; model Python aturan §3.3–3.4 dibandingkan field per field |
| `tools/island_content_native.py` (modul, dipanggil `gameplay_native.py`) | Rig emulasi pemilih bunga pulau `0xf50ad0`, grup bunga `0xf50f50`/`0xf51040`, dan buah khas/saudara `0xf509e0` |
| `tools/island_placement_native.py` (modul, dipanggil `gameplay_native.py`) | Rig emulasi predikat penempatan `0x7ab350`, `0x7a2e10`, `0x4b5cc0` di atas objek kerja lapangan sintetis; `Field` mengatur pasir, air, tinggi, `CliffLevel`, dan set sel |
| `tools/island_weed_native.py` (modul, dipanggil `gameplay_native.py`) | Rig emulasi tumbuh gulma `0x4b6000`, sebar `0x4b63e0`, dan konversi musim `0x4ba120` di atas rig penempatan; lapisan item, baris `FgMainParam`, tinggi, dan RNG harian (satu aliran bersama model) dikontrol |
| `tools/creature_spawn_native.py` (modul, dipanggil `gameplay_native.py`) | Rig emulasi undian ikan `0x5b9ba0`/`0x5b98b0`, gerbang `0x5b9270`, slot jam ikan/serangga, dan urutan getter `0x95ebe0` atas tabel asli; `... table` menulis `output/gameplay/creature_spawn.json` |
| `tools/insect_spawn_native.py` (modul, dipanggil `gameplay_native.py`) | Rig emulasi undian serangga pulau `0x957940` dan saringan `AppearFg` `0x958570`; array getter `Prob` dibangun konstruktor asli `0x95ebe0`, getter per kolom membaca tabel asli |
| `tools/villager_move_native.py` (modul, dipanggil `gameplay_native.py`) | Rig emulasi pindah keluar `0xf847f0`, pemilih `0xf87670`, pindah masuk `0xf84f10`; memuat `NmlNpcParam.bcsv` lokal sebagai objek tabel game dan menjalankan inisialisator `0xcc89e0`/`0xcd4050` |
| `python3 acnh-re/tools/save_layout_native.py` | Bangun ulang `output/gameplay/save_layout.json` (layout member save, terbukti native) |

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
| 2026-11-04 | Harga lobak (`0xfc6d00`) dan stok toko (`0xfd0630`, `0xfc56c0`, `0xfc8760`, `0xfca870`) | `a15223c` |
| 2026-11-04 | Prosesor pergantian hari tersisa (`0xf7d4c0`, `0xf8b460`, `0xbdfd40`, `0xf6130`, `0x4ae640`, `0xd21110`, `0xfc1b80`, `0xf8f190`) | `5589793` |
| 2026-11-04 | Layout save lewat emulasi `0xf32fa0`; `nso_sandbox.py`, `save_layout_native.py` | `28efa7d` |
| 2026-11-04 | Verifikasi native 8 bacaan lewat emulasi (`gameplay_native.py`) | `a48fa4d` |
| 2026-11-04 | Sisa kecil: RNG thread, level rumah, posisi plaza, penulis `AbandonedHouse`, jalur pindah masuk, kategori 10, bungkus item, mode sesi, tanggal ulang tahun, stok toko, harga jual, `EarlyOrLate`, botol pesan, layout pemain | `a607f18` |
| 2026-11-04 | Verifikasi native prosesor fasilitas (`0xfcc300`, `0xf77050` tenda, `0xf26330`) | `5a1d474` |
| 2026-11-04 | Filter kelas turunan Nook dan selector state 2/3; query Daisy Mae `EventFlowQueryBoaCanSetKabu` terikat ke `SNPC_boc` dan 4 cabang native teruji; dampak flag skor dan syarat bit struktur diperjelas; caller `AbandonedHouse` dibatasi dengan call graph; build indeks dan suite 21/21 | `6b4a0e8` |
| 2026-11-04 | Alur input lobak dan layout numerik dikaitkan lewat EventFlow; skema publik disejajarkan dengan layout save (85/88 member, 143/151 vtable paths); scan empat NSO dan caveat lintas versi dicatat | `4bf8556` |
| 2026-11-04 | Peta stok mingguan Nook (ID 0–14999, bucket per hari, batch tujuh hari, pruning `0xfcf580`); transisi save OfficeLevel 1→2; suite 21/21 termasuk emulasi native | `2d090fa` |
| 2026-11-05 | Rencana RE berikutnya: 9 item open di `re_queue.json` (pindah villager dan jadwal native, kemunculan makhluk, regenerasi lapangan, Nook Miles/turnamen, keakraban, skor dan toko native, sisa nama simbolik); GAMEPLAY_SCENARIO §8 | `a535f5e` |
| 2026-11-05 | Pindah villager terbukti native: 15 kasus (`villager_move_native.py`); temuan baru: pemilihan villager baru dua tahap spesies → villager, pool `InitLive` ≠ 0 (391), kepribadian = indeks `NpcLooks`, jendela ulang tahun 9 hari game; sandbox menangani guard statik, `memcmp`, `VSNPrintf`, mutex | `db4a36b` |
| 2026-11-05 | Jadwal pengunjung terbukti native: pembuat `0xfd8a80` (1500 minggu), validasi `0xfd9620` (3000 hari), pembungkus `0xfd8920` (`visitor_schedule_native.py`); temuan: indeks validasi dari waktu yang dinormalkan driver ke 05:00, hari kosong dan kode ≥ 10 tidak diganti, tepat satu anggota kolam tertunda saat semua terbuka | `283ae70` |
| 2026-11-05 | Pemilihan ikan terbukti native (`creature_spawn_native.py`, 7 kasus): undian per posisi `0x5b9ba0`, undian persen `0x5b98b0`, gerbang `0x5b9270` (Sirakansu hanya saat hujan; mode sesi ≥ 2 tanpa sampah), slot jam ikan 3 dan serangga 6, getter `Prob` serangga = bulan × 6 + slot; klasifikasi air `0x59ca80` dan cadangan Funa/Medaka/Aji dari disassembly; tabel kandidat `creature_spawn.json`; GAMEPLAY_SCENARIO §8; sisa serangga jadi item `insect-spawn-draw` | `8e0085b`, `65d4a6d` |
| 2026-11-05 | Objek lapangan harian dan isi awal pulau (`0x4ae640`, `0x4b6e70`, sensus `0x7a3ef0`/`0x7a46f0`/`0x7a97e0`); 3 kasus native baru (`field_regrowth_native.py`); ItemPreset = `FgMainParam.UniqueID`; roadmap 5 item `island-*` | `b2ebdd6` |
| 2026-11-05 | Isi awal pulau (`island-initial-content`): zona `0x7b8b30` (mask plaza `0x51cc30`, `CliffLevel`), buah khas/saudara `0xf509e0`, bunga pulau `0xf51150`/`0xf50ad0` (8 spesies, mask bulan), Cosmos ItemPreset diganti spesies pulau, jalur kelapa `0x5662e0` → `BlockItemPreset` (isi [NATIVE]); koreksi bacaan `LandFruit`; 3 kasus native baru (`island_content_native.py`), total 44; suite 32/32 | `e7ee8c2` |
| 2026-11-05 | Aturan penempatan (`island-placement-rules`): atribut tanah (`Sand`/`WaterCheck`/`PlayerNoEntry`), tempat pohon `0x7ab350`, lereng `0x7a2e10`, batu `0x7aa3c0`, fosil `0x7ad6e0`, penempat umum `0x7aadc0` (gulma, kerang, lily), tetangga bebas `0x4b5cc0` (utara tidak pernah dipilih); arti set 1–4, 20–25; koreksi 32 → 5 + 26 bitset; 3 kasus native baru (`island_placement_native.py`), total 47; suite 35/35 | `91d9a0e` |
| 2026-11-05 | Sebaran gulma (`island-weed-spread`): tahap = `Grow`, tabel musim `0x3060b80`/`0x3060cb0` (slot 1A–3), tumbuh `0x4b6000`, sebar `0x4b63e0` (salinan set 17, 8 tetangga set 2, beda tinggi ≤ 5, anak tahap 1 berhuruf lain, berhenti di batas), konversi `0x4ba120` per slot; ambang harian (150) dan pulau baru (1300, masker pohon buah/batu); ubin 3 = bitmap siram `SaveFg`, hanya hari pertama; koreksi sumber ubin 3 penuh (flag save `+0x230`, bukan argumen 2 `0x7a5c60`); 4 kasus native baru (`island_weed_native.py`), total 51; suite 38/38 | `1d96e3e` |
| 2026-11-06 | Antrian disusun ulang menurut prioritas pemilik (15 item open: 4 topik yang sudah dimulai, 6 topik baru dengan titik masuk dari indeks string, 5 item lama); audit `left_open` seluruh item `done` | `793269c` |
| 2026-11-06 | Undian serangga (`insect-spawn-draw`): undian pulau `0x957940` dan saringan `AppearFg` `0x958570` terbukti native (`insect_spawn_native.py`, 2 kasus, total 53); kelompok `AppearFg`, batas per spesies `0x8ddbd0`; koreksi: `0xb56850`/`0xb53d20` = ketersediaan pulau misteri (`MysteryTour*Param`), bit lapangan `+0x13e1` = mode pulau misteri | `56f6b0b` |
| 2026-11-06 | Follow-up paralel parsial: generator pulau 8 draw RNG; region terrain 506 kasus; gerak pemain 9 fixture; producer grid NPC 12 konteks; cuaca 96 perbandingan; crafting resep nyata 5 bahan. Semuanya punya label batas bukti/reproducer; item antrean terkait tetap `open`. Detail: `ISLAND_LOADER_FOLLOWUP`, `ISLAND_WATER_TERRAFORM_FOLLOWUP`, `PLAYER_PHYSICS_FOLLOWUP`, `NPC_SOCIAL_FOLLOWUP`, `ECOLOGY_WEATHER_FOLLOWUP`, `PROGRESSION_SYSTEMS_FOLLOWUP` | `ef6357d`, `459d3f5`, `cbb3671`, `d7d29d6`, `985aa53`, `5ffeeb7`, `030295d` |
| 2026-11-06 | Museum: batas art/gyroid pada data 1.0.0 ditegaskan; producer byte marker `+0xb0d` ditelusuri ke `0xe68280`; jalur submission→SaveMuseum→ambang 20→flag→updater dipetakan dengan batas adapter/supplied-state yang jelas. Makna byte dan jalur live save/runtime masih open; `museum-donation` tetap di antrean | `166ba90` |
