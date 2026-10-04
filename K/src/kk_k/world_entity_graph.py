from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
import pathlib
import re
import unicodedata

STATE_SCHEMA = "K.WORLD.ENTITY_GRAPH.STATE.1"
UPDATE_SCHEMA = "K.WORLD.ENTITY_GRAPH.UPDATE.1"
CONTEXT_SCHEMA = "K.WORLD.ENTITY_GRAPH.CONTEXT.1"
AUTHORITY = "DERIVED_OBSERVATION_GRAPH_ONLY"
TRUTH_STATUS = "UNVERIFIED"
MAX_ENTITIES = 512
MAX_RELATIONS = 2048
MAX_EVIDENCE_PER_EDGE = 32
MAX_SOURCE_GROUPS = 16
MAX_AGE_DAYS = 90

_ENTITY_KINDS = frozenset({"EVIDENCE", "SOURCE", "TOPIC", "EVENT", "NAMED_CANDIDATE"})
_PREDICATES = frozenset(
    {"FROM_SOURCE", "ABOUT_TOPIC", "UPDATES_EVENT", "MENTIONS", "CO_MENTIONED_WITH"}
)
_CAPITAL_PHRASE = re.compile(
    r"\b(?:[A-Z][A-Za-z0-9&.'-]{1,40}|[A-Z]{2,12})(?:\s+(?:[A-Z][A-Za-z0-9&.'-]{1,40}|[A-Z]{2,12})){0,4}\b"
)
_STOP_NAMES = frozenset(
    {
        "Reuters",
        "AP",
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
        "Sunday",
        "September",
        "October",
        "November",
        "December",
        "January",
        "February",
        "March",
        "April",
        "May",
        "June",
        "July",
        "August",
        "New",
        "Latest",
        "World",
        "Today",
    }
)


class WorldEntityGraphError(ValueError):
    pass


