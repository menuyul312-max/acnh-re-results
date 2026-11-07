# Follow-up resource UI prolog: tekstur, material/shader, efek, font

**Tanggal:** 7 November 2026  
**Cakupan:** halaman `Title`, `CharaMake`, `DateInput`, `CharaMakeMap`, `WipePrologue`, serta UI keyboard dan dialog di sekitar penamaan pulau/api unggun. Audit ini hanya membaca index sumber/layout/katalog yang tersedia. Tidak mengubah crosswalk utama, Godot, atau file model/audio.

Ledger machine-readable: [prologue_ui_resource_family_followup_20261107.json](../output/gameplay/prologue_ui_resource_family_followup_20261107.json). Index utama yang dicek adalah [`ui_island/layouts.json`](../output/ui_island/layouts.json), [`ui_hud/resource_bindings.json`](../output/ui_hud/resource_bindings.json), [`ui_hud/font_bindings.json`](../output/ui_hud/font_bindings.json), dan [`ui_hud/page_layout_method_bindings.json`](../output/ui_hud/page_layout_method_bindings.json). Semua index UI berasal dari arsip RomFS tambahan; identitas patch archive itu belum terikat ke build 1.0.0.

## Kesimpulan

Label `OPEN` 28/28 pada keluarga tekstur, material/shader, efek, dan font di crosswalk besar terlalu kasar untuk menyatakan bahwa tidak ada yang bisa dibaca. Pada halaman prolog, pane→material→BNTX dan pane→font alias sudah dapat ditautkan secara struktural. Dua layout campfire-related juga memiliki relasi material→GLSL bernama. Namun, UI action EventFlow→page instance belum dibuktikan; keberadaan layout dan resource di archive supplemental tidak membuktikan halaman itu dijalankan pada build target.

| Keluarga | Status tertinggi pada target prolog | Batas yang masih OPEN |
|---|---|---|
| Tekstur | **CONSUMER_JOINED**: pane BFLYT menunjuk material; material menunjuk indeks texture; nama cocok unik ke BNTX di archive Layout yang sama. | Trigger layar/runtime dan kecocokan patch 1.0.0. Gambar peta terpilih tidak ditemukan sebagai tekstur statis. |
| Material/shader | **CONSUMER_JOINED** untuk material-to-pane; **CONSUMER_JOINED** ke sumber GLSL `MsgWinBase`/`Morphing` di dua layar teks; **CANDIDATE** untuk shader archive CharaMake tanpa nama material yang menunjuknya. | Seleksi shader program/runtime pipeline, urutan render, dan parity visual. |
| Font | **CONSUMER_JOINED** secara deklaratif: BFLYT mencantumkan `SystemB_00.fcpx`; `FontInfo` dan indeks font mengikat alias itu ke member BFCpx serta fallback-face. | Page-to-screen runtime dan pemilihan varian locale yang aktual. `WipePrologue` tidak mendeklarasikan font. |
| Efek | **EXISTS** secara global di arsip tambahan: dua Particle/PTCL, ELink2DB, SLink2DB. | Tidak ada hubungan bernama dari flow/actor/layout prolog ke emitter atau effect key. Untuk beat ini tetap **OPEN**. |

## Resource yang dapat diikat ke pane/layout

Hash BFLYT di bawah adalah hash member yang diparse; hash BNTX adalah container di SARC Layout. `resource_bindings.json` memverifikasi relasi texture index→nama BNTX dan pane→material pada layout yang sama.

Untuk lima page utama dan tiga layout pendukung (map-card button, village-name keyboard, dan `MsgWin`), ada 66 entri texture-list; semuanya memiliki satu kandidat BNTX exact-name di archive yang sama. Jalur penuh **pane→material→texture-index→BNTX** berjumlah 65 edge yang benar-benar dipakai material pane; satu entri lain ada di texture-list tetapi tidak muncul pada material pane yang ditautkan. Index yang diperluas ke sembilan child layout langsung Title/Date menghasilkan 195 entri texture-list dan 193 edge material-pane. Karena itu, `EXISTS` untuk entri list dibedakan dari `CONSUMER_JOINED` untuk edge material yang dipakai.

