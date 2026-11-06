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
- **Belum ditemukan:** penulis friendship untuk hadiah, surat, pukulan jaring,
  pengabaian, decay harian, serta cap harian. Kasus delta negatif terkontrol di
  sini bukan bukti bahwa decay tersebut terjadi dalam gameplay.
- **Terbuka:** transisi `NpcAIActivityState`, pemilihan activity/talk topic,
  dan eksekusi native host/guest conversation. Registry state yang sudah
  terverifikasi dicatat di [`RESIDENT_MAP_NPC_FOLLOWUP.md`](RESIDENT_MAP_NPC_FOLLOWUP.md)
  dan [`NPC_NAVIGATION_KERNEL.md`](NPC_NAVIGATION_KERNEL.md); nama
  `cConversationHost`/`cConversationGuest` sendiri belum membuktikan state
  entry, dialog, atau transisi runtime.
