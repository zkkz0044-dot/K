from __future__ import annotations

import copy
import json
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from kk_k import world_entity_graph as weg


def item(eid: str, *, group='source-a', host='a.example', title='ExampleAI update with Microsoft', observed_at=None, status='OBSERVED_UNVERIFIED', memory_eligible=False):
    observed_at = observed_at or datetime.now(timezone.utc).isoformat()
    return {
        'evidence_id': eid,
        'observed_at': observed_at,
        'status': status,
        'memory_eligible': memory_eligible,
        'independence_group': group,
        'source_host': host,
        'source_class': 'PRIMARY',
        'topic': 'ai_technology',
        'title': title,
        'snippet': 'ExampleAI discussed infrastructure with Microsoft during a technical briefing.',
    }


def run(items, now=None):
    tmp = tempfile.TemporaryDirectory()
    root = Path(tmp.name)
    result = weg.apply_observations(items, root/'state', root/'updates', now=now)
    state = weg.load_state(root/'state'/'current.json')
    return tmp, root, result, state


def test_single_observation_builds_unverified_graph_only():
    tmp, root, result, state = run([item('ev-1')])
    try:
        assert result['processed'] == 1 and result['skipped'] == 0
        assert state['truth_status'] == 'UNVERIFIED'
        assert state['memory_eligible'] is False
        predicates = {r['predicate'] for r in state['relations']}
        assert {'FROM_SOURCE','ABOUT_TOPIC','MENTIONS','CO_MENTIONED_WITH'} <= predicates
        assert all(r['status'] == 'UNVERIFIED_CANDIDATE' for r in state['relations'])
    finally:
        tmp.cleanup()


def test_independent_sources_corroborate_only_repeated_same_relation():
    a=item('ev-a',group='wire-a',host='a.example')
    b=item('ev-b',group='wire-b',host='b.example')
    tmp, root, result, state = run([a,b])
    try:
        co = [r for r in state['relations'] if r['predicate']=='CO_MENTIONED_WITH']
        assert co and all(r['status']=='CORROBORATED_MENTION' for r in co)
        assert all(len(set(r['source_groups'])) == 2 for r in co)
        mentions = [r for r in state['relations'] if r['predicate']=='MENTIONS']
        assert mentions and all(r['status']=='UNVERIFIED_CANDIDATE' for r in mentions)
    finally:
        tmp.cleanup()


def test_same_independence_group_does_not_fake_corroboration():
    tmp, root, result, state = run([
        item('ev-a',group='same-wire',host='a.example'),
        item('ev-b',group='same-wire',host='mirror.example'),
    ])
    try:
        co = [r for r in state['relations'] if r['predicate']=='CO_MENTIONED_WITH']
        assert co and all(r['status']=='UNVERIFIED_CANDIDATE' for r in co)
    finally:
        tmp.cleanup()


def test_unknown_source_group_never_counts_as_independent_confirmation():
    a=item('ev-a',group='',host='')
    b=item('ev-b',group='',host='')
    tmp, root, result, state = run([a,b])
    try:
        co=[r for r in state['relations'] if r['predicate']=='CO_MENTIONED_WITH']
        assert co and all(r['status']=='UNVERIFIED_CANDIDATE' for r in co)
    finally:
        tmp.cleanup()


def test_replay_of_same_evidence_is_idempotently_skipped():
    tmp = tempfile.TemporaryDirectory(); root=Path(tmp.name)
    try:
        first=weg.apply_observations([item('ev-replay')],root/'state',root/'updates')
        state1=weg.load_state(root/'state'/'current.json')
        second=weg.apply_observations([item('ev-replay')],root/'state',root/'updates')
        state2=weg.load_state(root/'state'/'current.json')
        assert first['processed']==1
        assert second['processed']==0 and second['skipped']==1
        assert state2==state1
    finally:
        tmp.cleanup()


def test_duplicate_evidence_id_inside_batch_fails_closed():
    with tempfile.TemporaryDirectory() as td:
        root=Path(td)
        with pytest.raises(weg.WorldEntityGraphError,match='duplicate observation evidence id'):
            weg.apply_observations([item('dup'),item('dup',group='b')],root/'state',root/'updates')


def test_trust_escalated_input_is_rejected():
    with tempfile.TemporaryDirectory() as td:
        root=Path(td)
        with pytest.raises(weg.WorldEntityGraphError,match='trust escalation'):
            weg.apply_observations([item('bad',status='VERIFIED_FACT')],root/'state',root/'updates')
        with pytest.raises(weg.WorldEntityGraphError,match='trust escalation'):
            weg.apply_observations([item('bad2',memory_eligible=True)],root/'state',root/'updates')


