# Binding runtime preview bangunan ke selector dan resource asset — follow-up

**Tanggal:** 2026-11-07. **Cakupan:** RE statis ACNH 1.0.0 untuk selector request `StructureStartPreviewGuide`, hubungan keluarga field `StructureFacilityModel.ModelName` ke pembentuk nama pendamping `_pbc`, lalu batas menuju collider dan lifecycle bangunan final. Ledger pasangannya ada di [JSON follow-up](../output/gameplay/building_preview_runtime_asset_binding_followup_20261107.json). Tidak ada eksekusi game, pembukaan payload model/PBC, perubahan Godot, rebuild Ghidra, atau perubahan index.

## Hasil

Selector request preview sekarang terpecahkan sampai ke **slot 0** pada tabel tiga entri milik `ActorLoad` manager. Ini belum mengidentifikasi kelas actor yang dibuat: slot tersebut adalah indeks dispatch lokal pada member manager `+0x1d0`, sedangkan registry actor bernama masih memakai indeks 9 (`StructureActor`), 10 (`StructurePreviewSwapActor`), 56 (`StructurePreviewActor`), dan 80 (`StructurePreviewGuideActor`). Tidak ada join statis dari slot 0 ke salah satu nama itu.

Di jalur resource terpisah, accessor native untuk hash field `ModelName` cocok dengan keluarga schema `StructureFacilityModel`. Fungsi native `0x169b90` memanggil accessor itu dalam loop row yang sama dengan formatter `%s_pbc` dan memasukkan hasil penamaan ke daftar resource. Ini membuktikan mekanisme pembentukan nama pendamping PBC pada keluarga data tersebut. Belum ada edge dari slot 0 `StructureStartPreviewGuide` menuju loop ini; belum terbukti pula bahwa key tersebut memuat payload PBC atau memasangnya pada komponen collider.

## Selector request preview

Handler kandidat terdaftar `EventFlowActionStructureStartPreviewGuide` berada di raw ELF VA `0x3445b0`. Pada PC `0x344818`, handler memanggil `0x490f0` (`ActorLoad`). Handler menyiapkan request dengan nilai fallback `0`: helper `0x34ad0` menginisialisasi field request `+0xc8` menjadi mode `4`, lalu handler menetapkan `uStack_128 = 0` dan mengirimnya ke setter `0x34d90`, yang menulis nilai itu ke `+0x18`.

Di `0x49360`, mode `4` memilih field fallback `+0x18`; nilai efektifnya `0`. Callsite raw `0x4929c` menghubungkan `0x490f0 → 0x49360`, lalu PC `0x493bc` menghubungkan `0x49360 → 0x407e0`. Fungsi `0x407e0` memakai selector tersebut untuk membaca entri pertama pada tabel `ActorLoad` manager, yaitu `*(manager + 0x1d8)` relatif terhadap awal objek manager. Constructor manager `0x498c0` menyiapkan tabel di `manager + 0x1d0` lewat `0x40390`; tabel ini memiliki tiga entri. Slot yang terpilih terbukti, tetapi objek yang dirujuk slot pertama tidak dinamai sebagai kelas actor tertentu pada pseudocode yang tersedia.

Registry actor 158-entri memberikan empat kelas struktur/preview yang relevan, tetapi nomor registrinya tidak sama dengan bukti selector lokal di atas. Karena itu laporan ini mengunci pilihan ke slot dispatch 0 dan membiarkan `slot 0 → kelas actor bernama` sebagai **OPEN**.

## `StructureFacilityModel.ModelName` dan key pendamping PBC

Accessor native `0x16b5c0` mencari hash field `0x39b5a93d` pada descriptor row lalu mengembalikan alamat field. Accessor ini memakai cache descriptor yang sama dengan getter hash `StructureInfoUniqueID` (`0x00c1577d`), `Construction` (`0x9c8a400b`), `GrowLevel` (`0x35ac1bb4`), dan `FloorHeight` (`0x6efc082c`). Lima hash itu muncul bersama pada schema `StructureFacilityModel` dan, di antara schema tabel yang tersedia, kombinasi tersebut hanya cocok dengan tabel itu. Ini adalah join **TBL/PSEUDO** melalui fingerprint kolom; binary tidak menyimpan nama tabel literal.

Pada loop raw `0x169b90`, helper row `0x16b470` diikuti call ke accessor `0x16b5c0` pada PC `0x16a1b0`. Call berikutnya pada PC `0x16a1c0` memakai literal string VA `0x2a46397`, yaitu `%s_pbc`, melalui formatter `0x12930`; hasilnya diteruskan ke daftar resource oleh helper `0x1c9bc0`. Jadi terdapat native path untuk membentuk key PBC pendamping dari keluarga nilai model-name tersebut. Decompilation tidak mempertahankan aliran vararg dan identitas row set secara path-sensitive penuh; klaim yang aman adalah mekanisme resolver/key builder terpisah, bukan pilihan row atau resource oleh handler preview.

Join katalog sebelumnya tetap berlaku: seluruh 19 nilai `ModelName` pada `StructureFacilityModel` punya entri katalog model dan entri katalog nama `_pbc` yang cocok. Hasil follow-up ini tidak mengulang daftar katalog dan tidak membuka payload. Katalog saja maupun formatter `%s_pbc` tidak membuktikan bahwa payload berbentuk collider atau dikonsumsi oleh komponen fisika tertentu.

## Batas menuju preview, build, dan instance final

`PreviewStructure` kandidat `0x36e140` menyalin pose/metadata ke actor context pada `+0x288`; body langsungnya tidak memuat pemilihan `ModelName`, pemanggilan loader PBC, atau pemetaan kelas actor. `BuildStructure` kandidat `0x369d50` memilih site-list entry dan meneruskan koordinat ke actor-context handler `0xbe6480`. Di dalam jalur itu, `0xbe6340` memakai objek runtime pada owner `+0x68` dan virtual slot koordinat `+0x128`; kelas objek yang mengisi slot tersebut tetap dinamis.

Laporan batas vptr sebelumnya sudah menunjukkan constructor owner mengosongkan `+0x68` dan target komponen diisi kemudian oleh lifecycle yang belum ditemukan. Follow-up ini tidak menutup pemasangan komponen, pemanggilan collider/PBC dari objek tersebut, pembuatan actor struktur final, atau penulisan/reload save instance. Tidak ditemukan edge langsung dari selector slot 0 ke resolver `0x169b90` pada jalur call yang diperiksa; dispatch tidak langsung tetap mungkin.

## Reproduksibilitas

Alamat di laporan ini adalah raw ELF VA. Label pseudocode Ghidra memakai bias `+0x100000`. Identitas native yang digunakan adalah SHA-256 `5bf707c3dc5dac0ad9635af7d336ec580f81c3f7876d0f55400d1900e3415d74`; sidecar JSON mencatat hash input ExeFS, index bersama, tabel, registry, string-reference index, dan setiap decompilation yang diperiksa. Pembuktian hanya statis; tidak ada payload model/PBC, save, atau runtime yang dibuka.
