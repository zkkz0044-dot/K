import json
import os
from pathlib import Path
import unittest

from kk_k.authority_guard import AuthorityGuardError, read_root_authority
from kk_k.constitution import ConstitutionError, load_constitution
from kk_k.governance import GovernanceError, load_policy
from kk_k.test_support import project_tempdir


class KAuthorityGuardTests(unittest.TestCase):
    def test_real_constitution_and_policy_are_accepted(self):
        self.assertEqual(load_constitution('/root/K/K/K00_CONSTITUTION.json')['schema'],'K00.CONSTITUTION.1')
        self.assertEqual(load_policy('/root/K/K/K06_POLICY.json')['schema'],'K06.POLICY.1')
        raw=read_root_authority('/root/K/K/K_ISOLATION_POLICY.json',max_bytes=8192)
        self.assertEqual(json.loads(raw)['schema'],'K.ISOLATION.1')

    def test_group_world_writable_constitution_rejected(self):
        with project_tempdir() as td:
            p=Path(td)/'c.json'; p.write_text(Path('/root/K/K/K00_CONSTITUTION.json').read_text(),encoding='utf-8'); p.chmod(0o666)
            with self.assertRaises(ConstitutionError): load_constitution(str(p))

    def test_nonroot_owned_constitution_rejected(self):
        with project_tempdir() as td:
            p=Path(td)/'c.json'; p.write_text(Path('/root/K/K/K00_CONSTITUTION.json').read_text(),encoding='utf-8'); p.chmod(0o600)
            os.chown(p,65534,65534)
            with self.assertRaises(ConstitutionError): load_constitution(str(p))

    def test_leaf_symlink_rejected(self):
        with project_tempdir() as td:
            root=Path(td); real=root/'real.json'; link=root/'link.json'
            real.write_text(Path('/root/K/K/K00_CONSTITUTION.json').read_text(),encoding='utf-8'); real.chmod(0o600); link.symlink_to(real)
            with self.assertRaises(ConstitutionError): load_constitution(str(link))

    def test_parent_symlink_rejected(self):
        with project_tempdir() as td:
            root=Path(td); realdir=root/'real'; realdir.mkdir(); p=realdir/'c.json'
            p.write_text(Path('/root/K/K/K00_CONSTITUTION.json').read_text(),encoding='utf-8'); p.chmod(0o600)
            linkdir=root/'linked'; linkdir.symlink_to(realdir,target_is_directory=True)
            with self.assertRaises(ConstitutionError): load_constitution(str(linkdir/'c.json'))

    def test_policy_world_writable_rejected(self):
        with project_tempdir() as td:
            p=Path(td)/'p.json'; p.write_text(Path('/root/K/K/K06_POLICY.json').read_text(),encoding='utf-8'); p.chmod(0o666)
            with self.assertRaises(GovernanceError): load_policy(str(p))

    def test_outside_k_root_rejected_before_parse(self):
        with self.assertRaises(AuthorityGuardError): read_root_authority('/root/K/F/PROJECT_STATE.json',max_bytes=8192)

    def test_directory_cannot_be_authority_file(self):
        with project_tempdir() as td:
            with self.assertRaises(AuthorityGuardError): read_root_authority(td,max_bytes=8192)


if __name__=='__main__': unittest.main()
