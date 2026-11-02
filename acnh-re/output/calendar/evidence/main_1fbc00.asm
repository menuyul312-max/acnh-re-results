001fbc00 ffc300d1 sub      sp, sp, #0x30
001fbc04 f44f01a9 stp      x20, x19, [sp, #0x10]
001fbc08 fd7b02a9 stp      x29, x30, [sp, #0x20]
001fbc0c fd830091 add      x29, sp, #0x20
001fbc10 0810c039 ldrsb    w8, [x0, #4]
001fbc14 f30300aa mov      x19, x0
001fbc18 1f110071 cmp      w8, #4
001fbc1c cc010054 b.gt     #0x1fbc54
001fbc20 a88601d0 adrp     x8, #0x32d1000
001fbc24 086946f9 ldr      x8, [x8, #0xcd0]
001fbc28 140140f9 ldr      x20, [x8]
001fbc2c e00313aa mov      x0, x19
001fbc30 d44a8094 bl       #0x220e780
001fbc34 e10300aa mov      x1, x0
001fbc38 02008012 mov      w2, #-1
001fbc3c e00314aa mov      x0, x20
001fbc40 40060094 bl       #0x1fd540
001fbc44 e00700f9 str      x0, [sp, #8]
001fbc48 e0230091 add      x0, sp, #8
001fbc4c d14a8094 bl       #0x220e790
001fbc50 600200f9 str      x0, [x19]
001fbc54 a8008052 mov      w8, #5
001fbc58 680a0079 strh     w8, [x19, #4]
001fbc5c 7f1a0039 strb     wzr, [x19, #6]
001fbc60 fd7b42a9 ldp      x29, x30, [sp, #0x20]
001fbc64 f44f41a9 ldp      x20, x19, [sp, #0x10]
001fbc68 ffc30091 add      sp, sp, #0x30
001fbc6c c0035fd6 ret      
