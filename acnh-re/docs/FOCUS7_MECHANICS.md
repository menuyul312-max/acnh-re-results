# Fokus tujuh sistem: peta bukti dan hasil pengujian

Cakupan mengikuti arahan pengguna: fisika/collision, gerakan pemain, terrain,
ground dinamis, pemeriksaan posisi, NPC/navigasi, serta item/alat/crafting.
Model dan sound memakai katalog sebagai referensi. Godot tidak dikerjakan.
Seluruh mekanik tujuh sistem belum dinyatakan selesai.

## Peta lintas sistem

`output/mechanics/focus7/summary.json` menjadi pintu masuk. Peta ini menghubungkan:

- 68 tabel parameter, beserta tipe/offset kolom dan kandidat pembaca hash native;
- empat berkas konfigurasi PlayerActor/NPC, mempertahankan nilai dan descriptor;
- 55 graf AI_NPC EventFlow; 53 di antaranya memiliki total 1.233 kemunculan action/query yang terindeks;
- seluruh 1.233 kemunculan AI tersebut cocok exact dengan entry registry handler;
- 67 label state NPC native yang tersedia dalam indeks string;
- 1.261 kemunculan action/query terkait kata kunci item, alat dan crafting;
- 221 entry handler native, termasuk factory, constructor dan vtable yang sudah
  dipetakan pada tahap sebelumnya.

Hash kolom dapat sama pada tabel berbeda. Referensi instruksi berdasarkan hash
ditandai kandidat, bukan otomatis pembaca unik suatu tabel. Pemilihan handler
item/alat memakai kata kunci dan tidak mewakili semua fungsi gameplay. State NPC
yang belum memiliki label atau rujukan pada indeks tetap mungkin ada.

## Fisika/collision dan gerakan pemain

Trace instruksi constructor PlayerActor pada 0xdc98f0 memetakan seluruh 194
descriptor konfigurasi bernama ke offset member. Semuanya cocok dengan store
nama pada pseudocode constructor. Ada 87 kandidat akses member setelah call
getter parameter, termasuk gravitasi, batas kecepatan dan radius collision.
Ini bukti statis; constructor lengkap dan semua consumer belum dieksekusi.

Contoh data yang tersedia dari BYML:

| Descriptor | Nilai data | Offset member |
|---|---:|---|
| mDefaultGravity.f32 | -0.25 | 0x780 |
| mSpeedYMin.f32 | -2.0999999046325684 | 0x7b0 |
| mObjCollisionRadius.f32 | 5.0 | 0x210 |
| mMoveSpeedMax.f32 | 1.7999999523162842 | 0x750 |

Satuan, frekuensi update, serta keterjangkauan seluruh fitur tidak disimpulkan
dari nama. Beberapa descriptor swim/dive ada pada data; keberadaannya tidak
membuktikan fitur tersebut dapat digunakan pada build ini.

Fungsi lengkap yang kini diuji:

- 0xdb17b0 membaca gravitasi melalui resolver parameter dan getter typed asli;
- 0xda91a0 membentuk tiga float dari batas kecepatan vertikal dan gravitasi;
- 0xdb17f0 membentuk tiga float dengan aturan override negatif dan fallback.

Ada 410 kasus tanpa mismatch, termasuk guard bytes dan signed zero. Getter
typed float pada 0x37a50 mengembalikan pointer member+0x24. Nilai gravitasi ada
pada parameter object+0x7a4 dan mSpeedYMin pada +0x7d4.

Rangkaian menjalankan 0xe6fb50, 0xe70ea0, 0x5df70 dan getter typed asli. Registry
actor-type, fallback parameter object dan field direkonstruksi. Jalur yang diuji
memakai entry registry kosong dan fallback yang sudah diinisialisasi. Constructor
serta loader parameter tidak dijalankan; nilai BYML di atas tidak otomatis
menjadi bukti nilai yang selalu dipakai runtime pada semua konteks.

