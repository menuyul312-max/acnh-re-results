# Kalender SDK dan genetika bunga

Tahap ini memakai main 1.0.0 dan modul ExeFS tambahan yang sudah diverifikasi. Alamat main dan SDK dibedakan menurut modul. Seluruh pengujian berikut memakai instruksi asli; input object/cache direkonstruksi secara eksplisit dari raw dan metadata. Proyek Godot tetap utuh.

## Penghubungan modul

`native_linker.py` memetakan main, SDK, subsdk0, dan rtld, lalu menerapkan `R_AARCH64_RELATIVE`, `ABS64`, `GLOB_DAT`, dan `JUMP_SLOT`. Sebanyak **355.478 pointer relocation** cocok setelah pengujian kalender. Simbol terdefinisi dalam modul memakai alamat modulnya; undefined dengan satu ekspor strong memilih ekspor tersebut. Ambiguitas lain ditolak. Weak unresolved dicatat dan diikat nol. Ini kebijakan harness untuk helper terisolasi, belum merupakan pembuktian semua aturan pencarian simbol loader konsol.

Tidak ada constructor modul, TLS atau layanan OS yang dipalsukan. Interrupt/SVC menghentikan uji. Fungsi yang diuji tidak mencapai layanan OS. [Relocation dan batas](../output/native_modules/relocation_verification.json).

## Kalender dan batas hari game

Fungsi SDK `ToPosixTimeFromUtc`/`ToCalendarTimeInUtc` dipanggil melalui entry dan PLT/GOT asli, termasuk utility internal SDK. Layout kalender adalah `<s16 year, u8 month/day/hour/minute/second, padding>`, delapan byte.

Pengujian mencakup seluruh **146.097 tanggal pada 2000–2399**, tanggal batas tahun 1–9999, negatif Posix sebelum 1970, aturan abad bukan kabisat, dan sampel acak. Total **314.757 pemeriksaan**, terdiri dari:

| Kelompok | Perbandingan |
|---|---:|
| Kalender → Posix | 147.169 |
| Posix → kalender | 147.169 |
| Normalisasi hari game dan guard | 16.268 |
| Offset hari dan overflow integer | 4.151 |

Fungsi main `0x1fbc00` memakai aturan:

```
if hour < 5: calendar_date -= 1 day
hour, minute, second = 5, 0, 0
```

Contoh: 2024-03-01 04:59:59 → 2024-02-29 05:00:00; tepat 05:00 memakai tanggal yang sama. Aritmetika ini memakai konversi UTC pada field kalender yang diberikan, bukan mengambil jam host atau menentukan timezone pemain.

Helper offset `0x1fd540` lebih terbatas daripada matematika integer tanpa batas: hari s32 dikalikan 86.400.000.000.000 nanodetik modulo s64, dibagi 10⁹ dengan pemotongan menuju nol, lalu ditambahkan modulo s64 ke Posix. Perilaku overflow ekstrem diuji dan dipertahankan. Penggunaan umum -1/+1 hari cocok dengan tanggal kalender biasa.

[Hasil, sampel, alamat dan disassembly](../output/calendar/native_verification.json).

## Cuaca melewati pukul 05.00

Audit baru menjalankan pemilih hari biasa main dengan SDK asli pada 00:00:00, 04:59:59, 05:00:00, dan 23:59:59. Sebanyak **27.512 prediksi dan state RNG akhirnya** cocok, termasuk pergantian bulan/tahun. Jumlah pemeriksaan 59.756 mencakup pula 732 lookup kalender dan seluruh 4.000 slot bobot.

Flag override tetap 0; event khusus, simpan/muat seed, awan, kabut, aurora, pelangi dan bintang belum menjadi spesifikasi lengkap. Audit lama jam 12 tetap disimpan sebagai pembanding. [Uji terbaru](../output/weather/native_linked_verification.json).

## Pewarisan gen bunga

Main `0x4cd070` menyimpan empat lokus A/B/C/D, masing-masing dua bit. Tabel asli memetakan kode 00/01/10/11 ke dosage 0/1/1/2, dan mengodekan anak secara kanonis menjadi 00/01/11.

Untuk setiap lokus, fungsi mengunjungi induk A lalu B:

- Dosage 0 menyumbang 0 tanpa mengambil RNG.
- Dosage 2 menyumbang 1 tanpa mengambil RNG.
- Dosage 1 mengambil `rollMax(2)` dan menyumbang 1 bila hasilnya 0.

Urutan dan jumlah pengambilan RNG bergantung heterozigositas. **Seluruh 65.536 pasangan byte induk**, ditambah 1.024 pasangan u32, menghasilkan gen anak, state RNG, dan guard yang cocok. Label biologis R/Y/w/S dari rujukan eksternal tidak diperlukan untuk pembuktian ini; warna/resource berasal dari tabel lokal.

