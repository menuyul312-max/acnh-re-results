#!/usr/bin/env python3
"""Differential checks against actual isolated ARM64 helper instructions."""
import json
import hashlib
import random
import struct
from pathlib import Path

from native_emulator import Sandbox, UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE
from reverse_corpus import dump

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'output'


def evaluate(ast, values):
    op = ast[0]
    if op == 'var':
        return struct.unpack('<f', struct.pack('<f', values[ast[1]]))[0]
    if op == 'number':
        return ast[1]
    a, b = evaluate(ast[1], values), evaluate(ast[2], values)
    if op == '&&': return bool(a) and bool(b)
    if op == '||': return bool(a) or bool(b)
    if op == '==': return a == b
    if op == '!=': return a != b
    if op == '<': return a < b
    if op == '<=': return a <= b
    if op == '>': return a > b
    if op == '>=': return a >= b
    raise ValueError(op)


def build():
    s = Sandbox()
    source, dest = s.HEAP, s.HEAP + 0x1000
    reads, writes = set(), set()
    def record(uc, access, addr, size, value, user):
        if source <= addr < source + 14:
            reads.update(range(addr - source, addr - source + size))
        if dest <= addr < dest + 14:
            writes.update(range(addr - dest, addr - dest + size))
    hook = s.uc.hook_add(UC_HOOK_MEM_READ | UC_HOOK_MEM_WRITE, record)
    rng = random.Random(26061101)
    errors = []
    random_records = [bytes(rng.randrange(256) for _ in range(14)) for _ in range(1024)]
    byte_boundary_records = [bytes(12) + bytes([height, 0]) for height in range(256)]
    for raw in random_records + byte_boundary_records:
        s.uc.mem_write(source, raw)
        s.uc.mem_write(dest, b'\xcd' * 16)
        s.call(0x542db0, [dest, source])
        got = bytes(s.uc.mem_read(dest, 14))
        expected = bytearray(raw)
        expected[5] = expected[11] = 0
        expected[12] = raw[12] if raw[12] < 6 else 4
        expected[13] = 0xcd
        if got != bytes(expected):
            errors.append({'input': raw.hex(), 'expected': bytes(expected).hex(), 'actual': got.hex()})
    s.uc.hook_del(hook)
    terrain = {'function_va': '0x542db0', 'height_reader_va': '0xf52860',
               'cases': 1280, 'random_cases': 1024, 'exhaustive_height_byte_cases': 256, 'mismatches': errors,
               'source_bytes_read': sorted(reads), 'destination_bytes_written': sorted(writes),
               'padding_source_bytes_not_read': [5, 11, 13],
               'native_height_rule': {'valid_range': [0,5], 'invalid_fallback':4}}

    c1 = json.loads((OUT / 'audio/condition_bytecode.json').read_text())
    records = {r['raw']['sha256']: r for r in c1['conditions']}
    code, ctx, owner, types, vals = [s.HEAP + n for n in [0, 0x2000, 0x3000, 0x4000, 0x5000]]
    count = len(c1['global_properties'])
    s.uc.mem_write(ctx + 8, struct.pack('<Q', owner))
    s.uc.mem_write(owner + 0x104, struct.pack('<I', count))
    s.uc.mem_write(owner + 0x110, struct.pack('<Q', types))
    s.uc.mem_write(owner + 0x120, struct.pack('<Q', vals))
    types_raw = bytes(p['Type'] == 'Float' for p in c1['global_properties'])
    s.uc.mem_write(types, types_raw)
    states = [[0] * count, [1] * count, [-1] * count,
              [i for i in range(count)], [rng.randrange(-2, 120) for _ in range(count)],
              [rng.randrange(0, 4) for _ in range(count)]]
    witness = [0] * count
    witness[28:31] = [22, 29, 55]
    states.append(witness)
    checks, failures = 0, []
    for state_id, state in enumerate(states):
        s.uc.mem_write(vals, b''.join(struct.pack('<f' if types_raw[i] else '<i', value)
                                    for i, value in enumerate(state)))
        for r in records.values():
            raw = (OUT / r['raw']['$blob']).read_bytes()
            s.uc.mem_write(code, raw)
            got = bool(s.call(0x21e21e0, [code, ctx]) & 1)
            expected = bool(evaluate(r['decoded']['ast'], state))
            checks += 1
            if got != expected:
                failures.append({'path': r['path'], 'state': state_id, 'native': got, 'decoded_ast': expected})
    result = {'native_elf_sha256': hashlib.sha256(s.image.data).hexdigest(),
              'terrain': terrain, 'c1': {'native_entry_va': '0x21e21e0',
              'recursive_evaluator_va': '0x21e21f0', 'unique_programs': len(records),
              'source_references': len(c1['conditions']), 'states': len(states),
              'native_comparisons': checks, 'mismatches': failures,
              'global_context_layout': {'owner_pointer': 8, 'owner_count': 0x104,
                  'owner_types_pointer': 0x110, 'owner_values_pointer': 0x120}}}
    dump(OUT / 'native_verification.json', result)
    print(json.dumps(result, indent=2), flush=True)
    if errors or failures:
        raise SystemExit(1)


if __name__ == '__main__':
    build()
