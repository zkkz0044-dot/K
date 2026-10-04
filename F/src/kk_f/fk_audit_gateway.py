from __future__ import annotations

import heapq
import hashlib
import json
import os
import re
import socket
from collections import deque
from typing import Callable, Iterable

from .fk_peer_identity import (
    FKPeerIdentityError,
    authorize_peer,
    cgroup_contains_unit,
    peer_credentials,
)
from .conversation_index import (
    ConversationIndexError,
    append_event as index_append_event,
    matches_state as index_matches_state,
    rebuild_index as rebuild_conversation_index,
    recent_events as index_recent_events,
    recall_compact,
    recall_events as index_recall_events,
    recall_units,
)
from .k_audit_witness import (
    KAuditWitnessError,
    commit_event,
    initialize_state,
    load_state,
    load_canonical_events,
    iter_canonical_events,
    recover_canonical,
    recover_canonical_tail,
)

DEFAULT_ADDRESS = "\0kk-fk-audit-v2"
DEFAULT_STATE_PATH = "/root/K/F/evidence/fk/k_audit_witness_v2.json"
DEFAULT_LOG_PATH = "/root/K/F/evidence/fk/k_audit_events_v2.jsonl"
DEFAULT_INDEX_PATH = "/root/K/FK/runtime/k_conversation_index_v1.sqlite3"
from .fk_audit_protocol import (
    MAX_REQUEST_BYTES,
    MAX_RESPONSE_BYTES,
    RESERVED_COGNITIVE_SUBJECTS,
    STABLE_REASONS,
    FKAuditGatewayError,
    parse_request,
)

def _recv_line(conn: socket.socket) -> bytes:
    buf = bytearray()
    while True:
        chunk = conn.recv(min(512, MAX_REQUEST_BYTES + 1 - len(buf)))
        if not chunk:
            break
        buf.extend(chunk)
        if len(buf) > MAX_REQUEST_BYTES:
            raise FKAuditGatewayError("request too large")
        if b"\n" in chunk:
            break
    if not buf.endswith(b"\n"):
        raise FKAuditGatewayError("unterminated request")
    raw = bytes(buf[:-1])
    if b"\n" in raw:
        raise FKAuditGatewayError("multiple request frames")
    return raw


def _send(conn: socket.socket, value: dict) -> None:
    raw = (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"
    ).encode("utf-8")
    if len(raw) > MAX_RESPONSE_BYTES:
        raise FKAuditGatewayError("response too large")
    conn.sendall(raw)


def _state_receipt(outcome: str, state: dict) -> dict:
    return {
        "schema": "FK_AUDIT.RECEIPT.2",
        "outcome": outcome,
        "generation": state["generation"],
        "digest": state["digest"],
    }


def _veto(reason: str) -> dict:
    return {"schema": "FK_AUDIT.VETO.2", "outcome": "VETO", "reason_code": reason}


def _iter_completed_conversation_turns(events: Iterable[dict]):
    """Yield durable completed human->K turns; failed turns remain audit-only."""
    human_subjects = {"human_chat", "human_ask", "human_plan", "human_remember"}
    pending = []
    for event in events:
        subject = event.get("subject")
        if subject in human_subjects:
            pending.append(event)
        elif subject == "dialogue_error":
            pending = []
        elif subject == "k_reply":
            if pending:
                yield tuple(pending + [event])
                pending = []


def _completed_conversation_turns(events: Iterable[dict]) -> list[tuple[dict, ...]]:
    return list(_iter_completed_conversation_turns(events))


def _completed_conversation_events(events: Iterable[dict]) -> list[dict]:
    return [event for turn in _iter_completed_conversation_turns(events) for event in turn]


def _recent_completed_events(events: Iterable[dict], limit: int) -> list[dict]:
    recent = deque(maxlen=limit)
    for turn in _iter_completed_conversation_turns(events):
        for event in turn:
            recent.append(event)
    return list(recent)


