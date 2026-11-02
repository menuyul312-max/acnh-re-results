004cd310 ff0302d1 sub      sp, sp, #0x80
004cd314 fc6f02a9 stp      x28, x27, [sp, #0x20]
004cd318 fa6703a9 stp      x26, x25, [sp, #0x30]
004cd31c f85f04a9 stp      x24, x23, [sp, #0x40]
004cd320 f65705a9 stp      x22, x21, [sp, #0x50]
004cd324 f44f06a9 stp      x20, x19, [sp, #0x60]
004cd328 fd7b07a9 stp      x29, x30, [sp, #0x70]
004cd32c fdc30191 add      x29, sp, #0x70
004cd330 bb7001b0 adrp     x27, #0x32e2000
004cd334 7b2743f9 ldr      x27, [x27, #0x648]
004cd338 f303002a mov      w19, w0
004cd33c 600340f9 ldr      x0, [x27]
004cd340 e02300b4 cbz      x0, #0x4cd7bc
004cd344 cb644694 bl       #0x1666670
004cd348 a02300b4 cbz      x0, #0x4cd7bc
004cd34c 680340f9 ldr      x8, [x27]
004cd350 00010891 add      x0, x8, #0x200
004cd354 c7644694 bl       #0x1666670
004cd358 202300b4 cbz      x0, #0x4cd7bc
004cd35c e003132a mov      w0, w19
004cd360 d0030094 bl       #0x4ce2a0
004cd364 e83b1f32 mov      w8, #0xfffe
004cd368 1f00086b cmp      w0, w8
004cd36c 60220054 b.eq     #0x4cd7b8
004cd370 680340f9 ldr      x8, [x27]
004cd374 0af14379 ldrh     w10, [x8, #0x1f8]
004cd378 093c0012 and      w9, w0, #0xffff
004cd37c 29010a4b sub      w9, w9, w10
004cd380 0ad941b9 ldr      w10, [x8, #0x1d8]
004cd384 f603002a mov      w22, w0
004cd388 3f010a6b cmp      w9, w10
004cd38c 62210054 b.hs     #0x4cd7b8
004cd390 08f140f9 ldr      x8, [x8, #0x1e0]
004cd394 13d969f8 ldr      x19, [x8, w9, sxtw #3]
004cd398 132100b4 cbz      x19, #0x4cd7b8
004cd39c e00313aa mov      x0, x19
004cd3a0 c0624694 bl       #0x1665ea0
004cd3a4 a87001b0 adrp     x8, #0x32e2000
004cd3a8 086543f9 ldr      x8, [x8, #0x6c8]
004cd3ac 090140b9 ldr      w9, [x8]
004cd3b0 1f00096b cmp      w0, w9
004cd3b4 a2000054 b.hs     #0x4cd3c8
004cd3b8 080540f9 ldr      x8, [x8, #8]
004cd3bc 08d96078 ldrh     w8, [x8, w0, sxtw #1]
004cd3c0 1f750071 cmp      w8, #0x1d
004cd3c4 49000054 b.ls     #0x4cd3cc
004cd3c8 e8031f2a mov      w8, wzr
004cd3cc e81f00b9 str      w8, [sp, #0x1c]
004cd3d0 680340f9 ldr      x8, [x27]
004cd3d4 17c143b9 ldr      w23, [x8, #0x3c0]
004cd3d8 ff020071 cmp      w23, #0
004cd3dc f30300f9 str      x19, [sp]
004cd3e0 ed1f0054 b.le     #0x4cd7dc
004cd3e4 08008012 mov      w8, #-1
004cd3e8 e80f00b9 str      w8, [sp, #0xc]
004cd3ec b97001b0 adrp     x25, #0x32e2000
004cd3f0 ba7001b0 adrp     x26, #0x32e2000
004cd3f4 396343f9 ldr      x25, [x25, #0x6c0]
004cd3f8 5a5343f9 ldr      x26, [x26, #0x6a0]
004cd3fc f8031f2a mov      w24, wzr
004cd400 bc6c8652 mov      w28, #0x3365
004cd404 5c1aa172 movk     w28, #0x8d2, lsl #16
004cd408 147e8752 mov      w20, #0x3bf0
004cd40c 7454ad72 movk     w20, #0x6aa3, lsl #16
004cd410 680340f9 ldr      x8, [x27]
004cd414 00010891 add      x0, x8, #0x200
004cd418 e103182a mov      w1, w24
004cd41c c1feff97 bl       #0x4ccf20
004cd420 c01600b4 cbz      x0, #0x4cd6f8
004cd424 f30300aa mov      x19, x0
004cd428 9e624694 bl       #0x1665ea0
004cd42c 280340b9 ldr      w8, [x25]
004cd430 1f00086b cmp      w0, w8
004cd434 a2000054 b.hs     #0x4cd448
004cd438 280740f9 ldr      x8, [x25, #8]
004cd43c 08d96078 ldrh     w8, [x8, w0, sxtw #1]
004cd440 1f750071 cmp      w8, #0x1d
004cd444 49000054 b.ls     #0x4cd44c
004cd448 e8031f2a mov      w8, wzr
004cd44c e81300b9 str      w8, [sp, #0x10]
004cd450 e81340b9 ldr      w8, [sp, #0x10]
004cd454 e91f40b9 ldr      w9, [sp, #0x1c]
004cd458 1f01096b cmp      w8, w9
004cd45c 41080054 b.ne     #0x4cd564
004cd460 680240b9 ldr      w8, [x19]
004cd464 a80b0034 cbz      w8, #0x4cd5d8
004cd468 48034039 ldrb     w8, [x26]
004cd46c c8050034 cbz      w8, #0x4cd524
004cd470 a87001b0 adrp     x8, #0x32e2000
004cd474 085543f9 ldr      x8, [x8, #0x6a8]
004cd478 080980b9 ldrsw    x8, [x8, #8]
004cd47c 0816f836 tbz      w8, #0x1f, #0x4cd73c
004cd480 1f050031 cmn      w8, #1
004cd484 81160054 b.ne     #0x4cd754
004cd488 e00313aa mov      x0, x19
004cd48c f5031aaa mov      x21, x26
004cd490 7c624694 bl       #0x1665e80
004cd494 e00500b4 cbz      x0, #0x4cd550
004cd498 fa0300aa mov      x26, x0
004cd49c 71624694 bl       #0x1665e60
004cd4a0 001400b4 cbz      x0, #0x4cd720
004cd4a4 f90300aa mov      x25, x0
004cd4a8 e0031aaa mov      x0, x26
004cd4ac 69624694 bl       #0x1665e50
004cd4b0 a87001b0 adrp     x8, #0x32e2000
004cd4b4 085543f9 ldr      x8, [x8, #0x6a8]
004cd4b8 e97b1f32 mov      w9, #-2
004cd4bc 090900b9 str      w9, [x8, #8]
004cd4c0 00130034 cbz      w0, #0x4cd720
004cd4c4 e8031f2a mov      w8, wzr
004cd4c8 29130091 add      x9, x25, #4
004cd4cc fa0315aa mov      x26, x21
004cd4d0 ea03082a mov      w10, w8
004cd4d4 4af17dd3 lsl      x10, x10, #3
004cd4d8 2a6b6ab8 ldr      w10, [x25, x10]
004cd4dc 5f01146b cmp      w10, w20
004cd4e0 c0000054 b.eq     #0x4cd4f8
004cd4e4 08050011 add      w8, w8, #1
004cd4e8 29210091 add      x9, x9, #8
004cd4ec 1f01006b cmp      w8, w0
004cd4f0 03ffff54 b.lo     #0x4cd4d0
004cd4f4 36000014 b        #0x4cd5cc
004cd4f8 280140b9 ldr      w8, [x9]
004cd4fc a97001b0 adrp     x9, #0x32e2000
004cd500 295543f9 ldr      x9, [x9, #0x6a8]
004cd504 1f050031 cmn      w8, #1
004cd508 e803881a csel     w8, wzr, w8, eq
004cd50c 280900b9 str      w8, [x9, #8]
004cd510 b97001b0 adrp     x25, #0x32e2000
004cd514 680240b9 ldr      w8, [x19]
004cd518 396343f9 ldr      x25, [x25, #0x6c0]
004cd51c 68faff35 cbnz     w8, #0x4cd468
004cd520 2e000014 b        #0x4cd5d8
004cd524 e8030032 mov      w8, #1
004cd528 48030039 strb     w8, [x26]
004cd52c a87001b0 adrp     x8, #0x32e2000
004cd530 085543f9 ldr      x8, [x8, #0x6a8]
004cd534 09008092 mov      x9, #-1
004cd538 092501a9 stp      x9, x9, [x8, #0x10]
004cd53c 092500a9 stp      x9, x9, [x8]
004cd540 e00313aa mov      x0, x19
004cd544 f5031aaa mov      x21, x26
004cd548 4e624694 bl       #0x1665e80
004cd54c 60faffb5 cbnz     x0, #0x4cd498
004cd550 e8031f2a mov      w8, wzr
004cd554 fa0315aa mov      x26, x21
004cd558 df02086b cmp      w22, w8
004cd55c 20040054 b.eq     #0x4cd5e0
004cd560 66000014 b        #0x4cd6f8
004cd564 e00313aa mov      x0, x19
004cd568 4e624694 bl       #0x1665ea0
004cd56c 280340b9 ldr      w8, [x25]
004cd570 1f00086b cmp      w0, w8
004cd574 a2000054 b.hs     #0x4cd588
004cd578 280740f9 ldr      x8, [x25, #8]
004cd57c 08d96078 ldrh     w8, [x8, w0, sxtw #1]
004cd580 1f750071 cmp      w8, #0x1d
004cd584 49000054 b.ls     #0x4cd58c
004cd588 e8031f2a mov      w8, wzr
004cd58c e81300b9 str      w8, [sp, #0x10]
004cd590 e81340b9 ldr      w8, [sp, #0x10]
004cd594 1f650071 cmp      w8, #0x19
004cd598 080c0054 b.hi     #0x4cd718
004cd59c e9030032 mov      w9, #1
004cd5a0 2921c81a lsl      w9, w9, w8
004cd5a4 8a7ba052 mov      w10, #0x3dc0000
004cd5a8 3f010a6a tst      w9, w10
004cd5ac e00a0054 b.eq     #0x4cd708
004cd5b0 68038052 mov      w8, #0x1b
004cd5b4 0803080b add      w8, w24, w8
004cd5b8 18050051 sub      w24, w8, #1
004cd5bc 18070011 add      w24, w24, #1
004cd5c0 1f03176b cmp      w24, w23
004cd5c4 6bf2ff54 b.lt     #0x4cd410
004cd5c8 8e000014 b        #0x4cd800
004cd5cc b97001b0 adrp     x25, #0x32e2000
004cd5d0 396343f9 ldr      x25, [x25, #0x6c0]
004cd5d4 e8031f2a mov      w8, wzr
004cd5d8 df02086b cmp      w22, w8
004cd5dc e1080054 b.ne     #0x4cd6f8
004cd5e0 680240b9 ldr      w8, [x19]
004cd5e4 88080034 cbz      w8, #0x4cd6f4
004cd5e8 48034039 ldrb     w8, [x26]
004cd5ec 88050034 cbz      w8, #0x4cd69c
004cd5f0 a97001b0 adrp     x9, #0x32e2000
004cd5f4 295543f9 ldr      x9, [x9, #0x6a8]
004cd5f8 291d80b9 ldrsw    x9, [x9, #0x1c]
004cd5fc 490bf836 tbz      w9, #0x1f, #0x4cd764
004cd600 3f050031 cmn      w9, #1
004cd604 c10b0054 b.ne     #0x4cd77c
004cd608 e00313aa mov      x0, x19
004cd60c 1d624694 bl       #0x1665e80
004cd610 a00500b4 cbz      x0, #0x4cd6c4
004cd614 f90300aa mov      x25, x0
004cd618 12624694 bl       #0x1665e60
004cd61c 400500b4 cbz      x0, #0x4cd6c4
004cd620 f50300aa mov      x21, x0
004cd624 e00319aa mov      x0, x25
004cd628 0a624694 bl       #0x1665e50
004cd62c a87001b0 adrp     x8, #0x32e2000
004cd630 085543f9 ldr      x8, [x8, #0x6a8]
004cd634 e97b1f32 mov      w9, #-2
004cd638 091d00b9 str      w9, [x8, #0x1c]
004cd63c 40040034 cbz      w0, #0x4cd6c4
004cd640 b97001b0 adrp     x25, #0x32e2000
004cd644 396343f9 ldr      x25, [x25, #0x6c0]
004cd648 e8031f2a mov      w8, wzr
004cd64c a9120091 add      x9, x21, #4
004cd650 ea03082a mov      w10, w8
004cd654 4af17dd3 lsl      x10, x10, #3
004cd658 aa6a6ab8 ldr      w10, [x21, x10]
004cd65c 5f011c6b cmp      w10, w28
004cd660 c0000054 b.eq     #0x4cd678
004cd664 08050011 add      w8, w8, #1
004cd668 29210091 add      x9, x9, #8
004cd66c 1f01006b cmp      w8, w0
004cd670 03ffff54 b.lo     #0x4cd650
004cd674 1b000014 b        #0x4cd6e0
004cd678 280140b9 ldr      w8, [x9]
004cd67c a97001b0 adrp     x9, #0x32e2000
004cd680 295543f9 ldr      x9, [x9, #0x6a8]
004cd684 1f050031 cmn      w8, #1
004cd688 e803881a csel     w8, wzr, w8, eq
004cd68c 281d00b9 str      w8, [x9, #0x1c]
004cd690 680240b9 ldr      w8, [x19]
004cd694 a8faff35 cbnz     w8, #0x4cd5e8
004cd698 3e000014 b        #0x4cd790
004cd69c e8030032 mov      w8, #1
004cd6a0 48030039 strb     w8, [x26]
004cd6a4 a87001b0 adrp     x8, #0x32e2000
004cd6a8 085543f9 ldr      x8, [x8, #0x6a8]
004cd6ac 09008092 mov      x9, #-1
004cd6b0 092501a9 stp      x9, x9, [x8, #0x10]
004cd6b4 092500a9 stp      x9, x9, [x8]
004cd6b8 e00313aa mov      x0, x19
004cd6bc f1614694 bl       #0x1665e80
004cd6c0 a0faffb5 cbnz     x0, #0x4cd614
004cd6c4 f80f00b9 str      w24, [sp, #0xc]
004cd6c8 b97001b0 adrp     x25, #0x32e2000
004cd6cc 396343f9 ldr      x25, [x25, #0x6c0]
004cd6d0 18070011 add      w24, w24, #1
004cd6d4 1f03176b cmp      w24, w23
004cd6d8 cbe9ff54 b.lt     #0x4cd410
004cd6dc 49000014 b        #0x4cd800
004cd6e0 f80f00b9 str      w24, [sp, #0xc]
004cd6e4 18070011 add      w24, w24, #1
004cd6e8 1f03176b cmp      w24, w23
004cd6ec 2be9ff54 b.lt     #0x4cd410
004cd6f0 44000014 b        #0x4cd800
004cd6f4 f80f00b9 str      w24, [sp, #0xc]
004cd6f8 18070011 add      w24, w24, #1
004cd6fc 1f03176b cmp      w24, w23
004cd700 8be8ff54 b.lt     #0x4cd410
004cd704 3f000014 b        #0x4cd800
004cd708 1f550071 cmp      w8, #0x15
004cd70c 61000054 b.ne     #0x4cd718
004cd710 280a8052 mov      w8, #0x51
004cd714 a8ffff17 b        #0x4cd5b4
004cd718 e8031f2a mov      w8, wzr
004cd71c a6ffff17 b        #0x4cd5b4
004cd720 b97001b0 adrp     x25, #0x32e2000
004cd724 396343f9 ldr      x25, [x25, #0x6c0]
004cd728 e8031f2a mov      w8, wzr
004cd72c fa0315aa mov      x26, x21
004cd730 df02086b cmp      w22, w8
004cd734 60f5ff54 b.eq     #0x4cd5e0
004cd738 f0ffff17 b        #0x4cd6f8
004cd73c 080113ab adds     x8, x8, x19
004cd740 c0f4ff54 b.eq     #0x4cd5d8
004cd744 08014079 ldrh     w8, [x8]
004cd748 df02086b cmp      w22, w8
004cd74c a0f4ff54 b.eq     #0x4cd5e0
004cd750 eaffff17 b        #0x4cd6f8
004cd754 e8031f2a mov      w8, wzr
004cd758 df02086b cmp      w22, w8
004cd75c 20f4ff54 b.eq     #0x4cd5e0
004cd760 e6ffff17 b        #0x4cd6f8
004cd764 290113ab adds     x9, x9, x19
004cd768 e0010054 b.eq     #0x4cd7a4
004cd76c 29014039 ldrb     w9, [x9]
004cd770 f80f00b9 str      w24, [sp, #0xc]
004cd774 29fcff34 cbz      w9, #0x4cd6f8
004cd778 a0010014 b        #0x4cddf8
004cd77c f80f00b9 str      w24, [sp, #0xc]
004cd780 18070011 add      w24, w24, #1
004cd784 1f03176b cmp      w24, w23
004cd788 4be4ff54 b.lt     #0x4cd410
004cd78c 1d000014 b        #0x4cd800
004cd790 f80f00b9 str      w24, [sp, #0xc]
004cd794 18070011 add      w24, w24, #1
004cd798 1f03176b cmp      w24, w23
004cd79c abe3ff54 b.lt     #0x4cd410
004cd7a0 18000014 b        #0x4cd800
004cd7a4 f80f00b9 str      w24, [sp, #0xc]
004cd7a8 18070011 add      w24, w24, #1
004cd7ac 1f03176b cmp      w24, w23
004cd7b0 0be3ff54 b.lt     #0x4cd410
004cd7b4 13000014 b        #0x4cd800
004cd7b8 e0031f2a mov      w0, wzr
004cd7bc fd7b47a9 ldp      x29, x30, [sp, #0x70]
004cd7c0 f44f46a9 ldp      x20, x19, [sp, #0x60]
004cd7c4 f65745a9 ldp      x22, x21, [sp, #0x50]
004cd7c8 f85f44a9 ldp      x24, x23, [sp, #0x40]
004cd7cc fa6743a9 ldp      x26, x25, [sp, #0x30]
004cd7d0 fc6f42a9 ldp      x28, x27, [sp, #0x20]
004cd7d4 ff030291 add      sp, sp, #0x80
004cd7d8 c0035fd6 ret      
004cd7dc 00010891 add      x0, x8, #0x200
004cd7e0 a4634694 bl       #0x1666670
004cd7e4 a00000b4 cbz      x0, #0x4cd7f8
004cd7e8 92614694 bl       #0x1665e30
004cd7ec f703002a mov      w23, w0
004cd7f0 1f040071 cmp      w0, #1
004cd7f4 8adfff54 b.ge     #0x4cd3e4
004cd7f8 08008012 mov      w8, #-1
004cd7fc e80f00b9 str      w8, [sp, #0xc]
004cd800 e80340f9 ldr      x8, [sp]
004cd804 080140b9 ldr      w8, [x8]
004cd808 e80e0034 cbz      w8, #0x4cd9e4
004cd80c b47001b0 adrp     x20, #0x32e2000
004cd810 b87001b0 adrp     x24, #0x32e2000
004cd814 fa030032 mov      w26, #1
004cd818 943a43f9 ldr      x20, [x20, #0x670]
004cd81c 183f43f9 ldr      x24, [x24, #0x678]
004cd820 f7db9452 mov      w23, #0xa6df
004cd824 b758ad72 movk     w23, #0x6ac5, lsl #16
004cd828 19008092 mov      x25, #-1
004cd82c fc7b1f32 mov      w28, #-2
004cd830 89024039 ldrb     w9, [x20]
004cd834 c9000034 cbz      w9, #0x4cd84c
004cd838 082340b9 ldr      w8, [x24, #0x20]
004cd83c 6805f836 tbz      w8, #0x1f, #0x4cd8e8
004cd840 1f050031 cmn      w8, #1
004cd844 40010054 b.eq     #0x4cd86c
004cd848 67000014 b        #0x4cd9e4
004cd84c 9a020039 strb     w26, [x20]
004cd850 19e704a9 stp      x25, x25, [x24, #0x48]
004cd854 190300f9 str      x25, [x24]
004cd858 195b00b9 str      w25, [x24, #0x58]
004cd85c 19e703a9 stp      x25, x25, [x24, #0x38]
004cd860 19e702a9 stp      x25, x25, [x24, #0x28]
004cd864 19e701a9 stp      x25, x25, [x24, #0x18]
004cd868 19e700a9 stp      x25, x25, [x24, #8]
004cd86c e00340f9 ldr      x0, [sp]
004cd870 84614694 bl       #0x1665e80
004cd874 800b00b4 cbz      x0, #0x4cd9e4
004cd878 f60300aa mov      x22, x0
004cd87c 79614694 bl       #0x1665e60
004cd880 200b00b4 cbz      x0, #0x4cd9e4
004cd884 f30300aa mov      x19, x0
004cd888 e00316aa mov      x0, x22
004cd88c 71614694 bl       #0x1665e50
004cd890 1c2300b9 str      w28, [x24, #0x20]
004cd894 800a0034 cbz      w0, #0x4cd9e4
004cd898 e8031f2a mov      w8, wzr
004cd89c 69120091 add      x9, x19, #4
004cd8a0 ea03082a mov      w10, w8
004cd8a4 4af17dd3 lsl      x10, x10, #3
004cd8a8 6a6a6ab8 ldr      w10, [x19, x10]
004cd8ac 5f01176b cmp      w10, w23
004cd8b0 c0000054 b.eq     #0x4cd8c8
004cd8b4 08050011 add      w8, w8, #1
004cd8b8 29210091 add      x9, x9, #8
004cd8bc 1f01006b cmp      w8, w0
004cd8c0 03ffff54 b.lo     #0x4cd8a0
004cd8c4 48000014 b        #0x4cd9e4
004cd8c8 280140b9 ldr      w8, [x9]
004cd8cc 1f050031 cmn      w8, #1
004cd8d0 e803881a csel     w8, wzr, w8, eq
004cd8d4 082300b9 str      w8, [x24, #0x20]
004cd8d8 e80340f9 ldr      x8, [sp]
004cd8dc 080140b9 ldr      w8, [x8]
004cd8e0 88faff35 cbnz     w8, #0x4cd830
004cd8e4 40000014 b        #0x4cd9e4
004cd8e8 eb0340f9 ldr      x11, [sp]
004cd8ec 0a7d4093 sxtw     x10, w8
004cd8f0 4a010bab adds     x10, x10, x11
004cd8f4 80070054 b.eq     #0x4cd9e4
004cd8f8 4a01c079 ldrsh    w10, [x10]
004cd8fc 5f090031 cmn      w10, #2
004cd900 20070054 b.eq     #0x4cd9e4
004cd904 e00340f9 ldr      x0, [sp]
004cd908 0a0040b9 ldr      w10, [x0]
004cd90c 6a060034 cbz      w10, #0x4cd9d8
004cd910 fa030032 mov      w26, #1
004cd914 fc7b1f32 mov      w28, #-2
004cd918 3f1d0072 tst      w9, #0xff
004cd91c 01040054 b.ne     #0x4cd99c
004cd920 23000014 b        #0x4cd9ac
004cd924 f60300aa mov      x22, x0
004cd928 4e614694 bl       #0x1665e60
004cd92c 600500b4 cbz      x0, #0x4cd9d8
004cd930 f30300aa mov      x19, x0
004cd934 e00316aa mov      x0, x22
004cd938 46614694 bl       #0x1665e50
004cd93c 1c2300b9 str      w28, [x24, #0x20]
004cd940 c0040034 cbz      w0, #0x4cd9d8
004cd944 e8031f2a mov      w8, wzr
004cd948 69120091 add      x9, x19, #4
004cd94c ea03082a mov      w10, w8
004cd950 4af17dd3 lsl      x10, x10, #3
004cd954 6a6a6ab8 ldr      w10, [x19, x10]
004cd958 5f01176b cmp      w10, w23
004cd95c c0000054 b.eq     #0x4cd974
004cd960 08050011 add      w8, w8, #1
004cd964 29210091 add      x9, x9, #8
004cd968 1f01006b cmp      w8, w0
004cd96c 03ffff54 b.lo     #0x4cd94c
004cd970 1a000014 b        #0x4cd9d8
004cd974 280140b9 ldr      w8, [x9]
004cd978 1f050031 cmn      w8, #1
004cd97c e803881a csel     w8, wzr, w8, eq
004cd980 082300b9 str      w8, [x24, #0x20]
004cd984 a90240b9 ldr      w9, [x21]
004cd988 89020034 cbz      w9, #0x4cd9d8
004cd98c 89024039 ldrb     w9, [x20]
004cd990 e00315aa mov      x0, x21
004cd994 3f1d0072 tst      w9, #0xff
004cd998 a0000054 b.eq     #0x4cd9ac
004cd99c 2832f836 tbz      w8, #0x1f, #0x4cdfe0
004cd9a0 1f050031 cmn      w8, #1
004cd9a4 40010054 b.eq     #0x4cd9cc
004cd9a8 0c000014 b        #0x4cd9d8
004cd9ac 9a020039 strb     w26, [x20]
004cd9b0 19e704a9 stp      x25, x25, [x24, #0x48]
004cd9b4 190300f9 str      x25, [x24]
004cd9b8 195b00b9 str      w25, [x24, #0x58]
004cd9bc 19e703a9 stp      x25, x25, [x24, #0x38]
004cd9c0 19e702a9 stp      x25, x25, [x24, #0x28]
004cd9c4 19e701a9 stp      x25, x25, [x24, #0x18]
004cd9c8 19e700a9 stp      x25, x25, [x24, #8]
004cd9cc f50300aa mov      x21, x0
004cd9d0 2c614694 bl       #0x1665e80
004cd9d4 80faffb5 cbnz     x0, #0x4cd924
004cd9d8 e13b1f32 mov      w1, #0xfffe
004cd9dc e0430091 add      x0, sp, #0x10
004cd9e0 b02b2a94 bl       #0xf588a0
004cd9e4 e10f40b9 ldr      w1, [sp, #0xc]
004cd9e8 3f040031 cmn      w1, #1
004cd9ec 60070054 b.eq     #0x4cdad8
004cd9f0 680340f9 ldr      x8, [x27]
004cd9f4 00010891 add      x0, x8, #0x200
004cd9f8 4afdff97 bl       #0x4ccf20
004cd9fc e00600b4 cbz      x0, #0x4cdad8
004cda00 080040b9 ldr      w8, [x0]
004cda04 f30300aa mov      x19, x0
004cda08 28060034 cbz      w8, #0x4cdacc
004cda0c b77001b0 adrp     x23, #0x32e2000
004cda10 b87001b0 adrp     x24, #0x32e2000
004cda14 fa030032 mov      w26, #1
004cda18 f75243f9 ldr      x23, [x23, #0x6a0]
004cda1c 185743f9 ldr      x24, [x24, #0x6a8]
004cda20 d65b9152 mov      w22, #0x8ade
004cda24 16e4b872 movk     w22, #0xc720, lsl #16
004cda28 19008092 mov      x25, #-1
004cda2c fb7b1f32 mov      w27, #-2
004cda30 e8024039 ldrb     w8, [x23]
004cda34 c8000034 cbz      w8, #0x4cda4c
004cda38 081b80b9 ldrsw    x8, [x24, #0x18]
004cda3c 2805f836 tbz      w8, #0x1f, #0x4cdae0
004cda40 1f050031 cmn      w8, #1
004cda44 a0000054 b.eq     #0x4cda58
004cda48 2c000014 b        #0x4cdaf8
004cda4c fa020039 strb     w26, [x23]
004cda50 196701a9 stp      x25, x25, [x24, #0x10]
004cda54 196700a9 stp      x25, x25, [x24]
004cda58 e00313aa mov      x0, x19
004cda5c 09614694 bl       #0x1665e80
004cda60 c00400b4 cbz      x0, #0x4cdaf8
004cda64 f50300aa mov      x21, x0
004cda68 fe604694 bl       #0x1665e60
004cda6c 600400b4 cbz      x0, #0x4cdaf8
004cda70 f40300aa mov      x20, x0
004cda74 e00315aa mov      x0, x21
004cda78 f6604694 bl       #0x1665e50
004cda7c 1b1b00b9 str      w27, [x24, #0x18]
004cda80 c0030034 cbz      w0, #0x4cdaf8
004cda84 e8031f2a mov      w8, wzr
004cda88 89120091 add      x9, x20, #4
004cda8c ea03082a mov      w10, w8
004cda90 4af17dd3 lsl      x10, x10, #3
004cda94 8a6a6ab8 ldr      w10, [x20, x10]
004cda98 5f01166b cmp      w10, w22
004cda9c c0000054 b.eq     #0x4cdab4
004cdaa0 08050011 add      w8, w8, #1
004cdaa4 29210091 add      x9, x9, #8
004cdaa8 1f01006b cmp      w8, w0
004cdaac 03ffff54 b.lo     #0x4cda8c
004cdab0 12000014 b        #0x4cdaf8
004cdab4 280140b9 ldr      w8, [x9]
004cdab8 1f050031 cmn      w8, #1
004cdabc e803881a csel     w8, wzr, w8, eq
004cdac0 081b00b9 str      w8, [x24, #0x18]
004cdac4 680240b9 ldr      w8, [x19]
004cdac8 48fbff35 cbnz     w8, #0x4cda30
004cdacc fb031f2a mov      w27, wzr
004cdad0 f6031f2a mov      w22, wzr
004cdad4 38000014 b        #0x4cdbb4
004cdad8 e8031f2a mov      w8, wzr
004cdadc c5000014 b        #0x4cddf0
004cdae0 080113ab adds     x8, x8, x19
004cdae4 a0000054 b.eq     #0x4cdaf8
004cdae8 16014039 ldrb     w22, [x8]
004cdaec 680240b9 ldr      w8, [x19]
004cdaf0 a8000035 cbnz     w8, #0x4cdb04
004cdaf4 2f000014 b        #0x4cdbb0
004cdaf8 f6031f2a mov      w22, wzr
004cdafc 680240b9 ldr      w8, [x19]
004cdb00 88050034 cbz      w8, #0x4cdbb0
004cdb04 1aa68452 mov      w26, #0x2530
004cdb08 bab2ba72 movk     w26, #0xd595, lsl #16
004cdb0c fb030032 mov      w27, #1
004cdb10 fc7b1f32 mov      w28, #-2
004cdb14 e8024039 ldrb     w8, [x23]
004cdb18 c8000034 cbz      w8, #0x4cdb30
004cdb1c 081780b9 ldrsw    x8, [x24, #0x14]
004cdb20 6805f836 tbz      w8, #0x1f, #0x4cdbcc
004cdb24 1f050031 cmn      w8, #1
004cdb28 a0000054 b.eq     #0x4cdb3c
004cdb2c 2e000014 b        #0x4cdbe4
004cdb30 fb020039 strb     w27, [x23]
004cdb34 196701a9 stp      x25, x25, [x24, #0x10]
004cdb38 196700a9 stp      x25, x25, [x24]
004cdb3c e00313aa mov      x0, x19
004cdb40 d0604694 bl       #0x1665e80
004cdb44 000500b4 cbz      x0, #0x4cdbe4
004cdb48 f50300aa mov      x21, x0
004cdb4c c5604694 bl       #0x1665e60
004cdb50 a00400b4 cbz      x0, #0x4cdbe4
004cdb54 f40300aa mov      x20, x0
004cdb58 e00315aa mov      x0, x21
004cdb5c bd604694 bl       #0x1665e50
004cdb60 1c1700b9 str      w28, [x24, #0x14]
004cdb64 00040034 cbz      w0, #0x4cdbe4
004cdb68 e8031f2a mov      w8, wzr
004cdb6c 89120091 add      x9, x20, #4
004cdb70 ea03082a mov      w10, w8
004cdb74 4af17dd3 lsl      x10, x10, #3
004cdb78 8a6a6ab8 ldr      w10, [x20, x10]
004cdb7c 5f011a6b cmp      w10, w26
004cdb80 c0000054 b.eq     #0x4cdb98
004cdb84 08050011 add      w8, w8, #1
004cdb88 29210091 add      x9, x9, #8
004cdb8c 1f01006b cmp      w8, w0
004cdb90 03ffff54 b.lo     #0x4cdb70
004cdb94 14000014 b        #0x4cdbe4
004cdb98 280140b9 ldr      w8, [x9]
004cdb9c 1f050031 cmn      w8, #1
004cdba0 e803881a csel     w8, wzr, w8, eq
004cdba4 081700b9 str      w8, [x24, #0x14]
004cdba8 680240b9 ldr      w8, [x19]
004cdbac 48fbff35 cbnz     w8, #0x4cdb14
004cdbb0 fb031f2a mov      w27, wzr
004cdbb4 fa031f2a mov      w26, wzr
004cdbb8 e9031f2a mov      w9, wzr
004cdbbc e8031f2a mov      w8, wzr
004cdbc0 3f090071 cmp      w9, #2
004cdbc4 890f0054 b.ls     #0x4cddb4
004cdbc8 8a000014 b        #0x4cddf0
004cdbcc 080113ab adds     x8, x8, x19
004cdbd0 a0000054 b.eq     #0x4cdbe4
004cdbd4 1a014039 ldrb     w26, [x8]
004cdbd8 680240b9 ldr      w8, [x19]
004cdbdc a8000035 cbnz     w8, #0x4cdbf0
004cdbe0 2f000014 b        #0x4cdc9c
004cdbe4 fa031f2a mov      w26, wzr
004cdbe8 680240b9 ldr      w8, [x19]
004cdbec 88050034 cbz      w8, #0x4cdc9c
004cdbf0 bb4a8852 mov      w27, #0x4255
004cdbf4 3ba5ad72 movk     w27, #0x6d29, lsl #16
004cdbf8 fc7b1f32 mov      w28, #-2
004cdbfc e8024039 ldrb     w8, [x23]
004cdc00 c8000034 cbz      w8, #0x4cdc18
004cdc04 081380b9 ldrsw    x8, [x24, #0x10]
004cdc08 6805f836 tbz      w8, #0x1f, #0x4cdcb4
004cdc0c 1f050031 cmn      w8, #1
004cdc10 c0000054 b.eq     #0x4cdc28
004cdc14 2e000014 b        #0x4cdccc
004cdc18 e8030032 mov      w8, #1
004cdc1c e8020039 strb     w8, [x23]
004cdc20 196701a9 stp      x25, x25, [x24, #0x10]
004cdc24 196700a9 stp      x25, x25, [x24]
004cdc28 e00313aa mov      x0, x19
004cdc2c 95604694 bl       #0x1665e80
004cdc30 e00400b4 cbz      x0, #0x4cdccc
004cdc34 f50300aa mov      x21, x0
004cdc38 8a604694 bl       #0x1665e60
004cdc3c 800400b4 cbz      x0, #0x4cdccc
004cdc40 f40300aa mov      x20, x0
004cdc44 e00315aa mov      x0, x21
004cdc48 82604694 bl       #0x1665e50
004cdc4c 1c1300b9 str      w28, [x24, #0x10]
004cdc50 e0030034 cbz      w0, #0x4cdccc
004cdc54 e8031f2a mov      w8, wzr
004cdc58 89120091 add      x9, x20, #4
004cdc5c ea03082a mov      w10, w8
004cdc60 4af17dd3 lsl      x10, x10, #3
004cdc64 8a6a6ab8 ldr      w10, [x20, x10]
004cdc68 5f011b6b cmp      w10, w27
004cdc6c c0000054 b.eq     #0x4cdc84
004cdc70 08050011 add      w8, w8, #1
004cdc74 29210091 add      x9, x9, #8
004cdc78 1f01006b cmp      w8, w0
004cdc7c 03ffff54 b.lo     #0x4cdc5c
004cdc80 13000014 b        #0x4cdccc
004cdc84 280140b9 ldr      w8, [x9]
004cdc88 1f050031 cmn      w8, #1
004cdc8c e803881a csel     w8, wzr, w8, eq
004cdc90 081300b9 str      w8, [x24, #0x10]
004cdc94 680240b9 ldr      w8, [x19]
004cdc98 28fbff35 cbnz     w8, #0x4cdbfc
004cdc9c fb031f2a mov      w27, wzr
004cdca0 e9031f2a mov      w9, wzr
004cdca4 e8031f2a mov      w8, wzr
004cdca8 3f090071 cmp      w9, #2
004cdcac 49080054 b.ls     #0x4cddb4
004cdcb0 50000014 b        #0x4cddf0
004cdcb4 080113ab adds     x8, x8, x19
004cdcb8 a0000054 b.eq     #0x4cdccc
004cdcbc 1b014039 ldrb     w27, [x8]
004cdcc0 680240b9 ldr      w8, [x19]
004cdcc4 a8000035 cbnz     w8, #0x4cdcd8
004cdcc8 37000014 b        #0x4cdda4
004cdccc fb031f2a mov      w27, wzr
004cdcd0 680240b9 ldr      w8, [x19]
004cdcd4 88060034 cbz      w8, #0x4cdda4
004cdcd8 9c5d8f52 mov      w28, #0x7aec
004cdcdc dc1fbe72 movk     w28, #0xf0fe, lsl #16
004cdce0 e8024039 ldrb     w8, [x23]
004cdce4 c8000034 cbz      w8, #0x4cdcfc
004cdce8 080f80b9 ldrsw    x8, [x24, #0xc]
004cdcec e804f836 tbz      w8, #0x1f, #0x4cdd88
004cdcf0 1f050031 cmn      w8, #1
004cdcf4 c0000054 b.eq     #0x4cdd0c
004cdcf8 2b000014 b        #0x4cdda4
004cdcfc e8030032 mov      w8, #1
004cdd00 e8020039 strb     w8, [x23]
004cdd04 196701a9 stp      x25, x25, [x24, #0x10]
004cdd08 196700a9 stp      x25, x25, [x24]
004cdd0c e00313aa mov      x0, x19
004cdd10 5c604694 bl       #0x1665e80
004cdd14 800400b4 cbz      x0, #0x4cdda4
004cdd18 f50300aa mov      x21, x0
004cdd1c 51604694 bl       #0x1665e60
004cdd20 200400b4 cbz      x0, #0x4cdda4
004cdd24 f40300aa mov      x20, x0
004cdd28 e00315aa mov      x0, x21
004cdd2c 49604694 bl       #0x1665e50
004cdd30 e87b1f32 mov      w8, #-2
004cdd34 080f00b9 str      w8, [x24, #0xc]
004cdd38 60030034 cbz      w0, #0x4cdda4
004cdd3c e8031f2a mov      w8, wzr
004cdd40 89120091 add      x9, x20, #4
004cdd44 ea03082a mov      w10, w8
004cdd48 4af17dd3 lsl      x10, x10, #3
004cdd4c 8a6a6ab8 ldr      w10, [x20, x10]
004cdd50 5f011c6b cmp      w10, w28
004cdd54 c0000054 b.eq     #0x4cdd6c
004cdd58 08050011 add      w8, w8, #1
004cdd5c 29210091 add      x9, x9, #8
004cdd60 1f01006b cmp      w8, w0
004cdd64 03ffff54 b.lo     #0x4cdd44
004cdd68 0f000014 b        #0x4cdda4
004cdd6c 280140b9 ldr      w8, [x9]
004cdd70 1f050031 cmn      w8, #1
004cdd74 e803881a csel     w8, wzr, w8, eq
004cdd78 080f00b9 str      w8, [x24, #0xc]
004cdd7c 680240b9 ldr      w8, [x19]
004cdd80 08fbff35 cbnz     w8, #0x4cdce0
004cdd84 08000014 b        #0x4cdda4
004cdd88 080113ab adds     x8, x8, x19
004cdd8c c0000054 b.eq     #0x4cdda4
004cdd90 09014039 ldrb     w9, [x8]
004cdd94 e8031f2a mov      w8, wzr
004cdd98 3f090071 cmp      w9, #2
004cdd9c c9000054 b.ls     #0x4cddb4
004cdda0 14000014 b        #0x4cddf0
004cdda4 e9031f2a mov      w9, wzr
004cdda8 e8031f2a mov      w8, wzr
004cddac 3f090071 cmp      w9, #2
004cddb0 08020054 b.hi     #0x4cddf0
004cddb4 7f0b0071 cmp      w27, #2
004cddb8 c8010054 b.hi     #0x4cddf0
004cddbc df0a0071 cmp      w22, #2
004cddc0 88010054 b.hi     #0x4cddf0
004cddc4 5f0b0071 cmp      w26, #2
004cddc8 48010054 b.hi     #0x4cddf0
004cddcc 48290190 adrp     x8, #0x29f5000
004cddd0 08093e91 add      x8, x8, #0xf82
004cddd4 09496938 ldrb     w9, [x8, w9, uxtw]
004cddd8 0a497b38 ldrb     w10, [x8, w27, uxtw]
004cdddc 4909092a orr      w9, w10, w9, lsl #2
004cdde0 0a497a38 ldrb     w10, [x8, w26, uxtw]
004cdde4 4909092a orr      w9, w10, w9, lsl #2
004cdde8 08497638 ldrb     w8, [x8, w22, uxtw]
004cddec 0809092a orr      w8, w8, w9, lsl #2
004cddf0 001d0012 and      w0, w8, #0xff
004cddf4 72feff17 b        #0x4cd7bc
004cddf8 690240b9 ldr      w9, [x19]
004cddfc 490e0034 cbz      w9, #0x4cdfc4
004cde00 fc031aaa mov      x28, x26
004cde04 d45b9152 mov      w20, #0x8ade
004cde08 14e4b872 movk     w20, #0xc720, lsl #16
004cde0c f7030032 mov      w23, #1
004cde10 f87b1f32 mov      w24, #-2
004cde14 1f1d0072 tst      w8, #0xff
004cde18 61040054 b.ne     #0x4cdea4
004cde1c 29000014 b        #0x4cdec0
004cde20 f50300aa mov      x21, x0
004cde24 0f604694 bl       #0x1665e60
004cde28 e00500b4 cbz      x0, #0x4cdee4
004cde2c f60300aa mov      x22, x0
004cde30 e00315aa mov      x0, x21
004cde34 07604694 bl       #0x1665e50
004cde38 a87001b0 adrp     x8, #0x32e2000
004cde3c 085543f9 ldr      x8, [x8, #0x6a8]
004cde40 181900b9 str      w24, [x8, #0x18]
004cde44 00050034 cbz      w0, #0x4cdee4
004cde48 e8031f2a mov      w8, wzr
004cde4c c9120091 add      x9, x22, #4
004cde50 ea03082a mov      w10, w8
004cde54 4af17dd3 lsl      x10, x10, #3
004cde58 ca6a6ab8 ldr      w10, [x22, x10]
004cde5c 5f01146b cmp      w10, w20
004cde60 c0000054 b.eq     #0x4cde78
004cde64 08050011 add      w8, w8, #1
004cde68 29210091 add      x9, x9, #8
004cde6c 1f01006b cmp      w8, w0
004cde70 03ffff54 b.lo     #0x4cde50
004cde74 1c000014 b        #0x4cdee4
004cde78 280140b9 ldr      w8, [x9]
004cde7c a97001b0 adrp     x9, #0x32e2000
004cde80 295543f9 ldr      x9, [x9, #0x6a8]
004cde84 1f050031 cmn      w8, #1
004cde88 e803881a csel     w8, wzr, w8, eq
004cde8c 281900b9 str      w8, [x9, #0x18]
004cde90 680240b9 ldr      w8, [x19]
004cde94 680c0034 cbz      w8, #0x4ce020
004cde98 88034039 ldrb     w8, [x28]
004cde9c 1f1d0072 tst      w8, #0xff
004cdea0 00010054 b.eq     #0x4cdec0
004cdea4 a87001b0 adrp     x8, #0x32e2000
004cdea8 085543f9 ldr      x8, [x8, #0x6a8]
004cdeac 081980b9 ldrsw    x8, [x8, #0x18]
004cdeb0 080af836 tbz      w8, #0x1f, #0x4cdff0
004cdeb4 1f050031 cmn      w8, #1
004cdeb8 00010054 b.eq     #0x4cded8
004cdebc 0a000014 b        #0x4cdee4
004cdec0 97030039 strb     w23, [x28]
004cdec4 a87001b0 adrp     x8, #0x32e2000
004cdec8 085543f9 ldr      x8, [x8, #0x6a8]
004cdecc 09008092 mov      x9, #-1
004cded0 092501a9 stp      x9, x9, [x8, #0x10]
004cded4 092500a9 stp      x9, x9, [x8]
004cded8 e00313aa mov      x0, x19
004cdedc e95f4694 bl       #0x1665e80
004cdee0 00faffb5 cbnz     x0, #0x4cde20
004cdee4 f7031f2a mov      w23, wzr
004cdee8 680240b9 ldr      w8, [x19]
004cdeec c8080034 cbz      w8, #0x4ce004
004cdef0 14a68452 mov      w20, #0x2530
004cdef4 b4b2ba72 movk     w20, #0xd595, lsl #16
004cdef8 f8030032 mov      w24, #1
004cdefc f97b1f32 mov      w25, #-2
004cdf00 88034039 ldrb     w8, [x28]
004cdf04 08010034 cbz      w8, #0x4cdf24
004cdf08 a87001b0 adrp     x8, #0x32e2000
004cdf0c 085543f9 ldr      x8, [x8, #0x6a8]
004cdf10 081580b9 ldrsw    x8, [x8, #0x14]
004cdf14 c808f836 tbz      w8, #0x1f, #0x4ce02c
004cdf18 1f050031 cmn      w8, #1
004cdf1c 00010054 b.eq     #0x4cdf3c
004cdf20 49000014 b        #0x4ce044
004cdf24 98030039 strb     w24, [x28]
004cdf28 a87001b0 adrp     x8, #0x32e2000
004cdf2c 085543f9 ldr      x8, [x8, #0x6a8]
004cdf30 09008092 mov      x9, #-1
004cdf34 092501a9 stp      x9, x9, [x8, #0x10]
004cdf38 092500a9 stp      x9, x9, [x8]
004cdf3c e00313aa mov      x0, x19
004cdf40 d05f4694 bl       #0x1665e80
004cdf44 000800b4 cbz      x0, #0x4ce044
004cdf48 f50300aa mov      x21, x0
004cdf4c c55f4694 bl       #0x1665e60
004cdf50 a00700b4 cbz      x0, #0x4ce044
004cdf54 f60300aa mov      x22, x0
004cdf58 e00315aa mov      x0, x21
004cdf5c bd5f4694 bl       #0x1665e50
004cdf60 a87001b0 adrp     x8, #0x32e2000
004cdf64 085543f9 ldr      x8, [x8, #0x6a8]
004cdf68 191500b9 str      w25, [x8, #0x14]
004cdf6c c0060034 cbz      w0, #0x4ce044
004cdf70 e8031f2a mov      w8, wzr
004cdf74 c9120091 add      x9, x22, #4
004cdf78 ea03082a mov      w10, w8
004cdf7c 4af17dd3 lsl      x10, x10, #3
004cdf80 ca6a6ab8 ldr      w10, [x22, x10]
004cdf84 5f01146b cmp      w10, w20
004cdf88 c0000054 b.eq     #0x4cdfa0
004cdf8c 08050011 add      w8, w8, #1
004cdf90 29210091 add      x9, x9, #8
004cdf94 1f01006b cmp      w8, w0
004cdf98 03ffff54 b.lo     #0x4cdf78
004cdf9c 2a000014 b        #0x4ce044
004cdfa0 280140b9 ldr      w8, [x9]
004cdfa4 a97001b0 adrp     x9, #0x32e2000
004cdfa8 295543f9 ldr      x9, [x9, #0x6a8]
004cdfac 1f050031 cmn      w8, #1
004cdfb0 e803881a csel     w8, wzr, w8, eq
004cdfb4 281500b9 str      w8, [x9, #0x14]
004cdfb8 680240b9 ldr      w8, [x19]
004cdfbc 28faff35 cbnz     w8, #0x4cdf00
004cdfc0 11000014 b        #0x4ce004
004cdfc4 f8031f2a mov      w24, wzr
004cdfc8 f7031f2a mov      w23, wzr
004cdfcc f4031f2a mov      w20, wzr
004cdfd0 e8031f2a mov      w8, wzr
004cdfd4 3f090071 cmp      w9, #2
004cdfd8 29140054 b.ls     #0x4ce25c
004cdfdc 85ffff17 b        #0x4cddf0
004cdfe0 08c028ab adds     x8, x0, w8, sxtw
004cdfe4 a0cfff54 b.eq     #0x4cd9d8
004cdfe8 01014079 ldrh     w1, [x8]
004cdfec 7cfeff17 b        #0x4cd9dc
004cdff0 080113ab adds     x8, x8, x19
004cdff4 80f7ff54 b.eq     #0x4cdee4
004cdff8 17014039 ldrb     w23, [x8]
004cdffc 680240b9 ldr      w8, [x19]
004ce000 88f7ff35 cbnz     w8, #0x4cdef0
004ce004 f8031f2a mov      w24, wzr
004ce008 f4031f2a mov      w20, wzr
004ce00c e9031f2a mov      w9, wzr
004ce010 e8031f2a mov      w8, wzr
004ce014 3f090071 cmp      w9, #2
004ce018 29120054 b.ls     #0x4ce25c
004ce01c 75ffff17 b        #0x4cddf0
004ce020 f8031f2a mov      w24, wzr
004ce024 f7031f2a mov      w23, wzr
004ce028 f8ffff17 b        #0x4ce008
004ce02c 080113ab adds     x8, x8, x19
004ce030 a0000054 b.eq     #0x4ce044
004ce034 14014039 ldrb     w20, [x8]
004ce038 680240b9 ldr      w8, [x19]
004ce03c a8000035 cbnz     w8, #0x4ce050
004ce040 38000014 b        #0x4ce120
004ce044 f4031f2a mov      w20, wzr
004ce048 680240b9 ldr      w8, [x19]
004ce04c a8060034 cbz      w8, #0x4ce120
004ce050 b84a8852 mov      w24, #0x4255
004ce054 38a5ad72 movk     w24, #0x6d29, lsl #16
004ce058 f9030032 mov      w25, #1
004ce05c fa7b1f32 mov      w26, #-2
004ce060 88034039 ldrb     w8, [x28]
004ce064 08010034 cbz      w8, #0x4ce084
004ce068 a8700190 adrp     x8, #0x32e2000
004ce06c 085543f9 ldr      x8, [x8, #0x6a8]
004ce070 081180b9 ldrsw    x8, [x8, #0x10]
004ce074 2806f836 tbz      w8, #0x1f, #0x4ce138
004ce078 1f050031 cmn      w8, #1
004ce07c 00010054 b.eq     #0x4ce09c
004ce080 34000014 b        #0x4ce150
004ce084 99030039 strb     w25, [x28]
004ce088 a8700190 adrp     x8, #0x32e2000
004ce08c 085543f9 ldr      x8, [x8, #0x6a8]
004ce090 09008092 mov      x9, #-1
004ce094 092501a9 stp      x9, x9, [x8, #0x10]
004ce098 092500a9 stp      x9, x9, [x8]
004ce09c e00313aa mov      x0, x19
004ce0a0 785f4694 bl       #0x1665e80
004ce0a4 600500b4 cbz      x0, #0x4ce150
004ce0a8 f50300aa mov      x21, x0
004ce0ac 6d5f4694 bl       #0x1665e60
004ce0b0 000500b4 cbz      x0, #0x4ce150
004ce0b4 f60300aa mov      x22, x0
004ce0b8 e00315aa mov      x0, x21
004ce0bc 655f4694 bl       #0x1665e50
004ce0c0 a8700190 adrp     x8, #0x32e2000
004ce0c4 085543f9 ldr      x8, [x8, #0x6a8]
004ce0c8 1a1100b9 str      w26, [x8, #0x10]
004ce0cc 20040034 cbz      w0, #0x4ce150
004ce0d0 e8031f2a mov      w8, wzr
004ce0d4 c9120091 add      x9, x22, #4
004ce0d8 ea03082a mov      w10, w8
004ce0dc 4af17dd3 lsl      x10, x10, #3
004ce0e0 ca6a6ab8 ldr      w10, [x22, x10]
004ce0e4 5f01186b cmp      w10, w24
004ce0e8 c0000054 b.eq     #0x4ce100
004ce0ec 08050011 add      w8, w8, #1
004ce0f0 29210091 add      x9, x9, #8
004ce0f4 1f01006b cmp      w8, w0
004ce0f8 03ffff54 b.lo     #0x4ce0d8
004ce0fc 15000014 b        #0x4ce150
004ce100 280140b9 ldr      w8, [x9]
004ce104 a9700190 adrp     x9, #0x32e2000
004ce108 295543f9 ldr      x9, [x9, #0x6a8]
004ce10c 1f050031 cmn      w8, #1
004ce110 e803881a csel     w8, wzr, w8, eq
004ce114 281100b9 str      w8, [x9, #0x10]
004ce118 680240b9 ldr      w8, [x19]
004ce11c 28faff35 cbnz     w8, #0x4ce060
004ce120 f8031f2a mov      w24, wzr
004ce124 e9031f2a mov      w9, wzr
004ce128 e8031f2a mov      w8, wzr
004ce12c 3f090071 cmp      w9, #2
004ce130 69090054 b.ls     #0x4ce25c
004ce134 2fffff17 b        #0x4cddf0
004ce138 080113ab adds     x8, x8, x19
004ce13c a0000054 b.eq     #0x4ce150
004ce140 18014039 ldrb     w24, [x8]
004ce144 680240b9 ldr      w8, [x19]
004ce148 a8000035 cbnz     w8, #0x4ce15c
004ce14c 40000014 b        #0x4ce24c
004ce150 f8031f2a mov      w24, wzr
004ce154 680240b9 ldr      w8, [x19]
004ce158 a8070034 cbz      w8, #0x4ce24c
004ce15c 995d8f52 mov      w25, #0x7aec
004ce160 d91fbe72 movk     w25, #0xf0fe, lsl #16
004ce164 fa030032 mov      w26, #1
004ce168 fb7b1f32 mov      w27, #-2
004ce16c 88034039 ldrb     w8, [x28]
004ce170 08010034 cbz      w8, #0x4ce190
004ce174 a8700190 adrp     x8, #0x32e2000
004ce178 085543f9 ldr      x8, [x8, #0x6a8]
004ce17c 080d80b9 ldrsw    x8, [x8, #0xc]
004ce180 8805f836 tbz      w8, #0x1f, #0x4ce230
004ce184 1f050031 cmn      w8, #1
004ce188 00010054 b.eq     #0x4ce1a8
004ce18c 30000014 b        #0x4ce24c
004ce190 9a030039 strb     w26, [x28]
004ce194 a8700190 adrp     x8, #0x32e2000
004ce198 085543f9 ldr      x8, [x8, #0x6a8]
004ce19c 09008092 mov      x9, #-1
004ce1a0 092501a9 stp      x9, x9, [x8, #0x10]
004ce1a4 092500a9 stp      x9, x9, [x8]
004ce1a8 e00313aa mov      x0, x19
004ce1ac 355f4694 bl       #0x1665e80
004ce1b0 e00400b4 cbz      x0, #0x4ce24c
004ce1b4 f50300aa mov      x21, x0
004ce1b8 2a5f4694 bl       #0x1665e60
004ce1bc 800400b4 cbz      x0, #0x4ce24c
004ce1c0 f60300aa mov      x22, x0
004ce1c4 e00315aa mov      x0, x21
004ce1c8 225f4694 bl       #0x1665e50
004ce1cc a8700190 adrp     x8, #0x32e2000
004ce1d0 085543f9 ldr      x8, [x8, #0x6a8]
004ce1d4 1b0d00b9 str      w27, [x8, #0xc]
004ce1d8 a0030034 cbz      w0, #0x4ce24c
004ce1dc e8031f2a mov      w8, wzr
004ce1e0 c9120091 add      x9, x22, #4
004ce1e4 ea03082a mov      w10, w8
004ce1e8 4af17dd3 lsl      x10, x10, #3
004ce1ec ca6a6ab8 ldr      w10, [x22, x10]
004ce1f0 5f01196b cmp      w10, w25
004ce1f4 c0000054 b.eq     #0x4ce20c
004ce1f8 08050011 add      w8, w8, #1
004ce1fc 29210091 add      x9, x9, #8
004ce200 1f01006b cmp      w8, w0
004ce204 03ffff54 b.lo     #0x4ce1e4
004ce208 11000014 b        #0x4ce24c
004ce20c 280140b9 ldr      w8, [x9]
004ce210 a9700190 adrp     x9, #0x32e2000
004ce214 295543f9 ldr      x9, [x9, #0x6a8]
004ce218 1f050031 cmn      w8, #1
004ce21c e803881a csel     w8, wzr, w8, eq
004ce220 280d00b9 str      w8, [x9, #0xc]
004ce224 680240b9 ldr      w8, [x19]
004ce228 28faff35 cbnz     w8, #0x4ce16c
004ce22c 08000014 b        #0x4ce24c
004ce230 080113ab adds     x8, x8, x19
004ce234 c0000054 b.eq     #0x4ce24c
004ce238 09014039 ldrb     w9, [x8]
004ce23c e8031f2a mov      w8, wzr
004ce240 3f090071 cmp      w9, #2
004ce244 c9000054 b.ls     #0x4ce25c
004ce248 eafeff17 b        #0x4cddf0
004ce24c e9031f2a mov      w9, wzr
004ce250 e8031f2a mov      w8, wzr
004ce254 3f090071 cmp      w9, #2
004ce258 c8dcff54 b.hi     #0x4cddf0
004ce25c 1f0b0071 cmp      w24, #2
004ce260 88dcff54 b.hi     #0x4cddf0
004ce264 ff0a0071 cmp      w23, #2
004ce268 48dcff54 b.hi     #0x4cddf0
004ce26c 9f0a0071 cmp      w20, #2
004ce270 08dcff54 b.hi     #0x4cddf0
004ce274 282901f0 adrp     x8, #0x29f5000
004ce278 08093e91 add      x8, x8, #0xf82
004ce27c 09496938 ldrb     w9, [x8, w9, uxtw]
004ce280 0a497838 ldrb     w10, [x8, w24, uxtw]
004ce284 4909092a orr      w9, w10, w9, lsl #2
004ce288 0a497438 ldrb     w10, [x8, w20, uxtw]
004ce28c 4909092a orr      w9, w10, w9, lsl #2
004ce290 08497738 ldrb     w8, [x8, w23, uxtw]
004ce294 d6feff17 b        #0x4cddec
