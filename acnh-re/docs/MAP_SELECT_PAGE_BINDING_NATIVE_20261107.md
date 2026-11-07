# Trace native UIMapSelectHandling ke MapSelectPage/CharaMakeMap

## Kesimpulan

EventFlow `TerrainSelect` memang menjalankan `UIMapSelectHandling` lalu menyimpan hasil UI melalui `SaveSetFromUIResult {SaveType:cVillage}`. Untuk versi ACNH 1.0.0, nama aksi tersebut terdaftar di `BindInfo.byml`; factory dan vtable-nya berujung pada callback yang mengirim ID permintaan **42** beserta context ke jalur state/request bersama yang mengambil singleton dengan indeks **8**. Jalur polling action juga membaca state dari singleton indeks 8.

Ada rantai native terpisah yang membangun page dengan string `MapSelectPage`, menyimpan objeknya pada `+0x210`, dan kandidat callback yang memanggil fungsi konsumen layout dengan string `CharaMakeMap`. Tidak ditemukan direct call atau relocation statis yang menghubungkan jalur request ID 42 ke rantai page/layout ini. Relocation ke kandidat callback page ada, tetapi konsumen pointer tersebut belum ditemukan. Karena itu hubungan runtime antara keduanya belum terbukti.

Layout card membuktikan struktur kartu yang dapat dipakai ulang dan sebuah binding bernama `Capture^t`. Bukti tersebut belum menerangkan siapa yang memasok atau memperbarui isi tekstur itu. `cVillage` adalah parameter penyimpanan hasil UI dalam EventFlow; trace ini tidak membuktikan preset terrain atau generator dunia yang dipilih.

## Rantai yang terbukti

Semua alamat native berikut adalah ELF VA pada `A_logic/main.elf`; instruksi AArch64 diperiksa dari bytes ELF dan tabel relocation. Label `[EF]`, `[NATIVE]`, dan `[ASSET]` memisahkan sumber bukti.

| Bukti | Relasi | Arti terbatas |
|---|---|---|
| `[EF]` | `TerrainSelect #0 UIMapSelectHandling {}` → `#1 SaveSetFromUIResult {SaveType:cVillage}` | Kedua operation berurutan pada flow tree. Indeks aksi dalam array `EventFlowSystemActor` masing-masing 5 dan 6; itu berbeda dari nomor operation #0/#1. |
| `[NATIVE]` | nama aksi/hash `0x1a24f4b5` → record `0x3059bd8` → relocation `0x3059be0` → factory `0x44cb30` → constructor `0x356e90` | Hash little-endian di raw record adalah `b5 f4 24 1a`; relocation relatif menunjuk ke factory. Factory meminta objek `0xc0` byte dan memanggil constructor pada PC `0x44cb54`. Tidak ada alias pada entri `BindInfo.byml`. |
| `[NATIVE]` | constructor `0x356e90` → vtable address point `0x304e3e0`, slot 14 `0x356f10` | Cell `0x32dd640` menunjuk ke vtable base `0x304e3d0`; constructor menambahkan `0x10` dan menyimpan vptr di PC `0x356eb0`. Slot 14 berada pada offset `+0x70`. Method `0x356f10` menulis immediate `0x2a` ke action `+0xb8` pada PC `0x356f14`: ID callback adalah 42. |
| `[NATIVE]` | base callback `0x34b700` → `0x158ff60` | PC `0x34b710` membaca slot vtable `+0x70`, PC `0x34b718` memanggilnya, lalu callback membaca ID dari `self+0xb8`, mengambil context, dan bercabang ke `0x158ff60` pada PC `0x34b74c`. |
| `[NATIVE]` | `0x158ff60` → singleton getter `0x15411b0(8)` → method state/request `0x11eca30` | PC `0x158ff74` menyiapkan indeks 8. Pada cabang aktif, PC `0x1590004` meneruskan ID, `0x1590008` meneruskan context, lalu `0x159001c` branch ke `0x11eca30`. Method itu mengecek `+0x21c` terhadap `-1`; jika slot kosong, jalur di `0x11eca44` menyimpan ID di `+0x21c` (PC `0x11eca6c`), menulis byte state di `+0x220`, dan membersihkan `+0x224` (PC `0x11eca88`). Nama publik dan semantik kelas manager ini belum teridentifikasi. |
| `[NATIVE]` | polling base `0x34b760`/`0x34b7a0` → `0x1590180`/`0x15903c0` | Helper mengambil singleton indeks 8. `0x1590180` memanggil `0x11ecbd0`, yang membaca `+0x21c` dan `+0x228`; jalur pasangan mencapai helper service `0x15903c0`. Ini membuktikan pembacaan state/result bersama, bukan nama operasi eksternal tertentu. |

## Kandidat page dan layout, belum terhubung ke request ID 42

Fungsi `0x12424c0` mematerialisasi string `MapSelectPage` pada VA `0x29a2521`, menyertakannya pada argumen stack, lalu memanggil `0x1242550` pada PC `0x124252c`. Hasilnya disimpan ke objek `+0x210` pada PC `0x1242530`. Calon creator mengalokasikan `0x5c0` byte, memanggil helper constructor `0x12406d0` di PC `0x1242604`, lalu helper attachment/initialization `0x1da8210`, `0x1144600`, dan `0x1da8220`. Cell vptr `0x3307b48` mengarah ke vtable base `0x3110b28`, dengan address point `0x3110b38`.

