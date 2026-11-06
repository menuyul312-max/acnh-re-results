#!/usr/bin/env python3
"""Exercise the museum marker's native state-record writer and reader.

The original NSO bodies at 0xe68280, 0xe68900, 0xeaa8c0, and 0xfa4300 run
unchanged. State-manager allocation and the generic context/token adapters are
synthetic. This checks value flow and row-state gates, not the gameplay name
of the stored byte or its live save source.
"""
import hashlib
import json
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from nso_sandbox import Sandbox, NSO_SHA256  # noqa: E402

NSO = ROOT / "inputs/additional_exefs/main"
OUT = ROOT / "output/gameplay/museum_donation_followup/marker_state_native.json"
STATE_WRITE = 0xE68280
STATE_WRITE_WRAPPER = 0xE684F0
STATE_LOOKUP = 0xE68900
STATE_QUERY = 0xEAA8C0
PAIR_TO_SLOT = 0xFA4300
PAIR_ALLOCATOR = 0xFA4100
CONTEXT_MANAGER_GLOBAL = 0x32D4FF0
RECORD_STRIDE = 0xB28
RECORD_LIMIT = 8


def put_u32(sb, address, value):
    sb.uc.mem_write(address, struct.pack("<I", value & 0xFFFFFFFF))


def put_u64(sb, address, value):
    sb.uc.mem_write(address, struct.pack("<Q", value & 0xFFFFFFFFFFFFFFFF))


