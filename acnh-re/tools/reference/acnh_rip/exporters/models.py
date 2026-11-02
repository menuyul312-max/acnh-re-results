"""Phase 3/4: every Model/*.zs|*.szs archive -> glb + textures + animations.

Output (generated/models/<Archive>/):
  <Model>.glb            skeleton, skin, meshes (LOD0), materials (FMAT in extras)
  tex/<texture>.png      decoded BNTX textures (.hdr for BC6H)
  anim/<Anim>.json       sampled skeletal animations (per bone t/r/s per frame)
  <file>.phive           collision data copied verbatim (not yet parsed)
  manifest.json          what was produced and any errors
generated/models/_texture_index.json  texture name -> [paths]   (cross-archive lookup)
generated/models/_report.json         totals and failures
"""
import json
import os
import subprocess
import sys
import tempfile
import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from ..config import ROMFS, OUT, NATIVE_DIR
from ..formats import sarc, compression, bfres, bfres_anim, bntx
from . import gltf

MODELS = OUT / "models"
TEXDEC = NATIVE_DIR / "texdec"


def _build_texdec():
    src = NATIVE_DIR / "texdec.c"
    deps = [src, NATIVE_DIR / "astc.h"]
    if not TEXDEC.exists() or TEXDEC.stat().st_mtime < max(d.stat().st_mtime for d in deps):
        subprocess.run(["gcc", "-O2", "-o", str(TEXDEC), str(src), "-lm"], check=True)


def _decode_textures(bntx_bytes, out_dir: Path, manifest):
    texs = bntx.read_bntx(bntx_bytes)
    if not texs:
        return {}
    out_dir.mkdir(parents=True, exist_ok=True)
    produced = {}
    with tempfile.NamedTemporaryFile(suffix=".bntx", delete=False) as tf:
        tf.write(bntx_bytes)
        blob = tf.name
    try:
        jobs = []
        for t in texs:
            ext = ".hdr" if t["format"] >> 8 == 0x1F else ".png"
            safe = t["name"].replace("/", "_")
            path = out_dir / (safe + ext)
            produced[t["name"]] = path
            jobs.append(f"{blob} {t['mip0_offset']} {t['mip0_size']} {t['format']} {t['width']} {t['height']} "
                        f"{t['block_height_log2']} {' '.join(map(str, t['channel_sources']))} {path}")
            manifest["textures"].append({k: t[k] for k in ("name", "format_name", "width", "height",
                                                           "mip_count", "array_count", "channel_sources")})
        res = subprocess.run([str(TEXDEC)], input="\n".join(jobs) + "\n", capture_output=True, text=True)
        for line in res.stdout.splitlines():
            if line.startswith("ERR"):
                manifest["errors"].append("texture " + line)
                produced = {k: v for k, v in produced.items() if str(v) not in line}
    finally:
        os.unlink(blob)
    return produced


def convert_archive(path: str):
    path = Path(path)
    arch = path.name.split(".")[0]
    out = MODELS / arch
    manifest = {"source": str(path.relative_to(ROMFS)), "models": [], "textures": [], "anims": [],
                "collision": [], "errors": []}
    try:
        files = sarc.read_sarc(compression.read_file(path))
    except Exception as e:  # not an archive of models (rare)
        manifest["errors"].append(f"archive: {e}")
        return arch, manifest
    out.mkdir(parents=True, exist_ok=True)
    for fname, data in files.items():
        if fname.endswith(".phive") or data[:4] == b"SARC" and fname.endswith("phive"):
            (out / fname).write_bytes(data)
            manifest["collision"].append(fname)
            continue
        if data[:4] != b"FRES":
            continue
        try:
            bf = bfres.Bfres(data)
        except Exception as e:
            manifest["errors"].append(f"{fname}: {e}")
            continue
        produced = {}
        for en, eb in bf.external_files().items():
            if eb[:4] == b"BNTX":
                try:
                    produced.update(_decode_textures(eb, out / "tex", manifest))
                except Exception as e:
                    manifest["errors"].append(f"bntx {en}: {e}")

        def uri(name):
            p = produced.get(name)
            return f"tex/{p.name}" if p else None

        try:
            for m in bf.models():
                stats = gltf.export_model(bf, m, out / f"{m['name']}.glb", uri)
                missing = sorted({t for mat in m["materials"] for t in mat["textures"]} - set(produced))
                manifest["models"].append({"name": m["name"], **stats, "external_textures": missing})
        except Exception as e:
            manifest["errors"].append(f"model {fname}: {e!r} {traceback.format_exc(limit=2)}")
        if bf.counts["skeletal_anim"]:
            try:
                (out / "anim").mkdir(exist_ok=True)
                for a in bf.skeletal_anims():
                    data = {"name": a["name"], "loop": a["loop"], "frame_count": a["frame_count"],
                            "flags": a["flags"], "bones": bfres_anim.sample(a)}
                    (out / "anim" / f"{a['name']}.json").write_text(json.dumps(data, separators=(",", ":")))
                    manifest["anims"].append(a["name"])
            except Exception as e:
                manifest["errors"].append(f"anim {fname}: {e!r}")
        other = {k: v for k, v in bf.counts.items() if v and k not in ("model", "skeletal_anim", "external")}
        if other:
            manifest.setdefault("unconverted_sections", {}).update(other)
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1, ensure_ascii=False))
    return arch, manifest


def run(pattern="*", workers=2, skip_existing=True):
    _build_texdec()
    MODELS.mkdir(parents=True, exist_ok=True)
    paths = sorted(p for p in (ROMFS / "Model").glob(pattern + ".Nin_NX_NVN.*") if p.suffix in (".zs", ".szs"))
    if skip_existing:
        paths = [p for p in paths if not (MODELS / p.name.split(".")[0] / "manifest.json").exists()]
    done = 0
    with ProcessPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(convert_archive, str(p)) for p in paths]
        for f in as_completed(futs):
            done += 1
            if done % 200 == 0:
                print(f"  {done}/{len(paths)}", flush=True)
    return finalize()


def finalize():
    index, report = {}, {"archives": 0, "models": 0, "textures": 0, "anims": 0, "with_errors": [],
                         "unconverted_sections": {}}
    for mf in sorted(MODELS.glob("*/manifest.json")):
        m = json.loads(mf.read_text())
        arch = mf.parent.name
        report["archives"] += 1
        report["models"] += len(m["models"])
        report["anims"] += len(m["anims"])
        for t in m["textures"]:
            report["textures"] += 1
            index.setdefault(t["name"], []).append(f"{arch}/tex/{t['name']}")
        for k, v in m.get("unconverted_sections", {}).items():
            report["unconverted_sections"][k] = report["unconverted_sections"].get(k, 0) + v
        if m["errors"]:
            report["with_errors"].append({"archive": arch, "errors": m["errors"][:3]})
    (MODELS / "_texture_index.json").write_text(json.dumps(index, separators=(",", ":")))
    (MODELS / "_report.json").write_text(json.dumps(report, indent=1))
    return {k: (len(v) if isinstance(v, list) else v) for k, v in report.items()}


if __name__ == "__main__":
    print(run(*(sys.argv[1:2] or ["*"])))
