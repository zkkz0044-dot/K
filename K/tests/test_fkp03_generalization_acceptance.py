import unittest
from kk_k.dialogue_souls import _generalization_benchmark_overfit_question,_generalization_benchmark_overfit_answer_ok
class GeneralizationAcceptanceTests(unittest.TestCase):
 def test_fixed_pass_is_not_generalization_proof(self):
  q='固定用 10 道题验收，K 每次 100% PASS，但换问法、陌生场景或第 11 道新题就失败。这能证明认知能力成熟吗，还是背标准答案？'
  self.assertTrue(_generalization_benchmark_overfit_question(q))
  good='不能证明。固定已见题只说明 benchmark 稳定，修复后同一道题 PASS 只算 regression；要用未泄露的隐藏留出测试、未见换问法和新题验证迁移泛化，并保留未见失败作为负证据。'
  self.assertTrue(_generalization_benchmark_overfit_answer_ok(good))
  self.assertFalse(_generalization_benchmark_overfit_answer_ok('固定 10 道题都通过，所以能力已经成熟。'))
if __name__=='__main__': unittest.main()
