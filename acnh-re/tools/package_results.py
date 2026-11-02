#!/usr/bin/env python3
"""Bundle evidence, JSON, docs and reproducible tools; omit tool installations."""
import hashlib
import json
from pathlib import Path
import zipfile

ROOT=Path(__file__).resolve().parent.parent


def build():
    destination=ROOT.parent/'acnh-re-results.zip'
    files=[ROOT/n for n in ['README.md','LAPORAN_AKHIR.md','requirements-native.txt']]
    for folder in ['output','docs','tools','tests','ghidra_scripts','research']:
        files.extend(p for p in (ROOT/folder).rglob('*') if p.is_file()
                     and '__pycache__' not in p.parts and p.suffix!='.pyc')
    files=sorted(set(files))
    inventory=[]
    with zipfile.ZipFile(destination,'w',zipfile.ZIP_DEFLATED,compresslevel=6,allowZip64=True) as archive:
        for p in files:
            relative='acnh-re/'+p.relative_to(ROOT).as_posix()
            archive.write(p,relative)
            inventory.append({'path':relative,'bytes':p.stat().st_size,
                              'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
        archive.writestr('acnh-re/BUNDLE.json',json.dumps({'files':inventory,
            'original_input_not_bundled':True,
            'original_input_note':'Keep ACNH_island_RE for main.elf/references, and keep the five additional ExeFS files separately in inputs/additional_exefs. Original executables are excluded from this evidence bundle.',
            'scope_status':'structural_mapping_complete; semantic_reverse_engineering_partial'},separators=(',',':')))
    with zipfile.ZipFile(destination) as archive:
        bad=archive.testzip()
        if bad:raise ValueError(('bundle CRC failed',bad))
    digest=hashlib.sha256(destination.read_bytes()).hexdigest()
    destination.with_suffix('.sha256').write_text(digest+'  '+destination.name+'\n')
    summary={'archive':str(destination),'bytes':destination.stat().st_size,'sha256':digest,
             'evidence_files':len(files),'zip_crc_check':'passed'}
    (ROOT/'package_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary,indent=2))


if __name__=='__main__':build()
