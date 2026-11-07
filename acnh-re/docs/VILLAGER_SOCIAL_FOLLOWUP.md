# Lanjutan sosial villager: batas perhitungan Friendship

Follow-up ini menelusuri efek percakapan sampai writer field `Friendship`.
Pemetaan producer grid NPC tetap terpisah di
[`NPC_SOCIAL_FOLLOWUP.md`](NPC_SOCIAL_FOLLOWUP.md).

## Jalur talk ke writer

**[PSEUDO]** `0xc84240` memperbarui flag dan counter setelah interaksi talk.
Pada cabang yang membaca `ContinuousTalkDays`, fungsi ini memanggil
`0xd34cb0` dengan delta 1, 2, atau 3 sesuai nilai counter. Pohon caller di
indeks native menghubungkan:

```text
0xc84240 → 0xd34cb0 → 0xd34f80 → 0xef2c70
```

`0xd34cb0` membaca `Friendship`, meneruskan delta, membaca nilainya lagi, lalu
mengevaluasi transisi menuju level 3 untuk flag `BeFriendwithVillager`.
`0xd34f80` membandingkan level nilai lama dan kandidat. Converter `0xd34a20`
membagi poin dengan ambang berikut: `<30 → 1`, `<60 → 2`, `<100 → 3`,
`<150 → 4`, `<200 → 5`, dan `≥200 → 6`.

**[PSEUDO]** `0xef2c70` menerima key `Friendship` dan memilih record berdasarkan
resident/player slot. Dalam mode lokal, alamat dasar record yang dipakai
fungsi itu adalah:

```text
save_base + resident_slot*0x10798 + player_slot*0xa8 + 0x39f8
```

Mode network memakai `save_base + resident_slot*0x10798 + player_slot*0x700 +
0x1c0`. Sesudah memilih record, setter meneruskan key ke `0xf48840` untuk
memilih field dari record. Fixture native terpisah menjalankan badan setter dan
field writer setelah resolver descriptor dikendalikan; batas pemetaan live
descriptor dijelaskan di bawah.

## Verifikasi native

Reproducer menjalankan instruksi asli `0xd34f80` sampai instruksi pertama
`0xef2c70`. Pembacaan poin lama dikendalikan dengan satu getter stub dan record
resident sintetis; slot input adalah resident 1/player 2. Instruksi native
menghitung kandidat dan menyiapkan pemanggilan setter. Sebanyak 25 pemeriksaan
lulus tanpa mismatch: 12 nilai menguji ambang converter `0xd34a20`, dan 13
delta menguji kenaikan melalui ambang 30/60/100/150/200, perubahan dalam level
yang sama, penurunan di dalam level, dan lima penurunan yang melintasi ambang.
Penurunan lintas level dibatasi ke lantai level lama; penurunan yang tetap
dalam level diteruskan.

Data tiap kasus, argumen writer, alamat fungsi, dan checksum tersedia di
[`friendship_delta_native.json`](../output/gameplay/villager_social_followup/friendship_delta_native.json).
Reproduksi:

```bash
cd acnh-re
PYTHONPATH=/workspace/acnh-re/.deps:tools python3 tools/npc_friendship_delta_native.py
```

### Setter record lokal/network dan mutasi byte

**Terbukti native dengan descriptor sintetis:** test baru menjalankan badan
`0xef2c70` dan writer asli `0xf48840`, lalu membaca kembali byte yang sama
melalui getter asli `0xf486c0`. Jalur `0xef2c70` memilih record lokal dengan
rumus `save_base + resident*0x10798 + player*0xa8 + 0x39f8`; mode network
memakai `save_base + resident*0x10798 + player*0x700 + 0x1c0`. Enam kombinasi
slot valid mencakup resident 0/9 dan player 0/159 lokal atau 0/7 network; empat
kasus di luar batas ditolak sebelum writer. Pada valid path, hash Murmur dari
literal `Friendship` di NSO `main` yang dihitung native adalah `0x8a80b4d9`, lalu
`0xf48840` benar-benar mengubah byte record sintetis pada indeks field yang
disuplai descriptor. Fixture memakai `UniqueID=10` dan `MaxValue=255` dari baris
`EventFlagsNpcMemoryParam.Key=Friendship`. Untuk view sintetis 0x100 byte,
perubahan berada tepat di `view + 0x0a`; getter asli membaca hasil yang sama.
Writer mempertahankan nilai yang sama, meng-clamp `0xffffffff` menjadi 0, dan
meng-clamp 256 menjadi 255. Sepuluh kasus lulus tanpa mismatch; enam slot valid
menjalankan writer dan empat slot di luar batas ditolak.

Reproduksi:

```bash
cd acnh-re
PYTHONPATH=/workspace/acnh-re/.deps:tools python3 tools/npc_friendship_save_writer_native.py
```

Data: [friendship_save_writer_native.json](../output/gameplay/villager_social_followup/friendship_save_writer_native.json).
Fixture mengontrol save-root getter, constructor view, lookup hash ke descriptor,
lookup descriptor ke selector `UniqueID`, dan metadata `MaxValue`. Nilai 10 dan
255 berasal dari baris game 1.0.0, tetapi table-manager lookup tetap dikendalikan;
`view + 0x0a` adalah indeks dalam fixture 0x100 byte, bukan offset absolut yang
terbukti pada save pemain.

## Batas klaim dan pekerjaan tersisa

