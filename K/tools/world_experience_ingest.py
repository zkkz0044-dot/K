#!/usr/bin/env python3
from __future__ import annotations
from datetime import datetime, timezone
import hashlib, json, os, pathlib, sys
OUT=pathlib.Path('/root/K/K/world/experiences')

class ExperienceError(ValueError): pass

def load_json(path,max_bytes=131072):
    raw=pathlib.Path(path).read_bytes()
    if not raw or len(raw)>max_bytes: raise ExperienceError('invalid size')
    try: d=json.loads(raw)
    except Exception as exc: raise ExperienceError('invalid JSON') from exc
    if not isinstance(d,dict): raise ExperienceError('object required')
    return d,raw,hashlib.sha256(raw).hexdigest()

def validate_evidence(path):
    d,raw,sha=load_json(path)
    if set(d)!={'schema','observed_at','authority','policy','items'} or d.get('schema')!='K.WORLD.EVIDENCE.SET.1': raise ExperienceError('invalid evidence')
    if d.get('authority')!='EVIDENCE_ONLY' or d.get('policy')!={'observed_is_believed':False,'search_result_is_long_term_memory':False}: raise ExperienceError('invalid evidence policy')
    for x in d.get('items',[]):
        if not isinstance(x,dict) or x.get('status')!='OBSERVED_UNVERIFIED' or x.get('memory_eligible') is not False: raise ExperienceError('evidence trust escalation')
    return d,sha
def validate_think(path):
    d,raw,sha=load_json(path,65536)
    need={'schema','thought_at','source_evidence_sha256','authority','memory_eligible','thought'}
    if set(d)!=need or d.get('schema')!='K.WORLD.THINK.RUN.1': raise ExperienceError('invalid think run')
    if d.get('authority')!='COGNITIVE_NOTE_ONLY' or d.get('memory_eligible') is not False: raise ExperienceError('invalid think policy')
    t=d.get('thought')
    if not isinstance(t,dict) or set(t)!={'schema','assessment','notable_evidence_ids','follow_up_queries'} or t.get('schema')!='K.WORLD.THINK.1': raise ExperienceError('invalid thought')
    return d,sha

def atomic(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.parent/f'.{path.name}.tmp'
    tmp.write_bytes(data); os.chmod(tmp,0o644); os.replace(tmp,path)

def main():
    if len(sys.argv)!=5: raise SystemExit('base evidence, initial think, final evidence, final think required')
    base,bsha=validate_evidence(sys.argv[1]); initial,isha=validate_think(sys.argv[2])
    final,fsha=validate_evidence(sys.argv[3]); last,lsha=validate_think(sys.argv[4])
    if initial['source_evidence_sha256']!=bsha: raise ExperienceError('initial source mismatch')
    if last['source_evidence_sha256']!=fsha: raise ExperienceError('final source mismatch')
    out={'schema':'K.WORLD.EXPERIENCE.1','observed_at':base['observed_at'],'experienced_at':datetime.now(timezone.utc).isoformat(),'authority':'COGNITIVE_EXPERIENCE_ONLY','memory_eligible':False,'base_evidence_sha256':bsha,'final_evidence_sha256':fsha,'followup_performed':bsha!=fsha,'initial_thought_sha256':isha,'final_thought_sha256':lsha,'initial_thought':initial['thought'],'final_thought':last['thought']}
    raw=(json.dumps(out,ensure_ascii=False,sort_keys=True,separators=(',',':'))+'\n').encode()
    digest=hashlib.sha256(raw).hexdigest(); stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    target=OUT/f'{stamp}-{digest[:12]}.json'; atomic(target,raw)
    latest=OUT/'latest.json'; atomic(latest,raw)
    lines=['# Latest World Experience','',f'- observed_at: {out["observed_at"]}',f'- experienced_at: {out["experienced_at"]}','- authority: COGNITIVE_EXPERIENCE_ONLY','- memory_eligible: false',f'- followup_performed: {str(out["followup_performed"]).lower()}','','## Initial thought',out['initial_thought']['assessment'],'','## Final thought',out['final_thought']['assessment']]
    atomic(OUT/'latest.md',('\n'.join(lines)+'\n').encode())
    print(json.dumps({'status':'PASS','file':str(target),'sha256':digest,'followup_performed':out['followup_performed']},sort_keys=True))

if __name__=='__main__': main()
