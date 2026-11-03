; coast_grid_zero_init ELF 0x4de810 size=80 sha256=2c362c3d4af843275dad116428a7c018ff888ce0efac3dfec858837750ee6a73
004de810 e8031faa mov      x8, xzr
004de814 1f7c08a9 stp      xzr, xzr, [x0, #0x80]
004de818 1f7c07a9 stp      xzr, xzr, [x0, #0x70]
004de81c 1f7c06a9 stp      xzr, xzr, [x0, #0x60]
004de820 1f7c05a9 stp      xzr, xzr, [x0, #0x50]
004de824 1f7c04a9 stp      xzr, xzr, [x0, #0x40]
004de828 1f7c03a9 stp      xzr, xzr, [x0, #0x30]
004de82c 1f7c02a9 stp      xzr, xzr, [x0, #0x20]
004de830 1f7c01a9 stp      xzr, xzr, [x0, #0x10]
004de834 1f7c00a9 stp      xzr, xzr, [x0]
004de838 097d7f93 sbfiz    x9, x8, #1, #0x20
004de83c 08050011 add      w8, w8, #1
004de840 1f682978 strh     wzr, [x0, x9]
004de844 097d7f93 sbfiz    x9, x8, #1, #0x20
004de848 1f682978 strh     wzr, [x0, x9]
004de84c 09050091 add      x9, x8, #1
004de850 287d4092 and      x8, x9, #0xffffffff
004de854 3f210171 cmp      w9, #0x48
004de858 01ffff54 b.ne     #0x4de838
004de85c c0035fd6 ret

; setup_enable_flag_copy ELF 0x4de9a0 size=8 sha256=f40f917bec7a5e49fface58890afdec1bd2dd554f06991a76e10b145eae2525c
004de9a0 01000079 strh     w1, [x0]
004de9a4 c0035fd6 ret

; template_slot_selection ELF 0x4dea40 size=1136 sha256=183750b04468288740439614cdfee1e3476ccb9ae09e7318ab306b82a23f1b27
004dea40 ff8303d1 sub      sp, sp, #0xe0
004dea44 f44f0ca9 stp      x20, x19, [sp, #0xc0]
004dea48 fd7b0da9 stp      x29, x30, [sp, #0xd0]
004dea4c fd430391 add      x29, sp, #0xd0
004dea50 f30301aa mov      x19, x1
004dea54 01004079 ldrh     w1, [x0]
004dea58 a08300d1 sub      x0, x29, #0x20
004dea5c ddcd0194 bl       #0x5521d0
004dea60 a8835ef8 ldur     x8, [x29, #-0x18]
004dea64 682100b4 cbz      x8, #0x4dee90
004dea68 a08300d1 sub      x0, x29, #0x20
004dea6c 09ce0194 bl       #0x552290
004dea70 a0831db8 stur     w0, [x29, #-0x28]
004dea74 e00313aa mov      x0, x19
004dea78 e1030032 mov      w1, #1
004dea7c e2030032 mov      w2, #1
004dea80 84ffff97 bl       #0x4de890
004dea84 a00000b4 cbz      x0, #0x4dea98
004dea88 a1a300d1 sub      x1, x29, #0x28
004dea8c f40300aa mov      x20, x0
004dea90 08050094 bl       #0x4dfeb0
004dea94 80020079 strh     w0, [x20]
004dea98 a08300d1 sub      x0, x29, #0x20
004dea9c 11ce0194 bl       #0x5522e0
004deaa0 a0031db8 stur     w0, [x29, #-0x30]
004deaa4 e00313aa mov      x0, x19
004deaa8 e1031f32 mov      w1, #2
004deaac e2030032 mov      w2, #1
004deab0 78ffff97 bl       #0x4de890
004deab4 a00000b4 cbz      x0, #0x4deac8
004deab8 a1c300d1 sub      x1, x29, #0x30
004deabc f40300aa mov      x20, x0
004deac0 fc040094 bl       #0x4dfeb0
004deac4 80020079 strh     w0, [x20]
004deac8 a08300d1 sub      x0, x29, #0x20
004deacc 19ce0194 bl       #0x552330
004dead0 a0831cb8 stur     w0, [x29, #-0x38]
004dead4 e00313aa mov      x0, x19
004dead8 e1070032 mov      w1, #3
004deadc e2030032 mov      w2, #1
004deae0 6cffff97 bl       #0x4de890
004deae4 a00000b4 cbz      x0, #0x4deaf8
004deae8 a1e300d1 sub      x1, x29, #0x38
004deaec f40300aa mov      x20, x0
004deaf0 f0040094 bl       #0x4dfeb0
004deaf4 80020079 strh     w0, [x20]
004deaf8 a08300d1 sub      x0, x29, #0x20
004deafc 21ce0194 bl       #0x552380
004deb00 a0031cb8 stur     w0, [x29, #-0x40]
004deb04 e00313aa mov      x0, x19
004deb08 e1031e32 mov      w1, #4
004deb0c e2030032 mov      w2, #1
004deb10 60ffff97 bl       #0x4de890
004deb14 a00000b4 cbz      x0, #0x4deb28
004deb18 a10301d1 sub      x1, x29, #0x40
004deb1c f40300aa mov      x20, x0
004deb20 e4040094 bl       #0x4dfeb0
004deb24 80020079 strh     w0, [x20]
004deb28 a08300d1 sub      x0, x29, #0x20
004deb2c 29ce0194 bl       #0x5523d0
004deb30 a0831bb8 stur     w0, [x29, #-0x48]
004deb34 a1008052 mov      w1, #5
004deb38 e00313aa mov      x0, x19
004deb3c e2030032 mov      w2, #1
004deb40 54ffff97 bl       #0x4de890
004deb44 a00000b4 cbz      x0, #0x4deb58
004deb48 a12301d1 sub      x1, x29, #0x48
004deb4c f40300aa mov      x20, x0
004deb50 d8040094 bl       #0x4dfeb0
004deb54 80020079 strh     w0, [x20]
004deb58 a08300d1 sub      x0, x29, #0x20
004deb5c 31ce0194 bl       #0x552420
004deb60 a0031bb8 stur     w0, [x29, #-0x50]
004deb64 e00313aa mov      x0, x19
004deb68 e1071f32 mov      w1, #6
004deb6c e2030032 mov      w2, #1
004deb70 48ffff97 bl       #0x4de890
004deb74 a00000b4 cbz      x0, #0x4deb88
004deb78 a14301d1 sub      x1, x29, #0x50
004deb7c f40300aa mov      x20, x0
004deb80 cc040094 bl       #0x4dfeb0
004deb84 80020079 strh     w0, [x20]
004deb88 a08300d1 sub      x0, x29, #0x20
004deb8c 39ce0194 bl       #0x552470
004deb90 a0831ab8 stur     w0, [x29, #-0x58]
004deb94 e00313aa mov      x0, x19
004deb98 e10b0032 mov      w1, #7
004deb9c e2030032 mov      w2, #1
004deba0 3cffff97 bl       #0x4de890
004deba4 a00000b4 cbz      x0, #0x4debb8
004deba8 a16301d1 sub      x1, x29, #0x58
004debac f40300aa mov      x20, x0
004debb0 c0040094 bl       #0x4dfeb0
004debb4 80020079 strh     w0, [x20]
004debb8 a08300d1 sub      x0, x29, #0x20
004debbc 41ce0194 bl       #0x5524c0
004debc0 a0031ab8 stur     w0, [x29, #-0x60]
004debc4 e00313aa mov      x0, x19
004debc8 e1030032 mov      w1, #1
004debcc e2031f32 mov      w2, #2
004debd0 30ffff97 bl       #0x4de890
004debd4 a00000b4 cbz      x0, #0x4debe8
004debd8 a18301d1 sub      x1, x29, #0x60
004debdc f40300aa mov      x20, x0
004debe0 b4040094 bl       #0x4dfeb0
004debe4 80020079 strh     w0, [x20]
004debe8 a08300d1 sub      x0, x29, #0x20
004debec 49ce0194 bl       #0x552510
004debf0 e06b00b9 str      w0, [sp, #0x68]
004debf4 e00313aa mov      x0, x19
004debf8 e1030032 mov      w1, #1
004debfc e2070032 mov      w2, #3
004dec00 24ffff97 bl       #0x4de890
004dec04 a00000b4 cbz      x0, #0x4dec18
004dec08 e1a30191 add      x1, sp, #0x68
004dec0c f40300aa mov      x20, x0
004dec10 a8040094 bl       #0x4dfeb0
004dec14 80020079 strh     w0, [x20]
004dec18 a08300d1 sub      x0, x29, #0x20
004dec1c 51ce0194 bl       #0x552560
004dec20 e06300b9 str      w0, [sp, #0x60]
004dec24 e00313aa mov      x0, x19
004dec28 e1030032 mov      w1, #1
004dec2c e2031e32 mov      w2, #4
004dec30 18ffff97 bl       #0x4de890
004dec34 a00000b4 cbz      x0, #0x4dec48
004dec38 e1830191 add      x1, sp, #0x60
004dec3c f40300aa mov      x20, x0
004dec40 9c040094 bl       #0x4dfeb0
004dec44 80020079 strh     w0, [x20]
004dec48 a08300d1 sub      x0, x29, #0x20
004dec4c 59ce0194 bl       #0x5525b0
004dec50 e05b00b9 str      w0, [sp, #0x58]
004dec54 a2008052 mov      w2, #5
004dec58 e00313aa mov      x0, x19
004dec5c e1030032 mov      w1, #1
004dec60 0cffff97 bl       #0x4de890
004dec64 a00000b4 cbz      x0, #0x4dec78
004dec68 e1630191 add      x1, sp, #0x58
004dec6c f40300aa mov      x20, x0
004dec70 90040094 bl       #0x4dfeb0
004dec74 80020079 strh     w0, [x20]
004dec78 a08300d1 sub      x0, x29, #0x20
004dec7c 61ce0194 bl       #0x552600
004dec80 e05300b9 str      w0, [sp, #0x50]
004dec84 e00313aa mov      x0, x19
004dec88 e10b0032 mov      w1, #7
004dec8c e2031f32 mov      w2, #2
004dec90 00ffff97 bl       #0x4de890
004dec94 a00000b4 cbz      x0, #0x4deca8
004dec98 e1430191 add      x1, sp, #0x50
004dec9c f40300aa mov      x20, x0
004deca0 84040094 bl       #0x4dfeb0
004deca4 80020079 strh     w0, [x20]
004deca8 a08300d1 sub      x0, x29, #0x20
004decac 69ce0194 bl       #0x552650
004decb0 e04b00b9 str      w0, [sp, #0x48]
004decb4 e00313aa mov      x0, x19
004decb8 e10b0032 mov      w1, #7
004decbc e2070032 mov      w2, #3
004decc0 f4feff97 bl       #0x4de890
004decc4 a00000b4 cbz      x0, #0x4decd8
004decc8 e1230191 add      x1, sp, #0x48
004deccc f40300aa mov      x20, x0
004decd0 78040094 bl       #0x4dfeb0
004decd4 80020079 strh     w0, [x20]
004decd8 a08300d1 sub      x0, x29, #0x20
004decdc 71ce0194 bl       #0x5526a0
004dece0 e04300b9 str      w0, [sp, #0x40]
004dece4 e00313aa mov      x0, x19
004dece8 e10b0032 mov      w1, #7
004decec e2031e32 mov      w2, #4
004decf0 e8feff97 bl       #0x4de890
004decf4 a00000b4 cbz      x0, #0x4ded08
004decf8 e1030191 add      x1, sp, #0x40
004decfc f40300aa mov      x20, x0
004ded00 6c040094 bl       #0x4dfeb0
004ded04 80020079 strh     w0, [x20]
004ded08 a08300d1 sub      x0, x29, #0x20
004ded0c 79ce0194 bl       #0x5526f0
004ded10 e03b00b9 str      w0, [sp, #0x38]
004ded14 a2008052 mov      w2, #5
004ded18 e00313aa mov      x0, x19
004ded1c e10b0032 mov      w1, #7
004ded20 dcfeff97 bl       #0x4de890
004ded24 a00000b4 cbz      x0, #0x4ded38
004ded28 e1e30091 add      x1, sp, #0x38
004ded2c f40300aa mov      x20, x0
004ded30 60040094 bl       #0x4dfeb0
004ded34 80020079 strh     w0, [x20]
004ded38 a08300d1 sub      x0, x29, #0x20
004ded3c 81ce0194 bl       #0x552740
004ded40 e03300b9 str      w0, [sp, #0x30]
004ded44 e00313aa mov      x0, x19
004ded48 e1030032 mov      w1, #1
004ded4c e2071f32 mov      w2, #6
004ded50 d0feff97 bl       #0x4de890
004ded54 a00000b4 cbz      x0, #0x4ded68
004ded58 e1c30091 add      x1, sp, #0x30
004ded5c f40300aa mov      x20, x0
004ded60 54040094 bl       #0x4dfeb0
004ded64 80020079 strh     w0, [x20]
004ded68 a08300d1 sub      x0, x29, #0x20
004ded6c 89ce0194 bl       #0x552790
004ded70 e02b00b9 str      w0, [sp, #0x28]
004ded74 e00313aa mov      x0, x19
004ded78 e1031f32 mov      w1, #2
004ded7c e2071f32 mov      w2, #6
004ded80 c4feff97 bl       #0x4de890
004ded84 a00000b4 cbz      x0, #0x4ded98
004ded88 e1a30091 add      x1, sp, #0x28
004ded8c f40300aa mov      x20, x0
004ded90 48040094 bl       #0x4dfeb0
004ded94 80020079 strh     w0, [x20]
004ded98 a08300d1 sub      x0, x29, #0x20
004ded9c 91ce0194 bl       #0x5527e0
004deda0 e02300b9 str      w0, [sp, #0x20]
004deda4 e00313aa mov      x0, x19
004deda8 e1070032 mov      w1, #3
004dedac e2071f32 mov      w2, #6
004dedb0 b8feff97 bl       #0x4de890
004dedb4 a00000b4 cbz      x0, #0x4dedc8
004dedb8 e1830091 add      x1, sp, #0x20
004dedbc f40300aa mov      x20, x0
004dedc0 3c040094 bl       #0x4dfeb0
004dedc4 80020079 strh     w0, [x20]
004dedc8 a08300d1 sub      x0, x29, #0x20
004dedcc 99ce0194 bl       #0x552830
004dedd0 e01b00b9 str      w0, [sp, #0x18]
004dedd4 e00313aa mov      x0, x19
004dedd8 e1031e32 mov      w1, #4
004deddc e2071f32 mov      w2, #6
004dede0 acfeff97 bl       #0x4de890
004dede4 a00000b4 cbz      x0, #0x4dedf8
004dede8 e1630091 add      x1, sp, #0x18
004dedec f40300aa mov      x20, x0
004dedf0 30040094 bl       #0x4dfeb0
004dedf4 80020079 strh     w0, [x20]
004dedf8 a08300d1 sub      x0, x29, #0x20
004dedfc a1ce0194 bl       #0x552880
004dee00 e01300b9 str      w0, [sp, #0x10]
004dee04 a1008052 mov      w1, #5
004dee08 e00313aa mov      x0, x19
004dee0c e2071f32 mov      w2, #6
004dee10 a0feff97 bl       #0x4de890
004dee14 a00000b4 cbz      x0, #0x4dee28
004dee18 e1430091 add      x1, sp, #0x10
004dee1c f40300aa mov      x20, x0
004dee20 24040094 bl       #0x4dfeb0
004dee24 80020079 strh     w0, [x20]
004dee28 a08300d1 sub      x0, x29, #0x20
004dee2c a9ce0194 bl       #0x5528d0
004dee30 e00b00b9 str      w0, [sp, #8]
004dee34 e00313aa mov      x0, x19
004dee38 e1071f32 mov      w1, #6
004dee3c e2071f32 mov      w2, #6
004dee40 94feff97 bl       #0x4de890
004dee44 a00000b4 cbz      x0, #0x4dee58
004dee48 e1230091 add      x1, sp, #8
004dee4c f40300aa mov      x20, x0
004dee50 18040094 bl       #0x4dfeb0
004dee54 80020079 strh     w0, [x20]
004dee58 a08300d1 sub      x0, x29, #0x20
004dee5c b1ce0194 bl       #0x552920
004dee60 e00300b9 str      w0, [sp]
004dee64 e00313aa mov      x0, x19
004dee68 e10b0032 mov      w1, #7
004dee6c e2071f32 mov      w2, #6
004dee70 88feff97 bl       #0x4de890
004dee74 a00000b4 cbz      x0, #0x4dee88
004dee78 e1030091 mov      x1, sp
004dee7c f30300aa mov      x19, x0
004dee80 0c040094 bl       #0x4dfeb0
004dee84 60020079 strh     w0, [x19]
004dee88 f3030032 mov      w19, #1
004dee8c 02000014 b        #0x4dee94
004dee90 f3031f2a mov      w19, wzr
004dee94 a08300d1 sub      x0, x29, #0x20
004dee98 e2cc0194 bl       #0x552220
004dee9c e003132a mov      w0, w19
004deea0 fd7b4da9 ldp      x29, x30, [sp, #0xd0]
004deea4 f44f4ca9 ldp      x20, x19, [sp, #0xc0]
004deea8 ff830391 add      sp, sp, #0xe0
004deeac c0035fd6 ret

; outside_sea_edge_assembly ELF 0x4deeb0 size=3576 sha256=dd7b3e68701f5e1f4f0c77732dda2490c41e45fda581837f29651a8b96fca4ea
004deeb0 ff0301d1 sub      sp, sp, #0x40
004deeb4 f50b00f9 str      x21, [sp, #0x10]
004deeb8 f44f02a9 stp      x20, x19, [sp, #0x20]
004deebc fd7b03a9 stp      x29, x30, [sp, #0x30]
004deec0 fdc30091 add      x29, sp, #0x30
004deec4 f30301aa mov      x19, x1
004deec8 e00301aa mov      x0, x1
004deecc e1031d32 mov      w1, #8
004deed0 e2030032 mov      w2, #1
004deed4 6ffeff97 bl       #0x4de890
004deed8 f40300aa mov      x20, x0
004deedc e00313aa mov      x0, x19
004deee0 e10b0032 mov      w1, #7
004deee4 e2030032 mov      w2, #1
004deee8 6afeff97 bl       #0x4de890
004deeec b40100b4 cbz      x20, #0x4def20
004deef0 800100b4 cbz      x0, #0x4def20
004deef4 01004079 ldrh     w1, [x0]
004deef8 e0030091 mov      x0, sp
004deefc 3dcb0194 bl       #0x551bf0
004def00 e0030091 mov      x0, sp
004def04 73cb0194 bl       #0x551cd0
004def08 e1630091 add      x1, sp, #0x18
004def0c e01b00b9 str      w0, [sp, #0x18]
004def10 b0040094 bl       #0x4e01d0
004def14 80020079 strh     w0, [x20]
004def18 e0030091 mov      x0, sp
004def1c 49cb0194 bl       #0x551c40
004def20 e00313aa mov      x0, x19
004def24 e1031d32 mov      w1, #8
004def28 e2031f32 mov      w2, #2
004def2c 59feff97 bl       #0x4de890
004def30 f40300aa mov      x20, x0
004def34 e00313aa mov      x0, x19
004def38 e10b0032 mov      w1, #7
004def3c e2031f32 mov      w2, #2
004def40 54feff97 bl       #0x4de890
004def44 b40100b4 cbz      x20, #0x4def78
004def48 800100b4 cbz      x0, #0x4def78
004def4c 01004079 ldrh     w1, [x0]
004def50 e0030091 mov      x0, sp
004def54 27cb0194 bl       #0x551bf0
004def58 e0030091 mov      x0, sp
004def5c 5dcb0194 bl       #0x551cd0
004def60 e1630091 add      x1, sp, #0x18
004def64 e01b00b9 str      w0, [sp, #0x18]
004def68 9a040094 bl       #0x4e01d0
004def6c 80020079 strh     w0, [x20]
004def70 e0030091 mov      x0, sp
004def74 33cb0194 bl       #0x551c40
004def78 e00313aa mov      x0, x19
004def7c e1031d32 mov      w1, #8
004def80 e2070032 mov      w2, #3
004def84 43feff97 bl       #0x4de890
004def88 f40300aa mov      x20, x0
004def8c e00313aa mov      x0, x19
004def90 e10b0032 mov      w1, #7
004def94 e2070032 mov      w2, #3
004def98 3efeff97 bl       #0x4de890
004def9c b40100b4 cbz      x20, #0x4defd0
004defa0 800100b4 cbz      x0, #0x4defd0
004defa4 01004079 ldrh     w1, [x0]
004defa8 e0030091 mov      x0, sp
004defac 11cb0194 bl       #0x551bf0
004defb0 e0030091 mov      x0, sp
004defb4 47cb0194 bl       #0x551cd0
004defb8 e1630091 add      x1, sp, #0x18
004defbc e01b00b9 str      w0, [sp, #0x18]
004defc0 84040094 bl       #0x4e01d0
004defc4 80020079 strh     w0, [x20]
004defc8 e0030091 mov      x0, sp
004defcc 1dcb0194 bl       #0x551c40
004defd0 e00313aa mov      x0, x19
004defd4 e1031d32 mov      w1, #8
004defd8 e2031e32 mov      w2, #4
004defdc 2dfeff97 bl       #0x4de890
004defe0 f40300aa mov      x20, x0
004defe4 e00313aa mov      x0, x19
004defe8 e10b0032 mov      w1, #7
004defec e2031e32 mov      w2, #4
004deff0 28feff97 bl       #0x4de890
004deff4 b40100b4 cbz      x20, #0x4df028
004deff8 800100b4 cbz      x0, #0x4df028
004deffc 01004079 ldrh     w1, [x0]
004df000 e0030091 mov      x0, sp
004df004 fbca0194 bl       #0x551bf0
004df008 e0030091 mov      x0, sp
004df00c 31cb0194 bl       #0x551cd0
004df010 e1630091 add      x1, sp, #0x18
004df014 e01b00b9 str      w0, [sp, #0x18]
004df018 6e040094 bl       #0x4e01d0
004df01c 80020079 strh     w0, [x20]
004df020 e0030091 mov      x0, sp
004df024 07cb0194 bl       #0x551c40
004df028 b5008052 mov      w21, #5
004df02c e00313aa mov      x0, x19
004df030 e1031d32 mov      w1, #8
004df034 e203152a mov      w2, w21
004df038 16feff97 bl       #0x4de890
004df03c f40300aa mov      x20, x0
004df040 e00313aa mov      x0, x19
004df044 e10b0032 mov      w1, #7
004df048 e203152a mov      w2, w21
004df04c 11feff97 bl       #0x4de890
004df050 b40100b4 cbz      x20, #0x4df084
004df054 800100b4 cbz      x0, #0x4df084
004df058 01004079 ldrh     w1, [x0]
004df05c e0030091 mov      x0, sp
004df060 e4ca0194 bl       #0x551bf0
004df064 e0030091 mov      x0, sp
004df068 1acb0194 bl       #0x551cd0
004df06c e1630091 add      x1, sp, #0x18
004df070 e01b00b9 str      w0, [sp, #0x18]
004df074 57040094 bl       #0x4e01d0
004df078 80020079 strh     w0, [x20]
004df07c e0030091 mov      x0, sp
004df080 f0ca0194 bl       #0x551c40
004df084 e00313aa mov      x0, x19
004df088 e1031d32 mov      w1, #8
004df08c e2071f32 mov      w2, #6
004df090 00feff97 bl       #0x4de890
004df094 f40300aa mov      x20, x0
004df098 e00313aa mov      x0, x19
004df09c e10b0032 mov      w1, #7
004df0a0 e2071f32 mov      w2, #6
004df0a4 fbfdff97 bl       #0x4de890
004df0a8 b40100b4 cbz      x20, #0x4df0dc
004df0ac 800100b4 cbz      x0, #0x4df0dc
004df0b0 01004079 ldrh     w1, [x0]
004df0b4 e0030091 mov      x0, sp
004df0b8 ceca0194 bl       #0x551bf0
004df0bc e0030091 mov      x0, sp
004df0c0 04cb0194 bl       #0x551cd0
004df0c4 e1630091 add      x1, sp, #0x18
004df0c8 e01b00b9 str      w0, [sp, #0x18]
004df0cc 41040094 bl       #0x4e01d0
004df0d0 80020079 strh     w0, [x20]
004df0d4 e0030091 mov      x0, sp
004df0d8 daca0194 bl       #0x551c40
004df0dc e00313aa mov      x0, x19
004df0e0 e1031f2a mov      w1, wzr
004df0e4 e2030032 mov      w2, #1
004df0e8 eafdff97 bl       #0x4de890
004df0ec f40300aa mov      x20, x0
004df0f0 e00313aa mov      x0, x19
004df0f4 e1030032 mov      w1, #1
004df0f8 e2030032 mov      w2, #1
004df0fc e5fdff97 bl       #0x4de890
004df100 b40100b4 cbz      x20, #0x4df134
004df104 800100b4 cbz      x0, #0x4df134
004df108 01004079 ldrh     w1, [x0]
004df10c e0030091 mov      x0, sp
004df110 b8ca0194 bl       #0x551bf0
004df114 e0030091 mov      x0, sp
004df118 eeca0194 bl       #0x551cd0
004df11c e1630091 add      x1, sp, #0x18
004df120 e01b00b9 str      w0, [sp, #0x18]
004df124 2b040094 bl       #0x4e01d0
004df128 80020079 strh     w0, [x20]
004df12c e0030091 mov      x0, sp
004df130 c4ca0194 bl       #0x551c40
004df134 e00313aa mov      x0, x19
004df138 e1031f2a mov      w1, wzr
004df13c e2031f32 mov      w2, #2
004df140 d4fdff97 bl       #0x4de890
004df144 f40300aa mov      x20, x0
004df148 e00313aa mov      x0, x19
004df14c e1030032 mov      w1, #1
004df150 e2031f32 mov      w2, #2
004df154 cffdff97 bl       #0x4de890
004df158 b40100b4 cbz      x20, #0x4df18c
004df15c 800100b4 cbz      x0, #0x4df18c
004df160 01004079 ldrh     w1, [x0]
004df164 e0030091 mov      x0, sp
004df168 a2ca0194 bl       #0x551bf0
004df16c e0030091 mov      x0, sp
004df170 d8ca0194 bl       #0x551cd0
004df174 e1630091 add      x1, sp, #0x18
004df178 e01b00b9 str      w0, [sp, #0x18]
004df17c 15040094 bl       #0x4e01d0
004df180 80020079 strh     w0, [x20]
004df184 e0030091 mov      x0, sp
004df188 aeca0194 bl       #0x551c40
004df18c e00313aa mov      x0, x19
004df190 e1031f2a mov      w1, wzr
004df194 e2070032 mov      w2, #3
004df198 befdff97 bl       #0x4de890
004df19c f40300aa mov      x20, x0
004df1a0 e00313aa mov      x0, x19
004df1a4 e1030032 mov      w1, #1
004df1a8 e2070032 mov      w2, #3
004df1ac b9fdff97 bl       #0x4de890
004df1b0 b40100b4 cbz      x20, #0x4df1e4
004df1b4 800100b4 cbz      x0, #0x4df1e4
004df1b8 01004079 ldrh     w1, [x0]
004df1bc e0030091 mov      x0, sp
004df1c0 8cca0194 bl       #0x551bf0
004df1c4 e0030091 mov      x0, sp
004df1c8 c2ca0194 bl       #0x551cd0
004df1cc e1630091 add      x1, sp, #0x18
004df1d0 e01b00b9 str      w0, [sp, #0x18]
004df1d4 ff030094 bl       #0x4e01d0
004df1d8 80020079 strh     w0, [x20]
004df1dc e0030091 mov      x0, sp
004df1e0 98ca0194 bl       #0x551c40
004df1e4 e00313aa mov      x0, x19
004df1e8 e1031f2a mov      w1, wzr
004df1ec e2031e32 mov      w2, #4
004df1f0 a8fdff97 bl       #0x4de890
004df1f4 f40300aa mov      x20, x0
004df1f8 e00313aa mov      x0, x19
004df1fc e1030032 mov      w1, #1
004df200 e2031e32 mov      w2, #4
004df204 a3fdff97 bl       #0x4de890
004df208 b40100b4 cbz      x20, #0x4df23c
004df20c 800100b4 cbz      x0, #0x4df23c
004df210 01004079 ldrh     w1, [x0]
004df214 e0030091 mov      x0, sp
004df218 76ca0194 bl       #0x551bf0
004df21c e0030091 mov      x0, sp
004df220 acca0194 bl       #0x551cd0
004df224 e1630091 add      x1, sp, #0x18
004df228 e01b00b9 str      w0, [sp, #0x18]
004df22c e9030094 bl       #0x4e01d0
004df230 80020079 strh     w0, [x20]
004df234 e0030091 mov      x0, sp
004df238 82ca0194 bl       #0x551c40
004df23c b5008052 mov      w21, #5
004df240 e00313aa mov      x0, x19
004df244 e1031f2a mov      w1, wzr
004df248 e203152a mov      w2, w21
004df24c 91fdff97 bl       #0x4de890
004df250 f40300aa mov      x20, x0
004df254 e00313aa mov      x0, x19
004df258 e1030032 mov      w1, #1
004df25c e203152a mov      w2, w21
004df260 8cfdff97 bl       #0x4de890
004df264 b40100b4 cbz      x20, #0x4df298
004df268 800100b4 cbz      x0, #0x4df298
004df26c 01004079 ldrh     w1, [x0]
004df270 e0030091 mov      x0, sp
004df274 5fca0194 bl       #0x551bf0
004df278 e0030091 mov      x0, sp
004df27c 95ca0194 bl       #0x551cd0
004df280 e1630091 add      x1, sp, #0x18
004df284 e01b00b9 str      w0, [sp, #0x18]
004df288 d2030094 bl       #0x4e01d0
004df28c 80020079 strh     w0, [x20]
004df290 e0030091 mov      x0, sp
004df294 6bca0194 bl       #0x551c40
004df298 e00313aa mov      x0, x19
004df29c e1031f2a mov      w1, wzr
004df2a0 e2071f32 mov      w2, #6
004df2a4 7bfdff97 bl       #0x4de890
004df2a8 f40300aa mov      x20, x0
004df2ac e00313aa mov      x0, x19
004df2b0 e1030032 mov      w1, #1
004df2b4 e2071f32 mov      w2, #6
004df2b8 76fdff97 bl       #0x4de890
004df2bc b40100b4 cbz      x20, #0x4df2f0
004df2c0 800100b4 cbz      x0, #0x4df2f0
004df2c4 01004079 ldrh     w1, [x0]
004df2c8 e0030091 mov      x0, sp
004df2cc 49ca0194 bl       #0x551bf0
004df2d0 e0030091 mov      x0, sp
004df2d4 7fca0194 bl       #0x551cd0
004df2d8 e1630091 add      x1, sp, #0x18
004df2dc e01b00b9 str      w0, [sp, #0x18]
004df2e0 bc030094 bl       #0x4e01d0
004df2e4 80020079 strh     w0, [x20]
004df2e8 e0030091 mov      x0, sp
004df2ec 55ca0194 bl       #0x551c40
004df2f0 e00313aa mov      x0, x19
004df2f4 e1030032 mov      w1, #1
004df2f8 e20b0032 mov      w2, #7
004df2fc 65fdff97 bl       #0x4de890
004df300 f40300aa mov      x20, x0
004df304 e00313aa mov      x0, x19
004df308 e1030032 mov      w1, #1
004df30c e2071f32 mov      w2, #6
004df310 60fdff97 bl       #0x4de890
004df314 b40100b4 cbz      x20, #0x4df348
004df318 800100b4 cbz      x0, #0x4df348
004df31c 01004079 ldrh     w1, [x0]
004df320 e0030091 mov      x0, sp
004df324 33ca0194 bl       #0x551bf0
004df328 e0030091 mov      x0, sp
004df32c 69ca0194 bl       #0x551cd0
004df330 e1630091 add      x1, sp, #0x18
004df334 e01b00b9 str      w0, [sp, #0x18]
004df338 a6030094 bl       #0x4e01d0
004df33c 80020079 strh     w0, [x20]
004df340 e0030091 mov      x0, sp
004df344 3fca0194 bl       #0x551c40
004df348 e00313aa mov      x0, x19
004df34c e1031f32 mov      w1, #2
004df350 e20b0032 mov      w2, #7
004df354 4ffdff97 bl       #0x4de890
004df358 f40300aa mov      x20, x0
004df35c e00313aa mov      x0, x19
004df360 e1031f32 mov      w1, #2
004df364 e2071f32 mov      w2, #6
004df368 4afdff97 bl       #0x4de890
004df36c b40100b4 cbz      x20, #0x4df3a0
004df370 800100b4 cbz      x0, #0x4df3a0
004df374 01004079 ldrh     w1, [x0]
004df378 e0030091 mov      x0, sp
004df37c 1dca0194 bl       #0x551bf0
004df380 e0030091 mov      x0, sp
004df384 53ca0194 bl       #0x551cd0
004df388 e1630091 add      x1, sp, #0x18
004df38c e01b00b9 str      w0, [sp, #0x18]
004df390 90030094 bl       #0x4e01d0
004df394 80020079 strh     w0, [x20]
004df398 e0030091 mov      x0, sp
004df39c 29ca0194 bl       #0x551c40
004df3a0 e00313aa mov      x0, x19
004df3a4 e1070032 mov      w1, #3
004df3a8 e20b0032 mov      w2, #7
004df3ac 39fdff97 bl       #0x4de890
004df3b0 f40300aa mov      x20, x0
004df3b4 e00313aa mov      x0, x19
004df3b8 e1070032 mov      w1, #3
004df3bc e2071f32 mov      w2, #6
004df3c0 34fdff97 bl       #0x4de890
004df3c4 b40100b4 cbz      x20, #0x4df3f8
004df3c8 800100b4 cbz      x0, #0x4df3f8
004df3cc 01004079 ldrh     w1, [x0]
004df3d0 e0030091 mov      x0, sp
004df3d4 07ca0194 bl       #0x551bf0
004df3d8 e0030091 mov      x0, sp
004df3dc 3dca0194 bl       #0x551cd0
004df3e0 e1630091 add      x1, sp, #0x18
004df3e4 e01b00b9 str      w0, [sp, #0x18]
004df3e8 7a030094 bl       #0x4e01d0
004df3ec 80020079 strh     w0, [x20]
004df3f0 e0030091 mov      x0, sp
004df3f4 13ca0194 bl       #0x551c40
004df3f8 e00313aa mov      x0, x19
004df3fc e1031e32 mov      w1, #4
004df400 e20b0032 mov      w2, #7
004df404 23fdff97 bl       #0x4de890
004df408 f40300aa mov      x20, x0
004df40c e00313aa mov      x0, x19
004df410 e1031e32 mov      w1, #4
004df414 e2071f32 mov      w2, #6
004df418 1efdff97 bl       #0x4de890
004df41c b40100b4 cbz      x20, #0x4df450
004df420 800100b4 cbz      x0, #0x4df450
004df424 01004079 ldrh     w1, [x0]
004df428 e0030091 mov      x0, sp
004df42c f1c90194 bl       #0x551bf0
004df430 e0030091 mov      x0, sp
004df434 27ca0194 bl       #0x551cd0
004df438 e1630091 add      x1, sp, #0x18
004df43c e01b00b9 str      w0, [sp, #0x18]
004df440 64030094 bl       #0x4e01d0
004df444 80020079 strh     w0, [x20]
004df448 e0030091 mov      x0, sp
004df44c fdc90194 bl       #0x551c40
004df450 b5008052 mov      w21, #5
004df454 e00313aa mov      x0, x19
004df458 e103152a mov      w1, w21
004df45c e20b0032 mov      w2, #7
004df460 0cfdff97 bl       #0x4de890
004df464 f40300aa mov      x20, x0
004df468 e00313aa mov      x0, x19
004df46c e103152a mov      w1, w21
004df470 e2071f32 mov      w2, #6
004df474 07fdff97 bl       #0x4de890
004df478 b40100b4 cbz      x20, #0x4df4ac
004df47c 800100b4 cbz      x0, #0x4df4ac
004df480 01004079 ldrh     w1, [x0]
004df484 e0030091 mov      x0, sp
004df488 dac90194 bl       #0x551bf0
004df48c e0030091 mov      x0, sp
004df490 10ca0194 bl       #0x551cd0
004df494 e1630091 add      x1, sp, #0x18
004df498 e01b00b9 str      w0, [sp, #0x18]
004df49c 4d030094 bl       #0x4e01d0
004df4a0 80020079 strh     w0, [x20]
004df4a4 e0030091 mov      x0, sp
004df4a8 e6c90194 bl       #0x551c40
004df4ac e00313aa mov      x0, x19
004df4b0 e1071f32 mov      w1, #6
004df4b4 e20b0032 mov      w2, #7
004df4b8 f6fcff97 bl       #0x4de890
004df4bc f40300aa mov      x20, x0
004df4c0 e00313aa mov      x0, x19
004df4c4 e1071f32 mov      w1, #6
004df4c8 e2071f32 mov      w2, #6
004df4cc f1fcff97 bl       #0x4de890
004df4d0 b40100b4 cbz      x20, #0x4df504
004df4d4 800100b4 cbz      x0, #0x4df504
004df4d8 01004079 ldrh     w1, [x0]
004df4dc e0030091 mov      x0, sp
004df4e0 c4c90194 bl       #0x551bf0
004df4e4 e0030091 mov      x0, sp
004df4e8 fac90194 bl       #0x551cd0
004df4ec e1630091 add      x1, sp, #0x18
004df4f0 e01b00b9 str      w0, [sp, #0x18]
004df4f4 37030094 bl       #0x4e01d0
004df4f8 80020079 strh     w0, [x20]
004df4fc e0030091 mov      x0, sp
004df500 d0c90194 bl       #0x551c40
004df504 e00313aa mov      x0, x19
004df508 e10b0032 mov      w1, #7
004df50c e20b0032 mov      w2, #7
004df510 e0fcff97 bl       #0x4de890
004df514 f40300aa mov      x20, x0
004df518 e00313aa mov      x0, x19
004df51c e10b0032 mov      w1, #7
004df520 e2071f32 mov      w2, #6
004df524 dbfcff97 bl       #0x4de890
004df528 b40100b4 cbz      x20, #0x4df55c
004df52c 800100b4 cbz      x0, #0x4df55c
004df530 01004079 ldrh     w1, [x0]
004df534 e0030091 mov      x0, sp
004df538 aec90194 bl       #0x551bf0
004df53c e0030091 mov      x0, sp
004df540 e4c90194 bl       #0x551cd0
004df544 e1630091 add      x1, sp, #0x18
004df548 e01b00b9 str      w0, [sp, #0x18]
004df54c 21030094 bl       #0x4e01d0
004df550 80020079 strh     w0, [x20]
004df554 e0030091 mov      x0, sp
004df558 bac90194 bl       #0x551c40
004df55c e00313aa mov      x0, x19
004df560 e1030032 mov      w1, #1
004df564 e2031f2a mov      w2, wzr
004df568 cafcff97 bl       #0x4de890
004df56c f40300aa mov      x20, x0
004df570 e00313aa mov      x0, x19
004df574 e1030032 mov      w1, #1
004df578 e2030032 mov      w2, #1
004df57c c5fcff97 bl       #0x4de890
004df580 b40100b4 cbz      x20, #0x4df5b4
004df584 800100b4 cbz      x0, #0x4df5b4
004df588 01004079 ldrh     w1, [x0]
004df58c e0030091 mov      x0, sp
004df590 98c90194 bl       #0x551bf0
004df594 e0030091 mov      x0, sp
004df598 cec90194 bl       #0x551cd0
004df59c e1630091 add      x1, sp, #0x18
004df5a0 e01b00b9 str      w0, [sp, #0x18]
004df5a4 0b030094 bl       #0x4e01d0
004df5a8 80020079 strh     w0, [x20]
004df5ac e0030091 mov      x0, sp
004df5b0 a4c90194 bl       #0x551c40
004df5b4 e00313aa mov      x0, x19
004df5b8 e1031f32 mov      w1, #2
004df5bc e2031f2a mov      w2, wzr
004df5c0 b4fcff97 bl       #0x4de890
004df5c4 f40300aa mov      x20, x0
004df5c8 e00313aa mov      x0, x19
004df5cc e1031f32 mov      w1, #2
004df5d0 e2030032 mov      w2, #1
004df5d4 affcff97 bl       #0x4de890
004df5d8 b40100b4 cbz      x20, #0x4df60c
004df5dc 800100b4 cbz      x0, #0x4df60c
004df5e0 01004079 ldrh     w1, [x0]
004df5e4 e0030091 mov      x0, sp
004df5e8 82c90194 bl       #0x551bf0
004df5ec e0030091 mov      x0, sp
004df5f0 b8c90194 bl       #0x551cd0
004df5f4 e1630091 add      x1, sp, #0x18
004df5f8 e01b00b9 str      w0, [sp, #0x18]
004df5fc f5020094 bl       #0x4e01d0
004df600 80020079 strh     w0, [x20]
004df604 e0030091 mov      x0, sp
004df608 8ec90194 bl       #0x551c40
004df60c e00313aa mov      x0, x19
004df610 e1070032 mov      w1, #3
004df614 e2031f2a mov      w2, wzr
004df618 9efcff97 bl       #0x4de890
004df61c f40300aa mov      x20, x0
004df620 e00313aa mov      x0, x19
004df624 e1070032 mov      w1, #3
004df628 e2030032 mov      w2, #1
004df62c 99fcff97 bl       #0x4de890
004df630 b40100b4 cbz      x20, #0x4df664
004df634 800100b4 cbz      x0, #0x4df664
004df638 01004079 ldrh     w1, [x0]
004df63c e0030091 mov      x0, sp
004df640 6cc90194 bl       #0x551bf0
004df644 e0030091 mov      x0, sp
004df648 a2c90194 bl       #0x551cd0
004df64c e1630091 add      x1, sp, #0x18
004df650 e01b00b9 str      w0, [sp, #0x18]
004df654 df020094 bl       #0x4e01d0
004df658 80020079 strh     w0, [x20]
004df65c e0030091 mov      x0, sp
004df660 78c90194 bl       #0x551c40
004df664 e00313aa mov      x0, x19
004df668 e1031e32 mov      w1, #4
004df66c e2031f2a mov      w2, wzr
004df670 88fcff97 bl       #0x4de890
004df674 f40300aa mov      x20, x0
004df678 e00313aa mov      x0, x19
004df67c e1031e32 mov      w1, #4
004df680 e2030032 mov      w2, #1
004df684 83fcff97 bl       #0x4de890
004df688 b40100b4 cbz      x20, #0x4df6bc
004df68c 800100b4 cbz      x0, #0x4df6bc
004df690 01004079 ldrh     w1, [x0]
004df694 e0030091 mov      x0, sp
004df698 56c90194 bl       #0x551bf0
004df69c e0030091 mov      x0, sp
004df6a0 8cc90194 bl       #0x551cd0
004df6a4 e1630091 add      x1, sp, #0x18
004df6a8 e01b00b9 str      w0, [sp, #0x18]
004df6ac c9020094 bl       #0x4e01d0
004df6b0 80020079 strh     w0, [x20]
004df6b4 e0030091 mov      x0, sp
004df6b8 62c90194 bl       #0x551c40
004df6bc b5008052 mov      w21, #5
004df6c0 e00313aa mov      x0, x19
004df6c4 e103152a mov      w1, w21
004df6c8 e2031f2a mov      w2, wzr
004df6cc 71fcff97 bl       #0x4de890
004df6d0 f40300aa mov      x20, x0
004df6d4 e00313aa mov      x0, x19
004df6d8 e103152a mov      w1, w21
004df6dc e2030032 mov      w2, #1
004df6e0 6cfcff97 bl       #0x4de890
004df6e4 b40100b4 cbz      x20, #0x4df718
004df6e8 800100b4 cbz      x0, #0x4df718
004df6ec 01004079 ldrh     w1, [x0]
004df6f0 e0030091 mov      x0, sp
004df6f4 3fc90194 bl       #0x551bf0
004df6f8 e0030091 mov      x0, sp
004df6fc 75c90194 bl       #0x551cd0
004df700 e1630091 add      x1, sp, #0x18
004df704 e01b00b9 str      w0, [sp, #0x18]
004df708 b2020094 bl       #0x4e01d0
004df70c 80020079 strh     w0, [x20]
004df710 e0030091 mov      x0, sp
004df714 4bc90194 bl       #0x551c40
004df718 e00313aa mov      x0, x19
004df71c e1071f32 mov      w1, #6
004df720 e2031f2a mov      w2, wzr
004df724 5bfcff97 bl       #0x4de890
004df728 f40300aa mov      x20, x0
004df72c e00313aa mov      x0, x19
004df730 e1071f32 mov      w1, #6
004df734 e2030032 mov      w2, #1
004df738 56fcff97 bl       #0x4de890
004df73c b40100b4 cbz      x20, #0x4df770
004df740 800100b4 cbz      x0, #0x4df770
004df744 01004079 ldrh     w1, [x0]
004df748 e0030091 mov      x0, sp
004df74c 29c90194 bl       #0x551bf0
004df750 e0030091 mov      x0, sp
004df754 5fc90194 bl       #0x551cd0
004df758 e1630091 add      x1, sp, #0x18
004df75c e01b00b9 str      w0, [sp, #0x18]
004df760 9c020094 bl       #0x4e01d0
004df764 80020079 strh     w0, [x20]
004df768 e0030091 mov      x0, sp
004df76c 35c90194 bl       #0x551c40
004df770 e00313aa mov      x0, x19
004df774 e10b0032 mov      w1, #7
004df778 e2031f2a mov      w2, wzr
004df77c 45fcff97 bl       #0x4de890
004df780 f40300aa mov      x20, x0
004df784 e00313aa mov      x0, x19
004df788 e10b0032 mov      w1, #7
004df78c e2030032 mov      w2, #1
004df790 40fcff97 bl       #0x4de890
004df794 b40100b4 cbz      x20, #0x4df7c8
004df798 800100b4 cbz      x0, #0x4df7c8
004df79c 01004079 ldrh     w1, [x0]
004df7a0 e0030091 mov      x0, sp
004df7a4 13c90194 bl       #0x551bf0
004df7a8 e0030091 mov      x0, sp
004df7ac 49c90194 bl       #0x551cd0
004df7b0 e1630091 add      x1, sp, #0x18
004df7b4 e01b00b9 str      w0, [sp, #0x18]
004df7b8 86020094 bl       #0x4e01d0
004df7bc 80020079 strh     w0, [x20]
004df7c0 e0030091 mov      x0, sp
004df7c4 1fc90194 bl       #0x551c40
004df7c8 e00313aa mov      x0, x19
004df7cc e1031d32 mov      w1, #8
004df7d0 e2031f2a mov      w2, wzr
004df7d4 2ffcff97 bl       #0x4de890
004df7d8 f40300aa mov      x20, x0
004df7dc e00313aa mov      x0, x19
004df7e0 e1031d32 mov      w1, #8
004df7e4 e2030032 mov      w2, #1
004df7e8 2afcff97 bl       #0x4de890
004df7ec b40100b4 cbz      x20, #0x4df820
004df7f0 800100b4 cbz      x0, #0x4df820
004df7f4 01004079 ldrh     w1, [x0]
004df7f8 e0030091 mov      x0, sp
004df7fc fdc80194 bl       #0x551bf0
004df800 e0030091 mov      x0, sp
004df804 33c90194 bl       #0x551cd0
004df808 e1630091 add      x1, sp, #0x18
004df80c e01b00b9 str      w0, [sp, #0x18]
004df810 70020094 bl       #0x4e01d0
004df814 80020079 strh     w0, [x20]
004df818 e0030091 mov      x0, sp
004df81c 09c90194 bl       #0x551c40
004df820 e00313aa mov      x0, x19
004df824 e10b0032 mov      w1, #7
004df828 e2030032 mov      w2, #1
004df82c 19fcff97 bl       #0x4de890
004df830 f40300aa mov      x20, x0
004df834 e00313aa mov      x0, x19
004df838 e1031d32 mov      w1, #8
004df83c e2031f2a mov      w2, wzr
004df840 14fcff97 bl       #0x4de890
004df844 d40100b4 cbz      x20, #0x4df87c
004df848 f50300aa mov      x21, x0
004df84c 800100b4 cbz      x0, #0x4df87c
004df850 81024079 ldrh     w1, [x20]
004df854 e0030091 mov      x0, sp
004df858 e6c80194 bl       #0x551bf0
004df85c e0030091 mov      x0, sp
004df860 1cc90194 bl       #0x551cd0
004df864 e1630091 add      x1, sp, #0x18
004df868 e01b00b9 str      w0, [sp, #0x18]
004df86c 59020094 bl       #0x4e01d0
004df870 a0020079 strh     w0, [x21]
004df874 e0030091 mov      x0, sp
004df878 f2c80194 bl       #0x551c40
004df87c 140600b4 cbz      x20, #0x4df93c
004df880 81024079 ldrh     w1, [x20]
004df884 e0030091 mov      x0, sp
004df888 dac80194 bl       #0x551bf0
004df88c e00313aa mov      x0, x19
004df890 e10b0032 mov      w1, #7
004df894 e2031f2a mov      w2, wzr
004df898 fefbff97 bl       #0x4de890
004df89c 200200b4 cbz      x0, #0x4df8e0
004df8a0 f40300aa mov      x20, x0
004df8a4 e0030091 mov      x0, sp
004df8a8 32c90194 bl       #0x551d70
004df8ac 60000036 tbz      w0, #0, #0x4df8b8
004df8b0 ff1b00b9 str      wzr, [sp, #0x18]
004df8b4 08000014 b        #0x4df8d4
004df8b8 e0030091 mov      x0, sp
004df8bc 6dc90194 bl       #0x551e70
004df8c0 60000036 tbz      w0, #0, #0x4df8cc
004df8c4 e8030032 mov      w8, #1
004df8c8 02000014 b        #0x4df8d0
004df8cc e8031f32 mov      w8, #2
004df8d0 e81b00b9 str      w8, [sp, #0x18]
004df8d4 e1630091 add      x1, sp, #0x18
004df8d8 3e020094 bl       #0x4e01d0
004df8dc 80020079 strh     w0, [x20]
004df8e0 e00313aa mov      x0, x19
004df8e4 e1031d32 mov      w1, #8
004df8e8 e2030032 mov      w2, #1
004df8ec e9fbff97 bl       #0x4de890
004df8f0 200200b4 cbz      x0, #0x4df934
004df8f4 f40300aa mov      x20, x0
004df8f8 e0030091 mov      x0, sp
004df8fc 1dc90194 bl       #0x551d70
004df900 60000036 tbz      w0, #0, #0x4df90c
004df904 e8071f32 mov      w8, #6
004df908 07000014 b        #0x4df924
004df90c e0030091 mov      x0, sp
004df910 58c90194 bl       #0x551e70
004df914 60000036 tbz      w0, #0, #0x4df920
004df918 e80b0032 mov      w8, #7
004df91c 02000014 b        #0x4df924
004df920 e8031d32 mov      w8, #8
004df924 e1630091 add      x1, sp, #0x18
004df928 e81b00b9 str      w8, [sp, #0x18]
004df92c 29020094 bl       #0x4e01d0
004df930 80020079 strh     w0, [x20]
004df934 e0030091 mov      x0, sp
004df938 c2c80194 bl       #0x551c40
004df93c e00313aa mov      x0, x19
004df940 e1030032 mov      w1, #1
004df944 e2030032 mov      w2, #1
004df948 d2fbff97 bl       #0x4de890
004df94c f40300aa mov      x20, x0
004df950 e00313aa mov      x0, x19
004df954 e1031f2a mov      w1, wzr
004df958 e2031f2a mov      w2, wzr
004df95c cdfbff97 bl       #0x4de890
004df960 d40100b4 cbz      x20, #0x4df998
004df964 f50300aa mov      x21, x0
004df968 800100b4 cbz      x0, #0x4df998
004df96c 81024079 ldrh     w1, [x20]
004df970 e0030091 mov      x0, sp
004df974 9fc80194 bl       #0x551bf0
004df978 e0030091 mov      x0, sp
004df97c d5c80194 bl       #0x551cd0
004df980 e1630091 add      x1, sp, #0x18
004df984 e01b00b9 str      w0, [sp, #0x18]
004df988 12020094 bl       #0x4e01d0
004df98c a0020079 strh     w0, [x21]
004df990 e0030091 mov      x0, sp
004df994 abc80194 bl       #0x551c40
004df998 140600b4 cbz      x20, #0x4dfa58
004df99c 81024079 ldrh     w1, [x20]
004df9a0 e0030091 mov      x0, sp
004df9a4 93c80194 bl       #0x551bf0
004df9a8 e00313aa mov      x0, x19
004df9ac e1030032 mov      w1, #1
004df9b0 e2031f2a mov      w2, wzr
004df9b4 b7fbff97 bl       #0x4de890
004df9b8 200200b4 cbz      x0, #0x4df9fc
004df9bc f40300aa mov      x20, x0
004df9c0 e0030091 mov      x0, sp
004df9c4 ebc80194 bl       #0x551d70
004df9c8 60000036 tbz      w0, #0, #0x4df9d4
004df9cc ff1b00b9 str      wzr, [sp, #0x18]
004df9d0 08000014 b        #0x4df9f0
004df9d4 e0030091 mov      x0, sp
004df9d8 26c90194 bl       #0x551e70
004df9dc 60000036 tbz      w0, #0, #0x4df9e8
004df9e0 e8030032 mov      w8, #1
004df9e4 02000014 b        #0x4df9ec
004df9e8 e8031f32 mov      w8, #2
004df9ec e81b00b9 str      w8, [sp, #0x18]
004df9f0 e1630091 add      x1, sp, #0x18
004df9f4 f7010094 bl       #0x4e01d0
004df9f8 80020079 strh     w0, [x20]
004df9fc e00313aa mov      x0, x19
004dfa00 e1031f2a mov      w1, wzr
004dfa04 e2030032 mov      w2, #1
004dfa08 a2fbff97 bl       #0x4de890
004dfa0c 200200b4 cbz      x0, #0x4dfa50
004dfa10 f40300aa mov      x20, x0
004dfa14 e0030091 mov      x0, sp
004dfa18 d6c80194 bl       #0x551d70
004dfa1c 60000036 tbz      w0, #0, #0x4dfa28
004dfa20 48028052 mov      w8, #0x12
004dfa24 07000014 b        #0x4dfa40
004dfa28 e0030091 mov      x0, sp
004dfa2c 11c90194 bl       #0x551e70
004dfa30 60000036 tbz      w0, #0, #0x4dfa3c
004dfa34 68028052 mov      w8, #0x13
004dfa38 02000014 b        #0x4dfa40
004dfa3c 88028052 mov      w8, #0x14
004dfa40 e1630091 add      x1, sp, #0x18
004dfa44 e81b00b9 str      w8, [sp, #0x18]
004dfa48 e2010094 bl       #0x4e01d0
004dfa4c 80020079 strh     w0, [x20]
004dfa50 e0030091 mov      x0, sp
004dfa54 7bc80194 bl       #0x551c40
004dfa58 e00313aa mov      x0, x19
004dfa5c e10b0032 mov      w1, #7
004dfa60 e2071f32 mov      w2, #6
004dfa64 8bfbff97 bl       #0x4de890
004dfa68 f40300aa mov      x20, x0
004dfa6c e00313aa mov      x0, x19
004dfa70 e1031d32 mov      w1, #8
004dfa74 e20b0032 mov      w2, #7
004dfa78 86fbff97 bl       #0x4de890
004dfa7c d40100b4 cbz      x20, #0x4dfab4
004dfa80 f50300aa mov      x21, x0
004dfa84 800100b4 cbz      x0, #0x4dfab4
004dfa88 81024079 ldrh     w1, [x20]
004dfa8c e0030091 mov      x0, sp
004dfa90 58c80194 bl       #0x551bf0
004dfa94 e0030091 mov      x0, sp
004dfa98 8ec80194 bl       #0x551cd0
004dfa9c e1630091 add      x1, sp, #0x18
004dfaa0 e01b00b9 str      w0, [sp, #0x18]
004dfaa4 cb010094 bl       #0x4e01d0
004dfaa8 a0020079 strh     w0, [x21]
004dfaac e0030091 mov      x0, sp
004dfab0 64c80194 bl       #0x551c40
004dfab4 140600b4 cbz      x20, #0x4dfb74
004dfab8 81024079 ldrh     w1, [x20]
004dfabc e0030091 mov      x0, sp
004dfac0 4cc80194 bl       #0x551bf0
004dfac4 e00313aa mov      x0, x19
004dfac8 e10b0032 mov      w1, #7
004dfacc e20b0032 mov      w2, #7
004dfad0 70fbff97 bl       #0x4de890
004dfad4 200200b4 cbz      x0, #0x4dfb18
004dfad8 f40300aa mov      x20, x0
004dfadc e0030091 mov      x0, sp
004dfae0 a4c80194 bl       #0x551d70
004dfae4 60000036 tbz      w0, #0, #0x4dfaf0
004dfae8 e8071e32 mov      w8, #0xc
004dfaec 07000014 b        #0x4dfb08
004dfaf0 e0030091 mov      x0, sp
004dfaf4 dfc80194 bl       #0x551e70
004dfaf8 60000036 tbz      w0, #0, #0x4dfb04
004dfafc a8018052 mov      w8, #0xd
004dfb00 02000014 b        #0x4dfb08
004dfb04 e80b1f32 mov      w8, #0xe
004dfb08 e1630091 add      x1, sp, #0x18
004dfb0c e81b00b9 str      w8, [sp, #0x18]
004dfb10 b0010094 bl       #0x4e01d0
004dfb14 80020079 strh     w0, [x20]
004dfb18 e00313aa mov      x0, x19
004dfb1c e1031d32 mov      w1, #8
004dfb20 e2071f32 mov      w2, #6
004dfb24 5bfbff97 bl       #0x4de890
004dfb28 200200b4 cbz      x0, #0x4dfb6c
004dfb2c f40300aa mov      x20, x0
004dfb30 e0030091 mov      x0, sp
004dfb34 8fc80194 bl       #0x551d70
004dfb38 60000036 tbz      w0, #0, #0x4dfb44
004dfb3c e8071f32 mov      w8, #6
004dfb40 07000014 b        #0x4dfb5c
004dfb44 e0030091 mov      x0, sp
004dfb48 cac80194 bl       #0x551e70
004dfb4c 60000036 tbz      w0, #0, #0x4dfb58
004dfb50 e80b0032 mov      w8, #7
004dfb54 02000014 b        #0x4dfb5c
004dfb58 e8031d32 mov      w8, #8
004dfb5c e1630091 add      x1, sp, #0x18
004dfb60 e81b00b9 str      w8, [sp, #0x18]
004dfb64 9b010094 bl       #0x4e01d0
004dfb68 80020079 strh     w0, [x20]
004dfb6c e0030091 mov      x0, sp
004dfb70 34c80194 bl       #0x551c40
004dfb74 e00313aa mov      x0, x19
004dfb78 e1030032 mov      w1, #1
004dfb7c e2071f32 mov      w2, #6
004dfb80 44fbff97 bl       #0x4de890
004dfb84 f40300aa mov      x20, x0
004dfb88 e00313aa mov      x0, x19
004dfb8c e1031f2a mov      w1, wzr
004dfb90 e20b0032 mov      w2, #7
004dfb94 3ffbff97 bl       #0x4de890
004dfb98 d40100b4 cbz      x20, #0x4dfbd0
004dfb9c f50300aa mov      x21, x0
004dfba0 800100b4 cbz      x0, #0x4dfbd0
004dfba4 81024079 ldrh     w1, [x20]
004dfba8 e0030091 mov      x0, sp
004dfbac 11c80194 bl       #0x551bf0
004dfbb0 e0030091 mov      x0, sp
004dfbb4 47c80194 bl       #0x551cd0
004dfbb8 e1630091 add      x1, sp, #0x18
004dfbbc e01b00b9 str      w0, [sp, #0x18]
004dfbc0 84010094 bl       #0x4e01d0
004dfbc4 a0020079 strh     w0, [x21]
004dfbc8 e0030091 mov      x0, sp
004dfbcc 1dc80194 bl       #0x551c40
004dfbd0 140600b4 cbz      x20, #0x4dfc90
004dfbd4 81024079 ldrh     w1, [x20]
004dfbd8 e0030091 mov      x0, sp
004dfbdc 05c80194 bl       #0x551bf0
004dfbe0 e00313aa mov      x0, x19
004dfbe4 e1030032 mov      w1, #1
004dfbe8 e20b0032 mov      w2, #7
004dfbec 29fbff97 bl       #0x4de890
004dfbf0 200200b4 cbz      x0, #0x4dfc34
004dfbf4 f40300aa mov      x20, x0
004dfbf8 e0030091 mov      x0, sp
004dfbfc 5dc80194 bl       #0x551d70
004dfc00 60000036 tbz      w0, #0, #0x4dfc0c
004dfc04 e8071e32 mov      w8, #0xc
004dfc08 07000014 b        #0x4dfc24
004dfc0c e0030091 mov      x0, sp
004dfc10 98c80194 bl       #0x551e70
004dfc14 60000036 tbz      w0, #0, #0x4dfc20
004dfc18 a8018052 mov      w8, #0xd
004dfc1c 02000014 b        #0x4dfc24
004dfc20 e80b1f32 mov      w8, #0xe
004dfc24 e1630091 add      x1, sp, #0x18
004dfc28 e81b00b9 str      w8, [sp, #0x18]
004dfc2c 69010094 bl       #0x4e01d0
004dfc30 80020079 strh     w0, [x20]
004dfc34 e00313aa mov      x0, x19
004dfc38 e1031f2a mov      w1, wzr
004dfc3c e2071f32 mov      w2, #6
004dfc40 14fbff97 bl       #0x4de890
004dfc44 200200b4 cbz      x0, #0x4dfc88
004dfc48 f30300aa mov      x19, x0
004dfc4c e0030091 mov      x0, sp
004dfc50 48c80194 bl       #0x551d70
004dfc54 60000036 tbz      w0, #0, #0x4dfc60
004dfc58 48028052 mov      w8, #0x12
004dfc5c 07000014 b        #0x4dfc78
004dfc60 e0030091 mov      x0, sp
004dfc64 83c80194 bl       #0x551e70
004dfc68 60000036 tbz      w0, #0, #0x4dfc74
004dfc6c 68028052 mov      w8, #0x13
004dfc70 02000014 b        #0x4dfc78
004dfc74 88028052 mov      w8, #0x14
004dfc78 e1630091 add      x1, sp, #0x18
004dfc7c e81b00b9 str      w8, [sp, #0x18]
004dfc80 54010094 bl       #0x4e01d0
004dfc84 60020079 strh     w0, [x19]
004dfc88 e0030091 mov      x0, sp
004dfc8c edc70194 bl       #0x551c40
004dfc90 fd7b43a9 ldp      x29, x30, [sp, #0x30]
004dfc94 f50b40f9 ldr      x21, [sp, #0x10]
004dfc98 f44f42a9 ldp      x20, x19, [sp, #0x20]
004dfc9c e0030032 mov      w0, #1
004dfca0 ff030191 add      sp, sp, #0x40
004dfca4 c0035fd6 ret

; interior_clear ELF 0x4dfcb0 size=512 sha256=364f765723ede217a74354b7a7981cb652692dbb92bf7c5e4da86ea76a86e3d6
004dfcb0 f30f1ef8 str      x19, [sp, #-0x20]!
004dfcb4 fd7b01a9 stp      x29, x30, [sp, #0x10]
004dfcb8 fd430091 add      x29, sp, #0x10
004dfcbc f30301aa mov      x19, x1
004dfcc0 e00301aa mov      x0, x1
004dfcc4 e1031f32 mov      w1, #2
004dfcc8 e2031f32 mov      w2, #2
004dfccc f1faff97 bl       #0x4de890
004dfcd0 400000b4 cbz      x0, #0x4dfcd8
004dfcd4 1f000079 strh     wzr, [x0]
004dfcd8 e00313aa mov      x0, x19
004dfcdc e1031f32 mov      w1, #2
004dfce0 e2070032 mov      w2, #3
004dfce4 ebfaff97 bl       #0x4de890
004dfce8 400000b4 cbz      x0, #0x4dfcf0
004dfcec 1f000079 strh     wzr, [x0]
004dfcf0 e00313aa mov      x0, x19
004dfcf4 e1031f32 mov      w1, #2
004dfcf8 e2031e32 mov      w2, #4
004dfcfc e5faff97 bl       #0x4de890
004dfd00 400000b4 cbz      x0, #0x4dfd08
004dfd04 1f000079 strh     wzr, [x0]
004dfd08 a2008052 mov      w2, #5
004dfd0c e00313aa mov      x0, x19
004dfd10 e1031f32 mov      w1, #2
004dfd14 dffaff97 bl       #0x4de890
004dfd18 400000b4 cbz      x0, #0x4dfd20
004dfd1c 1f000079 strh     wzr, [x0]
004dfd20 e00313aa mov      x0, x19
004dfd24 e1070032 mov      w1, #3
004dfd28 e2031f32 mov      w2, #2
004dfd2c d9faff97 bl       #0x4de890
004dfd30 400000b4 cbz      x0, #0x4dfd38
004dfd34 1f000079 strh     wzr, [x0]
004dfd38 e00313aa mov      x0, x19
004dfd3c e1070032 mov      w1, #3
004dfd40 e2070032 mov      w2, #3
004dfd44 d3faff97 bl       #0x4de890
004dfd48 400000b4 cbz      x0, #0x4dfd50
004dfd4c 1f000079 strh     wzr, [x0]
004dfd50 e00313aa mov      x0, x19
004dfd54 e1070032 mov      w1, #3
004dfd58 e2031e32 mov      w2, #4
004dfd5c cdfaff97 bl       #0x4de890
004dfd60 400000b4 cbz      x0, #0x4dfd68
004dfd64 1f000079 strh     wzr, [x0]
004dfd68 a2008052 mov      w2, #5
004dfd6c e00313aa mov      x0, x19
004dfd70 e1070032 mov      w1, #3
004dfd74 c7faff97 bl       #0x4de890
004dfd78 400000b4 cbz      x0, #0x4dfd80
004dfd7c 1f000079 strh     wzr, [x0]
004dfd80 e00313aa mov      x0, x19
004dfd84 e1031e32 mov      w1, #4
004dfd88 e2031f32 mov      w2, #2
004dfd8c c1faff97 bl       #0x4de890
004dfd90 400000b4 cbz      x0, #0x4dfd98
004dfd94 1f000079 strh     wzr, [x0]
004dfd98 e00313aa mov      x0, x19
004dfd9c e1031e32 mov      w1, #4
004dfda0 e2070032 mov      w2, #3
004dfda4 bbfaff97 bl       #0x4de890
004dfda8 400000b4 cbz      x0, #0x4dfdb0
004dfdac 1f000079 strh     wzr, [x0]
004dfdb0 e00313aa mov      x0, x19
004dfdb4 e1031e32 mov      w1, #4
004dfdb8 e2031e32 mov      w2, #4
004dfdbc b5faff97 bl       #0x4de890
004dfdc0 400000b4 cbz      x0, #0x4dfdc8
004dfdc4 1f000079 strh     wzr, [x0]
004dfdc8 a2008052 mov      w2, #5
004dfdcc e00313aa mov      x0, x19
004dfdd0 e1031e32 mov      w1, #4
004dfdd4 affaff97 bl       #0x4de890
004dfdd8 400000b4 cbz      x0, #0x4dfde0
004dfddc 1f000079 strh     wzr, [x0]
004dfde0 a1008052 mov      w1, #5
004dfde4 e00313aa mov      x0, x19
004dfde8 e2031f32 mov      w2, #2
004dfdec a9faff97 bl       #0x4de890
004dfdf0 400000b4 cbz      x0, #0x4dfdf8
004dfdf4 1f000079 strh     wzr, [x0]
004dfdf8 a1008052 mov      w1, #5
004dfdfc e00313aa mov      x0, x19
004dfe00 e2070032 mov      w2, #3
004dfe04 a3faff97 bl       #0x4de890
004dfe08 400000b4 cbz      x0, #0x4dfe10
004dfe0c 1f000079 strh     wzr, [x0]
004dfe10 a1008052 mov      w1, #5
004dfe14 e00313aa mov      x0, x19
004dfe18 e2031e32 mov      w2, #4
004dfe1c 9dfaff97 bl       #0x4de890
004dfe20 400000b4 cbz      x0, #0x4dfe28
004dfe24 1f000079 strh     wzr, [x0]
004dfe28 a1008052 mov      w1, #5
004dfe2c e00313aa mov      x0, x19
004dfe30 e203012a mov      w2, w1
004dfe34 97faff97 bl       #0x4de890
004dfe38 400000b4 cbz      x0, #0x4dfe40
004dfe3c 1f000079 strh     wzr, [x0]
004dfe40 e00313aa mov      x0, x19
004dfe44 e1071f32 mov      w1, #6
004dfe48 e2031f32 mov      w2, #2
004dfe4c 91faff97 bl       #0x4de890
004dfe50 400000b4 cbz      x0, #0x4dfe58
004dfe54 1f000079 strh     wzr, [x0]
004dfe58 e00313aa mov      x0, x19
004dfe5c e1071f32 mov      w1, #6
004dfe60 e2070032 mov      w2, #3
004dfe64 8bfaff97 bl       #0x4de890
004dfe68 400000b4 cbz      x0, #0x4dfe70
004dfe6c 1f000079 strh     wzr, [x0]
004dfe70 e00313aa mov      x0, x19
004dfe74 e1071f32 mov      w1, #6
004dfe78 e2031e32 mov      w2, #4
004dfe7c 85faff97 bl       #0x4de890
004dfe80 400000b4 cbz      x0, #0x4dfe88
004dfe84 1f000079 strh     wzr, [x0]
004dfe88 a2008052 mov      w2, #5
004dfe8c e00313aa mov      x0, x19
004dfe90 e1071f32 mov      w1, #6
004dfe94 7ffaff97 bl       #0x4de890
004dfe98 400000b4 cbz      x0, #0x4dfea0
004dfe9c 1f000079 strh     wzr, [x0]
004dfea0 fd7b41a9 ldp      x29, x30, [sp, #0x10]
004dfea4 e0030032 mov      w0, #1
004dfea8 f30742f8 ldr      x19, [sp], #0x20
004dfeac c0035fd6 ret

; coast_grid_wrapper ELF 0x4de9b0 size=136 sha256=fd6355df87ba75d0f6613e8d3d4e999987246a20fac2e51fec59b60b3ad3be36
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

; parts_kind_selector ELF 0x4dfeb0 size=800 sha256=40e5f42b274542da9d1a5c591f890479406abbfbcfd46260c4d54cb23fcf6690
004dfeb0 ff0303d1 sub      sp, sp, #0xc0
004dfeb4 fc6f06a9 stp      x28, x27, [sp, #0x60]
004dfeb8 fa6707a9 stp      x26, x25, [sp, #0x70]
004dfebc f85f08a9 stp      x24, x23, [sp, #0x80]
004dfec0 f65709a9 stp      x22, x21, [sp, #0x90]
004dfec4 f44f0aa9 stp      x20, x19, [sp, #0xa0]
004dfec8 fd7b0ba9 stp      x29, x30, [sp, #0xb0]
004dfecc fdc30291 add      x29, sp, #0xb0
004dfed0 886f01d0 adrp     x8, #0x32d1000
004dfed4 08d545f9 ldr      x8, [x8, #0xba8]
004dfed8 190140f9 ldr      x25, [x8]
004dfedc 28a75679 ldrh     w8, [x25, #0xb52]
004dfee0 29a35679 ldrh     w9, [x25, #0xb50]
004dfee4 08050011 add      w8, w8, #1
004dfee8 3f21286b cmp      w9, w8, uxth
004dfeec 61000054 b.ne     #0x4dfef8
004dfef0 e0031f2a mov      w0, wzr
004dfef4 af000014 b        #0x4e01b0
004dfef8 1c7001f0 adrp     x28, #0x32e2000
004dfefc b66f01f0 adrp     x22, #0x32d6000
004dff00 b76f01f0 adrp     x23, #0x32d6000
004dff04 9cc344f9 ldr      x28, [x28, #0x980]
004dff08 d6d247f9 ldr      x22, [x22, #0xfa0]
004dff0c f7d647f9 ldr      x23, [x23, #0xfa8]
004dff10 f30301aa mov      x19, x1
004dff14 f8031f2a mov      w24, wzr
004dff18 9a0a8c52 mov      w26, #0x6054
004dff1c 1a8eaa72 movk     w26, #0x5470, lsl #16
004dff20 1b3d0012 and      w27, w8, #0xffff
004dff24 e803092a mov      w8, w9
004dff28 e10700f9 str      x1, [sp, #8]
004dff2c 02000014 b        #0x4dff34
004dff30 29a35679 ldrh     w9, [x25, #0xb50]
004dff34 143d0012 and      w20, w8, #0xffff
004dff38 8822294b sub      w8, w20, w9, uxth
004dff3c 29334bb9 ldr      w9, [x25, #0xb30]
004dff40 1f01096b cmp      w8, w9
004dff44 82000054 b.hs     #0x4dff54
004dff48 299f45f9 ldr      x9, [x25, #0xb38]
004dff4c 35d968f8 ldr      x21, [x9, w8, sxtw #3]
004dff50 f50000b5 cbnz     x21, #0x4dff6c
004dff54 087001f0 adrp     x8, #0x32e2000
004dff58 08c544f9 ldr      x8, [x8, #0x988]
004dff5c 157001f0 adrp     x21, #0x32e2000
004dff60 08fddf08 ldarb    w8, [x8]
004dff64 b5ca44f9 ldr      x21, [x21, #0x990]
004dff68 080f0036 tbz      w8, #0, #0x4e0148
004dff6c e00315aa mov      x0, x21
004dff70 cc174694 bl       #0x1665ea0
004dff74 880340b9 ldr      w8, [x28]
004dff78 1f00086b cmp      w0, w8
004dff7c a2000054 b.hs     #0x4dff90
004dff80 880740f9 ldr      x8, [x28, #8]
004dff84 08d96078 ldrh     w8, [x8, w0, sxtw #1]
004dff88 1f6d0071 cmp      w8, #0x1b
004dff8c 49000054 b.ls     #0x4dff94
004dff90 e8031f2a mov      w8, wzr
004dff94 e81300b9 str      w8, [sp, #0x10]
004dff98 e81340b9 ldr      w8, [sp, #0x10]
004dff9c 690240b9 ldr      w9, [x19]
004dffa0 1f01096b cmp      w8, w9
004dffa4 21080054 b.ne     #0x4e00a8
004dffa8 1f7f0071 cmp      w24, #0x1f
004dffac c80e0054 b.hi     #0x4e0184
004dffb0 a80240b9 ldr      w8, [x21]
004dffb4 48070034 cbz      w8, #0x4e009c
004dffb8 c8024039 ldrb     w8, [x22]
004dffbc 68050034 cbz      w8, #0x4e0068
004dffc0 e80a80b9 ldrsw    x8, [x23, #8]
004dffc4 a80bf836 tbz      w8, #0x1f, #0x4e0138
004dffc8 1f050031 cmn      w8, #1
004dffcc 61060054 b.ne     #0x4e0098
004dffd0 e00315aa mov      x0, x21
004dffd4 f30317aa mov      x19, x23
004dffd8 aa174694 bl       #0x1665e80
004dffdc c00900b4 cbz      x0, #0x4e0114
004dffe0 f70300aa mov      x23, x0
004dffe4 fc0316aa mov      x28, x22
004dffe8 9e174694 bl       #0x1665e60
004dffec e00800b4 cbz      x0, #0x4e0108
004dfff0 f60300aa mov      x22, x0
004dfff4 e00317aa mov      x0, x23
004dfff8 96174694 bl       #0x1665e50
004dfffc e87b1f32 mov      w8, #-2
004e0000 f70313aa mov      x23, x19
004e0004 680a00b9 str      w8, [x19, #8]
004e0008 e8031f2a mov      w8, wzr
004e000c c0080034 cbz      w0, #0x4e0124
004e0010 f30740f9 ldr      x19, [sp, #8]
004e0014 c9120091 add      x9, x22, #4
004e0018 ea03082a mov      w10, w8
004e001c 4af17dd3 lsl      x10, x10, #3
004e0020 ca6a6ab8 ldr      w10, [x22, x10]
004e0024 5f011a6b cmp      w10, w26
004e0028 c0000054 b.eq     #0x4e0040
004e002c 08050011 add      w8, w8, #1
004e0030 29210091 add      x9, x9, #8
004e0034 1f01006b cmp      w8, w0
004e0038 03ffff54 b.lo     #0x4e0018
004e003c 14000014 b        #0x4e008c
004e0040 280140b9 ldr      w8, [x9]
004e0044 1f050031 cmn      w8, #1
004e0048 e803881a csel     w8, wzr, w8, eq
004e004c e80a00b9 str      w8, [x23, #8]
004e0050 f6031caa mov      x22, x28
004e0054 1c7001d0 adrp     x28, #0x32e2000
004e0058 a80240b9 ldr      w8, [x21]
004e005c 9cc344f9 ldr      x28, [x28, #0x980]
004e0060 c8faff35 cbnz     w8, #0x4dffb8
004e0064 0e000014 b        #0x4e009c
004e0068 e8030032 mov      w8, #1
004e006c c8020039 strb     w8, [x22]
004e0070 08008092 mov      x8, #-1
004e0074 e82200a9 stp      x8, x8, [x23]
004e0078 e00315aa mov      x0, x21
004e007c f30317aa mov      x19, x23
004e0080 80174694 bl       #0x1665e80
004e0084 e0faffb5 cbnz     x0, #0x4dffe0
004e0088 23000014 b        #0x4e0114
004e008c f6031caa mov      x22, x28
004e0090 1c7001d0 adrp     x28, #0x32e2000
004e0094 9cc344f9 ldr      x28, [x28, #0x980]
004e0098 e8031f2a mov      w8, wzr
004e009c e9830091 add      x9, sp, #0x20
004e00a0 28d93878 strh     w8, [x9, w24, sxtw #1]
004e00a4 18070011 add      w24, w24, #1
004e00a8 29a75679 ldrh     w9, [x25, #0xb52]
004e00ac e803142a mov      w8, w20
004e00b0 1f01096b cmp      w8, w9
004e00b4 22020054 b.hs     #0x4e00f8
004e00b8 2ba35679 ldrh     w11, [x25, #0xb50]
004e00bc 08050011 add      w8, w8, #1
004e00c0 0a3d0012 and      w10, w8, #0xffff
004e00c4 4a010b4b sub      w10, w10, w11
004e00c8 2b334bb9 ldr      w11, [x25, #0xb30]
004e00cc 5f010b6b cmp      w10, w11
004e00d0 a2000054 b.hs     #0x4e00e4
004e00d4 2b9f45f9 ldr      x11, [x25, #0xb38]
004e00d8 6ad96af8 ldr      x10, [x11, w10, sxtw #3]
004e00dc aafeffb4 cbz      x10, #0x4e00b0
004e00e0 03000014 b        #0x4e00ec
004e00e4 ea031faa mov      x10, xzr
004e00e8 4afeffb4 cbz      x10, #0x4e00b0
004e00ec 7f23286b cmp      w27, w8, uxth
004e00f0 01f2ff54 b.ne     #0x4dff30
004e00f4 23000014 b        #0x4e0180
004e00f8 88060011 add      w8, w20, #1
004e00fc 7f23286b cmp      w27, w8, uxth
004e0100 81f1ff54 b.ne     #0x4dff30
004e0104 1f000014 b        #0x4e0180
004e0108 f6031caa mov      x22, x28
004e010c 1c7001d0 adrp     x28, #0x32e2000
004e0110 9cc344f9 ldr      x28, [x28, #0x980]
004e0114 e8031f2a mov      w8, wzr
004e0118 f70313aa mov      x23, x19
004e011c f30740f9 ldr      x19, [sp, #8]
004e0120 dfffff17 b        #0x4e009c
004e0124 f6031caa mov      x22, x28
004e0128 1c7001d0 adrp     x28, #0x32e2000
004e012c 9cc344f9 ldr      x28, [x28, #0x980]
004e0130 f30740f9 ldr      x19, [sp, #8]
004e0134 daffff17 b        #0x4e009c
004e0138 080115ab adds     x8, x8, x21
004e013c 00fbff54 b.eq     #0x4e009c
004e0140 08014079 ldrh     w8, [x8]
004e0144 d6ffff17 b        #0x4e009c
004e0148 007001d0 adrp     x0, #0x32e2000
004e014c 00c444f9 ldr      x0, [x0, #0x988]
004e0150 a4b87494 bl       #0x220e3e0
004e0154 157001d0 adrp     x21, #0x32e2000
004e0158 b5ca44f9 ldr      x21, [x21, #0x990]
004e015c a0000034 cbz      w0, #0x4e0170
004e0160 bf0200b9 str      wzr, [x21]
004e0164 007001d0 adrp     x0, #0x32e2000
004e0168 00c444f9 ldr      x0, [x0, #0x988]
004e016c a1b87494 bl       #0x220e3f0
004e0170 1c7001d0 adrp     x28, #0x32e2000
004e0174 9cc344f9 ldr      x28, [x28, #0x980]
004e0178 f30740f9 ldr      x19, [sp, #8]
004e017c 7cffff17 b        #0x4dff6c
004e0180 98ebff34 cbz      w24, #0x4dfef0
004e0184 e0430091 add      x0, sp, #0x10
004e0188 96275394 bl       #0x19a9fe0
004e018c e0430091 add      x0, sp, #0x10
004e0190 d4275394 bl       #0x19aa0e0
004e0194 087cb89b umull    x8, w0, w24
004e0198 09fd60d3 lsr      x9, x8, #0x20
004e019c 08fd6093 asr      x8, x8, #0x20
004e01a0 3f810071 cmp      w9, #0x20
004e01a4 e9830091 add      x9, sp, #0x20
004e01a8 08319f9a csel     x8, x8, xzr, lo
004e01ac 20796878 ldrh     w0, [x9, x8, lsl #1]
004e01b0 fd7b4ba9 ldp      x29, x30, [sp, #0xb0]
004e01b4 f44f4aa9 ldp      x20, x19, [sp, #0xa0]
004e01b8 f65749a9 ldp      x22, x21, [sp, #0x90]
004e01bc f85f48a9 ldp      x24, x23, [sp, #0x80]
004e01c0 fa6747a9 ldp      x26, x25, [sp, #0x70]
004e01c4 fc6f46a9 ldp      x28, x27, [sp, #0x60]
004e01c8 ff030391 add      sp, sp, #0xc0
004e01cc c0035fd6 ret

; outside_sea_selector ELF 0x4e01d0 size=852 sha256=4c94ede59c9b58e1cdbd5dc0c93b99f6261ad28ad3825a85f76a54ea71e3c344
004e01d0 ffc302d1 sub      sp, sp, #0xb0
004e01d4 fc6f05a9 stp      x28, x27, [sp, #0x50]
004e01d8 fa6706a9 stp      x26, x25, [sp, #0x60]
004e01dc f85f07a9 stp      x24, x23, [sp, #0x70]
004e01e0 f65708a9 stp      x22, x21, [sp, #0x80]
004e01e4 f44f09a9 stp      x20, x19, [sp, #0x90]
004e01e8 fd7b0aa9 stp      x29, x30, [sp, #0xa0]
004e01ec fd830291 add      x29, sp, #0xa0
004e01f0 886f01b0 adrp     x8, #0x32d1000
004e01f4 08d545f9 ldr      x8, [x8, #0xba8]
004e01f8 190140f9 ldr      x25, [x8]
004e01fc 28a75679 ldrh     w8, [x25, #0xb52]
004e0200 29a35679 ldrh     w9, [x25, #0xb50]
004e0204 08050011 add      w8, w8, #1
004e0208 3f21286b cmp      w9, w8, uxth
004e020c a0170054 b.eq     #0x4e0500
004e0210 167001d0 adrp     x22, #0x32e2000
004e0214 177001d0 adrp     x23, #0x32e2000
004e0218 1c7001d0 adrp     x28, #0x32e2000
004e021c d6c644f9 ldr      x22, [x22, #0x988]
004e0220 f7ca44f9 ldr      x23, [x23, #0x990]
004e0224 9cc344f9 ldr      x28, [x28, #0x980]
004e0228 f30301aa mov      x19, x1
004e022c f8031f2a mov      w24, wzr
004e0230 9a0a8c52 mov      w26, #0x6054
004e0234 1a8eaa72 movk     w26, #0x5470, lsl #16
004e0238 143d0012 and      w20, w8, #0xffff
004e023c e803092a mov      w8, w9
004e0240 02000014 b        #0x4e0248
004e0244 29a35679 ldrh     w9, [x25, #0xb50]
004e0248 1b3d0012 and      w27, w8, #0xffff
004e024c 6823294b sub      w8, w27, w9, uxth
004e0250 29334bb9 ldr      w9, [x25, #0xb30]
004e0254 1f01096b cmp      w8, w9
004e0258 82000054 b.hs     #0x4e0268
004e025c 299f45f9 ldr      x9, [x25, #0xb38]
004e0260 35d968f8 ldr      x21, [x9, w8, sxtw #3]
004e0264 950000b5 cbnz     x21, #0x4e0274
004e0268 c8fedf08 ldarb    w8, [x22]
004e026c f50317aa mov      x21, x23
004e0270 e8100036 tbz      w8, #0, #0x4e048c
004e0274 e00315aa mov      x0, x21
004e0278 0a174694 bl       #0x1665ea0
004e027c 880340b9 ldr      w8, [x28]
004e0280 1f00086b cmp      w0, w8
004e0284 a2000054 b.hs     #0x4e0298
004e0288 880740f9 ldr      x8, [x28, #8]
004e028c 08d96078 ldrh     w8, [x8, w0, sxtw #1]
004e0290 1f6d0071 cmp      w8, #0x1b
004e0294 49000054 b.ls     #0x4e029c
004e0298 e8031f2a mov      w8, wzr
004e029c e80300b9 str      w8, [sp]
004e02a0 e80340b9 ldr      w8, [sp]
004e02a4 1f610071 cmp      w8, #0x18
004e02a8 010b0054 b.ne     #0x4e0408
004e02ac e00315aa mov      x0, x21
004e02b0 fc164694 bl       #0x1665ea0
004e02b4 097001d0 adrp     x9, #0x32e2000
004e02b8 29cd44f9 ldr      x9, [x9, #0x998]
004e02bc 280140b9 ldr      w8, [x9]
004e02c0 1f00086b cmp      w0, w8
004e02c4 a2000054 b.hs     #0x4e02d8
004e02c8 280540f9 ldr      x8, [x9, #8]
004e02cc 08d96078 ldrh     w8, [x8, w0, sxtw #1]
004e02d0 1f5d0071 cmp      w8, #0x17
004e02d4 49000054 b.ls     #0x4e02dc
004e02d8 e8031f2a mov      w8, wzr
004e02dc e80300b9 str      w8, [sp]
004e02e0 e80340b9 ldr      w8, [sp]
004e02e4 690240b9 ldr      w9, [x19]
004e02e8 1f01096b cmp      w8, w9
004e02ec e1080054 b.ne     #0x4e0408
004e02f0 1f7f0071 cmp      w24, #0x1f
004e02f4 e80e0054 b.hi     #0x4e04d0
004e02f8 a80240b9 ldr      w8, [x21]
004e02fc 08080034 cbz      w8, #0x4e03fc
004e0300 a96f01d0 adrp     x9, #0x32d6000
004e0304 29d147f9 ldr      x9, [x9, #0xfa0]
004e0308 28014039 ldrb     w8, [x9]
004e030c c8050034 cbz      w8, #0x4e03c4
004e0310 a86f01d0 adrp     x8, #0x32d6000
004e0314 08d547f9 ldr      x8, [x8, #0xfa8]
004e0318 080980b9 ldrsw    x8, [x8, #8]
004e031c 080bf836 tbz      w8, #0x1f, #0x4e047c
004e0320 1f050031 cmn      w8, #1
004e0324 a1060054 b.ne     #0x4e03f8
004e0328 e00315aa mov      x0, x21
004e032c d5164694 bl       #0x1665e80
004e0330 c00500b4 cbz      x0, #0x4e03e8
004e0334 f70300aa mov      x23, x0
004e0338 ca164694 bl       #0x1665e60
004e033c 600900b4 cbz      x0, #0x4e0468
004e0340 f60300aa mov      x22, x0
004e0344 e00317aa mov      x0, x23
004e0348 c2164694 bl       #0x1665e50
004e034c a96f01d0 adrp     x9, #0x32d6000
004e0350 29d547f9 ldr      x9, [x9, #0xfa8]
004e0354 e87b1f32 mov      w8, #-2
004e0358 280900b9 str      w8, [x9, #8]
004e035c 60080034 cbz      w0, #0x4e0468
004e0360 177001d0 adrp     x23, #0x32e2000
004e0364 f7ca44f9 ldr      x23, [x23, #0x990]
004e0368 e8031f2a mov      w8, wzr
004e036c c9120091 add      x9, x22, #4
004e0370 ea03082a mov      w10, w8
004e0374 4af17dd3 lsl      x10, x10, #3
004e0378 ca6a6ab8 ldr      w10, [x22, x10]
004e037c 5f011a6b cmp      w10, w26
004e0380 c0000054 b.eq     #0x4e0398
004e0384 08050011 add      w8, w8, #1
004e0388 29210091 add      x9, x9, #8
004e038c 1f01006b cmp      w8, w0
004e0390 03ffff54 b.lo     #0x4e0370
004e0394 17000014 b        #0x4e03f0
004e0398 280140b9 ldr      w8, [x9]
004e039c a96f01d0 adrp     x9, #0x32d6000
004e03a0 29d547f9 ldr      x9, [x9, #0xfa8]
004e03a4 1f050031 cmn      w8, #1
004e03a8 e803881a csel     w8, wzr, w8, eq
004e03ac 280900b9 str      w8, [x9, #8]
004e03b0 167001d0 adrp     x22, #0x32e2000
004e03b4 a80240b9 ldr      w8, [x21]
004e03b8 d6c644f9 ldr      x22, [x22, #0x988]
004e03bc 28faff35 cbnz     w8, #0x4e0300
004e03c0 0f000014 b        #0x4e03fc
004e03c4 e8030032 mov      w8, #1
004e03c8 28010039 strb     w8, [x9]
004e03cc a96f01d0 adrp     x9, #0x32d6000
004e03d0 29d547f9 ldr      x9, [x9, #0xfa8]
004e03d4 08008092 mov      x8, #-1
004e03d8 282100a9 stp      x8, x8, [x9]
004e03dc e00315aa mov      x0, x21
004e03e0 a8164694 bl       #0x1665e80
004e03e4 80faffb5 cbnz     x0, #0x4e0334
004e03e8 177001d0 adrp     x23, #0x32e2000
004e03ec 22000014 b        #0x4e0474
004e03f0 167001d0 adrp     x22, #0x32e2000
004e03f4 d6c644f9 ldr      x22, [x22, #0x988]
004e03f8 e8031f2a mov      w8, wzr
004e03fc e9430091 add      x9, sp, #0x10
004e0400 28d93878 strh     w8, [x9, w24, sxtw #1]
004e0404 18070011 add      w24, w24, #1
004e0408 29a75679 ldrh     w9, [x25, #0xb52]
004e040c e8031b2a mov      w8, w27
004e0410 1f01096b cmp      w8, w9
004e0414 22020054 b.hs     #0x4e0458
004e0418 2ba35679 ldrh     w11, [x25, #0xb50]
004e041c 08050011 add      w8, w8, #1
004e0420 0a3d0012 and      w10, w8, #0xffff
004e0424 4a010b4b sub      w10, w10, w11
004e0428 2b334bb9 ldr      w11, [x25, #0xb30]
004e042c 5f010b6b cmp      w10, w11
004e0430 a2000054 b.hs     #0x4e0444
004e0434 2b9f45f9 ldr      x11, [x25, #0xb38]
004e0438 6ad96af8 ldr      x10, [x11, w10, sxtw #3]
004e043c aafeffb4 cbz      x10, #0x4e0410
004e0440 03000014 b        #0x4e044c
004e0444 ea031faa mov      x10, xzr
004e0448 4afeffb4 cbz      x10, #0x4e0410
004e044c 9f22286b cmp      w20, w8, uxth
004e0450 a1efff54 b.ne     #0x4e0244
004e0454 1e000014 b        #0x4e04cc
004e0458 68070011 add      w8, w27, #1
004e045c 9f22286b cmp      w20, w8, uxth
004e0460 21efff54 b.ne     #0x4e0244
004e0464 1a000014 b        #0x4e04cc
004e0468 167001d0 adrp     x22, #0x32e2000
004e046c 177001d0 adrp     x23, #0x32e2000
004e0470 d6c644f9 ldr      x22, [x22, #0x988]
004e0474 f7ca44f9 ldr      x23, [x23, #0x990]
004e0478 e0ffff17 b        #0x4e03f8
004e047c 080115ab adds     x8, x8, x21
004e0480 e0fbff54 b.eq     #0x4e03fc
004e0484 08014079 ldrh     w8, [x8]
004e0488 ddffff17 b        #0x4e03fc
004e048c e00316aa mov      x0, x22
004e0490 d4b77494 bl       #0x220e3e0
004e0494 177001d0 adrp     x23, #0x32e2000
004e0498 f7ca44f9 ldr      x23, [x23, #0x990]
004e049c 00010034 cbz      w0, #0x4e04bc
004e04a0 ff0200b9 str      wzr, [x23]
004e04a4 167001d0 adrp     x22, #0x32e2000
004e04a8 d6c644f9 ldr      x22, [x22, #0x988]
004e04ac e00316aa mov      x0, x22
004e04b0 d0b77494 bl       #0x220e3f0
004e04b4 f50317aa mov      x21, x23
004e04b8 6fffff17 b        #0x4e0274
004e04bc 167001d0 adrp     x22, #0x32e2000
004e04c0 d6c644f9 ldr      x22, [x22, #0x988]
004e04c4 f50317aa mov      x21, x23
004e04c8 6bffff17 b        #0x4e0274
004e04cc b8010034 cbz      w24, #0x4e0500
004e04d0 e0030091 mov      x0, sp
004e04d4 c3265394 bl       #0x19a9fe0
004e04d8 e0030091 mov      x0, sp
004e04dc 01275394 bl       #0x19aa0e0
004e04e0 087cb89b umull    x8, w0, w24
004e04e4 09fd60d3 lsr      x9, x8, #0x20
004e04e8 08fd6093 asr      x8, x8, #0x20
004e04ec 3f810071 cmp      w9, #0x20
004e04f0 e9430091 add      x9, sp, #0x10
004e04f4 08319f9a csel     x8, x8, xzr, lo
004e04f8 20796878 ldrh     w0, [x9, x8, lsl #1]
004e04fc 02000014 b        #0x4e0504
004e0500 e0031f2a mov      w0, wzr
004e0504 fd7b4aa9 ldp      x29, x30, [sp, #0xa0]
004e0508 f44f49a9 ldp      x20, x19, [sp, #0x90]
004e050c f65748a9 ldp      x22, x21, [sp, #0x80]
004e0510 f85f47a9 ldp      x24, x23, [sp, #0x70]
004e0514 fa6746a9 ldp      x26, x25, [sp, #0x60]
004e0518 fc6f45a9 ldp      x28, x27, [sp, #0x50]
004e051c ffc30291 add      sp, sp, #0xb0
004e0520 c0035fd6 ret

; coast_grid_to_cell_records ELF 0x4e0c90 size=204 sha256=8bed71370f14461551a3d699dcce9ac72c0fe4ea765d9182f762a8550a32943c
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

; coast_cell_coordinate_write ELF 0x4de610 size=8 sha256=53b84432c64767644f989182ad0f290602bcd86565a83d6aa17922d7e88da633
004de610 01880129 stp      w1, w2, [x0, #0xc]
004de614 c0035fd6 ret

; coast_grid_accessor ELF 0x4de8c0 size=48 sha256=21d9bd6e4d020cbe5b8748b117fde0614b1f5185560fd54119768c0205b97580
004de8c0 3f240071 cmp      w1, #9
004de8c4 28010054 b.hi     #0x4de8e8
004de8c8 480c020b add      w8, w2, w2, lsl #3
004de8cc 0801010b add      w8, w8, w1
004de8d0 09c4288b add      x9, x0, w8, sxtw #1
004de8d4 1f210171 cmp      w8, #0x48
004de8d8 2831809a csel     x8, x9, x0, lo
004de8dc 5f200071 cmp      w2, #8
004de8e0 e083889a csel     x0, xzr, x8, hi
004de8e4 c0035fd6 ret
004de8e8 e0031faa mov      x0, xzr
004de8ec c0035fd6 ret

; selected_template_setup ELF 0x528bf0 size=476 sha256=725d2c3f3ddebcb59103aab321d735e8625155987ca2eff0b71ebc1eaf67feb1
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
