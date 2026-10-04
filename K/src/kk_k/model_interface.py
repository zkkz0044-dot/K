from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Callable

from .action_registry import ALLOWED_ACTIONS

DELIBERATION_KEYS = frozenset({"schema", "assessment", "confidence", "candidate_actions"})
MAX_MODEL_OUTPUT_BYTES = 8192
MAX_PROMPT_BYTES = 32768


class ModelInterfaceError(ValueError):
    pass


@dataclass(frozen=True)
class Deliberation:
    assessment: str
    confidence: str
    candidate_actions: tuple[str, ...]


def _strict_json(raw: str) -> dict:
    def hook(pairs):
        out = {}
        for key, value in pairs:
            if key in out:
                raise ModelInterfaceError("duplicate JSON key")
            out[key] = value
        return out

    try:
        value = json.loads(raw, object_pairs_hook=hook)
    except ModelInterfaceError:
        raise
    except (json.JSONDecodeError, TypeError) as exc:
        raise ModelInterfaceError("invalid model JSON") from exc
    if not isinstance(value, dict) or frozenset(value) != DELIBERATION_KEYS:
        raise ModelInterfaceError("exact deliberation fields required")
    return value


def parse_deliberation(raw: object) -> Deliberation:
    if not isinstance(raw, str):
        raise ModelInterfaceError("model output must be text")
    if len(raw.encode("utf-8")) > MAX_MODEL_OUTPUT_BYTES:
        raise ModelInterfaceError("model output too large")
    v = _strict_json(raw)
    if v["schema"] != "K04.DELIBERATION.1":
        raise ModelInterfaceError("unsupported deliberation schema")
    if not isinstance(v["assessment"], str) or len(v["assessment"].encode("utf-8")) > 2048:
        raise ModelInterfaceError("invalid assessment")
    if v["confidence"] not in {"LOW", "MEDIUM", "HIGH"}:
        raise ModelInterfaceError("invalid confidence")
    actions = v["candidate_actions"]
    if not isinstance(actions, list) or not (1 <= len(actions) <= 5):
        raise ModelInterfaceError("invalid candidate action list")
    if any(not isinstance(x, str) or x not in ALLOWED_ACTIONS for x in actions):
        raise ModelInterfaceError("unknown candidate action")
    if len(set(actions)) != len(actions):
        raise ModelInterfaceError("duplicate candidate action")
    return Deliberation(v["assessment"], v["confidence"], tuple(actions))


def call_model_once(provider: Callable[[str], object], prompt: str) -> Deliberation:
    if not callable(provider):
        raise ModelInterfaceError("provider unavailable")
    if not isinstance(prompt, str) or len(prompt.encode("utf-8")) > MAX_PROMPT_BYTES:
        raise ModelInterfaceError("invalid prompt")
    try:
        raw = provider(prompt)
    except Exception as exc:
        raise ModelInterfaceError("provider call failed") from exc
    return parse_deliberation(raw)
