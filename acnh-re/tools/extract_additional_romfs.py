"""Extract plain files only, retaining hashes and comparisons to the original B_data."""
from pathlib import Path, PurePosixPath
from collections import Counter
import hashlib
import json
import shutil
import tarfile

BASE = Path('/workspace/downloads/acnh_additional_romfs_2026-11-02')
DEST = BASE / 'romfs'
OLD = Path('/workspace/downloads/ACNH_island_RE/ACNH_island_RE/B_data')
OUT = Path('/workspace/acnh-re/output/additional_romfs')


def extract():
    DEST.mkdir(exist_ok=True)
    inventory = json.loads((OUT / 'archive_inventory.json').read_text())
    required = inventory['total_file_bytes'] + 512 * 1024 * 1024
    if shutil.disk_usage(BASE).free < required:
        raise RuntimeError('Insufficient extraction budget')
    records = []
    with tarfile.open(BASE / 'extracted_romfs.tar.gz', 'r|gz') as archive:
        for member in archive:
            name = PurePosixPath(member.name)
            if name.is_absolute() or '..' in name.parts:
                raise ValueError(f'Unsafe archive path: {member.name}')
            if member.isdir():
                continue
            if not member.isfile():
                raise ValueError(f'Unsupported archive entry: {member.name}')
            destination = DEST.joinpath(*name.parts)
            destination.parent.mkdir(parents=True, exist_ok=True)
            digest = hashlib.sha256()
            prefix = b''
            with archive.extractfile(member) as source, destination.open('wb') as target:
                while chunk := source.read(1024 * 1024):
                    if not prefix:
                        prefix = chunk[:32]
                    digest.update(chunk)
                    target.write(chunk)
            destination.chmod(0o644)
            old = OLD.joinpath(*name.parts)
            comparison = 'new_path'
            if old.is_file():
                comparison = 'identical' if hashlib.sha256(old.read_bytes()).digest() == digest.digest() else 'different'
            records.append({'path': member.name, 'bytes': member.size,
                            'sha256': digest.hexdigest(), 'prefix_hex': prefix.hex(),
                            'original_B_data': comparison})
            if len(records) % 5000 == 0:
                print(json.dumps({'extracted': len(records)}), flush=True)
    current = {x['path'] for x in records}
    missing = [str(p.relative_to(OLD)) for p in OLD.rglob('*')
               if p.is_file() and str(p.relative_to(OLD)) not in current]
    summary = {'files': len(records), 'bytes': sum(x['bytes'] for x in records),
               'comparison': dict(Counter(x['original_B_data'] for x in records)),
               'original_B_data_paths_absent': missing,
               'top_directories': dict(Counter(x['path'].split('/')[0] for x in records)),
               'build_status': 'Compare content evidence; do not infer exact version from filenames.'}
    (OUT / 'extracted_manifest.json').write_text(json.dumps({'summary': summary, 'files': records}, indent=2) + '\n')
    print(json.dumps(summary), flush=True)


if __name__ == '__main__':
    extract()
