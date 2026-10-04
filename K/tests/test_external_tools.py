import json
from pathlib import Path
import tempfile
import unittest
from kk_k.external_tools import ExternalToolError, external_catalog_status, execute_external_tool, load_external_catalog, REQUEST_SCHEMA, REQUEST_SCHEMA_V2

class ExternalToolCatalogTests(unittest.TestCase):
    def test_exact_three_enabled_capabilities(self):
        tools=external_catalog_status(); enabled={x['name'] for x in tools if x['enabled']}
        self.assertEqual(enabled,{'remote.vps.health','files.read','browser.search'})
        self.assertTrue(all(x['authority_route']=='FK_TOOL_GATEWAY_V1' for x in tools))
        by_name={x['name']:x for x in tools}
        self.assertFalse(by_name['files.write']['enabled'])
    def test_disabled_backlog_stays_disabled(self):
        tools={x['name']:x for x in external_catalog_status()}
        for name in ('remote.windows.health','gmail.search','github.read','database.query.readonly','notify.send'):
            self.assertFalse(tools[name]['enabled'])
    def test_enabled_unknown_contract_rejected(self):
        bad={'schema':'K.EXTERNAL.TOOL.CATALOG.2','tools':{'x':{'class':'remote','risk':'L0','enabled':True,'human_required':False,'authority_route':'FK_TOOL_GATEWAY_V1','verifier':'X','args_schema':None}}}
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'c.json'; p.write_text(json.dumps(bad))
            with self.assertRaises(ExternalToolError): load_external_catalog(p)
    def test_remote_health_v1_wraps_verified_receipt(self):
        r={'schema':'FK_TOOL.F_RECEIPT.1','tool':'remote.vps.health','outcome':'EXECUTED','evidence':{'kind':'HOST_HEALTH','health':{'schema':'F.TOOL.HOST_HEALTH.1','uptime_seconds':1,'cpu_count':1,'load':{},'memory':{},'disk_root':{}}}}
        out=execute_external_tool({'schema':REQUEST_SCHEMA,'tool':'remote.vps.health'},transport=lambda _:r)
        self.assertTrue(out['verified'])
    def test_files_requires_v2_and_exact_args(self):
        with self.assertRaises(ExternalToolError): execute_external_tool({'schema':REQUEST_SCHEMA,'tool':'files.read'},transport_args=lambda *_: {})
        with self.assertRaises(ExternalToolError): execute_external_tool({'schema':REQUEST_SCHEMA_V2,'tool':'files.read','args':{'path':'/root/K/README.md','extra':'x'}},transport_args=lambda *_:{})
    def test_files_v2_verifier(self):
        r={'schema':'FK_TOOL.F_RECEIPT.1','tool':'files.read','outcome':'EXECUTED','evidence':{'kind':'FILE_READ','file':{'schema':'F.TOOL.FILE_READ.1','path':'/root/K/README.md','content':'ok','truncated':False}}}
        out=execute_external_tool({'schema':REQUEST_SCHEMA_V2,'tool':'files.read','args':{'path':'/root/K/README.md'}},transport_args=lambda *_:r)
        self.assertTrue(out['verified'])
    def test_search_v2_verifier(self):
        r={'schema':'FK_TOOL.F_RECEIPT.1','tool':'browser.search','outcome':'EXECUTED','evidence':{'kind':'WEB_SEARCH','search':{'schema':'F.TOOL.WEB_SEARCH.1','query':'x','results':[{'title':'t','url':'https://example.com','snippet':'s'}]}}}
        out=execute_external_tool({'schema':REQUEST_SCHEMA_V2,'tool':'browser.search','args':{'query':'x'}},transport_args=lambda *_:r)
        self.assertTrue(out['verified'])
    def test_files_write_is_not_a_k_cognition_tool(self):
        with self.assertRaises(ExternalToolError):
            execute_external_tool({'schema':REQUEST_SCHEMA_V2,'tool':'files.write','args':{'path':'/root/K/K/workspace/x.txt','content':'x'}},transport_args=lambda *_:{})
    def test_v2_cannot_smuggle_command(self):
        with self.assertRaises(ExternalToolError): execute_external_tool({'schema':REQUEST_SCHEMA_V2,'tool':'browser.search','args':{'query':'x','command':'id'}},transport_args=lambda *_:{})

if __name__=='__main__': unittest.main()
