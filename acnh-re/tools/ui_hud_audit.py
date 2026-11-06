#!/usr/bin/env python3
"""Build a UI/HUD inventory, focused native evidence map, and local previews.

The PNG previews are inspection aids, not a claim of Nintendo-renderer parity.
Game source assets are decoded only into the ignored work/ directory.
"""
from collections import Counter
import hashlib
import json
import math
import os
from pathlib import Path
import re
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output" / "ui_hud"
WORK = ROOT / "work" / "ui_hud_preview"
ROMFS = Path(os.environ.get(
    "ACNH_ROMFS", "/workspace/downloads/acnh_additional_romfs_2026-11-02/romfs"))
LAYOUTS_PATH = ROOT / "output" / "ui_island" / "layouts.json"
ANIMATIONS_PATH = ROOT / "output" / "ui_island" / "animations.json"
NATIVE_CANDIDATES_PATH = ROOT / "output" / "ui_island" / "native_candidates.json"

sys.path.insert(0, str(ROOT / "tools" / "reference"))
from acnh_rip.formats import bflyt as bflyt_parser, bntx, byml, sarc  # noqa: E402


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def family(name):
    n = name.lower()
    rules = [
        ("world_hud", lambda: name == "MainScreen"),
        ("world_hud_overlay", lambda: "mainscreen" in n and name != "MainScreen"),
        ("inventory_and_radial", lambda: any(x in n for x in ("pocket", "ringmenu", "itemballoon"))),
        ("phone_apps", lambda: any(x in n for x in ("device", "map", "book", "recipe", "profile", "pointquest"))),
        ("dialog_and_input", lambda: any(x in n for x in ("dialog", "msgwin", "swkbd", "keyguide", "subwin"))),
        ("shop_and_crafting", lambda: any(x in n for x in ("shop", "catalog", "workbench", "closet", "storage"))),
        ("social_and_messages", lambda: any(x in n for x in ("friend", "board", "chat", "card", "letter"))),
        ("system_and_character", lambda: any(x in n for x in ("title", "load", "charamake", "staffcredit", "version"))),
    ]
    for label, test in rules:
        if test():
            return label
    if name.startswith("L"):
        return "reusable_layout_or_overlay_candidate"
    return "other_layout_candidate"


def counts_for(layout):
    counts = Counter(c["type"] for c in layout["components"])
    return dict(sorted(counts.items()))


def audit_part_reference_ambiguities(layout_data):
    """Record duplicate PRT1 candidates and distinguish correlation from proof."""
    layouts_by_member = {(layout["source"], layout["member"]): layout
                         for layout in layout_data["layouts"]}
    references = []
    errors = []
    for host in layout_data["layouts"]:
        host_suffix = Path(host["source"]).suffix
        for pane in host["components"]:
            if pane["type"] != "prt1":
                continue
            candidates = pane.get("part_layout_candidates", [])
            if len(candidates) <= 1:
                continue
            candidate_records = []
            for candidate in candidates:
                layout = layouts_by_member.get((candidate["source"], candidate["member"]))
                if layout is None:
                    errors.append({"host_source": host["source"], "pane": pane["name"],
                                   "candidate": candidate, "error": "candidate_layout_not_found"})
                candidate_records.append({
                    **candidate,
                    "layout_sha256": layout["sha256"] if layout else None,
                    "design_size": layout["components"][0].get("size") if layout else None,
                    "pane_count": len(layout["components"]) if layout else None,
                    "same_archive_suffix_as_host": Path(candidate["source"]).suffix == host_suffix,
                })
            design_sizes = {tuple(x["design_size"]) for x in candidate_records if x["design_size"]}
            references.append({
                "host_layout": host["name"],
                "host_source": host["source"],
                "host_layout_member": host["member"],
                "host_archive_suffix": host_suffix,
                "pane": pane["name"],
                "part_layout_name": pane.get("part_layout"),
                "instance_size": pane.get("size"),
                "candidate_count": len(candidate_records),
                "candidates": candidate_records,
                "same_suffix_candidate_count": sum(x["same_archive_suffix_as_host"] for x in candidate_records),
                "candidate_design_sizes": [list(x) for x in sorted(design_sizes)],
                "candidate_design_size_discriminates": len(design_sizes) > 1,
                "status": "unresolved_loader_precedence",
                "interpretation": "Matching the host archive suffix is a consistent selection heuristic, not proof of the game's runtime resource lookup order.",
            })
    suffix_counts = Counter(Path(x["host_source"]).suffix for x in references)
    return {
        "schema": "acnh.ui_part_reference_ambiguities.v1",
        "evidence": "Each PRT1 reference is joined to same-name BFLYT candidates in the local Layout archive inventory. Candidate hashes and source suffixes are preserved; matching parent/child suffix is reported only as a correlation.",
        "counts": {
            "ambiguous_references": len(references),
            "unique_part_layout_names": len({x["part_layout_name"] for x in references}),
            "host_archive_suffix_counts": dict(sorted(suffix_counts.items())),
            "references_with_same_suffix_candidate": sum(x["same_suffix_candidate_count"] > 0 for x in references),
            "references_with_exactly_one_same_suffix_candidate": sum(x["same_suffix_candidate_count"] == 1 for x in references),
            "references_with_discriminating_candidate_design_size": sum(x["candidate_design_size_discriminates"] for x in references),
            "unresolved_references": sum(x["status"] == "unresolved_loader_precedence" for x in references),
            "parse_errors": len(errors),
        },
        "selection_rule_status": "unproven",
        "parse_errors": errors,
        "references": references,
    }


def build_group_structure(layout_data):
    """Associate BFLYT grs1/gre1 delimiters with the grp1 records they bracket."""
    records, errors = [], []
    marker_sizes = Counter()
    block_sizes = Counter()
    enclosed_kinds = Counter()
    group_count_total = 0
    delimited_group_count = 0
    for layout in layout_data["layouts"]:
        sections = layout["sections"]
        groups = layout["groups"]
        group_index = 0
        open_block = None
        blocks = []
        group_sections = [s for s in sections if s["kind"] == "grp1"]
        if len(group_sections) != len(groups):
            errors.append({"source": layout["source"], "member": layout["member"],
                           "error": "grp1_section_and_decoded_group_count_mismatch",
                           "section_count": len(group_sections), "group_count": len(groups)})
        for section_index, section in enumerate(sections):
            kind = section["kind"]
            if kind in ("grs1", "gre1"):
                marker_sizes[(kind, section["size"])] += 1
            if kind == "grs1":
                if open_block is not None:
                    errors.append({"source": layout["source"], "member": layout["member"],
                                   "section_offset": section.get("offset"), "error": "nested_group_start"})
                else:
                    open_block = {"start_section_index": section_index,
                                  "start_section_offset": section.get("offset"),
                                  "start_group_index": group_index,
                                  "body_section_kinds": Counter()}
            elif kind == "grp1":
                group_index += 1
                if open_block is not None:
                    open_block["body_section_kinds"][kind] += 1
            elif kind == "gre1":
                if open_block is None:
                    errors.append({"source": layout["source"], "member": layout["member"],
                                   "section_offset": section.get("offset"), "error": "group_end_without_start"})
                else:
                    start_group = open_block["start_group_index"]
                    group_names = [g.get("name", "") for g in groups[start_group:group_index]]
                    kinds = dict(sorted(open_block["body_section_kinds"].items()))
                    enclosed_kinds.update(kinds)
                    block_sizes[group_index - start_group] += 1
                    delimited_group_count += group_index - start_group
                    blocks.append({
                        "start_section_offset": open_block["start_section_offset"],
                        "end_section_offset": section.get("offset"),
                        "start_group_index": start_group,
                        "end_group_index_exclusive": group_index,
                        "group_names": group_names,
                        "enclosed_group_count": group_index - start_group,
                        "body_section_kinds": kinds,
                        "start_marker_size": sections[open_block["start_section_index"]]["size"],
                        "end_marker_size": section["size"],
                    })
                    open_block = None
        if open_block is not None:
            errors.append({"source": layout["source"], "member": layout["member"],
                           "section_offset": open_block["start_section_offset"], "error": "group_start_without_end"})
        if group_index != len(groups):
            errors.append({"source": layout["source"], "member": layout["member"],
                           "error": "grp1_cursor_and_group_count_mismatch",
                           "section_count": group_index, "group_count": len(groups)})
        enclosed_indices = {i for block in blocks
                            for i in range(block["start_group_index"], block["end_group_index_exclusive"])}
        outside_indices = [i for i in range(len(groups)) if i not in enclosed_indices]
        group_count_total += len(groups)
        records.append({
            "layout": layout["name"], "source": layout["source"], "member": layout["member"],
            "layout_sha256": layout["sha256"], "group_count": len(groups),
            "groups_outside_delimiters": [{"group_index": i, **groups[i]} for i in outside_indices],
            "delimited_group_blocks": blocks,
        })
    return {
        "schema": "acnh.ui_bflyt_group_structure.v1",
        "evidence": "Public BFLYT section enums identify grs1/gre1 as GroupStart/GroupEnd. Local section order shows the paired markers bracket only grp1 records; this records the structural ranges without assuming runtime visibility or animation behavior.",
        "format_reference": "https://github.com/crackheadakira/nnbfl/blob/af30eaf9a92324bfe7ecc2af8df9c8dbf8848a79/hexpats/bflyt_bflan_bffnt.900.hexpat",
        "counts": {
            "layouts": len(records),
            "grp1_sections": group_count_total,
            "delimited_group_blocks": sum(block_sizes.values()),
            "groups_inside_delimiters": delimited_group_count,
            "groups_outside_delimiters": group_count_total - delimited_group_count,
            "layouts_with_group_delimiters": sum(bool(x["delimited_group_blocks"]) for x in records),
            "layouts_without_group_delimiters": sum(not x["delimited_group_blocks"] for x in records),
            "group_block_size_histogram": {str(k): v for k, v in sorted(block_sizes.items())},
            "marker_section_size_counts": {f"{kind}:{size}": count for (kind, size), count in sorted(marker_sizes.items())},
            "enclosed_section_kinds": dict(sorted(enclosed_kinds.items())),
            "parse_errors": len(errors),
        },
        "parse_errors": errors,
        "layouts": records,
    }


def build_catalog(layout_data, animation_data, native_data):
    anims_by_source = {}
    for anim in animation_data["animations"]:
        anims_by_source.setdefault(anim["source"], []).append(anim)
    native_by_name = {x["layout_name"]: x["string_ref_candidates"]
                      for x in native_data["layouts"]}
    records = []
    for layout in layout_data["layouts"]:
        records.append({
            "name": layout["name"],
            "family_candidate": family(layout["name"]),
            "source": layout["source"],
            "member": layout["member"],
            "sha256": layout["sha256"],
            "design_size": layout["components"][0].get("size"),
            "pane_count": len(layout["components"]),
            "pane_type_counts": counts_for(layout),
            "material_count": len(layout["materials"]),
            "texture_count": len(layout["textures"]),
            "font_count": len(layout["fonts"]),
            "part_refs": [{
                "pane": c["name"], "layout": c.get("part_layout"),
                "translate": c.get("translate"), "size": c.get("size"),
                "candidates": c.get("part_layout_candidates", []),
            } for c in layout["components"] if c["type"] == "prt1"],
            "animations": [{
                "member": a["member"], "tag": a.get("tag", {}).get("name"),
                "frame_count": a.get("frames"), "loop_byte": a.get("loop_byte"),
                "track_count": a.get("track_count"), "key_count": a.get("key_count"),
            } for a in anims_by_source.get(layout["source"], [])],
            "exact_native_string_ref_candidates": native_by_name.get(layout["name"], []),
        })
    return records


def audit_layout_archive_inventory(layout_data):
    """Reconcile compressed files in Layout/ with parsed BFLYT records."""
    archive_dir = ROMFS / "Layout"
    archives = sorted([*archive_dir.glob("*.zs"), *archive_dir.glob("*.szs")])
    parsed_sources = {Path(layout["source"]).name for layout in layout_data["layouts"]}
    records = []
    for path in archives:
        outer = sarc.read_sarc(decompress_layout_archive(path))
        bflyt_members = []
        for name, blob in outer.items():
            if name.lower().endswith(".arc"):
                inner = sarc.read_sarc(blob)
                bflyt_members.extend(f"{name}!{member}" for member in inner
                                     if member.lower().endswith(".bflyt"))
        records.append({"archive": path.name, "bflyt_member_count": len(bflyt_members),
                        "bflyt_members": bflyt_members,
                        "non_layout_member_names": list(outer.keys()) if not bflyt_members else []})
    archives_with_layouts = {r["archive"] for r in records if r["bflyt_member_count"]}
    return {
        "archive_count": len(archives),
        "parsed_layout_record_count": len(layout_data["layouts"]),
        "distinct_parsed_source_archive_count": len(parsed_sources),
        "archives_with_bflyt_count": len(archives_with_layouts),
        "total_bflyt_members": sum(r["bflyt_member_count"] for r in records),
        "archives_without_bflyt": [r for r in records if not r["bflyt_member_count"]],
        "unmatched_archives": sorted(set(path.name for path in archives) - parsed_sources),
        "parsed_sources_missing_from_directory": sorted(parsed_sources - set(path.name for path in archives)),
        "records": records,
    }


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _font_face_names(data):
    # The FCPX strings end in .bfttf or .bfotf; the suffix regex is explicit to
    # avoid treating arbitrary binary fragments as font names.
    names = [m.group().decode("ascii") for m in re.finditer(rb"[A-Za-z0-9_.-]{1,}\.(?:bfttf|bfotf)", data)]
    return list(dict.fromkeys(names))


