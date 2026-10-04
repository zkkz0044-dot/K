import hashlib
import json
import os
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from kk_f.frozen_authority import build_frozen_authority, FrozenAuthorityError, authorize_process, load_frozen_authority


class F18FrozenAuthorityTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=pathlib.Path(self.tmp.name)
        self.cwd=self.root/'work';self.cwd.mkdir();self.exe=self.root/'worker.py';self.exe.write_text('#!/usr/bin/python3\n');self.exe.chmod(0o700)
        self.digest=hashlib.sha256(self.exe.read_bytes()).hexdigest();self.auth=self.root/'authority.json'
        self.manifest=build_frozen_authority('kk-f-root',self.spec(),3)
        self.write_manifest()
    def tearDown(self):self.tmp.cleanup()
    def write_manifest(self,value=None):
        self.auth.write_text(json.dumps(self.manifest if value is None else value,separators=(',',':'))+'\n');self.auth.chmod(0o600)
    def spec(self,**updates):
        value={'version':'0.1','executable':str(self.exe),'argv':[],'cwd':str(self.cwd),'env':{},'sha256':self.digest};value.update(updates);return value

    def test_valid_root_owned_manifest_authorizes_exact_candidate(self):
        r=authorize_process(str(self.auth),self.spec());self.assertEqual(r['authority_id'],'kk-f-root');self.assertEqual(r['max_restart_attempts'],3)
    def test_different_executable_denied(self):
        other=self.root/'other';other.write_text('x');other.chmod(0o700)
        with self.assertRaises(FrozenAuthorityError):authorize_process(str(self.auth),self.spec(executable=str(other)))
    def test_different_digest_denied(self):
        with self.assertRaises(FrozenAuthorityError):authorize_process(str(self.auth),self.spec(sha256='f'*64))
    def test_different_argv_denied(self):
        with self.assertRaises(FrozenAuthorityError): authorize_process(str(self.auth),self.spec(argv=["--other"]))
    def test_different_cwd_denied(self):
        other=self.root/'other-cwd';other.mkdir()
        with self.assertRaises(FrozenAuthorityError): authorize_process(str(self.auth),self.spec(cwd=str(other)))
    def test_different_env_denied(self):
        with self.assertRaises(FrozenAuthorityError): authorize_process(str(self.auth),self.spec(env={"MODE":"other"}))
    def test_group_writable_manifest_denied(self):
        self.auth.chmod(0o620)
        with self.assertRaises(FrozenAuthorityError):load_frozen_authority(str(self.auth))
    def test_world_writable_manifest_denied(self):
        self.auth.chmod(0o602)
        with self.assertRaises(FrozenAuthorityError):load_frozen_authority(str(self.auth))
    def test_symlink_manifest_denied(self):
        link=self.root/'authority-link.json';link.symlink_to(self.auth)
        with self.assertRaises(FrozenAuthorityError):load_frozen_authority(str(link))
    def test_non_root_owned_manifest_denied(self):
        os.chown(self.auth,65534,-1)
        with self.assertRaises(FrozenAuthorityError):load_frozen_authority(str(self.auth))
        os.chown(self.auth,0,-1)
    def test_unknown_field_denied(self):
        bad=dict(self.manifest,extra=True);self.write_manifest(bad)
        with self.assertRaises(FrozenAuthorityError):load_frozen_authority(str(self.auth))
    def test_duplicate_key_denied(self):
        raw=json.dumps(self.manifest,separators=(',',':')).replace('{"version":"0.2"','{"version":"0.2","version":"0.2"',1)+'\n';self.auth.write_text(raw);self.auth.chmod(0o600)
        with self.assertRaises(FrozenAuthorityError):load_frozen_authority(str(self.auth))
    def test_bool_restart_budget_denied(self):
        bad=dict(self.manifest,max_restart_attempts=True);self.write_manifest(bad)
        with self.assertRaises(FrozenAuthorityError):load_frozen_authority(str(self.auth))
    def test_relative_authority_path_denied(self):
        with self.assertRaises(FrozenAuthorityError):load_frozen_authority('authority.json')
    def test_invalid_process_spec_denied(self):
        bad=self.spec();bad['shell']=True
        with self.assertRaises(FrozenAuthorityError):authorize_process(str(self.auth),bad)


if __name__=='__main__':unittest.main()
