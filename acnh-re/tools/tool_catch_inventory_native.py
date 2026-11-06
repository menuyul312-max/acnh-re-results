#!/usr/bin/env python3
"""Exercise the native net/rod result-to-inventory insertion path."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
import struct
import sys
from unicorn import UC_HOOK_CODE

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from nso_sandbox import NSO_SHA256, Sandbox  # noqa: E402

DEFAULT_RESEARCH_OUTPUT = Path("/workspace/acnh-re/output")
NET_GET_DEMO = 0xE45B80
ROD_GET_DEMO = 0xE4E730
RESULT_TO_INVENTORY = 0xEFEC70
INVENTORY_WRITER = 0xEFEE80
INVENTORY_COMPACTOR = 0xEFFEA0
NATIVE_FUNCTIONS_TO_TRACE = (
    RESULT_TO_INVENTORY,
    INVENTORY_WRITER,
    INVENTORY_COMPACTOR,
    0xF57ED0,
    0xF58D00,
    0xA1E8C0,
    0xF59550,
    0xF589B0,
    0xF589E0,
)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def source_sample_items(research_output: Path) -> tuple[dict, dict, dict]:
    """Return one Fish and Insect item and build the original dense ItemParam index."""
    table_path = research_output / "tables_resolved/ItemParam.json"
    table = json.loads(table_path.read_text())
    manifest = json.loads((research_output / "manifest.json").read_text())
    entry = next(item for item in manifest["entries"]
                 if item["id"] == table["source_id"])
    decoded = json.loads((research_output / entry["decoded"]).read_text())["data"]
    raw_path = research_output / table["raw"]["$blob"]
    raw = raw_path.read_bytes()
    if sha256(raw) != table["raw"]["sha256"]:
        raise ValueError("ItemParam raw BCSV checksum mismatch")
    if len(table["rows"]) != decoded["row_count"]:
        raise ValueError("resolved ItemParam row count does not match decoded source")

    column_index = {column["name"]: index for index, column in enumerate(table["columns"])}
    ids = [row[column_index["UniqueID"]] for row in table["rows"]]
    minimum, maximum = min(ids), max(ids)
    samples = {}
    for row in table["rows"]:
        kind = row[column_index["ItemKind"]]
        labels = kind.get("labels") if isinstance(kind, dict) else None
        if labels and labels[0] in ("Fish", "Insect") and labels[0] not in samples:
            samples[labels[0]] = {
                "unique_id": row[column_index["UniqueID"]],
                "label": row[column_index["Label"]],
                "item_kind": labels[0],
            }
    if set(samples) != {"Fish", "Insect"}:
        raise ValueError(f"could not find representative fish/insect rows: {samples}")

    return table, {"raw": raw, "decoded": decoded, "ids": ids,
                   "minimum": minimum, "maximum": maximum}, samples


def build_itemparam_lookup(sandbox: Sandbox, research_output: Path,
                           table: dict, table_parts: dict) -> dict:
    """Recreate the dense UniqueID->row wrapper used by native F58D00."""
    raw = table_parts["raw"]
    ids = table_parts["ids"]
    decoded = table_parts["decoded"]
    minimum, maximum = table_parts["minimum"], table_parts["maximum"]
    table_va = sandbox.alloc(len(raw))
    sandbox.uc.mem_write(table_va, raw)
    dense_count = maximum - minimum + 1
    dense_va = sandbox.alloc(dense_count * 8)
    sandbox.uc.mem_write(dense_va, bytes(dense_count * 8))
    meta_va = sandbox.alloc(0x200)
    definition_va = sandbox.alloc(0x57E60)
    row_size = table["row_size"]
    for row_index, item_id in enumerate(ids):
        row_va = table_va + decoded["data_start"] + row_index * row_size
        sandbox.uc.mem_write(dense_va + (item_id - minimum) * 8,
                             struct.pack("<Q", row_va))
    sandbox.uc.mem_write(meta_va + 0x1D8, struct.pack("<I", dense_count))
    sandbox.uc.mem_write(meta_va + 0x1E0, struct.pack("<Q", dense_va))
    sandbox.uc.mem_write(meta_va + 0x1F8, struct.pack("<H", minimum))
    sandbox.uc.mem_write(definition_va + 0x57E58, struct.pack("<Q", meta_va))
    global_definition_ptr = sandbox.u64(0x32D3B88)
    sandbox.uc.mem_write(global_definition_ptr, struct.pack("<Q", definition_va))
    return {
        "source_id": table["source_id"],
        "raw_sha256": table["raw"]["sha256"],
        "row_count": len(ids),
        "unique_id_range": [minimum, maximum],
        "resolver_wrapper_reconstructed": True,
    }


def net_rod_callers(research_output: Path) -> list[dict]:
    db_path = research_output / "index.sqlite"
    with sqlite3.connect(db_path) as db:
        rows = db.execute(
            "SELECT owner_va, pc FROM direct_calls WHERE target_va=? ORDER BY owner_va,pc",
            (RESULT_TO_INVENTORY,),
        ).fetchall()
    callers = [{"owner_va": hex(owner), "call_pc": hex(pc)} for owner, pc in rows
               if owner in (NET_GET_DEMO, ROD_GET_DEMO)]
    expected = {
        (NET_GET_DEMO, 0xE45DFC),
        (ROD_GET_DEMO, 0xE4EBD0),
    }
    if {(int(item["owner_va"], 16), int(item["call_pc"], 16))
            for item in callers} != expected:
        raise AssertionError(f"net/rod direct call evidence changed: {callers}")
    return callers


def catch_result_preparation_calls(research_output: Path) -> list[dict]:
    """Record the catch-state helper reached before result inventory insertion."""
    with sqlite3.connect(research_output / "index.sqlite") as db:
        rows = db.execute(
            "SELECT owner_va, pc, target_va FROM direct_calls "
            "WHERE target_va=? AND owner_va IN (?, ?) ORDER BY owner_va, pc",
            (0xDB00F0, NET_GET_DEMO, ROD_GET_DEMO),
        ).fetchall()
    expected = {
        (NET_GET_DEMO, 0xE45CBC, 0xDB00F0),
        (ROD_GET_DEMO, 0xE4EA70, 0xDB00F0),
    }
    if set(rows) != expected:
        raise AssertionError(f"net/rod result preparation calls changed: {rows}")
    return [{"owner_va": hex(owner), "call_pc": hex(pc), "target_va": hex(target)}
            for owner, pc, target in rows]


def run(research_output: Path, nso_path: Path, output: Path) -> dict:
    if sha256(nso_path.read_bytes()) != NSO_SHA256:
        raise ValueError("main NSO does not match the indexed 1.0.0 image")

    table, table_parts, samples = source_sample_items(research_output)
    callers = net_rod_callers(research_output)
    preparation_calls = catch_result_preparation_calls(research_output)
    sandbox = Sandbox(nso_path)
    itemparam = build_itemparam_lookup(sandbox, research_output, table, table_parts)
    native_function_entries = {va: 0 for va in NATIVE_FUNCTIONS_TO_TRACE}

    def record_native_function_entry(_uc, address, _size, _user_data):
        native_function_entries[address] += 1

    for va in NATIVE_FUNCTIONS_TO_TRACE:
        sandbox.uc.hook_add(UC_HOOK_CODE, record_native_function_entry,
                            begin=va, end=va)

    # The unresolved object/state bridges are controlled so the native helper and
    # inventory writer can run against an isolated player inventory.
    request = sandbox.alloc(0x100)
    player = sandbox.alloc(0x1000)
    inventory = player + 0x4D8
    catalog_calls = []
    sandbox.stub(0xE76D50, lambda _sb: player)
    sandbox.stub(0xDA3FC0, lambda _sb: 0)
    sandbox.stub(0xF9D4A0, lambda _sb: 1)  # selects the +0x4d8 inventory view
    sandbox.stub(0xA9C290, lambda _sb: 0)  # optional item-definition wrapper metadata
    sandbox.stub(0xAB2A50, lambda _sb: 0)  # optional remake/normalization query
    sandbox.stub(0x4C6110, lambda _sb: 0)  # optional foreign-item conversion context
    def preserve_unmodified_item(sb):
        # AB60C0 returns a packed item word through the hidden x8 result pointer.
        # For these base fish/insect records, preserve the source word while the
        # item-category normalization manager remains unavailable.
        sb.uc.mem_write(sb.reg("x8"), sb.read(sb.reg("x0"), 8))
        return 0

    sandbox.stub(0xAB60C0, preserve_unmodified_item)

    # Game startup constructs the shared empty-item singleton before any catches
    # can happen. Sandbox does not run global constructors, so provide the same
    # 0xfffe item word at the global pointer consumed by the full-pocket path.
    empty_item = sandbox.alloc(8)
    empty_item_word = struct.pack("<HBBI", 0xFFFE, 0, 0, 0)
    sandbox.uc.mem_write(empty_item, empty_item_word)
    sandbox.uc.mem_write(0x32D25E0, struct.pack("<Q", empty_item))

    def capture_catalog(sb):
        catalog_calls.append({
            "request": sb.reg("x0"),
            "item_pointer": sb.reg("x1"),
            "flags": sb.reg("x2"),
        })
        return 1

    sandbox.stub(0xEEBE80, capture_catalog)

    cases = []
    for item in (samples["Insect"], samples["Fish"]):
        source = struct.pack("<HBBI", item["unique_id"], 0, 0, 0)
        item_pointer = sandbox.alloc(8)
        sandbox.uc.mem_write(item_pointer, source)
        for slot in range(20):
            for index in range(20):
                sandbox.uc.mem_write(
                    inventory + index * 8,
                    struct.pack("<HBBI", 2100 + index, 0, 0, 0),
                )
            sandbox.uc.mem_write(inventory + slot * 8,
                                 struct.pack("<HBBI", 0xFFFE, 0, 0, 0))
            sandbox.uc.mem_write(inventory + 0xA0, struct.pack("<I", 20))
            source_before = sandbox.read(item_pointer, 8)
            catalog_start = len(catalog_calls)
            try:
                accepted = sandbox.call(RESULT_TO_INVENTORY,
                                        (request, item_pointer, 0)) & 1
            except Exception as exc:
                raise RuntimeError(
                    f"native result insertion failed at pc={sandbox.reg('pc'):#x}, "
                    f"lr={sandbox.reg('x30'):#x}, args="
                    f"{[hex(sandbox.reg(f'x{i}')) for i in range(6)]}"
                ) from exc
            inserted = sandbox.read(inventory + slot * 8, 8)
            catalog = catalog_calls[catalog_start:]
            if accepted != 1 or inserted != source_before:
                raise AssertionError({"item": item, "slot": slot,
                                      "accepted": accepted,
                                      "inserted": inserted.hex(),
                                      "source": source_before.hex()})
            expected_catalog = [{"request": request, "item_pointer": item_pointer,
                                 "flags": 0}] * 2
            if catalog != expected_catalog:
                raise AssertionError({"item": item, "slot": slot,
                                      "catalog_calls": catalog})
            other_slots_unchanged = all(
                index == slot or sandbox.read(inventory + index * 8, 8) ==
                struct.pack("<HBBI", 2100 + index, 0, 0, 0)
                for index in range(20)
            )
            if not other_slots_unchanged:
                raise AssertionError(f"native insertion modified another slot: {slot}")
            cases.append({
                "result_kind": item["item_kind"],
                "result_item_unique_id": item["unique_id"],
                "result_item_label": item["label"],
                "first_empty_slot": slot,
                "helper_return": accepted,
                "source_word_hex": source_before.hex(),
                "stored_word_hex": inserted.hex(),
                "neighboring_slots_unchanged": True,
            })

    full_inventory_cases = []
    for item in (samples["Insect"], samples["Fish"]):
        source = struct.pack("<HBBI", item["unique_id"], 0, 0, 0)
        item_pointer = sandbox.alloc(8)
        sandbox.uc.mem_write(item_pointer, source)
        original_slots = [
            struct.pack("<HBBI", 2100 + index, 0, 0, 0)
            for index in range(20)
        ]
        for index, word in enumerate(original_slots):
            sandbox.uc.mem_write(inventory + index * 8, word)
        sandbox.uc.mem_write(inventory + 0xA0, struct.pack("<I", 20))

        catalog_start = len(catalog_calls)
        accepted = sandbox.call(RESULT_TO_INVENTORY,
                                (request, item_pointer, 0)) & 1
        stored_slots = [sandbox.read(inventory + index * 8, 8)
                        for index in range(20)]
        expected_slots = original_slots[1:] + [source]
        if accepted != 1 or stored_slots != expected_slots:
            raise AssertionError({
                "item": item,
                "accepted": accepted,
                "stored_slots": [word.hex() for word in stored_slots],
                "expected_slots": [word.hex() for word in expected_slots],
            })
        full_inventory_cases.append({
            "result_kind": item["item_kind"],
            "result_item_unique_id": item["unique_id"],
            "result_item_label": item["label"],
            "capacity": 20,
            "helper_return": accepted,
            "evicted_initial_slot": 0,
            "first_stored_original_item_after_compaction": 2101,
            "result_stored_at_slot": 19,
            "result_word_hex": source.hex(),
            "catalog_registration_request_count": len(catalog_calls) - catalog_start,
            "all_original_items_except_slot_zero_preserved": True,
        })

    if sandbox.unknown_imports:
        raise AssertionError(f"unexpected native imports: {sandbox.unknown_imports}")
    missing_native_functions = [hex(va) for va, count in native_function_entries.items()
                                if count == 0]
    if missing_native_functions:
        raise AssertionError(f"expected native insertion path was not executed: {missing_native_functions}")

    result = {
        "schema": "acnh-re/tool-catch-inventory-native/1",
        "native_elf_sha256": sha256(nso_path.read_bytes()),
        "itemparam_source": itemparam,
        "sample_result_items": list(samples.values()),
        "static_catch_result_preparation_calls": preparation_calls,
        "static_result_helper_callers": callers,
        "native_functions_executed": [
            "0xefec70 result-to-inventory helper",
            "0xefee80 inventory insertion wrapper",
            "0xeffea0 full-pocket compaction helper",
            "0xf57ed0 bounded slot writer",
            "0xf58d00 item-word validation",
            "0xa1e8c0 native ItemParam row resolver",
            "0xf59550 item-word normalization wrapper, with optional category conversion dependencies controlled",
            "0xf589b0/0xf589e0 packed-word copy operations",
        ],
        "native_functions_stubbed": [
            "0xe76d50 returns a synthetic player/inventory owner",
            "0xda3fc0 selector-context construction",
            "0xf9d4a0 returns 1 to select inventory view at owner+0x4d8",
            "0xa9c290 optional item-definition wrapper and 0xab2a50 optional remake query",
            "0x4c6110 optional foreign-item conversion context returns absent",
            "0xab60c0 item-category normalization returns the unmodified base item word",
            "0xeebe80 catalog registration is captured, not executed",
            "0x32d25e0 points to a synthetic 0xfffe empty-item word because global constructors are not run",
        ],
        "native_function_entry_counts": {
            hex(va): count for va, count in sorted(native_function_entries.items())
        },
        "inventory_shape": {
            "record_stride_bytes": 8,
            "capacity_field_offset": "0xa0",
            "capacity": 20,
            "empty_item_unique_id": 65534,
            "first_empty_slot_rule": "native helper scans from slot 0 and inserts at the first -2/0xfffe item id",
            "full_inventory_rule": "native helper clears slot 0 to the empty-item singleton, compacts slots 1..19 left, then inserts the result at slot 19",
        },
        "cases": cases,
        "full_inventory_cases": full_inventory_cases,
        "case_count": len(cases) + len(full_inventory_cases),
        "first_empty_case_count": len(cases),
        "full_inventory_case_count": len(full_inventory_cases),
        "catalog_registration_requests_per_first_empty_case": 2,
        "mismatches": 0,
        "unresolved_imports": sandbox.unknown_imports,
        "proven": [
            "The original result-to-inventory function accepts valid source ItemParam words for one insect and one fish sample.",
            "For base fish/insect words with optional normalization held at identity, the original native insertion path writes the 8-byte item word into each first-empty slot across all 20 tested positions; other slots remain unchanged.",
            "With a full 20-slot synthetic pocket and the native empty-item singleton initialized to 0xfffe, the original path clears slot 0, compacts slots 1..19 left, inserts the result at slot 19, and returns success; the other 19 original items retain their packed words.",
            "The original writer path includes EFEE80 and F57ED0 and reaches the packed-word copy operations; this is a real in-memory inventory mutation in the bounded emulator, not a stubbed slot write.",
            "The indexed native call sites show both NetGetDemo (0xe45b80) and RodGetDemo (0xe4e730) directly call the shared result-to-inventory helper at 0xefec70.",
        ],
        "limits": [
            "NetGetDemo and RodGetDemo caller bodies were not run end-to-end; result item production/catch eligibility is not established by this probe.",
            "Player-owner lookup, inventory-view selection, and catalog registration are controlled or stubbed; catalog/save persistence is not executed.",
            "The Sandbox does not run the game's global constructors; the full-pocket probe supplies a synthetic 0xfffe empty-item singleton at global pointer 0x32d25e0.",
            "This proves caught insect/fish result insertion for the shared helper, not tool durability decrement or break threshold.",
        ],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({key: value for key, value in result.items()
                      if key != "cases"}, indent=2, ensure_ascii=False))
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--research-output", type=Path, default=DEFAULT_RESEARCH_OUTPUT)
    parser.add_argument("--nso", type=Path, default=ROOT / "inputs/additional_exefs/main")
    parser.add_argument("--output", type=Path,
                        default=ROOT / "output/gameplay/tool_mechanics_followup/tool_catch_inventory_native.json")
    args = parser.parse_args()
    run(args.research_output, args.nso, args.output)


if __name__ == "__main__":
    main()
