# Pemakaian lima berkas ExeFS tambahan

Kelima unggahan dapat digunakan untuk melanjutkan RE. Sumber disimpan tanpa perubahan pada `inputs/additional_exefs/`; paket awal dan proyek Godot tetap utuh. Ini unggahan pengguna, bukan hasil pencarian dump dari repo publik. [Inventaris, hash, dan build ID](../output/native_modules/summary.json).

Tahap lanjutan sudah menautkan relocation untuk helper kalender, memverifikasi batas hari 05.00 melalui SDK asli, dan memperluas cuaca serta genetika bunga. [Kontrak dan hasil baru](CALENDAR_FLOWERS.md). Cakupan satu fungsi strcmp di audit awal tetap dicatat terpisah dari pengujian modul berikutnya.

| Berkas | Hasil pemeriksaan | Kegunaan |
|---|---|---|
| `main` | NSO0; build ID ACNH 1.0.0; ketiga segmen identik dengan `main.elf` lama | Semua alamat dan temuan native lama tetap berlaku |
| `sdk` | NSO0; SONAME `nnSdk.nss`; 25.042 simbol dinamis | Menyediakan ekspor bagi 880 impor main, termasuk implementasi library/SDK yang sebelumnya tidak tersedia |
| `subsdk0` | NSO0; 11.514 simbol dinamis | Menyediakan ekspor bagi 18 impor main; dapat ditelusuri untuk jalur library multimedia |
| `rtld` | NSO0; 20 simbol dinamis | Referensi loader, startup, relocation dan penghubungan modul |
| `main.npdm` | Title ID `01006f8002326000`; descriptor efektif cocok dengan NPDM lama | Metadata proses dan hak akses; kedua versi NPDM dipertahankan |

Semua 12 segmen executable berhasil didekompresi dan SHA-256 cocok dengan hash header NSO. Hash ini memeriksa integritas segmen; signature kriptografis NPDM tidak diverifikasi. NPDM mempunyai 510 byte berbeda, seluruhnya dalam region signature ACID dan kunci publik 512 byte. Semua bytes di luar region tersebut identik. [Perbandingan terperinci](../output/native_modules/npdm_comparison.json).

## Simbol dan alamat

Total 37.517 simbol dinamis tercatat. Sebanyak 898 dari 910 impor main mempunyai kecocokan ekspor unik. Dua belas yang belum cocok mempunyai binding `STB_WEAK`: empat marker `__rel_*`, delapan fungsi `glslc*`. Caller dan jalur fallback tetap perlu ditelusuri untuk menentukan dampak ketiadaan simbol itu. Semua lokasi relocation impor dipertahankan pada [import_resolution.json](../output/native_modules/import_resolution.json).

VA SDK, rtld, dan subsdk0 relatif ke modul masing-masing. VA `0x4d7900` pada SDK adalah fungsi `strcmp`, berbeda ruang alamat dari VA dengan angka sama pada main. Alamat pseudocode Ghidra main memakai tambahan `0x100000`; angka itu bukan load base universal bagi semua modul. Penghubungan runtime penuh masih memerlukan load base, relocation, TLS, initializer, dan layanan OS.

## Pemakaian yang sudah terbukti

Fungsi asli `strcmp` SDK ditautkan ke GOT main `0x32cede0` memakai relocation `R_AARCH64_JUMP_SLOT`. PLT, instruksi main, dan instruksi SDK tidak diubah. Emulasi hanya memetakan text SDK yang diperlukan fungsi mandiri ini; tidak menjalankan constructor/syscall SDK lainnya.

67.714 perbandingan strcmp cocok, mencakup semua pasangan byte unsigned, alignment, prefix, UTF-8, dan string panjang. Seluruh 2.313 BYML kemudian diuji ulang memakai instruksi asli main dan SDK: 2.546.185 pemeriksaan cocok, dengan 84.560 panggilan strcmp asli dan nol stub. [Uji strcmp](../output/native_modules/strcmp_native_verification.json), [disassembly SDK](../output/native_modules/sdk_strcmp.asm), [uji BYML lintas modul](../output/native_modules/linked_byml_verification.json).

Audit lama dengan pengganti strcmp tetap disimpan sebagai pembanding. Dua audit membaca korpus yang sama; jumlah entry tidak dijumlahkan sebagai cakupan data baru. Pengujian Stage/ExitFlowchart lama mempunyai batas stub masing-masing seperti yang tercatat pada hasilnya.

