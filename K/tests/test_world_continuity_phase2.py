import json

import pytest

from kk_k import world_continuity as wc
from world_test_fixtures import write_continuity_context


@pytest.fixture
def context_path(tmp_path):
    return write_continuity_context(tmp_path)


def refs(path):
    _data, rounds, ids, round_hashes, _sha = wc.load_context(path)
    current = rounds[-1]
    history = rounds[-2]
    return rounds, ids, round_hashes, current, history


def item(status, current, history, confidence="LOW"):
    if status == "NEW":
        hashes = [current["round_context_sha256"]]
        evidence = [current["evidence"][0]["evidence_id"]]
    elif status == "STALE":
        hashes = [history["round_context_sha256"]]
        evidence = [history["evidence"][0]["evidence_id"]]
    else:
        hashes = [history["round_context_sha256"], current["round_context_sha256"]]
        evidence = [history["evidence"][0]["evidence_id"], current["evidence"][0]["evidence_id"]]
    return {
        "subject": "synthetic subject",
        "status": status,
        "evidence_ids": evidence,
        "round_context_sha256s": hashes,
        "rationale": "Synthetic traceable provisional continuity judgment.",
        "confidence": confidence,
    }


def valid_provider_factory(path):
    _rounds, _ids, _hashes, current, history = refs(path)
    proposal = {
        "schema": "K.WORLD.CONTINUITY.PROPOSAL.1",
        "assessment": "Synthetic cross-round provisional comparison.",
        "items": [item("PERSISTING", current, history)],
    }

    def provider(role, prompt):
        if role == "WORLD_CONTINUITY_A":
            return json.dumps({
                "schema": "K.WORLD.CONTINUITY.MODEL.A.1",
                "proposal_text": json.dumps(proposal),
                "confidence": "LOW",
            })
        if role == "WORLD_CONTINUITY_B":
            return json.dumps({
                "schema": "K.WORLD.CONTINUITY.MODEL.B.1",
                "critique": "OK",
                "risk_flags": ["NONE"],
                "confidence": "LOW",
            })
        return json.dumps({
            "schema": "K.WORLD.CONTINUITY.MODEL.C.1",
            "verdict": "APPROVE_A",
            "confidence": "LOW",
        })

    return provider


def test_continuity_evaluate_stays_provisional(context_path):
    out = wc.evaluate(str(context_path), provider=valid_provider_factory(context_path))
    assert out["status"] == "APPROVED_PROVISIONAL"
    assert out["authority"] == "COGNITIVE_CONTINUITY_PROPOSAL_ONLY"
    assert out["memory_eligible"] is False


def test_cross_round_status_requires_current_and_history(context_path):
    _rounds, ids, hashes, current, history = refs(context_path)
    bad = item("PERSISTING", current, history)
    bad["round_context_sha256s"] = [history["round_context_sha256"]]
    bad["evidence_ids"] = [history["evidence"][0]["evidence_id"]]
    proposal = {"schema": "K.WORLD.CONTINUITY.PROPOSAL.1", "assessment": "x", "items": [bad]}
    with pytest.raises(wc.ContinuityError, match="current and history"):
        wc.parse_proposal(json.dumps(proposal), ids, hashes, current["round_context_sha256"])


def test_new_must_reference_current_only(context_path):
    _rounds, ids, hashes, current, history = refs(context_path)
    bad = item("NEW", current, history)
    bad["round_context_sha256s"] = [history["round_context_sha256"]]
    bad["evidence_ids"] = [history["evidence"][0]["evidence_id"]]
    proposal = {"schema": "K.WORLD.CONTINUITY.PROPOSAL.1", "assessment": "x", "items": [bad]}
    with pytest.raises(wc.ContinuityError, match="NEW must reference current only"):
        wc.parse_proposal(json.dumps(proposal), ids, hashes, current["round_context_sha256"])


def test_stale_cannot_reference_current(context_path):
    _rounds, ids, hashes, current, history = refs(context_path)
    bad = item("STALE", current, history)
    bad["round_context_sha256s"] = [current["round_context_sha256"]]
    bad["evidence_ids"] = [current["evidence"][0]["evidence_id"]]
    proposal = {"schema": "K.WORLD.CONTINUITY.PROPOSAL.1", "assessment": "x", "items": [bad]}
    with pytest.raises(wc.ContinuityError, match="STALE cannot reference current"):
        wc.parse_proposal(json.dumps(proposal), ids, hashes, current["round_context_sha256"])


@pytest.mark.parametrize("confidence", ["HIGH", "MEDIUM"])
def test_non_low_confidence_forbidden(context_path, confidence):
    _rounds, ids, hashes, current, history = refs(context_path)
    bad = item("PERSISTING", current, history, confidence=confidence)
    proposal = {"schema": "K.WORLD.CONTINUITY.PROPOSAL.1", "assessment": "x", "items": [bad]}
    with pytest.raises(wc.ContinuityError, match="status/confidence"):
        wc.parse_proposal(json.dumps(proposal), ids, hashes, current["round_context_sha256"])
