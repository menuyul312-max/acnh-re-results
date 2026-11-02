001fd540 e00301aa mov      x0, x1
001fd544 a2020034 cbz      w2, #0x1fd598
001fd548 e929b2d2 mov      x9, #0x914f0000
001fd54c 487c4093 sxtw     x8, w2
001fd550 6b969252 mov      w11, #0x94b3
001fd554 cbdaa472 movk     w11, #0x26d6, lsl #16
001fd558 89d2c9f2 movk     x9, #0x4e94, lsl #32
001fd55c 087d099b mul      x8, x8, x9
001fd560 093d7092 and      x9, x8, #0xffff0000
001fd564 0afd6093 asr      x10, x8, #0x20
001fd568 08fc488b add      x8, x0, x8, lsr #63
001fd56c 4c7d0b9b mul      x12, x10, x11
001fd570 2b7d0b9b mul      x11, x9, x11
001fd574 8b814b8b add      x11, x12, x11, lsr #32
001fd578 0c7d8152 mov      w12, #0xbe8
001fd57c cc25a272 movk     w12, #0x112e, lsl #16
001fd580 4a7d0c9b mul      x10, x10, x12
001fd584 297d0c9b mul      x9, x9, x12
001fd588 29412b8b add      x9, x9, w11, uxtw
001fd58c 4a818b8b add      x10, x10, x11, asr #32
001fd590 4981498b add      x9, x10, x9, lsr #32
001fd594 0069898b add      x0, x8, x9, asr #26
001fd598 c0035fd6 ret      
001fd59c 00000000 udf      #0
001fd5a0 e00301aa mov      x0, x1
001fd5a4 69969252 mov      w9, #0x94b3
001fd5a8 c9daa472 movk     w9, #0x26d6, lsl #16
001fd5ac 087d8152 mov      w8, #0xbe8
001fd5b0 c825a272 movk     w8, #0x112e, lsl #16
001fd5b4 42020034 cbz      w2, #0x1fd5fc
001fd5b8 0b0094d2 mov      x11, #0xa000
001fd5bc 0b17a6f2 movk     x11, #0x30b8, lsl #16
001fd5c0 4a7c4093 sxtw     x10, w2
001fd5c4 cb68c0f2 movk     x11, #0x346, lsl #32
001fd5c8 4a7d0b9b mul      x10, x10, x11
001fd5cc 4b497392 and      x11, x10, #0xffffe000
