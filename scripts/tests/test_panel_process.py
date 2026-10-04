"""Exercise process lifecycle using a real child with synthetic model output."""
from pathlib import Path
import subprocess
import sys
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'PANEL-v0.1'))
import panel_server as panel


class PanelProcessTests(unittest.TestCase):
    def test_stderr_flood_does_not_block_chat_and_lock_is_released(self):
        original_popen=subprocess.Popen
        code="import sys,json; sys.stdin.read(); sys.stderr.write('x'*200000); sys.stderr.flush(); print(json.dumps({'type':'result','status':'PASS','answer':'synthetic'}),flush=True)"
        def launch(*args,**kwargs):
            return original_popen([sys.executable,'-u','-c',code],**kwargs)
        run_id='process-regression'
        panel.RUNS[run_id]={'status':'RUNNING','created':0,'events':[],'next_seq':0}
        self.assertTrue(panel.CHAT_LOCK.acquire(blocking=False))
        try:
            with patch.object(panel.subprocess,'run',return_value=subprocess.CompletedProcess([],1)),patch.object(panel.subprocess,'Popen',side_effect=launch):
                thread=threading.Thread(target=panel._run_chat_job,args=(run_id,'test',[],None),daemon=True)
                thread.start(); thread.join(5)
                self.assertFalse(thread.is_alive(),'child blocked on stderr')
            self.assertEqual(panel.RUNS[run_id]['status'],'COMPLETE')
            self.assertEqual(panel.RUNS[run_id]['answer'],'synthetic')
            self.assertFalse(panel.CHAT_LOCK.locked())
        finally:
            panel.RUNS.pop(run_id,None)
            if panel.CHAT_LOCK.locked(): panel.CHAT_LOCK.release()

    def test_launch_failure_records_error_and_releases_lock(self):
        run_id='failure-regression'
        panel.RUNS[run_id]={'status':'RUNNING','created':0,'events':[],'next_seq':0}
        self.assertTrue(panel.CHAT_LOCK.acquire(blocking=False))
        try:
            with patch.object(panel.subprocess,'run',return_value=subprocess.CompletedProcess([],1)),patch.object(panel.subprocess,'Popen',side_effect=OSError('synthetic failure')):
                panel._run_chat_job(run_id,'test',[],None)
            self.assertEqual(panel.RUNS[run_id]['status'],'FAIL')
            self.assertEqual(panel.RUNS[run_id]['error'],'OSError')
            self.assertFalse(panel.CHAT_LOCK.locked())
        finally:
            panel.RUNS.pop(run_id,None)
            if panel.CHAT_LOCK.locked(): panel.CHAT_LOCK.release()
