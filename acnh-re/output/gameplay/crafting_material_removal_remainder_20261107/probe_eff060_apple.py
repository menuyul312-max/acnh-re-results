#!/usr/bin/env python3
"""Try one original main.elf Apple material removal with bounded synthetic state.

All generated output stays beside this script. The item/stack predicate at
0xaac730 is observed but never patched or intercepted.
"""
from collections import Counter
import hashlib
import json
from pathlib import Path
import sqlite3
import struct
import sys

sys.dont_write_bytecode = True
WORKTREE = Path(__file__).resolve().parents[4]
TOOLS = WORKTREE / "acnh-re" / "tools"
SHARED = Path("/workspace/acnh-re")
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(SHARED / ".deps"))
sys.path.insert(0, str(TOOLS))

from unicorn import UC_HOOK_CODE, UC_HOOK_MEM_READ_UNMAPPED, UC_HOOK_MEM_WRITE_UNMAPPED  # noqa: E402
from native_emulator import Sandbox, regs  # noqa: E402
from native_image import Image  # noqa: E402
import crafting_pocket_manager_probe as pocket_probe  # noqa: E402
import inventory_requirements_native as item_tables  # noqa: E402

item_tables.ROOT = SHARED


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_recipe_56():
    path = SHARED / "output/tables_resolved/RecipeCraftParam.json"
    table = json.loads(path.read_text())
    cols = {column["name"]: i for i, column in enumerate(table["columns"])}
    row = next(row for row in table["rows"] if row[cols["UniqueID"]] == 56)
    return path, table, row, cols


def static_boundary(analysis_elf, index_path):
    """Pin the native call/branch boundary against the original ELF and index."""
    image = Image(analysis_elf)

    def instruction(va):
        decoded = image.disasm(va, 4)
        assert decoded and decoded[0].address == va
        ins = decoded[0]
        return {
            "va": f"0x{va:x}",
            "bytes": ins.bytes.hex(),
            "mnemonic": ins.mnemonic,
            "operands": ins.op_str,
        }

    db = sqlite3.connect(f"file:{index_path}?mode=ro", uri=True)
    try:
        calls = {}
        for owner, target in ((0xEFF060, 0xF9E410),
                              (0xF9E840, 0xAAC910),
                              (0xAAC910, 0xAAC730)):
            calls[f"0x{owner:x}->0x{target:x}"] = [
                f"0x{pc:x}" for (pc,) in db.execute(
                    "SELECT pc FROM direct_calls WHERE owner_va=? AND target_va=? ORDER BY pc",
                    (owner, target),
                )
            ]
        itemkind_field = db.execute(
            "SELECT name, offset, width, type FROM columns_resolved "
            "WHERE table_name='ItemKind' AND hash=?",
            (0x0CE69142,),
        ).fetchone()
    finally:
        db.close()

    assert calls["0xeff060->0xf9e410"] == ["0xeff0e4"]
    assert calls["0xaac910->0xaac730"] == ["0xaac918"]
    assert itemkind_field == ("SaveCountMaxNum", 26, 2, "u16")

    recipe_path, _recipe, _row, _cols = load_recipe_56()
    itemparam = json.loads((SHARED / "output/tables_resolved/ItemParam.json").read_text())
    itemparam_cols = {col["name"]: i for i, col in enumerate(itemparam["columns"])}
    apple = next(row for row in itemparam["rows"]
                 if row[itemparam_cols["UniqueID"]] == 2213)
    apple_kind_hash = int(apple[itemparam_cols["ItemKind"]]["hash"], 16)
    itemkind = json.loads((SHARED / "output/tables_resolved/ItemKind.json").read_text())
    itemkind_cols = {col["name"]: i for i, col in enumerate(itemkind["columns"])}
    fruit = next(row for row in itemkind["rows"]
                 if __import__("zlib").crc32(row[itemkind_cols["Label"]].encode()) == apple_kind_hash)
    assert fruit[itemkind_cols["Label"]] == "Fruit"
    assert fruit[itemkind_cols["SaveCountMaxNum"]] == 0

    addresses = (0xEFF0E4, 0xF9E430, 0xF9E434, 0xF9E874,
                 0xF9E878, 0xAAC918, 0xAAC91C, 0xAAC920,
                 0xAAC74C, 0xAAC760, 0xAAC764, 0xAAC768,
                 0xAAC770, 0xAAC77C, 0xAAC79C, 0xAAC7D0,
                 0xAAC84C, 0xAAC854)
    return {
        "source": "Original analysis main.elf; static disassembly, no code patching.",
        "analysis_elf_sha256": sha256(analysis_elf),
        "shared_index_sha256": sha256(index_path),
        "recipe_table_path": str(recipe_path),
        "direct_calls": calls,
        "itemkind_field_read_by_aac730": {
            "crc32": "0x0ce69142",
            "resolved_column": itemkind_field[0],
            "offset": itemkind_field[1],
            "width": itemkind_field[2],
            "type": itemkind_field[3],
        },
        "dump_row_context": {
            "apple_item_id": 2213,
            "itemparam_itemkind_hash": f"0x{apple_kind_hash:08x}",
            "itemkind_label": fruit[itemkind_cols["Label"]],
            "itemkind_unique_id": fruit[itemkind_cols["UniqueID"]],
            "save_count_max_num": fruit[itemkind_cols["SaveCountMaxNum"]],
            "interpretation_limit": "Resolved dump row only; the controlled probe does not reconstruct the complete live row/cache manager.",
        },
        "instructions": [instruction(va) for va in addresses],
        "control_flow_facts": [
            "0xeff060 calls 0xf9e410 at 0xeff0e4.",
            "0xf9e410 calls 0xf9e840 at 0xf9e430 and tests W0 bit 0 at 0xf9e434; zero branches to its no-change epilogue at 0xf9e4f4.",
            "0xf9e840 calls 0xaac910 at 0xf9e874; zero at the 0xf9e878 test branches to the reject return at 0xf9ebf8.",
            "0xaac910 calls 0xaac730 at 0xaac918, then converts its W0 result to a boolean at 0xaac91c-0xaac920.",
            "0xaac730 reads its record+0x10 value, bounds it against the ItemParam lookup-cache count, and uses an in-range value as an index into a 16-bit kind map; an out-of-range value becomes index zero.",
            "0xaac730 searches a runtime ItemKind row for hash 0x0ce69142 and returns the field value; the resolved schema identifies this as ItemKind.SaveCountMaxNum.",
        ],
    }


