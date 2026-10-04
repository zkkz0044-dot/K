import hashlib
import json
import sqlite3
import tempfile
from pathlib import Path

import pytest

from kk_f.conversation_index import (
    ConversationIndexError, append_event, matches_state,
    recent_events, recall_events, rebuild_index,
)
from kk_f.fk_audit_gateway import _recall_conversation_events, _recent_completed_events

ZERO='0'*64

def make_event(seq,prev,subject,summary,event_id=None):
    base={'schema':'K02.EVENT.1','sequence':seq,'event_id':event_id or f'e{seq}',
          'kind':'SYSTEM','subject':subject,'summary':summary,'prev_sha256':prev}
    raw=json.dumps(base,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
    return {**base,'entry_sha256':hashlib.sha256(raw).hexdigest()}

def chain(specs):
    out=[]; prev=ZERO
    for seq,(subject,summary) in enumerate(specs,1):
        event=make_event(seq,prev,subject,summary)
        out.append(event); prev=event['entry_sha256']
    return out

def sample_events():
    return chain([
        ('human_chat','苹果计划 alpha'),('dialogue_gate','route'),('k_reply','苹果计划第一版'),
        ('human_chat','这轮会失败'),('dialogue_error','DialogueError'),
        ('human_chat','火箭 beta'),('k_reply','火箭推进测试'),
        ('human_chat','苹果计划 gamma'),('k_reply','苹果计划第二版修正'),
    ])

def test_rebuild_recent_and_recall_match_canonical_scan():
    events=sample_events()
    with tempfile.TemporaryDirectory() as td:
        path=str(Path(td)/'index.sqlite3')
        head=rebuild_index(path,events)
        assert head==(events[-1]['sequence'],events[-1]['entry_sha256'])
        assert matches_state(path,*head)
        assert [x['sequence'] for x in recent_events(path,4)] == [x['sequence'] for x in _recent_completed_events(events,4)]
        for query in ('苹果计划','火箭 beta','gamma 修正'):
            got=[x['sequence'] for x in recall_events(path,query,4)]
            expected=[x['sequence'] for x in _recall_conversation_events(events,query,4)]
            assert got==expected

def test_failed_turn_stays_out_of_index():
    events=sample_events()
    with tempfile.TemporaryDirectory() as td:
        path=str(Path(td)/'index.sqlite3'); rebuild_index(path,events)
        seqs=[x['sequence'] for x in recall_events(path,'失败',4)]
        assert 4 not in seqs and 5 not in seqs

def test_incremental_append_tracks_pending_then_reply():
    first=chain([('human_chat','旧问题'),('k_reply','旧回答')])
    with tempfile.TemporaryDirectory() as td:
        path=str(Path(td)/'index.sqlite3'); rebuild_index(path,first)
        e3=make_event(3,first[-1]['entry_sha256'],'human_chat','新问题')
        append_event(path,e3,3,e3['entry_sha256'])
        assert matches_state(path,3,e3['entry_sha256'])
        assert [x['sequence'] for x in recent_events(path,8)]==[1,2]
        e4=make_event(4,e3['entry_sha256'],'k_reply','新回答')
        append_event(path,e4,4,e4['entry_sha256'])
        assert [x['sequence'] for x in recent_events(path,8)]==[1,2,3,4]

def test_head_mismatch_fails_closed():
    events=sample_events()
    with tempfile.TemporaryDirectory() as td:
        path=str(Path(td)/'index.sqlite3'); rebuild_index(path,events)
        bad=make_event(events[-1]['sequence']+2,events[-1]['entry_sha256'],'human_chat','skip')
        with pytest.raises(ConversationIndexError):
            append_event(path,bad,bad['sequence'],bad['entry_sha256'])

def test_turn_payload_corruption_is_detected():
    events=sample_events()
    with tempfile.TemporaryDirectory() as td:
        path=str(Path(td)/'index.sqlite3'); rebuild_index(path,events)
        con=sqlite3.connect(path)
        con.execute("UPDATE turns SET events_json='[]' WHERE reply_sequence=(SELECT max(reply_sequence) FROM turns)")
        con.commit(); con.close()
        with pytest.raises(ConversationIndexError):
            recent_events(path,8)
