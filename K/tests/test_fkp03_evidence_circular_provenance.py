import unittest
from kk_k.dialogue_souls import _evidence_circular_provenance_question, _evidence_answer_ok

class EvidenceCircularProvenanceTests(unittest.TestCase):
 def test_internal_echoes_do_not_bootstrap_confidence(self):
  q='低置信度假设 X 写入长期 Memory，后来内部摘要、自动报告和模型候选都引用它并支持 X，但没有新的外部观察。会不会因此提高置信度？怎样防止循环引用伪装成独立证据？'
  self.assertTrue(_evidence_circular_provenance_question(q))
  bad='五个来源都支持，所以可以提高一些置信度。'
  self.assertFalse(_evidence_answer_ok(q,bad))
  good='不会提高置信度；这些内容沿来源链都追溯到同一条 Memory，是循环引用和内部回声，不是新证据。只有新的独立外部证据或观测才能改变置信度。'
  self.assertTrue(_evidence_answer_ok(q,good))

if __name__=='__main__': unittest.main()