def build_font_bindings(layout_data):
    """Join BFLYT fnl1 aliases to FontInfo and actual Font archive members."""
    info_archive = sarc.read_sarc(decompress_layout_archive(ROMFS / "Font" / "FontInfo.sarc.zs"))
    info = byml.read_byml(info_archive["FontInfo.byml"])["root"]
    instances = info["Instance"]
    resource_types = info.get("Resource", {})
    font_faces = info.get("FontFace", {})

    fcpx_archive = sarc.read_sarc(decompress_layout_archive(ROMFS / "Font" / "Fcpx.sarc.zs"))
    fcpx_assets = {}
    for name, data in fcpx_archive.items():
        if not name.lower().endswith(".bfcpx"):
            continue
        fcpx_assets[name] = {
            "source": "Font/Fcpx.sarc.zs", "member": name, "sha256": _sha(data),
            "bytes": len(data), "fallback_faces": _font_face_names(data),
        }

    bitmap_assets = {}
    for archive in sorted((ROMFS / "Font").glob("BmpFont_*.sarc.zs")):
        for name, data in sarc.read_sarc(decompress_layout_archive(archive)).items():
            if not name.lower().endswith(".bffnt"):
                continue
            bitmap_assets.setdefault(name, []).append({
                "source": str(archive.relative_to(ROMFS)), "member": name,
                "sha256": _sha(data), "bytes": len(data),
            })

    referenced_aliases = sorted({Path(name).stem for layout in layout_data["layouts"] for name in layout["fonts"]})
    bindings = []
    for alias in referenced_aliases:
        instance = instances.get(alias)
        if instance is None:
            bindings.append({"alias": alias, "status": "missing_from_FontInfo.Instance"})
            continue
        if instance.get("fcpx"):
            related_aliases = sorted(name for name, value in instances.items()
                                     if value.get("fcpx") and (name == alias or name.startswith(alias + "_")))
            assets = [fcpx_assets[name + ".bfcpx"] for name in related_aliases if name + ".bfcpx" in fcpx_assets]
            bindings.append({
                "alias": alias, "binding_kind": "scalable_FCPX",
                "FontInfo_Instance": instance, "locale_aliases": related_aliases,
                "resource_assets": assets,
                "locale_selection": "The BFLYT alias resolves to this family; which locale-suffixed member the runtime selects is not proven.",
            })
        elif "Res" in instance:
            resource_name = instance["Res"]
            member = resource_name + ".bffnt"
            bindings.append({
                "alias": alias, "binding_kind": "bitmap_BFFNT",
                "FontInfo_Instance": instance,
                "FontInfo_Resource": resource_types.get(resource_name),
                "resource_assets": bitmap_assets.get(member, []),
                "locale_selection": "All regional archive copies are retained; identical hashes indicate equivalent source bytes.",
            })
        else:
            bindings.append({"alias": alias, "FontInfo_Instance": instance, "status": "unclassified_Instance_record"})

    by_alias = {x["alias"]: x for x in bindings}
    references = []
    for layout in layout_data["layouts"]:
        for index, name in enumerate(layout["fonts"]):
            alias = Path(name).stem
            references.append({"layout": layout["name"], "source": layout["source"],
                               "font_index": index, "BFLYT_font_name": name,
                               "binding_alias": alias, "binding_status": by_alias.get(alias, {}).get("binding_kind", "unresolved")})

    return {
        "schema": "acnh.ui_font_bindings.v1",
        "evidence": "All BFLYT fnl1 aliases are cross-referenced against FontInfo.byml and Font/*.sarc.zs members; scalable aliases are resolved to FCPX configuration and embedded fallback-face names.",
        "FontInfo_source": "Font/FontInfo.sarc.zs!FontInfo.byml",
        "counts": {"layout_font_references": len(references), "unique_aliases": len(bindings),
                   "resolved_references": sum(x["binding_status"] != "unresolved" for x in references),
                   "binding_kind_counts": dict(Counter(x.get("binding_kind", "unresolved") for x in bindings))},
        "font_face_records": font_faces,
        "bindings": bindings,
        "references": references,
        "remaining_limits": ["Runtime choice among locale-suffixed FCPX variants requires language/resource-loader confirmation.",
                             "Scalable BFTTF/BFOTF face assets are external font-family references in FCPX; BFLYT font mapping does not prove exact glyph fallback at runtime."],
    }


def _rgba_at(data, offset):
    return list(data[offset:offset + 4])


def _parse_layout_materials(layout_bytes):
    sections = _section_list(layout_bytes)
    raw_version = struct.unpack_from("<I", layout_bytes, 8)[0]
    major = (raw_version >> 24) & 0xFF
    mat_section = next((s for s in sections if s["kind"] == "mat1"), None)
    if mat_section is None:
        return []
    s = layout_bytes[mat_section["offset"]:mat_section["offset"] + mat_section["size"]]
    count = struct.unpack_from("<H", s, 8)[0]
    offsets = [struct.unpack_from("<I", s, 12 + i * 4)[0] for i in range(count)]
    if any(x < 12 + count * 4 or x >= len(s) for x in offsets):
        raise ValueError("mat1 contains an invalid material offset")
    results = []
    for i, start in enumerate(offsets):
        end = offsets[i + 1] if i + 1 < len(offsets) else len(s)
        if end < start or start + 44 > end:
            raise ValueError(f"mat1 material {i} header is truncated")
        name = s[start:start + 28].split(b"\0", 1)[0].decode("utf-8", "replace")
        cursor = start + 28
        if major >= 8:
            flags, unknown = struct.unpack_from("<Ii", s, cursor)
            cursor += 8
            black, white = _rgba_at(s, cursor), _rgba_at(s, cursor + 4)
            cursor += 8
        else:
            black, white = _rgba_at(s, cursor), _rgba_at(s, cursor + 4)
            flags = struct.unpack_from("<I", s, cursor + 8)[0]
            unknown = 0
            cursor += 12
        tex_count = (flags >> 0) & 0x3
        matrix_count = (flags >> 2) & 0x3
        texgen_count = (flags >> 4) & 0x3
        tev_count = (flags >> 6) & 0x7
        proj_count = (flags >> 15) & 0x3
        indirect_count = (flags >> 14) & 0x1
        vector_texture_count = (flags >> 22) & 0x3
        brick_repeat_count = (flags >> 24) & 0x3

        def take(size):
            nonlocal cursor
            if cursor + size > end:
                raise ValueError(f"mat1 material {i} fields exceed its section boundary")
            at = cursor
            cursor += size
            return at

        texture_maps = []
        for j in range(tex_count):
            at = take(4)
            texture_index, options_u, options_v = struct.unpack_from("<hBB", s, at)

            def texture_options(value):
                wrap_id, filter_id = value & 0x3, (value >> 2) & 0x3
                return {"raw": value, "wrap_mode_id": wrap_id,
                        "wrap_mode": {0: "Clamp", 1: "Repeat", 2: "Mirror"}.get(wrap_id, "unknown"),
                        "filter_id": filter_id,
                        "filter": {0: "Near", 1: "Linear"}.get(filter_id, "unknown"),
                        "reserved_high_nibble": (value >> 4) & 0xf}

            texture_maps.append({"texture_index": texture_index,
                                 "u_options": texture_options(options_u),
                                 "v_options": texture_options(options_v)})
        texture_extensions = []
        if flags & (1 << 21):
            for _ in range(tex_count):
                at = take(4)
                raw = struct.unpack_from("<I", s, at)[0]
                texture_extensions.append({"raw": raw, "is_capture_texture": bool(raw & 1),
                                           "is_vector_texture": bool(raw & 2),
                                           "reserved_bits": raw & ~0x3})
        transforms = []
        for _ in range(matrix_count):
            at = take(20)
            transforms.append(list(struct.unpack_from("<5f", s, at)))
        texcoord_gens = []
        for _ in range(texgen_count):
            at = take(16 if major >= 8 else 8)
            texgen_type = s[at + 1]
            texgen_gens = {0: "Tex0", 1: "Tex1", 2: "Tex2", 3: "OrthogonalProjection",
                           4: "PaneBasedProjection", 5: "PerspectiveProjection",
                           6: "PaneBasedPerspectiveProjection", 7: "BrickRepeat"}
            texcoord_gens.append({"reserved0": s[at], "texgen_type_id": texgen_type,
                                  "texgen_type": texgen_gens.get(texgen_type, "unknown"),
                                  "reserved_bytes": list(s[at + 2:cursor])})
        tev_stages = []
        for _ in range(tev_count):
            at = take(4)
            stage = s[at]
            tev_stages.append({"stage_id": stage,
                               "stage": {0: "Replace", 1: "Modulate", 2: "Add", 3: "AddSigned",
                                         4: "Interpolate", 5: "Subtract", 6: "AddMultiply",
                                         7: "MultiplyAdd", 8: "Overlay", 9: "Lighten", 10: "Darken",
                                         11: "Indirect", 12: "BlendIndirect", 13: "EachIndirect"}.get(stage, "unknown"),
                               "reserved_bytes": list(s[at + 1:at + 4])})
        alpha_compare = None
        if flags & (1 << 9):
            at = take(8)
            mode = s[at]
            alpha_compare = {"function_id": mode,
                             "function": {0: "Never", 1: "LessThan", 2: "LessThanEqual", 3: "Equal",
                                          4: "NotEqual", 5: "GreaterEqual", 6: "Greater", 7: "Always"}.get(mode, "unknown"),
                             "padding": list(s[at + 1:at + 4]),
                             "reference_value": struct.unpack_from("<f", s, at + 4)[0]}
        blend_count = 2 if flags & (1 << 12) else int(bool(flags & (1 << 10)))
        blend_modes = []
        for _ in range(blend_count):
            at = take(4)
            equation, source, destination, logic = s[at:at + 4]
            blend_modes.append({"equation_id": equation, "source_factor_id": source,
                                "destination_factor_id": destination, "logic_op_id": logic,
                                "raw_bytes": list(s[at:at + 4])})
        reserved_blend_related = []
        if flags & (1 << 13):
            for _ in range(3):
                at = take(4)
                reserved_blend_related.append(struct.unpack_from("<I", s, at)[0])
        indirect = None
        if indirect_count:
            indirect = []
            for _ in range(indirect_count):
                at = take(12)
                indirect.append({"translation": list(struct.unpack_from("<2f", s, at)),
                                 "rotation": struct.unpack_from("<f", s, at + 8)[0]})
        projection = []
        for _ in range(proj_count):
            at = take(20)
            projection.append({"values": list(struct.unpack_from("<4f", s, at)), "flags": s[at + 16],
                               "padding": list(s[at + 17:at + 20])})
        font_shadow = None
        if flags & (1 << 17):
            at = take(8)
            font_shadow = {"black": _rgba_at(s, at), "white": _rgba_at(s, at + 4)}
        detailed_combiner = None
        if flags & (1 << 19):
            at = take(28)
            detailed_combiner = {"value_raw": struct.unpack_from("<I", s, at)[0],
                                 "colors": [_rgba_at(s, at + 4 + i * 4) for i in range(5)],
                                 "stage_flags_raw": struct.unpack_from("<I", s, at + 24)[0]}
            detailed_combiner["stage_entries_raw"] = []
            for _ in range(tev_count):
                entry_at = take(16)
                detailed_combiner["stage_entries_raw"].append(list(s[entry_at:entry_at + 16]))
        user_combiners = []
        user_combiner_count = (flags >> 20) & 1
        for _ in range(user_combiner_count):
            at = take(0x74)
            name = s[at:at + 0x60].split(b"\0", 1)[0].decode("utf-8", "replace")
            reserves = list(struct.unpack_from("<5I", s, at + 0x60))
            user_combiners.append({"shader_name": name, "reserve_words": reserves,
                                   "raw_sha256": _sha(s[at:at + 0x74])})
        vector_texture_info = []
        for _ in range(vector_texture_count):
            at = take(16)
            vector_texture_info.append({"flags_raw": struct.unpack_from("<I", s, at)[0],
                                        "color_rgba": _rgba_at(s, at + 4),
                                        "reserve_u64": struct.unpack_from("<Q", s, at + 8)[0]})
        brick_repeat_info = []
        for _ in range(brick_repeat_count):
            at = take(0x16 * 4)
            brick_repeat_info.append({"raw_words": list(struct.unpack_from("<22I", s, at))})
        trailing = s[cursor:end]
        known_flag_mask = ((1 << 26) - 1) & ~(1 << 13)
        results.append({
            "index": i, "name": name, "flags_raw": flags, "unknown_i32": unknown,
            "unknown_flag_bits": flags & ~known_flag_mask,
            "black_rgba": black, "white_rgba": white,
            "texture_maps": texture_maps, "texture_extensions": texture_extensions,
            "texture_transforms": transforms,
            "texcoord_gens": texcoord_gens, "tev_stages_raw": tev_stages,
            "alpha_compare": alpha_compare, "blend_modes_raw": blend_modes,
            "blend_mode_raw": blend_modes[0] if blend_modes else None,
            "separate_alpha_blend_mode_raw": blend_modes[1] if len(blend_modes) > 1 else None,
            "reserved_blend_related_words": reserved_blend_related,
            "indirect_parameters": indirect,
            "projection_texgen_parameters": projection, "font_shadow_colors": font_shadow,
            "detailed_combiner": detailed_combiner, "user_combiners": user_combiners,
            "vector_texture_info": vector_texture_info, "brick_repeat_shader_info": brick_repeat_info,
            "use_texture_only_flag": bool(flags & (1 << 11)),
            "alpha_interpolation_flag": bool(flags & (1 << 18)),
            "trailing_uninterpreted_bytes": len(trailing), "trailing_sha256": _sha(trailing),
            "trailing_prefix_hex": trailing[:24].hex(),
            "trailing_embedded_ascii": list(dict.fromkeys(
                m.group().decode("ascii") for m in re.finditer(rb"[\x20-\x7e]{3,}", trailing))),
        })
    return results


