from __future__ import annotations
import os, sys, unittest
from pathlib import Path
for p in ('/root/K/F/src','/root/K/K/src'):
    if p not in sys.path: sys.path.insert(0,p)
from kk_f.fk_gateway import ENABLED_ACTIONS, REQUEST_KEYS
from kk_f.monotonic_witness import CHANNELS
from kk_k.action_registry import ALLOWED_ACTIONS
from kk_k.fk_runtime import F_HUMAN_GATED_ACTIONS

class FKP05FinalMergeContractTests(unittest.TestCase):
    def setUp(self):
        self.deploy=Path('/root/K/FK/deploy')

    def test_exact_five_action_surface(self):
        expected={'A01_READ_PROJECT_STATE','A02_READ_F_STATUS','A03_RUN_F_SMOKE_TEST','A04_WRITE_K_DECISION_LOG','A05_NO_ACTION'}
        self.assertEqual(set(ALLOWED_ACTIONS),expected)
        self.assertEqual(set(ENABLED_ACTIONS),expected)
        self.assertEqual(set(F_HUMAN_GATED_ACTIONS),{'A03_RUN_F_SMOKE_TEST'})

    def test_request_has_no_privileged_payload(self):
        self.assertEqual(REQUEST_KEYS,frozenset({'schema','action_id'}))

    def test_original_f_witness_is_still_exact_four(self):
        self.assertEqual(CHANNELS,frozenset({'restart_ledger','evidence','release_state','safety_state'}))

    def test_persistent_unit_sources_are_root_owned_and_not_writable_by_others(self):
        for name in ('kk-fk-gateway.service','kk-fk-audit-witness.service','kk-k-model-gateway.service'):
            p=self.deploy/name; st=p.stat()
            self.assertEqual(st.st_uid,0); self.assertEqual(st.st_gid,0)
            self.assertEqual(st.st_mode & 0o022,0)

    def test_gateway_and_audit_units_are_local_af_unix_only(self):
        for name in ('kk-fk-gateway.service','kk-fk-audit-witness.service'):
            text=(self.deploy/name).read_text()
            self.assertIn('Restart=always',text)
            self.assertIn('RestrictAddressFamilies=AF_UNIX',text)
            self.assertIn('IPAddressDeny=any',text)
            self.assertIn('WantedBy=multi-user.target',text)
            self.assertNotIn('/var/www',text)
            self.assertNotIn('legacy-web-root',text.lower())
            self.assertNotIn('xianyu',text.lower())

    def test_model_unit_is_replaceable_nonroot_private_network(self):
        text=(self.deploy/'kk-k-model-gateway.service').read_text()
        for token in ('DynamicUser=yes','PrivateNetwork=yes','RestrictAddressFamilies=AF_UNIX','IPAddressDeny=any','WantedBy=multi-user.target'):
            self.assertIn(token,text)
        self.assertNotIn('User=root',text)

    def test_old_roots_absent(self):
        self.assertFalse(Path('/root/kk-f').exists())
        self.assertFalse(Path('/root/kk-k').exists())

if __name__=='__main__': unittest.main()
