import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from kk_f import conversation_index as ci
from kk_f import fk_audit_gateway as g
from kk_f.k_audit_witness import commit_event, initialize_state, iter_canonical_events, load_state
from kk_k.memory import append_event
from kk_k.test_support import project_tempdir


class ConversationIndexGatewayTests(unittest.TestCase):
    def setUp(self):
        tag = uuid4().hex
        self.tmp = project_tempdir()
        base = Path(self.tmp.name)
        self.state = base / f'.idx-{tag}.json'
        self.log = base / f'.idx-{tag}.jsonl'
        self.index = base / f'.idx-{tag}.sqlite3'
        self.local = base / 'local.jsonl'
        initialize_state(str(self.state))

    def tearDown(self):
        self.tmp.cleanup()
    def _commit(self, event_id, subject, summary):
        event = append_event(
            str(self.local), event_id=event_id, kind='SYSTEM',
            subject=subject, summary=summary,
        )
        commit_event(str(self.state), event, canonical_log_path=str(self.log))
        return event

    def _turns(self, count=12):
        for i in range(count):
            self._commit(f'h{i}', 'human_chat', f'用户讨论 project-{i % 4} topic-{i}')
            self._commit(f'k{i}', 'k_reply', f'K 回复 project-{i % 4} result-{i}')

    def _dispatch(self, request):
        return g._dispatch(
            request, str(self.state), str(self.log), str(self.index)
        )

    def test_current_index_avoids_full_canonical_rescan(self):
        self._turns()
        first = self._dispatch({'schema':'FK_AUDIT.HISTORY.2','limit':8})
        self.assertEqual(first['outcome'], 'HISTORY')
        self.assertTrue(ci.matches_state(
            str(self.index), load_state(str(self.state))['generation'],
            load_state(str(self.state))['digest'],
        ))
        with patch.object(g, 'recover_canonical', side_effect=AssertionError('full scan used')):
            second = self._dispatch({'schema':'FK_AUDIT.HISTORY.2','limit':8})
        self.assertEqual(second, first)
    def test_corrupt_index_rebuilds_from_canonical(self):
        self._turns()
        expected = self._dispatch({'schema':'FK_AUDIT.RECALL.2','query':'project-2','limit':4})
        self.index.write_bytes(b'not-a-sqlite-database')
        rebuilt = self._dispatch({'schema':'FK_AUDIT.RECALL.2','query':'project-2','limit':4})
        self.assertEqual(rebuilt, expected)
        state = load_state(str(self.state))
        self.assertTrue(ci.matches_state(str(self.index), state['generation'], state['digest']))

    def test_canonical_commit_survives_total_index_failure(self):
        self._turns(2)
        self._dispatch({'schema':'FK_AUDIT.HISTORY.2','limit':8})
        event = append_event(
            str(self.local), event_id='audit-extra', kind='SYSTEM',
            subject='audit', summary='non conversation event',
        )
        with patch.object(g, 'index_append_event', side_effect=ci.ConversationIndexError('boom')), patch.object(
            g, 'rebuild_conversation_index', side_effect=ci.ConversationIndexError('boom')
        ):
            state = g._commit_with_index(
                str(self.state), str(self.log), event, str(self.index)
            )
        self.assertEqual(state['generation'], event['sequence'])
        self.assertEqual(state['digest'], event['entry_sha256'])
        repaired = self._dispatch({'schema':'FK_AUDIT.HISTORY.2','limit':8})
        self.assertEqual(repaired['outcome'], 'HISTORY')
        self.assertTrue(ci.matches_state(str(self.index), state['generation'], state['digest']))
    def test_nonconversation_commit_keeps_index_head_current(self):
        self._turns(2)
        self._dispatch({'schema':'FK_AUDIT.HISTORY.2','limit':8})
        event = append_event(
            str(self.local), event_id='state-only', kind='SYSTEM',
            subject='personality_revision_shadow', summary='derived state marker',
        )
        state = g._commit_with_index(
            str(self.state), str(self.log), event, str(self.index)
        )
        self.assertTrue(ci.matches_state(str(self.index), state['generation'], state['digest']))

    def test_index_recall_matches_canonical_scan(self):
        for i in range(40):
            group = ('alpha', 'beta', 'gamma', 'delta')[i % 4]
            self._commit(f'h{i}', 'human_chat', f'{group} 长期记忆 测试轮次 {i}')
            self._commit(f'k{i}', 'k_reply', f'{group} 回答 结果 {i}')
        state = load_state(str(self.state))
        ci.rebuild_index(str(self.index), iter_canonical_events(str(self.log)))
        self.assertTrue(ci.matches_state(str(self.index), state['generation'], state['digest']))
        queries = ('alpha', 'beta 长期记忆', 'gamma 结果', 'delta', '不存在词')
        for query in queries:
            with self.subTest(query=query):
                indexed = ci.recall_events(str(self.index), query, 4)
                scanned = g._recall_conversation_events(
                    iter_canonical_events(str(self.log)), query, 4
                )
                self.assertEqual(indexed, scanned)


if __name__ == '__main__':
    unittest.main()
