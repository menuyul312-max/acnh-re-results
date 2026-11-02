"""Phase 6a: audio.

  generated/audio/stream/<name>.ogg   every Sound/Resource/Stream/*.bwav (BGM, radio, ...)
  generated/audio/sfx/<bars>/<name>.ogg  every BWAV embedded in Sound/Resource/*.bars,
                                       named by its AMTA string (not regex guesses)
  generated/audio/index.json          name -> {file, rate, channels, samples, loop, loop_start, loop_end}

Loop points are kept in samples exactly as stored in the BWAV channel info; the
Godot side sets AudioStreamOggVorbis.loop / loop_offset from them.
"""
import json
import struct
import subprocess
import tempfile
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from ..config import ROMFS, OUT, NATIVE_DIR

AUDIO = OUT / "audio"
BWAVDEC = NATIVE_DIR / "bwavdec"


def _build():
    src = NATIVE_DIR / "bwavdec.c"
    if not BWAVDEC.exists() or BWAVDEC.stat().st_mtime < src.stat().st_mtime:
        subprocess.run(["gcc", "-O2", "-o", str(BWAVDEC), str(src)], check=True)


def _convert(src_file: Path, offset: int, out_ogg: Path):
    out_ogg.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as td:
        wav = os.path.join(td, "a.wav")
        r = subprocess.run([str(BWAVDEC), str(src_file), str(offset), wav], capture_output=True, text=True)
        line = r.stdout.strip()
        if not line.startswith("META"):
            return {"error": line or r.stderr}
        nch, rate, ns, codec, loop, ls, le = map(int, line.split()[1:])
        if not out_ogg.exists():
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", wav, "-c:a", "libvorbis", "-q:a", "6",
                            str(out_ogg)], check=True)
    return {"file": str(out_ogg.relative_to(AUDIO)), "channels": nch, "rate": rate, "samples": ns,
            "codec": ["pcm16", "dsp_adpcm"][codec], "loop": bool(loop), "loop_start": ls, "loop_end": le}


def _bars_entries(path: Path):
    d = path.read_bytes()
    if d[:4] != b"BARS":
        return []
    cnt = struct.unpack_from("<I", d, 0x0C)[0]
    out = []
    for i in range(cnt):
        amta, bwav = struct.unpack_from("<II", d, 0x10 + cnt * 4 + i * 8)
        name = None
        if d[amta:amta + 4] == b"AMTA":
            p = amta + 0x24 + struct.unpack_from("<I", d, amta + 0x24)[0]
            name = d[p:d.index(b"\0", p)].decode("utf-8", "replace")
        if bwav < len(d) and d[bwav:bwav + 4] == b"BWAV":
            out.append((name or f"{path.stem}_{i}", bwav))
    return out


def run(workers=2):
    _build()
    index = {"stream": {}, "sfx": {}}
    jobs = []
    for p in sorted((ROMFS / "Sound/Resource/Stream").glob("*.bwav")):
        jobs.append(("stream", p.stem, p, 0, AUDIO / "stream" / f"{p.stem}.ogg"))
    for p in sorted((ROMFS / "Sound/Resource").glob("*.bars")):
        for name, off in _bars_entries(p):
            jobs.append(("sfx", f"{p.stem}/{name}", p, off, AUDIO / "sfx" / p.stem / f"{name}.ogg"))
    with ThreadPoolExecutor(max_workers=workers) as ex:
        results = list(ex.map(lambda j: (j, _convert(j[2], j[3], j[4])), jobs))
    errors = []
    for (kind, key, src, off, _), meta in results:
        meta["source"] = str(src.relative_to(ROMFS))
        index[kind][key] = meta
        if "error" in meta:
            errors.append(key)
    AUDIO.mkdir(parents=True, exist_ok=True)
    (AUDIO / "index.json").write_text(json.dumps(index, indent=0, ensure_ascii=False))
    for t in ("BgmPropertyParam", "BgmPropertyControlParam", "SoundAudioMusic"):
        f = OUT / "data/bcsv" / f"{t}.json"
        if f.exists():
            (AUDIO / f"{t}.json").write_text(f.read_text())
    return {"streams": len(index["stream"]), "sfx": len(index["sfx"]), "errors": len(errors)}
