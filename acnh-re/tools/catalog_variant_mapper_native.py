#!/usr/bin/env python3
"""Run the native RemakeID/packed-payload mapper with controlled table rows."""
import hashlib
import json
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from nso_sandbox import Sandbox  # noqa: E402

NSO = ROOT / "inputs/additional_exefs/main"
OUT = ROOT / "output/gameplay/catalog_variant_mapper_native.json"
MAPPER = 0xAB2940
ITEM_REMAKE_TYPE_SOURCE = 0xAB0F50
ITEM_INDEX = 7
REMAKE_TYPE_INDEX = 9


def run():
    sandbox = Sandbox(NSO)
    item = sandbox.alloc(8)
    param_row = sandbox.alloc(0x20)
    item_kind_row = sandbox.alloc(0x20)
    item_kind_registry = sandbox.alloc(0x20)
    item_kind_descriptor = sandbox.alloc(0x20)
    item_kind_values = sandbox.alloc(0x200)
    remake_type_descriptor = sandbox.alloc(0x20)
    remake_type_values = sandbox.alloc(0x200)
    remake_id_field = sandbox.alloc(2)
    inputs = {"valid": True, "item_kind": 5, "remake_type": 1,
              "allow_furniture": True, "allow_tool": True}

    # These are the relocated ELF VAs used by the NSO instructions for the
    # ItemParam.ItemKind and ItemKind.ItemRemakeType table views.
    sandbox.uc.mem_write(0x32F0A60, struct.pack("<Q", item_kind_descriptor))
    sandbox.uc.mem_write(item_kind_descriptor, struct.pack("<I", 256))
    sandbox.uc.mem_write(item_kind_descriptor + 8,
                         struct.pack("<Q", item_kind_values))
    sandbox.uc.mem_write(0x32F3F50, struct.pack("<Q", item_kind_registry))
    sandbox.uc.mem_write(0x32F31B8, struct.pack("<Q", remake_type_descriptor))
    sandbox.uc.mem_write(remake_type_descriptor, struct.pack("<I", 256))
    sandbox.uc.mem_write(remake_type_descriptor + 8,
                         struct.pack("<Q", remake_type_values))

    def copy_item_and_bind_row(sb):
        destination = sb.reg("x0")
        source = sb.reg("x1")
        sb.uc.mem_write(destination + 8, sb.read(source, 8))
        sb.uc.mem_write(destination + 0x10, struct.pack("<Q", param_row))
        return 0

    def row_index(sb):
        pointer = sb.reg("x0")
        if pointer == param_row:
            return ITEM_INDEX
        if pointer == item_kind_row:
            return REMAKE_TYPE_INDEX
        return 0

    sandbox.stub(0xF58D00, lambda sb: int(inputs["valid"]))
    sandbox.stub(0xA9C290, copy_item_and_bind_row)
    sandbox.stub(0xAAC250, lambda sb: 1)
    sandbox.stub(0xA1E920, lambda sb: remake_id_field)
    sandbox.stub(0xA1E280, lambda sb: item_kind_row)
    sandbox.stub(0x1665EA0, row_index)
    sandbox.stub(0xAA84F0, lambda sb: int(inputs["allow_furniture"]))
    sandbox.stub(0xAA7880,
                 lambda sb: sb.reg("x0") + 0x0C if inputs["allow_tool"] else 0)

    cases = [
        {"name": "furniture-byte-low-three", "remake_id": 83, "item_kind": 5,
         "remake_type": 1, "payload_byte": 0xAE, "allow_furniture": True,
         "allow_tool": True, "expected_low_bits": 6},
        {"name": "furniture-predicate-null", "remake_id": 83, "item_kind": 5,
         "remake_type": 1, "payload_byte": 0xAE, "allow_furniture": False,
         "allow_tool": True, "expected_low_bits": 0},
        {"name": "tool-payload-byte", "remake_id": 17, "item_kind": 17,
         "remake_type": 2, "payload_byte": 0xFF, "allow_furniture": True,
         "allow_tool": True, "expected_low_bits": 7},
        {"name": "tool-predicate-null", "remake_id": 17, "item_kind": 17,
         "remake_type": 2, "payload_byte": 0xFF, "allow_furniture": True,
         "allow_tool": False, "expected_low_bits": 0},
        {"name": "smartphone-kind-0x6c", "remake_id": 230, "item_kind": 0x6C,
         "remake_type": 3, "payload_byte": 0xAB, "allow_furniture": True,
         "allow_tool": True, "expected_low_bits": 3},
        {"name": "smartphone-kind-0x38", "remake_id": 230, "item_kind": 0x38,
         "remake_type": 3, "payload_byte": 0xF6, "allow_furniture": True,
         "allow_tool": True, "expected_low_bits": 6},
        {"name": "smartphone-other-kind", "remake_id": 230, "item_kind": 230,
         "remake_type": 3, "payload_byte": 0xF6, "allow_furniture": True,
         "allow_tool": True, "expected_low_bits": 0},
        {"name": "non-remake-kind", "remake_id": 83, "item_kind": 5,
         "remake_type": 0, "payload_byte": 0xAE, "allow_furniture": True,
         "allow_tool": True, "expected_low_bits": 0},
        {"name": "negative-remake-id-sentinel", "remake_id": -1, "item_kind": 5,
         "remake_type": 1, "payload_byte": 0xAE, "allow_furniture": True,
         "allow_tool": True, "expected_low_bits": None},
    ]
    results = []
    for case in cases:
        inputs.update(valid=True, item_kind=case["item_kind"],
                      remake_type=case["remake_type"],
                      allow_furniture=case["allow_furniture"],
                      allow_tool=case["allow_tool"])
        sandbox.uc.mem_write(remake_id_field,
                             struct.pack("<h", case["remake_id"]))
        sandbox.uc.mem_write(item, struct.pack("<HBBI", 4318, 1, 0,
                                                case["payload_byte"]))
        sandbox.uc.mem_write(item_kind_values + ITEM_INDEX * 2,
                             struct.pack("<H", case["item_kind"]))
        sandbox.uc.mem_write(remake_type_values + REMAKE_TYPE_INDEX * 2,
                             struct.pack("<H", case["remake_type"]))
        actual = sandbox.call(MAPPER, (item,))
        if case["expected_low_bits"] is None:
            expected = 0xFFFFFFFF
        else:
            expected = case["remake_id"] * 8 + case["expected_low_bits"]
        record = {
            "name": case["name"],
            "remake_id": case["remake_id"],
            "item_kind": case["item_kind"],
            "item_remake_type": case["remake_type"],
            "packed_payload_byte_at_item_offset_4": case["payload_byte"],
            "expected_low_bits": case["expected_low_bits"],
            "mapped_index": actual,
            "expected_index": expected,
            "match": actual == expected,
        }
        if actual != expected:
            raise AssertionError(record)
        results.append(record)

    if sandbox.unknown_imports:
        raise AssertionError({"unexpected_imports": sandbox.unknown_imports})
    result = {
        "native_elf_sha256": hashlib.sha256(NSO.read_bytes()).hexdigest(),
        "native_functions": {"item_to_catalog_index": hex(MAPPER),
                             "variant_source": hex(ITEM_REMAKE_TYPE_SOURCE)},
        "schema_enum_values": {"ItemKind.ItemRemakeType":
                               {"None": 0, "Ftr": 1, "Tool": 2,
                                "Smartphone": 3}},
        "scope": "AB2940, AB0F50 and F5AB10 execute original instructions with synthetic ItemParam/ItemKind table rows. Item lookup, RemakeID field access, and Ftr/Tool nested predicates are stubbed. No real table row or live save is loaded.",
        "cases": len(results),
        "mismatches": 0,
        "dependencies_stubbed": ["item validity", "A9C290 ItemParam row adapter",
                                  "ItemParam.ItemKind row index", "ItemKind row lookup",
                                  "RemakeID field accessor", "furniture/tool eligibility predicates"],
        "results": results,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({key: value for key, value in result.items()
                      if key != "results"}, indent=2))


if __name__ == "__main__":
    run()
