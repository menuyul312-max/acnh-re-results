"""Publish a scoped evidence map for the seven user-selected mechanics areas."""
from pathlib import Path
from collections import Counter,defaultdict
import json
import re
import sqlite3

ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/'output/mechanics/focus7'

def dump(name,obj):
    (OUT/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')

def main():
    OUT.mkdir(exist_ok=True)
    db=sqlite3.connect(ROOT/'output/index.sqlite')
    table_paths={p.stem:p for p in (ROOT/'output/tables_resolved').glob('*.json')}
    groups={
      'physics_collision':['ColGroundAttributeParam','PlayerStateParam','ItemSize','NmlNpcRaceParam','NpcSpModelScale'],
      'player_movement':['PlayerStateParam','HumanAnimParam'],
      'terrain':[n for n in table_paths if n.startswith('Field')]+['MysteryTourFieldParam','EventPlazaGround'],
      'dynamic_ground':['ColGroundAttributeParam','FieldOutsideParts','FieldOutsideTemplate','RoomFloorParam'],
      'position_checks':['ColGroundAttributeParam','ItemSize','FieldMainFieldParam'],
      'npc_navigation':[n for n in table_paths if n.startswith(('Npc','NmlNpc','SpNpc','MuseumNPC'))]+['AITag'],
      'items_tools_crafting':[n for n in table_paths if n.startswith('Item')]+['RecipeCraftParam']}
    field_refs=defaultdict(list)
    for h,pc,owner in db.execute('select hash,pc,owner_va from hash_refs'):
        field_refs[h].append({'pc':hex(pc),'owner_va':hex(owner)if owner is not None else None})
    fields={};table_refs={}
    for name in sorted({n for v in groups.values()for n in v}):
        if name not in table_paths:continue
        t=json.loads(table_paths[name].read_text())
        cols=[]
        for i,col in enumerate(t['columns']):
            cols.append({'column_index':i,'name':col['name'],'hash':col['hash'],'offset':col['offset'],
                'type':col['type'],'native_hash_reference_candidates':field_refs.get(int(col['hash'],16),[]),
                'candidate_scope':'Same hash may be shared across tables; these are not uniquely assigned readers.'})
        fields[name]={'json':f'tables_resolved/{name}.json','rows':t['row_count'],'columns':cols}
        table_refs[name]={'json':f'tables_resolved/{name}.json','rows':t['row_count'],'columns':len(cols),
            'columns_without_original_name':sum(c['name'].startswith('h_') for c in t['columns'])}
    dump('table_field_links.json',{'tables':fields,'scope':'Parsed schemas and candidate native readers; not complete gameplay semantics.'})
    parameters=[]
    for p in sorted((ROOT/'output/byml_resolved').glob('[0-9]*.json')):
        d=json.loads(p.read_text());source=d['source']
        if '!Param/Npc/' in source or source.endswith('Param/Actor/PlayerActor.byml'):
            roots=d['root']
            parameters.append({'source':source,'source_sha256':d['source_sha256'],
                'json':str(p.relative_to(ROOT/'output')),'root':roots,
                'scope':'Recovered descriptors and data values; units, reachability and algorithm consumers may remain unverified.'})
    dump('movement_npc_parameters.json',{'entries':parameters})
    handlers=json.loads((ROOT/'output/binary/event_handlers_resolved.json').read_text())['entries']
    ai_calls=[];ai_counts=Counter();flow_handlers=defaultdict(set)
    item_calls=[]
    item_regex=re.compile(r'Craft|Recipe|Tool|Scoop|Fishing|Item|Equip|Remake|BreakTool|Pocket',re.I)
    selected_handlers={}
    for flow,index,actor,kind,name,params in db.execute('select flow,event_index,actor,kind,name,params_json from event_calls'):
        key=actor+'.'+name
        record={'flow':flow,'event_index':index,'actor':actor,'kind':kind,'name':name,'parameters':json.loads(params) if params else None,
                'handler_key':key,'handler_resolved':key in handlers}
        ai=flow.startswith('AI_NPC_');item=bool(item_regex.search(name))
        if ai:
            ai_calls.append(record);ai_counts[flow]+=1;flow_handlers[flow].add(key)
        if item:item_calls.append(record)
        if (ai or item) and key in handlers:selected_handlers[key]=handlers[key]
    dump('npc_ai_eventflows.json',{'flows':dict(ai_counts),'calls':ai_calls,
        'scope':'Every indexed action/query occurrence in supplied AI_NPC_* flows. Flow timing, C++ scheduling and pathfinding remain unproven.'})
    # Preserve the actual branch/fork/join/subflow graph, not just handler calls.
    manifest=json.loads((ROOT/'output/manifest.json').read_text())['entries']
    all_flows={};graphs=[];subflows=[];graph_types=Counter();edges=0;entries=0
    for source in manifest:
        if source.get('format')!='BFEVFL':continue
        decoded=json.loads((ROOT/'output'/source['decoded']).read_text())['data']
        for fc in decoded['flowcharts']:
            if fc['name'] in all_flows:raise ValueError('Duplicate flowchart name')
            all_flows[fc['name']]={'chart':fc,'source':source['source'],
                 'source_sha256':source['sha256'],'decoded':source['decoded']}
    for name,source in all_flows.items():
        if not name.startswith('AI_NPC_'):continue
        fc=source['chart'];events=fc['events'];n=len(events)
        for i,event in enumerate(events):
            graph_types[str(event['type'])]+=1
            targets=[event[k] for k in ['next','join'] if event.get(k) is not None]
            targets+=event.get('forks',[])+[c['event']for c in event.get('cases',[])]
            assert all(isinstance(t,int)and 0<=t<n for t in targets)
            edges+=len(targets)
            if event['type']=='subflow':
                target=event.get('flowchart')or name;entry=event['entry_point']
                available=target in all_flows and entry in all_flows[target]['chart']['entry_points']
                assert available,(name,target,entry)
                subflows.append({'flow':name,'event':i,'target':target,'entry':entry,
                    'target_decoded':all_flows[target]['decoded'],'target_in_ai_subset':target.startswith('AI_NPC_')})
        for entry in fc['entry_points'].values():
            target=entry['main_event'];assert target is None or 0<=target<n
        entries+=len(fc['entry_points']);graphs.append(source)
    dump('npc_ai_flow_graphs.json',{'graphs':graphs,'subflows':subflows,'node_types':dict(graph_types),
        'local_edge_count':edges,'entry_points':entries,
        'scope':'Supplied AI EventFlow control graphs with bounded indices and supplied subflow targets. Native query outcomes and scheduler execution remain unproven.'})
    dump('item_tool_event_calls.json',{'calls':item_calls,'selection':'Handler name matches crafting/item/tool keywords; not an exhaustive inventory of gameplay functions.'})
    dump('native_event_handlers.json',{'entries':selected_handlers,'scope':'Existing registration/factory/vtable evidence. Slot roles and full action/query semantics remain partial.'})
    states=[]
    for va,owner,text in db.execute('select distinct string_va,function_va,text from string_refs'):
        if text.startswith(('NpcAIState::','NpcAIActivityState::')):
            states.append({'label':text,'string_va':hex(va),'owner_va':hex(owner) if owner else None})
    dump('npc_native_state_labels.json',{'states':states,'scope':'Native state-name evidence; not a complete transition or scheduling graph.'})
    proofs={
      'physics_collision':['collision_native_verification.json','collision_response_native.json','proximity_native.json','ballistic_velocity_native.json'],
      'player_movement':['collision_states.json','player_parameter_bindings.json','player_motion_native.json','player_position_native.json','player_root_motion_native.json','ballistic_velocity_native.json'],
      'terrain':['terrain_native.json','terrain_collision_parameters.json'],
      'dynamic_ground':['dynamic_ground_native.json','terrain_native.json','ground_context_gate_native.json','room_floor_ground_native.json','resident_floor_map_native.json'],
      'position_checks':['proximity_native.json','terrain_native.json'],
      'npc_navigation':['npc_activity_bindings.json','focus7/npc_ai_eventflows.json','focus7/npc_ai_flow_graphs.json','focus7/npc_native_state_labels.json','npc_state_registry_native.json','npc_navigation_request_native.json','npc_pathfinding_native.json','npc_route_handoff_native.json','npc_route_target_native.json','npc_navigation_kernel_map.json'],
      'items_tools_crafting':['crafting_materials_native.json','inventory_requirements_native.json','inventory_cache_native.json','focus7/item_tool_event_calls.json']}
    remaining={
      'physics_collision':['Geometric penetration response, friction and moving-body solver','Complete collision mask meanings'],
      'player_movement':['Input/state, runtime gravity integration and collision -> full frame; position/root-motion consumer and ballistic solver are verified in bounded contexts','Animation sample production, all traversal/landing/ladder/jump conditions and timestep units'],
      'terrain':['Raw 14-byte preset -> 52-byte runtime construction','Live terraform update and all building/placement restrictions'],
      'dynamic_ground':['Original PBC map contents and first48 bytes of each52-byte record; selection, transforms and consumers now execute on reconstructed resident maps','All dynamic override loader and reachability conditions; filesystem/async resource lifecycle'],
      'position_checks':['Full candidate collection, actor/type filtering and object registry','Complete placement queries and callers'],
      'npc_navigation':['Live terrain/collision-to-grid production, async worker and obstacle avoidance; native A* search/costs, route extraction and lookahead are now verified on declared reconstructed contexts','Active child-state handlers, steering/movement, scheduler priorities, social/interest decisions and all AI transitions'],
      'items_tools_crafting':['Save-wrapper acquisition and full parent cold-cache path; A/B/C producers on supplied-layout records and the requirement checker are verified','Atomic ingredient consumption, recipe unlocks, tool durability and all use/remake transactions']}
    domains={k:{'tables':[table_refs[n]for n in dict.fromkeys(v)if n in table_refs],
        'missing_requested_table_names':[n for n in v if n not in table_refs],
        'evidence_files':proofs[k],'remaining':remaining[k],'complete':False}for k,v in groups.items()}
    summary={'domains':domains,'counts':{'tables':len(table_refs),'parameter_files':len(parameters),
        'ai_flows':len(ai_counts),'ai_action_query_occurrences':len(ai_calls),
        'npc_native_state_label_records':len(states),'unique_npc_state_labels':len({s['label']for s in states}),
        'ai_graphs':len(graphs),'ai_graph_nodes':sum(graph_types.values()),'ai_graph_edges':edges,
        'ai_entry_points':entries,'ai_subflow_calls':len(subflows),
        'item_tool_action_query_occurrences':len(item_calls),'selected_native_handler_entries':len(selected_handlers),
        'ai_exact_handler_matches':sum(c['handler_resolved']for c in ai_calls)},
        'evidence_root':'output/mechanics/','table_json_root':'output/',
        'model_sound_policy':'Supplied catalogues only; no missing model/audio source requirement for this focus.',
        'full_requested_focus_complete':False,
        'scope':'Evidence map over supplied corpus and existing native index. It does not claim all code paths or functions are known.'}
    dump('summary.json',summary)
    print(json.dumps(summary['counts']),flush=True)

if __name__=='__main__':main()
