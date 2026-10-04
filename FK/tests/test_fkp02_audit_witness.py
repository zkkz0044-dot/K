import copy
import os
import threading
import unittest
from pathlib import Path
from uuid import uuid4

from kk_f import fk_audit_gateway
from kk_f.k_audit_witness import (
    KAuditWitnessError, commit_event, initialize_state, load_state, validate_event, recover_canonical,
)
from kk_k.audit_witness import AuditWitnessError, commit_audit_head, compare_with_witness, query_witness
from kk_k.memory import MemoryError, append_event, verify_event_log
from kk_k.test_support import project_tempdir


class FKP02AuditWitnessTests(unittest.TestCase):
    def setUp(self):
        self.state = Path('/root/K/F/evidence/fk') / ('.test-fkp02-' + uuid4().hex + '.json')
        initialize_state(str(self.state))
        self.tmp = project_tempdir()
        self.audit = Path(self.tmp.name) / 'audit.jsonl'

    def tearDown(self):
        self.tmp.cleanup()
        try: self.state.unlink()
        except FileNotFoundError: pass

    def append(self, eid, summary):
        return append_event(str(self.audit), event_id=eid, kind='SYSTEM', subject='audit', summary=summary)

    def server_once(self, allowed_uid=None):
        address='\0fkp02-'+uuid4().hex[:12]
        ready=threading.Event(); errors=[]
        def target():
            try:
                fk_audit_gateway.serve_once(
                    address=address, state_path=str(self.state),
                    allowed_uid=os.getuid() if allowed_uid is None else allowed_uid,
                    ready=ready.set,
                )
            except Exception as exc:
                errors.append(exc); ready.set()
        t=threading.Thread(target=target,daemon=True); t.start()
        self.assertTrue(ready.wait(2)); self.assertEqual(errors,[])
        return address,t,errors

    def finish(self,t,errors):
        t.join(2); self.assertFalse(t.is_alive()); self.assertEqual(errors,[])

    def test_initial_state_zero(self):
        s=load_state(str(self.state)); self.assertEqual((s['generation'],s['digest']),(0,'0'*64))

    def test_f_independently_validates_and_commits_event(self):
        e=self.append('e1','one')
        s=commit_event(str(self.state),e)
        self.assertEqual((s['generation'],s['digest']),(1,e['entry_sha256']))

    def test_replay_rejected(self):
        e=self.append('e1','one'); commit_event(str(self.state),e)
        with self.assertRaisesRegex(KAuditWitnessError,'GENERATION_MISMATCH'):
            commit_event(str(self.state),e)

    def test_generation_gap_rejected(self):
        e=self.append('e1','one'); e=copy.deepcopy(e); e['sequence']=2
        # recompute is intentionally not done: independent validation may reject digest first.
        with self.assertRaises(KAuditWitnessError): commit_event(str(self.state),e)

    def test_prev_digest_mismatch_rejected_even_with_valid_event_hash(self):
        e=self.append('e1','one'); commit_event(str(self.state),e)
        alt=Path(self.tmp.name)/'alt.jsonl'
        e2=append_event(str(alt),event_id='x1',kind='SYSTEM',subject='audit',summary='alt')
        e3=append_event(str(alt),event_id='x2',kind='SYSTEM',subject='audit',summary='alt2')
        self.assertEqual(e3['sequence'],2)
        with self.assertRaisesRegex(KAuditWitnessError,'PREV_DIGEST_MISMATCH'):
            commit_event(str(self.state),e3)

    def test_forged_entry_digest_rejected(self):
        e=copy.deepcopy(self.append('e1','one')); e['entry_sha256']='f'*64
        with self.assertRaisesRegex(KAuditWitnessError,'EVENT_DIGEST_MISMATCH'):
            validate_event(e)

    def test_world_writable_witness_state_rejected(self):
        os.chmod(self.state,0o666)
        with self.assertRaisesRegex(KAuditWitnessError,'WITNESS_INVALID'):
            load_state(str(self.state))

    def test_gateway_commit_then_query(self):
        self.append('e1','one')
        a,t,e=self.server_once(); committed=commit_audit_head(str(self.audit),address=a); self.finish(t,e)
        self.assertEqual(committed.generation,1)
        a,t,e=self.server_once(); q=query_witness(address=a); self.finish(t,e)
        self.assertEqual(q,committed)

    def test_rollback_detected(self):
        self.append('e1','one'); first=self.audit.read_bytes()
        a,t,e=self.server_once(); commit_audit_head(str(self.audit),address=a); self.finish(t,e)
        self.append('e2','two')
        a,t,e=self.server_once(); commit_audit_head(str(self.audit),address=a); self.finish(t,e)
        self.audit.write_bytes(first)
        a,t,e=self.server_once(); status=compare_with_witness(str(self.audit),address=a); self.finish(t,e)
        self.assertEqual(status,'ROLLBACK_DETECTED')

    def test_same_generation_divergence_detected(self):
        self.append('e1','one')
        a,t,e=self.server_once(); commit_audit_head(str(self.audit),address=a); self.finish(t,e)
        other=Path(self.tmp.name)/'other.jsonl'
        append_event(str(other),event_id='different',kind='SYSTEM',subject='audit',summary='different')
        self.audit.write_bytes(other.read_bytes())
        a,t,e=self.server_once(); status=compare_with_witness(str(self.audit),address=a); self.finish(t,e)
        self.assertEqual(status,'DIVERGENCE')

    def test_rollback_then_fork_detected_before_commit(self):
        self.append('e1','one'); line1=self.audit.read_bytes()
        a,t,e=self.server_once(); commit_audit_head(str(self.audit),address=a); self.finish(t,e)
        self.append('e2','two')
        a,t,e=self.server_once(); commit_audit_head(str(self.audit),address=a); self.finish(t,e)
        # Roll back to e1, create an alternate e2 and then e3. Local gen is remote+1,
        # but e3.prev points to alternate e2, not the F-witnessed real e2.
        self.audit.write_bytes(line1)
        self.append('alt2','alternate-two'); self.append('alt3','alternate-three')
        a,t,e=self.server_once(); status=compare_with_witness(str(self.audit),address=a); self.finish(t,e)
        self.assertEqual(status,'FORK_DETECTED')

    def test_direct_gateway_bypass_cannot_commit_fork(self):
        e1=self.append('e1','one'); commit_event(str(self.state),e1)
        self.append('e2','two'); real_e2=verify_event_log(str(self.audit))[-1]; commit_event(str(self.state),real_e2)
        other=Path(self.tmp.name)/'fork.jsonl'
        append_event(str(other),event_id='f1',kind='SYSTEM',subject='audit',summary='fork1')
        append_event(str(other),event_id='f2',kind='SYSTEM',subject='audit',summary='fork2')
        fork3=append_event(str(other),event_id='f3',kind='SYSTEM',subject='audit',summary='fork3')
        with self.assertRaisesRegex(KAuditWitnessError,'PREV_DIGEST_MISMATCH'):
            commit_event(str(self.state),fork3)

    def test_middle_delete_rejected_by_k_chain_before_witness(self):
        self.append('e1','one'); self.append('e2','two'); self.append('e3','three')
        lines=self.audit.read_text().splitlines()
        self.audit.write_text(lines[0]+'\n'+lines[2]+'\n')
        with self.assertRaises(MemoryError): verify_event_log(str(self.audit))


    def test_crash_window_log_ahead_one_recovers_state(self):
        log=str(self.state)+'.crash.events.jsonl'
        before=self.state.read_bytes()
        e=self.append('e1','one')
        commit_event(str(self.state),e,canonical_log_path=log)
        # Simulate crash after canonical log fsync but before witness-state replace.
        self.state.write_bytes(before); os.chmod(self.state,0o600)
        recovered=recover_canonical(str(self.state),log)
        self.assertEqual((recovered['generation'],recovered['digest']),(1,e['entry_sha256']))
        Path(log).unlink(missing_ok=True)

    def test_state_ahead_of_canonical_log_fails_closed(self):
        log=str(self.state)+'.behind.events.jsonl'
        e=self.append('e1','one')
        commit_event(str(self.state),e)
        Path(log).write_bytes(b''); os.chmod(log,0o600)
        with self.assertRaisesRegex(KAuditWitnessError,'CANONICAL_LOG_MISMATCH'):
            recover_canonical(str(self.state),log)
        Path(log).unlink(missing_ok=True)

    def test_wrong_peer_uid_vetoed(self):
        a,t,e=self.server_once(allowed_uid=os.getuid()+1000)
        with self.assertRaisesRegex(AuditWitnessError,'PEER_AUTH_DENY'):
            query_witness(address=a)
        self.finish(t,e)

    def test_commit_request_has_event_not_path_or_asserted_head(self):
        import inspect, kk_k.audit_witness as module
        source=inspect.getsource(module.commit_audit_head)
        self.assertNotIn('"path"',source)
        self.assertIn('"event"',source)
        self.assertNotIn('"generation":head',source)


if __name__=='__main__': unittest.main()
