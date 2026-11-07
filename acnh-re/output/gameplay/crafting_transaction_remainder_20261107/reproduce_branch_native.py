#!/usr/bin/env python3
"""Re-run the bounded original-ELF transaction branch probe into this directory.

The existing probe writes to the older follow-up directory by default. This
wrapper changes only that output path, so the original artifact is preserved.
"""
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[4]
TOOLS = REPO / "acnh-re" / "tools"
sys.path.insert(0, str(TOOLS))
sys.dont_write_bytecode = True

import crafting_transaction_branch_native as probe  # noqa: E402

probe.OUT = Path(__file__).resolve().parent
probe.main()