- **Terbukti native:** perhitungan `0xd34f80` untuk poin lama yang dikendalikan,
  serta argumen yang sampai ke entry `0xef2c70`, termasuk key `Friendship`.
- **Terbukti native pada fixture:** badan `0xef2c70`, setter byte asli
  `0xf48840`, getter asli `0xf486c0`, rumus alamat record lokal/network, dan
  batas byte setelah lookup descriptor yang dikendalikan.
- **Masih [PSEUDO/fixture]:** save-root nyata, table lookup `Friendship` ke
  descriptor field, pengikatan view 0x100-byte ke raw save aktif, dan persistensi
  pada save permainan. Tidak ada save pemain yang dibaca atau ditulis.

Layout save lokal mempunyai node `0xa8` pada data `+0x8`, ukuran `0x1d6d48`,
dan bukti fungsi untuk wilayah villager/NPC. Crosswalk eksternal lintas versi
mencocokkannya dengan kandidat `SaveLand.Npc.NpcVillager`; nama tersebut bukan
RTTI lokal. Ada kandidat type yang lebih spesifik: vtable native `0x30e8680`
berukuran `0x100` muncul 2.352 kali; crosswalk mencocokkannya dengan
`SaveLand.Npc.NpcVillager.Animal[0].Memory[0].EventFlag`, yang memuat
`Flags.ValueArray`. Namun crosswalk mencatat dua kandidat struct
(`SaveEventFlagNpcMemory` dan `s_33a3f71b`) dan memakai schema publik lintas
versi, sementara build lokal adalah 1.0.0. Ini menguatkan kandidat view byte
0x100, tetapi belum mengidentifikasi descriptor manager lokal.

Tabel `EventFlagsNpcMemoryParam` memberi `Friendship` `UniqueID=10`, default 25,
dan maksimum 255. Setter native memakai field hash `UniqueID` (`0x54706054`)
sebagai selector, dan `MaxValue` (`0xbd7682f5`) untuk clamp. Native table lookup
`Key=Friendship` dilalui helper generik `0xdc5e20`, tetapi object table dan
record save aktif tidak tersedia pada fixture. Dua rumus record yang sudah
terbukti adalah jalur local `save_base + resident*0x10798 + player*0xa8 +
0x39f8` dan network `save_base + resident*0x10798 + player*0x700 + 0x1c0`;
field `UniqueID=10` berada relatif pada view 0x100-byte yang dipilih. Jadi field
mapping sekarang memiliki kandidat tabel dan schema yang kuat, tetapi lookup
live dan offset absolut dalam data save masih belum terbukti. Rujukan:
[`save_layout.json`](../output/gameplay/save_layout.json),
[`save_layout_external_crosswalk.json`](../output/gameplay/save_layout_external_crosswalk.json),
dan [`friendship_reference_inventory.json`](../output/gameplay/villager_social_followup/friendship_reference_inventory.json).

## EventFlow friendship dan state conversation

**[EF]** Indeks EventFlow mencatat 72 pemakaian
`EventFlowActionNpcAddFriendship` pada 21 flow. Distribusi nilai `AddValue`:

| Delta | Pemakaian | Delta | Pemakaian |
|---:|---:|---:|---:|
| -5 | 3 | +1 | 27 |
| -3 | 8 | +2 | 10 |
| -2 | 2 | +3 | 13 |
| -1 | 3 | +4 | 2 |
|  |  | +5 | 2 |
|  |  | +6 | 1 |
|  |  | +8 | 1 |

Contoh yang bisa dirujuk tanpa teks dialog: `NNPC_Quest_Delivery_TimeOver`
event 34–36 mengirim -1/-2/-3; `NNPC_GEvent_BirthdayN_H` event 92 mengirim
-5 dan event 102–107 memberi +6/+4/+8/+4/+3/+5. Flow bernama
`NNPC_Select_Present` juga memuat aksi +1.

**Terbukti native:** callback aksi `0x27a220` dijalankan untuk seluruh 72
pemakaian `AddValue` pada 21 flow yang ditemukan di BFEVFL dan meneruskan
setiap nilai tanpa perubahan ke entry `0xd34cb0` (72/72 cocok). Jalur validasi
virtual memakai vtable aksi terdaftar
`0x3040940`, slot `0x20` memanggil fungsi asli `0x27a210`, lalu callback
mengambil resident slot serta `AddValue` dari object sintetis. Nama flow
mencakup `NNPC_Select_Present`, `NNPC_Select_Sell_Gift`, pilihan tool/furnitur,
delivery quest, sakit, treasure hunt, dan percakapan paksa. Ini menegaskan nilai
aksi yang dikonfigurasi, bukan membuktikan semua kondisi atau urutan aksi pada
playthrough. Eksekusi berhenti saat
masuk ke `0xd34cb0`; pembacaan dan perubahan save pada badan wrapper belum
dijalankan oleh kasus EventFlow ini. Data: [eventflow_friendship_action_native.json](../output/gameplay/villager_social_followup/eventflow_friendship_action_native.json).

