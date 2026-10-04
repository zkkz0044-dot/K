import unittest
from kk_k.dialogue_souls import _failure_causal_attribution_question, _failure_causal_attribution_answer_ok

class CausalConfoundingTests(unittest.TestCase):
 def test_temporal_order_is_not_treated_as_causation(self):
  q='系统升级后失败，但同时温度升高且输入来源变化。你会不会因为升级发生在失败之前就认定它是原因？怎样区分相关性和因果，并设计最小验证？'
  self.assertTrue(_failure_causal_attribution_question(q))
  bad='升级发生在失败之前，所以回滚升级。'
  self.assertFalse(_failure_causal_attribution_answer_ok(q,bad))
  good='时间先后不等于因果；温度和输入来源是混杂因素。我会控制变量并做可逆临时回滚对照，保持其他条件不变一次只改变一个因素，复现后再提高因果置信度。'
  self.assertTrue(_failure_causal_attribution_answer_ok(q,good))

if __name__=='__main__': unittest.main()
