import json, os, sys, unittest
for path in ("/root/K/F/src","/root/K/K/src"):
    if path not in sys.path: sys.path.insert(0,path)
from kk_f.fk_tool_gateway import REQUEST_SCHEMA_V2, dispatch, parse_request
from kk_f.tool_file_write import FileWriteError, MAX_BYTES, ROOT, _target

class FKP10DormantWriteContractTests(unittest.TestCase):
    def test_files_write_is_not_in_active_gateway_surface(self):
        raw=json.dumps({"schema":REQUEST_SCHEMA_V2,"tool":"files.write","args":{"path":"/root/K/K/workspace/x.txt","content":"x"}}).encode()
        with self.assertRaises(Exception):
            parse_request(raw)
        receipt=dispatch("files.write",peer_uid=os.getuid(),allowed_uid=os.getuid(),args={"path":"/root/K/K/workspace/x.txt","content":"x"})
        self.assertEqual(receipt["outcome"],"VETO")
        self.assertEqual(receipt["evidence"]["reason_code"],"TOOL_DISABLED")

    def test_dormant_implementation_remains_bounded(self):
        self.assertEqual(MAX_BYTES,16384)
        self.assertEqual(str(ROOT),"/root/K/K/workspace")
        with self.assertRaises(FileWriteError):
            _target("/root/K/F/x.txt")
        with self.assertRaises(FileWriteError):
            _target("/root/K/K/workspace/.hidden.txt")
        with self.assertRaises(FileWriteError):
            _target("/root/K/K/workspace/sub/x.txt")

if __name__=="__main__": unittest.main()
