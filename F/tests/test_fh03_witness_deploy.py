from __future__ import annotations
import hashlib, json, pathlib, tempfile, unittest
from unittest import mock

from kk_f.checkpoint import checkpoint_checksum, write_checkpoint
from kk_f.evidence import append, initialize as init_evidence, verify as verify_evidence
from kk_f.frozen_authority import build_frozen_authority
from kk_f.monotonic_witness import load_state
from kk_f.restart_ledger import initialize as init_ledger, evaluate_and_record
from kk_f.witness_provision import WitnessProvisionError, provision

ROOT = pathlib.Path(__file__).resolve().parents[1]

class FH03WitnessDeployTests(unittest.TestCase):
    def _fixture(self, td, existing=False):
        root=pathlib.Path(td); exe=root/'worker.py'; exe.write_text('#!/usr/bin/python3\n'); exe.chmod(0o700)
        spec={'version':'0.1','executable':str(exe),'argv':[str(exe)],'cwd':str(root),'env':{},'sha256':hashlib.sha256(exe.read_bytes()).hexdigest()}
        authority=root/'authority.json'; authority.write_text(json.dumps(build_frozen_authority('fh03-deploy',spec,2),sort_keys=True,separators=(',',':'))+'\n'); authority.chmod(0o600)
        ledger=root/'ledger'; evidence=root/'evidence'; runtime=root/'runtime.json'
        runtime.write_text(json.dumps({'version':'0.1','authority_path':str(authority),'ledger_directory':str(ledger),'evidence_directory':str(evidence),'heartbeat_path':str(root/'heartbeat.json'),'process_spec':spec,'healthy_within_seconds':1,'degraded_within_seconds':2,'grace_seconds':1,'base_delay_seconds':1,'max_delay_seconds':2,'poll_interval_seconds':1,'heartbeat_startup_grace_seconds':1})+'\n'); runtime.chmod(0o600)
        if existing:
            init_ledger(str(ledger),2); evaluate_and_record(str(ledger),'FAILED',attempted_at='2026-09-04T01:46:00Z')
            init_evidence(evidence)
            record={'protocol_version':'0.1','message_id':'123e4567-e89b-42d3-a456-426614174000','kind':'result','source_role':'worker','target_role':'supervisor','timestamp':'2026-09-04T01:45:00Z','status':'HEALTHY','payload':{'case':'deploy'},'error':None}
            append(evidence,record)
        return authority,runtime,ledger,evidence,root/'witness'/'witness.json'
    def test_fresh_provision_seeds_exact_genesis_bindings(self):
        with tempfile.TemporaryDirectory() as td:
            a,r,_,_,w=self._fixture(td)
            with mock.patch('kk_f.witness_provision.os.geteuid', return_value=0): provision(str(a),str(r),str(w))
            s=load_state(w); self.assertEqual(s['channels']['restart_ledger']['generation'],0); self.assertEqual(s['channels']['evidence']['digest'],'0'*64)
    def test_existing_durable_state_is_anchored_not_reset(self):
        with tempfile.TemporaryDirectory() as td:
            a,r,ledger,evidence,w=self._fixture(td,True)
            with mock.patch('kk_f.witness_provision.os.geteuid', return_value=0): provision(str(a),str(r),str(w))
            s=load_state(w); self.assertEqual(s['channels']['restart_ledger']['generation'],1); self.assertEqual(s['channels']['evidence']['generation'],1)
            self.assertEqual(s['channels']['evidence']['digest'],verify_evidence(evidence)['last_hash'])
    def test_existing_witness_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as td:
            a,r,_,_,w=self._fixture(td); w.parent.mkdir(); w.write_text('x')
            with mock.patch('kk_f.witness_provision.os.geteuid', return_value=0), self.assertRaises(WitnessProvisionError): provision(str(a),str(r),str(w))
    def test_nonroot_refused(self):
        with tempfile.TemporaryDirectory() as td:
            a,r,_,_,w=self._fixture(td)
            with mock.patch('kk_f.witness_provision.os.geteuid', return_value=1000), self.assertRaises(WitnessProvisionError): provision(str(a),str(r),str(w))
    def test_units_bind_runtime_to_witness(self):
        unit=(ROOT/'deploy/kk-f.service').read_text(); install=(ROOT/'deploy/install_layout.sh').read_text()
        self.assertIn('Requires=kk-f-witness.service',unit); self.assertIn('KK_F_WITNESS_SOCKET=/run/kk-f-witness/witness.sock',unit)
        witness=(ROOT/'deploy/kk-f-witness.service').read_text()
        self.assertIn('deploy/kk-f-witness.service',install); self.assertIn('kk_f.witness_provision',install)
        self.assertIn('--allowed-cgroup /system.slice/kk-f.service',witness)
        self.assertIn('if [ ! -e /var/lib/kk-f-witness/witness.json ]',install)

if __name__=='__main__': unittest.main()
