#!/usr/bin/env python3
from __future__ import annotations
from datetime import datetime, timezone
import argparse, json, os, pathlib

SCHEMA='K.WORLD.CURRENT.MODEL.1'
AUTHORITY='DERIVED_COGNITIVE_VIEW_ONLY'

class CurrentModelError(ValueError): pass

def load_json(path,max_bytes=524288):
    p=pathlib.Path(path); raw=p.read_bytes()
    if not raw or len(raw)>max_bytes: raise CurrentModelError(f'invalid size: {p}')
    d=json.loads(raw)
    if not isinstance(d,dict): raise CurrentModelError(f'object required: {p}')
    return d

def atomic(path,data):
    path=pathlib.Path(path); path.parent.mkdir(parents=True,exist_ok=True); tmp=path.parent/f'.{path.name}.tmp'; tmp.write_bytes(data); os.chmod(tmp,0o644); os.replace(tmp,path)

def parse_time(v):
    try:
        d=datetime.fromisoformat(str(v)); return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except Exception: return None

def freshness(v,now):
    d=parse_time(v)
    if d is None: return 'UNKNOWN'
    age=max(0.0,(now-d.astimezone(timezone.utc)).total_seconds())
    if age<=7*86400: return 'RECENT'
    if age<=30*86400: return 'AGING'
    return 'STALE_CANDIDATE'

def retained_hashes(root):
    out=set(); d=root/'retained_evidence'
    if not d.exists(): return out
    for p in d.glob('*.json'):
        try:
            x=load_json(p,262144)
            if x.get('schema')=='K.WORLD.RETAINED.EVIDENCE.1' and isinstance(x.get('source_evidence_sha256'),str): out.add(x['source_evidence_sha256'])
        except Exception: continue
    return out

def active_events(root,now):
    p=root/'event_state'/'current.json'
    if not p.is_file(): return []
    d=load_json(p)
    if d.get('schema')!='K.WORLD.EVENT.STATE.1' or d.get('authority')!='DERIVED_EVENT_CANDIDATE_ONLY' or d.get('truth_status')!='UNVERIFIED': raise CurrentModelError('invalid event state')
    rows=[]
    for e in d.get('events',[])[:16]:
        if not isinstance(e,dict): continue
        rows.append({'event_id':e.get('event_id'),'topic':e.get('topic'),'subject':e.get('subject'),'latest_subject':e.get('latest_subject'),'first_seen':e.get('first_seen'),'last_seen':e.get('last_seen'),'freshness':freshness(e.get('last_seen'),now),'update_count':int(e.get('update_count',0)),'source_groups':list(e.get('source_groups',[]))[:8],'source_classes':list(e.get('source_classes',[]))[:8],'truth_status':'UNVERIFIED_EVENT_CANDIDATE'})
    return rows

def recent_digests(root,now):
    rows=[]; d=root/'digests'
    if not d.exists(): return rows
    for p in d.glob('*.json'):
        try:
            x=load_json(p,65536)
            if x.get('schema')!='K.WORLD.DIGEST.1' or x.get('authority')!='COGNITIVE_NOTE_ONLY' or x.get('memory_eligible') is not False: continue
            exp=parse_time(x.get('expires_at'))
            if exp is None or exp.astimezone(timezone.utc)<=now: continue
            rows.append({'digested_at':x.get('digested_at'),'observed_at':x.get('observed_at'),'expires_at':x.get('expires_at'),'assessment':str(x.get('assessment') or '')[:1600],'source_evidence_sha256':x.get('source_evidence_sha256'),'truth_status':'UNVERIFIED_TEMPORARY_COGNITIVE_NOTE'})
        except Exception: continue
    rows.sort(key=lambda x:str(x.get('digested_at') or ''),reverse=True)
    return rows[:12]

def experiences(root,retained):
    live=[]; legacy=[]; d=root/'experiences'
    if not d.exists(): return live,legacy
    rows=[]
    for p in d.glob('*.json'):
        if p.name=='latest.json': continue
        try:
            x=load_json(p,262144)
            if x.get('schema')!='K.WORLD.EXPERIENCE.1' or x.get('authority')!='COGNITIVE_EXPERIENCE_ONLY' or x.get('memory_eligible') is not False: continue
            t=x.get('final_thought') or {}
            rows.append({'experienced_at':x.get('experienced_at'),'observed_at':x.get('observed_at'),'assessment':str(t.get('assessment') or '')[:1800],'notable_evidence_ids':list(t.get('notable_evidence_ids') or [])[:8],'follow_up_queries':list(t.get('follow_up_queries') or [])[:3],'final_evidence_sha256':x.get('final_evidence_sha256')})
        except Exception: continue
    rows.sort(key=lambda x:str(x.get('experienced_at') or ''),reverse=True)
    for x in rows:
        y=dict(x)
        if x.get('final_evidence_sha256') in retained:
            y['truth_status']='UNVERIFIED_NOTABLE_COGNITIVE_ASSESSMENT'; live.append(y)
        else:
            y['truth_status']='LEGACY_ORIENTATION_ONLY'; legacy.append(y)
    return live[:8],legacy[:4]

