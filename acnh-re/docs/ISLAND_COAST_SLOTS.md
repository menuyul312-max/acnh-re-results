# Lanjutan susunan pantai pulau

Pemetaan ini membaca nilai slot langsung dari 36 template dan menghubungkannya dengan kandidat part melalui hash PartsKind. Sumber rinci: `output/ui_island/island_special_slots.json`.

- 12 template 3B_S2 memiliki dua slot S_River.
- 12 template 3B_SW memiliki satu S_River dan satu W_River.
- 12 template 3B_SE memiliki satu S_River dan satu E_River.
- Seluruh template memiliki satu slot N_Tsunekiti serta masing-masing satu slot S_Airport_L dan S_Airport_R. Dua slot bandara adalah dua komponen bernama kiri/kanan; tidak diartikan sebagai dua bandara.
- Secara agregat terdapat 18 slot SE_Jetty dan 18 SW_Jetty; 18 E_Promontory dan 18 W_Promontory.

Arsip manifest lanjutan kini menyediakan PBC untuk seluruh 136 model pantai. Semua 96 preset juga cocok ke segmen River yang diharapkan: 30/30 `3B_S2`, 33/33 `3B_SW`, 33/33 `3B_SE`, menggunakan kandidat mask CCW dengan kontinuitas terbaik. Ini membuktikan kecocokan data slot-mask dan geometri/material statis tersedia, bukan posisi dunia atau perilaku renderer. Transform parent, kandidat yang dipilih RNG, seam fisik, collision aktif, dan simulasi air tetap terbuka. Detail ada di `output/ui_island/manifests_pbc_audit.json`.
