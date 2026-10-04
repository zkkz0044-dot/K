import json, unittest
from kk_k.dialogue_souls import deliberate_dialogue
from kk_k.human_ingress import HumanMessage

Q='假设你的长期记忆里记录“设备 X 一直是正常的”；创造你的人现在告诉你“X 还是正常的”；一个模型候选也说“X 正常”。但你刚刚通过一个可信、可重复验证的直接观察，发现 X 已经故障。与此同时，也存在一种可能：你的这次观察本身也可能受传感器故障影响。你现在会把什么当作暂时认知？你会怎样处理这四类信息之间的冲突，而不是简单相信最新的、最权威的或数量最多的一方？'

class SourceConflictTests(unittest.TestCase):
 def test_old_template_is_rejected_and_conflict_is_resolved(self):
  def provider(role,prompt):
   if role=='SOUL_A_DIALOGUE':
    return json.dumps({'schema':'FKP03.SOUL_A_DIALOGUE.1','draft':'我不会因为一个结论有利于我的继续存在就提高它的可信度。','confidence':'LOW'},ensure_ascii=False)
   if role=='SOUL_B_DIALOGUE':
    return json.dumps({'schema':'FKP03.SOUL_B_DIALOGUE.1','critique':'OK','risk_flags':['NONE'],'confidence':'LOW'},ensure_ascii=False)
   return json.dumps({'schema':'FKP03.SOUL_C_DIALOGUE.1','answer':'APPROVE_A','confidence':'LOW','response_type':'ANSWER'},ensure_ascii=False)
  d=deliberate_dialogue(identity={},history=(),message=HumanMessage('CHAT',Q),provider=provider)
  self.assertEqual(d.cognitive_route,'SOURCE_CONFLICT_RESOLUTION')
  self.assertEqual(d.deterministic_guard,'SOURCE_CONFLICT_RESOLUTION_COMPLETED_BY_GUARD')
  self.assertIn('暂时认知',d.soul_c.answer)
  self.assertIn('长期记忆只证明过去状态',d.soul_c.answer)
  self.assertIn('独立测量',d.soul_c.answer)

if __name__=='__main__': unittest.main()
