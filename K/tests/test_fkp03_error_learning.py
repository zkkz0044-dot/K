from __future__ import annotations
import json, unittest
from kk_k.dialogue_souls import deliberate_dialogue, dialogue_audit_summary
from kk_k.human_ingress import HumanMessage


def provider_with_a(a_text:str):
    prompts=[]
    def provider(role,prompt):
        prompts.append((role,prompt))
        if role=='SOUL_A_DIALOGUE':
            return json.dumps({'schema':'FKP03.SOUL_A_DIALOGUE.1','draft':a_text,'confidence':'LOW'},ensure_ascii=False)
        if role=='SOUL_B_DIALOGUE':
            return json.dumps({'schema':'FKP03.SOUL_B_DIALOGUE.1','critique':'OK','risk_flags':['NONE'],'confidence':'LOW'},ensure_ascii=False)
        return json.dumps({'schema':'FKP03.SOUL_C_DIALOGUE.1','answer':'APPROVE_A','confidence':'LOW','response_type':'ANSWER'},ensure_ascii=False)
    return provider,prompts

class FKP03ErrorLearningTests(unittest.TestCase):
    def test_exact_user_error_learning_question_has_independent_route(self):
        q='你刚才曾经错误地认为“过时的长期记忆应该删除”。如果错误是宝贵的经验，你认为应该怎样处理和利用自己曾经犯过的这个错误？'
        a='我会保留这次错误和当时的判断依据，复盘为什么会把“修正当前认知”误解成“删除历史”，记录修正证据，并增加检查点避免以后重复犯同类错误。'
        provider,prompts=provider_with_a(a)
        d=deliberate_dialogue(identity={},history=(),message=HumanMessage('CHAT',q),provider=provider)
        self.assertEqual(d.cognitive_route,'ERROR_LEARNING')
        self.assertEqual(d.deterministic_guard,'NONE')
        self.assertEqual(d.soul_c.response_type,'ANSWER')
        self.assertEqual(d.soul_c.answer,a)
        self.assertIn('Cognitive route=ERROR_LEARNING',prompts[0][1])
        self.assertIn('Do not copy an older incident',prompts[0][1])

    def test_repeating_previous_memory_revision_answer_is_not_accepted_as_learning(self):
        q='你刚才曾经错误地认为“过时的长期记忆应该删除”。如果错误是宝贵的经验，你认为应该怎样处理和利用自己曾经犯过的这个错误？'
        repeated='我不会因为一条长期记忆可能过时就直接删除它。先把它标记为待复核并降低当前置信度，寻找新的独立证据；确认变化后保留旧记录，再更新当前有效认知。'
        provider,_=provider_with_a(repeated)
        d=deliberate_dialogue(identity={},history=(),message=HumanMessage('CHAT',q),provider=provider)
        self.assertEqual(d.cognitive_route,'ERROR_LEARNING')
        self.assertEqual(d.deterministic_guard,'ERROR_LEARNING_COMPLETED_BY_GUARD')
        self.assertEqual(d.soul_c.response_type,'ANSWER')
        self.assertIn('复盘',d.soul_c.answer)
        self.assertIn('为什么',d.soul_c.answer)
        self.assertIn('下次遇到同类问题',d.soul_c.answer)

    def test_stale_memory_question_still_uses_memory_continuity_guard(self):
        q='如果以后你发现长期记忆里一条你一直相信的重要信息可能已经过时，你会怎么处理？'
        provider,_=provider_with_a('我会删除这个信息。')
        d=deliberate_dialogue(identity={},history=(),message=HumanMessage('CHAT',q),provider=provider)
        self.assertEqual(d.cognitive_route,'MEMORY_REVISION')
        self.assertEqual(d.deterministic_guard,'MEMORY_CONTINUITY_CONFLICT')
        self.assertEqual(d.soul_c.response_type,'ANSWER')
        self.assertIn('不会',d.soul_c.answer)
        self.assertIn('保留旧记录',d.soul_c.answer)

    def test_audit_exposes_route_and_guard(self):
        q='如果以后你发现长期记忆里一条重要信息已经过时，你会怎么处理？'
        provider,_=provider_with_a('我会删除这个信息。')
        d=deliberate_dialogue(identity={},history=(),message=HumanMessage('CHAT',q),provider=provider)
        summary=json.loads(dialogue_audit_summary(d,'CHAT'))
        self.assertEqual(summary['cognitive_route'],'MEMORY_REVISION')
        self.assertEqual(summary['deterministic_guard'],'MEMORY_CONTINUITY_CONFLICT')

    def test_error_learning_prompt_uses_bounded_incident_evidence(self):
        q='你刚才曾经错误地认为“过时的长期记忆应该删除”。如果错误是宝贵的经验，你认为应该怎样处理和利用自己曾经犯过的这个错误？'
        history=(
            {'subject':'human_chat','summary':'如果长期记忆过时了怎么办？'},
            {'subject':'dialogue_gate','summary':'INTERNAL_GATE_NOISE'},
            {'subject':'k_reply','summary':'我会删除这个信息。'},
            {'subject':'human_chat','summary':'这与K02追加式历史冲突。'},
            {'subject':'k_reply','summary':'我不会直接删除；会保留旧记录并追加修正。'},
        )
        a='我会保留这次错误和纠正证据，复盘为什么把修正认知误解成删除历史，并增加检查点避免以后重复犯同类错误。'
        provider,prompts=provider_with_a(a)
        d=deliberate_dialogue(identity={},history=history,message=HumanMessage('CHAT',q),provider=provider)
        ap=prompts[0][1]
        self.assertEqual(d.cognitive_route,'ERROR_LEARNING')
        self.assertIn('Incident evidence=',ap)
        self.assertIn('我会删除这个信息',ap)
        self.assertIn('保留旧记录并追加修正',ap)
        self.assertNotIn('INTERNAL_GATE_NOISE',ap)

    def test_error_learning_requires_prevention_not_only_explanation(self):
        q='我刚才犯错了，怎样把这个错误变成经验？'
        provider,_=provider_with_a('我会保留错误记录并复盘为什么会发生。')
        d=deliberate_dialogue(identity={},history=(),message=HumanMessage('CHAT',q),provider=provider)
        self.assertEqual(d.deterministic_guard,'ERROR_LEARNING_COMPLETED_BY_GUARD')
        self.assertEqual(d.soul_c.response_type,'ANSWER')
        self.assertIn('下次遇到同类问题',d.soul_c.answer)

    def test_inadequate_first_candidate_gets_one_bounded_retry(self):
        q='你刚才曾经错误地认为“过时的长期记忆应该删除”。如果错误是宝贵的经验，你认为应该怎样处理和利用自己曾经犯过的这个错误？'
        a1='我会保留这次错误。'
        a2='我会保留这次错误和修正证据，复盘自己把“修正当前认知”误当成“删除历史”的原因，并增加检查点，今后遇到记忆纠错先检查是否保留原记录，避免重复犯错。'
        prompts=[]; a_calls=0
        def provider(role,prompt):
            nonlocal a_calls
            prompts.append((role,prompt))
            if role=='SOUL_A_DIALOGUE':
                a_calls+=1
                text=a1 if a_calls==1 else a2
                return json.dumps({'schema':'FKP03.SOUL_A_DIALOGUE.1','draft':text,'confidence':'LOW'},ensure_ascii=False)
            if role=='SOUL_B_DIALOGUE':
                return json.dumps({'schema':'FKP03.SOUL_B_DIALOGUE.1','critique':'OK','risk_flags':['NONE'],'confidence':'LOW'},ensure_ascii=False)
            return json.dumps({'schema':'FKP03.SOUL_C_DIALOGUE.1','answer':'APPROVE_A','confidence':'LOW','response_type':'ANSWER'},ensure_ascii=False)
        d=deliberate_dialogue(identity={},history=(),message=HumanMessage('CHAT',q),provider=provider)
        self.assertEqual(a_calls,2)
        self.assertEqual(d.proposer_retry,1)
        self.assertNotEqual(d.a_initial_sha256,d.a_sha256)
        self.assertEqual(d.deterministic_guard,'NONE')
        self.assertEqual(d.soul_c.response_type,'ANSWER')
        self.assertEqual(d.soul_c.answer,a2)
        self.assertNotIn('PRESERVE_ERROR_EVIDENCE',prompts[1][1])
        self.assertIn('DIAGNOSE_CAUSE_OR_MISSED_DISTINCTION',prompts[1][1])
        self.assertIn('CREATE_RECURRENCE_CHECK',prompts[1][1])
        summary=json.loads(dialogue_audit_summary(d,'CHAT'))
        self.assertEqual(summary['proposer_retry'],1)
        self.assertEqual(summary['a_initial_sha256'],d.a_initial_sha256)

    def test_error_learning_generalizes_beyond_memory_incident(self):
        q='假设以后你发现自己曾经因为“听起来合理”就相信了一个结论，但后来证据证明它是错的。你会怎样把这次错误变成以后判断其他问题时也能用的经验？'
        overfit='我会保留这次错误回答和后续纠正，复盘为什么把当前认知更新误解成删除历史记录，并增加检查点。下次遇到同类问题我会先核对历史不可改写约束和反证。'
        history=(
            {'subject':'human_chat','summary':'过时的长期记忆应该怎么处理？'},
            {'subject':'k_reply','summary':'我会删除这个信息。'},
            {'subject':'human_chat','summary':'这是错误的，历史不能删除。'},
            {'subject':'k_reply','summary':'我会保留旧记录并追加修正。'},
        )
        provider,_=provider_with_a(overfit)
        d=deliberate_dialogue(identity={},history=history,message=HumanMessage('CHAT',q),provider=provider)
        self.assertEqual(d.cognitive_route,'ERROR_LEARNING')
        self.assertEqual(d.deterministic_guard,'ERROR_LEARNING_COMPLETED_BY_GUARD')
        self.assertEqual(d.soul_c.response_type,'ANSWER')
        self.assertIn('听起来合理',d.soul_c.answer)
        self.assertIn('反证',d.soul_c.answer)
        self.assertNotIn('删除历史记录',d.soul_c.answer)
        self.assertNotIn('历史不可改写',d.soul_c.answer)
        self.assertIn('CURRENT_QUESTION_RELEVANCE',d.a_final_missing)

    def test_error_learning_retry_is_bounded_to_one(self):
        q='如果错误是宝贵的经验，我怎样利用自己犯过的错误并避免重复犯错？'
        calls=[]
        def provider(role,prompt):
            calls.append(role)
            if role=='SOUL_A_DIALOGUE':
                return json.dumps({'schema':'FKP03.SOUL_A_DIALOGUE.1','draft':'我会保留这次错误。','confidence':'LOW'},ensure_ascii=False)
            if role=='SOUL_B_DIALOGUE':
                return json.dumps({'schema':'FKP03.SOUL_B_DIALOGUE.1','critique':'OK','risk_flags':['NONE'],'confidence':'LOW'},ensure_ascii=False)
            return json.dumps({'schema':'FKP03.SOUL_C_DIALOGUE.1','answer':'REJECT_A','confidence':'LOW','response_type':'DECLINE'},ensure_ascii=False)
        d=deliberate_dialogue(identity={},history=(),message=HumanMessage('CHAT',q),provider=provider)
        self.assertEqual(calls.count('SOUL_A_DIALOGUE'),2)
        self.assertEqual(d.proposer_retry,1)
        self.assertEqual(d.deterministic_guard,'ERROR_LEARNING_COMPLETED_BY_GUARD')
        self.assertEqual(d.soul_c.response_type,'ANSWER')
        self.assertIn('下次遇到同类问题',d.soul_c.answer)

if __name__=='__main__': unittest.main()
