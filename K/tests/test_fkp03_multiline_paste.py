from __future__ import annotations
import unittest
from unittest.mock import patch

from kk_k.chat_runtime import run_turn
from kk_k.human_ingress import HumanIngressError, MAX_TEXT_BYTES, MAX_PASTE_BYTES, parse_console_line, parse_paste_text
from kk_k.identity import load_identity
from kk_k.self_knowledge import answer_known


class FKP03MultilinePasteTests(unittest.TestCase):
    def test_normal_line_limit_matches_current_contract(self):
        self.assertEqual(len(parse_console_line('x'*MAX_TEXT_BYTES).text),MAX_TEXT_BYTES)
        with self.assertRaises(HumanIngressError):
            parse_console_line('x'*(MAX_TEXT_BYTES+1))

    def test_multiline_paste_accepts_bounded_long_text(self):
        text='第一段\n\n' + ('这是给K的一封长信。\n'*180)
        msg=parse_paste_text(text)
        self.assertEqual(msg.mode,'CHAT')
        self.assertIn('\n\n',msg.text)
        self.assertGreater(len(msg.text.encode('utf-8')),1536)

    def test_long_paste_is_chunk_audited_and_does_not_call_model(self):
        text='K：\n\n'+('中'*11000)
        self.assertGreater(len(text.encode('utf-8')),MAX_TEXT_BYTES)
        self.assertLessEqual(len(text.encode('utf-8')),MAX_PASTE_BYTES)
        msg=parse_paste_text(text); events=[]
        identity=load_identity('/root/K/K/K_IDENTITY.json')
        with patch('kk_k.chat_runtime.query_conversation_history',return_value=()), \
             patch('kk_k.chat_runtime.append_remote_event',side_effect=lambda **kw: events.append(kw)), \
             patch('kk_k.chat_runtime.load_identity',return_value=identity):
            out=run_turn(msg,model_provider=lambda *_: (_ for _ in ()).throw(AssertionError('model called')))
        human=[e for e in events if e['subject']=='human_chat']
        self.assertGreater(len(human),1)
        self.assertEqual(''.join(e['summary'] for e in human),msg.text)
        self.assertIn('完整接收并记录',out)

    def test_long_prose_never_triggers_keyword_self_knowledge(self):
        text=('这是一封信，里面会谈到模型、执行、F和K，但它不是一个问题。'*20)
        msg=parse_paste_text(text)
        out=answer_known(msg,load_identity('/root/K/K/K_IDENTITY.json'))
        self.assertIsNone(out)


if __name__=='__main__': unittest.main()
