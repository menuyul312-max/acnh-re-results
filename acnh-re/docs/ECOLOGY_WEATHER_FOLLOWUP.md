# Lanjutan cuaca, pola langit, dan pemicu EventFlow

Audit ini menutup satu bagian terbatas dari `weather-beyond-day-pattern`: konversi kode hujan pada cuaca bersalju, satu jalur perubahan pola cuaca EventFlow, dan inventaris nama cuaca khusus yang dapat dibaca dari biner. Bukti native tidak mencakup pemuat cuaca lengkap atau penjadwalan aktor langit.

## Konversi hujan saat periode salju

**[PSEUDO]** `0x204480(world, hour)` mengambil kode pada entri jam dari tabel pola yang dipilih `0x201b90`. Setelah itu ia memanggil `0x202490(world, byte[+0x651da], byte[+0x651db], 4)`. Bila hasil bertanda dari selector `4` bernilai sedikitnya `1`, kode `4` menjadi `6` dan kode `5` menjadi `7`; kode lainnya dilewatkan tanpa perubahan. `0x204590` lalu menguji `(kode | 1) == 5`, sehingga hanya kode efektif `4` atau `5` yang cocok. Di `0x5b9270`, pemeriksaan ini menjadi gerbang item ikan `0x8ec` Sirakansu.

**Terbukti native, dengan input terkendali.** Emulasi menjalankan instruksi asli `0x204480` dan `0x204590` pada 24 jam, delapan kode masukan, dan predicate selector-4 mati/hidup: 96 perbandingan, tanpa mismatch. Matriks hasil ada di [`weather_remap_native.json`](../output/gameplay/ecology_weather_followup/weather_remap_native.json). Rig mengendalikan nilai pulang `0x201b90`, nilai predicate `0x202490`, dan getter vtable parameter jam sintetis. Karena itu uji ini membuktikan cabang konversi dan gerbang kode, tetapi belum membuktikan cara game membentuk predicate salju atau memuat objek cuaca.

## Pola EventDay00 dan cuaca khusus

**[EF]** `System_GrowUp_WeatherControl.bfevfl` memuat dua aksi `EventFlowActionSetWeatherPattern`, masing-masing dengan `PatternName=EventDay00`: satu sebagai entry `FirstDay`, satu pada cabang entry `Root`. Jalur mentah `Root` adalah `EventBranch` hasil `0` → pemeriksaan `cLand:TkkFirstLive` hasil `1` → pemeriksaan `cLand:IslandEvaluationClearTkkLive` hasil `0` → aksi `EventDay00`. Semantik nilai Bool mengikuti aturan EventFlow yang sudah tercatat: case `0` = flag ON, case `1` = flag OFF.

**[TBL] + [PSEUDO]** Registry handler mengikat aksi itu ke slot execute `0x315e80`. Handler memanggil `0x206f50`, yang mencari nama pola di daftar pola cuaca dan meneruskan indeks yang cocok melalui `0xfdddf0` pada offset manager `+0x651e8`. Query `EventFlowQueryEnvSpecialWeather` berakhir pada slot evaluate `0x3f62f0`.

**[EF]** Saya memindai 456 BFEVFL tambahan; semuanya lolos validator. Ada lima pemakaian `EnvSpecialWeather` dan dua aksi `SetWeatherPattern`. `SNPC_ows` memberi nilai query `3` cabang dialog tersendiri di dua tempat. `NNPC_FreeB` dan `Demo_PublicAnnouncement_40_CmnNoNews` juga bercabang untuk sejumlah nilai `1–9`. Angka cabang itu belum saya petakan ke nama cuaca khusus.

**[PSEUDO]** String enum pada `0x26b9c0` berisi nama `cBeforeMeteor`, `cMeteorShower`, `cRainbow`, `cWRainbow`, `cBeforeAurora`, dan `cAurora` pada indeks `12–17`. Inisialisasi actor `0x64400` mendaftarkan `ActorRainbow`/`Rainbow`, dan `0x68e50` mendaftarkan `ActorShootingStar`/`ShootingStar`. Ini membuktikan kosakata enum dan registrasi tipe actor; belum ada bukti bahwa indeks EventFlow `0–9` sama dengan indeks enum tersebut atau bahwa salah satu actor dipicu oleh kondisi tertentu. `0xda58d0` menyentuh `WishStarCount` dan `PrayShootingStar`, tetapi jalur itu juga tidak menetapkan jadwal hujan meteor.

Indeks flow, hash sumber, pemakaian handler, serta kosakata enum tersimpan di [`sky_event_index.json`](../output/gameplay/ecology_weather_followup/sky_event_index.json). Teks dialog tidak dimasukkan.

## Batas dan pekerjaan terbuka

- Semantik internal `0x202490` dan state manager lingkungan belum diuji native; emulasi hanya menyuntikkan nilai predicate agar cabang `0x204480` dapat dijalankan.
- Hubungan indeks `EnvSpecialWeather` dengan `cMeteorShower`/`cRainbow`/`cAurora`, peluang dan jadwal pemicu, kabut, serta aktivasi aktor langit masih terbuka. Registrasi actor dan string enum sendiri tidak membuktikan pemicu runtime.
- Aturan `AppearWeather` serangga pulau utama dan penerapan cuaca pada jalur titik spawn `AppearFg` belum ditemukan; undian umum `0x957940` yang sudah dibuktikan tidak membaca `AppearWeather`.
- Regenerasi lapangan end-to-end tidak dikerjakan pada putaran ini.

Tidak ada berkas sumber yang hilang untuk audit terbatas ini: ExeFS `main`, index SQLite, EventFlow, dan `Env/GameEnv.szs` tersedia. Batas integrasi muncul karena manager dan objek parameter lingkungan yang sudah dimuat tidak tersedia sebagai fixture runtime; `GameEnv.szs` yang diperiksa adalah paket resource lingkungan, bukan fixture manager tersebut.
