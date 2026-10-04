import importlib.util, json
from datetime import datetime, timezone, timedelta
from pathlib import Path

SPEC=importlib.util.spec_from_file_location('wcm','/root/K/K/tools/world_current_model.py')
wcm=importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(wcm)

def dump(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(obj,ensure_ascii=False))

def event_state(now):
    return {'schema':'K.WORLD.EVENT.STATE.1','updated_at':now.isoformat(),'authority':'DERIVED_EVENT_CANDIDATE_ONLY','truth_status':'UNVERIFIED','memory_eligible':False,'events':[{'event_id':'evt-1','topic':'ai_technology','subject':'AI event begins','latest_subject':'AI event update','first_seen':(now-timedelta(days=2)).isoformat(),'last_seen':now.isoformat(),'update_count':2,'source_groups':['reuters.com','apnews.com'],'source_classes':['NEWSWIRE'],'evidence_fingerprints':['a'],'recent_urls':['https://reuters.com/x'],'last_tokens':['event']} ]}

def exp(ts,sha,query='verify primary source'):
    return {'schema':'K.WORLD.EXPERIENCE.1','authority':'COGNITIVE_EXPERIENCE_ONLY','memory_eligible':False,'experienced_at':ts.isoformat(),'observed_at':ts.isoformat(),'final_evidence_sha256':sha,'final_thought':{'assessment':'provisional assessment','notable_evidence_ids':['abc12345'],'follow_up_queries':[{'query':query,'reason':'needs independent confirmation'}]}}

def test_build_separates_live_and_legacy_and_open_questions(tmp_path):
    now=datetime(2026,9,14,tzinfo=timezone.utc)
    dump(tmp_path/'event_state/current.json',event_state(now))
    dump(tmp_path/'retained_evidence/r.json',{'schema':'K.WORLD.RETAINED.EVIDENCE.1','source_evidence_sha256':'live-sha'})
    dump(tmp_path/'experiences/a.json',exp(now,'live-sha'))
    dump(tmp_path/'experiences/b.json',exp(now-timedelta(days=1),'old-sha','legacy question'))
    m=wcm.build(tmp_path,now)
    assert len(m['active_event_candidates'])==1
    assert len(m['recent_notable_assessments'])==1
    assert len(m['legacy_orientation_notes'])==1
    assert [q['query'] for q in m['open_questions']]==['verify primary source']
    assert m['open_questions'][0]['status']=='OPEN_UNVERIFIED'

def test_expired_digest_excluded(tmp_path):
    now=datetime(2026,9,14,tzinfo=timezone.utc)
    dump(tmp_path/'digests/old.json',{'schema':'K.WORLD.DIGEST.1','authority':'COGNITIVE_NOTE_ONLY','memory_eligible':False,'digested_at':(now-timedelta(days=15)).isoformat(),'observed_at':(now-timedelta(days=15)).isoformat(),'expires_at':(now-timedelta(seconds=1)).isoformat(),'assessment':'old','source_evidence_sha256':'x'})
    assert wcm.build(tmp_path,now)['recent_temporary_digests']==[]

def test_open_questions_deduplicate(tmp_path):
    now=datetime(2026,9,14,tzinfo=timezone.utc)
    dump(tmp_path/'retained_evidence/r.json',{'schema':'K.WORLD.RETAINED.EVIDENCE.1','source_evidence_sha256':'s1'})
    e=exp(now,'s1'); e['final_thought']['follow_up_queries'].append({'query':'VERIFY PRIMARY SOURCE','reason':'duplicate'})
    dump(tmp_path/'experiences/a.json',e)
    assert len(wcm.build(tmp_path,now)['open_questions'])==1

def test_write_model_is_derived_view(tmp_path):
    out=tmp_path/'out'; rec=wcm.write_model(tmp_path,out)
    d=json.loads((out/'current.json').read_text())
    assert rec['status']=='PASS'
    assert d['authority']=='DERIVED_COGNITIVE_VIEW_ONLY'
    assert d['memory_eligible'] is False
    assert d['policy']['fresh_search_required_for_current_fact'] is True
    assert (out/'current.md').is_file()