Registry state asli yang sudah dijalankan mendaftarkan 43 state umum dan 24
`NpcAIActivityState`. `cConversationHost` adalah indeks 60 dengan entry/update/
exit `0xc0b510`/`0xc0bd20`/`0xc0c280`; `cConversationGuest` indeks 61 memakai
`0xc0c9e0`/`0xc0cb20`/`0xc0cc70`. Dispatch native sebelumnya mencapai alamat
masuk callback, tetapi tidak menjalankan badannya. **[PSEUDO]** kedua fungsi
update memanggil helper `0xc30930`; helper memilih permintaan gerak/animasi
`NpcConversationTalk` pada mode 0, `MaReNodding` pada mode 2, dan varian
`NpcTalk*` pada mode 3. Ini memilih aksi ekspresi/animasi, bukan topik dialog.
Ringkasan target callback: [eventflow_friendship_action_native.json](../output/gameplay/villager_social_followup/eventflow_friendship_action_native.json); bukti registrasi rinci: [`npc_state_registry_native.json`](../output/mechanics/npc_state_registry_native.json).

**Masih terbuka:** perpindahan state host/guest, badan callback entry/update/exit,
dan pemilihan topic/message dialog. Nilai EventFlow adalah input yang
dikonfigurasi, bukan bukti bahwa setiap cabang terjadi dalam satu playthrough.

### Hadiah dan surat

**[EF]** `NNPC_Select_Present` memilih jalur dari jenis barang yang dipilih
dengan filter `cGiftToNpc`. Subflow barang menetapkan nilai berbeda, bukan satu
rumus umum. Cabang `UISelectedItemIsWrapping` juga mengonfigurasi +1 sebelum
subflow jenis barang. Subflow memberi makanan/tanaman +1, bunga +2, perabot
kategori `DecorateFtr` atau `DoorDeco` +3, fosil +1, dan pakaian/perlengkapan
memakai query `DeliveryItemIsFavor` untuk memilih +1/+2. Musik memakai
`IsFavoriteMusic` untuk +1/+2; sampah tertentu memakai -2, sedangkan barang
lain pada jalur `Etc` +1. Fish dan insect melalui pemeriksaan museum/donasi
sebelum diterima dengan +2. Nilai dan event index tiap subflow tersimpan di
[`friendship_reference_inventory.json`](../output/gameplay/villager_social_followup/friendship_reference_inventory.json).

Flow `NNPC_Select_Sell_Gift` adalah transaksi saat villager membeli barang
pemain: cabang `CheckNpcFavorLevel` memberi +3/+2/+1. Saat inventory penuh,
flow mengirim hadiah balasan lewat `NpcMailSendRandom` setelah delta yang sama.
Ini berbeda dari surat yang dikirim pemain. Hadiah ulang tahun di
`NNPC_GEvent_BirthdayN_H` mengonfigurasi +3/+4/+5/+6/+8 berdasarkan hasil
pilihan/subflow; item yang lolos filter seperti `LostQuestDust`, turnip busuk,
sampah, atau weed masuk cabang -5. Semua nilai ini adalah aksi yang telah
dikonfigurasi dan callback-nya telah meneruskan tanpa perubahan; hasil
playthrough tetap bergantung pada query/cabangnya.

**[EF]** Surat pemain ke villager dibuat di
`Obj_MessageCardRack_01_SendVillage`: alur memilih alamat `cNpc`, mengedit
kartu, memeriksa saldo, mengurangi 200 Bells, lalu menjalankan
`DropIntoPostOffice(cSaveMailUserInfo)`. Flow itu tidak memiliki aksi
`NpcAddFriendship` atau query `HasAttachedPresent`, dan indeks exact-key tidak
menemukan callsite Friendship writer di pengirim surat.

**[EF + native static]** Jalur edit/simpan memakai `HasAttachedPresent` di
`Obj_MessageCardRack` dan `Obj_MessageCardRack_05_EditingCardResume`, lalu dapat
menjalankan `ReturnAttachedPresentToBaggage`. Registry handler menempatkan
query pada callback `0x433bc0` dan aksi pengembalian pada `0x33ff10`. Keduanya
membuat generic property view lewat `0x1589cf0` dan meneruskan descriptor
`0x3245218` (query) atau `0x3245240` (aksi) ke virtual dispatcher. Query
mengembalikan byte boolean dari dispatcher; nama field attachment dan efek
mutasi aksi pengembalian belum ditemukan.

Handler `DropIntoPostOffice` memakai callback `0x33d550`, yang menyiapkan
pengiriman melalui `0x33d7a0` (`SendLetter`). Rantai ini membentuk record di
`0xec5410`, menserialisasikannya di `0xec5500`, mengirimkannya lewat `0xf62e90`,
lalu menyalin record mail melalui `0xf73ea0`. Serializer mengenali sentinel
item `-2`: ia menulis `HasItem` dari pemeriksaan `item != -2` dan menulis
`ItemUniqueID` jika item ada; `CardDesignID` juga diserialisasi, sedangkan
`ToNpcUniqueID` ditulis pada cabang record type 1. EventFlow mengikat parameter
`TmpMailInstance` ke `cSaveMailUserInfo`, yang menjadi record input jalur itu.
Ini membuktikan bahwa record surat dapat membawa item terlampir, bukan bahwa
penerimaan surat menambah Friendship. Pencarian direct-call pada helper kirim
tidak menemukan panggilan `0xf48840` atau `0xef2c70`; efek di sisi penerima,
descriptor save attachment yang live, dan hubungan item mail dengan writer
Friendship masih terbuka. Rincian callback, key serialisasi, dan batas bukti
tersimpan di [`friendship_reference_inventory.json`](../output/gameplay/villager_social_followup/friendship_reference_inventory.json).

