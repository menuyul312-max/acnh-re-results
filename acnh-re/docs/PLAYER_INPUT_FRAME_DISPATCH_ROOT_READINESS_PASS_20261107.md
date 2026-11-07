# ACNH 1.0.0 controller dispatch and root readiness pass

This pass follows the HID poll method, the controller task callback, the scheduler's task-tree dispatch path, and stores that could affect the world query readiness byte. It uses the existing ACNH 1.0.0 `main.elf` plus the checked-in function inventory/decompilation and relocated code-pointer index. This is static AArch64 evidence only; no game process was run and no gameplay fixture was fabricated.

## Input and scheduler edges

The Npad poll body at raw VA `0x1968b80` is a virtual controller update entry. Its object constructor at `0x1968840` installs the controller table address point, and the pointer at `0x31a4040` (table start `0x31a4020`, offset `+0x20`) resolves to `0x1968b80`. The controller-manager table has its own update target: `0x19a4ab0` is at `0x31a6d78` (table start `0x31a6cc8`, offset `+0xb0`). That method iterates the registered device list and invokes each device's slot `+0x20` through `BLR x8` at `0x19a4af0`. Together these establish the static virtual edge `ControllerMgr update → Npad poll` for an Npad object in the manager list. They do not establish that the manager update itself is run during gameplay.

The separately named `sys::ControllerManager::update()` task is now traced through the scheduler's task-tree dispatcher. Registration at `0x14cef10` stores callback pointer `0x14ceed0` at owner `+0x2f0` (task node `+0x68`), owner pointer at `+0x2e8` (node `+0x60`), and the adapter vptr at `+0x2e0` (node `+0x58`). It links node `owner+0x288` into the scheduler group at global scheduler object `+0x5a0` with `0x14cef94 BL 0x1979ff0`.

The scheduler group walker `0x197a1d0` calls recursive node traversal `0x197a220` at `0x197a1f0`; recursive child traversal calls `0x197a220` at `0x197a25c`. When the node's enable bit permits callback dispatch, `0x197a220` loads node `+0x58`'s first method and invokes it with `BLR x8` at `0x197a244`. For the registered controller task, that adapter table address point is `0x313a6e0`, whose first pointer resolves to `0x14cf150` (the table source is relocated cell `0x330ee98`, plus `0x10`). The adapter reads owner and callback/context words from the descriptor; it reaches `BR x1` at `0x14cf178`, with `x1` loaded from node `+0x68`. Thus the static task-tree route reaches callback `0x14ceed0` with the manager as `x0` when the registered zero context is used.

This proves a static scheduler tree-to-task dispatch route. The indexed evidence does not identify a top-level per-frame caller of `0x197a1d0`, so its runtime cadence is still open. The three direct raw references to the walker found in the code are tail branches at `0x197abe4` and `0x197abf4`, plus a call at `0x197cb4c`; none is enough by itself to label the external frame loop.

The registered callback `0x14ceed0` still does not bridge to Npad polling or mapped player movement. Its body calls `0x14cf380` at `0x14ceee4`, checks manager state at `0x14ceee8`, then returns through `0x14cf390`. It neither calls `0x19a4ab0` nor reads a proven Npad state buffer. No state-to-command translation into movement helpers is established.

## Bounded raw-branch and pointer search

I scanned every aligned word in the ELF executable `PT_LOAD` segment (`VA 0x0`, size `0x2211a60`, flags RX) for immediate AArch64 `B` and `BL` instructions targeting the poll body, controller-manager update, registered callback, and scheduler walker. There are no immediate `B`/`BL` targets for `0x1968b80`, `0x19a4ab0`, or `0x14ceed0`; the callback route is indirect through `0x14cf150`/`BR x1`. The walker target `0x197a1d0` has immediate branches at `0x197abe4`, `0x197abf4`, and `0x197cb4c`. This negative covers direct immediate branches in that executable segment only; it does not rule out runtime indirect dispatch or other images/modules.

The relocated code-pointer index contains `0x1968b80` only at `0x31a4040` and `0x19a4ab0` only at `0x31a6d78`. Neither pointer slot alone proves invocation. The callback `0x14ceed0` is loaded from relocation cell `0x330ee90`, then dispatched by the task adapter as described above.

## Root readiness byte

The readiness predicate at `0x18ba40` follows global reference `0x32d0de8` to singleton storage slot `0x33728b0`, then returns true only when root is non-null, root `+0xa0` is non-null, and the byte at root `+0xf10` is nonzero. Root construction at `0x197740` initializes query context at root `+0x28`; query-context construction at `0x156840` explicitly clears its `+0xee8` byte, which is root `+0xf10`, at raw PC `0x156938`. Grid initialization at `0x156e30` writes the grid pointer at root `+0xa0`, creates the candidate list entry, and initializes terrain backing storage, but it does not write the query-context readiness byte. Its inspected field writes include other offsets (`+0xf20`, `+0xf21`, dimensions at `+0xf24` onward), not `+0xee8`.

I searched the indexed decompilation for explicit stores at offsets `+0xee8`, `+0xf10`, and pointer-index equivalent `+0x1dd`, then filtered those candidate receivers against functions referencing the root singleton and the known root/context initializer path. No nonzero store to the exact root readiness byte was found. Apparent same-offset stores are other objects: `0x15ca690` writes its receiver `+0xf10` and is called with a parent subobject at `+0x606` by `0x165dd50`; startup initializer `0x14ef8f0` clears a distinct object at `+0xf10`; `0x16b4290` writes `+0xee8` in a parsed/output record; and `0x7b1fe0` updates per-record masks. These are offset collisions, not established root writes. The negative is bounded to the available main-ELF function index/decompilation and the identifiable singleton/context path; an indirect setter or omitted ExeFS module could still exist.

## Existing evidence and remaining blockers

Existing artifacts under `output/mechanics` are isolated native checks for terrain/grid contracts, a prepared query-guard branch, a null-singleton boundary, and a separate world registry. They do not supply a running ACNH process, authentic live controller-state buffers, loaded island grid plus candidate list/vtables, or an observed ground-query result. No fixture currently demonstrates live HID-to-player movement or a live ready root.

Remaining open links are: (1) the top-level frame caller/timing for controller-manager update and the task-tree walker; (2) command/state translation from sampled Npad data into the player movement state; (3) a nonzero writer or lifecycle event for root `+0xf10`; and (4) an authentic live root/grid/candidate fixture capable of producing a gameplay query result. Static method/table edges above should not be treated as proof that those runtime results occur.

Source identity: ACNH 1.0.0 `main.elf` SHA-256 `5bf707c3dc5dac0ad9635af7d336ec580f81c3f7876d0f55400d1900e3415d74`; `output/binary/code_pointer_arrays.json` SHA-256 `64d474068ca289f9146f7f32e6647a16a05e8f5be8e635615a478744b62ef822`. Raw ELF VAs/PCs are used throughout.