def test_forged_lineage_digest_is_rejected_on_load():
    tmp, root, result, state = run([item('ev-lineage')])
    try:
        p=root/'state'/'current.json'
        tampered=copy.deepcopy(state)
        tampered['relations'][0]['lineage_sha256']='f'*64
        p.write_text(json.dumps(tampered,ensure_ascii=False),encoding='utf-8')
        with pytest.raises(weg.WorldEntityGraphError,match='lineage mismatch'):
            weg.load_state(p)
    finally:
        tmp.cleanup()


def test_dangling_relation_is_rejected_on_load():
    tmp, root, result, state = run([item('ev-dangle')])
    try:
        p=root/'state'/'current.json'
        tampered=copy.deepcopy(state)
        rel=tampered['relations'][0]
        rel['object_id']='ent-'+'f'*20
        rel['relation_id']=weg._relation_id(rel['subject_id'],rel['predicate'],rel['object_id'])
        rel['lineage_sha256']=weg._lineage_sha(rel['evidence_ids'],rel['source_groups'],rel['source_classes'])
        p.write_text(json.dumps(tampered,ensure_ascii=False),encoding='utf-8')
        with pytest.raises(weg.WorldEntityGraphError,match='dangling relation'):
            weg.load_state(p)
    finally:
        tmp.cleanup()


def test_observation_window_must_equal_first_and_last_seen():
    tmp, root, result, state = run([item('ev-window')])
    try:
        p=root/'state'/'current.json'
        tampered=copy.deepcopy(state)
        tampered['relations'][0]['observation_window']['from']='2000-01-01T00:00:00+00:00'
        p.write_text(json.dumps(tampered,ensure_ascii=False),encoding='utf-8')
        with pytest.raises(weg.WorldEntityGraphError,match='observation window time'):
            weg.load_state(p)
    finally:
        tmp.cleanup()


def test_entity_time_cannot_run_backwards():
    tmp, root, result, state = run([item('ev-time')])
    try:
        p=root/'state'/'current.json'
        tampered=copy.deepcopy(state)
        tampered['entities'][0]['first_seen']='2030-01-01T00:00:00+00:00'
        tampered['entities'][0]['last_seen']='2020-01-01T00:00:00+00:00'
        p.write_text(json.dumps(tampered,ensure_ascii=False),encoding='utf-8')
        with pytest.raises(weg.WorldEntityGraphError,match='invalid entity time'):
            weg.load_state(p)
    finally:
        tmp.cleanup()


def test_old_observation_becomes_stale_without_becoming_false():
    now=datetime(2026,9,15,tzinfo=timezone.utc)
    old=(now-timedelta(days=weg.MAX_AGE_DAYS+1)).isoformat()
    tmp, root, result, state = run([item('ev-old',observed_at=old)],now=now)
    try:
        assert state['relations']
        assert all(r['status']=='STALE' for r in state['relations'])
        assert state['truth_status']=='UNVERIFIED'
    finally:
        tmp.cleanup()


def test_query_returns_bounded_unverified_context():
    tmp, root, result, state = run([
        item('ev-q1',title='ExampleAI update with Microsoft'),
        item('ev-q2',group='source-b',host='b.example',title='NVIDIA update with ExampleAI'),
    ])
    try:
        ctx=weg.query_context('ExampleAI',path=root/'state'/'current.json',limit=4)
        assert ctx['schema']==weg.CONTEXT_SCHEMA
        assert ctx['authority']==weg.AUTHORITY
        assert ctx['truth_status']=='UNVERIFIED'
        assert ctx['memory_eligible'] is False
        assert 1 <= len(ctx['entities']) <= 4
        assert all('entity_id' in e for e in ctx['entities'])
        assert len(ctx['relations']) <= 8
    finally:
        tmp.cleanup()


def test_graph_state_is_bounded_and_round_trips():
    now=datetime.now(timezone.utc)
    batch=[item(f'ev-{i}',group=f'g-{i}',host=f'h{i}.example',title=f'ExampleAI update with Microsoft {i}') for i in range(20)]
    tmp, root, result, state=run(batch,now=now)
    try:
        loaded=weg.load_state(root/'state'/'current.json')
        assert loaded==state
        assert len(state['entities']) <= weg.MAX_ENTITIES
        assert len(state['relations']) <= weg.MAX_RELATIONS
    finally:
        tmp.cleanup()


def test_normalized_duplicate_named_candidates_do_not_create_self_edge():
    tmp, root, result, state = run([item('ev-normalized',title='EXAMPLE_AI update with ExampleAI')])
    try:
        assert all(r['subject_id'] != r['object_id'] for r in state['relations'])
        named=[e for e in state['entities'] if e['kind']=='NAMED_CANDIDATE' and e['label'].casefold()=='exampleai']
        assert len(named)==1
    finally:
        tmp.cleanup()