| Layout/member | BFLYT SHA-256 | Rincian structural yang terbukti |
|---|---|---|
| `Title.arc!blyt/Title.bflyt` | `40b872f05178df2009b2c5cca853e86120d9e01dee729fd4c54b5ad388749d0c` | 6 material dan 6 pane→material; 1 BNTX texture binding (`Capture^t`, container `47b2345b40f4d6d506a0efdb88596d13d8d03ee73ebb0b32b3d85d58e2d0569d`). Title/logo parts terpisah: `LTitleJP`, `LTitleUSEU`, `LTitleKR`, `LTitleCN`, `LTitleTW`. |
| `CharaMake.arc!blyt/CharaMake.bflyt` | `251b48fc218d87ed64305d3b00bb20874daf5dcb3b99103dd90941ab3fa82a01` | 38 material, 24 pane→material, 18 tekstur unik dengan BNTX pada container `690a8f3f30dca784465a3d50042b5d95537fc4f6561773f7def9c0fbc6691c9a`. Layout archive turut memuat `__ArchiveShader.bnsh` (100.352 byte; SHA `ed01db5247a6a44b0bd736f7158e268c3926f5cd1660ccae652238371d850e70`) dan `.bushvt`, tetapi tidak ada nama shader/GLSL di mat1 yang mengikatnya ke material tertentu. Jadi shader hanya **CANDIDATE**. |
| `DateInput.arc!blyt/DateInput.bflyt` | `2f2faed68871c59992eafa1ce96e38b83b441e965b45f798e42cb1648be5cb0d` | 33 material, 15 pane→material, 8 BNTX textures pada container `7e5cc31c5a106b571dee09779bb44e8da28b0bed8eaac4d9349343b95985ef71`. Child pane mencakup pilihan bulan/hari dan `LBirthdayDecideBtn`. |
| `CharaMakeMap.arc!blyt/CharaMakeMap.bflyt` | `b110eb4c09bb23ce89f3f7a32139a68d1cc6b37c615788d75284a113941ca6ea` | 14 material, 2 pane→material pada root, 7 BNTX textures/container `5d0bae0edd0ed336c6bdb88318ca58b788738c52532a25efd2f67a731a00bb93`. Root mempunyai empat `prt1` bernama `L_Btn_00`…`L_Btn_03`, semuanya menunjuk part `LCharaMakeMapBtn`. |
| `WipePrologue.arc!blyt/WipePrologue.bflyt` | `411ad0aee7fb031004d5246ba101471a108e0cb964b2b2ae7761721bdb8588bc` | Dua pane gambar (`P_Up_00`, `P_Down_00`), masing-masing dengan material dan satu tekstur `Black_00^r` di BNTX container `3d9924d76d92d45ccdfd6d9ce543f43a35b35cfd967b7408dcc0973f8f8bd2b5`. Tidak ada font di BFLYT. BFLAN `WipePrologue_In` memiliki track pane-height/alpha yang menyasar pane pada layout ini; pemicu transisi runtime masih belum diketahui. |

Page layout Title memiliki enam `prt1` child. Index parent→child dan resource di child menunjukkan logo bukan satu gambar besar pada BNTX root `Title`: regional `LTitleJP`, `LTitleUSEU`, `LTitleKR`, `LTitleCN`, `LTitleTW` masing-masing memuat layer gambar/text logo sendiri. Sebagai contoh, `LTitleUSEU` mempunyai BFLYT SHA `957d42aa82e570d1eeda034f03e5ffa65c0536a34b2ebd1c577386094eef3468`, 18 texture-list entry (`TitleListTextEven_*`, `TitleListTextOdd_*`, `TitleLogoUSEU*`) dan 17 pane→material reference; semuanya resolve ke BNTX member di archive yang sama. `LTitleJP` memiliki 26 texture-list dan 25 pane→material; `LTitleKR` 21/20; `LTitleCN` dan `LTitleTW` masing-masing 25/24. Ini `CONSUMER_JOINED` dari child layout ke resource, sedangkan pemilihan region/visibility saat runtime belum dibuktikan. `LTitlePressABtn` adalah child lain, dengan font `SystemB_00.fcpx` dan layout-local `Capture^t`.

Child langsung `DateInput` menambahkan `LCmnBg`, `LBtnListNumBirthday`, dan `LBirthdayDecideBtn`. Yang terakhir memiliki 10 tekstur dan 11 pane→material refs, font alias `SystemB_00.fcpx`, serta tekstur UI `Ef_Fireworks^s`. Nama `Ef_Fireworks` berada pada indeks tekstur BNTX; ini **bukan** bukti bahwa sistem effect/Particle menembakkan kembang api ketika tombol ulang tahun dipakai. `LBtnListNumBirthday` juga memuat compiled `__ArchiveShader.bnsh`, tetapi tidak ada nama shader pada material yang mengikat file itu ke program tertentu.

