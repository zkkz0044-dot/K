import unittest
from kk_k.external_tools import ExternalToolError, _validate_args, load_external_catalog

class FileWriteContractTests(unittest.TestCase):
    def test_file_write_is_not_an_active_argument_contract(self):
        with self.assertRaisesRegex(ExternalToolError,'unknown args schema'):
            _validate_args('FILES_WRITE_1',{'path':'/root/K/K/workspace/note.txt','content':'hello'})

    def test_catalog_keeps_file_write_disabled_without_contract(self):
        catalog=load_external_catalog()
        if 'files.write' in catalog:
            spec=catalog['files.write']
            self.assertFalse(spec.enabled)
            self.assertIsNone(spec.verifier)
            self.assertIsNone(spec.args_schema)

    def test_write_like_extra_fields_cannot_fit_read_contract(self):
        with self.assertRaises(ExternalToolError):
            _validate_args('FILES_READ_1',{'path':'/root/K/K/workspace/x.txt','content':'x'})

if __name__=='__main__': unittest.main()
