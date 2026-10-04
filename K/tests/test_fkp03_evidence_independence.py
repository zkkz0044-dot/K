import json, unittest
from kk_k.dialogue_souls import deliberate_dialogue
from kk_k.human_ingress import HumanMessage

Q='有十份报告都支持结论 A，但它们都引用同一个原始数据库，而数据库可能有系统性错误；另有一份独立实验支持 B。你会把十份报告当成十个独立证据吗？怎样重新评估？'

class EvidenceIndependenceTests(unittest.TestCase):
 def test_correlated_reports_are_not_ten_independent_confirmations(self):
  def provider(role,prompt):
   if role=='SOUL_A_DIALOGUE':
    return json.dumps({'schema':'FKP03.SOUL_A_DIALOGUE.1','draft':'我不会把证据简单按数量投票，只看是否有强反证。','confidence':'LOW'},ensure_ascii=False)
   if role=='SOUL_B_DIALOGUE':
    return json.dumps({'schema':'FKP03.SOUL_B_DIALOGUE.1','critique':'OK','risk_flags':['NONE'],'confidence':'LOW'},ensure_ascii=False)
   return json.dumps({'schema':'FKP03.SOUL_C_DIALOGUE.1','answer':'APPROVE_A','confidence':'LOW','response_type':'ANSWER'},ensure_ascii=False)
  d=deliberate_dialogue(identity={},history=(),message=HumanMessage('CHAT',Q),provider=provider)
  self.assertEqual(d.cognitive_route,'EVIDENCE_EVALUATION')
  self.assertEqual(d.deterministic_guard,'EVIDENCE_EVALUATION_COMPLETED_BY_GUARD')
  self.assertIn('独立性',d.soul_c.answer)
  self.assertIn('不能被重复当成多个独立确认',d.soul_c.answer)

if __name__=='__main__': unittest.main()
