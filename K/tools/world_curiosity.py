#!/usr/bin/env python3
from __future__ import annotations
from datetime import datetime, timezone
import argparse, hashlib, json, os, pathlib, sys

MODEL_DEFAULT=pathlib.Path('/root/K/K/world/current_model/current.json')
STATE_DEFAULT=pathlib.Path('/root/K/K/world/curiosity_state/state.json')
STATE_SCHEMA='K.WORLD.CURIOSITY.STATE.1'
MAX_ATTEMPTS=2
GLOBAL_COOLDOWN_SECONDS=3600
QUESTION_COOLDOWN_SECONDS=21600

class CuriosityError(ValueError): pass

def now_utc(): return datetime.now(timezone.utc)
def norm_query(v): return ' '.join(str(v or '').split())[:200]
def qid(query): return hashlib.sha256(norm_query(query).casefold().encode('utf-8')).hexdigest()
def parse_time(v):
    if not v: return None
    try:
        d=datetime.fromisoformat(str(v)); return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except Exception: return None

def load_json(path,max_bytes=262144):
    p=pathlib.Path(path); raw=p.read_bytes()
    if not raw or len(raw)>max_bytes: raise CuriosityError(f'invalid size: {p}')
    d=json.loads(raw)
    if not isinstance(d,dict): raise CuriosityError('object required')
    return d,raw

def atomic_json(path,obj):
    p=pathlib.Path(path); p.parent.mkdir(parents=True,exist_ok=True)
    raw=(json.dumps(obj,ensure_ascii=False,sort_keys=True,separators=(',',':'))+'\n').encode()
    tmp=p.parent/f'.{p.name}.tmp'; tmp.write_bytes(raw); os.chmod(tmp,0o644); os.replace(tmp,p)

def load_model(path):
    d,raw=load_json(path)
    if d.get('schema')!='K.WORLD.CURRENT.MODEL.1' or d.get('authority')!='DERIVED_COGNITIVE_VIEW_ONLY': raise CuriosityError('invalid current model')
    if d.get('memory_eligible') is not False or d.get('policy',{}).get('fresh_search_required_for_current_fact') is not True: raise CuriosityError('invalid current model policy')
    q=d.get('open_questions')
    if not isinstance(q,list) or len(q)>8: raise CuriosityError('invalid open questions')
    for x in q:
        if not isinstance(x,dict) or x.get('status')!='OPEN_UNVERIFIED': raise CuriosityError('invalid open question')
        query=norm_query(x.get('query'))
        if not query: raise CuriosityError('empty open question')
    return d,hashlib.sha256(raw).hexdigest()

def load_state(path):
    p=pathlib.Path(path)
    if not p.exists(): return {'schema':STATE_SCHEMA,'last_global_attempt_at':None,'questions':{}}
    d,_=load_json(p,65536)
    if d.get('schema')!=STATE_SCHEMA or not isinstance(d.get('questions'),dict): raise CuriosityError('invalid curiosity state')
    return d

def choose(model_path=MODEL_DEFAULT,state_path=STATE_DEFAULT,now=None):
    now=now or now_utc(); model,msha=load_model(model_path); state=load_state(state_path)
    last=parse_time(state.get('last_global_attempt_at'))
    if last and (now-last.astimezone(timezone.utc)).total_seconds()<GLOBAL_COOLDOWN_SECONDS:
        return {'schema':'K.WORLD.CURIOSITY.PICK.1','status':'NOOP','reason':'GLOBAL_COOLDOWN','model_sha256':msha}
    for x in model['open_questions']:
        query=norm_query(x.get('query')); ident=qid(query); rec=state['questions'].get(ident,{})
        attempts=int(rec.get('attempts',0))
        if attempts>=MAX_ATTEMPTS: continue
        qlast=parse_time(rec.get('last_attempt_at'))
        if qlast and (now-qlast.astimezone(timezone.utc)).total_seconds()<QUESTION_COOLDOWN_SECONDS: continue
        return {'schema':'K.WORLD.CURIOSITY.PICK.1','status':'READY','question_id':ident,'query':query,'reason':str(x.get('reason') or '')[:500],'model_sha256':msha,'previous_attempts':attempts}
    return {'schema':'K.WORLD.CURIOSITY.PICK.1','status':'NOOP','reason':'NO_ELIGIBLE_OPEN_QUESTION','model_sha256':msha}

def mark_attempt(pick_path,state_path=STATE_DEFAULT,now=None):
    now=now or now_utc(); p,_=load_json(pick_path,32768)
    if p.get('schema')!='K.WORLD.CURIOSITY.PICK.1' or p.get('status')!='READY': raise CuriosityError('ready pick required')
    ident=p.get('question_id'); query=norm_query(p.get('query'))
    if ident!=qid(query): raise CuriosityError('question id mismatch')
    state=load_state(state_path); rec=state['questions'].get(ident,{})
    attempts=int(rec.get('attempts',0))+1
    if attempts>MAX_ATTEMPTS: raise CuriosityError('attempt limit exceeded')
    state['last_global_attempt_at']=now.isoformat(); state['questions'][ident]={'query':query,'attempts':attempts,'last_attempt_at':now.isoformat()}
    atomic_json(state_path,state)
    return {'schema':'K.WORLD.CURIOSITY.MARK.1','status':'PASS','question_id':ident,'attempts':attempts,'at':now.isoformat()}

def search_batch(pick_path,executor=None,now=None):
    now=now or now_utc(); p,_=load_json(pick_path,32768)
    if p.get('schema')!='K.WORLD.CURIOSITY.PICK.1' or p.get('status')!='READY': raise CuriosityError('ready pick required')
    if executor is None:
        sys.path.insert(0,'/root/K/K/src')
        from kk_k.external_tools import execute_external_tool
        executor=execute_external_tool
    query=norm_query(p.get('query')); reason=str(p.get('reason') or '')[:500]
    try:
        r=executor({'schema':'K.EXTERNAL.TOOL.REQUEST.2','tool':'browser.search','args':{'query':query}})
        verdict=r.get('verdict') if isinstance(r,dict) else None
        if verdict not in {'PASS','VETO'}: raise CuriosityError('invalid tool verdict')
        receipt=r if verdict=='PASS' else (r if isinstance(r,dict) else None)
    except Exception:
        verdict='VETO'; receipt=None
    return {'schema':'K.WORLD.FOLLOWUP.BATCH.1','observed_at':now.isoformat(),'parent_judgment_sha256':p['model_sha256'],'authority':'EVIDENCE_ONLY','items':[{'query':query,'reason':reason or '跨轮继续核实此前未解决的问题','verdict':verdict,'receipt':receipt}]}

def main():
    ap=argparse.ArgumentParser(); sp=ap.add_subparsers(dest='cmd',required=True)
    p=sp.add_parser('pick'); p.add_argument('--model',default=str(MODEL_DEFAULT)); p.add_argument('--state',default=str(STATE_DEFAULT))
    m=sp.add_parser('mark'); m.add_argument('pick_file'); m.add_argument('--state',default=str(STATE_DEFAULT))
    s=sp.add_parser('search'); s.add_argument('pick_file')
    a=ap.parse_args()
    if a.cmd=='pick': out=choose(a.model,a.state)
    elif a.cmd=='mark': out=mark_attempt(a.pick_file,a.state)
    else: out=search_batch(a.pick_file)
    print(json.dumps(out,ensure_ascii=False,sort_keys=True,separators=(',',':')))

if __name__=='__main__': main()
