#!/usr/bin/env python3
"""Export static evidence for HHA same-anchor writes and grade-flag xrefs.

This pass distinguishes the grid's last accepted write from the still-unknown
order in which overlapping room furniture is initially inserted. It also
records the indexed save descriptor aliases and generic flag accessor coverage.
No game runtime or inbox delivery is simulated.
"""
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import sys
import zlib

ROOT = Path(__file__).resolve().parents[1]
DATA = Path("/workspace/acnh-re")
DB = DATA / "output/index.sqlite"
NSO = DATA / "inputs/additional_exefs/main"
DECOMP = DATA / "output/binary/analysis_decomp"
POINTER_ARRAYS = DATA / "output/binary/code_pointer_arrays.json"
EVENT_HANDLERS = DATA / "output/binary/event_handlers_resolved.json"
NATIVE_FLAGS = DATA / "output/gameplay/native_flag_refs.json"
FLAG_INDEX = DATA / "output/gameplay/flag_index.json"
MAIL_STATIC = ROOT / "output/gameplay/house_hha_followup/hha_overlap_mail_dispatch_static.json"
SAVE_LAYOUT = ROOT / "output/gameplay/save_layout.json"
SAVE_CROSSWALK = ROOT / "output/gameplay/save_layout_external_crosswalk.json"
OUT = ROOT / "output/gameplay/house_hha_followup/hha_same_anchor_flag_successor.json"

NSO_SHA256 = "f8d248109ff72999b4600ae3749f8c7397fb960f7ad3ab8dee3018ae9e14e900"
HHA_FLAG = "cPlayer:HHAGradeMailFlag"

if (DATA / ".deps").is_dir():
    sys.path.insert(0, str(DATA / ".deps"))
sys.path.insert(0, str(ROOT / "tools"))
from capstone import Cs, CS_ARCH_ARM64, CS_MODE_ARM  # noqa: E402
from exefs_modules import NsoModule  # noqa: E402


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def hx(value):
    return f"0x{value:x}"


def decomp(name):
    return (DECOMP / f"{name}.c").read_text()


def indexed_callers(db, target):
    rows = []
    for row in db.execute(
        "SELECT pc,owner_va,instruction FROM direct_calls WHERE target_va=? ORDER BY pc",
        (target,),
    ):
        owner = row["owner_va"]
        owner_name = None
        if owner is None:
            native = db.execute(
                "SELECT va,name FROM native_functions WHERE va<=? AND span_end_va>? "
                "ORDER BY va DESC LIMIT 1",
                (row["pc"], row["pc"]),
            ).fetchone()
            if native:
                owner, owner_name = native["va"], native["name"]
        else:
            function = db.execute(
                "SELECT ghidra_name FROM functions WHERE va=?", (owner,)
            ).fetchone()
            owner_name = function["ghidra_name"] if function else None
        rows.append({
            "call_pc": hx(row["pc"]),
            "owner_va": hx(owner) if owner is not None else None,
            "owner_name": owner_name,
            "instruction": row["instruction"],
        })
    return rows


def direct_call_graph(db):
    """Build only the indexed direct BL/B call graph; virtual edges stay separate."""
    graph = {}
    for row in db.execute("SELECT pc,owner_va,target_va FROM direct_calls ORDER BY pc"):
        owner = row["owner_va"]
        if owner is None:
            native = db.execute(
                "SELECT va FROM native_functions WHERE va<=? AND span_end_va>? "
                "ORDER BY va DESC LIMIT 1",
                (row["pc"], row["pc"]),
            ).fetchone()
            owner = native["va"] if native else None
        if owner is not None:
            graph.setdefault(owner, set()).add(row["target_va"])
    return graph


def shortest_direct_path(graph, start, target):
    """Return one shortest indexed direct-call path, or None."""
    from collections import deque

    todo = deque([(start, [start])])
    seen = {start}
    while todo:
        current, path = todo.popleft()
        if current == target:
            return [hx(value) for value in path]
        for callee in sorted(graph.get(current, ())):
            if callee not in seen:
                seen.add(callee)
                todo.append((callee, path + [callee]))
    return None


def pointer_array_hits(targets):
    arrays = json.loads(POINTER_ARRAYS.read_text())
    wanted = {hx(value) for value in targets}
    hits = []
    for array in arrays:
        for entry in array.get("entries", []):
            if entry.get("target_va") in wanted:
                hits.append({
                    "array_start_va": array.get("start_va"),
                    "pointer_va": entry.get("pointer_va"),
                    "target_va": entry.get("target_va"),
                })
    return hits


def hash_candidate_values(value):
    """Return common 32-bit text-hash candidates; these are probes, not game semantics."""
    data = value if isinstance(value, bytes) else value.encode("utf-8")

    def u32(number):
        return number & 0xFFFFFFFF

    fnv = 0x811C9DC5
    djb = 5381
    sdbm = 0
    jenkins = 0
    for byte in data:
        fnv = u32((fnv ^ byte) * 0x01000193)
        djb = u32(djb * 33 + byte)
        sdbm = u32(byte + (sdbm << 6) + (sdbm << 16) - sdbm)
        jenkins = u32(jenkins + byte)
        jenkins = u32(jenkins + (jenkins << 10))
        jenkins = u32(jenkins ^ (jenkins >> 6))
    jenkins = u32(jenkins + (jenkins << 3))
    jenkins = u32(jenkins ^ (jenkins >> 11))
    jenkins = u32(jenkins + (jenkins << 15))
    return {
        "crc32": zlib.crc32(data) & 0xFFFFFFFF,
        "fnv1a32": fnv,
        "djb2_32": djb,
        "sdbm32": sdbm,
        "jenkins_oat32": jenkins,
        "adler32": zlib.adler32(data) & 0xFFFFFFFF,
    }


