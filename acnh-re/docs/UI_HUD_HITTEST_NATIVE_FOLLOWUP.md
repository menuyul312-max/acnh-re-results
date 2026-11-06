# UI/HUD hit-test native follow-up

Tanggal: 6 November 2026. Sumber: ACNH 1.0.0 ExeFS `main`, SHA-256 `f8d248109ff72999b4600ae3749f8c7397fb960f7ad3ab8dee3018ae9e14e900`.

## Temuan tambahan

Kontrol button memang mencari pane bernama `B_Hit`. Helper `0x14885b0` menyimpan lookup tersebut pada field kontrol `+0x70` sebagai fallback; jika `+0x68` juga kosong, ia menyalin pointer fallback itu ke `+0x68`. Fungsi `0x14888b0` membaca `+0x70`, lalu `+0x68`, dan mengirim pane terpilih ke `0x14c80d0`. Caller `0x148b2b0` memakai hasilnya sebagai syarat memilih kontrol. Dengan demikian `B_Hit` terhubung secara native ke pemeriksaan visibilitas/aktivasi pane dalam kontrol button, selain crosswalk statis BND1 dan CNT1 yang tercatat sebelumnya.

Jalur ini belum membuktikan pointer `B_Hit` sama dengan pane yang dipakai oleh pohon hit-test. Tidak ada def-use yang ditemukan dari kontrol `+0x70/+0x68` ke node `+0x20` atau `+0x28` yang dipakai oleh `0x14b7820`. Identitas instance BND1 dan geometri yang diuji masih belum tertutup.

## Geometri batas dan prioritas hit

`0x14b7820` memeriksa pane dan rantai parent melalui `0x14c80d0`, lalu menguji titik terhadap rectangle pertama pada node `+0x30..+0x3c`. Jika pointer node `+0x28` non-null, ia menormalisasi rectangle kedua (`+0x40..+0x4c`) dan menguji irisan kedua rectangle itu. Uji titik memakai batas inklusif. `0x14b84f0` memperbarui rectangle dengan mengambil Pane pointer di `+0x20` dan `+0x28`, kemudian menulis hasil transform ke rectangle pertama dan kedua. `0x14b87b0` memasukkan node anak ke daftar sibling dan, bila bit `0x40` pada flag node aktif, menyalin pointer `parent+0x28` ke `child+0x28`. Ini membuktikan bahwa rectangle kedua memakai konteks batas yang diwariskan dari parent; nama semantiknya tidak tertulis di kode dan belum dapat dipastikan sebagai clipping gambar.

Walker native `0x14b8850` menguji node biasa lebih dahulu, lalu menelusuri child melalui `+0x8` dan sibling melalui `+0x18`. Node yang lolos mengganti kandidat sebelumnya; pada urutan depth-first yang dikendalikan, hit terakhir menang. Cabang khusus dengan bit `0x200` aktif dan bit 0 mati menguji node dengan mode geometri lain dan langsung mengembalikannya jika cocok. Urutan ini membuktikan prioritas traversal untuk flag/link yang diberikan; ia tidak membuktikan urutan visual/Z dari layout nyata.

Runner [ui_hud_hit_geometry_native.py](../tools/ui_hud_hit_geometry_native.py) mengeksekusi instruksi asli untuk pemeriksaan visibilitas, irisan rectangle, dan walker. Ia membandingkan 18 kasus tanpa mismatch: enam kasus visibilitas, enam geometri batas, dua pewarisan pointer batas, dan empat urutan pemilihan hit. Pada dua kasus pewarisan, helper relasi-list `0x14d9aa0`/`0x14d9990` distub; bytecode native `0x14b87b0` yang menyalin pointer tetap dieksekusi. Pada empat kasus walker, hanya predikat geometri `0x14b7820` yang distub agar urutan kandidat dapat dikontrol. Hasil rinci ada di [native_geometry_priority.json](../output/ui_hud/runtime_followup/native_geometry_priority.json).

Jalankan dari root worktree:

```sh
PYTHONPATH=/workspace/acnh-re/.deps python acnh-re/tools/ui_hud_hit_geometry_native.py
```

## Bagian yang masih terbuka

- Pointer `B_Hit` pada kontrol button belum terbukti identik dengan Pane pointer node hit-test, walaupun native memakai `B_Hit` untuk gate visibilitas button.
- Pointer batas kedua diwariskan dari parent saat bit `0x40` aktif dan dipotongkan terhadap batas pertama. Kode tidak memberi nama field itu sebagai clip/scissor, sehingga peran render dan peran interaksi tetap perlu dibedakan lewat bukti lebih lanjut.
- Urutan hit terbukti sebagai urutan traversal child/sibling untuk fixture. Hubungannya dengan urutan pane BFLYT, stacking visual, dan pilihan target saat event UI/game nyata belum teramati.
- Jalur scissor generik ditemukan terpisah dari objek `ScissorPane` viewport: pasangan `0x14c8fe0`/`0x14c9250` mengiris serta memulihkan rectangle di stack; `0x14c90e0` memanggil `0x19a9960`, yang memuat pointer API dari slot resolver `nvnCommandBufferSetScissor`. Itu membuktikan pemanggil GPU scissor pada context tersebut, tetapi belum menghubungkannya dengan objek `ScissorPane` yang dibuat di `0x1496460`.
- Tidak ada capture game sinkron, sehingga kecocokan titik layar, transform, skala viewport, dan pixel belum tervalidasi.

Reproducer statis untuk resolver/call path: [ui_hud_scissor_static_trace.py](../tools/ui_hud_scissor_static_trace.py), dengan hasil [scissor_static_path.json](../output/ui_hud/runtime_followup/scissor_static_path.json). Jalankan `PYTHONPATH=/workspace/acnh-re/.deps python acnh-re/tools/ui_hud_scissor_static_trace.py --output-root /workspace/acnh-re/output`.
