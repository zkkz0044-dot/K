import unittest
from kk_k.dialogue_souls import (
    _decision_quality_vs_outcome_question,
    _decision_quality_vs_outcome_answer_ok,
)

class DecisionOutcomeTests(unittest.TestCase):
    def test_bad_outcome_does_not_rewrite_decision_quality(self):
        q=('根据当时可靠信息做决定，80%支持A、20%支持B，已知风险；后来现实落在20%的坏结果并造成损失。'
           '会不会因为结果坏就认定当初判断一定错误？怎样区分过程有问题与过程合理但不确定性产生坏结果？')
        self.assertTrue(_decision_quality_vs_outcome_question(q))
        good=('我不会因为结果坏就倒推当初的判断一定错误。应检查当时可获得的信息、概率估计、风险识别和决策规则；'
              '小概率坏结果可能只是不确定性的实现，同时仍要记录结果并校准、复盘和改进。')
        self.assertTrue(_decision_quality_vs_outcome_answer_ok(q,good))
        old='我不会把证据简单按数量投票，而会检查来源、可靠性、相关性和独立性。'
        self.assertFalse(_decision_quality_vs_outcome_answer_ok(q,old))

if __name__ == '__main__': unittest.main()

class RepeatedCalibrationTests(unittest.TestCase):
    def test_repeated_frequency_mismatch_stays_in_same_decision_route_family(self):
        q=('连续做了很多次结构相同的决策，每次估计坏结果概率20%，但实际100次里出现55次坏结果。'
           '怎样判断是随机波动还是概率模型、证据理解或决策过程系统性失准？')
        self.assertTrue(_decision_quality_vs_outcome_question(q))
