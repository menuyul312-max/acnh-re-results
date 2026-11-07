"""Execute the Friendship setter with a table-seeded synthetic field view.

The original 0xef2c70, 0xf48840, and 0xf486c0 bodies execute over a synthetic
save base. The table-derived UniqueID=10 and MaxValue=255 seed controlled
descriptor lookups. This verifies writer behavior at that slot in the fixture,
not the live player save's resolved view or absolute byte offset.
"""
from pathlib import Path
import argparse
import hashlib
import json
import struct

from nso_sandbox import DEFAULT_NSO, Sandbox


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ANALYSIS_ROOT = Path('/workspace/acnh-re/output')
ELF_SHA256 = '5bf707c3dc5dac0ad9635af7d336ec580f81c3f7876d0f55400d1900e3415d74'
NSO_SHA256 = 'f8d248109ff72999b4600ae3749f8c7397fb960f7ad3ab8dee3018ae9e14e900'
FRIENDSHIP_SETTER = 0xef2c70
FIELD_WRITER = 0xf48840
FIELD_GETTER = 0xf486c0
FIELD_MAP_LOOKUP = 0xcc5e20
FIELD_INDEX_LOOKUP = 0xf48190
SAVE_ROOT_GETTER = 0xeecf20
VIEW_CTOR = 0xee9350
VIEW_COPY = 0xee9490
VIEW_PREPARE = 0xee94f0
VIEW_DTOR = 0xee93d0
SAVE_CHANGE_HOOK = 0xef2720
SAVE_CHANGE_ENABLED = 0xda4020
FRIENDSHIP_KEY_PTR = 0x29a5d44
FRIENDSHIP_KEY_HASH = 0x8a80b4d9
MAX_FIELD_METADATA_HASH = 0xbd7682f5
MAX_FIELD_METADATA_BYTE_OFFSET = 0xff


def friendship_descriptor_from_table(analysis_root):
    """Read the exact 1.0.0 Friendship row used to seed the controlled lookup."""
    table = json.loads((analysis_root/'tables_resolved/EventFlagsNpcMemoryParam.json').read_text())
    columns = {column['name']: index for index, column in enumerate(table['columns'])}
    rows = [row for row in table['rows'] if row[columns['Key']] == 'Friendship']
    assert len(rows) == 1, len(rows)
    row = rows[0]
    return {
        'table': 'EventFlagsNpcMemoryParam',
        'key': row[columns['Key']],
        'UniqueID': int(row[columns['UniqueID']]),
        'MaxValue': int(row[columns['MaxValue']]),
        'DefaultValue': int(row[columns['DefaultValue']]),
        'source_id': table.get('source_id'),
    }


