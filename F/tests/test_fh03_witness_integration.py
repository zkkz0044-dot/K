from __future__ import annotations
import copy, hashlib, json, multiprocessing, os, pathlib, tempfile, time, unittest

from kk_f.checkpoint import checkpoint_checksum, write_checkpoint
from kk_f.evidence import GENESIS_HASH, EvidenceError, append as evidence_append, initialize as evidence_initialize, verify as evidence_verify, _canonical_bytes, _hash_record
from kk_f.monotonic_witness import save_state, seed_state
from kk_f.restart_ledger import RestartLedgerError, evaluate_and_record, initialize as ledger_initialize, read_ledger
from kk_f.witness_client import WitnessClientError, prepare as client_prepare, verify as client_verify
from kk_f.witness_daemon import run_server

BASE = {
    "protocol_version":"0.1","message_id":"123e4567-e89b-42d3-a456-426614174000",
    "kind":"result","source_role":"worker","target_role":"supervisor",
    "timestamp":"2026-09-04T01:45:00Z","status":"HEALTHY","payload":{"case":"fh03"},"error":None,
}

def _serve(state, sock, uid, gid):
    run_server(state, sock, allowed_uid=uid, allowed_gid=gid)

class Harness:
    def __init__(self, root:pathlib.Path, bindings:dict):
        self.root=root; self.state=root/'witness.json'; self.sock=root/'sock'/'witness.sock'; self.proc=None
        save_state(self.state, seed_state(bindings))
    def start(self):
        self.proc=multiprocessing.Process(target=_serve,args=(str(self.state),str(self.sock),os.getuid(),os.getgid())); self.proc.start()
        deadline=time.monotonic()+3
        ready=False
        while time.monotonic()<deadline:
            if self.sock.exists():
                try:
                    client_verify(str(self.sock),'safety_state',0,'0'*64)
                    ready=True; break
                except WitnessClientError:
                    pass
            time.sleep(.02)
        if not ready: raise RuntimeError('witness socket did not become ready')
        os.environ['KK_F_WITNESS_SOCKET']=str(self.sock)
    def stop(self):
        os.environ.pop('KK_F_WITNESS_SOCKET',None)
        if self.proc is not None:
            self.proc.terminate(); self.proc.join(5); self.proc=None
    def restart(self): self.stop(); self.start()

class FH03IntegrationTests(unittest.TestCase):
    def setUp(self): self.td=tempfile.TemporaryDirectory(); self.root=pathlib.Path(self.td.name); self.h=None
    def tearDown(self):
        if self.h: self.h.stop()
        os.environ.pop('KK_F_WITNESS_SOCKET',None); self.td.cleanup()
    @staticmethod
    def initial_ledger_digest(max_attempts=2):
        payload={"ledger_version":"0.2","attempts":0,"max_attempts":max_attempts,"last_decision":"NO_ACTION","last_attempt_at":None}
        return checkpoint_checksum(0,"READY",payload)
    def test_restart_ledger_stale_replay_rejected_after_witness_restart(self):
        ledger=self.root/'ledger'; d0=self.initial_ledger_digest(); self.h=Harness(self.root,{"restart_ledger":{"generation":0,"digest":d0}}); self.h.start()
        ledger_initialize(str(ledger),2); old=(ledger/'checkpoint.json').read_bytes()
        evaluate_and_record(str(ledger),"FAILED",attempted_at="2026-09-04T01:46:00Z")
        self.assertEqual(read_ledger(str(ledger))["generation"],1)
        self.h.restart(); (ledger/'checkpoint.json').write_bytes(old)
        with self.assertRaises(RestartLedgerError): read_ledger(str(ledger))
    def test_restart_ledger_pending_new_disk_recovers_to_commit_after_restart(self):
        ledger=self.root/'ledger'; d0=self.initial_ledger_digest(); self.h=Harness(self.root,{"restart_ledger":{"generation":0,"digest":d0}}); self.h.start(); ledger_initialize(str(ledger),2)
        payload={"ledger_version":"0.2","attempts":1,"max_attempts":2,"last_decision":"REPLACE_INSTANCE","last_attempt_at":"2026-09-04T01:46:00Z"}
        d1=checkpoint_checksum(1,"FAILED",payload); client_prepare(str(self.h.sock),"restart_ledger",0,d0,1,d1); write_checkpoint(str(ledger),1,"FAILED",payload)
        self.h.restart(); got=read_ledger(str(ledger)); self.assertEqual(got["generation"],1); self.assertEqual(got["attempts"],1)
    def test_evidence_stale_replay_rejected_after_witness_restart(self):
        store=self.root/'evidence'; self.h=Harness(self.root,{"evidence":{"generation":0,"digest":GENESIS_HASH}}); self.h.start(); evidence_initialize(store)
        old_log=(store/'evidence.jsonl').read_bytes(); old_head=(store/'HEAD.json').read_bytes(); evidence_append(store,copy.deepcopy(BASE)); self.assertEqual(evidence_verify(store)["count"],1)
        self.h.restart(); (store/'evidence.jsonl').write_bytes(old_log); (store/'HEAD.json').write_bytes(old_head)
        with self.assertRaises(EvidenceError): evidence_verify(store)
    def test_evidence_log_fsync_before_head_crash_recovers_and_repairs_head(self):
        store=self.root/'evidence'; self.h=Harness(self.root,{"evidence":{"generation":0,"digest":GENESIS_HASH}}); self.h.start(); evidence_initialize(store)
        record=copy.deepcopy(BASE); digest=_hash_record(1,GENESIS_HASH,record); entry={"seq":1,"prev_hash":GENESIS_HASH,"record":record,"record_hash":digest}
        client_prepare(str(self.h.sock),"evidence",0,GENESIS_HASH,1,digest)
        with (store/'evidence.jsonl').open('ab') as fh: fh.write(_canonical_bytes(entry)+b'\n'); fh.flush(); os.fsync(fh.fileno())
        self.h.restart(); got=evidence_verify(store); self.assertEqual(got["count"],1); head=json.loads((store/'HEAD.json').read_text()); self.assertEqual(head["count"],1); self.assertEqual(head["last_hash"],digest)

if __name__=='__main__': unittest.main()
