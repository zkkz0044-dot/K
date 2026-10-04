#!/usr/bin/env python3
from __future__ import annotations
from datetime import datetime,timezone
import hashlib,json,os,pathlib,sys
OUT=pathlib.Path('/root/K/K/world/round_context')
POLICY={'observed_is_believed':False,'search_result_is_long_term_memory':False}
class ArchiveError(ValueError): pass

def main():
 if len(sys.argv)!=2: raise SystemExit('one merged evidence file required')
 src=pathlib.Path(sys.argv[1]); raw=src.read_bytes()
 if not raw or len(raw)>131072: raise ArchiveError('invalid context size')
 try: d=json.loads(raw)
 except Exception as exc: raise ArchiveError('invalid JSON') from exc
 if not isinstance(d,dict) or set(d)!={'schema','observed_at','authority','policy','items'}: raise ArchiveError('invalid envelope')
 if d.get('schema')!='K.WORLD.EVIDENCE.SET.1' or d.get('authority')!='EVIDENCE_ONLY' or d.get('policy')!=POLICY: raise ArchiveError('invalid policy')
 items=d.get('items')
 if not isinstance(items,list) or not (1<=len(items)<=20): raise ArchiveError('invalid items')
 for x in items:
  if not isinstance(x,dict) or x.get('status')!='OBSERVED_UNVERIFIED' or x.get('belief_status')!='NOT_EVALUATED' or x.get('memory_eligible') is not False: raise ArchiveError('trust escalation')
 dt=datetime.fromisoformat(d['observed_at'])
 if dt.tzinfo is None: raise ArchiveError('timezone required')
 digest=hashlib.sha256(raw).hexdigest(); stamp=dt.astimezone(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
 OUT.mkdir(parents=True,exist_ok=True); target=OUT/f'{stamp}-{digest[:12]}.json'
 if target.exists():
  if target.read_bytes()!=raw: raise ArchiveError('archive collision')
 else:
  tmp=OUT/f'.{target.name}.tmp'; tmp.write_bytes(raw); os.chmod(tmp,0o644); os.replace(tmp,target)
 print(json.dumps({'status':'PASS','file':str(target),'sha256':digest,'items':len(items)},sort_keys=True))
if __name__=='__main__': main()