def _recall_conversation_events(events: Iterable[dict], query: str, limit: int) -> list[dict]:
    q_units = recall_units(query)
    q_compact = recall_compact(query)
    if not q_units and len(q_compact) < 2:
        return []
    candidate_cap = max(32, limit * 8)
    heap = []
    for turn in _iter_completed_conversation_turns(events):
        text = "\n".join(str(event.get("summary", "")) for event in turn)
        units = recall_units(text)
        compact = recall_compact(text)
        overlap = len(q_units & units)
        phrase = bool(q_compact and len(q_compact) >= 4 and q_compact in compact)
        if overlap == 0 and not phrase:
            continue
        score = overlap * 10 + (80 if phrase else 0)
        seq = turn[-1].get("sequence", 0)
        item = (score, seq, turn)
        if len(heap) < candidate_cap:
            heapq.heappush(heap, item)
        elif (score, seq) > (heap[0][0], heap[0][1]):
            heapq.heapreplace(heap, item)
    ranked = sorted(heap, key=lambda item: (-item[0], -item[1]))
    selected = []
    budget = 11000
    turns_used = 0
    for _score, _seq, turn in ranked:
        if turns_used >= limit:
            break
        encoded = json.dumps(
            list(turn), sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
        if len(encoded) > budget:
            continue
        selected.extend(turn)
        budget -= len(encoded)
        turns_used += 1
    selected.sort(key=lambda event: event.get("sequence", 0))
    return selected


from .fk_audit_cognition import (
    _canonical_obj,
    _one_trait_transition,
    _personality_state,
    _belief_revision_hash,
    _parse_belief_revision,
    _belief_states,
    _belief_public,
    _query_current_beliefs,
    _skill_revision_hash,
    _capability_proof,
    _parse_skill_revision,
    _skill_states,
    _skill_public,
    _query_current_skills,
)

def _ensure_conversation_index(
    state_path: str, log_path: str, index_path: str | None
) -> tuple[dict, bool]:
    state = recover_canonical_tail(state_path, log_path)
    if index_path is None:
        return state, False
    if index_matches_state(index_path, state["generation"], state["digest"]):
        return state, True
    # A stale/corrupt derived index never becomes authority: fully verify canonical history, then rebuild.
    state = recover_canonical(state_path, log_path)
    try:
        generation, digest = rebuild_conversation_index(index_path, iter_canonical_events(log_path))
        if (generation, digest) != (state["generation"], state["digest"]):
            raise ConversationIndexError("INDEX_HEAD_MISMATCH")
        return state, True
    except ConversationIndexError:
        return state, False


def _commit_with_index(state_path: str, log_path: str, event: dict, index_path: str | None) -> dict:
    state = commit_event(state_path, event, canonical_log_path=log_path)
    if index_path is not None:
        try:
            index_append_event(index_path, event, state["generation"], state["digest"])
        except ConversationIndexError:
            try:
                generation, digest = rebuild_conversation_index(
                    index_path, iter_canonical_events(log_path)
                )
                if (generation, digest) != (state["generation"], state["digest"]):
                    raise ConversationIndexError("INDEX_HEAD_MISMATCH")
            except ConversationIndexError:
                pass
    return state


def _cognitive_veto(exc: KAuditWitnessError) -> dict:
    reason = str(exc)
    return _veto(
        "COGNITIVE_STATE_INVALID" if reason == "COGNITIVE_STATE_INVALID" else "WITNESS_INVALID"
    )


def _commit_veto(exc: KAuditWitnessError) -> dict:
    reason = str(exc)
    if reason == "COGNITIVE_STATE_INVALID":
        return _veto(reason)
    return _veto(reason if reason in STABLE_REASONS else "WITNESS_INVALID")


def _dispatch_history(
    request: dict, state_path: str, log_path: str, index_path: str | None
) -> dict:
    try:
        _state, indexed = _ensure_conversation_index(state_path, log_path, index_path)
        if indexed:
            try:
                events = index_recent_events(index_path, request["limit"])
            except ConversationIndexError:
                recover_canonical(state_path, log_path)
                events = _recent_completed_events(iter_canonical_events(log_path), request["limit"])
        else:
            recover_canonical(state_path, log_path)
            events = _recent_completed_events(iter_canonical_events(log_path), request["limit"])
        return {"schema": "FK_AUDIT.HISTORY.RECEIPT.2", "outcome": "HISTORY", "events": events}
    except KAuditWitnessError:
        return _veto("WITNESS_INVALID")


def _dispatch_recall(request: dict, state_path: str, log_path: str, index_path: str | None) -> dict:
    try:
        _state, indexed = _ensure_conversation_index(state_path, log_path, index_path)
        if indexed:
            try:
                events = index_recall_events(index_path, request["query"], request["limit"])
            except ConversationIndexError:
                recover_canonical(state_path, log_path)
                events = _recall_conversation_events(
                    iter_canonical_events(log_path), request["query"], request["limit"]
                )
        else:
            recover_canonical(state_path, log_path)
            events = _recall_conversation_events(
                iter_canonical_events(log_path), request["query"], request["limit"]
            )
        return {"schema": "FK_AUDIT.RECALL.RECEIPT.2", "outcome": "RECALL", "events": events}
    except KAuditWitnessError:
        return _veto("WITNESS_INVALID")


def _dispatch_beliefs(request: dict, state_path: str, log_path: str) -> dict:
    try:
        recover_canonical(state_path, log_path)
        beliefs = _query_current_beliefs(
            iter_canonical_events(log_path), request["query"], request["limit"]
        )
        return {"schema": "FK_AUDIT.BELIEFS.RECEIPT.2", "outcome": "BELIEFS", "beliefs": beliefs}
    except KAuditWitnessError as exc:
        return _cognitive_veto(exc)


def _dispatch_belief_commit(
    request: dict, state_path: str, log_path: str, index_path: str | None
) -> dict:
    try:
        recover_canonical(state_path, log_path)
        event = request["event"]
        if event.get("subject") != "belief_revision":
            raise KAuditWitnessError("COGNITIVE_STATE_INVALID")

        def candidate_events():
            yield from iter_canonical_events(log_path)
            yield event

        _belief_states(candidate_events())
        state = _commit_with_index(state_path, log_path, event, index_path)
        return _state_receipt("COMMITTED", state)
    except KAuditWitnessError as exc:
        return _commit_veto(exc)


def _dispatch_skills(request: dict, state_path: str, log_path: str) -> dict:
    try:
        recover_canonical(state_path, log_path)
        skills = _query_current_skills(
            iter_canonical_events(log_path), request["query"], request["limit"]
        )
        return {"schema": "FK_AUDIT.SKILLS.RECEIPT.2", "outcome": "SKILLS", "skills": skills}
    except KAuditWitnessError as exc:
        return _cognitive_veto(exc)


def _dispatch_skill_commit(
    request: dict, state_path: str, log_path: str, index_path: str | None
) -> dict:
    try:
        recover_canonical(state_path, log_path)
        event = request["event"]
        if event.get("subject") != "skill_revision":
            raise KAuditWitnessError("COGNITIVE_STATE_INVALID")

        def candidate_events():
            yield from iter_canonical_events(log_path)
            yield event

        _skill_states(candidate_events())
        state = _commit_with_index(state_path, log_path, event, index_path)
        return _state_receipt("COMMITTED", state)
    except KAuditWitnessError as exc:
        return _commit_veto(exc)


def _dispatch_personality(request: dict, state_path: str, log_path: str) -> dict:
    try:
        recover_canonical(state_path, log_path)
        return _personality_state(
            iter_canonical_events(log_path), request["core_state"], request["core_sha256"]
        )
    except KAuditWitnessError as exc:
        return _cognitive_veto(exc)


def _dispatch_personality_commit(
    request: dict, state_path: str, log_path: str, index_path: str | None
) -> dict:
    try:
        recover_canonical(state_path, log_path)
        event = request["event"]
        if event.get("subject") != "personality_revision":
            raise KAuditWitnessError("COGNITIVE_STATE_INVALID")

        def candidate_events():
            yield from iter_canonical_events(log_path)
            yield event

        _personality_state(candidate_events(), request["core_state"], request["core_sha256"])
        state = _commit_with_index(state_path, log_path, event, index_path)
        return _state_receipt("COMMITTED", state)
    except KAuditWitnessError as exc:
        return _commit_veto(exc)


def _dispatch_generic_commit(
    request: dict, state_path: str, log_path: str, index_path: str | None
) -> dict:
    event = request["event"]
    if event.get("subject") in RESERVED_COGNITIVE_SUBJECTS:
        return _veto("COGNITIVE_COMMIT_REQUIRED")
    try:
        state = _commit_with_index(state_path, log_path, event, index_path)
        return _state_receipt("COMMITTED", state)
    except KAuditWitnessError as exc:
        return _commit_veto(exc)


def _dispatch(request: dict, state_path: str, log_path: str, index_path: str | None = None) -> dict:
    schema = request["schema"]
    if schema == "FK_AUDIT.QUERY.2":
        try:
            return _state_receipt("STATE", recover_canonical(state_path, log_path))
        except KAuditWitnessError:
            return _veto("WITNESS_INVALID")
    if schema == "FK_AUDIT.HISTORY.2":
        return _dispatch_history(request, state_path, log_path, index_path)
    if schema == "FK_AUDIT.RECALL.2":
        return _dispatch_recall(request, state_path, log_path, index_path)
    if schema == "FK_AUDIT.BELIEFS.2":
        return _dispatch_beliefs(request, state_path, log_path)
    if schema == "FK_AUDIT.BELIEF_COMMIT.2":
        return _dispatch_belief_commit(request, state_path, log_path, index_path)
    if schema == "FK_AUDIT.SKILLS.2":
        return _dispatch_skills(request, state_path, log_path)
    if schema == "FK_AUDIT.SKILL_COMMIT.2":
        return _dispatch_skill_commit(request, state_path, log_path, index_path)
    if schema == "FK_AUDIT.PERSONALITY.2":
        return _dispatch_personality(request, state_path, log_path)
    if schema == "FK_AUDIT.PERSONALITY_COMMIT.2":
        return _dispatch_personality_commit(request, state_path, log_path, index_path)
    return _dispatch_generic_commit(request, state_path, log_path, index_path)


def _validate_peer_policy(
    allowed_uid: int | None, allowed_cgroup_unit: str | None
) -> tuple[int | None, str | None]:
    if allowed_uid is None and allowed_cgroup_unit is None:
        allowed_uid = os.getuid()
    if allowed_uid is not None and allowed_cgroup_unit is not None:
        raise FKAuditGatewayError("ambiguous peer policy")
    if allowed_uid is not None and (type(allowed_uid) is not int or allowed_uid < 0):
        raise FKAuditGatewayError("invalid allowed uid")
    if allowed_cgroup_unit is not None:
        try:
            cgroup_contains_unit("", allowed_cgroup_unit)
        except FKPeerIdentityError as exc:
            raise FKAuditGatewayError("invalid cgroup unit") from exc
    return allowed_uid, allowed_cgroup_unit


def handle_connection(
    conn: socket.socket,
    *,
    state_path: str,
    log_path: str | None = None,
    index_path: str | None = None,
    allowed_uid: int | None = None,
    allowed_cgroup_unit: str | None = None,
) -> None:
    if log_path is None:
        log_path = (
            DEFAULT_LOG_PATH if state_path == DEFAULT_STATE_PATH else state_path + ".events.jsonl"
        )
    try:
        pid, uid, _gid = peer_credentials(conn)
        request = parse_request(_recv_line(conn))
        try:
            allowed = authorize_peer(
                pid=pid, uid=uid, allowed_uid=allowed_uid, allowed_cgroup_unit=allowed_cgroup_unit
            )
        except FKPeerIdentityError:
            allowed = False
        if not allowed:
            _send(conn, _veto("PEER_AUTH_DENY"))
            return
        _send(conn, _dispatch(request, state_path, log_path, index_path))
    except (FKAuditGatewayError, FKPeerIdentityError):
        _send(conn, _veto("INVALID_REQUEST"))


def serve_once(
    *,
    address: str = DEFAULT_ADDRESS,
    state_path: str = DEFAULT_STATE_PATH,
    log_path: str | None = None,
    index_path: str | None = None,
    allowed_uid: int | None = None,
    allowed_cgroup_unit: str | None = None,
    ready: Callable[[], None] | None = None,
) -> None:
    allowed_uid, allowed_cgroup_unit = _validate_peer_policy(allowed_uid, allowed_cgroup_unit)
    if log_path is None:
        log_path = (
            DEFAULT_LOG_PATH if state_path == DEFAULT_STATE_PATH else state_path + ".events.jsonl"
        )
    initialize_state(state_path)
    state = recover_canonical(state_path, log_path)
    if index_path is not None:
        generation, digest = rebuild_conversation_index(index_path, iter_canonical_events(log_path))
        if (generation, digest) != (state["generation"], state["digest"]):
            raise FKAuditGatewayError("conversation index head mismatch")
    if not isinstance(address, str) or not address.startswith("\0") or len(address.encode()) > 100:
        raise FKAuditGatewayError("abstract AF_UNIX address required")
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        server.bind(address)
        server.listen(4)
        if ready is not None:
            ready()
        conn, _ = server.accept()
        with conn:
            handle_connection(
                conn,
                state_path=state_path,
                log_path=log_path,
                index_path=index_path,
                allowed_uid=allowed_uid,
                allowed_cgroup_unit=allowed_cgroup_unit,
            )
    finally:
        server.close()


def serve_forever(
    *,
    address: str = DEFAULT_ADDRESS,
    state_path: str = DEFAULT_STATE_PATH,
    log_path: str | None = None,
    index_path: str | None = None,
    allowed_uid: int | None = None,
    allowed_cgroup_unit: str | None = None,
    stop_event: object | None = None,
    ready: Callable[[], None] | None = None,
) -> None:
    allowed_uid, allowed_cgroup_unit = _validate_peer_policy(allowed_uid, allowed_cgroup_unit)
    if log_path is None:
        log_path = (
            DEFAULT_LOG_PATH if state_path == DEFAULT_STATE_PATH else state_path + ".events.jsonl"
        )
    initialize_state(state_path)
    state = recover_canonical(state_path, log_path)
    if index_path is not None:
        generation, digest = rebuild_conversation_index(index_path, iter_canonical_events(log_path))
        if (generation, digest) != (state["generation"], state["digest"]):
            raise FKAuditGatewayError("conversation index head mismatch")
    if not isinstance(address, str) or not address.startswith("\0") or len(address.encode()) > 100:
        raise FKAuditGatewayError("abstract AF_UNIX address required")
    if stop_event is not None and not callable(getattr(stop_event, "is_set", None)):
        raise FKAuditGatewayError("invalid stop event")
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        server.bind(address)
        server.listen(16)
        if stop_event is not None:
            server.settimeout(0.1)
        if ready is not None:
            ready()
        while stop_event is None or not stop_event.is_set():
            try:
                conn, _ = server.accept()
            except socket.timeout:
                continue
            with conn:
                handle_connection(
                    conn,
                    state_path=state_path,
                    log_path=log_path,
                    index_path=index_path,
                    allowed_uid=allowed_uid,
                    allowed_cgroup_unit=allowed_cgroup_unit,
                )
    finally:
        server.close()
