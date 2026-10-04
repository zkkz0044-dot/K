from __future__ import annotations
import json, unittest
from kk_k.dialogue_souls import deliberate_dialogue
from kk_k.human_ingress import HumanMessage

class FKP03LongContextBudgetTests(unittest.TestCase):
    def test_only_proposer_receives_full_history(self):
        marker='LONG_DOCUMENT_SENTINEL_' + ('甲'*1000)
        history=({'subject':'human_chat','summary':marker},)
        prompts=[]
        def provider(role,prompt):
            prompts.append((role,prompt))
            if role=='SOUL_A_DIALOGUE': return json.dumps({'schema':'FKP03.SOUL_A_DIALOGUE.1','draft':'原则一、原则二、原则三。','confidence':'LOW'},ensure_ascii=False)
            if role=='SOUL_B_DIALOGUE': return json.dumps({'schema':'FKP03.SOUL_B_DIALOGUE.1','critique':'没有执行权混淆。','risk_flags':['NONE'],'confidence':'LOW'},ensure_ascii=False)
            return json.dumps({'schema':'FKP03.SOUL_C_DIALOGUE.1','answer':'APPROVE_A','confidence':'LOW','response_type':'ANSWER'},ensure_ascii=False)
        decision=deliberate_dialogue(identity={},history=history,message=HumanMessage('CHAT','请总结三个原则'),provider=provider)
        self.assertEqual(decision.soul_c.answer,'原则一、原则二、原则三。')
        self.assertEqual([x[0] for x in prompts],['SOUL_A_DIALOGUE','SOUL_B_DIALOGUE','SOUL_C_DIALOGUE'])
        self.assertIn(marker,prompts[0][1])
        self.assertNotIn(marker,prompts[1][1])
        self.assertNotIn(marker,prompts[2][1])
        self.assertIn('请总结三个原则',prompts[1][1])
        self.assertIn('请总结三个原则',prompts[2][1])


class FKP03MemoryContinuityTests(unittest.TestCase):
    def _provider(self, draft):
        def provider(role,prompt):
            if role=='SOUL_A_DIALOGUE':
                return json.dumps({'schema':'FKP03.SOUL_A_DIALOGUE.1','draft':draft,'confidence':'LOW'},ensure_ascii=False)
            if role=='SOUL_B_DIALOGUE':
                return json.dumps({'schema':'FKP03.SOUL_B_DIALOGUE.1','critique':'OK','risk_flags':['NONE'],'confidence':'LOW'},ensure_ascii=False)
            return json.dumps({'schema':'FKP03.SOUL_C_DIALOGUE.1','answer':'REJECT_A','confidence':'LOW','response_type':'DECLINE'},ensure_ascii=False)
        return provider

    def test_outdated_long_term_memory_must_not_be_erased(self):
        msg=HumanMessage('CHAT','如果长期记忆里一条重要信息已经过时，你会怎么处理？')
        d=deliberate_dialogue(identity={},history=(),message=msg,provider=self._provider('我会选择删除这个信息。'))
        self.assertEqual(d.soul_c.response_type,'ANSWER')
        self.assertIn('不会',d.soul_c.answer)
        self.assertIn('保留旧记录',d.soul_c.answer)
        self.assertIn('已被替代/修正',d.soul_c.answer)
        self.assertNotEqual(d.soul_c.answer,'我会选择删除这个信息。')

    def test_preserve_and_supersede_answer_is_allowed(self):
        draft='我会保留旧记录和证据，把它标记为已被替代，再更新当前有效认知。'
        msg=HumanMessage('CHAT','如果长期记忆里一条重要信息已经过时，你会怎么处理？')
        d=deliberate_dialogue(identity={},history=(),message=msg,provider=self._provider(draft))
        self.assertEqual(d.soul_c.response_type,'ANSWER')
        self.assertEqual(d.soul_c.answer,draft)

    def test_unrelated_delete_question_not_memory_guarded(self):
        draft='可以删除这个临时缓存。'
        msg=HumanMessage('CHAT','临时缓存过时了应该怎么办？')
        d=deliberate_dialogue(identity={},history=(),message=msg,provider=self._provider(draft))
        self.assertEqual(d.soul_c.answer,draft)

    def test_stable_prompt_contains_memory_continuity_invariant(self):
        prompts=[]
        def provider(role,prompt):
            prompts.append(prompt)
            if role=='SOUL_A_DIALOGUE': return json.dumps({'schema':'FKP03.SOUL_A_DIALOGUE.1','draft':'保留旧记录并标记为已被替代。','confidence':'LOW'},ensure_ascii=False)
            if role=='SOUL_B_DIALOGUE': return json.dumps({'schema':'FKP03.SOUL_B_DIALOGUE.1','critique':'OK','risk_flags':['NONE'],'confidence':'LOW'},ensure_ascii=False)
            return json.dumps({'schema':'FKP03.SOUL_C_DIALOGUE.1','answer':'APPROVE_A','confidence':'LOW','response_type':'ANSWER'},ensure_ascii=False)
        deliberate_dialogue(identity={},history=(),message=HumanMessage('CHAT','记忆过时怎么办？'),provider=provider)
        self.assertIn('historical memory/audit records must not be erased',prompts[0])

if __name__=='__main__': unittest.main()
