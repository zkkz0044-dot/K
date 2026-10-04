import os, socket, threading, unittest
from pathlib import Path
from uuid import uuid4

from kk_f import fk_audit_gateway
from kk_f.k_audit_witness import initialize_state
from kk_k.audit_witness import append_remote_event, query_conversation_history, query_conversation_recall, AuditWitnessError
from kk_k.test_support import project_tempdir

class FKP03HistoryTests(unittest.TestCase):
 def setUp(self):
  self.tmp=project_tempdir(); self.root=Path(self.tmp.name)
  self.state=Path('/root/K/F/evidence/fk')/('.test-fkp03-'+uuid4().hex+'.json')
  self.log=Path('/root/K/F/evidence/fk')/('.test-fkp03-'+uuid4().hex+'.jsonl')
  initialize_state(str(self.state))
 def tearDown(self):
  self.tmp.cleanup()
  for p in (self.state,self.log):
   try:p.unlink()
   except FileNotFoundError:pass
 def server_n(self,n):
  addr='\0fkp03-hist-'+uuid4().hex[:10]; ready=threading.Event(); errors=[]
  def run():
   s=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
   try:
    s.bind(addr); s.listen(8); ready.set()
    for _ in range(n):
     c,_=s.accept()
     with c: fk_audit_gateway.handle_connection(c,state_path=str(self.state),log_path=str(self.log),allowed_uid=os.getuid())
   except Exception as exc: errors.append(exc)
   finally:s.close()
  t=threading.Thread(target=run,daemon=True); t.start(); self.assertTrue(ready.wait(2)); return addr,t,errors
 def finish(self,t,e): t.join(2); self.assertFalse(t.is_alive()); self.assertEqual(e,[])
 def test_history_returns_only_conversation_subjects(self):
  addr,t,e=self.server_n(9)
  append_remote_event(event_id='u1',kind='USER_NOTE',subject='human_chat',summary='hello',address=addr)
  append_remote_event(event_id='d1',kind='SYSTEM',subject='dialogue_gate',summary='hidden audit',address=addr)
  append_remote_event(event_id='k1',kind='SYSTEM',subject='k_reply',summary='hi',address=addr)
  append_remote_event(event_id='s1',kind='SYSTEM',subject='soul_gate',summary='not conversation',address=addr)
  hist=query_conversation_history(limit=8,address=addr)
  self.finish(t,e)
  self.assertEqual([x['subject'] for x in hist],['human_chat','k_reply'])
 def test_failed_turns_are_not_returned_but_long_paste_chunks_survive(self):
  events=[
   {'subject':'human_chat','summary':'paste1'},
   {'subject':'human_chat','summary':'paste2'},
   {'subject':'human_chat','summary':'paste3'},
   {'subject':'k_reply','summary':'paste accepted'},
   {'subject':'human_chat','summary':'failed mojibake'},
   {'subject':'dialogue_error','summary':'LocalModelError'},
   {'subject':'human_chat','summary':'failed retry'},
   {'subject':'dialogue_error','summary':'LocalModelError'},
   {'subject':'human_chat','summary':'good retry'},
   {'subject':'k_reply','summary':'good answer'},
  ]
  got=fk_audit_gateway._completed_conversation_events(events)
  self.assertEqual([(e['subject'],e['summary']) for e in got],[
   ('human_chat','paste1'),('human_chat','paste2'),('human_chat','paste3'),('k_reply','paste accepted'),
   ('human_chat','good retry'),('k_reply','good answer')])

 def test_history_limit_validation_is_local(self):
  with self.assertRaises(AuditWitnessError): query_conversation_history(limit=0,address='\0none')
  with self.assertRaises(AuditWitnessError): query_conversation_history(limit=9,address='\0none')

 def test_recall_finds_older_relevant_completed_turn(self):
  addr,t,e=self.server_n(13)
  append_remote_event(event_id='u-old',kind='USER_NOTE',subject='human_chat',summary='Z640 内存连续性需要保留旧记录',address=addr)
  append_remote_event(event_id='k-old',kind='SYSTEM',subject='k_reply',summary='我会保留 Z640 这条历史并追加修正',address=addr)
  append_remote_event(event_id='u-new',kind='USER_NOTE',subject='human_chat',summary='今天只是聊晚饭',address=addr)
  append_remote_event(event_id='k-new',kind='SYSTEM',subject='k_reply',summary='好',address=addr)
  append_remote_event(event_id='u-new2',kind='USER_NOTE',subject='human_chat',summary='另一个无关问题',address=addr)
  append_remote_event(event_id='k-new2',kind='SYSTEM',subject='k_reply',summary='收到',address=addr)
  got=query_conversation_recall('Z640 内存怎么处理',limit=2,address=addr)
  self.finish(t,e)
  self.assertEqual([x['event_id'] for x in got],['u-old','k-old'])

 def test_recall_excludes_failed_turn(self):
  addr,t,e=self.server_n(9)
  append_remote_event(event_id='u-fail',kind='USER_NOTE',subject='human_chat',summary='火星计划 secretword',address=addr)
  append_remote_event(event_id='err',kind='SYSTEM',subject='dialogue_error',summary='LocalModelError',address=addr)
  append_remote_event(event_id='u-good',kind='USER_NOTE',subject='human_chat',summary='普通对话',address=addr)
  append_remote_event(event_id='k-good',kind='SYSTEM',subject='k_reply',summary='普通回复',address=addr)
  got=query_conversation_recall('火星计划 secretword',limit=2,address=addr)
  self.finish(t,e)
  self.assertEqual(got,())

 def test_recall_validation_is_local(self):
  with self.assertRaises(AuditWitnessError): query_conversation_recall('',address='\0none')
  with self.assertRaises(AuditWitnessError): query_conversation_recall('x'*513,address='\0none')
  with self.assertRaises(AuditWitnessError): query_conversation_recall('valid',limit=5,address='\0none')

if __name__=='__main__':unittest.main()
