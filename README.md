# Hasil RE ACNH 1.0.0

Paket hasil reverse engineering Animal Crossing: New Horizons versi 1.0.0 (build ID `7FC1BAFF976AECA414520CB89F4616CB`), sebagai referensi konversi ke engine lain (Godot). Proyek Godot dan sumber asli pengguna tidak diubah.

**Status:** pemetaan struktural seluruh data yang tersedia sudah lengkap. Semantik (perilaku) game masih parsial; setiap batas dicatat eksplisit. Jumlah kasus uji native bukan persentase penyelesaian game.

## Mulai dari sini

| Dokumen | Isi |
|---|---|
| [Handoff untuk sesi berikutnya](acnh-re/docs/HANDOFF.md) | Status singkat, setup data, alat, aturan, log sesi; antrian kerja di [re_queue.json](acnh-re/docs/re_queue.json) |
| [Workflow penggunaan data RE](acnh-re/docs/WORKFLOW.md) | Persiapan, ekstrak ZIP, file mana untuk apa, siklus satu tahap RE, verifikasi, kerja multi-agen |
| [Alur gameplay dari data](acnh-re/docs/GAMEPLAY_FLOW.md) | Alur prolog sampai konser K.K. dan loop setelahnya, dari 456 EventFlow dan 1.555 flag, dengan label bukti per langkah |
| [Skenario gameplay lengkap](acnh-re/docs/GAMEPLAY_SCENARIO.md) | Satu hari (pipeline pergantian hari native), satu minggu, satu tahun (kalender event, musim), siklus villager, pengunjung khusus, timeline progres dalam pergantian hari |
| [Kontrak data](acnh-re/docs/DATA_CONTRACT.md) | Format JSON hasil: manifest, BCSV, BYML, item, AAMP, EventFlow |
| [Laporan lengkap baseline](acnh-re/LAPORAN_AKHIR.md) | Sumber input, pemetaan data, temuan native, lampiran 164 tabel |
| [Frontier mekanik (JSON)](acnh-re/output/mechanics/continuation_frontier.json) | Yang sudah terbukti, yang masih terbuka, target fungsi berikutnya, total kasus terbaru |
| [Cakupan komponen UI/pulau (JSON)](acnh-re/output/ui_island/component_coverage.json) | Level S/L/C/U per komponen |
| [Cakupan dan yang belum diketahui (JSON)](acnh-re/output/coverage.json) | Ringkasan baseline yang dapat dibaca mesin |

## Status per area

| Area | Status | Rujukan |
|---|---|---|
| Format data (BCSV, BYML, AAMP, SARC, EventFlow) | Lengkap secara struktural: 1.171 berkas, 2.986 entri; nama kolom 1.957/2.048, key BYML 2.979/3.410 | [LAPORAN_AKHIR](acnh-re/LAPORAN_AKHIR.md) |
| Teks, UI, animasi (RomFS tambahan) | 965.426 pesan dalam 14 bahasa, 523 layout, 2.095 animasi UI, 83 state machine | [ADDITIONAL_ROMFS](acnh-re/docs/ADDITIONAL_ROMFS.md) |
| Alur cerita/progres | Rantai utama terpetakan dari EventFlow; 693 flag tanpa penulis EventFlow, penyelesaian bangunan dan pembuka K.K. dibaca dari pseudocode native (belum dieksekusi) | [GAMEPLAY_FLOW](acnh-re/docs/GAMEPLAY_FLOW.md) |
| Rumus yang terbukti native | RNG, cuaca hari biasa, kalender dan batas hari 05:00, genetika bunga, pembaca BYML, item 8 byte, resep, flag reset | [CALENDAR_FLOWERS](acnh-re/docs/CALENDAR_FLOWERS.md), [NATIVE_STAGE_WEATHER](acnh-re/docs/NATIVE_STAGE_WEATHER.md) |
| Tujuh mekanik (collision, gerak, terrain, ground, posisi, NPC/navigasi, item/crafting) | Parsial; helper inti teruji di context rekonstruksi | [FOCUS7_MECHANICS](acnh-re/docs/FOCUS7_MECHANICS.md), frontier JSON |
| Pembentukan pulau (template, pantai, terrain, PBC) | Parsial; selector, perakitan pantai dan konsumen tinggi PBC teruji | [ISLAND_TEMPLATE_SELECTOR_NATIVE](acnh-re/docs/ISLAND_TEMPLATE_SELECTOR_NATIVE.md) |
| Save, ekonomi (lobak, toko), multiplayer, spawn ikan/serangga, scheduler villager | Belum di-RE secara native; data tabel tersedia | [GAMEPLAY_FLOW §12](acnh-re/docs/GAMEPLAY_FLOW.md), [coverage.json](acnh-re/output/coverage.json) |
| Model 3D, audio, Havok | Sumber tidak ada di dump; hanya katalog referensi | [ADDITIONAL_ROMFS](acnh-re/docs/ADDITIONAL_ROMFS.md) |

