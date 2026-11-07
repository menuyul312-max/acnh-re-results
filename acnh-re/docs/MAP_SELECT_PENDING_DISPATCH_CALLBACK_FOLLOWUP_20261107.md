# Follow-up native: request ID 42, result dispatch, and page callback registration

## Kesimpulan

Trace tambahan memisahkan tiga jalur yang sebelumnya tampak berdekatan. `UIMapSelectHandling` mengirim ID **42** melalui singleton registry indeks **8** ke slot pending pada offset `+0x21c`; polling action membaca status singleton yang sama. Jalur result/dispatch memakai field lain (`+0x210` untuk ID aktif dan `+0x228` untuk ID hasil), dan melakukan pencocokan alias ID. Tidak ditemukan perpindahan nilai pending `42` ke field aktif/result tersebut atau call edge dari manager ke objek halaman.

Cell relocation `0x3307bb8` kini memiliki consumer yang teridentifikasi: fungsi registrasi state halaman memuat callback `0x1242fa0` dari cell itu, memasangkannya dengan callback `0x1243110`, lalu mendaftarkan state index 3 bernama `State::cPlay`. Callback `0x1242fa0` memanggil fungsi `0x1243980`, yang memasok string `CharaMakeMap` ke helper resource/layout. Ini membuktikan edge dalam kandidat page/callback/layout, bukan edge dari request ID 42.

Kandidat controller page menyimpan address point tabel fungsi yang memuat entry ke pembuat `MapSelectPage`, tetapi titik dispatch tak langsung ke entry itu belum teridentifikasi. Informasi layout tetap punya batas sendiri: child map-card mengikat tekstur `Capture^t`, namun pengisi/render dinamisnya belum terbukti. `SaveSetFromUIResult {SaveType:cVillage}` tetap hanya operasi penyimpanan hasil UI pada EventFlow; trace ini tidak menetapkan preset terrain atau jalur generasi terrain.

## Bukti tambahan

Semua alamat native di bawah adalah ELF VA pada `A_logic/main.elf`, kecuali alamat tabel BSS yang disebut sebagai alamat analisis Ghidra dan alamat ELF padanannya. Relasi `[PROVED]` berasal dari raw instruction/relocation dan struktur data analisis; istilah “manager”, “page controller”, dan “result object” adalah label deskriptif, bukan nama class publik yang terverifikasi.

| Bukti | Relasi | Batas klaim |
|---|---|---|
| `[PROVED]` request | callback action `0x34b700` meneruskan ID dari action `+0xb8` ke `0x158ff60`; helper itu memanggil getter `0x15411b0(8)`, lalu cabang aktif ke `0x11eca30` | Action constructor sebelumnya menulis `42` ke `+0xb8`. `0x11eca30` hanya menerima bila field `+0x21c == -1`, lalu menulis ID ke `+0x21c`, status ke `+0x220`, dan membersihkan `+0x224`. Tidak tampak penulisan ke `+0x210` atau `+0x228` pada jalur ini. |
| `[PROVED]` poll | action poller `0x34b760` memanggil `0x1590180`; helper mengambil registry index 8 dan memanggil `0x11ecbd0` | Predicate `0x11ecbd0` bernilai aktif bila `+0x21c != -1` **atau** `+0x228 != -1`. Ini membuktikan polling slot state/result bersama, bukan dispatch ke halaman. Jalur pasangan action poll juga mencapai helper singleton-index-8 `0x15903c0`. |
| `[PROVED]` field state berbeda | `0x11ecaa0` mengecek pending `+0x21c`, membandingkan ID input dengan current ID `+0x210` melalui tabel ekuivalensi, lalu dapat menyimpan pending ID | Ini merupakan setter lain, tidak terbukti sebagai tujuan callback action `0x158ff60 → 0x11eca30`. Offset sama tidak boleh dianggap sebagai transisi otomatis. |
| `[PROVED]` pencocokan result | matcher `0x11ed010` membaca current ID `+0x210` dan result ID `+0x228`; bila tabel ekuivalensi cocok, ia meminta object/service berdasarkan current ID melalui `0x154e5d0`, lalu memanggil entry vtable pertama object itu dengan interface object global | Tabel di-init oleh fungsi `0x11ee260` pada alamat analisis `0x3731310` (ELF VA BSS `0x3631310`). Elemen indeks 42 bernilai 41; karena itu result ID 42 dapat cocok dengan current ID 41. Ini tidak menunjukkan bahwa pending ID 42 dari `+0x21c` telah menjadi current ID 41 atau menghasilkan page callback. |
| `[PROVED]` consumer result lain | caller matcher `0x11ed010` mencakup `0x11eceb0` (call PC `0x11ecfb8`), `0x11ed710` (`0x11ed724`), `0x11ed890` (`0x11ed9a8`), dan `0x11eda50` (`0x11eda68`) | Caller memproses/memompa jalur result dan state. Nama semantik eksternal tiap routine tidak teridentifikasi. |
| `[PROVED]` getter hasil | wrapper `0x1590250` mengambil singleton index 8 lalu memanggil `0x11ecc00`; getter itu membandingkan `+0x228` dengan argumen ID dan byte hasil `+0x22c`, kemudian mencari object berdasarkan current ID `+0x210` | Caller langsung terindeks yang ditemukan untuk wrapper ini adalah `0x2f48b0`, dengan argumen ID `0x30` (48), bukan 42. Poller action yang diketahui memakai `0x1590180`, bukan getter hasil ini. |

