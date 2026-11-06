# Follow-up runtime UI/HUD: BND1 dan hit-test sentuh

Audit ini menelusuri satu jalur: pane BND1 bernama `B_Hit`, binding pane pada controller, lalu pengujian geometri pada jalur pointer sentuh. Semua klaim native di sini bersifat statis untuk ACNH 1.0.0; tidak ada emulasi native atau capture game.

`[TBL]` Katalog aset berisi 158 record BND1 dan 2 record SCR1. Delapan belas record BND1 bernama `B_Hit`; masing-masing memiliki record CNT1 pada layout yang sama dengan binding `B_Hit:Hit`. Pemasangan tersebut mencakup 11 `ButtonNormal`, 4 `ButtonRepeat`, dan 3 `ButtonCheck`. Daftar pasangan layout, ukuran BND1, serta sumbernya ada di [bnd1_hit_test_trace.json](../output/ui_hud/runtime_followup/bnd1_hit_test_trace.json).

`[PSEUDO]` Konstruktor kontrol `0x14821d0` memanggil `0x14885b0` pada `0x14827c4`. Helper itu mencari `Cursor` dan `P_BtnFocusKey`, lalu mencari `C_Cursor` dan `B_Hit` sebagai fallback. Pointer hasilnya disimpan pada field kontrol `+0x68` dan `+0x70`; cabang `B_Hit` hanya terbukti sebagai fallback pada helper binding tersebut. Kode ini membaca nama pane, sementara label `BND1` berasal dari pencocokan aset, jadi hubungan jenis pane ke implementasi native tetap berupa crosswalk statis.

`[PSEUDO]` Pada jalur sentuh, `0x14b94c0` memanggil traversal `0x14b8850` di `0x14b958c`, lalu menyimpan node hasil pada offset `+0x38` record pointer di `0x14b9594`. Traversal memeriksa node dan keturunannya melalui `0x14b7820`, memakai child link `+0x8` dan sibling link `+0x18`. Jalur lanjut yang sudah dipetakan mengirim target tersimpan melalui `0x14b8950`, lalu traversal kontrol `0x14b7a10` mencocokkan target itu.

`[PSEUDO]` Helper `0x14b7820` membaca dua persegi panjang float dari offset node `+0x30..+0x3c` dan `+0x40..+0x4c`. Jika field terkait persegi panjang kedua pada `+0x28` tidak null, instruksi AArch64 memilih batas yang beririsan sebelum membandingkan titik sampel dengan rectangle hasilnya. Ini membuktikan ada perpotongan geometri pada hit-test. Bukti yang ada tidak memberi nama semantik untuk rectangle kedua, sumber koordinat, atau aturan prioritas saat beberapa node cocok.

Batas pentingnya adalah hubungan pointer `B_Hit` belum terbukti sampai rectangle node yang dibaca oleh `0x14b7820`. Tidak ada def-use atau call edge statis yang mengikat field kontrol `+0x68` ke field rectangle hit-test. Karena itu audit ini tidak menyimpulkan BND1 `B_Hit` menentukan target sentuh, tidak menyebut rectangle kedua sebagai clip, dan tidak menghubungkan setter `ScissorPane` ke perintah scissor GPU. Pemilihan hit target dari node yang tumpang tindih dan koordinat ruang layar juga masih terbuka.

`[PSEUDO]` Reproduksi disassembly raw pada ExeFS `main` dengan hash `f8d248109ff72999b4600ae3749f8c7397fb960f7ad3ab8dee3018ae9e14e900`:

```sh
python3 acnh-re/tools/ui_hud_dispatch_disasm.py \
  0x14827a0:0x60 0x14885b0:0x278 0x14b7820:0x1f0 \
  0x14b8850:0xf8 0x14b94c0:0x1e0
```

Disassembler memakai LLVM lokal. Tidak ada uji native; seluruh klaim mengikuti label `[TBL]` untuk aset dan `[PSEUDO]` untuk analisis kode.
