#!/usr/bin/env python3
from __future__ import annotations
from datetime import datetime,timezone
import hashlib,json,os,pathlib,sys
OUT=pathlib.Path('/root/K/K/world/continuity')
STATUSES={'NEW','PERSISTING','CHANGED','CONTRADICTED','STALE'}
CONF={'LOW'}
class ContinuityIngestError(ValueError): pass

def load(path,max_bytes):
 raw=pathlib.Path(path).read_bytes()
 if not raw or len(raw)>max_bytes: raise ContinuityIngestError('invalid size')
 try: d=json.loads(raw)
 except Exception as exc: raise ContinuityIngestError('invalid JSON') from exc
 if not isinstance(d,dict): raise ContinuityIngestError('object required')
 return d,raw

def validate_context(path):
 d,raw=load(path,131072)
 if set(d)!={'schema','generated_at','authority','memory_eligible','rounds'} or d.get('schema')!='K.WORLD.CONTINUITY.CONTEXT.1': raise ContinuityIngestError('invalid context')
 if d.get('authority')!='EVIDENCE_ONLY' or d.get('memory_eligible') is not False: raise ContinuityIngestError('invalid context policy')
 rounds=d.get('rounds')
 if not isinstance(rounds,list) or not (2<=len(rounds)<=4): raise ContinuityIngestError('invalid context rounds')
 by_round={}; all_rounds=[]
 for r in rounds:
  rh=r.get('round_context_sha256'); ev=r.get('evidence')
  if not isinstance(rh,str) or len(rh)!=64 or not isinstance(ev,list): raise ContinuityIngestError('invalid context round')
  ids={x.get('evidence_id') for x in ev if isinstance(x,dict)}
  if None in ids: raise ContinuityIngestError('invalid context evidence')
  by_round[rh]=ids; all_rounds.append(rh)
 return hashlib.sha256(raw).hexdigest(),by_round,all_rounds
def validate_run(path,context_path):
 d,raw=load(path,65536)
 need={'schema','evaluated_at','source_context_sha256','authority','memory_eligible','status','proposal','critic','judge'}
 if set(d)!=need or d.get('schema')!='K.WORLD.CONTINUITY.RUN.1': raise ContinuityIngestError('invalid run envelope')
 if d.get('authority')!='COGNITIVE_CONTINUITY_PROPOSAL_ONLY' or d.get('memory_eligible') is not False: raise ContinuityIngestError('trust escalation')
 context_sha,by_round,rounds=validate_context(context_path)
 if d.get('source_context_sha256')!=context_sha: raise ContinuityIngestError('context hash mismatch')
 try: dt=datetime.fromisoformat(d['evaluated_at'])
 except Exception as exc: raise ContinuityIngestError('invalid evaluated_at') from exc
 if dt.tzinfo is None: raise ContinuityIngestError('timezone required')
 p=d.get('proposal')
 if not isinstance(p,dict) or set(p)!={'schema','assessment','items'} or p.get('schema')!='K.WORLD.CONTINUITY.PROPOSAL.1': raise ContinuityIngestError('invalid proposal')
 if not isinstance(p.get('assessment'),str) or not (1<=len(p['assessment'].encode('utf-8'))<=800): raise ContinuityIngestError('invalid assessment')
 items=p.get('items')
 if not isinstance(items,list) or len(items)>4: raise ContinuityIngestError('invalid items')
 current=rounds[-1]
 for x in items:
  req={'subject','status','evidence_ids','round_context_sha256s','rationale','confidence'}
  if not isinstance(x,dict) or set(x)!=req: raise ContinuityIngestError('invalid item')
  if x.get('status') not in STATUSES or x.get('confidence') not in CONF: raise ContinuityIngestError('invalid status/confidence')
  if not isinstance(x.get('subject'),str) or not (1<=len(x['subject'].encode('utf-8'))<=240): raise ContinuityIngestError('invalid subject')
  if not isinstance(x.get('rationale'),str) or not (1<=len(x['rationale'].encode('utf-8'))<=300): raise ContinuityIngestError('invalid rationale')
  e=x.get('evidence_ids'); rs=x.get('round_context_sha256s')
  if not isinstance(e,list) or not (1<=len(e)<=6) or len(set(e))!=len(e): raise ContinuityIngestError('invalid evidence refs')
  if not isinstance(rs,list) or not (1<=len(rs)<=4) or len(set(rs))!=len(rs) or any(z not in by_round for z in rs): raise ContinuityIngestError('invalid round refs')
  for rh in rs:
   if not (set(e)&by_round[rh]): raise ContinuityIngestError('round lacks cited evidence')
  if any(eid not in set().union(*(by_round[r] for r in rs)) for eid in e): raise ContinuityIngestError('evidence outside cited rounds')
  status=x['status']
  if status=='NEW' and set(rs)!={current}: raise ContinuityIngestError('NEW must reference current only')
  if status=='STALE' and current in rs: raise ContinuityIngestError('STALE cannot reference current')
  if status in {'PERSISTING','CHANGED','CONTRADICTED'} and (current not in rs or len(rs)<2): raise ContinuityIngestError('cross-round status needs current and history')
 c=d.get('critic'); j=d.get('judge')
 if not isinstance(c,dict) or set(c)!={'critique','risk_flags'} or not isinstance(c.get('critique'),str) or not isinstance(c.get('risk_flags'),list): raise ContinuityIngestError('invalid critic')
 if not isinstance(j,dict) or set(j)!={'verdict'} or j.get('verdict') not in {'APPROVE_A','REJECT_A'}: raise ContinuityIngestError('invalid judge')
 expected='APPROVED_PROVISIONAL' if j['verdict']=='APPROVE_A' else 'REJECTED'
 if d.get('status')!=expected: raise ContinuityIngestError('status mismatch')
 return d,dt
def main():
 if len(sys.argv)!=3: raise SystemExit('run file and context file required')
 d,dt=validate_run(sys.argv[1],sys.argv[2])
 canon=(json.dumps(d,ensure_ascii=False,sort_keys=True,separators=(',',':'))+'\n').encode()
 digest=hashlib.sha256(canon).hexdigest(); OUT.mkdir(parents=True,exist_ok=True)
 stamp=dt.astimezone(timezone.utc).strftime('%Y%m%dT%H%M%SZ'); target=OUT/f'{stamp}-{digest[:12]}.json'
 tmp=OUT/f'.{target.name}.tmp'; tmp.write_bytes(canon); os.chmod(tmp,0o644); os.replace(tmp,target)
 p=d['proposal']; lines=['# Latest World Continuity','',f'- evaluated_at: {d["evaluated_at"]}',f'- status: {d["status"]}',f'- source_context_sha256: {d["source_context_sha256"]}',f'- continuity_sha256: {digest}','- authority: COGNITIVE_CONTINUITY_PROPOSAL_ONLY','- memory_eligible: false','','## Assessment',p['assessment'],'','## Continuity items']
 for x in p['items']:
  lines.append(f'- [{x["status"]}] {x["subject"]} ({x["confidence"]})')
  lines.append(f'  - {x["rationale"]}')
 if not p['items']: lines.append('- none')
 latest=OUT/'latest.md'; tmp2=OUT/'.latest.md.tmp'; tmp2.write_text('\n'.join(lines)+'\n',encoding='utf-8'); os.chmod(tmp2,0o644); os.replace(tmp2,latest)
 print(json.dumps({'status':'PASS','file':str(target),'sha256':digest,'continuity_status':d['status'],'items':len(p['items'])},sort_keys=True))
if __name__=='__main__': main()
