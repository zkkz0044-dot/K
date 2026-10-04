#!/usr/bin/env python3
from __future__ import annotations
import hashlib,json,os,pathlib,sys
STATE=pathlib.Path('/root/K/K/world/sensory_index')
POLICY={'observed_is_believed':False,'search_result_is_long_term_memory':False}
class DedupError(ValueError): pass

def canon_item(x):
    return {
      'topic':x.get('topic'),'url':x.get('url'),
      'title':x.get('title'),'snippet':x.get('snippet')}

def fingerprint(x):
    raw=json.dumps(canon_item(x),ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
    return hashlib.sha256(raw).hexdigest()

def load_evidence(path):
    raw=pathlib.Path(path).read_bytes(); d=json.loads(raw)
    if not isinstance(d,dict) or set(d)!={'schema','observed_at','authority','policy','items'}: raise DedupError('invalid evidence')
    if d['schema']!='K.WORLD.EVIDENCE.SET.1' or d['authority']!='EVIDENCE_ONLY' or d['policy']!=POLICY: raise DedupError('invalid policy')
    for x in d['items']:
        if x.get('status')!='OBSERVED_UNVERIFIED' or x.get('memory_eligible') is not False: raise DedupError('trust escalation')
    return d
def load_seen():
    p=STATE/'exact_seen.json'
    if not p.exists(): return set()
    d=json.loads(p.read_text())
    vals=d.get('fingerprints',[])
    if not isinstance(vals,list) or any(not isinstance(x,str) or len(x)!=64 for x in vals): raise DedupError('invalid seen registry')
    return set(vals)

def atomic_json(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    raw=(json.dumps(obj,ensure_ascii=False,sort_keys=True,separators=(',',':'))+'\n').encode()
    tmp=path.parent/f'.{path.name}.tmp'; tmp.write_bytes(raw); os.chmod(tmp,0o644); os.replace(tmp,path)

def prepare(src,out_path,receipt_path):
    d=load_evidence(src); seen=load_seen(); keep=[]; dup=[]
    for x in d['items']:
        fp=fingerprint(x)
        if fp in seen: dup.append({'fingerprint':fp,'evidence_id':x.get('evidence_id'),'url':x.get('url')})
        else:
            keep.append(x)
            seen.add(fp)
    filtered={**d,'items':keep}
    atomic_json(pathlib.Path(out_path),filtered)
    rec={'schema':'K.WORLD.EXACT.DEDUP.RECEIPT.1','source_items':len(d['items']),'delivered_items':len(keep),'exact_duplicates':len(dup),'duplicates':dup,'semantic_filtering':False}
    atomic_json(pathlib.Path(receipt_path),rec)
    return rec
def commit_delivered(src):
    d=load_evidence(src); seen=load_seen()
    for x in d['items']: seen.add(fingerprint(x))
    atomic_json(STATE/'exact_seen.json',{'schema':'K.WORLD.EXACT.SEEN.1','fingerprints':sorted(seen)})
    return {'status':'PASS','committed':len(d['items']),'seen_total':len(seen)}

def main():
    if len(sys.argv)<2: raise SystemExit('prepare|commit required')
    if sys.argv[1]=='prepare' and len(sys.argv)==5:
        print(json.dumps(prepare(sys.argv[2],sys.argv[3],sys.argv[4]),sort_keys=True,separators=(',',':')))
        return
    if sys.argv[1]=='commit' and len(sys.argv)==3:
        print(json.dumps(commit_delivered(sys.argv[2]),sort_keys=True,separators=(',',':')))
        return
    raise SystemExit('usage: prepare SRC OUT RECEIPT | commit SRC')

if __name__=='__main__': main()
