import unittest
from kk_k.file_write_verifier import FileWriteVerifyError, verify_file_write_receipt

class FileWriteVerifierTests(unittest.TestCase):
    def good(self):
        return {'outcome':'EXECUTED','evidence':{'kind':'FILE_WRITE','file':{'schema':'F.TOOL.FILE_WRITE.1','path':'/root/K/K/workspace/a.txt','bytes':1,'sha256':'0'*64,'created':True}}}
    def test_good(self): self.assertTrue(verify_file_write_receipt(self.good()))
    def test_veto(self): self.assertFalse(verify_file_write_receipt({'outcome':'VETO'}))
    def test_extra_or_bad_path_fails(self):
        r=self.good(); r['evidence']['file']['extra']=1
        with self.assertRaises(FileWriteVerifyError): verify_file_write_receipt(r)
        r=self.good(); r['evidence']['file']['path']='/root/K/F/x.txt'
        with self.assertRaises(FileWriteVerifyError): verify_file_write_receipt(r)
if __name__=='__main__': unittest.main()