def run_probe():
    manifest = json.loads((SHARED / "output/manifest.json").read_text())
    analysis_elf = Path(manifest["source_root"]) / "A_logic/main.elf"
    nso = SHARED / "inputs/additional_exefs/main"
    assert analysis_elf.is_file() and nso.is_file()
    s = Sandbox()
    u = s.uc
    table_info = item_tables.install_item_tables(s)
    recipe_path, recipe, row, cols = load_recipe_56()
    assert row[cols["Material1"]] == 2213 and row[cols["Amount1"]] == 1
    index_path = SHARED / "output/index.sqlite"
    assert index_path.is_file() and index_path.stat().st_size > 0
    static = static_boundary(analysis_elf, index_path)

    fixture = pocket_probe.initialize_manager_fixture(s, 2213, 2213)
    address = fixture.pop("_addresses")
    context = address["mode_context"]
    descriptor = address["item_descriptor"]
    pocket_record = address["pocket_record"]

    # 0xeff060 obtains the player member through the original accessor helpers.
    # At its native player-view boundary, provide only the 0x140-byte inventory
    # member consumed by 0xf9e410: 32 eight-byte IDs, then 32 u16 counts.
    # Slot 0 is table-backed Apple 2213 with nine units.
    inventory = s.HEAP + 0x1c0000
    empty = struct.pack("<HHI", 0xfffe, 0, 0)
    u.mem_write(inventory, struct.pack("<HHI", 2213, 0, 0) + empty * 31)
    u.mem_write(inventory + 0x100, struct.pack("<H", 9))
    u.mem_write(descriptor, struct.pack("<HHI", 2213, 0, 0))
    before = bytes(u.mem_read(inventory, 0x140))
    before_pocket = bytes(u.mem_read(pocket_record, 0x17c))
    original_aac730 = bytes(u.mem_read(0xaac730, 8)).hex()

    watched = {
        0xEFF060, 0xEF6700, 0xF8F400, 0xEE9350, 0xEE9490, 0xEE94F0,
        0xF9E410, 0xF9E434, 0xF9E840, 0xAAC730, 0xA9E440, 0xA774C0,
        0xAB9400, 0xF9E4F4,
    }
    calls = []
    f9e840_checks = []
    check_return_pcs = {}
    for ins in s.image.disasm(0xF9E840, 0x3D0):
        if ins.mnemonic == "bl" and ins.op_str.startswith("#"):
            target = int(ins.op_str[1:], 16)
            if target in (0xF58D00, 0xAAC910, 0xF58AF0):
                check_return_pcs[ins.address + 4] = f"0x{target:x}"
    aac730_return_pc = 0xAAC91C
    final_gate_pcs = {0xF9EBF8: "reject"}
    recent_pcs = []
    faults = []
    view_fixture = []
    error = None
    return_value = None

    def code_hook(uc, pc, _size, _user_data):
        recent_pcs.append(f"0x{pc:x}")
        if len(recent_pcs) > 40:
            del recent_pcs[0]
        if pc not in watched:
            if pc in check_return_pcs:
                f9e840_checks.append({
                    "return_pc": f"0x{pc:x}",
                    "callee": check_return_pcs[pc],
                    "return_w0": uc.reg_read(regs.UC_ARM64_REG_X0) & 0xffffffff,
                })
            elif pc == aac730_return_pc:
                f9e840_checks.append({
                    "return_pc": f"0x{pc:x}",
                    "callee": "0xaac730",
                    "return_w0": uc.reg_read(regs.UC_ARM64_REG_X0) & 0xffffffff,
                })
            elif pc in final_gate_pcs:
                f9e840_checks.append({
                    "pc": f"0x{pc:x}",
                    "gate_path": final_gate_pcs[pc],
                    "w0": uc.reg_read(regs.UC_ARM64_REG_X0) & 0xffffffff,
                })
            return
        regs_x0_x3 = [uc.reg_read(getattr(regs, f"UC_ARM64_REG_X{i}")) for i in range(4)]
        entry = {"va": f"0x{pc:x}", "x0_x3": [f"0x{x:x}" for x in regs_x0_x3]}
        if pc == 0xF8F400:
            entry["resolver_actor_va"] = f"0x{regs_x0_x3[0]:x}"
        if pc == 0xEE9350:
            # Use the pointer returned by native f8f400, not its incoming
            # actor/save-record pointer. ee9350 receives view+0x1c0 here.
            member_ref = regs_x0_x3[1]
            u.mem_write(member_ref + 8, struct.pack("<Q", inventory))
            u.mem_write(member_ref + 0x10, struct.pack("<Q", 0))
            u.mem_write(member_ref + 0x28, struct.pack("<Q", 0))
            view_fixture.append({
                "resolved_view_va": f"0x{member_ref - 0x1c0:x}",
                "member_ref_va": f"0x{member_ref:x}",
                "base_pointer_va": f"0x{inventory:x}",
                "offset": 0,
                "service_pointer": 0,
                "injected_at_native_f8f400_callsite": True,
            })
        if pc == 0xF9E434:
            entry["native_f9e840_return_w0"] = regs_x0_x3[0]
        if pc == 0xF9E410:
            entry["expected_item_descriptor"] = bytes(
                uc.mem_read(regs_x0_x3[1], 8)).hex()
        if pc == 0xAAC730:
            # Observation only: no code or return value patch at this VA.
            entry["predicate_bytes"] = bytes(uc.mem_read(pc, 8)).hex()
            entry["predicate_record_pointer_va"] = f"0x{regs_x0_x3[0]:x}"
            lookup_value = struct.unpack(
                "<Q", bytes(uc.mem_read(regs_x0_x3[0] + 0x10, 8)))[0]
            itemparam_count = len(table_info["item_table"]["rows"])
            entry["predicate_record_plus_0x10_u64"] = lookup_value
            entry["itemparam_lookup_cache_count"] = itemparam_count
            entry["predicate_record_plus_0x10_in_index_range"] = lookup_value < itemparam_count
        calls.append(entry)

    def unmapped_hook(uc, _access, address, size, _value, _user_data):
        faults.append({
            "pc": f"0x{uc.reg_read(regs.UC_ARM64_REG_PC):x}",
            "address": f"0x{address:x}",
            "size": size,
            "x0_x3": [f"0x{uc.reg_read(getattr(regs, f'UC_ARM64_REG_X{i}')):x}" for i in range(4)],
            "recent_pcs": recent_pcs[-24:],
        })
        return False

    u.hook_add(UC_HOOK_CODE, code_hook)
    u.hook_add(UC_HOOK_MEM_READ_UNMAPPED, unmapped_hook)
    u.hook_add(UC_HOOK_MEM_WRITE_UNMAPPED, unmapped_hook)
    try:
        # Material1 is one unit, so the actual transaction passes W2=-1.
        return_value = s.call(0xeff060, (context, descriptor, 0xffffffff), limit=1_000_000)
    except Exception as exc:  # Preserve the exact first boundary in JSON.
        error = f"{type(exc).__name__}: {exc}"

    after = bytes(u.mem_read(inventory, 0x140))
    after_pocket = bytes(u.mem_read(pocket_record, 0x17c))
    count_before = struct.unpack("<H", before[0x100:0x102])[0]
    count_after = struct.unpack("<H", after[0x100:0x102])[0]
    changed = [hex(i) for i, (a, b) in enumerate(zip(before, after)) if a != b]
    return {
        "schema": "acnh.crafting.material_removal_eff060_probe.v1",
        "scope": "One direct original-ELF 0xeff060 call for RecipeCraftParam row 56 Material1 Apple 2213, with a negative one-unit delta. No full transaction, rollback, or durable save is exercised.",
        "provenance": {
            "analysis_elf_path": str(analysis_elf),
            "analysis_elf_sha256": sha256(analysis_elf),
            "main_nso_path": str(nso),
            "main_nso_sha256": sha256(nso),
            "shared_index_path": str(index_path),
            "shared_index_sha256": static["shared_index_sha256"],
            "recipe_table_path": str(recipe_path),
            "recipe_table_raw_sha256": recipe["raw"]["sha256"],
            "itemparam_raw_sha256": table_info["item_raw_sha256"],
            "itemkind_raw_sha256": table_info["kind_raw_sha256"],
        },
        "fixture": {
            "class": "Controlled synthetic player/session/view and inventory member; no real save or live game process.",
            "recipe_id": 56,
            "recipe_material1": {"item_id": 2213, "amount": 1},
            "context_va": f"0x{context:x}",
            "descriptor_va": f"0x{descriptor:x}",
            "descriptor_bytes": bytes(u.mem_read(descriptor, 8)).hex(),
            "inventory_va": f"0x{inventory:x}",
            "inventory_layout": "0x140 bytes: 32 eight-byte descriptors at +0x00..+0xff; 32 u16 counts at +0x100..+0x13f",
            "slot0_before": list(struct.unpack("<HHI", before[:8])),
            "count_slot0_before": count_before,
            "player_manager_fixture": fixture,
            "player_member_view_injection": view_fixture,
            "pocket_view_before_slot0": list(struct.unpack("<HHI", before_pocket[0xb8:0xc0])),
        },
        "execution": {
            "entry_va": "0xeff060",
            "arguments": [f"0x{context:x}", f"0x{descriptor:x}", "0xffffffff (signed -1)"],
            "native_return_x0": None if return_value is None else f"0x{return_value:x}",
            "error": error,
            "first_unmapped_access": faults[0] if faults else None,
            "calls": calls,
            "f9e840_internal_returns": f9e840_checks,
            "native_call_counts": dict(Counter(row["va"] for row in calls)),
            "aac730": {
                "original_bytes_before": original_aac730,
                "original_bytes_after": bytes(u.mem_read(0xaac730, 8)).hex(),
                "patched": False,
                "calls_observed": sum(row["va"] == "0xaac730" for row in calls),
                "return_observed": next((row for row in f9e840_checks
                                          if row.get("callee") == "0xaac730"), None),
            },
        },
        "static_boundary": static,
        "result": {
            "f9e410_reached": any(row["va"] == "0xf9e410" for row in calls),
            "f9e840_return_observed": next((row.get("native_f9e840_return_w0") for row in calls
                                              if "native_f9e840_return_w0" in row), None),
            "f9e410_zero_gate_branch_observed": any(
                row["va"] == "0xf9e434" and row.get("native_f9e840_return_w0") == 0
                for row in calls),
            "f9e410_no_change_epilogue_observed": any(
                row["va"] == "0xf9e4f4" for row in calls),
            "f9e840_reject_branch_observed": any(
                row.get("pc") == "0xf9ebf8" and row.get("w0") == 0
                for row in f9e840_checks),
            "aac730_return_w0": next((row.get("return_w0") for row in f9e840_checks
                                      if row.get("callee") == "0xaac730"), None),
            "count_slot0_after": count_after,
            "changed_inventory_offsets": changed,
            "slot0_after": list(struct.unpack("<HHI", after[:8])),
            "pocket_view_unchanged": before_pocket == after_pocket,
            "consumption_verified": count_after == count_before - 1 and changed == ["0x100"],
        },
        "limits": [
            "The player member and its 0x140-byte view are synthetic; the member pointer/offset are installed at the native f8f400 call boundary.",
            "The member reference service pointer at +0x28 is null, so ee94f0 takes its native no-provider path; no virtual view provider is emulated.",
            "ItemParam and ItemKind tables are reconstructed from the supplied dump by inventory_requirements_native.install_item_tables; this does not recreate the game's whole runtime table manager graph.",
            "0xaac730 is original and unpatched. If the native gate rejects the fixture, no count mutation is claimed.",
        ],
    }


def main():
    report = run_probe()
    output = OUT / "eff060_apple_probe.json"
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(output)


if __name__ == "__main__":
    main()
