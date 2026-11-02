"""Pipeline entry point.

  python3 -m acnh_rip.build <step> [<step> ...]
steps: inventory, hashdict, data, models, audio, ui, asb, all
"""
import json
import sys
import time
from collections import Counter

from .config import ROMFS, OUT


def inventory():
    c = Counter()
    for p in ROMFS.rglob("*"):
        if p.is_file():
            top = p.relative_to(ROMFS).parts[0]
            ext = ".".join(p.name.split(".")[1:]) or "(none)"
            c[(top, ext)] += 1
    rows = [{"dir": d, "ext": e, "count": n} for (d, e), n in sorted(c.items())]
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "inventory.json").write_text(json.dumps(rows, indent=1))
    return {"file_kinds": len(rows), "files": sum(c.values())}


def _ensure_gdignore():
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / ".gdignore").touch()


def main(argv):
    steps = argv or ["all"]
    if "all" in steps:
        steps = ["inventory", "hashdict", "data", "models", "audio", "ui", "asb"]
    _ensure_gdignore()
    for s in steps:
        t = time.time()
        if s == "inventory":
            r = inventory()
        elif s == "hashdict":
            from . import hashdict
            d = hashdict.build(force=True)
            r = {k: len(v) for k, v in d.items()}
        elif s == "data":
            from .exporters import data
            r = data.run()
        elif s == "models":
            from .exporters import models
            r = models.run()
        elif s == "audio":
            from .exporters import audio
            r = audio.run()
        elif s == "ui":
            from .exporters import ui
            r = ui.run()
        elif s == "asb":
            from .exporters import asb
            r = asb.run()
        else:
            raise SystemExit(f"unknown step {s}")
        print(f"[{s}] {r} ({time.time() - t:.1f}s)", flush=True)


if __name__ == "__main__":
    main(sys.argv[1:])
