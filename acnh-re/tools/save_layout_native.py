"""Build output/gameplay/save_layout.json by emulating the save layout constructor 0xf32fa0 (nso_sandbox).

Each save member is a 0x38-byte node: +0x00 vtable (type descriptor), +0x10 data offset in the main save
data, +0x18 first child, +0x20 next sibling. Vtable slot 3 returns the data size. Offsets used elsewhere
in the docs (`F_ee9350(&x, base + OFF)`) are node offsets in the layout object, listed here as `node`.
Usage: python3 tools/save_layout_native.py [--output-root DIR] [--max-depth 2]  (deeper levels: ~43k nodes)
"""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from nso_sandbox import Sandbox, NSO_SHA256  # noqa: E402

CONSTRUCTOR = 0xf32fa0
PLAYER_CONSTRUCTOR = 0xf8f580   # layout of one player record (called from 0xf8f4d0)
PLAYER_KNOWN = {
    0x16a08: 'birthday (PlayerBirthday 0xefe10, 0xf920f0)',
    0x17370: 'birthday event date (written by 0xf920f0 at data +0x34942, read by BirthdayLive 0xf11b0)',
}
# node offset -> name, from readings in tools/gameplay_flow.py and docs/GAMEPLAY_*.md
KNOWN = {
    0xa8: 'villagers and NPC move state, 0x1d6d48 bytes (0xf84320)',
    0x4750: 'StructureMoveSaveIndex (0xf87670)',
    0x1575b0: 'land event flags (cLand flag store, 0x3e1470)',
    0x17cd48: 'player records (0xef8520 reads a value 0..8 at +i*0xe3b8)',
    0x1f3e98: 'shop block; u32 state 0..3 of Nook\'s Cranny at +0 (0xfc4e30)',
    0x1f40c8: 'Able Sisters block; state 0..2 at +0',
    0x1f67f0: 'Nook\'s Cranny stock, shop block +0x1400 (0xfd0630; also 0xfd0700)',
    0x1f3f40: 'Saharah stock, shop block +0x4 (0xfc56c0)',
    0x1f6080: 'Kicks stock, 32 items, shop block +0x1300 (0xfc8760)',
    0x208ed0: 'turnip prices u32[17], shop block +0x2ad0 (0xfc6d00, 0xfc7c70)',
    0x2092f8: '64-item list, shop block +0x2b14 (0xfc6300 -> 0xfc5d60)',
    0x20a168: 'museum block; state 0..4 at +0 (0xf77050)',
    0x20a210: 'special-visitor schedule (0xfd8a80)',
    0x20d0e0: 'value read for ItemKind Fruit price (0xaaaa80)',
    0x20d310: 'u32 set to 2 at each day change (0xf8f190)',
    0x20d3b8: 'member passed to 0xf234f0 (notice board) at day change',
    0x20d4d0: 'campsite state (0xf26330, 0xf7d7e0)',
    0x20d578: 'campsite visitor (0xf7d4c0)',
    0x24fdb0: 'island evaluation score (0x15c68c0)',
}


def build(max_depth=3, constructor=CONSTRUCTOR, known=None):
    known = KNOWN if known is None else known
    sb = Sandbox()
    root = sb.alloc(0x800000)
    sb.call(constructor, (root,))
    sizes = {}

    def size(vt):
        if vt not in sizes:
            sizes[vt] = sb.call(sb.u64(vt + 0x18), (root,), limit=2000)
        return sizes[vt]
    out, stack = [], [(root, 0, None)]
    while stack:
        n, depth, parent = stack.pop()
        vt = sb.u64(n + 0x10 - 0x10)
        row = {'node': hex(n - root), 'depth': depth, 'data': hex(sb.u64(n + 0x10)), 'size': hex(size(vt)),
               'type': hex(vt), 'parent': parent}
        if (n - root) in known:
            row['name'] = known[n - root]
        if depth <= max_depth or (n - root) in known:
            out.append(row)
        kids, c = [], sb.u64(n + 0x18)
        while c:
            kids.append(c)
            c = sb.u64(c + 0x20)
        for k in kids:
            stack.append((k, depth + 1, hex(n - root)))
    out.sort(key=lambda r: (int(r['data'], 16), r['depth']))
    return out, sb.unknown_imports


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--output-root', default=str(Path(__file__).resolve().parent.parent/'output'))
    ap.add_argument('--max-depth', type=int, default=2)
    a = ap.parse_args()
    rows, unknown = build(a.max_depth)
    player, unknown_p = build(1, PLAYER_CONSTRUCTOR, PLAYER_KNOWN)
    unknown.update(unknown_p)
    doc = {'meta': {'source': f'emulated 0xf32fa0 from ExeFS main sha256 {NSO_SHA256}', 'evidence': 'terbukti native (emulation)',
                    'max_depth': a.max_depth, 'unhandled_imports': unknown,
                    'fields': 'node = offset of the accessor node in the layout object (base + OFF in pseudocode); data = offset in save data; size from vtable slot 3; type = vtable VA'},
           'members': rows,
           'player_record': {'constructor': hex(PLAYER_CONSTRUCTOR), 'note': 'node/data offsets inside one player record; depth <= 1 plus named nodes', 'members': player}}
    path = Path(a.output_root)/'gameplay'/'save_layout.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=1)
    text = text.replace('\n  ', ' ').replace('\n }', ' }')
    path.write_text(text + '\n')
    print(path, len(rows), 'members')


if __name__ == '__main__':
    main()