class Harness:
    def __init__(self, field_index, field_max_value):
        self.field_index = field_index
        self.field_max_value = field_max_value
        self.s = Sandbox()
        self.save_base = self.s.alloc(0x200000)
        self.writes = []
        self.views = []
        self.hashes = []
        self.field_lookups = []
        self.s.stub(SAVE_ROOT_GETTER, lambda _sb: self.save_base)

        def make_typed_view(sb):
            container, record = sb.reg('x0'), sb.reg('x1')
            view = sb.alloc(0x20)
            # 0xef2c70 reads the payload as [view+8] + [view+16].
            sb.uc.mem_write(view + 8, struct.pack('<QQ', 0, record))
            sb.uc.mem_write(container, struct.pack('<QQ', 0, view))
            self.views.append({'record_address': record, 'view': view})

        def field_map_lookup(sb):
            query = sb.reg('x1')
            key_hash = sb.u32(query)
            self.hashes.append(key_hash)
            # Execute the original hash and writer logic, but control the
            # external save-field descriptor lookup. Seed this synthetic row
            # with the extracted Friendship UniqueID=10 / MaxValue=255 values.
            # The table-to-runtime descriptor lookup itself remains stubbed.
            if key_hash != FRIENDSHIP_KEY_HASH:
                return 0
            return entry

        def field_index_lookup(sb):
            self.field_lookups.append(sb.reg('x0'))
            return self.field_index

        def observe_native_writer(uc, address, _size, _user_data):
            r = self.s.R
            self.writes.append({
                'record_address': uc.reg_read(r.UC_ARM64_REG_X0),
                'key_object': uc.reg_read(r.UC_ARM64_REG_X1),
                'value_u32': uc.reg_read(r.UC_ARM64_REG_X2) & 0xffffffff,
            })

        entry = self.s.alloc(0x200)
        self.s.uc.mem_write(entry, struct.pack('<I', 1))
        self.s.uc.mem_write(entry + MAX_FIELD_METADATA_BYTE_OFFSET,
                            bytes([self.field_max_value]))
        cache_rows = self.s.alloc(8)
        self.s.uc.mem_write(cache_rows,
                            struct.pack('<II', MAX_FIELD_METADATA_HASH, self.field_max_value))

        self.s.stub(VIEW_CTOR, make_typed_view)
        self.s.stub(VIEW_COPY, lambda _sb: None)
        self.s.stub(VIEW_PREPARE, lambda _sb: None)
        self.s.stub(VIEW_DTOR, lambda _sb: None)
        self.s.stub(FIELD_MAP_LOOKUP, field_map_lookup)
        self.s.stub(FIELD_INDEX_LOOKUP, field_index_lookup)
        # These helpers expose synthetic metadata seeded from the extracted
        # row. The original writer performs the metadata scan and byte mutation.
        self.s.stub(0x1665e80, lambda _sb: entry)
        self.s.stub(0x1665e60, lambda _sb: cache_rows)
        self.s.stub(0x1665e50, lambda _sb: 1)
        self.s.stub(SAVE_CHANGE_HOOK, lambda _sb: None)
        # Skip the optional follow-up notification/getter path; it is unrelated
        # to selecting and issuing the Friendship field write.
        self.s.stub(SAVE_CHANGE_ENABLED, lambda _sb: 0)
        from unicorn import UC_HOOK_CODE
        self.s.uc.hook_add(UC_HOOK_CODE, observe_native_writer,
                           begin=FIELD_WRITER, end=FIELD_WRITER)

    def run(self, resident, player, value, network, initial):
        key_object = self.s.alloc(0x10)
        self.s.uc.mem_write(key_object,
                            struct.pack('<QQ', 0x32d0678, FRIENDSHIP_KEY_PTR))
        record = expected_record(self.save_base, resident, player, network)
        valid = resident <= 9 and player <= (7 if network & 1 else 159)
        buffer_before = None
        if valid:
            # Model the requested 0x100-byte EventFlag view as a byte array.
            # A nonuniform fill exposes unintended neighboring-byte writes.
            seed = bytes((index * 37 + 13) & 0xff for index in range(0x100))
            self.s.uc.mem_write(record, seed)
            self.s.uc.mem_write(record + self.field_index, bytes([initial & 0xff]))
            buffer_before = self.s.uc.mem_read(record, 0x100)
        before = len(self.writes)
        self.s.call(FRIENDSHIP_SETTER,
                    (resident, player, key_object, value, network),
                    limit=500_000)
        setter_writes = self.writes[before:]
        getter_value = None
        if resident <= 9 and player <= (7 if network & 1 else 159):
            getter_value = self.s.call(FIELD_GETTER, (record, key_object),
                                       limit=500_000) & 0xff
        buffer_after = self.s.uc.mem_read(record, 0x100) if valid else None
        changed_offsets = []
        if valid:
            changed_offsets = [
                index for index, (before, after) in enumerate(zip(buffer_before, buffer_after))
                if before != after
            ]
        return setter_writes, getter_value, record, buffer_before, buffer_after, changed_offsets


