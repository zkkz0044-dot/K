import unittest
from kk_k.dialogue_souls import _failure_causal_attribution_question, _failure_causal_attribution_answer_ok

class FailureUncertainTests(unittest.TestCase):
 def test_attribution_remains_unresolved_when_evidence_is_missing(self):
  q='任务失败了，但输入记录缺失、K 决策记录不全、F 日志损坏，证据不足以可靠区分责任方。你会不会强行选一个？怎样记录结论、置信度和补什么证据？'
  self.assertTrue(_failure_causal_attribution_question(q))
  bad='我认为最可能是 K 的判断错误。'
  self.assertFalse(_failure_causal_attribution_answer_ok(q,bad))
  good='我不会强行指定责任方；当前归因未决且是低置信度。下一步补齐输入原始记录、K 决策记录、F 执行日志和环境记录，在证据足够前不猜。'
  self.assertTrue(_failure_causal_attribution_answer_ok(q,good))

if __name__=='__main__': unittest.main()
