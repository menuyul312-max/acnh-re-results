#!/usr/bin/env python3
"""Run the native OpenDonatedNum catch-count gate over all local fish rows.

The field resolver is seeded with a controlled {hash, offset} descriptor and
the save accessor boundaries return controlled catch counts. The gate's row
lookup, field-cache logic, session-mode dispatch and final comparison execute
as original AArch64.
"""
import hashlib
import json
import os
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from nso_sandbox import Sandbox  # noqa: E402

DATA_ROOT = Path(os.environ.get("ACNH_RE_DATA_ROOT", "/workspace/acnh-re/output"))
NSO = ROOT / "inputs/additional_exefs/main"
OUT = ROOT / "output/gameplay/museum_donation_followup/open_donated_native.json"
ENTRY = 0x5B8E30
MODE_QUERY = 0xBC82D0
OPEN_DONATED_HASH = 0xEAC6A012
ROW_VALUE_OFFSET = 4
MODES = (0, 1, 2, 3)


def read_cstr(sb, address):
    return sb.read(address, 96).split(b"\0", 1)[0].decode("ascii")


def verify():
    fish_path = DATA_ROOT / "tables_resolved/FishStatusParam.json"
    fish = json.loads(fish_path.read_text())
    columns = [column["name"] for column in fish["columns"]]
    id_index, donated_index = columns.index("ItemID"), columns.index("OpenDonatedNum")
    hash_column = next(column for column in fish["columns"] if column["name"] == "OpenDonatedNum")
    if int(hash_column["hash"], 16) != OPEN_DONATED_HASH or hash_column["type"] != "u16":
        raise AssertionError({"schema": hash_column, "native_hash": hex(OPEN_DONATED_HASH)})
    table_rows = [(row[id_index], row[donated_index]) for row in fish["rows"]]
    item_ids = [item_id for item_id, _ in table_rows]
    if len(set(item_ids)) != len(item_ids):
        raise AssertionError("FishStatusParam ItemID values are not unique")
    base_id, last_id = min(item_ids), max(item_ids)
    row_count = last_id - base_id + 1

    sb = Sandbox(NSO)
    alloc = sb.alloc

    def q(address, value):
        sb.uc.mem_write(address, struct.pack("<Q", value))

    def w(address, value):
        sb.uc.mem_write(address, struct.pack("<I", value & 0xFFFFFFFF))

    def h(address, value):
        sb.uc.mem_write(address, struct.pack("<H", value & 0xFFFF))

    # F5B8E30 caches the value offset found for hash OPEN_DONATED_HASH.
    flag_ptr = sb.u64(0x32E5398)
    cache_ptr = sb.u64(0x32E53A8)
    sb.uc.mem_write(flag_ptr, b"\0")
    field_pairs = alloc(8)
    w(field_pairs, OPEN_DONATED_HASH)
    w(field_pairs + 4, ROW_VALUE_OFFSET)

    rows_by_id = {}
    ptr_array = alloc(row_count * 8)
    for item_id, threshold in table_rows:
        row_ptr = alloc(8)
        # The native table adapter presents a sequence of (field hash, value)
        # pairs. Use the real FishStatusParam value under the controlled hash.
        w(row_ptr, OPEN_DONATED_HASH)
        h(row_ptr + ROW_VALUE_OFFSET, threshold)
        q(ptr_array + (item_id - base_id) * 8, row_ptr)
        rows_by_id[item_id] = {"ptr": row_ptr, "threshold": threshold}

    table_view = alloc(0x400)
    h(table_view + 0x340, base_id)
    w(table_view + 0x320, row_count)
    q(table_view + 0x328, ptr_array)

    # The first condition in F5B8E30 checks an active local save context.
    player_context = alloc(0x200)
    w(player_context + 0x15C, 1)
    q(0x32D2A60, player_context)

    state = {"mode": 0, "local_catches": 0, "network_catches": 0}
    queried_keys = {"local": [], "network": []}
    resolver_calls = {"row_open": 0, "field_pairs": 0, "field_count": 0}

    def fish_row_lookup(s):
        item_id = s.reg("x1") & 0xFFFF
        s.uc.mem_write(s.reg("x0"), struct.pack("<h", item_id))
        return 0

    def catch_flag(s):
        key_pair = s.reg("x1")
        key = read_cstr(s, s.u64(key_pair + 8))
        queried_keys["local"].append(key)
        return state["local_catches"]

    def network_flag(s):
        key_pair = s.reg("x0")
        key = read_cstr(s, s.u64(key_pair + 8))
        queried_keys["network"].append(key)
        return state["network_catches"]

    # Save/table views are controlled. Native functions still resolve the
    # field hash through their cache and compare the resulting threshold.
    sb.stub(0xF588A0, fish_row_lookup)
    sb.stub(0xDA3FC0, lambda s: 0)
    sb.stub(0xE772E0, lambda s: 0)
    sb.stub(0xE712F0, lambda s: 0)
    sb.stub(0xDA4020, lambda s: 1)
    sb.stub(0xE77280, lambda s: 1)
    sb.stub(0xF628A0, catch_flag)
    sb.stub(0xF44AD0, network_flag)
    sb.stub(MODE_QUERY, lambda s: state["mode"])
    sb.stub(0x1665E80, lambda s: (resolver_calls.__setitem__("row_open", resolver_calls["row_open"] + 1) or 0x1234))
    sb.stub(0x1665E60, lambda s: (resolver_calls.__setitem__("field_pairs", resolver_calls["field_pairs"] + 1) or field_pairs))
    sb.stub(0x1665E50, lambda s: (resolver_calls.__setitem__("field_count", resolver_calls["field_count"] + 1) or 1))

    samples = []
    mismatches = []
    comparisons = 0
    for item_id, threshold in table_rows:
        counts = sorted({max(0, threshold - 1), threshold, threshold + 1})
        for mode in MODES:
            for count in counts:
                state.update(mode=mode, local_catches=count if mode < 2 else 0,
                             network_catches=count if mode >= 2 else 0)
                local_before = len(queried_keys["local"])
                network_before = len(queried_keys["network"])
                actual = sb.call(ENTRY, (table_view, item_id)) & 1
                selected_count = state["network_catches"] if mode >= 2 else state["local_catches"]
                expected = int(threshold <= selected_count)
                comparisons += 1
                if actual != expected:
                    mismatches.append({"item_id": item_id, "threshold": threshold, "mode": mode,
                                       "catch_count": selected_count, "actual": actual, "expected": expected})
                new_local = queried_keys["local"][local_before:]
                new_network = queried_keys["network"][network_before:]
                expected_local_reads = 2 if mode < 2 else 1
                expected_network_reads = 0 if mode < 2 else 1
                if new_local != ["CatchFish"] * expected_local_reads or \
                        new_network != (["FishNetHostCatchNumResult"] * expected_network_reads):
                    mismatches.append({"item_id": item_id, "mode": mode,
                                       "local_keys": new_local, "network_keys": new_network})
                if len(samples) < 16:
                    samples.append({"item_id": item_id, "threshold": threshold, "mode": mode,
                                    "catch_count": selected_count, "return": actual})

    expected_comparisons = sum(len({max(0, threshold - 1), threshold, threshold + 1})
                               for _, threshold in table_rows) * len(MODES)
    if comparisons != expected_comparisons:
        raise AssertionError({"comparisons": comparisons, "expected": expected_comparisons})
    if sb.u32(cache_ptr + 0x2C) != ROW_VALUE_OFFSET:
        raise AssertionError({"cached_field_offset": sb.u32(cache_ptr + 0x2C)})
    if resolver_calls != {"row_open": 1, "field_pairs": 1, "field_count": 1}:
        raise AssertionError({"resolver_calls": resolver_calls})
    if sb.unknown_imports:
        raise AssertionError({"unexpected_imports": sb.unknown_imports})

    histogram = {}
    for _, threshold in table_rows:
        histogram[str(threshold)] = histogram.get(str(threshold), 0) + 1
    result = {
        "native_nso_sha256": hashlib.sha256(NSO.read_bytes()).hexdigest(),
        "fish_status_raw_sha256": fish["raw"]["sha256"],
        "addresses": {"gate": hex(ENTRY), "mode_query": hex(MODE_QUERY),
                      "open_donated_hash": hex(OPEN_DONATED_HASH)},
        "native_contract": "F5B8E30 returns true exactly when the FishStatusParam.OpenDonatedNum u16 value is <= the selected catch count. Session modes 0/1 query CatchFish; modes 2/3 query FishNetHostCatchNumResult.",
        "table_source": "All 84 ItemID/OpenDonatedNum pairs come from the locally resolved baseline FishStatusParam table. Synthetic native row views contain the real threshold and field hash; the BCSV loader is not executed.",
        "field_resolver": "Native one-time field-cache initialization/search runs. Controlled 0x1665E80/60/50 adapters supply one field pair (hash 0xeac6a012, value offset +4); the function stores offset +4 and reuses it across the test set.",
        "save_accessors_controlled": ["0xf588a0 item row accessor", "0xda3fc0 table view", "0xe772e0/0xe712f0/0xe77280 save wrappers", "0xda4020 flag result", "0xf628a0 CatchFish value", "0xf44ad0 FishNetHostCatchNumResult value", "0xbc82d0 session mode"],
        "fish_status_rows": len(table_rows),
        "open_donated_num_histogram": histogram,
        "modes_tested": list(MODES),
        "threshold_boundary_comparisons": comparisons,
        "field_resolver_calls": resolver_calls,
        "mismatches": mismatches,
        "samples": samples,
        "open": ["Live save accessors and network-host ownership semantics", "This fish spawn gate does not identify the museum donation ledger or species donation bits."],
    }
    if mismatches:
        raise AssertionError(mismatches[:10])
    return result


def main():
    result = verify()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({key: value for key, value in result.items() if key != "samples"}, indent=2))


if __name__ == "__main__":
    main()
