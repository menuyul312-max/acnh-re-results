# Jalur biaya remake kit ke inventory

**Tanggal:** 2026-11-06  
**Cakupan:** menutup hubungan nilai `ItemRemake.RemakeKitNum` dengan kuantitas yang dibaca oleh handler `SaveSetFromUIResult cWorkRemake`. Ini bukti tabel dan disassembly statik; transaksi tidak dijalankan memakai save pemain.

## Hasil

Untuk jalur remake biasa ketika flag internal bit 4 bersih, hubungan biaya ke kuantitas inventory sekarang **terbukti statik**:

1. **[TBL]** `ItemParam.UniqueID=3436` memiliki `RemakeID=168`. Baris `ItemRemake.UniqueID=168` memiliki `RemakeKitNum=2`. Item kit adalah `ItemParam.UniqueID=2513`.
2. **[NATIVE STATIC]** Resolver `0xab2330` mencari hash field `0x29ecb129` (`RemakeKitNum`) pada baris remake dan mengembalikan byte pada offset field tersebut. Pembuat state workbench `0x15ad1c0`, dipanggil dari `0x15ad070`, menyimpan nilai balik itu pada `state+0x1928`.
3. **[NATIVE STATIC]** `0x15ae950` menyalin `state+0x1928` ke payload hasil UI `+0x14` jika bit 4 pada flag state bernilai nol. Setter `0x154a640` meneruskan payload ke `0x1546070`, yang menyalin `payload+0x14` ke `manager+0x5c`. Getter `0x154a670` mengembalikan `manager+0x48`; maka field yang dibaca di `getter_result+0x14` adalah alamat yang sama (`manager+0x5c`).
4. **[NATIVE STATIC]** `0x335d10`, handler case `cWorkRemake`, membaca `getter_result+0x14`. Jika nilainya minimal 1, ia mengirim ID kit `2513` dan kuantitas itu ke `0xefbdf0`, yang meneruskan perubahan inventory ke `0xf99b10`.

Jadi, untuk item 3436 pada jalur bit-4-bersih, angka tabel `2` mengalir hingga argumen kuantitas pengurangan kit. Batas pentingnya: tabel menyimpan field `u16`, sedangkan reader native mengambil low byte. Seluruh 654 nilai `RemakeKitNum` pada dump ini berada di rentang 1–50, sehingga tidak ada nilai yang terpotong pada build yang diperiksa.

## Urutan EventFlow dan alur hasil

`Workbench_Cmn_DIYdemo` memisahkan `SubflowResultChoice2`: case 0 memilih `cWorkCraft`; case 1 menjalankan `SaveSetFromUIResult cWorkRemake` (#182), `PlayerWorkbenchMaking IsRemake=true` (#184), lalu memilih demo normal (#185) atau cabang fork yang melewati demo kamera/fanfare (#197). Ini membuktikan alur dua hasil dan bahwa aksi remake berjalan sebelum demo hasil. Itu tidak menunjukkan bagaimana UI menerjemahkan pembatalan pengguna menjadi hasil subflow.

Pada handler native `0x335d10`, urutan yang terbaca adalah: panggil pengurangan kit `0xefbdf0` (`0x335d7c`), proses data hasil terpilih (`0xefcfc0`, `0x335dc0`), panggil helper remake (`0xefbad0`, `0x335dd0`), lalu lanjutkan salah satu dari dua cabang yang bergabung kembali di `0x335f18` dan publikasikan hasil UI (`0x154a640`, `0x33603c`). Nilai balik pengurangan kit tidak diperiksa oleh caller: instruksi berikutnya mengisi `w0=1`, lalu eksekusi berlanjut. Tidak terlihat panggilan pengembalian kit eksplisit dalam handler itu. Ini bukti pada tingkat caller; belum membuktikan bahwa nested helper atau jalur sistem save lain tidak melakukan rollback.

Reproduksi native helper `0xf99b10` pada pocket fixture yang direkonstruksi mengonfirmasi kasus parsial: 50 kit menjadi 48 saat permintaan 2. Permintaan 2 saat fixture hanya berisi 1 kit ditolak dan buffer fixture tetap sama. Batas penting: saat permintaan menghabiskan tepat seluruh stack, helper mengembalikan sukses tetapi fixture sintetis ini tidak berubah. Karena slot ini bukan rekaman save nyata, hasil exact-stack belum ditafsirkan sebagai perilaku permainan.

`0x15ae950` memiliki jalur bit-4-set yang sengaja menulis kuantitas nol dan flag tambahan. Arti bit tersebut serta pemetaannya dari `cRemakeSelectTutorial` belum tersambung, jadi laporan ini tidak mengklaim jalur tutorial memakai biaya 2. Untuk jalur biasa saat bit 4 bersih, pemetaan row-to-quantity terbukti.

Belum ada save pemain atau runtime interaction untuk memastikan rollback saat gagal/interupsi, batas commit ke penyimpanan persisten, dan urutan flush save. Native helper-level fixture tidak menjalankan event `cWorkRemake` lengkap. Jadi bukti ini menutup pemetaan biaya statik dan memperjelas urutan caller, tetapi tidak membuktikan atomicity atau persistensi transaksi lengkap.

## Reproduksi

```sh
python3 acnh-re/tools/crafting_remake_cost_static.py
python3 acnh-re/tools/crafting_remake_inventory_native.py
python3 -m unittest -v acnh-re.tests.test_crafting_remake_cost_static
```

Runner static membaca ELF, SQLite index, BCSV dan EventFlow; SQLite dibuka read-only. Runner native memasang ItemParam/ItemKind asli ke emulator, tetapi memakai pocket fixture sintetis dan tidak mengubah index bersama. Hasil tersimpan di [crafting_remake_cost_static.json](../output/gameplay/crafting_transaction_remainder/crafting_remake_cost_static.json) dan [crafting_remake_inventory_native.json](../output/gameplay/crafting_transaction_remainder/crafting_remake_inventory_native.json).
