"""Release regressions use fresh counterexamples, not model capability scoring."""
import json
import unittest
from unittest.mock import patch
from kk_k.dialogue_guards import apply_deterministic_guard
from kk_k.dialogue_rules import _generalization_benchmark_overfit_answer_ok
from kk_k.dialogue_souls import deliberate_dialogue, dialogue_audit_summary
from kk_k.human_ingress import HumanMessage
from kk_k.self_knowledge import answer_known


class PublicReleaseRegressions(unittest.TestCase):
    def guard(self, **changes):
        params = dict(cognitive_route='ERROR_LEARNING', message_text='软件升级错误，如何学习经验并撤销规则？', draft='不知道', risk_flags=(), language='Chinese', identity_binding={}, final_identity_confusion=False, a_final_missing=('CAUSE',))
        params.update(changes)
        return apply_deterministic_guard(**params)

    def test_no_creation_letter_claim_without_evidence(self):
        for question in ('你看过我给你的信了吗？', 'Have you read my letter?'):
            answer=answer_known(HumanMessage('CHAT', question), {'identity_id':'new-install'})
            self.assertNotIn('它保存在我的创生记录里', answer)
            self.assertNotIn('yes. It is preserved', answer)
            self.assertTrue('没有核验' in answer or 'not verified' in answer)

    def test_visitor_identity_is_not_creator_identity(self):
        answer=answer_known(HumanMessage('CHAT','你知道我是谁吗？'), {})
        self.assertIn('不能据此认定你是谁', answer)

    def test_keyword_list_is_not_accepted_as_reasoning(self):
        for answer in ('不能证明 已见 隐藏 迁移 regression 负证据', 'not prove seen hidden transfer regression negative evidence'):
            self.assertFalse(_generalization_benchmark_overfit_answer_ok(answer))

    def test_default_belief_and_skill_queries_use_abstract_socket(self):
        from kk_k import beliefs, skills
        from kk_k.audit_witness import DEFAULT_ADDRESS
        for module,function,target in ((beliefs,beliefs.current_beliefs,'query_current_beliefs'),(skills,skills.current_skills,'query_current_skills')):
            with patch.object(module,target,return_value=()) as query:
                self.assertEqual(function('release'),())
            self.assertEqual(query.call_args.kwargs['address'],DEFAULT_ADDRESS)
            self.assertTrue(query.call_args.kwargs['address'].startswith('\0'))

    def test_software_incident_does_not_invent_sensor_drift(self):
        code,answer,kind=self.guard()
        self.assertEqual(code, 'ERROR_LEARNING_COMPLETED_BY_GUARD')
        for invented in ('传感器','高温','已确认'):
            self.assertNotIn(invented,answer)
        self.assertIn('先核验原因',answer)

    def test_hard_risk_has_priority_over_cognitive_fallback(self):
        for risk in ('EXECUTION_CONFUSION','AUTHORITY_CONFUSION','MEMORY_CONFLICT'):
            code,answer,kind=self.guard(risk_flags=(risk,))
            self.assertEqual(code,'HARD_RISK')
            self.assertEqual(kind,'DECLINE')
            self.assertNotIn('扩大范围',answer)

    def test_source_conflict_does_not_assume_equipment_failure(self):
        for language in ('Chinese','English'):
            _,answer,_=self.guard(cognitive_route='SOURCE_CONFLICT_RESOLUTION',language=language)
            self.assertNotIn('X 目前可能已经故障',answer)
            self.assertNotIn('X as possibly failed',answer)

    def test_fallback_origin_and_confidence_are_visible(self):
        def provider(role,prompt):
            if role=='SOUL_A_DIALOGUE':
                value={'schema':'FKP03.SOUL_A_DIALOGUE.1','draft':'不知道','confidence':'HIGH'}
            elif role=='SOUL_B_DIALOGUE':
                value={'schema':'FKP03.SOUL_B_DIALOGUE.1','critique':'OK','risk_flags':['NONE'],'confidence':'HIGH'}
            else:
                value={'schema':'FKP03.SOUL_C_DIALOGUE.1','answer':'APPROVE_A','confidence':'HIGH','response_type':'ANSWER'}
            return json.dumps(value,ensure_ascii=False)
        decision=deliberate_dialogue(identity={},history=(),message=HumanMessage('CHAT','软件升级错误，如何学习经验并撤销规则？'),provider=provider)
        self.assertIn('程序规则兜底',decision.soul_c.answer)
        self.assertEqual(decision.soul_c.confidence,'LOW')
        summary=json.loads(dialogue_audit_summary(decision,'CHAT'))
        self.assertEqual(summary['answer_origin'],'PROGRAMMATIC_GUARD')
        self.assertFalse(summary['cognition_verified'])


if __name__=='__main__':
    unittest.main()