Pemetaan suara NPC juga bertambah. Enam kolom tanpa nama, pada seluruh 459 baris NmlNpcParam/SpNpcParam, terikat melalui kode asli ke byte konfigurasi +44/+45/+46. Seluruh nilai byte dan kombinasi metadata yang hilang diuji; fallback 5/4/1. Ada 995 pemeriksaan tanpa mismatch atau stub. Nama asli dan makna akustik tiga byte tersebut belum diketahui. [Bukti dan pointer raw](../output/npc/voice_configuration_native.json).

## Pemindaian nama gameplay pada modul yang tersedia

Pemindaian segment hasil dekompresi mencakup empat NSO yang ada (`main`, `rtld`, `subsdk0`, `sdk`) dan sembilan nama gameplay terkait blocker. Ketiga modul selain `main` memiliki nol kecocokan string untuk seluruh sembilan nama tersebut. `main` sendiri memberi kecocokan untuk nama save, skor pulau, dan halaman UI yang memang sudah dirujuk di peta fungsi.

Pemindaian RTTI-like menemukan lima nama pada `main`: dua anchor `nn::util::IntrusiveListNode` dan tiga vtable ABI C++; tidak ada nama kelas game. `subsdk0` dan `sdk` memang membawa banyak nama C++ (1.350 dan 2.557), tetapi tidak ada satu pun nama target gameplay yang dicari. Hasil ini memperkuat batas bahwa modul tambahan yang tersedia tidak menyediakan nama bagi 151 vtable save maupun identitas dispatch `AbandonedHouse`; identitas itu tetap terbuka. Ini bukan klaim bahwa seluruh ExeFS sudah tersedia. [Hasil rinci dan hash](../output/native_modules/gameplay_symbol_scan.json).

## Kelanjutan yang kini terbuka

- Menelusuri implementasi SDK dari impor main yang sudah bernama, termasuk file, waktu, save, memory, input, dan audio.
- Mencocokkan nama struktur save dari metadata publik menghasilkan kandidat lintas versi, tetapi tidak menggantikan RTTI dari build lokal. Alat [`save_layout_schema_crosswalk.py`](../tools/save_layout_schema_crosswalk.py) membaca skema bernama `save_schema_111_103.json` dari [Treeki/CylindricalEarth](https://github.com/Treeki/CylindricalEarth/blob/bb09c0ee71a4aa6011de088b88ea55fdee0bf6e9/savefile/save_schema_111_103.json) dan menulis `output/gameplay/save_layout_external_crosswalk.json`.
- Menguji helper SDK lain setelah menetapkan dependensi dan state yang dibacanya.
- Memetakan rtld, relocation lintas modul, TLS dan initializer sebelum mencoba cakupan runtime yang lebih luas.
- Menelusuri fungsi multimedia dari subsdk0 dan konsumen konfigurasi suara NPC.
- Tetap menyelesaikan key/kolom RomFS yang belum bernama melalui fungsi konsumen yang tersedia.

Executable ini tidak menambahkan mesh, animasi, waveform audio, VFX, shader atau arsip Havok yang hilang dari subset RomFS. Implementasi API dapat dipelajari, tetapi bytes resource tersebut tetap memerlukan sumber asetnya.

## Reproduksi

Letakkan lima berkas asli di `inputs/additional_exefs/` dengan nama yang sama. Python memakai `liblz4.so.1` sistem melalui fungsi dekompresi berbatas ukuran; Rust/Godot/game tidak dijalankan. `requirements-native.txt` memuat dependensi disassembly/emulasi.

```bash
python tools/exefs_modules.py
python tools/exefs_gameplay_scan.py --input-root <folder>/inputs/additional_exefs
python tools/save_layout_schema_crosswalk.py --schema <folder>/save_schema_111_103.json
python tools/linked_sdk_verify.py
python tools/npc_voice.py
python -m unittest discover -s tests -v
```

`build_all.py` menjalankan tahap ExeFS tambahan bila kelima input tersedia. Input executable asli dan hasil dekompresi kerja tidak dibundel dalam ZIP bukti; simpan unggahan secara terpisah bersama paket awal. Hasil JSON, disassembly, checksum, parser, dan tes ikut paket hasil.