### Empat gambar peta

Part `LCharaMakeMapBtn.arc!blyt/LCharaMakeMapBtn.bflyt` (BFLYT SHA `cc947b0e738ed7fbbbb340e2a585f9fdb135825398a515052fda4ca9611b0f74`) menambahkan pane `P_Capture_00`, ukuran `418×418`, alpha 240. Material index 20 bernama sama memakai BNTX `Black_00^r` dan `Noise+r`, plus texgen projection/indirect fields. Ini membuktikan bidang render dan resource tekstur pendukungnya; nama `Capture` memberi **CANDIDATE** bahwa isi kartu datang dari capture dinamis, tetapi tidak membuktikan sumber gambar, pemilihan empat preset, ataupun hubungan `cVillage` ke screenshot. Tidak ada empat preview map sebagai tekstur bernama pada root BNTX `CharaMakeMap` maupun child button BNTX yang diperiksa.

Maka temuan yang lebih tepat bukan “empat file preview ditemukan”, melainkan: empat slot preview UI ada; isi visualnya kemungkinan dipasok dari luar gambar statis yang terindeks di kedua archive itu, tetapi producer dan data inputnya masih **OPEN**.

## Font: deklarasi layout menuju FontInfo

Keempat layout `Title`, `CharaMake`, `DateInput`, `CharaMakeMap` mendeklarasikan `SystemB_00.fcpx`. Index font lintas layout (`font_bindings.json`) mencocokkan alias `SystemB_00` ke `Font/FontInfo.sarc.zs!FontInfo.byml`, lalu ke `Font/Fcpx.sarc.zs!SystemB_00.bfcpx` (704 byte, SHA-256 `f9bc690630950b7ad22ba39d0675955d985ded2a307864075f99f398637df5bc`). Empat varian `SystemB_00_CNzh/KRko/TWzh` juga tercatat; fallback-face names terdaftar. Ini adalah **CONSUMER_JOINED** untuk deklarasi resource BFLYT→alias→font config, bukan bukti page dibuka atau locale tertentu dipilih saat permainan.

`UISoftwareKeyboardHandling {FormType=cVillage}` pada `Tutorials_Prologue5_Campfire` event #7 memiliki kandidat semantik `SwkbdTextAreaVillageName.arc!blyt/SwkbdTextAreaVillageName.bflyt` (SHA `2bd43e04b842a6a158d569efe4a7df7f62cc03d50c6956d7f41c805d85d7f565`). Layout itu memakai `SystemB_00.fcpx`, sepuluh BNTX texture dan delapan pane→material. Tapi page scan tidak memberi mapping pasti dari handler itu ke BFLYT: `SwkbdPage` getter mengembalikan `SwkbdDummy`, yang tidak ada sebagai layout. Hubungan peristiwa→layout keyboard karena itu **CANDIDATE**, sedangkan font/texture pada layout tersebut **CONSUMER_JOINED** secara internal.

`EventFlowActionOpenMessageWindow` pada flow prolog dan dialog api unggun memiliki kandidat layout `TalkMessageWindowPage → MsgWin` (member `MsgWin.arc!blyt/MsgWin.bflyt`, SHA `c0c0ccb75d8d1d2f15bb35aae20a61d08af1d992a90aa1e3a17a71b331e55935`). Page method dan layout identifier cocok statis. Tidak ada call chain yang mengikat node pesan campfire ke instance halaman ini, jadi `MsgWin` tetap **CANDIDATE** sebagai screen cerita. Di dalam layout, `SystemB_00` dan `Normal_00` font serta 32 pane→material tercatat.

## Shader/material: dua consumer GLSL bernama

Di `SwkbdTextAreaVillageName`, `mat1` index 8 (`MsgWinBase`) terpasang pada pane `P_DialogBase_00`; user-combiner string `MsgWinBase` cocok unik dengan `SwkbdTextAreaVillageName.arc!bgsh/MsgWinBase.glsl` (SHA-256 `c7f38bbfe28fa514bd44e90dc74e84a4687fd909e44176881bbfe3aa42a07083`). Ini **CONSUMER_JOINED** di dalam layout.

