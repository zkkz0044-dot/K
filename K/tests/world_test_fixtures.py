from __future__ import annotations

import importlib.util
import json
from pathlib import Path


def synthetic_continuity_context() -> dict:
    old_sha = "1" * 64
    current_sha = "2" * 64
    old_id = "synthetic-old-001"
    current_id = "synthetic-current-001"
    return {
        "schema": "K.WORLD.CONTINUITY.CONTEXT.1",
        "generated_at": "2026-09-02T00:00:00+00:00",
        "authority": "EVIDENCE_ONLY",
        "memory_eligible": False,
        "rounds": [
            {
                "observed_at": "2026-09-01T00:00:00+00:00",
                "round_context_sha256": old_sha,
                "evidence": [{
                    "evidence_id": old_id,
                    "topic": "example_topic",
                    "title": "Synthetic prior observation",
                    "source_host": "example.com",
                    "observed_at": "2026-09-01T00:00:00+00:00",
                }],
                "judged_at": "2026-09-01T00:01:00+00:00",
                "judgment_sha256": "a" * 64,
                "judgment_status": "APPROVED_PROVISIONAL",
                "assessment": "Synthetic prior provisional assessment.",
                "priority_evidence_ids": [old_id],
                "corroborate_evidence_ids": [],
            },
            {
                "observed_at": "2026-09-02T00:00:00+00:00",
                "round_context_sha256": current_sha,
                "evidence": [{
                    "evidence_id": current_id,
                    "topic": "example_topic",
                    "title": "Synthetic current observation",
                    "source_host": "example.org",
                    "observed_at": "2026-09-02T00:00:00+00:00",
                }],
                "judged_at": "2026-09-02T00:01:00+00:00",
                "judgment_sha256": "b" * 64,
                "judgment_status": "APPROVED_PROVISIONAL",
                "assessment": "Synthetic current provisional assessment.",
                "priority_evidence_ids": [current_id],
                "corroborate_evidence_ids": [old_id],
            },
        ],
    }


def write_continuity_context(tmp_path: Path) -> Path:
    path = tmp_path / "continuity-context.json"
    path.write_text(
        json.dumps(synthetic_continuity_context(), ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )
    return path


def load_repo_tool(name: str):
    path = Path(__file__).resolve().parents[1] / "tools" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load test tool: {name}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
