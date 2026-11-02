#!/usr/bin/env python3
"""Decode and validate the two sead curve kinds actually present in GameEnv.

Layout names: open-ead/sead f4178a21e21235830357dc27c26a2c29956972ed.
Evaluation is independently checked against this corpus's ARM64 instructions.
"""
import json
import hashlib
import math
import struct
from pathlib import Path

from reverse_corpus import dump

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'output'
FUNCTIONS = {7: 0x19ab390, 10: 0x19ab540}


def evaluate(points, kind, t):
    if t <= points[0][0]:
        return points[0][1]
    if t >= points[-1][0]:
        return points[-1][1]
    for a, b in zip(points, points[1:]):
        if t < b[0]:
            dx = b[0] - a[0]
            u = (t - a[0]) / dx
            scale = dx if kind == 10 else 1
            return ((2*u**3 - 3*u*u + 1)*a[1] + (-2*u**3 + 3*u*u)*b[1]
                    + (u**3 - 2*u*u + u)*a[2]*scale + (u**3-u*u)*b[2]*scale)
    raise ValueError('no segment selected')


def parameters(value, path='$'):
    if isinstance(value, dict):
        if value.get('type') in ('curve1', 'curve4'):
            yield path, value
        else:
            for k, v in value.items():
                yield from parameters(v, path + '/' + str(k))
    elif isinstance(value, list):
        for i, v in enumerate(value):
            yield from parameters(v, path + '/' + str(i))


def build():
    from native_emulator import Sandbox
    s = Sandbox()
    result = {'native_elf_sha256': hashlib.sha256(s.image.data).hexdigest(),
              'layout': {'record_bytes': 128, 'num_use_u32': 0, 'kind_u32': 4,
                         'float_payload': 8, 'float_capacity': 30,
                         'point_components': ['x', 'y', 'tangent']},
              'kinds': {'7': 'Hermit2D', '10': 'Hermit2DSmooth'},
              'native_functions': {str(k): hex(v) for k, v in FUNCTIONS.items()},
              'records': [], 'comparisons': 0, 'mismatches': [], 'nonmonotonic': []}
    entries = json.loads((OUT / 'manifest.json').read_text())['entries']
    for entry in entries:
        if entry['format'] != 'AAMP':
            continue
        doc = json.loads((OUT / entry['decoded']).read_text())
        for path, param in parameters(doc):
            for channel, curve in enumerate(param['curves']):
                count, kind = curve['word0'], curve['word1']
                if kind not in FUNCTIONS or count % 3 or not 6 <= count <= 30:
                    raise ValueError(('unhandled curve', entry['id'], path, count, kind))
                data = curve['payload_f32']
                points = [data[i:i+3] for i in range(0, count, 3)]
                rec = {'source_id': entry['id'], 'source': entry['source'], 'path': path,
                       'channel': channel, 'raw': curve['raw'], 'num_use': count,
                       'kind': kind, 'points': points, 'unused_tail': data[count:]}
                result['records'].append(rec)
                if any(b[0] <= a[0] for a, b in zip(points, points[1:])):
                    result['nonmonotonic'].append(len(result['records']) - 1)
                s.uc.mem_write(s.HEAP, bytes([kind, 4, 30, count]))
                s.uc.mem_write(s.HEAP+0x100, struct.pack('<30f', *data))
                samples = [-1., 2.] + [i/64 for i in range(65)] + [p[0] for p in points]
                for t in samples:
                    t = struct.unpack('<f', struct.pack('<f', t))[0]
                    s.call(FUNCTIONS[kind], [s.HEAP, s.HEAP+0x100], [t])
                    got, expected = s.float_result(), evaluate(points, kind, t)
                    result['comparisons'] += 1
                    if not math.isclose(got, expected, rel_tol=2e-5, abs_tol=2e-6):
                        result['mismatches'].append({'record': len(result['records'])-1,
                            't': t, 'native': got, 'decoded': expected})
    result['parameter_count'] = len({(r['source_id'], r['path']) for r in result['records']})
    result['record_count'] = len(result['records'])
    dump(OUT / 'environment/curves.json', result)
    print(json.dumps({k: v for k,v in result.items() if k != 'records'}, indent=2))
    if result['mismatches']:
        raise SystemExit(1)


if __name__ == '__main__':
    build()
