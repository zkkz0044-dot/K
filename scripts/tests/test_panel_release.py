import http.client
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'PANEL-v0.1'))
import panel_server as panel
import mobile_gateway as mobile


class PanelReleaseTests(unittest.TestCase):
    def setUp(self):
        self.server=panel.LocalHTTPServer(('127.0.0.1',0),panel.Handler)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()
    def tearDown(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join(2)
    def request(self,method,path,body=None,headers=None):
        conn=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=3)
        try:
            conn.request(method,path,body,headers or {})
            result=conn.getresponse()
            return result.status,result.read()
        finally:
            conn.close()
    def test_cross_origin_cannot_start_chat(self):
        with patch.object(panel,'start_chat_run') as start:
            status,_=self.request('POST','/api/chat/start','{"text":"hello"}',{'Content-Type':'application/json','Origin':'https://unrelated.example'})
        self.assertEqual(status,403); start.assert_not_called()
    def test_rebinding_host_cannot_read_status(self):
        with patch.object(panel,'snapshot') as snapshot:
            status,_=self.request('GET','/api/status',headers={'Host':'unrelated.example'})
        self.assertEqual(status,403); snapshot.assert_not_called()
    def test_local_status_works(self):
        with patch.object(panel,'snapshot',return_value={'schema':'TEST','ok':True}):
            status,data=self.request('GET','/api/status')
        self.assertEqual(status,200); self.assertTrue(json.loads(data)['ok'])
    def test_local_chat_validates_before_start(self):
        with patch.object(panel,'start_chat_run',return_value='test-run') as start:
            status,data=self.request('POST','/api/chat/start','{"text":"hello"}',{'Content-Type':'application/json'})
        self.assertEqual(status,202); self.assertEqual(json.loads(data)['run_id'],'test-run'); start.assert_called_once()
    def test_oversize_body_rejected_before_reading(self):
        status,_=self.request('POST','/api/chat/start',b'',{'Content-Type':'application/json','Content-Length':str(panel.MAX_BODY+1)})
        self.assertEqual(status,413)
    def test_huge_log_has_bounded_tail(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'events.jsonl'
            path.write_bytes(b'x'*(panel.MAX_AUDIT_TAIL*2)+b'\n'+json.dumps({'sequence':7,'summary':'last'}).encode()+b'\n')
            with patch.object(panel,'AUDIT_LOG',path):
                events=panel.recent_events()
        self.assertEqual([item['sequence'] for item in events],[7])
    def test_state_file_size_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'state.json'; path.write_bytes(b' '*(panel.MAX_FILE+1))
            with self.assertRaises(ValueError): panel.read_json(path)
    def test_request_concurrency_is_bounded(self):
        self.server.request_slots.acquire(); self.server.request_slots.acquire()
        try:
            try:
                status,_=self.request('GET','/api/status')
                self.assertEqual(status,503)
            except (ConnectionError,http.client.RemoteDisconnected):
                # Platforms may reset a refused connection with unread data.
                pass
            self.assertFalse(self.server.request_slots.acquire(blocking=False))
        finally:
            self.server.request_slots.release(); self.server.request_slots.release()
    def test_media_and_device_input_rejected(self):
        with self.assertRaises(ValueError): panel._validate_media_http([{'kind':'file','name':'../x','data_b64':'x'*(42_500_001)}])
        with self.assertRaises(ValueError): panel._validate_device_http({'schema':'K.DEVICE.SNAPSHOT.1','captured_at_ms':True})
    def test_mobile_gateway_inherits_local_boundary(self):
        self.assertTrue(issubclass(mobile.Handler,panel.Handler))


if __name__=='__main__': unittest.main()
