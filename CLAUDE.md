# CLAUDE.md

Repo hasil reverse engineering Animal Crossing: New Horizons **1.0.0**. Dokumen dan pesan commit berbahasa Indonesia; kode dan nama field berbahasa Inggris.

## Mulai dari sini

1. Baca `acnh-re/docs/HANDOFF.md`. Isinya status, setup data, alat, aturan, dan log sesi.
2. Ambil pekerjaan dari `acnh-re/docs/re_queue.json`: item pertama dengan `status: "open"`.
3. Baca `acnh-re/docs/GAMEPLAY_FLOW.md` atau `GAMEPLAY_SCENARIO.md` hanya bagian yang relevan dengan item itu.

Jangan membaca seluruh repo. Banyak file JSON berukuran megabyte; query dengan `acnh-re/tools/re_helpers.py` atau Python.

## Data lokal

Hasil baseline ada di ZIP `downloads/` (lihat `acnh-re/docs/WORKFLOW.md` §3). Ekstrak dengan `unzip -n` agar file git tidak tertimpa. ExeFS `main` untuk `rodata`/`disasm` disimpan di `acnh-re/inputs/additional_exefs/` (di-ignore; minta ke pemilik repo).

## Aturan

- Alamat memakai ELF VA; pseudocode Ghidra = ELF+0x100000.
- Setiap klaim diberi label bukti: [EF] EventFlow, [TBL] tabel, [PSEUDO] pseudocode/disassembly, [NATIVE] belum dibaca, atau terbukti native (emulasi).
- Repo publik: jangan meng-commit teks dialog, aset, executable, atau link dump game.
- Area mekanik dan pembentukan pulau (`output/mechanics`, `output/ui_island`) dikerjakan agen lain; jangan diubah tanpa diminta.
- Commit per tahap, lalu push ke `main`. Perbarui log di `HANDOFF.md` dan `re_queue.json`.
- Tes alur gameplay: `python3 -m unittest discover -s acnh-re/tests -p 'test_gameplay_flow.py'`.
