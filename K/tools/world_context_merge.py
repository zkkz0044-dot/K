#!/usr/bin/env python3
from __future__ import annotations
import json,pathlib,sys
POLICY={'observed_is_believed':False,'search_result_is_long_term_memory':False}
class MergeError(ValueError): pass

def load(path):
 raw=pathlib.Path(path).read_bytes()
 if not raw or len(raw)>65536: raise MergeError('invalid evidence size')
 d=json.loads(raw)
 if not isinstance(d,dict) or set(d)!={'schema','observed_at','authority','policy','items'}: raise MergeError('invalid envelope')
 if d.get('schema')!='K.WORLD.EVIDENCE.SET.1' or d.get('authority')!='EVIDENCE_ONLY' or d.get('policy')!=POLICY: raise MergeError('invalid policy')
 if not isinstance(d.get('items'),list) or len(d['items'])>20: raise MergeError('invalid items')
 return d

def main():
 if len(sys.argv) not in {3,4}: raise SystemExit('base followup output [optional]')
 base=load(sys.argv[1]); follow=load(sys.argv[2])
 seen=set(); items=[]
 for x in list(base['items'])[:11]+list(follow['items'])[:9]:
  if not isinstance(x,dict): raise MergeError('invalid item')
  key=x.get('evidence_sha256') or x.get('evidence_id')
  if not isinstance(key,str): raise MergeError('invalid evidence key')
  if key in seen: continue
  seen.add(key); items.append(x)
 out={'schema':'K.WORLD.EVIDENCE.SET.1','observed_at':base['observed_at'],'authority':'EVIDENCE_ONLY','policy':POLICY,'items':items}
 dest=pathlib.Path(sys.argv[3]) if len(sys.argv)==4 else None
 raw=(json.dumps(out,ensure_ascii=False,sort_keys=True,separators=(',',':'))+'\n')
 if dest: dest.write_text(raw,encoding='utf-8')
 else: sys.stdout.write(raw)

if __name__=='__main__': main()
