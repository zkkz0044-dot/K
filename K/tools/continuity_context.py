#!/usr/bin/env python3
from __future__ import annotations
import hashlib,json,pathlib,sys
ROOT=pathlib.Path('/root/K/K/world')
POLICY={'observed_is_believed':False,'search_result_is_long_term_memory':False}
class ContinuityContextError(ValueError): pass

def load_json(path,max_bytes=65536):
 raw=path.read_bytes()
 if not raw or len(raw)>max_bytes: raise ContinuityContextError('invalid file size')
 try: d=json.loads(raw)
 except Exception as exc: raise ContinuityContextError('invalid JSON') from exc
 if not isinstance(d,dict): raise ContinuityContextError('object required')
 return d,hashlib.sha256(raw).hexdigest()

def load_evidence(path):
 d,sha=load_json(path)
 if set(d)!={'schema','observed_at','authority','policy','items'}: raise ContinuityContextError('invalid evidence envelope')
 if d['schema']!='K.WORLD.EVIDENCE.SET.1' or d['authority']!='EVIDENCE_ONLY' or d['policy']!=POLICY: raise ContinuityContextError('invalid evidence policy')
 if not isinstance(d['items'],list) or len(d['items'])>20: raise ContinuityContextError('invalid evidence items')
 rows=[]
 for x in d['items']:
  if not isinstance(x,dict) or x.get('status')!='OBSERVED_UNVERIFIED' or x.get('memory_eligible') is not False: raise ContinuityContextError('evidence trust escalation')
  rows.append({'evidence_id':x.get('evidence_id'),'topic':x.get('topic'),'title':x.get('title'),'source_host':x.get('source_host'),'observed_at':x.get('observed_at')})
 return {'observed_at':d['observed_at'],'sha256':sha,'items':rows[:12]}
def load_judgment(path):
 d,sha=load_json(path)
 required={'schema','judged_at','source_observed_at','source_evidence_sha256','authority','memory_eligible','status','proposal','critic','judge'}
 if set(d)!=required or d.get('schema')!='K.WORLD.JUDGMENT.RUN.1': raise ContinuityContextError('invalid judgment envelope')
 if d.get('authority')!='COGNITIVE_PROPOSAL_ONLY' or d.get('memory_eligible') is not False: raise ContinuityContextError('invalid judgment policy')
 if d.get('status') not in {'APPROVED_PROVISIONAL','REJECTED'}: raise ContinuityContextError('invalid judgment status')
 p=d.get('proposal')
 if not isinstance(p,dict) or p.get('schema')!='K.WORLD.JUDGMENT.PROPOSAL.1': raise ContinuityContextError('invalid proposal')
 return d,sha

def build(limit=4):
 if type(limit) is not int or not (2<=limit<=4): raise ContinuityContextError('invalid limit')
 contexts=[]
 for p in (ROOT/'round_context').glob('*.json'):
  e=load_evidence(p); contexts.append((e['observed_at'],p,e))
 contexts.sort(key=lambda x:x[0])
 judgments=[]
 for p in (ROOT/'judgments').glob('*.json'):
  d,sha=load_judgment(p); judgments.append((d,sha,p))
 rounds=[]
 for _obs,p,e in contexts[-limit:]:
  matches=[x for x in judgments if x[0]['source_evidence_sha256']==e['sha256']]
  if not matches: continue
  d,jsha,jp=sorted(matches,key=lambda x:x[0]['judged_at'])[-1]
  pr=d['proposal']
  rounds.append({'observed_at':e['observed_at'],'round_context_sha256':e['sha256'],'evidence':e['items'],'judged_at':d['judged_at'],'judgment_sha256':jsha,'judgment_status':d['status'],'assessment':pr['assessment'],'priority_evidence_ids':pr['priority_evidence_ids'],'corroborate_evidence_ids':pr['corroborate_evidence_ids']})
 if len(rounds)<2: raise ContinuityContextError('insufficient complete rounds')
 return rounds
from datetime import datetime,timezone
import os

def main():
 rounds=build(4)
 out={'schema':'K.WORLD.CONTINUITY.CONTEXT.1','generated_at':datetime.now(timezone.utc).isoformat(),'authority':'EVIDENCE_ONLY','memory_eligible':False,'rounds':rounds}
 raw=(json.dumps(out,ensure_ascii=False,sort_keys=True,separators=(',',':'))+'\n').encode()
 digest=hashlib.sha256(raw).hexdigest(); dest=ROOT/'continuity_context'
 dest.mkdir(parents=True,exist_ok=True)
 stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'); target=dest/f'{stamp}-{digest[:12]}.json'
 tmp=dest/f'.{target.name}.tmp'; tmp.write_bytes(raw); os.chmod(tmp,0o644); os.replace(tmp,target)
 latest=dest/'latest.json'; tmp2=dest/'.latest.json.tmp'; tmp2.write_bytes(raw); os.chmod(tmp2,0o644); os.replace(tmp2,latest)
 print(json.dumps({'status':'PASS','file':str(target),'sha256':digest,'rounds':len(rounds)},sort_keys=True))

if __name__=='__main__': main()
