"""No model, search, file-read tool or audit network is used in these tests."""
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
from contextlib import ExitStack
from unittest.mock import Mock, patch
import pytest
from kk_k import capability_planner as p, chat_runtime, model_client as client
from kk_k.identity import EXPECTED as IDENTITY
from kk_k.human_ingress import HumanMessage, MAX_TEXT_BYTES
from kk_k.capability_cognition import CapabilityCognitionError

ROOT=Path('/root/K')
BINDING=json.loads((ROOT/'K/config/dialogue_identity_binding.json').read_text())
NONE={'schema':p.SCHEMA,'need':'NONE','tool':None,'args':None,'reason':'No outside information needed'}
SEARCH={'schema':p.SCHEMA,'need':'READ_ONLY','tool':'browser.search','args':{'query':'official weather today'},'reason':'Current weather requested'}

def wrap(value):
    return json.dumps({'schema':'K.CAPABILITY.PLAN.MODEL.1','plan_text':json.dumps(value,ensure_ascii=False),'confidence':'LOW'},ensure_ascii=False)

def parse(value):
    return p.parse_plan(wrap(value),context_sha256='c'*64)

@pytest.fixture(autouse=True)
def isolate():
    with ExitStack() as stack:
        stack.enter_context(patch.object(p,'load_binding',return_value=BINDING))
        stack.enter_context(patch.object(p,'execute_external_tool',side_effect=AssertionError('real tool forbidden')))
        for name,value in {'_verify_goal_alignment':None,'load_personality_snapshot':SimpleNamespace(state={'version':1},revision_count=0),'prompt_view':{'version':1},'current_beliefs':(),'belief_prompt_view':{},'current_skills':(),'skill_prompt_view':{},'query_world_graph':{'entities':[]},'query_conversation_recall':()}.items():
            stack.enter_context(patch.object(chat_runtime,name,return_value=value))
        yield

def test_none_cannot_execute_even_when_original_message_contains_search_keywords():
    text='仅计算17×19；不要搜索外部信息。'
    provider=Mock(return_value=wrap(NONE)); executor=Mock()
    plan=p.plan_capability(identity=IDENTITY,history=(),message=HumanMessage('CHAT',text),provider=provider)
    assert p.execute_plan(plan,executor=executor) is None
    executor.assert_not_called(); provider.assert_called_once()
    assert provider.call_args.args[0]==p.ROLE and text in provider.call_args.args[1]

def test_one_positive_plan_passes_only_its_query_to_f_once():
    receipt={'tool':'browser.search','verdict':'PASS','executed':True}
    executor=Mock(return_value=receipt)
    evidence=p.execute_plan(parse(SEARCH),executor=executor)
    executor.assert_called_once_with({'schema':'K.EXTERNAL.TOOL.REQUEST.2','tool':'browser.search','args':SEARCH['args']})
    assert evidence['receipt']==receipt

@pytest.mark.parametrize('value',[
    {**NONE,'need':[]}, {**NONE,'tool':'browser.search'}, {**NONE,'args':{}},
    {**SEARCH,'tool':'files.write'}, {**SEARCH,'tool':'shell'}, {**SEARCH,'tool':{}},
    {**SEARCH,'args':{'query':'x','command':'id'}}, {**SEARCH,'args':{'query':'x'*201}},
    {**SEARCH,'args':{'query':'x\ny'}}, {**SEARCH,'args':{'query':'\ud800'}},
    {**SEARCH,'extra':True}, {**SEARCH,'reason':'x'*257},
    {**SEARCH,'tool':'files.read','args':{'path':'/root/K/F/secrets/key'}},
    {**SEARCH,'tool':'files.read','args':{'path':'/root/K/K/../F/file'}},
    {**SEARCH,'tool':'files.read','args':{'path':'/root/K/K//file'}},
    {**SEARCH,'tool':'remote.vps.health','args':{}},
])
def test_malformed_plan_rejected_before_any_tool(value):
    with pytest.raises(CapabilityCognitionError): parse(value)

@pytest.mark.parametrize('raw',['{"schema":1,"schema":2}','{"a":NaN}','{"a":Infinity}','[]','null','not json'])
def test_invalid_json_never_becomes_a_plan(raw):
    with pytest.raises(CapabilityCognitionError):
        p.parse_plan(json.dumps({'schema':'K.CAPABILITY.PLAN.MODEL.1','confidence':'LOW','plan_text':raw}),context_sha256='c'*64)

