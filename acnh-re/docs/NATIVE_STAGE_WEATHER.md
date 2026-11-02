# Kontrak native tambahan

Sumber primer: ELF SHA-256 `5bf707c3dc5dac0ad9635af7d336ec580f81c3f7876d0f55400d1900e3415d74`, build ID `7FC1BAFF976AECA414520CB89F4616CB` (ACNH 1.0.0). Semua alamat adalah VA ELF. Pseudocode Ghidra memakai tambahan image base `0x100000`, termasuk alamat literal yang dicetaknya. Offset file, VA, dan alamat pseudocode harus dibedakan.

Unggahan ExeFS berikutnya sekarang tersedia dan cocok dengan main ini. Audit awal di bawah memakai strcmp pengganti; audit tambahan mengulang seluruh pembacaan BYML memakai strcmp SDK asli, tanpa stub. Lihat [ADDITIONAL_EXEFS.md](ADDITIONAL_EXEFS.md). Batas stub pengujian lain tetap mengikuti masing-masing artefak, bukan otomatis dianggap dihapus.

Sesudah audit ini, [CALENDAR_FLOWERS.md](CALENDAR_FLOWERS.md) menutup batas sebelum pukul 05.00 melalui SDK asli, memperluas uji cuaca dan menambah genetika bunga. Pernyataan domain jam 12 di bawah merujuk artefak audit awal; bukti terbaru ada di `output/weather/native_linked_verification.json`.

## Pembaca BYML

[native_verification.json](../output/byml_typed/native_verification.json) memuat hasil untuk seluruh 2.313 sumber, 443.204 entry dictionary fisik, dan 319.774 entry array fisik. Entry fisik dapat berbeda jumlah dari kemunculan pada tree hasil ekspansi karena shared node dan key literal. Constructor, count, by-index, by-name, tag, word, guard, dan input yang tetap utuh diperiksa terpisah.

| Fungsi | VA |
|---|---|
| Constructor iterator | `0x1ef43f0` |
| Count | `0x1ef45c0` |
| Data by index | `0x1ef4610` |
| Data by name | `0x1ef46c0` |
| Normalisasi ByamlData | `0x1ef5cf0` |
| Dictionary by-index tanpa batas | `0x1ef63d0` |
| Dictionary entry dengan batas | `0x1ef6510` |

Output ByamlData adalah word u32 yang sudah dinormalisasi, tag u8, lalu padding tiga byte. Byte +5 bukan flag endian. Data reader mengubah urutan word saat sumber big endian; seluruh sumber paket ini little endian. Pengujian tidak membuktikan dukungan semua format/versi BYML yang tidak ada dalam input.

Helper dictionary langsung hanya menolak count nol. Indeks negatif atau >=count pada dictionary tidak kosong dapat tetap menghasilkan sukses dan pembacaan di luar node. Pembaca konversi harus memvalidasi batas. Lookup nama memakai helper entry yang memeriksa batas. Temuan ini dicatat sebagai kontrak fungsi; tidak dipakai untuk mengeksploitasi runtime.

Satu pengganti pada emulasi adalah `strcmp` SDK pada PLT `0x220f030`, dengan perbandingan byte unsigned hingga NUL. Tidak ada parser atau lookup game yang diganti. Semua cek ini memvalidasi struktur, bukan persentase pemahaman gameplay.

## Nama array parameter

Formatter vtable slot `0x58` memakai `%s[].%s` pada `0x29b9f57`; slot `0xe8` array sendiri mengembalikan `yml`. Jadi tipe elemen diambil dari formatter, bukan menganggap tipe array `yml` berarti tipe scalar. Sebelas tipe elemen yang ditemukan: `f32`, `V3f`, `s32`, `Enum`, `s8`, `u8`, `Str`, `bool`, `C4f`, `V2f`, `V2i`. Contoh: `mValueBuffer[].bool`, `mWeatherType[].Enum`, `mRate[].s8`. Array struct tetap dapat memakai `%s[]`. Nama diterima hanya setelah kecocokan CRC32 dan keluarga nilai wire; key asli tetap dapat dipulihkan melalui kamus.

Empat nama Stage (`ActorName`, `ActorList`, `UIList`, `UIName`) mempunyai kandidat Murmur3 polos, indeks key native, serta konsumen yang mendukung perannya. Biner menyimpan key tersebut sebagai string hex. Identitas nama asli tidak dianggap terbukti hanya karena sebuah kandidat CRC32 ditemukan. [Bukti per nama](../tools/knowledge/stage_key_roles.json).

