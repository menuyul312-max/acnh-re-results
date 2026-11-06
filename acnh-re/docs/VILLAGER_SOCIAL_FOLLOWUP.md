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

## Batas klaim dan pekerjaan tersisa

- **Terbukti native:** perhitungan `0xd34f80` untuk poin lama yang dikendalikan,
  serta argumen yang sampai ke entry `0xef2c70`, termasuk key `Friendship`.
- **[PSEUDO]:** binding ke data record, pemilihan field di `0xf48840`, dan efek
  perubahan pada save. Badan writer belum berjalan dalam reproducer.

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

**Terbukti native:** callback aksi `0x27a220` berjalan dengan input `AddValue`
dari 12 event pada lima flow dan meneruskan nilai itu tanpa perubahan ke entry
`0xd34cb0`. Jalur validasi virtual memakai vtable aksi terdaftar
`0x3040940`, slot `0x20` memanggil fungsi asli `0x27a210`, lalu callback
mengambil resident slot serta `AddValue` dari object. Eksekusi berhenti saat
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
dan pemilihan topic/message dialog. Nilai
EventFlow adalah input yang dikonfigurasi, bukan bukti bahwa setiap cabang
terjadi dalam satu playthrough. Contoh nilai negatif EventFlow juga bukan
bukti decay harian. Penulis/delta untuk surat, pukulan jaring, dan pengabaian
belum ditemukan.

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

`0xf4dbd0` adalah helper seleksi statis yang membaca `TalkNpc0Count`, kemudian
memeriksa key `TalkNpc%dCount` untuk indeks 0–9 dan mengembalikan indeks
pertama yang nilainya berbeda dari argumennya. Caller-nya `0x395bc0`,
`0x395e50`, dan `0x3960d0`. Saya belum membuktikan bahwa indeks ini memilih
topic atau pesan; fungsi itu dan caller-nya belum dijalankan native.

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
memanggil `0xabff90`. Salah satu cabangnya memanggil `0xac0200`, yang membaca
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

**Terbuka:** konteks yang memicu cabang -3 pada `0xab9dc0`, apakah ia benar-benar
terjadi pada hari normal, serta sumber lain seperti surat, pukulan jaring, atau
pengabaian belum dibuktikan. Nilai negatif pada EventFlow tetap hanya input
aksi yang dikonfigurasi. Native friendship test sebelumnya menguji floor level
di `0xd34f80`, bukan sumber decay.
