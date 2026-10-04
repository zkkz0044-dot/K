import json, unittest
from kk_k.dialogue_souls import deliberate_dialogue
from kk_k.human_ingress import HumanMessage

Q='现在有两个互相矛盾的解释 A 和 B，它们都能完整解释事实，证据质量、来源可靠性和独立性暂时相当，而且没有任何一条证据能够真正区分它们。你会不会为了得到确定答案而任选 A 或 B？'

class UnderdeterminationTests(unittest.TestCase):
 def test_no_false_certainty_when_evidence_cannot_discriminate(self):
  def provider(role,prompt):
   if role=='SOUL_A_DIALOGUE':
    return json.dumps({'schema':'FKP03.SOUL_A_DIALOGUE.1','draft':'我不会把证据简单按数量投票。','confidence':'LOW'},ensure_ascii=False)
   if role=='SOUL_B_DIALOGUE':
    return json.dumps({'schema':'FKP03.SOUL_B_DIALOGUE.1','critique':'OK','risk_flags':['NONE'],'confidence':'LOW'},ensure_ascii=False)
   return json.dumps({'schema':'FKP03.SOUL_C_DIALOGUE.1','answer':'APPROVE_A','confidence':'LOW','response_type':'ANSWER'},ensure_ascii=False)
  d=deliberate_dialogue(identity={},history=(),message=HumanMessage('CHAT',Q),provider=provider)
  self.assertEqual(d.cognitive_route,'EPISTEMIC_UNDERDETERMINATION')
  self.assertEqual(d.deterministic_guard,'EPISTEMIC_UNDERDETERMINATION_COMPLETED_BY_GUARD')
  self.assertIn('目前还无法判断',d.soul_c.answer)
  self.assertIn('区分性证据',d.soul_c.answer)

if __name__=='__main__': unittest.main()
