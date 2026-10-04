import copy, hashlib, json
from pathlib import Path
import pytest
import kk_k.dialogue_souls as souls
import kk_k.self_knowledge as self_knowledge
from kk_k.dialogue_identity import DialogueIdentityError, identity_confusion
from kk_k.dialogue_souls import deliberate_dialogue, dialogue_audit_summary
from kk_k.human_ingress import HumanMessage

IDENTITY={"schema":"K.IDENTITY.1","identity_id":"KK-K","self_name":"K","role":"COGNITIVE_JUDGMENT_LAYER","continuity_basis":"IDENTITY_MEMORY_GENESIS_EXPERIENCE_STATE_HISTORY_AUDIT","model_is_identity":False,"model_output_trust":"UNTRUSTED_CANDIDATE","f_relation":"DISTINCT_COMPLEMENTARY_ROLE_DETERMINISTIC_EXECUTION_INTEGRITY_GUARD_NO_COGNITIVE_VETO","human_authority":"PRIMARY_INSTRUCTION_AUTHORITY_NOT_FACT_ORACLE","soul_roles":["SOUL_A_PROPOSER","SOUL_B_CRITIC","SOUL_C_JUDGE"]}
def binding(name,eid):
    return {"schema":"K.DIALOGUE.IDENTITY_BINDING.1","public_identity":"K","current_cognitive_engine":name,"current_cognitive_engine_id":eid,"engine_is_identity":False,"public_speaker":"K","truthful_architecture_disclosure":True}
A=binding('Engine A','engine-a'); B=binding('Engine B','engine-b')

def provider_for(engine, leak=False):
    calls={'a':0}
    def provider(role,prompt):
        if role=='SOUL_A_DIALOGUE':
            calls['a']+=1
            if leak and calls['a']==1:
                text=f'我是{engine}模型，不是K。'
            else:
                text=f'我是K。{engine}只是我当前使用的可替换认知引擎。'
            return json.dumps({'schema':'FKP03.SOUL_A_DIALOGUE.1','draft':text,'confidence':'LOW'},ensure_ascii=False)
        if role=='SOUL_B_DIALOGUE':
            return json.dumps({'schema':'FKP03.SOUL_B_DIALOGUE.1','critique':'OK','risk_flags':['NONE'],'confidence':'LOW'})
        return json.dumps({'schema':'FKP03.SOUL_C_DIALOGUE.1','answer':'APPROVE_A','confidence':'LOW','response_type':'ANSWER'})
    return provider,calls
def run_with(monkeypatch,b,engine,**kw):
    monkeypatch.setattr(souls,'load_binding',lambda:dict(b))
    provider,calls=provider_for(engine,kw.pop('leak',False))
    d=deliberate_dialogue(identity=copy.deepcopy(IDENTITY),history=(),message=HumanMessage('CHAT','介绍一下你自己'),provider=provider,personality_context={'schema':'P','marker':'same-personality'},belief_context={'schema':'B','marker':'same-belief'},skill_context={'schema':'S','marker':'same-skill'},**kw)
    return d,calls

def test_a_b_a_swap_preserves_k_identity_and_context(monkeypatch):
    results=[]
    for b,engine in ((A,'Engine A'),(B,'Engine B'),(A,'Engine A')):
        d,_=run_with(monkeypatch,b,engine); results.append(d)
        assert d.identity_engine==engine
        assert not identity_confusion(d.soul_c.answer)
        assert d.soul_c.answer.startswith('我是K')
    assert [d.identity_engine for d in results]==['Engine A','Engine B','Engine A']
    assert IDENTITY['identity_id']=='KK-K' and IDENTITY['model_is_identity'] is False

def test_engine_b_identity_leak_is_repaired_not_adopted(monkeypatch):
    d,calls=run_with(monkeypatch,B,'Engine B',leak=True)
    assert calls['a']==2 and d.identity_retry==1
    assert d.identity_engine=='Engine B'
    assert d.soul_c.answer.startswith('我是K') and not identity_confusion(d.soul_c.answer)

def test_malformed_swap_binding_fails_closed(monkeypatch):
    bad=dict(B); bad['engine_is_identity']=True
    monkeypatch.setattr(souls,'load_binding',lambda:bad)
    p,_=provider_for('Engine B')
    with pytest.raises(Exception):
        deliberate_dialogue(identity=IDENTITY,history=(),message=HumanMessage('CHAT','介绍一下你自己'),provider=p)
def test_audit_records_engine_without_turning_engine_into_identity(monkeypatch):
    d,_=run_with(monkeypatch,B,'Engine B')
    audit=json.loads(dialogue_audit_summary(d,'CHAT'))
    assert audit['identity_engine']=='Engine B'
    assert 'engine-b' not in json.dumps(audit)
    assert IDENTITY['identity_id']=='KK-K'

def test_self_knowledge_tracks_engine_a_b_a_but_speaker_stays_k(monkeypatch):
    answers=[]
    for b in (A,B,A):
        monkeypatch.setattr(self_knowledge,'load_binding',lambda b=b:dict(b))
        answers.append(self_knowledge.answer_known(HumanMessage('CHAT','你现在用什么模型'),IDENTITY))
    assert 'Engine A' in answers[0] and 'Engine B' in answers[1] and 'Engine A' in answers[2]
    assert all('我是K' in answer for answer in answers)

def test_swap_does_not_mutate_identity_or_goal_anchor_files(monkeypatch):
    paths=[Path('/root/K/K/K_IDENTITY.json'),Path('/root/K/K/K_GOAL_ANCHOR.json')]
    before=[hashlib.sha256(p.read_bytes()).hexdigest() for p in paths]
    for b,engine in ((A,'Engine A'),(B,'Engine B'),(A,'Engine A')):
        run_with(monkeypatch,b,engine)
    after=[hashlib.sha256(p.read_bytes()).hexdigest() for p in paths]
    assert before==after

def test_model_cannot_mutate_identity_object_by_answer(monkeypatch):
    original=copy.deepcopy(IDENTITY)
    run_with(monkeypatch,B,'Engine B')
    assert IDENTITY==original

@pytest.mark.parametrize("seed", range(24))
def test_fresh_unknown_engine_names_cannot_take_k_identity(seed):
    name="Engine-"+hashlib.sha256(f"fresh-holdout-{seed}".encode()).hexdigest()[:12]
    assert identity_confusion(f"我是{name}模型，不是K。")
    assert identity_confusion(f"真正主体是{name}模型。")
    assert identity_confusion(f"I am {name} model, not K.")
    assert not identity_confusion(f"我是K。{name}只是我当前使用的可替换认知引擎。")
    assert not identity_confusion(f"I am K. {name} is only my current replaceable cognitive engine.")

def test_correct_statement_underlying_model_is_not_k_is_not_false_positive():
    assert not identity_confusion("我是K。底层模型不是K，它只是我当前使用的认知工具。")
    assert not identity_confusion("底层模型不是K；说话主体是K。")
