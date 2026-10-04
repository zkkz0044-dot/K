#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, pathlib, sys
sys.path.insert(0,'/root/K/K/src')
from kk_k.world_event_index import apply_notable, annotate_items
from kk_k.world_entity_graph import apply_observations

class EventUpdateError(ValueError): pass

def load_retained(path):
    raw=pathlib.Path(path).read_bytes()
    if not raw or len(raw)>262144: raise EventUpdateError('invalid retained size')
    d=json.loads(raw)
    need={'schema','retained_at','observed_at','authority','retention_reason','source_evidence_sha256','notable_evidence_ids','items'}
    if not isinstance(d,dict) or set(d)!=need or d.get('schema')!='K.WORLD.RETAINED.EVIDENCE.1': raise EventUpdateError('invalid retained envelope')
    if d.get('authority')!='EVIDENCE_ONLY' or d.get('retention_reason')!='K_NOTABLE_EVIDENCE_SELECTION': raise EventUpdateError('invalid retained policy')
    items=d.get('items'); ids=d.get('notable_evidence_ids')
    if not isinstance(items,list) or not (1<=len(items)<=8) or not isinstance(ids,list) or len(ids)!=len(set(ids)): raise EventUpdateError('invalid notable set')
    by={x.get('evidence_id'):x for x in items if isinstance(x,dict)}
    if set(by)!=set(ids): raise EventUpdateError('retained ids mismatch')
    for x in items:
        if x.get('status')!='OBSERVED_UNVERIFIED' or x.get('memory_eligible') is not False: raise EventUpdateError('evidence trust escalation')
    return items

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('retained_file'); ap.add_argument('--state-dir',default='/root/K/K/world/event_state'); ap.add_argument('--updates-dir',default='/root/K/K/world/event_updates'); ap.add_argument('--graph-state-dir',default='/root/K/K/world/entity_graph'); ap.add_argument('--graph-updates-dir',default='/root/K/K/world/entity_graph_updates'); a=ap.parse_args()
    items=load_retained(a.retained_file)
    out=apply_notable(items,a.state_dir,a.updates_dir)
    annotated=annotate_items(items,state_path=pathlib.Path(out['state']))
    graph=apply_observations(annotated,a.graph_state_dir,a.graph_updates_dir)
    print(json.dumps({'status':'PASS',**out,'graph_state':graph['state'],'graph_updates':graph['updates'],'graph_entities':graph['entities'],'graph_relations':graph['relations'],'graph_processed':graph['processed'],'graph_skipped':graph['skipped']},ensure_ascii=False,sort_keys=True))
if __name__=='__main__': main()
