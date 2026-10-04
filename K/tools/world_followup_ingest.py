#!/usr/bin/env python3
from __future__ import annotations
from datetime import datetime, timezone
import hashlib,json,os,pathlib,sys
from urllib.parse import parse_qs,urlparse
from world_source_quality import classify_source
ROOT=pathlib.Path('/root/K/K/world'); OUT=ROOT/'followups'; EVID=ROOT/'followup_evidence'
class FollowupIngestError(ValueError): pass

def fail(x): raise FollowupIngestError(x)
def canon(x): return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
def atomic(path,data):
 path.parent.mkdir(parents=True,exist_ok=True); tmp=path.parent/f'.{path.name}.tmp'; tmp.write_bytes(data); os.chmod(tmp,0o644); os.replace(tmp,path)
def source_url(url):
 try:
  p=urlparse(url)
  if p.hostname and p.hostname.lower().endswith('bing.com') and p.path.endswith('/news/apiclick.aspx'):
   target=parse_qs(p.query).get('url',[None])[0]
   if target: return target
 except Exception: pass
 return url

def validate(d):
 if set(d)!={'schema','observed_at','parent_judgment_sha256','authority','items'} or d.get('schema')!='K.WORLD.FOLLOWUP.BATCH.1' or d.get('authority')!='EVIDENCE_ONLY': fail('invalid envelope')
 try: dt=datetime.fromisoformat(d['observed_at'])
 except Exception as exc: raise FollowupIngestError('invalid time') from exc
 if dt.tzinfo is None: fail('timezone required')
 if not isinstance(d['parent_judgment_sha256'],str) or len(d['parent_judgment_sha256'])!=64: fail('invalid parent hash')
 items=d['items']
 if not isinstance(items,list) or len(items)>3: fail('invalid items')
 for x in items:
  if not isinstance(x,dict) or set(x)!={'query','reason','verdict','receipt'} or x['verdict'] not in {'PASS','VETO'}: fail('invalid item')
  if not isinstance(x['query'],str) or not (1<=len(x['query'])<=200): fail('invalid query')
  if not isinstance(x['reason'],str) or not (1<=len(x['reason'].encode('utf-8'))<=500): fail('invalid reason')
  r=x['receipt']
  if x['verdict']=='PASS':
   if not isinstance(r,dict) or r.get('schema')!='K.EXTERNAL.TOOL.RECEIPT.1' or r.get('tool')!='browser.search' or r.get('verdict')!='PASS' or r.get('human_required') is not False: fail('invalid receipt')
   results=r.get('fk_tool_receipt',{}).get('evidence',{}).get('search',{}).get('results',[])
   if not isinstance(results,list) or len(results)>3: fail('invalid results')
  elif r is not None and (not isinstance(r,dict) or r.get('verdict')!='VETO'): fail('invalid veto')
 return dt

def normalize(d):
 rows=[]
 for x in d['items']:
  if x['verdict']!='PASS': continue
  results=x['receipt'].get('fk_tool_receipt',{}).get('evidence',{}).get('search',{}).get('results',[])
  for z in results:
   url=source_url(str(z.get('url',''))[:4096])[:4096]; host=(urlparse(url).hostname or '').lower(); source_meta=classify_source(url,host)
   core={'topic':'k_followup','query':x['query'],'title':str(z.get('title',''))[:500],'snippet':str(z.get('snippet',''))[:2000],'url':url,'source_host':host,**source_meta,'source_published_at':None,'observed_at':d['observed_at'],'status':'OBSERVED_UNVERIFIED','belief_status':'NOT_EVALUATED','memory_eligible':False,'confidence':{'level':'LOW','basis':'K_DIRECTED_SEARCH_UNCORROBORATED'},'corroboration':{'independent_sources':1,'status':'NOT_CHECKED'},'conflict':{'status':'NOT_CHECKED'}}
   digest=hashlib.sha256(canon(core)).hexdigest(); rows.append({'evidence_id':digest[:20],'evidence_sha256':digest,**core})
 return {'schema':'K.WORLD.EVIDENCE.SET.1','observed_at':d['observed_at'],'authority':'EVIDENCE_ONLY','policy':{'observed_is_believed':False,'search_result_is_long_term_memory':False},'items':rows}
def main():
 if len(sys.argv)!=2: raise SystemExit('one followup batch required')
 raw=pathlib.Path(sys.argv[1]).read_bytes()
 if not raw or len(raw)>65536: fail('invalid size')
 d=json.loads(raw); dt=validate(d); batch=canon(d)
 stamp=dt.astimezone(timezone.utc).strftime('%Y%m%dT%H%M%SZ'); digest=hashlib.sha256(batch).hexdigest()
 raw_target=OUT/f'{stamp}-{digest[:12]}.json'; atomic(raw_target,batch+b'\n')
 ev=normalize(d); evbytes=canon(ev); evdigest=hashlib.sha256(evbytes).hexdigest(); ev_target=EVID/f'{stamp}-{evdigest[:12]}.json'; atomic(ev_target,evbytes+b'\n')
 print(json.dumps({'status':'PASS','file':str(raw_target),'sha256':digest,'evidence_file':str(ev_target),'evidence_sha256':evdigest,'evidence_items':len(ev['items'])},sort_keys=True))

if __name__=='__main__': main()
