# Batas query kandidat `0x7bccf0`

## Pemanggil dan bentuk input

`0x7bccf0` adalah batas query yang dipakai jalur post-motion `0xdac780` dan
jalur vertikal `0xda86b0`. Pada situs panggil yang diperiksa, kedua fungsi
mengirim `X0 = actor+0x278` (pointer posisi XYZ), `X1 = 0` (output opsional
null), `W2 = 0`, dan `S0 = 0.0`. `0xdac780` memakai nilai `S0` hasil query
untuk membandingkan/memilih kandidat Y sebelum menulis `actor+0x27c`; ini
belum membuktikan bahwa hasil tersebut adalah landing plane pada frame live.

Peta statis di dalam query menunjukkan dua tahap enumerasi sebelum konsumsi
hasil:

- `0x7bccf0` mengambil singleton melalui pointer global di `0x32d0de8`, lalu
  meneruskan konteks `root+0x28`, posisi input, dan alamat status lokal ke
  `0x1577a0`. Helper itu membaca konteks `+0x78` dan, bila ada, memanggil
  `0x172740` untuk query grid.
- Sesudahnya `0x7bccf0` memanggil `0x157270` pada konteks yang sama. Helper itu
  mengunci konteks `+8`, membandingkan `*(context+0x50)` dengan sentinel
  `context+0x48`, lalu pada list non-kosong membaca bias link node di
  `context+0x5c` dan memanggil virtual slot kandidat `+0x30` dengan posisi
  input serta status. Jadi pembentukan registry/list dan kandidat bukan
  bagian dari tiga argumen posisi yang dikirim pemain.
- Jalur sesudah dua helper tersebut mengambil properti query tambahan melalui
  `0xe6fb50`/virtual accessor dan membentuk scalar hasil. Bagian itu tidak
  tercapai pada fixture di bawah.

Offset di atas adalah struktur yang dibaca instruksi; jenis konkret objek,
inisialisasi registry, himpunan kandidat, dan makna status per kandidat belum
diikat ke objek runtime yang valid.

## Reproduksi batas native

Fixture mencoba satu posisi terkontrol `(13,-7,29)` langsung pada fungsi ELF
asli `0x7bccf0`, dengan input register yang sama seperti caller yang disebut
di atas. `native_emulator.Sandbox` memetakan segmen ELF dan relocation asli,
stack/heap/sentinel sintetis, dan mengaktifkan FP; ia tidak menjalankan
inisialisasi world/game. Tidak ada dependency yang di-stub atau pointer root
yang dipatch.

Pada sandbox baru, alamat global `0x32d0de8` menunjuk slot `0x33728b0`, tetapi
isi pointer root pada slot itu adalah nol. Jalur native lalu membentuk
konteks `0x28`; karena halaman ELF rendah memang terpetakan di emulator,
`0x1577a0` membaca word file ELF di `0xa0` seolah-olah itu pointer grid:
`0xf90033e8f9419e10`. Panggilan native `0x172740` kemudian mencoba membaca
word pada pointer tersebut `+0x30` dan berhenti dengan invalid read di
`0xf90033e8f9419e40`, PC `0x172780` (`ldr w10,[x20,#0x30]`). Ini adalah
reproduksi batas konteks yang belum diinisialisasi, bukan fault pada objek
grid live atau hasil query ACNH.

Jalankan dari checkout ini:

```bash
PYTHONPATH=/workspace/acnh-re/.deps python \
  /workspace/acnh-re-github/acnh-re/output/mechanics/player_collider_query_remainder_20261107/player_7bccf0_boundary_native.py
```

Hasil dan pointer/fault yang diassert disimpan di
[`player_7bccf0_boundary_native.json`](../output/mechanics/player_collider_query_remainder_20261107/player_7bccf0_boundary_native.json);
harness ada di
[`player_7bccf0_boundary_native.py`](../output/mechanics/player_collider_query_remainder_20261107/player_7bccf0_boundary_native.py).
Kasus harus berhenti tepat dengan PC/alamat fault di atas dan posisi input
tetap tidak berubah.

## Batas bukti

Native instruction stream dan jalur caller-input terbukti; query penuh tidak
berjalan. Fixture hanya mencapai `0x71cfa0`, `0x1577a0`, `0x18ba40`, dan awal
`0x172740` sebelum fault. Tidak ada hasil grid/candidate query, source
collider, koreksi landing, eksekusi `0xda86b0`, atau integrasi satu frame yang
dihasilkan. Menyuntikkan alamat root/grid/list tanpa layout dan initializer
runtime akan mengubah kegagalan ini menjadi fixture buatan, sehingga cabang
tersebut tetap terbuka.