Di `MsgWin`, material `MsgWinBase` dan `Morphing` dipakai sejumlah pane; nama combiner masing-masing cocok unik ke `MsgWin.arc!bgsh/MsgWinBase.glsl` dan `Morphing.glsl` (SHA `e1822860918de4f82f7f4944bae18134addb3093ac5df31e831ca0123e6510b2`). `CombinerUserShaderVariation` juga hadir sebagai shader source dalam archive. Source-file dan material assignment terpetakan, tetapi kompilasi/varian shader pada GPU dan hasil visual tetap belum divalidasi.

Untuk `Title`, `DateInput`, `CharaMakeMap`, dan `WipePrologue`, indeks menemukan material-pane dan texture binding, tetapi tidak ada shader-name/user-combiner binding di material. `CharaMake` memiliki compiled shader archive candidate tanpa named GLSL/material reference. Jangan menyamakan keberadaan `__ArchiveShader.bnsh` dengan bukti material menggunakannya.

## Efek: ada di dump tambahan, belum ada consumer prolog

Resource index supplemental mencatat:

- `Effect/Park_Idr.Nin_NX_NVN.szs!Particle.Nin_NX_NVN.ptcl`, 3.597.624 byte, SHA-256 `38d6a986ae156960bc37c8f6b397b4b01a224325d3f8d886eee0e351a49d0dc2`;
- `Effect/Park_Static.Nin_NX_NVN.szs!Particle.Nin_NX_NVN.ptcl`, 32.953.656 byte, SHA-256 `55977650362b5363293187b8258ae40e5ba49460429e4cdc695da42cee7ff9d7`;
- `ELink2/ELink2DB.szs!ELink2DB.belnk` dan `SLink2/SLink2DB.szs!SLink2DB.bslnk` hadir di archive/resource index.

Nama `Park_Idr`/`Park_Static` dan eksistensi dua link database tidak menunjukkan efek mana untuk api unggun, UI page mana yang menampilkan efek, atau actor/posisi/event pemicunya. `Ef_SmokeSphere^s` yang ditemukan di BNTX layout map dialog adalah **tekstur UI**, bukan bukti bahwa Particle effect `SmokeSphere` dipicu. Pada beat prolog/registrasi, keluarga effect masih **OPEN** setelah temuan keberadaan global ini.

## Provenance dan keyakinan versi

Untuk setiap layout UI yang diperiksa, file `Layout/*.Nin_NX_NVN.zs` terdaftar sebagai `new_path` dalam supplemental `extracted_manifest.json`; ringkasan archive mencatat 1.171 path cocok hash dengan korpus awal B_data dan 24.426 path baru, serta secara eksplisit melarang inferensi versi dari nama file. Dengan demikian, SHA/hash di atas membuktikan konsistensi index/member archive yang tersedia, bukan bahwa byte itu berasal persis dari game 1.0.0. Hash BFLYT di `layouts.json` disilangcek terhadap `layout_sha256` pada `resource_bindings.json`; texture/material/font/GLSL reference cocok berdasarkan index dan exact-name dalam archive yang sama. Tidak ada model/audio raw asset yang dibuka.

## Sisa pembuktian paling bernilai

1. Trace `UIMapSelectHandling` dan handler character/date ke page registry/instance; buktikan kapan layout dan animation tag dipanggil.
2. Cari capture/texture producer yang mengisi `P_Capture_00` dan hubungkan ke empat card result serta `cVillage`; jangan menetapkan PNG statis tanpa key yang cocok.
3. Trace `UISoftwareKeyboardHandling(cVillage)` ke Swkbd page controller, area font, focus/caret dan text-result callback.
4. Sambungkan `OpenMessageWindow` dan MessageID campfire ke `TalkMessageWindowPage/MsgWin` bila call chain dapat ditemukan.
5. Teruskan mapping `Park_Idr`/`Park_Static`/ELink/SLink dari resource key ke actor/effect event. Jika tidak ditemukan di sumber yang tersedia, biarkan OPEN dan gunakan hanya kandidat katalog.

Validasi terlampir mencocokkan hash layout, unique same-archive BNTX links, font alias/config hashes, GLSL/material exact-name joins, dan status `new_path`. Semua hash hanya milik supplemental archive sampai build identity dapat diverifikasi.
