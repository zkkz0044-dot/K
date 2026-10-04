from __future__ import annotations

from dataclasses import dataclass
import re

FACT_KEYS = frozenset({"schema", "key", "value", "source_id", "observed_at", "ttl_seconds"})
KEY_RE = re.compile(r"^[a-z][a-z0-9_.-]{0,63}$")
SOURCE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,95}$")
MAX_TTL = 7 * 24 * 3600


class WorldStateError(ValueError):
    pass


def _exact(value: object, keys: frozenset[str], label: str) -> dict:
    if not isinstance(value, dict) or frozenset(value) != keys:
        raise WorldStateError(f"exact {label} fields required")
    return value


def validate_fact(value: object) -> dict:
    v = _exact(value, FACT_KEYS, "fact")
    if v["schema"] != "K03.FACT.1":
        raise WorldStateError("unsupported fact schema")
    if not isinstance(v["key"], str) or not KEY_RE.fullmatch(v["key"]):
        raise WorldStateError("invalid fact key")
    if not isinstance(v["value"], str) or len(v["value"].encode("utf-8")) > 1024:
        raise WorldStateError("invalid fact value")
    if not isinstance(v["source_id"], str) or not SOURCE_RE.fullmatch(v["source_id"]):
        raise WorldStateError("invalid source_id")
    if type(v["observed_at"]) is not int or v["observed_at"] < 0:
        raise WorldStateError("invalid observed_at")
    if type(v["ttl_seconds"]) is not int or not (0 <= v["ttl_seconds"] <= MAX_TTL):
        raise WorldStateError("invalid ttl")
    return dict(v)


def build_snapshot(facts: list[object], now_epoch: int) -> dict:
    if type(now_epoch) is not int or now_epoch < 0:
        raise WorldStateError("invalid snapshot time")
    if not isinstance(facts, list) or len(facts) > 256:
        raise WorldStateError("invalid fact collection")
    seen = set()
    out = []
    for raw in facts:
        f = validate_fact(raw)
        if f["key"] in seen:
            raise WorldStateError("duplicate fact key")
        seen.add(f["key"])
        expires_at = f["observed_at"] + f["ttl_seconds"]
        freshness = "FRESH" if now_epoch <= expires_at else "STALE"
        out.append(
            {
                "key": f["key"],
                "value": f["value"],
                "source_id": f["source_id"],
                "observed_at": f["observed_at"],
                "expires_at": expires_at,
                "freshness": freshness,
            }
        )
    out.sort(key=lambda x: x["key"])
    return {"schema": "K03.SNAPSHOT.1", "generated_at": now_epoch, "facts": out}


def lookup(snapshot: object, key: str) -> dict:
    if not isinstance(snapshot, dict) or frozenset(snapshot) != {"schema", "generated_at", "facts"}:
        raise WorldStateError("invalid snapshot")
    if (
        snapshot["schema"] != "K03.SNAPSHOT.1"
        or type(snapshot["generated_at"]) is not int
        or not isinstance(snapshot["facts"], list)
    ):
        raise WorldStateError("invalid snapshot")
    if not isinstance(key, str) or not KEY_RE.fullmatch(key):
        raise WorldStateError("invalid lookup key")
    for fact in snapshot["facts"]:
        if not isinstance(fact, dict) or frozenset(fact) != {
            "key",
            "value",
            "source_id",
            "observed_at",
            "expires_at",
            "freshness",
        }:
            raise WorldStateError("invalid snapshot fact")
        if fact["key"] == key:
            state = "KNOWN" if fact["freshness"] == "FRESH" else "STALE"
            return {
                "state": state,
                "value": fact["value"],
                "source_id": fact["source_id"],
                "observed_at": fact["observed_at"],
                "expires_at": fact["expires_at"],
            }
    return {"state": "UNKNOWN"}
