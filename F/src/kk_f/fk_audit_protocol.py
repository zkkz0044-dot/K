from __future__ import annotations

import hashlib
import json
import re

MAX_REQUEST_BYTES = 4096
MAX_RESPONSE_BYTES = 16384
QUERY_KEYS = frozenset({"schema"})
HISTORY_KEYS = frozenset({"schema", "limit"})
RECALL_KEYS = frozenset({"schema", "query", "limit"})
PERSONALITY_KEYS = frozenset({"schema", "core_sha256", "core_state"})
PERSONALITY_COMMIT_KEYS = frozenset({"schema", "core_sha256", "core_state", "event"})
BELIEFS_KEYS = frozenset({"schema", "query", "limit"})
BELIEF_COMMIT_KEYS = frozenset({"schema", "event"})
SKILLS_KEYS = frozenset({"schema", "query", "limit"})
SKILL_COMMIT_KEYS = frozenset({"schema", "event"})
COMMIT_KEYS = frozenset({"schema", "event"})
RESERVED_COGNITIVE_SUBJECTS = frozenset(
    {"personality_revision", "belief_revision", "skill_revision"}
)
STABLE_REASONS = frozenset(
    {
        "GENERATION_MISMATCH",
        "PREV_DIGEST_MISMATCH",
        "EVENT_DIGEST_MISMATCH",
        "EVENT_INVALID",
        "WITNESS_INVALID",
        "WITNESS_WRITE_FAILED",
        "CANONICAL_LOG_INVALID",
        "CANONICAL_LOG_MISMATCH",
    }
)


class FKAuditGatewayError(ValueError):
    pass


def _strict_pairs(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise FKAuditGatewayError("duplicate JSON key")
        out[key] = value
    return out


def parse_request(raw: bytes) -> dict:
    if not isinstance(raw, bytes) or not raw or len(raw) > MAX_REQUEST_BYTES:
        raise FKAuditGatewayError("invalid request size")
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_strict_pairs)
    except FKAuditGatewayError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError) as exc:
        raise FKAuditGatewayError("invalid request JSON") from exc
    if not isinstance(value, dict):
        raise FKAuditGatewayError("request object required")
    schema = value.get("schema")
    if schema == "FK_AUDIT.QUERY.2":
        if frozenset(value) != QUERY_KEYS:
            raise FKAuditGatewayError("exact query fields required")
        return value
    if schema == "FK_AUDIT.HISTORY.2":
        if frozenset(value) != HISTORY_KEYS:
            raise FKAuditGatewayError("exact history fields required")
        if type(value["limit"]) is not int or not (1 <= value["limit"] <= 8):
            raise FKAuditGatewayError("invalid history limit")
        return value
    if schema == "FK_AUDIT.RECALL.2":
        if frozenset(value) != RECALL_KEYS:
            raise FKAuditGatewayError("exact recall fields required")
        query = value["query"]
        if not isinstance(query, str) or not query.strip() or len(query.encode("utf-8")) > 512:
            raise FKAuditGatewayError("invalid recall query")
        if type(value["limit"]) is not int or not (1 <= value["limit"] <= 4):
            raise FKAuditGatewayError("invalid recall limit")
        return value
    if schema == "FK_AUDIT.PERSONALITY.2":
        if frozenset(value) != PERSONALITY_KEYS:
            raise FKAuditGatewayError("exact personality fields required")
        if (
            not isinstance(value["core_sha256"], str)
            or re.fullmatch(r"[0-9a-f]{64}", value["core_sha256"]) is None
        ):
            raise FKAuditGatewayError("invalid personality core hash")
        if not isinstance(value["core_state"], dict):
            raise FKAuditGatewayError("invalid personality core state")
        core_raw = json.dumps(
            value["core_state"],
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
        if len(core_raw) > 8192 or hashlib.sha256(core_raw).hexdigest() != value["core_sha256"]:
            raise FKAuditGatewayError("personality core digest mismatch")
        return value
    if schema == "FK_AUDIT.PERSONALITY_COMMIT.2":
        if (
            frozenset(value) != PERSONALITY_COMMIT_KEYS
            or not isinstance(value.get("core_state"), dict)
            or not isinstance(value.get("event"), dict)
        ):
            raise FKAuditGatewayError("exact personality commit fields required")
        core_hash = value.get("core_sha256")
        if not isinstance(core_hash, str) or re.fullmatch(r"[0-9a-f]{64}", core_hash) is None:
            raise FKAuditGatewayError("invalid personality core hash")
        core_raw = json.dumps(
            value["core_state"],
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
        if len(core_raw) > 8192 or hashlib.sha256(core_raw).hexdigest() != core_hash:
            raise FKAuditGatewayError("personality core digest mismatch")
        return value
    if schema == "FK_AUDIT.BELIEFS.2":
        if frozenset(value) != BELIEFS_KEYS:
            raise FKAuditGatewayError("exact beliefs fields required")
        query = value.get("query")
        if not isinstance(query, str) or not query.strip() or len(query.encode("utf-8")) > 512:
            raise FKAuditGatewayError("invalid beliefs query")
        if type(value.get("limit")) is not int or not (1 <= value["limit"] <= 8):
            raise FKAuditGatewayError("invalid beliefs limit")
        return value
    if schema == "FK_AUDIT.BELIEF_COMMIT.2":
        if frozenset(value) != BELIEF_COMMIT_KEYS or not isinstance(value.get("event"), dict):
            raise FKAuditGatewayError("exact belief commit fields required")
        return value
    if schema == "FK_AUDIT.SKILLS.2":
        if frozenset(value) != SKILLS_KEYS:
            raise FKAuditGatewayError("exact skills fields required")
        query = value.get("query")
        if not isinstance(query, str) or not query.strip() or len(query.encode("utf-8")) > 512:
            raise FKAuditGatewayError("invalid skills query")
        if type(value.get("limit")) is not int or not (1 <= value["limit"] <= 8):
            raise FKAuditGatewayError("invalid skills limit")
        return value
    if schema == "FK_AUDIT.SKILL_COMMIT.2":
        if frozenset(value) != SKILL_COMMIT_KEYS or not isinstance(value.get("event"), dict):
            raise FKAuditGatewayError("exact skill commit fields required")
        return value
    if schema == "FK_AUDIT.COMMIT.2":
        if frozenset(value) != COMMIT_KEYS or not isinstance(value["event"], dict):
            raise FKAuditGatewayError("exact commit fields required")
        return value
    raise FKAuditGatewayError("unsupported audit request schema")
