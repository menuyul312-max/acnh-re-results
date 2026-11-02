"""Phase 6b: UI layouts and fonts.

  generated/ui/<Archive>/<layout>.json      BFLYT pane tree (see formats/bflyt.py)
  generated/ui/<Archive>/anim/<name>.json   BFLAN header + raw sections
  generated/ui/<Archive>/tex/<name>.png     layout textures (BNTX in the archive)
  generated/fonts/*.ttf|otf                 decoded BFTTF/BFOTF scalable fonts
  generated/fonts/bitmap/*.bffnt            bitmap fonts copied verbatim (not yet converted)
  generated/fonts/FontInfo.json             font assignment table from Font/FontInfo
"""
import json
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from ..config import ROMFS, OUT
from ..formats import sarc, compression, bflyt, bfttf, byml
from .models import _decode_textures, _build_texdec

UI = OUT / "ui"
FONTS = OUT / "fonts"


def convert_layout(path):
    path = Path(path)
    arch = path.name.split(".")[0]
    out = UI / arch
    man = {"source": str(path.relative_to(ROMFS)), "layouts": [], "anims": [], "textures": [], "errors": []}
    try:
        outer = sarc.read_sarc(compression.read_file(path))
    except Exception as e:
        man["errors"].append(f"archive: {e}")
        return arch, man
    for _, inner_b in outer.items():
        if inner_b[:4] != b"SARC":
            continue
        for name, b in sarc.read_sarc(inner_b).items():
            stem = Path(name).stem
            try:
                if name.endswith(".bflyt"):
                    out.mkdir(parents=True, exist_ok=True)
                    (out / f"{stem}.json").write_text(json.dumps(bflyt.read_bflyt(b), ensure_ascii=False,
                                                                 separators=(",", ":")))
                    man["layouts"].append(stem)
                elif name.endswith(".bflan"):
                    (out / "anim").mkdir(parents=True, exist_ok=True)
                    (out / "anim" / f"{stem}.json").write_text(json.dumps(bflyt.read_bflan_summary(b)))
                    man["anims"].append(stem)
                elif name.endswith(".bntx"):
                    _decode_textures(b, out / "tex", man)
            except Exception as e:
                man["errors"].append(f"{name}: {e!r}")
    if man["layouts"] or man["textures"]:
        out.mkdir(parents=True, exist_ok=True)
        (out / "manifest.json").write_text(json.dumps(man, indent=1))
    return arch, man


def export_fonts():
    FONTS.mkdir(parents=True, exist_ok=True)
    n = 0
    for p in sorted((ROMFS / "Font").glob("*.sarc.zs")):
        for name, b in sarc.read_sarc(compression.read_file(p)).items():
            if name.endswith((".bfttf", ".bfotf")):
                body, ext = bfttf.decode(b)
                (FONTS / (Path(name).stem + ext)).write_bytes(body)
                n += 1
            elif name.endswith(".bffnt"):
                (FONTS / "bitmap" / p.name.split(".")[0]).mkdir(parents=True, exist_ok=True)
                (FONTS / "bitmap" / p.name.split(".")[0] / name).write_bytes(b)
            elif name.endswith(".byml"):
                (FONTS / "FontInfo.json").write_text(json.dumps(byml.read_byml(b)["root"], ensure_ascii=False,
                                                                indent=1))
    return n


def run(workers=2):
    _build_texdec()
    nfont = export_fonts()
    paths = sorted(p for p in (ROMFS / "Layout").iterdir() if p.is_file())
    stats = {"archives": 0, "layouts": 0, "anims": 0, "textures": 0, "errors": 0}
    with ProcessPoolExecutor(max_workers=workers) as ex:
        for arch, man in ex.map(convert_layout, map(str, paths), chunksize=16):
            stats["archives"] += 1
            stats["layouts"] += len(man["layouts"])
            stats["anims"] += len(man["anims"])
            stats["textures"] += len(man["textures"])
            stats["errors"] += len(man["errors"])
    stats["fonts"] = nfont
    (UI / "_report.json").write_text(json.dumps(stats, indent=1))
    return stats
