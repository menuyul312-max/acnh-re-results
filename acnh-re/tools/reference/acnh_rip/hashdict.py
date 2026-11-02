"""Name dictionary for hashed identifiers.

ACNH hashes BCSV column names as CRC32("<Name> <type>") and BYML dictionary
keys as CRC32("<Name>") (both verified against strings in main.elf). The game
code compares hashes directly, so many names never appear as text anywhere in
the dump; those stay as h_XXXXXXXX and are never guessed.
"""
import json
import re
import zlib
from pathlib import Path

from .config import EXEFS, ROMFS, CACHE

BCSV_TYPES = ("u8", "s8", "u16", "s16", "u32", "s32", "u64", "s64", "f32", "f64", "string", "bool")
_CACHE_FILE = CACHE / "hashdict.json"
_EXTRA_FILE = Path(__file__).resolve().parent / "hashdict_extra.txt"


def crc32(s: str) -> int:
    return zlib.crc32(s.encode("utf-8"))


def _candidate_words():
    words = set()
    data = (EXEFS / "main.elf").read_bytes()
    for m in re.findall(rb"[\x20-\x7e]{2,96}", data):
        s = m.decode("latin1")
        words.add(s)
        words.update(re.findall(r"[A-Za-z_][A-Za-z0-9_]{1,63}", s))
        # sead enums are one "A,B,C," string; labels may be a single character
        # (fish shadow "SS,S,M,L,LL,LLL,U,J,K," and levels ",2,3,4,").
        if "," in s:
            words.update(t.strip() for t in s.split(",") if t.strip())
    # File stems in RomFS are identifiers too (model names, flow names, ...).
    for p in ROMFS.rglob("*"):
        if p.is_file():
            words.add(p.name.split(".")[0])
    if _EXTRA_FILE.exists():
        for line in _EXTRA_FILE.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                words.add(line)
    return words


def build(force=False) -> dict:
    """Return {"plain": {hash: name}, "typed": {hash: "name type"}}."""
    if _CACHE_FILE.exists() and not force:
        raw = json.loads(_CACHE_FILE.read_text())
        return {k: {int(h): n for h, n in v.items()} for k, v in raw.items()}
    plain, typed = {}, {}
    for w in _candidate_words():
        plain.setdefault(crc32(w), w)
        for t in BCSV_TYPES:
            typed.setdefault(crc32(f"{w} {t}"), f"{w} {t}")
    CACHE.mkdir(parents=True, exist_ok=True)
    _CACHE_FILE.write_text(json.dumps({"plain": plain, "typed": typed}))
    return {"plain": plain, "typed": typed}


_DICT = None


def get() -> dict:
    global _DICT
    if _DICT is None:
        _DICT = build()
    return _DICT


def name_plain(h: int) -> str:
    return get()["plain"].get(h, f"h_{h:08x}")


def name_typed(h: int):
    """Return (name, type) or (None, None) when unknown."""
    s = get()["typed"].get(h)
    if s is None:
        return None, None
    n, t = s.rsplit(" ", 1)
    return n, t
