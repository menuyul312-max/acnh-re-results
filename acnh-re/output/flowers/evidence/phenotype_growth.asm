004cc4d0 ffc302d1 sub      sp, sp, #0xb0
004cc4d4 fc6f05a9 stp      x28, x27, [sp, #0x50]
004cc4d8 fa6706a9 stp      x26, x25, [sp, #0x60]
004cc4dc f85f07a9 stp      x24, x23, [sp, #0x70]
004cc4e0 f65708a9 stp      x22, x21, [sp, #0x80]
004cc4e4 f44f09a9 stp      x20, x19, [sp, #0x90]
004cc4e8 fd7b0aa9 stp      x29, x30, [sp, #0xa0]
004cc4ec fd830291 add      x29, sp, #0xa0
004cc4f0 f30300aa mov      x19, x0
004cc4f4 f34f00b9 str      w19, [sp, #0x4c]
004cc4f8 b97001d0 adrp     x25, #0x32e2000
004cc4fc 392743f9 ldr      x25, [x25, #0x648]
004cc500 280340f9 ldr      x8, [x25]
004cc504 884f00b4 cbz      x8, #0x4ccef4
004cc508 00010891 add      x0, x8, #0x200
004cc50c f403022a mov      w20, w2
004cc510 f503012a mov      w21, w1
004cc514 57684694 bl       #0x1666670
004cc518 e04e00b4 cbz      x0, #0x4ccef4
004cc51c 881e0012 and      w8, w20, #0xff
004cc520 1f0d0071 cmp      w8, #3
004cc524 e8070032 mov      w8, #3
004cc528 8832881a csel     w8, w20, w8, lo
004cc52c 1f1d0072 tst      w8, #0xff
004cc530 f34300b9 str      w19, [sp, #0x40]
004cc534 18159f1a csinc    w24, w8, wzr, ne
004cc538 e84340b9 ldr      w8, [sp, #0x40]
004cc53c 13490051 sub      w19, w8, #0x12
004cc540 7f220071 cmp      w19, #8
004cc544 824d0054 b.hs     #0x4ccef4
004cc548 280340f9 ldr      x8, [x25]
004cc54c 17c143b9 ldr      w23, [x8, #0x3c0]
004cc550 ff020071 cmp      w23, #0
004cc554 2d4c0054 b.le     #0x4cced8
004cc558 082901f0 adrp     x8, #0x29ef000
004cc55c 08010d91 add      x8, x8, #0x340
004cc560 aa064092 and      x10, x21, #3
004cc564 08d973b8 ldr      w8, [x8, w19, sxtw #2]
004cc568 d3138352 mov      w19, #0x189e
004cc56c 538da572 movk     w19, #0x2c6a, lsl #16
004cc570 e83f00b9 str      w8, [sp, #0x3c]
004cc574 a80e42d3 ubfx     x8, x21, #2, #2
004cc578 e8ab02a9 stp      x8, x10, [sp, #0x28]
004cc57c a81644d3 ubfx     x8, x21, #4, #2
004cc580 e81300f9 str      x8, [sp, #0x20]
004cc584 a81e46d3 ubfx     x8, x21, #6, #2
004cc588 f5031f2a mov      w21, wzr
004cc58c e80f00f9 str      x8, [sp, #0x18]
004cc590 bc7001d0 adrp     x28, #0x32e2000
004cc594 9c3f43f9 ldr      x28, [x28, #0x678]
004cc598 1b008092 mov      x27, #-1
004cc59c fa668652 mov      w26, #0x3337
004cc5a0 fab4be72 movk     w26, #0xf5a7, lsl #16
004cc5a4 14c19f52 mov      w20, #0xfe08
004cc5a8 f4dcae72 movk     w20, #0x76e7, lsl #16
004cc5ac e9031f2a mov      w9, wzr
004cc5b0 280340f9 ldr      x8, [x25]
004cc5b4 00010891 add      x0, x8, #0x200
004cc5b8 e103152a mov      w1, w21
004cc5bc 59020094 bl       #0x4ccf20
004cc5c0 a00500b4 cbz      x0, #0x4cc674
004cc5c4 37664694 bl       #0x1665ea0
004cc5c8 a97001d0 adrp     x9, #0x32e2000
004cc5cc 296143f9 ldr      x9, [x9, #0x6c0]
004cc5d0 280140b9 ldr      w8, [x9]
004cc5d4 1f00086b cmp      w0, w8
004cc5d8 a2000054 b.hs     #0x4cc5ec
004cc5dc 280540f9 ldr      x8, [x9, #8]
004cc5e0 08d96078 ldrh     w8, [x8, w0, sxtw #1]
004cc5e4 1f750071 cmp      w8, #0x1d
004cc5e8 49000054 b.ls     #0x4cc5f0
004cc5ec e8031f2a mov      w8, wzr
004cc5f0 e84b00b9 str      w8, [sp, #0x48]
004cc5f4 eb3f40b9 ldr      w11, [sp, #0x3c]
004cc5f8 e94f40b9 ldr      w9, [sp, #0x4c]
004cc5fc e84b40b9 ldr      w8, [sp, #0x48]
004cc600 3f01086b cmp      w9, w8
004cc604 21020054 b.ne     #0x4cc648
004cc608 e81b40f9 ldr      x8, [sp, #0x30]
004cc60c 492801d0 adrp     x9, #0x29d6000
004cc610 29610e91 add      x9, x9, #0x398
004cc614 ec0309aa mov      x12, x9
004cc618 29696838 ldrb     w9, [x9, x8]
004cc61c ea2342a9 ldp      x10, x8, [sp, #0x20]
004cc620 7f110071 cmp      w11, #4
004cc624 88696838 ldrb     w8, [x12, x8]
004cc628 8a696a38 ldrb     w10, [x12, x10]
004cc62c c0020054 b.eq     #0x4cc684
004cc630 7f0d0071 cmp      w11, #3
004cc634 e0030054 b.eq     #0x4cc6b0
004cc638 7f090071 cmp      w11, #2
004cc63c c1450054 b.ne     #0x4ccef4
004cc640 2905090b add      w9, w9, w9, lsl #1
004cc644 1f000014 b        #0x4cc6c0
004cc648 e84300b9 str      w8, [sp, #0x40]
004cc64c e84340b9 ldr      w8, [sp, #0x40]
004cc650 1f650071 cmp      w8, #0x19
004cc654 e80c0054 b.hi     #0x4cc7f0
004cc658 e9030032 mov      w9, #1
004cc65c 2921c81a lsl      w9, w9, w8
004cc660 8a7ba052 mov      w10, #0x3dc0000
004cc664 3f010a6a tst      w9, w10
004cc668 400b0054 b.eq     #0x4cc7d0
004cc66c 68038052 mov      w8, #0x1b
004cc670 1501150b add      w21, w8, w21
004cc674 f63b1f32 mov      w22, #0xfffe
004cc678 bf02176b cmp      w21, w23
004cc67c abf9ff54 b.lt     #0x4cc5b0
004cc680 1e020014 b        #0x4ccef8
004cc684 eb0f40f9 ldr      x11, [sp, #0x18]
004cc688 080d080b add      w8, w8, w8, lsl #3
004cc68c 4c2801d0 adrp     x12, #0x29d6000
004cc690 8c610e91 add      x12, x12, #0x398
004cc694 8b696b38 ldrb     w11, [x12, x11]
004cc698 6c038052 mov      w12, #0x1b
004cc69c 28210c1b madd     w8, w9, w12, w8
004cc6a0 49050a0b add      w9, w10, w10, lsl #1
004cc6a4 0901090b add      w9, w8, w9
004cc6a8 e8030b2a mov      w8, w11
004cc6ac 05000014 b        #0x4cc6c0
004cc6b0 290d090b add      w9, w9, w9, lsl #3
004cc6b4 0805080b add      w8, w8, w8, lsl #1
004cc6b8 0901090b add      w9, w8, w9
004cc6bc e8030a2a mov      w8, w10
004cc6c0 2801080b add      w8, w9, w8
004cc6c4 290340f9 ldr      x9, [x25]
004cc6c8 0101150b add      w1, w8, w21
004cc6cc 20010891 add      x0, x9, #0x200
004cc6d0 f51700b9 str      w21, [sp, #0x14]
004cc6d4 13020094 bl       #0x4ccf20
004cc6d8 e04000b4 cbz      x0, #0x4ccef4
004cc6dc 080040b9 ldr      w8, [x0]
004cc6e0 f50300aa mov      x21, x0
004cc6e4 f70f00b9 str      w23, [sp, #0xc]
004cc6e8 48120034 cbz      w8, #0x4cc930
004cc6ec a97001d0 adrp     x9, #0x32e2000
004cc6f0 295143f9 ldr      x9, [x9, #0x6a0]
004cc6f4 28014039 ldrb     w8, [x9]
004cc6f8 88050034 cbz      w8, #0x4cc7a8
004cc6fc a87001d0 adrp     x8, #0x32e2000
004cc700 085543f9 ldr      x8, [x8, #0x6a8]
004cc704 080580b9 ldrsw    x8, [x8, #4]
004cc708 e807f836 tbz      w8, #0x1f, #0x4cc804
004cc70c 1f050031 cmn      w8, #1
004cc710 61080054 b.ne     #0x4cc81c
004cc714 e00315aa mov      x0, x21
004cc718 da654694 bl       #0x1665e80
004cc71c 000800b4 cbz      x0, #0x4cc81c
004cc720 f70300aa mov      x23, x0
004cc724 cf654694 bl       #0x1665e60
004cc728 a00700b4 cbz      x0, #0x4cc81c
004cc72c f60300aa mov      x22, x0
004cc730 e00317aa mov      x0, x23
004cc734 c7654694 bl       #0x1665e50
004cc738 a97001d0 adrp     x9, #0x32e2000
004cc73c 295543f9 ldr      x9, [x9, #0x6a8]
004cc740 abdb8652 mov      w11, #0x36dd
004cc744 6ba6ae72 movk     w11, #0x7533, lsl #16
004cc748 e87b1f32 mov      w8, #-2
004cc74c 280500b9 str      w8, [x9, #4]
004cc750 60060034 cbz      w0, #0x4cc81c
004cc754 e8031f2a mov      w8, wzr
004cc758 c9120091 add      x9, x22, #4
004cc75c ea03082a mov      w10, w8
004cc760 4af17dd3 lsl      x10, x10, #3
004cc764 ca6a6ab8 ldr      w10, [x22, x10]
004cc768 5f010b6b cmp      w10, w11
004cc76c c0000054 b.eq     #0x4cc784
004cc770 08050011 add      w8, w8, #1
004cc774 29210091 add      x9, x9, #8
004cc778 1f01006b cmp      w8, w0
004cc77c 03ffff54 b.lo     #0x4cc75c
004cc780 27000014 b        #0x4cc81c
004cc784 280140b9 ldr      w8, [x9]
004cc788 a97001d0 adrp     x9, #0x32e2000
004cc78c 295543f9 ldr      x9, [x9, #0x6a8]
004cc790 1f050031 cmn      w8, #1
004cc794 e803881a csel     w8, wzr, w8, eq
004cc798 280500b9 str      w8, [x9, #4]
004cc79c a80240b9 ldr      w8, [x21]
004cc7a0 68faff35 cbnz     w8, #0x4cc6ec
004cc7a4 63000014 b        #0x4cc930
004cc7a8 e8030032 mov      w8, #1
004cc7ac 28010039 strb     w8, [x9]
004cc7b0 a87001d0 adrp     x8, #0x32e2000
004cc7b4 085543f9 ldr      x8, [x8, #0x6a8]
004cc7b8 1b6d01a9 stp      x27, x27, [x8, #0x10]
004cc7bc 1b6d00a9 stp      x27, x27, [x8]
004cc7c0 e00315aa mov      x0, x21
004cc7c4 af654694 bl       #0x1665e80
004cc7c8 c0faffb5 cbnz     x0, #0x4cc720
004cc7cc 14000014 b        #0x4cc81c
004cc7d0 1f550071 cmp      w8, #0x15
004cc7d4 e1000054 b.ne     #0x4cc7f0
004cc7d8 280a8052 mov      w8, #0x51
004cc7dc 1501150b add      w21, w8, w21
004cc7e0 f63b1f32 mov      w22, #0xfffe
004cc7e4 bf02176b cmp      w21, w23
004cc7e8 4beeff54 b.lt     #0x4cc5b0
004cc7ec c3010014 b        #0x4ccef8
004cc7f0 b5060011 add      w21, w21, #1
004cc7f4 f63b1f32 mov      w22, #0xfffe
004cc7f8 bf02176b cmp      w21, w23
004cc7fc abedff54 b.lt     #0x4cc5b0
004cc800 be010014 b        #0x4ccef8
004cc804 080115ab adds     x8, x8, x21
004cc808 a0000054 b.eq     #0x4cc81c
004cc80c 16014079 ldrh     w22, [x8]
004cc810 e83b1f32 mov      w8, #0xfffe
004cc814 df02086b cmp      w22, w8
004cc818 41090054 b.ne     #0x4cc940
004cc81c a80240b9 ldr      w8, [x21]
004cc820 08070034 cbz      w8, #0x4cc900
004cc824 a97001d0 adrp     x9, #0x32e2000
004cc828 295143f9 ldr      x9, [x9, #0x6a0]
004cc82c 28014039 ldrb     w8, [x9]
004cc830 08010034 cbz      w8, #0x4cc850
004cc834 a87001d0 adrp     x8, #0x32e2000
004cc838 085543f9 ldr      x8, [x8, #0x6a8]
004cc83c 080980b9 ldrsw    x8, [x8, #8]
004cc840 a806f836 tbz      w8, #0x1f, #0x4cc914
004cc844 1f050031 cmn      w8, #1
004cc848 00010054 b.eq     #0x4cc868
004cc84c 39000014 b        #0x4cc930
004cc850 e8030032 mov      w8, #1
004cc854 28010039 strb     w8, [x9]
004cc858 a87001d0 adrp     x8, #0x32e2000
004cc85c 085543f9 ldr      x8, [x8, #0x6a8]
004cc860 1b6d01a9 stp      x27, x27, [x8, #0x10]
004cc864 1b6d00a9 stp      x27, x27, [x8]
004cc868 e00315aa mov      x0, x21
004cc86c 85654694 bl       #0x1665e80
004cc870 000600b4 cbz      x0, #0x4cc930
004cc874 f70300aa mov      x23, x0
004cc878 7a654694 bl       #0x1665e60
004cc87c f60300aa mov      x22, x0
004cc880 200400b4 cbz      x0, #0x4cc904
004cc884 e00317aa mov      x0, x23
004cc888 72654694 bl       #0x1665e50
004cc88c a97001d0 adrp     x9, #0x32e2000
004cc890 295543f9 ldr      x9, [x9, #0x6a8]
004cc894 e87b1f32 mov      w8, #-2
004cc898 280900b9 str      w8, [x9, #8]
004cc89c a0040034 cbz      w0, #0x4cc930
004cc8a0 e8031f2a mov      w8, wzr
004cc8a4 c9120091 add      x9, x22, #4
004cc8a8 0b7e8752 mov      w11, #0x3bf0
004cc8ac 6b54ad72 movk     w11, #0x6aa3, lsl #16
004cc8b0 ea03082a mov      w10, w8
004cc8b4 4af17dd3 lsl      x10, x10, #3
004cc8b8 ca6a6ab8 ldr      w10, [x22, x10]
004cc8bc 5f010b6b cmp      w10, w11
004cc8c0 c0000054 b.eq     #0x4cc8d8
004cc8c4 08050011 add      w8, w8, #1
004cc8c8 29210091 add      x9, x9, #8
004cc8cc 1f01006b cmp      w8, w0
004cc8d0 03ffff54 b.lo     #0x4cc8b0
004cc8d4 17000014 b        #0x4cc930
004cc8d8 280140b9 ldr      w8, [x9]
004cc8dc a97001d0 adrp     x9, #0x32e2000
004cc8e0 295543f9 ldr      x9, [x9, #0x6a8]
004cc8e4 1f050031 cmn      w8, #1
004cc8e8 e803881a csel     w8, wzr, w8, eq
004cc8ec 280900b9 str      w8, [x9, #8]
004cc8f0 a80240b9 ldr      w8, [x21]
004cc8f4 f6031f2a mov      w22, wzr
004cc8f8 68f9ff35 cbnz     w8, #0x4cc824
004cc8fc 02000014 b        #0x4cc904
004cc900 f6031f2a mov      w22, wzr
004cc904 081f0012 and      w8, w24, #0xff
004cc908 1f090071 cmp      w8, #2
004cc90c a1010054 b.ne     #0x4cc940
004cc910 7a010014 b        #0x4ccef8
004cc914 080115ab adds     x8, x8, x21
004cc918 c0000054 b.eq     #0x4cc930
004cc91c 16014079 ldrh     w22, [x8]
004cc920 081f0012 and      w8, w24, #0xff
004cc924 1f090071 cmp      w8, #2
004cc928 c1000054 b.ne     #0x4cc940
004cc92c 73010014 b        #0x4ccef8
004cc930 f6031f2a mov      w22, wzr
004cc934 081f0012 and      w8, w24, #0xff
004cc938 1f090071 cmp      w8, #2
004cc93c e02d0054 b.eq     #0x4ccef8
004cc940 f81300b9 str      w24, [sp, #0x10]
004cc944 e0030191 add      x0, sp, #0x40
004cc948 e103162a mov      w1, w22
004cc94c d52f2a94 bl       #0xf588a0
004cc950 350340f9 ldr      x21, [x25]
004cc954 e0030191 add      x0, sp, #0x40
004cc958 4e302a94 bl       #0xf58a90
004cc95c a9f24379 ldrh     w9, [x21, #0x1f8]
004cc960 083c0012 and      w8, w0, #0xffff
004cc964 0801094b sub      w8, w8, w9
004cc968 a9da41b9 ldr      w9, [x21, #0x1d8]
004cc96c 1f01096b cmp      w8, w9
004cc970 422c0054 b.hs     #0x4ccef8
004cc974 a9f240f9 ldr      x9, [x21, #0x1e0]
004cc978 35d968f8 ldr      x21, [x9, w8, sxtw #3]
004cc97c d50000b5 cbnz     x21, #0x4cc994
004cc980 5e010014 b        #0x4ccef8
004cc984 280140b9 ldr      w8, [x9]
004cc988 1f050031 cmn      w8, #1
004cc98c e803881a csel     w8, wzr, w8, eq
004cc990 884b00b9 str      w8, [x28, #0x48]
004cc994 a80240b9 ldr      w8, [x21]
004cc998 082b0034 cbz      w8, #0x4ccef8
004cc99c a97001d0 adrp     x9, #0x32e2000
004cc9a0 293943f9 ldr      x9, [x9, #0x670]
004cc9a4 28014039 ldrb     w8, [x9]
004cc9a8 a8030034 cbz      w8, #0x4cca1c
004cc9ac 884b80b9 ldrsw    x8, [x28, #0x48]
004cc9b0 e806f836 tbz      w8, #0x1f, #0x4cca8c
004cc9b4 1f050031 cmn      w8, #1
004cc9b8 a1070054 b.ne     #0x4ccaac
004cc9bc e00315aa mov      x0, x21
004cc9c0 30654694 bl       #0x1665e80
004cc9c4 400400b4 cbz      x0, #0x4cca4c
004cc9c8 f80300aa mov      x24, x0
004cc9cc 25654694 bl       #0x1665e60
004cc9d0 e00400b4 cbz      x0, #0x4cca6c
004cc9d4 f70300aa mov      x23, x0
004cc9d8 e00318aa mov      x0, x24
004cc9dc 1d654694 bl       #0x1665e50
004cc9e0 e87b1f32 mov      w8, #-2
004cc9e4 884b00b9 str      w8, [x28, #0x48]
004cc9e8 a0040034 cbz      w0, #0x4cca7c
004cc9ec e8031f2a mov      w8, wzr
004cc9f0 e9120091 add      x9, x23, #4
004cc9f4 ea03082a mov      w10, w8
004cc9f8 4af17dd3 lsl      x10, x10, #3
004cc9fc ea6a6ab8 ldr      w10, [x23, x10]
004cca00 5f011a6b cmp      w10, w26
004cca04 00fcff54 b.eq     #0x4cc984
004cca08 08050011 add      w8, w8, #1
004cca0c 29210091 add      x9, x9, #8
004cca10 1f01006b cmp      w8, w0
004cca14 03ffff54 b.lo     #0x4cc9f4
004cca18 11000014 b        #0x4cca5c
004cca1c e8030032 mov      w8, #1
004cca20 28010039 strb     w8, [x9]
004cca24 9b0300f9 str      x27, [x28]
004cca28 9bef04a9 stp      x27, x27, [x28, #0x48]
004cca2c 9b5b00b9 str      w27, [x28, #0x58]
004cca30 9bef03a9 stp      x27, x27, [x28, #0x38]
004cca34 9bef02a9 stp      x27, x27, [x28, #0x28]
004cca38 9bef01a9 stp      x27, x27, [x28, #0x18]
004cca3c 9bef00a9 stp      x27, x27, [x28, #8]
004cca40 e00315aa mov      x0, x21
004cca44 0f654694 bl       #0x1665e80
004cca48 00fcffb5 cbnz     x0, #0x4cc9c8
004cca4c ff0b00b9 str      wzr, [sp, #8]
004cca50 a80240b9 ldr      w8, [x21]
004cca54 88040035 cbnz     w8, #0x4ccae4
004cca58 28010014 b        #0x4ccef8
004cca5c ff0b00b9 str      wzr, [sp, #8]
004cca60 a80240b9 ldr      w8, [x21]
004cca64 08040035 cbnz     w8, #0x4ccae4
004cca68 24010014 b        #0x4ccef8
004cca6c ff0b00b9 str      wzr, [sp, #8]
004cca70 a80240b9 ldr      w8, [x21]
004cca74 88030035 cbnz     w8, #0x4ccae4
004cca78 20010014 b        #0x4ccef8
004cca7c ff0b00b9 str      wzr, [sp, #8]
004cca80 a80240b9 ldr      w8, [x21]
004cca84 08030035 cbnz     w8, #0x4ccae4
004cca88 1c010014 b        #0x4ccef8
004cca8c 080115ab adds     x8, x8, x21
004cca90 60010054 b.eq     #0x4ccabc
004cca94 09014039 ldrb     w9, [x8]
004cca98 e81340b9 ldr      w8, [sp, #0x10]
004cca9c 3f01286b cmp      w9, w8, uxtb
004ccaa0 e90b00b9 str      w9, [sp, #8]
004ccaa4 c1010054 b.ne     #0x4ccadc
004ccaa8 14010014 b        #0x4ccef8
004ccaac ff0b00b9 str      wzr, [sp, #8]
004ccab0 a80240b9 ldr      w8, [x21]
004ccab4 88010035 cbnz     w8, #0x4ccae4
004ccab8 10010014 b        #0x4ccef8
004ccabc ff0b00b9 str      wzr, [sp, #8]
004ccac0 a80240b9 ldr      w8, [x21]
004ccac4 08010035 cbnz     w8, #0x4ccae4
004ccac8 0c010014 b        #0x4ccef8
004ccacc 280140b9 ldr      w8, [x9]
004ccad0 1f050031 cmn      w8, #1
004ccad4 e803881a csel     w8, wzr, w8, eq
004ccad8 882f00b9 str      w8, [x28, #0x2c]
004ccadc a80240b9 ldr      w8, [x21]
004ccae0 c8200034 cbz      w8, #0x4ccef8
004ccae4 a87001d0 adrp     x8, #0x32e2000
004ccae8 083943f9 ldr      x8, [x8, #0x670]
004ccaec 09014039 ldrb     w9, [x8]
004ccaf0 a9030034 cbz      w9, #0x4ccb64
004ccaf4 882f40b9 ldr      w8, [x28, #0x2c]
004ccaf8 0805f836 tbz      w8, #0x1f, #0x4ccb98
004ccafc 1f050031 cmn      w8, #1
004ccb00 c1060054 b.ne     #0x4ccbd8
004ccb04 e00315aa mov      x0, x21
004ccb08 de644694 bl       #0x1665e80
004ccb0c 600600b4 cbz      x0, #0x4ccbd8
004ccb10 f80300aa mov      x24, x0
004ccb14 d3644694 bl       #0x1665e60
004ccb18 000600b4 cbz      x0, #0x4ccbd8
004ccb1c f70300aa mov      x23, x0
004ccb20 e00318aa mov      x0, x24
004ccb24 cb644694 bl       #0x1665e50
004ccb28 e87b1f32 mov      w8, #-2
004ccb2c 882f00b9 str      w8, [x28, #0x2c]
004ccb30 40050034 cbz      w0, #0x4ccbd8
004ccb34 e8031f2a mov      w8, wzr
004ccb38 e9120091 add      x9, x23, #4
004ccb3c ea03082a mov      w10, w8
004ccb40 4af17dd3 lsl      x10, x10, #3
004ccb44 ea6a6ab8 ldr      w10, [x23, x10]
004ccb48 5f01136b cmp      w10, w19
004ccb4c 00fcff54 b.eq     #0x4ccacc
004ccb50 08050011 add      w8, w8, #1
004ccb54 29210091 add      x9, x9, #8
004ccb58 1f01006b cmp      w8, w0
004ccb5c 03ffff54 b.lo     #0x4ccb3c
004ccb60 1e000014 b        #0x4ccbd8
004ccb64 e9030032 mov      w9, #1
004ccb68 09010039 strb     w9, [x8]
004ccb6c 9b0300f9 str      x27, [x28]
004ccb70 9bef04a9 stp      x27, x27, [x28, #0x48]
004ccb74 9b5b00b9 str      w27, [x28, #0x58]
004ccb78 9bef03a9 stp      x27, x27, [x28, #0x38]
004ccb7c 9bef02a9 stp      x27, x27, [x28, #0x28]
004ccb80 9bef01a9 stp      x27, x27, [x28, #0x18]
004ccb84 9bef00a9 stp      x27, x27, [x28, #8]
004ccb88 e00315aa mov      x0, x21
004ccb8c bd644694 bl       #0x1665e80
004ccb90 00fcffb5 cbnz     x0, #0x4ccb10
004ccb94 11000014 b        #0x4ccbd8
004ccb98 0a7d4093 sxtw     x10, w8
004ccb9c 4a0115ab adds     x10, x10, x21
004ccba0 c0010054 b.eq     #0x4ccbd8
004ccba4 4a01c079 ldrsh    w10, [x10]
004ccba8 5f090031 cmn      w10, #2
004ccbac 60010054 b.eq     #0x4ccbd8
004ccbb0 aa0240b9 ldr      w10, [x21]
004ccbb4 ca170034 cbz      w10, #0x4cceac
004ccbb8 f81340b9 ldr      w24, [sp, #0x10]
004ccbbc 3f1d0072 tst      w9, #0xff
004ccbc0 210f0054 b.ne     #0x4ccda4
004ccbc4 7c000014 b        #0x4ccdb4
004ccbc8 280140b9 ldr      w8, [x9]
004ccbcc 1f050031 cmn      w8, #1
004ccbd0 e803881a csel     w8, wzr, w8, eq
004ccbd4 883b00b9 str      w8, [x28, #0x38]
004ccbd8 a80240b9 ldr      w8, [x21]
004ccbdc e8180034 cbz      w8, #0x4ccef8
004ccbe0 a87001d0 adrp     x8, #0x32e2000
004ccbe4 083943f9 ldr      x8, [x8, #0x670]
004ccbe8 09014039 ldrb     w9, [x8]
004ccbec a9030034 cbz      w9, #0x4ccc60
004ccbf0 883b40b9 ldr      w8, [x28, #0x38]
004ccbf4 0805f836 tbz      w8, #0x1f, #0x4ccc94
004ccbf8 1f050031 cmn      w8, #1
004ccbfc e1170054 b.ne     #0x4ccef8
004ccc00 e00315aa mov      x0, x21
004ccc04 9f644694 bl       #0x1665e80
004ccc08 801700b4 cbz      x0, #0x4ccef8
004ccc0c f80300aa mov      x24, x0
004ccc10 94644694 bl       #0x1665e60
004ccc14 201700b4 cbz      x0, #0x4ccef8
004ccc18 f70300aa mov      x23, x0
004ccc1c e00318aa mov      x0, x24
004ccc20 8c644694 bl       #0x1665e50
004ccc24 e87b1f32 mov      w8, #-2
004ccc28 883b00b9 str      w8, [x28, #0x38]
004ccc2c 60160034 cbz      w0, #0x4ccef8
004ccc30 e8031f2a mov      w8, wzr
004ccc34 e9120091 add      x9, x23, #4
004ccc38 ea03082a mov      w10, w8
004ccc3c 4af17dd3 lsl      x10, x10, #3
004ccc40 ea6a6ab8 ldr      w10, [x23, x10]
004ccc44 5f01146b cmp      w10, w20
004ccc48 00fcff54 b.eq     #0x4ccbc8
004ccc4c 08050011 add      w8, w8, #1
004ccc50 29210091 add      x9, x9, #8
004ccc54 1f01006b cmp      w8, w0
004ccc58 03ffff54 b.lo     #0x4ccc38
004ccc5c a7000014 b        #0x4ccef8
004ccc60 e9030032 mov      w9, #1
004ccc64 09010039 strb     w9, [x8]
004ccc68 9b0300f9 str      x27, [x28]
004ccc6c 9bef04a9 stp      x27, x27, [x28, #0x48]
004ccc70 9b5b00b9 str      w27, [x28, #0x58]
004ccc74 9bef03a9 stp      x27, x27, [x28, #0x38]
004ccc78 9bef02a9 stp      x27, x27, [x28, #0x28]
004ccc7c 9bef01a9 stp      x27, x27, [x28, #0x18]
004ccc80 9bef00a9 stp      x27, x27, [x28, #8]
004ccc84 e00315aa mov      x0, x21
004ccc88 7e644694 bl       #0x1665e80
004ccc8c 00fcffb5 cbnz     x0, #0x4ccc0c
004ccc90 9a000014 b        #0x4ccef8
004ccc94 0a7d4093 sxtw     x10, w8
004ccc98 4a0115ab adds     x10, x10, x21
004ccc9c e0120054 b.eq     #0x4ccef8
004ccca0 4a01c079 ldrsh    w10, [x10]
004ccca4 5f090031 cmn      w10, #2
004ccca8 80120054 b.eq     #0x4ccef8
004cccac aa0240b9 ldr      w10, [x21]
004cccb0 ea0f0034 cbz      w10, #0x4cceac
004cccb4 f81340b9 ldr      w24, [sp, #0x10]
004cccb8 3f1d0072 tst      w9, #0xff
004cccbc e1000054 b.ne     #0x4cccd8
004cccc0 0a000014 b        #0x4ccce8
004cccc4 a97001d0 adrp     x9, #0x32e2000
004cccc8 293943f9 ldr      x9, [x9, #0x670]
004ccccc 29014039 ldrb     w9, [x9]
004cccd0 3f1d0072 tst      w9, #0xff
004cccd4 a0000054 b.eq     #0x4ccce8
004cccd8 280cf836 tbz      w8, #0x1f, #0x4cce5c
004cccdc 1f050031 cmn      w8, #1
004ccce0 a0010054 b.eq     #0x4ccd14
004ccce4 65000014 b        #0x4cce78
004ccce8 a87001d0 adrp     x8, #0x32e2000
004cccec 083943f9 ldr      x8, [x8, #0x670]
004cccf0 e9030032 mov      w9, #1
004cccf4 9bef04a9 stp      x27, x27, [x28, #0x48]
004cccf8 09010039 strb     w9, [x8]
004cccfc 9bef03a9 stp      x27, x27, [x28, #0x38]
004ccd00 9b0300f9 str      x27, [x28]
004ccd04 9bef02a9 stp      x27, x27, [x28, #0x28]
004ccd08 9b5b00b9 str      w27, [x28, #0x58]
004ccd0c 9bef01a9 stp      x27, x27, [x28, #0x18]
004ccd10 9bef00a9 stp      x27, x27, [x28, #8]
004ccd14 e00315aa mov      x0, x21
004ccd18 5a644694 bl       #0x1665e80
004ccd1c e00a00b4 cbz      x0, #0x4cce78
004ccd20 f70300aa mov      x23, x0
004ccd24 4f644694 bl       #0x1665e60
004ccd28 800a00b4 cbz      x0, #0x4cce78
004ccd2c f60300aa mov      x22, x0
004ccd30 e00317aa mov      x0, x23
004ccd34 47644694 bl       #0x1665e50
004ccd38 e87b1f32 mov      w8, #-2
004ccd3c 883b00b9 str      w8, [x28, #0x38]
004ccd40 c0090034 cbz      w0, #0x4cce78
004ccd44 e8031f2a mov      w8, wzr
004ccd48 c9120091 add      x9, x22, #4
004ccd4c ea03082a mov      w10, w8
004ccd50 4af17dd3 lsl      x10, x10, #3
004ccd54 ca6a6ab8 ldr      w10, [x22, x10]
004ccd58 5f01146b cmp      w10, w20
004ccd5c c0000054 b.eq     #0x4ccd74
004ccd60 08050011 add      w8, w8, #1
004ccd64 29210091 add      x9, x9, #8
004ccd68 1f01006b cmp      w8, w0
004ccd6c 03ffff54 b.lo     #0x4ccd4c
004ccd70 42000014 b        #0x4cce78
004ccd74 280140b9 ldr      w8, [x9]
004ccd78 1f050031 cmn      w8, #1
004ccd7c e803881a csel     w8, wzr, w8, eq
004ccd80 883b00b9 str      w8, [x28, #0x38]
004ccd84 a90240b9 ldr      w9, [x21]
004ccd88 e9f9ff35 cbnz     w9, #0x4cccc4
004ccd8c 3b000014 b        #0x4cce78
004ccd90 a97001d0 adrp     x9, #0x32e2000
004ccd94 293943f9 ldr      x9, [x9, #0x670]
004ccd98 29014039 ldrb     w9, [x9]
004ccd9c 3f1d0072 tst      w9, #0xff
004ccda0 a0000054 b.eq     #0x4ccdb4
004ccda4 4807f836 tbz      w8, #0x1f, #0x4cce8c
004ccda8 1f050031 cmn      w8, #1
004ccdac a0010054 b.eq     #0x4ccde0
004ccdb0 32000014 b        #0x4cce78
004ccdb4 a87001d0 adrp     x8, #0x32e2000
004ccdb8 083943f9 ldr      x8, [x8, #0x670]
004ccdbc e9030032 mov      w9, #1
004ccdc0 9bef04a9 stp      x27, x27, [x28, #0x48]
004ccdc4 09010039 strb     w9, [x8]
004ccdc8 9bef03a9 stp      x27, x27, [x28, #0x38]
004ccdcc 9b0300f9 str      x27, [x28]
004ccdd0 9bef02a9 stp      x27, x27, [x28, #0x28]
004ccdd4 9b5b00b9 str      w27, [x28, #0x58]
004ccdd8 9bef01a9 stp      x27, x27, [x28, #0x18]
004ccddc 9bef00a9 stp      x27, x27, [x28, #8]
004ccde0 e00315aa mov      x0, x21
004ccde4 27644694 bl       #0x1665e80
004ccde8 800400b4 cbz      x0, #0x4cce78
004ccdec f70300aa mov      x23, x0
004ccdf0 1c644694 bl       #0x1665e60
004ccdf4 200400b4 cbz      x0, #0x4cce78
004ccdf8 f60300aa mov      x22, x0
004ccdfc e00317aa mov      x0, x23
004cce00 14644694 bl       #0x1665e50
004cce04 e87b1f32 mov      w8, #-2
004cce08 882f00b9 str      w8, [x28, #0x2c]
004cce0c 60030034 cbz      w0, #0x4cce78
004cce10 e8031f2a mov      w8, wzr
004cce14 c9120091 add      x9, x22, #4
004cce18 ea03082a mov      w10, w8
004cce1c 4af17dd3 lsl      x10, x10, #3
004cce20 ca6a6ab8 ldr      w10, [x22, x10]
004cce24 5f01136b cmp      w10, w19
004cce28 c0000054 b.eq     #0x4cce40
004cce2c 08050011 add      w8, w8, #1
004cce30 29210091 add      x9, x9, #8
004cce34 1f01006b cmp      w8, w0
004cce38 03ffff54 b.lo     #0x4cce18
004cce3c 0f000014 b        #0x4cce78
004cce40 280140b9 ldr      w8, [x9]
004cce44 1f050031 cmn      w8, #1
004cce48 e803881a csel     w8, wzr, w8, eq
004cce4c 882f00b9 str      w8, [x28, #0x2c]
004cce50 a90240b9 ldr      w9, [x21]
004cce54 e9f9ff35 cbnz     w9, #0x4ccd90
004cce58 08000014 b        #0x4cce78
004cce5c a8c228ab adds     x8, x21, w8, sxtw
004cce60 c0000054 b.eq     #0x4cce78
004cce64 16014079 ldrh     w22, [x8]
004cce68 e80b40b9 ldr      w8, [sp, #8]
004cce6c 1f01386b cmp      w8, w24, uxtb
004cce70 a1d6ff54 b.ne     #0x4cc944
004cce74 13000014 b        #0x4ccec0
004cce78 f63b1f32 mov      w22, #0xfffe
004cce7c e80b40b9 ldr      w8, [sp, #8]
004cce80 1f01386b cmp      w8, w24, uxtb
004cce84 01d6ff54 b.ne     #0x4cc944
004cce88 0e000014 b        #0x4ccec0
004cce8c a8c228ab adds     x8, x21, w8, sxtw
004cce90 e0000054 b.eq     #0x4cceac
004cce94 16014079 ldrh     w22, [x8]
004cce98 f81340b9 ldr      w24, [sp, #0x10]
004cce9c e80b40b9 ldr      w8, [sp, #8]
004ccea0 1f01386b cmp      w8, w24, uxtb
004ccea4 01d5ff54 b.ne     #0x4cc944
004ccea8 06000014 b        #0x4ccec0
004cceac f81340b9 ldr      w24, [sp, #0x10]
004cceb0 f63b1f32 mov      w22, #0xfffe
004cceb4 e80b40b9 ldr      w8, [sp, #8]
004cceb8 1f01386b cmp      w8, w24, uxtb
004ccebc 41d4ff54 b.ne     #0x4cc944
004ccec0 f70f40b9 ldr      w23, [sp, #0xc]
004ccec4 f51740b9 ldr      w21, [sp, #0x14]
004ccec8 f63b1f32 mov      w22, #0xfffe
004ccecc bf02176b cmp      w21, w23
004cced0 0bb7ff54 b.lt     #0x4cc5b0
004cced4 09000014 b        #0x4ccef8
004cced8 00010891 add      x0, x8, #0x200
004ccedc e5654694 bl       #0x1666670
004ccee0 a00000b4 cbz      x0, #0x4ccef4
004ccee4 d3634694 bl       #0x1665e30
004ccee8 f703002a mov      w23, w0
004cceec 1f040071 cmp      w0, #1
004ccef0 4ab3ff54 b.ge     #0x4cc558
004ccef4 f63b1f32 mov      w22, #0xfffe
004ccef8 e003162a mov      w0, w22
004ccefc fd7b4aa9 ldp      x29, x30, [sp, #0xa0]
004ccf00 f44f49a9 ldp      x20, x19, [sp, #0x90]
004ccf04 f65748a9 ldp      x22, x21, [sp, #0x80]
004ccf08 f85f47a9 ldp      x24, x23, [sp, #0x70]
004ccf0c fa6746a9 ldp      x26, x25, [sp, #0x60]
004ccf10 fc6f45a9 ldp      x28, x27, [sp, #0x50]
004ccf14 ffc30291 add      sp, sp, #0xb0
004ccf18 c0035fd6 ret      
