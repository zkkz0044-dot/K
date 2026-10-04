import json

import pytest

from kk_k import world_think as wt

SYNTHETIC_EVIDENCE = {
    "schema": "K.WORLD.EVIDENCE.SET.1",
    "observed_at": "2026-09-01T00:00:00+00:00",
    "authority": "EVIDENCE_ONLY",
    "policy": {
        "observed_is_believed": False,
        "search_result_is_long_term_memory": False,
    },
    "items": [
        {
            "evidence_id": "synthetic-evidence-001",
            "topic": "example_topic",
            "query": "example verification",
            "title": "Example observation",
            "snippet": "A synthetic unverified observation used only by tests.",
            "url": "https://example.com/observation",
            "source_host": "example.com",
            "source_published_at": "2026-09-01T00:00:00+00:00",
            "source_class": "PRIMARY_OFFICIAL",
            "source_priority": "HIGH",
            "independence_group": "example.com",
            "lineage_status": "DIRECT",
            "retrieval_tool": "synthetic_fixture",
            "observed_at": "2026-09-01T00:00:00+00:00",
            "status": "OBSERVED_UNVERIFIED",
            "memory_eligible": False,
        }
    ],
}


@pytest.fixture
def evidence_file(tmp_path):
    path = tmp_path / "world-evidence.json"
    path.write_text(json.dumps(SYNTHETIC_EVIDENCE, ensure_ascii=False), encoding="utf-8")
    return path

def provider_for(path):
    def provider(role, prompt):
        _d, _items, ids, _sha = wt.load_evidence(path)
        eid = sorted(ids)[0]
        thought = {
            "schema": "K.WORLD.THINK.1",
            "assessment": "这是一条普通的临时世界观察。",
            "notable_evidence_ids": [eid],
            "follow_up_queries": [
                {"query": "official source verification", "reason": "继续核实来源"}
            ],
        }
        return json.dumps(
            {
                "schema": "K.WORLD.THINK.MODEL.1",
                "thought_text": json.dumps(thought, ensure_ascii=False),
                "confidence": "LOW",
            },
            ensure_ascii=False,
        )

    return provider


def test_world_think_is_not_memory_or_approval(evidence_file):
    out = wt.think(str(evidence_file), provider=provider_for(evidence_file))
    assert out["schema"] == "K.WORLD.THINK.RUN.1"
    assert out["authority"] == "COGNITIVE_NOTE_ONLY"
    assert out["memory_eligible"] is False
    assert len(out["thought"]["follow_up_queries"]) <= 3


def test_unknown_evidence_id_rejected():
    with pytest.raises(wt.WorldThinkError):
        wt.parse_thought(
            json.dumps(
                {
                    "schema": "K.WORLD.THINK.1",
                    "assessment": "x",
                    "notable_evidence_ids": ["not-a-real-id"],
                    "follow_up_queries": [],
                }
            ),
            {"real-evidence-id"},
        )

def test_world_think_prompt_matches_bounded_search_capability(evidence_file):
    seen = {}

    def provider(role, prompt):
        seen["role"] = role
        seen["prompt"] = prompt
        _d, _items, ids, _sha = wt.load_evidence(evidence_file)
        thought = {
            "schema": "K.WORLD.THINK.1",
            "assessment": "临时观察。",
            "notable_evidence_ids": [sorted(ids)[0]],
            "follow_up_queries": [],
        }
        return json.dumps(
            {
                "schema": "K.WORLD.THINK.MODEL.1",
                "thought_text": json.dumps(thought, ensure_ascii=False),
                "confidence": "LOW",
            },
            ensure_ascii=False,
        )

    wt.think(str(evidence_file), provider=provider)
    assert seen["role"] == "WORLD_THINK"
    assert "不要使用site:" in seen["prompt"]
    assert "机构全名" in seen["prompt"]
    assert "受限关键词搜索" in seen["prompt"]
