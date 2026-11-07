# MapSelect/cVillage ke lifecycle world: follow-up statis (ACNH 1.0.0)

Hasilnya menutup join nilai secara statis, tetapi belum membuktikan eksekusi satu lifecycle yang sama. `SaveSetFromUIResult(cVillage)` menyimpan indeks pilihan ke konteks native `+0x45f0`. Konsumen pilihan kemudian memakai indeks itu untuk memilih entry, mengambil u16 `UniqueID`, dan menulisnya ke `SaveMainField.MainFieldParamUniqueID` (`+0xcfa2a`). Routine world setup `0x565e30` membaca field save yang sama lalu memanggil loader LandMaking berdasarkan UID tersebut. Karena pemanggilan konsumen pilihan dan `0x565e30` belum dihubungkan dalam urutan runtime, belum terbukti bahwa preset yang dimuat adalah preset dari kartu yang dipilih.

Analisis ini hanya membaca executable, indeks, EventFlow, dan data dump ACNH 1.0.0. Tidak ada proyek Godot, save, atau game yang dijalankan atau diubah. PCs di bawah adalah VA ELF mentah.

## EventFlow setelah pilihan

Pada `Tutorials_Prologue1_Charactermaking.bfevfl` (source 661), cabang `Apply` saat `cLand:ValidateVillageSave` OFF memanggil `Areacheck` lalu `TerrainSelect`. Entry `TerrainSelect` menjalankan `UIMapSelectHandling {}` lalu `SaveSetFromUIResult {SaveType:cVillage}`. Setelahnya, `EndCharacterMaking` memeriksa lagi flag tersebut: cabang ON memanggil subflow `PV`, sedangkan cabang OFF mengikuti jalur pesan dan `WaitFrame`. Di `PV`, pemeriksaan ON meminta stage `cOpeningMovie`; pemeriksaan OFF menyetel `MakeVillagePlayerFlag` dan `IsFirstPrologue`. EventFlow `System_GrowUp:NewGame` (source 645) menjalankan `SaveGrowUp(cStart)` dan meminta `cMainFieldDemoLanding`.

Ini menetapkan urutan bernama pada EventFlow: map selection → penyimpanan hasil `cVillage` → alur opening/new-game. Dispatcher dari `cOpeningMovie` ke entry `System_GrowUp:NewGame`, serta hubungan aksi map-selection ke page/controller yang menampilkan kartu, belum ditemukan sebagai edge native. Factory aksi `UIMapSelectHandling` ada di `0x44cb30`, tetapi factory itu tidak mengidentifikasi `MapSelectPage` atau callback kartu.

## Indeks hasil ke UID save

Callback native `0x1243260` membaca indeks objek `+0x2cc` dan meneruskannya lewat wrapper `0x154a100` pada PC `0x124338c` ke result context `+0xae3c`. Cabang `cVillage` pada `SaveSetFromUIResult`, method `0x334650`, memanggil getter wrapper `0x154a130` pada PC `0x334d68`, mengambil u32 di hasil `+0x0c`, lalu menyimpannya ke `*0x33d1ba8+0x45f0` pada PC `0x334d80`. Nilai yang bertahan di sini adalah indeks opsi, bukan UID.

Container yang dibaca memakai empat entry. `0x529910` mengatur count `4` dan membangun entry pada callsites `0x529a80`, `0x529b90`, `0x529ca0`, dan `0x529db0`; konteks `0x5651b0` mencapai builder melalui `0x529860` pada PC `0x5651ec` jika guard builder lolos. `0x565300` memanggil cleanup/consumer `0x529e50` pada PC `0x565368`. Ketika feature dan status guard di `0x529e50` lolos, method itu membaca indeks dari member `+0x20` dan tail-branch dari PC `0x529e94` ke badan terpilih `0x529ea0`. Badan tersebut memilih `entry[index]`, membaca u16 UID dari entry `+0x0c` pada PC `0x529f34`, lalu menulisnya lewat descriptor SaveMainField pada PC `0x529f44` ke `+0xcfa2a`. Ia juga menyalin data OutsideField terpisah.

Dengan demikian, hubungan `indeks tersimpan → entry[index] → UID dalam SaveMainField` terbukti sebagai dataflow statis bersyarat. Belum terbukti bahwa indeks dari kartu yang terlihat adalah indeks entry yang sama: owner callback `0x1243260` dan edge `UIMapSelectHandling` → page/callback belum terselesaikan. Keempat UID aktual untuk satu sesi juga belum dipastikan. Penulisan `0x529f44` mengubah objek save in-memory; tidak ada serialisasi atau commit file yang dibuktikan oleh consumer ini.

## UID save ke terrain/preset loader