Temuan pemetaan ID menjelaskan kenapa pencarian konstanta saja mudah menyesatkan: nilai 42 juga muncul sebagai **indeks result** yang ekuivalen dengan current ID 41. Jalur pengiriman action yang dibuktikan tetap menulis 42 ke pending `+0x21c`; penggunaan alias pada matcher result tidak membuktikan hubungan objek halaman.

## Consumer cell callback dan page candidate

Fungsi registrasi state `0x1242ce0` memproses record callback per state. Untuk state index **3**, instruksi di PC `0x1242dec` memuat isi cell `0x3307bb8` (`0x1242fa0`) dan PC `0x1242df4` memuat cell berikut `0x3307bc0` (`0x1243110`). Fungsi menyimpan dua pointer itu pada record state halaman (field record `+0x10` dan `+0x20`), memberi nama `State::cPlay` dari string VA `0x29570e1`, menetapkan index 3, lalu memanggil registrar `0x1f064b0` pada PC `0x1242e1c`. Record serupa mengikat `cIdle`, `cAppear`, dan `cDisappear` ke slot lain. Karena cell `0x3307bb8` adalah bagian dari urutan relocation code-pointer `0x3307ba0–0x3307bf8`, ia **bukan** entry tabel dispatch manager index 8; consumer yang terlihat adalah registrasi callback state halaman.

`0x1242fa0` memeriksa page field `+0x218`, lalu memanggil `0x1243980` di PC `0x1242fc8`. Fungsi `0x1243980` membaca data lewat page field `+0x210` dan nested field `+0x3f8`; ia membentuk string `CharaMakeMap` (VA `0x294cbc3`) dan memasukkannya ke helper `0xb1aa20` pada PC `0x1243a0c`, diapit helper setup/teardown resource/layout. Dengan demikian cell `0x3307bb8 → 0x1242fa0 → 0x1243980 → helper dengan nama CharaMakeMap` adalah rantai kandidat layout yang didukung call/relocation. Tidak ditemukan edge dari submission ID 42 menuju record `State::cPlay` itu.

Objek controller halaman adalah kandidat terpisah. Constructor `0x12421a0` memuat cell vptr `0x3307b70` (relokasi ke base `0x3110dd0`), menambah `0x10`, lalu menyimpan address point `0x3110de0` pada objek. Sequence relocated di `0x3110de0` memiliki entry `0x3110df8` → `0x12421a0` (slot 3) dan `0x3110ea8` → `0x12424c0` (slot 25). Fungsi `0x12424c0` menyiapkan nama `MapSelectPage`, memanggil creator `0x1242550`, dan menyimpan hasil page pada field `+0x210` objek pemanggil. Creator mengalokasikan `0x5c0` byte serta menjalankan constructor/helper attachment.

