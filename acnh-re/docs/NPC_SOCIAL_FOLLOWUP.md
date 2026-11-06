# Lanjutan NPC: batas producer grid rute

Tahap ini menguji satu bagian yang belum tertutup oleh kernel A*: producer
region pada `0xc88310`, yang dipanggil wrapper pencarian aktif. Sebanyak **12
konteks native tanpa mismatch** mencakup origin tersimpan, origin yang dihitung
ulang, batas bawah/atas X/Z, serta penjepitan ke batas region yang disiapkan.
Ini pengujian producer grid; tidak mengubah bukti A*, navigasi villager, atau
perilaku sosial.

## Kontrak yang teruji

`0xc88310` mengubah kedua vec3 menjadi koordinat grid dengan helper asli
`0x15c0a60`, memperbarui region melalui `0xc88b80`, lalu memeriksa kedua
endpoint terhadap origin dan ukuran grid. Untuk konteks yang diuji, syaratnya
adalah:

```text
originX <= endpointX < originX + width
originZ <= endpointZ < originZ + height
```

Graph yang disiapkan memakai width 25 dan height 21. Origin berada di
`graph+0x0/+0x2`; batas region yang ditulis `0xc88b80` berada di
`graph+0x4..+0xa`; ukuran berada di `graph+0xc/+0x10`. Record batas dunia
diakses melalui instruksi native, dengan konteks uji min `[0,0]` dan max
inklusif `[100,100]`.

Dua mode producer diuji. Mode origin tersimpan mempertahankan origin `[10,10]`:
koordinat bawah `[10,10]` dan sel terakhir `[34,30]` diterima; satu sel di luar
masing-masing batas X atau Z menghasilkan return `0`. Mode recenter menghitung
origin dari titik tengah lalu membatasinya ke record region. Rentang `[0,0]` ke
`[24,20]` melewati kedua predicate pada origin `[0,0]`. Untuk rentang X
`[2,25]`, hasil origin `[1,0]` melewati predicate. Untuk `[1,25]`, origin
menjadi `[0,0]` dan endpoint X=25 ditolak pada batas atas eksklusif. Kasus
penjepitan bawah dan atas menghasilkan origin `[0,0]` dan `[76,80]`.

**Batas eksekusi positif:** setiap kasus yang melewati dua predicate berhenti di
`0xc884c8`, tepat sebelum instruksi native pertama untuk menginisialisasi array
grid (`memset` pada `0x220e440`). Karena itu hasil ini membuktikan predicate
admission dan region yang ditulis sebelumnya, bukan return sukses penuh,
penulisan flag/biaya cell, worker, atau pencarian rute. Kasus yang gagal
menjalankan jalur asli sampai return `0`.

## Batas bukti

Semua instruksi yang disebut dijalankan dari ELF ACNH 1.0.0 SHA-256
`5bf707c3dc5dac0ad9635af7d336ec580f81c3f7876d0f55400d1900e3415d74` tanpa
pengganti fungsi. Origin/grid, singleton yang menyimpan batas region, dan vec3
disiapkan sebagai input eksplisit. Nilai tersebut bukan hasil pembacaan pulau
aktif.

Tahap ini belum menjalankan pengisian flag dan kategori biaya dari terrain,
collision atau actor, inisialisasi graf setelah admission, pengajuan worker,
cancellation, publikasi hasil, steering, ataupun transisi aktivitas NPC.
Tidak ada kesimpulan talk/friendship dari bukti ini.

Data rinci dan batas tiap kasus: [npc_grid_producer_native.json](../output/mechanics/npc_social_followup/npc_grid_producer_native.json).

Reproduksi pada environment ini:

```bash
cd acnh-re
PYTHONPATH=/workspace/acnh-re/.deps:tools python tools/npc_social_followup_native.py
```