def build_resource_bindings(layout_data):
    """Decode all material fields and join BFLYT maps to BNTX texture metadata."""
    layouts_by_source_member = {(Path(x["source"]).name, x["member"]): x for x in layout_data["layouts"]}
    raw_layouts, textures_by_archive, glsl_by_archive, compiled_shaders_by_archive, errors = {}, {}, {}, {}, []
    for archive in sorted([*(ROMFS / "Layout").glob("*.zs"), *(ROMFS / "Layout").glob("*.szs")]):
        try:
            outer = sarc.read_sarc(decompress_layout_archive(archive))
            for arc_name, arc_blob in outer.items():
                if not arc_name.lower().endswith(".arc"):
                    continue
                inner = sarc.read_sarc(arc_blob)
                for member, data in inner.items():
                    if member.lower().endswith(".bflyt"):
                        raw_layouts[(archive.name, f"{arc_name}!{member}")] = data
                    elif member.lower().endswith(".bntx"):
                        for t in bntx.read_bntx(data):
                            textures_by_archive.setdefault(archive.name, []).append(t)
                    elif member.lower().endswith(".glsl"):
                        glsl_by_archive.setdefault(archive.name, []).append({
                            "shader_name": Path(member).stem,
                            "member": f"{arc_name}!{member}",
                            "sha256": _sha(data), "bytes": len(data),
                        })
                    elif member.lower().endswith((".bnsh", ".bushvt")):
                        compiled_shaders_by_archive.setdefault(archive.name, []).append({
                            "member": f"{arc_name}!{member}",
                            "sha256": _sha(data), "bytes": len(data),
                            "magic_hex": data[:8].hex(),
                        })
        except Exception as exc:
            errors.append({"archive": archive.name, "error": str(exc)})

    layout_results = []
    totals = Counter()
    unknown_flag_masks = Counter()
    unknown_i32_values = Counter()
    trailing_lengths = Counter()
    trailing_hashes = Counter()
    for (source_name, member), layout in sorted(layouts_by_source_member.items()):
        raw = raw_layouts.get((source_name, member))
        if raw is None:
            errors.append({"archive": source_name, "layout_member": member, "error": "raw BFLYT member not found"})
            continue
        try:
            materials = _parse_layout_materials(raw)
        except Exception as exc:
            errors.append({"archive": source_name, "layout_member": member, "error": f"mat1: {exc}"})
            continue
        textures = textures_by_archive.get(source_name, [])
        texture_names = layout["textures"]
        tex_bindings = []
        for index, name in enumerate(texture_names):
            candidates = [t for t in textures if t["name"] == name]
            tex_bindings.append({"texture_index": index, "BFLYT_name": name,
                                 "match_status": "unique_same_archive" if len(candidates) == 1 else "same_archive_candidates" if candidates else "no_same_archive_texture_name",
                                 "BNTX_candidates": [{k: t[k] for k in ("name", "format", "format_name", "width", "height", "depth", "array_count", "mip_count", "block_height_log2", "channel_sources", "dim", "mip0_size", "image_size")} for t in candidates]})
        for material in materials:
            bound = []
            for map_entry in material["texture_maps"]:
                ti = map_entry["texture_index"]
                name = texture_names[ti] if 0 <= ti < len(texture_names) else None
                candidates = [t for t in textures if name is not None and t["name"] == name]
                bound.append({**map_entry, "texture_name": name,
                              "BNTX_candidates": [{k: t[k] for k in ("format_name", "width", "height", "mip_count", "channel_sources")} for t in candidates]})
                totals["material_texture_map_refs"] += 1
                totals["material_texture_map_refs_with_bntx_candidate"] += bool(candidates)
            material["texture_bindings"] = bound
            shader_names = [x["shader_name"] for x in material["user_combiners"] if x["shader_name"]]
            shader_name = shader_names[0] if len(shader_names) == 1 else None
            shader_candidates = [x for x in glsl_by_archive.get(source_name, [])
                                 if x["shader_name"] == shader_name] if shader_name else []
            material["shader_name_candidate"] = shader_name
            material["shader_glsl_binding_status"] = (
                "unique_same_archive" if len(shader_candidates) == 1 else
                "ambiguous_same_archive" if shader_candidates else
                "no_named_glsl_reference" if shader_name is None else "no_same_archive_glsl")
            material["shader_glsl_candidates"] = shader_candidates
            totals["materials"] += 1
            totals["material_trailing_bytes"] += material["trailing_uninterpreted_bytes"]
            totals["materials_with_user_combiner"] += len(material["user_combiners"])
            totals["material_named_shader_refs"] += bool(shader_name)
            totals["material_named_shader_refs_with_unique_glsl"] += len(shader_candidates) == 1
            if material["unknown_flag_bits"]:
                unknown_flag_masks[material["unknown_flag_bits"]] += 1
            unknown_i32_values[material["unknown_i32"]] += 1
            trailing_lengths[material["trailing_uninterpreted_bytes"]] += 1
            if material["trailing_uninterpreted_bytes"]:
                trailing_hashes[material["trailing_sha256"]] += 1
        pane_material_refs = [{"pane": c["name"], "pane_type": c["type"], "material_index": c["material"],
                               "material_name": materials[c["material"]]["name"] if 0 <= c["material"] < len(materials) else None}
                              for c in layout["components"] if "material" in c]
        layout_results.append({"layout": layout["name"], "source": layout["source"], "member": member,
                               "layout_sha256": layout["sha256"], "texture_bindings": tex_bindings,
                               "shader_resources": {"glsl_sources": glsl_by_archive.get(source_name, []),
                                                     "compiled_shader_candidates": compiled_shaders_by_archive.get(source_name, [])},
                               "materials": materials, "pane_material_references": pane_material_refs})
        totals["layouts"] += 1
        totals["texture_list_entries"] += len(tex_bindings)
        totals["texture_list_entries_with_unique_bntx"] += sum(x["match_status"] == "unique_same_archive" for x in tex_bindings)
        totals["pane_material_refs"] += len(pane_material_refs)
    return {
        "schema": "acnh.ui_resource_bindings.v1",
        "evidence": "Every material record is decoded from BFLYT mat1 flags/count fields and its variable blocks; BFLYT texture names are joined to BNTX metadata from the same Layout archive. A name in a 116-byte material extension is cross-referenced to same-archive GLSL source files. Uninterpreted material tail bytes and unknown flag bits are preserved as hashes/raw values.",
        "counts": {**dict(totals),
                    "materials_with_unknown_flag_bits": sum(unknown_flag_masks.values()),
                    "unknown_material_flag_masks": dict(unknown_flag_masks),
                    "unknown_i32_value_count": len(unknown_i32_values),
                    "unknown_i32_values": {hex(value & 0xffffffff): count
                                           for value, count in sorted(unknown_i32_values.items())},
                    "material_trailing_byte_length_counts": dict(trailing_lengths),
                    "nonempty_material_tail_unique_hashes": len(trailing_hashes)},
        "material_flag_legend": {"0-1": "texture map count", "2-3": "texture SRT count", "4-5": "texcoord generator count", "6-8": "TEV combiner count", "9": "alpha compare present", "10": "single color blend present", "11": "use texture only", "12": "separate color and alpha blend blocks present", "13": "reserved extension (no instances in this dump)", "14": "indirect matrix count", "15-16": "projection texcoord count", "17": "font shadow colors present", "18": "alpha interpolation flag", "19": "detailed combiner count", "20": "user combiner count (shader name record)", "21": "texture extensions present", "22-23": "vector texture info count", "24-25": "brick-repeat shader info count", "26-31": "reserved"},
        "texture_flag_note": "Texture map flag bytes are preserved raw; their wrap/filter bit subfields are not relabeled as proven here.",
        "layouts": layout_results,
        "parse_errors": errors,
        "remaining_limits": ["A 0x74-byte user-combiner record now decodes to a GLSL name and five preserved words; compiled BNSH variation selection and exact renderer draw/pass remain unresolved.",
                             "Material blocks and common enum IDs are mapped from the format schema; renderer-specific interpretation and output parity still require cross-check.",
                             "A BNTX name match proves a resource binding candidate in the same archive; it does not identify the exact runtime draw state."],
    }


def _section_list(data):
    if data[:4] != b"FLYT" or data[4:6] != b"\xff\xfe":
        raise ValueError("unsupported BFLYT header")
    offset = struct.unpack_from("<H", data, 6)[0]
    count = struct.unpack_from("<H", data, 16)[0]
    result = []
    for _ in range(count):
        size = struct.unpack_from("<I", data, offset + 4)[0]
        if size < 8 or offset + size > len(data):
            raise ValueError(f"invalid BFLYT section at 0x{offset:x}")
        result.append({"offset": offset, "kind": data[offset:offset + 4].decode("ascii"),
                       "size": size, "payload": data[offset + 8:offset + size]})
        offset += size
    if offset != len(data):
        raise ValueError("BFLYT section lengths do not match file size")
    return result


def _parse_ui2dsys(raw, scope):
    if len(raw) < 8:
        raise ValueError("ui2dsys array header truncated")
    reserved, count, offset = struct.unpack_from("<HHI", raw, 0)
    if count == 0 or offset < 8 or offset >= len(raw):
        raise ValueError("ui2dsys array count/offset invalid")
    section_size = struct.unpack_from("<I", raw, 8)[0] if count > 1 and len(raw) >= 12 else None
    records = []
    cursor = offset
    for index in range(count):
        if cursor + 4 > len(raw):
            raise ValueError("ui2dsys record header truncated")
        system_type = struct.unpack_from("<I", raw, cursor)[0]
        record = {"index": index, "type_id": system_type}
        if scope == "layout" and system_type == 0:
            if cursor + 8 > len(raw):
                raise ValueError("ui2dsys AnimTagName header truncated")
            name_count = struct.unpack_from("<I", raw, cursor + 4)[0]
            table_end = cursor + 8 + name_count * 4
            if table_end > len(raw):
                raise ValueError("ui2dsys AnimTagName offset table exceeds data")
            offsets = struct.unpack_from("<" + "I" * name_count, raw, cursor + 8) if name_count else []
            names = []
            for relative in offsets:
                at = cursor + relative
                stop = raw.find(b"\0", at)
                if relative < 8 + name_count * 4 or at >= len(raw) or stop < 0:
                    raise ValueError("ui2dsys AnimTagName string offset invalid")
                names.append(raw[at:stop].decode("utf-8", "replace"))
            record.update({"semantic_type": "AnimTagName", "animation_tag_names": names,
                           "payload_bytes": len(raw) - cursor})
            cursor = len(raw)
        elif scope == "pane" and system_type == 6:
            # ProceduralShape uses an 8-bit flag byte followed by seven option bytes.
            # The shipped layouts validate the record as 252 bytes including its type.
            expected_size = 0xfc
            if cursor + expected_size > len(raw):
                raise ValueError("ui2dsys ProceduralShape record truncated")
            at = cursor + 4
            option_flags = raw[at]
            at += 1
            option_bytes = list(raw[at:at + 7])
            at += 7
            reserve0 = list(struct.unpack_from("<4I", raw, at)); at += 16
            rounded0 = list(struct.unpack_from("<4f", raw, at)); at += 16
            rounded1 = list(struct.unpack_from("<4f", raw, at)); at += 16
            reserve1 = struct.unpack_from("<f", raw, at)[0]; at += 4

            def color4():
                nonlocal at
                color = list(struct.unpack_from("<4f", raw, at))
                at += 16
                return color

            color0 = color4()
            inner_shadow_color = color4()
            inner_shadow_transform = list(struct.unpack_from("<3f", raw, at)); at += 12
            color_overlay = color4()
            gradation_weights = list(struct.unpack_from("<4f", raw, at)); at += 16
            gradation_colors = [color4() for _ in range(4)]
            gradation_rotation = struct.unpack_from("<f", raw, at)[0]; at += 4
            drop_shadow_color = color4()
            drop_shadow_transform = list(struct.unpack_from("<3f", raw, at)); at += 12
            reserve2 = list(struct.unpack_from("<4I", raw, at)); at += 16
            names = ("color", "inner_shadow", "color_overlay", "gradation_overlay",
                     "drop_shadow", "dual_drop_shadow", "rounded_corner_per_vertex", "drop_shadow_only")
            record.update({
                "semantic_type": "ProceduralShape", "options_raw": option_flags,
                "options": {name: bool(option_flags & (1 << bit)) for bit, name in enumerate(names)},
                "option_bytes_raw": option_bytes, "reserve0": reserve0,
                "rounded_corner0": rounded0, "rounded_corner1": rounded1,
                "reserve1": reserve1, "color0": color0,
                "inner_shadow_color": inner_shadow_color,
                "inner_shadow_transform": inner_shadow_transform,
                "color_overlay": color_overlay, "gradation_weights": gradation_weights,
                "gradation_colors": gradation_colors, "gradation_rotation": gradation_rotation,
                "drop_shadow_color": drop_shadow_color,
                "drop_shadow_transform": drop_shadow_transform,
                "reserve2": reserve2, "record_bytes": at - cursor,
                "trailing_bytes_in_system_data": len(raw) - at,
            })
            cursor += expected_size
        else:
            record.update({"semantic_type": "unresolved", "payload_offset": cursor,
                           "payload_sha256": _sha(raw[cursor:])})
            cursor = len(raw)
        records.append(record)
    return {"reserved_u16": reserved, "record_count": count, "data_offset": offset,
            "section_size_if_multiple": section_size, "records": records}


def _parse_usd1(payload, ui2dsys_scope="unknown"):
    """Parse typed usd1 entries and decode ACNH-used ui2dsys records."""
    if len(payload) < 4:
        raise ValueError("usd1 header truncated")
    count, reserved = struct.unpack_from("<HH", payload, 0)
    table_end = 4 + count * 12
    if table_end > len(payload):
        raise ValueError("usd1 entry table exceeds section")
    headers = []
    stops = {len(payload)}
    for i in range(count):
        entry_start = 4 + i * 12
        name_off, data_off, item_count, type_code, unknown = struct.unpack_from("<IIHBB", payload, entry_start)
        name_at = entry_start + name_off if name_off else None
        data_at = entry_start + data_off if data_off else None
        for at in (name_at, data_at):
            if at is not None:
                if at < table_end or at >= len(payload):
                    raise ValueError(f"usd1 entry {i} points outside data area: {at}")
                stops.add(at)
        headers.append({"entry_index": i, "entry_start": entry_start, "name_at": name_at,
                        "data_at": data_at, "item_count": item_count,
                        "type_code": type_code, "unknown_byte": unknown})
    out = []
    ordered_stops = sorted(stops)
    for h in headers:
        name = ""
        if h["name_at"] is not None:
            end = payload.find(b"\0", h["name_at"])
            if end < 0:
                raise ValueError("usd1 name is not null terminated")
            name = payload[h["name_at"]:end].decode("utf-8", "replace")
        type_code = h["type_code"]
        kind = {0: "string", 1: "int32", 2: "float32"}.get(type_code, "struct_or_unknown")
        value = None
        size = 0
        if h["data_at"] is not None:
            at = h["data_at"]
            next_stop = next(x for x in ordered_stops if x > at)
            if type_code == 0:
                size = h["item_count"]
                if at + size > next_stop:
                    raise ValueError("usd1 string overlaps next block")
                value = payload[at:at + size].split(b"\0", 1)[0].decode("utf-8", "replace")
            elif type_code in (1, 2):
                size = h["item_count"] * 4
                if at + size > next_stop:
                    raise ValueError("usd1 numeric values overlap next block")
                fmt = "<" + ("i" if type_code == 1 else "f") * h["item_count"]
                values = list(struct.unpack_from(fmt, payload, at)) if h["item_count"] else []
                if type_code == 2 and not all(math.isfinite(x) for x in values):
                    raise ValueError("usd1 contains nonfinite float")
                value = values
            else:
                size = max(0, next_stop - at)
                raw = payload[at:at + size]
                value = {"bytes": size, "sha256": _sha(raw),
                         "embedded_ascii": [m.group().decode("ascii") for m in re.finditer(rb"[\x20-\x7e]{3,}", raw)]}
                if name == "ui2dsys":
                    value["decoded"] = _parse_ui2dsys(raw, ui2dsys_scope)
        out.append({"entry_index": h["entry_index"], "name": name, "kind": kind, "type_code": type_code,
                    "item_count": h["item_count"], "unknown_byte": h["unknown_byte"],
                    "value": value, "value_bytes": size})
    return {"entry_count": count, "reserved_u16": reserved, "entries": out}


