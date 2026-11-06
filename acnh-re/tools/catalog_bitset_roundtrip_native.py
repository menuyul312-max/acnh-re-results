#!/usr/bin/env python3
"""Check the native catalog bit setter/getter against one synthetic bitset."""
import hashlib
import json
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from nso_sandbox import Sandbox  # noqa: E402

NSO = ROOT / "inputs/additional_exefs/main"
OUT = ROOT / "output/gameplay/catalog_bitset_roundtrip_native.json"
SETTER = 0xEECAD0
GETTER = 0xEECBA0


def run():
    sandbox = Sandbox(NSO)
    manager = sandbox.alloc(0x40)
    bits = sandbox.alloc(2000)
    world = sandbox.alloc(0x2000)
    row = sandbox.alloc(0x20)
    remake_id_field = sandbox.alloc(2)
    variant_field = sandbox.alloc(1)
    sandbox.uc.mem_write(manager + 8, struct.pack("<Q", bits))
    sandbox.uc.mem_write(manager + 16, struct.pack("<Q", 0))
    inputs = {"valid_item": True, "variant_present": True}

    # Keep the mapper native. Only table selection, item validity, accessors,
    # and the synthetic save-backed context/bitset are controlled boundaries.
    sandbox.stub(0xF58D00, lambda s: int(inputs["valid_item"]))

    def bind_item_row(s):
        s.uc.mem_write(s.reg("x0") + 0x10, struct.pack("<Q", row))
        return 0

    def bind_manager(s):
        s.uc.mem_write(s.reg("x0") + 8, struct.pack("<Q", manager))
        return 0

    sandbox.stub(0xA9C290, bind_item_row)
    sandbox.stub(0xAAC250, lambda s: 1)
    sandbox.stub(0xA1E920, lambda s: remake_id_field)
    sandbox.stub(0xAB0F50,
                 lambda s: variant_field if inputs["variant_present"] else 0)
    sandbox.stub(0xF8F400, lambda s: s.reg("x0"))
    sandbox.stub(0xF8F540, lambda s: s.reg("x0"))
    sandbox.stub(0xDA3FC0, lambda s: 0)
    sandbox.stub(0xEF6700, lambda s: world)
    sandbox.stub(0xEE9350, bind_manager)
    sandbox.stub(0xEE9490, bind_manager)
    sandbox.stub(0xEE94F0, lambda s: 0)
    sandbox.stub(0xEE93D0, lambda s: 0)

    cases = []

    def check(remake_id, variant, *, valid_item=True, variant_present=True):
        inputs["valid_item"] = valid_item
        inputs["variant_present"] = variant_present
        sandbox.uc.mem_write(remake_id_field, struct.pack("<h", remake_id))
        sandbox.uc.mem_write(variant_field, bytes([variant & 0xFF]))
        sandbox.uc.mem_write(bits, bytes(2000))

        if not valid_item or remake_id < 0:
            index = None
        else:
            index = remake_id * 8 + ((variant & 7) if variant_present else 0)

        set_result = sandbox.call(SETTER, (world, 4318))
        query_result = sandbox.call(GETTER, (world, 4318))
        expected_set = int(index is not None)
        expected_query = bool(index is not None and index < 16000)
        expected_bytes = bytearray(2000)
        if expected_query:
            byte_offset = index >> 3
            expected_bytes[byte_offset] |= 1 << (index & 7)
        actual_bytes = sandbox.read(bits, 2000)

        record = {
            "remake_id": remake_id,
            "variant_input": variant & 0xFF,
            "variant_present": variant_present,
            "valid_item": valid_item,
            "mapped_index": index,
            "setter_return": set_result,
            "getter_return": bool(query_result),
            "expected_getter": expected_query,
            "bitset_matches": actual_bytes == bytes(expected_bytes),
        }
        if (set_result != expected_set or bool(query_result) != expected_query
                or actual_bytes != bytes(expected_bytes)):
            raise AssertionError(record)
        cases.append(record)

    for remake_id, variant in [
            (0, 0), (0, 7), (3, 7), (4, 0), (31, 0), (31, 7),
            (1999, 0), (1999, 7), (2000, 0), (-1, 0)]:
        check(remake_id, variant)
    check(7, 0xFF, variant_present=False)
    check(5, 2, valid_item=False)

    # Confirm the neighboring variant index remains clear after one setter call.
    inputs["valid_item"] = True
    inputs["variant_present"] = True
    sandbox.uc.mem_write(remake_id_field, struct.pack("<h", 3))
    sandbox.uc.mem_write(variant_field, bytes([5]))
    sandbox.uc.mem_write(bits, bytes(2000))
    sandbox.call(SETTER, (world, 4318))
    sandbox.uc.mem_write(variant_field, bytes([4]))
    neighbor_result = sandbox.call(GETTER, (world, 4318))
    cases.append({"remake_id": 3, "set_variant": 5, "queried_neighbor_variant": 4,
                  "getter_return": bool(neighbor_result), "expected_getter": False,
                  "bitset_matches": not bool(neighbor_result)})
    if neighbor_result:
        raise AssertionError("neighboring variant unexpectedly shared the set bit")

    if sandbox.unknown_imports:
        raise AssertionError({"unexpected_imports": sandbox.unknown_imports})
    result = {
        "native_elf_sha256": hashlib.sha256(NSO.read_bytes()).hexdigest(),
        "native_functions": {"setter": hex(SETTER), "getter": hex(GETTER)},
        "scope": "Original setter, getter, mapper, and index arithmetic run on a synthetic 2000-byte bitset. ItemParam/save context and accessor boundaries are stubbed; no live save is loaded or written.",
        "cases": len(cases),
        "mismatches": 0,
        "dependencies_stubbed": ["item validity", "ItemParam row/RemakeID lookup", "variant-byte source", "world/save accessor wrappers", "synthetic bitset manager"],
        "results": cases,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({key: value for key, value in result.items() if key != "results"}, indent=2))


if __name__ == "__main__":
    run()
