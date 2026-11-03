"""Aggregate original registered-region release evidence."""
from pathlib import Path
import json
ROOT=Path(__file__).resolve().parent.parent;OUT=ROOT/'output'
def write(p,d):p.write_text(json.dumps(d,indent=2,ensure_ascii=False)+'\n')
def main():
 proof=json.loads((OUT/'mechanics/world_registry_release_native.json').read_text());assert proof['cases']==126 and proof['mismatches']==[]
 cov=json.loads((OUT/'coverage.json').read_text());cov['native_helper_checks']['world_registry_release_native']=126
 assert sum(cov['native_helper_checks'].values())==1136083
 cov['full_user_goal_completed']=False;cov['mechanics_research']['world_registry_release_native']='mechanics/world_registry_release_native.json';cov['mechanics_research']['world_registry_report']='../docs/WORLD_REGISTRY_RELEASE.md';write(OUT/'coverage.json',cov)
 progress={'native_helper_cases_before':1135957,'new_native_cases':126,'native_helper_cases_after':1136083,'mismatches':[],'full_game_semantics_complete':False,'source_elf_sha256':proof['elf_sha256'],'report':'../docs/WORLD_REGISTRY_RELEASE.md'};write(OUT/'mechanics/world_registry_progress.json',progress)
 p=OUT/'mechanics/continuation_frontier.json';f=json.loads(p.read_text())
 for key in ['terrain','position_checks','npc_navigation']:
  a=f['areas'][key];a['verified_reference']=list(dict.fromkeys(a['verified_reference']+['mechanics/world_registry_release_native.json']))
 f['areas']['position_checks']['registry_release_boundary']='Complete original registered-region unlink/count/world dispatch/release wrapper on prepared lists; allocation/insertion, full actor registry and placement callers remain open.'
 f['latest_phase']={'report':'../docs/WORLD_REGISTRY_RELEASE.md','progress':'mechanics/world_registry_progress.json','new_native_cases':126,'native_helper_cases_total':1136083};write(p,f)
 p=OUT/'mechanics/focus7/summary.json';f=json.loads(p.read_text())
 for key in ['terrain','position_checks','npc_navigation']:
  a=f['domains'][key];a['evidence_files']=list(dict.fromkeys(a['evidence_files']+['world_registry_release_native.json']))
 f['world_registry_followup']=progress;write(p,f);print(json.dumps(progress))
if __name__=='__main__':main()
