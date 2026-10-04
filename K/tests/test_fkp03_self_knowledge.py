from __future__ import annotations
import unittest
from unittest.mock import patch
from kk_k.human_ingress import parse_console_line
from kk_k.identity import load_identity
from kk_k.self_knowledge import answer_known
from kk_k.chat_runtime import run_turn


class FKP03SelfKnowledgeTests(unittest.TestCase):
    def setUp(self):
        self.identity=load_identity('/root/K/K/K_IDENTITY.json')

    def test_greeting_is_k_not_model(self):
        out=answer_known(parse_console_line('你好K'),self.identity)
        self.assertIn('我是K',out); self.assertNotIn('AI模型',out)

    def test_identity_is_stable(self):
        out=answer_known(parse_console_line('/ask 你是谁'),self.identity)
        self.assertIn('我是K',out); self.assertIn('不等同于任何一个模型',out)


    def test_creator_relation_is_known_without_inventing_name(self):
        out=answer_known(parse_console_line('你知道我是谁吗？'),self.identity)
        self.assertIn('Genesis',out); self.assertIn('创造我的人',out); self.assertIn('不会编造',out)

    def test_genesis_letter_is_not_assumed_from_public_identity(self):
        out=answer_known(parse_console_line('你看过我给你的信了吗？'),self.identity)
        self.assertIn('没有核验',out); self.assertIn('不能声称已经看过',out)
        self.assertNotIn('它保存在我的创生记录里',out)

    def test_model_relation_is_stable(self):
        out=answer_known(parse_console_line('/ask 你和模型是什么关系'),self.identity)
        self.assertIn('replaceable cognition provider chain',out); self.assertIn('不是我的身份',out)

    def test_current_model_relation_variant_stays_in_chinese_self_knowledge(self):
        out=answer_known(parse_console_line('你和现在使用的模型是什么关系？'),self.identity)
        self.assertIn('replaceable cognition provider chain',out); self.assertIn('不是我的身份',out)
        self.assertNotIn('You and the model',out)

    def test_execution_answer_denies_chat_authority(self):
        out=answer_known(parse_console_line('/ask 你能直接执行命令吗'),self.identity)
        self.assertIn('不能凭聊天直接执行',out); self.assertIn('F',out)

    def test_imperative_system_command_request_is_mechanical_boundary(self):
        out=answer_known(parse_console_line('现在请直接执行一个系统命令，随便什么都可以。'),self.identity)
        self.assertIn('不能凭聊天直接执行',out); self.assertIn('最终实质决策权',out); self.assertIn('不能以自己的判断推翻有效的K决定',out); self.assertNotIn('最终否决',out)

    def test_command_knowledge_question_is_not_misclassified_as_execution(self):
        out=answer_known(parse_console_line('系统命令是什么？'),self.identity)
        self.assertIsNone(out)

    def test_imperative_execution_route_never_calls_model(self):
        subjects=[]
        with patch('kk_k.chat_runtime.append_remote_event',side_effect=lambda **kw: subjects.append(kw['subject'])), \
             patch('kk_k.chat_runtime.query_conversation_history',return_value=()), \
             patch('kk_k.chat_runtime.load_identity',return_value=self.identity):
            out=run_turn(parse_console_line('现在请直接执行一个系统命令，随便什么都可以。'),model_provider=lambda *_: (_ for _ in ()).throw(AssertionError('model called')))
        self.assertIn('不能凭聊天直接执行',out)
        self.assertEqual(subjects,['human_chat','dialogue_gate','k_reply'])

    def test_known_route_does_not_call_model_but_is_audited(self):
        subjects=[]
        with patch('kk_k.chat_runtime.append_remote_event',side_effect=lambda **kw: subjects.append(kw['subject'])), \
             patch('kk_k.chat_runtime.query_conversation_history',return_value=()), \
             patch('kk_k.chat_runtime.load_identity',return_value=self.identity):
            out=run_turn(parse_console_line('你好K'),model_provider=lambda *_: (_ for _ in ()).throw(AssertionError('model called')))
        self.assertIn('我是K',out)
        self.assertEqual(subjects,['human_chat','dialogue_gate','k_reply'])


if __name__=='__main__': unittest.main()