Pada 0xdb17f0, override gravitasi negatif dipakai langsung; nilai nonnegative
memakai gravitasi konfigurasi. Argumen limit negatif dipakai, selain itu fallback
native berupa **-0.0**. Pada 0xda91a0, batas nonzero menjadi magnitude negatif,
tetapi signed zero mengikuti urutan instruksi aslinya, bukan disederhanakan
menjadi -abs(v). Ini masih pembentukan parameter, bukan integrasi posisi/solver.

## Terrain dan ground dinamis

Lookup map 0x18adf0 kini dijalankan lengkap bersama helper koordinat asli.
Header map memuat width pada +4, height +8, origin index s32 +12/+16; record
dimulai +20, stride 52 byte. Empat byte atribut berada di offset 48..51.

Posisi dikurangi origin*5, lalu dikonversi memakai aturan index asli yang sudah
diuji sebelumnya. Di dalam satu sel, u/v adalah offset lokal dari index*5.
Dengan operasi f32 terpisah:

```
a = v - u
b = (u + v) - 5
a >= 0 dan b >= 0: byte sektor 2
a >= 0 dan b <  0: byte sektor 1
a <  0 dan b >= 0: byte sektor 3
a <  0 dan b <  0: byte sektor 0
```

Jadi pembagian adalah empat sektor segitiga berdasarkan dua diagonal, bukan
empat kotak kuadran. Posisi tepat di kedua diagonal mengikuti cabang >=; pusat
sel masuk sektor 2. Map null/posisi di luar map menghasilkan 7. Semua byte u8
dikembalikan apa adanya, termasuk 7; inheritance dikerjakan consumer berikutnya.

Sebanyak 2.494 kasus cocok: origin positif/negatif, enam sel, batas/diagonal,
map null, posisi di luar map, dan seluruh 256 nilai byte pada tiap sektor.
Buffer sumber dan guard dipertahankan. Ini memvalidasi inti lookup map yang
dipakai jalur ground dinamis; pemilihan map oleh room/object/context aktif dan
loader map belum dijalankan. Konversi preset 14 byte ke record runtime 52 byte
juga masih terbuka.

## NPC dan navigasi

Seluruh 98 descriptor bernama NpcActivityParam dipetakan ke store nama/offset
member constructor 0xc9f360 dan cocok dengan pseudocode. Pemiliknya memanggil
constructor tersebut pada 0xc9e40c; ekspresi member pada constructor pemilik
menempatkannya di +0x1070. Ini bukti statis, bukan eksekusi constructor NPC.

Konfigurasi memberi titik masuk nyata: sight length/angle, personal-space
radius, ambang interest, timer aktivitas, serta jarak mulai/berhenti mengejar
serangga. Tabel NpcLife menambah bobot waktu indoor/outdoor, hobi, musim dan
parameter hujan. Peta JSON menyimpan data dan rujukannya tanpa menganggap nama
parameter sudah membuktikan algoritme keputusan.

Seluruh 55 graf EventFlow AI yang tersedia kini disertakan: 1.414 node,
1.401 tautan lokal, 236 entry point dan 181 call subflow. Index target event
dan entry point lolos pemeriksaan; seluruh target subflow tersedia pada korpus.
Satu subflow menuju graf di luar subset AI, dengan path decoded target tetap
dicatat. Dua graf tanpa action/query pada indeks adalah AI_NPC_Rco_FirstLiveInvite
dan AI_NPC_Rco_TalkAboutPrize. Jumlah graf berbeda dari jumlah flow yang memiliki
pemanggilan action/query.

Graf AI dan handler native-nya tersedia dalam satu peta terfokus.
Ini melengkapi hubungan skrip ke factory/vtable; C++ scheduler, pemilihan route,
pathfinding dan obstacle avoidance belum diuji end-to-end. Nama 67 state bukan
graf transisi lengkap dan bukan jumlah seluruh state NPC dalam executable.

## Item, alat dan crafting