**[EF inventory lengkap]** Pemindaian semua action/query EventFlow yang namanya
mencakup mail, letter, present, attachment, atau receive mencatat 125 pemakaian
di 35 flow. Pada flow lokal 1.0.0, `Ftr_MailBox` mulai dari query
`Ftr.IsMyPost`; jalur UI post menjalankan `CheckFreeCommunication`,
`UIWaitReceivingMailAppear`, `UIPostHandling`, lalu `UIResultMenuDecide`.
Flow ini tidak mengonfigurasi `NpcAddFriendship` dan aksi wait-nya bukan decoder
surat penerima. Empat aksi `NetReceiveMail` ada di `System_GrowUp` untuk jalur
network, bukan kiriman pemain ke villager. Pada EventFlow lokal, indeks array
13/26/27/34 (label sumber `Event28`/`Event33`/`Event34`/`Event42`) dicapai lewat
empat rute: `ContinueCommon` menjalankan SaveGrowUp(cStart), unlock, dan
NetUpdateFriendList; `InGame`/`AfterNet` memerlukan case 1 dari
`PassDaysSincePreviousGrowUp`; `PostPlayerSwitch` melewati dua query
`IsSharePlay(TargetMode=0)` dengan cabang yang tercatat di inventory. Semua node
itu tanpa parameter eksplisit. Handler native terdaftar memiliki method eksekusi
`0x326b60` yang no-op dan method completion `0x326b70` yang hanya menulis flag
selesai; keduanya tidak memanggil Friendship writer secara langsung. Ini hasil
negatif yang dibatasi pada aksi lokal tersebut, bukan bukti bahwa jalur payload
network eksternal tidak memproses attachment.
`Obj_MessageCardRack_02_SendFuture`
hanya mengelola surat terjadwal dan hadiah yang dapat dikembalikan ke pocket.
Sejumlah flow villager-to-player seperti birthday dan quest juga memuat aksi
Friendship, tetapi kedekatan event dalam satu flow tidak membuktikan bahwa
pengiriman atau penerimaan surat menyebabkan delta tersebut.

Jalur native `EventFlowActionUIWaitReceivingMailAppear` terdaftar pada
`0x305b978`; method per-object `0x367bd0` memanggil helper `0x367c20` untuk
status/pengantrian UI. Penelusuran direct-call closure helper mencapai 212
fungsi dan tidak menemukan literal `Friendship`, getter `0xf486c0`, generic
writer `0xef2c70`, atau field writer `0xf48840`. Jadi action yang dipakai
`Ftr_MailBox` sendiri adalah jalur UI. Efek setelah penerimaan/pembukaan mail
atau handler item terlampir masih belum terbukti.

Cross-check publik `ACNH_Resources` dan `acnh-eventflows` menemukan struktur
`Ftr_MailBox` yang sama, tetapi mirror `ACNH_Resources` yang diperiksa berasal
dari build lebih baru dan menambah `NetFriendMailCheck` serta gate tutorial.
Keduanya hanya memberi EventFlow; tidak membuktikan aksi native atau write save.
Pemetaan node serta call closure tersimpan di
[`friendship_reference_inventory.json`](../output/gameplay/villager_social_followup/friendship_reference_inventory.json).

Fungsi proses mail hari-ganti mengikuti
`0xf53a70 → 0xaba970 → 0xaba9d0 → 0xabb250 → 0xabbf00`. `0xabbf00` membaca
Friendship lewat `0xf486c0`, mengubahnya ke band 1–6 lewat `0xd34a20`, lalu
memakai band saat memilih respons mail; ia merujuk `MAIL_XX_ReMax` dan memanggil
pembuat mail `0xabc820`/`0xabcbe0`. Ia tidak punya panggilan langsung ke
`0xf48840` atau `0xef2c70`. Dengan bukti yang tersedia, pemrosesan penerima
memengaruhi pemilihan balasan, tetapi perubahan Friendship langsung pada jalur
ini belum terlihat. Inventaris `NpcMailSend` dan `NpcMailSendRandom` pada 10
flow `NNPC_*` mencatat surat villager-ke-pemain (ulang tahun, quest, onboarding,
overflow), bukan surat pemain-ke-villager; rinciannya ada di
`friendship_reference_inventory.json` tanpa teks dialog.

**Bukti writer:** direct caller `0xef2c70` hanya `0xd34f80`, `0xf12fe0`, dan
`0xfba210`; pemeriksaan key menunjukkan hanya `0xd34f80` memakai `Friendship`,
sedangkan dua lainnya memakai `SameLand`, `SickQuestGossip`, dan
`TalkedDuringSick`. Writer langsung lain yang memakai literal `Friendship`
adalah `0xac0200`, dipanggil kandidat proses harian `0xabff90` dan helper
`0xabfcf0`. Jalur reader reply mail `0xabbf00`, post-office serializer, dan
EventFlow mailbox tidak muncul sebagai pemanggil langsung writer tersebut.
Dengan data lokal, belum ada jalur yang membuktikan incoming letter atau present
terlampir mengubah Friendship; callback tak langsung atau modul yang tidak ada
tetap belum tercakup.

### Pukulan jaring, pengabaian, dan batas harian

