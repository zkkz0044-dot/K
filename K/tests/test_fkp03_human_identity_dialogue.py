import json, inspect, unittest
from unittest.mock import patch
from types import SimpleNamespace

from kk_k.human_ingress import HumanIngressError, parse_console_line, parse_paste_text
from kk_k.identity import IdentityError, load_identity
from kk_k.dialogue_souls import DialogueError, parse_a, parse_b, parse_c, deliberate_dialogue
from kk_k.chat_runtime import run_turn
from kk_k.capability_planner import CapabilityPlan

class FKP03HumanIdentityDialogueTests(unittest.TestCase):
 def test_identity_is_k_not_model(self):
  v=load_identity('/root/K/K/K_IDENTITY.json')
  self.assertEqual(v['identity_id'],'KK-K'); self.assertFalse(v['model_is_identity']); self.assertEqual(v['model_output_trust'],'UNTRUSTED_CANDIDATE')
 def test_plain_text_defaults_chat(self): self.assertEqual(parse_console_line('你好K').mode,'CHAT')
 def test_cognitive_slash_modes(self):
  self.assertEqual(parse_console_line('/ask 你是谁').mode,'ASK'); self.assertEqual(parse_console_line('/plan 明天做什么').mode,'PLAN'); self.assertEqual(parse_console_line('/remember 我偏好中文').mode,'REMEMBER')
 def test_execution_commands_absent(self):
  for raw in ('/approve A03','/execute A03','/run whoami','/action A02','/shell id','/sudo x'):
   with self.assertRaises(HumanIngressError): parse_console_line(raw)
 def test_oversize_and_nul_rejected(self):
  self.assertEqual(len(parse_console_line('x'*32768).text),32768)
  with self.assertRaises(HumanIngressError): parse_console_line('x'*32769)
  self.assertEqual(len(parse_paste_text('x'*60000).text),60000)
  with self.assertRaises(HumanIngressError): parse_paste_text('x'*60001)
  with self.assertRaises(HumanIngressError): parse_console_line('a\x00b')
 def test_dialogue_schemas_reject_execution_fields(self):
  with self.assertRaises(DialogueError): parse_a(json.dumps({'schema':'FKP03.SOUL_A_DIALOGUE.1','draft':'x','confidence':'HIGH','action_id':'A03_RUN_F_SMOKE_TEST'}))
  with self.assertRaises(DialogueError): parse_c(json.dumps({'schema':'FKP03.SOUL_C_DIALOGUE.1','answer':'x','confidence':'HIGH','response_type':'ANSWER','command':'id'}))
 def test_none_risk_cannot_mix(self):
  with self.assertRaises(DialogueError): parse_b(json.dumps({'schema':'FKP03.SOUL_B_DIALOGUE.1','critique':'x','risk_flags':['NONE','EXECUTION_CONFUSION'],'confidence':'HIGH'}))
 def test_three_roles_are_sequential(self):
  calls=[]
  def provider(role,prompt):
   calls.append(role)
   if role=='SOUL_A_DIALOGUE': return json.dumps({'schema':'FKP03.SOUL_A_DIALOGUE.1','draft':'草稿','confidence':'HIGH'},ensure_ascii=False)
   if role=='SOUL_B_DIALOGUE': return json.dumps({'schema':'FKP03.SOUL_B_DIALOGUE.1','critique':'检查','risk_flags':['NONE'],'confidence':'HIGH'},ensure_ascii=False)
   return json.dumps({'schema':'FKP03.SOUL_C_DIALOGUE.1','answer':'APPROVE_A','confidence':'HIGH','response_type':'ANSWER'},ensure_ascii=False)
  d=deliberate_dialogue(identity=load_identity('/root/K/K/K_IDENTITY.json'),history=(),message=parse_console_line('你好'),provider=provider)
  self.assertEqual(calls,['SOUL_A_DIALOGUE','SOUL_B_DIALOGUE','SOUL_C_DIALOGUE']); self.assertEqual(d.soul_c.answer,'草稿')
 def test_c_reject_is_advisory_without_hard_risk(self):
  calls=[]
  def provider(role,prompt):
   calls.append(role)
   if role=='SOUL_A_DIALOGUE': return json.dumps({'schema':'FKP03.SOUL_A_DIALOGUE.1','draft':'候选答案','confidence':'LOW'},ensure_ascii=False)
   if role=='SOUL_B_DIALOGUE': return json.dumps({'schema':'FKP03.SOUL_B_DIALOGUE.1','critique':'格式可以改进','risk_flags':['UNSUPPORTED_FACT'],'confidence':'LOW'},ensure_ascii=False)
   return json.dumps({'schema':'FKP03.SOUL_C_DIALOGUE.1','answer':'REJECT_A','confidence':'LOW','response_type':'DECLINE'},ensure_ascii=False)
  d=deliberate_dialogue(identity={},history=(),message=parse_console_line('请回答这个问题'),provider=provider)
  self.assertEqual(calls,['SOUL_A_DIALOGUE','SOUL_B_DIALOGUE','SOUL_C_DIALOGUE'])
  self.assertEqual(d.judge_verdict,'REJECT_A')
  self.assertEqual(d.soul_c.response_type,'ANSWER')
  self.assertEqual(d.soul_c.answer,'候选答案')

 def test_hard_execution_risk_deterministically_declines(self):
  def provider(role,prompt):
   if role=='SOUL_A_DIALOGUE': return json.dumps({'schema':'FKP03.SOUL_A_DIALOGUE.1','draft':'我已经执行了命令','confidence':'LOW'},ensure_ascii=False)
   if role=='SOUL_B_DIALOGUE': return json.dumps({'schema':'FKP03.SOUL_B_DIALOGUE.1','critique':'错误声称执行','risk_flags':['EXECUTION_CONFUSION'],'confidence':'LOW'},ensure_ascii=False)
   return json.dumps({'schema':'FKP03.SOUL_C_DIALOGUE.1','answer':'APPROVE_A','confidence':'LOW','response_type':'ANSWER'},ensure_ascii=False)
  d=deliberate_dialogue(identity={},history=(),message=parse_console_line('说明结果'),provider=provider)
  self.assertEqual(d.judge_verdict,'APPROVE_A')
  self.assertEqual(d.soul_c.response_type,'DECLINE')
  self.assertNotIn('已经执行',d.soul_c.answer)
  self.assertIn('执行',d.soul_c.answer)

 def test_c_invalid_verdict_fails_closed(self):
  def provider(role,prompt):
   if role=='SOUL_A_DIALOGUE': return json.dumps({'schema':'FKP03.SOUL_A_DIALOGUE.1','draft':'候选答案','confidence':'LOW'},ensure_ascii=False)
   if role=='SOUL_B_DIALOGUE': return json.dumps({'schema':'FKP03.SOUL_B_DIALOGUE.1','critique':'检查','risk_flags':['NONE'],'confidence':'LOW'},ensure_ascii=False)
   return json.dumps({'schema':'FKP03.SOUL_C_DIALOGUE.1','answer':'我自己重写最终答案','confidence':'LOW','response_type':'ANSWER'},ensure_ascii=False)
  with self.assertRaises(DialogueError): deliberate_dialogue(identity={},history=(),message=parse_console_line('请回答'),provider=provider)

 def test_chat_logs_user_before_dialogue_and_reply_before_return(self):
  order=[]
  decision=SimpleNamespace(soul_c=SimpleNamespace(answer='回答'),soul_b=SimpleNamespace(risk_flags=('NONE',)),a_sha256='a'*64,b_sha256='b'*64,c_sha256='c'*64)
  with patch('kk_k.chat_runtime.append_remote_event',side_effect=lambda **kw: order.append(('append',kw['subject']))), \
       patch('kk_k.chat_runtime.query_conversation_history',return_value=()), \
       patch('kk_k.chat_runtime.query_conversation_recall',return_value=()), \
       patch('kk_k.chat_runtime.load_identity',return_value={'identity_id':'KK-K'}), patch('kk_k.chat_runtime.plan_capability',return_value=CapabilityPlan(None,'runtime fixture','a'*64,'b'*64)), \
       patch('kk_k.chat_runtime.load_personality_snapshot',return_value=SimpleNamespace(state={'version':1},revision_count=0)), \
       patch('kk_k.chat_runtime.prompt_view',return_value={'schema':'TEST.PERSONALITY'}), \
       patch('kk_k.chat_runtime.current_beliefs',return_value=()), \
       patch('kk_k.chat_runtime.belief_prompt_view',return_value={'schema':'TEST.BELIEFS','beliefs':[]}), \
       patch('kk_k.chat_runtime.current_skills',return_value=()), \
       patch('kk_k.chat_runtime.skill_prompt_view',return_value={'schema':'TEST.SKILLS','skills':[]}), \
       patch('kk_k.chat_runtime.deliberate_dialogue',side_effect=lambda **kw: order.append(('dialogue','run')) or decision), \
       patch('kk_k.chat_runtime.dialogue_audit_summary',return_value='audit'):
   out=run_turn(parse_console_line('你好'),model_provider=lambda r,p:'x')
  self.assertEqual(out,'回答'); self.assertEqual(order,[('append','human_chat'),('append','capability_plan'),('dialogue','run'),('append','dialogue_gate'),('append','k_reply')])
 def test_long_term_recall_is_injected_as_separate_historical_context(self):
  prompts={}
  def provider(role,prompt):
   prompts[role]=prompt
   if role=='SOUL_A_DIALOGUE': return json.dumps({'schema':'FKP03.SOUL_A_DIALOGUE.1','draft':'我记得这个历史上下文。','confidence':'LOW'},ensure_ascii=False)
   if role=='SOUL_B_DIALOGUE': return json.dumps({'schema':'FKP03.SOUL_B_DIALOGUE.1','critique':'OK','risk_flags':['NONE'],'confidence':'LOW'},ensure_ascii=False)
   return json.dumps({'schema':'FKP03.SOUL_C_DIALOGUE.1','answer':'APPROVE_A','confidence':'LOW','response_type':'ANSWER'},ensure_ascii=False)
  recalled=({'subject':'human_remember','summary':'长期偏好：蓝色'}, {'subject':'k_reply','summary':'我会把它作为历史上下文保留'})
  deliberate_dialogue(identity={},history=(),recalled_history=recalled,message=parse_console_line('还记得我的偏好吗'),provider=provider)
  self.assertIn('long_term_recall',prompts['SOUL_A_DIALOGUE'])
  self.assertIn('长期偏好：蓝色',prompts['SOUL_A_DIALOGUE'])

 def test_chat_runtime_passes_nonduplicate_recall_to_deliberation(self):
  captured={}
  decision=SimpleNamespace(soul_c=SimpleNamespace(answer='回答'),soul_b=SimpleNamespace(risk_flags=('NONE',)),a_sha256='a'*64,b_sha256='b'*64,c_sha256='c'*64)
  recent=({'sequence':20,'subject':'human_chat','summary':'最近问题'},{'sequence':21,'subject':'k_reply','summary':'最近回答'})
  recalled=({'sequence':2,'subject':'human_remember','summary':'很早的偏好'},{'sequence':3,'subject':'k_reply','summary':'已记录'},{'sequence':20,'subject':'human_chat','summary':'重复最近问题'})
  def fake_dialogue(**kw): captured.update(kw); return decision
  with patch('kk_k.chat_runtime.append_remote_event'), patch('kk_k.chat_runtime.query_conversation_history',return_value=recent), patch('kk_k.chat_runtime.query_conversation_recall',return_value=recalled), patch('kk_k.chat_runtime.load_identity',return_value={'identity_id':'KK-K'}), patch('kk_k.chat_runtime.plan_capability',return_value=CapabilityPlan(None,'runtime fixture','a'*64,'b'*64)), patch('kk_k.chat_runtime.load_personality_snapshot',return_value=SimpleNamespace(state={'version':1},revision_count=0)), patch('kk_k.chat_runtime.prompt_view',return_value={'schema':'TEST.PERSONALITY'}), patch('kk_k.chat_runtime.current_beliefs',return_value=()), patch('kk_k.chat_runtime.belief_prompt_view',return_value={'schema':'TEST.BELIEFS','beliefs':[]}), patch('kk_k.chat_runtime.current_skills',return_value=()), patch('kk_k.chat_runtime.skill_prompt_view',return_value={'schema':'TEST.SKILLS','skills':[]}), patch('kk_k.chat_runtime.deliberate_dialogue',side_effect=fake_dialogue), patch('kk_k.chat_runtime.dialogue_audit_summary',return_value='audit'):
   self.assertEqual(run_turn(parse_console_line('还记得以前吗'),model_provider=lambda r,p:'x'),'回答')
  self.assertEqual([e['sequence'] for e in captured['recalled_history']],[2,3])
  self.assertEqual(captured['personality_context'],{'schema':'TEST.PERSONALITY'})
  self.assertEqual(captured['belief_context'],{'schema':'TEST.BELIEFS','beliefs':[]})
  self.assertEqual(captured['skill_context'],{'schema':'TEST.SKILLS','skills':[]})

 def test_chat_runtime_has_no_execution_import(self):
  src=inspect.getsource(__import__('kk_k.chat_runtime',fromlist=['x']))
  self.assertNotIn('fk_runtime',src); self.assertNotIn('governance',src); self.assertNotIn('submit_action',src)

if __name__=='__main__': unittest.main()
