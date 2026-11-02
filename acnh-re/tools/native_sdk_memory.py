"""Bind original SDK memory/string routines through the main import GOT.

Only self-contained routines used by these isolated tests are supported. This
does not initialize the SDK, resolve every import or implement console services.
"""
from pathlib import Path
import hashlib
import itertools
import json
import struct
from exefs_modules import NsoModule, DEFAULT_INPUT
from native_emulator import Sandbox

ROOT = Path(__file__).resolve().parent.parent
SDK_BASE = 0x70000000


def install_sdk_memory(s, names=('memcpy', 'memset', 'strcmp')):
    sdk = NsoModule((DEFAULT_INPUT/'sdk').read_bytes())
    expected = json.loads((ROOT/'output/native_modules/sdk.json').read_text())['input_sha256']
    assert hashlib.sha256(sdk.raw).hexdigest() == expected
    text = sdk.segments[0]
    assert text['name'] == 'text'
    start = (SDK_BASE+text['va']) & ~4095
    end = (SDK_BASE+text['va']+text['size']+4095) & ~4095
    s.uc.mem_map(start, end-start)
    s.uc.mem_write(SDK_BASE+text['va'], text['data'])
    bindings = json.loads((ROOT/'output/native_modules/import_resolution.json').read_text())['main']['bindings']
    resolved = {}
    for name in names:
        symbol = next(x for x in sdk.symbols if x['name'] == name and x['section'])
        binding = next(x for x in bindings if x['symbol']['name'] == name)
        address = SDK_BASE+int(symbol['va'], 16)
        for relocation in binding['relocations']:
            assert relocation['type'] == 1026
            s.uc.mem_write(int(relocation['site'], 16), struct.pack('<Q', address))
        resolved[name] = {'module_va': symbol['va'], 'emulated_va': hex(address),
                          'main_got_sites': [x['site'] for x in binding['relocations']]}
    return {'module': 'sdk', 'module_sha256': expected, 'build_id': sdk.build_id,
            'base': hex(SDK_BASE), 'bindings': resolved,
            'scope': 'Original SDK text; main GOT import relocation only. No instruction patching or simulated libc.',
            'dependencies_stubbed': []}


def main():
    s = Sandbox(); u = s.uc; evidence = install_sdk_memory(s)
    dest = s.HEAP+0x10000; source = s.HEAP+0x20000
    lengths = [0, 1, 2, 3, 4, 7, 8, 9, 15, 16, 17, 24, 25, 31, 32, 33, 63, 64, 65, 127, 128, 129, 1024, 30000]
    guard = bytes([0xa5])*16; groups = {'SDK_memset': 0, 'SDK_memcpy': 0}
    memset = int(evidence['bindings']['memset']['emulated_va'], 16)
    memcpy = int(evidence['bindings']['memcpy']['emulated_va'], 16)
    for count, offset, value in itertools.product(lengths, [0, 1, 7], [0, 255, 256, 0xffffffff]):
        base = dest+offset
        u.mem_write(base-16, guard+bytes([0x33])*count+guard)
        assert s.call(memset, (base, value, count), limit=10000) == base
        assert bytes(u.mem_read(base-16, count+32)) == guard+bytes([value & 255])*count+guard
        groups['SDK_memset'] += 1
    for count, source_offset, dest_offset in itertools.product(lengths, [0, 1, 7], [0, 1, 7]):
        data = bytes((i*37+11) % 256 for i in range(count))
        u.mem_write(source+source_offset, data)
        base = dest+dest_offset; u.mem_write(base-16, guard+bytes([0x33])*count+guard)
        assert s.call(memcpy, (base, source+source_offset, count), limit=300000) == base
        assert bytes(u.mem_read(base-16, count+32)) == guard+data+guard
        assert bytes(u.mem_read(source+source_offset, count)) == data
        groups['SDK_memcpy'] += 1
    result = {'groups': groups, 'cases': sum(groups.values()), 'mismatches': [],
              'dependencies_stubbed': [], 'sdk': evidence,
              'scope': 'Nonoverlapping memcpy and memset with length/alignment/guard boundaries. SDK support validation, not gameplay-rule completion.',
              'elf_sha256': hashlib.sha256(s.image.data).hexdigest()}
    (ROOT/'output/mechanics/sdk_memory_native.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({'groups': groups, 'cases': result['cases'], 'mismatches': 0}), flush=True)


if __name__ == '__main__': main()
