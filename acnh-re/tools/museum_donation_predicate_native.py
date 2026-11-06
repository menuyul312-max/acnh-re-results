#!/usr/bin/env python3
"""Drive DonationCheckItemType and its SaveMuseum duplicate scanner natively.

The predicate, 1024-slot scan, and ordinary item-key equality path execute as
original AArch64. Service accessors, selected-item serialization, ItemParam
lookup, and lower inventory/view equality adapters are controlled.
"""
import hashlib
import json
from pathlib import Path
import struct
import sys
from unicorn import UC_HOOK_CODE

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from nso_sandbox import Sandbox  # noqa: E402

NSO = ROOT / "inputs/additional_exefs/main"
OUT = ROOT / "output/gameplay/museum_donation_followup/predicate_native.json"
PREDICATE = 0x3D9B60
NOT_ALREADY_DONATED = 0xF77E00
MEMBERSHIP_SCAN = 0xF77F60
SCAN_MATCHER = 0xF58AF0
ITEM_ROW_INDEX = 0x1665EA0
ITEM_KIND_TABLE_GLOBAL = 0x32F0A60
SLOT_COUNT = 0x400
SLOT_BYTES = SLOT_COUNT
KIND_GLOBALS = (0x35EC944, 0x35EC948, 0x35EC94C)


