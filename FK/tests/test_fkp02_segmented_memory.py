import os
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from kk_f import k_audit_witness as witness
from kk_f.k_audit_witness import KAuditWitnessError, commit_event, initialize_state, load_canonical_events, load_state, recover_canonical
from kk_k.memory import append_event
from kk_k.test_support import project_tempdir


class SegmentedCanonicalMemoryTests(unittest.TestCase):
    def setUp(self):
        tag=uuid4().hex
        self.state=Path('/root/K/F/evidence/fk')/('.seg-'+tag+'.json')
        self.log=Path('/root/K/F/evidence/fk')/('.seg-'+tag+'.jsonl')
        initialize_state(str(self.state))
        self.tmp=project_tempdir()
        self.local=Path(self.tmp.name)/'local.jsonl'

    def tearDown(self):
        self.tmp.cleanup()
        self.state.unlink(missing_ok=True)
        self.log.unlink(missing_ok=True)
        for p in self.log.parent.glob(self.log.name+'.seg.*'):
            p.unlink(missing_ok=True)

    def _commit_many(self,count):
        out=[]
        for i in range(1,count+1):
            event=append_event(str(self.local),event_id=f'e{i}',kind='SYSTEM',subject='audit',summary=('memory-'+str(i)+'-'+('x'*90)))
            commit_event(str(self.state),event,canonical_log_path=str(self.log))
            out.append(event)
        return out

    def test_rollover_preserves_one_global_hash_chain(self):
        with patch.object(witness,'SEGMENT_TARGET_BYTES',700):
            expected=self._commit_many(30)
        segments=sorted(self.log.parent.glob(self.log.name+'.seg.*'))
        self.assertGreaterEqual(len(segments),2)
        got=load_canonical_events(str(self.log))
        self.assertEqual([e['sequence'] for e in got],list(range(1,31)))
        self.assertEqual(got[-1]['entry_sha256'],expected[-1]['entry_sha256'])
        self.assertEqual(load_state(str(self.state))['digest'],expected[-1]['entry_sha256'])

    def test_segment_gap_fails_closed(self):
        with patch.object(witness,'SEGMENT_TARGET_BYTES',550):
            self._commit_many(24)
        segments=sorted(self.log.parent.glob(self.log.name+'.seg.*'))
        self.assertGreaterEqual(len(segments),3)
        segments[0].rename(segments[0].with_name(self.log.name+'.seg.999999'))
        with self.assertRaisesRegex(KAuditWitnessError,'CANONICAL_LOG_INVALID'):
            load_canonical_events(str(self.log))

    def test_tampered_sealed_segment_fails_closed(self):
        with patch.object(witness,'SEGMENT_TARGET_BYTES',600):
            self._commit_many(20)
        segment=sorted(self.log.parent.glob(self.log.name+'.seg.*'))[0]
        raw=bytearray(segment.read_bytes()); raw[len(raw)//2] ^= 1; segment.write_bytes(raw); os.chmod(segment,0o600)
        with self.assertRaises(KAuditWitnessError):
            load_canonical_events(str(self.log))

    def test_normal_commit_uses_bounded_tail_not_full_rescan(self):
        with patch.object(witness,'SEGMENT_TARGET_BYTES',10**9), patch.object(witness,'recover_canonical',side_effect=AssertionError('full scan used')):
            self._commit_many(25)
        self.assertEqual(load_state(str(self.state))['generation'],25)

    def test_fast_tail_repairs_one_event_crash_before_next_commit(self):
        self._commit_many(5); before=self.state.read_bytes()
        event6=append_event(str(self.local),event_id='e6x',kind='SYSTEM',subject='audit',summary='crash-six')
        commit_event(str(self.state),event6,canonical_log_path=str(self.log)); self.state.write_bytes(before); os.chmod(self.state,0o600)
        event7=append_event(str(self.local),event_id='e7x',kind='SYSTEM',subject='audit',summary='after-repair')
        repaired=commit_event(str(self.state),event7,canonical_log_path=str(self.log))
        self.assertEqual((repaired['generation'],repaired['digest']),(7,event7['entry_sha256']))

    def test_rollover_performs_full_chain_verification_before_seal(self):
        original=witness.canonical_head
        with patch.object(witness,'SEGMENT_TARGET_BYTES',600), patch.object(witness,'canonical_head',wraps=original) as head:
            self._commit_many(18)
        self.assertGreaterEqual(head.call_count,1)

    def test_crash_after_segment_append_repairs_witness_head(self):
        with patch.object(witness,'SEGMENT_TARGET_BYTES',620):
            self._commit_many(12)
            before=self.state.read_bytes()
            event=append_event(str(self.local),event_id='e13',kind='SYSTEM',subject='audit',summary='crash-window-'+'z'*90)
            commit_event(str(self.state),event,canonical_log_path=str(self.log))
            self.state.write_bytes(before); os.chmod(self.state,0o600)
            repaired=recover_canonical(str(self.state),str(self.log))
        self.assertEqual(repaired['generation'],13)
        self.assertEqual(repaired['digest'],event['entry_sha256'])


if __name__=='__main__': unittest.main()