def candidate_hash_audit(db):
    labels = [
        "HHAGradeMailFlag",
        "cPlayer:HHAGradeMailFlag",
        "Player:HHAGradeMailFlag",
        "EventFlagsPlayerParam:HHAGradeMailFlag",
        "cPlayer_HHAGradeMailFlag",
        "HHA|評価の手紙送付ON?",
        "SavePlayerHouse+0x263d0",
        "SavePlayerHouse+0x263d1",
        "SavePlayerHouse+0x263e0",
        "SavePlayerHouse:0x263d0",
        "SavePlayerHouse:0x263d1",
        "SavePlayerHouse:0x263e0",
        "0x263d0",
        "0x263d1",
        "0x263e0",
    ]
    candidates = {}
    for label in labels:
        for variant in {label, label.lower(), label.upper()}:
            for suffix in (b"", b"\x00"):
                variant_bytes = variant.encode("utf-8") + suffix
                for algorithm, value in hash_candidate_values(variant_bytes).items():
                    candidates.setdefault(value, []).append({
                        "label": label,
                        "variant": "lower" if variant == label.lower() and variant != label else (
                            "upper" if variant == label.upper() and variant != label else "exact"
                        ),
                        "nul_terminated": bool(suffix),
                        "algorithm": algorithm,
                    })
    matches = []
    for value, sources in sorted(candidates.items()):
        refs = [dict(row) for row in db.execute(
            "SELECT hash,pc,owner_va FROM hash_refs WHERE hash=? ORDER BY pc", (value,)
        )]
        if refs:
            matches.append({"candidate_hash": hx(value), "sources": sources, "refs": refs})
    raw_offsets = {}
    for value in (0x263D0, 0x263D1, 0x263E0):
        raw_offsets[hx(value)] = [dict(row) for row in db.execute(
            "SELECT hash,pc,owner_va FROM hash_refs WHERE hash=? ORDER BY pc", (value,)
        )]

    generic_columns = {}
    for value in (0x5140E4B4, 0xBED25A86):
        generic_columns[hx(value)] = {
            "table_columns": [dict(row) for row in db.execute(
                "SELECT table_name,name,offset,width,evidence FROM columns_resolved "
                "WHERE hash=? ORDER BY table_name", (value,)
            )],
            "native_hash_reference_sites": [dict(row) for row in db.execute(
                "SELECT printf('0x%08x',hash) AS hash,printf('0x%llx',pc) AS pc,"
                "printf('0x%llx',owner_va) AS owner_va FROM hash_refs "
                "WHERE hash=? ORDER BY pc", (value,)
            )],
        }
    return {
        "index_hash_ref_rows": db.execute("SELECT count(*) FROM hash_refs").fetchone()[0],
        "candidate_algorithms": ["CRC32", "FNV-1a 32", "djb2 32", "SDBM 32", "Jenkins one-at-a-time 32", "Adler-32"],
        "candidate_labels": labels,
        "case_and_nul_variants_tested": ["exact", "lowercase", "uppercase", "each with and without trailing NUL"],
        "distinct_candidate_hashes_tested": len(candidates),
        "candidate_hash_matches": matches,
        "raw_offset_integer_hash_refs": raw_offsets,
        "generic_event_flag_column_hashes": generic_columns,
        "interpretation": "No tested text-hash candidate or raw offset integer has a hash_refs hit. 0x5140e4b4 and 0xbed25a86 are unresolved BCSV column hashes reused across EventFlags schemas; they are not aliases for HHAGradeMailFlag. This is a bounded candidate scan, not proof that no dynamic alias/hash exists.",
    }


def decomp_offset_inventory():
    offsets = (0x263D0, 0x263D1, 0x263E0, 0x263F0)
    patterns = {value: re.compile(r"\+\s*0x" + f"{value:x}" + r"\b", re.IGNORECASE) for value in offsets}
    hits = {hx(value): [] for value in offsets}
    file_count = 0
    for path in DECOMP.glob("*.c"):
        file_count += 1
        try:
            lines = path.read_text(errors="replace").splitlines()
        except OSError:
            continue
        for line_number, line in enumerate(lines, 1):
            for value, pattern in patterns.items():
                if pattern.search(line):
                    hits[hx(value)].append({
                        "function_file": path.name,
                        "line": line_number,
                        "pseudocode": line.strip(),
                    })
    return {
        "source_directory": str(DECOMP),
        "decomp_file_count_scanned": file_count,
        "literal_offset_reference_hits": hits,
        "interpretation": "This inventory finds pseudocode expressions using these literal offsets, including +0x263f0 in a separate constructor with an unresolved base pointer. It does not assign semantic field names to unlabelled save bytes.",
    }


def pointer_index_audit(targets):
    arrays = json.loads(POINTER_ARRAYS.read_text())
    wanted = {hx(target): target for target in targets}
    hits = {key: [] for key in wanted}
    for array in arrays:
        for entry in array.get("entries", []):
            target = entry.get("target_va")
            if target in hits:
                hits[target].append({
                    "array_start_va": array.get("start_va"),
                    "pointer_va": entry.get("pointer_va"),
                    "status": array.get("status"),
                })
    return {
        "indexed_pointer_sequence_count": len(arrays),
        "target_hits": hits,
        "interpretation": "The scan covers exact target addresses in the indexed relocated code-pointer sequences. Those sequences are not presumed to be C++ vtables; absence excludes these indexed pointer targets only.",
    }


def generic_accessor_owner_inventory(db, native_flags):
    result = {}
    flags = native_flags["data"]["flags"]
    for target in (0xF4AFF0, 0xF4B0D0, 0xF4B170):
        rows = list(db.execute(
            "SELECT pc,owner_va FROM direct_calls WHERE target_va=? ORDER BY pc", (target,)
        ))
        counts = {}
        for row in rows:
            owner = row["owner_va"]
            if owner is None:
                continue
            counts[owner] = counts.get(owner, 0) + 1
        owners = []
        for owner, call_count in sorted(counts.items()):
            owner_hex = hx(owner)
            owner_flags = sorted(
                key for key, info in flags.items()
                if owner_hex in info.get("referencing_functions", [])
            )
            relevant_flags = [key for key in owner_flags if re.search(r"hha|grade|mail|house|home", key, re.IGNORECASE)]
            if relevant_flags:
                owners.append({
                    "owner_va": owner_hex,
                    "direct_callsite_count": call_count,
                    "named_relevant_flags_in_native_flag_index": relevant_flags,
                })
        result[hx(target)] = {
            "direct_callsite_count": len(rows),
            "unique_resolved_owner_count": len(counts),
            "owners_with_HHA_grade_mail_or_house_named_flag_refs": owners,
        }
    return result