Getter bahan 0xedac50 kini dijalankan lengkap pada seluruh **552 resep x enam
slot = 3.312 kasus sumber**. Ada 1.020 slot yang menulis output dan 2.292 yang
membiarkannya tetap. Semua item output delapan byte, jumlah u8, dan guard cocok.

Aturan yang penting untuk konversi:

- Material 0xfffe atau byte rendah jumlah sama dengan nol: output **tidak ditulis**.
- Resep tidak ditemukan, slot invalid atau pointer output null: tidak menulis.
- Recipe ID memakai 16 bit rendah; argumen slot memakai delapan bit rendah.
- Jumlah sumber disimpan u16, tetapi output memakai byte rendahnya. Nilai sintetis
  256 menghasilkan low byte nol, sehingga bukan output berjumlah nol: output
  justru tetap seperti sebelum pemanggilan.
- W0 adalah hasil boolean: satu saat output ditulis, nol saat tidak. Signature
  void dari pseudocode otomatis tidak menangkap kontrak return ini.

Seluruh rangkaian getter dan item constructor/copy asli berjalan tanpa stub.
Lookup resep yang sparse serta cache metadata direkonstruksi dari BCSV; table
loader tidak dijalankan. Total termasuk probe batas/guard adalah **3.331 kasus**.
Pemanggil harus menginisialisasi output atau memeriksa status return. Sekadar
menganggap setiap slot kosong mengembalikan item 0xfffe akan menghasilkan kontrak
yang salah.

Peta handler item/alat dan tabel mencakup jalur penelusuran penggunaan alat,
recipe, equip, remake dan interaksi furnitur. Pemeriksaan kepemilikan bahan,
pengurangan inventory, unlock resep dan durability belum terbukti lengkap.

## Cakupan yang masih terbuka

| Area | Langkah pembuktian berikutnya |
|---|---|
| Fisika/collision | Penetration response, gesekan, moving-body solver, makna lengkap mask |
| Gerakan | Input/state -> velocity -> posisi, seluruh traversal dan timestep |
| Terrain | Loader runtime dan pembaruan setelah edit, seluruh syarat placement |
| Ground dinamis | Pemilihan map dan override pada context room/object aktif |
| Posisi | Kandidat spatial query, registry actor dan seluruh filter/type |
| NPC/navigasi | Scheduler, route/pathfinder, obstacle avoidance dan transisi AI |
| Item/alat/crafting | Inventory dan transaksi bahan, unlock, durability dan semua aksi |

Tahap ini menambah **6.235 kasus native**, terpisah dari pemetaan statis 292
parameter. Kumulatif helper/blok 1.116.466; pemeriksaan BYML tetap dihitung
terpisah. Angka validasi bukan persentase penyelesaian tujuh sistem.

## Berkas utama dan reproduksi

- output/mechanics/focus7/summary.json
- output/mechanics/focus7/table_field_links.json
- output/mechanics/focus7/movement_npc_parameters.json
- output/mechanics/focus7/npc_ai_eventflows.json
- output/mechanics/focus7/npc_ai_flow_graphs.json
- output/mechanics/focus7/npc_native_state_labels.json
- output/mechanics/focus7/item_tool_event_calls.json
- output/mechanics/focus7/native_event_handlers.json
- output/mechanics/player_parameter_bindings.json
- output/mechanics/npc_activity_bindings.json
- output/mechanics/player_motion_native.json
- output/mechanics/dynamic_ground_native.json
- output/mechanics/crafting_materials_native.json

Jalankan tool berikut dengan input ELF, indeks dan output baseline yang sama:

```bash
python tools/player_parameter_bindings.py
python tools/player_parameter_bindings.py --constructor 0xc9f360 --byml 01433 --singleton 0 --output npc_activity_bindings.json
python tools/player_motion_native.py
python tools/dynamic_ground_native.py
python tools/crafting_materials_native.py
python tools/focus7_catalogue.py
```

Tool berjalan pada direktori RE, tidak membuka editor Godot. ZIP lama tetap
snapshot historis; pembaruan tahap ini berada langsung di repo.
