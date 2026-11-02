# Lanjutan: lantai aktif, producer bahan dan pembentuk lintasan

Tahap ini melanjutkan bagian yang terbuka setelah commit `379531f`.
Semua alamat adalah VA ELF build ACNH 1.0.0 yang sama, SHA-256
`5bf707c3dc5dac0ad9635af7d336ec580f81c3f7876d0f55400d1900e3415d74`.
Godot tidak diubah. Model/sound tetap memakai katalog sebagai referensi.

**3.926 kasus baru lolos tanpa mismatch:** 3.422 kasus mekanik dan 504 kasus
pendukung SDK. Total helper/blok menjadi **1.127.220**. Pemeriksaan BYML tetap
2.546.185 dan dihitung terpisah. Ini volume validasi pada konteks terkontrol,
bukan persentase penyelesaian game. Seluruh tujuh sistem belum selesai.

| Area | Sebelumnya | Yang kini terbukti | Kasus baru |
|---|---|---|---:|
| Ground aktif | Gerbang Stage/world dan item context kosong | Item lantai asli, pemilihan variasi, fallback atribut dan pengaruhnya pada query ground | 1.131 |
| Bahan crafting | Reader A/B/C dengan counter yang disiapkan | Producer asli membentuk counter dari record item lalu memberi hasil ke reader | 722 |
| Gerakan/gravitasi | Parameter dan consumer posisi/root motion | Pemecah velocity XYZ dan blok pemanggil state pemain | 1.569 |
| Pendukung SDK | strcmp sudah teruji pada tahap sebelumnya | memcpy/memset asli untuk menjalankan producer tanpa stub | 504 |

## Jalur ground yang ditelusuri adalah override lantai ruangan

`0x157ab0` mengambil item context, membuka definisi ItemParam, memeriksa ordinal
native `ItemKind.RoomFloor`, lalu membaca `ItemParam.FloorTableId`. Nilai itu
menunjuk ke `RoomFloorParam`; tidak menunjuk ke FieldOutsideParts.
Seluruh **173** pasangan `RoomFloorParam.ItemTableId -> ItemParam.FloorTableId`
cocok dengan ID lantai pada data sumber.

Dari 173 lantai, **14** memiliki `HasJmp=1`, dan 159 lainnya nol. Getter lengkap
`0x856270` dan metadata discovery-nya kini berjalan pada BCSV asli. Bila HasJmp
nol, selector mengembalikan sentinel7 sebelum resolver map dipanggil.

Dengan task Stage/world aktif dan item lantai terisi, klasifikasi context
menghasilkan pemilihan berikut:

| Nilai state context yang diuji | Kategori | Variasi map |
|---|---:|---:|
| 1 | 1 | Selector mengembalikan7 |
| 2..5 | 2 | 0 |
| 6..16 | 3 | 1 |
| 17..18 | 4 | 2 atau3 |
| 19 | 5 | Selector mengembalikan7 |
| Nilai lain yang diuji, termasuk batas signed | 3 | 1 |

Pada state 17/18, variasi adalah `2 + (Horizon XOR orientation_bit6)`. Horizon
dibaca melalui `0x8563d0`, lalu `0x881e50` menggabungkannya dengan bit context.
**Rotatable bukan field pembentuk XOR tersebut.** Rotatable digunakan di bagian
resolver yang berbeda. Pemisahan ini diperiksa lewat target BL, hash kolom,
metadata offset yang ditemukan native, dan variasi yang diamati saat eksekusi.

Uji memasang resource-manager dengan jumlah resident map nol. Resolver asli
`0x16e6d0` mengembalikan null, kemudian `0x855fa0` membaca
`RoomFloorParam.Floorboards`. `0x18ee80` menghubungkan ID itu ke baris
ColGroundAttributeParam. Pada context tanpa remap vector yang diuji, hasilnya
adalah **indeks baris**, yang tidak selalu sama dengan UniqueID. Contoh lantai
170 memiliki Floorboards ID51 yang menjadi indeks48.

Sampel sumber yang masuk fallback mencakup lantai atletik, sidewalk, platform,
arena, moss, ice floe, oasis, fish tank, volcano dan river. Nama resource dan
ID sumber masing-masing disimpan di JSON.

### Pengaruh override sudah dibedakan dari terrain base

Empat belas lantai HasJmp diuji melalui tiga fungsi lengkap: `0x187420`
(WaterCheck seluruh titik), `0x1874f0` (PlayerNoEntry salah satu titik), dan
`0x187610` (tepat dua titik WaterCheck). Terrain base sengaja dipilih agar hasil
query true ketika context Stage dinonaktifkan. Mengaktifkan context lantai
mengganti atribut sehingga hasil berubah menjadi false pada data fallback ini.

