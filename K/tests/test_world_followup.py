import json,tempfile
from kk_k.world_followup_observer import observe_followups

def judgment(status='APPROVED_PROVISIONAL',n=3):
    q=[{'query':f'q{i}','reason':f'r{i}'} for i in range(n)]
    return {'schema':'K.WORLD.JUDGMENT.RUN.1','judged_at':'2026-09-13T00:00:00+00:00','source_observed_at':'2026-09-13T00:00:00+00:00','source_evidence_sha256':'a'*64,'authority':'COGNITIVE_PROPOSAL_ONLY','memory_eligible':False,'status':status,'proposal':{'schema':'K.WORLD.JUDGMENT.PROPOSAL.1','assessment':'x','priority_evidence_ids':[],'noise_evidence_ids':[],'corroborate_evidence_ids':[],'follow_up_queries':q},'critic':{'critique':'OK','risk_flags':['NONE']},'judge':{'verdict':'APPROVE_A' if status=='APPROVED_PROVISIONAL' else 'REJECT_A'}}

def write_tmp(d):
    f=tempfile.NamedTemporaryFile('w',delete=False,encoding='utf-8')
    json.dump(d,f); f.close(); return f.name

def fake_receipt(req):
    return {'schema':'K.EXTERNAL.TOOL.RECEIPT.1','tool':'browser.search','risk':'L0','human_required':False,'executed':True,'verified':True,'verdict':'PASS','fk_tool_receipt':{'schema':'FK_TOOL.F_RECEIPT.1','tool':'browser.search','outcome':'EXECUTED','evidence':{'kind':'WEB_SEARCH','search':{'schema':'F.TOOL.WEB_SEARCH.1','query':req['args']['query'],'results':[]}}}}
def test_approved_runs_at_most_three_searches():
    p=write_tmp(judgment()); seen=[]
    def fake(req): seen.append(req); return fake_receipt(req)
    out=observe_followups(p,executor=fake)
    assert len(seen)==3 and len(out['items'])==3
    assert all(x['verdict']=='PASS' for x in out['items'])

def test_rejected_runs_zero_searches():
    p=write_tmp(judgment('REJECTED')); seen=[]
    out=observe_followups(p,executor=lambda req: seen.append(req))
    assert seen==[] and out['items']==[]

def test_four_followups_are_rejected():
    p=write_tmp(judgment(n=4))
    try: observe_followups(p,executor=fake_receipt)
    except Exception as exc: assert 'invalid followups' in str(exc)
    else: raise AssertionError('four followups accepted')