def open_questions(live):
    out=[]; seen=set()
    for x in live:
        for q in x.get('follow_up_queries',[]):
            if not isinstance(q,dict): continue
            query=' '.join(str(q.get('query') or '').split())[:200]
            reason=' '.join(str(q.get('reason') or '').split())[:500]
            if not query: continue
            key=query.casefold()
            if key in seen: continue
            seen.add(key)
            out.append({'query':query,'reason':reason,'source_experienced_at':x.get('experienced_at'),'status':'OPEN_UNVERIFIED'})
            if len(out)>=8: return out
    return out

def build(world_root='/root/K/K/world',now=None):
    root=pathlib.Path(world_root); now=now or datetime.now(timezone.utc); rh=retained_hashes(root); ev=active_events(root,now); dg=recent_digests(root,now); live,legacy=experiences(root,rh); oq=open_questions(live)
    return {'schema':SCHEMA,'generated_at':now.isoformat(),'authority':AUTHORITY,'truth_status':'MIXED_UNVERIFIED','memory_eligible':False,'policy':{'fresh_search_required_for_current_fact':True,'event_candidates_are_facts':False,'cognitive_notes_are_evidence':False,'legacy_notes_are_current_authority':False,'history_is_not_rewritten':True},'active_event_candidates':ev,'recent_temporary_digests':dg,'recent_notable_assessments':live,'open_questions':oq,'legacy_orientation_notes':legacy,'stats':{'active_event_candidates':len(ev),'recent_temporary_digests':len(dg),'recent_notable_assessments':len(live),'open_questions':len(oq),'legacy_orientation_notes':len(legacy)}}

def markdown(model):
    lines=['# K Current World Model','',f'- generated_at: {model["generated_at"]}',f'- authority: {model["authority"]}',f'- truth_status: {model["truth_status"]}','- current facts still require fresh search','', '## Active event candidates']
    if model['active_event_candidates']:
        for e in model['active_event_candidates']:
            lines.append(f'- [{e["freshness"]} / UNVERIFIED] {e["latest_subject"] or e["subject"]} — updates={e["update_count"]}, last_seen={e["last_seen"]}')
    else: lines.append('- none')
    lines+=['','## Recent temporary digests']
    if model['recent_temporary_digests']:
        for x in model['recent_temporary_digests']: lines.append(f'- [TEMP / UNVERIFIED] {x["assessment"]}')
    else: lines.append('- none')
    lines+=['','## Recent notable cognitive assessments']
    if model['recent_notable_assessments']:
        for x in model['recent_notable_assessments']: lines.append(f'- [NOTABLE / UNVERIFIED] {x["assessment"]}')
    else: lines.append('- none')
    lines+=['','## Open questions']
    if model['open_questions']:
        for x in model['open_questions']: lines.append(f'- [OPEN / UNVERIFIED] {x["query"]} — {x["reason"]}')
    else: lines.append('- none')
    lines+=['','## Legacy orientation notes']
    if model['legacy_orientation_notes']:
        for x in model['legacy_orientation_notes']: lines.append(f'- [LEGACY_ORIENTATION_ONLY] {x["assessment"]}')
    else: lines.append('- none')
    lines+=['','## Epistemic rules','- Event candidates are not facts.','- Cognitive notes are not evidence.','- Legacy notes are not current authority.','- Current-world factual answers require fresh search.','']
    return '\n'.join(lines)

def write_model(world_root='/root/K/K/world',output_dir=None):
    root=pathlib.Path(world_root); out=pathlib.Path(output_dir) if output_dir else root/'current_model'; model=build(root); raw=(json.dumps(model,ensure_ascii=False,sort_keys=True,separators=(',',':'))+'\n').encode(); md=markdown(model).encode('utf-8'); atomic(out/'current.json',raw); atomic(out/'current.md',md); return {'status':'PASS','json':str(out/'current.json'),'markdown':str(out/'current.md'),'stats':model['stats']}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--root',default='/root/K/K/world'); ap.add_argument('--output-dir'); a=ap.parse_args(); print(json.dumps(write_model(a.root,a.output_dir),ensure_ascii=False,sort_keys=True))
if __name__=='__main__': main()
