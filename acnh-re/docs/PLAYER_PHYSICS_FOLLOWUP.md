# Lanjutan fisika pemain: record state menuju velocity dan gravity

Lanjutan ini memperluas uji solver ballistic lama dari blok `0xe17e54..0xe17e94`
ke blok asli `0xe17e0c..0xe17e94` dalam fungsi `0xe17cb0`. Batasnya tetap
terkontrol: prefix yang menghasilkan titik target dan record state tidak
dijalankan; nilai keduanya disusun di memori, lalu instruksi native dari blok
tersebut dijalankan.

## Jalur yang diuji

**[Bukti instruksi]** Pada `0xe17e0c`, fungsi membaca pointer pasangan di
`SP+0x38`. Pointer pertama menunjuk record primer; pointer kedua menunjuk
record fallback. Waktu akhir primer dibaca pada `+0x18`; bila nilainya kurang
dari nol, waktu akhir dipilih dari record fallback `+0x0c`. Waktu awal tetap
dibaca dari record primer `+0x14`. Instruksi `FCVTZU` mengubah selisih menjadi
u32; hasil nol dinaikkan menjadi satu. Unit kedua field waktu belum diketahui.

**[Bukti eksekusi native]** Blok berikutnya memanggil getter `0xdb17b0`, solver
`0x1d280`, lalu pembentuk motion `0xdb17f0`. Getter parameter mengambil
`PlayerActor.mDefaultGravity.f32` dari jalur typed asli, dengan nilai `-0.25`
pada data sumber yang sudah terikat sebelumnya. Solver mengembalikan XYZ di
S0/S1/S2. Hasil disimpan pada `player+0x574`; triplet pada `player+0xf58`
menjadi `[velocityY, -0.0, gravity]`.

| Kasus record | Durasi native | Hasil yang diperiksa |
|---|---:|---|
| Primer `start=1`, `end=4` | 3 | Velocity `[3.3333333, 2.1666667, -1.6666666]` |
| Primer `start=0.25`, `end=3.95` | 3 | Pecahan dipotong oleh konversi u32 |
| Primer memiliki end negatif, fallback `end=7.5`, start `2` | 5 | Endpoint fallback dipakai |
| Selisih nol atau negatif | 1 | Durasi minimum pada blok ini |
| Pointer pasangan atau record primer kosong | 1 | Cabang default pada blok ini |

Kesembilan fixture lolos tanpa mismatch. Velocity dan triplet dibandingkan
bit-per-bit terhadap recurrence f32; buffer aktor, target, record, guard, dan
field pemain selain dua area keluaran dipastikan tidak berubah. Tidak ada
dependency yang di-stub.

## Batas bukti

**[Input fixture]** Record waktu, titik target, posisi awal aktor, registry
jenis aktor yang sudah terinisialisasi, dan fallback parameter PlayerActor
disuplai oleh harness. Karena prefix state tidak berjalan, hasil ini belum
mengidentifikasi record tersebut sebagai timer gameplay tertentu atau
membuktikan bagaimana tombol maupun state transisi mengisinya.

**[Batas runtime]** Blok berhenti sebelum bagian fungsi yang memproses query
posisi dan gerak setelah velocity disimpan. Tahap ini tidak menambah bukti
untuk collision geometry, penetration response, koreksi landing, mask solver,
penjadwalan traversal, satuan durasi, atau simulasi satu frame penuh. Fixture
finite yang disebutkan juga tidak mencakup NaN, infinity, atau durasi besar
dengan loop panjang.

Alamat adalah VA ELF ACNH 1.0.0, SHA-256
`5bf707c3dc5dac0ad9635af7d336ec580f81c3f7876d0f55400d1900e3415d74`. Input
`additional_exefs/main` SHA-256
`f8d248109ff72999b4600ae3749f8c7397fb960f7ad3ab8dee3018ae9e14e900`; audit
[ADDITIONAL_EXEFS](ADDITIONAL_EXEFS.md) mencatat segmen kode main NSO identik
dengan `main.elf` yang memuat alamat tersebut. Kedua input hanya dibaca.

Data terperinci, sampel, dan hash byte ada di
[`player_state_velocity_native.json`](../output/mechanics/player_physics_followup/player_state_velocity_native.json).
Harness dapat dijalankan dengan:

```bash
PYTHONPATH=/workspace/acnh-re/.deps python tools/player_physics_followup_native.py
```

Lingkungan memakai Unicorn 2.1.4 dan pyelftools 0.33; Capstone yang tersedia
5.0.7, sedangkan versi yang dipin repo 5.0.9. Tidak ada paket yang dipasang
atau file sumber yang diubah.