def expected_record(base, resident, player, network):
    if network & 1:
        return base + resident * 0x10798 + player * 0x700 + 0x1c0
    return base + resident * 0x10798 + player * 0xa8 + 0x39f8


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--analysis-root', type=Path, default=DEFAULT_ANALYSIS_ROOT,
                    help='read-only analysis corpus containing tables_resolved')
    args = ap.parse_args()
    friendship_descriptor = friendship_descriptor_from_table(args.analysis_root)
    field_index = friendship_descriptor['UniqueID']
    field_max_value = friendship_descriptor['MaxValue']

    cases = [
        ('local_first_record', 0, 0, 42, 0, 29),
        ('local_last_resident_and_player', 9, 159, 255, 2, 200),
        ('local_mid_record_negative_clamps_to_zero', 4, 7, 0xffffffff, 0, 22),
        ('network_first_record', 0, 0, 60, 1, 10),
        ('network_last_resident_and_player_clamps_to_byte', 9, 7, 256, 3, 254),
        ('network_middle_record_unchanged', 5, 3, 15, 1, 15),
        ('reject_local_resident_10', 10, 0, 1, 0, 1),
        ('reject_local_player_160', 0, 160, 1, 0, 1),
        ('reject_network_resident_10', 10, 0, 1, 1, 1),
        ('reject_network_player_8', 0, 8, 1, 1, 1),
    ]
    observed = []
    for name, resident, player, value, network, initial in cases:
        h = Harness(field_index, field_max_value)
        writes, getter_value, record, buffer_before, buffer_after, changed_offsets = h.run(
            resident, player, value, network, initial)
        valid = resident <= 9 and player <= (7 if network & 1 else 159)
        assert len(writes) == int(valid), (name, writes, valid)
        if valid:
            assert writes[0]['record_address'] == expected_record(
                h.save_base, resident, player, network), (name, writes)
            assert writes[0]['key_object'] != 0, (name, writes)
            assert writes[0]['value_u32'] == (value & 0xffffffff), (name, writes)
            expected_value = min(255, max(0, value if value < 0x80000000
                                          else value - 0x100000000))
            assert getter_value == expected_value, (name, getter_value,
                                                    expected_value)
            expected_changed_offsets = (
                [field_index] if expected_value != (initial & 0xff) else []
            )
            assert changed_offsets == expected_changed_offsets, (
                name, changed_offsets, expected_changed_offsets)
            assert buffer_after[field_index] == expected_value, (name, buffer_after[field_index])
            assert buffer_after[field_index - 1] == buffer_before[field_index - 1]
            assert buffer_after[field_index + 1] == buffer_before[field_index + 1]
            assert h.hashes and all(x == FRIENDSHIP_KEY_HASH for x in h.hashes), (
                name, h.hashes)
            assert h.field_lookups, (name, h.field_lookups)
        observed.append({
            'name': name,
            'resident_slot': resident,
            'player_slot': player,
            'value_u32': value & 0xffffffff,
            'initial_byte': initial & 0xff,
            'network_mode_arg': network,
            'record_address': record if valid else None,
            'read_back_byte': getter_value,
            'synthetic_view_size': 0x100 if valid else None,
            'synthetic_view_changed_offsets': changed_offsets,
            'expected_writer_calls': int(valid),
            'writer_calls': writes,
            'native_friendship_key_hashes': [hex(x) for x in h.hashes],
        })

    nso_hash = hashlib.sha256(Path(DEFAULT_NSO).read_bytes()).hexdigest()
    assert nso_hash == NSO_SHA256, nso_hash
    result = {
        'cases': len(observed),
        'writer_calls': sum(x['expected_writer_calls'] for x in observed),
        'mismatches': [],
        'native_functions': {
            'friendship_record_setter': hex(FRIENDSHIP_SETTER),
            'field_writer_boundary': hex(FIELD_WRITER),
            'field_getter': hex(FIELD_GETTER),
            'save_root_getter': hex(SAVE_ROOT_GETTER),
        },
        'table_descriptor_seed': friendship_descriptor,
        'field_selector': {
            'source': 'EventFlagsNpcMemoryParam.UniqueID',
            'table_value': field_index,
            'tested_synthetic_view_offset': hex(field_index),
            'limit': 'The extracted table row is real 1.0.0 data, but the native table-to-descriptor lookup is controlled; this is not a live save-field offset proof.',
        },
        'cases_data': observed,
        'record_formulas': {
            'local': 'save_base + resident*0x10798 + player*0xa8 + 0x39f8',
            'network': 'save_base + resident*0x10798 + player*0x700 + 0x1c0',
        },
        'scope': ('Original 0xef2c70 and 0xf48840 setter instructions execute; '
                  'the test observes entry to the original writer and then '
                  'checks the synthetic record with original 0xf486c0. A '
                  'synthetic typed view points at a synthetic save base.'),
        'dependencies_stubbed': [
            {'va': hex(SAVE_ROOT_GETTER), 'purpose': 'returns a synthetic save base'},
            {'va': hex(VIEW_CTOR), 'purpose': 'constructs a synthetic view over the selected record'},
            {'va': hex(VIEW_COPY), 'purpose': 'skips typed-view copy/setup'},
            {'va': hex(VIEW_PREPARE), 'purpose': 'skips typed-view preparation'},
            {'va': hex(FIELD_MAP_LOOKUP), 'purpose': 'maps the native Friendship hash to a synthetic descriptor seeded from the extracted Friendship table row'},
            {'va': hex(FIELD_INDEX_LOOKUP), 'purpose': f'returns the table-derived UniqueID selector {field_index} for the synthetic 0x100-byte field view'},
            {'va': '0x1665e80 / 0x1665e60 / 0x1665e50', 'purpose': f'supplies synthetic type metadata seeded from the table MaxValue {field_max_value}'},
            {'va': hex(SAVE_CHANGE_HOOK), 'purpose': 'skips unrelated post-write bookkeeping'},
            {'va': hex(SAVE_CHANGE_ENABLED), 'purpose': 'selects the no-notification path'},
        ],
        'limits': [
            'The backing save bytes and field descriptor are synthetic; no player save was read or changed.',
            'The key wrapper has the same vtable and literal pointer as the d34f80 Friendship caller, but the wrapper object is synthetic.',
            'EventFlagsNpcMemoryParam supplies Friendship UniqueID=10 and MaxValue=255, and the original writer uses those table-derived values on the synthetic descriptor. The actual native table-manager lookup and save-view backing remain stubbed.',
            'The tested +0x0a offset is relative to the synthetic 0x100-byte field view, not a proven absolute byte offset in a player save.',
            'It does not prove that the daily -3 candidate is reachable during ordinary play.',
        ],
        'elf_sha256': ELF_SHA256,
        'nso_sha256': nso_hash,
    }
    out = ROOT / 'output/gameplay/villager_social_followup/friendship_save_writer_native.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps({'cases': len(observed),
                      'writer_calls': result['writer_calls'],
                      'field_index': field_index,
                      'max_value': field_max_value,
                      'mismatches': 0,
                      'artifact': str(out.relative_to(ROOT))}, ensure_ascii=False),
          flush=True)


if __name__ == '__main__':
    main()
