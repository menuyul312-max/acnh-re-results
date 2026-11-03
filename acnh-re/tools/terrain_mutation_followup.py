"""Aggregate the native region-mutation phase."""
from pathlib import Path
import json
ROOT=Path(__file__).resolve().parent.parent;OUT=ROOT/'output'
def write(p,d):p.write_text(json.dumps(d,indent=2,ensure_ascii=False)+'\n')
def main():
 proof=json.loads((OUT/'mechanics/terrain_region_mutation_native.json').read_text());assert proof['cases']==164 and proof['mismatches']==[]
 cov=json.loads((OUT/'coverage.json').read_text());cov['native_helper_checks']['terrain_region_mutation_native']=164
 assert sum(cov['native_helper_checks'].values())>=1135957
 cov['full_user_goal_completed']=False;cov['mechanics_research']['terrain_region_mutation_native']='mechanics/terrain_region_mutation_native.json';cov['mechanics_research']['terrain_mutation_report']='../docs/TERRAIN_REGION_MUTATION.md';write(OUT/'coverage.json',cov)
 progress={'native_helper_cases_before':1135793,'new_native_cases':164,'native_helper_cases_after':1135957,'mismatches':[],'full_game_semantics_complete':False,'source_elf_sha256':proof['elf_sha256'],'report':'../docs/TERRAIN_REGION_MUTATION.md'};write(OUT/'mechanics/terrain_mutation_progress.json',progress)
 p=OUT/'mechanics/continuation_frontier.json';f=json.loads(p.read_text())
 for key in ['terrain','position_checks','npc_navigation']:
  a=f['areas'][key];a['verified_reference']=list(dict.fromkeys(a['verified_reference']+['mechanics/terrain_region_mutation_native.json']))
 f['latest_phase']={'report':'../docs/TERRAIN_REGION_MUTATION.md','progress':'mechanics/terrain_mutation_progress.json','new_native_cases':164,'native_helper_cases_total':1135957}
 f['areas']['position_checks']['region_mutation_boundary']='Original region word-bit2/6 setters, world-member wrappers and bit6-to-navigation decoder chain. Registry removal and live placement policy remain open.';write(p,f)
 p=OUT/'mechanics/focus7/summary.json';f=json.loads(p.read_text())
 for key in ['terrain','position_checks','npc_navigation']:
  a=f['domains'][key];a['evidence_files']=list(dict.fromkeys(a['evidence_files']+['terrain_region_mutation_native.json']))
 f['terrain_mutation_followup']=progress;write(p,f)
 print(json.dumps(progress))
if __name__=='__main__':main()
