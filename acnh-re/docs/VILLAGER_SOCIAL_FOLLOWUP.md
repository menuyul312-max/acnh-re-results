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
memilih field dari record. Karena reproducer berhenti sebelum badan `0xef2c70`,
field-selector dan mutasi byte save ini masih bukti pseudocode/disassembly;
eksekusi native di bawah mengikat perhitungan ke entry setter serta key-nya.

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
`0xf48840` benar-benar mengubah byte record sintetis pada offset `+0x38`.
Writer juga mempertahankan nilai yang sama, meng-clamp `0xffffffff` menjadi 0,
dan meng-clamp 256 menjadi 255. Sepuluh kasus lulus tanpa mismatch.

Reproduksi:

```bash
cd acnh-re
PYTHONPATH=/workspace/acnh-re/.deps:tools python3 tools/npc_friendship_save_writer_native.py
```

Data: [friendship_save_writer_native.json](../output/gameplay/villager_social_followup/friendship_save_writer_native.json).
Fixture mengontrol save-root getter, constructor view, lookup hash ke descriptor,
lookup descriptor ke field byte `+0x38`, serta metadata maksimum byte 255.
Karena tabel descriptor asli tidak dijalankan dan fixture save sintetis,
temuan ini membuktikan efek native setter/getter setelah descriptor diberikan;
ia belum membuktikan bahwa save pemain nyata memakai nilai tabel tersebut.

## Batas klaim dan pekerjaan tersisa

- **Terbukti native:** perhitungan `0xd34f80` untuk poin lama yang dikendalikan,
  serta argumen yang sampai ke entry `0xef2c70`, termasuk key `Friendship`.
- **Terbukti native pada fixture:** badan `0xef2c70`, setter byte asli
  `0xf48840`, getter asli `0xf486c0`, rumus alamat record lokal/network, dan
  batas byte setelah lookup descriptor yang dikendalikan.
- **Masih [PSEUDO/fixture]:** save-root nyata, table lookup `Friendship` ke
  descriptor field, descriptor ke offset `+0x38`, dan persistensi pada save
  permainan. Tidak ada save pemain yang dibaca atau ditulis.

Layout save lokal mempunyai node `0xa8` pada data `+0x8`, ukuran `0x1d6d48`,
dan bukti fungsi untuk wilayah villager/NPC. Crosswalk eksternal lintas versi
mencocokkannya dengan kandidat `SaveLand.Npc.NpcVillager`; nama tersebut bukan
RTTI lokal. Tabel `EventFlagsNpcMemoryParam` memberi `Friendship` `UniqueID=10`,
default 25, maksimum 255, tetapi tidak membuktikan indeks byte runtime. Fixture
setter mengarahkan hash Friendship ke descriptor sintetis pada offset `+0x38`
dan maksimum 255. Karena lookup map/index/metadata dikontrol, byte runtime
nyata dan kaitannya dengan record SaveLand masih belum terbukti. Rujukan:
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
menemukan callsite Friendship writer di pengirim surat. Native handler untuk
`UIMsgCardAdrHandling`, `UIMsgCardEditTextHandling`, dan `DropIntoPostOffice`
belum ditelusuri, jadi efek penerimaan present terlampir masih terbuka.

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
offset konteks `+0xacac`. Handler `NpcClearHitParam` `0x258b10` mengosongkan
counter u32 `+0xaca8` dan byte `+0xacb1`. Kode penghitung waktu dan penambah
counter belum ditemukan, sehingga lama jendela hit serta frekuensi tepat per
hari masih terbuka. Hitungan dapat dibangun kembali setelah `NpcClearHitParam`
mengosongkan counter. Ini bukti pukulan jaring dapat memulai penalti bersyarat,
bukan bahwa setiap pukulan langsung mengurangi poin. Callback aksi meneruskan
nilai EventFlow 72/72; query dan transisi AI masih bukti pseudocode. Empat aksi
-3 lain di entry `Push` dan aksi +5 di entry `Flea` pada flow sama bukan jalur
net-hit.

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
memanggil `0xabff90` setelah processor mail recipient `0xaba970`; guard internal
`0xabff90` menentukan apakah pembaruan berjalan. Salah satu cabangnya memanggil
`0xac0200`, yang membaca
`Friendship` lewat `0xf486c0`, memanggil kalkulator `0xab9dc0`, lalu menyiapkan
`nilai_lama + iStack_a0` untuk `0xf48840`. Decomp kalkulator menginisialisasi
`iStack_a0` ke 0 dan mengisinya dengan -3 pada dua cabang validasi awal. Ini
adalah jalur kandidat yang dapat mengurangi field pada proses harian, tetapi
kondisi tersebut belum direproduksi native dan konteks caller selain day-change
belum dipastikan. Karena itu belum cukup untuk menyebutnya decay normal.

`0xd26b70` juga memanggil `0xd34c20`, tetapi helper `0xf48740` yang dipanggilnya
tidak memanggil setter field; pseudo-code-nya membaca byte dari record. Saya
tidak menghitungnya sebagai writer tambahan. Daftar pembaca/penulis dan rantai
candidate disimpan di
[`friendship_source_candidates.json`](../output/gameplay/villager_social_followup/friendship_source_candidates.json).

**Terbuka:** konteks yang memicu cabang -3 pada `0xab9dc0` dan apakah ia terjadi
pada hari normal; efek penerimaan surat/present terlampir di handler mail; bukti
descriptor save runtime yang asli; serta countdown dan penambah counter net-hit.
Penurunan -3 dari net-hit dan timeout quest adalah aksi bersyarat yang
dikonfigurasi, bukan bukti decay pasif. Batas total Friendship harian juga belum
terbukti; tidak ada cap agregat di bukti writer/EventFlow yang terindeks.
Pengujian `0xd34f80` membuktikan floor saat turun lintas level, bukan sumber
decay.
