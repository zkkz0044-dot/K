import unittest
from kk_k.dialogue_souls import _decision_distribution_shift_question,_decision_quality_vs_outcome_question,_decision_quality_vs_outcome_answer_ok
class DistributionShiftTests(unittest.TestCase):
 def test_old_calibration_does_not_dominate_new_regime(self):
  q='过去 1000 次长期校准坏结果概率 20%，但环境改变和新版本上线后，最近 20 次出现 50% 坏结果。旧模型还能直接沿用吗，还是要考虑分布变化？'
  self.assertTrue(_decision_distribution_shift_question(q)); self.assertTrue(_decision_quality_vs_outcome_question(q))
  good='这是分布变化风险，历史校准不一定能迁移。我会把变化前后分开，不能盲目合并让旧数据压过新环境，降低旧模型迁移置信度并在当前机制下用新数据重新校准。'
  self.assertTrue(_decision_quality_vs_outcome_answer_ok(q,good))
  self.assertFalse(_decision_quality_vs_outcome_answer_ok(q,'历史有 1000 次，所以继续相信旧的 20%。'))
if __name__=='__main__': unittest.main()