def run_native_cases():
    image_hash = hashlib.sha256(NSO.read_bytes()).hexdigest()
    if image_hash != NSO_SHA256:
        raise AssertionError(f"unexpected ExeFS main hash: {image_hash}")

    sb = Sandbox(NSO)
    controls = {"row_index": 0, "context_token": 5, "view_token": 5}
    helper_calls = {}

    # The writer's generic lifetime/side-effect helpers are controlled. The
    # four target bodies (including the pointer-pair mapper) are never stubbed.
    for address in (0xE69300, 0xEA8EA0, 0xEA8EC0, 0xE67C10, 0xEAA1A0,
                    0xE68A90, 0xE68C70):
        sb.stub(address, lambda s, va=address: helper_calls.__setitem__(hex(va), helper_calls.get(hex(va), 0) + 1) or 0)

    # Avoid the optional serial-number side path in E68280; a negative result
    # takes its native early exit before touching the serial counter global.
    sb.stub(0xE678D0, lambda s: 0xFFFFFFFF)

    def context_snapshot(s):
        # CC85B0 returns its eight-byte result through AAPCS64's x8 register.
        s.uc.mem_write(s.reg("x8"), bytes([controls["context_token"]]) + bytes(7))
        return 0

    def resolve_view(s):
        return controls["view_ptr"]

    sb.stub(0xBC85B0, context_snapshot)
    sb.stub(0xEAA590, resolve_view)
    sb.stub(0xEAA990, lambda s: controls["row_index"])

    context = sb.alloc(8, align=8)
    view = sb.alloc(8, align=8)
    controls["view_ptr"] = view
    manager_global_cell = sb.alloc(8, align=8)
    put_u64(sb, CONTEXT_MANAGER_GLOBAL, manager_global_cell)

    def set_manager(manager_ptr):
        put_u64(sb, manager_global_cell, manager_ptr)

    manager = sb.alloc(0x6000, align=0x10)
    set_manager(manager)

    # FA4300's original code maps an identity pair in an eight-row table to
    # its slot number, which CD9F0 passes as E68280's third argument.
    pair_table = sb.alloc(RECORD_LIMIT * 9 * 8, align=8)
    pair = sb.alloc(16, align=8)
    pair_cases = []
    for slot in range(RECORD_LIMIT):
        first, second = 0x100000 + slot, 0x200000 + slot
        put_u64(sb, pair_table + slot * 9 * 8, first)
        put_u64(sb, pair_table + slot * 9 * 8 + 8, second)
        put_u64(sb, pair, first)
        put_u64(sb, pair + 8, second)
        actual = sb.call(PAIR_TO_SLOT, (pair_table, pair))
        if actual != slot:
            raise AssertionError({"pair_slot": slot, "actual": hex(actual)})
        pair_cases.append({"slot": slot, "returned": actual})

    allocator_table = sb.alloc(RECORD_LIMIT * 9 * 8, align=8)
    allocated_state_manager = sb.alloc(0x6000, align=0x10)
    allocator_cases = []
    for slot in range(RECORD_LIMIT):
        first, second = 0x300000 + slot, 0x400000 + slot
        put_u64(sb, pair, first)
        put_u64(sb, pair + 8, second)
        actual = sb.call(PAIR_ALLOCATOR, (allocator_table, pair))
        expected_row = allocator_table + slot * 9 * 8
        if actual != slot or sb.u64(expected_row) != first or sb.u64(expected_row + 8) != second:
            raise AssertionError({"allocated_pair_slot": slot, "actual": hex(actual)})
        state_row = sb.call(STATE_WRITE, (allocated_state_manager, 0, actual, 1))
        stored_slot = sb.read(allocated_state_manager + state_row * RECORD_STRIDE + 0xB0D, 1)[0]
        if state_row != slot or stored_slot != actual:
            raise AssertionError({"allocated_pair_state_slot": slot, "row": state_row, "stored": stored_slot})
        allocator_cases.append({"slot": slot, "returned": actual,
                                "pair_stored": [hex(sb.u64(expected_row)), hex(sb.u64(expected_row + 8))],
                                "state_row": state_row, "stored_plus_b0d": stored_slot})
    put_u64(sb, pair, 0x500000)
    put_u64(sb, pair + 8, 0x600000)
    allocator_full_return = sb.call(PAIR_ALLOCATOR, (allocator_table, pair))
    if allocator_full_return != 0xFFFFFFFF:
        raise AssertionError({"pair_allocator_full_return": hex(allocator_full_return)})

    # Test the numeric values passed by the successful index-producing
    # callers. Each call allocates the next native record, and EAA8C0 reads the
    # low byte back only for an active state-kind-0 record.
    value_cases = []
    for slot, pair_case in enumerate(pair_cases):
        value = pair_case["returned"]
        actual_slot = sb.call(STATE_WRITE, (manager, 0, value, 1))
        if actual_slot != slot:
            raise AssertionError({"expected_state_slot": slot, "actual": actual_slot})
        row = manager + slot * RECORD_STRIDE
        record = sb.read(row + 0xB08, 7)
        state_kind, active, stored_value, secondary = record[0:4], record[4], record[5], record[6]
        controls["row_index"] = slot
        controls["context_token"] = 5
        controls["view_token"] = 5
        sb.uc.mem_write(view, bytes([controls["view_token"]]))
        result = sb.call(STATE_QUERY, (context, 2))
        if state_kind != b"\x00\x00\x00\x00" or active != 1 or stored_value != value or secondary != 1:
            raise AssertionError({"slot": slot, "record": record.hex()})
        if result != value:
            raise AssertionError({"slot": slot, "expected_value": value, "query": hex(result)})
        value_cases.append({"row": slot, "param_3": value, "stored_plus_b0d": stored_value,
                            "row_state": 0, "active": active, "query_result": result})

    full_manager_return = sb.call(STATE_WRITE, (manager, 0, 0x55, 1))
    if full_manager_return != 0xFFFFFFFF:
        raise AssertionError({"full_manager_return": hex(full_manager_return)})

    # E684F0's caller passes a runtime row key in param_3. Exercise its
    # forwarding path with a synthetic key so the wrapper is covered too.
    wrapper_manager = sb.alloc(0xC000, align=0x10)
    wrapper_index = sb.call(STATE_WRITE_WRAPPER, (wrapper_manager, 0, 0x42))
    wrapper_record = wrapper_manager + 0xB08
    wrapper_state = sb.u32(wrapper_record)
    wrapper_active = sb.read(wrapper_record + 4, 1)[0]
    wrapper_value = sb.read(wrapper_record + 5, 1)[0]
    if wrapper_index != 0 or wrapper_state != 0 or wrapper_active != 1 or wrapper_value != 0x42:
        raise AssertionError({"wrapper": (wrapper_index, wrapper_state, wrapper_active, wrapper_value)})

    wrapper_kind1_manager = sb.alloc(0xC000, align=0x10)
    wrapper_kind1_index = sb.call(STATE_WRITE_WRAPPER, (wrapper_kind1_manager, 1, 0x43))
    kind1_record = wrapper_kind1_manager + 0xB08
    kind1_state = sb.u32(kind1_record)
    kind1_active = sb.read(kind1_record + 4, 1)[0]
    kind1_value = sb.read(kind1_record + 5, 1)[0]
    set_manager(wrapper_kind1_manager)
    controls["row_index"] = 0
    controls["context_token"] = 5
    controls["view_token"] = 5
    sb.uc.mem_write(view, bytes([5]))
    kind1_query = sb.call(STATE_QUERY, (context, 2))
    if (wrapper_kind1_index != 0 or kind1_state != 1 or kind1_active != 1
            or kind1_value != 0x43 or kind1_query != 0xFFFFFFFF):
        raise AssertionError({"wrapper_kind1": (wrapper_kind1_index, kind1_state, kind1_active,
                                                 kind1_value, hex(kind1_query))})

    # The two 0xCCD40 branches use state-kind 2 and param_3=0. The row stays
    # active, but the marker query rejects any nonzero state kind.
    error_manager = sb.alloc(0x6000, align=0x10)
    error_index = sb.call(STATE_WRITE, (error_manager, 2, 0, 1))
    if error_index != 0:
        raise AssertionError({"state2_index": error_index})
    error_row = error_manager
    error_state = sb.u32(error_row + 0xB08)
    error_active = sb.read(error_row + 0xB0C, 1)[0]
    error_value = sb.read(error_row + 0xB0D, 1)[0]
    set_manager(error_manager)
    controls["row_index"] = 0
    query_state2 = sb.call(STATE_QUERY, (context, 2))
    if error_state != 2 or error_active != 1 or error_value != 0 or query_state2 != 0xFFFFFFFF:
        raise AssertionError({"state2": (error_state, error_active, error_value, hex(query_state2))})

    # A mode-2 context-token mismatch also returns the sentinel before row
    # lookup. Restore a valid kind-0 row to isolate this gate.
    mismatch_manager = sb.alloc(0x6000, align=0x10)
    sb.call(STATE_WRITE, (mismatch_manager, 0, 0x2A, 1))
    set_manager(mismatch_manager)
    controls["row_index"] = 0
    controls["context_token"] = 5
    controls["view_token"] = 4
    sb.uc.mem_write(view, bytes([controls["view_token"]]))
    query_mismatch = sb.call(STATE_QUERY, (context, 2))
    if query_mismatch != 0xFFFFFFFF:
        raise AssertionError({"token_mismatch_query": hex(query_mismatch)})

    # No active row and out-of-range token index each return the same sentinel.
    empty_manager = sb.alloc(0x6000, align=0x10)
    set_manager(empty_manager)
    controls["context_token"] = 5
    controls["view_token"] = 5
    sb.uc.mem_write(view, bytes([5]))
    controls["row_index"] = 0
    query_absent = sb.call(STATE_QUERY, (context, 2))
    controls["row_index"] = 8
    query_out_of_range = sb.call(STATE_QUERY, (context, 2))
    if query_absent != 0xFFFFFFFF or query_out_of_range != 0xFFFFFFFF:
        raise AssertionError({"absent": hex(query_absent), "out_of_range": hex(query_out_of_range)})

    if sb.unknown_imports:
        raise AssertionError({"unexpected_imports": sb.unknown_imports})

    return {
        "source_nso_sha256": image_hash,
        "native_functions": {
            "state_writer": hex(STATE_WRITE),
            "state_writer_wrapper": hex(STATE_WRITE_WRAPPER),
            "state_lookup": hex(STATE_LOOKUP),
            "state_query": hex(STATE_QUERY),
            "identity_pair_allocator": hex(PAIR_ALLOCATOR),
            "pair_to_slot_mapper": hex(PAIR_TO_SLOT),
        },
        "execution_scope": "Original E68280, E684F0, E68900, EAA8C0, FA4100 and FA4300 instructions execute. Generic state initialization, context-token snapshot, view resolution, optional serial side effects, and manager memory are synthetic/controlled.",
        "callsite_value_cases": value_cases,
        "pair_to_slot_cases": pair_cases,
        "pair_allocator_cases": allocator_cases,
        "pair_allocator_full_return": hex(allocator_full_return),
        "state_kind_2_case": {
            "param_2": 2,
            "param_3": 0,
            "stored_state_kind": error_state,
            "active": error_active,
            "stored_plus_b0d": error_value,
            "query_result": hex(query_state2),
        },
        "runtime_key_wrapper_case": {
            "wrapper_param_2": 0,
            "wrapper_param_3": "0x42",
            "returned_record": wrapper_index,
            "stored_state_kind": wrapper_state,
            "active": wrapper_active,
            "stored_plus_b0d": hex(wrapper_value),
        },
        "secondary_kind_wrapper_case": {
            "wrapper_param_2": 1,
            "wrapper_param_3": "0x43",
            "returned_record": wrapper_kind1_index,
            "stored_state_kind": kind1_state,
            "active": kind1_active,
            "stored_plus_b0d": hex(kind1_value),
            "mode_2_query_result": hex(kind1_query),
        },
        "query_gate_cases": {
            "context_token_mismatch": hex(query_mismatch),
            "absent_row": hex(query_absent),
            "out_of_range_row_index": hex(query_out_of_range),
        },
        "record_limit": RECORD_LIMIT,
        "full_manager_write_return": hex(full_manager_return),
        "helper_call_counts": helper_calls,
        "case_count": len(value_cases) + len(pair_cases) + len(allocator_cases) + 8,
        "mismatches": 0,
        "not_proven": [
            "Static callers show E68280 can receive 0..7 identity-pair or MakeVillagePlayerFlag slot values, but the Museum path reads a kind-0 CFAD0 configuration key from +0xb0d; the fixture's row values are synthetic and do not identify the donor.",
            "The full 0x2ee460 pair/context-copy and 0x2f5030/0x2f5240 caller bodies are static-only; the fixture exercises their slot allocators and the shared writer/query contract with controlled inputs.",
            "CFAD0 supplies E684F0 with the first u32 from a runtime configuration row, and E68280 stores its low byte at +0xb0d; concrete CFAD0 row values are absent from the captured tables/runtime snapshot.",
            "No live save file or running game is available to trace the selected CFAD0 key through OwlDonationDone into the next-day facility transition.",
        ],
    }


def main():
    result = run_native_cases()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({key: value for key, value in result.items() if key not in ("callsite_value_cases", "pair_to_slot_cases")}, indent=2))


if __name__ == "__main__":
    main()
