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

`Workbench_Cmn_DIYdemo` memisahkan `SubflowResultChoice2`: case 0 memilih `cWorkCraft`; case 1 menjalankan `SaveSetFromUIResult cWorkRemake` (#182), `PlayerWorkbenchMaking IsRemake=true` (#184), lalu memilih demo normal (#185) atau cabang fork yang melewati demo kamera/fanfare (#197). Ini membuktikan alur dua hasil dan bahwa aksi remake berjalan sebelum demo hasil. Gate pembatalan pilihan biasa berada di entry `Remake`, sebelum subflow ini.

Pada handler native `0x335d10`, urutan yang terbaca adalah: panggil pengurangan kit `0xefbdf0` (`0x335d7c`), proses data hasil terpilih (`0xefcfc0`, `0x335dc0`), panggil helper remake (`0xefbad0`, `0x335dd0`), lalu lanjutkan salah satu dari dua cabang yang bergabung kembali di `0x335f18` dan publikasikan hasil UI (`0x154a640`, `0x33603c`). Nilai balik pengurangan kit tidak diperiksa oleh caller: instruksi berikutnya mengisi `w0=1`, lalu eksekusi berlanjut. Tidak terlihat panggilan pengembalian kit eksplisit dalam handler itu. Ini bukti pada tingkat caller; belum membuktikan bahwa nested helper atau jalur sistem save lain tidak melakukan rollback.

Reproduksi native helper `0xf99b10` pada pocket fixture yang direkonstruksi mengonfirmasi kasus parsial: 50 kit menjadi 48 saat permintaan 2. Permintaan 2 saat fixture hanya berisi 1 kit ditolak dan buffer fixture tetap sama. Batas penting: saat permintaan menghabiskan tepat seluruh stack, helper mengembalikan sukses tetapi fixture sintetis ini tidak berubah. Karena slot ini bukan rekaman save nyata, hasil exact-stack belum ditafsirkan sebagai perilaku permainan.

### Bit 4 dan tutorial

**[NATIVE STATIC]** Builder state `0x15ad1c0` mengisi byte flag di `state+0x1c`. Bit 4 ditetapkan oleh hasil `0x15806f0`, yang memanggil `0xa9cb60` pada objek item terpilih dengan kode tipe `0x38`. Jika predikat itu benar, `0x15ae950` menulis kuantitas kit nol dan menyalakan byte hasil `+0x18`; jika salah, ia menyalin `state+0x1928` (nilai `RemakeKitNum`) ke payload `+0x14`. Jadi bit 4 berasal dari klasifikasi item yang dipilih, bukan dari pembacaan langsung string `DisplayType`.

**[EVENTFLOW + TBL]** Jalur tutorial `RcoRemakeTrialOngoing` memberi 50 item kit 2513, membuka pemilih item dengan `Mode=cItemSelectRemakeTutorial` untuk item 3436, lalu menjalankan `UIWorkingHandling DisplayType=cRemakeSelectTutorial` (#100) dan masuk ke `Workbench_Cmn_DIYdemo`. Item 3436 adalah `ItemKind=Ftr`, `RemakeID=168`, dan biayanya 2. Kode tipe native `0x38` sama dengan ordinal 56 pada urutan baris `ItemKind`, yaitu `CraftPhoneCase` (`UniqueID=256`); hubungan antara kode `0xa9cb60` dan ordinal tabel ini masih merupakan crosswalk statik, belum diuji native. Karena itu, untuk target tutorial 3436 bukti yang ada mendukung jalur biaya normal bila klasifikasi tersebut cocok, tetapi belum membuktikan hasil bit 4 pada runtime.

### Pembatalan

**[EVENTFLOW]** Pada `Ftr_Working:Remake`, `UIResultMenuDecide` #9 case 0 meneruskan ke `cRemakeSelect`; sesudahnya #8 case 0 menetapkan hasil subflow dan memanggil `Workbench_Cmn_DIYdemo`. Case 1 pada #8 mengulang entry `Remake`, sedangkan case 1 pada #9 mengakhiri entry. Kedua cabang keluar sebelum `SaveSetFromUIResult cWorkRemake`, sehingga event biasa tidak mengirim pembatalan ke handler transaksi. Penafsiran case 1 sebagai aksi batal mengikuti nama query dan bentuk cabang; pemetaan tombol UI ke nilai query belum dijalankan.

Di jalur tutorial, setelah `UIWorkingHandling cRemakeSelectTutorial` (#100), EventFlow langsung mengisi hasil subflow dan memanggil demo transaksi; tidak ada query hasil/pembatalan eksternal pada jalur tersebut. Perilaku pembatalan internal halaman tutorial belum terpetakan.

### Rollback dan batas persistensi

`0xefbdf0` mengembalikan status dari `0xf99b10`, tetapi caller `0x335d10` menimpa `w0` dengan 1 di `0x335d80` dan terus memproses hasil remake. Tidak ada cabang kegagalan langsung, pemanggilan pengembalian kit, atau pemanggilan kedua `0xefbdf0` di handler itu. Cabang sesudah `0xefbad0` memilih helper hasil berdasarkan payload `+0x18`; kedua jalur bergabung sebelum hasil UI dipublikasikan. Ini batas pada caller dan helper yang sudah dibaca, bukan bukti bahwa semua jalur sistem lain tidak dapat rollback.

Ada petunjuk preflight pada halaman workbench: `0x1580580` memakai pengecualian tipe `0x38`; untuk tipe lain ia membandingkan `RemakeKitNum` dengan nilai hitungan yang diberikan. Caller `0x136d9d0` memakai hasil itu untuk mengatur properti UI ke `1.0` atau `2.0`. Arti properti tersebut belum diketahui, jadi bacaan ini belum membuktikan bahwa kekurangan kit menonaktifkan pilihan.

**[NATIVE STATIC]** `0xefbdf0` mengambil konteks pemain lewat `0xf8f400`, membuka member di offset `+0x70` pada record terkait pemain lewat accessor `0xee9350`/`0xee9490`/`0xee94f0`, lalu meminta `0xf99b10` mengubah record inventory itu. Ini menunjukkan mutasi record save pemain di memori. Handler tidak memanggil serializer atau flush save yang teridentifikasi; batas durabilitas ke file save masih belum diketahui. Native helper fixture terdahulu hanya menguji record pocket sintetis: permintaan 2 mengurangi stack 50 ke 48, permintaan 2 saat tersedia 1 ditolak tanpa perubahan, sedangkan kasus tepat menghabiskan stack tetap ambigu pada fixture.

Dengan demikian bukti ini menetapkan jalur biaya, cabang batal normal sebelum handler, predikat bit 4, dan batas mutasi record yang terlihat. Ia belum membuktikan rollback penuh setelah dispatch, perilaku cancel internal halaman tutorial, hasil bit 4 runtime untuk item 3436, atau kapan record itu tersimpan permanen.

## Reproduksi

```sh
python3 acnh-re/tools/crafting_remake_cost_static.py
python3 acnh-re/tools/crafting_remake_inventory_native.py
python3 -m unittest -v acnh-re.tests.test_crafting_remake_cost_static
```

Runner static membaca ELF, SQLite index, BCSV dan EventFlow; SQLite dibuka read-only. Runner native memasang ItemParam/ItemKind asli ke emulator, tetapi memakai pocket fixture sintetis dan tidak mengubah index bersama. Hasil tersimpan di [crafting_remake_cost_static.json](../output/gameplay/crafting_transaction_remainder/crafting_remake_cost_static.json) dan [crafting_remake_inventory_native.json](../output/gameplay/crafting_transaction_remainder/crafting_remake_inventory_native.json).
