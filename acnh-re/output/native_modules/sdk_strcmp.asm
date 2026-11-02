004d7900 2800004a eor      w8, w1, w0
004d7904 08094092 and      x8, x8, #7
004d7908 880200b4 cbz      x8, #0x4d7958
004d790c 08004039 ldrb     w8, [x0]
004d7910 29004039 ldrb     w9, [x1]
004d7914 1f010071 cmp      w8, #0
004d7918 0011497a ccmp     w8, w9, #0, ne
004d791c 01010054 b.ne     #0x4d793c
004d7920 00040091 add      x0, x0, #1
004d7924 21040091 add      x1, x1, #1
004d7928 08004039 ldrb     w8, [x0]
004d792c 29004039 ldrb     w9, [x1]
004d7930 1f010071 cmp      w8, #0
004d7934 0011497a ccmp     w8, w9, #0, ne
004d7938 40ffff54 b.eq     #0x4d7920
004d793c 0001094b sub      w0, w8, w9
004d7940 c0035fd6 ret      
004d7944 08144038 ldrb     w8, [x0], #1
004d7948 29144038 ldrb     w9, [x1], #1
004d794c 1f010071 cmp      w8, #0
004d7950 0011497a ccmp     w8, w9, #0, ne
004d7954 41ffff54 b.ne     #0x4d793c
004d7958 08084092 and      x8, x0, #7
004d795c 48ffffb5 cbnz     x8, #0x4d7944
004d7960 08004039 ldrb     w8, [x0]
004d7964 29004039 ldrb     w9, [x1]
004d7968 1f010071 cmp      w8, #0
004d796c 0011497a ccmp     w8, w9, #0, ne
004d7970 61feff54 b.ne     #0x4d793c
004d7974 eadb07b2 mov      x10, #-0x101010101010102
004d7978 e8031f2a mov      w8, wzr
004d797c eadf9ff2 movk     x10, #0xfeff
004d7980 088440f8 ldr      x8, [x0], #8
004d7984 0b010a8b add      x11, x8, x10
004d7988 298440f8 ldr      x9, [x1], #8
004d798c 2c0108ca eor      x12, x9, x8
004d7990 6b01288a bic      x11, x11, x8
004d7994 6bc10192 and      x11, x11, #0x8080808080808080
004d7998 6b010caa orr      x11, x11, x12
004d799c 2bffffb4 cbz      x11, #0x4d7980
004d79a0 6c0000b5 cbnz     x12, #0x4d79ac
004d79a4 e0031f2a mov      w0, wzr
004d79a8 c0035fd6 ret      
004d79ac 6a01c0da rbit     x10, x11
004d79b0 4a11c0da clz      x10, x10
004d79b4 4a0d7d92 and      x10, x10, #0x78
004d79b8 0825ca9a lsr      x8, x8, x10
004d79bc 081d0012 and      w8, w8, #0xff
004d79c0 2925ca9a lsr      x9, x9, x10
004d79c4 0001294b sub      w0, w8, w9, uxtb
004d79c8 c0035fd6 ret      