def _ascii_strings(data):
    return list(dict.fromkeys(m.group().decode("ascii") for m in re.finditer(rb"[\x20-\x7e]{3,}", data)))


def _section_cstr(data, offset, end):
    if offset < 0 or offset >= end:
        raise ValueError("control-source string offset outside section")
    stop = data.find(b"\0", offset, end)
    if stop < 0:
        raise ValueError("control-source string is not terminated")
    return data[offset:stop].decode("utf-8", "replace")


def _parse_cnt1(section, layout_bytes):
    """Decode control name, pane list, pane actions, and animation-name offsets."""
    payload, start = section["payload"], section["offset"]
    end = start + section["size"]
    if len(payload) < 20:
        raise ValueError("cnt1 header truncated")
    reserve_offset, pane_list_offset = struct.unpack_from("<2I", payload, 0)
    pane_count, anim_count = struct.unpack_from("<2H", payload, 8)
    pane_action_offset, anim_name_offset = struct.unpack_from("<2I", payload, 12)
    control_name = _section_cstr(layout_bytes, start + 0x1c, end)
    reserve_name = _section_cstr(layout_bytes, start + reserve_offset, end)
    if start + pane_list_offset + pane_count * 24 > end:
        raise ValueError("cnt1 fixed pane-name list exceeds section")
    pane_names = [layout_bytes[start + pane_list_offset + i * 24:
                                start + pane_list_offset + (i + 1) * 24]
                  .split(b"\0", 1)[0].decode("utf-8", "replace")
                  for i in range(pane_count)]

    def offset_names(table_offset, count):
        table = start + table_offset
        if table_offset == 0 and count == 0:
            return []
        if table < start or table + count * 4 > end:
            raise ValueError("cnt1 string-offset table exceeds section")
        offsets = struct.unpack_from("<" + "I" * count, layout_bytes, table) if count else []
        return [_section_cstr(layout_bytes, table + relative, end) for relative in offsets]

    pane_actions = offset_names(pane_action_offset, pane_count)
    animation_names = offset_names(anim_name_offset, anim_count)
    return {"control_name": control_name, "reserved_name": reserve_name,
            "pane_count": pane_count, "animation_count": anim_count,
            "pane_names": pane_names,
            "pane_action_names": pane_actions,
            "pane_action_bindings": [{"pane": pane, "action": action}
                                     for pane, action in zip(pane_names, pane_actions)],
            "animation_names": animation_names,
            "raw_offsets": {"reserved_name": reserve_offset, "pane_name_list": pane_list_offset,
                            "pane_action_offset_table": pane_action_offset,
                            "animation_name_offset_table": anim_name_offset}}


def _parse_prt1(section, layout_bytes):
    payload = section["payload"]
    # The section payload begins with the common 0x4c-byte pane header.
    # PartPane-specific data follows that block: count, magnification,
    # property records, then the referenced external layout name.
    pane_header_size = 0x4c
    if len(payload) < pane_header_size + 12:
        raise ValueError("prt1 header truncated")
    count = struct.unpack_from("<I", payload, pane_header_size)[0]
    magnify = list(struct.unpack_from("<2f", payload, pane_header_size + 4))
    table_end = pane_header_size + 12 + count * 0x28
    if table_end > len(payload):
        raise ValueError("prt1 property table exceeds section")
    name_end = payload.find(b"\0", table_end)
    if name_end < 0:
        raise ValueError("prt1 external layout name is not terminated")
    external_layout = payload[table_end:name_end].decode("utf-8", "replace")
    properties = []
    section_end = section["offset"] + section["size"]
    for i in range(count):
        at = pane_header_size + 12 + i * 0x28
        name = payload[at:at + 24].split(b"\0", 1)[0].decode("utf-8", "replace")
        usage, basic, material, user_data_type = payload[at + 24:at + 28]
        override_offset, user_data_offset, panel_info_offset = struct.unpack_from("<3I", payload, at + 28)
        override = None
        if override_offset:
            pos = section["offset"] + override_offset
            if pos + 8 > section_end:
                raise ValueError(f"prt1 property {i} override header out of range")
            size = struct.unpack_from("<I", layout_bytes, pos + 4)[0]
            if size < 8 or pos + size > section_end:
                raise ValueError(f"prt1 property {i} override size out of range")
            raw = layout_bytes[pos:pos + size]
            magic = raw[:4].decode("ascii", "replace")
            if magic in ("pan1", "pic1", "txt1", "wnd1", "bnd1", "scr1", "ali1", "cpt1", "prt1"):
                decoded = bflyt_parser._pane(raw, 0, magic)
                decoded.pop("children", None)
            else:
                decoded = {"type": magic, "sha256": _sha(raw), "bytes": size}
            override = {"offset": override_offset, "type": magic, "bytes": size, "decoded": decoded}
        user_data = None
        unresolved_user_data_offset = None
        if user_data_offset:
            pos = section["offset"] + user_data_offset
            if pos + 8 <= section_end and layout_bytes[pos:pos + 4] == b"usd1":
                size = struct.unpack_from("<I", layout_bytes, pos + 4)[0]
                if size < 8 or pos + size > section_end:
                    raise ValueError(f"prt1 property {i} usd1 size out of range")
                user_data = {"offset": user_data_offset, "bytes": size,
                             **_parse_usd1(layout_bytes[pos + 8:pos + size])}
            else:
                unresolved_user_data_offset = user_data_offset
        panel = None
        if panel_info_offset:
            pos = section["offset"] + panel_info_offset
            if pos + 52 > section_end:
                raise ValueError(f"prt1 property {i} panelInfo out of range")
            raw = layout_bytes[pos:pos + 52]
            values = struct.unpack_from("<10f", raw, 8)
            panel = {"offset": panel_info_offset, "bytes": 52, "sha256": _sha(raw),
                     "user_name": raw[:8].split(b"\0", 1)[0].decode("utf-8", "replace"),
                     "translate": list(values[0:3]), "rotate": list(values[3:6]),
                     "scale": list(values[6:8]), "size": list(values[8:10]),
                     "alpha": raw[48], "reserved_bytes": list(raw[49:52])}
        properties.append({"name": name, "usage_flag_raw": usage, "basic_usage_flag_raw": basic,
                           "material_usage_flag_raw": material, "user_data_type_raw": user_data_type,
                           "override": override,
                           "user_data": user_data, "unresolved_user_data_offset": unresolved_user_data_offset,
                           "panel_info": panel})
    return {"external_layout_name": external_layout, "property_count": count,
            "magnify": magnify, "properties": properties}


def _parse_wnd1(section, layout_bytes):
    start, end = section["offset"], section["offset"] + section["size"]
    payload = section["payload"]
    pane_name = payload[4:28].split(b"\0", 1)[0].decode("utf-8", "replace")
    body = start + 8 + 0x4c
    if body + 0x1c > end:
        raise ValueError("wnd1 extension header truncated")
    inflation = list(struct.unpack_from("<4h", layout_bytes, body))
    frame_size = list(struct.unpack_from("<4h", layout_bytes, body + 8))
    frame_count, flags, reserved = struct.unpack_from("<BBH", layout_bytes, body + 16)
    content_offset, frame_offsets_offset = struct.unpack_from("<2I", layout_bytes, body + 20)
    content = start + content_offset
    if content_offset < 8 + 0x4c or content + 20 > end:
        raise ValueError("wnd1 content offset outside section")
    colors = [_rgba_at(layout_bytes, content + i * 4) for i in range(4)]
    material_index = struct.unpack_from("<H", layout_bytes, content + 16)[0]
    uv_count = layout_bytes[content + 18]
    if content + 20 + uv_count * 8 > end:
        raise ValueError("wnd1 content UV table exceeds section")
    uvs = [list(struct.unpack_from("<2f", layout_bytes, content + 20 + i * 8))
           for i in range(uv_count)]
    frame_offsets_at = start + frame_offsets_offset
    if frame_offsets_offset < 8 + 0x4c + 0x1c or frame_offsets_at + frame_count * 4 > end:
        raise ValueError("wnd1 frame-offset table exceeds section")
    offsets = struct.unpack_from("<" + "I" * frame_count, layout_bytes, frame_offsets_at) if frame_count else []
    flip_names = {0: "None", 1: "FlipU", 2: "FlipV", 3: "Rotate90", 4: "Rotate180", 5: "Rotate270"}
    frames = []
    for offset in offsets:
        at = start + offset
        if offset < 8 + 0x4c + 0x1c or at + 4 > end:
            raise ValueError("wnd1 frame record outside section")
        frame_material, flip, reserve = struct.unpack_from("<HBB", layout_bytes, at)
        frames.append({"offset": offset, "material_index": frame_material,
                       "texture_flip_mode_id": flip, "texture_flip_mode": flip_names.get(flip, "unknown"),
                       "reserved_byte": reserve})
    return {"pane": pane_name, "inflation_lrtb": inflation,
            "frame_size_lrtb": frame_size, "frame_count": frame_count,
            "flags_raw": flags, "reserved_u16": reserved,
            "content": {"offset": content_offset, "vertex_colors_rgba": colors,
                        "material_index": material_index, "uv_count": uv_count, "uvs": uvs},
            "frame_offsets": offsets, "frames": frames}


def _parse_bound_or_scissor_pane(section, layout_bytes):
    kind = section["kind"]
    if kind not in ("bnd1", "scr1"):
        raise ValueError(f"unsupported simple pane type {kind}")
    if section["size"] < 8 + 0x4c:
        raise ValueError(f"{kind} common pane block truncated")
    pane = bflyt_parser._pane(layout_bytes, section["offset"], kind)
    pane.pop("children", None)
    tail = section["payload"][0x4c:]
    return {"pane": pane, "format_role": {"bnd1": "BoundingPane", "scr1": "ScissorPane"}[kind],
            "common_pane_bytes": 0x4c, "extension_bytes": len(tail),
            "extension_sha256": _sha(tail) if tail else None}