def _canon(obj: object) -> bytes:
    try:
        return (
            json.dumps(
                obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
            )
            + "\n"
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise WorldEntityGraphError("non-canonical graph value") from exc


def _atomic(path: pathlib.Path, obj: object) -> str:
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = _canon(obj)
    tmp = path.parent / ("." + path.name + ".tmp")
    tmp.write_bytes(raw)
    os.chmod(tmp, 0o644)
    os.replace(tmp, path)
    return hashlib.sha256(raw).hexdigest()


def _norm(value: object) -> str:
    return " ".join(unicodedata.normalize("NFKC", str(value or "")).casefold().split())


def _parse_time(value: object) -> datetime | None:
    try:
        dt = datetime.fromisoformat(str(value))
    except Exception:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _bounded_union(old, new, limit: int):
    out = []
    for value in list(old or []) + list(new or []):
        if value not in (None, "") and value not in out:
            out.append(value)
    return out[-limit:]


def _entity_id(kind: str, label: str) -> str:
    if kind not in _ENTITY_KINDS:
        raise WorldEntityGraphError("invalid entity kind")
    return "ent-" + hashlib.sha256((kind + "|" + _norm(label)).encode("utf-8")).hexdigest()[:20]


def _relation_id(subject_id: str, predicate: str, object_id: str) -> str:
    if predicate not in _PREDICATES:
        raise WorldEntityGraphError("invalid graph predicate")
    if predicate == "CO_MENTIONED_WITH" and object_id < subject_id:
        subject_id, object_id = object_id, subject_id
    return (
        "rel-"
        + hashlib.sha256(
            (subject_id + "|" + predicate + "|" + object_id).encode("utf-8")
        ).hexdigest()[:20]
    )


def _empty_state() -> dict:
    return {
        "schema": STATE_SCHEMA,
        "updated_at": None,
        "authority": AUTHORITY,
        "truth_status": TRUTH_STATUS,
        "memory_eligible": False,
        "entities": [],
        "relations": [],
    }


def _validate_entity(value: object) -> dict:
    keys = {
        "entity_id",
        "kind",
        "label",
        "aliases",
        "first_seen",
        "last_seen",
        "evidence_ids",
        "source_groups",
        "mentions",
    }
    if not isinstance(value, dict) or set(value) != keys:
        raise WorldEntityGraphError("invalid entity fields")
    if value.get("kind") not in _ENTITY_KINDS:
        raise WorldEntityGraphError("invalid entity kind")
    label = value.get("label")
    if not isinstance(label, str) or not label.strip() or len(label.encode("utf-8")) > 300:
        raise WorldEntityGraphError("invalid entity label")
    if value.get("entity_id") != _entity_id(value["kind"], label):
        raise WorldEntityGraphError("entity id mismatch")
    aliases = value.get("aliases")
    if (
        not isinstance(aliases, list)
        or len(aliases) > 12
        or any(not isinstance(x, str) or not x for x in aliases)
    ):
        raise WorldEntityGraphError("invalid aliases")
    first = _parse_time(value.get("first_seen"))
    last = _parse_time(value.get("last_seen"))
    if first is None or last is None or first > last:
        raise WorldEntityGraphError("invalid entity time")
    evidence = value.get("evidence_ids")
    groups = value.get("source_groups")
    if (
        not isinstance(evidence, list)
        or len(evidence) > MAX_EVIDENCE_PER_EDGE
        or any(not isinstance(x, str) or not x for x in evidence)
    ):
        raise WorldEntityGraphError("invalid entity evidence")
    if (
        not isinstance(groups, list)
        or len(groups) > MAX_SOURCE_GROUPS
        or any(not isinstance(x, str) or not x for x in groups)
    ):
        raise WorldEntityGraphError("invalid entity source groups")
    if type(value.get("mentions")) is not int or value["mentions"] < 1:
        raise WorldEntityGraphError("invalid entity mentions")
    return dict(value)


def _validate_relation(value: object) -> dict:
    keys = {
        "relation_id",
        "subject_id",
        "predicate",
        "object_id",
        "first_seen",
        "last_seen",
        "observation_window",
        "status",
        "evidence_ids",
        "source_groups",
        "source_classes",
        "lineage_sha256",
    }
    if not isinstance(value, dict) or set(value) != keys:
        raise WorldEntityGraphError("invalid relation fields")
    predicate = value.get("predicate")
    if predicate not in _PREDICATES:
        raise WorldEntityGraphError("invalid relation predicate")
    sid = value.get("subject_id")
    oid = value.get("object_id")
    if (
        not isinstance(sid, str)
        or not isinstance(oid, str)
        or not sid.startswith("ent-")
        or not oid.startswith("ent-")
        or sid == oid
    ):
        raise WorldEntityGraphError("invalid relation endpoints")
    if value.get("relation_id") != _relation_id(sid, predicate, oid):
        raise WorldEntityGraphError("relation id mismatch")
    first = _parse_time(value.get("first_seen"))
    last = _parse_time(value.get("last_seen"))
    if first is None or last is None or first > last:
        raise WorldEntityGraphError("invalid relation time")
    window = value.get("observation_window")
    if (
        not isinstance(window, dict)
        or set(window) != {"mode", "from", "until"}
        or window.get("mode") != "OBSERVATION_WINDOW_ONLY"
    ):
        raise WorldEntityGraphError("invalid observation window")
    wfrom = _parse_time(window.get("from"))
    wuntil = _parse_time(window.get("until"))
    if wfrom is None or wuntil is None or wfrom != first or wuntil != last:
        raise WorldEntityGraphError("invalid observation window time")
    if value.get("status") not in {"UNVERIFIED_CANDIDATE", "CORROBORATED_MENTION", "STALE"}:
        raise WorldEntityGraphError("invalid relation status")
    evidence = value.get("evidence_ids")
    groups = value.get("source_groups")
    classes = value.get("source_classes")
    if not isinstance(evidence, list) or not evidence or len(evidence) > MAX_EVIDENCE_PER_EDGE:
        raise WorldEntityGraphError("invalid relation evidence")
    if not isinstance(groups, list) or not groups or len(groups) > MAX_SOURCE_GROUPS:
        raise WorldEntityGraphError("invalid relation source groups")
    if not isinstance(classes, list) or len(classes) > 8:
        raise WorldEntityGraphError("invalid relation source classes")
    lineage = value.get("lineage_sha256")
    if not isinstance(lineage, str) or re.fullmatch(r"[0-9a-f]{64}", lineage) is None:
        raise WorldEntityGraphError("invalid relation lineage")
    if lineage != _lineage_sha(evidence, groups, classes):
        raise WorldEntityGraphError("relation lineage mismatch")
    return dict(value)


def load_state(path=None) -> dict:
    if path is None:
        candidates = [
            pathlib.Path("/run/kk-k-ro/world/entity_graph/current.json"),
            pathlib.Path("/root/K/K/world/entity_graph/current.json"),
        ]
        path = next((p for p in candidates if p.is_file()), None)
        if path is None:
            return _empty_state()
    else:
        path = pathlib.Path(path)
        if not path.is_file():
            return _empty_state()
    raw = path.read_bytes()
    if not raw or len(raw) > 2_000_000:
        raise WorldEntityGraphError("invalid graph state size")
    try:
        state = json.loads(raw)
    except Exception as exc:
        raise WorldEntityGraphError("invalid graph JSON") from exc
    if not isinstance(state, dict) or set(state) != {
        "schema",
        "updated_at",
        "authority",
        "truth_status",
        "memory_eligible",
        "entities",
        "relations",
    }:
        raise WorldEntityGraphError("invalid graph envelope")
    if (
        state.get("schema") != STATE_SCHEMA
        or state.get("authority") != AUTHORITY
        or state.get("truth_status") != TRUTH_STATUS
        or state.get("memory_eligible") is not False
    ):
        raise WorldEntityGraphError("invalid graph policy")
    entities = state.get("entities")
    relations = state.get("relations")
    if (
        not isinstance(entities, list)
        or len(entities) > MAX_ENTITIES
        or not isinstance(relations, list)
        or len(relations) > MAX_RELATIONS
    ):
        raise WorldEntityGraphError("invalid graph collection")
    entity_ids = set()
    for entity in entities:
        checked = _validate_entity(entity)
        if checked["entity_id"] in entity_ids:
            raise WorldEntityGraphError("duplicate entity")
        entity_ids.add(checked["entity_id"])
    relation_ids = set()
    for relation in relations:
        checked = _validate_relation(relation)
        if checked["relation_id"] in relation_ids:
            raise WorldEntityGraphError("duplicate relation")
        relation_ids.add(checked["relation_id"])
        if checked["subject_id"] not in entity_ids or checked["object_id"] not in entity_ids:
            raise WorldEntityGraphError("dangling relation")
    return state


def _named_candidates(item: dict) -> list[str]:
    out = []
    seen = set()
    # Title and snippet are independent evidence fields. Never let the regex
    # create a synthetic multi-token entity across their boundary.
    for field in ("title", "snippet"):
        text = str(item.get(field) or "").strip()
        for match in _CAPITAL_PHRASE.findall(text):
            label = " ".join(match.split()).strip(" ,.;:")
            if label in _STOP_NAMES or len(label) < 2 or len(label.encode("utf-8")) > 160:
                continue
            key = _norm(label)
            if key in seen:
                continue
            seen.add(key)
            out.append(label)
            if len(out) >= 12:
                return out
    return out


def _lineage_sha(evidence_ids, source_groups, source_classes) -> str:
    payload = {
        "evidence_ids": sorted(set(evidence_ids)),
        "source_groups": sorted(set(source_groups)),
        "source_classes": sorted(set(source_classes)),
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _touch_entity(
    by_id: dict, *, kind: str, label: str, observed_at: str, evidence_id: str, source_group: str
) -> str:
    eid = _entity_id(kind, label)
    entity = by_id.get(eid)
    if entity is None:
        entity = {
            "entity_id": eid,
            "kind": kind,
            "label": label,
            "aliases": [label],
            "first_seen": observed_at,
            "last_seen": observed_at,
            "evidence_ids": [evidence_id],
            "source_groups": [source_group],
            "mentions": 1,
        }
        by_id[eid] = entity
    else:
        entity["aliases"] = _bounded_union(entity.get("aliases"), [label], 12)
        entity["last_seen"] = max(str(entity.get("last_seen")), observed_at)
        entity["first_seen"] = min(str(entity.get("first_seen")), observed_at)
        entity["evidence_ids"] = _bounded_union(
            entity.get("evidence_ids"), [evidence_id], MAX_EVIDENCE_PER_EDGE
        )
        entity["source_groups"] = _bounded_union(
            entity.get("source_groups"), [source_group], MAX_SOURCE_GROUPS
        )
        entity["mentions"] = int(entity.get("mentions", 0)) + 1
    return eid


def _touch_relation(
    by_id: dict,
    *,
    subject_id: str,
    predicate: str,
    object_id: str,
    observed_at: str,
    evidence_id: str,
    source_group: str,
    source_class: str,
) -> str:
    rid = _relation_id(subject_id, predicate, object_id)
    relation = by_id.get(rid)
    if relation is None:
        relation = {
            "relation_id": rid,
            "subject_id": subject_id,
            "predicate": predicate,
            "object_id": object_id,
            "first_seen": observed_at,
            "last_seen": observed_at,
            "observation_window": {
                "mode": "OBSERVATION_WINDOW_ONLY",
                "from": observed_at,
                "until": observed_at,
            },
            "status": "UNVERIFIED_CANDIDATE",
            "evidence_ids": [evidence_id],
            "source_groups": [source_group],
            "source_classes": [source_class],
            "lineage_sha256": "",
        }
        by_id[rid] = relation
    else:
        relation["first_seen"] = min(str(relation.get("first_seen")), observed_at)
        relation["last_seen"] = max(str(relation.get("last_seen")), observed_at)
        relation["observation_window"] = {
            "mode": "OBSERVATION_WINDOW_ONLY",
            "from": relation["first_seen"],
            "until": relation["last_seen"],
        }
        relation["evidence_ids"] = _bounded_union(
            relation.get("evidence_ids"), [evidence_id], MAX_EVIDENCE_PER_EDGE
        )
        relation["source_groups"] = _bounded_union(
            relation.get("source_groups"), [source_group], MAX_SOURCE_GROUPS
        )
        relation["source_classes"] = _bounded_union(
            relation.get("source_classes"), [source_class], 8
        )
    independent_groups = {
        str(x).strip().casefold()
        for x in relation["source_groups"]
        if str(x).strip() and str(x).strip().casefold() not in {"unknown", "legacy_unknown"}
    }
    relation["status"] = (
        "CORROBORATED_MENTION" if len(independent_groups) >= 2 else "UNVERIFIED_CANDIDATE"
    )
    relation["lineage_sha256"] = _lineage_sha(
        relation["evidence_ids"], relation["source_groups"], relation["source_classes"]
    )
    return rid


def _mark_stale(relations: list[dict], now: datetime) -> None:
    for relation in relations:
        last = _parse_time(relation.get("last_seen"))
        if last and (now - last.astimezone(timezone.utc)).total_seconds() > MAX_AGE_DAYS * 86400:
            relation["status"] = "STALE"


def apply_observations(items: list[dict], state_dir, updates_dir, now=None) -> dict:
    if not isinstance(items, list) or len(items) > 64:
        raise WorldEntityGraphError("invalid observation collection")
    now = now or datetime.now(timezone.utc)
    state_dir = pathlib.Path(state_dir)
    updates_dir = pathlib.Path(updates_dir)
    state_path = state_dir / "current.json"
    state = load_state(state_path)
    entities = {x["entity_id"]: dict(x) for x in state["entities"]}
    relations = {x["relation_id"]: dict(x) for x in state["relations"]}
    update_paths = []
    processed = 0
    skipped = 0
    seen_batch = set()
    for item in items:
        if not isinstance(item, dict):
            raise WorldEntityGraphError("invalid observation item")
        if item.get("status") != "OBSERVED_UNVERIFIED" or item.get("memory_eligible") is not False:
            raise WorldEntityGraphError("observation trust escalation")
        evidence_id = item.get("evidence_id")
        observed_at = str(item.get("observed_at") or now.isoformat())
        if (
            not isinstance(evidence_id, str)
            or not evidence_id
            or len(evidence_id.encode("utf-8")) > 128
            or "\x00" in evidence_id
            or _parse_time(observed_at) is None
        ):
            raise WorldEntityGraphError("invalid observation identity/time")
        if evidence_id in seen_batch:
            raise WorldEntityGraphError("duplicate observation evidence id")
        seen_batch.add(evidence_id)
        if _entity_id("EVIDENCE", evidence_id) in entities:
            skipped += 1
            continue
        source_group = str(
            item.get("independence_group") or item.get("source_host") or "unknown"
        ).strip()
        source_class = str(item.get("source_class") or "LEGACY_UNKNOWN").strip()
        topic = str(item.get("topic") or "unknown").strip()
        source_label = str(item.get("source_host") or source_group or "unknown").strip()
        if (
            not source_group
            or len(source_group.encode("utf-8")) > 240
            or not source_class
            or len(source_class.encode("utf-8")) > 80
            or not topic
            or len(topic.encode("utf-8")) > 160
            or not source_label
            or len(source_label.encode("utf-8")) > 240
        ):
            raise WorldEntityGraphError("invalid observation labels")
        event_candidate = (
            item.get("event_candidate") if isinstance(item.get("event_candidate"), dict) else {}
        )
        event_label = str(event_candidate.get("event_id") or "")
        evidence_eid = _touch_entity(
            entities,
            kind="EVIDENCE",
            label=evidence_id,
            observed_at=observed_at,
            evidence_id=evidence_id,
            source_group=source_group,
        )
        source_eid = _touch_entity(
            entities,
            kind="SOURCE",
            label=source_label,
            observed_at=observed_at,
            evidence_id=evidence_id,
            source_group=source_group,
        )
        topic_eid = _touch_entity(
            entities,
            kind="TOPIC",
            label=topic,
            observed_at=observed_at,
            evidence_id=evidence_id,
            source_group=source_group,
        )
        touched = [
            _touch_relation(
                relations,
                subject_id=evidence_eid,
                predicate="FROM_SOURCE",
                object_id=source_eid,
                observed_at=observed_at,
                evidence_id=evidence_id,
                source_group=source_group,
                source_class=source_class,
            ),
            _touch_relation(
                relations,
                subject_id=evidence_eid,
                predicate="ABOUT_TOPIC",
                object_id=topic_eid,
                observed_at=observed_at,
                evidence_id=evidence_id,
                source_group=source_group,
                source_class=source_class,
            ),
        ]
        if event_label:
            event_eid = _touch_entity(
                entities,
                kind="EVENT",
                label=event_label,
                observed_at=observed_at,
                evidence_id=evidence_id,
                source_group=source_group,
            )
            touched.append(
                _touch_relation(
                    relations,
                    subject_id=evidence_eid,
                    predicate="UPDATES_EVENT",
                    object_id=event_eid,
                    observed_at=observed_at,
                    evidence_id=evidence_id,
                    source_group=source_group,
                    source_class=source_class,
                )
            )
        named_ids = []
        for label in _named_candidates(item):
            named_id = _touch_entity(
                entities,
                kind="NAMED_CANDIDATE",
                label=label,
                observed_at=observed_at,
                evidence_id=evidence_id,
                source_group=source_group,
            )
            if named_id in named_ids:
                continue
            named_ids.append(named_id)
            touched.append(
                _touch_relation(
                    relations,
                    subject_id=evidence_eid,
                    predicate="MENTIONS",
                    object_id=named_id,
                    observed_at=observed_at,
                    evidence_id=evidence_id,
                    source_group=source_group,
                    source_class=source_class,
                )
            )
        for i in range(len(named_ids)):
            for j in range(i + 1, len(named_ids)):
                touched.append(
                    _touch_relation(
                        relations,
                        subject_id=named_ids[i],
                        predicate="CO_MENTIONED_WITH",
                        object_id=named_ids[j],
                        observed_at=observed_at,
                        evidence_id=evidence_id,
                        source_group=source_group,
                        source_class=source_class,
                    )
                )
        update = {
            "schema": UPDATE_SCHEMA,
            "updated_at": now.isoformat(),
            "evidence_id": evidence_id,
            "entity_ids": sorted(set([evidence_eid, source_eid, topic_eid] + named_ids)),
            "relation_ids": sorted(set(touched)),
            "authority": AUTHORITY,
            "truth_status": TRUTH_STATUS,
            "memory_eligible": False,
        }
        target = updates_dir / f"{now.strftime('%Y%m%dT%H%M%SZ')}-{evidence_id[:24]}.json"
        _atomic(target, update)
        update_paths.append(str(target))
        processed += 1
    entity_list = list(entities.values())
    relation_list = list(relations.values())
    _mark_stale(relation_list, now)
    entity_list.sort(key=lambda x: (str(x.get("last_seen")), x["entity_id"]), reverse=True)
    relation_list.sort(key=lambda x: (str(x.get("last_seen")), x["relation_id"]), reverse=True)
    entity_list = entity_list[:MAX_ENTITIES]
    keep_ids = {x["entity_id"] for x in entity_list}
    relation_list = [
        x for x in relation_list if x["subject_id"] in keep_ids and x["object_id"] in keep_ids
    ][:MAX_RELATIONS]
    if processed == 0 and entity_list == state["entities"] and relation_list == state["relations"]:
        return {
            "state": str(state_path),
            "updates": update_paths,
            "entities": len(entity_list),
            "relations": len(relation_list),
            "processed": 0,
            "skipped": skipped,
        }
    new_state = {
        "schema": STATE_SCHEMA,
        "updated_at": now.isoformat(),
        "authority": AUTHORITY,
        "truth_status": TRUTH_STATUS,
        "memory_eligible": False,
        "entities": entity_list,
        "relations": relation_list,
    }
    _atomic(state_path, new_state)
    load_state(state_path)
    return {
        "state": str(state_path),
        "updates": update_paths,
        "entities": len(entity_list),
        "relations": len(relation_list),
        "processed": processed,
        "skipped": skipped,
    }


def query_context(query: str, *, path=None, limit: int = 12) -> dict:
    if not isinstance(query, str) or not query.strip() or len(query.encode("utf-8")) > 512:
        raise WorldEntityGraphError("invalid graph query")
    if type(limit) is not int or not (1 <= limit <= 24):
        raise WorldEntityGraphError("invalid graph limit")
    state = load_state(path)
    q = _norm(query)
    q_tokens = set(re.findall(r"[a-z0-9][a-z0-9_.-]{1,63}|[\u4e00-\u9fff]{2,}", q))
    scored = []
    for entity in state["entities"]:
        text = _norm(entity["label"] + " " + " ".join(entity.get("aliases", [])))
        score = (50 if q and q in text else 0) + sum(5 for t in q_tokens if t in text)
        if score:
            scored.append((score, entity["last_seen"], entity))
    scored.sort(key=lambda x: (-x[0], str(x[1])), reverse=False)
    selected = [x[2] for x in scored[:limit]]
    ids = {x["entity_id"] for x in selected}
    relations = [r for r in state["relations"] if r["subject_id"] in ids or r["object_id"] in ids][
        : limit * 2
    ]
    return {
        "schema": CONTEXT_SCHEMA,
        "authority": AUTHORITY,
        "truth_status": TRUTH_STATUS,
        "memory_eligible": False,
        "entities": selected,
        "relations": relations,
    }
