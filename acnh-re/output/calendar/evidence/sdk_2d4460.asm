002d4460 09088039 ldrsb    x9, [x0, #2]
002d4464 6a559552 mov      w10, #0xaaab
002d4468 4a55a572 movk     w10, #0x2aaa, lsl #16
002d446c 2a7d0a9b mul      x10, x9, x10
002d4470 4bfd7fd3 lsr      x11, x10, #0x3f
002d4474 4afd6193 asr      x10, x10, #0x21
002d4478 4a010b0b add      w10, w10, w11
002d447c eb071e32 mov      w11, #0xc
002d4480 0800c079 ldrsh    w8, [x0]
002d4484 4801080b add      w8, w10, w8
002d4488 49a50b1b msub     w9, w10, w11, w9
002d448c 3f010071 cmp      w9, #0
002d4490 ea179f1a cset     w10, eq
002d4494 6e01891a csel     w14, w11, w9, eq
002d4498 b13a0090 adrp     x17, #0xa28000
002d449c 31523791 add      x17, x17, #0xdd4
002d44a0 08010a4b sub      w8, w8, w10
002d44a4 31ca2e8b add      x17, x17, w14, sxtw #2
002d44a8 0a0d0011 add      w10, w8, #3
002d44ac 1f010071 cmp      w8, #0
002d44b0 0d0cc039 ldrsb    w13, [x0, #3]
002d44b4 31c25fb8 ldur     w17, [x17, #-4]
002d44b8 4fb1881a csel     w15, w10, w8, lt
002d44bc 2a5c8f52 mov      w10, #0x7ae1
002d44c0 8ac2b572 movk     w10, #0xae14, lsl #16
002d44c4 0a7d2a9b smull    x10, w8, w10
002d44c8 a92d8052 mov      w9, #0x16d
002d44cc df090071 cmp      w14, #2
002d44d0 4bfd7fd3 lsr      x11, x10, #0x3f
002d44d4 4afd6593 asr      x10, x10, #0x25
002d44d8 ad01110b add      w13, w13, w17
002d44dc 50010b0b add      w16, w10, w11
002d44e0 eaa39052 mov      w10, #0x851f
002d44e4 6a3daa72 movk     w10, #0x51eb, lsl #16
002d44e8 0935091b madd     w9, w8, w9, w13
002d44ec 0b7d2a9b smull    x11, w8, w10
002d44f0 2901100b add      w9, w9, w16
002d44f4 6afd7fd3 lsr      x10, x11, #0x3f
002d44f8 6cfd6793 asr      x12, x11, #0x27
002d44fc 29098f0b add      w9, w9, w15, asr #2
002d4500 8c010a0b add      w12, w12, w10
002d4504 29010c0b add      w9, w9, w12
002d4508 29b50551 sub      w9, w9, #0x16d
002d450c ac010054 b.gt     #0x2d4540
002d4510 0d328052 mov      w13, #0x190
002d4514 8ca10d1b msub     w12, w12, w13, w8
002d4518 2c010034 cbz      w12, #0x2d453c
002d451c 6bfd6593 asr      x11, x11, #0x25
002d4520 6a010a0b add      w10, w11, w10
002d4524 8b0c8052 mov      w11, #0x64
002d4528 4aa10b1b msub     w10, w10, w11, w8
002d452c 08050012 and      w8, w8, #3
002d4530 5f010071 cmp      w10, #0
002d4534 0019407a ccmp     w8, #0, #0, ne
002d4538 41000054 b.ne     #0x2d4540
002d453c 29050051 sub      w9, w9, #1
002d4540 28050051 sub      w8, w9, #1
002d4544 09108039 ldrsb    x9, [x0, #4]
002d4548 0a148039 ldrsb    x10, [x0, #5]
002d454c ec071d32 mov      w12, #0x18
002d4550 08252c9b smaddl   x8, w8, w12, x9
002d4554 e90f1e32 mov      w9, #0x3c
002d4558 0829099b madd     x8, x8, x9, x10
002d455c 0b188039 ldrsb    x11, [x0, #6]
002d4560 082d099b madd     x8, x8, x9, x11
002d4564 e9df9e92 mov      x9, #-0xf700
002d4568 c90db1f2 movk     x9, #0x886e, lsl #16
002d456c 29fedff2 movk     x9, #0xfff1, lsl #32
002d4570 0001098b add      x0, x8, x9
002d4574 c0035fd6 ret      
002d4578 00000000 udf      #0
002d457c 00000000 udf      #0
