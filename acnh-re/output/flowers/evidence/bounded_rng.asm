00f53420 f30f1ef8 str      x19, [sp, #-0x20]!
00f53424 fd7b01a9 stp      x29, x30, [sp, #0x10]
00f53428 fd430091 add      x29, sp, #0x10
00f5342c f303002a mov      w19, w0
00f53430 a03401d0 adrp     x0, #0x35e9000
00f53434 00401491 add      x0, x0, #0x510
00f53438 2a5b2994 bl       #0x19aa0e0
00f5343c 087cb39b umull    x8, w0, w19
00f53440 fd7b41a9 ldp      x29, x30, [sp, #0x10]
00f53444 00fd60d3 lsr      x0, x8, #0x20
00f53448 f30742f8 ldr      x19, [sp], #0x20
00f5344c c0035fd6 ret      
