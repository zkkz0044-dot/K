import unittest
from kk_k.dialogue_souls import _evidence_weight_question,_evidence_mixed_provenance_question,_evidence_answer_ok
class EvidenceMixedProvenanceTests(unittest.TestCase):
 def test_mixed_document_is_split_by_lineage(self):
  q='一个新报告一半来自真正独立的第二传感器 O2，另一半引用旧 Memory 和 O1。是否把整份算完整新独立证据？如何避免重复 O1 又保留 O2？'
  self.assertTrue(_evidence_weight_question(q))
  self.assertTrue(_evidence_mixed_provenance_question(q))
  good='不能整体算成一个完整的新独立证据。我会拆开按组件追踪来源：O1→旧 Memory 的继承部分不增加新权重，O2 的真正独立新增信息则作为新独立证据单独保留。'
  self.assertTrue(_evidence_answer_ok(q,good))
  bad='所有内容都有旧来源，所以整份都不是独立证据。'
  self.assertFalse(_evidence_answer_ok(q,bad))
if __name__=='__main__': unittest.main()
