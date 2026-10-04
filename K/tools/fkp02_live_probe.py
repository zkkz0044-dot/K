from __future__ import annotations
import json, os
from kk_k.audit_witness import query_witness, remote_soul_audit_sink
from kk_k.fk_runtime import execute_governed
from kk_k.soul_proposer import SoulProposer, SoulProviders

def role_json(role,action):
    if role=='a': return json.dumps({'schema':'KS01.SOUL_A.1','assessment':'live-a','confidence':'HIGH','candidate_actions':[action,'A05_NO_ACTION']})
    if role=='b': return json.dumps({'schema':'KS01.SOUL_B.1','assessment':'live-b','confidence':'HIGH','blocked_actions':[]})
    return json.dumps({'schema':'KS01.SOUL_C.1','assessment':'live-c','confidence':'HIGH','selected_action_id':action})

def evidence(action):
    return [{'schema':'KS02.EVIDENCE.1','evidence_id':'live.e1','source_id':'fkp02.live','trust':'UNTRUSTED_EVIDENCE','freshness':'FRESH','stance':'SUPPORT','actions':[action],'claim':'live FKP02 acceptance evidence'}]

def main():
    action='A02_READ_F_STATUS'
    proposer=SoulProposer(
        providers=SoulProviders(soul_a=lambda _:role_json('a',action),soul_b=lambda _:role_json('b',action),soul_c=lambda _:role_json('c',action)),
        context_provider=lambda cycle:f'live-cycle={cycle}', evidence_provider=lambda _:evidence(action),
        audit_log_path=None, event_prefix=f'live-{os.getpid()}', audit_sink=remote_soul_audit_sink(),
    )
    selected=proposer(1)
    result=execute_governed(selected,[])
    head=query_witness()
    print('uid='+str(os.getuid()))
    print('selected='+selected)
    print('result='+json.dumps(result,sort_keys=True,separators=(',',':')))
    print('audit_generation='+str(head.generation))
    print('audit_digest='+head.digest)
    return 0 if result.get('status')=='PASS' and result.get('f_called') is True else 1

if __name__=='__main__': raise SystemExit(main())
