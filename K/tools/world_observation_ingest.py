#!/usr/bin/env python3
"""Validate raw observer output and archive raw + normalized evidence without promoting belief."""
from __future__ import annotations
from datetime import datetime, timezone
import hashlib, json, os, pathlib, sys
from urllib.parse import parse_qs, urlparse
from world_source_quality import classify_source

TOPICS=('global_affairs','conflicts_emergencies','economy_finance','ai_technology','platform_infrastructure')
ROOT=pathlib.Path('/root/K/K/world')
OUT=ROOT/'observations'
EVIDENCE=ROOT/'evidence'
LIFECYCLE=ROOT/'lifecycle'

def fail(msg): raise SystemExit(msg)
def canon(obj): return json.dumps(obj,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
def atomic_bytes(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.parent/f'.{path.name}.tmp'; tmp.write_bytes(data); os.chmod(tmp,0o644); os.replace(tmp,path)
def atomic_text(path,text): atomic_bytes(path,text.encode('utf-8'))

def source_url(url):
    try:
        p=urlparse(url)
        if p.hostname and p.hostname.lower().endswith('bing.com') and p.path.endswith('/news/apiclick.aspx'):
            target=parse_qs(p.query).get('url',[None])[0]
            if target: return target
    except Exception:
        pass
    return url

def validate(d):
    if set(d)!={'schema','observed_at','mode','authority','topics'}: fail('invalid envelope')
    if d['schema']!='K.WORLD.OBSERVATION.BATCH.1' or d['mode']!='READ_ONLY_ACTIVE_OBSERVATION' or d['authority']!='EVIDENCE_ONLY': fail('invalid policy')
    dt=datetime.fromisoformat(d['observed_at'])
    if dt.tzinfo is None: fail('timezone required')
    items=d['topics']
    if not isinstance(items,list) or [x.get('topic') for x in items]!=list(TOPICS): fail('invalid topics')
    for x in items:
        if set(x)!={'topic','query','verdict','receipt'} or x['verdict'] not in {'PASS','VETO'}: fail('invalid item')
        if not isinstance(x['query'],str) or not (1<=len(x['query'])<=200): fail('invalid query')
        r=x['receipt']
        if x['verdict']=='PASS':
            if not isinstance(r,dict) or r.get('schema')!='K.EXTERNAL.TOOL.RECEIPT.1' or r.get('tool')!='browser.search' or r.get('verdict')!='PASS' or r.get('human_required') is not False: fail('invalid receipt')
            results=r.get('fk_tool_receipt',{}).get('evidence',{}).get('search',{}).get('results',[])
            if not isinstance(results,list) or len(results)>3: fail('invalid results')
        elif r is not None and (not isinstance(r,dict) or r.get('verdict')!='VETO'): fail('invalid veto')
    return dt

def normalize(d):
    rows=[]
    for x in d['topics']:
        if x['verdict']!='PASS': continue
        results=x['receipt'].get('fk_tool_receipt',{}).get('evidence',{}).get('search',{}).get('results',[])
        for z in results:
            raw_url=str(z.get('url',''))[:4096]
            url=source_url(raw_url)[:4096]
            host=(urlparse(url).hostname or '').lower()
            source_meta=classify_source(url,host)
            core={
                'topic':x['topic'],'query':x['query'],'title':str(z.get('title',''))[:500],
                'snippet':str(z.get('snippet',''))[:2000],'url':url,'source_host':host,**source_meta,
                'source_published_at':None,'observed_at':d['observed_at'],
                'status':'OBSERVED_UNVERIFIED','belief_status':'NOT_EVALUATED','memory_eligible':False,
                'confidence':{'level':'LOW','basis':'SINGLE_SEARCH_RESULT_UNCORROBORATED'},
                'corroboration':{'independent_sources':1,'status':'NOT_CHECKED'},
                'conflict':{'status':'NOT_CHECKED'},
            }
            digest=hashlib.sha256(canon(core)).hexdigest()
            rows.append({'evidence_id':digest[:20],'evidence_sha256':digest,**core})
    return {
        'schema':'K.WORLD.EVIDENCE.SET.1','observed_at':d['observed_at'],'authority':'EVIDENCE_ONLY',
        'policy':{'observed_is_believed':False,'search_result_is_long_term_memory':False},'items':rows,
    }

def main():
    if len(sys.argv)!=2: fail('one input required')
    src=pathlib.Path(sys.argv[1]); raw=src.read_bytes()
    if not raw or len(raw)>65536: fail('invalid batch size')
    d=json.loads(raw); dt=validate(d)
    batch=canon(d); stamp=dt.astimezone(timezone.utc).strftime('%Y%m%dT%H%M%SZ'); digest=hashlib.sha256(batch).hexdigest()
    raw_target=OUT/f'{stamp}-{digest[:12]}.json'; atomic_bytes(raw_target,batch+b'\n')
    evidence=normalize(d); evbytes=canon(evidence); evdigest=hashlib.sha256(evbytes).hexdigest()
    ev_target=EVIDENCE/f'{stamp}-{evdigest[:12]}.json'; atomic_bytes(ev_target,evbytes+b'\n')
    lifecycle={'schema':'K.WORLD.LIFECYCLE.1','created_at':datetime.now(timezone.utc).isoformat(),'observation_path':str(raw_target),'observation_sha256':digest,'evidence_path':str(ev_target),'evidence_sha256':evdigest}
    life_target=LIFECYCLE/(ev_target.name+'.json'); atomic_bytes(life_target,canon(lifecycle)+b'\n')
    lines=['# Latest World Observation','',f'- observed_at: {d["observed_at"]}',f'- raw_sha256: {digest}',f'- evidence_sha256: {evdigest}','- authority: EVIDENCE_ONLY','- belief_status: NOT_EVALUATED','- memory_eligible: false','']
    grouped={t:[] for t in TOPICS}
    for r in evidence['items']: grouped[r['topic']].append(r)
    for topic in TOPICS:
        lines.append(f'## {topic}')
        if not grouped[topic]: lines.append('- no verified search result')
        for r in grouped[topic]:
            lines += [f'- [{r["title"]}]({r["url"]})',f'  - source: {r["source_host"] or "unknown"}',f'  - status: {r["status"]}; confidence: {r["confidence"]["level"]}',f'  - evidence_sha256: {r["evidence_sha256"]}']
    atomic_text(OUT/'latest.md','\n'.join(lines)+'\n')
    print(json.dumps({'status':'PASS','file':str(raw_target),'sha256':digest,'evidence_file':str(ev_target),'evidence_sha256':evdigest,'evidence_items':len(evidence['items']),'lifecycle_file':str(life_target)},sort_keys=True))
if __name__=='__main__': main()
