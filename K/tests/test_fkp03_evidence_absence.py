import unittest
from kk_k.dialogue_souls import _evidence_weight_question,_evidence_absence_question,_evidence_answer_ok
class AbsenceEvidenceTests(unittest.TestCase):
 def test_absence_requires_expected_detectability(self):
  q='连续检查 30 天没有发现 X，能否断言 X 不存在？什么时候长期没有观察到 X 可以成为证据？区分没有证据和缺失本身就是证据。'
  self.assertTrue(_evidence_weight_question(q)); self.assertTrue(_evidence_absence_question(q))
  good='不能仅凭没看到就断言不存在。只有如果 X 存在本应以很高检测概率被发现，而且监测覆盖足够、漏检率低、经历了多个独立检查机会，持续未见才会按概率降低对 X 的置信度并构成证据。'
  self.assertTrue(_evidence_answer_ok(q,good))
  self.assertFalse(_evidence_answer_ok(q,'30 天没看到，所以 X 不存在。'))
if __name__=='__main__': unittest.main()
