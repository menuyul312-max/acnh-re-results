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
pemilihan topic/message dialog, dan batas frekuensi sosial harian. Nilai
EventFlow adalah input yang dikonfigurasi, bukan bukti bahwa setiap cabang
terjadi dalam satu playthrough. Contoh nilai negatif EventFlow juga bukan
bukti decay harian. Penulis/delta untuk surat, pukulan jaring, dan pengabaian
belum ditemukan.
