"""Real audit IPC and persistence; synthetic model, no provider/network access."""
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from uuid import uuid4
from kk_f.fk_audit_gateway import serve_forever
from kk_k.audit_witness import query_conversation_history, query_conversation_recall
from kk_k.beliefs import current_beliefs
from kk_k.skills import current_skills
from kk_k.chat_runtime import run_turn
from kk_k.human_ingress import parse_console_line


class OfflineChatIntegration(unittest.TestCase):
    def test_fresh_chat_and_restart_preserve_verified_history(self):
        calls=[]
        def provider(role,prompt):
            calls.append(role)
            if role=='K_CAPABILITY_PLAN':
                plan={'schema':'K.CAPABILITY.PLAN.1','need':'NONE','tool':None,'args':None,'reason':'offline test needs no external tool'}
                value={'schema':'K.CAPABILITY.PLAN.MODEL.1','plan_text':json.dumps(plan),'confidence':'LOW'}
            elif role=='SOUL_A_DIALOGUE':
                value={'schema':'FKP03.SOUL_A_DIALOGUE.1','draft':'离线合成模型回答：orbit-release-42 已进入测试对话。','confidence':'LOW'}
            elif role=='SOUL_B_DIALOGUE':
                value={'schema':'FKP03.SOUL_B_DIALOGUE.1','critique':'OK','risk_flags':['NONE'],'confidence':'LOW'}
            else:
                value={'schema':'FKP03.SOUL_C_DIALOGUE.1','answer':'APPROVE_A','confidence':'LOW','response_type':'ANSWER'}
            return json.dumps(value,ensure_ascii=False)
        with tempfile.TemporaryDirectory(dir='/root/K/F/evidence/fk') as td:
            state=str(Path(td)/'head.json'); log=str(Path(td)/'events.jsonl')
            address='\0lll-offline-'+uuid4().hex[:16]
            def start():
                stop=threading.Event(); ready=threading.Event(); errors=[]
                def serve():
                    try:
                        serve_forever(address=address,state_path=state,log_path=log,allowed_uid=os.getuid(),stop_event=stop,ready=ready.set)
                    except BaseException as exc: errors.append(exc)
                thread=threading.Thread(target=serve,daemon=True); thread.start()
                self.assertTrue(ready.wait(3),errors)
                return stop,thread,errors
            stop,thread,errors=start()
            try:
                greeting=run_turn(parse_console_line('你好K'),audit_address=address,model_provider=provider)
                self.assertIn('我是K',greeting); self.assertEqual(calls,[])
                answer=run_turn(parse_console_line('请讨论 orbit-release-42 这条离线标记'),audit_address=address,model_provider=provider)
                self.assertIn('orbit-release-42',answer)
                self.assertEqual(calls,['K_CAPABILITY_PLAN','SOUL_A_DIALOGUE','SOUL_B_DIALOGUE','SOUL_C_DIALOGUE'])
                self.assertEqual(current_beliefs('orbit-release-42',address=address),())
                self.assertEqual(current_skills('orbit-release-42',address=address),())
                history=query_conversation_history(address=address)
            finally:
                stop.set(); thread.join(3)
            self.assertFalse(thread.is_alive()); self.assertEqual(errors,[])
            stop,thread,errors=start()
            try:
                restored=query_conversation_history(address=address)
                self.assertEqual(restored,history)
                recalled=query_conversation_recall('orbit-release-42',address=address)
                self.assertTrue(any('orbit-release-42' in item['summary'] for item in recalled))
            finally:
                stop.set(); thread.join(3)
            self.assertFalse(thread.is_alive()); self.assertEqual(errors,[])