Tabel `0x3110de0` merupakan sequence pointer fungsi relocated yang disimpan sebagai vptr oleh constructor, sehingga layak disebut kandidat tabel dispatch objek. Namun, call site tak langsung yang memilih slot 25 belum ditemukan; `0x12424c0` tidak memiliki caller langsung terindeks. Vptr page hasil konstruksi pada cell `0x3307b48` (address point `0x3110b38`) dan callback-state cells `0x3307ba0...` adalah struktur lain. Offset `+0x210` pada objek page controller juga bukan field `+0x210` milik singleton manager hanya karena offset-nya sama.

## Bukti yang belum menutup gap

- Dari callback action, bukti berakhir pada pending field singleton `+0x21c`. Tidak ditemukan instruksi yang menyalin pending ID ke current ID `+0x210`, membentuk result ID `+0x228`, atau memilih `MapSelectPage`/callback `State::cPlay`.
- Result matcher `0x11ed010` dan getter `0x11ecc00` menunjukkan bagaimana manager dapat mencari object berdasarkan current ID, tetapi tidak mengungkap caller ID 42 atau target `MapSelectPage`. Di antara caller langsung wrapper getter yang terindeks, satu-satunya yang ditemukan mengirim 48.
- Fungsi page `0x12424c0` berada di sequence fungsi yang disimpan sebagai vptr; titik dispatch tak langsungnya belum dilacak. Relasi state-registration ke CharaMakeMap didukung, tetapi hubungan lifecycle page dengan aksi EventFlow belum terbukti.
- `Capture^t` terbukti sebagai binding tekstur `P_Map_00` di layout child `LMapChoice`; manifest BNTX mencatat BC5_UNORM 8×8, satu mip, 512 byte image. Tidak ada bukti di trace ini bahwa tekstur tersebut diganti saat runtime, dipakai sebagai render target, atau memuat thumbnail pulau. Konversi BFLYT statis tidak cukup untuk menetapkan provenance piksel map-card.
- `cVillage` adalah nilai `SaveType` pada operasi `SaveSetFromUIResult` setelah aksi UI. Itu tidak mengidentifikasi terrain preset terpilih, generator terrain, atau format data thumbnail.

Rincian archive/member layout, animasi, dan hash BFLYT/BFLAN/BNTX tetap ada pada laporan dasar [MAP_SELECT_PAGE_BINDING_NATIVE_20261107.md](MAP_SELECT_PAGE_BINDING_NATIVE_20261107.md) dan JSON-nya; temuan follow-up ini hanya menambah trace request/result dan consumer callback. Pertahankan hash arsip sumber sekaligus hash member saat mengonversi aset.

## Hash bukti

| Artefak yang diverifikasi | Ukuran/jenis | SHA256 |
|---|---|---|
| `A_logic/main.elf` | 53,729,580 byte | `5bf707c3dc5dac0ad9635af7d336ec580f81c3f7876d0f55400d1900e3415d74` |
| `output/binary/code_pointer_arrays.json` | analisis pointer/relocation | `64d474068ca289f9146f7f32e6647a16a05e8f5be8e635615a478744b62ef822` |
| `output/binary/analysis_decomp/11ee260.c` | dekompilasi initializer tabel ID | `c6517db532fd663b0f310a816e92ee1776a18f0d0503271232cbb32d25629b5e` |
| `output/binary/analysis_decomp/11ed010.c` | dekompilasi matcher result | `b24e890de7490c702fa0ca98aeb0de829d904fed8a60da460caad4eca50a68b7` |
| `output/binary/analysis_decomp/1590180.c` | dekompilasi poll helper | `3db2118ec5e4d445969bb39a3bf2963593da2df557ffb28d2bda7c03f8cee34a` |
| `output/binary/analysis_decomp/1590250.c` | dekompilasi result getter wrapper | `ebb9efc5b88ed572250a582972689c84108ef646f4a2d01546d27245889320a9` |
| `output/binary/analysis_decomp/1242550.c` | dekompilasi page creator | `cfa5349e8b02a96d0877e528f08f15601ddca4eab735ddb1ffaa37332c16c8f9` |
| `output/binary/analysis_decomp/1243980.c` | dekompilasi CharaMakeMap consumer candidate | `2a7adac8e5238348cd7b2cd4bded49f6adeb280f642de1606a3028b76839f28d` |

JSON pendamping divalidasi dengan `python3 -m json.tool`; hash input di tabel dihitung dari file yang tercantum. Tidak ada report sebelumnya yang diedit, dan tidak ada commit/push.