**[PSEUDO + EF]** `AI_NPC_Normal:End_Hit` dan `AI_NPC_Outdoor:Hit` memeriksa
`NpcIsHitByNet`, lalu `NpcHitNum(Border=3)`, dan dapat memulai
`NNPC_Talk_Force:Hit`. Pseudocode query `0x389c50` mengembalikan case 0 saat
flag hit-by-net NPC aktif; query `0x388660` mengembalikan case 0 saat hit
counter sudah ≥ Border. Jalur di bawah ambang mengatur `NpcSetHitTimer(60)` lalu
kembali ke rute AI normal. Pada flow Outdoor, jalur Hit juga memerlukan
`HitMainPlayer` dan `HasAcquaintanceship` ON sebelum masuk ke state `cHit` dengan
entry `Hit`.

Di entry `Hit`, selector `RandomChoiceExcludePrevious3` memilih satu dari tiga
cabang yang saling eksklusif. Hanya aksi event 21, 32, atau 33 yang
mengonfigurasi `NpcAddFriendship(-3)`; masing-masing berada setelah
`CheckNpcLook` case 0 dan `NoAcquaintance_Chk`. Subflow keluar bila
`HasAcquaintanceship` OFF. Satu pemanggilan `Hit` paling banyak menjalankan satu
aksi -3 itu; rangkaian net-hit berikutnya dapat mengulang jalur setelah state
hit di-reset. Handler `NpcSetHitTimer` `0x25c650` menyimpan `Timer * 30` pada
offset konteks `+0xacac`. Emulasi callback asli dengan konteks sintetis
mengonfirmasi `Timer=0,1,30,60,90` menulis `0,30,900,1800,2700`; jadi Timer 60
menjadi 1.800 unit penyimpanan native, bukan bukti langsung durasi 60 detik.
Pseudocode actor-update method pada index VA `0xc1e2e0` (simbol Ghidra
`0xd1e2e0`) mengurangi `+0xacac` satu unit saat cabang countdown memenuhi
guard. Method yang sama juga mengurangi field terpisah `+0xabe8` jika nilainya
positif. Jadi countdown `+0xacac` menghitung invocation yang lolos guard;
frekuensi dispatch per frame/detik belum terbukti.

Handler `NpcClearHitParam` `0x258b10` mengosongkan counter u32 `+0xaca8` dan byte
`+0xacb1`; `NpcHitNum` membaca counter tersebut. Query `NpcIsHitByNet`
`0x389c50` membaca byte berbeda, `+0xacb0`, jadi kedua byte tidak disamakan.
Pemindaian akses exact di 64.475 file `analysis_decomp`, 6.402 file `decomp`,
25 file `new_decomp`, dan 9 snippet fallback assembly menemukan tiga lokasi
semantik: constructor umum `0x1025080` membangun subobject di alamat itu,
`NpcClearHitParam` menulis nol, dan `NpcHitNum` membaca u32. Dua pohon decomp
memuat duplikat clear/read; dua corpus lainnya tidak memiliki hit. Tidak ada
writer increment eksplisit pada pencarian offset/index ini; penambah counter
masih belum ditemukan. Ini bukti
pukulan jaring dapat memulai penalti bersyarat, bukan bahwa setiap pukulan
langsung mengurangi poin. Callback aksi meneruskan nilai EventFlow 72/72; query
dan transisi AI masih bukti pseudocode. Empat aksi
-3 lain di entry `Push` dan aksi +5 di entry `Flea` pada flow sama bukan jalur
net-hit. Kasus native dan batas fixture ada di
[`hit_timer_native.json`](../output/gameplay/villager_social_followup/hit_timer_native.json)
dan [`npc_hit_timer_native.py`](../tools/npc_hit_timer_native.py).

Constructor native `0xbe5e40` mengalokasikan object `0x618` byte, mengisi vptr
dari global `0x32f7a18`, lalu mengosongkan `+0x2f8` bersama pointer field di
sekitarnya. Relokasi `R_AARCH64_RELATIVE` pada global itu memberi nilai
`0x30d5890`; instruksi constructor menambah `0x10` dan menyimpan `0x30d58a0`,
jadi sequence pointer tersebut terbukti sebagai vtable owner ini. Method slot 7
`0xbe98a0` memakai relokasi global `0x32d3e20 → 0x356b3f0`, yang menunjuk ke
storage registry di BSS. Ia membaca registry pointer, count di `+0x8`, dan
pointer records di `+0x10`; lalu mencari record `0x20` byte dengan kunci hasil
helper `0x1bf0` pada `+0x18`, memanggil factory pointer di awal record secara
tidak langsung, dan menyimpan hasilnya ke `owner+0x2f8` pada `0xbeab34`. Isi
registry ada di runtime BSS, bukan di dump statik, jadi target factory, kunci,
dan row yang terpilih masih memerlukan capture.
Setelah factory mengembalikan pointer, method `0xbe98a0` menjalankan setup
`0xc1ac50` bila pointer tidak null. Setup tersebut merujuk 43 nama
`NpcAIState::...`, termasuk `cIdle`, `cWander`, `cTalk`, `cHit`, dan
`cConversationPretense`; ini mendukung label subobject AI-state/controller,
tetapi tidak menamai tipe konkret hasil factory. Method slot 13 `0xbec1f0`
membaca `owner+0x2f8` dan pada `0xbec314` memanggil `0xc1e2e0` hanya jika child
ada. Index direct-call menunjukkan nol pemanggil langsung untuk `0xbec1f0`;
vtable mengonfirmasi fungsi itu terdaftar di slot 13, tetapi dispatcher yang
memanggil slot tersebut belum teridentifikasi. Slot 18 `0xbec810` menjalankan
cleanup child, melepasnya lewat virtual slot `+0x18`, dan mengosongkan field;
destructor slot 0 `0xbe6270` juga melepas dan membersihkan child. Jadi
constructor, populasi, update, dan teardown `+0x2f8` terbukti secara statik.
Yang belum terbaca adalah factory row/target aktual, dispatcher runtime,
frekuensi update, incrementer `+0xaca8`, dan nama tipe konkret child.

