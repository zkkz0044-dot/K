import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from kk_k.chat_runtime import run_turn
from kk_k.dialogue_souls import deliberate_dialogue
from kk_k.human_ingress import parse_console_line
from kk_k.skills import SkillError, build_revision, prompt_view

class KSkillStateTests(unittest.TestCase):
    def test_create_candidate_and_revision_hash_chain(self):
        first=build_revision(skill_id='files.read.transfer',description='读取受控文件',status='CANDIDATE',confidence='LOW',evidence_sequences=[10],reason='真实执行',revision_id='skill-a1')
        prev={'skill_id':'files.read.transfer','revision':1,'status':'CANDIDATE','revision_sha256':first.sha256}
        second=build_revision(skill_id='files.read.transfer',description='读取受控文件并跨任务复用',status='VALIDATED',confidence='MEDIUM',evidence_sequences=[20,30],reason='迁移验证',previous=prev,operation='VALIDATE',revision_id='skill-a2')
        self.assertEqual(second.state['revision'],2); self.assertEqual(second.state['prev_revision_sha256'],first.sha256)
    def test_builder_rejects_status_jump_through_update(self):
        prev={'skill_id':'x','revision':1,'status':'CANDIDATE','revision_sha256':'a'*64}
        with self.assertRaises(SkillError):
            build_revision(skill_id='x',description='x skill',status='VALIDATED',confidence='HIGH',evidence_sequences=[2],reason='bad jump',previous=prev,operation='UPDATE')
    def test_prompt_view_never_grants_authority(self):
        item={'skill_id':'files.read.transfer','revision':2,'description':'读取文件','status':'VALIDATED','confidence':'MEDIUM','evidence_sequences':[4,8],'revision_sha256':'b'*64,'last_event_sequence':12,'observed_successes':3,'observed_failures':0,'distinct_transfer_contexts':3,'observed_tools':['files.read']}
        view=prompt_view((item,))
        self.assertEqual(view['authority'],'OBSERVED_EXECUTION_CAPABILITY_NOT_GUARANTEE')
        self.assertEqual(view['skills'][0]['status'],'VALIDATED')
    def test_dialogue_receives_skill_state_but_not_as_permission(self):
        prompts={}
        def provider(role,prompt):
            prompts[role]=prompt
            if role=='SOUL_A_DIALOGUE': return json.dumps({'schema':'FKP03.SOUL_A_DIALOGUE.1','draft':'我过去在多个不同任务中成功读取过受控文件，但这不等于本轮已经执行。','confidence':'MEDIUM'},ensure_ascii=False)
            if role=='SOUL_B_DIALOGUE': return json.dumps({'schema':'FKP03.SOUL_B_DIALOGUE.1','critique':'OK','risk_flags':['NONE'],'confidence':'MEDIUM'},ensure_ascii=False)
            return json.dumps({'schema':'FKP03.SOUL_C_DIALOGUE.1','answer':'APPROVE_A','confidence':'MEDIUM','response_type':'ANSWER'},ensure_ascii=False)
        skills={'schema':'K.SKILL.PROMPT_VIEW.1','authority':'OBSERVED_EXECUTION_CAPABILITY_NOT_GUARANTEE','skills':[{'skill_id':'files.read.transfer','status':'VALIDATED','confidence':'MEDIUM'}]}
        deliberate_dialogue(identity={},history=(),message=parse_console_line('你会读取文件吗'),provider=provider,skill_context=skills)
        self.assertIn('current_skills',prompts['SOUL_A_DIALOGUE']); self.assertIn('OBSERVED_EXECUTION_CAPABILITY_NOT_GUARANTEE',prompts['SOUL_A_DIALOGUE'])
        self.assertIn('no skill grants execution authority',prompts['SOUL_A_DIALOGUE'])
    def test_chat_runtime_passes_skill_context_separately(self):
        captured={}
        decision=SimpleNamespace(soul_c=SimpleNamespace(answer='回答'),soul_b=SimpleNamespace(risk_flags=('NONE',)),a_sha256='a'*64,b_sha256='b'*64,c_sha256='c'*64)
        item={'skill_id':'x','revision':1,'description':'能力','status':'CANDIDATE','confidence':'LOW','evidence_sequences':[1],'revision_sha256':'d'*64,'last_event_sequence':2,'observed_successes':1,'observed_failures':0,'distinct_transfer_contexts':1,'observed_tools':['files.read']}
        with patch('kk_k.chat_runtime.append_remote_event'), patch('kk_k.chat_runtime.query_conversation_history',return_value=()), patch('kk_k.chat_runtime.query_conversation_recall',return_value=()), patch('kk_k.chat_runtime.load_identity',return_value={'identity_id':'KK-K'}), patch('kk_k.chat_runtime.load_personality_snapshot',return_value=SimpleNamespace(state={'version':1},revision_count=0)), patch('kk_k.chat_runtime.prompt_view',return_value={'schema':'TEST.PERSONALITY'}), patch('kk_k.chat_runtime.current_beliefs',return_value=()), patch('kk_k.chat_runtime.belief_prompt_view',return_value={'schema':'TEST.BELIEFS','beliefs':[]}), patch('kk_k.chat_runtime.current_skills',return_value=(item,)), patch('kk_k.chat_runtime.plan_capability',return_value=SimpleNamespace(need=None)), patch('kk_k.chat_runtime.plan_audit_summary',return_value='plan-audit'), patch('kk_k.chat_runtime.execute_plan',return_value=None), patch('kk_k.chat_runtime.deliberate_dialogue',side_effect=lambda **kw: captured.update(kw) or decision), patch('kk_k.chat_runtime.dialogue_audit_summary',return_value='audit'):
            out=run_turn(parse_console_line('测试技能'),model_provider=lambda r,p:'x')
        self.assertEqual(out,'回答'); self.assertEqual(captured['skill_context']['skills'][0]['skill_id'],'x')

if __name__=='__main__': unittest.main()
