# Post-prologue UI/resource-family follow-up

Scope: day-2 Workbench/DIY, facility/plot placement, office and campsite announcements, Island Evaluation, first K.K. live/credits, and Island Designer install. The audit reads index/catalog data only; it does not change Godot, copy raw model/audio payloads, or alter the main crosswalk.

## Evidence result

The strongest useful result is structural: selected BFLYT records can be traced through pane→material→texture→unique same-archive BNTX, font aliases can be followed into FontInfo resources, named GLSL can be tied to material records, and BFLAN tags/tracks can be tied to same-archive panes/materials. These links make the UI assets usable as conversion references. They do not establish that a story action opens the page or runs a given animation. No beat→page runtime association was upgraded to proven.

Status meanings: `EXISTS` means an indexed source exists; `PSEUDO` means an exact static page getter string but no runtime page load; `CANDIDATE` means a plausible semantic association; `CONSUMER_JOINED` means a direct structural resource relation; `OPEN` means no exact runtime consumer is established.

## Beat-to-layout audit

| Beat | Candidate layout/resource family | Exact evidence | Runtime page/action join |
|---|---|---|---|
| day2.workshop_diy | WorkBench, WorkBenchInfo, WorkBenchBG, MenuRecipe | Ftr_Working | OPEN |
| shop-place-open-and-unlock-plots | MenuMapFull, LMapIconMarket, LMapIconNewPlace | StructureStartPreviewGuide(cMarket,cPlayer) [data.Player_HousingKit.entries.ShopReserveKit.notable_actions[1]]; Daily shop processor checks structure type 0 [§0.5 / §5.3 / 0xfc4560]; Demo_PublicAnnouncement_21_CmnEvChk:ChkMarket [MarketOpen1stDay1 → result 13=1] | OPEN |
| bridge-and-ladder | ShopBridgeSlope, ShopBridgeSlopeBG, MenuMapFull, LMapIconBridge, LMapIconSlope | SNPC_rco_53_MigrantsQuest:FirstIntroduction [PlayerSetCraftRecipe ItemUniqueId=7211]; StructureStartPreviewGuide(cBridge,cPlayer) [data.Player_HousingKit.entries.BridgeReserveKit.notable_actions[1]]; Player_Demo_HousingFinish:HousingFinish_Bridge [UIPocketMenuItemSelected UID 7211 → ImmQ_SetBridge] | OPEN |
| three-housing-plots | MenuMapFull, LMapIconNPCHouse, LMapIconNewPlace | SNPC_rco_53_MigrantsQuest:GetHousingKit [SetItemToPocket 5827/5828/5829; ImmQ_A/B/C_GetHousing]; StructureStartPreviewGuide(cReserveNpcHouse,cSettlerQuest) [MigrateQuestA/B/C events 168-170]; Player_Demo_HousingFinish:HousingFinish_NnpcImmigrateQuestA [events 23,78,98] | OPEN |
| plot-furniture-requirements | MenuMapFull, LMapIconNPCHouse | Obj_ReservedPlaceBox:DelFtrA1/DelFtrA2/DelFtrA3 [DeleteSelectedSettlerQuestInsideMaterial then ImmQ_A_Interior1-3Donate]; Obj_ReservedPlaceBox:ChkOutdoorFtrA [OutsideCheckType 0-2]; Demo_PublicAnnouncement_Process:ImmQFtrChkA [checks all 3 interior flags and OutsideCheckType=3] | OPEN |
| office.opening_isabelle | MenuMapFull, LMapIconOffice, CmnDialog | Structure kind 1 present at day change [0x10c2ad0]; Isabelle public announcement [PAnnounceSza] | OPEN |
| office.ceremony_and_island_dev | MenuMapFull, LMapIconOffice, CmnDialog, CmnDialogBG | Enable Island Development quest [OfficeOpening_Force:#35]; Request office ceremony stage [#234/#283] | OPEN |
| campsite.build_and_ceremony | MenuMapFull, LMapIconCamp, CmnDialog | PlayerSetCraftRecipe [CampSiteRequest:#2 UnlockType=CampSite, ItemUniqueId=65534]; RcoBuildCampsiteComplete [§9 campsite]; Native facility state check [0xf26330] | OPEN |
| campsite.first_camper | MenuMapFull, LMapIconCamp, CmnDialog | Set first camper visit/request flags [FirstCamperCheck]; Grant first camper housing kit [SetFirstCamperHouseRequest:#116 SetItemToPocket ItemUniqueId=3349]; Amiibo campsite unlock [FirstCamperCheck:#14] | OPEN |
| island_evaluation.rating | CmnDialog | Set IslandEvaluationUnlock [IslandEvaluationRunning:#153]; IslandEvaluationChk [IslandEvaluationChk]; Score classifier/aggregator [§10.1; functions 0x15c4590, 0x15c61f0] | OPEN |
| kk.first_live_unlock_and_announcement | CmnDialog | ClearTkkFirstLiveScore [ClearTkkFirstLiveScore]; Enable first-live schedule [0xfd8920]; Reserve and change stage [Root_Init #83/#91; PAnnounceSza #41] | OPEN |
| kk.first_live_performance_and_credits | StaffCredit, CmnDialog | Request song by context [Root:#17 TkkRequestSongSet SelectSongMethod=cTkkSelectSongMethod_ToContext]; Performance enter/live/exit [Tkk_LiveDemoEnter:#35/#37; Tkk_LiveDemoExit:#36]; Mark first-live joined [Tkk_LiveAfter_Flag:#142-#141] | OPEN |
| kk.post_live_island_designer | MenuDevice, WipeDevice, RingMenuTools | Grant Welcome Horizons [InvitePlayerHouse:#10 ItemUniqueID=4318]; Enable Island Designer app [InvitePlayerHouse:#16/#17]; Clear follow-up standby [InvitePlayerHouse:#31] | OPEN |

### Important separation

- DIY story evidence includes `RcoTentAskDIYtrial`/`Ftr_Working`; page-method bindings name `WorkBench`, `WorkBenchInfo`, `WorkBenchBG`, and `MenuRecipe`. That supports a strong candidate family, while an action→page caller/render trace remains open.
- The `StructureStartPreviewGuide(cMarket/cBridge/cReserveNpcHouse, ...)` action does not map to a named BFLYT preview page in the available index. `ShopBridgeSlope` is a bridge/slope shop/style page candidate and must not be treated as proof of the placement preview UI.
- `MenuMapFull` has exact BFLYT part references to the `LMap` structure; `LMap` in turn has exact part references to facility/bridge/house/camp icons. These are structural map-resource joins, not proof that a quest action opens the map or selects a marker state.
- The story action `UIMenuDeviceAppear(EventType=cInstall, Application=cConstructLicense)` makes `MenuDevice` a candidate for the Island Designer app-install surface. The static `MenuDevicePage → MenuDevice` identifier exists; the separate page-registry/factory association is still marked name-only/unproven, and the action-to-page runtime caller is open. The page index also has an `cWorkCraft` registry entry that does not normalize to an exact factory class, despite static WorkCraft page getters returning WorkBench layout IDs.
- `StaffCredit` and its role/name child layouts exist, with a `CorporationIn` BFLAN tag. The indexed K.K. flow still has no direct credit trigger. `MenuPointResult*` was not promoted as Isabelle rating UI because its name/layout record does not establish that story consumer.
- Effects: supplemental effect banks exist, but no candidate PTCL emitter or effect-link resource is connected to one of these UI beats. Model/audio remain catalog-only and were not expanded here.

## Layout resource joins

Rows below are selected page/layout candidates plus exact BFLYT `prt1` dependencies recursively reached from them. Direct beat association remains candidate; child dependencies are structural.

| Layout | Beat association | Static page ID (PSEUDO) | Source archive status | BFLYT SHA-256 | Pane→mat→BNTX joined / texture edges | Font | Named GLSL joined | BFLAN tags (track count) |
|---|---|---|---|---:|---|---:|---|
| CmnDialog | CANDIDATE | CommonDialogPage → CmnDialog | new_path | `13032dc728e51e954d5ee85a98965f4807efd6b85cdd86fbbd179fd6d1fde6ee` | 14 / 14 | SystemB_00.fcpx | 2 | Error(24); In(12); StopRandom(12); State(2); Loop(8); Out(12); Type(42); InEffect(40) |
| CmnDialogBG | CANDIDATE | CommonDialogBGPage → CmnDialogBG | new_path | `6e677f5451d99e8d3812649f2dcf3c3c37c2c9c18c49b02b4158ff01b0142e67` | 0 / 0 | — | 0 | In(1); Out(1) |
| LBtnListShopBridgeSlope | CONSUMER_JOINED | — | new_path | `343ac78185eff755ea5e5adacf5a26e05dba2a93b461436104b74d976a86e241` | 0 / 0 | — | 0 | In(1) |
| LBtnListShopBridgeSlopeBtn | CONSUMER_JOINED | — | new_path | `1b9bd9b951f2329975f61da25ee72b9cf3981bc2579bfe1bd68ca088955fc7eb` | 6 / 6 | SystemB_00.fcpx | 0 | Select(12); Loop(2); Decide(12) |
| LCmnBg | CONSUMER_JOINED | — | new_path | `e3b2cf926848588556c9235bcfe4225ce3f3245794f0ffcbb73a7260fa498f8b` | 3 / 3 | — | 0 | — |
| LCmnDialogBtn | CONSUMER_JOINED | — | new_path | `658df7d240b12c3c5a368628e532f384321c7feef67161df8904668c409af4dd` | 9 / 9 | SystemB_00.fcpx | 0 | Decide(53); Invalid(2); InvSelect(2); Loop(8); InvDecide(3); Select(8) |
| LCmnScrollBar | CONSUMER_JOINED | — | new_path | `3ad3abece2f905e86288f316c254d6c0407d4ecf349b0aa60928442a04de3d93` | 0 / 0 | SystemB_00.fcpx | 0 | GuideOff(1); Select(1); Invalid(1); Volume(1) |
| LCursor | CONSUMER_JOINED | SelectCursorPage → LCursor | new_path | `5fb7a886081ba301bc31bd6391ea4257a4b956134fa5ee85a429aa901cbbac55` | 3 / 3 | — | 0 | Loop(4); Drag(3); Type(2); In(1); Decide(2); Release(2) |
| LDIYCategory | CONSUMER_JOINED | — | new_path | `7412666e064603d402aeff112134644157f1a5aa6e11d667beef24ae16b57ea2` | 2 / 2 | SystemB_00.fcpx | 0 | Pattern(1); Select(8) |
| LIconLoad | CONSUMER_JOINED | — | new_path | `c55f1e401bf8d892b56d5b0bec6b83f94a1427f739fec76696b154fcc2127d76` | 16 / 16 | — | 0 | In(1); Loop(40) |
| LMap | CONSUMER_JOINED | — | new_path | `dbb99edb76a41fd8f5aaa7354b8c83366562a2f60eb1a6d934cdc83ed2f36f6e` | 35 / 35 | SystemB_00.fcpx | 0 | In(1); Out(1) |
| LMapBtn | CONSUMER_JOINED | — | new_path | `90b1ef597ad5afc0a971e9ef7c0058c334d70693fde765f012ab49d49125e2a8` | 8 / 8 | — | 0 | Loop(7); StopRandom(1); Select(9); SelectLoop(1); Decide(2); Cancel(2); Normal(7); IconType(5) |
| LMapBtnBuilding | CONSUMER_JOINED | — | new_path | `86b6c4d386e6c178d6c32daeb2128adb9d7abaa753292f5be84b0d37b12c2610` | 11 / 11 | — | 0 | Select(9); Decide(1); AirPortType(1); Loop(7); Cancel(1); IconType(4); SelectLoop(1); Normal(7) |
| LMapIconAirport | CONSUMER_JOINED | — | new_path | `44f0c2308513de12eca089562ab004808a6663a4bb74d38d66752301b69c1232` | 1 / 1 | — | 0 | In(1); Normal(6); Attention(6); Type(1) |
| LMapIconBridge | CANDIDATE | — | new_path | `4b700da2e9b9f97becead0568a84f87e19fccb2486bcb4acaf2e27e946078a50` | 0 / 0 | — | 0 | In(1); Normal(7); Type(3); State(11); Attention(7) |
| LMapIconCamp | CANDIDATE | — | new_path | `90c6c84c679449f46d1357d7d407605c4ff61b5d407fdf21712c52119262195d` | 1 / 1 | — | 0 | Type(1); Attention(6); In(1); Normal(6) |
| LMapIconInfoTent | CONSUMER_JOINED | — | new_path | `5a2a4b8bf5698e07e26a9ba10ab4a025a9994f0d7e8c31d05ff5f50d4133ec4f` | 1 / 1 | — | 0 | In(1); Type(1); Normal(6); Attention(6) |
| LMapIconMarket | CANDIDATE | — | new_path | `a78acf3cf399b49898360ee9c04402ecc90206d34df9b772a51c5f9122c094da` | 1 / 1 | — | 0 | Normal(6); In(1); Attention(6); Type(1) |
| LMapIconMuseum | CONSUMER_JOINED | — | new_path | `0ff39109b0b0693877fe2b58d5f95c5e7e48a8629c527ab19ee7692056606d02` | 1 / 1 | — | 0 | Normal(6); In(1); Type(1); Attention(6) |
| LMapIconNPCHouse | CANDIDATE | — | new_path | `5d5366e86bbed96ce41773a3aeebcc75547c504c09971e27f479d173207fa48e` | 1 / 1 | — | 0 | In(1); Type(2); Attention(6); Normal(6) |
| LMapIconName | CONSUMER_JOINED | — | new_path | `3e79d686afdd25801f6d446843334a8474e4696efa7618ec7a837d95a39788f8` | 5 / 5 | SystemB_00.fcpx | 1 | Attention(3); Out(1); Normal(1); RegionLanguageType(1); In(4); Loop(1) |
| LMapIconNewPlace | CANDIDATE | — | new_path | `82eec4f1e489b0d0d02448e29510a7f822655b73be006fed96c42ff65a695b6f` | 6 / 6 | — | 0 | Type(6); Attention(36); In(1); Normal(36) |
| LMapIconOffice | CANDIDATE | — | new_path | `8184d4d3ab7322cc1e83cb02103286c3eaf355219a8053fb21b8978602bc1a37` | 1 / 1 | — | 0 | Type(2); Normal(6); Attention(6); In(1) |
| LMapIconOpenSpace | CONSUMER_JOINED | — | new_path | `4707a24335b8a31e8123c39388891ac753ab9d5aa96a11d48c968fa515625740` | 1 / 1 | — | 0 | Attention(3); Normal(3); In(1); Type(1) |
| LMapIconPlayer | CONSUMER_JOINED | — | new_path | `606d26506f1c59d5319708ca6cd38b6ce7ae67922e0f4d0b34317d3ef69468c6` | 1 / 1 | — | 0 | In(1) |
| LMapIconPlayerHouse | CONSUMER_JOINED | — | new_path | `588730f6be27c1b8498496ecab95634bfc550dc8c7bb92920e3ec9a3f7cb668d` | 1 / 1 | — | 0 | In(1); Normal(6); Attention(6); Type(2) |
| LMapIconSlope | CANDIDATE | — | new_path | `5d52b731ab001f92dfc8264a54431dab313f86e98ec6e296e7c0c4bf9110c683` | 3 / 3 | — | 0 | In(1); Type(3); State(2); Normal(7); Attention(7) |
| LMapIconTailor | CONSUMER_JOINED | — | new_path | `5b4de90bcedf5af1e2e14af1fc543f4d4f53c2409e129e5949d877cbbad68e26` | 1 / 1 | — | 0 | In(1); Type(1); Attention(6); Normal(6) |
| LMapOptionNoticeWin | CONSUMER_JOINED | — | new_path | `f3c44328e7bd3d8102b05748e885347b96c72d0cec2af23a63203543e60ef9d7` | 1 / 1 | SystemB_00.fcpx | 0 | Type(1); In(2); Out(2) |
| LMaterial | CONSUMER_JOINED | — | new_path | `361a0d466e10be59ab72ae95de062ba2fb7d0d5dec99727c57fdf1e676176228` | 3 / 3 | SystemB_00.fcpx | 0 | GaugeSize(5) |
| LMenuDeviceBtn | CONSUMER_JOINED | — | new_path | `1a879bc34abd005d8a9a4cf49e5c38ae8fd4177f69c52f6c82f64f612f785055` | 95 / 95 | — | 1 | Type(35); Invalid(3); Select(95); SelectLoop(92); Decide(93); State(3); DemoInstall00(43); Normal(100); DemoInstall01(33) |
| LMenuDeviceIndicator | CONSUMER_JOINED | — | new_path | `842166fca1730abce730d82352e221b70a5eeee33fc8333346477d7118b45678` | 27 / 27 | — | 0 | Num(27) |
| LNookLogo | CONSUMER_JOINED | — | new_path | `8ac192329b66159daf2481e067dab58ba4e07498f820b360b85276a353aa58fd` | 3 / 3 | — | 0 | RegionLanguageType(5) |
| LPlayerIcon | CONSUMER_JOINED | — | new_path | `fdbf0a7521686215f5ec5dedac25b2fccb166df8f833c86779b1ef3f737e14ac` | 8 / 8 | — | 0 | EyeColor(6); HairColor(6); FaceColor(7); CheekColor(6) |
| LPocketBalloon | CONSUMER_JOINED | — | new_path | `0464435347502485c5064edab491e9e7eb56054596c06583728f869c564f8fe7` | 4 / 4 | SystemB_00.fcpx | 1 | Loop(2); BeakPos(1); In(3); Out(3) |
| LRecipeBtn | CONSUMER_JOINED | — | new_path | `99022bc02feef36712b7cb81a2b5aff7bd6a3597dea6c38516dc9219c442cbd6` | 28 / 28 | SystemB_00.fcpx | 0 | New(1); Select(3); BtnListRandom(1); State(3); Decide(3); Remake(1); EquipOut(14); UnSelect(3); Loop(12); BoardColor(96); StorageNum(1); EquipIn(54); PocketNum(2); Check(1) |
| LRecipeBtnList | CONSUMER_JOINED | — | new_path | `7f7729e0cd0630611f26633c2bca373d779d8c27185147cadb906ed4f5409588` | 0 / 0 | — | 0 | — |
| LRecipeMaterial | CONSUMER_JOINED | — | new_path | `b01b853a99cd5cbdfae13290afdc47c12bb5d72b49c830430eaa8a123918684c` | 3 / 3 | SystemB_00.fcpx | 0 | GaugeSize(6) |
| LRingMenuItemName | CONSUMER_JOINED | — | new_path | `02c659c8f2c566761c7a9258e2d025398d22f9c3154d47e27bb18a4c86576178` | 4 / 4 | SystemB_00.fcpx | 1 | In(3); Loop(2); Out(3); BeakPos(1) |
| LRingMenuTools | CONSUMER_JOINED | — | new_path | `3edc1b8043cdf264363f0f3c0290e5c688754a7edd16e09b98d902d95e57162d` | 16 / 16 | — | 0 | Inv3(2); Inv4(2); ActiveReg(1); Inv5(2); Inv6(2); InEffect(64); Inv0(2); Inv7(2); Out(25); Inv1(2); In(25); Inv2(2) |
| LRingMenuToolsBtn | CONSUMER_JOINED | — | new_path | `6517a01f0fc37a91b91525081de18a8b77e0d1ca30189a34fdefaa3d5fcfeedb` | 39 / 39 | — | 4 | Loop(8); UnSelectActiveReg(5); Select(8); Decide(104); SelectActiveReg(9); EquipOut(7); DecideActiveReg(12); UnSelect(8); ActiveReg(2); EquipIn(7); Confirm(14); InvAnim(21) |
| LSaveIcon | CONSUMER_JOINED | — | new_path | `b1280d3fd78e6ba971f398e8df635312479a3eddb6d4fcfefffdeebdd6fb5db3` | 16 / 16 | — | 0 | Loop(40); Out(3); In(3) |
| LShopPriceTagBridgeSlope | CONSUMER_JOINED | — | new_path | `4ec28560fec0a19f6dca0bdd3d6efbf68a9b3dc65d6caa8a674463fd07fa5d34` | 1 / 1 | SystemB_00.fcpx | 0 | In(1); Attack(1) |
| LStorageNoticeWin | CONSUMER_JOINED | — | new_path | `61cce12ef03b51c95cb15d860570c0833e106fbab051ed5b100f00240ba1bada` | 0 / 0 | SystemB_00.fcpx | 0 | Out(2); In(2) |
| LWorkBenchBtnList | CONSUMER_JOINED | — | new_path | `4c33f1f82c9eb43fbe342bf810015ead23cfd52f7ef88ed94e723f359814d999` | 0 / 0 | — | 0 | — |
| LWorkBenchCardBtn | CONSUMER_JOINED | — | new_path | `207415b768ebab049cb97883891882c4265cc02068a441721236e8bc5e83fd1d` | 27 / 27 | SystemB_00.fcpx | 0 | State(5); EquipOut(6); Select(3); EquipIn(54); New(1); Decide(3); Remake(1); PocketNum(2); UnSelect(3); Invalid(1); BoardColor(91); StorageNum(1); CanMake(1); Loop(15); BtnListRandom(2) |
| LWorkBenchMakeBtn | CONSUMER_JOINED | — | new_path | `34c348bb4d13c6149c6000441b795732fb08b27ebae83eb526ae214821272b5d` | 9 / 9 | SystemB_00.fcpx | 0 | Decide(53); Loop(8); Invalid(2); InvSelect(2); InvDecide(3); Select(8) |
| LWorkBenchScrollBarRe | CONSUMER_JOINED | — | new_path | `1051f3142ec0f9335a402d9103f6863a33be4a4bc617c56e36bb5e6140cf8214` | 0 / 0 | SystemB_00.fcpx | 0 | Volume(1); Select(1); Invalid(1); GuideOff(1) |
| MenuDevice | CANDIDATE | MenuDevicePage → MenuDevice | new_path | `4a241584f43ecc1e0e28449bccce710346eec748cd569c1149276f74bfd11b69` | 23 / 23 | SystemB_00.fcpx | 0 | VisibleOff(5); DemoStart(128); RegionLanguageType(2); Out(22); Loop(3); VisibleOn(2); In(110); DemoInstall(36); Time(1) |
| MenuMapFull | CANDIDATE | MapPage → MenuMapFull | new_path | `688a04a65e4e70c096e5d0b6d582d901e8a602ac1f2f66d5fd37ba41c62f8d46` | 28 / 28 | SystemB_00.fcpx | 0 | MapIn(3); Loop(38); TypeBuilding(30); In(14); TypeResident(90); Load(1); Out(13) |
| MenuRecipe | CANDIDATE | MenuRecipePage → MenuRecipe | new_path | `c54f8be27c12465de6bea65a2ff80f0b1533c25a9dad82e873623f81f3c6b60e` | 20 / 20 | SystemB_00.fcpx | 0 | SizeType(1); SizePattern(1); PocketNum(12); CategoryNum(27); In(6); Empty(3); MaterialNum(6); StorageNum(12); SizeH(1); StorageOff(5); Share(2); SizeW(1); Category(1); Out(6) |
| RingMenuTools | CANDIDATE | RingMenuToolsPage → RingMenuTools | new_path | `5e57475bac83134b19fbbe1b2259c3b5605c424e6f559cace613ed6d87b0cce5` | 0 / 0 | — | 0 | — |
| ShopBridgeSlope | CANDIDATE | ShopBridgeSlopePage → ShopBridgeSlope | new_path | `85af12e9c3f61ef43dcc8413cf05c179684ef12376e8d67d5723aa1c6d931f2e` | 4 / 4 | — | 0 | Out(7); In(6) |
| ShopBridgeSlopeBG | CANDIDATE | ShopBridgeSlopeBGPage → ShopBridgeSlopeBG | new_path | `75f1e93137a918a5b325fa3d15acef0e584731d93a93939a0079b4b20a1ef099` | 1 / 1 | — | 0 | In(1); Out(2); InEffect(1) |
| StaffCredit | CANDIDATE | StaffCreditPage → StaffCredit | new_path | `6bb0365cdf659e0ae692efde31b9eb3c67893c5f4d0784251b7cea98a79ea369` | 0 / 0 | SystemB_00.fcpx | 0 | CorporationIn(1) |
| StaffCreditNameDouble | CONSUMER_JOINED | — | new_path | `bce72c9398a48598d949460159080810365ee8c3d3671a763d43ca31d975ca96` | 0 / 0 | SystemB_00.fcpx | 0 | — |
| StaffCreditNameSingle | CONSUMER_JOINED | — | new_path | `c2155b4066b31fa1f4d616a873356d845474cdbe19f321b868629fb5992dab7f` | 0 / 0 | SystemB_00.fcpx | 0 | — |
| StaffCreditRole | CONSUMER_JOINED | — | new_path | `09497f416893f9d37914c6931308430917b722da08e0f9c54e7d35e4f60f64fc` | 0 / 0 | SystemB_00.fcpx | 0 | — |
| WipeDevice | CANDIDATE | DeviceContentBootWipePage → WipeDevice | new_path | `64e8761ba48597e514bf920497bfc280ab32e24d768094a0737930e4bc1f6586` | 4 / 4 | — | 0 | Loop(3); Type(13); OutAppClose(9); Out(15); In(16); InAppClose(9) |
| WorkBench | CANDIDATE | WorkCraftListPage → WorkBench | new_path | `475188c3996c5ecca9e4d95d32ccee704696e4bdf850916e307590f2e2a1bd0b` | 4 / 4 | SystemB_00.fcpx | 0 | In(5); Change(1); Share(2); Out(2); CategoryNum(27); Empty(1) |
| WorkBenchBG | CANDIDATE | WorkCraftBgPage → WorkBenchBG | new_path | `74538ae233d2a481c899a890bc677e619fa7af71a2226a5464782ee1f3a01e19` | 5 / 5 | — | 0 | In(4); Change(3); Out(2) |
| WorkBenchInfo | CANDIDATE | WorkCraftInfoPage → WorkBenchInfo | new_path | `f8b7af3e4acd855e3ea991d0decaa62fc9fa60911397a8a526e739921cb62735` | 35 / 35 | SystemB_00.fcpx | 4 | PressLeft(6); EquipIn(54); StorageOff(5); SizeW(1); State(1); SizePattern(1); EquipOut(6); Category(1); New(1); PocketNum(12); Change(11); Loop(3); SizeType(1); MaterialNum(6); PressRight(6); Remake(1); Out(2); StorageNum(12); SizeH(1); In(2) |

The JSON companion contains the full edge list per pane/material/texture and the exact font, GLSL and BFLAN member hashes. A page-method hit is labeled `PSEUDO`: its getter returns that exact layout identifier, but no action/page load is implied. Separate factory/registry matches remain `name_only_candidate_unproven` unless stronger caller evidence exists. `__ArchiveShader.bnsh` records remain compiled shader candidates without variant/draw confirmation.

## Effect index

The supplemental resource inventory contains these effect/link assets; all are `EXISTS`, while their consumer joins remain `OPEN`:

| Source | Member | SHA-256 |
|---|---|---|
| ELink2/ELink2DB.szs | (container) | `d23076a07689cc903f59cdb0280e98db00055cb9eb0f44ee8944ecca74a2718b` |
| ELink2/ELink2DB.szs | ELink2DB.belnk | `74253a530471274b0ee1d2593d6a817e98b9dd32d02944a9befd1f9f99fd6f07` |
| Effect/Park_Idr.Nin_NX_NVN.szs | (container) | `885d691577295d57900a0ee78420ed362947ec14bb8368c4ef684704d0c844bc` |
| Effect/Park_Idr.Nin_NX_NVN.szs | Particle.Nin_NX_NVN.ptcl | `38d6a986ae156960bc37c8f6b397b4b01a224325d3f8d886eee0e351a49d0dc2` |
| Effect/Park_Static.Nin_NX_NVN.szs | (container) | `8403c69e1d7e18c75f8797ea541623d201e52d22c607eb81a654bd872bfabde7` |
| Effect/Park_Static.Nin_NX_NVN.szs | Particle.Nin_NX_NVN.ptcl | `55977650362b5363293187b8258ae40e5ba49460429e4cdc695da42cee7ff9d7` |
| SLink2/SLink2DB.szs | (container) | `3b862461be9fc775ada9a864ac063dd7d31eb66cce193d8b4c39f48e9b6513d9` |
| SLink2/SLink2DB.szs | SLink2DB.bslnk | `94fa5b8d5cba04d2004e686a1405b369b393bc261cbaa54679f00909b79b7762` |

## Version and hash limits

- Story flow/action keys use the project baseline `B_data` gameplay evidence; layout sources are from the supplemental additional-RomFS dataset.
- The supplemental manifest has 25,597 files (1,171 content-identical, 24,426 `new_path`) and warns not to infer the exact version from filenames. Each selected layout row carries the manifest classification and container SHA-256; the BFLYT member has its own hash.
- BFLAN/GLSL/font/effect member hashes are included where the supplemental resource inventory provides them. A matching hash identifies bytes, not version compatibility or runtime behavior.
- The full supplemental extracted manifest/resource inventory were read from `/workspace/acnh-re/output/additional_romfs` and referenced by SHA-256 in the JSON; they were not copied.

## Remaining proof gaps

1. Resolve EventFlow/native handlers from `RcoTentAskDIYtrial`, placement guide actions, public-announcement calls, and `UIMenuDeviceAppear(cConstructLicense)` to page constructors or page-request functions.
2. Identify the placement preview renderer/panes/materials and state transitions for shop, bridge, and three housing kits; the shop UI is not a substitute for this proof.
3. Locate Island Evaluation result screen and Isabelle page/message layout, then connect score outputs and message flags to that page.
4. Find the K.K. credit trigger and verify whether the `StaffCredit` family is invoked after the first-live scene.
5. Decode/resolve ELink/SLink/PTCL effect names and link each candidate emitter to a concrete story/action or UI page.
6. Pin the supplemental layout archive build against the baseline `B_data` version before using the resource chain as a one-to-one conversion source.

## Validation

- Selected layouts: 62; BFLYT hashes agree with resource-binding index for all rows: `True`.
- Pane→texture edges: 540; unique same-archive BNTX consumer joins: 540.
- Font refs: 27; named-GLSL consumer joins: 14; BFLAN records: 282 with 282 member hashes.
- No story-action→page runtime link was promoted to proven.

Machine-readable companion: `acnh-re/output/gameplay/post_prologue_ui_resource_family_followup_20261107.json`.
