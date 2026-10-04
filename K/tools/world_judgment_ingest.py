#!/usr/bin/env python3
from __future__ import annotations
from datetime import datetime, timezone
import hashlib,json,os,pathlib,string,sys
OUT=pathlib.Path('/root/K/K/world/judgments')
TOP=frozenset({'schema','judged_at','source_observed_at','source_evidence_sha256','authority','memory_eligible','status','proposal','critic','judge'})
PKEYS=frozenset({'schema','assessment','priority_evidence_ids','noise_evidence_ids','corroborate_evidence_ids','follow_up_queries'})
class JudgmentIngestError(ValueError): pass

def strict(raw:bytes)->dict:
 def hook(pairs):
  out={}
  for k,v in pairs:
   if k in out: raise JudgmentIngestError('duplicate JSON key')
   out[k]=v
  return out
 try: d=json.loads(raw.decode('utf-8'),object_pairs_hook=hook)
 except JudgmentIngestError: raise
 except Exception as exc: raise JudgmentIngestError('invalid JSON') from exc
 if not isinstance(d,dict): raise JudgmentIngestError('object required')
 return d

def valid_sha(v): return isinstance(v,str) and len(v)==64 and all(c in string.hexdigits for c in v)

def main():
 if len(sys.argv)!=2: raise SystemExit('one judgment input required')
 raw=pathlib.Path(sys.argv[1]).read_bytes()
 if not raw or len(raw)>65536: raise JudgmentIngestError('invalid size')
 d=strict(raw)
 if frozenset(d)!=TOP or d.get('schema')!='K.WORLD.JUDGMENT.RUN.1': raise JudgmentIngestError('invalid envelope')
 if d.get('authority')!='COGNITIVE_PROPOSAL_ONLY' or d.get('memory_eligible') is not False: raise JudgmentIngestError('trust escalation forbidden')
 if not valid_sha(d.get('source_evidence_sha256')): raise JudgmentIngestError('invalid source hash')
 try: dt=datetime.fromisoformat(d['judged_at'])
 except Exception as exc: raise JudgmentIngestError('invalid judged_at') from exc
 if dt.tzinfo is None: raise JudgmentIngestError('timezone required')
 p=d.get('proposal')
 if not isinstance(p,dict) or frozenset(p)!=PKEYS or p.get('schema')!='K.WORLD.JUDGMENT.PROPOSAL.1': raise JudgmentIngestError('invalid proposal')
 if not isinstance(p.get('assessment'),str) or not (1<=len(p['assessment'].encode('utf-8'))<=2400): raise JudgmentIngestError('invalid assessment')
 for key in ('priority_evidence_ids','noise_evidence_ids','corroborate_evidence_ids'):
  z=p.get(key)
  if not isinstance(z,list) or len(z)>5 or len(set(z))!=len(z) or any(not isinstance(x,str) for x in z): raise JudgmentIngestError('invalid id list')
 fq=p.get('follow_up_queries')
 if not isinstance(fq,list) or len(fq)>3: raise JudgmentIngestError('invalid followups')
 for q in fq:
  if not isinstance(q,dict) or set(q)!={'query','reason'} or not isinstance(q['query'],str) or not isinstance(q['reason'],str): raise JudgmentIngestError('invalid followup')
 c=d.get('critic'); j=d.get('judge')
 if not isinstance(c,dict) or set(c)!={'critique','risk_flags'} or not isinstance(c['critique'],str) or not isinstance(c['risk_flags'],list): raise JudgmentIngestError('invalid critic')
 if not isinstance(j,dict) or set(j)!={'verdict'} or j['verdict'] not in {'APPROVE_A','REJECT_A'}: raise JudgmentIngestError('invalid judge')
 expected='APPROVED_PROVISIONAL' if j['verdict']=='APPROVE_A' else 'REJECTED'
 if d.get('status')!=expected: raise JudgmentIngestError('status mismatch')
 canon=json.dumps(d,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode(); digest=hashlib.sha256(canon).hexdigest()
 OUT.mkdir(parents=True,exist_ok=True); stamp=dt.astimezone(timezone.utc).strftime('%Y%m%dT%H%M%SZ'); target=OUT/f'{stamp}-{digest[:12]}.json'
 tmp=OUT/f'.{target.name}.tmp'; tmp.write_bytes(canon+b'\n'); os.chmod(tmp,0o644); os.replace(tmp,target)
 lines=['# Latest World Judgment','',f'- judged_at: {d["judged_at"]}',f'- status: {d["status"]}',f'- source_evidence_sha256: {d["source_evidence_sha256"]}',f'- judgment_sha256: {digest}','- authority: COGNITIVE_PROPOSAL_ONLY','- memory_eligible: false','', '## Assessment',p['assessment'],'','## Priority evidence']
 lines.extend(f'- {x}' for x in p['priority_evidence_ids'])
 if not p['priority_evidence_ids']: lines.append('- none')
 lines+=['','## Needs corroboration']; lines.extend(f'- {x}' for x in p['corroborate_evidence_ids'])
 if not p['corroborate_evidence_ids']: lines.append('- none')
 lines+=['','## Follow-up searches']
 for q in fq: lines.append(f'- {q["query"]} — {q["reason"]}')
 if not fq: lines.append('- none')
 latest=OUT/'latest.md'; tmp2=OUT/'.latest.md.tmp'; tmp2.write_text('\n'.join(lines)+'\n',encoding='utf-8'); os.chmod(tmp2,0o644); os.replace(tmp2,latest)
 print(json.dumps({'status':'PASS','file':str(target),'sha256':digest,'judgment_status':d['status']},sort_keys=True))

if __name__=='__main__': main()