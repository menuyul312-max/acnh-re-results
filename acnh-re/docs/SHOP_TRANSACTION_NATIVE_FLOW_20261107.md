# Shop transaction: EventFlow to item and money mutation

**Build:** ACNH 1.0.0. **Scope:** Nook tent/Cranny buy and sell flows, native handlers, item-table price lookup, and visible progression effects. This is static ROMFS/native tracing; no live game session or save was executed.

## Findings

The tent interaction has separate choices for material delivery, selling, buying, and ending the conversation. The material-delivery choice is the main-story shop-building quest; buying and selling enter optional economy flows. The ordinary purchase and sale paths can be followed through the EventFlow actions to native item-manager and money-container mutations. The trace establishes in-memory effects and EventFlow flags, but does not establish a durable save/flush boundary.

### Purchase

`SNPC_rcm_01_Tent_1_Entries:Root` routes choice 2 to `SNPC_rcm_00_Common:Rcm_Common_Buy` (choice 1 is selling; choice 0 is material collection). The buy flow opens the shop UI, transfers the chosen item price/name into UI tags, then routes a confirmed choice through `Rcm_Common_BuyCheckUI`. It checks `ShopHasBellCount` at rate `1.0` or `5.0`, shopping capacity with empty-slot sentinel `ItemUniqueId=65534`, and one-space availability in `cPocketBag`. The common action is `ShopBuyDone(UseTailorTicket=false, Set5=false/true)`.

The native action is `MainNpc.EventFlowActionShopBuyDone`, slot 11 at raw PC `0x2c8d10`. It reads the selected item descriptor from the UI result and computes its price through `FUN_00baaa80` (`0x00baaa80`): the reader requests the `ItemParam.Price` field (BCSV hash `0x718b024d`) and multiplies by the selected quantity. The `Set5=true` branch multiplies the selected count by five. A separate conditional discount exists in the helper; its full category predicate is not identified here.

For this flow's `UseTailorTicket=false` branch, `ShopBuyDone` calls `FUN_00ffd440`, which resolves the player's item manager at object offset `+0x17c` and calls `FUN_0109ab70` to debit the amount from money-item stacks. The money lookup uses item ID `2212` (`0x8a4`, ItemParam label `99000Bell`). In the ordinary inventory branch, `ShopBuyDone` calls `FUN_00ffab90` → `FUN_00ffac20` → `FUN_010987c0`; the final helper searches the manager's item slots and writes/updates a slot record. This joins the flow's `cPocketBag` space gate to a concrete item-manager mutation. Some special item classes take alternate branches, so this is proof for the ordinary item branch rather than every shop product.

One explicit product example in the specialized DIY-book subflow is item `5603` (`DIYbook1`, ItemParam price 480); item `5604` (`DIYbook2`, price 2680) is also checked by `SNPC_rcm_11_BuyDIYbook`. That flow calls the shared `Rcm_Common_BuyCheckUI` path and contains `PlayerSetCraftRecipe` actions for `UnlockType=DIYbook1/2/3`. The exact persistent ownership/consumption behavior of each book after its confirmation is not established. These are optional shop recipe unlocks, not the tent's material-gathering gate.

After a purchase, EventFlow sets `cPlayerTemp:RcmBoughtGrocery` and increments `cLifeSupportAchievement:BuyItemRcm` by 1 or 5. These are the flags directly observed in the transaction graph; no main-story construction flag is written by the common purchase action.

### Sale

`SNPC_rcm_00_Common_Sell:Root` opens item selection with `FilterType=cSell`, `Mode=cItemSelect`, and the empty-slot sentinel `65534`. The flow calls `ShopSellCalc(Rate=1.0, IsBox=false)`, writes `SellTotal` into the `cMoney` UI tag, then asks `MoneyCapacity(AddMoney=SellTotal, SellType=cShop)` before confirmation. The confirmed branch calls `ShopSellDone(Rate=1.0, IsBox=false)`.

`ShopSellCalc` is slot 11 of `MainNpc.EventFlowActionShopSellCalc` at raw PC `0x2cb1b0`. It iterates the selected-item bitset, obtains each selected item's `ItemParam.Price` through `FUN_00bab8c0`, applies the action rate, and stores the total in the EventFlow action variable. `ShopSellDone`, slot 11 at raw PC `0x2cbb10`, repeats the selected-item walk to update display tags/counters and calls `FUN_00ffbad0` per selected slot. That helper routes through `FUN_00ffb1f0` to `FUN_01098650`, which mutates the item-manager slot. This is static evidence for removal/decrement of sold selection records; it does not identify a serialized save record.

For `IsBox=false`, the handler compares the sale total with money-container capacity. The wallet-credit route is `FUN_00ffd2f0` → `FUN_00ffd350` → `FUN_0109a5a0`, which writes money-item records (again using item `2212`). When the wallet cannot fit the proceeds, the handler calls `FUN_00fff3d0`, which adds to a separate numeric member at `+0x3288`, capped at `999,999,999`. This looks like the savings/bank balance, but the field's schema/name is not independently resolved, so that label remains a candidate. `IsBox=true` uses another branch (`FUN_00fff5a0`) and is outside the tent path.

The sale flow increments `cLifeSupportAchievement:SellItemRcm` by 1. It has special handling for item categories (including turnips, fruit, shells, and weeds); the exact selected item is runtime UI data, not one fixed ID in the generic sale entry.

## Main-story relationship and limits

The shop-building quest is separate from ordinary commerce: its material flow requests 30 each of softwood `2767`, wood `2768`, hardwood `2769`, and iron nugget `2511`, then awards/places the shop kit through its own flags. The tent menu calls `SNPC_rcm_21_MaterialCollecting` for that choice; it does not pass through `ShopBuyDone` or `ShopSellDone`. Thus the commerce transaction is mapped and usable as an optional gameplay loop, but it is not required to build Nook's Cranny.

**Proven from static evidence:** NPC/menu routing; purchase/sale gates and UI price/total tags; ItemParam price access; purchase debit and ordinary item-slot insertion call paths; sale item-slot mutation and wallet/savings credit branches; recipe unlock and achievement/temp-flag writes.

**Still open:** live confirmation/cancel behavior; exact player inventory ownership/save-object identity behind manager `+0x17c`; whether the `+0x3288` member is definitively the bank balance; every special purchase/sale category; and the durable serialization, flush, and reload of item/money/flag changes. No missing runtime module blocks this static trace; live execution and save durability simply are not evidenced by the available dump.

Models and audio are not used for this transaction proof. Their catalogs do not establish the shop item's visual/audio runtime binding.

## Evidence sources and provenance

Primary decoded flows are `SNPC_rcm_01_Tent_1_Entries.json`, `SNPC_rcm_00_Common.json`, `SNPC_rcm_00_Common_Sell.json`, and `SNPC_rcm_11_BuyDIYbook.json` under `/workspace/analysis/acnh/project/generated/eventflow/`. Handler identities/slots are in `/workspace/analysis/acnh/project/generated/re/evfl_vtables.json`; handler and helper pseudocode is in the generated decomp files named in the JSON ledger. Item IDs/prices are from `/workspace/acnh-re/output/tables_resolved/ItemParam.json`.

SHA-256 values for these primary inputs are recorded in [the JSON ledger](../output/gameplay/shop_transaction_native_flow_20261107.json). The source inputs remain unchanged; this report adds no proof-index or asset-crosswalk edits.