Relocation relatif pada cell `0x3307bb8` mengarah ke fungsi kandidat `0x1242fa0`. Fungsi itu memeriksa `+0x218`, lalu memanggil `0x1243980` pada PC `0x1242fc8`. Pointer cell tersebut bukan slot vtable page: slot 14 vtable di `0x3110ba8` mengarah ke `0x1da5680`, sedangkan cell `0x3307bb8` mengarah ke `0x1242fa0`. Pengguna runtime pointer cell belum teridentifikasi.

Fungsi `0x1243980` membaca field objek `+0x210`, nested `+0x3f8`, dan `+0x218`; ia mematerialisasi string `CharaMakeMap` pada VA `0x294cbc3` di PC `0x12439ec` dan memasukkannya ke pemanggilan helper `0xb1aa20` pada PC `0x1243a0c`. Panggilan helper `0xb1b690`, `0xb1af00`, dan `0xb1a960` mengapit langkah tersebut. Bukti ini mendukung kandidat konsumen layout bernama `CharaMakeMap`, bukan pengaitan terverifikasi dengan action ID 42.

Query tabel `direct_calls` memberikan caller berikut: `0x11eca30` hanya dari `0x159001c`; `0x1242550` hanya dari `0x124252c`; `0x1243980` hanya dari `0x1242fc8`; dan `0x1242fa0` tidak punya direct caller terindeks. Tidak ada direct call dari `0x158ff60`, `0x11eca30`, `0x1590180`, atau `0x15903c0` ke `0x1242550`, `0x1242fa0`, atau `0x1243980`. Call tidak langsung atau consumer relocation yang dinamis masih mungkin, tetapi edge itu belum ditemukan.

## Layout card dan implikasi provenance

`CharaMakeMap.bflyt` memiliki empat part `L_Btn_00` sampai `L_Btn_03` yang masing-masing memakai `LCharaMakeMapBtn`, serta `L_Dialog_00`. Layout child berisi pane `N_Capture_00` berukuran 390×390, part `L_MapChoice_00` yang memakai `LMapChoice`, dan pane `P_Capture_00`. Di dalam `LMapChoice`, pane `P_Map_00` memakai material 0 dengan tekstur indeks 0 bernama `Capture^t`; `P_Material_00` memakai `Noise^r`.

Manifest BNTX same-source mengidentifikasi `Capture^t` sebagai BC5_UNORM 8×8, satu mip, 512 byte image; container member SHA256 `6cc500513685c399c42dc3ec3cdf8f68c8a2611aa76af3afeb3bd203da2648b9`. Nama dan binding texture terbukti. Tidak terbukti apakah runtime mengganti tekstur kecil itu, menggambar map ke target, atau hanya menampilkannya sebagai resource statis. Jadi konversi layout statis saja belum mereproduksi sumber/piksel thumbnail dinamis.

Data animasi yang terurai mencakup `CharaMakeMap_In`, `CharaMakeMap_Out`, `CharaMakeMap_RegionLanguageType`, `LCharaMakeMapBtn_Select`, dan `LCharaMakeMapBtn_Decide`. Tag, target, frame, dan key berasal dari BFLAN; urutan trigger, arti pilihan kartu, dan hubungan animasi ke callback belum dibuktikan. Simpan hash arsip `.zs` beserta hash member BFLYT/BFLAN/BNTX saat mengonversi aset agar nama member tidak menggantikan provenance.

## Hash sumber

Hash fisik dan ukuran di bawah dihitung ulang dari file sumber ACNH 1.0.0. Hash member BFLYT/BFLAN/BNTX dicocokkan dengan manifest hasil parser aset.

| Sumber | Byte | SHA256 |
|---|---:|---|
| `A_logic/main.elf` | 53,729,580 | `5bf707c3dc5dac0ad9635af7d336ec580f81c3f7876d0f55400d1900e3415d74` |
| `B_data/EventFlow/Tutorials_Prologue1_Charactermaking.bfevfl` | 29,072 | `cbf8fc7e4f5df544398f8dfd4b401f558bf386862af1abac72b8ab57c1d8688d` |
| `B_data/EventFlow/Info/BindInfo.byml` | 7,280 | `d5867e0729d4d0eb222c27ff8a6b5cdc0ac401f34feadd3353f420c36368e999` |
| `Layout/CharaMakeMap.Nin_NX_NVN.zs` | 53,194 | `873d26ca41ba4b982cc96b55daf68adcdc657099be50626266615b3a9f2b6700` |
| `Layout/LCharaMakeMapBtn.Nin_NX_NVN.zs` | 43,866 | `04bb82e3cbd7c02109af61f3d76731b1188d32e6d748a044ccb78c5ce397fb34` |
| `Layout/LMapChoice.Nin_NX_NVN.zs` | 3,210 | `d53a3adecc2b6a30586f46fa62b3a59dee533110d70e9ccf3c69b68cb6108cc1` |

Lihat [JSON evidence](../output/ui_island/map_select_page_binding_native_20261107.json) untuk alamat, raw relocation, edge, member, animation, dan hash lengkap. JSON divalidasi dengan `python3 -m json.tool`. Hanya dua file baru ini ditambahkan; tidak ada report lama yang diedit dan tidak ada commit/push.
