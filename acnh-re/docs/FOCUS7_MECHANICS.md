# Fokus tujuh sistem: peta bukti dan hasil pengujian

Cakupan mengikuti arahan pengguna: fisika/collision, gerakan pemain, terrain,
ground dinamis, pemeriksaan posisi, NPC/navigasi, serta item/alat/crafting.
Model dan sound memakai katalog sebagai referensi. Godot tidak dikerjakan.
Seluruh mekanik tujuh sistem belum dinyatakan selesai.

Lanjutan terbaru: [terrain runtime, bitset dan evaluator NPC](WORLD_NAV_BRIDGE.md).
Ada **1.568 kasus tambahan** pada writer ketinggian/flag, callback node,
biaya default, flood-fill dan jalur evaluator, sehingga total helper/blok
menjadi **1.135.577**. [Tahap sebelumnya](NPC_NAVIGATION_KERNEL.md) menambah 2.083 kasus.
Status terbaru per jalur dijelaskan pada laporan lanjutan
dan `output/mechanics/continuation_frontier.json`; angka tahap lama di bawah
tetap menjadi riwayat pembuktian.

## Peta lintas sistem

`output/mechanics/focus7/summary.json` menjadi pintu masuk. Peta ini menghubungkan:

- 69 tabel parameter, beserta tipe/offset kolom dan kandidat pembaca hash native;
- empat berkas konfigurasi PlayerActor/NPC, mempertahankan nilai dan descriptor;
- 55 graf AI_NPC EventFlow; 53 di antaranya memiliki total 1.233 kemunculan action/query yang terindeks;
- seluruh 1.233 kemunculan AI tersebut cocok exact dengan entry registry handler;
- 67 state NPC dengan indeks/descriptor dan 201 target callback asli yang terverifikasi;
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
menjadi -abs(v). Ketiga helper tersebut membentuk parameter. Pembaruan posisi
0xdac550 dan consumer hasil animasi kini sudah diuji terpisah pada tahap
lanjutan; input, integrasi gravitasi dan solver lengkap tetap terbuka.

Lanjutan terbaru juga menjalankan pemecah velocity XYZ 0x1d280 dan blok
pemanggil pemain 0xe17e54 sampai sebelum 0xe17e94. Ada 1.569 kasus baru. Fungsi
solver mengembalikan tiga float pada S0/S1/S2; N0 tetap membagi komponen Y
dengan nol. Ini belum menjadi pembuktian integrator gerak lengkap atau landing.

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
dipakai jalur ground dinamis. Tahap lanjutan menguji gerbang task Stage/world
dan selector dengan item kosong; pemilihan map oleh item context terisi dan
loader map belum dijalankan. Konversi preset 14 byte ke record runtime 52 byte
juga masih terbuka.

Pada tahap context terisi, item context telah dijalankan untuk seluruh 173
pasangan item lantai dan RoomFloorParam. Empat belas lantai mengaktifkan
HasJmp. State 17/18 memilih variasi 2/3 lewat Horizon XOR bit orientasi, dan
ketiadaan resident map memakai fallback Floorboards. Sebanyak 1.131 kasus
mencakup 42 kontrol query ground aktif/nonaktif. Tahap terbaru menambah 2.278
kasus resident map: file `.pbc`, transform posisi, Rotatable, kesiapan resource
dan consumer ground. Map dibentuk untuk pengujian; PBC asli tidak tersedia.
Atribut 7 dari map terpilih mempertahankan base tanpa fallback Floorboards.
Ini override RoomFloor, bukan bukti editor terrain pulau selesai.

Tahap terbaru menjalankan writer runtime 0x180d20: 48 byte awal record 52 byte
dikonsumsi sebagai 12 float ketinggian. Pada atribut sektor 0 yang diuji, batas
selisih internal dan antar sel 1,25 serta word flag dapat ditelusuri ke callback
node navigasi dan A*. Constructor preset 14 byte, PBC asli dan live terraform
tetap terbuka; arti seluruh field source tidak disimpulkan dari stride yang sama.

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
pathfinding dan obstacle avoidance belum diuji end-to-end. Tahap terbaru
menjalankan registrasi 67 state dan 201 dispatcher sampai handler tujuan, sebelum
badan handler berjalan. Tambahan 333 kasus menguji request/status navigasi,
polling dengan child tidak aktif dan blok batas grid/escape. Ini belum menjadi
graf transisi lengkap atau jumlah seluruh state NPC dalam executable.

