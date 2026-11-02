004cd070 fb0f1af8 str      x27, [sp, #-0x60]!
004cd074 fa6701a9 stp      x26, x25, [sp, #0x10]
004cd078 f85f02a9 stp      x24, x23, [sp, #0x20]
004cd07c f65703a9 stp      x22, x21, [sp, #0x30]
004cd080 f44f04a9 stp      x20, x19, [sp, #0x40]
004cd084 fd7b05a9 stp      x29, x30, [sp, #0x50]
004cd088 fd430191 add      x29, sp, #0x50
004cd08c f303012a mov      w19, w1
004cd090 f403002a mov      w20, w0
004cd094 562801b0 adrp     x22, #0x29d6000
004cd098 d6620e91 add      x22, x22, #0x398
004cd09c 68064092 and      x8, x19, #3
004cd0a0 980e42d3 ubfx     x24, x20, #2, #2
004cd0a4 d76a6838 ldrb     w23, [x22, x8]
004cd0a8 88064092 and      x8, x20, #3
004cd0ac c86a6838 ldrb     w8, [x22, x8]
004cd0b0 1f090071 cmp      w8, #2
004cd0b4 80010054 b.eq     #0x4cd0e4
004cd0b8 1f050071 cmp      w8, #1
004cd0bc a1020054 b.ne     #0x4cd110
004cd0c0 e0031f32 mov      w0, #2
004cd0c4 d7182a94 bl       #0xf53420
004cd0c8 1f000071 cmp      w0, #0
004cd0cc f5179f1a cset     w21, eq
004cd0d0 d96a7838 ldrb     w25, [x22, x24]
004cd0d4 7b0e42d3 ubfx     x27, x19, #2, #2
004cd0d8 ff0a0071 cmp      w23, #2
004cd0dc 41020054 b.ne     #0x4cd124
004cd0e0 06000014 b        #0x4cd0f8
004cd0e4 f5030032 mov      w21, #1
004cd0e8 d96a7838 ldrb     w25, [x22, x24]
004cd0ec 7b0e42d3 ubfx     x27, x19, #2, #2
004cd0f0 ff0a0071 cmp      w23, #2
004cd0f4 81010054 b.ne     #0x4cd124
004cd0f8 b5060011 add      w21, w21, #1
004cd0fc d86a7b38 ldrb     w24, [x22, x27]
004cd100 9a1644d3 ubfx     x26, x20, #4, #2
004cd104 3f0b0071 cmp      w25, #2
004cd108 21020054 b.ne     #0x4cd14c
004cd10c 1b000014 b        #0x4cd178
004cd110 f5031f2a mov      w21, wzr
004cd114 d96a7838 ldrb     w25, [x22, x24]
004cd118 7b0e42d3 ubfx     x27, x19, #2, #2
004cd11c ff0a0071 cmp      w23, #2
004cd120 c0feff54 b.eq     #0x4cd0f8
004cd124 ff060071 cmp      w23, #1
004cd128 a1000054 b.ne     #0x4cd13c
004cd12c e0031f32 mov      w0, #2
004cd130 bc182a94 bl       #0xf53420
004cd134 1f000071 cmp      w0, #0
004cd138 b516951a cinc     w21, w21, eq
004cd13c d86a7b38 ldrb     w24, [x22, x27]
004cd140 9a1644d3 ubfx     x26, x20, #4, #2
004cd144 3f0b0071 cmp      w25, #2
004cd148 80010054 b.eq     #0x4cd178
004cd14c 3f070071 cmp      w25, #1
004cd150 a1020054 b.ne     #0x4cd1a4
004cd154 e0031f32 mov      w0, #2
004cd158 b2182a94 bl       #0xf53420
004cd15c 1f000071 cmp      w0, #0
004cd160 f7179f1a cset     w23, eq
004cd164 d96a7a38 ldrb     w25, [x22, x26]
004cd168 7b1644d3 ubfx     x27, x19, #4, #2
004cd16c 1f0b0071 cmp      w24, #2
004cd170 41020054 b.ne     #0x4cd1b8
004cd174 06000014 b        #0x4cd18c
004cd178 f7030032 mov      w23, #1
004cd17c d96a7a38 ldrb     w25, [x22, x26]
004cd180 7b1644d3 ubfx     x27, x19, #4, #2
004cd184 1f0b0071 cmp      w24, #2
004cd188 81010054 b.ne     #0x4cd1b8
004cd18c f7060011 add      w23, w23, #1
004cd190 d86a7b38 ldrb     w24, [x22, x27]
004cd194 9a1e46d3 ubfx     x26, x20, #6, #2
004cd198 3f0b0071 cmp      w25, #2
004cd19c 21020054 b.ne     #0x4cd1e0
004cd1a0 1b000014 b        #0x4cd20c
004cd1a4 f7031f2a mov      w23, wzr
004cd1a8 d96a7a38 ldrb     w25, [x22, x26]
004cd1ac 7b1644d3 ubfx     x27, x19, #4, #2
004cd1b0 1f0b0071 cmp      w24, #2
004cd1b4 c0feff54 b.eq     #0x4cd18c
004cd1b8 1f070071 cmp      w24, #1
004cd1bc a1000054 b.ne     #0x4cd1d0
004cd1c0 e0031f32 mov      w0, #2
004cd1c4 97182a94 bl       #0xf53420
004cd1c8 1f000071 cmp      w0, #0
004cd1cc f716971a cinc     w23, w23, eq
004cd1d0 d86a7b38 ldrb     w24, [x22, x27]
004cd1d4 9a1e46d3 ubfx     x26, x20, #6, #2
004cd1d8 3f0b0071 cmp      w25, #2
004cd1dc 80010054 b.eq     #0x4cd20c
004cd1e0 3f070071 cmp      w25, #1
004cd1e4 81020054 b.ne     #0x4cd234
004cd1e8 e0031f32 mov      w0, #2
004cd1ec 8d182a94 bl       #0xf53420
004cd1f0 1f000071 cmp      w0, #0
004cd1f4 f4179f1a cset     w20, eq
004cd1f8 791e46d3 ubfx     x25, x19, #6, #2
004cd1fc d36a7a38 ldrb     w19, [x22, x26]
004cd200 1f0b0071 cmp      w24, #2
004cd204 21020054 b.ne     #0x4cd248
004cd208 06000014 b        #0x4cd220
004cd20c f4030032 mov      w20, #1
004cd210 791e46d3 ubfx     x25, x19, #6, #2
004cd214 d36a7a38 ldrb     w19, [x22, x26]
004cd218 1f0b0071 cmp      w24, #2
004cd21c 61010054 b.ne     #0x4cd248
004cd220 94060011 add      w20, w20, #1
004cd224 d66a7938 ldrb     w22, [x22, x25]
004cd228 7f0a0071 cmp      w19, #2
004cd22c 01020054 b.ne     #0x4cd26c
004cd230 18000014 b        #0x4cd290
004cd234 f4031f2a mov      w20, wzr
004cd238 791e46d3 ubfx     x25, x19, #6, #2
004cd23c d36a7a38 ldrb     w19, [x22, x26]
004cd240 1f0b0071 cmp      w24, #2
004cd244 e0feff54 b.eq     #0x4cd220
004cd248 1f070071 cmp      w24, #1
004cd24c a1000054 b.ne     #0x4cd260
004cd250 e0031f32 mov      w0, #2
004cd254 73182a94 bl       #0xf53420
004cd258 1f000071 cmp      w0, #0
004cd25c 9416941a cinc     w20, w20, eq
004cd260 d66a7938 ldrb     w22, [x22, x25]
004cd264 7f0a0071 cmp      w19, #2
004cd268 40010054 b.eq     #0x4cd290
004cd26c 7f060071 cmp      w19, #1
004cd270 a1010054 b.ne     #0x4cd2a4
004cd274 e0031f32 mov      w0, #2
004cd278 6a182a94 bl       #0xf53420
004cd27c 1f000071 cmp      w0, #0
004cd280 f3179f1a cset     w19, eq
004cd284 df0a0071 cmp      w22, #2
004cd288 41010054 b.ne     #0x4cd2b0
004cd28c 04000014 b        #0x4cd29c
004cd290 f3030032 mov      w19, #1
004cd294 df0a0071 cmp      w22, #2
004cd298 c1000054 b.ne     #0x4cd2b0
004cd29c 73060011 add      w19, w19, #1
004cd2a0 0a000014 b        #0x4cd2c8
004cd2a4 f3031f2a mov      w19, wzr
004cd2a8 df0a0071 cmp      w22, #2
004cd2ac 80ffff54 b.eq     #0x4cd29c
004cd2b0 df060071 cmp      w22, #1
004cd2b4 a1000054 b.ne     #0x4cd2c8
004cd2b8 e0031f32 mov      w0, #2
004cd2bc 59182a94 bl       #0xf53420
004cd2c0 1f000071 cmp      w0, #0
004cd2c4 7316931a cinc     w19, w19, eq
004cd2c8 48290190 adrp     x8, #0x29f5000
004cd2cc 08093e91 add      x8, x8, #0xf82
004cd2d0 09497338 ldrb     w9, [x8, w19, uxtw]
004cd2d4 0a497438 ldrb     w10, [x8, w20, uxtw]
004cd2d8 4909092a orr      w9, w10, w9, lsl #2
004cd2dc 0b497738 ldrb     w11, [x8, w23, uxtw]
004cd2e0 6909092a orr      w9, w11, w9, lsl #2
004cd2e4 08497538 ldrb     w8, [x8, w21, uxtw]
004cd2e8 0009092a orr      w0, w8, w9, lsl #2
004cd2ec fd7b45a9 ldp      x29, x30, [sp, #0x50]
004cd2f0 f44f44a9 ldp      x20, x19, [sp, #0x40]
004cd2f4 f65743a9 ldp      x22, x21, [sp, #0x30]
004cd2f8 f85f42a9 ldp      x24, x23, [sp, #0x20]
004cd2fc fa6741a9 ldp      x26, x25, [sp, #0x10]
004cd300 fb0746f8 ldr      x27, [sp], #0x60
004cd304 c0035fd6 ret      