Ada **42 kontrol berpasangan aktif/nonaktif**, serta tiga kasus lantai HasJmp
nol yang membuktikan sentinel7 mempertahankan terrain base. Jadi pengujian
integrasi tidak hanya memanggil fungsi yang kebetulan menghasilkan nilai sama.
Blob BCSV asli dipastikan tetap identik setelah seluruh uji.

Yang belum dijalankan: resident JMP resource/container, pemilihan file map yang
tersedia, transform posisi/rotasi ketika map benar-benar terpilih, dan loader.
Tidak ada klaim jalur terrain pulau atau editor terraforming selesai dari hasil
override RoomFloor ini. Peta fokus kini mencakup **69 tabel**, bertambah satu
dengan RoomFloorParam.

Data: [room_floor_ground_native.json](../output/mechanics/room_floor_ground_native.json).
JSON merujuk ItemParam, ItemKind, RoomFloorParam dan ColGroundAttributeParam,
beserta source ID, blob dan checksum.

## A/B/C kini dibentuk oleh producer asli

Tiga komponen cache memakai vtable asli dari constructor `0xed8870`:

| Komponen | Loader lengkap | Producer asli pada slot+0x40 | Record disalin | Batas slot dipindai |
|---|---|---|---:|---:|
| A | 0xeda040 | 0xee72b0 | 20 | 20 |
| B | 0xeda160 | 0xee7550 | 20 | 20 |
| C | 0xeda280 | 0xee7800 | 5.000 | 1.600 |

Pengujian memasok record dengan layout yang ditelusuri dari reader, count u32,
metadata, dan node pool yang direkonstruksi. Instruksi copy, normalisasi item,
lookup kind, penghitungan stack, pembuatan counter dan node list tetap asli.
SDK memset yang dipanggil melalui PLT juga merupakan implementasi asli dari
modul sdk unggahan, bukan pengganti Python.

Count dipakai sebagai unsigned: nilai `0xffffffff` dipersempit ke batas slot,
seperti count yang melebihi20 atau1.600. C tetap menyalin seluruh 5.000 word,
tetapi hanya slot aktif sampai 1.600 yang mengisi counter. Normalized-ID array
di luar count aktif tidak ditulis oleh loader ini.

### Jumlah stack dan batas integer

ItemKind memakai `MultiHoldMaxNum`, hash `4c9ba961`. Pada item normal tanpa
wrap/remake yang diuji:

- Bila MultiHoldMaxNum kurang dari 2, satu item dihitung sebagai1.
- Selain itu, kandidat jumlah adalah `((low16(FreeParam)+1)&255)`.
- Kandidat yang melebihi MultiHoldMaxNum menjadi 1; kandidat nol tetap nol.
- Penjumlahan counter u16 berputar modulo 65.536.

Uji memakai item2511,5983,2624 dan 109: batas stack30,10,99 dan 0. Kasus Weed
2624 menunjukkan1.600 stack berisi 99 dihitung secara matematis 158.400 tetapi
counter native menjadi **27.328** setelah narrowing u16. Nilai FreeParam255
menghasilkan kandidat jumlah nol, bukan256.

Loader copy menghapus mask/list slot pada cache. Mask tersebut tidak sama
dengan word metadata terakhir yang disalin dari record sumber. Mengisi mask
cache secara terpisah lalu menjalankan producer asli menghasilkan node
berisi indeks slot dan word item. **Item yang masuk daftar ini tetap ikut
dihitung dalam counter** pada producer yang diuji; mask tidak langsung
mengurangi ketersediaan bahan.

Ada 264 kasus A,264 kasus B dan 98 kasus C. Seluruh array15000 counter u16
dicocokkan, ID normalisasi dan word salinan diperiksa, serta source dipastikan
tidak berubah. Cabang node list terisi tercapai pada 220 skenario.

Tambahan **96 kasus** menjalankan producer A/B/C lalu langsung memanggil
`0xee0be0`. Counter tidak diisi manual. Opsi memasukkan C dan flag kecukupan
yang tetap false setelah kekurangan bahan cocok dengan pembuktian sebelumnya.

Yang masih terbuka: perolehan record dari save-wrapper dalam parent cold-cache,
binding A/B/C ke nama member save, item wrap/remake/special count, serta transaksi
pengurangan bahan dan pemberian hasil. Nama pocket/storage belum ditetapkan
tanpa binding tersebut. Tidak ada item inventory asli yang dikonsumsi oleh uji.

