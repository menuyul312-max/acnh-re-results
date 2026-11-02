#!/usr/bin/env python3
"""Regenerate EventFlow native links in a separate RE workspace."""
import os
from pathlib import Path
import sys

root = Path(__file__).resolve().parent.parent
source = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('/workspace/downloads/ACNH_island_RE/ACNH_island_RE')
os.environ.update(ACNH_ROMFS=str(source / 'B_data'), ACNH_EXEFS=str(source / 'A_logic'),
                  ACNH_OUT=str(root / 'work'), PYTHONDONTWRITEBYTECODE='1')
sys.path.insert(0, str(root / 'tools/reference'))
from acnh_rip.exporters import eventflow
from acnh_rip.re import evfl_handlers, evfl_vtables

if __name__ == '__main__':
    (root / 'work/re').mkdir(parents=True, exist_ok=True)
    for name, module in [('eventflow', eventflow), ('factories', evfl_handlers), ('vtables', evfl_vtables)]:
        print(name, module.run(), flush=True)