Model probabilitas teoritis mencakup **6.561 pasangan genotipe kanonis** dan 50.625 keluaran berbobot, masing-masing pasangan berjumlah 256. Asumsinya pemilihan alel adil dan independen. Ini distribusi pewarisan setelah pasangan ditentukan, bukan peluang bunga melakukan breeding atau memilih pasangan di lapangan. [Model probabilitas](../output/flowers/inheritance_probabilities.json).

## Genotipe, resource dan pertumbuhan

Raw FgFlowerHeredity mempunyai **270 baris**: Rose 81 kombinasi (empat lokus), tujuh jenis lain masing-masing 27 (tiga lokus). Tiga-lokus mengabaikan lokus D pada lookup. Literal enum 30 nama dalam ELF menentukan indeks kind; setiap nama dicocokkan CRC32 dengan field Kind sumber. Delapan jenis tersebut adalah Rose, Tulip, Pansy, Cosmos, Lily, Hyacinth, Anemones, dan Mum.

Harness menyiapkan array row, shared-buffer holder, cache enum, serta lookup dense ID dari raw FgMainParam/FgFlowerHeredity. Constructor, allocator dan file loader tidak dijalankan; pembaca metadata/hash dan fungsi lookup tetap asli.

`0x4cc4d0` mengubah genotype ke indeks ternary pada tabel, memakai field `753336dd` bila terisi atau `Name` sebagai awal. Permintaan growth 0 menjadi 1; nilai >2 menjadi 3. Fungsi mengikuti `GrowupFg`, atau `ChangeFg` bila GrowupFg kosong, sampai growth yang diminta. Name/hash, resource/model, color index dan item terkait dipertahankan dalam [genotypes.json](../output/flowers/genotypes.json). Ketersediaan nama model belum membuktikan mesh model tersebut ikut input.

Field `753336dd` belum bernama asli. Seluruh nilai nonempty-nya pada paket ini menunjuk resource Grow=0 dan dipakai sebagai awal alternatif. Peran tersebut tidak diubah menjadi descriptor rekaan.

`0x4cd310` menghasilkan gen default pada **180 resource bunga**: normalisasi ke bud Grow=2, mencari baris Kind/Name, lalu berhenti pada `DefaultHeredity != 0`. Bila tidak ada penanda, fungsi memakai **baris matching terakhir**. Pseudocode otomatis menuliskan signature void, sementara eksekusi asli membuktikan nilai gen dikembalikan di W0. [Gen default](../output/flowers/default_genes.json).

## Item anakan dan FreeParam

Caller `0x4d5e50` kini diuji pada **11.664 pasangan genotipe kanonis dalam jenis yang sama**. Ia membaca gen induk dari **byte terendah FreeParam, offset item+4**, menjalankan pewarisan, memilih resource bud anak, lalu menulis item delapan byte. ID hasil, byte gen, state RNG, guard output, dan item induk yang tetap utuh cocok dengan model.

ABI hasil object C++ memakai **X8 sebagai pointer return tersembunyi**; argumen eksplisit adalah X0=object parameter Fg, X1=item induk lain. Pseudocode otomatis menampilkan pointer hasil seolah argumen biasa, sehingga signature tersebut tidak dipakai sebagai kontrak panggilan.

Ini membuktikan satu interpretasi union FreeParam untuk keluarga bunga. Arti seluruh bit item dan FreeParam keluarga lain tetap memerlukan bukti sendiri. Pasangan disuplai langsung; seleksi pasangan, validasi kelayakan, lokasi spawn, bonus air/pengunjung, serta golden rose di caller lebih tinggi belum terbukti lengkap. [Sampel item asli](../output/flowers/offspring_items.json).

## Kasus Black Cosmos yang harus dipertahankan

Data lokal mempunyai siklus:

| ID | Label | Grow | Lanjutan |
|---|---|---:|---:|
| 60151 | PltFlwCosmos2Black | 2 | 60153 |
| 60153 | PltFlwCosmos3Black | 3 | 60155 |
| 60155 | PltFlwCosmos1Black | **0** | 60151 |

Permintaan Grow=1 tidak ada pada siklus tersebut. **24 input sintetis** (termasuk alias growth 0→1 dan alias kode heterozigot) mengulang dua putaran yang sama dalam fungsi asli, tanpa kembali dalam batas 20.000 instruksi. Data dan label tidak dikoreksi otomatis. Ini hasil bounded execution; belum ada bukti bahwa workflow game biasa memanggil kasus itu, sehingga belum dinyatakan sebagai bug gameplay yang teramati.

Caller item anakan `0x4d5e50` yang sudah diuji selalu meminta Grow=2, sehingga tidak memicu kasus Grow=1 tersebut pada seluruh 11.664 pasangan yang diperiksa. Kesimpulan ini hanya berlaku pada caller tersebut.

[Trace kasus batas](../output/flowers/growth_cycles.json), [seluruh perbandingan dan cakupan](../output/flowers/native_verification.json).
