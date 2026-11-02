"""Container decompression: zstd (.zs) and Yaz0 (.szs)."""
import subprocess
import tempfile
import os
from pathlib import Path

from ..config import NATIVE_DIR

_YAZ0_BIN = NATIVE_DIR / "yaz0dec"


def _build_native():
    src = NATIVE_DIR / "yaz0dec.c"
    if not _YAZ0_BIN.exists() or _YAZ0_BIN.stat().st_mtime < src.stat().st_mtime:
        subprocess.run(["gcc", "-O2", "-o", str(_YAZ0_BIN), str(src)], check=True)


def zstd_decompress(data: bytes) -> bytes:
    res = subprocess.run(["zstd", "-dc"], input=data, capture_output=True)
    if res.returncode != 0:
        raise ValueError("zstd failed: " + res.stderr.decode(errors="replace"))
    return res.stdout


def yaz0_decompress(data: bytes) -> bytes:
    _build_native()
    with tempfile.TemporaryDirectory() as td:
        i, o = os.path.join(td, "in"), os.path.join(td, "out")
        with open(i, "wb") as f:
            f.write(data)
        subprocess.run([str(_YAZ0_BIN), i, o], check=True)
        with open(o, "rb") as f:
            return f.read()


ZSTD_MAGIC = b"\x28\xb5\x2f\xfd"


def decompress(data: bytes) -> bytes:
    """Decompress by magic; returns data unchanged when not compressed."""
    if data[:4] == b"Yaz0":
        return yaz0_decompress(data)
    if data[:4] == ZSTD_MAGIC:
        return zstd_decompress(data)
    return data


def read_file(path) -> bytes:
    return decompress(Path(path).read_bytes())
