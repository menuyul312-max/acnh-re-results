#!/usr/bin/env python3
"""Rebuild the RE corpus from the supplied, unchanged source package."""
from pathlib import Path
import subprocess
import sys

tools = Path(__file__).resolve().parent
source = sys.argv[1:] or ['/workspace/downloads/ACNH_island_RE/ACNH_island_RE']
if len(source) != 1:
    raise SystemExit('usage: build_all.py [source_package]')
for script, args in [('reverse_corpus.py', ['--source', source[0]]),
                     ('map_native.py', source), ('index_corpus.py', ['--source', source[0]]),
                     ('semantic_links.py', source), ('typed_byml.py', []), ('resolve_schemas.py', []),
                     ('resolve_handlers.py', []), ('native_relations.py', []),
                     ('expand_hashes.py', []), ('audit_unknowns.py', []),
                     ('byml_names.py', []), ('item_words.py', []),
                     ('native_byml_verify.py', []), ('stage_native.py', []),
                     ('bcsv_native_views.py', []), ('flag_policies.py', []), ('npc_voice.py', []), ('flowers_native.py', []),
                     ('native_rng.py', []), ('weather_corpus.py', []), ('weather_native.py', []),
                     ('verify_native_helpers.py', []), ('curves.py', []),
                     ('verify_builtin.py', []), ('texture_sources.py', []), ('native_atlas.py', []),
                     ('native_evidence.py', [])]:
    print('Running', script, flush=True)
    subprocess.run([sys.executable, str(tools / script), *args], check=True)

additional=tools.parent/'inputs/additional_exefs'
if all((additional/name).is_file()for name in ['main.npdm','rtld','main','subsdk0','sdk']):
    for script in ['exefs_modules.py','linked_sdk_verify.py','calendar_native.py','weather_linked.py']:
        print('Running',script,flush=True)
        subprocess.run([sys.executable,str(tools/script)],check=True)
subprocess.run([sys.executable,str(tools/'finalize_report.py')],check=True)

with (tools.parent/'output/verification.log').open('w') as log:
    subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', str(tools.parent/'tests'), '-v'],
                   stdout=log, stderr=subprocess.STDOUT, check=True)
print('Integration verification passed; output/verification.log', flush=True)
