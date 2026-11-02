004d5e50 f657bda9 stp      x22, x21, [sp, #-0x30]!
004d5e54 f44f01a9 stp      x20, x19, [sp, #0x10]
004d5e58 fd7b02a9 stp      x29, x30, [sp, #0x20]
004d5e5c fd830091 add      x29, sp, #0x20
004d5e60 f30300aa mov      x19, x0
004d5e64 15200091 add      x21, x0, #8
004d5e68 00304039 ldrb     w0, [x0, #0xc]
004d5e6c 21104039 ldrb     w1, [x1, #4]
004d5e70 f40308aa mov      x20, x8
004d5e74 7fdcff97 bl       #0x4cd070
004d5e78 f603002a mov      w22, w0
004d5e7c e00314aa mov      x0, x20
004d5e80 840a2a94 bl       #0xf58890
004d5e84 610a40f9 ldr      x1, [x19, #0x10]
004d5e88 e00315aa mov      x0, x21
004d5e8c a5d7ff97 bl       #0x4cbd20
004d5e90 007c4092 and      x0, x0, #0xffffffff
004d5e94 c11e0012 and      w1, w22, #0xff
004d5e98 e2031f32 mov      w2, #2
004d5e9c 8dd9ff97 bl       #0x4cc4d0
004d5ea0 80020079 strh     w0, [x20]
004d5ea4 96120039 strb     w22, [x20, #4]
004d5ea8 fd7b42a9 ldp      x29, x30, [sp, #0x20]
004d5eac f44f41a9 ldp      x20, x19, [sp, #0x10]
004d5eb0 f657c3a8 ldp      x22, x21, [sp], #0x30
004d5eb4 c0035fd6 ret      
004d5eb8 00000000 udf      #0
004d5ebc 00000000 udf      #0
004d5ec0 f44fbea9 stp      x20, x19, [sp, #-0x20]!
004d5ec4 fd7b01a9 stp      x29, x30, [sp, #0x10]
004d5ec8 fd430091 add      x29, sp, #0x10
004d5ecc f30300aa mov      x19, x0
004d5ed0 e00308aa mov      x0, x8
004d5ed4 f40308aa mov      x20, x8
004d5ed8 6e0a2a94 bl       #0xf58890
004d5edc 60220091 add      x0, x19, #8
004d5ee0 ec0a2a94 bl       #0xf58a90
004d5ee4 03e2ff97 bl       #0x4ce6f0
004d5ee8 80020079 strh     w0, [x20]
004d5eec 680e40b9 ldr      w8, [x19, #0xc]
004d5ef0 88120039 strb     w8, [x20, #4]
004d5ef4 fd7b41a9 ldp      x29, x30, [sp, #0x10]
004d5ef8 f44fc2a8 ldp      x20, x19, [sp], #0x20
004d5efc c0035fd6 ret      