Kernel A* asli kini dieksekusi dalam 619 pencarian pada grid yang disiapkan,
dibandingkan dengan Dijkstra untuk reachability, legalitas langkah dan biaya.
Callback biaya/heuristik, extractor/list pool, batas 256 node, target/lookahead
dan bitset eligibility juga diuji. Sepuluh rantai native menghubungkan hasil
pencarian ke consumer tanpa mengganti path di tengah. Producer terrain/collision
menjadi grid, worker async, steering dan seluruh scheduler tetap terbuka.

Tahap world kini membuktikan sebagian producer runtime dan classifier biaya,
flood/wrapper versus queue oracle serta jalur evaluator 0xc87710 hingga return.
Arrival memakai jarak XZ dengan batas strict; waypoint mempertahankan Y aktor;
expired wait memakai RNG asli. Seluruh evaluator, actor predicates, lifecycle
async dan integrasi posisi/physics belum terbukti penuh.

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
recipe, equip, remake dan interaksi furnitur. Pemeriksa kecukupan pada cache
yang sudah terisi kini diuji pada tahap lanjutan. Pengumpulan inventory asli,
pengurangan bahan, unlock resep dan durability belum terbukti lengkap.

Producer A/B/C kini dijalankan dengan record input: salinan20/20/5.000 slot,
batas scan20/20/1.600, jumlah stack, u16 wrap dan node list. Ada 722 kasus,
termasuk 96 alur producer ke pemeriksa requirement. Save-wrapper parent dan
transaksi pengurangan bahan belum dijalankan; nama pocket/storage belum
ditetapkan untuk A/B/C.

## Cakupan yang masih terbuka

| Area | Langkah pembuktian berikutnya |
|---|---|
| Fisika/collision | Penetration response, gesekan, moving-body solver, makna lengkap mask |
| Gerakan | Producer input/state/velocity/gravity, full frame, seluruh traversal dan timestep |
| Terrain | Loader runtime dan pembaruan setelah edit, seluruh syarat placement |
| Ground dinamis | PBC asli/field opaque, loader/async/lifetime dan override selain RoomFloor |
| Posisi | Kandidat spatial query, registry actor dan seluruh filter/type |
| NPC/navigasi | Sisa producer world/surface classes, actor predicates, worker async, steering, scheduler dan transisi AI |
| Item/alat/crafting | Akses record save, transaksi bahan, unlock dan durability |

Tahap pemetaan awal di dokumen ini menambah **6.235 kasus native**, terpisah
dari pemetaan statis 292 parameter, dan mencapai total 1.116.466. Lanjutan
berikutnya menambah 6.828 menjadi 1.123.294. Tahap context terisi menambah 3.926
menjadi 1.127.220, termasuk 504 pendukung SDK. Tahap resident/NPC menambah 4.706
menjadi **1.131.926**, termasuk 1.825 pendukung arsip. Pemeriksaan BYML tetap
dihitung terpisah. Angka validasi bukan persentase penyelesaian tujuh sistem.

Tahap kernel navigasi menambah 2.083 menjadi **1.134.009**. Seluruh tambahan
adalah kasus mekanik/blok; tidak ada tambahan tes pendukung SDK/arsip.

Tahap world menambah 1.568 menjadi **1.135.577**. Semua tambahan merupakan kasus
mekanik/blok dengan context yang dinyatakan.

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
- output/mechanics/inventory_requirements_native.json
- output/mechanics/player_position_native.json
- output/mechanics/player_root_motion_native.json
- output/mechanics/ground_context_gate_native.json
- output/mechanics/continuation_frontier.json
- output/mechanics/room_floor_ground_native.json
- output/mechanics/inventory_cache_native.json
- output/mechanics/ballistic_velocity_native.json
- output/mechanics/sdk_memory_native.json
- output/mechanics/resident_floor_map_native.json
- output/mechanics/native_archive_verification.json
- output/mechanics/npc_state_registry_native.json
- output/mechanics/npc_navigation_request_native.json
- output/mechanics/resident_npc_progress.json
- output/mechanics/active_context_progress.json
- output/mechanics/npc_pathfinding_native.json
- output/mechanics/npc_route_handoff_native.json
- output/mechanics/npc_route_target_native.json
- output/mechanics/npc_navigation_kernel_map.json
- output/mechanics/npc_navigation_progress.json
- output/mechanics/terrain_nav_flags_native.json
- output/mechanics/npc_reachable_mask_native.json
- output/mechanics/npc_route_evaluator_native.json
- output/mechanics/world_nav_bridge_map.json
- output/mechanics/world_nav_bridge_progress.json

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

Reproduksi fase terbaru mengikuti [urutan tool world/navigation](WORLD_NAV_BRIDGE.md#reproduksi).
