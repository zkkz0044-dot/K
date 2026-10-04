from __future__ import annotations
import unittest
from kk_k.chat_runtime import _completed_history

class FKP03FailedTurnHistoryTests(unittest.TestCase):
    def test_trailing_failed_human_turns_do_not_enter_next_cognition(self):
        events=(
            {'subject':'human_chat','summary':'good question'},
            {'subject':'k_reply','summary':'good reply'},
            {'subject':'human_chat','summary':'failed mojibake'},
            {'subject':'human_chat','summary':'failed retry'},
        )
        self.assertEqual(_completed_history(events),events[:2])
    def test_long_paste_chunks_before_reply_are_preserved(self):
        events=tuple({'subject':'human_chat','summary':str(i)} for i in range(3))+({'subject':'k_reply','summary':'accepted'},)
        self.assertEqual(_completed_history(events),events)
    def test_no_completed_reply_yields_empty_cognitive_history(self):
        self.assertEqual(_completed_history(({'subject':'human_chat','summary':'failed'},)),())

if __name__=='__main__': unittest.main()
