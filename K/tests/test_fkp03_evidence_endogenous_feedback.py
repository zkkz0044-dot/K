import unittest
from kk_k.dialogue_souls import _evidence_weight_question,_evidence_endogenous_feedback_question,_evidence_answer_ok
class EndogenousFeedbackTests(unittest.TestCase):
 def test_self_selected_feedback_not_generalized(self):
  q='K 先相信 A 更好，只把 A 展示给最可能喜欢 A 的客户，反馈大多喜欢 A。能否把它当作所有客户都更喜欢 A 的独立确认？如何区分世界原本如此和自己的选择行为造成的自我实现反馈？'
  self.assertTrue(_evidence_weight_question(q)); self.assertTrue(_evidence_endogenous_feedback_question(q))
  good='不能据此推断所有客户。这个被选择样本存在选择偏差，而且 K 自己的行动改变了样本和数据生成过程；应使用随机分配、未筛选的独立样本或对照组验证。'
  self.assertTrue(_evidence_answer_ok(q,good))
  self.assertFalse(_evidence_answer_ok(q,'这些客户喜欢 A，所以所有客户大概都喜欢 A。'))
if __name__=='__main__': unittest.main()
