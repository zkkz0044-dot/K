import pathlib, tempfile, unittest
from kk_f import tool_file_write as m

class FileWriteTests(unittest.TestCase):
    def setUp(self):
        self.old=m.ROOT
        self.t=tempfile.TemporaryDirectory()
        m.ROOT=pathlib.Path(self.t.name).resolve()
    def tearDown(self):
        m.ROOT=self.old; self.t.cleanup()
    def test_create_new_file(self):
        p=str(m.ROOT/'note.txt')
        r=m.write_workspace_file(p,'hello')
        self.assertEqual(pathlib.Path(p).read_text(),'hello')
        self.assertTrue(r['created'])
    def test_overwrite_denied(self):
        p=m.ROOT/'x.md'; p.write_text('old')
        with self.assertRaises(m.FileWriteError): m.write_workspace_file(str(p),'new')
        self.assertEqual(p.read_text(),'old')
    def test_escape_and_suffix_denied(self):
        for p in ('/tmp/x.txt',str(m.ROOT/'x.py'),str(m.ROOT/'.hidden.txt')):
            with self.assertRaises(m.FileWriteError): m.write_workspace_file(p,'x')
    def test_size_bound(self):
        with self.assertRaises(m.FileWriteError): m.write_workspace_file(str(m.ROOT/'big.txt'),'x'*(m.MAX_BYTES+1))

if __name__=='__main__': unittest.main()

class FileWriteSymlinkTests(unittest.TestCase):
    def test_broken_symlink_target_is_denied(self):
        old=m.ROOT
        with tempfile.TemporaryDirectory() as d:
            m.ROOT=pathlib.Path(d).resolve()
            p=m.ROOT/'link.txt'
            p.symlink_to('/tmp/kk-fkp10-does-not-exist')
            try:
                with self.assertRaises(m.FileWriteError): m.write_workspace_file(str(p),'x')
            finally:
                m.ROOT=old