def test_untrusted_envelope_cannot_promote_confidence():
    raw=json.loads(wrap(NONE));raw['confidence']='HIGH'
    with pytest.raises(CapabilityCognitionError):p.parse_plan(json.dumps(raw),context_sha256='c'*64)

def test_identity_input_and_history_roles_preserved_at_full_valid_text_limit():
    message=HumanMessage('CHAT','中'*(MAX_TEXT_BYTES//3))
    history=({'subject':'human_chat','summary':'old request'}, {'subject':'k_reply','summary':'old answer'})
    provider=Mock(return_value=wrap(NONE))
    p.plan_capability(identity=IDENTITY,history=history,message=message,provider=provider,media=({'kind':'file','data_b64':'DO_NOT_UPLOAD_TWICE'},),device_context={'location':'PRIVATE_DEVICE_COORDINATES'})
    prompt=provider.call_args.args[1];ctx=json.loads(prompt.split('CONTEXT_JSON=',1)[1])
    assert ctx['current_human']['text']==message.text and ctx['identity']==IDENTITY
    assert [item['role'] for item in ctx['completed_history']]==['USER','K']
    assert len(prompt.encode())<=client.MAX_PROMPT_BYTES
    assert 'DO_NOT_UPLOAD_TWICE' not in prompt and 'PRIVATE_DEVICE_COORDINATES' not in prompt

def test_veto_receipt_remains_evidence_without_retry():
    executor=Mock(return_value={'tool':'browser.search','verdict':'VETO'})
    assert p.execute_plan(parse(SEARCH),executor=executor)['verdict']=='VETO'
    executor.assert_called_once()

def test_mutated_args_cannot_widen_tool_scope():
    plan=parse(SEARCH);plan.need.args['command']='id';executor=Mock()
    with pytest.raises(CapabilityCognitionError):p.execute_plan(plan,executor=executor)
    executor.assert_not_called()

@pytest.mark.parametrize('failure',[TimeoutError('timeout'),client.ModelClientError('transport failed'),CapabilityCognitionError('bad JSON')])
def test_plan_failure_has_zero_tools_zero_abc_and_no_retry(failure):
    provider=Mock(side_effect=failure)
    # Transport failures normally arrive as ModelClientError; normalize raw timeout in this stub.
    if isinstance(failure,TimeoutError):provider.side_effect=client.ModelClientError(str(failure))
    with patch.object(chat_runtime,'query_conversation_history',return_value=()), patch.object(chat_runtime,'append_remote_event'), patch.object(chat_runtime,'load_identity',return_value=IDENTITY), patch.object(chat_runtime,'answer_known',return_value=None), patch.object(chat_runtime,'execute_plan') as execute, patch.object(chat_runtime,'deliberate_dialogue') as abc:
        with pytest.raises(chat_runtime.ChatRuntimeError):chat_runtime.run_turn(HumanMessage('CHAT','calculate 17*19 without search'),model_provider=provider)
    provider.assert_called_once();execute.assert_not_called();abc.assert_not_called()

def test_audit_precedes_f_and_original_media_device_reach_dialogue():
    order=[];media=({'kind':'image','name':'image'},);device={'terminal':{'device_id':'test'}}
    def provider(role,prompt):order.append('K_plan');return wrap(SEARCH)
    def executor(request):order.append('F');return {'tool':'browser.search','verdict':'PASS'}
    def audit(**kw):order.append(kw['subject'])
    decision=SimpleNamespace(soul_c=SimpleNamespace(answer='answer'))
    with patch.object(chat_runtime,'query_conversation_history',return_value=()), patch.object(chat_runtime,'append_remote_event',side_effect=audit), patch.object(chat_runtime,'load_identity',return_value=IDENTITY), patch.object(chat_runtime,'answer_known',return_value=None), patch.object(p,'execute_external_tool',side_effect=executor), patch.object(chat_runtime,'deliberate_dialogue',return_value=decision) as abc, patch.object(chat_runtime,'dialogue_audit_summary',return_value='{}'):
        assert chat_runtime.run_turn(HumanMessage('CHAT','search current weather'),model_provider=provider,media=media,device_context=device)=='answer'
    assert order.index('human_chat')<order.index('K_plan')<order.index('capability_plan')<order.index('F')<order.index('capability_evidence')<order.index('k_reply')
    assert abc.call_args.kwargs['device_context']==device