def verify():
    sb = Sandbox(NSO)
    alloc = sb.alloc
    for address, value in zip(KIND_GLOBALS, (70, 65, 64)):
        sb.uc.mem_write(address, struct.pack("<I", value))

    kind_table = alloc(0x10, align=8)
    kind_values = alloc(2, align=2)
    sb.uc.mem_write(kind_table, struct.pack("<I", 1))
    sb.uc.mem_write(kind_table + 8, struct.pack("<Q", kind_values))
    sb.uc.mem_write(ITEM_KIND_TABLE_GLOBAL, struct.pack("<Q", kind_table))

    def q(address, value):
        sb.uc.mem_write(address, struct.pack("<Q", value))

    def h(address, value):
        sb.uc.mem_write(address, struct.pack("<h", value))

    def uh(address, value):
        sb.uc.mem_write(address, struct.pack("<H", value & 0xFFFF))

    def make_string(value):
        raw = value.encode("ascii") + b"\0"
        ptr = alloc(len(raw))
        sb.uc.mem_write(ptr, raw)
        return ptr

    handler = alloc(0x400)
    selected = alloc(0x400)
    manager = alloc(0x40)
    # Native F77F60 reads 0x1000 bytes of lookup records and 0x400 marker bytes.
    catalog_data = alloc(0x3404)
    handler_vtable = alloc(0x40)
    source_vtable = alloc(0x40)
    source_context = alloc(0x20a200)
    allow_list = make_string("cUISelect , cDeliveryItem")
    global_slot = alloc(0x20)
    q(global_slot, allow_list)

    q(handler, handler_vtable)
    q(handler_vtable + 0x20, 0x3D9B58)
    q(handler + 8, selected)  # non-null evaluation context
    q(handler + 0xD0, source_vtable)
    q(source_vtable + 0x18, 0x3D9B50)
    q(handler + 0x310, selected)
    # F589B0's controlled serializer copies this 8-byte selected-item record.
    selected_record = struct.pack("<HBBI", 105, 0, 0, 0x10203040)
    sb.uc.mem_write(selected, selected_record)
    h(selected + 0x228, 105)  # valid synthetic selected item; -2 means empty
    q(manager + 8, 0)
    q(manager + 16, catalog_data)

    state = {"type_ptr": 0, "match_slot": None, "kind": 0,
             "kind_value_ptr": kind_values}
    match_calls = []

    # Native path/return adapters. The predicate and membership scan are not stubbed.
    sb.stub(0x3DA0B0, lambda s: global_slot)
    sb.stub(0x455D20, lambda s: s.reg("x0"))
    sb.stub(0x3D9B50, lambda s: state["type_ptr"])
    sb.stub(0x3D9B58, lambda s: 1)
    sb.stub(0xF58D00, lambda s: 1)  # selected item is present in controlled ItemParam lookup
    sb.stub(0xEECF00, lambda s: source_context)

    def open_catalog_view(s):
        # EE9350 writes the context returned by its accessor into the local wrapper.
        s.uc.mem_write(s.reg("x0") + 8, struct.pack("<Q", manager))
        return 0

    sb.stub(0xEE9350, open_catalog_view)
    sb.stub(0xEE93D0, lambda s: 0)
    # The scan and ordinary identity comparison execute natively. Only item
    # record serialization and lower database/inventory adapters are controlled.
    def serialize_selected(s):
        s.uc.mem_write(s.reg("x0"), s.read(s.reg("x1"), 8))
        return 0

    sb.stub(0xF589B0, serialize_selected)
    def initialize_item_view(s):
        s.uc.mem_write(s.reg("x0") + 0x10, struct.pack("<Q", s.reg("x1")))
        return 0

    sb.stub(0xA9C290, initialize_item_view)
    # These adapters stand in for live inventory ownership and ItemParam view
    # comparison after F58AF0's native identity/flag checks have matched.
    sb.stub(0xA1E8C0, lambda s: 1)
    sb.stub(0xA9C3A0, lambda s: 1)
    sb.stub(ITEM_ROW_INDEX, lambda s: 0)

    def count_native_key_match(uc, address, size, _):
        slot = (sb.reg("x0") - (catalog_data + 0x1004)) // 8
        match_calls.append(slot)

    # Instrument the call site without replacing the native matcher body.
    sb.uc.hook_add(UC_HOOK_CODE, count_native_key_match,
                   begin=SCAN_MATCHER, end=SCAN_MATCHER)

    def setup_catalog(match_slot, marker):
        match_calls.clear()
        sb.uc.mem_write(catalog_data + 0x1004, bytes(0x2000))
        sb.uc.mem_write(catalog_data + 0x3004, bytes(SLOT_BYTES))
        if match_slot is not None:
            sb.uc.mem_write(catalog_data + 0x1004 + match_slot * 8, selected_record)
            sb.uc.mem_write(catalog_data + 0x3004 + match_slot, bytes([marker]))

    # F77E00 is the native supported-kind + not-already-donated gate called
    # immediately before SaveMuseum insertion in FUN_003c2410.
    kind_gate_cases = []
    for kind in (70, 65, 64):
        for match_slot, marker in ((None, 0), (2, 0), (2, 0xFF)):
            setup_catalog(match_slot, marker)
            state["kind"] = kind
            uh(kind_values, kind)
            actual = sb.call(NOT_ALREADY_DONATED, (catalog_data, selected))
            expected = int(match_slot is None or marker == 0xFF)
            if actual != expected:
                raise AssertionError({"kind": kind, "match_slot": match_slot,
                                      "marker": marker, "actual": actual,
                                      "expected": expected,
                                      "scan_calls": len(match_calls)})
            expected_scans = SLOT_COUNT if match_slot is None else match_slot + 1
            if len(match_calls) != expected_scans:
                raise AssertionError({"kind": kind, "match_slot": match_slot,
                                      "scan_calls": len(match_calls),
                                      "expected": expected_scans})
            kind_gate_cases.append({"kind": kind, "match_slot": match_slot,
                                    "marker_byte": marker, "return": actual,
                                    "expected_return": expected,
                                    "native_scan_calls": len(match_calls)})
    setup_catalog(None, 0)
    state["kind"] = 66
    uh(kind_values, 66)
    rejected_kind = sb.call(NOT_ALREADY_DONATED, (catalog_data, selected))
    if rejected_kind != 0 or match_calls:
        raise AssertionError({"other_kind_return": rejected_kind,
                              "unexpected_scans": len(match_calls)})
    kind_gate_cases.append({"kind": 66, "match_slot": None,
                            "marker_byte": 0, "return": rejected_kind,
                            "expected_return": 0, "native_scan_calls": 0})

    cases = [
        ("cUISelect", None, 0),
        ("cUISelect", 3, 0),
        ("cUISelect", 3, 0xFF),
        ("cDeliveryItem", None, 0),
        ("cDeliveryItem", 3, 0),
    ]
    results = []
    for type_name, match_slot, marker in cases:
        type_ptr = make_string(type_name)
        q(global_slot + 8, type_ptr)
        q(handler + 0xD8, type_ptr)
        state.update(type_ptr=type_ptr, match_slot=match_slot)
        uh(kind_values, 64)
        match_calls.clear()
        setup_catalog(match_slot, marker)

        returned = sb.call(PREDICATE, (handler,))
        expected = 0 if match_slot is not None and marker != 0xFF else 1
        if returned != expected:
            raise AssertionError({"type": type_name, "match_slot": match_slot,
                                  "marker": marker, "returned": returned,
                                  "expected": expected})
        expected_scans = SLOT_COUNT if match_slot is None else match_slot + 1
        if len(match_calls) != expected_scans:
            raise AssertionError({"type": type_name, "match_slot": match_slot,
                                  "scan_calls": len(match_calls), "expected": expected_scans})
        results.append({
            "selector_type_state": type_name,
            "controlled_key_match_slot": match_slot,
            "marker_byte": marker,
            "native_scan_calls": len(match_calls),
            "predicate_return": returned,
            "expected_return": expected,
        })

    if sb.unknown_imports:
        raise AssertionError({"unexpected_imports": sb.unknown_imports})
    return {
        "source_nso_sha256": hashlib.sha256(NSO.read_bytes()).hexdigest(),
        "addresses": {"predicate": hex(PREDICATE), "duplicate_scan": hex(MEMBERSHIP_SCAN),
                      "ordinary_identity_matcher": hex(SCAN_MATCHER)},
        "native_execution": "0x3d9b60, 0xf77e00, 0xf77f60, 0xa9f670 ItemKind table lookup, and ordinary F58AF0 item identity/flag comparisons ran original instructions. The selected item context, one-row ItemParam table, and catalog byte array are synthetic.",
        "selector_literal": "cUISelect , cDeliveryItem (string initialized by native 0x3da0b0; its parser/context result is controlled here)",
        "duplicate_scan_contract": "F77F60 scans up to 1024 8-byte records using native F58AF0. For the synthetic ordinary item record (flags byte 0), equal 16-bit IDs pass the native identity checks; lower inventory ownership and ItemParam view-equivalence adapters return true. A matching slot marker 0xff makes F77F60 return 0; other marker values make it return 1. DonationCheckItemType inverts this result for its selected-item branch.",
        "cases": len(results),
        "mismatches": 0,
        "writer_precondition_native": {
            "address": hex(NOT_ALREADY_DONATED),
            "contract": "F77E00 accepts only ItemKind codes 70/65/64, then returns logical-not of F77F60 duplicate-list match. F77F60's matching marker 0xff suppresses the duplicate result; other marker bytes count as already present.",
            "kind_labels_from_local_ItemParam_crosswalk": {"70": "Fossil", "65": "Fish", "64": "Insect"},
            "kind_gate_cases": len(kind_gate_cases),
            "kind_gate_mismatches": 0,
            "results": kind_gate_cases,
            "execution": "F77E00, F77F60, A9F670 table lookup, and ordinary F58AF0 identity checks execute from the original NSO; the ItemParam row index is controlled.",
        },
        "dependencies_stubbed": [
            "0x3da0b0 selector-state accessor",
            "0x3d9b50/0x3d9b58 controlled virtual context/item-selection getters",
            "0x455d20 object/context accessor",
            "0xf58d00 valid selected-item lookup",
            "0xeecf00/0xee9350/0xee93d0 catalog view accessors",
            "0xf589b0 selected-item serializer",
            "0xa9c290 synthetic ItemParam view; 0x1665ea0 controlled row index (native 0xa9f670 lookup runs)",
            "0xa1e8c0 inventory ownership query and 0xa9c3a0 ItemParam-view equivalence",
        ],
        "results": results,
        "open": [
            "Per-kind ItemParam acceptance for special item encodings, beyond the tested ordinary 16-bit identity path",
            "Meaning and producer of the 0xff marker in the museum donation list",
            "Art or gyroid donation coverage; the traced writer and F77E00 gate accept only native ItemKind values 64/65/70",
        ],
    }


def main():
    result = verify()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({key: value for key, value in result.items() if key != "results"}, indent=2))


if __name__ == "__main__":
    main()