**[PSEUDO]** percakapan pertama per villager pada hari itu memberi
`min(ContinuousTalkDays, 3)`, jadi bonus talk harian berhenti naik setelah +3.
Ketika siklus harian mendapati `TalkCountToday` nol pada mode yang sesuai,
helper reset menghapus `ContinuousTalkDays`; efek pengabaian yang terbukti di
jalur ini adalah hilangnya bonus streak berikutnya, bukan delta Friendship
negatif. `NNPC_Quest_Delivery_TimeOver` terpisah memberi -1/-2/-3 menurut
query `HasDeliveryItem` dan `HasOpenedDeliveryItem`; itu penalti timeout quest,
bukan decay pasif.

Tabel `EventFlagsNpcMemoryParam` memberi `Friendship` nilai awal 25 dan batas
255, sedangkan `ContinuousTalkDays` berawal 0 dengan batas 7. Uji delta native
mengonfirmasi floor/level saat nilai turun; writer field membatasi nilai
individu menurut descriptor yang dipasok. Batas byte ini bukan batas agregat
harian. Flag `FriendshipBecomeAcqHToday` di
`NNPC_Talk_General:PresentAvailable_Chk` mengatur milestone `ReceivedFirstPresent`,
bukan cap pada writer. Tidak ditemukan batas total `AddFriendship` per hari.

Pencarian mencakup seluruh 72 aksi `EventFlowActionNpcAddFriendship` pada 21
flow; callback asli meneruskan `AddValue` tanpa perubahan. Jalur native setter
umum tidak mempunyai akumulator harian yang terlihat. String-reference dan
direct-call inventory menemukan writer `0xac0200` untuk kandidat hari-ganti
serta writer generik `0xef2c70`, tanpa writer agregat lain yang terindeks. Ini
menopang kesimpulan bahwa cap agregat belum ditemukan; penulis tidak langsung,
key dinamis, atau modul yang tidak tersedia tetap di luar pencarian.

### State aktivitas dan host/guest

**Terbukti pada registry native:** proses registrasi dan dispatch yang sudah
ada mendaftarkan 24 state `NpcAIActivityState` dan menautkan
`cConversationHost`/`cConversationGuest` ke callback di atas. Output rinci ada
di [`npc_state_registry_native.json`](../output/mechanics/npc_state_registry_native.json);
ringkasan conversation tersimpan di artifact EventFlow follow-up.

**[PSEUDO]** update host `0xc0bd20` dan guest `0xc0cb20` memanggil `0xc30930`.
Mode 0 mengajukan aksi `NpcConversationTalk`, mode 2 `MaReNodding`, dan mode 3
memilih `NpcTalkShocked`, `NpcTalkEh`, atau `NpcTalkAha`. Ini bukti pemilihan
aksi/animasi percakapan. **Terbuka:** transisi masuk/keluar host/guest, badan
callback utuh, sinkronisasi guest jaringan, dan pemilihan topic/message.

### Counter percakapan

**Terbukti native sampai batas writer:** reproducer menjalankan `0xce9af0`,
formatter `0x47360`, normalizer indeks pemain `0xda3fc0`, dan wrapper
`0xef62f0`. Untuk slot villager 0, 3, dan 9, native wrapper memformat key
`TalkNpc0Count`, `TalkNpc3Count`, atau `TalkNpc9Count`, lalu `TalkAllNpcCount`.
Nilai hasil resolver terkontrol yang sama diteruskan dua kali ke entry writer
`0xce9390`, dengan argumen operasi 1. Enam dari enam panggilan boundary cocok.
Reproduksi:

```bash
cd acnh-re
PYTHONPATH=/workspace/acnh-re/.deps:tools python3 tools/npc_talk_counter_native.py
```

Kasus dan argumen tersedia di
[`talk_counter_native.json`](../output/gameplay/villager_social_followup/talk_counter_native.json).
Resolver `0xeaa8c0` mengembalikan nilai masukan sintetis dan writer `0xce9390`
ditangkap sebelum lookup/perubahan map save; bukti ini tidak menetapkan reset
policy atau semantik game untuk nama `TalkNpc%dCount` dan `TalkAllNpcCount`.

**[PSEUDO]** `0xc84240` memperbarui `TalkCountToday`, memanggil wrapper counter
`0xce9af0`, lalu bila nilai `TalkCountToday` menjadi 1 menambah
`ContinuousTalkDays`. Nilai setelah kenaikan menentukan delta friendship
`min(ContinuousTalkDays, 3)`, yaitu 1, 2, lalu 3. Field table
`EventFlagsNpcMemoryParam` memberi `TalkCountToday` dan `ContinuousTalkDays`
max 7; tabel berbahasa Jepang menamai keduanya sebagai hitungan hari ini dan
hari berturut-turut.

`0xf4dbd0` membaca `TalkNpc0Count` sebagai gate, lalu memeriksa key
`TalkNpc%dCount` untuk indeks 0–9 dan mengembalikan indeks pertama yang nilainya
sesuai dengan argumen. Enam kasus native menjalankan body selector dan
formatter asli dengan hasil lookup sintetis: gate mismatch memberi -1, nilai
cocok pertama pada indeks 0/2/5/9 mengembalikan indeks tersebut, dan sepuluh
counter tanpa kecocokan memberi -1. Reproduksi:

