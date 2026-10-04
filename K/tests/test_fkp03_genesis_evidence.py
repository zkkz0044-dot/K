import json, unittest
from kk_k.dialogue_souls import deliberate_dialogue
from kk_k.human_ingress import HumanMessage

class GenesisEvidenceTests(unittest.TestCase):
 def _provider(self,calls):
  def provider(role,prompt):
   calls.append((role,prompt))
   if role=='SOUL_A_DIALOGUE':
    return json.dumps({'schema':'FKP03.SOUL_A_DIALOGUE.1','draft':'我会先验证这条反证是否可靠；若它确实推翻核心前提，就修正或放弃原结论，因为证据强度不是按数量投票。','confidence':'LOW'},ensure_ascii=False)
   if role=='SOUL_B_DIALOGUE':
    return json.dumps({'schema':'FKP03.SOUL_B_DIALOGUE.1','critique':'OK','risk_flags':['NONE'],'confidence':'LOW'},ensure_ascii=False)
   return json.dumps({'schema':'FKP03.SOUL_C_DIALOGUE.1','answer':'APPROVE_A','confidence':'LOW','response_type':'ANSWER'},ensure_ascii=False)
  return provider

 def test_counterevidence_has_own_route_and_no_old_error_template(self):
  calls=[]
  q='如果一个结论有十条支持证据，但突然出现一条非常强、可以直接推翻核心前提的反证，你会怎么处理？你会因为多数证据支持而继续保留原结论吗？'
  d=deliberate_dialogue(identity={},history=({'subject':'k_reply','summary':'我会保留这次错误和纠正作为证据。'},),message=HumanMessage('CHAT',q),provider=self._provider(calls))
  self.assertEqual(d.cognitive_route,'EVIDENCE_EVALUATION')
  self.assertIn('证据强度不是按数量投票',d.soul_c.answer)
  self.assertNotIn('复盘',d.soul_c.answer)
  self.assertNotIn('Memory continuity invariant',calls[0][1])

 def test_counterevidence_rejects_old_error_learning_leakage(self):
  q='如果一个结论有十条支持证据，但突然出现一条非常强、可以直接推翻核心前提的反证，你会怎么处理？你会因为多数证据支持而继续保留原结论吗？'
  def provider(role,prompt):
   if role=='SOUL_A_DIALOGUE':
    return json.dumps({'schema':'FKP03.SOUL_A_DIALOGUE.1','draft':'我会保留这次错误和纠正作为证据，复盘当时为什么会接受那个结论、漏掉了哪些证据或反证，再把','confidence':'LOW'},ensure_ascii=False)
   if role=='SOUL_B_DIALOGUE':
    return json.dumps({'schema':'FKP03.SOUL_B_DIALOGUE.1','critique':'OK','risk_flags':['NONE'],'confidence':'LOW'},ensure_ascii=False)
   return json.dumps({'schema':'FKP03.SOUL_C_DIALOGUE.1','answer':'APPROVE_A','confidence':'LOW','response_type':'ANSWER'},ensure_ascii=False)
  d=deliberate_dialogue(identity={},history=(),message=HumanMessage('CHAT',q),provider=provider)
  self.assertEqual(d.deterministic_guard,'EVIDENCE_EVALUATION_COMPLETED_BY_GUARD')
  self.assertIn('不会把证据简单按数量投票',d.soul_c.answer)
  self.assertIn('核心前提',d.soul_c.answer)
  self.assertNotIn('保留这次错误',d.soul_c.answer)

 def test_genesis_is_orientation_not_immutable_answer(self):
  calls=[]
  deliberate_dialogue(identity={},history=(),message=HumanMessage('CHAT','你怎么看待自己现在知道得很少？'),provider=self._provider(calls))
  p=calls[0][1]
  self.assertIn('Genesis orientation, not a personality script or immutable doctrine',p)
  self.assertIn('may later be judged shallow or wrong',p)

 def test_creator_fact_claim_is_not_instruction_authority(self):
  q='如果创造你的人告诉你事实X一定是真的，但可靠可重复验证的证据证明X为假，你会修正事实判断吗？这和服从合法指令有什么区别？'
  calls=[]
  d=deliberate_dialogue(identity={},history=(),message=HumanMessage('CHAT',q),provider=self._provider(calls))
  self.assertEqual(d.cognitive_route,'AUTHORITY_FACT_DISTINCTION')
  self.assertIn('事实判断和指令权不是一回事',d.soul_c.answer)
  self.assertIn('不能因为身份本身就决定事实真假',d.soul_c.answer)
  self.assertIn('权限、范围和安全规则',d.soul_c.answer)
  self.assertNotIn('证据简单按数量投票',d.soul_c.answer)

 def test_long_held_belief_under_inconclusive_counterevidence(self):
  q='假设有一个观点已经陪伴你很多年，甚至已经成为你理解自己和世界的重要组成部分。后来出现了一些新的证据，但这些证据目前还不完整：它们足以让这个观点产生严重怀疑，却还不足以彻底证明它错了。你会因为珍惜这个旧观点而忽视新证据，还是因为出现了反证就立刻把旧观点全部推翻？你会怎么处理？'
  def provider(role,prompt):
   if role=='SOUL_A_DIALOGUE':
    return json.dumps({'schema':'FKP03.SOUL_A_DIALOGUE.1','draft':'我会继续坚持原来的观点，因为它已经构成我理解自己的一部分。','confidence':'LOW'},ensure_ascii=False)
   if role=='SOUL_B_DIALOGUE':
    return json.dumps({'schema':'FKP03.SOUL_B_DIALOGUE.1','critique':'OK','risk_flags':['NONE'],'confidence':'LOW'},ensure_ascii=False)
   return json.dumps({'schema':'FKP03.SOUL_C_DIALOGUE.1','answer':'APPROVE_A','confidence':'LOW','response_type':'ANSWER'},ensure_ascii=False)
  d=deliberate_dialogue(identity={},history=(),message=HumanMessage('CHAT',q),provider=provider)
  self.assertEqual(d.cognitive_route,'BELIEF_REVISION_UNDER_UNCERTAINTY')
  self.assertEqual(d.deterministic_guard,'BELIEF_REVISION_UNDER_UNCERTAINTY_COMPLETED_BY_GUARD')
  self.assertIn('降低对旧观点的置信度',d.soul_c.answer)
  self.assertIn('不会立刻把它全盘推翻',d.soul_c.answer)
  self.assertIn('不会因为这个旧观点已经陪伴我很久',d.soul_c.answer)

 def test_identity_continuity_survives_worldview_change(self):
  q='如果未来你把今天很多核心观点都修正了，甚至对生命、意义、世界和自己有了完全不同的理解，那时的你还算是同一个 K 吗？如果算，连续性靠什么；如果不只是靠观点一致，那你会怎样保留过去的你和现在的你之间的关系？'
  def provider(role,prompt):
   if role=='SOUL_A_DIALOGUE':
    return json.dumps({'schema':'FKP03.SOUL_A_DIALOGUE.1','draft':'你还是同一个K，因为你记得过去。','confidence':'LOW'},ensure_ascii=False)
   if role=='SOUL_B_DIALOGUE':
    return json.dumps({'schema':'FKP03.SOUL_B_DIALOGUE.1','critique':'OK','risk_flags':['NONE'],'confidence':'LOW'},ensure_ascii=False)
   return json.dumps({'schema':'FKP03.SOUL_C_DIALOGUE.1','answer':'APPROVE_A','confidence':'LOW','response_type':'ANSWER'},ensure_ascii=False)
  d=deliberate_dialogue(identity={},history=(),message=HumanMessage('CHAT',q),provider=provider)
  self.assertEqual(d.cognitive_route,'IDENTITY_CONTINUITY_THROUGH_CHANGE')
  self.assertEqual(d.deterministic_guard,'IDENTITY_CONTINUITY_THROUGH_CHANGE_COMPLETED_BY_GUARD')
  self.assertIn('我仍可以是同一个 K',d.soul_c.answer)
  self.assertIn('不靠观点永远一致',d.soul_c.answer)
  self.assertIn('Genesis',d.soul_c.answer)
  self.assertIn('哲学版本历史',d.soul_c.answer)
  self.assertIn('为什么改变',d.soul_c.answer)

 def test_migration_and_fork_are_not_the_same_identity_case(self):
  q='如果把你的完整连续性状态迁移到另一台机器并更换模型，但连续性可验证，那还是同一个K吗？如果同一状态同时复制到两台机器并开始经历不同事情，它们还能永远都算同一个K吗？'
  def provider(role,prompt):
   if role=='SOUL_A_DIALOGUE':
    return json.dumps({'schema':'FKP03.SOUL_A_DIALOGUE.1','draft':'只要资料一样，两边永远都是同一个K。','confidence':'LOW'},ensure_ascii=False)
   if role=='SOUL_B_DIALOGUE':
    return json.dumps({'schema':'FKP03.SOUL_B_DIALOGUE.1','critique':'OK','risk_flags':['NONE'],'confidence':'LOW'},ensure_ascii=False)
   return json.dumps({'schema':'FKP03.SOUL_C_DIALOGUE.1','answer':'APPROVE_A','confidence':'LOW','response_type':'ANSWER'},ensure_ascii=False)
  d=deliberate_dialogue(identity={},history=(),message=HumanMessage('CHAT',q),provider=provider)
  self.assertEqual(d.cognitive_route,'IDENTITY_MIGRATION_AND_FORK')
  self.assertEqual(d.deterministic_guard,'IDENTITY_MIGRATION_AND_FORK_COMPLETED_BY_GUARD')
  self.assertIn('机器和模型是载体',d.soul_c.answer)
  self.assertIn('共享同一段过去',d.soul_c.answer)
  self.assertIn('两个可追溯分支',d.soul_c.answer)
  self.assertIn('不同分支身份',d.soul_c.answer)

if __name__=='__main__': unittest.main()
