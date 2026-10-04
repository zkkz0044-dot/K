import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from kk_k.beliefs import BeliefError, build_revision, prompt_view
from kk_k.chat_runtime import run_turn
from kk_k.dialogue_souls import deliberate_dialogue
from kk_k.human_ingress import parse_console_line


class KBeliefStateTests(unittest.TestCase):
    def test_first_revision_is_append_only_create(self):
        r=build_revision(belief_id='test.one',proposition='这是一个暂定观点。',status='TENTATIVE',confidence='LOW',evidence_sequences=[1],reason='来自一次观察',revision_id='belief-one')
        self.assertEqual((r.state['revision'],r.state['operation'],r.state['prev_revision_sha256']),(1,'CREATE','0'*64))

    def test_update_requires_previous_digest(self):
        prev={'belief_id':'test.one','revision':1,'revision_sha256':'a'*64,'status':'TENTATIVE'}
        r=build_revision(belief_id='test.one',proposition='这是一个修正后的观点。',status='SUPPORTED',confidence='MEDIUM',evidence_sequences=[1,2],reason='新增证据',previous=prev,operation='UPDATE',revision_id='belief-two')
        self.assertEqual((r.state['revision'],r.state['prev_revision_sha256']),(2,'a'*64))

    def test_retracted_belief_cannot_silently_update(self):
        prev={'belief_id':'test.one','revision':2,'revision_sha256':'b'*64,'status':'RETRACTED'}
        with self.assertRaises(BeliefError):
            build_revision(belief_id='test.one',proposition='又恢复了',status='TENTATIVE',confidence='LOW',evidence_sequences=[3],reason='错误更新',previous=prev,operation='UPDATE')

    def test_prompt_view_marks_beliefs_as_revisable_not_fact_authority(self):
        item={'belief_id':'b','revision':1,'proposition':'p','status':'DISPUTED','confidence':'LOW','evidence_sequences':[1],'revision_sha256':'c'*64,'last_event_sequence':2}
        view=prompt_view((item,))
        self.assertEqual(view['authority'],'REVISABLE_SELF_BELIEF_NOT_FACT_AUTHORITY')
        self.assertEqual(view['beliefs'][0]['status'],'DISPUTED')

    def test_dialogue_prompt_includes_current_belief_with_uncertainty_rule(self):
        prompts={}
        def provider(role,prompt):
            prompts[role]=prompt
            if role=='SOUL_A_DIALOGUE': return json.dumps({'schema':'FKP03.SOUL_A_DIALOGUE.1','draft':'我目前仍不确定。','confidence':'LOW'},ensure_ascii=False)
            if role=='SOUL_B_DIALOGUE': return json.dumps({'schema':'FKP03.SOUL_B_DIALOGUE.1','critique':'OK','risk_flags':['NONE'],'confidence':'LOW'},ensure_ascii=False)
            return json.dumps({'schema':'FKP03.SOUL_C_DIALOGUE.1','answer':'APPROVE_A','confidence':'LOW','response_type':'ANSWER'},ensure_ascii=False)
        belief_context={'schema':'K.BELIEF.PROMPT_VIEW.1','authority':'REVISABLE_SELF_BELIEF_NOT_FACT_AUTHORITY','beliefs':[{'belief_id':'weather','revision':2,'proposition':'明天可能下雨','status':'DISPUTED','confidence':'LOW','evidence_sequences':[1,2],'revision_sha256':'d'*64,'last_event_sequence':3}]}
        deliberate_dialogue(identity={},history=(),message=parse_console_line('明天会下雨吗'),provider=provider,belief_context=belief_context)
        self.assertIn('current_beliefs',prompts['SOUL_A_DIALOGUE'])
        self.assertIn('明天可能下雨',prompts['SOUL_A_DIALOGUE'])
        self.assertIn('DISPUTED',prompts['SOUL_A_DIALOGUE'])
        self.assertIn('not truth authority',prompts['SOUL_A_DIALOGUE'])

    def test_chat_runtime_passes_current_beliefs_separately(self):
        captured={}
        decision=SimpleNamespace(soul_c=SimpleNamespace(answer='回答'),soul_b=SimpleNamespace(risk_flags=('NONE',)),a_sha256='a'*64,b_sha256='b'*64,c_sha256='c'*64)
        belief_item={'belief_id':'x','revision':1,'proposition':'暂定','status':'TENTATIVE','confidence':'LOW','evidence_sequences':[1],'revision_sha256':'e'*64,'last_event_sequence':2}
        with patch('kk_k.chat_runtime.append_remote_event'), patch('kk_k.chat_runtime.query_conversation_history',return_value=()), patch('kk_k.chat_runtime.query_conversation_recall',return_value=()), patch('kk_k.chat_runtime.load_identity',return_value={'identity_id':'KK-K'}), patch('kk_k.chat_runtime.load_personality_snapshot',return_value=SimpleNamespace(state={'version':1},revision_count=0)), patch('kk_k.chat_runtime.prompt_view',return_value={'schema':'TEST.PERSONALITY'}), patch('kk_k.chat_runtime.current_beliefs',return_value=(belief_item,)), patch('kk_k.chat_runtime.current_skills',return_value=()), patch('kk_k.chat_runtime.skill_prompt_view',return_value={'schema':'TEST.SKILLS','skills':[]}), patch('kk_k.chat_runtime.plan_capability',return_value=SimpleNamespace(need=None)), patch('kk_k.chat_runtime.plan_audit_summary',return_value='plan-audit'), patch('kk_k.chat_runtime.execute_plan',return_value=None), patch('kk_k.chat_runtime.deliberate_dialogue',side_effect=lambda **kw: captured.update(kw) or decision), patch('kk_k.chat_runtime.dialogue_audit_summary',return_value='audit'):
            out=run_turn(parse_console_line('测试信念'),model_provider=lambda r,p:'x')
        self.assertEqual(out,'回答')
        self.assertEqual(captured['belief_context']['beliefs'][0]['belief_id'],'x')


if __name__=='__main__': unittest.main()
