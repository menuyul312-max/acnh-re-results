#!/usr/bin/env python3
"""Exercise the native SaveMuseum donation-list insertion routine.

The NSO bodies at 0xf780e0, 0xf78130, 0xf41eb0, and 0xa9f670 are executed
unchanged. Controlled adapters supply save/item views, the calendar scalar,
validity, and ItemParam row index for a synthetic 0x3404-byte SaveMuseum block.
"""
import hashlib
import json
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from nso_sandbox import Sandbox  # noqa: E402

NSO = ROOT / "inputs/additional_exefs/main"
OUT = ROOT / "output/gameplay/museum_donation_followup/writer_native.json"
WRITER = 0xF78130
WRAPPER = 0xF780E0
SAVE_VIEW = 0xDA3FC0
MARKER_QUERY = 0xEF62F0
ITEM_VALID = 0xF58D00
ITEM_VIEW_INIT = 0xA9C290
ITEM_ROW_INDEX = 0x1665EA0
ITEM_KIND_TABLE_GLOBAL = 0x32F0A60
TIME_SOURCE = 0x1FCAC0
SLOT_COUNT = 0x400
SAVE_SIZE = 0x3404
ITEMS_OFFSET = 0x1004
MARKERS_OFFSET = 0x3004
CALENDAR_DATE = struct.pack("<HBB", 2026, 4, 15)
CALENDAR_DATE_WORD = struct.unpack("<I", CALENDAR_DATE)[0]
KIND_GLOBALS = (0x35EC944, 0x35EC948, 0x35EC94C)


def q(sb, address, value):
    sb.uc.mem_write(address, struct.pack("<Q", value))


def w(sb, address, value):
    sb.uc.mem_write(address, struct.pack("<I", value & 0xFFFFFFFF))


def read_save(sb, ptr):
    return sb.read(ptr, SAVE_SIZE)


def make_save(sb, empty_slots=(), marker_fill=0x7E):
    """Return a populated synthetic block; -2 is the native empty-slot ID."""
    ptr = sb.alloc(SAVE_SIZE, align=8)
    block = bytearray([0xA5]) * SAVE_SIZE
    struct.pack_into("<I", block, 0, 0xCAFEBABE)  # MuseumLevel sentinel
    for index in range(SLOT_COUNT):
        struct.pack_into("<h", block, ITEMS_OFFSET + 8 * index, 1)
        block[MARKERS_OFFSET + index] = marker_fill
    for index in empty_slots:
        struct.pack_into("<h", block, ITEMS_OFFSET + 8 * index, -2)
    sb.uc.mem_write(ptr, bytes(block))
    return ptr


def verify_case(sb, case, state):
    save_ptr = make_save(sb, case.get("empty_slots", ()))
    item_ptr = sb.alloc(8, align=8)
    item = bytes.fromhex(case["item_hex"])
    sb.uc.mem_write(item_ptr, item)
    before = read_save(sb, save_ptr)

    state.update(kind=case["kind"], valid=case.get("valid", 1),
                 marker=case["marker_argument"])
    sb.uc.mem_write(state["kind_value_ptr"], struct.pack("<H", case["kind"]))
    # The wrapper resolves a save view and marker before calling F78130.
    sb.call(WRAPPER, (save_ptr, item_ptr, case["marker_argument"]))
    after = read_save(sb, save_ptr)

    inserted_at = case.get("inserted_at")
    if inserted_at is None:
        if after != before:
            raise AssertionError({"case": case["name"], "expected": "unchanged", "changed": True})
        expected_date_word = None
        expected_marker = None
        record_matches = False
    else:
        record_offset = ITEMS_OFFSET + inserted_at * 8
        stamp_offset = 4 + inserted_at * 4
        marker_offset = MARKERS_OFFSET + inserted_at
        expected = bytearray(before)
        expected[record_offset:record_offset + 8] = item
        struct.pack_into("<I", expected, stamp_offset, CALENDAR_DATE_WORD)
        expected[marker_offset] = case["marker_argument"] & 0xFF
        if after != bytes(expected):
            changed = [i for i, (a, b) in enumerate(zip(expected, after)) if a != b]
            raise AssertionError({"case": case["name"], "first_changed_offsets": changed[:12],
                                  "expected_record_offset": record_offset,
                                  "expected_stamp_offset": stamp_offset,
                                  "expected_marker_offset": marker_offset,
                                  "actual_date_word": hex(struct.unpack_from("<I", after, stamp_offset)[0]),
                                  "expected_date_word": hex(CALENDAR_DATE_WORD)})
        expected_date_word = struct.unpack_from("<I", after, stamp_offset)[0]
        expected_marker = after[marker_offset]
        record_matches = after[record_offset:record_offset + 8] == item

    return {
        "name": case["name"],
        "controlled_item_kind": case["kind"],
        "controlled_validity": case.get("valid", 1),
        "empty_slots": list(case.get("empty_slots", ())),
        "marker_argument": hex(case["marker_argument"]),
        "inserted_at": inserted_at,
        "copied_record_matches": record_matches,
        "calendar_date_word": None if expected_date_word is None else hex(expected_date_word),
        "marker_byte": None if expected_marker is None else hex(expected_marker),
        "full_block_matches_expected": True,
    }


