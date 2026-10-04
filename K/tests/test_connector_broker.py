import unittest
from kk_k.connector_broker import (
    ConnectorBrokerError, REQ_SCHEMA, RECEIPT_SCHEMA,
    parse_request, verify_receipt,
)

class ConnectorBrokerTests(unittest.TestCase):
    def test_github_request_exact(self):
        r=parse_request({'schema':REQ_SCHEMA,'tool':'github.read','args':{'repository':'example-org/example-repo'}})
        self.assertEqual(r.tool,'github.read')
        with self.assertRaises(ConnectorBrokerError):
            parse_request({'schema':REQ_SCHEMA,'tool':'github.read','args':{'repository':'a/b','token':'x'}})

    def test_gmail_request_exact(self):
        r=parse_request({'schema':REQ_SCHEMA,'tool':'gmail.search','args':{'query':'newer_than:7d','limit':3}})
        self.assertEqual(r.args['limit'],3)
        with self.assertRaises(ConnectorBrokerError):
            parse_request({'schema':REQ_SCHEMA,'tool':'gmail.search','args':{'query':'x','limit':99}})

    def test_github_receipt_minimal(self):
        out=verify_receipt('github.read',{
            'schema':RECEIPT_SCHEMA,'tool':'github.read','status':'PASS',
            'data':{'repository':'example-org/example-repo','visibility':'private','default_branch':'main','archived':False,'size':5088}})
        self.assertEqual(out['default_branch'],'main')
    def test_gmail_receipt_has_no_addresses_or_body(self):
        out=verify_receipt('gmail.search',{
            'schema':RECEIPT_SCHEMA,'tool':'gmail.search','status':'PASS','data':[
                {'id':'1','subject':'S','snippet':'N','timestamp':'2026-09-06T00:00:00Z','has_attachment':False}
            ]})
        self.assertEqual(len(out),1)
        with self.assertRaises(ConnectorBrokerError):
            verify_receipt('gmail.search',{
                'schema':RECEIPT_SCHEMA,'tool':'gmail.search','status':'PASS','data':[
                    {'id':'1','subject':'S','snippet':'N','timestamp':'T','has_attachment':False,'from':'a@example.com'}
                ]})

    def test_unknown_connector_fails_closed(self):
        with self.assertRaises(ConnectorBrokerError):
            parse_request({'schema':REQ_SCHEMA,'tool':'gmail.send','args':{}})

if __name__=='__main__':
    unittest.main()