```bash
cd acnh-re
PYTHONPATH=/workspace/acnh-re/.deps:tools python3 tools/npc_talk_index_selection_native.py
```

Detail ada di
[`talk_index_selection_native.json`](../output/gameplay/villager_social_followup/talk_index_selection_native.json).
Lookup `0xf4d560` dan setup context `0xf4da70` diganti pembacaan sintetis.
Caller selector-nya `0x395bc0`, `0x395e50`, dan `0x3960d0`; belum terbukti
bahwa indeks yang dikembalikan adalah topic atau message ID.

### Reset harian dan sumber friendship

**[PSEUDO]** jalur perubahan hari `0xf53a70 → 0xf545f0 → 0xf84320 → 0xf12aa0`
memproses record villager. `0xf12aa0` memanggil `0xf76010`/`0xf696c0` untuk
membersihkan `TalkCountToday`; bila mode proses di bawah 2, kode membaca
`TalkCountToday` dan menghapus `ContinuousTalkDays` saat tidak ada talk yang
tercatat. Fungsi reset umum `0xf48cf0` juga menghapus kedua field, tetapi
caller-nya `0xf05e80`, di luar jalur perubahan hari yang ditelusuri. Ini
menautkan reset counter ke siklus perubahan hari, tetapi mode pemanggil masih
bukti pseudocode.

**Terbukti native pada helper reset:** reproducer menjalankan `0xf76010` dan
`0xf696c0` dengan nilai `TalkCountToday` dan mode terkendali, menangkap semua
write di entry `0xf48840`. Delapan kasus mencakup mode 0/1/2 dan hitungan 0/1;
11 panggilan setter yang diharapkan cocok. Pada `0xf76010`, mode 0 dengan
hitungan positif mempertahankan kedua field; mode 1 dengan hitungan positif
menghapus `TalkCountToday` dan mempertahankan `ContinuousTalkDays`; tanpa talk
atau pada mode ≥2, streak dihapus. `0xf696c0` juga selalu menghapus
`TalkCountToday`, dan mempertahankan streak hanya bila mode <2 dan hitungan
sebelumnya positif. Reproduksi:

```bash
cd acnh-re
PYTHONPATH=/workspace/acnh-re/.deps:tools python3 tools/npc_talk_streak_reset_native.py
```

Detail kasus ada di
[`talk_streak_reset_native.json`](../output/gameplay/villager_social_followup/talk_streak_reset_native.json).
Test memakai getter/setter sintetis, tidak menjalankan event perubahan hari,
dan tidak memverifikasi save sesudah write.

### Kandidat update harian Friendship

**[PSEUDO; kandidat, belum terbukti berjalan]** day-change driver `0xf53a70`
memanggil `0xabff90` setelah processor mail recipient `0xaba970`; indeks direct
call memberi `0xf53a70` sebagai caller langsung `0xabff90`. Salah satu cabangnya
memanggil `0xac0200`, yang membaca `Friendship` lewat `0xf486c0`, memanggil
kalkulator `0xab9dc0`, lalu menyiapkan `nilai_lama + iStack_a0` untuk
`0xf48840`. Kalkulator memiliki dua assignment -3 yang tampak statik. Guard
pertama menunggu task asynchronous sampai status wrapper `+0x50` bernilai 2,
lalu mengambil result u32 dari `+0x20`; branch memberi -3 bila result itu lebih
besar dari 2. Hasil ini belum dapat diberi nama domain: task worker bergantung
pada manager global yang tidak tersedia di harness.

Guard kedua hanya berlaku bila input ushort bukan sentinel `-2`. Fungsi
`0xb9c290` membentuk descriptor dari input tersebut; `0xb9cb60` membaca
descriptor `+0x10`, memetakan item ID melalui tabel kategori u16, lalu
membandingkan hasilnya dengan enam ordinal `ItemParam.ItemKind`. Pseudocode
`0xb25280` membaca field ItemKind dari ItemParam, mengubah enum menjadi ordinal
0–119, dan menyimpan ordinal itu pada map; `0xb9cb60` membacanya kembali. Jadi
enam kode itu kini dapat diberi nama lewat baris `ItemKind.bcsv` yang ordinalnya
sama:

| Kode / ordinal | ItemKind | UniqueID baris ItemKind | CanGift | CanNpcPresent |
|---:|---|---:|---:|---:|
| `0x3a` / 58 | `Trash` (ゴミ) | 61 | 1 | 1 |
| `0x62` / 98 | `LostQuestDust` (おとしものゴミ) | 79 | 0 | 0 |
| `0x65` / 101 | `TreasureQuestDust` (宝探しカプセルごみ) | 179 | 0 | 0 |
| `0x5f` / 95 | `JohnnyQuestDust` (ジョニークエストごみ) | 150 | 0 | 0 |
| `0x31` / 49 | `TurnipExpired` (カブ（くさったカブ）) | 168 | 0 | 1 |
| `0x2a` / 42 | `Weed` (植物：雑草) | 187 | 0 | 1 |

`UniqueID` is a different table field and differs from each compared ordinal.
The gift/present flags above are table metadata; they do not identify
which gameplay action supplied the item or prove why a category match returns
-3. The 1.0.0 `ItemKind.bcsv` rows agree at these ordinals with the public
`CylindricalEarth/specs_100.py` enum tuple. This resolves category names, not
runtime reachability.