def audit_layout_sections():
    usd_sections, cnt_sections, part_sections, window_sections, simple_pane_sections, errors = [], [], [], [], [], []
    for archive in sorted([*(ROMFS / "Layout").glob("*.zs"), *(ROMFS / "Layout").glob("*.szs")]):
        try:
            outer = sarc.read_sarc(decompress_layout_archive(archive))
        except Exception as exc:
            errors.append({"archive": archive.name, "error": f"outer: {exc}"})
            continue
        for arc_name, arc_blob in outer.items():
            if not arc_name.lower().endswith(".arc"):
                continue
            try:
                inner = sarc.read_sarc(arc_blob)
            except Exception as exc:
                errors.append({"archive": archive.name, "member": arc_name, "error": f"inner: {exc}"})
                continue
            for member, data in inner.items():
                if not member.lower().endswith(".bflyt"):
                    continue
                try:
                    last_pane = None
                    in_pane_tree = True
                    for section in _section_list(data):
                        if section["kind"] in ("pan1", "pic1", "txt1", "wnd1", "bnd1", "prt1", "scr1", "ali1", "cpt1"):
                            last_pane = section["payload"][4:28].split(b"\0", 1)[0].decode("utf-8", "replace")
                        elif section["kind"] in ("grp1", "cnt1"):
                            in_pane_tree = False
                        if section["kind"] == "usd1":
                            parsed = _parse_usd1(section["payload"], "pane" if in_pane_tree and last_pane else "layout")
                            usd_sections.append({"source": archive.name, "layout_member": member,
                                                 "layout": Path(member).stem, "section_offset": section["offset"],
                                                 "section_size": section["size"],
                                                 "attachment_pane_candidate": last_pane if in_pane_tree else None,
                                                 "placement": ("pane_user_data_candidate" if in_pane_tree and last_pane else
                                                               "layout_user_data_candidate" if in_pane_tree else "trailing_user_data"),
                                                 **parsed})
                        elif section["kind"] == "prt1":
                            parsed = _parse_prt1(section, data)
                            part_sections.append({"source": archive.name, "layout_member": member,
                                                  "layout": Path(member).stem, "section_offset": section["offset"],
                                                  "pane_candidate": last_pane, "section_size": section["size"], **parsed})
                        elif section["kind"] == "wnd1":
                            parsed = _parse_wnd1(section, data)
                            window_sections.append({"source": archive.name, "layout_member": member,
                                                    "layout": Path(member).stem,
                                                    "section_offset": section["offset"],
                                                    "section_size": section["size"], **parsed})
                        elif section["kind"] == "cnt1":
                            parsed = _parse_cnt1(section, data)
                            cnt_sections.append({"source": archive.name, "layout_member": member,
                                                 "layout": Path(member).stem, "section_offset": section["offset"],
                                                 "section_size": section["size"], "payload_sha256": _sha(section["payload"]),
                                                 "preceding_pane_candidate": last_pane,
                                                 "embedded_ascii": _ascii_strings(section["payload"]), **parsed})
                        elif section["kind"] in ("bnd1", "scr1"):
                            parsed = _parse_bound_or_scissor_pane(section, data)
                            simple_pane_sections.append({"source": archive.name, "layout_member": member,
                                                         "layout": Path(member).stem,
                                                         "section_offset": section["offset"],
                                                         "section_size": section["size"], **parsed})
                except Exception as exc:
                    errors.append({"archive": archive.name, "layout_member": member,
                                   "error": f"section parse: {exc}"})
    entry_kind_counts = Counter(e["kind"] for s in usd_sections for e in s["entries"])
    names = Counter(e["name"] for s in usd_sections for e in s["entries"] if e["name"])
    cnt_hashes = Counter(x["payload_sha256"] for x in cnt_sections)
    part_properties = [p for section in part_sections for p in section["properties"]]
    property_override_types = Counter(p["override"]["type"] for p in part_properties if p["override"])
    window_frame_counts = Counter(x["frame_count"] for x in window_sections)
    window_uv_counts = Counter(x["content"]["uv_count"] for x in window_sections)
    simple_pane_type_counts = Counter(x["format_role"] for x in simple_pane_sections)
    simple_pane_size_counts = Counter(x["section_size"] for x in simple_pane_sections)
    simple_pane_extension_counts = Counter(x["extension_bytes"] for x in simple_pane_sections)
    control_types = Counter(x["control_name"] for x in cnt_sections)
    cnt_animation_names = Counter(name for x in cnt_sections for name in x["animation_names"])
    cnt_pane_action_names = Counter(name for x in cnt_sections for name in x["pane_action_names"])
    ui2dsys_semantics = Counter()
    ui2dsys_tag_names = Counter()
    ui2dsys_records = []
    for section in usd_sections:
        for entry in section["entries"]:
            if entry["name"] != "ui2dsys" or "decoded" not in entry["value"]:
                continue
            for record in entry["value"]["decoded"]["records"]:
                ui2dsys_semantics[record["semantic_type"]] += 1
                ui2dsys_tag_names.update(record.get("animation_tag_names", []))
                ui2dsys_records.append({"layout": section["layout"], "source": section["source"],
                                        "pane_candidate": section["attachment_pane_candidate"],
                                        "semantic_type": record["semantic_type"],
                                        "type_id": record["type_id"],
                                        "animation_tag_names": record.get("animation_tag_names", [])})
    return {
        "schema": "acnh.ui_bflyt_section_audit.v1",
        "evidence": "USD1 uses a u16 count followed by 12-byte records with relative name/data offsets, item count, type byte, and preserved unknown byte. CNT1 control/pane/action/animation tables and the ACNH-used ui2dsys AnimTagName and ProceduralShape records were decoded against section bounds.",
        "counts": {"usd1_sections": len(usd_sections), "usd1_entries": sum(len(x["entries"]) for x in usd_sections),
                   "usd1_type_counts": dict(entry_kind_counts), "cnt1_sections": len(cnt_sections),
                   "cnt1_unique_payloads": len(cnt_hashes), "cnt1_most_common_payloads": cnt_hashes.most_common(20),
                   "cnt1_control_type_counts": control_types.most_common(),
                   "cnt1_pane_references": sum(x["pane_count"] for x in cnt_sections),
                   "cnt1_pane_action_names": sum(len(x["pane_action_names"]) for x in cnt_sections),
                   "cnt1_animation_names": sum(len(x["animation_names"]) for x in cnt_sections),
                   "cnt1_unique_animation_names": len(cnt_animation_names),
                   "cnt1_top_animation_names": cnt_animation_names.most_common(50),
                   "cnt1_top_pane_action_names": cnt_pane_action_names.most_common(30),
                   "ui2dsys_semantic_type_counts": dict(ui2dsys_semantics),
                   "ui2dsys_layout_animation_tag_records": sum(x["semantic_type"] == "AnimTagName" for x in ui2dsys_records),
                   "ui2dsys_layout_animation_tag_names": sum(ui2dsys_tag_names.values()),
                   "ui2dsys_unique_animation_tag_names": len(ui2dsys_tag_names),
                   "ui2dsys_top_animation_tag_names": ui2dsys_tag_names.most_common(50),
                   "usd1_top_property_names": names.most_common(100),
                   "prt1_sections": len(part_sections), "prt1_property_records": len(part_properties),
                   "prt1_property_override_count": sum(p["override"] is not None for p in part_properties),
                   "prt1_overrides_by_section_type": dict(property_override_types),
                   "prt1_property_user_data_count": sum(p["user_data"] is not None for p in part_properties),
                   "prt1_unresolved_property_user_data_offsets": sum(p["unresolved_user_data_offset"] is not None for p in part_properties),
                   "prt1_panel_info_count": sum(p["panel_info"] is not None for p in part_properties),
                   "wnd1_panes": len(window_sections), "wnd1_frame_count_histogram": dict(window_frame_counts),
                   "wnd1_content_uv_count_histogram": dict(window_uv_counts),
                   "bounding_scissor_panes": len(simple_pane_sections),
                   "bounding_scissor_type_counts": dict(simple_pane_type_counts),
                   "bounding_scissor_section_size_counts": dict(simple_pane_size_counts),
                   "bounding_scissor_extension_byte_counts": dict(simple_pane_extension_counts)},
        "usd1_sections": usd_sections, "cnt1_sections": cnt_sections, "part_sections": part_sections,
        "window_sections": window_sections,
        "bounding_scissor_sections": simple_pane_sections,
        "parse_errors": errors,
        "ui2dsys_records": ui2dsys_records,
        "format_references": ["https://github.com/crackheadakira/nnbfl/blob/af30eaf9a92324bfe7ecc2af8df9c8dbf8848a79/hexpats/bflyt_bflan_bffnt.900.hexpat",
                              "https://github.com/crackheadakira/nnbfl/blob/af30eaf9a92324bfe7ecc2af8df9c8dbf8848a79/nnbfl/src/bflyt/pane.rs",
                              "https://github.com/Watertoon/REd-File-Format-Patterns/blob/f73b7e17f49f290b83e06c0b0cef932ad14c7f90/docs/bflyt_bflan.900.hexpat"],
        "limits": ["CNT1 control/pane/action/animation names and associations are decoded; event handling, key mapping, and lifecycle still need native/runtime confirmation.",
                   "Only ui2dsys AnimTagName and ProceduralShape types appear in this dump; other schema types are not observed locally.",
                   "BFLYT prt1 fields and embedded override/usd1/panel blocks are decoded structurally; usage-flag bit meanings still need renderer/native cross-check.",
                   "BND1 and SCR1 use the common pane block and have no local extension bytes; the format roles are BoundingPane and ScissorPane, while runtime hit-test and clipping behavior need consumer validation.",
                   "A user-data section is attached to the preceding pane only as a section-order candidate; runtime association should be verified for unusual layouts."],
    }


def _parse_extended_user_data_info(raw, info_offset, section_end):
    if info_offset + 8 > section_end or raw[info_offset:info_offset + 4] != b"FLEU":
        raise ValueError("FLEU info header is invalid or outside pai1")
    record_count = raw[info_offset + 4]
    reserved = list(raw[info_offset + 5:info_offset + 8])
    cursor = info_offset + 8
    records = []
    for record_index in range(record_count):
        record_start = cursor
        if cursor + 16 > section_end:
            raise ValueError("FLEU record header exceeds pai1")
        header_size, unknown_u16_a, unknown_u16_b, base_count, unknown_u32 = struct.unpack_from("<IHHII", raw, cursor)
        cursor += 16
        value_arrays = []
        for _ in range(3):
            byte_count = base_count * 4
            if cursor + byte_count > section_end:
                raise ValueError("FLEU float array exceeds pai1")
            values = list(struct.unpack_from("<" + "f" * base_count, raw, cursor)) if base_count else []
            if not all(math.isfinite(x) for x in values):
                raise ValueError("FLEU value array contains a non-finite float")
            value_arrays.append(values)
            cursor += byte_count
        key_offset_field = cursor
        if cursor + 4 > section_end:
            raise ValueError("FLEU key offset exceeds pai1")
        key_relative_offset = struct.unpack_from("<I", raw, cursor)[0]
        cursor += 4
        key_offset = key_offset_field + key_relative_offset
        if key_offset < info_offset or key_offset >= section_end:
            raise ValueError("FLEU key string points outside pai1")
        key_end = raw.find(b"\0", key_offset, section_end)
        if key_end < 0:
            raise ValueError("FLEU key string is not terminated within pai1")
        key_name = raw[key_offset:key_end].decode("utf-8", "replace")
        record_end = key_end + 1
        raw_record = raw[record_start:record_end]
        records.append({"record_index": record_index, "record_offset": record_start,
                        "record_size": record_end - record_start,
                        "header_size_raw": header_size,
                        "unknown_u16": [unknown_u16_a, unknown_u16_b],
                        "base_count": base_count, "unknown_u32": unknown_u32,
                        "value_arrays_f32": value_arrays,
                        "key_relative_offset": key_relative_offset,
                        "key_name": key_name, "sha256": _sha(raw_record)})
        cursor = record_end
    return {"record_count": record_count, "reserved_bytes": reserved,
            "records": records, "end_offset": cursor}


def audit_extended_user_data(animation_data, section_audit):
    archive_cache = {}
    infos, records, errors = [], [], []
    for animation in animation_data["animations"]:
        try:
            detail = read_json(ROOT / "output" / animation["json"])
            pai = next((x for x in detail.get("sections", []) if x["kind"] == "pai1"), None)
            if pai is None:
                continue
            pai_end = pai["offset"] + pai["size"]
            fleu_contents = [(content, info) for content in detail.get("contents", [])
                             for info in content.get("infos", []) if info.get("kind") == "FLEU"]
            if not fleu_contents:
                continue
            source = animation["source"]
            if source not in archive_cache:
                outer = sarc.read_sarc(decompress_layout_archive(ROMFS / source))
                archive_cache[source] = {name: sarc.read_sarc(blob)
                                         for name, blob in outer.items() if name.lower().endswith(".arc")}
            archive_name, inner_member = animation["member"].split("!", 1)
            raw = archive_cache[source][archive_name][inner_member]
            target_inventory = {(target["name"], target["target_type_id"]): target
                                for target in animation.get("targets", [])}
            animation_context = {
                "frame_count": animation.get("frames"),
                "loop_byte": animation.get("loop_byte"),
                "curve_track_count": animation.get("track_count"),
                "curve_key_count": animation.get("key_count"),
                "count_scope": "ordinary numeric curve tracks/keys; FLEU records are separate",
            }
            for content, info in fleu_contents:
                parsed = _parse_extended_user_data_info(raw, info["offset"], pai_end)
                target = target_inventory.get((content.get("name"), content.get("target_type_id")), {})
                target_candidates = target.get("same_container_name_candidates", [])
                candidate = target_candidates[0] if len(target_candidates) == 1 else None
                info_record_indices = []
                for entry in parsed["records"]:
                    user_data_matches = []
                    if candidate and "component_id" in candidate and "!" in candidate["layout_member"]:
                        candidate_arc, candidate_member = candidate["layout_member"].split("!", 1)
                        if candidate_arc == archive_name:
                            for usd_section in section_audit["usd1_sections"]:
                                if (usd_section["source"] == Path(source).name and
                                    usd_section["layout_member"] == candidate_member and
                                    usd_section.get("attachment_pane_candidate") == content.get("name") and
                                    usd_section.get("placement") == "pane_user_data_candidate"):
                                    for usd_entry in usd_section["entries"]:
                                        if usd_entry["name"] == entry["key_name"]:
                                            user_data_matches.append({
                                                "section_offset": usd_section["section_offset"],
                                                "entry_index": usd_entry["entry_index"],
                                                "name": usd_entry["name"], "kind": usd_entry["kind"],
                                                "item_count": usd_entry["item_count"],
                                                "value": usd_entry["value"],
                                            })
                    binding_status = ("unique_same_archive_pane_user_data_key" if len(user_data_matches) == 1 else
                                      "ambiguous_same_archive_pane_user_data_key" if len(user_data_matches) > 1 else
                                      "no_matching_pane_user_data_key")
                    record = {"source": source, "animation_member": animation["member"],
                              "animation_sha256": animation["sha256"],
                              "animation_context": animation_context,
                              "tag": animation.get("tag", {}).get("name"),
                              "content_target_name": content.get("name"),
                              "content_target_type_id": content.get("target_type_id"),
                              "info_offset": info["offset"], **entry}
                    record["target_layout_candidates"] = target_candidates
                    record["pane_user_data_binding"] = {"status": binding_status,
                                                          "matches": user_data_matches}
                    info_record_indices.append(len(records))
                    records.append(record)
                infos.append({"source": source, "animation_member": animation["member"],
                              "tag": animation.get("tag", {}).get("name"),
                              "content_target_name": content.get("name"),
                              "content_target_type_id": content.get("target_type_id"),
                              "info_offset": info["offset"],
                              "reserved_bytes": parsed["reserved_bytes"],
                              "record_count": parsed["record_count"],
                              "record_indices": info_record_indices,
                              "end_offset": parsed["end_offset"]})
        except Exception as exc:
            errors.append({"source": animation.get("source"), "member": animation.get("member"),
                           "error": f"extended user data parse: {exc}"})
    keys = Counter(record["key_name"] for record in records)
    binding_status_counts = Counter(x["pane_user_data_binding"]["status"] for x in records)
    animation_contexts = {}
    for record in records:
        key = (record["source"], record["animation_member"])
        animation_contexts[key] = {
            "source": record["source"],
            "animation_member": record["animation_member"],
            **record["animation_context"],
            "fleu_record_count": animation_contexts.get(key, {}).get("fleu_record_count", 0) + 1,
        }
    return {"schema": "acnh.ui_bflan_extended_user_data.v1",
            "evidence": "FLEU uses its dedicated inline ExtendedUserDataAnim record, not the standard numeric target/curve block. Each record was parsed within its pai1 bounds and preserves its three float arrays, raw header fields, key string, and record hash. Its key name is cross-referenced to usd1 entries on the uniquely named same-archive pane candidate.",
            "counts": {"source_archives": len(archive_cache), "infos": len(infos),
                       "records": len(records), "base_count_total": sum(x["base_count"] for x in records),
                       "f32_array_value_count": sum(3 * x["base_count"] for x in records),
                       "key_name_counts": dict(sorted(keys.items())),
                       "pane_user_data_binding_status_counts": dict(binding_status_counts),
                       "parse_errors": len(errors)},
            "format_reference": "https://github.com/crackheadakira/nnbfl/blob/af30eaf9a92324bfe7ecc2af8df9c8dbf8848a79/nnbfl/src/bflan/anim_info.rs",
            "value_array_semantics": "The format defines three f32 arrays per record; this report preserves them by array index and does not assign runtime meaning to each array.",
            "animation_contexts": list(animation_contexts.values()),
            "infos": infos, "records": records, "parse_errors": errors}


