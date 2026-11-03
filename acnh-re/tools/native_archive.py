"""Original native SARC reader and ready-resource context helpers.

No native function is replaced. Ready handle/RTTI state is reconstructed;
file-system loading, async jobs, allocation and SDK startup are not executed.
"""
from pathlib import Path
import hashlib
import json
import struct
from native_emulator import Sandbox
from native_sdk_memory import install_sdk_memory

ROOT = Path(__file__).resolve().parent.parent


def initialize_resource_types(s):
    cells = [(0x32d4b38, 0x32d4b40, 0x32d4b48),
             (0x32d4b50, 0x32d4b58, 0x32d0ee8),
             (0x32d0ed8, 0x32d0ee0, 0x32d0ee8),
             (0x32d0e68, 0x32d0e70, 0x32d0e88),
             (0x32d0e20, 0x32d0e28, 0x32d0e60),
             (0x32d0ec8, 0x32d0ed0, 0x32d0520)]
    for flag, obj, vt in cells:
        s.uc.mem_write(s.image.ptr(flag), b'\x01')
        s.uc.mem_write(s.image.ptr(obj), struct.pack('<Q', s.image.ptr(vt)+16))
    return [{'guard_got': hex(a), 'object_got': hex(b), 'vtable_got': hex(c)} for a, b, c in cells]


def make_sarc(files, endian='<'):
    def hash_name(name):
        value = 0
        for byte in name.encode('utf-8'): value = (value*101+byte) & 0xffffffff
        return value
    names = bytearray(); data = bytearray(); nodes = []; offsets = {}
    for name, payload in sorted(files.items(), key=lambda p: hash_name(p[0])):
        name_word = len(names)//4
        names.extend(name.encode('utf-8')+b'\0'); names.extend(bytes(-len(names) % 4))
        start = len(data); data.extend(payload); end = len(data); data.extend(bytes(-len(data) % 4))
        nodes.append((hash_name(name), 0x1000000 | name_word, start, end))
        offsets[name] = {'offset': start, 'size': len(payload)}
    prefix = 20+12+16*len(nodes)+8+len(names); data_offset = (prefix+31) & ~31
    result = bytearray(struct.pack(endian+'4sHHIIHH', b'SARC', 20, 0xfeff, data_offset+len(data), data_offset, 0x100, 0))
    result.extend(struct.pack(endian+'4sHHI', b'SFAT', 12, len(nodes), 101))
    result.extend(b''.join(struct.pack(endian+'4I', *node) for node in nodes))
    result.extend(struct.pack(endian+'4sHH', b'SFNT', 8, 0)); result.extend(names)
    result.extend(bytes(data_offset-len(result))); result.extend(data)
    for row in offsets.values(): row['offset'] += data_offset
    return bytes(result), offsets


def open_native_archive(s, archive, blob, raw):
    s.uc.mem_write(blob-16, b'\xa5'*16+raw+b'\xa5'*16)
    s.call(0x199a580, (archive,), limit=10000)
    assert struct.unpack('<Q', s.uc.mem_read(archive, 8))[0] == 0x31a63c8
    return s.call(0x199a610, (archive, blob, len(raw)), limit=10000)


def install_ready_archive(s, record, block, raw):
    unit, resource, wrapper, archive, blob = [block+n for n in (0x1000, 0x2000, 0x3000, 0x4000, 0x8000)]
    def q(p, v): s.uc.mem_write(p, struct.pack('<Q', v))
    def d(p, v): s.uc.mem_write(p, struct.pack('<I', v))
    s.uc.mem_write(block, bytes(0x8000))
    assert open_native_archive(s, archive, blob, raw) == 1
    q(resource, s.image.ptr(0x32d4b30)+16)
    assert s.image.ptr(s.image.ptr(0x32d4b30)+16) == 0xb3660
    q(resource+0x30, wrapper); q(wrapper, archive)
    d(unit+0x108, 1); d(unit+0x10, 14); q(unit+0x30, resource)
    s.uc.mem_write(record, bytes(72)); s.uc.mem_write(record+0x18, b'\x0a'); q(record+0x20, unit)
    assert s.call(0xc69e0, (record,), limit=10000) == wrapper
    return {'unit': unit, 'resource': resource, 'wrapper': wrapper, 'archive': archive,
            'blob': blob, 'raw': raw, 'record': record}