Total kasus helper/blok native terbaru dicatat di satu tempat saja: `latest_phase.native_helper_cases_total` dalam [continuation_frontier.json](acnh-re/output/mechanics/continuation_frontier.json). Uji pulau dilaporkan terpisah di dokumen pulau.

## Unduh dan ekstrak

Hasil rinci baseline ada di lima ZIP [downloads/](downloads/), dan hasil RomFS tambahan di tiga ZIP [downloads/additional_romfs/](downloads/additional_romfs/). Masing-masing ZIP mandiri. Cara termudah adalah mengunduh repo lengkap ([ZIP repo](https://github.com/menuyul312-max/acnh-re-results/archive/refs/heads/main.zip)) atau melakukan clone.

Ekstrak kedelapan ZIP ke root repo **tanpa menimpa** file yang sudah ada. ZIP baseline berisi versi lama `acnh-re/README.md`, `acnh-re/LAPORAN_AKHIR.md`, dan `acnh-re/output/coverage.json`.

```bash
for z in downloads/*.zip downloads/additional_romfs/*.zip; do unzip -n -q "$z" -d .; done
```

Rincian, cara verifikasi, dan file yang wajib ada: [WORKFLOW §3](acnh-re/docs/WORKFLOW.md#3-persiapan).

- [Checksum lima ZIP baseline](downloads/SHA256SUMS.txt) · [Halaman release](https://github.com/menuyul312-max/acnh-re-results/releases/tag/hasil-re-2026-11-02)
- SHA-256 ZIP lengkap lokal sebelum dibagi: `52ad5f6ecf1a185b3ca40de5391822ee8109323378eec52cbdb651e003229af1`
- ZIP adalah snapshot 2 November 2026. Hasil sesudahnya tersimpan langsung di tree Git (`acnh-re/output/mechanics`, `ui_island`, `gameplay`).

## Fokus terbaru (terbaru di atas)

- **Pindah keluar dan pengisian slot villager** — [GAMEPLAY_SCENARIO §5.1–5.2](acnh-re/docs/GAMEPLAY_SCENARIO.md):
  - undian harian `5 × villager menetap + hari sejak percakapan pindah` persen, dengan RNG harian, jeda 15 hari, minimal 6 villager;
  - bobot pemilihan dari rata-rata `Friendship` (makin tidak akrab, makin mungkin pindah); dikecualikan yang berulang tahun ≤7 hari lagi, yang terakhir pindah masuk, dan yang terakhir dibujuk tinggal;
  - setelah dikonfirmasi: status slot 2 pada pergantian hari berikutnya, pergi sehari sesudahnya;
  - pengisian slot: peluang `(10 − n + plot kosong [+ AddPoint]) × 10%`, villager baru dari kepribadian yang paling sedikit.
- **Pembuat jadwal pengunjung mingguan** — [GAMEPLAY_SCENARIO §3](acnh-re/docs/GAMEPLAY_SCENARIO.md):
  - `0xfd8a80` membuat jadwal tiap Senin 05:00;
  - urutan penempatan: Mabel, Saharah, Kicks, lalu kolam acak Label/C.J./Flick/Gulliver dengan prioritas carry-over;
  - hari Celeste dipilih dari hari cuaca `Fine00`;
  - Wisp mengisi hari kosong;
  - validasi harian `0xfd9620` membatalkan entri atau menggantinya dengan Gulliver/Wisp;
  - layout member 0x78 byte dan kode 0–9 ada di `native_flag_refs.json` (`data.visitor_schedule`).
- **Jadwal pengunjung dan penghuni plot** — [GAMEPLAY_SCENARIO §3, §5, §6](acnh-re/docs/GAMEPLAY_SCENARIO.md):
  - kode pengunjung mingguan 1–8 → Gulliver, Label, Saharah, Mabel, C.J., Flick, Kicks;
  - aturan Daisy Mae (indeks hari 0), Celeste (slot `+0x74`, malam), dan Wisp (malam);
  - seed RNG harian `tahun×365+bulan+hari+GrowUpRandomFactor+0x1934`;
  - pemilihan penghuni plot (filter kepribadian [0,5,4], pemilih acak dengan bitset eksklusi);
  - alat baru [re_helpers.py](acnh-re/tools/re_helpers.py) dan [handoff](acnh-re/docs/HANDOFF.md).
- **Skenario gameplay lengkap** — [GAMEPLAY_SCENARIO](acnh-re/docs/GAMEPLAY_SCENARIO.md):
  - driver pergantian hari native `0xf53a70` dan urutan prosesornya;
  - jadwal aktif NPC, kalender event per belahan bumi, `SeasonCalendar`;
  - siklus villager: undangan dan kode alasan gagal, kontrak lahan, pindah masuk/keluar;
  - syarat Harvey dan slot mingguan Label;
  - timeline progres dalam hitungan pergantian hari;
  - konvensi query `NpcHouseNum` dan `VillageScoreCheck` dikonfirmasi dari pseudocode handler.
- **Alur gameplay dari data** — [GAMEPLAY_FLOW](acnh-re/docs/GAMEPLAY_FLOW.md) dan [tool](acnh-re/tools/gameplay_flow.py):
  - indeks penulis/pembaca 1.555 flag pada 456 EventFlow, pohon flow progres di [output/gameplay](acnh-re/output/gameplay/);
  - rumus bintang pulau (ambang Nature/Life, syarat ≥8 rumah NPC);
  - syarat konser K.K. (≥3★);
  - rantai toko → quest 3 rumah → Resident Services;
  - aturan case Bool (98,3% konsisten), dengan 7 uji di `tests/test_gameplay_flow.py`;
  - sisi native pergantian hari (`0xf545f0`): penyelesaian museum, toko, penjahit, campsite, Resident Services, dan pembuka konser K.K. dibaca dari pseudocode lewat rujukan string flag ([native_flag_refs.json](acnh-re/output/gameplay/native_flag_refs.json); 318 dari 693 flag native punya rujukan).
  - Tiga file Google Drive (4 Nov) sudah diverifikasi identik dengan input RomFS, ExeFS, dan `manifests` yang sudah diproses ([GAMEPLAY_FLOW §13](acnh-re/docs/GAMEPLAY_FLOW.md#13-pemeriksaan-tiga-file-google-drive-4-november-2026)).
- **Konsumen pantai dan terrain pulau** — [ISLAND_TEMPLATE_SELECTOR_NATIVE](acnh-re/docs/ISLAND_TEMPLATE_SELECTOR_NATIVE.md), [TERRAIN_RUNTIME](acnh-re/docs/TERRAIN_RUNTIME.md):
  - rangkaian `0x4de810→…→0x4e0c90` pada 36 template, 2.592 record tanpa mismatch;
  - selector kandidat bagian pantai;
  - 208 awalan tinggi PBC ke penulis `0x180d20`;
  - skala LandMaking 10 unit = 2×2 sampel PBC.
- **Audit PBC pulau dan ground** — [manifests_pbc_audit.json](acnh-re/output/ui_island/manifests_pbc_audit.json): indeks ground PBC, semantik material air, batas resolusi grid.
- **Selector template pulau** — [ISLAND_TEMPLATE_SELECTOR_NATIVE](acnh-re/docs/ISLAND_TEMPLATE_SELECTOR_NATIVE.md): 528 kasus, instruksi asli tanpa stub. Loader lengkap, perakitan pantai, dan air tetap parsial.
- **UI dan penataan pulau** — [UI_ISLAND_MAPPING](acnh-re/docs/UI_ISLAND_MAPPING.md), [ringkasan](acnh-re/output/ui_island/summary.json): 523 layout, 10.882 pane, 2.095 animasi UI dengan 16.162 track dan 92.038 keyframe, 36 template pantai, 96 bundel preset.
- **Registry wilayah** — [WORLD_REGISTRY_RELEASE](acnh-re/docs/WORLD_REGISTRY_RELEASE.md) (126 kasus), [TERRAIN_REGION_MUTATION](acnh-re/docs/TERRAIN_REGION_MUTATION.md) (164 kasus), [TERRAIN_REGION_CHECK](acnh-re/docs/TERRAIN_REGION_CHECK.md) (216 kasus).
- **Tujuh mekanik** — [FOCUS7_MECHANICS](acnh-re/docs/FOCUS7_MECHANICS.md), [peta JSON](acnh-re/output/mechanics/focus7/summary.json): 69 tabel, 55 graf AI, 292 parameter.
  - Lanjutan: [WORLD_NAV_BRIDGE](acnh-re/docs/WORLD_NAV_BRIDGE.md) (1.568 kasus), [NPC_NAVIGATION_KERNEL](acnh-re/docs/NPC_NAVIGATION_KERNEL.md), [RESIDENT_MAP_NPC_FOLLOWUP](acnh-re/docs/RESIDENT_MAP_NPC_FOLLOWUP.md), [ACTIVE_CONTEXT_FOLLOWUP](acnh-re/docs/ACTIVE_CONTEXT_FOLLOWUP.md), [MECHANICS_CONTINUATION](acnh-re/docs/MECHANICS_CONTINUATION.md).
- **Collision, kedekatan, terrain runtime** — [MECHANICS_RE](acnh-re/docs/MECHANICS_RE.md) (262.164 perbandingan blok, 235 state pemain), [COLLISION_RESPONSE](acnh-re/docs/COLLISION_RESPONSE.md) (62.702 kasus), [PROXIMITY_GROUND](acnh-re/docs/PROXIMITY_GROUND.md) (3.235 kasus), [TERRAIN_RUNTIME](acnh-re/docs/TERRAIN_RUNTIME.md) (1.791 kasus).
- **RomFS tambahan (2 Nov 2026)** — [ADDITIONAL_ROMFS](acnh-re/docs/ADDITIONAL_ROMFS.md), [ringkasan](acnh-re/output/additional_romfs/summary.json): 8.030/8.093 rujukan pesan EventFlow dan 8.074/8.208 nama item terhubung ke teks.
- **Baseline** — [LAPORAN_AKHIR](acnh-re/LAPORAN_AKHIR.md), [SDK/ExeFS tambahan](acnh-re/docs/ADDITIONAL_EXEFS.md), [kalender, cuaca dan bunga](acnh-re/docs/CALENDAR_FLOWERS.md), [log 34 uji integrasi](acnh-re/output/verification.log).

## Indeks dokumen

| Dokumen | Topik |
|---|---|
| [HANDOFF](acnh-re/docs/HANDOFF.md) | Titik mulai sesi berikutnya dan antrian kerja |
| [WORKFLOW](acnh-re/docs/WORKFLOW.md) | Cara memakai dan melanjutkan RE |
| [GAMEPLAY_FLOW](acnh-re/docs/GAMEPLAY_FLOW.md) | Alur gameplay awal–akhir dari EventFlow |
| [GAMEPLAY_SCENARIO](acnh-re/docs/GAMEPLAY_SCENARIO.md) | Skenario hari/minggu/tahun, villager, pengunjung |
| [DATA_CONTRACT](acnh-re/docs/DATA_CONTRACT.md) | Format output |
| [GITHUB_REFERENCES](acnh-re/docs/GITHUB_REFERENCES.md) | Rujukan publik dan batas versi |
| [ADDITIONAL_EXEFS](acnh-re/docs/ADDITIONAL_EXEFS.md) | Modul main/sdk/subsdk0/rtld dan kontrak input |
| [ADDITIONAL_ROMFS](acnh-re/docs/ADDITIONAL_ROMFS.md) | Pesan, BDLI, ASB, UI, shader |
| [NATIVE_STAGE_WEATHER](acnh-re/docs/NATIVE_STAGE_WEATHER.md) | Stage, pembaca BYML, flag, RNG, cuaca |
| [CALENDAR_FLOWERS](acnh-re/docs/CALENDAR_FLOWERS.md) | Kalender SDK, batas hari, genetika bunga |
| [C1_CONDITIONS](acnh-re/docs/C1_CONDITIONS.md) | Bytecode kondisi BGM |
| [MECHANICS_RE](acnh-re/docs/MECHANICS_RE.md) | Collision dan ledger seluruh sistem |
| [FOCUS7_MECHANICS](acnh-re/docs/FOCUS7_MECHANICS.md) | Peta tujuh sistem mekanik |
| [COLLISION_RESPONSE](acnh-re/docs/COLLISION_RESPONSE.md), [PROXIMITY_GROUND](acnh-re/docs/PROXIMITY_GROUND.md) | Collision, kedekatan, izin ground |
| [TERRAIN_RUNTIME](acnh-re/docs/TERRAIN_RUNTIME.md), [TERRAIN_REGION_CHECK](acnh-re/docs/TERRAIN_REGION_CHECK.md), [TERRAIN_REGION_MUTATION](acnh-re/docs/TERRAIN_REGION_MUTATION.md), [WORLD_REGISTRY_RELEASE](acnh-re/docs/WORLD_REGISTRY_RELEASE.md) | Terrain dan wilayah |
| [MECHANICS_CONTINUATION](acnh-re/docs/MECHANICS_CONTINUATION.md), [ACTIVE_CONTEXT_FOLLOWUP](acnh-re/docs/ACTIVE_CONTEXT_FOLLOWUP.md) | Bahan, posisi pemain, gerbang ground |
| [NPC_NAVIGATION_KERNEL](acnh-re/docs/NPC_NAVIGATION_KERNEL.md), [WORLD_NAV_BRIDGE](acnh-re/docs/WORLD_NAV_BRIDGE.md), [RESIDENT_MAP_NPC_FOLLOWUP](acnh-re/docs/RESIDENT_MAP_NPC_FOLLOWUP.md) | Navigasi NPC dan peta resident |
| [UI_ISLAND_MAPPING](acnh-re/docs/UI_ISLAND_MAPPING.md), [ISLAND_COAST_SLOTS](acnh-re/docs/ISLAND_COAST_SLOTS.md), [ISLAND_TEMPLATE_SELECTOR_NATIVE](acnh-re/docs/ISLAND_TEMPLATE_SELECTOR_NATIVE.md) | UI dan pembentukan pulau |

## Sumber dan lisensi

Executable asli (main.elf/NPDM, main, rtld, subsdk0, sdk), RomFS mentah, instalasi tool besar, dan direktori kerja tidak dimasukkan. Simpan sumber tersebut secara terpisah sesuai kontrak input; baca [petunjuk ExeFS](acnh-re/docs/ADDITIONAL_EXEFS.md) sebelum menjalankan pemeriksaan native.

Lisensi setiap rujukan tetap berlaku; lihat [NOTICE rujukan](acnh-re/tools/external/NOTICE.md). Tidak ada lisensi umum baru yang diberikan untuk konten game.
