0016a43c e00319aa mov      x0, x25
0016a440 a8050094 bl       #0x16bae0
0016a444 e20300aa mov      x2, x0
0016a448 e0030491 add      x0, sp, #0x100
0016a44c e13e0190 adrp     x1, #0x2946000
0016a450 215c0e91 add      x1, x1, #0x397
0016a454 37a1fa97 bl       #0x12930
0016a458 69ba45f9 ldr      x9, [x19, #0xb70]
0016a45c 0a098052 mov      w10, #0x48
0016a460 686a4bb9 ldr      w8, [x19, #0xb68]
0016a464 238b01d0 adrp     x3, #0x32d0000
0016a468 e01b40f9 ldr      x0, [sp, #0x30]
0016a46c e2030491 add      x2, sp, #0x100
0016a470 63d443f9 ldr      x3, [x3, #0x7a8]
0016a474 aa260a9b madd     x10, x21, x10, x9
0016a478 bf0208eb cmp      x21, x8
0016a47c 4131899a csel     x1, x10, x9, lo
0016a480 d07dfd97 bl       #0xc9bc0
0016a484 acffff17 b        #0x16a334
