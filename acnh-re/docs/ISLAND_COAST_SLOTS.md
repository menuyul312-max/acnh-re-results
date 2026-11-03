# Lanjutan susunan pantai pulau

Pemetaan ini membaca nilai slot langsung dari 36 template dan menghubungkannya dengan kandidat part melalui hash PartsKind. Sumber rinci: `output/ui_island/island_special_slots.json`.

- 12 template 3B_S2 memiliki dua slot S_River.
- 12 template 3B_SW memiliki satu S_River dan satu W_River.
- 12 template 3B_SE memiliki satu S_River dan satu E_River.
- Seluruh template memiliki satu slot N_Tsunekiti serta masing-masing satu slot S_Airport_L dan S_Airport_R. Dua slot bandara adalah dua komponen bernama kiri/kanan; tidak diartikan sebagai dua bandara.
- Secara agregat terdapat 18 slot SE_Jetty dan 18 SW_Jetty; 18 E_Promontory dan 18 W_Promontory.

Ini membuktikan susunan simbolik slot dalam data, belum posisi dunia atau perilaku runtime. Muara pantai tidak membuktikan konektivitas sungai di dalam pulau. Pemilihan model kandidat, transform, seam, collision, dan algoritme penyusunan masih terbuka. Tidak ada tambahan kasus eksekusi native pada tahap ini.
