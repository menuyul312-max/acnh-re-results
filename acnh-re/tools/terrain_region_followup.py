"""Publish the rectangle-predicate phase without recounting historical proofs."""
from pathlib import Path
import json
ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/'output'
def write(p,d):p.write_text(json.dumps(d,indent=2,ensure_ascii=False)+'\n')
def main():
 proof=json.loads((OUT/'mechanics/terrain_region_check_native.json').read_text())
 assert proof['cases']==216 and proof['mismatches']==[] and proof['dependencies_stubbed']==[]
 coverage=json.loads((OUT/'coverage.json').read_text())
 previous=json.loads((OUT/'mechanics/world_nav_bridge_progress.json').read_text())
 assert previous['native_helper_cases_after']==1135577 and proof['elf_sha256']==previous['source_elf_sha256']
 coverage['native_helper_checks']['terrain_region_check_native']=proof['cases']
 assert sum(coverage['native_helper_checks'].values())==1135793
 progress={'native_helper_cases_before':1135577,'new_native_cases':216,'native_helper_cases_after':1135793,'mismatches':[],
  'full_game_semantics_complete':False,'source_elf_sha256':proof['elf_sha256'],'report':'../docs/TERRAIN_REGION_CHECK.md'}
 write(OUT/'mechanics/terrain_region_progress.json',progress)
 coverage['mechanics_research']['terrain_region_check_native']='mechanics/terrain_region_check_native.json'
 coverage['mechanics_research']['terrain_region_report']='../docs/TERRAIN_REGION_CHECK.md'
 coverage['full_user_goal_completed']=False;write(OUT/'coverage.json',coverage)
 p=OUT/'mechanics/continuation_frontier.json';frontier=json.loads(p.read_text())
 for key in ['terrain','position_checks']:
  area=frontier['areas'][key];area['verified_reference']=list(dict.fromkeys(area['verified_reference']+['mechanics/terrain_region_check_native.json']))
  area['region_predicate_boundary']='Original0x181fa0 on finite reconstructed rectangular base/overlay heights and world-word flags. Live placement callers remain unexecuted.'
 frontier['latest_phase']={'report':'../docs/TERRAIN_REGION_CHECK.md','progress':'mechanics/terrain_region_progress.json','new_native_cases':216,'native_helper_cases_total':1135793};write(p,frontier)
 p=OUT/'mechanics/focus7/summary.json';focus=json.loads(p.read_text())
 for key in ['terrain','position_checks']:
  domain=focus['domains'][key];domain['evidence_files']=list(dict.fromkeys(domain['evidence_files']+['terrain_region_check_native.json']))
 focus['terrain_region_followup']=frontier['latest_phase'];write(p,focus)
 print(json.dumps(progress))
if __name__=='__main__':main()