`0x565e30` membaca `SaveMainField.MainFieldParamUniqueID` dari offset yang sama, membungkus nilai lewat `0x558ea0` pada PC `0x56620c`, lalu memanggil `0x558ef0` pada PC `0x566220`. Wrapper itu memanggil loader `0x558f40` pada PC `0x558f28`. Loader melakukan lookup row berdasarkan `UniqueID`, membaca `FieldData`, membentuk nama `%s_LandMaking`, lalu memuat resource LandMaking dan mentransfer grid 112×96 ke akses sel runtime. `0x565e30` juga memanggil loader EventPlaza `0x5598c0` dan konsumen heap LandMaking tambahan `0x559b80`.

Join tabel yang menyatakan resource untuk UID tertentu sudah tersedia: `FieldMainFieldParam.bcsv` (source 41) memetakan UID ke stem `FieldData`; misalnya UID 0 → `FieldPresetA00` → `FieldPresetA00_LandMaking.byml` (source 2442). Itu contoh join data, bukan bukti bahwa UID 0 atau kartu tertentu dipilih saat runtime. Loader membuktikan pembacaan preset terrain; pembentukan collision/PBC, actor/model, transformasi dunia final, dan spawn tidak diselesaikan oleh rantai ini.

## Uji lifecycle dan batas bukti

Indeks `direct_calls` mencatat tepat dua pemanggil langsung `0x565e30`: `0x5662e0` pada PC `0x5665c4`, dan `0xcd270` pada PC `0xcd2c0`.

`0x5662e0` adalah jalur pembuat preset terpisah: ia mengundi/menimbang kandidat, menulis nilai UID dan OutsideField-nya sendiri, lalu memanggil `0x565e30`. Jalur ini membuktikan ada inisialisasi world dari preset tersimpan, tetapi tidak boleh disamakan dengan hasil pilihan `cVillage`.

`0xcd270` memiliki callsite ke `0x565e30` pada PC `0xcd2c0` dengan guard status. Fungsi pemanggil `0xccd40` merujuk string `ValidateVillageSave` dan memanggil `0xcd270` pada PC `0xccf1c`. EventFlow prologue memang menguji `cLand:ValidateVillageSave` setelah `SaveSetFromUIResult(cVillage)`, tetapi juga mengujinya sebelum map selection. Tidak ada edge langsung dari query EventFlow ke `0xccd40` yang ditemukan dalam indeks call langsung, jadi kemunculan uji flag sesudah pilihan belum membuktikan bahwa callsite loader tersebut berjalan pada titik itu.

Pemanggilan `0x565300` yang ditemukan berada di PC `0xfe6070`; inventaris fungsi baru menempatkannya di dalam `0xfe5fe0`, tetapi fungsi itu tidak memiliki dekompilasi lokal di dump. Indeks lama menyimpan owner callsite sebagai null. Jadi callsite ini belum memberi urutan yang menghubungkan consumer `0x529ea0` dengan loader `0x565e30`. Batas fungsi `0x529ea0` juga berbeda antar-indeks: tabel `functions` memasukkannya di rentang `0x529e50`, sedangkan `native_functions` membaginya sebagai entry `0x529ea0`; tail-branch `0x529e94` ke sana tetap membuktikan alur kontrol.

Pencarian negatif yang dibatasi pada `/workspace/acnh-re/output/index.sqlite` menghasilkan: tidak ada direct-call record dengan target `0x529ea0` (consumer dicapai dengan branch, bukan `BL`); tidak ada pemanggilan langsung dari method `0x334650` ke `0x565300` atau `0x565e30`; dan semua direct-call record ke `0x565e30` berjumlah dua seperti di atas. Ini tidak menyingkirkan dispatch virtual/EventFlow atau caller tidak langsung. Dalam tree EventFlow, `System_GrowUp:NewGame` memang meminta `cMainFieldDemoLanding`, tetapi tree itu sendiri tidak menghubungkan hasil `cVillage` ke salah satu caller native `0x565e30`.

## Status akhir

| Tepi | Status |
|---|---|
| `TerrainSelect → UIMapSelectHandling → SaveSetFromUIResult(cVillage)` | Terbukti pada EventFlow. |
| Indeks result context → field container `+0x45f0` | Terbukti sebagai dataflow native; identitas page/controller produsennya belum terbukti. |
| Indeks container → UID entry → `SaveMainField +0xcfa2a` | Terbukti sebagai consumer native bersyarat. |
| `SaveMainField +0xcfa2a` → lookup `FieldData` → loader LandMaking | Terbukti sebagai consumer native dan join data per UID. |
| Kartu yang dipilih → UID yang tersimpan → pemanggilan loader pada lifecycle new-game yang sama | **OPEN**: pemetaan kartu/entry, pemanggilan consumer pilihan, dan urutan menuju `0x565e30` belum terhubung. |
| Preset terrain → collision/PBC/actor/spawn dunia lengkap | **OPEN** di luar consumer LandMaking yang teridentifikasi. |

Ledger pasangan mencatat hash build, indeks, fungsi dekompilasi, sumber EventFlow, tabel/preset, callsite, dan hasil pencarian negatif.
