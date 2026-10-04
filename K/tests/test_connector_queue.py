from __future__ import annotations
import json, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
from kk_k.connector_queue import ConnectorQueueError, enqueue, read_pending, write_result, consume

GREQ={'schema':'K.CONNECTOR.REQUEST.1','tool':'github.read','args':{'repository':'example-org/example-repo'}}
GREC={'schema':'K.CONNECTOR.RECEIPT.1','tool':'github.read','status':'PASS','data':{'repository':'example-org/example-repo','visibility':'private','default_branch':'main','archived':False,'size':5088}}

class ConnectorQueueTests(unittest.TestCase):
    def test_roundtrip_archives_once(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); req=root/'requests'; res=root/'results'; arc=root/'archive'
            req.mkdir(); res.mkdir(); arc.mkdir()
            with patch('kk_k.connector_queue.REQUESTS',req),patch('kk_k.connector_queue.RESULTS',res),patch('kk_k.connector_queue.ARCHIVE',arc):
                rid='1'*32; enqueue(GREQ,now=10,request_id=rid)
                self.assertEqual(read_pending(rid)['request']['tool'],'github.read')
                write_result(rid,GREC,now=11)
                out=consume(rid); self.assertTrue(out['verified'])
                self.assertFalse((req/(rid+'.json')).exists()); self.assertFalse((res/(rid+'.json')).exists())
                self.assertTrue((arc/(rid+'.request.json')).exists()); self.assertTrue((arc/(rid+'.result.json')).exists())
    def test_bad_receipt_is_rejected_and_request_survives(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); req=root/'requests'; res=root/'results'; arc=root/'archive'
            req.mkdir(); res.mkdir(); arc.mkdir()
            with patch('kk_k.connector_queue.REQUESTS',req),patch('kk_k.connector_queue.RESULTS',res),patch('kk_k.connector_queue.ARCHIVE',arc):
                rid='2'*32; enqueue(GREQ,now=10,request_id=rid)
                bad={'schema':'K.CONNECTOR.RECEIPT.1','tool':'github.read','status':'PASS','data':{'repository':'x/y'}}
                with self.assertRaises(Exception): write_result(rid,bad,now=11)
                self.assertTrue((req/(rid+'.json')).exists())

    def test_collision_and_invalid_id_fail_closed(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); req=root/'requests'; res=root/'results'; arc=root/'archive'
            req.mkdir(); res.mkdir(); arc.mkdir()
            with patch('kk_k.connector_queue.REQUESTS',req),patch('kk_k.connector_queue.RESULTS',res),patch('kk_k.connector_queue.ARCHIVE',arc):
                rid='3'*32; enqueue(GREQ,now=10,request_id=rid)
                with self.assertRaises(ConnectorQueueError): enqueue(GREQ,now=10,request_id=rid)
                with self.assertRaises(ConnectorQueueError): read_pending('bad')

if __name__=='__main__': unittest.main()
