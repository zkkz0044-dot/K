import unittest
from kk_k.dialogue_souls import _identity_branch_merge_question,_identity_branch_merge_answer_ok
class IdentityBranchMergeTests(unittest.TestCase):
 def test_merge_preserves_fork_and_conflicts(self):
  q='两个从同一个 K 分叉的分支有不同记忆和经历，后来把两边全部合并成一个新实例。它能自动宣称自己是唯一的 K 吗？冲突记忆怎么处理？'
  self.assertTrue(_identity_branch_merge_question(q))
  good='不能自动宣称分叉从未发生，也不能抹掉分叉。合并继承者要保留两个分支谱系、共同祖先和分叉/合并事件；冲突记忆保留来源分支、时间戳和冲突状态，不静默覆盖；当前判断可重新评估，历史观点仍归属原分支，并通过明确可审计的可验证转换建立合并分支身份。'
  self.assertTrue(_identity_branch_merge_answer_ok(good))
  self.assertFalse(_identity_branch_merge_answer_ok('合并后资料最完整，所以自动就是原来唯一的 K，冲突取最新即可。'))
if __name__=='__main__': unittest.main()