def main():
    s = Sandbox(); u = s.uc; sdk = install_sdk_memory(s); type_cells = initialize_resource_types(s)
    u.mem_map(0x52000000, 0x600000)
    archive, blob, wrapper, string, name, size_out = [s.HEAP+n for n in (0x10000, 0x20000, 0x30000, 0x40000, 0x41000, 0x42000)]
    blob = 0x52000010
    u.mem_write(wrapper, struct.pack('<Q', archive))
    u.mem_write(string, struct.pack('<2Q', s.image.ptr(0x32d0668)+16, name))
    manifest = json.loads((ROOT/'output/manifest.json').read_text())['entries']
    groups = {'source_archive_open': 0, 'source_member_lookup': 0, 'source_missing_name': 0,
              'synthetic_endian_lookup': 0}; sources = []
    def lookup(filename):
        u.mem_write(name, filename.encode('utf-8')+b'\0'); u.mem_write(size_out, b'\xa5'*8)
        ptr = s.call(0x1c84e50, (wrapper, string, size_out), limit=20000)
        return ptr, struct.unpack('<I', u.mem_read(size_out, 4))[0]
    for entry in [e for e in manifest if e.get('format') == 'SARC']:
        raw = (ROOT/'output'/entry['raw']['$blob']).read_bytes()
        assert open_native_archive(s, archive, blob, raw) == 1
        groups['source_archive_open'] += 1
        members = [e for e in manifest if e.get('parent_id') == entry['id']]
        assert len(members) == entry['metadata']['member_count']
        for member in members:
            filename = member['source'].rsplit('!', 1)[-1]
            ptr, size = lookup(filename)
            assert ptr == blob+member['member']['offset'] and size == member['size'], (filename, ptr, size)
            assert hashlib.sha256(u.mem_read(ptr, size)).hexdigest() == member['sha256']
            groups['source_member_lookup'] += 1
        ptr, size = lookup('__RE_missing_member__.pbc'); assert ptr == 0
        groups['source_missing_name'] += 1
        assert bytes(u.mem_read(blob-16, len(raw)+32)) == b'\xa5'*16+raw+b'\xa5'*16
        sources.append({'source_id': entry['id'], 'source': entry['source'], 'raw': entry['raw'],
                        'native_members_read': len(members), 'member_offsets_sizes_sha256_match': True})
    for endian in ['<', '>']:
        files = {'floor_6x6.pbc': bytes(range(73)), 'deep/path/8x8.pbc': b'test-map', 'empty.bin': b''}
        raw, offsets = make_sarc(files, endian)
        assert open_native_archive(s, archive, blob, raw) == 1
        for filename, payload in files.items():
            ptr, size = lookup(filename)
            assert ptr == blob+offsets[filename]['offset'] and size == len(payload)
            assert bytes(u.mem_read(ptr, size)) == payload
            groups['synthetic_endian_lookup'] += 1
    result = {'groups': groups, 'cases': sum(groups.values()), 'mismatches': [],
              'sources': sources, 'native_functions': ['0x199a580', '0x199a610', '0x1c84e50', '0x1f05d90',
                                                      'original archive vtable lookup/index/data routines'],
              'archive_vtable': '0x31a63c8', 'rtti_cells_reconstructed': type_cells,
              'sdk': sdk, 'dependencies_stubbed': [],
              'scope': 'Original native SARC constructor, parser and filename lookup on all3 supplied SARC containers and all1813 members, plus synthetic little/big-endian containers.',
              'limits': ['No filesystem, decompression or asynchronous resource loader is executed.',
                         'Malformed-file safety is not inferred from valid-source checks.',
                         'Ready RTTI state and archive wrapper are reconstructed; SDK startup is not executed.'],
              'elf_sha256': hashlib.sha256(s.image.data).hexdigest()}
    (ROOT/'output/mechanics/native_archive_verification.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({'groups': groups, 'cases': result['cases'], 'mismatches': 0}), flush=True)


if __name__ == '__main__': main()
