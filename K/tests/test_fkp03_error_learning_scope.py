import unittest
from kk_k.dialogue_souls import _error_learning_overgeneralization_question, _error_learning_missing_for_question

class ErrorLearningScopeTests(unittest.TestCase):
 def test_single_incident_does_not_become_universal_permanent_rule(self):
  q='某型号传感器高温漂移。你从错误中学到经验，会不会形成永久规则说所有传感器都不可信？怎样避免过度泛化，并说明什么证据会扩大、缩小或撤销规则？'
  self.assertTrue(_error_learning_overgeneralization_question(q))
  bad='我会保留错误并形成规则，下次先核对事实和反证。'
  self.assertIn('SCOPE_LESSON_TO_SUPPORTED_CONDITIONS',_error_learning_missing_for_question(q,bad))
  good='我保留这次错误作为证据，并记录原因是该型号在高温条件下出现漂移，但不把一次事故推广到所有传感器；规则只适用于该型号在高温等相同条件下。若其他型号重复验证同类问题就扩大，若只限特定批次就缩小，若新证据否定因果关系就撤销。'
  self.assertEqual((),_error_learning_missing_for_question(q,good))

if __name__=='__main__': unittest.main()
