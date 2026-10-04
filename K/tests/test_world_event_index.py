from datetime import datetime, timezone
from pathlib import Path
import json
from kk_k import world_event_index as wei
from kk_k import world_think as wt

NOW=datetime(2026,9,14,2,tzinfo=timezone.utc)

def item(eid,title,snippet,url,host='reuters.com'):
    return {'topic':'global_affairs','url':url,'title':title,'snippet':snippet,'observed_at':'2026-09-14T01:00:00+00:00','evidence_id':eid,'source_host':host,'source_class':'NEWSWIRE','independence_group':host,'status':'OBSERVED_UNVERIFIED','memory_eligible':False}

def test_same_event_across_sources_is_candidate(tmp_path):
    a=item('abcdefgh1111','Major earthquake strikes coastal city officials report widespread damage','Rescue teams search buildings after a major earthquake struck the coastal city.','https://reuters.com/a')
    b=item('abcdefgh2222','Officials report widespread damage after major earthquake strikes coastal city','Emergency crews searched buildings in the coastal city after the major earthquake.','https://apnews.com/b','apnews.com')
    wei.apply_notable([a],tmp_path/'state',tmp_path/'updates',NOW)
    out=wei.annotate_items([b],tmp_path/'state'/'current.json',NOW)[0]['event_candidate']
    assert out['relation']=='POSSIBLE_CONTINUATION' and out['truth_status']=='UNVERIFIED'

def test_unrelated_event_does_not_merge(tmp_path):
    a=item('abcdefgh1111','Major earthquake strikes coastal city officials report widespread damage','Rescue teams search damaged buildings.','https://reuters.com/a')
    b=item('abcdefgh3333','Central bank holds interest rates after inflation report','Policymakers kept rates unchanged after new inflation data.','https://reuters.com/c')
    wei.apply_notable([a],tmp_path/'state',tmp_path/'updates',NOW)
    assert wei.annotate_items([b],tmp_path/'state'/'current.json',NOW)[0]['event_candidate']['relation']=='NO_STRONG_MATCH'

def test_same_content_is_idempotent(tmp_path):
    a=item('abcdefgh1111','Major earthquake strikes coastal city officials report widespread damage','Rescue teams search damaged buildings.','https://reuters.com/a')
    first=wei.apply_notable([a],tmp_path/'state',tmp_path/'updates',NOW)
    second=wei.apply_notable([a],tmp_path/'state',tmp_path/'updates',datetime(2026,9,14,3,tzinfo=timezone.utc))
    assert len(first['updates'])==1 and second['skipped']==1 and second['updates']==[]
    assert len(list((tmp_path/'updates').glob('*.json')))==1

def test_event_history_append_only_and_current_view_bounded(tmp_path):
    a=item('abcdefgh1111','Major earthquake strikes coastal city officials report widespread damage','Rescue teams search buildings after a major earthquake struck the coastal city.','https://reuters.com/a')
    b=item('abcdefgh2222','Officials report widespread damage after major earthquake strikes coastal city','Emergency crews searched buildings in the coastal city after the major earthquake.','https://apnews.com/b','apnews.com')
    wei.apply_notable([a],tmp_path/'state',tmp_path/'updates',NOW)
    wei.apply_notable([b],tmp_path/'state',tmp_path/'updates',datetime(2026,9,14,3,tzinfo=timezone.utc))
    updates=sorted((tmp_path/'updates').glob('*.json')); state=json.loads((tmp_path/'state'/'current.json').read_text())
    assert len(updates)==2 and len(state['events'])==1 and state['events'][0]['update_count']==2
    assert state['authority']=='DERIVED_EVENT_CANDIDATE_ONLY' and state['truth_status']=='UNVERIFIED' and state['memory_eligible'] is False

def test_world_think_load_path_exposes_event_candidate(tmp_path,monkeypatch):
    x=item('abcdefgh1111','Example event title','Example event snippet','https://example.com/a','example.com')
    x.update({'query':'q','source_published_at':None,'belief_status':'NOT_EVALUATED','confidence':{'level':'LOW','basis':'SINGLE_SEARCH_RESULT_UNCORROBORATED'},'corroboration':{'independent_sources':1,'status':'NOT_CHECKED'},'conflict':{'status':'NOT_CHECKED'},'evidence_sha256':'a'*64})
    d={'schema':'K.WORLD.EVIDENCE.SET.1','observed_at':'2026-09-14T01:00:00+00:00','authority':'EVIDENCE_ONLY','policy':{'observed_is_believed':False,'search_result_is_long_term_memory':False},'items':[x]}
    p=tmp_path/'e.json'; p.write_text(json.dumps(d))
    monkeypatch.setattr(wt,'annotate_event_items',lambda rows:[{**rows[0],'event_candidate':{'event_id':'evt-test','subject':'Example','relation':'POSSIBLE_CONTINUATION','mechanical_similarity':0.9,'match_reason':'TOKEN_SIMILARITY','truth_status':'UNVERIFIED'}}])
    _d,rows,_ids,_sha=wt.load_evidence(p)
    assert rows[0]['event_candidate']['event_id']=='evt-test' and rows[0]['event_candidate']['truth_status']=='UNVERIFIED'

def test_default_state_tolerates_inaccessible_root_fallback(monkeypatch):
    original=Path.is_file
    def guarded(path):
        text=str(path)
        if text=='/run/kk-k-ro/world/event_state/current.json':
            return False
        if text=='/root/K/K/world/event_state/current.json':
            raise PermissionError('sandbox denied')
        return original(path)
    monkeypatch.setattr(Path,'is_file',guarded)
    state=wei.load_state()
    assert state['events']==[]
    assert state['truth_status']=='UNVERIFIED'
    assert state['memory_eligible'] is False


def test_explicit_inaccessible_state_path_fails_closed(monkeypatch,tmp_path):
    target=tmp_path/'current.json'
    original=Path.is_file
    def guarded(path):
        if path==target:
            raise PermissionError('explicit state denied')
        return original(path)
    monkeypatch.setattr(Path,'is_file',guarded)
    import pytest
    with pytest.raises(PermissionError):
        wei.load_state(target)
