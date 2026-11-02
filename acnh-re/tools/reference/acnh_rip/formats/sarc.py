"""SARC archive reader (little endian, as used by ACNH)."""
import struct


class SarcError(ValueError):
    pass


def read_sarc(data: bytes) -> dict:
    """Return {name: bytes}. Unnamed nodes are keyed by their hash."""
    if data[:4] != b"SARC":
        raise SarcError("not a SARC")
    hdr_size, bom = struct.unpack_from("<HH", data, 4)
    if bom != 0xFEFF:
        raise SarcError("big-endian SARC not supported")
    data_off = struct.unpack_from("<I", data, 0xC)[0]
    sfat = hdr_size
    if data[sfat:sfat + 4] != b"SFAT":
        raise SarcError("missing SFAT")
    sfat_hdr, node_count, hash_key = struct.unpack_from("<HHI", data, sfat + 4)
    nodes_off = sfat + sfat_hdr
    sfnt = nodes_off + node_count * 16
    if data[sfnt:sfnt + 4] != b"SFNT":
        raise SarcError("missing SFNT")
    names_off = sfnt + struct.unpack_from("<H", data, sfnt + 4)[0]
    out = {}
    for i in range(node_count):
        h, attr, start, end = struct.unpack_from("<IIII", data, nodes_off + i * 16)
        if attr & 0x01000000:
            p = names_off + (attr & 0xFFFF) * 4
            name = data[p:data.index(b"\0", p)].decode("utf-8")
        else:
            name = f"{h:08x}"
        out[name] = data[data_off + start:data_off + end]
    return out