## Stage dan registry actor

[Katalog](../output/stage/catalogue.json) mencakup seluruh 108 resource Stage, termasuk `Stage/Game/MainField.byml`. Setiap record mempertahankan source ID, SHA-256, raw blob, pointer tree asli, dan field yang belum dikenal.

Registry actor diinisialisasi melalui suffix independen `0x61ee0` dari initializer `0x61e40`. Prefix SDK yang tidak berkaitan dilewati; register dasar dan return stack diisi eksplisit. Getter `0x62870`, lookup hash `0x628b0`, dan tabel pasangan hash/index `0x29d775c` mengonfirmasi 158 label asli. [Registry](../output/stage/actor_type_registry.json) menyimpan nama string, alamatnya, indeks, dan dua properti numerik mentah tanpa menebak maknanya.

311 kemunculan actor memakai 58 hash jenis. Tiga hash pada 18 kemunculan menghasilkan indeks `0xffffffff` dan dilewati pembaca `0xfeb390`: 260482876 (kandidat `SeafoodFieldActorMgr`), 4065619304 (kandidat `SeafoodMuseumActorMgr`), 1407911812 (belum bernama). Dua label kandidat ini tidak dipromosikan menjadi class terdaftar; sebab ketidakhadiran belum terbukti. `Parent` adalah hash jenis actor, bukan ID instance unik.

Initializer key Stage `0xffa310` mempunyai suffix penyimpanan SafeString `0xffa3b0`, dengan getter `0xffa690` untuk 40 key. Empat nama common Stage dibaca asli dan dicocokkan dengan resource lokal bila tersedia. Target lain memakai nama kandidat dan kecocokan stem file yang dibedakan dari resolusi scene factory penuh. `environment_modules` menyimpan hash dan indeks native; makna modul yang belum diketahui tidak diberi label rekaan.

Proyeksi `0xfeeeb0` untuk 142 record volume/perpindahan:

```
angle32 = trunc(f32(f32(degrees) * 11930465.0)) mod 2^32
distance = f32(f32(depth*0.5 + key_17e534ec)
               + (mode_bit0 ? key_422c21d8 : 0))
point = f32(Pos + native_direction(angle32) * distance)
```

Penjumlahan opsional default 0. Key `422c21d8` tidak muncul pada record yang tersedia; cabang adanya nilai opsional tersebut belum diuji dengan data nyata. Semua sudut sumber kardinal. Uji tambahan arah mencakup sudut acak/batas.

`0x1cb70` memakai tabel 256 record `[sin, deltaSin, cos, deltaCos]`; delapan bit tinggi memilih record, 24 bit bawah menjadi fraksi interpolasi f32. X=sin×distance, Y=0, Z=cos×distance, dengan pembulatan per operasi tanpa FMA. Hasil 284 proyeksi dan 265 kasus interpolasi cocok bit demi bit. Interpretasi output sebagai arah spawn/exit tertentu masih membutuhkan konteks caller. Satu dependensi strcmp berasal dari pembacaan BYML; proyeksi, interpolasi dan lookup enum tetap asli.

## BCSV dan kebijakan flag

Empat kolom unresolved mempunyai view native satu byte yang terverifikasi. Lebar span kolom mencakup padding dan tidak otomatis berarti lebar tipe.

| Tabel / hash | View | Bukti |
|---|---|---|
| HumanAnimParam / d5217761 | s8 | `LDRSB` di `0x7d16c4` |
| EventFlagsLandTempParam / 3c7fb88f | u8 | `LDRB` di `0xf4683c` |
| ItemRemake / d4f43b0b | u8 | `LDRB` di `0xab26c4` |
| FieldLandMakingError / 0b3be609 | s8 | `LDRSB` di `0xe325a4` |

HumanAnim mempunyai 445 nilai 0xff yang dibaca -1. Bila blok `0x7d16c4..0x7d16ec` dicapai, byte nonnegatif dipakai sebagai selector; byte negatif memilih fallback caller. Enclosing guard membatasi argumen ketiga pada 2 atau 3. Ini bukti satu blok, bukan simulasi sistem animasi lengkap. [View dan 1.172 baris sumber](../output/schemas/native_read_views.json).

