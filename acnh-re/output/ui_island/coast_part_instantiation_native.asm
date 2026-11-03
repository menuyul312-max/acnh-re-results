; template_setup ELF 0x528bf0 size=476 sha256=725d2c3f3ddebcb59103aab321d735e8625155987ca2eff0b71ebc1eaf67feb1
00528bf0 ff0302d1 sub      sp, sp, #0x80
00528bf4 f72300f9 str      x23, [sp, #0x40]
00528bf8 f65705a9 stp      x22, x21, [sp, #0x50]
00528bfc f44f06a9 stp      x20, x19, [sp, #0x60]
00528c00 fd7b07a9 stp      x29, x30, [sp, #0x70]
00528c04 fdc30191 add      x29, sp, #0x70
00528c08 1f0800b9 str      wzr, [x0, #8]
00528c0c 1fd000b9 str      wzr, [x0, #0xd0]
00528c10 28104079 ldrh     w8, [x1, #8]
00528c14 350040f9 ldr      x21, [x1]
00528c18 08180079 strh     w8, [x0, #0xc]
00528c1c 28144079 ldrh     w8, [x1, #0xa]
00528c20 081c0079 strh     w8, [x0, #0xe]
00528c24 280c40b9 ldr      w8, [x1, #0xc]
00528c28 f30300aa mov      x19, x0
00528c2c 08b800b9 str      w8, [x0, #0xb8]
00528c30 489b9652 mov      w8, #0xb4da
00528c34 a889a472 movk     w8, #0x244d, lsl #16
00528c38 e0c30091 add      x0, sp, #0x30
00528c3c f40301aa mov      x20, x1
00528c40 ff0b00b9 str      wzr, [sp, #8]
00528c44 ff330039 strb     wzr, [sp, #0xc]
00528c48 ff1b00b9 str      wzr, [sp, #0x18]
00528c4c e80b00f9 str      x8, [sp, #0x10]
00528c50 68e0ff97 bl       #0x520df0
00528c54 e0c30091 add      x0, sp, #0x30
00528c58 e2230091 add      x2, sp, #8
00528c5c e10315aa mov      x1, x21
00528c60 ccd7ff97 bl       #0x51eb90
00528c64 605200f9 str      x0, [x19, #0xa0]
00528c68 e0c30091 add      x0, sp, #0x30
00528c6c 6de0ff97 bl       #0x520e20
00528c70 611a4079 ldrh     w1, [x19, #0xc]
00528c74 e0c30091 add      x0, sp, #0x30
00528c78 8ac00094 bl       #0x558ea0
00528c7c 685240f9 ldr      x8, [x19, #0xa0]
00528c80 e80000b4 cbz      x8, #0x528c9c
00528c84 085540f9 ldr      x8, [x8, #0xa8]
00528c88 a80000b4 cbz      x8, #0x528c9c
00528c8c 02c10091 add      x2, x8, #0x30
00528c90 e0c30091 add      x0, sp, #0x30
00528c94 e10315aa mov      x1, x21
00528c98 aac00094 bl       #0x558f40
00528c9c 62020391 add      x2, x19, #0xc0
00528ca0 e0c30091 add      x0, sp, #0x30
00528ca4 e10315aa mov      x1, x21
00528ca8 06c30094 bl       #0x5598c0
00528cac 685240f9 ldr      x8, [x19, #0xa0]
00528cb0 880100b4 cbz      x8, #0x528ce0
00528cb4 611e4079 ldrh     w1, [x19, #0xe]
00528cb8 e0230091 add      x0, sp, #8
00528cbc 39d7fe97 bl       #0x4de9a0
00528cc0 76420091 add      x22, x19, #0x10
00528cc4 e0230091 add      x0, sp, #8
00528cc8 e10316aa mov      x1, x22
00528ccc 39d7fe97 bl       #0x4de9b0
00528cd0 685240f9 ldr      x8, [x19, #0xa0]
00528cd4 005d40f9 ldr      x0, [x8, #0xb8]
00528cd8 e10316aa mov      x1, x22
00528cdc eddffe97 bl       #0x4e0c90
00528ce0 00138052 mov      w0, #0x98
00528ce4 e10315aa mov      x1, x21
00528ce8 e2031d32 mov      w2, #8
00528cec 89fa5094 bl       #0x1967710
00528cf0 f60300aa mov      x22, x0
00528cf4 8f070194 bl       #0x56ab30
00528cf8 e8230091 add      x8, sp, #8
00528cfc 17410091 add      x23, x8, #0x10
00528d00 e00317aa mov      x0, x23
00528d04 9bfc0094 bl       #0x567f70
00528d08 080e80d2 mov      x8, #0x70
00528d0c 080cc0f2 movk     x8, #0x60, lsl #32
00528d10 817901b0 adrp     x1, #0x3459000
00528d14 21202991 add      x1, x1, #0xa48
00528d18 e00317aa mov      x0, x23
00528d1c ff530079 strh     wzr, [sp, #0x28]
00528d20 f5a300a9 stp      x21, x8, [sp, #8]
00528d24 33fd0094 bl       #0x5681f0
00528d28 e8030032 mov      w8, #1
00528d2c e1230091 add      x1, sp, #8
00528d30 e00316aa mov      x0, x22
00528d34 e8a70039 strb     w8, [sp, #0x29]
00528d38 ba070194 bl       #0x56ac20
00528d3c 685240f9 ldr      x8, [x19, #0xa0]
00528d40 e00317aa mov      x0, x23
00528d44 c80a00f9 str      x8, [x22, #0x10]
00528d48 765600f9 str      x22, [x19, #0xa8]
00528d4c 21fd0094 bl       #0x5681d0
00528d50 e00b1c32 mov      w0, #0x70
00528d54 e10315aa mov      x1, x21
00528d58 e2031d32 mov      w2, #8
00528d5c 6dfa5094 bl       #0x1967710
00528d60 f60300aa mov      x22, x0
00528d64 07730094 bl       #0x545980
00528d68 685640f9 ldr      x8, [x19, #0xa8]
00528d6c f5a300a9 stp      x21, x8, [sp, #8]
00528d70 880e40b9 ldr      w8, [x20, #0xc]
00528d74 09198052 mov      w9, #0xc8
00528d78 e1230091 add      x1, sp, #8
00528d7c e00316aa mov      x0, x22
00528d80 e8270329 stp      w8, w9, [sp, #0x18]
00528d84 27730094 bl       #0x545a20
00528d88 605640f9 ldr      x0, [x19, #0xa8]
00528d8c e1030032 mov      w1, #1
00528d90 765a00f9 str      x22, [x19, #0xb0]
00528d94 f3090194 bl       #0x56b560
00528d98 605a40f9 ldr      x0, [x19, #0xb0]
00528d9c ed730094 bl       #0x545d50
00528da0 680a40b9 ldr      w8, [x19, #8]
00528da4 08010032 orr      w8, w8, #1
00528da8 e0c30091 add      x0, sp, #0x30
00528dac 680a00b9 str      w8, [x19, #8]
00528db0 44c00094 bl       #0x558ec0
00528db4 fd7b47a9 ldp      x29, x30, [sp, #0x70]
00528db8 f72340f9 ldr      x23, [sp, #0x40]
00528dbc f44f46a9 ldp      x20, x19, [sp, #0x60]
00528dc0 f65745a9 ldp      x22, x21, [sp, #0x50]
00528dc4 ff030291 add      sp, sp, #0x80
00528dc8 c0035fd6 ret

; template_update_dispatch ELF 0x529de0 size=104 sha256=12b14577389ce9b849ee63a56a317e9929373634ffb74fdaf79f085665c3f47d
00529de0 f44fbea9 stp      x20, x19, [sp, #-0x20]!
00529de4 fd7b01a9 stp      x29, x30, [sp, #0x10]
00529de8 fd430091 add      x29, sp, #0x10
00529dec f30300aa mov      x19, x0
00529df0 e0598352 mov      w0, #0x1acf
00529df4 40aeb072 movk     w0, #0x8572, lsl #16
00529df8 ba0d2b94 bl       #0xfed4e0
00529dfc 80010036 tbz      w0, #0, #0x529e2c
00529e00 68224039 ldrb     w8, [x19, #8]
00529e04 48010036 tbz      w8, #0, #0x529e2c
00529e08 741240b9 ldr      w20, [x19, #0x10]
00529e0c 14010034 cbz      w20, #0x529e2c
00529e10 730e40f9 ldr      x19, [x19, #0x18]
00529e14 600240f9 ldr      x0, [x19]
00529e18 96fcff97 bl       #0x529070
00529e1c e0000036 tbz      w0, #0, #0x529e38
00529e20 73220091 add      x19, x19, #8
00529e24 940600f1 subs     x20, x20, #1
00529e28 61ffff54 b.ne     #0x529e14
00529e2c fd7b41a9 ldp      x29, x30, [sp, #0x10]
00529e30 f44fc2a8 ldp      x20, x19, [sp], #0x20
00529e34 c0035fd6 ret
00529e38 600240f9 ldr      x0, [x19]
00529e3c fd7b41a9 ldp      x29, x30, [sp, #0x10]
00529e40 f44fc2a8 ldp      x20, x19, [sp], #0x20
00529e44 07fcff17 b        #0x528e60

; coast_instance_update ELF 0x528e60 size=528 sha256=5da662546e997a7255a959d3bace16d93f22eb9ca8bf346fcfbed4077aaa5291
00528e60 ff4305d1 sub      sp, sp, #0x150
00528e64 fc9300f9 str      x28, [sp, #0x120]
00528e68 f44f13a9 stp      x20, x19, [sp, #0x130]
00528e6c fd7b14a9 stp      x29, x30, [sp, #0x140]
00528e70 fd030591 add      x29, sp, #0x140
00528e74 080840b9 ldr      w8, [x0, #8]
00528e78 280f0036 tbz      w8, #0, #0x52905c
00528e7c f30300aa mov      x19, x0
00528e80 005840f9 ldr      x0, [x0, #0xb0]
00528e84 a9028052 mov      w9, #0x15
00528e88 3f01286a bics     wzr, w9, w8
00528e8c 61000054 b.ne     #0x528e98
00528e90 08204039 ldrb     w8, [x0, #8]
00528e94 480e0837 tbnz     w8, #1, #0x52905c
00528e98 56730094 bl       #0x545bf0
00528e9c 685a40f9 ldr      x8, [x19, #0xb0]
00528ea0 08214039 ldrb     w8, [x8, #8]
00528ea4 c80d0836 tbz      w8, #1, #0x52905c
00528ea8 680a40b9 ldr      w8, [x19, #8]
00528eac c8010837 tbnz     w8, #1, #0x528ee4
00528eb0 486d01b0 adrp     x8, #0x32d1000
00528eb4 08d545f9 ldr      x8, [x8, #0xba8]
00528eb8 080140f9 ldr      x8, [x8]
00528ebc 099b8252 mov      w9, #0x14d8
00528ec0 0001098b add      x0, x8, x9
00528ec4 685240f9 ldr      x8, [x19, #0xa0]
00528ec8 015d40f9 ldr      x1, [x8, #0xb8]
00528ecc c2a89752 mov      w2, #0xbd46
00528ed0 42c4ac72 movk     w2, #0x6622, lsl #16
00528ed4 7fd1fe97 bl       #0x4dd4d0
00528ed8 680a40b9 ldr      w8, [x19, #8]
00528edc 08011f32 orr      w8, w8, #2
00528ee0 680a00b9 str      w8, [x19, #8]
00528ee4 68021037 tbnz     w8, #2, #0x528f30
00528ee8 486d01b0 adrp     x8, #0x32d1000
00528eec 08d545f9 ldr      x8, [x8, #0xba8]
00528ef0 080140f9 ldr      x8, [x8]
00528ef4 e9030032 mov      w9, #1
00528ef8 a9031d38 sturb    w9, [x29, #-0x30]
00528efc 099b8252 mov      w9, #0x14d8
00528f00 ca5901f0 adrp     x10, #0x3063000
00528f04 4a813091 add      x10, x10, #0xc20
00528f08 0001098b add      x0, x8, x9
00528f0c a8c300d1 sub      x8, x29, #0x30
00528f10 e1630091 add      x1, sp, #0x18
00528f14 eaa301a9 stp      x10, x8, [sp, #0x18]
00528f18 52d1fe97 bl       #0x4dd460
00528f1c a9035d38 ldurb    w9, [x29, #-0x30]
00528f20 680a40b9 ldr      w8, [x19, #8]
00528f24 69000034 cbz      w9, #0x528f30
00528f28 08011e32 orr      w8, w8, #4
00528f2c 680a00b9 str      w8, [x19, #8]
00528f30 e8071837 tbnz     w8, #3, #0x52902c
00528f34 fb8dfd97 bl       #0x48c720
00528f38 e103002a mov      w1, w0
00528f3c a0c300d1 sub      x0, x29, #0x30
00528f40 e849fd97 bl       #0x47b6e0
00528f44 a00301d1 sub      x0, x29, #0x40
00528f48 c6080094 bl       #0x52b260
00528f4c a0c300d1 sub      x0, x29, #0x30
00528f50 004afd97 bl       #0x47b750
00528f54 486d0190 adrp     x8, #0x32d0000
00528f58 083543f9 ldr      x8, [x8, #0x668]
00528f5c 14410091 add      x20, x8, #0x10
00528f60 f48301a9 stp      x20, x0, [sp, #0x18]
00528f64 61020391 add      x1, x19, #0xc0
00528f68 e0630091 add      x0, sp, #0x18
00528f6c a20301d1 sub      x2, x29, #0x40
00528f70 4c84f197 bl       #0x18a0a0
00528f74 a00301d1 sub      x0, x29, #0x40
00528f78 a14301d1 sub      x1, x29, #0x50
00528f7c 51090094 bl       #0x52b4c0
00528f80 e0630091 add      x0, sp, #0x18
00528f84 bf431bb8 stur     wzr, [x29, #-0x4c]
00528f88 d22eec97 bl       #0x34ad0
00528f8c c86d01b0 adrp     x8, #0x32e1000
00528f90 087943f9 ldr      x8, [x8, #0x6f0]
00528f94 080140b9 ldr      w8, [x8]
00528f98 e0630091 add      x0, sp, #0x18
00528f9c a14301d1 sub      x1, x29, #0x50
00528fa0 e81f00b9 str      w8, [sp, #0x1c]
00528fa4 6f2fec97 bl       #0x34d60
00528fa8 e0630091 add      x0, sp, #0x18
00528fac e1031f2a mov      w1, wzr
00528fb0 e2030032 mov      w2, #1
00528fb4 7b2fec97 bl       #0x34da0
00528fb8 a0c300d1 sub      x0, x29, #0x30
00528fbc e549fd97 bl       #0x47b750
00528fc0 f48300a9 stp      x20, x0, [sp, #8]
00528fc4 e0630091 add      x0, sp, #0x18
00528fc8 e1230091 add      x1, sp, #8
00528fcc 7d2fec97 bl       #0x34dc0
00528fd0 486d0190 adrp     x8, #0x32d0000
00528fd4 08f146f9 ldr      x8, [x8, #0xde0]
00528fd8 000140f9 ldr      x0, [x8]
00528fdc e21b40b9 ldr      w2, [sp, #0x18]
00528fe0 e1630091 add      x1, sp, #0x18
00528fe4 e3031f2a mov      w3, wzr
00528fe8 4280ec97 bl       #0x490f0
00528fec a8035bb8 ldur     w8, [x29, #-0x50]
00528ff0 60221a29 stp      w0, w8, [x19, #0xd0]
00528ff4 a8435bb8 ldur     w8, [x29, #-0x4c]
00528ff8 68da00b9 str      w8, [x19, #0xd8]
00528ffc a8835bb8 ldur     w8, [x29, #-0x48]
00529000 68de00b9 str      w8, [x19, #0xdc]
00529004 680a40b9 ldr      w8, [x19, #8]
00529008 08011d32 orr      w8, w8, #8
0052900c e0630091 add      x0, sp, #0x18
00529010 680a00b9 str      w8, [x19, #8]
00529014 c32fec97 bl       #0x34f20
00529018 a00301d1 sub      x0, x29, #0x40
0052901c f1080094 bl       #0x52b3e0
00529020 a0c300d1 sub      x0, x29, #0x30
00529024 c349fd97 bl       #0x47b730
00529028 680a40b9 ldr      w8, [x19, #8]
0052902c 88012037 tbnz     w8, #4, #0x52905c
00529030 61420391 add      x1, x19, #0xd0
00529034 e0630091 add      x0, sp, #0x18
00529038 e2031f2a mov      w2, wzr
0052903c 715bec97 bl       #0x3fe00
00529040 e80f40f9 ldr      x8, [sp, #0x18]
00529044 880000b5 cbnz     x8, #0x529054
00529048 680a40b9 ldr      w8, [x19, #8]
0052904c 08011c32 orr      w8, w8, #0x10
00529050 680a00b9 str      w8, [x19, #8]
00529054 e0630091 add      x0, sp, #0x18
00529058 fa5bec97 bl       #0x40040
0052905c fd7b54a9 ldp      x29, x30, [sp, #0x140]
00529060 fc9340f9 ldr      x28, [sp, #0x120]
00529064 f44f53a9 ldp      x20, x19, [sp, #0x130]
00529068 ff430591 add      sp, sp, #0x150
0052906c c0035fd6 ret

; template_grid_enable_flag ELF 0x4de9a0 size=8 sha256=f40f917bec7a5e49fface58890afdec1bd2dd554f06991a76e10b145eae2525c
004de9a0 01000079 strh     w1, [x0]
004de9a4 c0035fd6 ret

; coast_grid_assembly_wrapper ELF 0x4de9b0 size=136 sha256=fd6355df87ba75d0f6613e8d3d4e999987246a20fac2e51fec59b60b3ad3be36
004de9b0 610300b4 cbz      x1, #0x4dea1c
004de9b4 ffc302d1 sub      sp, sp, #0xb0
004de9b8 f44f09a9 stp      x20, x19, [sp, #0x90]
004de9bc fd7b0aa9 stp      x29, x30, [sp, #0xa0]
004de9c0 fd830291 add      x29, sp, #0xa0
004de9c4 f40300aa mov      x20, x0
004de9c8 e0030091 mov      x0, sp
004de9cc f30301aa mov      x19, x1
004de9d0 90ffff97 bl       #0x4de810
004de9d4 e1030091 mov      x1, sp
004de9d8 e00314aa mov      x0, x20
004de9dc 19000094 bl       #0x4dea40
004de9e0 20020036 tbz      w0, #0, #0x4dea24
004de9e4 e1030091 mov      x1, sp
004de9e8 e00314aa mov      x0, x20
004de9ec 31010094 bl       #0x4deeb0
004de9f0 e1030091 mov      x1, sp
004de9f4 af040094 bl       #0x4dfcb0
004de9f8 02128052 mov      w2, #0x90
004de9fc e1030091 mov      x1, sp
004dea00 e00313aa mov      x0, x19
004dea04 8bbe7494 bl       #0x220e430
004dea08 e0030032 mov      w0, #1
004dea0c fd7b4aa9 ldp      x29, x30, [sp, #0xa0]
004dea10 f44f49a9 ldp      x20, x19, [sp, #0x90]
004dea14 ffc30291 add      sp, sp, #0xb0
004dea18 c0035fd6 ret
004dea1c e0031f2a mov      w0, wzr
004dea20 c0035fd6 ret
004dea24 e0031f2a mov      w0, wzr
004dea28 fd7b4aa9 ldp      x29, x30, [sp, #0xa0]
004dea2c f44f49a9 ldp      x20, x19, [sp, #0x90]
004dea30 ffc30291 add      sp, sp, #0xb0
004dea34 c0035fd6 ret

; coast_grid_to_part_records ELF 0x4e0c90 size=204 sha256=8bed71370f14461551a3d699dcce9ac72c0fe4ea765d9182f762a8550a32943c
004e0c90 f90f1bf8 str      x25, [sp, #-0x50]!
004e0c94 f85f01a9 stp      x24, x23, [sp, #0x10]
004e0c98 f65702a9 stp      x22, x21, [sp, #0x20]
004e0c9c f44f03a9 stp      x20, x19, [sp, #0x30]
004e0ca0 fd7b04a9 stp      x29, x30, [sp, #0x40]
004e0ca4 fd030191 add      x29, sp, #0x40
004e0ca8 280180d2 mov      x8, #9
004e0cac 0801c0f2 movk     x8, #8, lsl #32
004e0cb0 f40301aa mov      x20, x1
004e0cb4 f30300aa mov      x19, x0
004e0cb8 f7031f2a mov      w23, wzr
004e0cbc 080400f9 str      x8, [x0, #8]
004e0cc0 f5031f2a mov      w21, wzr
004e0cc4 18400091 add      x24, x0, #0x10
004e0cc8 28018052 mov      w8, #9
004e0ccc e9031d32 mov      w9, #8
004e0cd0 f9071d32 mov      w25, #0x18
004e0cd4 e8020034 cbz      w8, #0x4e0d30
004e0cd8 f6031f2a mov      w22, wzr
004e0cdc e00314aa mov      x0, x20
004e0ce0 e103162a mov      w1, w22
004e0ce4 e203152a mov      w2, w21
004e0ce8 f6f6ff97 bl       #0x4de8c0
004e0cec 800100b4 cbz      x0, #0x4e0d1c
004e0cf0 e802160b add      w8, w23, w22
004e0cf4 094d399b smaddl   x9, w8, w25, x19
004e0cf8 29410091 add      x9, x9, #0x10
004e0cfc 1f210171 cmp      w8, #0x48
004e0d00 2831989a csel     x8, x9, x24, lo
004e0d04 09004079 ldrh     w9, [x0]
004e0d08 e00308aa mov      x0, x8
004e0d0c e103162a mov      w1, w22
004e0d10 e203152a mov      w2, w21
004e0d14 09110079 strh     w9, [x8, #8]
004e0d18 3ef6ff97 bl       #0x4de610
004e0d1c 680a40b9 ldr      w8, [x19, #8]
004e0d20 d6060011 add      w22, w22, #1
004e0d24 df02086b cmp      w22, w8
004e0d28 a3fdff54 b.lo     #0x4e0cdc
004e0d2c 690e40b9 ldr      w9, [x19, #0xc]
004e0d30 b5060011 add      w21, w21, #1
004e0d34 f7260011 add      w23, w23, #9
004e0d38 bf02096b cmp      w21, w9
004e0d3c c3fcff54 b.lo     #0x4e0cd4
004e0d40 7fd206b9 str      wzr, [x19, #0x6d0]
004e0d44 fd7b44a9 ldp      x29, x30, [sp, #0x40]
004e0d48 f44f43a9 ldp      x20, x19, [sp, #0x30]
004e0d4c f65742a9 ldp      x22, x21, [sp, #0x20]
004e0d50 f85f41a9 ldp      x24, x23, [sp, #0x10]
004e0d54 f90745f8 ldr      x25, [sp], #0x50
004e0d58 c0035fd6 ret

; part_record_getter ELF 0x4e0d60 size=32 sha256=181bb23812eef93ee8fe12679c082fdfae286dc7db94bca2491cbb9b41187748
004e0d60 480c020b add      w8, w2, w2, lsl #3
004e0d64 0801010b add      w8, w8, w1
004e0d68 09400091 add      x9, x0, #0x10
004e0d6c ea071d32 mov      w10, #0x18
004e0d70 0a252a9b smaddl   x10, w8, w10, x9
004e0d74 1f210171 cmp      w8, #0x48
004e0d78 4031899a csel     x0, x10, x9, lo
004e0d7c c0035fd6 ret

; part_grid_bounds_check ELF 0x4e0d80 size=40 sha256=f00c9f2c847cf6ab48ac14d67c9a5a0dc8af2c58b992186f13a48b85ce1e7550
004e0d80 080840b9 ldr      w8, [x0, #8]
004e0d84 1f01016b cmp      w8, w1
004e0d88 83000054 b.lo     #0x4e0d98
004e0d8c 080c40b9 ldr      w8, [x0, #0xc]
004e0d90 1f01026b cmp      w8, w2
004e0d94 62000054 b.hs     #0x4e0da0
004e0d98 e0031f2a mov      w0, wzr
004e0d9c c0035fd6 ret
004e0da0 e0030032 mov      w0, #1
004e0da4 c0035fd6 ret

; coast_part_instance_loop ELF 0x4dd4d0 size=428 sha256=3089b821d3b940ade66f1d8d55385367071909b47d8293149050ea14898c6170
004dd4d0 ff4306d1 sub      sp, sp, #0x190
004dd4d4 ec8300fd str      d12, [sp, #0x100]
004dd4d8 eb2b116d stp      d11, d10, [sp, #0x110]
004dd4dc e923126d stp      d9, d8, [sp, #0x120]
004dd4e0 fc6f13a9 stp      x28, x27, [sp, #0x130]
004dd4e4 fa6714a9 stp      x26, x25, [sp, #0x140]
004dd4e8 f85f15a9 stp      x24, x23, [sp, #0x150]
004dd4ec f65716a9 stp      x22, x21, [sp, #0x160]
004dd4f0 f44f17a9 stp      x20, x19, [sp, #0x170]
004dd4f4 fd7b18a9 stp      x29, x30, [sp, #0x180]
004dd4f8 fd030691 add      x29, sp, #0x180
004dd4fc 287001b0 adrp     x8, #0x32e2000
004dd500 08a944f9 ldr      x8, [x8, #0x950]
004dd504 080140bd ldr      s8, [x8]
004dd508 287001b0 adrp     x8, #0x32e2000
004dd50c 08ad44f9 ldr      x8, [x8, #0x958]
004dd510 0a0140bd ldr      s10, [x8]
004dd514 287001b0 adrp     x8, #0x32e2000
004dd518 00102c1e fmov     s0, #0.50000000
004dd51c 0909201e fmul     s9, s8, s0
004dd520 4b09201e fmul     s11, s10, s0
004dd524 089944f9 ldr      x8, [x8, #0x930]
004dd528 996f01f0 adrp     x25, #0x32d0000
004dd52c 9b6f01f0 adrp     x27, #0x32d0000
004dd530 180140b9 ldr      w24, [x8]
004dd534 395b43f9 ldr      x25, [x25, #0x6b0]
004dd538 7bf346f9 ldr      x27, [x27, #0xde0]
004dd53c f303022a mov      w19, w2
004dd540 f40301aa mov      x20, x1
004dd544 f5031faa mov      x21, xzr
004dd548 1a200091 add      x26, x0, #8
004dd54c a002221e scvtf    s0, w21
004dd550 4009201e fmul     s0, s10, s0
004dd554 0c282b1e fadd     s12, s0, s11
004dd558 f6031faa mov      x22, xzr
004dd55c e00314aa mov      x0, x20
004dd560 e103162a mov      w1, w22
004dd564 e203152a mov      w2, w21
004dd568 060e0094 bl       #0x4e0d80
004dd56c 40060036 tbz      w0, #0, #0x4dd634
004dd570 e00314aa mov      x0, x20
004dd574 e103162a mov      w1, w22
004dd578 e203152a mov      w2, w21
004dd57c f90d0094 bl       #0x4e0d60
004dd580 17104079 ldrh     w23, [x0, #8]
004dd584 97050034 cbz      w23, #0x4dd634
004dd588 c002221e scvtf    s0, w22
004dd58c 0009201e fmul     s0, s8, s0
004dd590 0028291e fadd     s0, s0, s9
004dd594 280340f9 ldr      x8, [x25]
004dd598 a0a302d1 sub      x0, x29, #0xa8
004dd59c e103172a mov      w1, w23
004dd5a0 a88316f8 stur     x8, [x29, #-0x98]
004dd5a4 a08316bc stur     s0, [x29, #-0x98]
004dd5a8 ac0317bc stur     s12, [x29, #-0x90]
004dd5ac 91d10194 bl       #0x551bf0
004dd5b0 e0030091 mov      x0, sp
004dd5b4 475ded97 bl       #0x34ad0
004dd5b8 e0030091 mov      x0, sp
004dd5bc a16302d1 sub      x1, x29, #0x98
004dd5c0 f80700b9 str      w24, [sp, #4]
004dd5c4 e75ded97 bl       #0x34d60
004dd5c8 e0030091 mov      x0, sp
004dd5cc e1031f2a mov      w1, wzr
004dd5d0 e203172a mov      w2, w23
004dd5d4 f35ded97 bl       #0x34da0
004dd5d8 e0030091 mov      x0, sp
004dd5dc e1030032 mov      w1, #1
004dd5e0 e203132a mov      w2, w19
004dd5e4 ef5ded97 bl       #0x34da0
004dd5e8 a0a302d1 sub      x0, x29, #0xa8
004dd5ec cdd10194 bl       #0x551d20
004dd5f0 80000036 tbz      w0, #0, #0x4dd600
004dd5f4 e0030091 mov      x0, sp
004dd5f8 e1031f2a mov      w1, wzr
004dd5fc 03000014 b        #0x4dd608
004dd600 e0030091 mov      x0, sp
004dd604 e1031f32 mov      w1, #2
004dd608 2a5eed97 bl       #0x34eb0
004dd60c 600340f9 ldr      x0, [x27]
004dd610 e20340b9 ldr      w2, [sp]
004dd614 e1030091 mov      x1, sp
004dd618 e3031f2a mov      w3, wzr
004dd61c b5aeed97 bl       #0x490f0
004dd620 407b36b8 str      w0, [x26, x22, lsl #2]
004dd624 e0030091 mov      x0, sp
004dd628 3e5eed97 bl       #0x34f20
004dd62c a0a302d1 sub      x0, x29, #0xa8
004dd630 84d10194 bl       #0x551c40
004dd634 d6060091 add      x22, x22, #1
004dd638 df2600f1 cmp      x22, #9
004dd63c 01f9ff54 b.ne     #0x4dd55c
004dd640 b5060091 add      x21, x21, #1
004dd644 5a930091 add      x26, x26, #0x24
004dd648 bf2200f1 cmp      x21, #8
004dd64c 01f8ff54 b.ne     #0x4dd54c
004dd650 e923526d ldp      d9, d8, [sp, #0x120]
004dd654 ec8340fd ldr      d12, [sp, #0x100]
004dd658 eb2b516d ldp      d11, d10, [sp, #0x110]
004dd65c fd7b58a9 ldp      x29, x30, [sp, #0x180]
004dd660 f44f57a9 ldp      x20, x19, [sp, #0x170]
004dd664 f65756a9 ldp      x22, x21, [sp, #0x160]
004dd668 f85f55a9 ldp      x24, x23, [sp, #0x150]
004dd66c fa6754a9 ldp      x26, x25, [sp, #0x140]
004dd670 fc6f53a9 ldp      x28, x27, [sp, #0x130]
004dd674 ff430691 add      sp, sp, #0x190
004dd678 c0035fd6 ret

; part_unique_id_lookup ELF 0x551bf0 size=72 sha256=aec82bd71035bcc01ab002bf45b8dad017d78127517588ea2a82a54102b5ac30
00551bf0 896c01f0 adrp     x9, #0x32e4000
00551bf4 296943f9 ldr      x9, [x9, #0x6d0]
00551bf8 29410091 add      x9, x9, #0x10
00551bfc 097c00a9 stp      x9, xzr, [x0]
00551c00 096c0190 adrp     x9, #0x32d1000
00551c04 29d545f9 ldr      x9, [x9, #0xba8]
00551c08 290140f9 ldr      x9, [x9]
00551c0c 2ba15679 ldrh     w11, [x9, #0xb50]
00551c10 2a3c0012 and      w10, w1, #0xffff
00551c14 4a010b4b sub      w10, w10, w11
00551c18 2b314bb9 ldr      w11, [x9, #0xb30]
00551c1c e8031faa mov      x8, xzr
00551c20 5f010b6b cmp      w10, w11
00551c24 62000054 b.hs     #0x551c30
00551c28 289d45f9 ldr      x8, [x9, #0xb38]
00551c2c 08d96af8 ldr      x8, [x8, w10, sxtw #3]
00551c30 080400f9 str      x8, [x0, #8]
00551c34 c0035fd6 ret

; outside_sea_kind_check ELF 0x551d20 size=76 sha256=c0527fd969b15251f74651be1bf6f7b23a140969cf14074232562e79e63908c8
00551d20 000440f9 ldr      x0, [x0, #8]
00551d24 200200b4 cbz      x0, #0x551d68
00551d28 fd7bbfa9 stp      x29, x30, [sp, #-0x10]!
00551d2c fd030091 mov      x29, sp
00551d30 5c504494 bl       #0x1665ea0
00551d34 886c01b0 adrp     x8, #0x32e2000
00551d38 08c144f9 ldr      x8, [x8, #0x980]
00551d3c 090140b9 ldr      w9, [x8]
00551d40 1f00096b cmp      w0, w9
00551d44 fd7bc1a8 ldp      x29, x30, [sp], #0x10
00551d48 a2000054 b.hs     #0x551d5c
00551d4c 080540f9 ldr      x8, [x8, #8]
00551d50 08d96078 ldrh     w8, [x8, w0, sxtw #1]
00551d54 1f6d0071 cmp      w8, #0x1b
00551d58 49000054 b.ls     #0x551d60
00551d5c e8031f2a mov      w8, wzr
00551d60 1f610071 cmp      w8, #0x18
00551d64 e0179f1a cset     w0, eq
00551d68 c0035fd6 ret
