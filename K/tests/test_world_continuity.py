import hashlib
import json

import pytest

from kk_k import world_continuity as wc
from world_test_fixtures import load_repo_tool, write_continuity_context

wci = load_repo_tool("world_continuity_ingest")


@pytest.fixture
def context_path(tmp_path):
    return write_continuity_context(tmp_path)


def refs(path):
    data, rounds, ids, round_hashes, _sha = wc.load_context(path)
    current = rounds[-1]
    return data, rounds, ids, round_hashes, current


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


def provider_for(path):
    _d, rounds, _ids, _hashes, current = refs(path)
    history = rounds[-2]
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


def test_valid_new_with_fake_provider(context_path):
    out = wc.evaluate(str(context_path), provider=provider_for(context_path))
    assert out["status"] == "APPROVED_PROVISIONAL"
    assert out["memory_eligible"] is False


def test_cross_round_requires_two_rounds(context_path):
    _d, rounds, ids, hashes, _current = refs(context_path)
    history = rounds[-2]
    bad = item("PERSISTING", rounds[-1], history)
    bad["round_context_sha256s"] = [history["round_context_sha256"]]
    with pytest.raises(wc.ContinuityError):
        wc.parse_proposal(
            json.dumps({"schema": "K.WORLD.CONTINUITY.PROPOSAL.1", "assessment": "x", "items": [bad]}),
            ids,
            hashes,
        )


def test_high_confidence_rejected(context_path):
    _d, rounds, ids, hashes, _current = refs(context_path)
    bad = item("NEW", rounds[-1], rounds[-2], confidence="HIGH")
    with pytest.raises(wc.ContinuityError, match="status/confidence"):
        wc.parse_proposal(
            json.dumps({"schema": "K.WORLD.CONTINUITY.PROPOSAL.1", "assessment": "x", "items": [bad]}),
            ids,
            hashes,
        )


def _run_for(context_path, proposal_item):
    raw = context_path.read_bytes()
    return {
        "schema": "K.WORLD.CONTINUITY.RUN.1",
        "evaluated_at": "2026-09-02T01:00:00+00:00",
        "source_context_sha256": hashlib.sha256(raw).hexdigest(),
        "authority": "COGNITIVE_CONTINUITY_PROPOSAL_ONLY",
        "memory_eligible": False,
        "status": "APPROVED_PROVISIONAL",
        "proposal": {
            "schema": "K.WORLD.CONTINUITY.PROPOSAL.1",
            "assessment": "Synthetic provisional comparison.",
            "items": [proposal_item],
        },
        "critic": {"critique": "OK", "risk_flags": ["NONE"]},
        "judge": {"verdict": "APPROVE_A"},
    }


def test_ingest_rejects_new_from_old_round(context_path, tmp_path):
    _d, rounds, _ids, _hashes, _current = refs(context_path)
    old = rounds[0]
    candidate = item("STALE", rounds[-1], old)
    candidate["status"] = "NEW"
    run_path = tmp_path / "run.json"
    run_path.write_text(json.dumps(_run_for(context_path, candidate)), encoding="utf-8")
    with pytest.raises(wci.ContinuityIngestError, match="NEW must reference current only"):
        wci.validate_run(str(run_path), str(context_path))


def test_ingest_accepts_cross_round_persisting(context_path, tmp_path):
    _d, rounds, _ids, _hashes, _current = refs(context_path)
    candidate = item("PERSISTING", rounds[-1], rounds[0])
    run_path = tmp_path / "run.json"
    run_path.write_text(json.dumps(_run_for(context_path, candidate)), encoding="utf-8")
    data, _dt = wci.validate_run(str(run_path), str(context_path))
    assert data["memory_eligible"] is False
