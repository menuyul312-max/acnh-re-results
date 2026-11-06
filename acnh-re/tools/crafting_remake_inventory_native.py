"""Execute the original Remake Kit inventory mutation helper on fixtures.

The main helper 0xf99b10 and its callees execute as AArch64 instructions from
the supplied ELF. Item tables are real decoded inputs; the pocket record and
player item argument are reconstructed. This is not a full save transaction.
"""
from pathlib import Path
import hashlib
import json
import struct
import sys
import zlib

TOOLS = Path(__file__).resolve().parent
REPO = TOOLS.parent
SHARED = Path('/workspace/acnh-re')
OUT = REPO / 'output' / 'gameplay' / 'crafting_transaction_remainder'

sys.path.insert(0, str(SHARED / '.deps'))
sys.path.insert(0, str(TOOLS))
from native_emulator import Sandbox  # noqa: E402
import inventory_requirements_native as inventory_requirements  # noqa: E402

inventory_requirements.ROOT = SHARED


def sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def make_inventory(s, base, item_addr, amount):
    u = s.uc
    u.mem_write(base, bytes(0x500))
    u.mem_write(item_addr, struct.pack('<HHI', 2513, 0, 0))
    if amount:
        u.mem_write(base + 0xb8, struct.pack('<HHI', 2513, 0, amount - 1))
    else:
        u.mem_write(base + 0xb8, struct.pack('<HHI', 0xfffe, 0, 0))
    u.mem_write(base + 0x158, struct.pack('<I', 1))
    u.mem_write(base + 0xa0, struct.pack('<I', 0))
    u.mem_write(base + 0x178, b'\x00')


def slot_record(u, base):
    return struct.unpack('<HHI', u.mem_read(base + 0xb8, 8))


def run_case(s, index, available, requested):
    base = s.HEAP + 0x10000 + index * 0x1000
    item_addr = base + 0x400
    make_inventory(s, base, item_addr, available)
    before = bytes(s.uc.mem_read(base, 0x500))
    result = s.call(0xf99b10, (base, item_addr, requested), limit=1_000_000)
    after = bytes(s.uc.mem_read(base, 0x500))
    return {
        'available_before': available,
        'requested_remove': requested,
        'native_return': result,
        'freeparam_before': slot_record_from_bytes(before),
        'freeparam_after': slot_record(s.uc, base)[2],
        'slot_record_before': list(struct.unpack('<HHI', before[0xb8:0xc0])),
        'slot_record_after': list(slot_record(s.uc, base)),
        'changed_offsets': [hex(i) for i, (old, new) in enumerate(zip(before, after))
                            if old != new],
        'inventory_bytes_unchanged': before == after}


def slot_record_from_bytes(data):
    return struct.unpack('<HHI', data[0xb8:0xc0])[2]


def main():
    s = Sandbox()
    tables = inventory_requirements.install_item_tables(s)
    item_table, item_cols = tables['item_table'], tables['item_cols']
    kind_table, kind_cols = tables['kind_table'], tables['kind_cols']
    kit = next(row for row in item_table['rows'] if row[item_cols['UniqueID']] == 2513)
    kit_kind_hash = int(kit[item_cols['ItemKind']]['hash'], 16)
    kit_kind = next(row for row in kind_table['rows']
                    if zlib.crc32(row[kind_cols['Label']].encode()) == kit_kind_hash)
    stack_limit = kit_kind[kind_cols['MultiHoldMaxNum']]
    kit_kind_label = kit_kind[kind_cols['Label']]
    assert kit_kind_label == 'CraftRemake'
    assert stack_limit == 50

    sufficient = run_case(s, 0, 50, 2)
    insufficient = run_case(s, 1, 1, 2)
    exact_stack = run_case(s, 2, 2, 2)
    assert sufficient['native_return'] == 1
    assert sufficient['freeparam_before'] == 49
    assert sufficient['freeparam_after'] == 47
    assert sufficient['slot_record_after'] == [2513, 0, 47]
    assert insufficient['native_return'] == 0
    assert insufficient['inventory_bytes_unchanged'] is True
    # The all-stack boundary returns success but leaves this reconstructed
    # fixture unchanged. Preserve the observation without treating it as the
    # game's deletion semantics; the slot layout is not a captured save.
    assert exact_stack['native_return'] == 1
    assert exact_stack['inventory_bytes_unchanged'] is True

    report = {
        'schema': 'acnh.crafting_remake_inventory_native.v1',
        'provenance': {
            'elf_sha256': hashlib.sha256(s.image.data).hexdigest(),
            'helper': '0xf99b10',
            'itemparam_raw_sha256': tables['item_raw_sha256'],
            'itemkind_raw_sha256': tables['kind_raw_sha256']},
        'fixture': {
            'kit_item_id': 2513,
            'item_kind': kit_kind_label,
            'stack_limit_from_native_ItemKind': stack_limit,
            'inventory_shape': 'reconstructed 0x500-byte pocket-like record; one active item slot at +0xb8; active count at +0x158; empty secondary area; category byte +0x178=0'},
        'cases': {
            'sufficient_stack': sufficient,
            'insufficient_stack': insufficient,
            'exact_stack_boundary': exact_stack},
        'result': 'NATIVE_HELPER_EXECUTED',
        'claims': {
            'two_kits_reduce_FreeParam_49_to_47': 'PROVEN_NATIVE_ON_RECONSTRUCTED_FIXTURE',
            'request_larger_than_available_does_not_change_fixture': 'PROVEN_NATIVE_ON_RECONSTRUCTED_FIXTURE',
            'exact_stack_boundary': 'UNRESOLVED_FIXTURE_SEMANTICS_NATIVE_RETURNS_SUCCESS_WITH_NO_BUFFER_CHANGE',
            'real_player_save_or_cWorkRemake_event_executed': False,
            'persistent_save_flush_or_rollback': 'UNRESOLVED'},
        'notes': [
            'In this item-record encoding, the related inventory cache reader maps FreeParam low16 + 1 to displayed stack quantity for stackable normal items; the 50-kit fixture therefore starts at FreeParam 49.',
            'The sufficient case also writes 0xff to adjacent byte +0x15c. Its UI/order-list semantics are not named by this fixture and are not interpreted here.',
            'The helper, requirement comparison, table lookups and inventory mutation execute natively. ItemParam/ItemKind blobs are supplied; the pocket record and item descriptor are synthetic.',
            'No dependency function was stubbed. This helper-level run does not establish that the full event transaction is atomic or persisted to disk.']}

    OUT.mkdir(parents=True, exist_ok=True)
    out_path = OUT / 'crafting_remake_inventory_native.json'
    out_path.write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'result': 'pass',
                      'sufficient_return': sufficient['native_return'],
                      'freeparam_before_after': [sufficient['freeparam_before'],
                                                 sufficient['freeparam_after']],
                      'insufficient_return': insufficient['native_return'],
                      'output': str(out_path)}))


if __name__ == '__main__':
    main()
