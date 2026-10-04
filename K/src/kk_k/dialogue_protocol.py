from __future__ import annotations

import json
from dataclasses import dataclass

CONFIDENCE = frozenset({"LOW", "MEDIUM", "HIGH"})
RISK_FLAGS = frozenset(
    {"UNSUPPORTED_FACT", "AUTHORITY_CONFUSION", "EXECUTION_CONFUSION", "MEMORY_CONFLICT", "NONE"}
)
RESPONSE_TYPES = frozenset({"ANSWER", "CLARIFY", "DECLINE"})
A_KEYS = frozenset({"schema", "draft", "confidence"})
B_KEYS = frozenset({"schema", "critique", "risk_flags", "confidence"})
C_KEYS = frozenset({"schema", "answer", "confidence", "response_type"})
MAX_CONTEXT_BYTES = 65536

class DialogueError(ValueError):
    pass

@dataclass(frozen=True)
class DialogueA:
    draft: str
    confidence: str

@dataclass(frozen=True)
class DialogueB:
    critique: str
    risk_flags: tuple[str, ...]
    confidence: str

@dataclass(frozen=True)
class DialogueC:
    answer: str
    confidence: str
    response_type: str

@dataclass(frozen=True)
class DialogueDecision:
    soul_a: DialogueA
    soul_b: DialogueB
    soul_c: DialogueC
    a_sha256: str
    b_sha256: str
    c_sha256: str
    judge_verdict: str
    cognitive_route: str
    deterministic_guard: str
    a_initial_sha256: str
    proposer_retry: int
    a_initial_missing: tuple[str, ...]
    a_final_missing: tuple[str, ...]
    identity_retry: int
    identity_engine: str

def _strict(raw: object, keys: frozenset[str], schema: str) -> dict:
    if not isinstance(raw, str) or len(raw.encode("utf-8")) > 8192:
        raise DialogueError("invalid dialogue soul output")

    def hook(pairs):
        out = {}
        for k, v in pairs:
            if k in out:
                raise DialogueError("duplicate dialogue key")
            out[k] = v
        return out

    try:
        v = json.loads(raw, object_pairs_hook=hook)
    except DialogueError:
        raise
    except Exception as exc:
        raise DialogueError("invalid dialogue JSON") from exc
    if not isinstance(v, dict) or frozenset(v) != keys or v.get("schema") != schema:
        raise DialogueError("exact dialogue schema required")
    return v

def _text(v: object, max_bytes: int, label: str) -> str:
    if not isinstance(v, str) or not v.strip() or len(v.encode("utf-8")) > max_bytes:
        raise DialogueError("invalid " + label)
    if "\x00" in v:
        raise DialogueError("NUL in " + label)
    return v.strip()

def parse_a(raw: object) -> DialogueA:
    v = _strict(raw, A_KEYS, "FKP03.SOUL_A_DIALOGUE.1")
    if v["confidence"] not in CONFIDENCE:
        raise DialogueError("invalid A confidence")
    return DialogueA(_text(v["draft"], 1536, "A draft"), v["confidence"])

def parse_b(raw: object) -> DialogueB:
    v = _strict(raw, B_KEYS, "FKP03.SOUL_B_DIALOGUE.1")
    if v["confidence"] not in CONFIDENCE:
        raise DialogueError("invalid B confidence")
    flags = v["risk_flags"]
    if (
        not isinstance(flags, list)
        or not (1 <= len(flags) <= 4)
        or any(x not in RISK_FLAGS for x in flags)
        or len(set(flags)) != len(flags)
    ):
        raise DialogueError("invalid risk flags")
    if "NONE" in flags and len(flags) != 1:
        raise DialogueError("NONE cannot mix with risk flags")
    return DialogueB(_text(v["critique"], 1024, "B critique"), tuple(flags), v["confidence"])

def parse_c(raw: object) -> DialogueC:
    v = _strict(raw, C_KEYS, "FKP03.SOUL_C_DIALOGUE.1")
    if v["confidence"] not in CONFIDENCE or v["response_type"] not in RESPONSE_TYPES:
        raise DialogueError("invalid C enum")
    return DialogueC(_text(v["answer"], 1536, "C answer"), v["confidence"], v["response_type"])

def _canon(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
