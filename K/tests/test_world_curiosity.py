import importlib.util, json
from datetime import datetime, timezone, timedelta
from pathlib import Path

SPEC=importlib.util.spec_from_file_location('wcq','/root/K/K/tools/world_curiosity.py')
wcq=importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(wcq)

def dump(p,o): p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(o))
def model(qs): return {'schema':'K.WORLD.CURRENT.MODEL.1','authority':'DERIVED_COGNITIVE_VIEW_ONLY','memory_eligible':False,'policy':{'fresh_search_required_for_current_fact':True},'open_questions':qs}
def q(text='verify source'): return {'query':text,'reason':'independent check','status':'OPEN_UNVERIFIED'}

def test_pick_ready_then_global_cooldown(tmp_path):
    mp=tmp_path/'m.json'; sp=tmp_path/'s.json'; now=datetime(2026,9,14,tzinfo=timezone.utc); dump(mp,model([q()]))
    p=wcq.choose(mp,sp,now); assert p['status']=='READY'
    pp=tmp_path/'p.json'; dump(pp,p); wcq.mark_attempt(pp,sp,now)
    assert wcq.choose(mp,sp,now+timedelta(minutes=30))['reason']=='GLOBAL_COOLDOWN'

def test_question_attempt_limit(tmp_path):
    mp=tmp_path/'m.json'; sp=tmp_path/'s.json'; now=datetime(2026,9,14,tzinfo=timezone.utc); dump(mp,model([q()]))
    for hours in (0,7):
        p=wcq.choose(mp,sp,now+timedelta(hours=hours)); assert p['status']=='READY'; pp=tmp_path/f'p{hours}.json'; dump(pp,p); wcq.mark_attempt(pp,sp,now+timedelta(hours=hours))
    assert wcq.choose(mp,sp,now+timedelta(hours=14))['reason']=='NO_ELIGIBLE_OPEN_QUESTION'

def test_search_batch_is_browser_search_and_unverified(tmp_path):
    mp=tmp_path/'m.json'; sp=tmp_path/'s.json'; pp=tmp_path/'p.json'; now=datetime(2026,9,14,tzinfo=timezone.utc); dump(mp,model([q()])); dump(pp,wcq.choose(mp,sp,now))
    seen=[]
    def fake(req):
        seen.append(req); return {'schema':'K.EXTERNAL.TOOL.RECEIPT.1','tool':'browser.search','risk':'L0','human_required':False,'executed':True,'verified':True,'verdict':'PASS','fk_tool_receipt':{'evidence':{'search':{'results':[]}}}}
    b=wcq.search_batch(pp,fake,now)
    assert seen[0]['tool']=='browser.search'
    assert b['authority']=='EVIDENCE_ONLY' and b['items'][0]['verdict']=='PASS'

def test_no_questions_is_noop(tmp_path):
    mp=tmp_path/'m.json'; sp=tmp_path/'s.json'; dump(mp,model([]))
    assert wcq.choose(mp,sp,datetime(2026,9,14,tzinfo=timezone.utc))['status']=='NOOP'