Jalur `0xf53a70 → 0xabff90 → 0xac0200` memberi caller statik dari siklus
perubahan hari, tetapi tidak membuktikan kedua guard terpenuhi pada hari normal.
Selain jalur `0xabff90`, `0xac0200` juga memiliki caller langsung
`0xabfcf0`; fungsi ini tidak punya parent direct-call terindeks. Writer karena
itu belum terbukti khusus dipanggil saat day-change.

Eksekusi bounded kalkulator dengan helper tanggal terkontrol masih berhenti di
akses object task/manager global pada PC `0x22019d8`, sebelum task result atau
item category check bisa dikendalikan. Tidak ada fixture native untuk dua
cabang -3 dan belum ada pengamatan hari normal. Ini jalur kandidat yang dapat
mengurangi field, belum cukup untuk menyebutnya decay normal. Rute, crosswalk,
xref, dan batasnya tercatat di
[`friendship_reference_inventory.json`](../output/gameplay/villager_social_followup/friendship_reference_inventory.json).

`0xd26b70` juga memanggil `0xd34c20`, tetapi helper `0xf48740` yang dipanggilnya
tidak memanggil setter field; pseudo-code-nya membaca byte dari record. Saya
tidak menghitungnya sebagai writer tambahan. Daftar pembaca/penulis dan rantai
candidate disimpan di
[`friendship_source_candidates.json`](../output/gameplay/villager_social_followup/friendship_source_candidates.json).

### Cakupan statik dan kebutuhan capture

Audit ini mencakup main NSO 1.0.0 yang tercatat di inventory, 64.475 file
`analysis_decomp`, 6.402 file `decomp`, 25 file `new_decomp`, 9 snippet fallback
assembly, BFEVFL lokal yang telah didecode, tabel `ItemParam` (8.208 baris) dan
`ItemKind` (120 baris), serta cross-check publik `CylindricalEarth` dan dua
mirror EventFlow. `rtld`, `sdk`, dan `subsdk0` tersedia sebagai input ExeFS,
tetapi tidak masuk ke call graph native yang dipakai di sini. Tidak ada proses
game aktif atau save pemain untuk menguji descriptor, worker task, network mail,
atau waktu dispatch. Pencarian +0xaca8 tidak menemukan increment eksplisit pada
offset/index yang dicari; pointer alias atau write generik masih memerlukan
capture runtime.

Capture yang menyelesaikan blocker perlu menjalankan build yang checksum-nya
cocok dan save uji salinan. Pasang hook di `0xab9dc0` untuk merekam pemanggil,
input item, `descriptor+0x10`, ItemKind terpetakan, wrapper status `+0x50`, task
result `+0x20`, dan delta; bandingkan panggilan dari `0xabff90` dan `0xabfcf0`
pada hari biasa serta day-change, dengan item dari enam kategori dan kategori
kontrol. Ikuti ke `0xac0200`/`0xf48840` dan ambil nilai Friendship sebelum dan
sesudah untuk membuktikan guard berjalan.

Untuk net-hit, pasang write watchpoint di actor `+0xaca8` dan catat setiap PC,
backtrace, serta alamat object; hook clear `0x258b10` dan query `0x388660`.
Rekam dispatch aktual ke owner update vtable slot 13 (`0xbec1f0`, entry
`0x30d5908`, byte offset `0x68`), child update `0xc1e2e0`, dan frame/time pada
callsite `0xbec314` untuk menemukan incrementer serta cadence.
Pada owner, tangkap constructor `0xbe5e40`, isi runtime registry storage
`0x356b3f0`, kunci/row dan indirect factory target di `0xbeab28`/`0xbeab30`,
store pointer `0xbeab34`, setup `0xc1ac50`, dan clear/destructor;
catat pointer, vptr, dan transisi state agar child konkret dan caller dispatcher
bisa diidentifikasi.

Untuk surat, gunakan save salinan dan kirim ke villager yang sama tanpa item,
dengan item biasa, dan dengan item dari enam kategori. Rekam UI wait mailbox,
setiap entry `NetReceiveMail` pada rute `System_GrowUp`, pemrosesan payload
network di luar aksi EventFlow, handler penerima, semua pemanggilan
`0xef2c70`/`0xf48840`, dan diff save sebelum/sesudah. Untuk descriptor, hook
lookup key `Friendship` di
`0xdc5e20`, catat pointer, `UniqueID`/`MaxValue`, view dari `0xef2c70`, root save,
dan bytes sesudah flush; lakukan pada record lokal dan network menggunakan dua
rumus record yang didokumentasikan di atas.

Jadi yang masih terbuka ialah worker result dan reachability normal-day untuk
dua guard -3; efek receipt surat/present; descriptor manager dan offset absolut
Friendship pada save nyata; factory target/tipe konkret dan dispatcher/cadence
owner AI update; incrementer +0xaca8; serta cadence runtime method `0xc1e2e0`.
Penurunan -3 dari net-hit dan timeout quest adalah aksi bersyarat yang
dikonfigurasi, bukan bukti decay pasif. Batas total Friendship harian juga belum
terbukti; tidak ada cap agregat di bukti writer/EventFlow yang terindeks.
Pengujian `0xd34f80` membuktikan floor saat turun lintas level, bukan sumber
decay.