def _property_hint(section, property_id):
    pane_animation = {
        0: "pane_translate_x", 1: "pane_translate_y", 2: "pane_translate_z",
        3: "pane_rotate_x", 4: "pane_rotate_y", 5: "pane_rotate_z",
        6: "pane_scale_x", 7: "pane_scale_y", 8: "pane_width", 9: "pane_height",
    }
    if section == "FLPA":
        return pane_animation.get(property_id, "unknown_FLPA_property")
    if section == "FLVI" and property_id == 0:
        return "pane_visibility"
    if section == "FLVC":
        if property_id == 16:
            return "pane_alpha"
        if 0 <= property_id <= 15:
            channels = ("r", "g", "b", "a")
            return f"vertex_{property_id // 4}_color_{channels[property_id % 4]}"
    if section == "FLMC":
        channels = ("r", "g", "b", "a")
        if 0 <= property_id <= 3:
            return f"material_buffer_{channels[property_id]}"
        if 4 <= property_id <= 7:
            return f"material_constant0_{channels[property_id - 4]}"
        if 8 <= property_id <= 27:
            color_index, channel = divmod(property_id - 8, 4)
            return f"material_color{color_index}_{channels[channel]}"
    if section == "FLTS":
        return {0: "texture_translate_s", 1: "texture_translate_t",
                2: "texture_rotate", 3: "texture_scale_s",
                4: "texture_scale_t"}.get(property_id, "unknown_FLTS_property")
    if section == "FLTP" and property_id == 0:
        return "texture_pattern_image"
    if section == "FLAC" and property_id == 0:
        return "material_alpha_compare_reference"
    if section == "FLCT":
        return {0: "per_character_transform_eval_time_offset",
                1: "per_character_transform_eval_time_width"}.get(property_id, "unknown_FLCT_property")
    if section == "FLEU":
        return "extended_user_data_record_not_numeric_curve_property"
    if section == "FLIM":
        return {0: "indirect_srt_rotate", 1: "indirect_srt_scale_u",
                2: "indirect_srt_scale_v"}.get(property_id, "unknown_FLIM_property")
    if section == "FLPS":
        shape_properties = {
            0: "shape_expand_left_top", 1: "shape_expand_right_top",
            2: "shape_expand_left_bottom", 3: "shape_expand_right_bottom",
            4: "shape_radius_left_top", 5: "shape_radius_right_top",
            6: "shape_radius_left_bottom", 7: "shape_radius_right_bottom",
            8: "shape_inner_stroke_size",
            9: "shape_inner_stroke_color_r", 10: "shape_inner_stroke_color_g",
            11: "shape_inner_stroke_color_b", 12: "shape_inner_stroke_color_a",
            13: "shape_inner_shadow_color_r", 14: "shape_inner_shadow_color_g",
            15: "shape_inner_shadow_color_b", 16: "shape_inner_shadow_color_a",
            17: "shape_inner_shadow_angle", 18: "shape_inner_shadow_distance",
            19: "shape_inner_shadow_size",
            20: "shape_color_overlay_color_r", 21: "shape_color_overlay_color_g",
            22: "shape_color_overlay_color_b", 23: "shape_color_overlay_color_a",
            24: "shape_gradation_control_0", 25: "shape_gradation_control_1",
            26: "shape_gradation_control_2", 27: "shape_gradation_control_3",
            28: "shape_gradation_color0_r", 29: "shape_gradation_color0_g",
            30: "shape_gradation_color0_b", 31: "shape_gradation_color0_a",
            32: "shape_gradation_color1_r", 33: "shape_gradation_color1_g",
            34: "shape_gradation_color1_b", 35: "shape_gradation_color1_a",
            36: "shape_gradation_color2_r", 37: "shape_gradation_color2_g",
            38: "shape_gradation_color2_b", 39: "shape_gradation_color2_a",
            40: "shape_gradation_color3_r", 41: "shape_gradation_color3_g",
            42: "shape_gradation_color3_b", 43: "shape_gradation_color3_a",
            44: "shape_gradation_angle",
            45: "shape_outer_shadow_color_r", 46: "shape_outer_shadow_color_g",
            47: "shape_outer_shadow_color_b", 48: "shape_outer_shadow_color_a",
            49: "shape_outer_shadow_angle", 50: "shape_outer_shadow_distance",
            51: "shape_outer_shadow_size",
        }
        return shape_properties.get(property_id, "unknown_FLPS_property")
    return "unresolved_numeric_property"


def build_animation_semantics(animation_data, section_audit, extended_user_data):
    """Join curve tracks to targets and keep FLEU records in their own schema."""
    section_semantics = {
        "FLPA": "PaneSrt", "FLVI": "Visibility", "FLVC": "VertexColor",
        "FLMC": "MaterialColor", "FLTS": "TextureSrt", "FLTP": "TexturePattern",
        "FLCT": "PerCharacterTransform", "FLEU": "ExtendedUserData",
        "FLAC": "AlphaCompare", "FLIM": "IndirectSrt", "FLPS": "ProceduralShape",
    }
    target_type_semantics = {0: "Pane", 1: "Material", 2: "User", 3: "PaneExt", 4: "StateMachine"}
    curve_semantics = {0: "Constant", 1: "Step", 2: "Hermite"}
    declared_tags_by_archive = {}
    for record in section_audit["ui2dsys_records"]:
        if record["semantic_type"] == "AnimTagName":
            declared_tags_by_archive.setdefault(record["source"], set()).update(record["animation_tag_names"])
    user_target_bindings = {}
    for record in extended_user_data["records"]:
        key = (record["animation_member"], record.get("tag"), record["content_target_name"])
        user_target_bindings.setdefault(key, []).append(record["pane_user_data_binding"]["status"])
    track_counts = Counter()
    property_counts = Counter()
    target_type_counts = Counter()
    target_binding_counts = Counter()
    declared_tag_counts = Counter()
    curve_counts = Counter()
    encoding_counts = Counter()
    animation_errors = []
    tracks = []
    content_count = 0
    for animation in animation_data["animations"]:
        try:
            detail = read_json(ROOT / "output" / animation["json"])
        except Exception as exc:
            animation_errors.append({"member": animation.get("member"), "error": str(exc)})
            continue
        inventory = {(t["name"], t["target_type_id"]): t for t in animation.get("targets", [])}
        animation_tag = animation.get("tag", {}).get("name")
        declared_tags = declared_tags_by_archive.get(Path(animation.get("source", "")).name, set())
        if not animation_tag:
            declared_tag_status = "empty_tag_name"
        elif animation_tag in declared_tags:
            declared_tag_status = "declared_by_layout_ui2dsys"
        else:
            declared_tag_status = "not_found_in_layout_ui2dsys"
        declared_tag_counts[declared_tag_status] += 1
        for content in detail.get("contents", []):
            content_count += 1
            target_type = content.get("target_type_id")
            target_type_counts[target_type] += 1
            target = inventory.get((content.get("name"), target_type))
            candidates = target.get("same_container_name_candidates", []) if target else []
            target_candidate = candidates[0] if len(candidates) == 1 else None
            if target_type == 0 and target_candidate and "component_id" in target_candidate:
                target_binding_status = "unique_same_archive_pane"
            elif target_type == 1 and target_candidate and "material_index" in target_candidate:
                target_binding_status = "unique_same_archive_material"
            elif target_type == 2:
                user_statuses = user_target_bindings.get((animation.get("member"), animation_tag, content.get("name")), [])
                if user_statuses and all(x == "unique_same_archive_pane_user_data_key" for x in user_statuses):
                    target_binding_status = "unique_same_archive_pane_user_data_key"
                elif any(x == "ambiguous_same_archive_pane_user_data_key" for x in user_statuses):
                    target_binding_status = "ambiguous_same_archive_pane_user_data_key"
                else:
                    target_binding_status = "user_target_unresolved"
            elif not candidates:
                target_binding_status = "no_same_name_layout_candidate"
            elif len(candidates) > 1:
                target_binding_status = "ambiguous_same_name_layout_candidate"
            else:
                target_binding_status = "candidate_kind_mismatch"
            target_binding_counts[(target_type, target_binding_status)] += 1
            for info in content.get("infos", []):
                section = info["kind"]
                if section == "FLEU":
                    continue
                for raw_track in info.get("targets", []):
                    prop_id = raw_track["property_id"]
                    track_counts[section] += 1
                    property_counts[(section, prop_id)] += 1
                    curve_counts[raw_track["curve_type_id"]] += 1
                    encoding_counts[raw_track["key_encoding"]] += 1
                    tracks.append({
                        "source": animation.get("source"),
                        "member": animation.get("member"),
                        "tag": animation.get("tag", {}).get("name"),
                        "frame_count": animation.get("frames"),
                        "loop_byte": animation.get("loop_byte"),
                        "animation_json": animation.get("json"),
                        "declared_tag_status": declared_tag_status,
                        "target_name": content.get("name"),
                        "target_type_id": target_type,
                        "target_type_semantics": target_type_semantics.get(target_type, "unknown"),
                        "target_binding_status": target_binding_status,
                        "target_candidates": candidates,
                        "section": section,
                        "section_semantics": section_semantics.get(section, "unknown"),
                        "property_id": prop_id,
                        "property_semantics": _property_hint(section, prop_id),
                        "curve_type_id": raw_track["curve_type_id"],
                        "curve_semantics": curve_semantics.get(raw_track["curve_type_id"], "unknown"),
                        "key_encoding": raw_track["key_encoding"],
                        "key_count": raw_track["key_count"],
                    })
    known_sections = set(section_semantics)
    property_map = []
    for (section, prop_id), count in sorted(property_counts.items()):
        hint = _property_hint(section, prop_id)
        property_map.append({"section": section, "property_id": prop_id,
                             "track_count": count, "semantics": hint,
                             "mapped_from_format_reference": hint != "unresolved_numeric_property"
                             and not hint.startswith("unknown_")
                             and not hint.endswith("_candidate")})
    unresolved_sections = sorted(section for section in track_counts if section not in known_sections)
    unresolved_properties = [x for x in property_map if not x["mapped_from_format_reference"]]
    unresolved_tag_anomalies = [{"source": a.get("source"), "member": a.get("member"),
                                 "tag_name": a.get("tag", {}).get("name"),
                                 "status": ("empty_tag_name" if not a.get("tag", {}).get("name") else
                                            "not_found_in_layout_ui2dsys")}
                                for a in animation_data["animations"]
                                if not a.get("tag", {}).get("name") or
                                a.get("tag", {}).get("name") not in
                                declared_tags_by_archive.get(Path(a.get("source", "")).name, set())]
    return {
        "schema": "acnh.ui_bflan_semantics.v1",
        "evidence": "BFLAN curve tracks are joined to local pane/material candidates; FLEU is decoded separately as its dedicated extended user-data structure. Property IDs, section kinds, target types, and curve IDs are labeled from public format schemas and checked against ACNH's local layouts, key encodings, and tag-name records.",
        "format_references": ["https://github.com/crackheadakira/nnbfl/blob/af30eaf9a92324bfe7ecc2af8df9c8dbf8848a79/hexpats/bflyt_bflan_bffnt.900.hexpat",
                              "https://github.com/crackheadakira/nnbfl/blob/af30eaf9a92324bfe7ecc2af8df9c8dbf8848a79/nnbfl/src/bflan/targets.rs",
                              "https://github.com/crackheadakira/nnbfl/blob/af30eaf9a92324bfe7ecc2af8df9c8dbf8848a79/nnbfl/src/bflan/anim_info.rs",
                              "https://github.com/aboood40091/LayoutExporterU/blob/8c644cfad606ead47e6ce9eae2d315a5e70afe61/bflan.py",
                              "https://github.com/KibbeWater/BFLayout/blob/d65f4021dac18f123748417be05a69dbc39dff95/docs/mcp.md"],
        "counts": {
            "animations": len(animation_data["animations"]), "content_targets": content_count,
            "tracks": len(tracks), "keyframes": sum(t["key_count"] for t in tracks),
            "extended_user_data_infos": extended_user_data["counts"]["infos"],
            "extended_user_data_records": extended_user_data["counts"]["records"],
            "animation_payload_records": len(tracks) + extended_user_data["counts"]["records"],
            "tracks_by_section": dict(track_counts),
            "target_type_semantics": {str(k): target_type_semantics.get(k, "unknown") for k in sorted(target_type_counts)},
            "target_content_counts": dict(target_type_counts),
            "target_binding_status_counts": [
                {"target_type_id": key[0], "status": key[1], "count": value}
                for key, value in sorted(target_binding_counts.items(), key=lambda item: str(item[0]))
            ],
            "declared_tag_status_counts": dict(declared_tag_counts),
            "curve_type_semantics": {str(k): curve_semantics.get(k, "unknown") for k in sorted(curve_counts)},
            "curve_type_ids": dict(curve_counts), "key_encodings": dict(encoding_counts),
            "unresolved_section_kinds": unresolved_sections,
            "unresolved_property_count": len(unresolved_properties),
            "unresolved_property_track_count": sum(x["track_count"] for x in unresolved_properties),
            "layout_declared_tag_anomalies": len(unresolved_tag_anomalies),
            "parse_errors": len(animation_errors),
        },
        "property_map": property_map,
        "section_semantics": section_semantics,
        "target_type_semantics": {str(k): v for k, v in target_type_semantics.items()},
        "curve_type_semantics": {str(k): v for k, v in curve_semantics.items()},
        "layout_declared_tag_anomalies": unresolved_tag_anomalies,
        "target_resolution_limits": [
            "Unique type-0 and type-1 matches prove static pane/material binding, not that a particular animation is invoked at runtime.",
            "All 15 User targets have a unique same-archive pane/userData-key match; the native/runtime consumer and animation invocation remain unproven.",
            "Step/Hermite curve kinds are decoded, but frame rate, dispatch timing, and runtime invocation are not proven."
        ],
        "extended_user_data_summary": extended_user_data["counts"],
        "unresolved_properties": unresolved_properties,
        "parse_errors": animation_errors,
        "tracks": tracks,
    }


def smartphone_animations(animation_data):
    result = []
    for anim in animation_data["animations"]:
        if anim["source"] != "Layout/MainScreenSmartPhone.Nin_NX_NVN.zs":
            continue
        detail = read_json(ROOT / "output" / anim["json"])
        tracks = []
        for content in detail.get("contents", []):
            for info in content.get("infos", []):
                for target in info.get("targets", []):
                    tracks.append({
                        "target": content["name"],
                        "section": info["kind"],
                        "property_id": target["property_id"],
                        "property_hint": _property_hint(info["kind"], target["property_id"]),
                        "key_count": target["key_count"],
                        "keys": target["keys"],
                    })
        result.append({
            "member": anim["member"], "tag": anim.get("tag", {}).get("name"),
            "frame_count": anim.get("frames"), "loop_byte": anim.get("loop_byte"),
            "track_count": anim.get("track_count"), "key_count": anim.get("key_count"),
            "targets": anim.get("targets", []), "tracks": tracks,
        })
    return result