Data: [inventory_cache_native.json](../output/mechanics/inventory_cache_native.json).

## Pemecah lintasan mengembalikan tiga float

Signature pseudocode `0x1d280` yang hanya mengembalikan float melewatkan dua
hasil. Instruksi asli mengembalikan **VX/VY/VZ di S0/S1/S2**. Dua pemanggilnya
berada pada state gerakan `0xe17cb0` dan `0xe42b30`.

Input: start vec3 pada X0, target vec3 pada X1, durasi pada W2, gravitasi pada
S0 dan cap vertikal pada S1. Untuk N positif, model native membentuk urutan
velocity gravitasi dari nol: kurangi magnitude gravitasi pada tiap langkah;
cap bawah diterapkan hanya jika argumen cap negatif. Jumlah displacement
gravitasi dijumlahkan dengan f32 berurutan.

```
VX = (targetX - startX) / N
VY = ((targetY - startY) - gravity_displacement_sum) / N
VZ = (targetZ - startZ) / N
```

Contoh `start=[0,0,0]`, `target=[10,5,-5]`, N10 dan gravitasi-0,25 tanpa cap:
gravity sum=-13,75, sehingga hasil `[1.0,1.875,-0.5]`. Jumlah gravitasi ini mulai
dari velocity nol; hasilnya tidak otomatis membuktikan semua integrator runtime
memakai aturan cap yang sama setelah initial VY ditambahkan.

**N0 tidak mengembalikan vektor nol secara menyeluruh.** X/Z memakai nilai
default native, tetapi komponen vertikal tetap dibagi nol: deltaY nonzero
menghasilkan infinity bertanda, deltaY nol menghasilkan NaN. Durasi memakai
32 bit rendah; durasi sangat besar tidak dijalankan karena loop-nya linear.
Satuan durasi dan frame rate belum ditetapkan dari helper ini.

Ada 1.500 kasus finite yang cocok bit per bit dengan model recurrence, enam
kasus N0 dan tiga alias durasi64-bit. Buffer start/target dan guard tidak berubah.

### Hasil solver tersambung ke field pemain

Blok instruksi asli `0xe17e54` sampai sebelum `0xe17e94` dijalankan pada 60
context positif yang disiapkan. Blok ini memanggil getter gravitasi typed,
solver `0x1d280`, lalu pembentuk motion `0xdb17f0`. Register X19/W22 dan target
di stack disiapkan sesuai input blok, bukan menjalankan prefix state lengkap.

Blok menyimpan velocity XYZ pada player+0x574 dan triplet
`[velocityY, -0.0, configuredGravity]` pada player+0xf58. Semua field dan guard
cocok; posisi actor belum diubah oleh blok ini. Ini hubungan nyata antara
parameter gravitasi, hasil solver dan state pemain, dengan batas blok yang
eksplisit. Input/state lengkap, integrasi gerak, collision dan landing masih
terbuka.

Data: [ballistic_velocity_native.json](../output/mechanics/ballistic_velocity_native.json).

## Dependency SDK dan reproduksi

Tool memasang alamat memcpy, memset dan strcmp asli dari modul sdk ke GOT
import main. Instruksi main/SDK tidak dipatch. Uji baru mencakup 288 kasus memset
dan 216 kasus memcpy nonoverlap, panjang0..30.000, alignment, return pointer dan
guard. Ini504 kasus pendukung, bukan504 aturan gameplay.

SDK text ini cukup untuk rutin yang tercapai pada uji; initializer SDK, TLS,
syscall dan seluruh runtime console tetap belum dijalankan. Blob executable
atau arsip sumber asli tidak dipublikasikan.

```bash
python tools/native_sdk_memory.py
python tools/room_floor_ground_native.py
python tools/inventory_cache_native.py
python tools/ballistic_velocity_native.py
python tools/focus7_catalogue.py
python tools/mechanics_continuation.py
python tools/active_context_followup.py
```

Jalankan agregator fase terakhir setelah agregator historis agar frontier
terbaru tetap terpasang. [Progress JSON](../output/mechanics/active_context_progress.json)
memisahkan kasus mekanik dan SDK. [Frontier](../output/mechanics/continuation_frontier.json)
mencatat sisa pembuktian, termasuk collision solver, terraform aktif, registry
spatial, pathfinder/scheduler NPC, durability, unlock dan transaksi inventory.
Area NPC dan terraform tidak mendapat bukti runtime tambahan pada tahap ini.
Pembaruan berada langsung di tree repo; ZIP lama tetap snapshot historis.