def main():
    if sha256(NSO) != NSO_SHA256:
        raise AssertionError("main NSO hash differs from the indexed 1.0.0 build")
    nso = NsoModule(NSO.read_bytes())
    db = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    db.row_factory = sqlite3.Row

    # Check that the indexed pseudocode and native instruction flow still agree.
    insert = decomp("52d980")
    update = decomp("52e0a0")
    rectangle_writer = decomp("52e360")
    cell_writer = decomp("52df00")
    hha_resolver = decomp("a13fe0")
    if "FUN_0062df00(param_1,param_2,&lStack_60);" not in insert:
        raise AssertionError("same-anchor insert no longer calls the cell writer")
    if "FUN_0062e360(param_1,plVar6[1] + (long)plVar10,auStack_90);" not in update:
        raise AssertionError("occupied-cell update no longer reaches rectangle writer")
    if "FUN_010589e0(plStack_80[1] + (long)plVar5,param_2);" not in cell_writer:
        raise AssertionError("generic grid cell writer no longer assigns one cell value")
    if "FUN_0062f220();" not in hha_resolver:
        raise AssertionError("HHA resolver no longer reads through the room-grid getter")

    decoder = Cs(CS_ARCH_ARM64, CS_MODE_ARM)
    disassembly = {}
    for start, size in ((0x52D980, 0x180), (0x52E0A0, 0x2A0), (0x52E360, 0x2D0)):
        disassembly.update({ins.address: ins for ins in decoder.disasm(nso.read(start, size), start)})

    def require(pc, mnemonic, operands):
        ins = disassembly.get(pc)
        actual = (ins.mnemonic, ins.op_str) if ins else None
        if actual != (mnemonic, operands):
            raise AssertionError({"pc": hx(pc), "expected": [mnemonic, operands], "actual": actual})

    # 0x52d980's anchor branch writes the incoming descriptor without reading
    # or comparing the prior cell value. The rectangle helper's separate
    # non-anchor conflict checks are intentionally outside this rule.
    require(0x52DAE8, "sub", "x2, x29, #0x50")
    require(0x52DAF0, "mov", "x1, x20")
    require(0x52DAF4, "bl", "#0x52df00")
    # 0x52e0a0 skips -2 cells; recognized occupants reach the rectangle writer.
    require(0x52E1A8, "ldrsh", "w8, [x8, x0]")
    require(0x52E1AC, "cmn", "w8, #2")
    require(0x52E1B0, "b.eq", "#0x52e33c")
    require(0x52E1D4, "bl", "#0xf58e20")
    require(0x52E1FC, "tbz", "w22, #0, #0x52e210")
    require(0x52E208, "bl", "#0x52e360")
    require(0x52E214, "cmn", "w8, #3")
    require(0x52E218, "b.ne", "#0x52e33c")
    if "FUN_01058e20" not in update:
        raise AssertionError("occupied cell recognition predicate missing")

    room_update = decomp("63ca90")
    room_setter = decomp("a14320")
    room_replace = decomp("a144b0")
    if not all(token in room_update for token in ("FUN_00b143d0(param_1);", "FUN_0062f280();")):
        raise AssertionError("room-scoped update wrapper changed")
    if "FUN_0062f270();" not in room_setter:
        raise AssertionError("room-scoped insert wrapper changed")
    if "FUN_0062f280();" not in room_replace:
        raise AssertionError("room-scoped occupied-cell update wrapper changed")

    hha_callsites = {
        hx(target): indexed_callers(db, target)
        for target in (
            0x52F220, 0x52D640, 0x52F270, 0x52F280, 0x52D980,
            0x52E0A0, 0x52E360, 0x52DF00, 0xA14320, 0xA144B0,
            0x63CA90,
        )
    }
    if [row["owner_va"] for row in hha_callsites["0x52e0a0"]] != ["0x52f280"]:
        raise AssertionError("direct 0x52e0a0 caller inventory changed")
    if sorted({row["owner_va"] for row in hha_callsites["0x52df00"]}) != ["0x52d980", "0x52e360"]:
        raise AssertionError("direct cell writer callers changed")

    # The room wrapper is called from a native loop that visits generated
    # spatial rows, but those rows are not proven to be the initial save-item
    # loader order for a shared-anchor case.
    population_loop = {
        "native_function_va": "0x5ff7f0",
        "direct_call_pc": "0x600188",
        "call_target": "0x63ca90",
        "call_site_setup": [
            "x1 is the immediate room index 1",
            "x2 is a pointer to the current generated 0x38-byte spatial row + 8",
            "the enclosing loop increments its row counter and stops at a generated count",
        ],
        "direct_callers_of_loop": [
            row["owner_va"] for row in indexed_callers(db, 0x5FF7F0)
        ],
        "limit": "This proves a room-grid update path over generated spatial rows, not the order in which saved furniture objects are initially loaded into a room grid.",
    }
    graph = direct_call_graph(db)
    spatial_parent_targets = (0x600F30, 0x6010B0, 0x601230)
    spatial_parent_rows = {
        hx(target): indexed_callers(db, target) for target in spatial_parent_targets
    }
    room_setter_pointer_hits = pointer_array_hits({
        0x5FF7F0, 0x600F30, 0x6010B0, 0x601230, 0x63CA90, 0xA14320, 0xA144B0,
    })
    save_house_single_update = decomp("f95e60")
    if "lVar3 + 0x263e0,param_3" not in save_house_single_update:
        raise AssertionError("SavePlayerHouse update callsite changed")
    insert_callers = hha_callsites["0xa14320"]
    update_callers = hha_callsites["0xa144b0"]
    if len(insert_callers) != 30 or len(update_callers) != 62:
        raise AssertionError({"room_grid_setter_callers": [len(insert_callers), len(update_callers)]})
    if len(hha_callsites["0x63ca90"]) != 1 or hha_callsites["0x63ca90"][0]["owner_va"] != "0x5ff7f0":
        raise AssertionError("0x63ca90 caller inventory changed")
    if [row["owner_va"] for row in indexed_callers(db, 0x5FF7F0)] != [
        "0x600f30", "0x6010b0", "0x601230",
    ]:
        raise AssertionError("0x5ff7f0 direct caller inventory changed")

    # Separate the HHA report queue from the EventFlow SystemMailSend route.
    # The report producer is reached through direct native calls; the action's
    # route-specific insertion is implemented by a virtual slot, so that edge
    # is read from the already validated static route artifact below.
    mail_static = json.loads(MAIL_STATIC.read_text())
    mail_route = mail_static["system_mail_send"]
    if mail_route["registration"]["event_uses"] != 50:
        raise AssertionError("SystemMailSend EventFlow usage count changed")
    hha_mail_direct_targets = (
        0x345890, 0x346A50, 0xAC7070, 0xFAABF0, 0xFAA3F0, 0xFAAEB0,
    )
    hha_to_mail_paths = {
        hx(target): shortest_direct_path(graph, 0x7B1DD0, target)
        for target in hha_mail_direct_targets
    }
    if any(path is not None for path in hha_to_mail_paths.values()):
        raise AssertionError({"unexpected_direct_HHA_to_mail_route": hha_to_mail_paths})
    grade_queue_path = [0x7B1DD0, 0x7B29D0, 0x7B4FC0, 0x7B6470, 0xABF610]
    if any(target not in graph.get(owner, set()) for owner, target in zip(grade_queue_path, grade_queue_path[1:])):
        raise AssertionError("HHA grade report queue call path changed")
    grade_builder_path = [0x7B1DD0, 0x7B29D0, 0x7B4FC0, 0x7B6470, 0xAC77A0]
    if any(target not in graph.get(owner, set()) for owner, target in zip(grade_builder_path, grade_builder_path[1:])):
        raise AssertionError("HHA grade report builder call path changed")
    hha_action_events = [
        dict(row) for row in db.execute(
            "SELECT flow,event_index,name,params_json FROM event_calls "
            "WHERE name='EventFlowActionSystemMailSend' "
            "AND (params_json LIKE '%MAIL_SP_HHA%' OR params_json LIKE '%cHHA%') "
            "ORDER BY flow,event_index"
        )
    ]
    if len(hha_action_events) != 1 or "MAIL_SP_HHA_BuildCelebration" not in hha_action_events[0]["params_json"]:
        raise AssertionError({"unexpected_HHA_SystemMailSend_actions": hha_action_events})

    save_layout = json.loads(SAVE_LAYOUT.read_text())
    crosswalk = json.loads(SAVE_CROSSWALK.read_text())
    house_record = next(row for row in save_layout["members"] if row["node"] == "0x17cd48")
    byte_sample = next(row for row in save_layout["type_census"] if row["sample_node"] == "0x18b058")
    pair_sample = next(row for row in save_layout["type_census"] if row["sample_node"] == "0x18b020")
    crosswalk_by_node = {row["node"]: row for row in crosswalk["member_crosswalk"]}
    crosswalk_by_sample = {row["sample_node"]: row for row in crosswalk["vtable_crosswalk"]}
    if int(byte_sample["sample_data"], 16) - int(house_record["data"], 16) != 0x263D0:
        raise AssertionError("one-byte descriptor no longer lands at SavePlayerHouse +0x263d0")
    if byte_sample["size"] != "0x1" or byte_sample["instances"] != 16:
        raise AssertionError("unexpected one-byte save descriptor census")

    flag_string_refs = [dict(row) for row in db.execute(
        "SELECT string_va,function_va,text FROM string_refs WHERE text=? ORDER BY string_va,function_va",
        ("HHAGradeMailFlag",),
    )]
    if [(row["string_va"], row["function_va"]) for row in flag_string_refs] != [(0x292E423, 0x7B1FE0)]:
        raise AssertionError({"unexpected_flag_string_xrefs": flag_string_refs})
    flag_hash_refs = {}
    for label in ("HHAGradeMailFlag", HHA_FLAG):
        value = zlib.crc32(label.encode("utf-8")) & 0xFFFFFFFF
        refs = [dict(row) for row in db.execute(
            "SELECT hash,pc,owner_va FROM hash_refs WHERE hash=? ORDER BY pc", (value,)
        )]
        flag_hash_refs[label] = {"crc32": hx(value), "refs": refs}
        if refs:
            raise AssertionError({"unexpected_flag_crc_refs": flag_hash_refs[label]})

    native_flags = json.loads(NATIVE_FLAGS.read_text())
    native_flag = native_flags["data"]["flags"][HHA_FLAG]
    indexed_flag = json.loads(FLAG_INDEX.read_text())["data"][HHA_FLAG]
    if native_flag["referencing_functions"] != ["0x7b1fe0"] or native_flag["pseudocode_readings"]:
        raise AssertionError({"native_flag_index_changed": native_flag})
    if indexed_flag["eventflow_readers"] or indexed_flag["eventflow_writers"]:
        raise AssertionError({"eventflow_flag_index_changed": indexed_flag})
    generic_flag_accessors = {
        hx(target): {
            "direct_callsites": indexed_callers(db, target),
            "indexed_code_pointer_array_hits": pointer_array_hits({target}),
        }
        for target in (0xF4AFF0, 0xF4B0D0, 0xF4B170)
    }
    if any(row["target_va"] == "0xf4aff0" for row in generic_flag_accessors["0xf4aff0"]["indexed_code_pointer_array_hits"]):
        raise AssertionError("unexpected flag getter pointer-array entry")

    event_rows = [dict(row) for row in db.execute(
        "SELECT flow,event_index,name,params_json FROM event_calls "
        "WHERE params_json LIKE '%HHAGradeMailFlag%' ORDER BY flow,event_index"
    )]
    player_flag_table = json.loads((DATA / "output/tables_resolved/EventFlagsPlayerParam.json").read_text())
    player_flag_columns = {column["name"]: index for index, column in enumerate(player_flag_table["columns"])}
    hha_flag_row = next(
        row for row in player_flag_table["rows"]
        if row[player_flag_columns["Key"]] == "HHAGradeMailFlag"
    )
    event_handlers = json.loads(EVENT_HANDLERS.read_text())["entries"]
    system_mail_handler = event_handlers["EventFlowSystemActor.EventFlowActionSystemMailSend"]
    direct_mail_handler = event_handlers["EventFlowSystemActor.EventFlowActionSystemMailSendDirect"]
    eventflow_calls = db.execute("SELECT count(*) FROM event_calls").fetchone()[0]
    mail_action_count = db.execute(
        "SELECT count(*) FROM event_calls WHERE name='EventFlowActionSystemMailSend'"
    ).fetchone()[0]
    hha_mail_resource_events = [dict(row) for row in db.execute(
        "SELECT flow,event_index,name,params_json FROM event_calls "
        "WHERE params_json LIKE '%MAIL_SP_HHA%' ORDER BY flow,event_index"
    )]
    grade_named_events = [dict(row) for row in db.execute(
        "SELECT flow,event_index,name,params_json FROM event_calls "
        "WHERE name LIKE '%HHAGrade%' OR params_json LIKE '%HHAGradeMailFlag%' "
        "OR params_json LIKE '%MAIL_SP_HHA_Grade%' ORDER BY flow,event_index"
    )]
    all_hha_event_mentions = [dict(row) for row in db.execute(
        "SELECT flow,event_index,name,params_json FROM event_calls "
        "WHERE name LIKE '%HHA%' OR params_json LIKE '%HHA%' ORDER BY flow,event_index"
    )]
    if eventflow_calls != 24804 or mail_action_count != 50:
        raise AssertionError({"eventflow_index_counts": [eventflow_calls, mail_action_count]})
    if hha_mail_resource_events != hha_action_events or grade_named_events:
        raise AssertionError({"eventflow_HHA_mail_or_grade_inventory": [hha_mail_resource_events, grade_named_events]})

    hash_alias_audit = candidate_hash_audit(db)
    save_byte_offset_inventory = decomp_offset_inventory()
    final_pointer_targets = (
        0xF4AFF0, 0xF4B0D0, 0xF4B170,
        0x7B1DD0, 0x7B1FE0, 0x7B29D0, 0x7B3FF0, 0x7B4FC0, 0x7B6470,
        0xABF610, 0xAC77A0, 0xAC1FF0, 0xAC0A60,
        0x345890, 0x346A50, 0xAC7070, 0xFAABF0, 0xFAA3F0, 0xFAAEB0,
        0x52F220, 0x52F270, 0x52F280, 0x52D980, 0x52E0A0, 0x52E360,
        0x52DF00, 0xA14320, 0xA144B0, 0x63CA90, 0x5FF7F0,
        0x600F30, 0x6010B0, 0x601230, 0xF95610, 0xF949C0, 0xF95BA0,
        0xF95CA0, 0xF95E60, 0xF95C60, 0xF95BF0,
    )
    final_pointer_index = pointer_index_audit(final_pointer_targets)
    accessor_owner_summary = generic_accessor_owner_inventory(db, native_flags)
    HHA_GENERIC_GETTER_OWNERS = {
        owner["owner_va"]
        for owner in accessor_owner_summary["0xf4aff0"]["owners_with_HHA_grade_mail_or_house_named_flag_refs"]
    }
    if HHA_GENERIC_GETTER_OWNERS != {"0x7b4330", "0x7b4fc0", "0x7b5e60"}:
        raise AssertionError({"unexpected_HHA_generic_getter_owners": sorted(HHA_GENERIC_GETTER_OWNERS)})

    result = {
        "schema": "acnh-re/hha-same-anchor-flag-successor/3",
        "scope": "Static follow-up for HHA room-grid same-anchor ordering, HHAGradeMailFlag reader/clearer xrefs, and the boundary between HHA report queuing and EventFlow SystemMailSend. It stops before claiming a particular save object's winner or runtime inbox delivery.",
        "source": {
            "main_nso_sha256": NSO_SHA256,
            "indexed_build_match": True,
            "index_database": str(DB),
        },
        "final_static_successor_audit": {
            "coverage": [
                "exact native string/hash references and candidate text-hash aliases",
                "SavePlayerHouse byte-offset pseudocode references across the full analysis_decomp corpus",
                "all indexed direct generic flag accessor callsites and their named HHA/house flag owners",
                "all indexed EventFlow calls, resolved mail action registration, HHA/grade parameters, and relevant relocated code-pointer targets",
                "direct room-grid insert/update caller inventory and exact indirect pointer hits for known loader/writer candidates",
            ],
            "field_alias_hash_scan": hash_alias_audit,
            "save_byte_offset_pseudocode_scan": save_byte_offset_inventory,
            "event_flag_data_row": {
                "table": "EventFlagsPlayerParam",
                "source_id": player_flag_table["source_id"],
                "row_index": hha_flag_row[2],
                "resolved_row": dict(zip(
                    [column["name"] for column in player_flag_table["columns"]], hha_flag_row
                )),
                "unresolved_column_note": "The per-row bytes 0 and 1 under column hashes 0x5140e4b4 and 0xbed25a86 are table policy fields; matching those hash immediates in native table handlers does not create an alias for the row's Key value HHAGradeMailFlag.",
            },
            "generic_flag_accessor_owner_inventory": {
                "by_accessor": accessor_owner_summary,
                "hha_adjacent_generic_getter_owners": [
                    {
                        "owner_va": "0x7b4330",
                        "named_flag_refs": [
                            "cPlayer:HappyHomeMission1",
                            "cPlayer:HappyHomeMission2",
                            "cPlayer:HappyHomeMission3",
                            "cPlayer:HappyHomeMission4",
                            "cPlayer:HappyHomeMission5",
                            "cPlayer:HappyHomeMission6",
                        ],
                        "meaning": "HHA mission flag checks via the generic getter; no HHAGradeMailFlag reference.",
                    },
                    {
                        "owner_va": "0x7b4fc0",
                        "named_flag_refs": ["cLifeSupportAchievement:GetSRankonHHA", "cPlayer:HappyHomeMission1"],
                        "meaning": "HHA achievement/mission checks via the generic getter; no HHAGradeMailFlag reference.",
                    },
                    {
                        "owner_va": "0x7b5e60",
                        "named_flag_refs": [
                            "cLifeSupportAchievement:GetSRankonHHA",
                            "cPlayer:HappyHomeMission1",
                            "cPlayer:HappyHomeMission2",
                            "cPlayer:HappyHomeMission3",
                            "cPlayer:HappyHomeMission4",
                            "cPlayer:HappyHomeMission5",
                        ],
                        "meaning": "HHA achievement/mission checks via the generic getter; no HHAGradeMailFlag reference.",
                    },
                ],
                "coverage_limit": "The direct caller list is complete for the indexed direct BL/B calls to the three generic accessors. Calls with keys assembled at runtime, unindexed indirect-call mechanisms, or code outside this indexed build remain runtime/coverage limits.",
            },
            "eventflow_and_action_index": {
                "indexed_event_calls": eventflow_calls,
                "system_mail_send_action_uses": mail_action_count,
                "event_calls_mentioning_HHAGradeMailFlag": len(event_rows),
                "event_calls_mentioning_MAIL_SP_HHA_Grade": len(grade_named_events),
                "event_calls_with_any_HHA_text": all_hha_event_mentions,
                "HHA_mail_resource_event_calls": hha_mail_resource_events,
                "grade_HHA_event_calls": grade_named_events,
                "resolved_action_registration": {
                    "SystemMailSend": {
                        "registration_hash": system_mail_handler["registration_hash"],
                        "registration_va": system_mail_handler["registration_va"],
                        "factory": system_mail_handler["factory"],
                        "constructor": system_mail_handler["constructor"],
                        "vtable": system_mail_handler["vtable"],
                        "event_uses": system_mail_handler["event_uses"],
                        "method_slot_target": "0x345890",
                    },
                    "SystemMailSendDirect": {
                        "registration_hash": direct_mail_handler["registration_hash"],
                        "registration_va": direct_mail_handler["registration_va"],
                        "factory": direct_mail_handler["factory"],
                        "constructor": direct_mail_handler["constructor"],
                        "vtable": direct_mail_handler["vtable"],
                        "event_uses": direct_mail_handler["event_uses"],
                    },
                },
                "interpretation": "The full indexed EventFlow call corpus has one HHA SystemMailSend payload: BuildCelebration/cFastTomorrow. It is a house-upgrade event. No indexed action/query names or parameters mention HHAGradeMailFlag or MAIL_SP_HHA_Grade; the HHA grade report remains on the separate native queue/virtual-consumer path already mapped.",
            },
            "indexed_dynamic_pointer_routes": final_pointer_index,
            "room_furniture_load_enumeration": {
                "direct_grid_insert_callsite_count": len(insert_callers),
                "direct_grid_update_callsite_count": len(update_callers),
                "known_grid_setter_or_spatial_loop_pointer_hits": {
                    target: final_pointer_index["target_hits"][target]
                    for target in (
                        "0x52f220", "0x52f270", "0x52f280", "0x52d980", "0x52e0a0",
                        "0x52e360", "0x52df00", "0xa14320", "0xa144b0", "0x63ca90",
                        "0x5ff7f0", "0x600f30", "0x6010b0", "0x601230",
                    )
                },
                "SavePlayerHouse_callback_pointer_hit": final_pointer_index["target_hits"]["0xf95e60"],
                "interpretation": "The complete indexed direct grid-setter caller inventory and exact code-pointer scan find no initial saved-furniture loader function. The one SavePlayerHouse-related callback at 0xf95e60 is a one-value comparison/update/insert route through +0x263e0, not a furniture-list traversal. 0x5ff7f0 processes generated spatial rows only.",
                "remaining_blocker": "The dump/index has no identified constructor/loader symbol or data structure enumeration trace tying a saved furniture list to initial occupancy-grid insertion. Same-anchor winner is therefore last accepted writer, but the stable save enumeration order is not statically proven.",
            },
            "mail_action_pointer_hits": {
                target: final_pointer_index["target_hits"][target]
                for target in ("0x345890", "0x346a50", "0xac7070", "0xfaabf0", "0xfaa3f0", "0xfaaeb0")
            },
            "static_result": "Exhaustive over the available indexed direct-call, string/hash-reference, EventFlow call/action, save-layout, pseudocode-offset, and relocated code-pointer datasets for these exact targets. The indexes show no static HHAGradeMailFlag reader/clearer, grade-to-SystemMailSend route, or initial saved-furniture enumeration path. Dynamic key resolution and runtime ordering remain unproven.",
        },
        "same_anchor": {
            "hha_read_route": ["0x7b1fe0", "0xa13fe0", "0x52f220", "0x52d640"],
            "cell_value": "one signed short; no owner list or all-items enumeration is returned",
            "room_grid_writer_routes": {
                "insert_replace": {
                    "room_context_wrapper": "0xa14320",
                    "wrapper_target": "0x52f270",
                    "implementation": "0x52d980",
                    "anchor_write": "0x52d980 calls 0x52df00 with incoming descriptor at the anchor after validating the incoming descriptor; anchor path does not inspect or compare the prior cell value.",
                    "winner_rule": "Among accepted writes that target the same anchor through this route, the last 0x52df00 assignment wins.",
                },
                "occupied_cell_update": {
                    "room_context_wrapper": "0xa144b0 / 0x63ca90",
                    "wrapper_target": "0x52f280",
                    "implementation": "0x52e0a0 -> 0x52e360 -> 0x52df00",
                    "gate": "Skips a cell whose current value is -2. For a non--2 cell, if 0xf58e20 recognizes the existing descriptor it updates the rectangle; otherwise only -3 enters the alternate-grid fallback, and other values skip.",
                    "winner_rule": "An accepted update also overwrites the target cell, but this is a guarded update path rather than proof of initial room population order.",
                },
            },
            "setter_inventory": hha_callsites,
            "observed_room_update_loop": population_loop,
            "construction_order_audit": {
                "room_update_wrapper": {
                    "target": "0x63ca90",
                    "direct_callers": hha_callsites["0x63ca90"],
                    "callers_of_spatial_loop": indexed_callers(db, 0x5FF7F0),
                    "spatial_loop_callers": spatial_parent_rows,
                    "pointer_array_hits_for_loop_and_setters": room_setter_pointer_hits,
                    "interpretation": "0x5ff7f0 is entered through coordinate/spatial-processing helpers and calls 0x63ca90 for generated 0x38-byte rows. Its ordered row counter establishes ordering for that generated update pass only; the index has no edge from a SavePlayerHouse furniture-list loader to this path.",
                },
                "direct_grid_insert_callers": insert_callers,
                "direct_grid_update_callers": update_callers,
                "save_house_update_callsite": {
                    "function": "0xf95e60",
                    "behavior": "Compares the selected incoming value against one member at +0x18, then calls 0xa144b0 followed by 0xa14320 for that one changed value. It contains no furniture-list traversal.",
                    "pseudocode_verified": True,
                },
                "resolved": "The indexed direct-call inventory covers 30 insert-wrapper callsites and 62 update-wrapper callsites; only 0xf95e60 is visibly tied to the local SavePlayerHouse record, and it updates one selected value. No constructor/loader call chain that enumerates saved room furniture into 0xa14320 was identified. The potential same-anchor winner therefore remains last accepted writer, with initial object ordering unknown.",
                "coverage_limit": "No code-pointer array targets 0x5ff7f0, its three direct callers, 0x63ca90, 0xa14320, or 0xa144b0 in the indexed array scan. This excludes those exact indexed function-pointer routes, not unresolved callbacks or code omitted from the dump/index.",
            },
            "resolved": "The cell is last-accepted-writer-wins on the traced setter paths when their gates pass; the data structure has no intrinsic score/priority comparison at the anchor.",
            "unresolved": "Static evidence does not establish which saved furniture object is inserted last during room initialization. The 0x5ff7f0 loop writes generated spatial rows but is not tied to the initial saved-furniture loader sequence; constructor/loader identity and stable saved-object enumeration order require a matching runtime trace or additional loader data.",
        },
        "saved_byte_descriptor_aliases": {
            "field": "SavePlayerHouse +0x263d0",
            "save_record": {
                "local_node": house_record["node"],
                "local_data": house_record["data"],
                "size": house_record["size"],
                "external_matches": crosswalk_by_node[house_record["node"]]["matches"],
            },
            "one_byte_descriptor": {
                "vtable": byte_sample["vtable"],
                "sample_node": byte_sample["sample_node"],
                "sample_data": byte_sample["sample_data"],
                "sample_offset_in_save_record": "0x263d0",
                "size": byte_sample["size"],
                "instances": byte_sample["instances"],
                "external_match_status": crosswalk_by_sample[byte_sample["sample_node"]]["status"],
                "external_matches": crosswalk_by_sample[byte_sample["sample_node"]]["matches"],
            },
            "overlapping_two_byte_descriptor": {
                "vtable": pair_sample["vtable"],
                "sample_node": pair_sample["sample_node"],
                "sample_data": pair_sample["sample_data"],
                "size": pair_sample["size"],
                "instances": pair_sample["instances"],
                "external_match_status": crosswalk_by_sample[pair_sample["sample_node"]]["status"],
                "external_matches": crosswalk_by_sample[pair_sample["sample_node"]]["matches"],
                "candidate_alias": "SaveLand.PlayerHouseList.HouseList[0].PlayerList[0]",
                "confidence": "Cross-version primitive field-size match only. The local one-byte descriptor itself remains unnamed; this does not prove PlayerList semantics for the byte.",
            },
            "native_uses": {
                "0xf95610": "signed char read at +0x263d0",
                "0xf949c0": "uses signed char at +0x263d0 during house-level update",
                "0xf95ba0": "compares a candidate against signed chars at +0x263d0 and +0x263d1",
                "0xf95ca0": "serializes +0x263d0 and +0x263d1 separately when non--1",
            },
            "semantic_alias_proven": False,
        },
        "grade_flag_accessor_coverage": {
            "key": HHA_FLAG,
            "exact_string_xrefs": [
                {"string_va": hx(row["string_va"]), "function_va": hx(row["function_va"])}
                for row in flag_string_refs
            ],
            "native_flag_index": {
                "referencing_functions": native_flag["referencing_functions"],
                "pseudocode_readings": native_flag["pseudocode_readings"],
            },
            "eventflow_index": {
                "readers": indexed_flag["eventflow_readers"],
                "writers": indexed_flag["eventflow_writers"],
                "actions_mentioning_key": event_rows,
            },
            "generic_flag_accessors": generic_flag_accessors,
            "crc32_xrefs": flag_hash_refs,
            "conclusion": "The exact-name indexed native reference remains only the setter call in 0x7b1fe0. The indexed EventFlow reader/writer lists and action-parameter search are empty, and the checked CRC32 values have no indexed references. Generic native get/set APIs exist and have many unrelated callers; the static corpus does not identify an indirect/dynamic caller that reads or clears this key.",
            "runtime_needed": "Trace generic flag getter/setter calls with their resolved key and value during one HHA evaluation on the matching build; record before/after state for the same player slot.",
        },
        "grade_flag_to_mail_route_audit": {
            "hha_manager_direct_paths": {
                "grade_report_builder_and_queue": {
                    "shortest_path_to_any_HHA_report_builder": shortest_direct_path(graph, 0x7B1DD0, 0xAC77A0),
                    "shortest_path_to_any_HHA_queue_append": shortest_direct_path(graph, 0x7B1DD0, 0xABF610),
                    "rank_report_branch_path_to_builder": [hx(value) for value in grade_builder_path],
                    "rank_report_branch_path_to_queue_append": [hx(value) for value in grade_queue_path],
                },
                "SystemMailSend_or_route_writers": hha_to_mail_paths,
                "interpretation": "HHA evaluation reaches its own report record builder/queue. The indexed direct graph has no path from the evaluator manager to the EventFlow SystemMailSend action/dispatcher, the route virtual insertion method, or the three route-specific save writers. Existing HHA report formatter/consumer evidence is a distinct virtual record path and is not proof that HHAGradeMailFlag triggers SystemMailSend.",
            },
            "flag_reader_clearer_coverage": {
                "exact_native_name_xrefs": len(flag_string_refs),
                "exact_native_functions": native_flag["referencing_functions"],
                "indexed_eventflow_readers": indexed_flag["eventflow_readers"],
                "indexed_eventflow_writers": indexed_flag["eventflow_writers"],
                "actions_mentioning_key": event_rows,
                "checked_crc32_xrefs": {label: len(info["refs"]) for label, info in flag_hash_refs.items()},
                "generic_accessor_direct_callsite_counts": {
                    "getter_0xf4aff0": len(generic_flag_accessors["0xf4aff0"]["direct_callsites"]),
                    "setter_0xf4b0d0": len(generic_flag_accessors["0xf4b0d0"]["direct_callsites"]),
                    "low_level_writer_0xf4b170": len(generic_flag_accessors["0xf4b170"]["direct_callsites"]),
                },
                "conclusion": "The named key is set in the HHA evaluator using the byte read from SavePlayerHouse +0x263d0. The indexed corpus has no reader/clearer, EventFlow action, or direct route from that setter to SystemMailSend/mail-slot serialization. Dynamic generic flag API calls remain possible only if their key is resolved at runtime or the access route is absent from the indexed static corpus.",
            },
            "system_mail_send_queue_when": {
                "static_evidence_artifact": "output/gameplay/house_hha_followup/hha_overlap_mail_dispatch_static.json",
                "eventflow_use_count": mail_route["registration"]["event_uses"],
                "route_counts": mail_route["eventflow_route_counts"],
                "routes": mail_route["record_paths"],
                "HHA_specific_action": hha_action_events,
                "queue_semantics": "When the registered SystemMailSend action executes, it builds/formats a record and dispatches according to Route. cFastToday and cFastTomorrow reach their save-backed slot insertion methods if payload/eligibility checks pass and a free slot is selected. cSlowRetry first attempts the shared record handler and only uses its four-slot fallback if that handler returns false. This describes record insertion at action execution, not inbox delivery or clock/date arrival.",
                "boundary": "The only indexed HHA action is BuildCelebration/cFastTomorrow, a separate house-upgrade event. No indexed grade-HHA action connects HHAGradeMailFlag or the HHA report record queue to SystemMailSend. Static evidence stops at saved collection insertion; inbox visibility and delivery timing are not asserted.",
            },
            "runtime_capture_needed": "On the matching build and same player slot, trace the canonical flag key and get/set values around one HHA pass; record the evaluator result, each HHA report queue record and its virtual consumer target, and the save-mail collection slot before/after. To prove a flag-to-SystemMailSend route, also capture the EventFlow action invocation, route, selected writer and written slot in the same timeline; then separately observe inbox before/after across the relevant clock transition. No such synchronized trace is present.",
        },
        "exact_synchronized_capture_needed": {
            "build": NSO_SHA256,
            "save_scope": "Same SaveLand/player slot and SavePlayerHouse record before and after a single HHA pass; include bytes +0x263d0 and +0x263d1.",
            "room_grid": "Capture room index, constructor/loader function and saved furniture record IDs in enumerated order, plus coordinates; then every write to the selected occupancy grid with writer VA, anchor, incoming short descriptor, prior cell value, and resulting cell value. Capture the value returned by 0xa13fe0 for that same anchor. Repeat a two-item shared-anchor fixture with save/list order reversed while other state is fixed.",
            "same_anchor_fixture": "Two recognized furniture descriptors at one anchor, repeated with insertion order reversed while all other save state is fixed. This isolates whether scene/load ordering or item ownership influences the last accepted write.",
            "flag_and_mail": "In the same timestamped pass, capture resolved HHAGradeMailFlag getter/setter keys and values, raw +0x263d0/+0x263d1 bytes, HHA report queue records, the virtual consumer target and each save-backed mail collection's counts/slots before and after. Record any SystemMailSend action invocation/route/writer in the same timeline. Capture inbox before/after across the applicable clock transition only as a separate delivery observation; separate mail captures cannot prove a flag-to-mail edge.",
            "capture_fields": {
                "identity": ["matching main NSO SHA-256", "save SHA-256", "player slot", "house/room index", "monotonic timestamp", "hook sequence number"],
                "furniture_loader": ["loader function and entry/exit PC", "list count and stride", "saved record index and furniture ID", "room, anchor, orientation", "validation result", "actual enumeration order", "repeat fixture with two same-anchor records reversed in save order"],
                "grid_write": ["wrapper VA", "implementation VA and call PC", "grid/room", "cell coordinates", "incoming signed-short descriptor", "prior/resulting cell value", "existing-object predicate result", "0xa13fe0 resolver result", "preceding-object footprint if anchor was masked"],
                "save_flag": ["SavePlayerHouse address", "raw +0x263d0 and +0x263d1 bytes", "signed-short +0x263e0", "every generic flag API call", "resolved canonical key", "player slot", "old/new value"],
                "hha_report": ["evaluation start/end", "house-level selector", "score and bucket outputs", "report record bytes/ID", "queue address", "virtual consumer target", "save insertion result"],
                "mail_action": ["before/after save-mail slot counts and entries", "EventFlow name/event index/full params", "Route", "validation result", "writer VA", "selected slot", "separate inbox snapshots around the clock transition if delivery is tested"],
            },
            "runtime_status": "No synchronized room-grid/save/flag/mail capture is present in the static corpus; no runtime behavior is claimed.",
        },
    }
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({
        "output": str(OUT),
        "same_anchor_insert_callsites": len(hha_callsites["0x52df00"]),
        "same_anchor_update_callsites": len(hha_callsites["0x52e360"]),
        "generic_getter_callsites": len(generic_flag_accessors["0xf4aff0"]["direct_callsites"]),
        "generic_setter_callsites": len(generic_flag_accessors["0xf4b0d0"]["direct_callsites"]),
        "flag_string_xrefs": len(flag_string_refs),
        "eventflow_flag_actions": len(event_rows),
    }, sort_keys=True))


if __name__ == "__main__":
    main()
