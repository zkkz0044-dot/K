import json
import os
import unittest
from pathlib import Path
from uuid import uuid4

from kk_f import fk_audit_gateway
from kk_f.k_audit_witness import KAuditWitnessError, SCHEMA, initialize_state, load_state
from kk_f.monotonic_witness import CHANNELS, empty_state


class FKAuditWitnessMigrationTests(unittest.TestCase):
    def test_fh03_exact_four_channels_are_unchanged(self):
        self.assertEqual(CHANNELS, frozenset({'restart_ledger','evidence','release_state','safety_state'}))
        self.assertEqual(set(empty_state()['channels']), set(CHANNELS))

    def test_k_audit_extension_is_v2_and_separate(self):
        self.assertEqual(SCHEMA,'FK_AUDIT.WITNESS.2')
        self.assertNotIn('k_audit',CHANNELS)

    def test_old_v1_audit_state_is_rejected_not_silently_migrated(self):
        p=Path('/root/K/F/evidence/fk')/('.old-v1-'+uuid4().hex+'.json')
        p.write_text(json.dumps({
            'schema':'FK_AUDIT.WITNESS.1','generation':0,'digest':'0'*64,'checksum':'0'*64,
        }),encoding='utf-8'); p.chmod(0o600)
        try:
            with self.assertRaises(KAuditWitnessError): load_state(str(p))
        finally:
            p.unlink(missing_ok=True)

    def test_old_v1_wire_schema_is_rejected(self):
        with self.assertRaises(fk_audit_gateway.FKAuditGatewayError):
            fk_audit_gateway.parse_request(b'{"schema":"FK_AUDIT.QUERY.1"}')

    def test_new_state_is_root_owned_nonwritable(self):
        p=Path('/root/K/F/evidence/fk')/('.v2-'+uuid4().hex+'.json')
        try:
            initialize_state(str(p)); st=p.stat()
            self.assertEqual(st.st_uid,0); self.assertEqual(st.st_mode & 0o022,0)
        finally:
            p.unlink(missing_ok=True)


if __name__=='__main__': unittest.main()