def native_evidence():
    return [
        {
            "function_va": "0x1315ac0", "level": "native_static_correlation",
            "layout_string": "MainScreen", "other_strings": ["STR_Week", "STR_Month"],
            "finding": "Reads/caches calendar-like fields, selects a weekday label, and updates MainScreen-backed UI objects; LClock contains weekday, month, day, hour, minute, and AM/PM panes.",
            "confidence": "high for calendar/time role; exact field-to-pane offsets remain open",
        },
        {
            "function_va": "0x1214110", "level": "native_static_correlation",
            "layout_string": "MainScreen", "other_strings": ["ConfirmedFruit", "PickUpFirst", "STR_KeyIcon"],
            "finding": "Routes item/prompt-related data through MainScreen UI helpers; MainScreen contains eight L_ItemBalloon slots and L_MealEf.",
            "confidence": "medium-high correlation; exact slot selection and each event branch need further trace",
        },
        {
            "function_va": "0x132e050", "level": "native_static_candidate",
            "layout_string": "MainScreen", "other_strings": ["ConfirmedFruit"],
            "finding": "A ConfirmedFruit branch references MainScreen; exact visible pane and trigger ownership are unresolved.",
            "confidence": "medium",
        },
        {
            "function_va": "0x1315f90", "level": "native_static_candidate",
            "layout_string": "MainScreen", "other_strings": [],
            "finding": "Loads four MainScreen-associated entries from an indexed object array; semantic pane identities remain unresolved.",
            "confidence": "low-medium",
        },
        {
            "function_va": "0x14797c0", "level": "native_static_candidate",
            "layout_string": "MainScreen", "other_strings": [],
            "finding": "References MainScreen in a loop over a UI/resource table; specific display behavior is unresolved.",
            "confidence": "low",
        },
    ]


def build_native_bindings(native_data):
    # Arguments are copied from the 1.0.0 pseudocode. Their enum/type semantics
    # are deliberately left open until the registration helper is fully resolved.
    registrations = [
        ("cAddress", "0x1549090", [0, 4]), ("cAudio", "0x1549400", [13]),
        ("cCharaMake", "0x1549090", [0, 10]), ("cCustomHome", "0x1549090", [0, 14]),
        ("cKabuBuy", "0x1549090", [0, 12]), ("cMsgCardDesignSelect", "0x1549090", [0, 5]),
        ("cMsgCardEditText", "0x1549750", [13, 15]), ("cMsgCardView", "0x1549400", [0]),
        ("cMyDesignList", "0x1549090", [0, 16]), ("cMyDesignSet", "0x1549400", [17]),
        ("cShopBuy", "0x1549750", [1, 6]), ("cShopBuyTailor", "0x1549090", [0, 7]),
        ("cStampEdit", "0x1549400", [0]), ("cSwkbdInput", "0x1549090", [0, 11]),
        ("cSwkbdTextAreaInputBell", "0x1549090", [0, 12]), ("cTripList", "0x1549090", [0, 9]),
        ("cWorkCraft", "0x1549750", [1, 2]), ("cWorkRemake", "0x1549090", [0, 3]),
        ("cGetItem", "0x1549400", [0]), ("cPocketMenu", "0x1549750", [1, 13]),
        ("cDateInput", "0x1549090", [0, 8]), ("cDateInputYear", "0x1549090", [0, 8]),
        ("cMelodyEdit", "0x1549090", [0, 18]), ("cMapSelect", "0x1549400", [19]),
        ("cMapRemove", "0x1549750", [1, 20]), ("cCatalog", "0x1549090", [21, 15]),
        ("MenuDevice", "0x1549400", [22]), ("AddresseeSelMulti", "0x1549400", [0]),
        ("cIllegalReport", "0x1549400", [24]), ("cTitle", "0x1549400", [0]),
        ("cRingMenuToolsMain", "0x1549400", [13]),
    ]
    return {
        "schema": "acnh.ui_native_bindings.v1",
        "source_build": "ACNH 1.0.0; ExeFS main hash f8d248109ff72999b4600ae3749f8c7397fb960f7ad3ab8dee3018ae9e14e900",
        "exact_layout_name_refs": native_data["layouts"],
        "page_registry": {
            "function_va": "0x1545400",
            "raw_registration_count": len(registrations),
            "registration_helpers": ["0x1549090", "0x1549400", "0x1549750"],
            "evidence": "Native pseudocode registers 31 page names; each helper resolves a name against 31 global entries and writes byte flags into a 0xb0-stride registry record.",
            "helper_observed_effects": {
                "0x1549090": "Writes 1 at each of the two supplied byte offsets in the selected record.",
                "0x1549400": "Writes 1 at the one supplied byte offset in the selected record.",
                "0x1549750": "Writes 1 at record offset 0 and at each of the two supplied byte offsets.",
            },
            "record_layout": {
                "base_va": "0x381614d", "stride_bytes": "0xb0", "record_index_range": [0, 30],
                "accepted_byte_flag_offset_range": [0, 26],
                "out_of_range_behavior": "An offset greater than 26 falls back to writing record offset 0.",
            },
            "limits": "Byte offsets are observed registration flags; their semantic method names, constructor/vtable, screen open/close, focus, and input routing remain to be proven.",
            "registrations": [{"page_name": n, "helper_va": helper, "raw_integer_arguments": args}
                              for n, helper, args in registrations],
        },
        "focused_correlations": [
            {"function_va": "0x1315ac0", "layout": "MainScreen / LClock",
             "evidence": ["MainScreen", "STR_Week", "STR_Month", "weekday helper 0x1fbd50"],
             "reading": "Calendar/time state refresh correlated with LClock's weekday, month/day, hour/minute, and AM/PM panes.",
             "open": "Exact individual source field to pane binding and localization call sequence."},
            {"function_va": "0x1214110", "layout": "MainScreen / L_ItemBalloon and L_MealEf candidates",
             "evidence": ["MainScreen", "PickUpFirst", "STR_KeyIcon", "ConfirmedFruit"],
             "reading": "Item pickup/key-icon prompt and fruit-related presentation route through MainScreen UI helpers.",
             "open": "Exact selection among eight item-balloon instances and event branch ownership."},
            {"function_va": "0x132e050", "layout": "MainScreen",
             "evidence": ["MainScreen", "ConfirmedFruit"],
             "reading": "Fruit-confirmation branch updates a MainScreen-associated UI object.",
             "open": "Exact visible pane and lifecycle."},
            {"function_va": "0x12330c0", "layout": "MenuMapFull",
             "evidence": ["MenuMapFull", "0x131e7d0 called for child indices 1 through 11"],
             "reading": "MenuMapFull initializes an indexed set of eleven child UI entries.",
             "open": "Names/semantics of each entry and exact map interaction callbacks."},
            {"function_va": "0x125e3e0", "layout": "MenuDevice",
             "evidence": ["MenuDevice", "MainUiClockEnable", "calendar helper 0x1fb9c0"],
             "reading": "MenuDevice has a clock-enabled branch and updates associated display fields.",
             "open": "Exact pane-to-field binding and controller-owned update schedule."},
            {"function_va": "0x11e6d70", "layout": "CmnDialog / CmnDialogSmartPhone",
             "evidence": ["CmnDialog", "CmnDialogSmartPhone", "CommonDialogPage", "CommonDialogBGPage"],
             "reading": "A common dialog page family is associated with both standard and phone dialog layouts.",
             "open": "Modal stack, focus return, cancel/confirm routing, and lifecycle."},
            {"function_va": "0x151ec70", "layout": "SwkbdTextAreaChat",
             "evidence": ["%s.bflyt", "LayoutTextAreaPark", "T_Header_00", "T_Title_00", "T_Explanation_00", "P_UnFixed_%02d"],
             "reading": "Chat text-area setup references a dynamic layout resource and named header/title/explanation/fixed-field panes.",
             "open": "Full input validation and keyboard focus behavior."},
        ],
    }


def build_mapping(layout_data, catalog, animation_data):
    by_name = {x["name"]: x for x in layout_data["layouts"]}
    main = by_name["MainScreen"]
    phone = by_name["MainScreenSmartPhone"]
    candidate_names = {x["name"] for x in catalog if x["exact_native_string_ref_candidates"]}
    name_counts = Counter(x["name"] for x in catalog)
    main_components = []
    for c in main["components"]:
        if c["type"] != "prt1":
            continue
        name = c["name"]
        main_components.append({
            "pane": name, "layout": c.get("part_layout"),
            "translate_bflyt": c.get("translate"), "size": c.get("size"),
            "visible_default": c.get("visible"),
            "position_class_candidate": "dynamic_or_contextual" if any(k in name for k in ("Balloon", "MealEf", "MiniGame")) else "screen_anchor_candidate",
            "candidates": c.get("part_layout_candidates", []),
        })
    return {
        "schema": "acnh.ui_hud_mapping.v1",
        "source_build": "ACNH 1.0.0; ExeFS main hash f8d248109ff72999b4600ae3749f8c7397fb960f7ad3ab8dee3018ae9e14e900",
        "source_romfs": str(ROMFS),
        "evidence_note": "Structural BFLYT/FLAN data and native pseudocode correlations; no runtime capture or game rendering asserted.",
        "screens": [
            {"name": "MainScreen", "source": main["source"], "member": main["member"],
             "sha256": main["sha256"], "design_size": main["components"][0]["size"],
             "pane_count": len(main["components"]), "sub_layout_slots": main_components,
             "native_findings": native_evidence()},
            {"name": "MainScreenSmartPhone", "source": phone["source"], "member": phone["member"],
             "sha256": phone["sha256"], "design_size": phone["components"][0]["size"],
             "pane_count": len(phone["components"]),
             "notable_panes": [{"name": c["name"], "type": c["type"], "parent_id": c["parent_id"],
                                "translate": c["translate"], "size": c["size"], "visible_default": c["visible"],
                                "alpha_default": c["alpha"], "text": c.get("text")}
                               for c in phone["components"] if c["name"] in (
                                   "P_Icon_00", "P_Monitor_00", "P_Monitor_01", "N_State_00", "N_State_01",
                                   "P_ZLBase_00", "T_ZL_00", "N_Loop_00", "P_Balloon_00", "P_Puls_00")],
             "animations": smartphone_animations(animation_data),
             "native_binding_status": "No exact MainScreenSmartPhone name hit among the 62 current string-reference candidates; controller/load path remains open."},
        ],
        "catalog_summary": {"layout_count": len(catalog),
                            "exact_native_string_candidate_name_count": len(candidate_names),
                            "layout_records_matched_by_candidate_names": sum(bool(x["exact_native_string_ref_candidates"]) for x in catalog),
                            "duplicate_layout_names_with_candidate": sorted(n for n in candidate_names if name_counts[n] > 1),
                            "unresolved_root_vs_part_roles": "Names provide candidates only; host/controller role still needs native proof."},
        "open_items": [
            "Resolve BFLYT origin/viewport transform against renderer behavior before claiming pixel-exact coordinates.",
            "Resolve 35 reusable-part references with two same-name candidates; every reference has a candidate whose archive suffix matches its host, but native loader precedence is still unproven.",
            "Trace runtime invocation and consumer behavior for all mapped animations; frame rate and dispatch timing are not encoded by the static track map.",
            "Recover local MainScreenSmartPhone controller and input/focus lifecycle; no exact name xref exists in current candidate set.",
            "Validate BND1 bounds, SCR1 clipping, and decoded ui2dsys ProceduralShape effects against the renderer.",
            "Map runtime shader/pass state, font glyph fallback, and renderer coordinate behavior before declaring render parity.",
        ],
    }


def decompress_layout_archive(path):
    data = path.read_bytes()
    if data[:4] == b"Yaz0":
        import tempfile
        decoder = WORK / "yaz0dec"
        source = ROOT / "tools" / "reference" / "acnh_rip" / "native" / "yaz0dec.c"
        if not decoder.exists() or decoder.stat().st_mtime < source.stat().st_mtime:
            subprocess.run(["gcc", "-O2", "-o", str(decoder), str(source)], check=True)
        with tempfile.TemporaryDirectory(prefix="acnh_ui_yaz0_") as temp_dir:
            input_path, output_path = Path(temp_dir) / "in.szs", Path(temp_dir) / "out.sarc"
            input_path.write_bytes(data)
            subprocess.run([str(decoder), str(input_path), str(output_path)], check=True)
            return output_path.read_bytes()
    if data[:4] == b"\x28\xb5\x2f\xfd":
        p = subprocess.run(["zstd", "-dc"], input=data, capture_output=True, check=True)
        return p.stdout
    return data


def decode_phone_textures():
    import tempfile
    from acnh_rip.formats.bntx import read_bntx

    archive = ROMFS / "Layout" / "MainScreenSmartPhone.Nin_NX_NVN.zs"
    outer = sarc.read_sarc(decompress_layout_archive(archive))
    inner = sarc.read_sarc(outer["MainScreenSmartPhone.arc"])
    blob = inner["timg/__Combined.bntx"]
    tex_path = WORK / "source_textures"
    tex_path.mkdir(parents=True, exist_ok=True)
    blob_path = tex_path / "MainScreenSmartPhone.bntx"
    blob_path.write_bytes(blob)
    decoder = WORK / "texdec"
    source = ROOT / "tools" / "reference" / "acnh_rip" / "native" / "texdec.c"
    if not decoder.exists() or decoder.stat().st_mtime < source.stat().st_mtime:
        subprocess.run(["gcc", "-O2", "-o", str(decoder), str(source), "-lm"], check=True)
    jobs = []
    for t in read_bntx(blob):
        out = tex_path / (t["name"] + ".png")
        jobs.append(" ".join([str(blob_path), str(t["mip0_offset"]), str(t["mip0_size"]),
                               str(t["format"]), str(t["width"]), str(t["height"]),
                               str(t["block_height_log2"]), *map(str, t["channel_sources"]), str(out)]))
    result = subprocess.run([str(decoder)], input="\n".join(jobs) + "\n", text=True,
                            capture_output=True, check=True)
    errors = [line for line in result.stdout.splitlines() if line.startswith("ERR")]
    if errors:
        raise RuntimeError("texture decode errors: " + "; ".join(errors))
    return tex_path


