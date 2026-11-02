"""BNTX texture container reader (follows header pointers, no magic scanning).

BRTI fields (offsets inside the BRTI block):
  0x10 u8 flags  0x11 u8 dim  0x12 u16 tile_mode  0x14 u16 swizzle  0x16 u16 mip_count
  0x18 u32 sample_count  0x1C u32 format  0x24 u32 width  0x28 u32 height
  0x2C u32 depth  0x30 u32 array_count  0x34 u32 layout (low 3 bits = block height log2)
  0x50 u32 image_size  0x58 u8[4] channel sources  0x60 name  0x70 mip offset table
"""
import struct

FORMAT_NAMES = {0x02: "R8", 0x07: "R5G6B5", 0x09: "R8G8", 0x0B: "R8G8B8A8", 0x0C: "B8G8R8A8",
                0x0E: "R10G10B10A2", 0x1A: "BC1", 0x1B: "BC2", 0x1C: "BC3", 0x1D: "BC4",
                0x1E: "BC5", 0x1F: "BC6H", 0x20: "BC7"}
VARIANTS = {0x01: "UNORM", 0x02: "SNORM", 0x05: "FLOAT", 0x06: "SRGB", 0x0A: "UFLOAT"}
_ASTC = ["4x4", "5x4", "5x5", "6x5", "6x6", "8x5", "8x6", "8x8", "10x5", "10x6", "10x8", "10x10", "12x10", "12x12"]


def format_name(fmt):
    t, v = fmt >> 8, fmt & 0xFF
    n = FORMAT_NAMES.get(t) or (f"ASTC_{_ASTC[t - 0x2D]}" if 0x2D <= t <= 0x3A else f"0x{t:02x}")
    return f"{n}_{VARIANTS.get(v, hex(v))}"


def read_bntx(data: bytes):
    if data[:4] != b"BNTX":
        raise ValueError("not BNTX")
    count = struct.unpack_from("<I", data, 0x24)[0]
    arr = struct.unpack_from("<Q", data, 0x28)[0]
    out = []
    for i in range(count):
        t = struct.unpack_from("<Q", data, arr + i * 8)[0]
        if data[t:t + 4] != b"BRTI":
            raise ValueError("BRTI expected")
        mips = struct.unpack_from("<H", data, t + 0x16)[0]
        fmt = struct.unpack_from("<I", data, t + 0x1C)[0]
        w, h, d, arrc, layout = struct.unpack_from("<IIIII", data, t + 0x24)
        img_size = struct.unpack_from("<I", data, t + 0x50)[0]
        sw = list(data[t + 0x58:t + 0x5C])
        nptr = struct.unpack_from("<Q", data, t + 0x60)[0]
        nlen = struct.unpack_from("<H", data, nptr)[0]
        name = data[nptr + 2:nptr + 2 + nlen].decode("utf-8")
        mip_tab = struct.unpack_from("<Q", data, t + 0x70)[0]
        mip_offs = [struct.unpack_from("<Q", data, mip_tab + k * 8)[0] for k in range(mips)]
        # mip0 size: up to the next mip, or the whole image for single-mip textures
        mip0_size = (mip_offs[1] - mip_offs[0]) if mips > 1 else img_size // max(arrc, 1)
        out.append({"name": name, "format": fmt, "format_name": format_name(fmt), "width": w,
                    "height": h, "depth": d, "array_count": arrc, "mip_count": mips,
                    "block_height_log2": layout & 7, "channel_sources": sw, "dim": data[t + 0x11],
                    "mip0_offset": mip_offs[0], "mip0_size": mip0_size, "image_size": img_size})
    return out
