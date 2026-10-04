#!/usr/bin/python3
import hashlib, json, pathlib, sys, tempfile
sys.path.insert(0, '/root/K/F/src')
from kk_f.evidence import initialize as init_evidence, verify as verify_evidence
from kk_f.runtime_bootstrap import bootstrap_runtime
from kk_f.runtime_cycle import run_cycle
from kk_f.restart_ledger import read_ledger

root = pathlib.Path(tempfile.mkdtemp(prefix='kk-f-final-'))
cwd = root/'work'; cwd.mkdir(); ledger=root/'ledger'; store=root/'evidence'; init_evidence(store)
exe=root/'worker.py'; exe.write_text('#!/usr/bin/python3\nimport time\ntime.sleep(30)\n'); exe.chmod(0o700)
digest=hashlib.sha256(exe.read_bytes()).hexdigest(); auth=root/'authority.json'
spec={'version':'0.1','executable':str(exe),'argv':[],'cwd':str(cwd),'env':{},'sha256':digest}
manifest={'version':'0.2','authority_id':'kk-f-final-root','process_spec':spec,'max_restart_attempts':2}
auth.write_text(json.dumps(manifest,separators=(',',':'))+'\n'); auth.chmod(0o600)
handles=[]
try:
    boot=bootstrap_runtime(str(auth),str(ledger),spec); current=boot.worker; handles.append(current)
    hb1={'version':'0.1','sequence':1,'observed_at':'2026-09-04T06:00:20Z'}
    r1=run_cycle(str(auth),str(ledger),str(store),current,hb1,spec,previous_heartbeat=None,now='2026-09-04T06:00:30Z',healthy_within_seconds=15,degraded_within_seconds=30,grace_seconds=0.1,message_id='123e4567-e89b-42d3-a456-426614174101',timestamp='2026-09-04T06:00:30Z')
    assert r1.supervision.health_status=='HEALTHY' and r1.current is current
    hb2={'version':'0.1','sequence':2,'observed_at':'2026-09-04T06:00:21Z'}
    r2=run_cycle(str(auth),str(ledger),str(store),r1.current,hb2,spec,previous_heartbeat=r1.accepted_heartbeat,now='2026-09-04T06:01:00Z',healthy_within_seconds=15,degraded_within_seconds=30,grace_seconds=0.1,message_id='223e4567-e89b-42d3-a456-426614174102',timestamp='2026-09-04T06:01:00Z')
    assert r2.supervision.decision=='REPLACE_INSTANCE' and r2.supervision.attempts==1 and r2.current is not None; handles.append(r2.current)
    hb3={'version':'0.1','sequence':3,'observed_at':'2026-09-04T06:00:22Z'}
    r3=run_cycle(str(auth),str(ledger),str(store),r2.current,hb3,spec,previous_heartbeat=r2.accepted_heartbeat,now='2026-09-04T06:02:00Z',healthy_within_seconds=15,degraded_within_seconds=30,grace_seconds=0.1,message_id='323e4567-e89b-42d3-a456-426614174103',timestamp='2026-09-04T06:02:00Z')
    assert r3.supervision.decision=='REPLACE_INSTANCE' and r3.supervision.attempts==2 and r3.current is not None; handles.append(r3.current)
    hb4={'version':'0.1','sequence':4,'observed_at':'2026-09-04T06:00:23Z'}
    r4=run_cycle(str(auth),str(ledger),str(store),r3.current,hb4,spec,previous_heartbeat=r3.accepted_heartbeat,now='2026-09-04T06:03:00Z',healthy_within_seconds=15,degraded_within_seconds=30,grace_seconds=0.1,message_id='423e4567-e89b-42d3-a456-426614174104',timestamp='2026-09-04T06:03:00Z')
    assert r4.supervision.decision=='HOLD_FAILED' and r4.supervision.attempts==2 and r4.current is None
    ev=verify_evidence(store); led=read_ledger(str(ledger))
    assert ev['count']==4 and led['attempts']==2 and led['max_attempts']==2 and led['last_decision']=='HOLD_FAILED'
    print(json.dumps({'final_acceptance':'PASS','evidence_count':ev['count'],'evidence_last_hash':ev['last_hash'],'restart_attempts':led['attempts'],'max_restart_attempts':led['max_attempts'],'last_decision':led['last_decision'],'authority_id':boot.authority_id},sort_keys=True))
finally:
    for h in handles:
        try:h.stop(grace_seconds=0.05)
        except Exception:pass
