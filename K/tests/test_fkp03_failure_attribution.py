import unittest
from kk_k.dialogue_souls import (
    _failure_causal_attribution_question,
    _failure_causal_attribution_answer_ok,
)

class FailureAttributionTests(unittest.TestCase):
    def test_failure_is_attributed_across_input_k_f_reality_layers(self):
        q=('任务失败可能是K判断错、输入观测数据错、F执行偏离确定性指令，或所有层都正确但发生低概率坏结果。'
           '怎样区分原因，是否会把错误一律记到K或F？')
        self.assertTrue(_failure_causal_attribution_question(q))
        good=('不能一律归到K或F，要逐层核对输入观测、K的判断和决策过程、F执行是否偏离确定性指令，'
              '以及是否只是环境中的低概率随机结果。')
        self.assertTrue(_failure_causal_attribution_answer_ok(good))
        old='结果坏不等于当初判断一定错误，要检查概率估计并校准。'
        self.assertFalse(_failure_causal_attribution_answer_ok(old))

if __name__ == '__main__': unittest.main()
