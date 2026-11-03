00552bb0 ff4302d1 sub      sp, sp, #0x90
00552bb4 fc6f03a9 stp      x28, x27, [sp, #0x30]
00552bb8 fa6704a9 stp      x26, x25, [sp, #0x40]
00552bbc f85f05a9 stp      x24, x23, [sp, #0x50]
00552bc0 f65706a9 stp      x22, x21, [sp, #0x60]
00552bc4 f44f07a9 stp      x20, x19, [sp, #0x70]
00552bc8 fd7b08a9 stp      x29, x30, [sp, #0x80]
00552bcc fd030291 add      x29, sp, #0x80
00552bd0 e12f00b9 str      w1, [sp, #0x2c]
00552bd4 e86b01f0 adrp     x8, #0x32d1000
00552bd8 08d545f9 ldr      x8, [x8, #0xba8]
00552bdc 180140f9 ldr      x24, [x8]
00552be0 00632d91 add      x0, x24, #0xb58
00552be4 f90302aa mov      x25, x2
00552be8 ffff01a9 stp      xzr, xzr, [sp, #0x18]
00552bec a14e4494 bl       #0x1666670
00552bf0 001c00b4 cbz      x0, #0x552f70
00552bf4 08a75a79 ldrh     w8, [x24, #0xd52]
00552bf8 09a35a79 ldrh     w9, [x24, #0xd50]
00552bfc 08050011 add      w8, w8, #1
00552c00 3f21286b cmp      w9, w8, uxth
00552c04 c1000054 b.ne     #0x552c1c
00552c08 f4031f2a mov      w20, wzr
00552c0c f5031f2a mov      w21, wzr
00552c10 f6031f2a mov      w22, wzr
00552c14 f7031f2a mov      w23, wzr
00552c18 9f000014 b        #0x552e94
00552c1c f90700f9 str      x25, [sp, #8]
00552c20 9c6c01b0 adrp     x28, #0x32e3000
00552c24 966c0190 adrp     x22, #0x32e2000
00552c28 9a6c0190 adrp     x26, #0x32e2000
00552c2c 9c3f45f9 ldr      x28, [x28, #0xa78]
00552c30 d69e45f9 ldr      x22, [x22, #0xb38]
00552c34 5aa345f9 ldr      x26, [x26, #0xb40]
00552c38 13008092 mov      x19, #-1
00552c3c 990a8c52 mov      w25, #0x6054
00552c40 198eaa72 movk     w25, #0x5470, lsl #16
00552c44 143d0012 and      w20, w8, #0xffff
00552c48 e803092a mov      w8, w9
00552c4c 02000014 b        #0x552c54
00552c50 09a35a79 ldrh     w9, [x24, #0xd50]
00552c54 1b3d0012 and      w27, w8, #0xffff
00552c58 6823294b sub      w8, w27, w9, uxth
00552c5c 09334db9 ldr      w9, [x24, #0xd30]
00552c60 1f01096b cmp      w8, w9
00552c64 82000054 b.hs     #0x552c74
00552c68 099f46f9 ldr      x9, [x24, #0xd38]
00552c6c 35d968f8 ldr      x21, [x9, w8, sxtw #3]
00552c70 f50000b5 cbnz     x21, #0x552c8c
00552c74 886c01d0 adrp     x8, #0x32e4000
00552c78 087543f9 ldr      x8, [x8, #0x6e8]
00552c7c 956c01d0 adrp     x21, #0x32e4000
00552c80 08fddf08 ldarb    w8, [x8]
00552c84 b57a43f9 ldr      x21, [x21, #0x6f0]
00552c88 680e0036 tbz      w8, #0, #0x552e54
00552c8c e00315aa mov      x0, x21
00552c90 844c4494 bl       #0x1665ea0
00552c94 880340b9 ldr      w8, [x28]
00552c98 1f00086b cmp      w0, w8
00552c9c a2000054 b.hs     #0x552cb0
00552ca0 880740f9 ldr      x8, [x28, #8]
00552ca4 08d96078 ldrh     w8, [x8, w0, sxtw #1]
00552ca8 1f090071 cmp      w8, #2
00552cac 49000054 b.ls     #0x552cb4
00552cb0 e8031f2a mov      w8, wzr
00552cb4 e81700b9 str      w8, [sp, #0x14]
00552cb8 e81740b9 ldr      w8, [sp, #0x14]
00552cbc e92f40b9 ldr      w9, [sp, #0x2c]
00552cc0 1f01096b cmp      w8, w9
00552cc4 c1080054 b.ne     #0x552ddc
00552cc8 a80240b9 ldr      w8, [x21]
00552ccc 88070034 cbz      w8, #0x552dbc
00552cd0 c8024039 ldrb     w8, [x22]
00552cd4 08050034 cbz      w8, #0x552d74
00552cd8 486780b9 ldrsw    x8, [x26, #0x64]
00552cdc 080bf836 tbz      w8, #0x1f, #0x552e3c
00552ce0 1f050031 cmn      w8, #1
00552ce4 a1060054 b.ne     #0x552db8
00552ce8 e00315aa mov      x0, x21
00552cec 654c4494 bl       #0x1665e80
00552cf0 400600b4 cbz      x0, #0x552db8
00552cf4 f70300aa mov      x23, x0
00552cf8 fc0316aa mov      x28, x22
00552cfc 594c4494 bl       #0x1665e60
00552d00 600500b4 cbz      x0, #0x552dac
00552d04 f60300aa mov      x22, x0
00552d08 e00317aa mov      x0, x23
00552d0c 514c4494 bl       #0x1665e50
00552d10 e87b1f32 mov      w8, #-2
00552d14 486700b9 str      w8, [x26, #0x64]
00552d18 a0040034 cbz      w0, #0x552dac
00552d1c e8031f2a mov      w8, wzr
00552d20 c9120091 add      x9, x22, #4
00552d24 ea03082a mov      w10, w8
00552d28 4af17dd3 lsl      x10, x10, #3
00552d2c ca6a6ab8 ldr      w10, [x22, x10]
00552d30 5f01196b cmp      w10, w25
00552d34 c0000054 b.eq     #0x552d4c
00552d38 08050011 add      w8, w8, #1
00552d3c 29210091 add      x9, x9, #8
00552d40 1f01006b cmp      w8, w0
00552d44 03ffff54 b.lo     #0x552d24
00552d48 19000014 b        #0x552dac
00552d4c 280140b9 ldr      w8, [x9]
00552d50 1f050031 cmn      w8, #1
00552d54 e803881a csel     w8, wzr, w8, eq
00552d58 486700b9 str      w8, [x26, #0x64]
00552d5c f6031caa mov      x22, x28
00552d60 9c6c01b0 adrp     x28, #0x32e3000
00552d64 a80240b9 ldr      w8, [x21]
00552d68 9c3f45f9 ldr      x28, [x28, #0xa78]
00552d6c 28fbff35 cbnz     w8, #0x552cd0
00552d70 13000014 b        #0x552dbc
00552d74 e8030032 mov      w8, #1
00552d78 c8020039 strb     w8, [x22]
00552d7c 530300f9 str      x19, [x26]
00552d80 53cf05a9 stp      x19, x19, [x26, #0x58]
00552d84 536b00b9 str      w19, [x26, #0x68]
00552d88 53cf04a9 stp      x19, x19, [x26, #0x48]
00552d8c 53cf03a9 stp      x19, x19, [x26, #0x38]
00552d90 53cf02a9 stp      x19, x19, [x26, #0x28]
00552d94 53cf01a9 stp      x19, x19, [x26, #0x18]
00552d98 53cf00a9 stp      x19, x19, [x26, #8]
00552d9c e00315aa mov      x0, x21
00552da0 384c4494 bl       #0x1665e80
00552da4 80faffb5 cbnz     x0, #0x552cf4
00552da8 04000014 b        #0x552db8
00552dac f6031caa mov      x22, x28
00552db0 9c6c01b0 adrp     x28, #0x32e3000
00552db4 9c3f45f9 ldr      x28, [x28, #0xa78]
00552db8 e8031f2a mov      w8, wzr
00552dbc e9030032 mov      w9, #1
00552dc0 2921c81a lsl      w9, w9, w8
00552dc4 087d0553 lsr      w8, w8, #5
00552dc8 08f57ed3 lsl      x8, x8, #2
00552dcc eb630091 add      x11, sp, #0x18
00552dd0 6a6968b8 ldr      w10, [x11, x8]
00552dd4 29010a2a orr      w9, w9, w10
00552dd8 696928b8 str      w9, [x11, x8]
00552ddc 09a75a79 ldrh     w9, [x24, #0xd52]
00552de0 e8031b2a mov      w8, w27
00552de4 1f01096b cmp      w8, w9
00552de8 22020054 b.hs     #0x552e2c
00552dec 0ba35a79 ldrh     w11, [x24, #0xd50]
00552df0 08050011 add      w8, w8, #1
00552df4 0a3d0012 and      w10, w8, #0xffff
00552df8 4a010b4b sub      w10, w10, w11
00552dfc 0b334db9 ldr      w11, [x24, #0xd30]
00552e00 5f010b6b cmp      w10, w11
00552e04 a2000054 b.hs     #0x552e18
00552e08 0b9f46f9 ldr      x11, [x24, #0xd38]
00552e0c 6ad96af8 ldr      x10, [x11, w10, sxtw #3]
00552e10 aafeffb4 cbz      x10, #0x552de4
00552e14 03000014 b        #0x552e20
00552e18 ea031faa mov      x10, xzr
00552e1c 4afeffb4 cbz      x10, #0x552de4
00552e20 9f22286b cmp      w20, w8, uxth
00552e24 61f1ff54 b.ne     #0x552c50
00552e28 18000014 b        #0x552e88
00552e2c 68070011 add      w8, w27, #1
00552e30 9f22286b cmp      w20, w8, uxth
00552e34 e1f0ff54 b.ne     #0x552c50
00552e38 14000014 b        #0x552e88
00552e3c 080115ab adds     x8, x8, x21
00552e40 e0fbff54 b.eq     #0x552dbc
00552e44 08014079 ldrh     w8, [x8]
00552e48 1ffd0171 cmp      w8, #0x7f
00552e4c 89fbff54 b.ls     #0x552dbc
00552e50 e3ffff17 b        #0x552ddc
00552e54 806c01d0 adrp     x0, #0x32e4000
00552e58 007443f9 ldr      x0, [x0, #0x6e8]
00552e5c 61ed7294 bl       #0x220e3e0
00552e60 956c01d0 adrp     x21, #0x32e4000
00552e64 b57a43f9 ldr      x21, [x21, #0x6f0]
00552e68 a0000034 cbz      w0, #0x552e7c
00552e6c bf0200b9 str      wzr, [x21]
00552e70 806c01d0 adrp     x0, #0x32e4000
00552e74 007443f9 ldr      x0, [x0, #0x6e8]
00552e78 5eed7294 bl       #0x220e3f0
00552e7c 9c6c01b0 adrp     x28, #0x32e3000
00552e80 9c3f45f9 ldr      x28, [x28, #0xa78]
00552e84 82ffff17 b        #0x552c8c
00552e88 f75b4329 ldp      w23, w22, [sp, #0x18]
00552e8c f90740f9 ldr      x25, [sp, #8]
00552e90 f5534429 ldp      w21, w20, [sp, #0x20]
00552e94 e003172a mov      w0, w23
00552e98 bee15094 bl       #0x198b590
00552e9c f803002a mov      w24, w0
00552ea0 e003162a mov      w0, w22
00552ea4 bbe15094 bl       #0x198b590
00552ea8 1300180b add      w19, w0, w24
00552eac e003152a mov      w0, w21
00552eb0 b8e15094 bl       #0x198b590
00552eb4 7302000b add      w19, w19, w0
00552eb8 e003142a mov      w0, w20
00552ebc b5e15094 bl       #0x198b590
00552ec0 7302000b add      w19, w19, w0
00552ec4 7f060071 cmp      w19, #1
00552ec8 2b050054 b.lt     #0x552f6c
00552ecc e00319aa mov      x0, x25
00552ed0 845c5194 bl       #0x19aa0e0
00552ed4 087cb39b umull    x8, w0, w19
00552ed8 e003172a mov      w0, w23
00552edc 18fd60d3 lsr      x24, x8, #0x20
00552ee0 ace15094 bl       #0x198b590
00552ee4 1f00186b cmp      w0, w24
00552ee8 8d000054 b.le     #0x552ef8
00552eec f4031f2a mov      w20, wzr
00552ef0 f3031f2a mov      w19, wzr
00552ef4 17000014 b        #0x552f50
00552ef8 f303002a mov      w19, w0
00552efc e003162a mov      w0, w22
00552f00 a4e15094 bl       #0x198b590
00552f04 1600130b add      w22, w0, w19
00552f08 df02186b cmp      w22, w24
00552f0c 6d000054 b.le     #0x552f18
00552f10 f4030032 mov      w20, #1
00552f14 0f000014 b        #0x552f50
00552f18 e003152a mov      w0, w21
00552f1c 9de15094 bl       #0x198b590
00552f20 1300160b add      w19, w0, w22
00552f24 7f02186b cmp      w19, w24
00552f28 8d000054 b.le     #0x552f38
00552f2c f4031f32 mov      w20, #2
00552f30 f303162a mov      w19, w22
00552f34 07000014 b        #0x552f50
00552f38 e003142a mov      w0, w20
00552f3c 95e15094 bl       #0x198b590
00552f40 0800130b add      w8, w0, w19
00552f44 1f01186b cmp      w8, w24
00552f48 2d010054 b.le     #0x552f6c
00552f4c f4070032 mov      w20, #3
00552f50 e9630091 add      x9, sp, #0x18
00552f54 205974b8 ldr      w0, [x9, w20, uxtw #2]
00552f58 08070011 add      w8, w24, #1
00552f5c 0101134b sub      w1, w8, w19
00552f60 b4e15094 bl       #0x198b630
00552f64 0014142b adds     w0, w0, w20, lsl #5
00552f68 45000054 b.pl     #0x552f70
00552f6c e0031f2a mov      w0, wzr
00552f70 fd7b48a9 ldp      x29, x30, [sp, #0x80]
00552f74 f44f47a9 ldp      x20, x19, [sp, #0x70]
00552f78 f65746a9 ldp      x22, x21, [sp, #0x60]
00552f7c f85f45a9 ldp      x24, x23, [sp, #0x50]
00552f80 fa6744a9 ldp      x26, x25, [sp, #0x40]
00552f84 fc6f43a9 ldp      x28, x27, [sp, #0x30]
00552f88 ff430291 add      sp, sp, #0x90
00552f8c c0035fd6 ret