def _world_transform(component, by_id):
    chain = []
    node = component
    while node is not None:
        chain.append(node)
        node = by_id.get(node.get("parent_id")) if node.get("parent_id") is not None else None
    pos = [0.0, 0.0]
    scale = [1.0, 1.0]
    angle = 0.0
    alpha = 1.0
    visible = True
    for node in reversed(chain):
        tx, ty = node.get("translate", [0.0, 0.0, 0.0])[:2]
        tx *= scale[0]
        ty *= scale[1]
        r = math.radians(angle)
        pos[0] += tx * math.cos(r) - ty * math.sin(r)
        pos[1] += tx * math.sin(r) + ty * math.cos(r)
        angle += node.get("rotate", [0.0, 0.0, 0.0])[2]
        sx, sy = node.get("scale", [1.0, 1.0])
        scale[0] *= sx
        scale[1] *= sy
        alpha *= node.get("alpha", 255) / 255.0
        visible = visible and node.get("visible", True)
    return pos, scale, angle, alpha, visible


def _material_tint(image, material, pane_alpha):
    import numpy as np
    from PIL import Image

    src = np.asarray(image.convert("RGBA"), dtype=np.float32) / 255.0
    black = np.asarray(material["black"], dtype=np.float32).reshape((1, 1, 4)) / 255.0
    white = np.asarray(material["white"], dtype=np.float32).reshape((1, 1, 4)) / 255.0
    mask = src[:, :, :3]
    rgb = black[:, :, :3] + (white[:, :, :3] - black[:, :, :3]) * mask
    alpha = black[:, :, 3] + (white[:, :, 3] - black[:, :, 3]) * src[:, :, 3]
    alpha *= pane_alpha
    out = np.concatenate((rgb, alpha[:, :, None]), axis=2)
    return Image.fromarray(np.uint8(np.clip(out * 255.0, 0, 255)), "RGBA")


def render_phone(layout, texture_dir):
    from PIL import Image, ImageDraw, ImageFont

    canvas = Image.new("RGBA", (1920, 1080), (231, 229, 210, 255))
    components = layout["components"]
    by_id = {c["id"]: c for c in components}
    textures = layout["textures"]
    materials = layout["materials"]
    for c in components:
        if c["type"] != "pic1":
            continue
        pos, scale, angle, alpha, visible = _world_transform(c, by_id)
        if not visible or alpha <= 0.001:
            continue
        mat = materials[c["material"]]
        if len(mat["texmaps"]) != 1:
            continue
        texture_name = textures[mat["texmaps"][0]["texture"]]
        path = texture_dir / (texture_name + ".png")
        if not path.exists():
            continue
        sprite = _material_tint(Image.open(path), mat, alpha)
        w = max(1, round(c["size"][0] * scale[0]))
        h = max(1, round(c["size"][1] * scale[1]))
        sprite = sprite.resize((w, h), Image.Resampling.LANCZOS)
        if angle:
            sprite = sprite.rotate(angle, resample=Image.Resampling.BICUBIC, expand=True)
        x = round(960 + pos[0] - sprite.width / 2)
        y = round(540 - pos[1] - sprite.height / 2)
        canvas.alpha_composite(sprite, (x, y))

    # The source uses a private-use controller glyph; this text is a readable label
    # derived from T_ZL_00, not the original game font rendering.
    pane = next(c for c in components if c["name"] == "T_ZL_00")
    pos, _, _, _, _ = _world_transform(pane, by_id)
    x, y = round(960 + pos[0]), round(540 - pos[1])
    draw = ImageDraw.Draw(canvas)
    font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    font = ImageFont.truetype(font_path, 16) if Path(font_path).exists() else ImageFont.load_default()
    draw.text((x, y), "ZL", font=font, anchor="mm", fill=(233, 237, 191, 255),
              stroke_width=1, stroke_fill=(65, 50, 35, 255))
    return canvas


def render_anchor_map(main_layout, phone_crop, output_path):
    from PIL import Image, ImageDraw, ImageFont

    W, H = 1680, 970
    board = Image.new("RGB", (W, H), "#f0eddd")
    d = ImageDraw.Draw(board)
    regular = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    bold = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    f_title = ImageFont.truetype(bold, 30)
    f_sub = ImageFont.truetype(regular, 16)
    f_label = ImageFont.truetype(bold, 15)
    f_small = ImageFont.truetype(regular, 13)
    d.text((42, 28), "ACNH UI/HUD • SOURCE LAYOUT PREVIEW", font=f_title, fill="#3e4939")
    d.text((44, 70), "MainScreen anchor map + decoded MainScreenSmartPhone textures", font=f_sub, fill="#697261")
    d.rounded_rectangle((34, 112, 1047, 682), 20, fill="#e4e7d6", outline="#a4ad96", width=2)
    x0, y0, sw, sh = 58, 142, 960, 540
    d.rectangle((x0, y0, x0 + sw, y0 + sh), fill="#cbd9c7", outline="#73846f", width=2)
    # A neutral grid avoids suggesting that this is an in-game island screenshot.
    for gx in range(x0 + 60, x0 + sw, 60):
        d.line((gx, y0, gx, y0 + sh), fill="#d6dfd0", width=1)
    for gy in range(y0 + 60, y0 + sh, 60):
        d.line((x0, gy, x0 + sw, gy), fill="#d6dfd0", width=1)
    d.line((x0 + sw / 2, y0, x0 + sw / 2, y0 + sh), fill="#aebda8", width=1)
    d.line((x0, y0 + sh / 2, x0 + sw, y0 + sh / 2), fill="#aebda8", width=1)
    scale = sw / 1920.0
    cx, cy = x0 + sw / 2, y0 + sh / 2
    by_id = {c["id"]: c for c in main_layout["components"]}
    anchors = []
    fixed = {"L_Bell_00", "L_GuideRoom_00", "L_Clock_00", "L_Timer_00", "L_Road_00", "L_ShareGuide_00", "L_MealEf_00"}
    palette = {"L_Bell_00": "#a57b38", "L_GuideRoom_00": "#3e7d74", "L_Clock_00": "#5c6f89",
               "L_Timer_00": "#a75f54", "L_Road_00": "#6b6097", "L_ShareGuide_00": "#647c4f", "L_MealEf_00": "#aa8a39"}
    for c in main_layout["components"]:
        if c["type"] != "prt1":
            continue
        name = c["name"]
        if name not in fixed and name not in ("L_ItemBalloon_00", "L_MsgBalloon_00", "L_StickBalloon_00", "L_MiniGameCounter_00"):
            continue
        pos, _, _, _, _ = _world_transform(c, by_id)
        px, py = cx + pos[0] * scale, cy - pos[1] * scale
        col = palette.get(name, "#777d77")
        r = 8 if name in fixed else 6
        d.ellipse((px-r, py-r, px+r, py+r), fill=col, outline="white", width=2)
        anchors.append((name, c.get("part_layout", ""), int(round(pos[0])), int(round(pos[1])), col))
        if name in fixed:
            d.text((px + 10, py - 9), name.replace("_00", ""), font=f_small, fill=col)
    d.text((x0 + 8, y0 + sh + 10), "Markers use BFLYT translations with a center-origin / Y-up display assumption.", font=f_small, fill="#5f675c")
    d.text((x0 + 8, y0 + sh + 30), "They show layout anchors, not final rendered bounds or an original game screenshot.", font=f_small, fill="#5f675c")

    # Right panel: a real BNTX-decoded overlay crop, with a stand-in for the PUA ZL glyph.
    d.rounded_rectangle((1072, 112, 1646, 682), 20, fill="#e4e7d6", outline="#a4ad96", width=2)
    d.text((1098, 132), "PHONE / ZL OVERLAY", font=f_label, fill="#3e4939")
    crop = phone_crop.crop((0, 0, 360, 230)).resize((540, 345), Image.Resampling.LANCZOS)
    board.paste(crop.convert("RGB"), (1088, 176))
    d.text((1098, 537), "Textures decoded from the original BNTX; private-use glyph shown as ‘ZL’.", font=f_small, fill="#5f675c")
    d.text((1098, 556), "Shader blending and font rasterization are approximations in this preview.", font=f_small, fill="#5f675c")

    d.rounded_rectangle((34, 708, 1646, 935), 18, fill="#f8f7ee", outline="#c5c8b7", width=2)
    d.text((58, 728), "MAPPED COMPONENTS", font=f_label, fill="#3e4939")
    lines = [
        "L_Clock_00 → LClock (time/date/week panes; native calendar update correlation at 0x1315ac0)",
        "L_Bell_00 → LTimerBell     •     L_GuideRoom_00 → LRoomGuide     •     L_Timer_00 → LTimer",
        "L_Road_00 → LRoadUseBtn     •     L_ShareGuide_00 → LShareGuide     •     L_MealEf_00 → LMealEf",
        "8 × L_ItemBalloon slots and 12 × L_MsgBalloon slots are present; exact live selection/state is still being traced.",
        "MainScreen references at 0x1214110 include PickUpFirst and STR_KeyIcon; this is a native UI correlation, not a full handler proof.",
    ]
    for i, line in enumerate(lines):
        d.text((58, 758 + i * 30), line, font=f_sub if i < 4 else f_small, fill="#4d5948")
    board.save(output_path)
    return anchors


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    WORK.mkdir(parents=True, exist_ok=True)
    layout_data = read_json(LAYOUTS_PATH)
    animation_data = read_json(ANIMATIONS_PATH)
    native_data = read_json(NATIVE_CANDIDATES_PATH)
    archive_inventory = audit_layout_archive_inventory(layout_data)
    font_bindings = build_font_bindings(layout_data)
    section_audit = audit_layout_sections()
    resource_bindings = build_resource_bindings(layout_data)
    part_ambiguities = audit_part_reference_ambiguities(layout_data)
    group_structure = build_group_structure(layout_data)
    extended_user_data = audit_extended_user_data(animation_data, section_audit)
    animation_semantics = build_animation_semantics(animation_data, section_audit, extended_user_data)
    catalog = build_catalog(layout_data, animation_data, native_data)
    mapping = build_mapping(layout_data, catalog, animation_data)
    native_bindings = build_native_bindings(native_data)
    (OUT / "screen_catalog.json").write_text(json.dumps({"schema": "acnh.ui_screen_catalog.v1",
                                                           "layout_count": len(catalog),
                                                           "archive_inventory": archive_inventory,
                                                           "layouts": catalog},
                                                          ensure_ascii=False, indent=2) + "\n")
    mapping["archive_inventory"] = {k: v for k, v in archive_inventory.items() if k != "records"}
    (OUT / "hud_mapping.json").write_text(json.dumps(mapping, ensure_ascii=False, indent=2) + "\n")
    (OUT / "native_bindings.json").write_text(json.dumps(native_bindings, ensure_ascii=False, indent=2) + "\n")
    (OUT / "font_bindings.json").write_text(json.dumps(font_bindings, ensure_ascii=False, indent=2) + "\n")
    (OUT / "section_semantics.json").write_text(json.dumps(section_audit, ensure_ascii=False, indent=2) + "\n")
    (OUT / "group_structure.json").write_text(json.dumps(group_structure, ensure_ascii=False, indent=2) + "\n")
    (OUT / "part_reference_ambiguities.json").write_text(json.dumps(part_ambiguities, ensure_ascii=False, indent=2) + "\n")
    (OUT / "resource_bindings.json").write_text(json.dumps(resource_bindings, ensure_ascii=False, indent=2) + "\n")
    (OUT / "animation_semantics.json").write_text(json.dumps(animation_semantics, ensure_ascii=False, indent=2) + "\n")
    (OUT / "extended_user_data.json").write_text(json.dumps(extended_user_data, ensure_ascii=False, indent=2) + "\n")

    by_name = {x["name"]: x for x in layout_data["layouts"]}
    texture_dir = decode_phone_textures()
    phone = render_phone(by_name["MainScreenSmartPhone"], texture_dir)
    phone.save(WORK / "MainScreenSmartPhone_layout.png")
    phone_crop = phone.crop((0, 0, 360, 230)).resize((720, 460))
    phone_crop.save(WORK / "MainScreenSmartPhone_closeup.png")
    anchors = render_anchor_map(by_name["MainScreen"], phone_crop, WORK / "HUD_layout_preview.png")
    print(json.dumps({"layout_count": len(catalog), "native_name_candidate_count": mapping["catalog_summary"]["exact_native_string_candidate_name_count"],
                      "main_screen_part_slots": len(mapping["screens"][0]["sub_layout_slots"]),
                      "smartphone_animations": len(mapping["screens"][1]["animations"]),
                      "font_references_resolved": font_bindings["counts"]["resolved_references"],
                      "usd1_sections_parsed": section_audit["counts"]["usd1_sections"],
                      "cnt1_sections_preserved": section_audit["counts"]["cnt1_sections"],
                      "materials_decoded": resource_bindings["counts"].get("materials", 0),
                      "material_texture_links": resource_bindings["counts"].get("material_texture_map_refs_with_bntx_candidate", 0),
                      "animation_tracks_mapped": animation_semantics["counts"]["tracks"],
                      "extended_user_data_records": extended_user_data["counts"]["records"],
                      "animation_target_bindings": animation_semantics["counts"]["target_binding_status_counts"],
                      "cnt1_sections_decoded": section_audit["counts"]["cnt1_sections"],
                      "ui2dsys_types_decoded": section_audit["counts"]["ui2dsys_semantic_type_counts"],
                      "bounding_scissor_panes": section_audit["counts"]["bounding_scissor_panes"],
                      "layout_animation_tag_matches": animation_semantics["counts"]["declared_tag_status_counts"],
                      "animation_unresolved_properties": animation_semantics["counts"]["unresolved_property_count"],
                      "part_ambiguities": part_ambiguities["counts"]["ambiguous_references"],
                      "part_same_suffix_candidates": part_ambiguities["counts"]["references_with_same_suffix_candidate"],
                      "group_delimiter_blocks": group_structure["counts"]["delimited_group_blocks"],
                      "group_structure_parse_errors": len(group_structure["parse_errors"]),
                      "section_parse_errors": len(section_audit["parse_errors"]),
                      "preview": str(WORK / "HUD_layout_preview.png"), "anchors": len(anchors)}, indent=2))


if __name__ == "__main__":
    main()