def verify():
    sb = Sandbox(NSO)
    state = {"kind": 0, "valid": 1, "marker": 0}
    # These are the three native comparison operands. Their semantic labels
    # come from the local ItemParam item-kind enum crosswalk, not from the NSO.
    for address, value in zip(KIND_GLOBALS, (70, 65, 64)):
        w(sb, address, value)

    # A9F670 runs natively over a one-row synthetic ItemParam table; only its
    # table-row index adapter is controlled.
    kind_table = sb.alloc(0x10, align=8)
    kind_values = sb.alloc(2, align=2)
    w(sb, kind_table, 1)
    q(sb, kind_table + 8, kind_values)
    q(sb, ITEM_KIND_TABLE_GLOBAL, kind_table)
    state["kind_value_ptr"] = kind_values

    # 0x1fcac0 returns a packed calendar scalar; F41EB0 consumes its address
    # as {year:u16, month:u8, day:u8} and validates that date.
    sb.stub(TIME_SOURCE, lambda s: CALENDAR_DATE_WORD)
    sb.stub(SAVE_VIEW, lambda s: 0)
    sb.stub(MARKER_QUERY, lambda s: state["marker"])
    sb.stub(ITEM_VALID, lambda s: state["valid"])
    # The item adapter still supplies a synthetic ItemParam row pointer.
    def initialize_item_view(s):
        s.uc.mem_write(s.reg("x0") + 0x10, struct.pack("<Q", s.reg("x1")))
        return 0

    sb.stub(ITEM_VIEW_INIT, initialize_item_view)
    sb.stub(ITEM_ROW_INDEX, lambda s: 0)

    cases = [
        {"name": "fossil kind; first empty slot wins", "kind": 70, "empty_slots": (3, 9),
         "inserted_at": 3, "marker_argument": 0x00, "item_hex": "3412aabb78563412"},
        {"name": "fish kind; marker byte is copied", "kind": 65, "empty_slots": (5,),
         "inserted_at": 5, "marker_argument": 0x22, "item_hex": "78563412efcdab90"},
        {"name": "insect kind; final slot boundary", "kind": 64, "empty_slots": (1023,),
         "inserted_at": 1023, "marker_argument": 0x7F, "item_hex": "ffff010203040506"},
        {"name": "other kind rejected", "kind": 66, "empty_slots": (0,),
         "inserted_at": None, "marker_argument": 0x01, "item_hex": "0100010203040506"},
        {"name": "invalid item rejected", "kind": 70, "valid": 0, "empty_slots": (0,),
         "inserted_at": None, "marker_argument": 0x01, "item_hex": "0200010203040506"},
        {"name": "bit-31 marker argument exits before mutation", "kind": 70,
         "empty_slots": (0,), "inserted_at": None, "marker_argument": 0x80000000,
         "item_hex": "0300010203040506"},
        {"name": "full list leaves all records unchanged", "kind": 70,
         "empty_slots": (), "inserted_at": None, "marker_argument": 0x01,
         "item_hex": "0400010203040506"},
    ]

    results = [verify_case(sb, case, state) for case in cases]
    if sb.unknown_imports:
        raise AssertionError({"unexpected_imports": sb.unknown_imports})
    return {
        "source_nso_sha256": hashlib.sha256(NSO.read_bytes()).hexdigest(),
        "native_addresses": {"save_item_wrapper": hex(WRAPPER), "list_insertion_writer": hex(WRITER)},
        "native_layout": {
            "save_block_size": hex(SAVE_SIZE), "museum_level": "u32 at +0",
            "slot_count": SLOT_COUNT, "slot_id_probe": "signed s16 at +0x1004 + 8*i; -2 means empty",
            "item_record": "8 bytes at +0x1004 + 8*i",
            "calendar_date_word": "u32 at +4 + 4*i; native 0xf41eb0 packs year u16, month u8, day u8",
            "marker_byte": "u8 at +0x3004 + i",
        },
        "native_category_comparisons": {
            "global_addresses": [hex(x) for x in KIND_GLOBALS],
            "values_seeded": [70, 65, 64],
            "local_ItemParam_enum_crosswalk": {"70": "Fossil", "65": "Fish", "64": "Insect"},
            "native_getter": "0xa9f670 reads a controlled one-row ItemParam-kind table natively; 0x1665ea0 supplies row index 0.",
            "caveat": "Semantic labels use the local resolved ItemParam enum; the NSO globals themselves are numeric values.",
        },
        "static_save_member_caller": {
            "function": "0x2c2410 FUN_003c2410 (no stronger semantic name in the local native index)",
            "museum_member_node_offset": "0x20a168",
            "native_call_order": [
                "0x2c2470 opens base + 0x20a168 as a 0x3404-byte museum view",
                "0x2c2588 calls 0xf77e00 (supported-kind and not-already-donated gate)",
                "0x2c25b8 calls 0xf780e0 only when that gate returns true",
                "0xf78118 inside 0xf780e0 calls 0xf78130",
            ],
            "evidence_scope": "Static cross-reference and decompilation; FUN_003c2410 itself is not emulated by this focused writer runner.",
        },
        "execution": "0xf780e0 → 0xf78130, 0xf41eb0 calendar packing, 0xa9f670 ItemKind lookup, the 1024-slot scan, and the 8-byte item copy execute as original NSO instructions. The save block, save-view adapter, marker query, calendar scalar, item-validity result, ItemParam view constructor, and one-row table/index are synthetic/controlled. The sandbox's nn::time IsValidDate import checks the synthetic Y/M/D.",
        "controlled_adapters": [hex(x) for x in (SAVE_VIEW, MARKER_QUERY, TIME_SOURCE, ITEM_VALID, ITEM_VIEW_INIT, ITEM_ROW_INDEX)],
        "cases": len(results),
        "mismatches": 0,
        "results": results,
        "not_proven": [
            "Semantic label/live EventFlow invocation for FUN_003c2410; its static calls into the gate and writer are proven.",
            "Which calendar source supplies each live donation, and whether game logic assigns additional meaning to the stored date.",
            "Concrete runtime CFAD0 full-u32 keys, selector-to-player mapping, and live marker values remain unavailable. NHSE labels the SaveMuseum +0x3004 byte as the donor/player number; this writer fixture uses controlled marker values. Live item identity/key adapters are also controlled.",
            "Live ItemParam row selection and donation kinds outside the three accepted codes, including art or gyroids.",
        ],
    }


def main():
    result = verify()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({key: value for key, value in result.items() if key != "results"}, indent=2))


if __name__ == "__main__":
    main()