Hash `5140e4b4` pada lima tabel EventFlags, 884 baris, berperan sebagai selector predicate reset default. Nama asli tidak diketahui. `0xf54530` membaca context counter s64 di +0 dan byte tambahan di +0x1a:

| Selector | Predicate |
|---|---|
| 0 / selain 1–4 | false |
| 1 | counter != 0 |
| 2 | counter != 0 atau byte != 0 |
| 3 | true |
| 4 | counter > 0 |

8.910 kasus mencakup seluruh selector byte, batas signed counter, dan seluruh byte tambahan pada selector 0–4, tanpa stub. Caller `0xf43220` memanggil predicate kemudian membaca `DefaultValue` (`4c24f1cf`). Makna tingkat gameplay counter/byte serta pengikatan setiap caller ke tabel spesifik belum diklaim. [Kontrak](../output/flags/reset_policy_native.json).

## RNG dan cuaca

RNG terisolasi di `0x19aa040..0x19aa150` memperluas seed melalui pengali `0x6c078965`, menghasilkan u32 xorshift, u64 dari dua draw (pertama high word), serta mengekspor empat word state. State eksplisit semua nol diganti state hasil seed 0. MeteoNook menerima nol pada `with_state`; karena itu dua API tidak sepenuhnya identik meskipun jalur `with_seed` cocok. 35.567 perbandingan tanpa stub memeriksa nilai, state, dan guard. Constructor berbasis tick SDK belum diuji.

[Pola](../output/weather/patterns.json) dan [peluang](../output/weather/rates.json) berasal dari BYML paket. Snapshot AGPL MeteoNook hanya dibaca sebagai literal dengan parser terbatas, tidak dieksekusi. Semua 40 tabel peluang (4.000 slot), 732 tanggal valid leap year, 816 nilai angin, serta 34 nama pola cocok. Dari 816 nilai cuaca, empat berbeda: Fine02 jam 18/19, Fine06 jam 17/19. Nilai lokal dipertahankan beserta perbandingannya. Alasan perbedaan tidak disimpulkan sebagai perubahan versi tertentu. Rain/SnowDrawParam disimpan terpisah tanpa menafsirkan satuan visual yang belum terbukti.

[Uji pemilih native](../output/weather/native_verification.json) menjalankan fungsi `0xfdd9b0` untuk hari biasa. Parameter object sintetis diisi dari data lokal, memakai vtable serta accessor asli, bukan callback pengganti. Constructor/deserialisasi object tidak dijalankan di uji ini.

```
mixed_seed = stored_seed + (year*512 + month*32 + day)*65536  (mod 2^32)
expand_seed(mixed_seed)
discard draw 1 and draw 2
roll = high_u32(draw3 * 100)
choose first cumulative signed-s8 weight > roll
```

Fungsi menerima stored seed u32 apa adanya. API uji tidak menambahkan high bit; initializer seed asli menulis high bit, tetapi asal/persistensi save seed belum dipetakan lengkap. Hemisphere 0/1 memilih North/South. Lookup `0x201dc0` memilih end-date pertama yang >=tanggal. `0x206ef0` memilih container parameter. Pengujian mencakup 6.878 prediksi pada seed batas/acak, 732 tanggal, 4.000 slot bobot, dan state akhir masing-masing prediksi: 18.488 cek cocok tanpa stub.

Domain teruji: tanggal valid, jam masuk 12, flag override=0. Normalizer `0x1fbc00` menetapkan 05:00:00; untuk jam <=4 ia memanggil SDK untuk mundur tanggal. Cabang itu dan flag override=1 tidak dijalankan dalam uji. Cloud, fog, rainbow, aurora, stars, snow conversion, dan seluruh render/runtime cuaca tetap parsial.

## Reproduksi dan batas laporan

`tools/build_all.py` membangun semua JSON dan bukti, lalu menjalankan uji integrasi. Disassembly yang dibatasi region disimpan pada [critical_evidence.json](../output/binary/critical_evidence.json). Indeks kandidat, nama yang dipulihkan, pseudocode otomatis, uji struktur, serta helper perilaku mempunyai cakupan berbeda. `full_user_goal_completed=false` tetap benar: pekerjaan ini belum merupakan spesifikasi seluruh perilaku ACNH.
