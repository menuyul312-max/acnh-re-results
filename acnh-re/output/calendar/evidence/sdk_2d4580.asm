002d4580 120040f9 ldr      x18, [x0]
002d4584 ea2a85d2 mov      x10, #0x2957
002d4588 2acab9f2 movk     x10, #0xce51, lsl #16
002d458c 0a14d9f2 movk     x10, #0xc8a0, lsl #32
002d4590 aa08e3f2 movk     x10, #0x1845, lsl #48
002d4594 4a7e4a9b smulh    x10, x18, x10
002d4598 e95689d2 mov      x9, #0x4ab7
002d459c 2951aef2 movk     x9, #0x7289, lsl #16
002d45a0 5f0200f1 cmp      x18, #0
002d45a4 c9a0c8f2 movk     x9, #0x4506, lsl #32
002d45a8 c945f8f2 movk     x9, #0xc22e, lsl #48
002d45ac 8b4d9f52 mov      w11, #0xfa6c
002d45b0 4b01a072 movk     w11, #0xa, lsl #16
002d45b4 acd78052 mov      w12, #0x6bd
002d45b8 6c2da772 movk     w12, #0x396b, lsl #16
002d45bc 405692da cneg     x0, x18, mi
002d45c0 097cc99b umulh    x9, x0, x9
002d45c4 08308a52 mov      w8, #0x5180
002d45c8 2800a072 movk     w8, #1, lsl #16
002d45cc 2d568752 mov      w13, #0x3ab1
002d45d0 4d00a072 movk     w13, #2, lsl #16
002d45d4 5f0200f1 cmp      x18, #0
002d45d8 6e3f9052 mov      w14, #0x81fb
002d45dc 8eb5bc72 movk     w14, #0xe5ac, lsl #16
002d45e0 6f0e9652 mov      w15, #0xb073
002d45e4 afcda272 movk     w15, #0x166d, lsl #16
002d45e8 02aa9852 mov      w2, #0xc550
002d45ec a2ffbf72 movk     w2, #0xfffd, lsl #16
002d45f0 f0031f32 mov      w16, #2
002d45f4 f1e70132 mov      w17, #-0x66666667
002d45f8 41fd7fd3 lsr      x1, x10, #0x3f
002d45fc 4afd4dd3 lsr      x10, x10, #0xd
002d4600 4a01010b add      w10, w10, w1
002d4604 4a010b0b add      w10, w10, w11
002d4608 4b7d2c9b smull    x11, w10, w12
002d460c 29fd50d3 lsr      x9, x9, #0x10
002d4610 2981089b msub     x9, x9, x8, x0
002d4614 80d59152 mov      w0, #0x8eac
002d4618 6cfd60d3 lsr      x12, x11, #0x20
002d461c 6bfd7fd3 lsr      x11, x11, #0x3f
002d4620 6b3d8c0b add      w11, w11, w12, asr #15
002d4624 29a589da cneg     x9, x9, lt
002d4628 6aa90d1b msub     w10, w11, w13, w10
002d462c 4c010d0b add      w12, w10, w13
002d4630 5f010071 cmp      w10, #0
002d4634 8cb18a1a csel     w12, w12, w10, lt
002d4638 6a7d8a0b add      w10, w11, w10, asr #31
002d463c 8d7d2e9b smull    x13, w12, w14
002d4640 adfd60d3 lsr      x13, x13, #0x20
002d4644 ad010c0b add      w13, w13, w12
002d4648 ae7d0f13 asr      w14, w13, #0xf
002d464c d27d4d0b add      w18, w14, w13, lsr #31
002d4650 0e328052 mov      w14, #0x190
002d4654 8d0c8052 mov      w13, #0x64
002d4658 4a7d0e1b mul      w10, w10, w14
002d465c 41b2001b msub     w1, w18, w0, w12
002d4660 8c01020b add      w12, w12, w2
002d4664 2b7c2f9b smull    x11, w1, w15
002d4668 6ffd60d3 lsr      x15, x11, #0x20
002d466c 6bfd7fd3 lsr      x11, x11, #0x3f
002d4670 6b1d8f0b add      w11, w11, w15, asr #7
002d4674 afb68052 mov      w15, #0x5b5
002d4678 6f850f1b msub     w15, w11, w15, w1
002d467c 4a2a0d1b madd     w10, w18, w13, w10
002d4680 32369f52 mov      w18, #0xf9b1
002d4684 9271b672 movk     w18, #0xb38c, lsl #16
002d4688 f27d329b smull    x18, w15, w18
002d468c e2d11651 sub      w2, w15, #0x5b4
002d4690 5fb40571 cmp      w2, #0x16d
002d4694 e2279f1a cset     w2, lo
002d4698 9f01006b cmp      w12, w0
002d469c 4cfe60d3 lsr      x12, x18, #0x20
002d46a0 8c010f0b add      w12, w12, w15
002d46a4 927d0813 asr      w18, w12, #8
002d46a8 527e4c0b add      w18, w18, w12, lsr #31
002d46ac ac2d8052 mov      w12, #0x16d
002d46b0 4cbe0c1b msub     w12, w18, w12, w15
002d46b4 8f090c0b add      w15, w12, w12, lsl #2
002d46b8 e11a9052 mov      w1, #0x80d7
002d46bc 61c5ba72 movk     w1, #0xd62b, lsl #16
002d46c0 4a090b0b add      w10, w10, w11, lsl #2
002d46c4 4a01120b add      w10, w10, w18
002d46c8 eb7b1c32 mov      w11, #-9
002d46cc ef090011 add      w15, w15, #2
002d46d0 e07d219b smull    x0, w15, w1
002d46d4 a1038052 mov      w1, #0x1d
002d46d8 00fc60d3 lsr      x0, x0, #0x20
002d46dc 0f000f0b add      w15, w0, w15
002d46e0 e07d0713 asr      w0, w15, #7
002d46e4 0f7c4f0b add      w15, w0, w15, lsr #31
002d46e8 20138052 mov      w0, #0x99
002d46ec f041001b madd     w16, w15, w0, w16
002d46f0 107e319b smull    x16, w16, w17
002d46f4 e0279f1a cset     w0, lo
002d46f8 0000022a orr      w0, w0, w2
002d46fc 62018052 mov      w2, #0xb
