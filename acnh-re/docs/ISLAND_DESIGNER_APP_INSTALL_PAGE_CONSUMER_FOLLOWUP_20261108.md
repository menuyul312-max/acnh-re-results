# Island Designer app-install request and MenuDevice consumer follow-up (ACNH 1.0.0)

Static follow-up dated 8 November 2026. It traces `UIMenuDeviceAppear(EventType=cInstall, Application=cConstructLicense)` through native request/result storage to the MenuDevice code that consumes the application ID, then checks the matching page and resource keys. Machine-readable evidence is in [`island_designer_app_install_page_consumer_followup_20261108.json`](../output/gameplay/island_designer_app_install_page_consumer_followup_20261108.json). The raw main-NSO disassembly and source index are under `/workspace/acnh-re/output/ui_hud/`; no game, save, or Godot runtime was used.

The new result closes a real app-manager consumer edge. The native `UIMenuDeviceAppear` handler parses `cConstructLicense` as application enum index 9 and maps it to native application ID `0x0c`. It submits that ID to the shared UI-event manager. A separate MenuDevice code-group function reads the same manager field on its `cInstall` (`0x2e`) path, searches the page’s app-entry vector, and stores a matching entry index. This is stronger than an asset-catalogue join: the request’s application payload is consumed by native page-side app-list logic.

## Request and consumer chain

The authored unlock paths are `SNPC_rco_55_TkkFirstLive:InvitePlayerHouse` events 16–17 (set `MainmenuConstructLicense`, then install `cConstructLicense`) and `Player_StartGamePhoneCall:IslandCreaterTell` events 145–146. The invite branch is conditional on baggage space and `TkkFirstLiveReserved`; the phone-call branch’s scheduling and EventFlow start remain unjoined. These sources and their bounds are carried from the 7 November progression follow-up.

Native registration identifies `EventFlowActionUIMenuDeviceAppear` (`49f7be22`) with string parameters `EventType` and `Application`. In callback `0x357770`, the install event takes code `0x2e` (the boot event uses `0x2d`). The Application parser at `0x357990` returns enum index 9 for `cConstructLicense`; callback case 9 writes application ID `12` (`0x0c`) at packet offset `+0x0c`. At PC `0x357984`, the callback calls writer wrapper `0x154a040` (instruction bytes `afc94794`).

The writer and reader share the singleton returned by `0x1544dc0`. Writer path `0x154a040 → 0x15479b0` copies packet `+0x8` to manager `+0xb038` and packet `+0xc` to manager `+0xb03c`. Reader path `0x154a070 → 0x1547940` checks the pending marker at `+0xb038`, consumes and clears it, and returns the manager record base at `+0xb030`. On its `cInstall` path, function `0x125bcd0` calls the reader at PCs `0x125bd4c` and `0x125be04`; the returned pointer’s `+0x0c` is the same application field at manager `+0xb03c`. The function compares this value against app entries and writes a matching entry index at page-object offset `+0x280`. It also writes through the same manager at PC `0x125c1cc`.

The function is the actual native app-manager consumer found in this pass. Its MenuDevicePage attribution remains a strong code-group candidate rather than a typed virtual-method proof: a 19-entry relocated code-pointer sequence at `0x3308100` contains `0x125bcd0`, but the sequence owner/type is not resolved. The independently identified `MenuDevicePage` factory and constructor do not close the action-to-page-instance dispatch.

## Page and resource keys

The `MenuDevicePage` factory is `0x125ae40`, constructor `0x1258460`, and slot-46 layout getter `0x12595f0`. The getter returns the exact string `MenuDevice` at `0x295bfe8`, matching `MenuDevice.arc!blyt/MenuDevice.bflyt` (SHA-256 `4a241584…bfd11b69`). The page registry row named `MenuDevice` has raw argument 22 and a name-matched factory candidate; its dispatch status remains unproven.

The native MenuDevice code also references `DemoStart`, `DemoInstall`, and `DemoInstall00` directly. The resolved static parameter `B_data/Pack/StaticParam.pack!Param/Layout/MenuDevice.byml` identifies user key `UI_MenuDevice`; root animation tags `DemoStart` and `DemoInstall`; and a `Button`/`Btn` part operation using tag `DemoInstall00`. The same supplemental archive has `MenuDevice.arc!anim/MenuDevice_DemoInstall.bflan` with tag `DemoInstall` (130 frames, 184 keys; SHA-256 `c65a4101…734de58c`). `MenuDevice_In` and `MenuDevice_Out` BFLAN members are also indexed. These are concrete resource records and native key references, but no static call chain ties the consumed app result to playback of the `DemoInstall` or `DemoInstall00` operation.

The MenuDevice layout archive is marked `new_path`; its exact update patch is not pinned. The getter’s exact string match establishes the page’s declared layout identifier, not a runtime loader call.

## Join status and bounds

| Join | Result |
|---|---|
| Island Designer EventFlow action → native UIMenuDeviceAppear callback | **Confirmed statically:** action registration and authored events agree on `cInstall/cConstructLicense`. |
| `cConstructLicense` → manager application value | **Confirmed statically:** parser index 9 maps to ID `0x0c`; writer copies it to manager `+0xb03c`. |
| Shared manager → app-list consumer | **Confirmed statically:** `0x125bcd0` reads the shared record on event `0x2e`, searches app entries, and stores a matching index. Runtime list contents were not executed. |
| Consumer function → concrete MenuDevicePage object | **Open:** pointer sequence membership supports code-group attribution; owner/type and instance association remain unresolved. |
| MenuDevicePage getter → BFLYT key | **Pseudo-exact:** slot-46 getter returns `MenuDevice`, equal to the BFLYT member/layout name. Direct getter call count in the full main-text B/BL scan is zero; indirect loader dispatch remains possible. |
| StaticParam/native resource keys → BFLAN members | **Resource records confirmed:** `DemoInstall` matches an exact same-archive BFLAN tag; `DemoInstall00` is configured for `Button/Btn`. Runtime trigger from the install result remains open. |
| First-live progression → actual app installation/save | **Open at runtime:** the flows are authored, but branch selection, UI opening, install persistence, and save commitment were not executed. |

The full text scan is bounded to direct AArch64 `BL` instructions. It finds two writer calls and two reader calls; both reader calls belong to `0x125bcd0`. It finds no direct `B`/`BL` call to getter `0x12595f0`. These negatives do not cover indirect dispatch. Source hashes, exact PCs/bytes, resource member hashes, and the local dump index are recorded in the JSON ledger.
