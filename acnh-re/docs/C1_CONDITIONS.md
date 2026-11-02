# Bytecode kondisi BGM `C1`

Sumber: 2.644 blob yang dirujuk `Sound/Bgm/BgmStatic.json` beserta ekspresi teks pasangannya. BYML asal BGM tidak disertakan; JSON dan seluruh blob rujukannya tersedia. Semua pembacaan di bawah diuji pada korpus tersebut. Ini bukan klaim bahwa seluruh opcode atau seluruh variasi format game lain sudah ditemukan.

## Struktur yang teramati

| Offset | Bentuk | Arti |
|---|---|---|
| 0 | dua byte `43 31` | Magic ASCII `C1` |
| 2 | u16 little-endian | Ukuran total blob; cocok pada 2.644/2.644 |
| 4 | u8 | Offset root dan awal array node; evaluator native membaca satu byte |
| 5 | u8 | Nol pada korpus ini; tidak dipakai sebagai byte tinggi offset oleh evaluator |
| 6 | u8 | Jumlah referensi properti di header; dapat berulang |
| 7 | u8 × jumlah | Indeks properti, kemudian padding hingga kelipatan empat |
| root | record empat byte | Root ekspresi, indeks node 0 |

Root memenuhi `align4(7 + jumlah_referensi)`. Posisi node `i` adalah `root + 4*i`. Node dibaca sebagai `u8 opcode`, `u8 byte1`, `u16 word2`.

| Opcode | Bentuk yang teramati |
|---:|---|
| 0 | `AND(node[byte1], node[byte2])` |
| 1 | `OR(node[byte1], node[byte2])` |
| 2 | `<` pada dua node anak |
| 3 | `<=` pada dua node anak |
| 4 | `>` pada dua node anak |
| 5 | `>=` pada dua node anak |
| 6 | `==` pada dua node anak |
| 7 | `!=` pada dua node anak |
| 8 | Properti lokal `word2`; ditemukan dalam dispatcher native, tidak dipakai oleh blob korpus ini |
| 9 | Referensi properti `word2`; `byte1` dipertahankan pada daftar instruksi |
| 11 | Literal f32 di `offset_node + word2`; `byte1` dipertahankan |

Index anak adalah relatif terhadap awal array node, sedangkan pointer literal relatif terhadap lokasi node literal itu sendiri. Literal yang sama dapat dipakai beberapa node. Parser memeriksa ukuran, indeks, siklus, referensi properti, dan tumpang tindih literal dengan instruksi terjangkau.

Untuk operator biner, byte ketiga adalah indeks anak u8 dan byte keempat tidak ikut indeks. Untuk properti/literal, dua byte pada offset node+2 dibaca sebagai u16. Pembedaan ini dikonfirmasi dari instruksi evaluator native, meskipun byte tinggi seluruh indeks anak dalam input ini memang nol.

Contoh blob `$15==1`:

```text
433118000800010f0601020009010f000b0004000000803f
```

AST hasil pembacaan: `["==", ["var", 15], ["number", 1.0]]`.

Properti 15 pada urutan `GlobalProperty` adalah `FacilityMusicNumber`. Memakai ID 15 dari tabel `BgmPropertyParam` akan menghasilkan nama lain dan mengubah arti kondisi.

## Satu perbedaan prioritas operator

2.643 ekspresi cocok setelah normalisasi asosiasi AND/OR murni. Satu ekspresi tidak cocok dengan aturan prioritas boolean yang umum:

```text
( $30<54 || ($29!=29 && $29!=49 && $29!=54 && $29!=58)) && $29!=59 || $28!=23
```

Jika bagian dalam tanda kurung pertama disebut `A`, syarat `$29!=59` disebut `B`, dan `$28!=23` disebut `C`, pembacaan teks konvensional adalah `(A && B) || C`. Struktur node biner menunjukkan `A && (B || C)`.

Contoh nilai yang membedakan keduanya: `$28=22`, `$29=29`, `$30=55`. Teks konvensional bernilai true, AST bytecode bernilai false dengan pemetaan opcode yang cocok pada korpus lain.

Jangan otomatis memperbaiki bytecode mengikuti teks atau sebaliknya. Hasil menyimpan kedua AST beserta sumber blob. Evaluator ARM64 asli di `0x21e21e0`/`0x21e21f0` dieksekusi terisolasi dengan Unicorn: 940 program unik, tujuh keadaan properti, 6.580 perbandingan, tanpa mismatch. Keadaan pembeda di atas juga menghasilkan false secara native. Ini memverifikasi evaluasi helper pada keadaan tersebut; game lengkap tidak dijalankan pada Switch.

Context global: pointer owner di context+8, jumlah properti di owner+0x104, pointer tipe di +0x110, dan nilai empat byte di +0x120. Tipe nol membaca s32 lalu dikonversi f32, tipe bukan nol membaca f32. Context properti lokal memakai count+0x60, type pointer+0x70, dan value pointer+0x80. Bukti dan checksum ELF ada di `output/native_verification.json`.

Implementasi pembaca: `tools/conditions.py`. Hasil lengkap: `output/audio/condition_bytecode.json`.
