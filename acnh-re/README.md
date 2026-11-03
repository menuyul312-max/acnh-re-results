# ACNH: sumber rekayasa balik untuk konversi berikutnya

Seluruh B_data yang tersedia sudah dibaca secara struktural. Semantik seluruh game belum terpetakan 100%; batas dan field yang belum diketahui dicatat, tanpa mengubah proyek Godot asal.

- [Laporan temuan, keberhasilan, validasi, dan batas cakupan](LAPORAN_AKHIR.md).
- [Lanjutan terbaru: terrain runtime, bitset dan evaluator NPC](docs/WORLD_NAV_BRIDGE.md): 1.568 kasus tambahan; total 1.135.577 helper/blok. Ketujuh sistem tetap parsial.
- [Manifest sumber](output/manifest.json), [inventaris seluruh paket](output/source_inventory.json), [cakupan yang dapat dibaca mesin](output/coverage.json).
- [Perubahan dari laporan sebelumnya](output/progress_since_previous.json).
- [Katalog tabel JSON terbaru](output/schemas/catalogue.json), [katalog aset JSON](output/assets/catalogue.json), [kontrak data](docs/DATA_CONTRACT.md).
- [BYML dengan nama field pulih](output/byml_resolved/catalogue.json), [kamus descriptor](output/schemas/byml_names.json), [word item dan penempatan](output/items/catalogue.json), [uji native item](output/items/native_verification.json).
- [Dispatch native](output/binary/event_handlers_resolved.json), [terrain](output/relations/terrain_native.json), [resep](output/relations/recipe_materials_native.json), [kurva](output/environment/curves.json), [tekstur](output/environment/textures.json).
- [Stage dan actor](output/stage/catalogue.json), [cuaca dan validasi native](output/weather/native_verification.json), [RNG](output/random/native_rng.json), [predicate flag](output/flags/reset_policy_native.json), [kontrak dan batas](docs/NATIVE_STAGE_WEATHER.md).
- [ExeFS tambahan dan simbol SDK](output/native_modules/summary.json), [BYML tanpa stub SDK](output/native_modules/linked_byml_verification.json), [konfigurasi suara NPC](output/npc/voice_configuration_native.json), [kontrak input](docs/ADDITIONAL_EXEFS.md).
- [Kalender dan batas hari](output/calendar/native_verification.json), [cuaca lintas SDK](output/weather/native_linked_verification.json), [genotipe bunga](output/flowers/genotypes.json), [gen default](output/flowers/default_genes.json), [kasus siklus](output/flowers/growth_cycles.json), [kontrak](docs/CALENDAR_FLOWERS.md).
- [Field belum bernama beserta bukti](output/schemas/unresolved_evidence.json), [indeks SQLite](output/index.sqlite), [status dekompilasi](output/binary/decompilation_summary.json).

Nilai raw dan provenance tetap otoritatif. Nama/hash kandidat, pseudocode otomatis, dan struktur yang valid dibedakan dari perilaku yang sudah diverifikasi native.
