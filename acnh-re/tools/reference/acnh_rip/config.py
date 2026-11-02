"""Paths used by the pipeline. Override with ACNH_ROMFS / ACNH_EXEFS / ACNH_OUT."""
import os
from pathlib import Path

PKG_DIR = Path(__file__).resolve().parent
GODOT_DIR = PKG_DIR.parent.parent
WORKSPACE = GODOT_DIR.parent

ROMFS = Path(os.environ.get("ACNH_ROMFS", WORKSPACE / "extracted_romfs"))
EXEFS = Path(os.environ.get("ACNH_EXEFS", WORKSPACE / "extracted_nsp" / "exefs"))
# Generated output lives inside the Godot project but is .gdignore'd and loaded
# at runtime (GLTFDocument / JSON / Ogg) so the editor never imports 37k files.
OUT = Path(os.environ.get("ACNH_OUT", GODOT_DIR / "generated"))
CACHE = Path(os.environ.get("ACNH_CACHE", OUT / ".cache"))

NATIVE_DIR = PKG_DIR / "native"
