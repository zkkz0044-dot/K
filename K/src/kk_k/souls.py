from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Callable

from .action_registry import ALLOWED_ACTIONS

MAX_CONTEXT_BYTES = 32768
MAX_OUTPUT_BYTES = 8192
MAX_ASSESSMENT_BYTES = 2048
MAX_ACTIONS = 5
CONFIDENCE = frozenset({"LOW", "MEDIUM", "HIGH"})
A_KEYS = frozenset({"schema", "assessment", "confidence", "candidate_actions"})
B_KEYS = frozenset({"schema", "assessment", "confidence", "blocked_actions"})
C_KEYS = frozenset({"schema", "assessment", "confidence", "selected_action_id"})


class SoulsError(ValueError):
    pass


@dataclass(frozen=True)
class SoulAResult:
    assessment: str
    confidence: str
    candidate_actions: tuple[str, ...]


@dataclass(frozen=True)
class SoulBResult:
    assessment: str
    confidence: str
    blocked_actions: tuple[str, ...]


@dataclass(frozen=True)
class SoulCResult:
    assessment: str
    confidence: str
    selected_action_id: str


@dataclass(frozen=True)
class SoulDecision:
    selected_action_id: str
    soul_a: SoulAResult
    soul_b: SoulBResult
    soul_c: SoulCResult


def _strict_object(raw: object, keys: frozenset[str], schema: str) -> dict:
    if not isinstance(raw, str) or len(raw.encode("utf-8")) > MAX_OUTPUT_BYTES:
        raise SoulsError("invalid soul output")

    def hook(pairs):
        out = {}
        for key, value in pairs:
            if key in out:
                raise SoulsError("duplicate JSON key")
            out[key] = value
        return out

    try:
        value = json.loads(raw, object_pairs_hook=hook)
    except SoulsError:
        raise
    except (json.JSONDecodeError, TypeError) as exc:
        raise SoulsError("invalid soul JSON") from exc
    if not isinstance(value, dict) or frozenset(value) != keys:
        raise SoulsError("exact soul fields required")
    if value["schema"] != schema:
        raise SoulsError("unsupported soul schema")
    assessment = value["assessment"]
    confidence = value["confidence"]
    if not isinstance(assessment, str) or len(assessment.encode("utf-8")) > MAX_ASSESSMENT_BYTES:
        raise SoulsError("invalid soul assessment")
    if confidence not in CONFIDENCE:
        raise SoulsError("invalid soul confidence")
    return value


def _action_list(value: object, label: str) -> tuple[str, ...]:
    if not isinstance(value, list) or len(value) > MAX_ACTIONS:
        raise SoulsError(f"invalid {label}")
    if any(not isinstance(item, str) or item not in ALLOWED_ACTIONS for item in value):
        raise SoulsError(f"unknown action in {label}")
    if len(set(value)) != len(value):
        raise SoulsError(f"duplicate action in {label}")
    return tuple(value)


def parse_soul_a(raw: object) -> SoulAResult:
    value = _strict_object(raw, A_KEYS, "KS01.SOUL_A.1")
    actions = _action_list(value["candidate_actions"], "candidate_actions")
    if not actions:
        raise SoulsError("Soul A must propose at least one candidate action")
    return SoulAResult(value["assessment"], value["confidence"], actions)


def parse_soul_b(raw: object, candidates: tuple[str, ...]) -> SoulBResult:
    value = _strict_object(raw, B_KEYS, "KS01.SOUL_B.1")
    blocked = _action_list(value["blocked_actions"], "blocked_actions")
    if not set(blocked) <= set(candidates):
        raise SoulsError("Soul B may block only Soul A candidates")
    return SoulBResult(value["assessment"], value["confidence"], blocked)


def parse_soul_c(raw: object, candidates: tuple[str, ...]) -> SoulCResult:
    value = _strict_object(raw, C_KEYS, "KS01.SOUL_C.1")
    selected = value["selected_action_id"]
    if not isinstance(selected, str) or selected not in ALLOWED_ACTIONS:
        raise SoulsError("unknown Soul C action")
    if selected != "A05_NO_ACTION" and selected not in candidates:
        raise SoulsError("Soul C selected action outside Soul A candidates")
    return SoulCResult(value["assessment"], value["confidence"], selected)


def _call_once(provider: Callable[[str], object], prompt: str) -> object:
    if not callable(provider):
        raise SoulsError("soul provider unavailable")
    try:
        return provider(prompt)
    except Exception as exc:
        raise SoulsError("soul provider failed") from exc


def deliberate(
    *,
    context: str,
    soul_a_provider: Callable[[str], object],
    soul_b_provider: Callable[[str], object],
    soul_c_provider: Callable[[str], object],
) -> SoulDecision:
    if not isinstance(context, str) or len(context.encode("utf-8")) > MAX_CONTEXT_BYTES:
        raise SoulsError("invalid soul context")

    a_prompt = "ROLE=SOUL_A\nUNTRUSTED_CANDIDATE_ONLY\n" + context
    a = parse_soul_a(_call_once(soul_a_provider, a_prompt))
    a_public = json.dumps(
        {
            "assessment": a.assessment,
            "confidence": a.confidence,
            "candidate_actions": list(a.candidate_actions),
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )

    b_prompt = "ROLE=SOUL_B\nCRITIQUE_ONLY\nCONTEXT:\n" + context + "\nSOUL_A:\n" + a_public
    b = parse_soul_b(_call_once(soul_b_provider, b_prompt), a.candidate_actions)
    b_public = json.dumps(
        {
            "assessment": b.assessment,
            "confidence": b.confidence,
            "blocked_actions": list(b.blocked_actions),
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )

    c_prompt = (
        "ROLE=SOUL_C\nINTERNAL_JUDGE_ONLY\nCONTEXT:\n"
        + context
        + "\nSOUL_A:\n"
        + a_public
        + "\nSOUL_B:\n"
        + b_public
    )
    c = parse_soul_c(_call_once(soul_c_provider, c_prompt), a.candidate_actions)
    return SoulDecision(c.selected_action_id, a, b, c)
