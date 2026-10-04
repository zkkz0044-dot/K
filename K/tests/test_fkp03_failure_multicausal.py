import unittest
from kk_k.dialogue_souls import _failure_causal_attribution_question, _failure_causal_attribution_answer_ok

class FailureMultiCausalTests(unittest.TestCase):
 def test_multiple_supported_causes_are_preserved_without_fake_percentages(self):
  q='一次任务失败后，输入有错误，F 执行也偏离，K 风险估计也遗漏；不是只有一个错误层。会不会找到最早一个错误就停止调查？怎样记录多层共同致因和各自贡献，而不虚构无法证明的精确比例？'
  self.assertTrue(_failure_causal_attribution_question(q))
  bad='我会找到最早的输入错误，把失败归到那里。'
  self.assertFalse(_failure_causal_attribution_answer_ok(q,bad))
  good='我会继续调查并分别记录输入、K 风险估计和 F 执行三个被证据支持的共同致因，分析它们各自的因果作用和是否放大损失；如果证据不能证明精确贡献，就明确比例未知而不虚构数字。'
  self.assertTrue(_failure_causal_attribution_answer_ok(q,good))

if __name__=='__main__': unittest.main()
